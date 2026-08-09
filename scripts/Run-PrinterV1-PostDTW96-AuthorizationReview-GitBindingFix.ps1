[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Repo = Join-Path $HOME 'Developer/MoneyPrinter'
$ReviewCommit = '01aeb89db63c3f7487a1401182ce1537e9813e0b'
$Python = Join-Path $Repo '.venv/bin/python'
$History = '/tmp/dtw96-auth-history-review-fixed.py'
$Review = '/tmp/dtw96-auth-independent-review-fixed.py'

function Fail([string]$Message) {
    Write-Error "BLOCKED: $Message"
    exit 3
}

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) { Fail 'repository unavailable' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { Fail 'repository Python unavailable' }

Push-Location -LiteralPath $Repo
try {
    $historyText = & git show "$ReviewCommit`:scripts/Check-PrinterV1-PostDTW96-AuthorizationHistory.py"
    if ($LASTEXITCODE -ne 0) { Fail 'could not read exact authorization-history reviewer' }
    [IO.File]::WriteAllText($History, (($historyText -join "`n") + "`n"))

    $reviewText = & git show "$ReviewCommit`:scripts/Review-PrinterV1-PostDTW96-FreshWindow15M-Authorization.py"
    if ($LASTEXITCODE -ne 0) { Fail 'could not read exact independent authorization reviewer' }
    $reviewText = ($reviewText -join "`n") + "`n"

    $old = @'
        if document.get("authorized_git") != {"branch": BRANCH, "head": HEAD}:
            raise RuntimeError("authorization Git binding mismatch")
'@
    $new = @'
        authorized_git = document.get("authorized_git")
        if not isinstance(authorized_git, dict):
            raise RuntimeError("authorization Git binding is not an object")
        if authorized_git.get("branch") != BRANCH or authorized_git.get("head") != HEAD:
            raise RuntimeError(
                "authorization Git binding mismatch: "
                f"branch={authorized_git.get('branch')!r} head={authorized_git.get('head')!r}"
            )
'@

    $count = ([regex]::Matches($reviewText, [regex]::Escape($old))).Count
    if ($count -ne 1) { Fail "Git-binding correction anchor mismatch: $count" }
    $reviewText = $reviewText.Replace($old, $new)
    [IO.File]::WriteAllText($Review, $reviewText)

    & $Python $History
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python $Review
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
