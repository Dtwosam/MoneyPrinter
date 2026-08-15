from pathlib import Path

path = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    '''_HISTORICAL_FOUR_TOKEN_QUEUE_IDS = (58, 59)\n_HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS = tuple(range(2011, 2021))\n_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256 = {\n''',
    '''_HISTORICAL_FOUR_TOKEN_QUEUE_IDS = (58, 59)\n_HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS = tuple(range(2011, 2021))\n_HISTORICAL_DISCOVERY_BATCH_ID = (\n    "discovery-batch:20260814T172224Z-490856f405bf-campaign:"\n    "20260814T172224Z-490856f405bf-campaign-run:"\n    "20260814T172224Z-490856f405bf-cycle"\n)\n_HISTORICAL_DISCOVERY_BATCH_CANONICAL_HASH = (\n    "4071014af1e602c399482f07b1da357dad9ec48474edc67a6a787945838f0443"\n)\n_HISTORICAL_DISCOVERY_BATCH_CYCLE_SEED_HASH = (\n    "092dcebfe80c993630c94d6e5b6e29fefc84194acf64e50e6b69121ec98c7288"\n)\n_HISTORICAL_DISCOVERY_BATCH_SELECTION_SEED_IDENTITY = (\n    "b4c15ed2f729d353afa0d3e6cc1ae600b9fbfc37cbd9c35733be5a30fdffb4c7"\n)\n_HISTORICAL_DISCOVERY_BATCH_POLICY_VERSION = (\n    "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1"\n)\n_HISTORICAL_DISCOVERY_BATCH_PROVIDER_CONTRACTS_JSON = (\n    '{"direct":"V2-9.7E.11","geckoterminal":"V2-9.7D.7B.4B"}'\n)\n_HISTORICAL_DISCOVERY_BATCH_GIT_PROVENANCE = "live-operational:V2-9.7E.11"\n_HISTORICAL_DISCOVERY_WORK_TYPES = (\n    "DISCOVERY_PUMPFUN_LATEST",\n    "DISCOVERY_IDENTITY_MERGE",\n    "DISCOVERY_ORIGIN_VERIFICATION",\n    "DISCOVERY_PUMPSWAP_CONFIRMATION",\n    "DISCOVERY_FIXED_ELIGIBILITY_GATES",\n    "DISCOVERY_UNIFORM_SELECTION",\n    "DISCOVERY_TRACKING_HANDOFF_SLOT_1",\n    "DISCOVERY_TRACKING_HANDOFF_SLOT_2",\n)\n_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256 = {\n''',
    "historical discovery constants",
)

replace_once(
    '''    expected_scheduler_job_ids: tuple[int, ...] = (\n        _HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS\n    )\n    expected_artifact_sha256: Mapping[str, str] = field(\n''',
    '''    expected_scheduler_job_ids: tuple[int, ...] = (\n        _HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS\n    )\n    expected_discovery_batch_id: str = _HISTORICAL_DISCOVERY_BATCH_ID\n    expected_discovery_batch_canonical_hash: str = (\n        _HISTORICAL_DISCOVERY_BATCH_CANONICAL_HASH\n    )\n    expected_discovery_batch_cycle_seed_hash: str = (\n        _HISTORICAL_DISCOVERY_BATCH_CYCLE_SEED_HASH\n    )\n    expected_discovery_batch_selection_seed_identity: str = (\n        _HISTORICAL_DISCOVERY_BATCH_SELECTION_SEED_IDENTITY\n    )\n    expected_discovery_batch_policy_version: str = (\n        _HISTORICAL_DISCOVERY_BATCH_POLICY_VERSION\n    )\n    expected_discovery_batch_provider_contracts_json: str = (\n        _HISTORICAL_DISCOVERY_BATCH_PROVIDER_CONTRACTS_JSON\n    )\n    expected_discovery_batch_git_provenance: str = (\n        _HISTORICAL_DISCOVERY_BATCH_GIT_PROVENANCE\n    )\n    expected_discovery_work_types: tuple[str, ...] = (\n        _HISTORICAL_DISCOVERY_WORK_TYPES\n    )\n    expected_artifact_sha256: Mapping[str, str] = field(\n''',
    "contract discovery fields",
)

replace_once(
    '''        "printer_tracking_queue": "id",\n        "printer_memory_factory_runs": "run_id",\n    }\n''',
    '''        "printer_tracking_queue": "id",\n        "printer_memory_factory_runs": "run_id",\n        "printer_discovery_batches": "discovery_batch_id",\n    }\n''',
    "identity map discovery batch",
)

