"""E+F: later-cycle per-cycle source ownership and failure-domain classification."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    derive_campaign_source_request_key_root,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LiveOperationalError,
    LiveTransportError,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    FAILURE_DOMAIN_ELIGIBILITY,
    FAILURE_DOMAIN_INTERNAL,
    FAILURE_DOMAIN_SOURCE,
    LaterCycleGraduatedSupplyError,
    build_later_cycle_graduated_supply,
    classify_later_cycle_failure,
)


NOW = datetime(2026, 8, 17, 14, 0, tzinfo=timezone.utc)


def _supply(*, ready: bool, terminal: str, diagnostics: dict) -> GraduatedSupply:
    return GraduatedSupply(
        ready=ready,
        terminal=terminal,
        graduated_supply=(),
        graduation_proofs={},
        candidate_a=None,
        candidate_b=None,
        two_candidate_selection={},
        handoff_readiness={},
        discovery_report={},
        front_door_report={},
        diagnostics=diagnostics,
        holder_reserve_supply=(),
        holder_reserve_candidates={},
    )


def _insert_cycle_request(path: Path, request_key_root: str) -> None:
    connection = sqlite3.connect(path)
    request_id = int(
        connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,source_status,"
            "data_quality_label) VALUES ('solana_rpc',"
            "'restored_pump_migration_transaction',?,?, 'FAILED','DIRTY_DATA')",
            ("2026-08-17T14:00:00+00:00", f"{request_key_root}-migrate-1"),
        ).lastrowid
    )
    connection.execute(
        "INSERT INTO printer_source_failures("
        "source_name,request_kind,failed_at,failure_type,source_status,"
        "data_quality_label,source_request_id) VALUES ("
        "'solana_rpc','restored_pump_migration_transaction',?,"
        "'SOURCE_AVAILABILITY_FAILURE','FAILED','DIRTY_DATA',?)",
        ("2026-08-17T14:00:01+00:00", request_id),
    )
    connection.commit()
    connection.close()


def test_classify_internal_versus_source_versus_eligibility() -> None:
    assert (
        classify_later_cycle_failure(
            shortage_classification="SOURCE_AVAILABILITY_FAILURE"
        )
        == FAILURE_DOMAIN_SOURCE
    )
    assert (
        classify_later_cycle_failure(
            shortage_classification="DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
        )
        == FAILURE_DOMAIN_INTERNAL
    )
    assert (
        classify_later_cycle_failure(
            shortage_classification="TRACKING_STATE_CAPACITY_BLOCKED"
        )
        == FAILURE_DOMAIN_ELIGIBILITY
    )
    assert (
        classify_later_cycle_failure(
            exception=LiveTransportError("TRANSPORT_UNAVAILABLE", "getTransaction")
        )
        == FAILURE_DOMAIN_SOURCE
    )
    assert (
        classify_later_cycle_failure(
            exception=LaterCycleGraduatedSupplyError("HOLDER_EVIDENCE_OWNER_REQUIRED")
        )
        == FAILURE_DOMAIN_INTERNAL
    )
    assert (
        classify_later_cycle_failure(terminal_cause="NO_EXACT_PAIR")
        == FAILURE_DOMAIN_ELIGIBILITY
    )
    assert (
        classify_later_cycle_failure(terminal_cause="UNKNOWN_UNMAPPED_CAUSE")
        == FAILURE_DOMAIN_INTERNAL
    )


@pytest.mark.parametrize(
    "terminal_cause",
    [
        "SOURCE_AVAILABILITY_FAILURE",
        "SOURCE_VISIBILITY_SHORTAGE",
        "BUDGET_EXHAUSTION",
        "DURATION_EXHAUSTION",
        "TRUE_MARKET_SUPPLY_SHORTAGE",
        "REFRESH_SOURCE_FAILURE",
    ],
)
def test_explicit_canonical_source_terminal_causes_remain_source(
    terminal_cause: str,
) -> None:
    assert (
        classify_later_cycle_failure(terminal_cause=terminal_cause)
        == FAILURE_DOMAIN_SOURCE
    )


@pytest.mark.parametrize(
    "terminal_cause",
    [
        "SOURCE_GOVERNOR_UNAVAILABLE",
        "MIGRATE_ACCOUNT_LAYOUT_MISMATCH",
        "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE",
        "UNKNOWN_ARBITRARY_LOCAL_TERMINAL",
    ],
)
def test_internal_and_unknown_terminal_causes_never_become_source(
    terminal_cause: str,
) -> None:
    assert (
        classify_later_cycle_failure(terminal_cause=terminal_cause)
        == FAILURE_DOMAIN_INTERNAL
    )


def test_exception_types_preserve_source_versus_internal_boundary() -> None:
    assert (
        classify_later_cycle_failure(
            exception=LiveTransportError("TRANSPORT_UNAVAILABLE", "getTransaction")
        )
        == FAILURE_DOMAIN_SOURCE
    )
    assert (
        classify_later_cycle_failure(
            exception=LiveOperationalError("SOURCE_GOVERNOR_UNAVAILABLE")
        )
        == FAILURE_DOMAIN_INTERNAL
    )


def test_blocked_cycle_retains_cycle_scoped_source_lineage(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cycle2-owned.sqlite3"
    apply_migrations(path)
    execution_id = "20260817T140000Z-acctown"
    root = derive_campaign_source_request_key_root(f"{execution_id}:c0002")
    _insert_cycle_request(path, root)

    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda db_path, **kwargs: _supply(
            ready=False,
            terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL",
            diagnostics={
                "shortage_classification": "SOURCE_AVAILABILITY_FAILURE",
                "exhaustion_certificate": {"certificate_id": "exh-source"},
            },
        ),
    )
    result = build_later_cycle_graduated_supply(
        path,
        campaign_id="campaign-a",
        campaign_run_id="run-a",
        authoritative_factory_run_id="factory-a",
        proposed_cycle_id="cycle-2",
        proposed_cycle_ordinal=2,
        evaluated_at=NOW,
        execution_id=execution_id,
        selection_seed="factory-a:run-a:c0002",
        migration_transport=object(),
        graduated_supply_kwargs={},
    )
    assert result.candidates == ()
    assert len(result.source_evidence) == 1
    assert result.source_evidence[0].source_failure_id is not None
    assert result.source_evidence[0].source_response_id is None
    assert result.failure_domain == FAILURE_DOMAIN_SOURCE
    assert (
        result.diagnostics["shortage_classification"]
        == "SOURCE_AVAILABILITY_FAILURE"
    )


def test_blocked_cycle_without_requests_does_not_invent_lineage(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "cycle2-empty.sqlite3"
    apply_migrations(path)
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda db_path, **kwargs: _supply(
            ready=False,
            terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL",
            diagnostics={
                "shortage_classification": "DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE"
            },
        ),
    )
    result = build_later_cycle_graduated_supply(
        path,
        campaign_id="campaign-a",
        campaign_run_id="run-a",
        authoritative_factory_run_id="factory-a",
        proposed_cycle_id="cycle-2",
        proposed_cycle_ordinal=2,
        evaluated_at=NOW,
        execution_id="exec-empty",
        selection_seed="seed-empty",
        migration_transport=object(),
        graduated_supply_kwargs={},
    )
    assert result.source_evidence == ()
    assert result.failure_domain == FAILURE_DOMAIN_INTERNAL


def test_blocked_cycle_ambiguous_lineage_remains_internal(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cycle2-ambiguous.sqlite3"
    apply_migrations(path)
    execution_id = "20260817T140000Z-ambig"
    root = derive_campaign_source_request_key_root(f"{execution_id}:c0002")
    connection = sqlite3.connect(path)
    connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,request_key,source_status,"
        "data_quality_label) VALUES ('solana_rpc',"
        "'restored_pump_migration_transaction',?,?, 'COMPLETE','CLEAN_DATA')",
        ("2026-08-17T14:00:00+00:00", f"{root}-migrate-1"),
    )
    connection.commit()
    connection.close()
    monkeypatch.setattr(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        lambda db_path, **kwargs: _supply(
            ready=False,
            terminal="BLOCKED_INSUFFICIENT_ELIGIBLE_CANDIDATE_POOL",
            diagnostics={"shortage_classification": "TRUE_MARKET_SUPPLY_SHORTAGE"},
        ),
    )
    with pytest.raises(
        LaterCycleGraduatedSupplyError, match="CYCLE_SOURCE_LINEAGE_AMBIGUOUS"
    ):
        build_later_cycle_graduated_supply(
            path,
            campaign_id="campaign-a",
            campaign_run_id="run-a",
            authoritative_factory_run_id="factory-a",
            proposed_cycle_id="cycle-2",
            proposed_cycle_ordinal=2,
            evaluated_at=NOW,
            execution_id=execution_id,
            selection_seed="seed-ambig",
            migration_transport=object(),
            graduated_supply_kwargs={},
        )


def test_three_positional_construction_still_defaults_domain() -> None:
    supply = LaterCycleCandidateSupply((), (), "NO_PAIR")
    assert supply.failure_domain is None
    assert dict(supply.diagnostics) == {}
