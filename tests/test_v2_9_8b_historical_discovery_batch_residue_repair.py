from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sqlite3

import pytest

from printer_v1.operator_cli import operational_campaign_recovery as recovery


BATCH_ID = (
    "discovery-batch:20260814T172224Z-490856f405bf-campaign:"
    "20260814T172224Z-490856f405bf-campaign-run:"
    "20260814T172224Z-490856f405bf-cycle"
)
CANONICAL_HASH = "4071014af1e602c399482f07b1da357dad9ec48474edc67a6a787945838f0443"
CYCLE_SEED_HASH = "092dcebfe80c993630c94d6e5b6e29fefc84194acf64e50e6b69121ec98c7288"
CAMPAIGN_SELECTION_SEED_IDENTITY = (
    "b4c15ed2f729d353afa0d3e6cc1ae600b9fbfc37cbd9c35733be5a30fdffb4c7"
)
POLICY_VERSION = "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1"
PROVIDER_CONTRACT_VERSIONS_JSON = (
    '{"direct":"V2-9.7E.11","geckoterminal":"V2-9.7D.7B.4B"}'
)
GIT_PROVENANCE_IDENTITY = "live-operational:V2-9.7E.11"
WORK_TYPES = (
    "DISCOVERY_PUMPFUN_LATEST",
    "DISCOVERY_IDENTITY_MERGE",
    "DISCOVERY_ORIGIN_VERIFICATION",
    "DISCOVERY_PUMPSWAP_CONFIRMATION",
    "DISCOVERY_FIXED_ELIGIBILITY_GATES",
    "DISCOVERY_UNIFORM_SELECTION",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
    "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
)


def _fixture_module():
    path = Path(__file__).with_name(
        "test_v2_9_8b_historical_four_token_reconciliation.py"
    )
    spec = importlib.util.spec_from_file_location("historical_fixture_batch", path)
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


def _insert_exact_batch_and_work(db: Path, fixture) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """INSERT INTO printer_discovery_batches(
                   discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                   cycle_cutoff,policy_version,provider_contract_versions_json,
                   git_provenance_identity,campaign_selection_seed_identity,
                   cycle_seed_hash,pump_cursor_slot,pump_cursor_signature,
                   pump_continuity_state,batch_state,canonical_hash,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'UNKNOWN','DISCOVERING',?,?)""",
            (
                BATCH_ID,
                fixture.CAMPAIGN_ID,
                fixture.CONFIGURATION_ID,
                fixture.RUN_ID,
                fixture.CYCLE_ID,
                fixture.START.isoformat(),
                POLICY_VERSION,
                PROVIDER_CONTRACT_VERSIONS_JSON,
                GIT_PROVENANCE_IDENTITY,
                CAMPAIGN_SELECTION_SEED_IDENTITY,
                CYCLE_SEED_HASH,
                None,
                None,
                CANONICAL_HASH,
                fixture.START.isoformat(),
            ),
        )
        for index, (job_id, work_type) in enumerate(
            zip(range(2011, 2019), WORK_TYPES, strict=True), start=1
        ):
            connection.execute(
                """INSERT INTO printer_discovery_work(
                       discovery_work_id,discovery_batch_id,campaign_id,run_id,cycle_id,
                       scheduler_job_id,work_type,work_state,deadline_at,
                       first_terminal_cause,terminal_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,'SUCCEEDED',?,?,?,?,?)""",
                (
                    f"work:{work_type}:{BATCH_ID}",
                    BATCH_ID,
                    fixture.CAMPAIGN_ID,
                    fixture.RUN_ID,
                    fixture.CYCLE_ID,
                    job_id,
                    work_type,
                    fixture.START.isoformat(),
                    f"HISTORICAL_DISCOVERY_WORK_SUCCEEDED_{index}",
                    fixture.START.isoformat(),
                    fixture.START.isoformat(),
                    fixture.START.isoformat(),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def _prepare_exact_batch_residue(tmp_path: Path):
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(tmp_path)
    _insert_exact_batch_and_work(db, fixture)
    rebound = type(contract)(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    return fixture, db, pre_campaign, root, rebound


def _batch_row(db: Path) -> dict[str, object]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM printer_discovery_batches WHERE discovery_batch_id=?",
            (BATCH_ID,),
        ).fetchone()
        assert row is not None
        return dict(row)
    finally:
        connection.close()


def test_exact_historical_batch_is_tenth_approved_reconciliation_identity(
    tmp_path: Path,
) -> None:
    fixture, db, pre_campaign, root, contract = _prepare_exact_batch_residue(tmp_path)
    before = _batch_row(db)

    result = fixture._run_recovery(db, pre_campaign, root, contract, tmp_path)

    assert result["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"
    assert result["changed_database_row_identities"] == 10
    assert result["cleanup"]["discovery_batch_rowcount"] == 1
    assert result["cleanup"]["discovery_work_rowcount"] == 0

    after = _batch_row(db)
    assert after["batch_state"] == "TERMINAL_FAILED"
    assert after["first_terminal_cause"] == fixture.CAUSE
    assert after["terminal_at"] is not None
    for field in before:
        if field not in {"batch_state", "first_terminal_cause", "terminal_at"}:
            assert after[field] == before[field]


def test_exact_historical_batch_identity_drift_fails_before_mutation(
    tmp_path: Path,
) -> None:
    fixture, db, pre_campaign, root, contract = _prepare_exact_batch_residue(tmp_path)
    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "UPDATE printer_discovery_batches SET canonical_hash=? WHERE discovery_batch_id=?",
            ("f" * 64, BATCH_ID),
        )
        connection.commit()
    finally:
        connection.close()
    rebound = type(contract)(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    before_sha = _sha256(db)

    with pytest.raises(recovery.OperationalCampaignRecoveryError, match="discovery batch"):
        fixture._run_recovery(db, pre_campaign, root, rebound, tmp_path)

    assert _sha256(db) == before_sha
    assert (root / "campaign.lease.lock").exists()


def test_already_reconciled_requires_terminal_historical_batch(tmp_path: Path) -> None:
    fixture = _fixture_module()
    db, pre_campaign, root, contract = fixture._prepare_exact_residue(tmp_path)
    first = fixture._run_recovery(db, pre_campaign, root, contract, tmp_path)
    assert first["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"

    _insert_exact_batch_and_work(db, fixture)
    rebound = type(contract)(
        expected_current_sha256=_sha256(db),
        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
        expected_artifact_sha256=contract.expected_artifact_sha256,
    )
    before_sha = _sha256(db)

    with pytest.raises(recovery.OperationalCampaignRecoveryError):
        fixture._run_recovery(
            db,
            pre_campaign,
            root,
            rebound,
            tmp_path,
            recovery_root=tmp_path / "recovery-replay-check",
        )

    assert _sha256(db) == before_sha
