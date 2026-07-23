"""Offline proof for the E.36-38 snapshot-maturity readiness boundary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from unittest.mock import MagicMock

import pytest

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.bounded_readiness_report import (
    build_bounded_readiness_report,
    canonical_report_bytes,
)
from printer_v1.scheduler.snapshot_maturity import (
    SNAPSHOT_MATURITY_SECONDS,
    SnapshotMaturityContractError,
    SnapshotMaturityState,
    evaluate_snapshot_maturity,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
)

import test_v2_9_7e_33_canonical_readiness_boundary as e33
import test_v2_9_7e_8_origin_to_lifecycle_integration as e8


def _create_transport(block_times: list[int]):
    rows = []
    transactions = {}
    for ordinal, block_time in enumerate(block_times, start=1):
        signature = f"maturitySig{ordinal}"
        slot = 800 + ordinal
        transaction, _mint = e33.create_transaction(
            signature,
            slot,
            block_time,
            mint_label=f"maturity{ordinal}",
        )
        rows.append(e33.signature_row(signature, slot))
        transactions[signature] = transaction
    return e33._FakePumpTransport(list(reversed(rows)), transactions)


def _db_counts(path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        tables = (
            "printer_holder_evidence_attempts",
            "printer_token_snapshots",
            "printer_memory_windows",
            "printer_memory_factory_run_steps",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        )
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
    finally:
        connection.close()


class TestSchedulerMaturityPolicy:
    def test_exact_boundary_and_integer_epoch_are_utc_safe(self) -> None:
        origin_epoch = 1_700_000_000
        due = datetime.fromtimestamp(
            origin_epoch + SNAPSHOT_MATURITY_SECONDS, tz=timezone.utc
        )

        before = evaluate_snapshot_maturity(
            pump_block_time=origin_epoch,
            evaluated_at=due - timedelta(microseconds=1),
        )
        at = evaluate_snapshot_maturity(
            pump_block_time=origin_epoch,
            evaluated_at=due,
        )
        after = evaluate_snapshot_maturity(
            pump_block_time=origin_epoch,
            evaluated_at=due + timedelta(microseconds=1),
        )

        assert before.state is SnapshotMaturityState.IMMATURE
        assert at.state is SnapshotMaturityState.DUE
        assert after.state is SnapshotMaturityState.DUE
        assert at.origin_block_time_utc == datetime.fromtimestamp(
            origin_epoch, tz=timezone.utc
        )
        assert at.due_at_utc == due
        assert at.evaluated_at_utc.tzinfo is timezone.utc

    @pytest.mark.parametrize("value", [True, 0, -1, "1700000000", None, 10**30])
    def test_invalid_pump_epoch_fails_closed_categorically(self, value) -> None:
        decision = evaluate_snapshot_maturity(
            pump_block_time=value,
            evaluated_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
        )
        assert decision.state is SnapshotMaturityState.INVALID_ORIGIN_TIME

    def test_naive_evaluation_clock_is_rejected(self) -> None:
        with pytest.raises(SnapshotMaturityContractError):
            evaluate_snapshot_maturity(
                pump_block_time=1_700_000_000,
                evaluated_at=datetime(2026, 7, 23),
            )

    def test_cancellation_is_terminal_and_due_independent(self) -> None:
        decision = evaluate_snapshot_maturity(
            pump_block_time=1_700_000_000,
            evaluated_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
            cancelled=True,
        )
        assert decision.state is SnapshotMaturityState.CANCELLED
        assert decision.due_at_utc is None


class TestCanonicalMaturityBoundary(e33._SnapshotReadinessBase):
    def _run_cancelled(self, *, transport, now):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_snapshot_readiness(
            command=self.command,
            pump_transport=transport,
            source_governor=e33.GOV,
            central_scheduler=e33.SCH,
            selection_seed="e36-cancel-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=now.isoformat(),
            context_adapter_factories=e33._eligible_safety_factories(),
            geckoterminal_base_adapter_factory=self._base_factory(),
            geckoterminal_transports=e33._gt_15m_transports(now),
            secret_present=True,
            holder_request_pacer=e33._NoSleepPacer(),
            snapshot_request_pacer=e33._NoSleepPacer(),
            cancellation_requested=True,
        )

    def test_immature_candidates_make_zero_holder_and_snapshot_calls(self) -> None:
        now = self._now()
        transport = _create_transport(
            [int(now.timestamp()) - 899, int(now.timestamp()) - 100]
        )
        base_factory = MagicMock(side_effect=AssertionError("snapshot call forbidden"))

        result = self._run(
            pump_transport=transport,
            now=now,
            base_factory=base_factory,
        )

        assert result.status == "BLOCKED_INSUFFICIENT_MATURE_POOL"
        assert result.summary["snapshot_maturity"]["mature_candidate_count"] == 0
        assert result.summary["snapshot_maturity"]["state_counts"]["IMMATURE"] == 2
        assert result.report["holder_attempts"] == []
        assert result.snapshot_bundles == ()
        base_factory.assert_not_called()
        counts = _db_counts(self.db)
        assert counts["printer_holder_evidence_attempts"] == 0
        assert counts["printer_token_snapshots"] == 0

    def test_fewer_than_two_mature_candidates_closes_without_holder_work(self) -> None:
        now = self._now()
        transport = _create_transport(
            [
                int(now.timestamp()) - 901,
                int(now.timestamp()) - 899,
                int(now.timestamp()) - 100,
            ]
        )
        result = self._run(pump_transport=transport, now=now)

        assert result.status == "BLOCKED_INSUFFICIENT_MATURE_POOL"
        assert result.summary["snapshot_maturity"]["mature_candidate_count"] == 1
        assert result.holder_eligible_count == 0
        assert result.report["holder_attempts"] == []
        assert result.summary["budget"]["candidate_cap"] == 3

    def test_two_mature_candidates_reach_two_complete_canonical_bundles(self) -> None:
        now = self._now()
        transport = _create_transport(
            [int(now.timestamp()) - 900, int(now.timestamp()) - 901]
        )
        result = self._run(pump_transport=transport, now=now, via_dispatcher=True)

        assert result.status == "READY"
        assert result.complete_bundle_count == 2
        assert result.summary["snapshot_maturity"]["mature_candidate_count"] == 2
        assert result.summary["snapshot_maturity"]["state_counts"]["DUE"] == 2
        assert result.summary["budget"] == {
            "operation_ceiling": 45,
            "candidate_cap": 3,
            "reserved_snapshot_operations": 2,
            "reserved_snapshot_completion_operations": 4,
            "charged_operations": result.summary["budget"]["charged_operations"],
        }
        assert result.replay_deterministic
        assert result.replay_new_source_calls == 0
        assert result.report["integrity"] == "ok"
        assert result.report["foreign_key_violations"] == 0

        counts = _db_counts(self.db)
        assert counts["printer_token_snapshots"] == 2
        for table in (
            "printer_memory_windows",
            "printer_memory_factory_run_steps",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            assert counts[table] == 0

    def test_mature_age_never_replaces_exact_15m_evidence(self) -> None:
        now = self._now()
        block_times = [int(now.timestamp()) - 901, int(now.timestamp()) - 902]
        current_start = int(now.timestamp() // 900 * 900)
        completed_start = current_start - 900
        complete_ohlcv = {
            "data": {"attributes": {"ohlcv_list": [
                [completed_start, 1.0, 1.2, 0.9, 1.1, 500.0]
            ]}}
        }
        partial_trades = {
            "data": [
                {"attributes": {
                    "block_timestamp": datetime.fromtimestamp(
                        completed_start + 60, tz=timezone.utc
                    ).isoformat()
                }}
                for _ in range(300)
            ]
        }
        malformed_trades = {"data": [{"attributes": {"block_timestamp": None}}]}
        cases = (
            (
                "missing",
                self._base_factory(liquidity=None),
                e33._gt_15m_transports(now),
            ),
            (
                "unpublished",
                self._base_factory(),
                {
                    GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _c: {
                        "data": {"attributes": {"ohlcv_list": []}}
                    },
                    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _c: {"data": []},
                },
            ),
            (
                "skipped",
                self._base_factory(),
                {
                    GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _c: {
                        "data": {"attributes": {"ohlcv_list": [
                            [completed_start - 1800, 1.0, 1.1, 0.9, 1.0, 100.0]
                        ]}}
                    },
                    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _c: {"data": []},
                },
            ),
            (
                "partial",
                self._base_factory(),
                {
                    GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _c: complete_ohlcv,
                    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _c: partial_trades,
                },
            ),
            (
                "malformed",
                self._base_factory(),
                {
                    GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _c: complete_ohlcv,
                    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _c: malformed_trades,
                },
            ),
        )

        for index, (label, base_factory, transports) in enumerate(cases):
            if index:
                self.tearDown()
                self.setUp()
            with self.subTest(label=label):
                result = self._run(
                    pump_transport=_create_transport(block_times),
                    now=now,
                    base_factory=base_factory,
                    transports=transports,
                )
                assert result.status == "BLOCKED_SNAPSHOT_READINESS"
                assert result.summary["snapshot_maturity"]["mature_candidate_count"] == 2
                assert result.complete_bundle_count < 2

    def test_mature_age_with_stale_exact_pool_evidence_still_blocks(self) -> None:
        evaluated = self._now() + timedelta(seconds=181)
        transport = _create_transport(
            [int(evaluated.timestamp()) - 901, int(evaluated.timestamp()) - 902]
        )

        result = self._run(pump_transport=transport, now=evaluated)

        assert result.status == "BLOCKED_SNAPSHOT_READINESS"
        assert result.summary["snapshot_maturity"]["mature_candidate_count"] == 2
        assert result.complete_bundle_count == 0
        assert any(
            "READINESS_PRIMARY_STALE" in bundle["blocked_reasons"]
            for bundle in result.snapshot_bundles
        )

    def test_cancellation_cleans_up_and_remains_single_use(self) -> None:
        now = self._now()
        block_times = [int(now.timestamp()) - 901, int(now.timestamp()) - 902]
        owner = AuthoritativeLiveOperationalCampaignOwner()
        owner._driver = MagicMock()

        result = self._run_cancelled(
            transport=_create_transport(block_times),
            now=now,
        )
        assert result.status == "CANCELLED"
        assert result.summary["snapshot_maturity"]["state_counts"]["CANCELLED"] == 2
        assert result.report["holder_attempts"] == []
        assert result.snapshot_bundles == ()
        assert result.report["cleanup"] == {
            "active_tracking_queue": 0,
            "active_scheduler_jobs": 0,
        }
        assert result.replay_deterministic
        assert result.replay_new_source_calls == 0
        owner._driver.run.assert_not_called()

        second = self._run(
            pump_transport=e33._RaisingPumpTransport("TIMEOUT"),
            now=now,
        )
        assert second.status == "REFUSED_SECOND_EXECUTION"

    def test_blocked_replay_is_deterministic_zero_source_and_integrity_clean(self) -> None:
        now = self._now()
        result = self._run(
            pump_transport=_create_transport(
                [int(now.timestamp()) - 10, int(now.timestamp()) - 20]
            ),
            now=now,
        )
        assert result.status == "BLOCKED_INSUFFICIENT_MATURE_POOL"

        first = build_bounded_readiness_report(
            self.db, run_id="run", cycle_id="cyc"
        )
        second = build_bounded_readiness_report(
            self.db, run_id="run", cycle_id="cyc"
        )
        assert canonical_report_bytes(first) == canonical_report_bytes(second)
        assert first["source_requests_made_by_replay"] == 0
        assert first["integrity"] == "ok"
        assert first["foreign_key_violations"] == 0
        assert all(value == 0 for value in first["forbidden_capability_counts"].values())
