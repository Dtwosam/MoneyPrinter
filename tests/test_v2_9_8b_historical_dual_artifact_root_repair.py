from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


APPLICATION_ARTIFACTS = (
    "application-marker.json",
    "git-provenance-manifest.json",
    "wrapper-terminal.json",
    "child-terminal.json",
    "child-stderr.txt",
)


def _fixture_module():
    path = Path(__file__).with_name("test_v2_9_8b_historical_four_token_reconciliation.py")
    spec = importlib.util.spec_from_file_location("historical_four_token_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    return {
        str(path.relative_to(root)): (path.stat().st_size, _sha256(path))
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _split_application_root(root: Path, tmp_path: Path) -> Path:
    application_root = tmp_path / "application-artifacts"
    application_root.mkdir()
    for name in APPLICATION_ARTIFACTS:
        shutil.move(str(root / name), str(application_root / name))
    return application_root


def _run(
    *,
    db: Path,
    pre_campaign: Path,
    root: Path,
    application_root: Path,
    contract,
    recovery_root: Path,
    now,
):
    return recovery.reconcile_exact_historical_four_token_execution(
        operator_approved=True,
        current_db=db,
        pre_campaign_backup=pre_campaign,
        artifact_root=root,
        application_artifact_root=application_root,
        recovery_root=recovery_root,
        contract=contract,
        live_process_probe=lambda _execution: False,
        now=now,
    )


def test_two_root_reconciliation_preserves_application_root_and_replays_idempotently(
    tmp_path: Path,
) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    application_root = _split_application_root(root, tmp_path)
    application_before = _file_snapshot(application_root)
    execution_before = _file_snapshot(root)

    first = _run(
        db=db,
        pre_campaign=pre_campaign,
        root=root,
        application_root=application_root,
        contract=contract,
        recovery_root=tmp_path / "recovery-first",
        now=fixture.NOW,
    )

    assert first["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert first["changed_database_row_identities"] == 10
    assert _file_snapshot(application_root) == application_before
    execution_after = _file_snapshot(root)
    assert "campaign.lease.lock" in execution_before
    assert "campaign.lease.lock" not in execution_after
    assert {
        key: value for key, value in execution_before.items() if key != "campaign.lease.lock"
    } == execution_after

    first_sha = _sha256(db)
    second_root = tmp_path / "recovery-second"
    second = _run(
        db=db,
        pre_campaign=pre_campaign,
        root=root,
        application_root=application_root,
        contract=contract,
        recovery_root=second_root,
        now=fixture.NOW,
    )
    assert second["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED"
    assert second["database_writes"] == 0
    assert _sha256(db) == first_sha
    assert not second_root.exists()
    assert _file_snapshot(application_root) == application_before


def test_missing_application_artifact_rejects_before_db_or_lease_mutation(
    tmp_path: Path,
) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    application_root = _split_application_root(root, tmp_path)
    (application_root / "wrapper-terminal.json").unlink()
    before_db = _sha256(db)
    before_lease = _sha256(root / "campaign.lease.lock")
    recovery_root = tmp_path / "recovery"

    with pytest.raises(recovery.OperationalCampaignRecoveryError, match="artifact missing"):
        _run(
            db=db,
            pre_campaign=pre_campaign,
            root=root,
            application_root=application_root,
            contract=contract,
            recovery_root=recovery_root,
            now=fixture.NOW,
        )

    assert _sha256(db) == before_db
    assert _sha256(root / "campaign.lease.lock") == before_lease
    assert not recovery_root.exists()


def test_application_artifacts_never_fall_back_to_execution_root(tmp_path: Path) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    application_root = tmp_path / "empty-application-root"
    application_root.mkdir()
    before_db = _sha256(db)
    before_lease = _sha256(root / "campaign.lease.lock")

    with pytest.raises(recovery.OperationalCampaignRecoveryError, match="artifact missing"):
        _run(
            db=db,
            pre_campaign=pre_campaign,
            root=root,
            application_root=application_root,
            contract=contract,
            recovery_root=tmp_path / "recovery",
            now=fixture.NOW,
        )

    assert _sha256(db) == before_db
    assert _sha256(root / "campaign.lease.lock") == before_lease


def test_terminal_summary_must_remain_owned_by_execution_root(tmp_path: Path) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    application_root = _split_application_root(root, tmp_path)
    shutil.move(str(root / "terminal-summary.json"), str(application_root / "terminal-summary.json"))
    before_db = _sha256(db)
    before_lease = _sha256(root / "campaign.lease.lock")

    with pytest.raises(recovery.OperationalCampaignRecoveryError, match="artifact missing"):
        _run(
            db=db,
            pre_campaign=pre_campaign,
            root=root,
            application_root=application_root,
            contract=contract,
            recovery_root=tmp_path / "recovery",
            now=fixture.NOW,
        )

    assert _sha256(db) == before_db
    assert _sha256(root / "campaign.lease.lock") == before_lease
