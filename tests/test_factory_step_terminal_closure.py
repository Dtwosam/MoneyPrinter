"""Exact-run terminal closure on migrated disposable state, with offline guard."""
from pathlib import Path

import pytest

from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
from tests.test_v2_9_8b_reconcile_already_terminal_factory_persist_repair import (
    CAMPAIGN, RUN, CYCLE, FACTORY, NOW, _seed, _open,
)

CAUSE = 'LEASE_RENEWAL_SQLITE_LOCKED'


def _rows(db):
    connection = _open(db)
    try:
        return {
            table: [dict(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY rowid')]
            for (table,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        }
    finally:
        connection.close()


def seed_step_closure_graph(tmp_path: Path, factory_status='RUNNING'):
    db = tmp_path / 'closure.sqlite3'
    _seed(db, campaign_state='RUNNING', run_state='RUNNING',
          cycle_state='TRACKING', factory_status=factory_status)
    instant = NOW.isoformat()
    connection = _open(db)
    with connection:
        connection.execute("INSERT INTO printer_tokens(id,token_mint) VALUES (1,'mint')")
        connection.execute("INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (1,1,'pair')")
        connection.execute("""INSERT INTO printer_token_snapshots(
            id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,source_status,data_quality_label)
            VALUES (1,1,1,?,'TRACK_FAST','OFFLINE','COMPLETE','CLEAN_DATA')""", (instant,))
        connection.execute("""UPDATE printer_memory_factory_run_steps SET snapshot_id=1,
            result_json='{"snapshot_id":1,"evidence":"preserve exact bytes"}',token_id=1,pair_id=1
            WHERE run_id=?""", (FACTORY,))
        connection.execute("""INSERT INTO printer_memory_factory_runs(
            run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at)
            VALUES ('unrelated','RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',?)""", (instant,))
        for index, (owner, state, reason, finished) in enumerate([
            (FACTORY, 'PENDING', None, None),
            (FACTORY, 'RUNNING', 'EXISTING_REASON', instant),
            (FACTORY, 'FAILED', 'FAILED_REASON', instant),
            (FACTORY, 'CANCELLED', 'OLD_CAUSE', instant),
            (FACTORY, 'SKIPPED', 'SKIP_REASON', instant),
            (FACTORY, 'OTHER_TERMINAL', 'OTHER_REASON', instant),
            ('unrelated', 'PENDING', None, None),
            ('unrelated', 'RUNNING', None, None),
        ], 1):
            connection.execute("""INSERT INTO printer_scheduler_jobs(
                id,job_name,job_kind,status,scheduled_for,locked_at,lock_owner)
                VALUES (?,?,'SNAPSHOT',?,?,?,?)""",
                (index, f'isolated-job-{index}', state, instant,
                 instant if state == 'RUNNING' else None, 'worker' if state == 'RUNNING' else None))
            connection.execute("""INSERT INTO printer_memory_factory_run_steps(
                run_id,step_key,step_kind,step_status,token_id,pair_id,scheduled_for,
                scheduler_job_id,error_or_skip_reason,finished_at,created_at,updated_at)
                VALUES (?,?,'SNAPSHOT',?,1,1,?,?,?,?,?,?)""",
                (owner, f'mixed-{index}', state, instant, index, reason, finished, instant, instant))
        connection.execute("""INSERT INTO printer_tracking_queue(
            id,token_id,pair_id,tracking_lane,tracking_action,queue_status,source_status,data_quality_label)
            VALUES (1,1,1,'TRACK_FAST','PROMOTE_TO_TRACK_FAST','QUEUED','COMPLETE','CLEAN_DATA')""")
        connection.execute("""INSERT INTO printer_memory_factory_campaign_token_slots(
            token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,token_identity,token_row_id,
            mint_identity,pair_identity,pair_row_id,lifecycle_identity,tracking_queue_id,
            token_state,created_at,updated_at)
            VALUES ('slot',?,?,?,1,'token',1,'mint','pair',1,'root',1,'SELECTED',?,?)""",
            (CAMPAIGN, RUN, CYCLE, instant, instant))
        connection.execute("""INSERT INTO printer_memory_factory_campaign_windows(
            window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,pair_row_id,
            window_kind,window_state,root_15m_lifecycle_identity,checkpoint_cutoff,support_only,
            created_at,updated_at)
            VALUES ('window',?,?,?,'slot',1,1,'WINDOW_15M','COLLECTING','root',?,0,?,?)""",
            (CAMPAIGN, RUN, CYCLE, instant, instant, instant))
    connection.close()
    return db


@pytest.mark.parametrize('factory_status', ['RUNNING', 'SAFE_STOPPED'])
def test_exact_factory_step_closure_preserves_evidence_and_replay(tmp_path: Path, factory_status):
    db = seed_step_closure_graph(tmp_path, factory_status)
    instant = NOW.isoformat()
    before = _rows(db)
    kwargs = dict(campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
                  factory_run_id=FACTORY, lifecycle_started=True, run_status='FAILED',
                  terminal_cause=CAUSE, now=instant)
    result = reconcile_campaign_terminal(db, **kwargs)
    after = _rows(db)
    steps = 'printer_memory_factory_run_steps'
    for old, new in zip(before[steps], after[steps], strict=True):
        if old['run_id'] == FACTORY and old['step_status'] in ('PENDING', 'RUNNING'):
            assert new == {**old, 'step_status': 'CANCELLED',
                           'error_or_skip_reason': old['error_or_skip_reason'] or CAUSE,
                           'finished_at': old['finished_at'] or instant, 'updated_at': instant}
        else:
            assert new == old
    assert after['printer_token_snapshots'] == before['printer_token_snapshots']
    jobs = after['printer_scheduler_jobs']
    assert all(row['status'] == 'CANCELLED' and row['locked_at'] is None
               and row['lock_owner'] is None for row in jobs[:2])
    assert jobs[2:] == before['printer_scheduler_jobs'][2:]
    assert after['printer_memory_factory_runs'][1] == before['printer_memory_factory_runs'][1]
    assert result['factory_run'] == 'SAFE_STOPPED'
    for table, column, state in [
        ('printer_memory_factory_campaigns', 'campaign_state', 'TERMINAL_FAILED'),
        ('printer_memory_factory_campaign_runs', 'run_state', 'TERMINAL_FAILED'),
        ('printer_memory_factory_campaign_cycles', 'cycle_state', 'TERMINAL_FAILED'),
        ('printer_memory_factory_campaign_windows', 'window_state', 'CANCELLED'),
        ('printer_memory_factory_campaign_token_slots', 'token_state', 'MANUAL_REVIEW'),
    ]:
        assert after[table][0][column] == state
        assert after[table][0]['first_terminal_cause'] == CAUSE
    assert after['printer_tracking_queue'][0]['queue_status'] == 'SKIPPED'
    assert after['printer_tracking_queue'][0]['tracking_action'] == 'MANUAL_REVIEW'
    for key in ('pending_or_running_run_steps', 'active_jobs', 'active_factory_runs'):
        assert result['active_work'][key] == 0
    assert result['clean_terminal'] is True
    assert result['restart_created'] is result['successor_created'] is False
    replay = reconcile_campaign_terminal(db, **{**kwargs, 'terminal_cause': 'SECOND_CAUSE'})
    assert replay['clean_terminal'] is True
    assert _rows(db) == after
    connection = _open(db)
    try:
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        connection.close()


@pytest.mark.parametrize('supplied_factory', [None, 'missing-factory'])
def test_step_cancellation_requires_existing_exact_factory(tmp_path: Path, supplied_factory):
    db = tmp_path / 'no-exact-owner.sqlite3'
    _seed(db)
    connection = _open(db)
    with connection:
        connection.execute("UPDATE printer_memory_factory_run_steps SET step_status='PENDING'")
    connection.close()
    before = _rows(db)['printer_memory_factory_run_steps']
    reconcile_campaign_terminal(
        db, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
        factory_run_id=supplied_factory, terminal_cause=CAUSE, now=NOW.isoformat(),
    )
    assert _rows(db)['printer_memory_factory_run_steps'] == before
