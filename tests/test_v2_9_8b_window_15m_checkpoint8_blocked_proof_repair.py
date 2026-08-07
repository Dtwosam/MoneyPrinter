from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from printer_v1.contracts.enums import SourceStatus
from printer_v1.sources.contracts import GOVERNOR_ONLY_EXECUTION_PATH
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    SOURCE_NAME as MIGRATION_SOURCE,
    TRANSACTION_REQUEST_KIND,
    build_direct_pump_migration_adapter,
)


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = (
    ROOT / "scripts" / "v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
)


def _load_harness(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context(request_kind: str, *, signature: str | None = None):
    payload = {} if signature is None else {"signature": signature}
    return SimpleNamespace(
        request=SimpleNamespace(
            source_name=MIGRATION_SOURCE,
            request_kind=request_kind,
            payload=payload,
        ),
        governor_approved=True,
        execution_path=GOVERNOR_ONLY_EXECUTION_PATH,
    )


def test_checkpoint8_restored_migration_fixture_passes_real_adapter_contract(
    tmp_path: Path,
) -> None:
    harness = _load_harness("checkpoint8_blocked_repair_migration_contract")
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path,
        proof_id="checkpoint8-blocked-repair-migration-contract",
        git_head="a" * 40,
    )
    materialized = harness.proof.materialize_disposable_public_composition_execution(
        prepared.runtime
    )
    migration_transport = materialized.top_level_transports["migration_transport"]
    adapter = build_direct_pump_migration_adapter(
        enabled=True,
        transport=migration_transport,
    )

    page = adapter.execute(_context(SIGNATURE_PAGE_REQUEST_KIND))
    assert page.source_status is SourceStatus.COMPLETE
    assert page.failure_type is None
    signatures = list(page.normalized_payload["signatures"])
    assert len(signatures) == 4

    observed_mints: set[str] = set()
    observed_pools: set[str] = set()
    for row in signatures:
        result = adapter.execute(
            _context(
                TRANSACTION_REQUEST_KIND,
                signature=str(row["signature"]),
            )
        )
        assert result.source_status is SourceStatus.COMPLETE
        assert result.failure_type is None
        tokens = list(result.normalized_payload["tokens"])
        assert len(tokens) == 1
        token = tokens[0]
        assert token["migration_signature"] == row["signature"]
        assert token["pump_instruction_verified"] is True
        observed_mints.add(str(token["mint"]))
        observed_pools.add(str(token["pool_address"]))

    assert len(observed_mints) == 4
    assert len(observed_pools) == 4
    assert not (observed_mints & observed_pools)


def _pre_lifecycle_terminal(*, run_id: str = "run-c8") -> dict[str, object]:
    return {
        "status": "OPERATIONAL_CAMPAIGN_PRE_LIFECYCLE_TERMINAL",
        "campaign_id": "campaign-c8",
        "campaign_acceptance_verdict": "HONEST_BLOCKED",
        "campaign_pass": False,
        "report": {
            "campaign_id": "campaign-c8",
            "report_id": "report-c8",
        },
        "cleanup": {
            "campaign_id": "campaign-c8",
            "run_id": run_id,
        },
        "reconciliation": {
            "active_work": {
                "scope": {
                    "campaign_id": "campaign-c8",
                    "run_id": run_id,
                }
            },
            "discovery_parity": {
                "scope": {
                    "campaign_id": "campaign-c8",
                    "run_id": run_id,
                }
            },
        },
    }


def test_checkpoint8_terminal_identity_accepts_real_pre_lifecycle_shape() -> None:
    harness = _load_harness("checkpoint8_blocked_repair_terminal_identity")
    assert harness.extract_checkpoint8_terminal_identity(
        _pre_lifecycle_terminal()
    ) == ("campaign-c8", "run-c8")


def test_checkpoint8_terminal_identity_rejects_conflicting_nested_run_ids() -> None:
    harness = _load_harness("checkpoint8_blocked_repair_terminal_conflict")
    terminal = _pre_lifecycle_terminal()
    terminal["reconciliation"]["active_work"]["scope"]["run_id"] = "other-run"
    with pytest.raises(
        harness.Checkpoint8ControllingProofError,
        match="CHECKPOINT8_TERMINAL_IDENTITY_CONFLICT",
    ):
        harness.extract_checkpoint8_terminal_identity(terminal)


def test_checkpoint8_terminal_identity_accepts_lifecycle_success_shape() -> None:
    harness = _load_harness("checkpoint8_blocked_repair_terminal_success")
    terminal = {
        "status": "OPERATIONAL_CAMPAIGN_TERMINAL",
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "report": {
            "campaign_id": "campaign-c8",
            "run_id": "run-c8",
        },
    }
    assert harness.extract_checkpoint8_terminal_identity(terminal) == (
        "campaign-c8",
        "run-c8",
    )
