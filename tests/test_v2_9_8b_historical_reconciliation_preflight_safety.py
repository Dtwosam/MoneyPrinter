from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


def _fixture_module():
    path = Path(__file__).with_name(
        "test_v2_9_8b_historical_four_token_reconciliation.py"
    )
    spec = importlib.util.spec_from_file_location("historical_fixture", path)
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


def test_nonterminal_discovery_batch_is_rejected_before_any_mutation(
    tmp_path: Path,
) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            """INSERT INTO printer_discovery_batches(
                   discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                   cycle_cutoff,policy_version,provider_contract_versions_json,
                   git_provenance_identity,campaign_selection_seed_identity,
                   cycle_seed_hash,pump_cursor_slot,pump_cursor_signature,
                   pump_continuity_state,batch_state,canonical_hash,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'NONE','PLANNED',?,?)""",
            (
                "historical-nonterminal-batch",
                fixture.CAMPAIGN_ID,
                fixture.CONFIGURATION_ID,
                fixture.RUN_ID,
                fixture.CYCLE_ID,
                fixture.START.isoformat(),
                "historical-safety-fixture",
                "{}",
                "git:historical",
                "seed:historical",
                "c" * 64,
                None,
                None,
                "d" * 64,
                fixture.START.isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    drifted = type(contract)(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    before_sha = _sha256(db)
    error_type = recovery.OperationalCampaignRecoveryError
    with pytest.raises(error_type, match="discovery batch"):
        fixture._run_recovery(
            db,
            pre_campaign,
            root,
            drifted,
            tmp_path,
        )
    assert _sha256(db) == before_sha
    assert (root / "campaign.lease.lock").exists()
