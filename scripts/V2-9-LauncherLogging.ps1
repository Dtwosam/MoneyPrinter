# V2-9.4.3 launcher logging and native-output capture reliability boundary.
#
# Dot-sourced by Start-V2-9-Proof.ps1. Contains no proof-runtime, source,
# budget, cadence, schema, or safety-lock logic.
#
# Attempt 6 proved the fault this boundary exists to prevent: a filesystem
# heartbeat succeeded and atomically renewed the lease, then the PowerShell
# native-output capture/logging boundary threw ("Stream was not readable").
# Because logging ran inside the supervision-output loop and the catch path
# reused the same logger, the successful heartbeat result was discarded, the
# fault could not record itself, and supervision silently stopped while a
# healthy child ran on for hours.
#
# Contract enforced here:
#   * launcher-event logging can never throw;
#   * a logging fault never discards an already-successful command result,
#     never stops heartbeat renewal, never kills a healthy child, and never
#     becomes OPERATOR_CANCELLED;
#   * the exact first fault cause is captured once and never replaced;
#   * a durable fallback diagnostic path does not depend on the primary logger;
#   * every launcher JSONL record is appended as one complete line.

$script:LauncherLogPath = $null
$script:LauncherFallbackPath = $null
$script:LauncherExecutionId = $null
$script:LauncherAttemptNumber = 0
$script:LauncherLogHealthy = $true
$script:LauncherLogFirstFault = $null
$script:LauncherUtf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Initialize-LauncherLogging {
    param(
        [Parameter(Mandatory = $true)][string]$LauncherLogPath,
        [Parameter(Mandatory = $true)][string]$FallbackLogPath,
        [Parameter(Mandatory = $true)][string]$ExecutionId,
        [Parameter(Mandatory = $true)][int]$AttemptNumber
    )
    $script:LauncherLogPath = $LauncherLogPath
    $script:LauncherFallbackPath = $FallbackLogPath
    $script:LauncherExecutionId = $ExecutionId
    $script:LauncherAttemptNumber = $AttemptNumber
    $script:LauncherLogHealthy = $true
    $script:LauncherLogFirstFault = $null
}

function Test-LauncherLogHealthy {
    return $script:LauncherLogHealthy
}

function Get-LauncherLogFirstFault {
    return $script:LauncherLogFirstFault
}

function Write-LauncherFallback {
    # Durable diagnostic path. Uses direct .NET file IO with no pipeline and no
    # dependency on the primary launcher logger, so it stays usable exactly when
    # the primary logger is the thing that failed. Never throws.
    param([Parameter(Mandatory = $true)][string]$Text)
    try {
        if ([string]::IsNullOrWhiteSpace($script:LauncherFallbackPath)) {
            return $false
        }
        [System.IO.File]::AppendAllText(
            $script:LauncherFallbackPath, ($Text + "`n"), $script:LauncherUtf8NoBom
        )
        return $true
    }
    catch {
        try {
            [Console]::Error.WriteLine("V2-9 launcher fallback log unavailable: $Text")
        }
        catch {
            # Last resort exhausted; never propagate a diagnostic failure.
        }
        return $false
    }
}

