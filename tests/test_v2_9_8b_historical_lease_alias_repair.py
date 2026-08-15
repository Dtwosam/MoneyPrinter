from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import sqlite3

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


def _fixture_module():
    path = Path(__file__).with_name(
        "test_v2_9_8b_historical_four_token_reconciliation.py"
    )
    spec = importlib.util.spec_from_file_location("historical_lease_fixture", path)
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


def _prepare_disposable_copy(tmp_path: Path):
    fixture = _fixture_module()
    source = tmp_path / "source"
    source.mkdir()
    source_db, source_pre_campaign, source_root, contract = fixture._prepare_exact_residue(
        source, include_discovery_batch=True
    )

    disposable = tmp_path / "disposable"
    disposable.mkdir()
    disposable_db = disposable / "historical.sqlite3"
    disposable_pre_campaign = disposable / "printer_v1.pre-campaign.backup.sqlite3"
    disposable_root = disposable / fixture.EXECUTION_ID
    shutil.copy2(source_db, disposable_db)
    shutil.copy2(source_pre_campaign, disposable_pre_campaign)
    shutil.copytree(source_root, disposable_root)

    assert _sha256(disposable_db) == _sha256(source_db)
    assert _sha256(disposable_pre_campaign) == _sha256(source_pre_campaign)
    return (
        fixture,
        source_db,
        source_root,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    )


def test_exact_disposable_alias_reconciles_without_rebinding_sqlite_lease_path(
    tmp_path: Path,
) -> None:
    (
        fixture,
        _source_db,
        source_root,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    ) = _prepare_disposable_copy(tmp_path)
    recorded_lease = source_root / "campaign.lease.lock"
    alias = disposable_root / "campaign.lease.lock"
    recorded_before = recorded_lease.read_bytes()

    result = fixture._run_recovery(
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
        tmp_path,
        recovery_root=tmp_path / "recovery-alias",
        disposable_lease_alias=alias,
    )

    assert result["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert result["changed_database_row_identities"] == 10
    assert result["cleanup"]["lease_release_mode"] == "DISPOSABLE_ALIAS"
    assert result["cleanup"]["recorded_lease_preserved"] is True
    assert not alias.exists()
    assert recorded_lease.read_bytes() == recorded_before

    connection = sqlite3.connect(disposable_db)
    try:
        recorded_path = connection.execute(
            "SELECT lease_lock_path FROM printer_memory_factory_campaign_supervision "
            "WHERE supervision_id=?",
            (fixture.SUPERVISION_ID,),
        ).fetchone()[0]
    finally:
        connection.close()
    assert Path(recorded_path).resolve() == recorded_lease.resolve()

    first_sha = _sha256(disposable_db)
    replay = fixture._run_recovery(
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
        tmp_path,
        recovery_root=tmp_path / "recovery-alias-replay",
        disposable_lease_alias=alias,
    )
    assert replay["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED"
    assert replay["database_writes"] == 0
    assert _sha256(disposable_db) == first_sha
    assert recorded_lease.read_bytes() == recorded_before


def test_relocated_artifact_root_without_alias_remains_fail_closed(tmp_path: Path) -> None:
    (
        fixture,
        _source_db,
        _source_root,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    ) = _prepare_disposable_copy(tmp_path)
    before_sha = _sha256(disposable_db)

    with pytest.raises(
        recovery.OperationalCampaignRecoveryError,
        match="historical lease path mismatch",
    ):
        fixture._run_recovery(
            disposable_db,
            disposable_pre_campaign,
            disposable_root,
            contract,
            tmp_path,
            recovery_root=tmp_path / "recovery-no-alias",
        )

    assert _sha256(disposable_db) == before_sha


def test_disposable_alias_must_match_recorded_lease_before_db_mutation(
    tmp_path: Path,
) -> None:
    (
        fixture,
        _source_db,
        source_root,
        disposable_db,
        disposable_pre_campaign,
        disposable_root,
        contract,
    ) = _prepare_disposable_copy(tmp_path)
    recorded_lease = source_root / "campaign.lease.lock"
    alias = disposable_root / "campaign.lease.lock"
    recorded_before = recorded_lease.read_bytes()
    alias.write_text('{"scope":"OPERATIONAL_CAMPAIGN","owner_id":"wrong"}\n')
    before_sha = _sha256(disposable_db)

    with pytest.raises(recovery.OperationalCampaignRecoveryError):
        fixture._run_recovery(
            disposable_db,
            disposable_pre_campaign,
            disposable_root,
            contract,
            tmp_path,
            recovery_root=tmp_path / "recovery-bad-alias",
            disposable_lease_alias=alias,
        )

    assert _sha256(disposable_db) == before_sha
    assert recorded_lease.read_bytes() == recorded_before


def test_disposable_alias_cannot_equal_recorded_lease_path(tmp_path: Path) -> None:
    fixture = _fixture_module()
    source = tmp_path / "same-path-source"
    source.mkdir()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        source, include_discovery_batch=True
    )
    recorded_lease = root / "campaign.lease.lock"
    before_db_sha = _sha256(db)
    before_lease = recorded_lease.read_bytes()

    with pytest.raises(recovery.OperationalCampaignRecoveryError):
        fixture._run_recovery(
            db,
            pre_campaign,
            root,
            contract,
            tmp_path,
            recovery_root=tmp_path / "recovery-same-alias",
            disposable_lease_alias=recorded_lease,
        )

    assert _sha256(db) == before_db_sha
    assert recorded_lease.read_bytes() == before_lease
