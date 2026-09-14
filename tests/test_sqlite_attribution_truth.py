"""Transaction evidence against real disposable SQLite, including lock failures."""
import json
import sqlite3
import time

import pytest

from printer_v1.db.sqlite_write_contracts import (
    activate_writer_attribution, connect_attributed, deactivate_writer_attribution,
    set_writer_attribution_context, writer_attribution_connection_id,
)


@pytest.fixture
def fixture_db(tmp_path):
    db = tmp_path / 'test.sqlite'
    with sqlite3.connect(db) as seed:
        seed.execute('CREATE TABLE items (value INTEGER)')
        seed.executemany('INSERT INTO items VALUES (?)', [(1,), (2,), (3,)])
    seed.close()
    timeline = activate_writer_attribution(db, artifact_path=tmp_path / 'trace.json', max_records=512)
    connections = []
    def connect(role='TEST'):
        conn = connect_attributed(db, connection_role=role, timeout=.02)
        connections.append(conn)
        set_writer_attribution_context(conn, owner='fixture', operation='SOURCE_RESPONSE_RECORD', context={'nested': {'value': 1}})
        return conn
    yield db, timeline, connect
    for conn in connections:
        conn.close()
    deactivate_writer_attribution(db)


def active(timeline, conn):
    return next((t for t in timeline._payload()['active_transactions'] if t['connection_id'] == writer_attribution_connection_id(conn)), None)


def events(timeline, conn):
    return [r['event'] for r in timeline._payload()['records'] if r.get('connection_id') == writer_attribution_connection_id(conn)]


@pytest.mark.parametrize('surface,sql,params', [
    ('connection', 'BEGIN IMMEDIATE', ()),
    ('cursor', 'BEGIN IMMEDIATE', ()),
    ('connection', 'INSERT INTO items VALUES (?)', (4,)),
    ('cursor', 'INSERT INTO items VALUES (?)', (4,)),
    ('connection_many', 'INSERT INTO items VALUES (?)', [(4,), (5,)]),
    ('cursor_many', 'INSERT INTO items VALUES (?)', [(4,), (5,)]),
    ('connection', '-- lead\n/* comment */ INSERT INTO items VALUES (4)', ()),
    ('connection_script', 'BEGIN; INSERT INTO items VALUES (4);', None),
    ('cursor_script', 'BEGIN IMMEDIATE; INSERT INTO items VALUES (4);', None),
])
def test_write_api_matrix(fixture_db, surface, sql, params):
    _, timeline, connect = fixture_db
    conn = connect()
    target = conn.cursor() if surface.startswith('cursor') else conn
    if surface.endswith('many'):
        target.executemany(sql, params)
    elif surface.endswith('script'):
        target.executescript(sql)
    else:
        target.execute(sql, params)
    tx = active(timeline, conn)
    assert conn.in_transaction and tx is not None
    assert tx['transaction_kind'] == 'WRITE'
    assert tx['begin_requested_monotonic'] <= tx['begin_acquired_monotonic']
    assert tx['transaction_owner'] == 'fixture'
    assert tx['transaction_operation'] == 'SOURCE_RESPONSE_RECORD'
    conn.commit()
    assert not conn.in_transaction and active(timeline, conn) is None
    assert events(timeline, conn)[-2:] == ['TRANSACTION_COMMIT_REQUESTED', 'TRANSACTION_COMMIT_SUCCEEDED']


@pytest.mark.parametrize('sql', ['COMMIT', 'END', '/*comment*/ COMMIT TRANSACTION'])
def test_read_transaction_sql_terminal(fixture_db, sql):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('BEGIN')
    assert active(timeline, conn)['transaction_kind'] == 'UNKNOWN'
    conn.execute('SELECT * FROM items').fetchall()
    assert active(timeline, conn)['transaction_kind'] == 'READ'
    result = timeline.contention_attribution(heartbeat_connection_id=None, attempt_started_monotonic=time.monotonic())
    assert result['disposition'] == 'PROVEN_APPLICATION_OWNED_OVERLAPPING_READER'
    assert result['external_or_uninstrumented_blocker_possible'] is True
    conn.execute(sql)
    assert not conn.in_transaction and active(timeline, conn) is None
    assert 'TRANSACTION_COMMIT_SUCCEEDED' in events(timeline, conn)


