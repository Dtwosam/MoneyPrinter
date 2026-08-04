"""V2-9.8B holder partial transport count repair.

Offline fixture-only. Proves exactly one repair:

When holder persistence fails after real executions have already produced
measured transport evidence, ``persist_bundle_attempts()`` must preserve the
proven transport counts instead of resetting them to zero. The partial measured
transport total must equal the sum of the counts proven from the preserved real
executions, and ``_evaluate_holder_eligibility()`` must charge that real total
to the campaign ledger.

Zero remains correct only for an execution whose measurement is itself absent,
invalid, negative, or contradictory. Counts are never inferred from source
names, response presence, RPC method names, or provider type.

No providers, discovery runtime, Scheduler runtime, authorization,
``WINDOW_15M``, memory generation, retrieval, decisions, positions, trades,
audits, or PnL are run.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping
from unittest.mock import MagicMock, patch

import pytest

from printer_v1.operator_cli.holder_reliability_budget_control import (
    HolderBundlePersistPartialError,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter
import printer_v1.operator_cli.holder_reliability_budget_control as budget

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_33_canonical_readiness_boundary as e33
import test_v2_9_8b_holder_partial_accounting_repair as prior

MINT_A = prior.MINT_A
MINT_B = prior.MINT_B
NOW = prior.NOW
FORBIDDEN_ACTIVITY_TABLES = prior.FORBIDDEN_ACTIVITY_TABLES


# ---------------------------------------------------------------------------
# Fixtures — genuine governed executions with distinct measured counts
# ---------------------------------------------------------------------------


def _counted_goplus_factories(counts: Mapping[str, int]) -> dict[str, Any]:
    """GoPlus factory whose measured transport count varies per mint."""

    def factory(**kwargs: Any):
        mint = str(kwargs.get("token_mint") or MINT_A)
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload=prior._goplus_payload(
                mint,
                holders=[{"percent": "3"} for _ in range(10)],
                underlying_operation_count=int(counts.get(mint.lower(), 1)),
            ),
        )

    return {"goplus": factory}


def _failing_record_attempt(fail_from_call: int):
    """Real ``record_attempt`` until ``fail_from_call``, then raise."""
    real = budget.record_attempt
    calls = {"n": 0}

    def _flaky(conn, **values):
        calls["n"] += 1
        if calls["n"] >= fail_from_call:
            raise RuntimeError("fixture holder evidence persistence failure")
        return real(conn, **values)

    return _flaky


def _partial_over_two_measured(connection, monkeypatch, *, second_count=2):
    """Two real governed executions (measured 1 and ``second_count``).

    Failure is injected only in holder evidence persistence, after both durable
    ``printer_source_requests`` rows already exist.
    """
    first = prior._goplus_execution(
        connection, mint=MINT_A, request_key="transport-1", underlying_operation_count=1
    )
    second = prior._goplus_execution(
        connection,
        mint=MINT_B,
        request_key="transport-2",
        underlying_operation_count=second_count,
    )
    monkeypatch.setattr(budget, "record_attempt", _failing_record_attempt(2))
    with pytest.raises(HolderBundlePersistPartialError) as excinfo:
        budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={"safety": first, "safety_alt": second},
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
    return (
        excinfo.value,
        int(first.request_record.id),
        int(second.request_record.id),
    )


def _coverage_by_id(partial, request_id: int) -> Mapping[str, Any]:
    matches = [
        entry
        for entry in partial.source_request_coverage
        if int(entry["source_request_id"]) == int(request_id)
    ]
    assert matches, f"coverage for durable request {request_id} must be preserved"
    return matches[0]


# ===========================================================================
# Persist-owner partial contract
# ===========================================================================


class TestPartialPersistPreservesMeasuredTransport:
    def test_1_second_execution_persistence_raises_typed_partial(
        self, tmp_path, monkeypatch
    ):
        connection = prior._db(tmp_path)
        error, first_id, second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        assert error.code == "HOLDER_BUNDLE_PERSIST_INCOMPLETE"
        assert error.partial.accounting_blocker is True
        assert error.partial.accounting_blocker_reason
        # Both durable rows really exist; failure was persistence-only.
        for rid in (first_id, second_id):
            assert (
                connection.execute(
                    "SELECT id FROM printer_source_requests WHERE id=?", (rid,)
                ).fetchone()
                is not None
            )

    def test_2_both_durable_request_ids_are_preserved(self, tmp_path, monkeypatch):
        connection = prior._db(tmp_path)
        error, first_id, second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        assert set(error.partial.source_request_ids) == {first_id, second_id}

    def test_3_both_coverage_entries_are_blocked(self, tmp_path, monkeypatch):
        connection = prior._db(tmp_path)
        error, first_id, second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        partial = error.partial
        assert len(partial.source_request_coverage) == 2
        for rid in (first_id, second_id):
            entry = _coverage_by_id(partial, rid)
            assert entry["terminal_status"] == "BLOCKED"
            assert int(entry["normalized_member_count"]) == 0

    def test_4_preserved_transport_counts_remain_one_and_two(
        self, tmp_path, monkeypatch
    ):
        connection = prior._db(tmp_path)
        error, first_id, second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        partial = error.partial
        assert int(_coverage_by_id(partial, first_id)["transport_identity_count"]) == 1
        assert int(_coverage_by_id(partial, second_id)["transport_identity_count"]) == 2

    def test_5_partial_measured_transport_total_is_three(self, tmp_path, monkeypatch):
        connection = prior._db(tmp_path)
        error, _first_id, _second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        partial = error.partial
        assert partial.measured_transport_count == 3
        # Required invariant: the total equals the sum of the preserved counts.
        assert partial.measured_transport_count == sum(
            int(entry["transport_identity_count"])
            for entry in partial.source_request_coverage
        )

    def test_6_partial_governed_request_count_remains_two(self, tmp_path, monkeypatch):
        connection = prior._db(tmp_path)
        error, _first_id, _second_id = _partial_over_two_measured(
            connection, monkeypatch
        )
        assert error.partial.governed_request_count == 2

    def test_11_unmeasured_execution_stays_zero_and_blocks(self, tmp_path, monkeypatch):
        """A genuinely unmeasured execution contributes zero, never a guess."""
        connection = prior._db(tmp_path)
        measured = prior._goplus_execution(
            connection, mint=MINT_A, request_key="mixed-1",
            underlying_operation_count=1,
        )
        unmeasured = prior._goplus_execution(
            connection, mint=MINT_B, request_key="mixed-2",
            underlying_operation_count=None,
        )
        unmeasured_id = int(unmeasured.request_record.id)
        monkeypatch.setattr(budget, "record_attempt", _failing_record_attempt(2))
        with pytest.raises(HolderBundlePersistPartialError) as excinfo:
            budget.persist_bundle_attempts(
                connection,
                run_id="run",
                cycle_id="cycle",
                mint=MINT_A,
                executions={"safety": measured, "safety_alt": unmeasured},
                created_at=NOW.isoformat(),
                campaign_id="campaign",
                candidate_ordinal=1,
            )
        partial = excinfo.value.partial
        assert int(
            _coverage_by_id(partial, unmeasured_id)["transport_identity_count"]
        ) == 0
        assert partial.measured_transport_count == 1
        assert partial.accounting_blocker is True

    def test_12_measured_source_failure_preserves_its_count(self, tmp_path):
        """A failed source with complete measured accounting keeps its count."""
        connection = prior._db(tmp_path)
        result = prior._evaluate(
            connection, factories=prior._rate_limited_goplus_factories()
        )
        assert result.accounting_blocker is False
        assert result.measured_transport_count >= 1
        blocked = [
            entry
            for entry in result.source_request_coverage
            if entry["terminal_status"] == "BLOCKED"
        ]
        assert blocked, "the rate-limited source must terminalize BLOCKED"
        assert all(
            int(entry["transport_identity_count"]) >= 1 for entry in blocked
        ), "a measured source failure must not lose its proven transport count"

    def test_13_alias_executions_remain_deduplicated(self, tmp_path, monkeypatch):
        """The same execution under two keys is counted exactly once."""
        connection = prior._db(tmp_path)
        holder = prior._goplus_execution(
            connection, mint=MINT_A, request_key="alias-1",
            underlying_operation_count=2,
        )
        holder_id = int(holder.request_record.id)
        monkeypatch.setattr(budget, "record_attempt", _failing_record_attempt(1))
        with pytest.raises(HolderBundlePersistPartialError) as excinfo:
            budget.persist_bundle_attempts(
                connection,
                run_id="run",
                cycle_id="cycle",
                mint=MINT_A,
                executions={"holder": holder, "holder_primary": holder},
                created_at=NOW.isoformat(),
                campaign_id="campaign",
                candidate_ordinal=1,
            )
        partial = excinfo.value.partial
        assert partial.source_request_ids == (holder_id,)
        assert len(partial.source_request_coverage) == 1
        assert partial.governed_request_count == 1
        assert partial.measured_transport_count == 2


# ===========================================================================
# Campaign holder stage and ledger
# ===========================================================================


class TestHolderStageChargesPreservedTransport:
    def _evaluate_with_failing_second_persist(self, tmp_path, monkeypatch):
        connection = prior._db(tmp_path)
        factories = _counted_goplus_factories(
            {MINT_A.lower(): 1, MINT_B.lower(): 2}
        )
        monkeypatch.setattr(budget, "record_attempt", _failing_record_attempt(2))
        result = prior._evaluate(
            connection,
            factories=factories,
            mints=(MINT_A, MINT_B),
            eligible_target=2,
        )
        return connection, result

    def test_7_evaluate_adds_exactly_three_transports_to_its_ledger(
        self, tmp_path, monkeypatch
    ):
        connection, result = self._evaluate_with_failing_second_persist(
            tmp_path, monkeypatch
        )
        assert result.accounting_blocker is True
        # The stage started from a zero-operation ledger, so the returned
        # ledger delta is exactly the proven real transport total.
        assert result.ledger.underlying_transport_operations == 3
        assert result.ledger.governed_requests == 2
        # Not double-charged during recovery.
        assert result.governed_request_count == 2

    def test_8_holder_context_exposes_measured_transport_count_three(
        self, tmp_path, monkeypatch
    ):
        connection, result = self._evaluate_with_failing_second_persist(
            tmp_path, monkeypatch
        )
        assert result.measured_transport_count == 3
        diagnostics = result.as_holder_context_diagnostics()
        assert diagnostics["measured_transport_count"] == 3
        assert diagnostics["governed_request_count"] == 2
        counts = sorted(
            int(entry["transport_identity_count"])
            for entry in result.source_request_coverage
        )
        assert counts == [1, 2]
        # Every reported ID is a genuine durable governed request row.
        for rid in result.source_request_ids:
            assert (
                connection.execute(
                    "SELECT id FROM printer_source_requests WHERE id=?", (int(rid),)
                ).fetchone()
                is not None
            )

    def test_14_no_lifecycle_memory_or_financial_activity_occurs(
        self, tmp_path, monkeypatch
    ):
        connection, _result = self._evaluate_with_failing_second_persist(
            tmp_path, monkeypatch
        )
        for table in FORBIDDEN_ACTIVITY_TABLES:
            assert (
                int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )
                == 0
            ), table


# ===========================================================================
# Readiness and reconciliation still fail closed
# ===========================================================================


class TestReadinessAndReconciliationOnPreservedPartial:
    def test_9_pilot_input_readiness_blocks_on_the_partial_attempt(self):
        factories = _counted_goplus_factories(
            {mint.lower(): 2 for mint in prior._MINTS}
        )
        with patch.object(
            budget, "record_attempt", _failing_record_attempt(1)
        ):
            base, result = prior._run_pilot_input_readiness(
                seed="holder-transport-block", factories=factories
            )
        try:
            life = result.lifecycle
            assert life.get("pilot_input_readiness") is None
            diag = life.get("graduated_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ctx.get("accounting_blocker") is True
            assert holder_ctx.get("source_request_ids")
            # The proven counts survive into the campaign surfaces.
            assert int(holder_ctx.get("measured_transport_count") or 0) >= 2
            assert int(holder_ctx.get("measured_transport_count") or 0) == sum(
                int(entry["transport_identity_count"])
                for entry in holder_ctx.get("source_request_coverage") or ()
            )
        finally:
            base.tearDown()


class TestSnapshotReadinessOnPreservedPartial(e33._SnapshotReadinessBase):
    def test_10_snapshot_readiness_attempts_zero_readiness_bundles(self) -> None:
        base_factory = MagicMock(
            side_effect=AssertionError("readiness snapshot call forbidden")
        )
        factories = _counted_goplus_factories(
            {mint.lower(): 2 for mint in prior._MINTS}
        )
        now, transport = (
            prior.TestSnapshotReadinessHolderAccounting._mature_transport(self)
        )
        owner = prior.AuthoritativeLiveOperationalCampaignOwner()
        with patch.object(budget, "record_attempt", _failing_record_attempt(1)):
            result = owner.run_snapshot_readiness(
                command=self.command,
                pump_transport=transport,
                source_governor=e33.GOV,
                central_scheduler=e33.SCH,
                selection_seed="holder-transport-readiness",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=now.isoformat(),
                context_adapter_factories=dict(factories),
                geckoterminal_base_adapter_factory=base_factory,
                geckoterminal_transports=e33._gt_15m_transports(now),
                secret_present=True,
                holder_request_pacer=e33._NoSleepPacer(),
                snapshot_request_pacer=e33._NoSleepPacer(),
            )
        base_factory.assert_not_called()
        self.assertEqual(result.snapshot_bundles, ())
        self.assertEqual(result.complete_bundle_count, 0)
        self.assertEqual(result.status, "BLOCKED_HOLDER_ACCOUNTING")
        context = result.summary["holder_context"]
        self.assertTrue(context["accounting_blocker"])
        # The measured transports proven before the failure are still charged.
        self.assertGreaterEqual(int(context["measured_transport_count"]), 2)
        connection = sqlite3.connect(self.db)
        try:
            snapshots = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_token_snapshots"
                ).fetchone()[0]
            )
            for table in FORBIDDEN_ACTIVITY_TABLES:
                self.assertEqual(
                    int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                    ),
                    0,
                    table,
                )
        finally:
            connection.close()
        self.assertEqual(snapshots, 0)
