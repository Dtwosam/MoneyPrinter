"""Post-close queue disposition must not erase proven four-hour completion."""
import pytest

from printer_v1.operator_cli import one_command_15m_factory as factory


@pytest.mark.parametrize("disposition", ["COOLDOWN", "ARCHIVED"])
@pytest.mark.parametrize("missing_close", [False, True])
def test_terminal_disposition_still_requires_exact_four_hour_evidence(disposition, missing_close):
    from tests.test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset import (
        StandardFourHourEligibleSubsetTests,
    )
    case = StandardFourHourEligibleSubsetTests()
    case.setUp()
    try:
        case._plan(["slot-2"])
        case._terminalize_dirty_eligible_token(2)
        connection = case.fx.connection
        with connection:
            connection.execute(
                "UPDATE printer_memory_factory_campaign_token_slots SET token_state=?, "
                "first_terminal_cause='OWNED_TERMINAL_WINDOW_COOLDOWN', "
                "terminal_at='2026-08-07T16:05:00+00:00' "
                "WHERE token_slot_id='slot-2'", (disposition,),
            )
            if missing_close:
                connection.execute(
                    "DELETE FROM printer_memory_factory_campaign_scheduler_work "
                    "WHERE scheduler_job_id IN (SELECT scheduler_job_id FROM "
                    "printer_memory_factory_run_steps WHERE run_id='factory-run-1' "
                    "AND token_id=2 AND step_kind='LONG_CONTINUATION_CLOSE_AUDIT')"
                )
        result = factory._standard_campaign_four_hour_terminal_validation(
            connection, factory_run_id="factory-run-1", campaign_id="campaign-1h",
            run_id="run-1h", cycle_id="cycle-1h",
        )
        assert result["complete"] is (not missing_close), result["reasons"]
        # Honest dirty evidence stays dirty; terminal disposition grants no promotion.
        assert result["eligible_window_details"][0]["window_state"] == "DIRTY"
    finally:
        case.tearDown()
