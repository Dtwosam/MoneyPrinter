from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


recovery = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
supervision = Path("src/printer_v1/operator_cli/campaign_supervision.py")

replace_once(
    supervision,
    '''    now: datetime | None = None,\n    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,\n) -> dict[str, Any]:\n''',
    '''    now: datetime | None = None,\n    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,\n    lease_lock_path_override: str | Path | None = None,\n) -> dict[str, Any]:\n''',
    "cleanup signature",
)
replace_once(
    supervision,
    '''    released = _release_lock(Path(terminal_row["lease_lock_path"]), terminal_row)\n''',
    '''    release_path = (\n        Path(lease_lock_path_override).resolve()\n        if lease_lock_path_override is not None\n        else Path(terminal_row["lease_lock_path"]).resolve()\n    )\n    released = _release_lock(release_path, terminal_row)\n''',
    "cleanup physical lease release",
)

replace_once(
    recovery,
    '''def _historical_already_reconciled(\n    *,\n    db_path: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n) -> bool:\n''',
    '''def _historical_already_reconciled(\n    *,\n    db_path: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n    physical_lease_path: Path,\n    lease_path_override_enabled: bool,\n) -> bool:\n''',
    "already reconciled signature",
)
replace_once(
    recovery,
    '''            and supervision[3] is not None\n            and supervision[4] is not None\n            and not Path(str(supervision[5])).exists()\n            and len(slots) == 2\n''',
    '''            and supervision[3] is not None\n            and supervision[4] is not None\n            and (\n                lease_path_override_enabled\n                or Path(str(supervision[5])).resolve() == physical_lease_path\n            )\n            and not physical_lease_path.exists()\n            and len(slots) == 2\n''',
    "already reconciled physical lease",
)
replace_once(
    recovery,
    '''def _historical_preflight(\n    *,\n    db_path: Path,\n    pre_campaign_backup: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n    live_process_probe: Callable[[str], bool],\n    now: datetime,\n) -> dict[str, Any]:\n''',
    '''def _historical_preflight(\n    *,\n    db_path: Path,\n    pre_campaign_backup: Path,\n    artifact_root: Path,\n    contract: HistoricalFourTokenRecoveryContract,\n    live_process_probe: Callable[[str], bool],\n    now: datetime,\n    physical_lease_path: Path,\n    lease_path_override_enabled: bool,\n) -> dict[str, Any]:\n''',
    "preflight signature",
)
replace_once(
    recovery,
    '''        lease_path = Path(str(supervision["lease_lock_path"])).resolve()\n        if lease_path != (artifact_root / "campaign.lease.lock").resolve():\n            raise OperationalCampaignRecoveryError(\n                "historical lease path mismatch"\n            )\n        if not lease_path.is_file():\n''',
    '''        persisted_lease_path = Path(str(supervision["lease_lock_path"])).resolve()\n        expected_artifact_lease_path = (artifact_root / "campaign.lease.lock").resolve()\n        if physical_lease_path != expected_artifact_lease_path:\n            raise OperationalCampaignRecoveryError(\n                "historical lease override must equal artifact-root lease"\n            )\n        if (\n            not lease_path_override_enabled\n            and persisted_lease_path != physical_lease_path\n        ):\n            raise OperationalCampaignRecoveryError(\n                "historical lease path mismatch"\n            )\n        lease_path = physical_lease_path\n        if not lease_path.is_file():\n''',
    "preflight physical lease validation",
)
replace_once(
    recovery,
    '''def reconcile_exact_historical_four_token_execution(\n    *,\n    operator_approved: bool,\n    current_db: str | Path,\n    pre_campaign_backup: str | Path,\n    artifact_root: str | Path,\n    recovery_root: str | Path,\n    contract: HistoricalFourTokenRecoveryContract | None = None,\n    live_process_probe: Callable[[str], bool] = _default_live_process_probe,\n    now: datetime | None = None,\n) -> dict[str, Any]:\n''',
    '''def reconcile_exact_historical_four_token_execution(\n    *,\n    operator_approved: bool,\n    current_db: str | Path,\n    pre_campaign_backup: str | Path,\n    artifact_root: str | Path,\n    recovery_root: str | Path,\n    contract: HistoricalFourTokenRecoveryContract | None = None,\n    live_process_probe: Callable[[str], bool] = _default_live_process_probe,\n    now: datetime | None = None,\n    lease_lock_path_override: str | Path | None = None,\n) -> dict[str, Any]:\n''',
    "reconciliation signature",
)
replace_once(
    recovery,
    '''    artifacts = Path(artifact_root).resolve()\n    instant = now or datetime.now(timezone.utc)\n\n    if _historical_already_reconciled(\n        db_path=db_path,\n        artifact_root=artifacts,\n        contract=active,\n    ):\n''',
    '''    artifacts = Path(artifact_root).resolve()\n    instant = now or datetime.now(timezone.utc)\n    artifact_lease_path = (artifacts / "campaign.lease.lock").resolve()\n    lease_path_override_enabled = lease_lock_path_override is not None\n    physical_lease_path = (\n        Path(lease_lock_path_override).resolve()\n        if lease_path_override_enabled\n        else artifact_lease_path\n    )\n    if lease_path_override_enabled and physical_lease_path != artifact_lease_path:\n        raise OperationalCampaignRecoveryError(\n            "historical lease override must equal artifact-root lease"\n        )\n\n    if _historical_already_reconciled(\n        db_path=db_path,\n        artifact_root=artifacts,\n        contract=active,\n        physical_lease_path=physical_lease_path,\n        lease_path_override_enabled=lease_path_override_enabled,\n    ):\n''',
    "top-level physical lease selection",
)
replace_once(
    recovery,
    '''        live_process_probe=live_process_probe,\n        now=instant,\n    )\n\n    recovery_directory = Path(recovery_root).resolve()\n''',
    '''        live_process_probe=live_process_probe,\n        now=instant,\n        physical_lease_path=physical_lease_path,\n        lease_path_override_enabled=lease_path_override_enabled,\n    )\n\n    recovery_directory = Path(recovery_root).resolve()\n''',
    "preflight call",
)
replace_once(
    recovery,
    '''        first_terminal_cause=active.original_terminal_cause,\n        now=instant,\n    )\n    if (\n        int(cleanup.get("terminalized_discovery_batches", -1)) != 1\n''',
    '''        first_terminal_cause=active.original_terminal_cause,\n        now=instant,\n        lease_lock_path_override=(\n            physical_lease_path if lease_path_override_enabled else None\n        ),\n    )\n    if (\n        int(cleanup.get("terminalized_discovery_batches", -1)) != 1\n''',
    "cleanup call physical lease",
)
replace_once(
    recovery,
    '''    if not _historical_already_reconciled(\n        db_path=db_path,\n        artifact_root=artifacts,\n        contract=active,\n    ):\n''',
    '''    if not _historical_already_reconciled(\n        db_path=db_path,\n        artifact_root=artifacts,\n        contract=active,\n        physical_lease_path=physical_lease_path,\n        lease_path_override_enabled=lease_path_override_enabled,\n    ):\n''',
    "post-state already reconciled call",
)

for path in (recovery, supervision):
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
