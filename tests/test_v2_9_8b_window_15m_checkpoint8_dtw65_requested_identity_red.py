from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BASE_FIXTURE_PATH = (
    ROOT
    / "tests"
    / "test_v2_9_8b_window_15m_checkpoint8_dtw57_durable_reconstruction_red.py"
)
INSPECTOR_PATH = ROOT / "scripts" / "v2_9_8b_checkpoint8_independent_inspection.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = _load_module(BASE_FIXTURE_PATH, "dtw65_base_fixture")


def _load_inspector(name: str):
    return _load_module(INSPECTOR_PATH, name)


def _summary_and_reconstructed_identity(tmp_path: Path):
    _proof_dir, _db_path, summary = BASE._build_fixture(tmp_path)
    identity = dict(
        summary["report_only"]["full_run_terminal_evidence"]["identity"]
    )
    return summary, identity


def _replace_requested_identity_with_exact_legacy_top_level(summary: dict) -> None:
    replay = summary["report_only"]
    replay.pop("requested_identity")
    replay["campaign_id"] = summary["campaign_id"]
    replay["run_id"] = summary["run_id"]


def test_durable_missing_requested_identity_cannot_use_exact_top_level_fallback(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw65_missing_requested_identity")
    summary, identity = _summary_and_reconstructed_identity(tmp_path)
    _replace_requested_identity_with_exact_legacy_top_level(summary)

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_REQUESTED_IDENTITY_MISSING",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(
            summary,
            reconstructed_identity=identity,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("status", "NOT_REPLAYED"),
        ("mode", "NOT_REPORT_ONLY"),
    ),
)
def test_durable_missing_requested_identity_cannot_bypass_replay_mode_checks(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    inspector = _load_inspector(f"dtw65_missing_requested_identity_{field}")
    summary, identity = _summary_and_reconstructed_identity(tmp_path)
    _replace_requested_identity_with_exact_legacy_top_level(summary)
    summary["report_only"][field] = value

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_REQUESTED_IDENTITY_MISSING",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(
            summary,
            reconstructed_identity=identity,
        )


@pytest.mark.parametrize("field", ("campaign_id", "run_id"))
def test_durable_requested_identity_required_field_missing_uses_missing_boundary(
    tmp_path: Path,
    field: str,
) -> None:
    inspector = _load_inspector(f"dtw65_requested_identity_missing_{field}")
    summary, identity = _summary_and_reconstructed_identity(tmp_path)
    summary["report_only"]["requested_identity"].pop(field)

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_REQUESTED_IDENTITY_MISSING",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(
            summary,
            reconstructed_identity=identity,
        )


def test_legacy_direct_helper_still_allows_exact_top_level_fallback(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw65_legacy_fallback")
    summary, _identity = _summary_and_reconstructed_identity(tmp_path)
    _replace_requested_identity_with_exact_legacy_top_level(summary)

    result = inspector.validate_checkpoint8_report_and_manifest_identity(summary)
    assert result == {
        "campaign_identity_exact": True,
        "run_identity_exact": True,
        "fixture_manifest_exact": True,
    }


def test_present_wrong_requested_identity_keeps_mismatch_boundary(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw65_wrong_requested_identity")
    summary, identity = _summary_and_reconstructed_identity(tmp_path)
    summary["report_only"]["requested_identity"]["run_id"] = "wrong-run"

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_IDENTITY_MISMATCH",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(
            summary,
            reconstructed_identity=identity,
        )


def test_present_requested_identity_wrong_mode_keeps_mismatch_boundary(
    tmp_path: Path,
) -> None:
    inspector = _load_inspector("dtw65_wrong_requested_mode")
    summary, identity = _summary_and_reconstructed_identity(tmp_path)
    summary["report_only"]["mode"] = "NOT_REPORT_ONLY"

    with pytest.raises(
        inspector.Checkpoint8IndependentInspectionError,
        match="REPORT_REPLAY_IDENTITY_MISMATCH",
    ):
        inspector.validate_checkpoint8_report_and_manifest_identity(
            summary,
            reconstructed_identity=identity,
        )
