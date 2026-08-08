[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Repo = Join-Path $HOME 'Developer/MoneyPrinter'
$AuthBranch = 'agent/v2-9-8b-post-dtw92-window15m-authorization-preparation'
$AuthHead = 'b85a42d404f41487497347a2e0fd9f778ff0ef2e'
$Db = Join-Path $Repo 'data/printer_v1.sqlite3'
$PreviousAuth = Join-Path $Repo 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z/final_authorization.json'
$Report = Join-Path $Repo 'docs/printer-v1-v2-9-8b-post-dtw92-fresh-window-15m-one-use-authorization-report.md'
$Python = Join-Path $Repo '.venv/bin/python'
$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$Evidence = Join-Path $HOME "PrinterV1OperatorReadiness/DTW93_WINDOW15M_AUTH_$Stamp"

function Fail([string]$Message) {
    Write-Error "BLOCKED: $Message"
    exit 3
}

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) { Fail 'repository is unavailable' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { Fail 'repository Python interpreter is unavailable' }

Push-Location -LiteralPath $Repo
try {
    & git diff --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked worktree is not clean' }
    & git diff --cached --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked index is not clean' }

    & git fetch origin $AuthBranch
    if ($LASTEXITCODE -ne 0) { Fail 'could not fetch authorization branch' }

    $RemoteHead = (& git rev-parse FETCH_HEAD).Trim()
    if ($RemoteHead -ne $AuthHead) { Fail "remote authorization HEAD drifted to $RemoteHead" }

    & git show-ref --verify --quiet "refs/heads/$AuthBranch"
    if ($LASTEXITCODE -eq 0) {
        & git switch $AuthBranch
    }
    else {
        & git switch --track -c $AuthBranch "origin/$AuthBranch"
    }
    if ($LASTEXITCODE -ne 0) { Fail 'could not switch to authorization branch' }

    & git merge --ff-only "origin/$AuthBranch"
    if ($LASTEXITCODE -ne 0) { Fail 'authorization branch cannot fast-forward cleanly' }

    $LiveHead = (& git rev-parse --verify HEAD).Trim()
    $LiveBranch = (& git rev-parse --abbrev-ref HEAD).Trim()
    if ($LiveHead -ne $AuthHead) { Fail "local HEAD is $LiveHead instead of $AuthHead" }
    if ($LiveBranch -ne $AuthBranch) { Fail "local branch is $LiveBranch instead of $AuthBranch" }

    & git diff --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked worktree changed during alignment' }
    & git diff --cached --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked index changed during alignment' }

    if (-not (Test-Path -LiteralPath $PreviousAuth -PathType Leaf)) { Fail 'previous V2 authorization template is unavailable' }
    if (-not (Test-Path -LiteralPath $Report -PathType Leaf)) { Fail 'authorization preparation report is unavailable' }

    New-Item -ItemType Directory -Path $Evidence -Force | Out-Null

    $GuardOut = Join-Path $Evidence 'migration_guard_prepare.json'
    $GuardErr = Join-Path $Evidence 'migration_guard_prepare.stderr.txt'
    & $Python -m printer_v1.operator_cli.pre_authorization_migration_ledger_guard prepare --db-path $Db --migrations-dir (Join-Path $Repo 'migrations') 1> $GuardOut 2> $GuardErr
    if ($LASTEXITCODE -ne 0) { Fail "migration/DB guard failed; see $GuardErr" }

    $PreflightOut = Join-Path $Evidence 'preflight_stdout.json'
    $PreflightErr = Join-Path $Evidence 'preflight_stderr.txt'
    & pwsh -NoProfile -File (Join-Path $Repo 'scripts/Start-PrinterV1-MemoryFactory.ps1') -Mode preflight-only -OperatorApproved 1> $PreflightOut 2> $PreflightErr
    if ($LASTEXITCODE -ne 0) { Fail "zero-runtime preflight failed; see $PreflightErr" }

    $env:PRINTER_DTW93_REPO = $Repo
    $env:PRINTER_DTW93_AUTH_BRANCH = $AuthBranch
    $env:PRINTER_DTW93_AUTH_HEAD = $AuthHead
    $env:PRINTER_DTW93_DB = $Db
    $env:PRINTER_DTW93_PREVIOUS_AUTH = $PreviousAuth
    $env:PRINTER_DTW93_REPORT = $Report
    $env:PRINTER_DTW93_EVIDENCE = $Evidence

    $Code = @'
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from printer_v1.operator_cli.authorization_temporal_validity import validate_authorization_temporal_validity
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    PACKAGE_BINDING_FIELDS,
    assert_migration_ledger_ready,
    package_binding_from_document,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import build_manifest_bytes
from printer_v1.operator_cli.git_provenance_authorization_manifest import validate_git_provenance_manifest_pre_marker

repo = Path(os.environ['PRINTER_DTW93_REPO']).resolve()
branch = os.environ['PRINTER_DTW93_AUTH_BRANCH']
head = os.environ['PRINTER_DTW93_AUTH_HEAD']
db = Path(os.environ['PRINTER_DTW93_DB']).resolve()
previous_auth = Path(os.environ['PRINTER_DTW93_PREVIOUS_AUTH']).resolve()
report = Path(os.environ['PRINTER_DTW93_REPORT']).resolve()
evidence = Path(os.environ['PRINTER_DTW93_EVIDENCE']).resolve()

expected_db = {
    'path': str(db),
    'sha256': 'e0dbc8c227eb640e242faae048f573f25eceffc63c7483ed722d95e6a7d7a4be',
    'size': 70082560,
    'inode': 1230526,
    'mtime_ns': 1786218584923920460,
    'migration_count': 53,
    'migration_head': '053_pilot_input_readiness_route_domain.sql',
}

phase = 'START'
auth_id = None
auth_file = None
package_written = False


def canonical_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def git(*args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def no_dupes(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


try:
    phase = 'GIT_RECHECK'
    if git('rev-parse', '--abbrev-ref', 'HEAD') != branch:
        raise RuntimeError('authorization branch mismatch')
    if git('rev-parse', '--verify', 'HEAD') != head:
        raise RuntimeError('authorization HEAD mismatch')

    for args, label in [
        (('diff', '--quiet', '--no-ext-diff', '--'), 'unstaged tracked changes'),
        (('diff', '--cached', '--quiet', '--no-ext-diff', '--'), 'staged changes'),
    ]:
        rc = subprocess.run(['git', *args], cwd=repo).returncode
        if rc != 0:
            raise RuntimeError(label)

    phase = 'DB_RECHECK'
    prepare = assert_migration_ledger_ready(mode='prepare', db_path=db, migrations_dir=repo / 'migrations')
    observed_db = {key: prepare.database.get(key) for key in PACKAGE_BINDING_FIELDS}
    if observed_db != expected_db:
        raise RuntimeError('authoritative DB identity differs from the DTW92 frozen binding')

    phase = 'HISTORY_RECONCILIATION'
    report_text = report.read_text(encoding='utf-8')
    history = sorted(set(re.findall(r'V2_9_8B_WINDOW_15M_AUTH_\d{8}T\d{6}Z', report_text)))
    if len(history) != 21:
        raise RuntimeError(f'expected 21 historical non-reusable authorization IDs, found {len(history)}')
    if 'V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z' not in history:
        raise RuntimeError('DTW83 consumed authorization is missing from non-reuse history')

    phase = 'TEMPLATE_LOAD'
    template = json.loads(previous_auth.read_text(encoding='utf-8'), object_pairs_hook=no_dupes)
    if template.get('schema_version') != 'PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2':
        raise RuntimeError('previous authorization is not canonical V2 schema')

    phase = 'PACKAGE_BUILD'
    now = datetime.now(timezone.utc).replace(microsecond=0)
    auth_id = f"V2_9_8B_WINDOW_15M_AUTH_{now.strftime('%Y%m%dT%H%M%SZ')}"
    if auth_id in history:
        raise RuntimeError('generated authorization ID is not unique')

    document = copy.deepcopy(template)
    document['authorization_id'] = auth_id
    document['authorized_at'] = now.isoformat().replace('+00:00', 'Z')
    document['expires_at'] = (now + timedelta(seconds=86400)).isoformat().replace('+00:00', 'Z')
    document['validity_seconds'] = 86400
    document['verdict'] = 'V2_9_8B_POST_DTW92_FRESH_WINDOW_15M_ONE_USE_FINAL_AUTHORIZATION_PASS'

    if not isinstance(document.get('authorized_git'), dict):
        raise RuntimeError('authorized_git is malformed')
    document['authorized_git']['branch'] = branch
    document['authorized_git']['head'] = head

    document['authoritative_database'] = dict(expected_db)
    document['prior_authorizations_non_reusable'] = history

    command = document.get('authorized_command')
    if not isinstance(command, dict):
        raise RuntimeError('authorized_command is malformed')
    command['mode'] = 'run'
    command['operator_approved'] = True
    command['allowed_invocation_count'] = 1
    for flag in ('automatic_retry_allowed', 'manual_rerun_allowed', 'resume_allowed', 'restart_allowed', 'successor_allowed'):
        command[flag] = False

    policy = document.get('campaign_policy')
    if not isinstance(policy, dict):
        raise RuntimeError('campaign_policy is malformed')
    policy['main_window'] = 'WINDOW_15M'
    policy['selective_1h_continuation'] = False

    package_binding_from_document(document)
    temporal = validate_authorization_temporal_validity(document)

    auth_dir = repo / 'operator-runs' / 'v2-9-8b-window-15m-final-authorization' / auth_id
    application_dir = Path.home() / 'PrinterOperations' / 'v2-9-8' / 'window-15m-one-shot-applications' / auth_id
    if auth_dir.exists():
        raise RuntimeError('new authorization package directory already exists')
    if application_dir.exists():
        raise RuntimeError('new authorization application directory already exists')

    auth_dir.mkdir(parents=True, exist_ok=False)
    auth_file = auth_dir / 'final_authorization.json'
    auth_bytes = canonical_bytes(document)
    with auth_file.open('xb') as handle:
        handle.write(auth_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    package_written = True
    auth_sha = sha256_bytes(auth_bytes)

    phase = 'PACKAGE_DB_REVIEW'
    review = assert_migration_ledger_ready(
        mode='review',
        db_path=db,
        migrations_dir=repo / 'migrations',
        package_binding=package_binding_from_document(document),
    )

    phase = 'PRE_MARKER_REVIEW'
    manifest, manifest_bytes = build_manifest_bytes(
        repository_root=repo,
        authorization_file=auth_file,
        authorization_sha256=auth_sha,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_path = evidence / 'pre_marker_manifest.json'
    with manifest_path.open('xb') as handle:
        handle.write(manifest_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    manifest_sha = sha256_bytes(manifest_bytes)

    prepared = validate_git_provenance_manifest_pre_marker(
        repository_root=repo,
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_sha,
    )

    phase = 'FINAL_NON_MUTATION_RECHECK'
    post = assert_migration_ledger_ready(mode='prepare', db_path=db, migrations_dir=repo / 'migrations')
    post_db = {key: post.database.get(key) for key in PACKAGE_BINDING_FIELDS}
    if post_db != expected_db:
        raise RuntimeError('authoritative DB changed during authorization preparation')
    if application_dir.exists():
        raise RuntimeError('application directory appeared during preparation')

    result = {
        'status': 'PASS',
        'verdict': 'V2_9_8B_POST_DTW92_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PACKAGE_REVIEW_PASS',
        'authorization_id': auth_id,
        'authorization_file': auth_file.relative_to(repo).as_posix(),
        'authorization_sha256': auth_sha,
        'authorized_at': document['authorized_at'],
        'expires_at': document['expires_at'],
        'authorized_git': {'branch': branch, 'head': head},
        'historical_non_reusable_authorization_count': len(history),
        'migration_guard_prepare': prepare.verdict,
        'migration_guard_review': review.verdict,
        'temporal_status': temporal['status'],
        'pre_marker_manifest_sha256': manifest_sha,
        'pre_marker_allowed_file_count': prepared.file_count,
        'pre_marker_allowed_file_set_sha256': prepared.allowed_file_set_sha256,
        'application_marker_created': False,
        'wrapper_invoked': False,
        'printer_runtime_started': False,
        'scheduler_runtime_started': False,
        'window_15m_started': False,
        'database_unchanged_during_preparation': True,
        'next_step': 'INDEPENDENT_AUTHORIZATION_CLOSEOUT_BEFORE_WRAPPER_INVOCATION',
    }

    review_path = evidence / 'authorization_review.json'
    review_bytes = canonical_bytes(result)
    with review_path.open('xb') as handle:
        handle.write(review_bytes)
        handle.flush()
        os.fsync(handle.fileno())

    print(json.dumps(result, indent=2, sort_keys=True))

except Exception as exc:
    blocked = {
        'status': 'BLOCKED',
        'verdict': 'V2_9_8B_POST_DTW92_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_BLOCKED',
        'phase': phase,
        'error': f'{type(exc).__name__}: {exc}',
        'authorization_id': auth_id,
        'authorization_file': str(auth_file.relative_to(repo)) if auth_file is not None and auth_file.exists() else None,
        'authorization_package_written': package_written,
        'application_marker_created': False,
        'wrapper_invoked': False,
        'next_step': 'STOP_AND_REVIEW_BLOCKER',
    }
    print(json.dumps(blocked, indent=2, sort_keys=True), file=sys.stderr)
    raise SystemExit(3)
'@

    $Code | & $Python -
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