def test_failed_commit_retains_writer_and_reader_is_not_writer(fixture_db):
    _, timeline, connect = fixture_db
    reader, writer = connect('READER'), connect('HEARTBEAT')
    reader.execute('BEGIN')
    reader.execute('SELECT * FROM items').fetchall()
    writer.execute('BEGIN IMMEDIATE')
    writer.execute('UPDATE items SET value=value+1')
    txid = active(timeline, writer)['transaction_id']
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        writer.commit()
    assert writer.in_transaction
    assert active(timeline, writer)['transaction_id'] == txid
    assert events(timeline, writer)[-1] == 'TRANSACTION_COMMIT_FAILED'
    result = timeline.contention_attribution(heartbeat_connection_id=writer_attribution_connection_id(writer), attempt_started_monotonic=time.monotonic())
    assert result['disposition'] == 'PROVEN_APPLICATION_OWNED_OVERLAPPING_READER'
    writer.rollback()
    assert active(timeline, writer) is None
    assert events(timeline, writer)[-1] == 'TRANSACTION_ROLLBACK_SUCCEEDED'


@pytest.mark.parametrize('surface', ['connection', 'cursor'])
def test_scripts_autocommit_and_explicit_terminals(fixture_db, surface):
    _, timeline, connect = fixture_db
    conn = connect()
    target = conn if surface == 'connection' else conn.cursor()
    target.executescript("INSERT INTO items VALUES (4); BEGIN; INSERT INTO items VALUES (5); COMMIT;")
    assert not conn.in_transaction and active(timeline, conn) is None
    recorded = events(timeline, conn)
    assert 'STATEMENT_EXECUTION_SUCCEEDED' in recorded
    assert 'TRANSACTION_COMMIT_SUCCEEDED' in recorded
    assert conn.execute('SELECT count(*) FROM items').fetchone()[0] == 5


