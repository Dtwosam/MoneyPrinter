from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE_FIXTURE_PATH = (
    ROOT
    / "tests"
    / "test_v2_9_8b_window_15m_checkpoint8_dtw57_durable_reconstruction_red.py"
)
INSPECTOR_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_independent_inspection.py"

REQUIRED_IDENTITY_FIELDS = (
    "campaign_id",
    "campaign_run_id",
    "configuration_id",
    "cycle_id",
    "factory_run_id",
    "execution_id",
    "supervision_id",
)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module(BASE_FIXTURE_PATH, "dtw61_base_fixture")


def _load_inspector(name: str):
    return _load_module(INSPECTOR_PATH, name)


def _rewrite_terminal_report_without_identity_field(
    proof_dir: Path,
    db_path: Path,
    field: str,
) -> None:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT report_id, report_json FROM printer_memory_factory_campaign_reports "
            "WHERE report_kind='TERMINAL' AND report_state='REPORT_TERMINAL'"
        ).fetchone()
        assert row is not None
        payload = json.loads(row["report_json"])
    finally:
        connection.close()

    identity = payload["full_run_terminal_evidence"]["identity"]
    assert field in identity
    identity.pop(field)
    report_text = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    report_hash = hashlib.sha256(report_text.encode("utf-8")).hexdigest()

    BASE._replace_row(
        db_path,
        "printer_memory_factory_campaign_reports",
        "report_id",
        row["report_id"],
        {"report_json": report_text, "report_hash": report_hash},
    )

    artifacts = sorted(
        (proof_dir / "checkpoint8-artifacts").rglob("*.campaign-report.json")
    )
    assert len(artifacts) == 1
    artifacts[0].write_bytes(report_text.encode("utf-8"))


def _remove_replay_identity_field(payload: dict, field: str | None) -> None:
    evidence = payload["report_only"]["full_run_terminal_evidence"]
    if field is None:
        evidence.pop("identity")
        return
    identity = evidence["identity"]
    assert field in identity
    identity.pop(field)


def _remove_replay_proof_expectation_piece(payload: dict, case: str) -> None:
    evidence = payload["report_only"]["full_run_terminal_evidence"]
    if case == "authorization_and_invocation":
        evidence.pop("authorization_and_invocation")
        return
    authorization = evidence["authorization_and_invocation"]
    if case == "proof_expectation":
        authorization.pop("proof_expectation")
        return
    expectation = authorization["proof_expectation"]
    if case == "proof_id":
        expectation.pop("proof_id")
        return
    if case == "fixture_composition_manifest_sha256":
        expectation.pop("fixture_composition_manifest_sha256")
        return
    raise AssertionError(case)


@pytest.mark.parametrize("field", REQUIRED_IDENTITY_FIELDS)
def test_terminal_report_required_identity_field_missing_fails_closed(
    tmp_path: Path,
    field: str,
) -> None:
    inspector = _load_inspector(f"dtw61_terminal_{field}")
    proof_dir, _db_path, _summary = BASE._build_fixture(
        tmp_path,
        terminal_identity_omit_field=field,
    )

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="TERMINAL_REPORT_IDENTITY_MISSING",
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)


@pytest.mark.parametrize("field", (None, *REQUIRED_IDENTITY_FIELDS))
def test_replay_full_run_required_identity_missing_fails_closed(
    tmp_path: Path,
    field: str | None,
) -> None:
    inspector = _load_inspector(f"dtw61_replay_identity_{field or 'carrier'}")
    proof_dir, _db_path, _summary = BASE._build_fixture(tmp_path)
    BASE._mutate_summary(
        proof_dir,
        lambda payload: _remove_replay_identity_field(payload, field),
    )

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_IDENTITY_MISSING",
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)


@pytest.mark.parametrize(
    "case",
    (
        "authorization_and_invocation",
        "proof_expectation",
        "proof_id",
        "fixture_composition_manifest_sha256",
    ),
)
def test_replay_proof_expectation_required_identity_missing_fails_closed(
    tmp_path: Path,
    case: str,
) -> None:
    inspector = _load_inspector(f"dtw61_replay_expectation_{case}")
    proof_dir, _db_path, _summary = BASE._build_fixture(tmp_path)
    BASE._mutate_summary(
        proof_dir,
        lambda payload: _remove_replay_proof_expectation_piece(payload, case),
    )

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING",
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)


def test_present_wrong_replay_factory_identity_still_uses_mismatch_boundary(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw61_wrong_replay_factory")
    proof_dir, _db_path, _summary = BASE._build_fixture(tmp_path)
    BASE._mutate_summary(
        proof_dir,
        lambda payload: payload["report_only"]["full_run_terminal_evidence"][
            "identity"
        ].__setitem__("factory_run_id", BASE.ALT_FACTORY_RUN_ID),
    )

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="CURRENT_FACTORY_RUN_IDENTITY_CONFLICT|REPORT_REPLAY_IDENTITY_MISMATCH",
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)


def test_present_wrong_replay_manifest_still_uses_manifest_mismatch_boundary(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw61_wrong_replay_manifest")
    proof_dir, _db_path, _summary = BASE._build_fixture(tmp_path)
    BASE._mutate_summary(
        proof_dir,
        lambda payload: payload["report_only"]["full_run_terminal_evidence"][
            "authorization_and_invocation"
        ]["proof_expectation"].__setitem__(
            "fixture_composition_manifest_sha256",
            "f" * 64,
        ),
    )

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="FIXTURE_MANIFEST_IDENTITY_MISMATCH",
    ):
        inspector.inspect_checkpoint8_frozen_proof_directory(proof_dir)