replace_once(
    '''def _historical_already_reconciled(\n''',
    '''def _historical_discovery_batch_rows(\n    connection: sqlite3.Connection,\n    contract: HistoricalFourTokenRecoveryContract,\n) -> list[sqlite3.Row]:\n    return connection.execute(\n        "SELECT discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,"\n        "canonical_hash,cycle_seed_hash,campaign_selection_seed_identity,"\n        "policy_version,provider_contract_versions_json,git_provenance_identity,"\n        "pump_cursor_slot,pump_cursor_signature,pump_continuity_state,"\n        "batch_state,first_terminal_cause,terminal_at "\n        "FROM printer_discovery_batches WHERE campaign_id=? AND run_id=? "\n        "ORDER BY discovery_batch_id",\n        (contract.campaign_id, contract.run_id),\n    ).fetchall()\n\n\ndef _historical_discovery_batch_identity_matches(\n    row: sqlite3.Row,\n    contract: HistoricalFourTokenRecoveryContract,\n) -> bool:\n    return tuple(row[:14]) == (\n        contract.expected_discovery_batch_id,\n        contract.campaign_id,\n        contract.configuration_id,\n        contract.run_id,\n        contract.cycle_id,\n        contract.expected_discovery_batch_canonical_hash,\n        contract.expected_discovery_batch_cycle_seed_hash,\n        contract.expected_discovery_batch_selection_seed_identity,\n        contract.expected_discovery_batch_policy_version,\n        contract.expected_discovery_batch_provider_contracts_json,\n        contract.expected_discovery_batch_git_provenance,\n        None,\n        None,\n        "UNKNOWN",\n    )\n\n\ndef _historical_expected_discovery_work_rows(\n    contract: HistoricalFourTokenRecoveryContract,\n) -> tuple[tuple[object, ...], ...]:\n    return tuple(\n        (\n            f"work:{work_type}:{contract.expected_discovery_batch_id}",\n            job_id,\n            work_type,\n            "SUCCEEDED",\n        )\n        for job_id, work_type in zip(\n            range(2011, 2019),\n            contract.expected_discovery_work_types,\n            strict=True,\n        )\n    )\n\n\ndef _historical_already_reconciled(\n''',
    "historical discovery helpers",
)

replace_once(
    '''        factory = connection.execute(\n            "SELECT run_status,stop_reason,finished_at "\n            "FROM printer_memory_factory_runs WHERE run_id=?",\n            (contract.factory_run_id,),\n        ).fetchone()\n        exact = bool(\n''',
    '''        factory = connection.execute(\n            "SELECT run_status,stop_reason,finished_at "\n            "FROM printer_memory_factory_runs WHERE run_id=?",\n            (contract.factory_run_id,),\n        ).fetchone()\n        discovery_batches = _historical_discovery_batch_rows(connection, contract)\n        discovery_batch = discovery_batches[0] if len(discovery_batches) == 1 else None\n        exact = bool(\n''',
    "replay load discovery batch",
)

replace_once(
    '''            and factory[2] is not None\n            and _historical_provenance_rows(connection, contract) == 0\n        )\n''',
    '''            and factory[2] is not None\n            and discovery_batch is not None\n            and _historical_discovery_batch_identity_matches(\n                discovery_batch, contract\n            )\n            and discovery_batch[14] == "TERMINAL_FAILED"\n            and discovery_batch[15] == contract.original_terminal_cause\n            and discovery_batch[16] is not None\n            and _historical_provenance_rows(connection, contract) == 0\n        )\n''',
    "replay require terminal batch",
)

replace_once(
    '''        nonterminal_discovery_batches = 0\n        if _historical_table_exists(connection, "printer_discovery_batches"):\n            nonterminal_discovery_batches = int(\n                connection.execute(\n                    "SELECT COUNT(*) FROM printer_discovery_batches "\n                    "WHERE campaign_id=? AND run_id=? "\n                    "AND batch_state NOT LIKE 'TERMINAL_%'",\n                    (contract.campaign_id, contract.run_id),\n                ).fetchone()[0]\n            )\n        if nonterminal_discovery_batches:\n            raise OperationalCampaignRecoveryError(\n                "historical nonterminal discovery batch exists"\n            )\n\n''',
    '''        discovery_batches = _historical_discovery_batch_rows(connection, contract)\n        if len(discovery_batches) != 1:\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch count mismatch"\n            )\n        discovery_batch = discovery_batches[0]\n        if (\n            not _historical_discovery_batch_identity_matches(discovery_batch, contract)\n            or discovery_batch[14] != "DISCOVERING"\n            or discovery_batch[15] is not None\n            or discovery_batch[16] is not None\n        ):\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch identity or pre-state drifted"\n            )\n        nonterminal_discovery_batches = int(\n            connection.execute(\n                "SELECT COUNT(*) FROM printer_discovery_batches "\n                "WHERE batch_state NOT LIKE 'TERMINAL_%'"\n            ).fetchone()[0]\n        )\n        if nonterminal_discovery_batches != 1:\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch nonterminal cardinality drifted"\n            )\n        discovery_work = connection.execute(\n            "SELECT discovery_work_id,scheduler_job_id,work_type,work_state "\n            "FROM printer_discovery_work WHERE discovery_batch_id=? "\n            "ORDER BY scheduler_job_id",\n            (contract.expected_discovery_batch_id,),\n        ).fetchall()\n        if tuple(tuple(row) for row in discovery_work) != (\n            _historical_expected_discovery_work_rows(contract)\n        ):\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch linked work drifted"\n            )\n        discovery_batch_before_row = connection.execute(\n            "SELECT * FROM printer_discovery_batches WHERE discovery_batch_id=?",\n            (contract.expected_discovery_batch_id,),\n        ).fetchone()\n        if discovery_batch_before_row is None:\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch disappeared during preflight"\n            )\n        discovery_batch_before = dict(discovery_batch_before_row)\n\n''',
    "replace zero-batch guard",
)

