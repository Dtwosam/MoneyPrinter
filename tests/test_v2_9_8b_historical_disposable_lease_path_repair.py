from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


def _fixture_module():
    path = Path(__file__).with_name(
        "test_v2_9_8b_historical_four_token_reconciliation.py"
    )
    spec = importlib.util.spec_from_file_location("historical_fixture_lease", path)
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


def _prepare_disposable(tmp_path: Path):
    fixture = _fixture_module()
    original = tmp_path / "original"
    original.mkdir()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        original, include_discovery_batch=True
    )

    original_db_sha = _sha256(db)
    original_lease = root / "campaign.lease.lock"
    original_lease_sha = _sha256(original_lease)

    disposable = tmp_path / "disposable"
    disposable.mkdir()
    disposable_db = disposable / "historical.sqlite3"
    disposable_pre_campaign = disposable / "printer_v1.pre-campaign.backup.sqlite3"
    disposable_root = disposable / fixture.EXECUTION_ID
    shutil.copy2(db, disposable_db)
    shutil.copy2(pre_campaign, disposable_pre_campaign)
    shutil.copytree(root, disposable_root)

    assert _sha256(disposable_db) == original_db_sha
    rebound = type(contract)(
        expected_current_sha256=original_db_sha,
        pre_campaign_backup_sha256=_sha256(disposable_pre_campaign),
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    return (
        fixture,
        db,
        root,
        original_db_sha,
        original_lease_sha,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        rebound,
    )


def test_exact_disposable_lease_override_reconciles_without_touching_original(
    tmp_path: Path,
) -> None:
    (
        fixture,
        original_db,
        original_root,
        original_db_sha,
        original_lease_sha,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    ) = _prepare_disposable(tmp_path)

    disposable_lease = disposable_root / "campaign.lease.lock"
    result = fixture._run_recovery(
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
        tmp_path,
        recovery_root=tmp_path / "disposable-recovery",
        lease_lock_path_override=disposable_lease,
    )

    assert result["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert result["changed_database_row_identities"] == 10
    assert not disposable_lease.exists()
    assert _sha256(original_db) == original_db_sha
    assert (original_root / "campaign.lease.lock").is_file()
    assert _sha256(original_root / "campaign.lease.lock") == original_lease_sha

    post_sha = _sha256(disposable_db)
    second = fixture._run_recovery(
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
        tmp_path,
        recovery_root=tmp_path / "disposable-recovery-2",
        lease_lock_path_override=disposable_lease,
    )
    assert second["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED"
    assert second["database_writes"] == 0
    assert _sha256(disposable_db) == post_sha


def test_disposable_lease_override_must_be_exact_artifact_root_lease(
    tmp_path: Path,
) -> None:
    (
        fixture,
        original_db,
        original_root,
        original_db_sha,
        original_lease_sha,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    ) = _prepare_disposable(tmp_path)
    before_sha = _sha256(disposable_db)

    with pytest.raises(recovery.OperationalCampaignRecoveryError):
        fixture._run_recovery(
            disposable_db,
            disposable_pre_campaign,
            disposable_root,
            contract,
            tmp_path,
            recovery_root=tmp_path / "bad-recovery",
            lease_lock_path_override=tmp_path / "unrelated" / "campaign.lease.lock",
        )

    assert _sha256(disposable_db) == before_sha
    assert _sha256(original_db) == original_db_sha
    assert (original_root / "campaign.lease.lock").is_file()
    assert _sha256(original_root / "campaign.lease.lock") == original_lease_sha
