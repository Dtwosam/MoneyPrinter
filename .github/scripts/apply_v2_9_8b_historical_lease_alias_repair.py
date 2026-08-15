from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


supervision = Path("src/printer_v1/operator_cli/campaign_supervision.py")
recovery = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")

replace_once(
    supervision,
    '''def cleanup_campaign_supervision(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: datetime | None = None,
    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
''',
    '''def _cleanup_campaign_supervision_impl(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: datetime | None = None,
    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
    lease_release_path: str | Path | None = None,
) -> dict[str, Any]:
''',
    "internal cleanup signature",
)

replace_once(
    supervision,
    '''    work_cursor = None
    job_cursor = None
    window_cursor = None
    cycle_cursor = None
    try:
''',
    '''    work_cursor = None
    job_cursor = None
    window_cursor = None
    cycle_cursor = None
    recorded_lease_path: Path | None = None
    recorded_lease_bytes: bytes | None = None
    selected_release_path: Path | None = None
    try:
''',
    "lease alias state",
)

replace_once(
    supervision,
    '''        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        if row["supervision_state"] == "TERMINAL":
''',
    '''        row = _load_exact(
            connection, supervision_id=supervision_id, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id, owner_id=owner_id,
        )
        recorded_lease_path = Path(str(row["lease_lock_path"])).resolve()
        selected_release_path = recorded_lease_path
        if lease_release_path is not None:
            selected_release_path = Path(lease_release_path).resolve()
            if selected_release_path == recorded_lease_path:
                raise CampaignSupervisionError(
                    "disposable lease alias must differ from recorded lease path"
                )
            try:
                recorded_lease_bytes = recorded_lease_path.read_bytes()
                alias_lease_bytes = selected_release_path.read_bytes()
            except OSError as exc:
                raise CampaignSupervisionError(
                    "disposable lease alias evidence is unreadable"
                ) from exc
            if alias_lease_bytes != recorded_lease_bytes:
                raise CampaignSupervisionError(
                    "disposable lease alias is not byte-identical to recorded lease"
                )
            _exact_lock(_lock_payload(recorded_lease_path), row)
            _exact_lock(_lock_payload(selected_release_path), row)
        if row["supervision_state"] == "TERMINAL":
''',
    "pre-mutation alias validation",
)

replace_once(
    supervision,
    '''    released = _release_lock(Path(terminal_row["lease_lock_path"]), terminal_row)
    if not released:
        raise CampaignSupervisionError("operational campaign lease release failed")
    _finish_released_lease(db_path, terminal_row, released_at=timestamp)
''',
    '''    release_target = selected_release_path or Path(
        str(terminal_row["lease_lock_path"])
    ).resolve()
    released = _release_lock(release_target, terminal_row)
    if not released:
        raise CampaignSupervisionError("operational campaign lease release failed")
    lease_release_mode = "RECORDED"
    recorded_lease_preserved = False
    if lease_release_path is not None:
        if recorded_lease_path is None or recorded_lease_bytes is None:
            raise CampaignSupervisionError(
                "disposable lease alias preservation evidence is incomplete"
            )
        try:
            current_recorded_bytes = recorded_lease_path.read_bytes()
        except OSError as exc:
            raise CampaignSupervisionError(
                "recorded lease was not preserved during disposable cleanup"
            ) from exc
        if current_recorded_bytes != recorded_lease_bytes:
            raise CampaignSupervisionError(
                "recorded lease changed during disposable cleanup"
            )
        _exact_lock(_lock_payload(recorded_lease_path), terminal_row)
        lease_release_mode = "DISPOSABLE_ALIAS"
        recorded_lease_preserved = True
    _finish_released_lease(db_path, terminal_row, released_at=timestamp)
''',
    "alias release finalization",
)

replace_once(
    supervision,
    '''        "cleanup_completed": True,
        "lease_released": True,
        "new_child_work_allowed": False,
''',
    '''        "cleanup_completed": True,
        "lease_released": True,
        "lease_release_mode": lease_release_mode,
        "recorded_lease_preserved": recorded_lease_preserved,
        "new_child_work_allowed": False,
''',
    "cleanup result lease evidence",
)

