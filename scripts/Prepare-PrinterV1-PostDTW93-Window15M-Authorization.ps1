[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Repo = Join-Path $HOME 'Developer/MoneyPrinter'
$AuthBranch = 'agent/v2-9-8b-post-dtw93-window15m-authorization-preparation'
$AuthHead = '6c30377c28d62c578020ad3f7d32e020c393fc0e'
$Db = Join-Path $Repo 'data/printer_v1.sqlite3'
$PreviousAuth = Join-Path $Repo 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z/final_authorization.json'
$Python = Join-Path $Repo '.venv/bin/python'
$Stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$Evidence = Join-Path $HOME "PrinterV1OperatorReadiness/POST_DTW93_WINDOW15M_AUTH_$Stamp"

function Fail([string]$Message) {
    Write-Error "BLOCKED: $Message"
    exit 3
}

if (-not (Test-Path -LiteralPath $Repo -PathType Container)) { Fail 'repository unavailable' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { Fail 'repository Python unavailable' }

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
    if ($LASTEXITCODE -eq 0) { & git switch $AuthBranch }
    else { & git switch --track -c $AuthBranch "origin/$AuthBranch" }
    if ($LASTEXITCODE -ne 0) { Fail 'could not switch to authorization branch' }
    & git reset --hard $AuthHead | Out-Null

    if ((& git rev-parse HEAD).Trim() -ne $AuthHead) { Fail 'local HEAD mismatch' }
    if ((& git branch --show-current).Trim() -ne $AuthBranch) { Fail 'local branch mismatch' }
    & git diff --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked worktree changed during alignment' }
    & git diff --cached --quiet --no-ext-diff --
    if ($LASTEXITCODE -ne 0) { Fail 'tracked index changed during alignment' }
    if (-not (Test-Path -LiteralPath $PreviousAuth -PathType Leaf)) { Fail 'DTW93 authorization template unavailable' }

    New-Item -ItemType Directory -Path $Evidence -Force | Out-Null
    $env:PRINTER_POST_DTW93_REPO = $Repo
    $env:PRINTER_POST_DTW93_BRANCH = $AuthBranch
    $env:PRINTER_POST_DTW93_HEAD = $AuthHead
    $env:PRINTER_POST_DTW93_DB = $Db
    $env:PRINTER_POST_DTW93_TEMPLATE = $PreviousAuth
    $env:PRINTER_POST_DTW93_EVIDENCE = $Evidence

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

from printer_v1.operator_cli.authorization_temporal_validity import validate_authorization_temporal_validity
from printer_v1.operator_cli.git_provenance_authorization_manifest import validate_git_provenance_manifest_pre_marker
from printer_v1.operator_cli.holder_reliability_budget_control import build_operational_budget_preflight
from printer_v1.operator_cli.operational_memory_factory_command import (
    ADMISSION_OPERATION_CEILING,
    DISCOVERY_REQUEST_CEILING,
    GOVERNED_15M_REQUEST_CEILING,
    GOVERNED_REQUESTS_PER_TOKEN,
    _active_counts,
    _locked_capability_counts,
    _read_only,
    _validate_locked_baseline,
)
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    PACKAGE_BINDING_FIELDS,
    assert_migration_ledger_ready,
    package_binding_from_document,
)
from printer_v1.operator_cli.readiness_source_contract_preflight import build_readiness_source_contract_preflight
from printer_v1.operator_cli.unified_terminal_closure import assert_runtime_dependency_preflight
from printer_v1.operator_cli.window_15m_concrete_composition import (
    run_window_15m_concrete_composition_preflight,
    window_15m_preflight_builders,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import build_manifest_bytes

repo = Path(os.environ['PRINTER_POST_DTW93_REPO']).resolve()
branch = os.environ['PRINTER_POST_DTW93_BRANCH']
head = os.environ['PRINTER_POST_DTW93_HEAD']
db = Path(os.environ['PRINTER_POST_DTW93_DB']).resolve()
template_path = Path(os.environ['PRINTER_POST_DTW93_TEMPLATE']).resolve()
evidence = Path(os.environ['PRINTER_POST_DTW93_EVIDENCE']).resolve()

expected_db = {
    'path': str(db),
    'sha256': '6a0f7afc2f4d542854bcf7f1db6857c6405f50f9085dded922fc419e938bfc35',
    'size': 71127040,
    'inode': 1230526,
    'mtime_ns': 1786227161080487776,
    'migration_count': 53,
    'migration_head': '053_pilot_input_readiness_route_domain.sql',
}

history = sorted([
    'V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T005013Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z',
    'V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z',
])

def canonical_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode()

def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()

def git(*args):
    return subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

def no_dupes(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RuntimeError(f'duplicate JSON key: {key}')
        out[key] = value
    return out

phase = 'START'
auth_id = None
auth_file = None
try:
    phase = 'GIT_RECHECK'
    if git('branch', '--show-current') != branch or git('rev-parse', 'HEAD') != head:
        raise RuntimeError('exact authorization Git binding mismatch')
    for args in [('diff','--quiet','--no-ext-diff','--'), ('diff','--cached','--quiet','--no-ext-diff','--')]:
        if subprocess.run(['git', *args], cwd=repo).returncode != 0:
            raise RuntimeError('tracked Git state is not clean')

    phase = 'DB_GUARD_PREPARE'
    prepare = assert_migration_ledger_ready(mode='prepare', db_path=db, migrations_dir=repo/'migrations')
    observed_db = {k: prepare.database.get(k) for k in PACKAGE_BINDING_FIELDS}
    if observed_db != expected_db:
        raise RuntimeError(f'authoritative DB identity mismatch: {observed_db!r}')

    phase = 'READINESS_NON_GIT'
    source = build_readiness_source_contract_preflight()
    if source.get('status') != 'READY' or int(source.get('external_requests') or 0) != 0:
        raise RuntimeError(f'source contract not zero-I/O READY: {source!r}')
    composition = run_window_15m_concrete_composition_preflight(repository_root=str(repo), timeout_seconds=5.0)
    if composition.get('status') != 'READY':
        raise RuntimeError(f'concrete composition not READY: {composition!r}')
    dependency = assert_runtime_dependency_preflight(
        repository_root=repo,
        adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
    )
    if dependency.status != 'READY':
        raise RuntimeError(f'runtime dependency not READY: {dependency.to_dict()!r}')
    budget = build_operational_budget_preflight(
        admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
        discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
        governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
        governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
    )
    if budget.get('status') != 'READY':
        raise RuntimeError(f'holder budget not READY: {budget!r}')
    conn = _read_only(db)
    try:
        active = dict(_active_counts(conn))
        locked = dict(_locked_capability_counts(conn))
        historical_audit = int(conn.execute(
            'SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL'
        ).fetchone()[0])
    finally:
        conn.close()
    if any(active.values()):
        raise RuntimeError(f'active operational residue: {active!r}')
    _validate_locked_baseline(locked)
    if historical_audit != 1:
        raise RuntimeError(f'historical paper-audit baseline changed: {historical_audit}')

    readiness = {
        'status': 'READY',
        'source_contract_status': source.get('status'),
        'source_contract_external_requests': source.get('external_requests'),
        'concrete_composition_status': composition.get('status'),
        'dependency_status': dependency.status,
        'holder_budget_status': budget.get('status'),
        'active_counts': active,
        'historical_paper_audit_rows_preserved': historical_audit,
        'source_calls': 0,
        'scheduler_runtime_calls': 0,
        'database_writes': 0,
    }

    phase = 'HISTORY_RECONCILIATION'
    auth_root = repo/'operator-runs'/'v2-9-8b-window-15m-final-authorization'
    existing = {
        p.name for p in auth_root.iterdir()
        if p.is_dir() and re.fullmatch(r'V2_9_8B_WINDOW_15M_AUTH_\d{8}T\d{6}Z', p.name)
    } if auth_root.is_dir() else set()
    unexpected = sorted(existing - set(history))
    if unexpected:
        raise RuntimeError(f'unreviewed authorization package(s) already exist: {unexpected}')
    if len(history) != 22 or history[-1] != 'V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z':
        raise RuntimeError('historical non-reuse trust root is malformed')

    phase = 'TEMPLATE_LOAD'
    template = json.loads(template_path.read_text(), object_pairs_hook=no_dupes)
    if template.get('schema_version') != 'PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2':
        raise RuntimeError('DTW93 template is not canonical V2 authorization schema')

    phase = 'PACKAGE_BUILD'
    now = datetime.now(timezone.utc).replace(microsecond=0)
    auth_id = f"V2_9_8B_WINDOW_15M_AUTH_{now.strftime('%Y%m%dT%H%M%SZ')}"
    if auth_id in history or auth_id in existing:
        raise RuntimeError('fresh authorization ID collision')
    document = copy.deepcopy(template)
    document['authorization_id'] = auth_id
    document['authorized_at'] = now.isoformat().replace('+00:00','Z')
    document['expires_at'] = (now + timedelta(hours=24)).isoformat().replace('+00:00','Z')
    document['validity_seconds'] = 86400
    document['verdict'] = 'V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_FINAL_AUTHORIZATION_PASS'
    document['authorized_git']['branch'] = branch
    document['authorized_git']['head'] = head
    document['authoritative_database'] = dict(expected_db)
    document['prior_authorizations_non_reusable'] = history
    command = document['authorized_command']
    command['mode'] = 'run'
    command['operator_approved'] = True
    command['allowed_invocation_count'] = 1
    for flag in ('automatic_retry_allowed','manual_rerun_allowed','resume_allowed','restart_allowed','successor_allowed'):
        command[flag] = False
    document['campaign_policy']['main_window'] = 'WINDOW_15M'
    document['campaign_policy']['selective_1h_continuation'] = False
    package_binding_from_document(document)
    temporal = validate_authorization_temporal_validity(document)

    auth_dir = auth_root/auth_id
    app_dir = Path.home()/'PrinterOperations'/'v2-9-8'/'window-15m-one-shot-applications'/auth_id
    if auth_dir.exists() or app_dir.exists():
        raise RuntimeError('fresh authorization/application identity already exists')
    auth_dir.mkdir(parents=True, exist_ok=False)
    auth_file = auth_dir/'final_authorization.json'
    auth_bytes = canonical_bytes(document)
    with auth_file.open('xb') as handle:
        handle.write(auth_bytes); handle.flush(); os.fsync(handle.fileno())
    auth_sha = sha256_bytes(auth_bytes)

    phase = 'PACKAGE_DB_REVIEW'
    review = assert_migration_ledger_ready(
        mode='review', db_path=db, migrations_dir=repo/'migrations',
        package_binding=package_binding_from_document(document),
    )

    phase = 'PRE_MARKER_REVIEW'
    manifest, manifest_bytes = build_manifest_bytes(
        repository_root=repo,
        authorization_file=auth_file,
        authorization_sha256=auth_sha,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_path = evidence/'pre_marker_manifest.json'
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha = sha256_bytes(manifest_bytes)
    prepared = validate_git_provenance_manifest_pre_marker(
        repository_root=repo,
        manifest_path=str(manifest_path),
        manifest_sha256=manifest_sha,
    )
    prepared_summary = prepared.summary()

    phase = 'FINAL_RECHECK'
    post = assert_migration_ledger_ready(mode='prepare', db_path=db, migrations_dir=repo/'migrations')
    post_db = {k: post.database.get(k) for k in PACKAGE_BINDING_FIELDS}
    if post_db != expected_db:
        raise RuntimeError('authoritative DB changed during authorization preparation')
    if app_dir.exists():
        raise RuntimeError('application marker/directory appeared during preparation')

    result = {
        'status': 'PASS',
        'verdict': 'V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PACKAGE_REVIEW_PASS',
        'authorization_id': auth_id,
        'authorization_file': auth_file.relative_to(repo).as_posix(),
        'authorization_sha256': auth_sha,
        'authorized_at': document['authorized_at'],
        'expires_at': document['expires_at'],
        'authorized_git': {'branch': branch, 'head': head},
        'authoritative_database': expected_db,
        'historical_non_reusable_authorization_count': len(history),
        'migration_guard_prepare': prepare.verdict,
        'migration_guard_review': review.verdict,
        'temporal_status': getattr(temporal, 'status', 'TEMPORALLY_VALID'),
        'readiness_non_git': readiness,
        'pre_marker_manifest_sha256': manifest_sha,
        'pre_marker_allowed_file_count': prepared_summary['allowed_file_count'],
        'pre_marker_allowed_file_set_sha256': prepared_summary['allowed_file_set_sha256'],
        'application_marker_created': False,
        'wrapper_invoked': False,
        'printer_runtime_started': False,
        'scheduler_runtime_started': False,
        'window_15m_started': False,
        'database_unchanged_during_preparation': True,
        'host_awake_required_for_later_runtime': True,
        'next_step': 'INDEPENDENT_AUTHORIZATION_CLOSEOUT_BEFORE_WRAPPER_INVOCATION',
    }
    print(json.dumps(result, indent=2, sort_keys=True))
except BaseException as exc:
    print(json.dumps({
        'status': 'BLOCKED',
        'verdict': 'V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_BLOCKED',
        'phase': phase,
        'authorization_id': auth_id,
        'authorization_file': str(auth_file) if auth_file else None,
        'error': f'{type(exc).__name__}:{exc}',
        'wrapper_invoked': False,
        'printer_runtime_started': False,
        'scheduler_runtime_started': False,
        'window_15m_started': False,
    }, indent=2, sort_keys=True))
    raise
'@

    & $Python -c $Code
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