function Register-LauncherLogFault {
    # Records the exact first logging/capture fault once. A later fault never
    # replaces the original cause. Always mirrored to the fallback path.
    param(
        [Parameter(Mandatory = $true)]$ErrorRecord,
        [Parameter(Mandatory = $true)][string]$Boundary
    )
    $script:LauncherLogHealthy = $false
    if ($null -ne $script:LauncherLogFirstFault) {
        return $script:LauncherLogFirstFault
    }

    $exceptionType = $null
    $message = $null
    $categoryText = $null
    $errorId = $null
    $stackTrace = $null
    $positionMessage = $null
    $commandName = $null
    try { $message = [string]$ErrorRecord.Exception.Message } catch { $message = '<unavailable>' }
    try { $exceptionType = $ErrorRecord.Exception.GetType().FullName } catch { $exceptionType = '<unavailable>' }
    try { $categoryText = [string]$ErrorRecord.CategoryInfo } catch { $categoryText = '<unavailable>' }
    try { $errorId = [string]$ErrorRecord.FullyQualifiedErrorId } catch { $errorId = '<unavailable>' }
    try { $stackTrace = [string]$ErrorRecord.ScriptStackTrace } catch { $stackTrace = '<unavailable>' }
    try {
        if ($null -ne $ErrorRecord.InvocationInfo) {
            $positionMessage = [string]$ErrorRecord.InvocationInfo.PositionMessage
            $commandName = [string]$ErrorRecord.InvocationInfo.MyCommand
        }
    }
    catch {
        $positionMessage = '<unavailable>'
    }

    $detail = [ordered]@{
        at = [DateTime]::UtcNow.ToString('o')
        event = 'LAUNCHER_LOG_FAULT'
        execution_id = $script:LauncherExecutionId
        attempt_number = $script:LauncherAttemptNumber
        boundary = $Boundary
        exception_type = $exceptionType
        message = $message
        category = $categoryText
        fully_qualified_error_id = $errorId
        script_stack_trace = $stackTrace
        position_message = $positionMessage
        command = $commandName
        launcher_log_path = $script:LauncherLogPath
    }
    $script:LauncherLogFirstFault = $detail

    $json = $null
    try {
        $json = ConvertTo-Json -InputObject $detail -Compress -Depth 8
    }
    catch {
        $json = "{""event"":""LAUNCHER_LOG_FAULT"",""boundary"":""$Boundary"",""message"":""$message""}"
    }
    Write-LauncherFallback -Text $json | Out-Null
    return $script:LauncherLogFirstFault
}

function Write-LauncherEvent {
    # Never throws. A launcher-log write failure must not stop future heartbeat
    # renewals, kill a healthy child, become OPERATOR_CANCELLED, or replace the
    # original fault cause. Returns $true only when the record was persisted.
    param(
        [Parameter(Mandatory = $true)][string]$Event,
        [hashtable]$Details = @{}
    )
    try {
        $record = [ordered]@{
            at = [DateTime]::UtcNow.ToString('o')
            event = $Event
            execution_id = $script:LauncherExecutionId
            attempt_number = $script:LauncherAttemptNumber
            details = $Details
        }
        # No pipeline: a pipeline fault here previously surfaced as
        # PipelineStoppedException and was misread as an operator interrupt.
        $json = ConvertTo-Json -InputObject $record -Compress -Depth 8
        # One complete line per append: never leaves a partial JSON record.
        [System.IO.File]::AppendAllText(
            $script:LauncherLogPath, ($json + "`n"), $script:LauncherUtf8NoBom
        )
        return $true
    }
    catch {
        Register-LauncherLogFault -ErrorRecord $_ -Boundary "Write-LauncherEvent:$Event" | Out-Null
        return $false
    }
}

function Invoke-SupervisionCommand {
    # Separates the authoritative native supervision result from launcher-event
    # logging. The command result is captured and its exit code read before any
    # logging happens, so a logging or capture fault can never discard a
    # successful heartbeat/lease renewal.
    param(
        [Parameter(Mandatory = $true)][string]$PythonPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $global:LASTEXITCODE = $null
    $output = @()
    $captureFault = $null
    try {
        $output = @(& $PythonPath -m printer_v1.operator_cli.proof_supervision @Arguments 2>&1)
    }
    catch {
        $captureFault = $_
    }
    $exitCode = $global:LASTEXITCODE

    if ($null -ne $captureFault) {
        Register-LauncherLogFault -ErrorRecord $captureFault `
            -Boundary "Invoke-Supervision:capture:$($Arguments[0])" | Out-Null
    }

    foreach ($line in $output) {
        Write-LauncherEvent -Event 'SUPERVISION_OUTPUT' -Details @{
            command = $Arguments[0]
            text = [string]$line
        } | Out-Null
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
        CaptureFault = ($null -ne $captureFault)
    }
}