text = supervision.read_text(encoding="utf-8")
if not text.endswith("\n"):
    text += "\n"
text += '''

def cleanup_campaign_supervision(
    db_path: str | Path,
    *,
    supervision_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    owner_id: str,
    terminal_status: str,
    first_terminal_cause: str,
    now: datetime | None = None,
    scheduler_operation_observer: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Canonical public cleanup; always releases the SQLite-recorded lease."""
    return _cleanup_campaign_supervision_impl(
        db_path,
        supervision_id=supervision_id,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        owner_id=owner_id,
        terminal_status=terminal_status,
        first_terminal_cause=first_terminal_cause,
        now=now,
        scheduler_operation_observer=scheduler_operation_observer,
    )
'''
supervision.write_text(text, encoding="utf-8")

replace_once(
    recovery,
    '''from printer_v1.operator_cli.campaign_supervision import (
    cleanup_campaign_supervision,
)
''',
    '''from printer_v1.operator_cli.campaign_supervision import (
    _cleanup_campaign_supervision_impl,
    cleanup_campaign_supervision,
)
''',
    "historical internal cleanup import",
)

replace_once(
    recovery,
    '''def _historical_already_reconciled(
''',
    '''def _historical_lease_bytes(
    path: Path,
    *,
    contract: HistoricalFourTokenRecoveryContract,
    expected_expiry: str,
) -> bytes:
    if not path.is_file():
        raise OperationalCampaignRecoveryError("historical lease file is missing")
    try:
        raw = path.read_bytes()
        lease = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OperationalCampaignRecoveryError(
            "historical lease payload is unreadable"
        ) from exc
    if not isinstance(lease, dict):
        raise OperationalCampaignRecoveryError(
            "historical lease payload is unreadable"
        )
    expected_lease = {
        "scope": "OPERATIONAL_CAMPAIGN",
        "supervision_id": contract.supervision_id,
        "campaign_id": contract.campaign_id,
        "configuration_id": contract.configuration_id,
        "run_id": contract.run_id,
        "owner_id": contract.owner_id,
    }
    if any(lease.get(key) != value for key, value in expected_lease.items()):
        raise OperationalCampaignRecoveryError("historical lease ownership mismatch")
    if str(lease.get("lease_expires_at")) != str(expected_expiry):
        raise OperationalCampaignRecoveryError("historical lease expiry mismatch")
    return raw


def _historical_already_reconciled(
''',
    "historical lease validator",
)

replace_once(
    recovery,
    '''def _historical_already_reconciled(
    *,
    db_path: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
) -> bool:
''',
    '''def _historical_already_reconciled(
    *,
    db_path: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
    disposable_lease_alias: Path | None = None,
) -> bool:
''',
    "already reconciled alias signature",
)

replace_once(
    recovery,
    '''            "cleanup_completed_at,lease_released_at,lease_lock_path "
''',
    '''            "cleanup_completed_at,lease_released_at,lease_lock_path,lease_expires_at "
''',
    "already reconciled lease expiry query",
)

replace_once(
    recovery,
    '''        discovery_batches = _historical_discovery_batch_rows(connection, contract)
        discovery_batch = discovery_batches[0] if len(discovery_batches) == 1 else None
        exact = bool(
''',
    '''        discovery_batches = _historical_discovery_batch_rows(connection, contract)
        discovery_batch = discovery_batches[0] if len(discovery_batches) == 1 else None
        lease_terminal_ok = False
        if supervision is not None:
            recorded_lease_path = Path(str(supervision[5])).resolve()
            if disposable_lease_alias is None:
                lease_terminal_ok = not recorded_lease_path.exists()
            else:
                alias = disposable_lease_alias.resolve()
                lease_terminal_ok = (
                    alias != recorded_lease_path
                    and not alias.exists()
                    and recorded_lease_path.is_file()
                )
                if lease_terminal_ok:
                    try:
                        _historical_lease_bytes(
                            recorded_lease_path,
                            contract=contract,
                            expected_expiry=str(supervision[6]),
                        )
                    except OperationalCampaignRecoveryError:
                        lease_terminal_ok = False
        exact = bool(
''',
    "already reconciled lease mode",
)

