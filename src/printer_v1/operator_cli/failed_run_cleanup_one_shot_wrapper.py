"""Marker-first application of one exact failed-run cleanup, never a campaign."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from printer_v1.db.sqlite_write_contracts import activate_writer_attribution, deactivate_writer_attribution
from printer_v1.operator_cli import failed_run_cleanup_authorization_preparation as auth
from printer_v1.operator_cli.campaign_supervision import cleanup_campaign_supervision
from printer_v1.operator_cli.unified_terminal_closure import (
    reconcile_campaign_terminal, write_campaign_terminal_summary,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    _write_exclusive, _make_read_only, _fsync_directory,
)

MARKER = 'application-marker.json'
RESOLUTION = 'cleanup-resolution.json'
TERMINAL = 'application-terminal.json'
ZERO_FIELDS = ('active_jobs','active_work_rows','terminal_work_with_active_job',
               'pending_or_running_run_steps','active_factory_runs',
               'active_pre_lifecycle_refresh_waits','active_pre_admission_attempts')
TERMINAL_STATES = {
 'printer_scheduler_jobs':'CANCELLED', 'printer_memory_factory_run_steps':'CANCELLED',
 'printer_memory_factory_runs':'SAFE_STOPPED', 'printer_memory_factory_campaigns':'TERMINAL_FAILED',
 'printer_memory_factory_campaign_runs':'TERMINAL_FAILED', 'printer_memory_factory_campaign_cycles':'TERMINAL_FAILED',
 'printer_memory_factory_campaign_windows':'CANCELLED', 'printer_memory_factory_campaign_token_slots':'MANUAL_REVIEW',
 'printer_memory_factory_campaign_scheduler_work':'CANCELLED', 'printer_memory_factory_campaign_supervision':'TERMINAL',
 'printer_tracking_queue':'SKIPPED', 'printer_discovery_batches':'TERMINAL_FAILED', 'printer_discovery_work':'FAILED',
}


def verify_zero_state(facts):
    """Fresh immutable reader; owner return values are not terminal proof."""
    db=facts['database']['path'];scope=facts['scope']
    auth.require(not Path(facts['lease']['path']).exists(), 'lease remains')
    c=auth.read_only(db)
    try:
        auth.health(c)
        report=auth.scope_report(c,scope)
        auth.require(report['clean_terminal'] is True and report['locked_job_ids']==[]
                     and all(type(report[k]) is int and report[k]==0 for k in ZERO_FIELDS), 'zero-state verification failed')
        auth.require(auth.preservation(c,facts['residue'])==facts['preservation'], 'unrelated/evidence/capability state changed')
        after=auth.load_residue(c,scope)
        for table,rows in facts['residue'].items():
            keyed={auth.row_key(c,table,r):r for r in after[table]}
            state,_=auth.MUTABLE[table]
            for old in rows:
                new=keyed[auth.row_key(c,table,old)]
                if old[state] not in auth.ACTIVE:
                    auth.require(old==new, 'terminal evidence rewritten');continue
                auth.require(new[state]==TERMINAL_STATES[table], 'terminal state mismatch: '+table)
                for field in ('first_terminal_cause','stop_reason','error_or_skip_reason'):
                    if field in old:
                        expected=old[field] if old[field] is not None else auth.CAUSE
                        auth.require(new[field]==expected, 'terminal cause changed')
                if 'finished_at' in old:
                    auth.require(new['finished_at'] is not None and
                                 (old['finished_at'] is None or new['finished_at']==old['finished_at']), 'finish time not preserved')
                if table=='printer_scheduler_jobs':
                    auth.require(new['locked_at'] is None and new['lock_owner'] is None, 'Scheduler lock remains')
                if table=='printer_tracking_queue':
                    auth.require(new['tracking_action']=='MANUAL_REVIEW', 'queue disposition mismatch')
                if table=='printer_memory_factory_campaign_supervision':
                    auth.require(new['terminal_status']=='FAILED' and new['cleanup_completed_at'] and new['lease_released_at'], 'supervision incomplete')
        return report
    finally:
        c.close()


def validate_consumed_package(directory, authorization_bytes, marker_bytes):
    auth.require((directory/'authorization.json').read_bytes()==authorization_bytes, 'published authorization differs')
    auth.require((directory/MARKER).read_bytes()==marker_bytes, 'consumed marker differs')
    expected=json.loads(authorization_bytes)
    manifest=json.loads((directory/'provenance.json').read_bytes())
    auth.require(manifest==dict(repository=expected['facts']['repository'],authorization_sha256=auth.digest(expected)), 'published provenance differs')
    marker=json.loads(marker_bytes)
    auth.require(marker['authorization_sha256']==auth.digest(expected)
                 and marker['authorization_id']==expected['authorization_id']
                 and marker['invocation_count']==1, 'consumed package identity mismatch')


def apply_cleanup_authorization(*, authorization_file, expected_sha256, operator_approved=False, now=None):
    auth.require(operator_approved is True, 'explicit cleanup approval required')
    now=now or datetime.now(timezone.utc)
    path=auth.path_checked(authorization_file)
    identity=auth.file_identity(str(path))
    auth.require(identity['sha256']==expected_sha256, 'authorization bytes/hash mismatch')
    authorization_bytes=path.read_bytes();document=json.loads(authorization_bytes)
    auth.require(authorization_bytes==auth.canonical(document), 'authorization bytes not canonical')
    auth.validate_document(document,now)
    root=auth.path_checked(document['application_root'])
    directory=root/document['authorization_id']
    # Any prior package, including an interrupted publication, blocks reuse.
    auth.require(not directory.exists(), 'cleanup authority consumed or application already published')
    facts=auth.check_live(document,now)
    auth.require(path.read_bytes()==authorization_bytes, 'authorization changed during free gates')
    root.mkdir(parents=True,exist_ok=True)
    directory.mkdir()  # exclusive namespace acquisition; never remove on failure
    _write_exclusive(directory/'authorization.json',authorization_bytes)
    _write_exclusive(directory/'provenance.json',auth.canonical(dict(repository=facts['repository'],authorization_sha256=expected_sha256)))
    marker=dict(schema_version='PRINTER_V1_FAILED_RUN_CLEANUP_MARKER_V1',
                authorization_id=document['authorization_id'],authorization_sha256=expected_sha256,
                consumed_at=now.isoformat(),invocation_count=1,repository=facts['repository'],database=facts['database'])
    marker_bytes=auth.canonical(marker)
    _write_exclusive(directory/MARKER,marker_bytes)
    for name in ('authorization.json','provenance.json',MARKER): _make_read_only(directory/name)
    _fsync_directory(directory);_fsync_directory(root)
    result=dict(authorization_id=document['authorization_id'],execution_id=facts['scope']['execution_id'],
                consumed=True,first_terminal_cause=auth.CAUSE,lifecycle_started=True,
                accounting_status='SIX_UNIT_ACCOUNTING_BLOCKED',report_written=False,
                report_block_reason='SIX_UNIT_EVIDENCE_MISSING',historical_six_unit_evidence='ABSENT',
                restart_created=False,successor_created=False,source_calls_by_cleanup=0,
                scheduler_runtime_calls_by_cleanup=0,cleanup_complete=False,
                lease_released=False,reconciliation_complete=False,zero_state_proven=False)
    try:
        validate_consumed_package(directory,authorization_bytes,marker_bytes)
        # Close publication time-of-check drift before the first mutation.
        auth.check_live(document,now)
        scope=facts['scope'];db=facts['database']['path']
        activate_writer_attribution(db, artifact_path=directory/'sqlite-writer-attribution.json', scope={**scope, 'cleanup_authorization_id': document['authorization_id']})
        cleanup=cleanup_campaign_supervision(db,**{k:scope[k] for k in ('supervision_id','campaign_id','configuration_id','run_id','owner_id')},
                    terminal_status='FAILED',first_terminal_cause=auth.CAUSE,now=now)
        result['cleanup']=cleanup
        auth.require(all(cleanup.get(k)==scope[k] for k in ('supervision_id','campaign_id','configuration_id','run_id','owner_id'))
                     and cleanup.get('cleanup_completed') is True and cleanup.get('lease_released') is True
                     and type(cleanup.get('active_owned_work_after')) is int and cleanup['active_owned_work_after']==0, 'cleanup owner not proven')
        result.update(cleanup_complete=True,lease_released=True)
        reconciliation=reconcile_campaign_terminal(db,**{k:scope[k] for k in ('campaign_id','run_id','cycle_id','factory_run_id')},
                    terminal_cause=auth.CAUSE,run_status='SAFE_STOPPED',lifecycle_started=True,now=now.isoformat())
        result['reconciliation']=reconciliation
        auth.require(reconciliation.get('reconciled') is True, 'reconciliation owner failed')
        result['reconciliation_complete']=True
        result['active_work']=verify_zero_state(facts)
        result['zero_state_proven']=True
        artifacts=auth.historical_artifacts(document['summary_path'],document['artifact_roots'],scope)
        auth.require(artifacts==facts['historical_artifacts'], 'historical artifact changed')
        result.update(original_historical_artifact_preserved=True,
                      original_terminal_summary_sha256=facts['historical_artifacts'][document['summary_path']]['sha256'],
                      status='FAILED_RUN_CLEANUP_COMPLETE',resolved_at=now.isoformat())
        write_campaign_terminal_summary(directory/RESOLUTION,summary=result)
    except BaseException as exc:
        result.update(status='FAILED_RUN_CLEANUP_APPLICATION_FAILED',application_error=f'{type(exc).__name__}:{exc}')
        try:
            write_campaign_terminal_summary(directory/TERMINAL,summary=result)
        except BaseException as artifact_error:
            exc.add_note(f'Consumed; terminal artifact failure: {type(artifact_error).__name__}:{artifact_error}')
        raise
    finally:
        deactivate_writer_attribution(facts['database']['path'])
    return result
