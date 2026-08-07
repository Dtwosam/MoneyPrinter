from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from printer_v1.db.migrate import (
    apply_migrations,
    canonical_migration_count,
    canonical_migration_names,
)
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _summary_payload(proof_dir: Path, db_path: Path) -> dict:
    payload = {
        "summary_schema": "CHECKPOINT8_CONTROLLING_PROOF_SUMMARY_V1",
        "proof_id": "checkpoint8-independent-fixture",
        "git_head": "a" * 40,
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "campaign_acceptance_verdict": "CAMPAIGN_PASS",
        "campaign_pass": True,
        "fixture_composition_manifest_sha256": "b" * 64,
        "fixture_transport_operation_count": 7,
        "network_attempt_count": 0,
        "network_attempts": [],
        "replay_zero_work": True,
        "pre_run_evidence": {
            "db_path": str(db_path.resolve()),
            "artifact_root": str((proof_dir / "artifacts").resolve()),
            "migration_count": canonical_migration_count(),
            "migration_head": canonical_migration_names()[-1],
            "protected_capability_counts": {
                "printer_memory_retrieval_queries": 0,
                "printer_memory_retrieval_matches": 0,
                "printer_paper_decisions": 0,
                "printer_paper_positions": 0,
                "printer_paper_trade_events": 0,
                "printer_paper_trade_audits": 0,
            },
        },
        "post_run_evidence": {
            "integrity_check": "ok",
            "foreign_key_violations": 0,
            "protected_capability_deltas": {
                "printer_memory_retrieval_queries": 0,
                "printer_memory_retrieval_matches": 0,
                "printer_paper_decisions": 0,
                "printer_paper_positions": 0,
                "printer_paper_trade_events": 0,
                "printer_paper_trade_audits": 0,
            },
            "longer_window_counts": {
                "WINDOW_1H": 0,
                "WINDOW_4H": 0,
                "WINDOW_12H": 0,
                "WINDOW_24H": 0,
            },
        },
        "terminal": {
            "campaign_id": "campaign-c8",
            "campaign_acceptance_verdict": "CAMPAIGN_PASS",
            "campaign_pass": True,
            "report": {"campaign_id": "campaign-c8", "run_id": "run-c8"},
        },
        "report_only": {
            "status": "REPORT_ONLY_PASS",
            "campaign_id": "campaign-c8",
            "run_id": "run-c8",
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
            "replay_new_source_calls": 0,
            "replay_new_scheduler_calls": 0,
            "replay_database_writes": 0,
        },
        "sentinel_path": str((proof_dir / "checkpoint8-controlling-attempt.json").resolve()),
    }
    payload["frozen_evidence_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return payload


def _write_frozen_fixture(tmp_path: Path) -> tuple[Path, Path, dict]:
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    (proof_dir / "artifacts").mkdir()
    db_path = proof_dir / "checkpoint8-controlling-proof.sqlite3"
    apply_migrations(db_path)
    payload = _summary_payload(proof_dir, db_path)
    (proof_dir / "checkpoint8-controlling-attempt.json").write_text(
        json.dumps(
            {
                "attempt_ordinal": 1,
                "git_head": payload["git_head"],
                "proof_id": payload["proof_id"],
                "sentinel_schema": "CHECKPOINT8_CONTROLLING_ATTEMPT_V1",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (proof_dir / "checkpoint8-controlling-proof-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return proof_dir, db_path, payload


def _clean_graph_projection() -> dict:
    return {
        "campaign_id": "campaign-c8",
        "run_id": "run-c8",
        "windows": [
            {
                "token_mint": "MintAlpha11111111111111111111111111111111",
                "memory_window_id": "window-alpha",
                "window_kind": "WINDOW_15M",
                "terminal": True,
                "memory_quality_label": "CLEAN_MEMORY",
                "fingerprint_sha256": "c" * 64,
            },
            {
                "token_mint": "MintBravo11111111111111111111111111111111",
                "memory_window_id": "window-bravo",
                "window_kind": "WINDOW_15M",
                "terminal": True,
                "memory_quality_label": "CLEAN_MEMORY",
                "fingerprint_sha256": "d" * 64,
            },
        ],
    }


def _clean_governance_projection() -> dict:
    return {
        "source_governor_owner": "Source Governor",
        "central_scheduler_owner": "Central Scheduler",
        "active_work_count": 0,
        "locked_scheduler_job_count": 0,
        "orphan_owned_work_count": 0,
        "lease_released": True,
        "lease_file_present": False,
        "automatic_retry_created": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_created": False,
        "successor_created": False,
    }


def test_frozen_summary_hash_is_recomputed_and_tamper_blocks(tmp_path: Path) -> None:
    inspector = _load_inspector("checkpoint8_inspector_frozen_hash")
    proof_dir, _db_path, payload = _write_frozen_fixture(tmp_path)
    loaded = inspector.load_checkpoint8_frozen_summary(proof_dir)
    assert loaded["proof_id"] == payload["proof_id"]

    summary_path = proof_dir / "checkpoint8-controlling-proof-summary.json"
    tampered = dict(payload)
    tampered["campaign_id"] = "tampered-campaign"
    summary_path.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="FROZEN_EVIDENCE_SHA256_MISMATCH",
    ):
        inspector.load_checkpoint8_frozen_summary(proof_dir)


def test_database_safety_is_recomputed_read_only_and_bytes_unchanged(tmp_path: Path) -> None:
    inspector = _load_inspector("checkpoint8_inspector_db_safety")
    proof_dir, db_path, payload = _write_frozen_fixture(tmp_path)
    before = _sha256(db_path)
    result = inspector.recompute_checkpoint8_database_safety(
        payload,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    after = _sha256(db_path)
    assert before == after
    assert result["migration_count"] == canonical_migration_count()
    assert result["migration_head"] == canonical_migration_names()[-1]
    assert result["integrity_check"] == "ok"
    assert result["foreign_key_violations"] == 0
    assert result["read_only"] is True
    assert Path(result["db_path"]).resolve() == db_path.resolve()


def test_graph_projection_requires_exact_two_clean_terminal_window_15m_memories() -> None:
    inspector = _load_inspector("checkpoint8_inspector_graph_projection")
    result = inspector.validate_checkpoint8_graph_projection(
        _clean_graph_projection()
    )
    assert result["exact_two_terminal_window_15m"] is True
    assert result["exact_two_distinct_mints"] is True
    assert result["both_clean_memory"] is True
    assert result["both_fingerprints_present"] is True

    broken = _clean_graph_projection()
    broken["windows"] = broken["windows"][:1]
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED",
    ):
        inspector.validate_checkpoint8_graph_projection(broken)


def test_governance_projection_requires_exact_owners_cleanup_and_no_reuse() -> None:
    inspector = _load_inspector("checkpoint8_inspector_governance_projection")
    result = inspector.validate_checkpoint8_governance_projection(
        _clean_governance_projection()
    )
    assert result["source_governor_exact"] is True
    assert result["central_scheduler_exact"] is True
    assert result["zero_active_locked_orphan_work"] is True
    assert result["lease_released"] is True
    assert result["no_retry_rerun_resume_restart_successor"] is True

    broken = _clean_governance_projection()
    broken["successor_created"] = True
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="RETRY_OR_REUSE_FACT_FORBIDDEN",
    ):
        inspector.validate_checkpoint8_governance_projection(broken)


def test_frozen_safety_requires_zero_network_replay_downstream_and_long_windows(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("checkpoint8_inspector_frozen_safety")
    _proof_dir, _db_path, payload = _write_frozen_fixture(tmp_path)
    result = inspector.validate_checkpoint8_frozen_safety(payload)
    assert result["campaign_pass"] is True
    assert result["acceptance_pass"] is True
    assert result["zero_network_attempts"] is True
    assert result["fixture_operations_positive"] is True
    assert result["replay_zero_work"] is True
    assert result["protected_capability_zero_delta"] is True
    assert result["longer_windows_absent"] is True

    broken = dict(payload)
    broken["network_attempt_count"] = 1
    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="NETWORK_ATTEMPTS_MUST_BE_ZERO",
    ):
        inspector.validate_checkpoint8_frozen_safety(broken)


def test_independent_findings_combine_db_graph_governance_and_frozen_safety(tmp_path: Path) -> None:
    inspector = _load_inspector("checkpoint8_inspector_findings")
    _proof_dir, _db_path, payload = _write_frozen_fixture(tmp_path)
    findings = inspector.build_checkpoint8_independent_findings(
        frozen_summary=payload,
        database_safety={
            "migration_count": canonical_migration_count(),
            "migration_head": canonical_migration_names()[-1],
            "integrity_check": "ok",
            "foreign_key_violations": 0,
            "read_only": True,
        },
        graph_projection=inspector.validate_checkpoint8_graph_projection(
            _clean_graph_projection()
        ),
        governance_projection=inspector.validate_checkpoint8_governance_projection(
            _clean_governance_projection()
        ),
        frozen_safety=inspector.validate_checkpoint8_frozen_safety(payload),
    )
    assert findings["verdict"] == "CHECKPOINT8_INDEPENDENT_INSPECTION_PASS"
    assert findings["pass"] is True


def test_inspection_artifact_is_separate_exclusive_and_never_mutates_db(tmp_path: Path) -> None:
    inspector = _load_inspector("checkpoint8_inspector_artifact")
    proof_dir, db_path, payload = _write_frozen_fixture(tmp_path)
    before = _sha256(db_path)
    findings = {
        "verdict": "CHECKPOINT8_INDEPENDENT_INSPECTION_PASS",
        "pass": True,
        "proof_id": payload["proof_id"],
        "campaign_id": payload["campaign_id"],
        "run_id": payload["run_id"],
    }
    artifact = inspector.write_checkpoint8_independent_inspection_artifact(
        proof_dir,
        findings,
    )
    assert Path(artifact).is_file()
    assert Path(artifact).parent == proof_dir.resolve()
    assert Path(artifact).name == "checkpoint8-independent-inspection.json"
    assert _sha256(db_path) == before

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="INDEPENDENT_INSPECTION_ARTIFACT_ALREADY_EXISTS",
    ):
        inspector.write_checkpoint8_independent_inspection_artifact(
            proof_dir,
            findings,
        )