replace_once(
    recovery,
    '''            and supervision[4] is not None
            and not Path(str(supervision[5])).exists()
            and len(slots) == 2
''',
    '''            and supervision[4] is not None
            and lease_terminal_ok
            and len(slots) == 2
''',
    "already reconciled lease predicate",
)

replace_once(
    recovery,
    '''def _historical_preflight(
    *,
    db_path: Path,
    pre_campaign_backup: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
    live_process_probe: Callable[[str], bool],
    now: datetime,
) -> dict[str, Any]:
''',
    '''def _historical_preflight(
    *,
    db_path: Path,
    pre_campaign_backup: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
    live_process_probe: Callable[[str], bool],
    now: datetime,
    disposable_lease_alias: Path | None = None,
) -> dict[str, Any]:
''',
    "preflight alias signature",
)

replace_once(
    recovery,
    '''        lease_path = Path(str(supervision["lease_lock_path"])).resolve()
        if lease_path != (artifact_root / "campaign.lease.lock").resolve():
            raise OperationalCampaignRecoveryError(
                "historical lease path mismatch"
            )
        if not lease_path.is_file():
            raise OperationalCampaignRecoveryError(
                "historical lease file is missing"
            )
        try:
            lease = json.loads(lease_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OperationalCampaignRecoveryError(
                "historical lease payload is unreadable"
            ) from exc
        expected_lease = {
            "scope": "OPERATIONAL_CAMPAIGN",
            "supervision_id": contract.supervision_id,
            "campaign_id": contract.campaign_id,
            "configuration_id": contract.configuration_id,
            "run_id": contract.run_id,
            "owner_id": contract.owner_id,
        }
        if any(
            lease.get(key) != value for key, value in expected_lease.items()
        ):
            raise OperationalCampaignRecoveryError(
                "historical lease ownership mismatch"
            )
        if str(lease.get("lease_expires_at")) != str(
            supervision["lease_expires_at"]
        ):
            raise OperationalCampaignRecoveryError(
                "historical lease expiry mismatch"
            )
''',
    '''        lease_path = Path(str(supervision["lease_lock_path"])).resolve()
        expected_artifact_lease = (artifact_root / "campaign.lease.lock").resolve()
        recorded_lease_bytes = _historical_lease_bytes(
            lease_path,
            contract=contract,
            expected_expiry=str(supervision["lease_expires_at"]),
        )
        if disposable_lease_alias is None:
            if lease_path != expected_artifact_lease:
                raise OperationalCampaignRecoveryError(
                    "historical lease path mismatch"
                )
            lease_release_path = lease_path
        else:
            alias = disposable_lease_alias.resolve()
            if alias != expected_artifact_lease:
                raise OperationalCampaignRecoveryError(
                    "historical disposable lease alias path mismatch"
                )
            if alias == lease_path:
                raise OperationalCampaignRecoveryError(
                    "historical disposable lease alias must differ from recorded lease"
                )
            alias_bytes = _historical_lease_bytes(
                alias,
                contract=contract,
                expected_expiry=str(supervision["lease_expires_at"]),
            )
            if alias_bytes != recorded_lease_bytes:
                raise OperationalCampaignRecoveryError(
                    "historical disposable lease alias is not byte-identical"
                )
            lease_release_path = alias
''',
    "historical preflight lease alias",
)

replace_once(
    recovery,
    '''        "zero_counts": zero_counts,
        "discovery_batch_before": discovery_batch_before,
    }
''',
    '''        "zero_counts": zero_counts,
        "discovery_batch_before": discovery_batch_before,
        "recorded_lease_path": str(lease_path),
        "recorded_lease_sha256": hashlib.sha256(recorded_lease_bytes).hexdigest(),
        "lease_release_path": str(lease_release_path),
    }
''',
    "preflight lease evidence return",
)

replace_once(
    recovery,
    '''    contract: HistoricalFourTokenRecoveryContract | None = None,
    live_process_probe: Callable[[str], bool] = _default_live_process_probe,
    now: datetime | None = None,
) -> dict[str, Any]:
''',
    '''    contract: HistoricalFourTokenRecoveryContract | None = None,
    live_process_probe: Callable[[str], bool] = _default_live_process_probe,
    now: datetime | None = None,
    disposable_lease_alias: str | Path | None = None,
) -> dict[str, Any]:
''',
    "reconcile alias signature",
)

