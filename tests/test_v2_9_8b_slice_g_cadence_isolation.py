from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sqlite3
import threading

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    ACQUISITION_QUANTUM_YIELDED,
    COOPERATIVE_QUANTUM_MAX_SOURCE_OPERATIONS,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    WAITING_FOR_ELIGIBLE_SUPPLY,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenAdmissionDisposition,
    FourTokenAdmissionDispositionKind,
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner import (
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    build_later_cycle_graduated_supply,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _later_cycle_attempt_is_terminal,
    _later_cycle_acquisition_deadline_conflict,
    _run_four_token_admission_boundary,
)
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import (
    claim_due_job,
    enqueue_job,
    yield_job,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
HEALTH = MultiCycleAdmissionHealth()
QUANTUM_SECONDS = 110.0


def _candidate(slot: int) -> LaterCycleDiscoveryCandidate:
    return LaterCycleDiscoveryCandidate(
        token_identity=f"solana-mainnet:mint-{slot}",
        token_row_id=slot,
        mint_identity=f"mint-{slot}",
        pair_identity=f"pool-{slot}",
        pair_row_id=slot,
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:pool-{slot}",
        canonical_pool_identity=f"pool-{slot}",
        channels=frozenset({f"fixture-{slot}"}),
        holder_evidence_eligible=True,
        canonical_evidence_json='{"quality":"exact"}',
        canonical_evidence_hash=str(slot) * 64,
        evidence_version="slice-g-v1",
        observed_at=NOW,
    )


@pytest.fixture()
def callback_database(tmp_path):
    path = tmp_path / "slice-g.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-g','RUNNING','OPERATIONAL_PERSISTENT','db-g','policy-g')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-g", "campaign-g", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("factory-g", "RUNNING", "WINDOW_15M", "OPERATIONAL_PERSISTENT", "a" * 64, "{}", NOW.isoformat()),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("campaign-run-g", "campaign-g", 1, "RUNNING", "factory-g", NOW.isoformat(), NOW.isoformat()),
    )
    for slot in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,'solana')",
            (slot, f"mint-{slot}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (slot, slot, f"pool-{slot}"),
        )
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,source_status,data_quality_label) "
            "VALUES ('dexscreener','fresh_profiles',?,'COMPLETE','CLEAN_DATA')",
            (NOW.isoformat(),),
        ).lastrowid
    )
    response_id = int(
        connection.execute(
            "INSERT INTO printer_source_responses("
            "source_request_id,source_name,received_at,source_status,data_quality_label) "
            "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
            (request_id, NOW.isoformat()),
        ).lastrowid
    )
    connection.commit()
    connection.close()
    return path, request_id, response_id


def _invoke(callback, *, evaluated_at: datetime = NOW):
    return callback(
        campaign_id="campaign-g",
        campaign_run_id="campaign-run-g",
        authoritative_factory_run_id="factory-g",
        cycle_id="cycle-g-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=evaluated_at.isoformat(),
        selection_seed="seed-g-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )


def test_g2_imminent_lifecycle_deadline_blocks_acquisition_quantum() -> None:
    assert COOPERATIVE_QUANTUM_MAX_SOURCE_OPERATIONS == 22
    assert QUANTUM_SECONDS == 22 * 5.0
    assert _later_cycle_acquisition_deadline_conflict(
        now=NOW,
        earliest_lifecycle_deadline=NOW + timedelta(seconds=30),
        worst_case_quantum_seconds=QUANTUM_SECONDS,
    ) is True
    assert _later_cycle_acquisition_deadline_conflict(
        now=NOW,
        earliest_lifecycle_deadline=NOW + timedelta(seconds=111),
        worst_case_quantum_seconds=QUANTUM_SECONDS,
    ) is False


def test_g9_canonical_scheduler_job_yields_and_requires_fresh_claim(tmp_path) -> None:
    path = tmp_path / "scheduler-yield.sqlite3"
    apply_migrations(path)
    result, job_id = enqueue_job(
        path,
        job_name="pre-admission-discovery-selection:slice-g",
        job_kind=JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
        scheduled_for=NOW,
    )
    assert result is LockResult.ACQUIRED
    assert job_id is not None
    assert claim_due_job(path, job_id=job_id, lock_owner="slice-g", now=NOW) is LockResult.ACQUIRED

    yield_job(path, job_id=job_id, scheduled_for=NOW + timedelta(seconds=1), now=NOW)

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT job_kind,status,lock_owner,locked_at,scheduled_for FROM printer_scheduler_jobs WHERE id=?",
        (job_id,),
    ).fetchone()
    connection.close()
    assert row[:4] == (
        JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value,
        JobStatus.PENDING.value,
        None,
        None,
    )
    assert claim_due_job(path, job_id=job_id, lock_owner="slice-g", now=NOW) is LockResult.NOT_DUE
    assert claim_due_job(
        path,
        job_id=job_id,
        lock_owner="slice-g",
        now=NOW + timedelta(seconds=1),
    ) is LockResult.ACQUIRED


