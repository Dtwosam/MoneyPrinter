[CmdletBinding()]
param(
    [ValidateSet('preflight-only', 'run', 'status', 'cooperative-stop', 'recover-orphan', 'report-only')]
    [string]$Mode = 'preflight-only',
    [switch]$OperatorApproved
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository '.venv/bin/python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Printer V1 repository interpreter is unavailable."
}

$arguments = @(
    '-m',
    'printer_v1.operator_cli.operational_memory_factory_command',
    $Mode
)
if ($OperatorApproved) {
    $arguments += '--operator-approved'
}

Push-Location -LiteralPath $repository
try {
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
