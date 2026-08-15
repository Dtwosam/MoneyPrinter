from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


production = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
replace_once(
    production,
    '''        int(cleanup.get("discovery_batch_rowcount", -1)) != 1
        or int(cleanup.get("discovery_work_rowcount", -1)) != 0
''',
    '''        int(cleanup.get("terminalized_discovery_batches", -1)) != 1
        or int(cleanup.get("cancelled_discovery_work", -1)) != 0
''',
    "canonical cleanup report keys",
)

new_test = Path("tests/test_v2_9_8b_historical_discovery_batch_residue_repair.py")
replace_once(
    new_test,
    '''    assert result["cleanup"]["discovery_batch_rowcount"] == 1
    assert result["cleanup"]["discovery_work_rowcount"] == 0
''',
    '''    assert result["cleanup"]["terminalized_discovery_batches"] == 1
    assert result["cleanup"]["cancelled_discovery_work"] == 0
''',
    "repair test cleanup report keys",
)
replace_once(
    new_test,
    '''def test_already_reconciled_requires_terminal_historical_batch(tmp_path: Path) -> None:
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
''',
    '''def test_already_reconciled_requires_terminal_historical_batch(tmp_path: Path) -> None:
    fixture, db, pre_campaign, root, contract = _prepare_exact_batch_residue(tmp_path)
    first = fixture._run_recovery(db, pre_campaign, root, contract, tmp_path)
    assert first["status"] == "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED"

    connection = sqlite3.connect(db)
    try:
        connection.execute(
            "UPDATE printer_discovery_batches "
            "SET batch_state='DISCOVERING',first_terminal_cause=NULL,terminal_at=NULL "
            "WHERE discovery_batch_id=?",
            (BATCH_ID,),
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
''',
    "replay negative fixture",
)

historical_test = Path("tests/test_v2_9_8b_historical_four_token_reconciliation.py")
replace_once(
    historical_test,
    "def _prepare_exact_residue(tmp_path: Path):\n",
    "def _prepare_exact_residue(tmp_path: Path, *, include_discovery_batch: bool = False):\n",
    "historical fixture signature",
)
replace_once(
    historical_test,
    '''    connection.commit()
    connection.close()

    expected_artifacts = {
''',
    '''    if include_discovery_batch:
        batch_id = (
            "discovery-batch:20260814T172224Z-490856f405bf-campaign:"
            "20260814T172224Z-490856f405bf-campaign-run:"
            "20260814T172224Z-490856f405bf-cycle"
        )
        work_types = (
            "DISCOVERY_PUMPFUN_LATEST",
            "DISCOVERY_IDENTITY_MERGE",
            "DISCOVERY_ORIGIN_VERIFICATION",
            "DISCOVERY_PUMPSWAP_CONFIRMATION",
            "DISCOVERY_FIXED_ELIGIBILITY_GATES",
            "DISCOVERY_UNIFORM_SELECTION",
            "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
            "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
        )
        connection.execute(
            """INSERT INTO printer_discovery_batches(
                   discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                   cycle_cutoff,policy_version,provider_contract_versions_json,
                   git_provenance_identity,campaign_selection_seed_identity,
                   cycle_seed_hash,pump_cursor_slot,pump_cursor_signature,
                   pump_continuity_state,batch_state,canonical_hash,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'UNKNOWN','DISCOVERING',?,?)""",
            (
                batch_id,
                CAMPAIGN_ID,
                CONFIGURATION_ID,
                RUN_ID,
                CYCLE_ID,
                START.isoformat(),
                "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1",
                '{"direct":"V2-9.7E.11","geckoterminal":"V2-9.7D.7B.4B"}',
                "live-operational:V2-9.7E.11",
                "b4c15ed2f729d353afa0d3e6cc1ae600b9fbfc37cbd9c35733be5a30fdffb4c7",
                "092dcebfe80c993630c94d6e5b6e29fefc84194acf64e50e6b69121ec98c7288",
                None,
                None,
                "4071014af1e602c399482f07b1da357dad9ec48474edc67a6a787945838f0443",
                START.isoformat(),
            ),
        )
        for index, (job_id, work_type) in enumerate(
            zip(range(2011, 2019), work_types, strict=True), start=1
        ):
            connection.execute(
                """INSERT INTO printer_discovery_work(
                       discovery_work_id,discovery_batch_id,campaign_id,run_id,cycle_id,
                       scheduler_job_id,work_type,work_state,deadline_at,
                       first_terminal_cause,terminal_at,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,'SUCCEEDED',?,?,?,?,?)""",
                (
                    f"work:{work_type}:{batch_id}",
                    batch_id,
                    CAMPAIGN_ID,
                    RUN_ID,
                    CYCLE_ID,
                    job_id,
                    work_type,
                    START.isoformat(),
                    f"HISTORICAL_DISCOVERY_WORK_SUCCEEDED_{index}",
                    START.isoformat(),
                    START.isoformat(),
                    START.isoformat(),
                ),
            )
    connection.commit()
    connection.close()

    expected_artifacts = {
''',
    "historical fixture exact discovery batch",
)
replace_once(
    historical_test,
    '''def test_exact_historical_reconciliation_closes_only_approved_residue(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(tmp_path)
''',
    '''def test_exact_historical_reconciliation_closes_only_approved_residue(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
''',
    "historical success fixture",
)
replace_once(
    historical_test,
    '    assert result["changed_database_row_identities"] == 9\n',
    '    assert result["changed_database_row_identities"] == 10\n',
    "historical changed identity count",
)
replace_once(
    historical_test,
    '''def test_exact_historical_reconciliation_is_idempotent_without_second_mutation(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(tmp_path)
''',
    '''def test_exact_historical_reconciliation_is_idempotent_without_second_mutation(tmp_path: Path) -> None:
    db, pre_campaign, root, contract = _prepare_exact_residue(
        tmp_path, include_discovery_batch=True
    )
''',
    "historical idempotence fixture",
)

for target in (production, new_test, historical_test):
    target.write_text(target.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
