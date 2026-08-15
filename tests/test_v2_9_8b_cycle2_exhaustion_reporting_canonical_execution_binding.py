"""V2-9.8B Cycle-2 exhaustion reporting / canonical execution-binding repair.

Focused offline regression proof for the two COMMITTED_CODE_DEFECT manifestations
established by
``docs/printer-v1-v2-9-8b-cycle2-authoritative-exhaustion-certificate-reconciliation.md``
and bounded by
``docs/printer-v1-v2-9-8b-cycle2-exhaustion-reporting-canonical-execution-binding-repair-design.md``.

No source fetching, no runtime, no authoritative DB, no authorization, no proof
rerun. Every database used here is a per-test ``tmp_path`` fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Any, Mapping

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    derive_campaign_source_request_key_root,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
    AuthoritativeLiveOperationalCampaignOwner,
    _graduated_supply_terminal_cause,
    _project_supply_exhaustion_certificate,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
import printer_v1.operator_cli.later_cycle_graduated_supply as adapter


NOW = datetime(2026, 8, 15, 19, 53, tzinfo=timezone.utc)

# Exact identities from the reconciled execution.
CANONICAL_EXECUTION_ID = "20260815T194831Z-6d09a756e8d1"
CAMPAIGN_ID = "20260815T194831Z-6d09a756e8d1-campaign"
CAMPAIGN_RUN_ID = "20260815T194831Z-6d09a756e8d1-campaign-run"
FACTORY_RUN_ID = "9296ffff-7e71-46d2-8e63-dd7b755780c9"
PROPOSED_CYCLE_ID = "20260815T194831Z-6d09a756e8d1-cycle-1-2"

# The composite the factory hands the later-cycle boundary as selection input.
SELECTION_SEED = f"{FACTORY_RUN_ID}:{CAMPAIGN_RUN_ID}:c0002"

# The cycle-qualified canonical execution identity the repair must bind.
EXPECTED_CYCLE_EXECUTION_IDENTITY = f"{CANONICAL_EXECUTION_ID}:c0002"

BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL = (
    "BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL"
)

EXHAUSTION_CERTIFICATE = {
    "certificate_id": f"exh-{EXPECTED_CYCLE_EXECUTION_IDENTITY}",
    "campaign_id": CAMPAIGN_ID,
    "execution_id": EXPECTED_CYCLE_EXECUTION_IDENTITY,
    "run_id": CAMPAIGN_RUN_ID,
    "cycle_id": PROPOSED_CYCLE_ID,
    "required_eligible_capacity": 4,
    "eligible_reserve_count": 2,
    "shortage_classification": "TRACKING_STATE_CAPACITY_BLOCKED",
    "last_reason_discovery_could_not_continue": (
        "ALL_REACHABLE_CANDIDATES_EVALUATED"
    ),
    "unexplored_work_prevented_by_hard_ceiling": False,
}

BLOCKED_DIAGNOSTICS: Mapping[str, Any] = {
    "exhaustion_certificate": dict(EXHAUSTION_CERTIFICATE),
    "shortage_classification": "TRACKING_STATE_CAPACITY_BLOCKED",
    "tracking_terminal_cause": "COOLDOWN_REOPEN_REQUIRED",
    "discovery_rounds": 2,
    "eligible_reserve_count": 2,
    "last_stop_reason": "ALL_REACHABLE_CANDIDATES_EVALUATED",
}


GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
HEALTH = MultiCycleAdmissionHealth(
    source_budget_available=True,
    provider_budgets_available=True,
    scheduler_budget_available=True,
    scheduler_due_work_healthy=True,
    close_reserve_available=True,
    campaign_supervision_healthy=True,
    lease_healthy=True,
    db_healthy=True,
    shared_terminal_condition=False,
    cancellation_requested=False,
    discovery_capacity_available=True,
    protected_work_capacity_available=True,
)


@dataclass(frozen=True)
class _TemporalContext:
    admission_observed_at_utc: str


@dataclass(frozen=True)
class _Admission:
    mint: str
    pool_address: str
    market_identity: str
    temporal_context: _TemporalContext


def _graduated_supply(
    *,
    ready: bool,
    terminal: str,
    admissions: tuple[Any, ...] = (),
    reserve_candidates: Mapping[str, Mapping[str, Any]] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> GraduatedSupply:
    return GraduatedSupply(
        ready=ready,
        terminal=terminal,
        graduated_supply=admissions,
        graduation_proofs={},
        candidate_a=None,
        candidate_b=None,
        two_candidate_selection={},
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        diagnostics=dict(diagnostics or {}),
        holder_reserve_supply=admissions,
        holder_reserve_candidates=dict(reserve_candidates or {}),
    )


@pytest.fixture()
def blocked_supply_capture(monkeypatch, tmp_path):
    """Capture the exact kwargs the adapter hands the canonical front door."""
    captured: dict[str, Any] = {}

    def fake_build_graduated_supply(db_path, **kwargs: Any) -> GraduatedSupply:
        captured.update(kwargs)
        captured["db_path"] = db_path
        return _graduated_supply(
            ready=False,
            terminal=BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL,
            diagnostics=BLOCKED_DIAGNOSTICS,
        )

    monkeypatch.setattr(
        adapter, "build_graduated_supply", fake_build_graduated_supply
    )
    return captured, tmp_path / "cycle2-binding.sqlite3"


def _build(db_path, **overrides: Any) -> LaterCycleCandidateSupply:
    kwargs: dict[str, Any] = {
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
        "authoritative_factory_run_id": FACTORY_RUN_ID,
        "proposed_cycle_id": PROPOSED_CYCLE_ID,
        "proposed_cycle_ordinal": 2,
        "evaluated_at": NOW,
        "execution_id": CANONICAL_EXECUTION_ID,
        "selection_seed": SELECTION_SEED,
        "migration_transport": object(),
        "graduated_supply_kwargs": {},
    }
    kwargs.update(overrides)
    return adapter.build_later_cycle_graduated_supply(db_path, **kwargs)


# --------------------------------------------------------------------------
# Defect 1 — canonical execution binding
# --------------------------------------------------------------------------


def test_canonical_execution_id_owns_governed_source_scope(
    blocked_supply_capture,
) -> None:
    captured, db_path = blocked_supply_capture
    _build(db_path)

    scope = captured["campaign_source_request_scope"]
    expected_root = derive_campaign_source_request_key_root(
        EXPECTED_CYCLE_EXECUTION_IDENTITY
    )

    assert scope.execution_id == EXPECTED_CYCLE_EXECUTION_IDENTITY
    assert scope.request_key_root == expected_root
    assert captured["discovery_request_key_prefix"] == expected_root
    assert captured["front_door_request_key_prefix"] == expected_root
    # The canonical execution id must own the root, and the seed must not.
    assert scope.request_key_root.startswith(
        f"{derive_campaign_source_request_key_root(CANONICAL_EXECUTION_ID)}:"
    )
    assert FACTORY_RUN_ID not in scope.request_key_root
    assert CAMPAIGN_RUN_ID not in scope.execution_id


def test_canonical_execution_id_owns_exhaustion_certificate_ownership(
    blocked_supply_capture,
) -> None:
    captured, db_path = blocked_supply_capture
    _build(db_path)

    # The execution_id kwarg is the sole input to the certificate identity
    # and its execution ownership column.
    assert captured["execution_id"] == EXPECTED_CYCLE_EXECUTION_IDENTITY
    assert captured["execution_id"] != SELECTION_SEED
    assert captured["execution_id"].startswith(f"{CANONICAL_EXECUTION_ID}:")


def test_selection_seed_is_preserved_as_selection_input_only(
    blocked_supply_capture,
) -> None:
    captured, db_path = blocked_supply_capture
    _build(db_path)

    assert captured["cycle_seed"] == SELECTION_SEED
    assert captured["campaign_id"] == CAMPAIGN_ID
    assert captured["run_id"] == CAMPAIGN_RUN_ID
    assert captured["cycle_id"] == PROPOSED_CYCLE_ID
    scope = captured["campaign_source_request_scope"]
    assert scope.campaign_id == CAMPAIGN_ID
    assert scope.run_id == CAMPAIGN_RUN_ID
    assert scope.cycle_id == PROPOSED_CYCLE_ID


def test_missing_canonical_execution_id_fails_closed(
    blocked_supply_capture,
) -> None:
    _captured, db_path = blocked_supply_capture
    with pytest.raises(adapter.LaterCycleGraduatedSupplyError) as excinfo:
        _build(db_path, execution_id="   ")
    assert "CANONICAL_EXECUTION_ID_REQUIRED" in str(excinfo.value)


# --------------------------------------------------------------------------
# Defect 2 — blocked diagnostic propagation
# --------------------------------------------------------------------------


def test_blocked_later_cycle_supply_preserves_exhaustion_diagnostics(
    blocked_supply_capture,
) -> None:
    _captured, db_path = blocked_supply_capture
    supply = _build(db_path)

    assert supply.candidates == ()
    assert supply.terminal_cause == BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL
    diagnostics = dict(supply.diagnostics)
    assert (
        diagnostics["shortage_classification"]
        == "TRACKING_STATE_CAPACITY_BLOCKED"
    )
    assert diagnostics["exhaustion_certificate"] == dict(EXHAUSTION_CERTIFICATE)
    assert diagnostics["tracking_terminal_cause"] == "COOLDOWN_REOPEN_REQUIRED"


def test_three_positional_later_cycle_supply_construction_remains_valid() -> None:
    supply = LaterCycleCandidateSupply((), (), "NO_PAIR")
    assert supply.terminal_cause == "NO_PAIR"
    assert dict(supply.diagnostics) == {}


def test_blocked_diagnostics_reach_the_existing_authoritative_mapping(
    blocked_supply_capture,
) -> None:
    _captured, db_path = blocked_supply_capture
    supply = _build(db_path)

    # The single authoritative mapping owner, consulted verbatim.
    assert _graduated_supply_terminal_cause(supply) == "COOLDOWN_REOPEN_REQUIRED"
    assert (
        _graduated_supply_terminal_cause(supply)
        != BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL
    )
    assert (
        _graduated_supply_terminal_cause(supply)
        != BLOCKED_INSUFFICIENT_GRADUATED_POOL
    )


def test_certificate_projection_is_non_null_for_adapter_diagnostics(
    blocked_supply_capture,
) -> None:
    _captured, db_path = blocked_supply_capture
    supply = _build(db_path)

    projected = _project_supply_exhaustion_certificate(dict(supply.diagnostics))
    assert projected is not None
    assert projected["shortage_classification"] == (
        "TRACKING_STATE_CAPACITY_BLOCKED"
    )
    assert projected["execution_id"] == EXPECTED_CYCLE_EXECUTION_IDENTITY
    assert dict(supply.diagnostics)["shortage_classification"] is not None


def test_true_market_shortage_retains_historical_insufficient_pool_conclusion(
    monkeypatch, tmp_path
) -> None:
    def fake_build_graduated_supply(db_path, **kwargs: Any) -> GraduatedSupply:
        return _graduated_supply(
            ready=False,
            terminal=BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL,
            diagnostics={
                "shortage_classification": "TRUE_MARKET_SUPPLY_SHORTAGE",
                "exhaustion_certificate": {"certificate_id": "exh-market"},
            },
        )

    monkeypatch.setattr(
        adapter, "build_graduated_supply", fake_build_graduated_supply
    )
    supply = _build(tmp_path / "market.sqlite3")
    assert (
        _graduated_supply_terminal_cause(supply)
        == BLOCKED_INSUFFICIENT_GRADUATED_POOL
    )


# --------------------------------------------------------------------------
# Successful path keeps diagnostics
# --------------------------------------------------------------------------


@pytest.fixture()
def ready_supply_database(monkeypatch, tmp_path):
    path = tmp_path / "cycle2-ready.sqlite3"
    apply_migrations(path)
    root = derive_campaign_source_request_key_root(
        EXPECTED_CYCLE_EXECUTION_IDENTITY
    )
    connection = sqlite3.connect(path)
    request_id = connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,request_key,requested_at,source_status,"
        "data_quality_label) "
        "VALUES ('dexscreener','fresh_profiles',?,?,'COMPLETE','CLEAN_DATA')",
        (f"{root}-locator", NOW.isoformat()),
    ).lastrowid
    connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,"
        "data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    )
    connection.commit()
    connection.close()

    admissions = tuple(
        _Admission(
            mint=f"mint-{slot}",
            pool_address=f"pool-{slot}",
            market_identity=f"solana-mainnet:pumpswap:pool-{slot}",
            temporal_context=_TemporalContext(NOW.isoformat()),
        )
        for slot in (1, 2)
    )
    reserve = {
        f"mint-{slot}": {"provenance": "dexscreener_fresh_profiles_locator"}
        for slot in (1, 2)
    }

    def fake_build_graduated_supply(db_path, **kwargs: Any) -> GraduatedSupply:
        return _graduated_supply(
            ready=True,
            terminal="CANDIDATE_SUPPLY_READY",
            admissions=admissions,
            reserve_candidates=reserve,
            diagnostics={
                "shortage_classification": None,
                "exhaustion_certificate": None,
                "discovery_rounds": 1,
                "eligible_reserve_count": 2,
                "request_key_root": root,
            },
        )

    monkeypatch.setattr(
        adapter, "build_graduated_supply", fake_build_graduated_supply
    )
    return path


def test_successful_later_cycle_supply_preserves_diagnostics(
    ready_supply_database,
) -> None:
    supply = _build(
        ready_supply_database,
        holder_evidence_owner=lambda _supply: {
            "mint-1": {"eligible": True},
            "mint-2": {"eligible": True},
        },
    )

    assert len(supply.candidates) == 2
    assert supply.terminal_cause is None
    diagnostics = dict(supply.diagnostics)
    assert diagnostics["discovery_rounds"] == 1
    assert diagnostics["eligible_reserve_count"] == 2
    assert diagnostics["request_key_root"] == derive_campaign_source_request_key_root(
        EXPECTED_CYCLE_EXECUTION_IDENTITY
    )


# --------------------------------------------------------------------------
# End-to-end: the truthful cause reaches the durable pre-admission terminal
# --------------------------------------------------------------------------


@pytest.fixture()
def callback_database(tmp_path):
    path = tmp_path / "later-cycle-terminal.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES (?,'RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')",
        (CAMPAIGN_ID,),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", CAMPAIGN_ID, "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,"
        "started_at) VALUES (?,?,?,?,?,?,?)",
        (
            FACTORY_RUN_ID,
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (
            CAMPAIGN_RUN_ID,
            CAMPAIGN_ID,
            1,
            "RUNNING",
            FACTORY_RUN_ID,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    connection.commit()
    connection.close()
    return path


def _invoke_callback(callback):
    return callback(
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        authoritative_factory_run_id=FACTORY_RUN_ID,
        cycle_id=PROPOSED_CYCLE_ID,
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed=SELECTION_SEED,
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )


def test_tracking_state_capacity_blocked_reaches_the_durable_terminal(
    callback_database,
) -> None:
    owner = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=lambda **_: LaterCycleCandidateSupply(
            candidates=(),
            source_evidence=(),
            terminal_cause=BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL,
            diagnostics=dict(BLOCKED_DIAGNOSTICS),
        )
    )
    callback = owner._build_later_cycle_discovery_callback(
        db_path=callback_database, configuration_id="configuration-1"
    )
    result = _invoke_callback(callback)

    assert result.state == "NO_PAIR"
    assert result.first_terminal_cause == "COOLDOWN_REOPEN_REQUIRED"

    connection = sqlite3.connect(callback_database)
    try:
        stored = connection.execute(
            "SELECT first_terminal_cause FROM "
            "printer_pre_admission_discovery_attempts"
        ).fetchone()[0]
    finally:
        connection.close()
    assert stored == "COOLDOWN_REOPEN_REQUIRED"
    assert stored != BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL


def test_blocked_supply_without_diagnostics_keeps_existing_terminal_cause(
    callback_database,
) -> None:
    owner = AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=lambda **_: LaterCycleCandidateSupply(
            (), (), "NO_EXACT_PAIR"
        )
    )
    callback = owner._build_later_cycle_discovery_callback(
        db_path=callback_database, configuration_id="configuration-1"
    )
    result = _invoke_callback(callback)

    assert result.state == "NO_PAIR"
    assert result.first_terminal_cause == "NO_EXACT_PAIR"


def test_unused_candidate_carrier_type_is_still_exported() -> None:
    # Guards the carrier module surface the adapter imports.
    assert LaterCycleDiscoveryCandidate is not None
    assert LaterCycleSourceEvidence is not None
