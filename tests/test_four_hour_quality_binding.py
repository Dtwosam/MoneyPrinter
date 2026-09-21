"""Physical 4h ownership must be visible before independent quality readers."""
from contextlib import closing
import sqlite3

import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.campaign_ownership import CampaignOwnershipError
from tests import test_v2_9_8b_post_dtw100_standard_four_hour_close_memory_terminal_reconciliation as fixtures


@pytest.fixture
def close_case():
    case = fixtures.StandardFourHourCloseMemoryTerminalTests()
    case.setUp()
    try:
        yield case
    finally:
        case.tearDown()


def _job(case, token_id=1):
    return case.fx.connection.execute(
        "SELECT scheduler_job_id FROM printer_memory_factory_run_steps "
        "WHERE token_id=? AND step_kind='LONG_CONTINUATION_CLOSE_AUDIT'",
        (token_id,),
    ).fetchone()[0]


def test_quality_binding_is_durable_without_premature_success(close_case):
    case = close_case
    case._set_close_pending(1)
    memory_id = case._insert_physical_4h(1)
    factory._bind_owned_long_memory_before_quality(
        case.fx.connection, scheduler_job_id=_job(case), memory_window_row_id=memory_id,
    )
    path = case.fx.connection.execute('PRAGMA database_list').fetchone()[2]
    with closing(sqlite3.connect(path)) as reader:
        row = reader.execute(
            "SELECT memory_window_row_id,window_state,first_terminal_cause,terminal_at "
            "FROM printer_memory_factory_campaign_windows WHERE window_id=?",
            (case._window(1)["window_id"],),
        ).fetchone()
    assert row == (memory_id, "CLOSE_PENDING", None, None)
    assert case._window(1)["token_state"] == "WINDOW_4H_CONTINUING"
    assert case._window(2)["memory_window_row_id"] is None
    # Repeating the same bind is lawful, but creates no clean object.
    factory._bind_owned_long_memory_before_quality(
        case.fx.connection, scheduler_job_id=_job(case), memory_window_row_id=memory_id,
    )
    assert case.fx.connection.execute(
        "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?", (memory_id,)
    ).fetchone()[0] == 0


def test_quality_binding_rejects_other_tokens_memory(close_case):
    case = close_case
    case._set_close_pending(1)
    memory_id = case._insert_physical_4h(2)
    with pytest.raises(CampaignOwnershipError, match="identity mismatch"):
        factory._bind_owned_long_memory_before_quality(
            case.fx.connection, scheduler_job_id=_job(case), memory_window_row_id=memory_id,
        )
    assert case._window(1)["memory_window_row_id"] is None
    assert case._window(1)["window_state"] == "CLOSE_PENDING"


def test_quality_binding_requires_real_close_pending(close_case):
    case = close_case
    memory_id = case._insert_physical_4h(1)
    with pytest.raises(ValueError, match="CLOSE_PENDING"):
        factory._bind_owned_long_memory_before_quality(
            case.fx.connection, scheduler_job_id=_job(case), memory_window_row_id=memory_id,
        )
    assert case._window(1)["memory_window_row_id"] is None
