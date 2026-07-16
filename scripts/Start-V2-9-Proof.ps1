[CmdletBinding()]
param(
    [switch]$OperatorApproved,
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 999)]
    [int]$AttemptNumber,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$HeartbeatSeconds = 30,
    [int]$LeaseSeconds = 90,
    [int]$CooperativeStopGraceSeconds = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $OperatorApproved) {
    throw 'V2-9 proof launch requires -OperatorApproved.'
}
if ($HeartbeatSeconds -lt 10 -or $LeaseSeconds -le ($HeartbeatSeconds * 2)) {
    throw 'LeaseSeconds must be more than twice HeartbeatSeconds.'
}
if ($CooperativeStopGraceSeconds -lt 10) {
    throw 'CooperativeStopGraceSeconds must be at least 10.'
}

$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$python = (Get-Command python).Source
$runs = Join-Path $root 'operator-runs'
$persistent = Join-Path $root 'data\printer_v1.sqlite3'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')
$executionId = [Guid]::NewGuid().ToString()
$artifactPrefix = "v2-9-attempt$AttemptNumber-$stamp"
$proof = Join-Path $runs "$artifactPrefix.sqlite3"
$backup = Join-Path $runs "$artifactPrefix.backup.sqlite3"
$prepareLog = Join-Path $runs "$artifactPrefix-preparation.json"
$stdoutLog = Join-Path $runs "$artifactPrefix-stdout.log"
$stderrLog = Join-Path $runs "$artifactPrefix-stderr.log"
$launcherLog = Join-Path $runs "$artifactPrefix-launcher.jsonl"
$lockPath = Join-Path $runs 'v2-9-one-proof.lock.json'

New-Item -ItemType Directory -Force -Path $runs | Out-Null
Set-Location -LiteralPath $root

function Write-LauncherEvent {
    param(
        [Parameter(Mandatory = $true)][string]$Event,
        [hashtable]$Details = @{}
    )
    $record = [ordered]@{
        at = [DateTime]::UtcNow.ToString('o')
        event = $Event
        execution_id = $executionId
        attempt_number = $AttemptNumber
        details = $Details
    }
    $record | ConvertTo-Json -Compress -Depth 8 |
        Add-Content -LiteralPath $launcherLog -Encoding utf8
}

