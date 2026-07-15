[CmdletBinding()]
param(
    [switch]$OperatorApproved,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$HeartbeatSeconds = 30,
    [int]$LeaseSeconds = 90
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $OperatorApproved) {
    throw 'V2-9 proof launch requires -OperatorApproved.'
}
if ($HeartbeatSeconds -lt 10 -or $LeaseSeconds -le ($HeartbeatSeconds * 2)) {
    throw 'LeaseSeconds must be more than twice HeartbeatSeconds.'
}

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = (Get-Command python).Source
$runs = Join-Path $root 'operator-runs'
$persistent = Join-Path $root 'data\printer_v1.sqlite3'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$executionId = [Guid]::NewGuid().ToString()
$proof = Join-Path $runs "v2-9-attempt4-$stamp.sqlite3"
$backup = Join-Path $runs "v2-9-attempt4-$stamp.backup.sqlite3"
$prepareLog = Join-Path $runs "v2-9-attempt4-$stamp-preparation.json"
$stdoutLog = Join-Path $runs "v2-9-attempt4-$stamp-stdout.log"
$stderrLog = Join-Path $runs "v2-9-attempt4-$stamp-stderr.log"
$lockPath = Join-Path $runs 'v2-9-one-proof.lock.json'

New-Item -ItemType Directory -Force -Path $runs | Out-Null
Set-Location -LiteralPath $root

$lockReport = & $python -m printer_v1.operator_cli.proof_supervision inspect-lock --lock-path $lockPath |
    ConvertFrom-Json
if (-not $lockReport.available) {
    throw "One V2-9 proof is active or unresolved: $($lockReport.execution_id)"
}

# Sole canonical V2-9.1 preparation path.
$preparation = & $python -m printer_v1.operator_cli.proof_db_schema_readiness `
    --operator-approved `
    --persistent-db-path $persistent `
    --proof-db-path $proof `
    --backup-proof-path $backup
$preparation | Set-Content -LiteralPath $prepareLog -Encoding utf8
$prepared = $preparation | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $prepared.status -ne 'PROOF_DB_SCHEMA_READY') {
    throw 'Canonical V2-9.1 proof preparation failed.'
}
if (-not $prepared.proof_backup_byte_identical -or
    -not $prepared.persistent_unchanged) {
    throw 'Proof/backup equality or persistent isolation failed.'
}
if (-not $prepared.proof_validation.runtime_ready -or
    -not $prepared.backup_validation.runtime_ready) {
    throw 'Proof or backup runtime schema validation failed.'
}

# One request per endpoint, no retry or rotation. Runtime evidence requests
# remain Source-Governor-owned and Central-Scheduler-owned.
$networkTargets = @(
    'https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1',
    'https://api.dexscreener.com/latest/dex/search?q=solana'
)
foreach ($target in $networkTargets) {
    $response = Invoke-WebRequest -Uri $target -Method Get `
        -TimeoutSec 15 -UseBasicParsing
    if ($response.StatusCode -ne 200) {
        throw "Network preflight failed for $target with HTTP $($response.StatusCode)."
    }
}

& $python -m printer_v1.operator_cli.proof_supervision create `
    --operator-approved `
    --db-path $proof `
    --backup-proof-path $backup `
    --execution-id $executionId `
    --owner-launcher-type MANUAL_POWERSHELL `
    --lock-path $lockPath `
    --stdout-log-path $stdoutLog `
    --stderr-log-path $stderrLog `
    --lease-seconds $LeaseSeconds | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Durable supervision could not be created.'
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PrinterPowerState {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
# PowerShell parses the hex literal 0x80000000 as a negative Int32
# (two's complement), and [uint32] performs a checked/range conversion
# that then throws "Cannot convert value "-2147483648" to type
# "System.UInt32"". The equivalent decimal literal is parsed as a
# positive Int64 and converts to UInt32 cleanly.
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1
$proofProcess = $null
$operatorCancelled = $false
$launcherError = $null

try {
    # Exactly one proof process is launched. There is no retry loop.
    $proofProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @(
            '-m',
            'printer_v1.operator_cli.proof_supervision',
            'run',
            '--operator-approved',
            '--db-path', $proof,
            '--backup-proof-path', $backup,
            '--execution-id', $executionId
        ) `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -NoNewWindow `
        -PassThru

    [PrinterPowerState]::SetThreadExecutionState(
        $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED
    ) | Out-Null
    while (-not $proofProcess.HasExited) {
        & $python -m printer_v1.operator_cli.proof_supervision heartbeat `
            --db-path $proof `
            --execution-id $executionId `
            --pid $proofProcess.Id `
            --lease-seconds $LeaseSeconds | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw 'Proof heartbeat failed.'
        }
        Start-Sleep -Seconds $HeartbeatSeconds
        $proofProcess.Refresh()
    }
}
catch [System.Management.Automation.PipelineStoppedException] {
    $operatorCancelled = $true
    $launcherError = $_
}
catch {
    $operatorCancelled = $true
    $launcherError = $_
}
finally {
    [PrinterPowerState]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
    if ($null -ne $proofProcess -and -not $proofProcess.HasExited) {
        $operatorCancelled = $true
        Stop-Process -Id $proofProcess.Id -Force
        $proofProcess.WaitForExit()
    }
    if ($operatorCancelled) {
        & $python -m printer_v1.operator_cli.proof_supervision cancel `
            --operator-approved `
            --db-path $proof `
            --execution-id $executionId | Out-Null
    }
}

$final = & $python -m printer_v1.operator_cli.proof_supervision inspect `
    --db-path $proof `
    --execution-id $executionId | ConvertFrom-Json
if ($final.execution_status -ne 'TERMINAL') {
    do {
        Start-Sleep -Seconds $HeartbeatSeconds
        $final = & $python -m printer_v1.operator_cli.proof_supervision inspect `
            --db-path $proof `
            --execution-id $executionId | ConvertFrom-Json
    } until ($final.lease_expired)
    & $python -m printer_v1.operator_cli.proof_supervision recover `
        --operator-approved `
        --db-path $proof `
        --execution-id $executionId | Out-Null
    $final = & $python -m printer_v1.operator_cli.proof_supervision inspect `
        --db-path $proof `
        --execution-id $executionId | ConvertFrom-Json
}

[ordered]@{
    execution_id = $executionId
    terminal_status = $final.terminal_status
    first_stop_reason = $final.first_stop_reason
    stdout_log = $stdoutLog
    stderr_log = $stderrLog
    preparation_log = $prepareLog
    automatic_retries = 0
    launcher_error = if ($null -ne $launcherError) {
        $launcherError.Exception.Message
    } else {
        $null
    }
} | ConvertTo-Json -Depth 4
