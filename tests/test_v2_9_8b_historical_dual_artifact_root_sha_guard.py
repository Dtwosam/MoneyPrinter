from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


def _load(name: str, filename: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
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


def test_wrong_application_artifact_sha_rejects_before_mutation(tmp_path: Path) -> None:
    fixture = _load(
        "historical_four_token_fixture_sha",
        "test_v2_9_8b_historical_four_token_reconciliation.py",
    )
    dual = _load(
        "historical_dual_root_fixture_sha",
        "test_v2_9_8b_historical_dual_artifact_root_repair.py",
    )
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
    application_root = dual._split_application_root(root, tmp_path)
    marker = application_root / "application-marker.json"
    marker.write_bytes(marker.read_bytes() + b"tampered")
    before_db = _sha256(db)
    before_lease = _sha256(root / "campaign.lease.lock")
    recovery_root = tmp_path / "recovery"

    with pytest.raises(recovery.OperationalCampaignRecoveryError, match="SHA mismatch"):
        recovery.reconcile_exact_historical_four_token_execution(
            operator_approved=True,
            current_db=db,
            pre_campaign_backup=pre_campaign,
            artifact_root=root,
            application_artifact_root=application_root,
            recovery_root=recovery_root,
            contract=contract,
            live_process_probe=lambda _execution: False,
            now=fixture.NOW,
        )

    assert _sha256(db) == before_db
    assert _sha256(root / "campaign.lease.lock") == before_lease
    assert not recovery_root.exists()