def test_savepoint_release_and_rollback_to(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('SAVEPOINT outer')
    assert active(timeline, conn)['transaction_kind'] == 'UNKNOWN'
    conn.execute('INSERT INTO items VALUES (4)')
    assert active(timeline, conn)['transaction_kind'] == 'WRITE'
    conn.execute('SAVEPOINT inner')
    conn.execute('ROLLBACK TO inner')
    assert conn.in_transaction and active(timeline, conn)
    conn.execute('RELEASE inner')
    assert conn.in_transaction and active(timeline, conn)
    conn.execute('RELEASE outer')
    assert not conn.in_transaction and active(timeline, conn) is None
    assert 'SAVEPOINT_RELEASE_SUCCEEDED' in events(timeline, conn)


@pytest.mark.parametrize('fails', [False, True])
def test_context_manager_truth(fixture_db, fails):
    _, timeline, connect = fixture_db
    conn = connect()
    try:
        with conn:
            conn.execute('INSERT INTO items VALUES (4)')
            if fails:
                raise ValueError('fixture')
    except ValueError:
        pass
    assert not conn.in_transaction and active(timeline, conn) is None
    assert events(timeline, conn)[-1] == ('TRANSACTION_ROLLBACK_SUCCEEDED' if fails else 'TRANSACTION_COMMIT_SUCCEEDED')


def test_context_snapshot_and_with_write(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('BEGIN')
    conn.execute('WITH x AS (SELECT 4) INSERT INTO items SELECT * FROM x')
    assert active(timeline, conn)['transaction_kind'] == 'WRITE'
    set_writer_attribution_context(conn, owner='snapshot', operation='SNAPSHOT', context={'nested': {'value': 2}})
    assert active(timeline, conn)['transaction_operation'] == 'SOURCE_RESPONSE_RECORD'
    assert active(timeline, conn)['context']['nested']['value'] == 1
    conn.commit()
    conn.execute('INSERT INTO items VALUES (5)')
    assert active(timeline, conn)['transaction_operation'] == 'SNAPSHOT'


def test_close_active_transaction_is_rollback(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('BEGIN IMMEDIATE')
    cid = writer_attribution_connection_id(conn)
    conn.close()
    data = json.loads(timeline.artifact_path.read_text())
    assert not data['active_transactions']
    records = [r for r in data['records'] if r.get('connection_id') == cid]
    assert records[-2]['event'] == 'TRANSACTION_CLOSE_ROLLBACK_SUCCEEDED'


def test_autocommit_cursor_shared_lock_is_visible_until_exhausted(fixture_db):
    _, timeline, connect = fixture_db
    reader, writer = connect('READER'), connect('WRITER')
    cursor = reader.execute('SELECT * FROM items')
    assert not reader.in_transaction
    writer.execute('BEGIN IMMEDIATE')
    writer.execute('UPDATE items SET value=value+1')
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        writer.commit()
    result = timeline.contention_attribution(heartbeat_connection_id=writer_attribution_connection_id(writer), attempt_started_monotonic=time.monotonic())
    assert result['disposition'] == 'PROVEN_APPLICATION_OWNED_OVERLAPPING_READER'
    assert result['candidates'][0]['activity_scope'] == 'OPEN_RESULT_CURSOR'
    cursor.fetchall()
    writer.commit()
    assert not timeline.contention_attribution(heartbeat_connection_id=None, attempt_started_monotonic=time.monotonic())['candidates']


def test_failed_context_manager_commit_records_failure_then_rollback(fixture_db):
    _, timeline, connect = fixture_db
    reader, writer = connect('READER'), connect('WRITER')
    reader.execute('BEGIN')
    reader.execute('SELECT * FROM items').fetchall()
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        with writer:
            writer.execute('INSERT INTO items VALUES (4)')
    assert not writer.in_transaction and active(timeline, writer) is None
    recorded = events(timeline, writer)
    assert 'TRANSACTION_COMMIT_FAILED' in recorded
    assert 'TRANSACTION_COMMIT_SUCCEEDED' not in recorded
    assert recorded[-1] == 'TRANSACTION_ROLLBACK_SUCCEEDED'


def test_real_campaign_heartbeat_reader_contention(tmp_path):
    from datetime import timedelta
    from test_v2_9_8b_20_sqlite_heartbeat_concurrency import _seed_supervision, NOW
    from printer_v1.db import apply_migrations
    from printer_v1.db.sqlite_write_contracts import active_writer_attribution
    from printer_v1.operator_cli.campaign_supervision import renew_campaign_lease
    db = tmp_path / 'campaign.sqlite'
    apply_migrations(db)
    ids = _seed_supervision(db)
    reader = connect_attributed(db, connection_role='FIXTURE_SHARED_READER')
    try:
        reader.execute('BEGIN')
        reader.execute('SELECT * FROM printer_memory_factory_campaign_supervision').fetchall()
        result = renew_campaign_lease(db, **ids, now=NOW + timedelta(seconds=30))
        assert result['renewal_confirmed'] is False
        attribution = result['writer_attribution']
        assert attribution['disposition'] == 'PROVEN_APPLICATION_OWNED_OVERLAPPING_READER'
        assert attribution['failure_phase'] == 'COMMIT'
        assert attribution['connection_id'] == writer_attribution_connection_id(reader)
        records = active_writer_attribution(db)._payload()['records']
        failed = [r for r in records if r['event'] == 'TRANSACTION_COMMIT_FAILED']
        assert failed and all(r['transaction_kind'] == 'WRITE' for r in failed)
    finally:
        reader.close()
        deactivate_writer_attribution(db)


@pytest.mark.parametrize('module,name,role', [
    ('printer_v1.sources.recording', 'writable_connection', 'SOURCE_GOVERNOR_PERSISTENCE'),
    ('printer_v1.scheduler._scheduler_base', 'connect', 'SCHEDULER_PERSISTENCE'),
    ('printer_v1.snapshots.recorder', 'connect', 'SNAPSHOT_PERSISTENCE'),
    ('printer_v1.lifecycle.tracking_queue', 'connect', 'LIFECYCLE_PERSISTENCE'),
])
def test_operational_scope_connections_preserve_contract(fixture_db, module, name, role):
    import importlib
    db, timeline, _ = fixture_db
    with getattr(importlib.import_module(module), name)(db) as conn:
        cid = writer_attribution_connection_id(conn)
        assert cid is not None
        assert timeline._connections[cid]['connection_role'] == role
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 0
        conn.execute('INSERT INTO items VALUES (7)')
        assert active(timeline, conn)['transaction_kind'] == 'WRITE'
    assert not timeline._payload()['active_transactions']


def test_campaign_and_read_only_supervision_connections(fixture_db):
    from printer_v1.operator_cli.campaign_persistence import _connect
    from printer_v1.operator_cli.campaign_supervision import _connect as supervise_connect
    db, _, _ = fixture_db
    conn = _connect(db)
    try:
        assert writer_attribution_connection_id(conn)
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 5000
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    finally:
        conn.close()
    conn = supervise_connect(db, read_only=True, busy_timeout_seconds=.05)
    try:
        assert writer_attribution_connection_id(conn)
        assert conn.execute('PRAGMA busy_timeout').fetchone()[0] == 50
        assert conn.execute('PRAGMA query_only').fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            conn.execute('INSERT INTO items VALUES (8)')
    finally:
        conn.close()


def test_failed_begin_preserves_real_writer_identity(fixture_db):
    _, timeline, connect = fixture_db
    writer, heartbeat = connect('WRITER'), connect('HEARTBEAT')
    writer.execute('BEGIN IMMEDIATE')
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        heartbeat.cursor().execute('BEGIN IMMEDIATE')
    assert not heartbeat.in_transaction and active(timeline, heartbeat) is None
    assert events(timeline, heartbeat)[-1] == 'TRANSACTION_BEGIN_FAILED'
    result = timeline.contention_attribution(heartbeat_connection_id=writer_attribution_connection_id(heartbeat), attempt_started_monotonic=time.monotonic())
    assert result['disposition'] == 'PROVEN_APPLICATION_OWNED_OVERLAPPING_WRITER'
    assert result['connection_id'] == writer_attribution_connection_id(writer)


@pytest.mark.parametrize('sql', [
    "/* start */ WITH x AS (SELECT 'DELETE') UPDATE items SET value=4",
    'WITH RECURSIVE x(a) AS (SELECT 1 UNION ALL SELECT a+1 FROM x WHERE a<2) INSERT INTO items SELECT a FROM x',
    'CREATE TABLE another (a)', 'ALTER TABLE items ADD COLUMN extra',
])
def test_classifier_write_after_deferred_begin(fixture_db, sql):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('BEGIN')
    conn.execute(sql)
    assert active(timeline, conn)['transaction_kind'] == 'WRITE'


def test_nested_savepoint_failed_release_keeps_transaction(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.executescript('SAVEPOINT a; INSERT INTO items VALUES (4); SAVEPOINT b;')
    txid = active(timeline, conn)['transaction_id']
    with pytest.raises(sqlite3.OperationalError):
        conn.execute('RELEASE missing')
    assert conn.in_transaction and active(timeline, conn)['transaction_id'] == txid
    conn.execute('ROLLBACK TO a')
    conn.execute('RELEASE a')
    assert not conn.in_transaction and active(timeline, conn) is None
    assert conn.execute('SELECT count(*) FROM items').fetchone()[0] == 3


def test_actual_snapshot_boundary_replaces_source_response_context(tmp_path):
    from printer_v1.db import apply_migrations
    from printer_v1.operator_cli.e2m_snapshot_persistence import persist_snapshot_from_source_response, E2M_STATUS_PERSISTED
    from tests.test_post_rc_lane_e2m_snapshot_persistence import _DbTestBase, _MINT_1, _PAIR_1
    db = tmp_path / 'snapshot.sqlite'
    apply_migrations(db)
    timeline = activate_writer_attribution(db, artifact_path=tmp_path / 'snapshot.json')
    conn = connect_attributed(db, connection_role='FACTORY_MAIN')
    conn.row_factory = sqlite3.Row
    try:
        set_writer_attribution_context(conn, owner='source', operation='SOURCE_RESPONSE_RECORD')
        _, response_id = _DbTestBase()._make_clean_response(conn)
        assert not conn.in_transaction
        result = persist_snapshot_from_source_response(conn, response_id, _MINT_1, expected_pair_address=_PAIR_1)
        assert result['e2m_status'] == E2M_STATUS_PERSISTED
        tx = active(timeline, conn)
        assert tx['transaction_operation'] == 'SNAPSHOT'
        assert tx['transaction_owner'] == 'persist_snapshot_from_source_response'
        assert tx['context']['source_response_id'] == response_id
    finally:
        conn.close()
        deactivate_writer_attribution(db)


@pytest.mark.parametrize('kinds,expected', [
    (['READ', 'READ'], 'AMBIGUOUS_APPLICATION_OWNED_READERS'),
    (['READ', 'WRITE'], 'MIXED_APPLICATION_OWNED_READERS_AND_WRITERS'),
    (['UNKNOWN'], 'UNKNOWN_APPLICATION_OWNED_TRANSACTIONS'),
])
def test_contention_kind_dispositions(fixture_db, kinds, expected):
    _, timeline, connect = fixture_db
    for kind in kinds:
        conn = connect(kind)
        conn.execute('BEGIN IMMEDIATE' if kind == 'WRITE' else 'BEGIN')
        if kind == 'READ':
            conn.execute('SELECT * FROM items').fetchall()
    result = timeline.contention_attribution(heartbeat_connection_id=None, attempt_started_monotonic=time.monotonic())
    assert result['disposition'] == expected
    assert result['causal_blocker_proven'] is False


@pytest.mark.parametrize('surface', ['sql', 'script'])
def test_failed_sql_commit_keeps_transaction(fixture_db, surface):
    _, timeline, connect = fixture_db
    reader, writer = connect('READER'), connect('WRITER')
    reader.execute('BEGIN')
    reader.execute('SELECT * FROM items').fetchall()
    writer.execute('BEGIN IMMEDIATE')
    writer.execute('UPDATE items SET value=value+1')
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        if surface == 'sql':
            writer.cursor().execute('COMMIT')
        else:
            writer.executescript('SELECT 1;')  # native legacy pre-script COMMIT
    assert writer.in_transaction and active(timeline, writer)
    assert events(timeline, writer)[-1] == 'TRANSACTION_COMMIT_FAILED'


def test_script_error_after_commit_does_not_claim_commit_failed(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    with pytest.raises(sqlite3.OperationalError):
        conn.executescript('BEGIN; INSERT INTO items VALUES (9); COMMIT; NOT SQL;')
    assert not conn.in_transaction and active(timeline, conn) is None
    assert 'TRANSACTION_COMMIT_FAILED' not in events(timeline, conn)
    assert conn.execute('SELECT count(*) FROM items WHERE value=9').fetchone()[0] == 1


def test_trigger_failure_does_not_report_autocommit_success(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.executescript("CREATE TRIGGER reject_insert BEFORE INSERT ON items BEGIN SELECT RAISE(ABORT, 'no'); END;")
    before = len(timeline._records)
    with pytest.raises(sqlite3.IntegrityError):
        conn.executescript('INSERT INTO items VALUES (9);')
    assert not any(r['event'] == 'STATEMENT_EXECUTION_SUCCEEDED' for r in timeline._records[before:])


def test_unified_terminal_uses_attributed_connection(tmp_path):
    from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
        _prepare, CAMPAIGN_ID, CAMPAIGN_RUN_ID, CYCLE_ID, FACTORY_RUN_ID, START,
    )
    from printer_v1.operator_cli.unified_terminal_closure import reconcile_campaign_terminal
    db, _, _ = _prepare(tmp_path)
    timeline = activate_writer_attribution(db, artifact_path=tmp_path / 'terminal.json', max_records=512)
    try:
        result = reconcile_campaign_terminal(
            db, campaign_id=CAMPAIGN_ID, run_id=CAMPAIGN_RUN_ID, cycle_id=CYCLE_ID,
            terminal_cause='FIXTURE_STOP', run_status='SAFE_STOPPED', factory_run_id=FACTORY_RUN_ID,
            lifecycle_started=False, now=START.isoformat(),
        )
        assert result['reconciled'] is True
        records = timeline._payload()['records']
        assert any(r.get('connection_role') == 'UNIFIED_TERMINAL_RECONCILIATION'
                   and r['event'] == 'TRANSACTION_COMMIT_SUCCEEDED' for r in records)
        assert not timeline._payload()['active_transactions']
        assert not timeline._payload()['active_connections']
    finally:
        deactivate_writer_attribution(db)


def test_open_select_result_does_not_claim_autocommit_completed(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    cursor = conn.execute('SELECT * FROM items')
    assert 'STATEMENT_AUTOCOMMIT_SUCCEEDED' not in events(timeline, conn)
    cursor.close()


def test_unclassified_sql_cannot_leave_a_writer_labeled_read(fixture_db):
    _, timeline, connect = fixture_db
    conn = connect()
    conn.execute('BEGIN')
    conn.execute('SELECT * FROM items').fetchall()
    conn.execute('PRAGMA user_version=7')  # writes, deliberately outside narrow classifier
    conn.execute('SELECT * FROM items').fetchall()
    assert active(timeline, conn)['transaction_kind'] == 'UNKNOWN'
    assert timeline.contention_attribution(heartbeat_connection_id=None, attempt_started_monotonic=time.monotonic())['disposition'] == 'UNKNOWN_APPLICATION_OWNED_TRANSACTIONS'


def test_failed_write_can_hold_a_lock_without_proven_write_classification(fixture_db):
    _, timeline, connect = fixture_db
    conn, other = connect(), connect()
    conn.execute('CREATE UNIQUE INDEX item_value ON items(value)')
    conn.execute('BEGIN')
    conn.execute('SELECT * FROM items').fetchall()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute('INSERT INTO items VALUES (1)')
    with pytest.raises(sqlite3.OperationalError, match='locked'):
        other.execute('BEGIN IMMEDIATE')
    assert active(timeline, conn)['transaction_kind'] == 'UNKNOWN'
