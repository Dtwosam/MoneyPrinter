[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AuthorizationFile,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$AuthorizationSha256,

    [switch]$OperatorApproved
)

$ErrorActionPreference = 'Stop'
if (-not $OperatorApproved) {
    throw "Explicit operator approval is required."
}

$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository '.venv/bin/python'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Printer V1 repository interpreter is unavailable."
}

Push-Location -LiteralPath $repository
try {
    & $python -m printer_v1.operator_cli.window_15m_one_shot_wrapper `
        --authorization-file $AuthorizationFile `
        --authorization-sha256 $AuthorizationSha256 `
        --operator-approved
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
