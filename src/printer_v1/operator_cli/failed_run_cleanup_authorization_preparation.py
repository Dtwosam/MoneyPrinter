"""Read-only exact-residue authority for failed runs with missing accounting.

This profile never grants campaign/report/source execution. Readiness facts must
be independently reviewed and supplied to preparation; drift is not adopted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli.authorization_temporal_validity import validate_authorization_temporal_validity
from printer_v1.operator_cli.four_token_proof_zero_state_gate import active_printer_runtime_processes
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    require_safe_authorization_id, validate_prior_authorizations_non_reusable,
)
from printer_v1.operator_cli.migration_one_shot_authorization import _live_git_facts
from printer_v1.operator_cli.operational_campaign_recovery import host_process_inventory
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report, campaign_scoped_job_ids
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    _canonical_json_bytes, _write_exclusive, _fsync_directory, _make_read_only,
)

SCHEMA = 'PRINTER_V1_FAILED_RUN_CLEANUP_AUTHORIZATION_V1'
MODE = 'REPORT_INELIGIBLE_HISTORICAL_EVIDENCE_MISSING'
CAUSE = 'LEASE_RENEWAL_SQLITE_LOCKED'
APPLICATION_ROOT = Path.home() / 'PrinterOperations/v2-9-8/failed-run-cleanup-applications'
SEQUENCE = ['cleanup_campaign_supervision', 'reconcile_campaign_terminal',
            'campaign_active_work_report', 'write_campaign_terminal_summary']
POLICY = dict(allowed_invocation_count=1, automatic_retry_allowed=False,
              manual_rerun_allowed=False, resume_allowed=False, restart_allowed=False,
              successor_allowed=False, provider_calls_allowed=False,
              scheduler_execution_allowed=False, campaign_report_allowed=False)
SCOPE_KEYS = {'execution_id','campaign_id','configuration_id','run_id','cycle_id',
              'supervision_id','owner_id','factory_run_id'}
EVIDENCE_KEYS = {'six_unit_evidence','partial_six_unit_evidence','six_unit_totals',
                 'transport_operations','scheduler_work_identities',
                 'local_validation_identities','lifecycle_reservation_identities'}
# Exact rows are selected below. These are the only mutable columns in those rows.
MUTABLE = {
 'printer_scheduler_jobs': ('status', {'status','locked_at','lock_owner','last_error','finished_at','updated_at'}),
 'printer_memory_factory_run_steps': ('step_status', {'step_status','error_or_skip_reason','finished_at','updated_at'}),
 'printer_memory_factory_runs': ('run_status', {'run_status','stop_reason','finished_at','updated_at'}),
 'printer_memory_factory_campaigns': ('campaign_state', {'campaign_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_runs': ('run_state', {'run_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_cycles': ('cycle_state', {'cycle_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_windows': ('window_state', {'window_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_token_slots': ('token_state', {'token_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_scheduler_work': ('work_state', {'work_state','first_terminal_cause','terminal_at','updated_at'}),
 'printer_memory_factory_campaign_supervision': ('supervision_state', {'supervision_state','terminal_status','first_terminal_cause','cleanup_completed_at','lease_released_at','updated_at'}),
 'printer_tracking_queue': ('queue_status', {'queue_status','tracking_action','priority_reason','last_checked_at','updated_at'}),
 'printer_discovery_batches': ('batch_state', {'batch_state','first_terminal_cause','terminal_at'}),
 'printer_discovery_work': ('work_state', {'work_state','first_terminal_cause','terminal_at','updated_at'}),
}
ACTIVE = {'PENDING','RUNNING','COOLDOWN','PLANNED','TRACKING','COLLECTING',
          'CLOSE_PENDING','AUDITING','SELECTED','QUEUED','ACTIVE','DISCOVERING'}

class CleanupAuthorizationError(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise CleanupAuthorizationError(reason)


def canonical(value):
    return _canonical_json_bytes(value)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def path_checked(value):
    p = Path(value)
    require(p.is_absolute() and '..' not in p.parts, 'path must be absolute and canonical')
    require(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path forbidden')
    require(str(p) == str(p.resolve()), 'noncanonical path')
    return p


def file_identity(value):
    p = path_checked(value)
    require(p.is_file(), 'file missing')
    a = p.stat()
    with p.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    b = p.stat()
    require((a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns), 'file changed during inspection')
    return dict(path=str(p),sha256=sha,size=a.st_size,inode=a.st_ino,
                device=a.st_dev,mtime_ns=a.st_mtime_ns)


def no_sidecars(p):
    require(not any(Path(str(p)+s).exists() for s in ('-wal','-shm','-journal')), 'SQLite sidecar present')


def read_only(p):
    no_sidecars(p)
    c = sqlite3.connect(Path(p).as_uri()+'?mode=ro&immutable=1',uri=True,timeout=0)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA query_only=ON')
    return c


def health(c):
    require([x[0] for x in c.execute('PRAGMA integrity_check')]==['ok'], 'integrity failed')
    require(not c.execute('PRAGMA foreign_key_check').fetchall(), 'foreign keys failed')
    versions = [x[0] for x in c.execute('SELECT version FROM printer_schema_migrations ORDER BY version')]
    require(versions == list(canonical_migration_names()), 'migration drift')
    return dict(migration_count=len(versions),migration_head=versions[-1])


def evidence_absent(value):
    if isinstance(value, dict):
        require(not any(k in EVIDENCE_KEYS and v is not None for k,v in value.items()), 'historical six-unit evidence present')
        for v in value.values(): evidence_absent(v)
    elif isinstance(value, list):
        for v in value: evidence_absent(v)


def historical_artifacts(summary_path, artifact_roots, scope):
    summary = path_checked(summary_path)
    roots = [path_checked(x) for x in artifact_roots]
    require(summary.parent in roots, 'historical summary root missing')
    files = {}
    for root in roots:
        require(root.is_dir(), 'historical artifact root missing')
        for p in sorted(root.rglob('*')):
            require(not p.is_symlink(), 'historical artifact symlink')
            if not p.is_file() or p.suffix not in ('.json','.txt'): continue
            identity = file_identity(str(p)); data = p.read_text()
            if data.strip():
                try:
                    evidence_absent(json.loads(data))
                except json.JSONDecodeError:
                    require(not any('"'+k+'"' in data for k in EVIDENCE_KEYS), 'unparsed accounting evidence')
            files[str(p)] = identity
    require(str(summary) in files, 'summary not inventoried')
    original = json.loads(summary.read_text())
    require(original.get('execution_id')==scope['execution_id'], 'historical execution mismatch')
    for key in ('campaign_id','run_id','configuration_id'):
        require(original.get(key)==scope[key], 'historical ownership mismatch')
    require(original.get('first_terminal_cause')==CAUSE, 'historical first cause mismatch')
    require(original.get('accounting_status')=='NOT_FINALIZED_CLEANUP_UNPROVEN'
            and original.get('report_written') is False
            and original.get('report_block_reason')=='TERMINAL_CLEANUP_UNPROVEN', 'historical report state mismatch')
    return files


def scope_report(c, scope):
    return campaign_active_work_report(c, **{k:scope[k] for k in ('factory_run_id','campaign_id','run_id','cycle_id')})


def load_residue(c, s):
    result = {}
    for table in MUTABLE:
        if table in ('printer_scheduler_jobs','printer_tracking_queue'): continue
        columns = {x[1] for x in c.execute(f'PRAGMA table_info("{table}")')}
        key = 'campaign_id' if 'campaign_id' in columns else 'run_id'
        value = s['campaign_id'] if key=='campaign_id' else s['factory_run_id']
        result[table] = [dict(x) for x in c.execute(f'SELECT * FROM "{table}" WHERE {key}=?',(value,))]
    groups = campaign_scoped_job_ids(c, **{k:s[k] for k in ('factory_run_id','campaign_id','run_id','cycle_id')})
    ids = sorted(set().union(*groups.values()))
    result['printer_scheduler_jobs'] = [dict(c.execute('SELECT * FROM printer_scheduler_jobs WHERE id=?',(i,)).fetchone()) for i in ids]
    queues = sorted({x['tracking_queue_id'] for x in result['printer_memory_factory_campaign_token_slots']})
    require(None not in queues, 'slot queue missing')
    result['printer_tracking_queue'] = [dict(c.execute('SELECT * FROM printer_tracking_queue WHERE id=?',(i,)).fetchone()) for i in queues]
    return result


def row_key(c, table, row):
    keys = [x[1] for x in sorted(c.execute(f'PRAGMA table_info("{table}")'),key=lambda x:x[5]) if x[5]]
    require(bool(keys), 'table primary key missing')
    return json.dumps([row[k] for k in keys])


def preservation(c, residue):
    """Hash every table, masking only approved fields in exact active rows.

    Detects inserts/deletes, unrelated mutations, completed evidence changes and
    future capability changes without giving those domains mutation authority.
    """
    masks = {}
    for table, rows in residue.items():
        state, fields = MUTABLE[table]
        masks[table] = {row_key(c,table,r):fields for r in rows if r[state] in ACTIVE}
    hashes = {}
    for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        rows = []
        for row in c.execute(f'SELECT * FROM "{table}"'):
            value = dict(row)
            omit = masks.get(table,{}).get(row_key(c,table,value),set()) if table in masks else set()
            rows.append({k:v for k,v in value.items() if k not in omit})
        hashes[table] = digest({"rows": sorted(rows,key=lambda r:canonical(r))})
    return hashes


def runtime_processes(db):
    live = set(active_printer_runtime_processes(db))
    for pid, command in host_process_inventory():
        if pid not in (os.getpid(), os.getppid()) and any(
            marker in command.lower() for marker in ('source_governor', 'central_scheduler')
        ):
            live.add(pid)
    return sorted(live)


def validate_prior_inventory(document):
    """Require published cleanup IDs in the canonical explicit non-reuse list."""
    prior = set(validate_prior_authorizations_non_reusable(
        document['prior_authorizations_non_reusable'],
        current_authorization_id=document['authorization_id']))
    root = path_checked(document['application_root'])
    if root.exists():
        for child in root.iterdir():
            require(not child.is_symlink() and child.is_dir(), 'invalid cleanup application inventory')
            require_safe_authorization_id(child.name, label='prior cleanup application')
            if child.name != document['authorization_id']:
                require(child.name in prior, 'prior cleanup authority omitted from non-reuse inventory')
    # Original application markers are historical inputs, never cleanup authority.
    for name in document['facts']['historical_artifacts']:
        if Path(name).name == 'application-marker.json':
            old = json.loads(Path(name).read_text()).get('authorization_id')
            require(old in prior, 'original consumed authorization missing from non-reuse inventory')


def inspect_cleanup(*, repository_root, database_path, scope, summary_path, artifact_roots, now=None):
    """Read-only readiness snapshot. Does not create or consume authority."""
    now = now or datetime.now(timezone.utc)
    require(set(scope)==SCOPE_KEYS and all(type(v) is str and v for v in scope.values()), 'scope schema')
    root = path_checked(repository_root)
    db = path_checked(database_path)
    no_sidecars(db)
    git = _live_git_facts(root)
    require(git['tracked_clean'] and git['branch'] and git['head']==git['remote_head'], 'Git drift')
    require(not runtime_processes(db), 'active Printer process')
    no_sidecars(db); before = file_identity(str(db))
    artifacts = historical_artifacts(summary_path,artifact_roots,scope)
    c = read_only(db)
    try:
        migrations = health(c); residue = load_residue(c,scope)
        def one(table,key,value):
            rows=residue[table]; require(len(rows)==1 and rows[0].get(key)==value, 'execution graph mismatch: '+table);return rows[0]
        campaign=one('printer_memory_factory_campaigns','campaign_id',scope['campaign_id'])
        run=one('printer_memory_factory_campaign_runs','run_id',scope['run_id'])
        cycle=one('printer_memory_factory_campaign_cycles','cycle_id',scope['cycle_id'])
        sup=one('printer_memory_factory_campaign_supervision','supervision_id',scope['supervision_id'])
        factory=one('printer_memory_factory_runs','run_id',scope['factory_run_id'])
        require(run['authoritative_run_id']==scope['factory_run_id'], 'factory ownership mismatch')
        for row in (run,cycle,sup):
            require(row['campaign_id']==scope['campaign_id'], 'campaign ownership mismatch')
        require(cycle['run_id']==sup['run_id']==scope['run_id'], 'run ownership mismatch')
        require(sup['configuration_id']==scope['configuration_id'] and sup['owner_id']==scope['owner_id'], 'supervision ownership mismatch')
        require(campaign['campaign_state']=='RUNNING' and run['run_state']=='RUNNING'
                and cycle['cycle_state'] in ('PLANNED','TRACKING') and sup['supervision_state']=='ACTIVE'
                and factory['run_status']=='RUNNING', 'non-active execution graph')
        require(all(r.get('first_terminal_cause') in (None,CAUSE) for t,rows in residue.items() for r in rows if r[MUTABLE[t][0]] in ACTIVE), 'first-cause drift')
        require(factory['stop_reason'] in (None,CAUSE), 'factory cause drift')
        require(factory['final_report_json'] is None, 'factory final report present')
        require(c.execute('SELECT COUNT(*) FROM printer_memory_factory_campaign_reports WHERE campaign_id=?',(scope['campaign_id'],)).fetchone()[0]==0, 'campaign report present')
        steps=residue['printer_memory_factory_run_steps']
        succeeded=[r for r in steps if r['step_status']=='SUCCEEDED' and r['snapshot_id'] is not None]
        require(bool(succeeded), 'started lifecycle evidence missing')
        for step in succeeded:
            require(c.execute('SELECT 1 FROM printer_token_snapshots WHERE id=?',(step['snapshot_id'],)).fetchone() is not None, 'snapshot missing')
        for t in ('printer_four_token_pre_lifecycle_terminal_provenance','printer_four_token_zero_attempt_terminal_provenance','printer_four_token_started_lifecycle_zero_attempt_terminal_provenance','printer_pre_admission_discovery_attempts'):
            require(c.execute(f'SELECT COUNT(*) FROM {t} WHERE campaign_id=?',(scope['campaign_id'],)).fetchone()[0]==0, 'unexpected attempt/provenance')
        for t in ('printer_memory_factory_campaign_windows','printer_memory_factory_campaign_token_slots','printer_memory_factory_campaign_scheduler_work','printer_discovery_batches','printer_discovery_work'):
            for r in residue[t]:
                require(r.get('run_id')==scope['run_id'] and r.get('cycle_id')==scope['cycle_id'], 'residue ownership mismatch')
        for row in residue['printer_scheduler_jobs']:
            require(row['status'] in ACTIVE or (row['locked_at'] is None and row['lock_owner'] is None), 'terminal Scheduler lock residue unsupported')
        active=scope_report(c,scope)
        require(active['active_pre_lifecycle_refresh_waits']==0 and active['active_pre_admission_attempts']==0, 'unsupported auxiliary work')
        require(active['active_jobs']>0 and active['pending_or_running_run_steps']>0, 'active residue missing')
        lease=file_identity(sup['lease_lock_path']); payload=json.loads(Path(lease['path']).read_text())
        for key in ('campaign_id','configuration_id','run_id','supervision_id','owner_id'):
            require(payload.get(key)==scope[key], 'lease ownership mismatch')
        require(datetime.fromisoformat(payload['lease_expires_at'])<now, 'lease not expired')
        require(payload.get('scope') == 'OPERATIONAL_CAMPAIGN', 'lease scope mismatch')
        protected=preservation(c,residue)
    finally:
        c.close()
    require(file_identity(str(db))==before, 'database changed during inspection')
    no_sidecars(db)
    return dict(repository=git,database={**before,**migrations},scope=scope,residue=residue,
                active_work=active,lease=lease,historical_artifacts=artifacts,preservation=protected,
                lifecycle_started=True,first_terminal_cause=CAUSE,six_unit_evidence_status='ABSENT',mode=MODE)


def validate_document(document, now=None):
    keys={'schema_version','authorization_id','authorized_at','expires_at','validity_seconds',
          'repository_root','summary_path','artifact_roots','facts','one_shot_policy','owner_sequence',
          'prior_authorizations_non_reusable','application_root'}
    require(type(document) is dict and set(document)==keys, 'authorization schema mismatch')
    require(document['schema_version']==SCHEMA and canonical(document['one_shot_policy'])==canonical(POLICY)
            and document['owner_sequence']==SEQUENCE, 'cleanup profile mismatch')
    require_safe_authorization_id(document['authorization_id'],label='cleanup authorization ID')
    validate_prior_authorizations_non_reusable(document['prior_authorizations_non_reusable'],current_authorization_id=document['authorization_id'])
    require(document['application_root']==str(APPLICATION_ROOT.resolve()), 'application namespace mismatch')
    validate_authorization_temporal_validity(document,now=now)
    return document


def check_live(document, now=None):
    validate_document(document,now)
    expected=document['facts']
    actual=inspect_cleanup(repository_root=document['repository_root'],database_path=expected['database']['path'],
        scope=expected['scope'],summary_path=document['summary_path'],artifact_roots=document['artifact_roots'],now=now)
    require(canonical(actual)==canonical(expected), 'bound cleanup facts drift')
    validate_prior_inventory(document)
    return actual


def prepare_cleanup_authorization(*, authorization_id, repository_root, summary_path, artifact_roots,
                                  expected_facts, prior_authorizations_non_reusable, destination,
                                  now=None, validity_seconds=3600):
    """Publish a reviewed exact binding, without touching DB or consuming it."""
    now=now or datetime.now(timezone.utc)
    document=dict(schema_version=SCHEMA,authorization_id=authorization_id,authorized_at=now.isoformat(),
        expires_at=(now+timedelta(seconds=validity_seconds)).isoformat(),validity_seconds=validity_seconds,
        repository_root=str(repository_root),summary_path=str(summary_path),artifact_roots=list(artifact_roots),
        facts=expected_facts,one_shot_policy=POLICY,owner_sequence=SEQUENCE,
        prior_authorizations_non_reusable=list(prior_authorizations_non_reusable),application_root=str(APPLICATION_ROOT.resolve()))
    check_live(document,now)
    require(not (APPLICATION_ROOT/authorization_id).exists(), 'cleanup authority already used')
    path=path_checked(destination)
    _write_exclusive(path,canonical(document));_make_read_only(path);_fsync_directory(path.parent)
    return dict(authorization_file=str(path),sha256=file_identity(str(path))['sha256'],consumed=False)
