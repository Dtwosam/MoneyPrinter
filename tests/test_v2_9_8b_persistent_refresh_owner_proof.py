from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from printer_v1.db import apply_migrations
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    REFRESH_COMPLETED,
)
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def test_same_authorization_completes_three_scheduler_owned_refresh_ordinals(tmp_path):
    db_path = tmp_path / "proof.sqlite3"
    apply_migrations(db_path)

    current = [datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)]
    in_stage_reports = []

    def waiter(seconds: float) -> bool:
        current[0] = current[0] + timedelta(seconds=seconds)
        return False

    def clock() -> str:
        return _iso(current[0])

    def refresh_stage(connection, **kwargs):
        # This callback executes after the Scheduler claim and RUNNING durable
        # refresh-work insertion, so clean terminal must be false here.
        in_stage_reports.append(
            campaign_active_work_report(
                connection,
                campaign_id="campaign-proof",
                run_id="run-proof",
                cycle_id="cycle-proof",
            )
        )
        ordinal = int(kwargs["refresh_ordinal"])
        return {
            "source_operations": 1,
            "provider_failures": 0,
            "channels_unavailable": (),
            "channels_attempted": (f"fixture-source-{ordinal}",),
            "channels_skipped": (),
            "newly_observed_exact_identities": (
                {"mint": f"MINT_{ordinal}", "pool": f"POOL_{ordinal}"},
            ),
            "promoted_observation_eligible": (),
        }

    owner = PreLifecycleTemporalRefreshOwner(
        db_path,
        campaign_id="campaign-proof",
        run_id="run-proof",
        cycle_id="cycle-proof",
        supervision_id="supervision-proof",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at="2026-08-16T00:40:00+00:00",
        work_deadline_at="2026-08-16T01:00:00+00:00",
        refresh_stage=refresh_stage,
        supervision_probe=lambda: {
            "supervision_active": True,
            "cancellation_requested": False,
        },
        waiter=waiter,
        clock=clock,
        refresh_interval_seconds=600,
    )

    outcomes = []
    remaining = 30
    for _ in range(3):
        outcome = owner.request_temporal_refresh(
            reserve_depth=2,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=remaining,
            provider_terminal_failure=False,
            now="2026-08-16T00:00:00+00:00",
        )
        assert outcome.status == REFRESH_COMPLETED
        remaining -= outcome.source_operations
        outcomes.append(outcome)

    assert [outcome.refresh_ordinal for outcome in outcomes] == [1, 2, 3]
    assert [outcome.source_operations for outcome in outcomes] == [1, 1, 1]
    assert [outcome.channels_attempted for outcome in outcomes] == [
        ("fixture-source-1",),
        ("fixture-source-2",),
        ("fixture-source-3",),
    ]
    assert all(report["clean_terminal"] is False for report in in_stage_reports)
    assert all(report["active_work_rows"] >= 1 for report in in_stage_reports)
    assert all(
        any(
            detail.get("owner_table")
            == "printer_pre_lifecycle_discovery_refresh_work"
            for detail in report["active_work_details"]
        )
        for report in in_stage_reports
    )

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        work_rows = connection.execute(
            """SELECT refresh_ordinal, work_state, first_terminal_cause
               FROM printer_pre_lifecycle_discovery_refresh_work
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
               ORDER BY refresh_ordinal""",
            ("campaign-proof", "run-proof", "cycle-proof"),
        ).fetchall()
        assert [int(row["refresh_ordinal"]) for row in work_rows] == [1, 2, 3]
        assert [str(row["work_state"]) for row in work_rows] == [
            "SUCCEEDED",
            "SUCCEEDED",
            "SUCCEEDED",
        ]
        assert all(
            str(row["first_terminal_cause"]) == "PRE_LIFECYCLE_REFRESH_COMPLETED"
            for row in work_rows
        )

        job_rows = connection.execute(
            """SELECT status
               FROM printer_scheduler_jobs
               WHERE job_name LIKE 'PRE_LIFECYCLE_DISCOVERY_REFRESH:campaign-proof:%'
               ORDER BY id"""
        ).fetchall()
        assert [str(row["status"]) for row in job_rows] == [
            "SUCCEEDED",
            "SUCCEEDED",
            "SUCCEEDED",
        ]

        # The repair must not consume or collide with the legacy one-per-cycle
        # discovery work slot.
        legacy_work = connection.execute(
            """SELECT COUNT(*) FROM printer_discovery_work
               WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
            ("campaign-proof", "run-proof", "cycle-proof"),
        ).fetchone()[0]
        assert int(legacy_work) == 0

        final_report = campaign_active_work_report(
            connection,
            campaign_id="campaign-proof",
            run_id="run-proof",
            cycle_id="cycle-proof",
        )
        assert final_report["active_jobs"] == 0
        assert final_report["active_work_rows"] == 0
        assert final_report["terminal_work_with_active_job"] == 0
        assert final_report["active_pre_lifecycle_refresh_waits"] == 0
        assert final_report["clean_terminal"] is True
    finally:
        connection.close()