function Invoke-Supervision {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    $output = @(& $python -m printer_v1.operator_cli.proof_supervision @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        Write-LauncherEvent -Event 'SUPERVISION_OUTPUT' -Details @{
            command = $Arguments[0]
            text = [string]$line
        }
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function Request-CooperativeStop {
    param([Parameter(Mandatory = $true)][string]$Reason)
    $result = Invoke-Supervision -Arguments @(
        'request-stop',
        '--operator-approved',
        '--lock-path', $lockPath,
        '--execution-id', $executionId,
        '--reason', $Reason
    )
    if ($result.ExitCode -ne 0) {
        Write-LauncherEvent -Event 'COOPERATIVE_STOP_REQUEST_FAILED' -Details @{
            reason = $Reason
            output = $result.Output
        }
        return $false
    }
    Write-LauncherEvent -Event 'COOPERATIVE_STOP_REQUESTED' -Details @{
        reason = $Reason
    }
    return $true
}

Write-LauncherEvent -Event 'LAUNCHER_START' -Details @{
    artifact_prefix = $artifactPrefix
    heartbeat_seconds = $HeartbeatSeconds
    lease_seconds = $LeaseSeconds
}

$lockResult = Invoke-Supervision -Arguments @(
    'inspect-lock', '--lock-path', $lockPath
)
if ($lockResult.ExitCode -ne 0) {
    throw "One-proof lock inspection failed: $($lockResult.Output)"
}
$lockReport = $lockResult.Output | ConvertFrom-Json
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

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PrinterPowerState {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint esFlags);
}
'@
$ES_CONTINUOUS = [uint32]2147483648
$ES_SYSTEM_REQUIRED = [uint32]1

$created = Invoke-Supervision -Arguments @(
    'create',
    '--operator-approved',
    '--db-path', $proof,
    '--backup-proof-path', $backup,
    '--execution-id', $executionId,
    '--owner-launcher-type', 'MANUAL_POWERSHELL',
    '--lock-path', $lockPath,
    '--stdout-log-path', $stdoutLog,
    '--stderr-log-path', $stderrLog,
    '--lease-seconds', [string]$LeaseSeconds
)
if ($created.ExitCode -ne 0) {
    throw "Durable supervision could not be created: $($created.Output)"
}

$proofProcess = $null
$operatorCancelled = $false
$launcherFaultReason = $null
$launcherError = $null
$cooperativeStopRequested = $false
$heartbeatFailures = 0
$lastHeartbeatSuccessUtc = [DateTime]::UtcNow
$forcedTermination = $false

try {
    # Exactly one unbuffered proof process is launched. There is no retry loop.
    $proofProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @(
            '-u',
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
    Write-LauncherEvent -Event 'CHILD_STARTED' -Details @{ pid = $proofProcess.Id }

    [PrinterPowerState]::SetThreadExecutionState(
        $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED
    ) | Out-Null

    while (-not $proofProcess.HasExited) {
        $heartbeat = Invoke-Supervision -Arguments @(
            'heartbeat',
            '--lock-path', $lockPath,
            '--execution-id', $executionId,
            '--pid', [string]$proofProcess.Id,
            '--lease-seconds', [string]$LeaseSeconds
        )
        if ($heartbeat.ExitCode -eq 0) {
            $heartbeatFailures = 0
            $lastHeartbeatSuccessUtc = [DateTime]::UtcNow
            Write-LauncherEvent -Event 'HEARTBEAT_RENEWED' -Details @{
                pid = $proofProcess.Id
            }
        }
        else {
            $heartbeatFailures += 1
            Write-LauncherEvent -Event 'HEARTBEAT_RENEWAL_FAILED' -Details @{
                consecutive_failures = $heartbeatFailures
                output = $heartbeat.Output
            }
            # One failed renewal never kills or stops a process with a valid lease.
            if ($heartbeatFailures -ge 2 -and -not $cooperativeStopRequested) {
                $launcherFaultReason = 'SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED'
                $cooperativeStopRequested = Request-CooperativeStop -Reason $launcherFaultReason
            }
        }

        for ($second = 0; $second -lt $HeartbeatSeconds; $second += 1) {
            Start-Sleep -Seconds 1
            $proofProcess.Refresh()
            if ($proofProcess.HasExited) {
                break
            }
        }

        if ($null -ne $launcherFaultReason -and -not $proofProcess.HasExited) {
            $forceAfter = $lastHeartbeatSuccessUtc.AddSeconds(
                $LeaseSeconds + $CooperativeStopGraceSeconds
            )
            if ([DateTime]::UtcNow -ge $forceAfter) {
                Write-LauncherEvent -Event 'FORCED_TERMINATION_AFTER_EXPIRED_LEASE' -Details @{
                    reason = $launcherFaultReason
                    pid = $proofProcess.Id
                }
                Stop-Process -Id $proofProcess.Id -Force
                $proofProcess.WaitForExit()
                $forcedTermination = $true
            }
        }
    }
}
catch [System.Management.Automation.PipelineStoppedException] {
    # This branch alone represents a genuine operator Ctrl+C.
    $operatorCancelled = $true
    $launcherError = $_
    $cooperativeStopRequested = Request-CooperativeStop -Reason 'SAFE_STOP_OPERATOR_INTERRUPTED'
}
catch {
    $launcherError = $_
    $launcherFaultReason = "SUPERVISION_LAUNCHER_FAULT:$($_.Exception.Message)"
    Write-LauncherEvent -Event 'LAUNCHER_FAULT' -Details @{
        reason = $launcherFaultReason
    }
    if ($null -ne $proofProcess -and -not $proofProcess.HasExited) {
        $cooperativeStopRequested = Request-CooperativeStop -Reason $launcherFaultReason
    }
}
finally {
    [PrinterPowerState]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null

    if ($null -ne $proofProcess -and -not $proofProcess.HasExited -and
        ($operatorCancelled -or $null -ne $launcherFaultReason)) {
        $deadline = [DateTime]::UtcNow.AddSeconds(
            $LeaseSeconds + $CooperativeStopGraceSeconds
        )
        while (-not $proofProcess.HasExited -and [DateTime]::UtcNow -lt $deadline) {
            Start-Sleep -Seconds 1
            $proofProcess.Refresh()
        }
        if (-not $proofProcess.HasExited) {
            Write-LauncherEvent -Event 'FORCED_TERMINATION_AFTER_COOPERATIVE_GRACE' -Details @{
                operator_cancelled = $operatorCancelled
                reason = $launcherFaultReason
                pid = $proofProcess.Id
            }
            Stop-Process -Id $proofProcess.Id -Force
            $proofProcess.WaitForExit()
            $forcedTermination = $true
        }
    }
}

$finalResult = Invoke-Supervision -Arguments @(
    'inspect', '--db-path', $proof, '--execution-id', $executionId
)
if ($finalResult.ExitCode -ne 0) {
    throw "Final supervision inspection failed: $($finalResult.Output)"
}
$final = $finalResult.Output | ConvertFrom-Json

if ($final.execution_status -ne 'TERMINAL') {
    if ($operatorCancelled -and ($null -eq $proofProcess -or $proofProcess.HasExited)) {
        $cleanup = Invoke-Supervision -Arguments @(
            'cancel', '--operator-approved', '--db-path', $proof,
            '--execution-id', $executionId
        )
        if ($cleanup.ExitCode -ne 0) {
            throw "Operator cancellation cleanup failed: $($cleanup.Output)"
        }
    }
    elseif ($null -ne $launcherFaultReason -and
        ($null -eq $proofProcess -or $proofProcess.HasExited)) {
        $cleanup = Invoke-Supervision -Arguments @(
            'stop', '--operator-approved', '--db-path', $proof,
            '--execution-id', $executionId, '--reason', $launcherFaultReason
        )
        if ($cleanup.ExitCode -ne 0) {
            throw "Launcher-fault cleanup failed: $($cleanup.Output)"
        }
    }
    else {
        do {
            Start-Sleep -Seconds 1
            $finalResult = Invoke-Supervision -Arguments @(
                'inspect', '--db-path', $proof, '--execution-id', $executionId
            )
            if ($finalResult.ExitCode -ne 0) {
                throw "Abandoned-run inspection failed: $($finalResult.Output)"
            }
            $final = $finalResult.Output | ConvertFrom-Json
        } until ($final.lease_expired)

        $recovery = Invoke-Supervision -Arguments @(
            'recover', '--operator-approved', '--db-path', $proof,
            '--execution-id', $executionId
        )
        if ($recovery.ExitCode -ne 0) {
            throw "Abandoned-run recovery failed: $($recovery.Output)"
        }
    }

    $finalResult = Invoke-Supervision -Arguments @(
        'inspect', '--db-path', $proof, '--execution-id', $executionId
    )
    if ($finalResult.ExitCode -ne 0) {
        throw "Post-cleanup supervision inspection failed: $($finalResult.Output)"
    }
    $final = $finalResult.Output | ConvertFrom-Json
}

Write-LauncherEvent -Event 'LAUNCHER_FINISH' -Details @{
    terminal_status = $final.terminal_status
    first_stop_reason = $final.first_stop_reason
    child_exit_code = if ($null -ne $proofProcess -and $proofProcess.HasExited) {
        $proofProcess.ExitCode
    } else {
        $null
    }
    forced_termination = $forcedTermination
}

[ordered]@{
    execution_id = $executionId
    attempt_number = $AttemptNumber
    artifact_prefix = $artifactPrefix
    terminal_status = $final.terminal_status
    first_stop_reason = $final.first_stop_reason
    stdout_log = $stdoutLog
    stderr_log = $stderrLog
    launcher_log = $launcherLog
    preparation_log = $prepareLog
    automatic_retries = 0
    forced_termination = $forcedTermination
    launcher_error = if ($null -ne $launcherError) {
        $launcherError.Exception.Message
    } else {
        $null
    }
} | ConvertTo-Json -Depth 4