def test_g3_g4_g6_g8_callback_runs_one_quantum_per_claim_and_resumes_cumulatively(
    callback_database,
) -> None:
    path, request_id, response_id = callback_database
    calls: list[int] = []
    cumulative_operations = 0

    def supply(**_context):
        nonlocal cumulative_operations
        cumulative_operations += 1
        calls.append(cumulative_operations)
        if cumulative_operations < 3:
            return LaterCycleCandidateSupply(
                (),
                (),
                (
                    ACQUISITION_QUANTUM_YIELDED
                    if cumulative_operations == 1
                    else WAITING_FOR_ELIGIBLE_SUPPLY
                ),
                {
                    "stage_local_source_requests": cumulative_operations,
                    "provider_failures": 0,
                    "shortage_classification": None,
                },
            )
        return LaterCycleCandidateSupply(
            (_candidate(1), _candidate(2)),
            (
                LaterCycleSourceEvidence(
                    logical_stage="ELIGIBLE_SUPPLY",
                    source_request_id=request_id,
                    source_response_id=response_id,
                ),
            ),
            None,
            {
                "stage_local_source_requests": cumulative_operations,
                "provider_failures": 0,
                "shortage_classification": None,
            },
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path,
        configuration_id="configuration-g",
    )

    first = _invoke(callback)
    assert first.state == "RUNNING"
    assert first.first_terminal_cause == ""
    assert calls == [1]
    second = _invoke(callback, evaluated_at=NOW + timedelta(seconds=1))
    assert second.state == "RUNNING"
    assert calls == [1, 2]
    final = _invoke(callback, evaluated_at=NOW + timedelta(seconds=2))
    assert final.state == "PAIR_READY"
    assert final.selected_count == 2
    assert calls == [1, 2, 3]

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT attempt_state,first_terminal_cause FROM printer_pre_admission_discovery_attempts"
    ).fetchone()
    job = connection.execute(
        "SELECT job_kind,status,retry_count,last_error FROM printer_scheduler_jobs"
    ).fetchone()
    failure_count = connection.execute(
        "SELECT COUNT(*) FROM printer_source_failures"
    ).fetchone()[0]
    connection.close()
    assert row == ("PAIR_READY", "EXACT_PAIR_FROZEN")
    assert job == ("PRE_ADMISSION_DISCOVERY_SELECTION", "SUCCEEDED", 0, None)
    assert failure_count == 0
    assert cumulative_operations == 3


@dataclass
class _Binding:
    campaign_id: str = "campaign-g"
    campaign_run_id: str = "campaign-run-g"
    authoritative_factory_run_id: str = "factory-g"
    configuration_id: str = "configuration-g"


@dataclass
class _Projection:
    health: MultiCycleAdmissionHealth = HEALTH


def _admission_disposition() -> FourTokenAdmissionDisposition:
    return FourTokenAdmissionDisposition(
        FourTokenAdmissionDispositionKind.CYCLE_ADMISSION,
        "ADMISSION_READY",
        NOW,
        True,
    )


def test_g2_boundary_selects_lifecycle_without_starting_acquisition() -> None:
    callback_calls = 0

    def forbidden_callback(**_kwargs):
        nonlocal callback_calls
        callback_calls += 1
        raise AssertionError("acquisition crossed an imminent lifecycle deadline")

    result = _run_four_token_admission_boundary(
        connection=object(),
        controller=object(),
        binding=_Binding(),
        first_cycle_id="cycle-g-1",
        now=NOW,
        next_due_work_at=NOW + timedelta(seconds=30),
        proof_deadline=NOW + timedelta(hours=1),
        project_health=lambda: _Projection(),
        evaluate=lambda _projection: _admission_disposition(),
        later_cycle_callback=forbidden_callback,
        admit=lambda **_kwargs: None,
        materialize=lambda **_kwargs: None,
        plan_opening=lambda **_kwargs: None,
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        clock=lambda: NOW,
        acquisition_quantum_worst_case_seconds=QUANTUM_SECONDS,
    )

    assert callback_calls == 0
    assert result.disposition.kind is FourTokenAdmissionDispositionKind.LIFECYCLE_WORK
    assert result.disposition.at == NOW + timedelta(seconds=30)