replace_once(
    '''        "slot_ids": slot_ids,\n        "zero_counts": zero_counts,\n    }\n''',
    '''        "slot_ids": slot_ids,\n        "zero_counts": zero_counts,\n        "discovery_batch_before": discovery_batch_before,\n    }\n''',
    "return discovery batch pre-state",
)

replace_once(
    '''    cleanup = cleanup_campaign_supervision(\n        db_path,\n        supervision_id=active.supervision_id,\n        campaign_id=active.campaign_id,\n        configuration_id=active.configuration_id,\n        run_id=active.run_id,\n        owner_id=active.owner_id,\n        terminal_status="FAILED",\n        first_terminal_cause=active.original_terminal_cause,\n        now=instant,\n    )\n    reconciliation = reconcile_campaign_terminal(\n''',
    '''    cleanup = cleanup_campaign_supervision(\n        db_path,\n        supervision_id=active.supervision_id,\n        campaign_id=active.campaign_id,\n        configuration_id=active.configuration_id,\n        run_id=active.run_id,\n        owner_id=active.owner_id,\n        terminal_status="FAILED",\n        first_terminal_cause=active.original_terminal_cause,\n        now=instant,\n    )\n    if (\n        int(cleanup.get("discovery_batch_rowcount", -1)) != 1\n        or int(cleanup.get("discovery_work_rowcount", -1)) != 0\n    ):\n        raise OperationalCampaignRecoveryError(\n            "historical discovery cleanup rowcount mismatch"\n        )\n    reconciliation = reconcile_campaign_terminal(\n''',
    "assert cleanup discovery rowcounts",
)

replace_once(
    '''            "printer_tracking_queue": {\n                str(item) for item in active.expected_queue_ids\n            },\n            "printer_memory_factory_runs": {active.factory_run_id},\n        }\n''',
    '''            "printer_tracking_queue": {\n                str(item) for item in active.expected_queue_ids\n            },\n            "printer_memory_factory_runs": {active.factory_run_id},\n            "printer_discovery_batches": {\n                active.expected_discovery_batch_id\n            },\n        }\n''',
    "allow exact discovery batch identity",
)

replace_once(
    '''        attempts = int(\n            connection.execute(\n                "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "\n                "WHERE campaign_id=? AND campaign_run_id=?",\n                (active.campaign_id, active.run_id),\n            ).fetchone()[0]\n        )\n''',
    '''        attempts = int(\n            connection.execute(\n                "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "\n                "WHERE campaign_id=? AND campaign_run_id=?",\n                (active.campaign_id, active.run_id),\n            ).fetchone()[0]\n        )\n        discovery_batch_after_row = connection.execute(\n            "SELECT * FROM printer_discovery_batches WHERE discovery_batch_id=?",\n            (active.expected_discovery_batch_id,),\n        ).fetchone()\n        if discovery_batch_after_row is None:\n            raise OperationalCampaignRecoveryError(\n                "historical discovery batch missing after reconciliation"\n            )\n        discovery_batch_after = dict(discovery_batch_after_row)\n''',
    "load discovery batch post-state",
)

replace_once(
    '''    if provenance_rows or active_jobs or windows or steps or attempts:\n        raise OperationalCampaignRecoveryError(\n            "historical reconciliation left forbidden active/provenance residue"\n        )\n''',
    '''    if provenance_rows or active_jobs or windows or steps or attempts:\n        raise OperationalCampaignRecoveryError(\n            "historical reconciliation left forbidden active/provenance residue"\n        )\n    if (\n        discovery_batch_after.get("batch_state") != "TERMINAL_FAILED"\n        or discovery_batch_after.get("first_terminal_cause")\n        != active.original_terminal_cause\n        or discovery_batch_after.get("terminal_at") is None\n    ):\n        raise OperationalCampaignRecoveryError(\n            "historical discovery batch terminal state mismatch"\n        )\n    for key, before_value in preflight["discovery_batch_before"].items():\n        if key in {"batch_state", "first_terminal_cause", "terminal_at"}:\n            continue\n        if discovery_batch_after.get(key) != before_value:\n            raise OperationalCampaignRecoveryError(\n                f"historical discovery batch immutable field changed: {key}"\n            )\n''',
    "verify discovery batch post-state",
)

path.write_text(text.rstrip() + "\n", encoding="utf-8")
