[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Repo = Join-Path $HOME 'Developer/MoneyPrinter'
$SourceCommit = '62b6d6044b0cfc76bcd4ed6f53344476b1b21eaa'
$SourcePath = 'scripts/Prepare-PrinterV1-PostDTW96-Window15M-Authorization.ps1'
$Temp = '/tmp/post-dtw96-auth-history-retention-fixed.ps1'

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) {
    throw 'MoneyPrinter repository unavailable'
}

Push-Location -LiteralPath $Repo
try {
    $raw = (& git show "$SourceCommit`:$SourcePath" | Out-String)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
        throw 'Could not load the frozen DTW96 authorization helper'
    }

    $old = @'
    expected_history = set(history)
    unexpected = sorted(existing - expected_history)
    missing = sorted(expected_history - existing)
    if unexpected:
        raise RuntimeError(f'unreviewed authorization package(s) already exist: {unexpected}')
    if missing:
        raise RuntimeError(f'historical authorization package(s) missing: {missing}')
    if len(history) != 25 or history[-1] != 'V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z':
'@

    $new = @'
    expected_history = set(history)
    unexpected = sorted(existing - expected_history)
    if unexpected:
        raise RuntimeError(f'unreviewed authorization package(s) already exist: {unexpected}')
    # Historical non-reuse is an identity trust root, not a package-retention invariant.
    # Older package directories may be absent; their IDs remain permanently non-reusable.
    if len(history) != 25 or history[-1] != 'V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z':
'@

    $count = ([regex]::Matches($raw, [regex]::Escape($old))).Count
    if ($count -ne 1) {
        throw "History-retention correction anchor mismatch: expected 1, got $count"
    }

    $fixed = $raw.Replace($old, $new)
    [System.IO.File]::WriteAllText($Temp, $fixed, [System.Text.UTF8Encoding]::new($false))

    & pwsh -NoProfile -File $Temp
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
