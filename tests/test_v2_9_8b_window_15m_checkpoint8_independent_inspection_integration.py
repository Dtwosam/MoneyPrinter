from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_PATH = (
    ROOT / "scripts" / "v2_9_8b_checkpoint8_independent_inspection.py"
)


def _load_inspector(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, INSPECTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspector_derives_current_run_graph_and_governance_from_read_only_db(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("checkpoint8_inspector_db_derivation")
    db_path = tmp_path / "empty-canonical.sqlite3"
    apply_migrations(db_path)
    frozen_summary = {
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "pre_run_evidence": {"db_path": str(db_path.resolve())},
    }

    source = inspect.getsource(
        inspector.derive_checkpoint8_independent_db_projections
    )
    for required in (
        "open_independent_read_only_db",
        "printer_memory_factory_run_steps",
        "printer_episodes",
        "printer_memory_fingerprints",
        "printer_memory_factory_campaign_supervision",
        "printer_memory_factory_campaign_scheduler_work",
        "printer_scheduler_jobs",
        "printer_discovery_work",
        "run_id",
        "campaign_id",
    ):
        assert required in source

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="CURRENT_RUN_GRAPH_MISSING",
    ):
        inspector.derive_checkpoint8_independent_db_projections(
            frozen_summary,
            canonical_db_path=CANONICAL_PERSISTENT_DB,
        )


def test_report_replay_and_fixture_manifest_identity_parity() -> None:
    inspector = _load_inspector("checkpoint8_inspector_identity_parity")
    summary = {
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "fixture_composition_manifest_sha256": "a" * 64,
        "pre_run_evidence": {
            "fixture_composition_manifest_sha256": "a" * 64,
        },
        "terminal": {
            "campaign_id": "campaign-c8",
            "report": {
                "campaign_id": "campaign-c8",
                "run_id": "run-c8",
            },
        },
        "report_only": {
            "campaign_id": "campaign-c8",
            "run_id": "run-c8",
            "fixture_composition_manifest_sha256": "a" * 64,
        },
    }
    result = inspector.validate_checkpoint8_report_and_manifest_identity(summary)
    assert result["campaign_identity_exact"] is True
    assert result["run_identity_exact"] is True
    assert result["fixture_manifest_exact"] is True

    broken = {
        **summary,
        "report_only": {
            **summary["report_only"],
            "run_id": "wrong-run",
        },
    }
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_IDENTITY_MISMATCH",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(broken)


def test_full_inspection_orchestrator_uses_db_derivation_and_no_operational_calls() -> None:
    inspector = _load_inspector("checkpoint8_inspector_orchestrator")
    source = inspect.getsource(inspector.inspect_checkpoint8_frozen_proof_directory)
    for required in (
        "load_checkpoint8_frozen_summary",
        "recompute_checkpoint8_database_safety",
        "derive_checkpoint8_independent_db_projections",
        "validate_checkpoint8_graph_projection",
        "validate_checkpoint8_governance_projection",
        "validate_checkpoint8_frozen_safety",
        "validate_checkpoint8_report_and_manifest_identity",
        "build_checkpoint8_independent_findings",
        "write_checkpoint8_independent_inspection_artifact",
    ):
        assert required in source
    assert "run_operational_campaign(" not in source
    assert "report_only(" not in source


def test_inspector_main_is_proof_directory_only_and_wired_to_orchestrator() -> None:
    inspector = _load_inspector("checkpoint8_inspector_main")
    signature = inspect.signature(inspector.main)
    assert tuple(signature.parameters) == ("argv",)
    source = inspect.getsource(inspector.main)
    assert "--proof-dir" in source
    assert "inspect_checkpoint8_frozen_proof_directory" in source
    assert "run_operational_campaign(" not in source
    assert "report_only(" not in source


def test_inspector_source_has_no_campaign_or_replay_dependency() -> None:
    source = INSPECTOR_PATH.read_text(encoding="utf-8")
    assert "operational_memory_factory_command" not in source
    assert "run_operational_campaign(" not in source
    assert "report_only(" not in source
    assert "v2_9_8b_checkpoint8_controlling_public_composition_proof" not in source
