"""Focused RED/GREEN contracts for the four 4/2/2 orchestration defects."""

from __future__ import annotations

import inspect
import sqlite3
import pytest
import unittest
from datetime import datetime, timedelta, timezone

from printer_v1.db import apply_migrations

from printer_v1.operator_cli import one_command_15m_factory as factory
from tests.test_v2_9_8b_post_dtw100_checkpoint6_1h_terminal_reconciliation import (
    Checkpoint6FirstHourTerminalReconciliationTests,
)
from tests.test_v2_9_8b_slice_b_bounded_migration_acquisition import (
    RecordingTransport,
    _non_migration_tx,
    _row,
    _sig,
)


class OneHourCampaignBindingOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.helper = Checkpoint6FirstHourTerminalReconciliationTests()
        self.fx = self.helper._prepared_campaign()
        self.close_step, self.memory_window_id = self.helper._physical_1h(self.fx)

    def tearDown(self) -> None:
        self.fx.close()

    def _bind(self):
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_1h_campaign_window_memory_row,
        )

        window = self.helper._campaign_window(self.fx, 1)
        slot = self.fx.connection.execute(
            """SELECT token_slot_id FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id='campaign-1h' AND run_id='run-1h'
                 AND cycle_id='cycle-1h' AND token_row_id=1"""
        ).fetchone()
        return bind_precreated_1h_campaign_window_memory_row(
            self.fx.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            token_slot_id=str(slot["token_slot_id"]),
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=str(window["window_id"]),
            memory_window_row_id=self.memory_window_id,
        )

    def test_one_hour_identity_bind_is_idempotent_and_nonterminal(self) -> None:
        before = self.helper._campaign_window(self.fx, 1)
        first = self._bind()
        second = self._bind()
        after = self.helper._campaign_window(self.fx, 1)

        self.assertTrue(first["bound"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(int(after["memory_window_row_id"]), self.memory_window_id)
        self.assertEqual(str(after["window_state"]), str(before["window_state"]))
        self.assertEqual(after["first_terminal_cause"], before["first_terminal_cause"])
        self.assertEqual(after["terminal_at"], before["terminal_at"])

    def test_one_hour_factory_owner_binds_before_terminal_reconciliation(self) -> None:
        result = factory._bind_precreated_1h_campaign_window_before_e2z(
            self.fx.connection,
            step=self.close_step,
            memory_window_row_id=self.memory_window_id,
        )
        row = self.helper._campaign_window(self.fx, 1)
        self.assertTrue(result["bound"])
        self.assertEqual(int(row["memory_window_row_id"]), self.memory_window_id)
        self.assertEqual(str(row["window_state"]), "CLOSE_PENDING")
        self.assertIsNone(row["first_terminal_cause"])
        self.assertIsNone(row["terminal_at"])

    def test_one_hour_bind_rejects_wrong_physical_token_pair(self) -> None:
        wrong = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,window_status,
                       memory_quality_label,do_not_train,supporting_context_json
                   ) VALUES (2,2,'WINDOW_1H','2026-08-01T00:00:00+00:00',
                       '2026-08-01T01:00:00+00:00','PARTIAL_MEMORY','CLEAN_DATA',
                       'WINDOW_CLOSED','PARTIAL_MEMORY',0,'{}')"""
            ).lastrowid
        )
        with self.assertRaisesRegex(Exception, "identity"):
            factory._bind_precreated_1h_campaign_window_before_e2z(
                self.fx.connection,
                step=self.close_step,
                memory_window_row_id=wrong,
            )
        self.assertIsNone(
            self.helper._campaign_window(self.fx, 1)["memory_window_row_id"]
        )

    def test_one_hour_bind_rejects_ambiguous_campaign_window(self) -> None:
        original = self.helper._campaign_window(self.fx, 1)
        self.fx.connection.execute(
            """INSERT INTO printer_memory_factory_campaign_windows(
                   window_id,campaign_id,run_id,cycle_id,token_slot_id,
                   token_row_id,pair_row_id,window_kind,window_state,
                   root_15m_lifecycle_identity,predecessor_window_id,
                   checkpoint_cutoff,support_only,created_at,updated_at
               ) VALUES ('ambiguous-1h','campaign-1h','run-1h','cycle-1h',?,
                   1,1,'WINDOW_1H','CLOSE_PENDING',?,?,?,0,?,?)""",
            (
                str(original["token_slot_id"]),
                str(original["root_15m_lifecycle_identity"]),
                str(original["predecessor_window_id"]),
                str(original["checkpoint_cutoff"]),
                str(original["created_at"]),
                str(original["updated_at"]),
            ),
        )
        self.fx.connection.commit()
        with self.assertRaisesRegex(Exception, "ambiguous"):
            self._bind()


def test_direct_migration_next_request_bound_fits_track_fast() -> None:
    from printer_v1.discovery.eligible_token_supply import (
        AcquisitionQuantumKind,
        acquisition_governed_request_bound,
        acquisition_quantum_bound,
    )

    coarse = acquisition_quantum_bound(
        AcquisitionQuantumKind.DIRECT_MIGRATION
    ).worst_case_seconds
    next_request = acquisition_governed_request_bound(
        AcquisitionQuantumKind.DIRECT_MIGRATION,
        request_kind="DIRECT_PUMP_SIGNATURE_PAGE",
        checkpoint_reserve_seconds=5.0,
    ).worst_case_seconds
    assert coarse == 115.0
    assert next_request == 10.0
    now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    deadline = now + timedelta(seconds=117)
    assert coarse >= (deadline - now).total_seconds() - 2
    assert next_request < (deadline - now).total_seconds()


def test_direct_migration_claim_executes_one_missing_governed_request_and_replays(
    tmp_path,
) -> None:
    from printer_v1.discovery.direct_migration_discovery import (
        run_direct_migration_discovery,
    )

    database = tmp_path / "cooperative-direct.sqlite3"
    apply_migrations(database)
    signature = _sig("OneRequest")
    transport = RecordingTransport(
        {None: [_row(signature, 900)]},
        {signature: _non_migration_tx(900)},
    )
    kwargs = dict(
        migration_transport=transport,
        verifier_transport_factory=lambda _mint, _signature: (_ for _ in ()).throw(
            AssertionError("non-migration must not verify")
        ),
        now="2026-08-28T12:00:00+00:00",
        request_key_prefix="cooperative-direct",
        max_candidates=1,
        max_transaction_lookups=1,
        cooperative_request_limit=1,
        cooperative_checkpoint_reserve_seconds=5.0,
    )

    first = run_direct_migration_discovery(database, **kwargs)
    assert first["status"] == "ACQUISITION_QUANTUM_YIELDED"
    assert transport.page_count == 1
    assert transport.transaction_signatures == []
    assert first["new_governed_request_count"] == 1
    assert first["next_governed_request_worst_case_seconds"] == 10.0

    second = run_direct_migration_discovery(database, **kwargs)
    assert second["status"] == "COMPLETE"
    assert transport.page_count == 1
    assert transport.transaction_signatures == [signature]
    assert second["new_governed_request_count"] == 1

    third = run_direct_migration_discovery(database, **kwargs)
    assert third["status"] == "COMPLETE"
    assert transport.page_count == 1
    assert transport.transaction_signatures == [signature]
    assert third["new_governed_request_count"] == 0


def test_pumpswap_verifier_remains_one_source_governed_request() -> None:
    from printer_v1.discovery.eligible_token_supply import (
        AcquisitionQuantumKind,
        acquisition_governed_request_bound,
    )

    bound = acquisition_governed_request_bound(
        AcquisitionQuantumKind.DIRECT_MIGRATION,
        request_kind="PUMPSWAP_EXACT_VERIFICATION",
        checkpoint_reserve_seconds=5.0,
    )
    assert bound.governed_request_count == 1
    assert bound.transport_count == 4
    assert bound.worst_case_seconds == 85.0


def test_refresh_opportunities_are_anchored_to_original_acquisition_start() -> None:
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        refresh_opportunity_at,
    )

    started = "2026-08-28T12:00:00+00:00"
    assert refresh_opportunity_at(started, refresh_ordinal=1) == (
        "2026-08-28T12:10:00+00:00"
    )
    assert refresh_opportunity_at(started, refresh_ordinal=2) == (
        "2026-08-28T12:20:00+00:00"
    )
    assert refresh_opportunity_at(started, refresh_ordinal=3) == (
        "2026-08-28T12:30:00+00:00"
    )


def test_claimed_refresh_work_yields_and_resumes_same_scheduler_owner(tmp_path) -> None:
    from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
        REFRESH_COMPLETED,
        WAITING_FOR_ELIGIBLE_SUPPLY,
    )
    from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
        PreLifecycleTemporalRefreshOwner,
    )

    database = tmp_path / "cooperative-refresh.sqlite3"
    apply_migrations(database)
    calls: list[int] = []

    def stage(_connection, **context):
        calls.append(int(context["refresh_ordinal"]))
        if len(calls) == 1:
            return {
                "source_operations": 1,
                "provider_failures": 0,
                "cooperative_incomplete": True,
                "next_governed_request_kind": "restored_pump_migration_transaction",
                "next_governed_request_worst_case_seconds": 10.0,
            }
        return {"source_operations": 1, "provider_failures": 0}

    owner = PreLifecycleTemporalRefreshOwner(
        database,
        campaign_id="campaign-refresh",
        run_id="run-refresh",
        cycle_id="cycle-refresh",
        supervision_id="supervision-refresh",
        source_governor=True,
        central_scheduler=True,
        acquisition_deadline_at="2026-08-28T12:40:00+00:00",
        work_deadline_at="2026-08-28T13:00:00+00:00",
        refresh_stage=stage,
        waiter=None,
        refresh_interval_seconds=600,
    )
    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=10,
        now="2026-08-28T12:00:00+00:00",
    )
    partial = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=10,
        now="2026-08-28T12:10:00+00:00",
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert partial.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert partial.claimed is True
    assert partial.scheduler_job_id == waiting.scheduler_job_id
    assert partial.source_operations == 1
    assert partial.next_governed_request_worst_case_seconds == 10.0

    connection = sqlite3.connect(database)
    wait_state = connection.execute(
        "SELECT wait_state FROM printer_pre_lifecycle_discovery_refresh_waits"
    ).fetchone()[0]
    work_state = connection.execute(
        "SELECT work_state FROM printer_pre_lifecycle_discovery_refresh_work"
    ).fetchone()[0]
    job_state = connection.execute(
        "SELECT status FROM printer_scheduler_jobs WHERE id=?",
        (partial.scheduler_job_id,),
    ).fetchone()[0]
    connection.close()
    assert (wait_state, work_state, job_state) == ("CLAIMED", "RUNNING", "PENDING")

    completed = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=9,
        now="2026-08-28T12:10:01+00:00",
    )
    assert completed.status == REFRESH_COMPLETED
    assert completed.scheduler_job_id == waiting.scheduler_job_id
    assert calls == [1, 1]


def test_track_fast_deadline_priority_uses_next_request_not_coarse_stage() -> None:
    from printer_v1.operator_cli.one_command_15m_factory import (
        _later_cycle_acquisition_deadline_conflict,
    )

    now = datetime(2026, 8, 28, 12, 0, 2, tzinfo=timezone.utc)
    next_deadline = datetime(2026, 8, 28, 12, 1, 57, tzinfo=timezone.utc)
    assert _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=next_deadline,
        worst_case_quantum_seconds=115.0,
    )
    assert not _later_cycle_acquisition_deadline_conflict(
        now=now,
        earliest_lifecycle_deadline=next_deadline,
        worst_case_quantum_seconds=85.0,
    )


def test_attempt_evidence_reduces_truthfully_across_cooperative_claims(tmp_path) -> None:
    from printer_v1.operator_cli.pre_admission_attempt_evidence import (
        append_pre_admission_attempt_evidence,
        reduce_pre_admission_attempt_evidence,
    )

    database = tmp_path / "attempt-evidence.sqlite3"
    apply_migrations(database)
    connection = sqlite3.connect(database)
    try:
        append_pre_admission_attempt_evidence(
            connection,
            attempt_id="attempt-evidence",
            event_key="initial:claim:1:mint-a",
            opportunity_ordinal=0,
            claim_ordinal=1,
            evidence_kind="CANDIDATE_OBSERVED",
            mint_identity="MINT_A",
            categorical_reason=None,
            payload={"pair": "PAIR_A", "exact_pair_confirmed": False},
            observed_at="2026-08-28T12:00:00+00:00",
        )
        append_pre_admission_attempt_evidence(
            connection,
            attempt_id="attempt-evidence",
            event_key="initial:claim:2:reject-a",
            opportunity_ordinal=0,
            claim_ordinal=2,
            evidence_kind="CANDIDATE_REJECTED",
            mint_identity="MINT_A",
            categorical_reason="EXACT_PAIR_NOT_CONFIRMED",
            payload={"pair": "PAIR_A"},
            observed_at="2026-08-28T12:00:10+00:00",
        )
        append_pre_admission_attempt_evidence(
            connection,
            attempt_id="attempt-evidence",
            event_key="refresh-1:claim:1:failure-7",
            opportunity_ordinal=1,
            claim_ordinal=1,
            evidence_kind="PROVIDER_FAILURE",
            categorical_reason="RPC_RATE_LIMITED",
            payload={"source": "solana_rpc", "provider_failure_id": 7},
            observed_at="2026-08-28T12:10:00+00:00",
        )
        # Same deterministic event is an idempotent replay, not a second fact.
        append_pre_admission_attempt_evidence(
            connection,
            attempt_id="attempt-evidence",
            event_key="refresh-1:claim:1:failure-7",
            opportunity_ordinal=1,
            claim_ordinal=1,
            evidence_kind="PROVIDER_FAILURE",
            categorical_reason="RPC_RATE_LIMITED",
            payload={"source": "solana_rpc", "provider_failure_id": 7},
            observed_at="2026-08-28T12:10:00+00:00",
        )
        reduced = reduce_pre_admission_attempt_evidence(
            connection, attempt_id="attempt-evidence"
        )
    finally:
        connection.close()

    assert reduced["unique_tokens_observed"] == 1
    assert reduced["rejected_count"] == 1
    assert reduced["rejection_reasons"] == {"EXACT_PAIR_NOT_CONFIRMED": 1}
    assert reduced["provider_failures"] == 1
    assert reduced["opportunities_executed"] == [0, 1]
    assert reduced["claims_executed"] == 3


def test_terminal_certificate_is_rebuilt_from_attempt_evidence() -> None:
    from printer_v1.operator_cli.pre_admission_attempt_evidence import (
        rebuild_exhaustion_certificate_from_attempt_evidence,
    )

    rebuilt = rebuild_exhaustion_certificate_from_attempt_evidence(
        {
            "unique_tokens_observed": 0,
            "rejected_count": 0,
            "rejection_reasons": {},
            "provider_failures": 0,
            "discovery_rounds": 0,
        },
        {
            "unique_tokens_observed": 4,
            "rejected_count": 3,
            "rejection_reasons": {"LIQUIDITY_BELOW_SELECTION_FLOOR": 2},
            "provider_failures": 1,
            "refresh_rounds": 2,
            "opportunities_executed": [0, 1, 2],
        },
    )
    assert rebuilt["unique_tokens_observed"] == 4
    assert rebuilt["rejected_count"] == 3
    assert rebuilt["provider_failures"] == 1
    assert rebuilt["discovery_rounds"] == 3
    assert rebuilt["rejection_reasons"] == {
        "LIQUIDITY_BELOW_SELECTION_FLOOR": 2
    }


def test_preclose_reservations_accumulate_without_overwriting() -> None:
    from printer_v1.operator_cli.one_command_15m_factory import (
        _merge_lifecycle_reservation_records,
    )

    base = {
        "boundary": "LIFECYCLE_RESERVATION",
        "run_id": "factory-run",
        "scheduler_job_id": 9,
        "step_key": "token_1_window_close_pre_close_critical",
        "step_kind": "WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
        "token_id": 1,
        "pair_id": 2,
    }
    first = {**base, "reservation_ordinal": 901, "source_unit_identity": "UNIT_A"}
    second = {**base, "reservation_ordinal": 902, "source_unit_identity": "UNIT_B"}
    merged = _merge_lifecycle_reservation_records([first], [second])
    assert merged["records"] == [first, second]
    assert merged["new_records"] == [second]
    replay = _merge_lifecycle_reservation_records(merged["records"], [second])
    assert replay["records"] == [first, second]
    assert replay["new_records"] == []
    with pytest.raises(ValueError, match="CONFLICT"):
        _merge_lifecycle_reservation_records(
            [first], [{**first, "source_unit_identity": "UNIT_WRONG"}]
        )


def test_durable_preclose_reservations_reconstruct_all_owner_identities() -> None:
    from printer_v1.operator_cli.campaign_full_run_accounting import (
        OperationalLifecycleOwnershipContext,
        reservation_identities_from_durable_records,
    )

    context = OperationalLifecycleOwnershipContext(
        campaign_id="campaign",
        configuration_id="configuration",
        campaign_run_id="campaign-run",
        factory_run_id="factory-run",
        cycle_id="cycle",
    )
    records = [
        {
            "boundary": "LIFECYCLE_RESERVATION",
            "run_id": "factory-run",
            "campaign_id": "campaign",
            "campaign_run_id": "campaign-run",
            "cycle_id": "cycle",
            "factory_run_id": "factory-run",
            "scheduler_job_id": 9,
            "step_key": "token_1_window_close_pre_close_critical",
            "step_kind": "WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
            "token_id": 1,
            "pair_id": 2,
            "reservation_ordinal": 901,
            "source_unit_identity": "UNIT_A",
        },
        {
            "boundary": "LIFECYCLE_RESERVATION",
            "run_id": "factory-run",
            "campaign_id": "campaign",
            "campaign_run_id": "campaign-run",
            "cycle_id": "cycle",
            "factory_run_id": "factory-run",
            "scheduler_job_id": 9,
            "step_key": "token_1_window_close_pre_close_critical",
            "step_kind": "WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
            "token_id": 1,
            "pair_id": 2,
            "reservation_ordinal": 901,
            "source_unit_identity": "UNIT_A",
        },
        {
            "boundary": "LIFECYCLE_RESERVATION",
            "run_id": "factory-run",
            "campaign_id": "campaign",
            "campaign_run_id": "campaign-run",
            "cycle_id": "cycle",
            "factory_run_id": "factory-run",
            "scheduler_job_id": 9,
            "step_key": "token_1_window_close_pre_close_critical",
            "step_kind": "WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
            "token_id": 1,
            "pair_id": 2,
            "reservation_ordinal": 902,
            "source_unit_identity": "UNIT_B",
        },
    ]
    identities = reservation_identities_from_durable_records(
        context,
        slot_ordinal=1,
        scheduler_job_id=9,
        step_key="token_1_window_close_pre_close_critical",
        step_kind="WINDOW_CLOSE_PRE_CLOSE_CRITICAL",
        token_id=1,
        pair_id=2,
        records=records,
        source_unit_manifest=(
            {"source_unit_identity": "UNIT_A"},
            {"source_unit_identity": "UNIT_B"},
        ),
    )
    assert [item.reservation_ordinal for item in identities] == [901, 902]


def test_later_cycle_holder_forwards_action_local_transport_observer() -> None:
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        AuthoritativeLiveOperationalCampaignOwner,
    )

    source = inspect.getsource(
        AuthoritativeLiveOperationalCampaignOwner
    )
    assert "holder_transport_identity_observer=transport_identity_observer" in source
    assert "holder_transport_identity_observer=None" not in source


if __name__ == "__main__":
    unittest.main()