replace_once(
    recovery,
    '''    artifacts = Path(artifact_root).resolve()
    instant = now or datetime.now(timezone.utc)

    if _historical_already_reconciled(
''',
    '''    artifacts = Path(artifact_root).resolve()
    lease_alias = (
        None if disposable_lease_alias is None
        else Path(disposable_lease_alias).resolve()
    )
    instant = now or datetime.now(timezone.utc)

    if _historical_already_reconciled(
''',
    "resolve disposable alias",
)

replace_once(
    recovery,
    '''        artifact_root=artifacts,
        contract=active,
    ):
''',
    '''        artifact_root=artifacts,
        contract=active,
        disposable_lease_alias=lease_alias,
    ):
''',
    "initial replay alias",
)

replace_once(
    recovery,
    '''        live_process_probe=live_process_probe,
        now=instant,
    )
''',
    '''        live_process_probe=live_process_probe,
        now=instant,
        disposable_lease_alias=lease_alias,
    )
''',
    "preflight alias argument",
)

replace_once(
    recovery,
    '''    cleanup = cleanup_campaign_supervision(
        db_path,
        supervision_id=active.supervision_id,
        campaign_id=active.campaign_id,
        configuration_id=active.configuration_id,
        run_id=active.run_id,
        owner_id=active.owner_id,
        terminal_status="FAILED",
        first_terminal_cause=active.original_terminal_cause,
        now=instant,
    )
''',
    '''    cleanup_kwargs = {
        "supervision_id": active.supervision_id,
        "campaign_id": active.campaign_id,
        "configuration_id": active.configuration_id,
        "run_id": active.run_id,
        "owner_id": active.owner_id,
        "terminal_status": "FAILED",
        "first_terminal_cause": active.original_terminal_cause,
        "now": instant,
    }
    if lease_alias is None:
        cleanup = cleanup_campaign_supervision(db_path, **cleanup_kwargs)
    else:
        cleanup = _cleanup_campaign_supervision_impl(
            db_path,
            **cleanup_kwargs,
            lease_release_path=lease_alias,
        )
''',
    "historical alias cleanup dispatch",
)

replace_once(
    recovery,
    '''    if (
        int(cleanup.get("terminalized_discovery_batches", -1)) != 1
        or int(cleanup.get("cancelled_discovery_work", -1)) != 0
    ):
''',
    '''    expected_lease_mode = "RECORDED" if lease_alias is None else "DISPOSABLE_ALIAS"
    if cleanup.get("lease_release_mode") != expected_lease_mode:
        raise OperationalCampaignRecoveryError(
            "historical lease cleanup mode mismatch"
        )
    if lease_alias is not None and cleanup.get("recorded_lease_preserved") is not True:
        raise OperationalCampaignRecoveryError(
            "historical recorded lease was not preserved"
        )
    if (
        int(cleanup.get("terminalized_discovery_batches", -1)) != 1
        or int(cleanup.get("cancelled_discovery_work", -1)) != 0
    ):
''',
    "historical cleanup lease evidence",
)

# Replace the final replay call only; the first was already changed above.
text = recovery.read_text(encoding="utf-8")
old = '''    if not _historical_already_reconciled(
        db_path=db_path,
        artifact_root=artifacts,
        contract=active,
    ):
'''
new = '''    if lease_alias is not None:
        recorded_lease_path = Path(preflight["recorded_lease_path"])
        if (
            not recorded_lease_path.is_file()
            or _sha256(recorded_lease_path) != preflight["recorded_lease_sha256"]
        ):
            raise OperationalCampaignRecoveryError(
                "historical recorded lease changed during disposable reconciliation"
            )
    if not _historical_already_reconciled(
        db_path=db_path,
        artifact_root=artifacts,
        contract=active,
        disposable_lease_alias=lease_alias,
    ):
'''
if text.count(old) != 1:
    raise SystemExit(f"final replay alias: expected one match, found {text.count(old)}")
recovery.write_text(text.replace(old, new, 1), encoding="utf-8")

for path in (supervision, recovery):
    path.write_text(path.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