def test_g1_g5_two_token_heavy_supply_never_breaks_240_second_cadence() -> None:
    now = NOW
    next_due = {"token-1": NOW + timedelta(seconds=120), "token-2": NOW + timedelta(seconds=120)}
    snapshots = {"token-1": [NOW], "token-2": [NOW]}
    acquisition_quanta = 0

    while acquisition_quanta < 8:
        token = min(next_due, key=lambda item: (next_due[item], item))
        deadline = next_due[token]
        if _later_cycle_acquisition_deadline_conflict(
            now=now,
            earliest_lifecycle_deadline=deadline,
            worst_case_quantum_seconds=QUANTUM_SECONDS,
        ):
            now = deadline
            snapshots[token].append(now)
            next_due[token] = now + timedelta(seconds=120)
            continue
        now += timedelta(seconds=QUANTUM_SECONDS)
        acquisition_quanta += 1

    for token, observed in snapshots.items():
        gaps = [
            (later - earlier).total_seconds()
            for earlier, later in zip(observed, observed[1:], strict=False)
        ]
        assert gaps
        assert max(gaps) <= 240, (token, gaps)
    assert acquisition_quanta == 8


def test_g10_cooperative_path_does_not_start_background_thread(monkeypatch) -> None:
    started = []

    def forbidden_start(self):
        started.append(self)
        raise AssertionError("Slice G must not start an acquisition thread")

    monkeypatch.setattr(threading.Thread, "start", forbidden_start)
    assert _later_cycle_acquisition_deadline_conflict(
        now=NOW,
        earliest_lifecycle_deadline=NOW + timedelta(seconds=30),
        worst_case_quantum_seconds=QUANTUM_SECONDS,
    )
    assert started == []


def test_g3_nonterminal_yield_does_not_consume_the_only_admission_attempt() -> None:
    assert _later_cycle_attempt_is_terminal("RUNNING") is False
    for state in ("PAIR_READY", "NO_PAIR", "BLOCKED", "FAILED", "CANCELLED", "CONSUMED"):
        assert _later_cycle_attempt_is_terminal(state) is True


def test_g3_persisted_temporal_refresh_resumes_without_sleep_or_new_wait(tmp_path) -> None:
    path = tmp_path / "refresh-resume.sqlite3"
    apply_migrations(path)
    stage_calls: list[int] = []

    def refresh_stage(_connection, **context):
        stage_calls.append(int(context["refresh_ordinal"]))
        return {
            "campaign_id": "campaign-g",
            "run_id": "campaign-run-g",
            "cycle_id": "cycle-g-2",
            "source_operations": 1,
            "provider_failures": 0,
        }

    owner = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-g",
        run_id="campaign-run-g",
        cycle_id="cycle-g-2",
        supervision_id="supervision-g",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        acquisition_deadline_at=(NOW + timedelta(minutes=20)).isoformat(),
        work_deadline_at=(NOW + timedelta(hours=1)).isoformat(),
        refresh_stage=refresh_stage,
        waiter=None,
        refresh_interval_seconds=60,
    )

    waiting = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=5,
        now=NOW.isoformat(),
    )
    assert waiting.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert waiting.claimed is False
    assert stage_calls == []

    resumed = owner.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=5,
        now=(NOW + timedelta(seconds=60)).isoformat(),
    )
    assert resumed.status == "REFRESH_COMPLETED"
    assert resumed.claimed is True
    assert resumed.scheduler_job_id == waiting.scheduler_job_id
    assert resumed.refresh_ordinal == waiting.refresh_ordinal == 1
    assert resumed.source_operations == 1
    assert stage_calls == [1]


def test_g4_later_cycle_rebind_disables_private_wait(tmp_path) -> None:
    path = tmp_path / "refresh-rebind.sqlite3"
    apply_migrations(path)
    waited: list[float] = []

    def build_child(**_kwargs):
        return PreLifecycleTemporalRefreshOwner(
            path,
            campaign_id="campaign-g",
            run_id="campaign-run-g",
            cycle_id="cycle-g-2",
            supervision_id="supervision-g",
            source_governor=GOVERNOR,
            central_scheduler=SCHEDULER,
            acquisition_deadline_at=(NOW + timedelta(minutes=20)).isoformat(),
            work_deadline_at=(NOW + timedelta(hours=1)).isoformat(),
            refresh_stage=lambda _connection, **_context: {},
            waiter=lambda seconds: waited.append(seconds) or False,
            refresh_interval_seconds=60,
            cycle_rebinder=build_child,
        )

    parent = PreLifecycleTemporalRefreshOwner(
        path,
        campaign_id="campaign-g",
        run_id="campaign-run-g",
        cycle_id="cycle-g-1",
        supervision_id="supervision-g",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        acquisition_deadline_at=(NOW + timedelta(minutes=20)).isoformat(),
        work_deadline_at=(NOW + timedelta(hours=1)).isoformat(),
        refresh_stage=lambda _connection, **_context: {},
        waiter=lambda seconds: waited.append(seconds) or False,
        refresh_interval_seconds=60,
        cycle_rebinder=build_child,
    )
    rebound = parent.for_cycle(
        cycle_id="cycle-g-2",
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        request_key_prefix="scope-g",
        cooperative_yield=True,
    )

    outcome = rebound.request_temporal_refresh(
        reserve_depth=0,
        required_capacity=2,
        universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
        source_operations_remaining=5,
        now=NOW.isoformat(),
    )
    assert outcome.status == WAITING_FOR_ELIGIBLE_SUPPLY
    assert waited == []


def test_g6_cumulative_budget_regression_fails_closed(callback_database) -> None:
    path, _, _ = callback_database
    reported = iter((2, 1))

    def regressing_supply(**_context):
        return LaterCycleCandidateSupply(
            (),
            (),
            WAITING_FOR_ELIGIBLE_SUPPLY,
            {
                "stage_local_source_requests": next(reported),
                "provider_failures": 0,
                "shortage_classification": None,
            },
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=regressing_supply
    )._build_later_cycle_discovery_callback(
        db_path=path,
        configuration_id="configuration-g",
    )
    assert _invoke(callback).state == "RUNNING"
    second = _invoke(callback, evaluated_at=NOW + timedelta(seconds=1))
    assert second.state == "FAILED"
    assert second.failure_domain == "INTERNAL"
    assert second.first_terminal_cause == "LATER_CYCLE_SUPPLY_FAILED"


def test_g7_budget_exhaustion_after_yield_keeps_source_truth(
    callback_database,
) -> None:
    path, _, _ = callback_database
    calls = 0

    def exhausted_supply(**_context):
        nonlocal calls
        calls += 1
        if calls == 1:
            return LaterCycleCandidateSupply(
                (),
                (),
                ACQUISITION_QUANTUM_YIELDED,
                {
                    "stage_local_source_requests": 2,
                    "provider_failures": 0,
                    "shortage_classification": None,
                },
            )
        return LaterCycleCandidateSupply(
            (),
            (),
            "BUDGET_EXHAUSTION",
            {
                "stage_local_source_requests": 3,
                "provider_failures": 0,
                "shortage_classification": "BUDGET_EXHAUSTION",
            },
            "SOURCE",
        )

    callback = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=exhausted_supply
    )._build_later_cycle_discovery_callback(
        db_path=path,
        configuration_id="configuration-g",
    )

    assert _invoke(callback).state == "RUNNING"
    exhausted = _invoke(callback, evaluated_at=NOW + timedelta(seconds=1))
    assert exhausted.state == "NO_PAIR"
    assert exhausted.failure_domain == "SOURCE"
    assert exhausted.first_terminal_cause == "BUDGET_EXHAUSTION"
    assert calls == 2


@pytest.mark.parametrize(
    "terminal",
    [ACQUISITION_QUANTUM_YIELDED, WAITING_FOR_ELIGIBLE_SUPPLY],
)
def test_g8_supply_adapter_does_not_assign_failure_domain_to_yield(
    tmp_path,
    monkeypatch,
    terminal,
) -> None:
    path = tmp_path / f"yield-{terminal}.sqlite3"
    apply_migrations(path)
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda *_args, **_kwargs: GraduatedSupply(
            ready=False,
            terminal=terminal,
            graduated_supply=(),
            graduation_proofs={},
            candidate_a=None,
            candidate_b=None,
            two_candidate_selection={},
            handoff_readiness={},
            discovery_report={},
            front_door_report={},
            diagnostics={
                "stage_local_source_requests": 1,
                "provider_failures": 0,
                "shortage_classification": None,
            },
            holder_reserve_supply=(),
            holder_reserve_candidates={},
        ),
    )

    result = build_later_cycle_graduated_supply(
        path,
        campaign_id="campaign-g",
        campaign_run_id="campaign-run-g",
        authoritative_factory_run_id="factory-g",
        proposed_cycle_id="cycle-g-2",
        proposed_cycle_ordinal=2,
        evaluated_at=NOW,
        execution_id="exec-g",
        selection_seed="seed-g",
        migration_transport=object(),
        graduated_supply_kwargs={},
        cooperative_quantum=True,
    )

    assert result.terminal_cause == terminal
    assert result.failure_domain is None
