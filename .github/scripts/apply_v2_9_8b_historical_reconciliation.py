from pathlib import Path

TARGET = Path("src/printer_v1/operator_cli/operational_campaign_recovery.py")
MARKER = "# V2-9.8B exact historical four-token reconciliation"

IMPLEMENTATION = r'''


# ---------------------------------------------------------------------------
# V2-9.8B exact historical four-token reconciliation
# ---------------------------------------------------------------------------

_HISTORICAL_FOUR_TOKEN_EXECUTION_ID = "20260814T172224Z-490856f405bf"
_HISTORICAL_FOUR_TOKEN_FACTORY_RUN_ID = "ed0fa279-38e6-401b-8b34-0a9531a9c720"
_HISTORICAL_FOUR_TOKEN_DB_SHA256 = (
    "5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc"
)
_HISTORICAL_FOUR_TOKEN_PRE_CAMPAIGN_SHA256 = (
    "a9c82e97bc546fd0a44b2e1f10b1713df2bce5d8d6171c67377d80474617a235"
)
_HISTORICAL_FOUR_TOKEN_CAUSE = (
    "FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction"
)
_HISTORICAL_FOUR_TOKEN_MINTS = (
    "yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump",
    "CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump",
)
_HISTORICAL_FOUR_TOKEN_QUEUE_IDS = (58, 59)
_HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS = tuple(range(2011, 2021))
_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256 = {
    "application-marker.json": "1e0038b4515156244dad586d6d90692857dc53ab12f7df67d4b03a981ea4665c",
    "git-provenance-manifest.json": "ee76043850f7569fe21d05f2770e51ac64e5de36f39362c962f09f7b7ae73f18",
    "wrapper-terminal.json": "36312b244b335fa951e3ed9aa6799ce2e3cb15a8a2c46a6e127409e40108ccc3",
    "child-terminal.json": "5b96652d5473120d28f1e1730c1843715fa27888af85640a774a00b0d2acd0fd",
    "child-stderr.txt": "eab9a9236a3735658915db3a8e5bff934ae65a46d8b81caf61f6176fc4b7f504",
    "terminal-summary.json": "21d0e6fe4046e69b15a3239caea26703c280a8303302dc85c3bd63ec3a41d7c1",
}


@dataclass(frozen=True)
class HistoricalFourTokenRecoveryContract:
    """Exact, non-generic contract for the consumed 2026-08-14 execution."""

    execution_id: str = _HISTORICAL_FOUR_TOKEN_EXECUTION_ID
    factory_run_id: str = _HISTORICAL_FOUR_TOKEN_FACTORY_RUN_ID
    expected_current_sha256: str = _HISTORICAL_FOUR_TOKEN_DB_SHA256
    pre_campaign_backup_sha256: str = _HISTORICAL_FOUR_TOKEN_PRE_CAMPAIGN_SHA256
    original_terminal_cause: str = _HISTORICAL_FOUR_TOKEN_CAUSE
    expected_slot_mints: tuple[str, str] = _HISTORICAL_FOUR_TOKEN_MINTS
    expected_queue_ids: tuple[int, int] = _HISTORICAL_FOUR_TOKEN_QUEUE_IDS
    expected_scheduler_job_ids: tuple[int, ...] = (
        _HISTORICAL_FOUR_TOKEN_SCHEDULER_JOB_IDS
    )
    expected_artifact_sha256: Mapping[str, str] = field(
        default_factory=lambda: dict(_HISTORICAL_FOUR_TOKEN_ARTIFACT_SHA256)
    )

    @property
    def campaign_id(self) -> str:
        return f"{self.execution_id}-campaign"

    @property
    def configuration_id(self) -> str:
        return f"{self.execution_id}-configuration"

    @property
    def run_id(self) -> str:
        return f"{self.execution_id}-campaign-run"

    @property
    def cycle_id(self) -> str:
        return f"{self.execution_id}-cycle"

    @property
    def supervision_id(self) -> str:
        return f"{self.execution_id}-supervision"

    @property
    def owner_id(self) -> str:
        return f"{self.execution_id}-owner"


def _historical_table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _historical_reject_sidecars(db_path: Path) -> None:
    present = [
        str(Path(f"{db_path}{suffix}"))
        for suffix in ("-wal", "-shm", "-journal")
        if Path(f"{db_path}{suffix}").exists()
    ]
    if present:
        raise OperationalCampaignRecoveryError(
            f"historical reconciliation requires quiescent SQLite state: {present}"
        )


def _historical_validate_artifacts(
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for name, expected in dict(contract.expected_artifact_sha256).items():
        path = artifact_root / name
        if not path.is_file():
            raise OperationalCampaignRecoveryError(
                f"historical artifact missing: {name}"
            )
        digest = _sha256(path)
        if digest != str(expected):
            raise OperationalCampaignRecoveryError(
                f"historical artifact SHA mismatch: {name}"
            )
        observed[name] = digest
    try:
        child = json.loads(
            (artifact_root / "child-stderr.txt").read_text(encoding="utf-8")
        )
        summary = json.loads(
            (artifact_root / "terminal-summary.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationalCampaignRecoveryError(
            "historical terminal artifacts are unreadable"
        ) from exc
    if (
        not isinstance(child, dict)
        or child.get("error_type") != "FourTokenFactoryAdapterError"
        or child.get("error_message")
        != "cycle terminal reconciliation requires a fresh transaction"
    ):
        raise OperationalCampaignRecoveryError(
            "historical child terminal cause mismatch"
        )
    closure_errors = summary.get("closure_errors") if isinstance(summary, dict) else None
    if (
        not isinstance(summary, dict)
        or summary.get("original_exception_type") != "FourTokenFactoryAdapterError"
        or not isinstance(closure_errors, list)
        or "cleanup:OperationalError:database is locked" not in closure_errors
        or "reconciliation:OperationalError:database is locked" not in closure_errors
    ):
        raise OperationalCampaignRecoveryError(
            "historical terminal-summary evidence mismatch"
        )
    return observed


def _historical_table_hashes(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        table: _canonical_rows_hash(_rows(connection, table))
        for table in _table_names(connection)
    }


def _historical_identity_maps(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, dict[str, Any]]]:
    identities = {
        "printer_memory_factory_campaigns": "campaign_id",
        "printer_memory_factory_campaign_runs": "run_id",
        "printer_memory_factory_campaign_cycles": "cycle_id",
        "printer_memory_factory_campaign_token_slots": "token_slot_id",
        "printer_memory_factory_campaign_supervision": "supervision_id",
        "printer_tracking_queue": "id",
        "printer_memory_factory_runs": "run_id",
    }
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for table, identity_column in identities.items():
        result[table] = {
            str(row[identity_column]): dict(row)
            for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()
        }
    return result


def _historical_changed_identities(
    before: Mapping[str, Mapping[str, Mapping[str, Any]]],
    after: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, set[str]]:
    changed: dict[str, set[str]] = {}
    for table in before:
        before_rows = before[table]
        after_rows = after[table]
        keys = set(before_rows).union(after_rows)
        changed[table] = {
            key for key in keys if before_rows.get(key) != after_rows.get(key)
        }
    return changed


def _historical_provenance_rows(
    connection: sqlite3.Connection,
    contract: HistoricalFourTokenRecoveryContract,
) -> int:
    if not _historical_table_exists(
        connection, "printer_four_token_pre_lifecycle_terminal_provenance"
    ):
        return 0
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_four_token_pre_lifecycle_terminal_provenance "
            "WHERE campaign_id=? AND campaign_run_id=?",
            (contract.campaign_id, contract.run_id),
        ).fetchone()[0]
    )


def _historical_already_reconciled(
    *,
    db_path: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
) -> bool:
    if not db_path.is_file():
        return False
    connection = _read_only(db_path)
    try:
        campaign = connection.execute(
            "SELECT campaign_state,first_terminal_cause "
            "FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (contract.campaign_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT run_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_runs WHERE run_id=?",
            (contract.run_id,),
        ).fetchone()
        cycle = connection.execute(
            "SELECT cycle_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (contract.cycle_id,),
        ).fetchone()
        supervision = connection.execute(
            "SELECT supervision_state,terminal_status,first_terminal_cause,"
            "cleanup_completed_at,lease_released_at,lease_lock_path "
            "FROM printer_memory_factory_campaign_supervision WHERE supervision_id=?",
            (contract.supervision_id,),
        ).fetchone()
        slots = connection.execute(
            "SELECT token_state,first_terminal_cause,tracking_queue_id "
            "FROM printer_memory_factory_campaign_token_slots WHERE cycle_id=? "
            "ORDER BY slot_ordinal",
            (contract.cycle_id,),
        ).fetchall()
        queues = connection.execute(
            "SELECT id,queue_status,tracking_action,priority_reason "
            "FROM printer_tracking_queue WHERE id IN (?,?) ORDER BY id",
            tuple(contract.expected_queue_ids),
        ).fetchall()
        factory = connection.execute(
            "SELECT run_status,stop_reason,finished_at "
            "FROM printer_memory_factory_runs WHERE run_id=?",
            (contract.factory_run_id,),
        ).fetchone()
        exact = bool(
            campaign is not None
            and tuple(campaign) == (
                "TERMINAL_FAILED", contract.original_terminal_cause
            )
            and run is not None
            and tuple(run) == ("TERMINAL_FAILED", contract.original_terminal_cause)
            and cycle is not None
            and tuple(cycle) == (
                "TERMINAL_FAILED", contract.original_terminal_cause
            )
            and supervision is not None
            and supervision[0] == "TERMINAL"
            and supervision[1] == "FAILED"
            and supervision[2] == contract.original_terminal_cause
            and supervision[3] is not None
            and supervision[4] is not None
            and not Path(str(supervision[5])).exists()
            and len(slots) == 2
            and all(
                row[0] == "MANUAL_REVIEW"
                and row[1] == contract.original_terminal_cause
                and int(row[2]) == int(contract.expected_queue_ids[index])
                for index, row in enumerate(slots)
            )
            and len(queues) == 2
            and all(
                int(row[0]) == int(contract.expected_queue_ids[index])
                and row[1] == "SKIPPED"
                and row[2] == "MANUAL_REVIEW"
                and row[3]
                == f"campaign_terminal:{contract.original_terminal_cause}"
                for index, row in enumerate(queues)
            )
            and factory is not None
            and factory[0] == "SAFE_STOPPED"
            and factory[1] == contract.original_terminal_cause
            and factory[2] is not None
            and _historical_provenance_rows(connection, contract) == 0
        )
    finally:
        connection.close()
    if exact:
        _historical_validate_artifacts(artifact_root, contract)
    return exact


def _historical_preflight(
    *,
    db_path: Path,
    pre_campaign_backup: Path,
    artifact_root: Path,
    contract: HistoricalFourTokenRecoveryContract,
    live_process_probe: Callable[[str], bool],
    now: datetime,
) -> dict[str, Any]:
    _historical_reject_sidecars(db_path)
    if _sha256(db_path) != contract.expected_current_sha256:
        raise OperationalCampaignRecoveryError(
            "historical authoritative DB SHA mismatch"
        )
    if _sha256(pre_campaign_backup) != contract.pre_campaign_backup_sha256:
        raise OperationalCampaignRecoveryError(
            "historical pre-campaign backup SHA mismatch"
        )
    if live_process_probe(contract.execution_id):
        raise OperationalCampaignRecoveryError("live Printer owner process exists")
    artifacts = _historical_validate_artifacts(artifact_root, contract)

    connection = _read_only(db_path)
    try:
        migrations = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        ]
        if (
            len(migrations) != 55
            or migrations[-1:]
            != ["055_pre_admission_discovery_attempt_ownership.sql"]
        ):
            raise OperationalCampaignRecoveryError(
                "historical migration-055 ledger identity mismatch"
            )
        if _historical_table_exists(
            connection, "printer_four_token_pre_lifecycle_terminal_provenance"
        ):
            raise OperationalCampaignRecoveryError(
                "historical execution must not have migration-056 provenance schema"
            )
        if tuple(
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        ) != ("ok",):
            raise OperationalCampaignRecoveryError(
                "historical database integrity failed"
            )
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise OperationalCampaignRecoveryError(
                "historical foreign-key check failed"
            )

        campaign = connection.execute(
            "SELECT campaign_state,first_terminal_cause,terminal_at "
            "FROM printer_memory_factory_campaigns WHERE campaign_id=?",
            (contract.campaign_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT campaign_id,run_ordinal,run_state,authoritative_run_id,"
            "first_terminal_cause,terminal_at "
            "FROM printer_memory_factory_campaign_runs WHERE run_id=?",
            (contract.run_id,),
        ).fetchone()
        cycle = connection.execute(
            "SELECT campaign_id,run_id,cycle_ordinal,cycle_state,first_terminal_cause "
            "FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
            (contract.cycle_id,),
        ).fetchone()
        supervision = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_supervision "
            "WHERE supervision_id=? AND campaign_id=? AND configuration_id=? "
            "AND run_id=? AND owner_id=?",
            (
                contract.supervision_id,
                contract.campaign_id,
                contract.configuration_id,
                contract.run_id,
                contract.owner_id,
            ),
        ).fetchone()
        factory = connection.execute(
            "SELECT run_status,stop_reason,finished_at,selected_token_count,config_json "
            "FROM printer_memory_factory_runs WHERE run_id=?",
            (contract.factory_run_id,),
        ).fetchone()
        if (
            campaign is None
            or tuple(campaign) != ("RUNNING", None, None)
            or run is None
            or tuple(run[:4])
            != (contract.campaign_id, 1, "RUNNING", contract.factory_run_id)
            or run[4] is not None
            or run[5] is not None
            or cycle is None
            or tuple(cycle[:4])
            != (contract.campaign_id, contract.run_id, 1, "PLANNED")
            or cycle[4] is not None
            or supervision is None
            or supervision["supervision_state"] != "ACTIVE"
            or supervision["terminal_status"] is not None
            or supervision["first_terminal_cause"] is not None
            or supervision["cleanup_completed_at"] is not None
            or supervision["lease_released_at"] is not None
            or supervision["cancellation_requested_at"] is not None
            or supervision["cancellation_reason"] is not None
            or factory is None
            or factory[0] != "RUNNING"
            or factory[1] is not None
            or factory[2] is not None
            or int(factory[3] or 0) != 0
        ):
            raise OperationalCampaignRecoveryError(
                "historical ownership graph state drifted"
            )
        try:
            factory_config = json.loads(str(factory[4]))
        except json.JSONDecodeError as exc:
            raise OperationalCampaignRecoveryError(
                "historical factory configuration is malformed"
            ) from exc
        if any(
            str(factory_config.get(key) or "") != expected
            for key, expected in (
                ("campaign_id", contract.campaign_id),
                ("campaign_run_id", contract.run_id),
                ("cycle_id", contract.cycle_id),
            )
        ):
            raise OperationalCampaignRecoveryError(
                "historical factory configuration identity mismatch"
            )

        slots = connection.execute(
            "SELECT token_slot_id,slot_ordinal,mint_identity,token_state,tracking_queue_id "
            "FROM printer_memory_factory_campaign_token_slots "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY slot_ordinal",
            (contract.campaign_id, contract.run_id, contract.cycle_id),
        ).fetchall()
        if len(slots) != 2:
            raise OperationalCampaignRecoveryError(
                "historical slot count mismatch"
            )
        for index, row in enumerate(slots):
            if (
                int(row[1]) != index + 1
                or str(row[2]) != contract.expected_slot_mints[index]
                or str(row[3]) != "SELECTED"
                or int(row[4]) != int(contract.expected_queue_ids[index])
            ):
                raise OperationalCampaignRecoveryError(
                    "historical slot order or queue linkage mismatch"
                )
        queues = connection.execute(
            "SELECT id,tracking_lane,tracking_action,priority_reason,queue_status,"
            "source_status,data_quality_label,last_checked_at "
            "FROM printer_tracking_queue WHERE id IN (?,?) ORDER BY id",
            tuple(contract.expected_queue_ids),
        ).fetchall()
        if len(queues) != 2:
            raise OperationalCampaignRecoveryError(
                "historical tracking queue missing"
            )
        for index, row in enumerate(queues):
            if tuple(row) != (
                int(contract.expected_queue_ids[index]),
                "TRACK_NORMAL",
                "PROMOTE_TO_TRACK_NORMAL",
                "combined_discovery_handoff",
                "QUEUED",
                "COMPLETE",
                "CLEAN_DATA",
                None,
            ):
                raise OperationalCampaignRecoveryError(
                    "historical tracking queue state drifted"
                )

        zero_counts = {
            "windows": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
                    "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
                    (contract.campaign_id, contract.run_id, contract.cycle_id),
                ).fetchone()[0]
            ),
            "steps": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id=?",
                    (contract.factory_run_id,),
                ).fetchone()[0]
            ),
            "attempts": int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
                    "WHERE campaign_id=? AND campaign_run_id=? "
                    "AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=2",
                    (contract.campaign_id, contract.run_id, contract.factory_run_id),
                ).fetchone()[0]
            ),
        }
        if any(zero_counts.values()):
            raise OperationalCampaignRecoveryError(
                "historical zero-window/step/attempt shape drifted"
            )

        work = connection.execute(
            "SELECT scheduler_job_id,work_state,ownership_contract_version,work_scope "
            "FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE campaign_id=? AND run_id=? AND cycle_id=? ORDER BY scheduler_job_id",
            (contract.campaign_id, contract.run_id, contract.cycle_id),
        ).fetchall()
        if len(work) != 10 or tuple(int(row[0]) for row in work) != tuple(
            contract.expected_scheduler_job_ids
        ):
            raise OperationalCampaignRecoveryError(
                "historical Scheduler-work ownership mismatch"
            )
        for row in work:
            job_id = int(row[0])
            expected_state = "SUCCEEDED" if job_id <= 2018 else "CANCELLED"
            expected_scope = (
                "DISCOVERY_SELECTION"
                if job_id <= 2018
                else "FIRST_15M_HANDOFF"
            )
            if (
                row[1] != expected_state
                or row[2] != "V2_STAGE_SCOPED"
                or row[3] != expected_scope
            ):
                raise OperationalCampaignRecoveryError(
                    "historical Scheduler-work state drifted"
                )
        jobs = connection.execute(
            "SELECT id,status,locked_at,lock_owner FROM printer_scheduler_jobs "
            "WHERE id BETWEEN 2011 AND 2020 ORDER BY id"
        ).fetchall()
        if len(jobs) != 10:
            raise OperationalCampaignRecoveryError(
                "historical Scheduler jobs missing"
            )
        for row in jobs:
            expected_state = (
                "SUCCEEDED" if int(row[0]) <= 2018 else "CANCELLED"
            )
            if (
                row[1] != expected_state
                or row[2] is not None
                or row[3] is not None
            ):
                raise OperationalCampaignRecoveryError(
                    "historical Scheduler job state drifted"
                )
        placeholders = ",".join("?" * len(ACTIVE_STATUS_VALUES))
        active_jobs = int(
            connection.execute(
                f"SELECT COUNT(*) FROM printer_scheduler_jobs "
                f"WHERE status IN ({placeholders}) "
                "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL",
                ACTIVE_STATUS_VALUES,
            ).fetchone()[0]
        )
        active_proof = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_proof_run_supervision "
                "WHERE execution_status IN ('STARTING','RUNNING')"
            ).fetchone()[0]
        )
        active_discovery = 0
        if _historical_table_exists(connection, "printer_discovery_work"):
            active_discovery = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_work "
                    "WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')"
                ).fetchone()[0]
            )
        if active_jobs or active_proof or active_discovery:
            raise OperationalCampaignRecoveryError(
                "historical active work unexpectedly exists"
            )

        lease_path = Path(str(supervision["lease_lock_path"])).resolve()
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
        if _parse(str(supervision["lease_expires_at"])) > now:
            raise OperationalCampaignRecoveryError(
                "historical lease is still live"
            )

        locked_counts = _locked_counts(connection)
        locked_hashes = _locked_hashes(connection)
        table_hashes = _historical_table_hashes(connection)
        identity_maps = _historical_identity_maps(connection)
        slot_ids = tuple(str(row[0]) for row in slots)
    finally:
        connection.close()
    _historical_reject_sidecars(db_path)
    return {
        "artifacts": artifacts,
        "locked_counts": locked_counts,
        "locked_hashes": locked_hashes,
        "table_hashes": table_hashes,
        "identity_maps": identity_maps,
        "slot_ids": slot_ids,
        "zero_counts": zero_counts,
    }


def reconcile_exact_historical_four_token_execution(
    *,
    operator_approved: bool,
    current_db: str | Path,
    pre_campaign_backup: str | Path,
    artifact_root: str | Path,
    recovery_root: str | Path,
    contract: HistoricalFourTokenRecoveryContract | None = None,
    live_process_probe: Callable[[str], bool] = _default_live_process_probe,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reconcile only the exact consumed four-token execution after full proof."""
    if not operator_approved:
        raise OperationalCampaignRecoveryError(
            "explicit operator approval is required"
        )
    active = contract or HistoricalFourTokenRecoveryContract()
    db_path = Path(current_db).resolve()
    baseline = Path(pre_campaign_backup).resolve()
    artifacts = Path(artifact_root).resolve()
    instant = now or datetime.now(timezone.utc)

    if _historical_already_reconciled(
        db_path=db_path,
        artifact_root=artifacts,
        contract=active,
    ):
        return {
            "status": "V2_9_8B_HISTORICAL_FOUR_TOKEN_ALREADY_RECONCILED",
            "execution_id": active.execution_id,
            "database_writes": 0,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "restart_created": False,
            "successor_created": False,
        }

    preflight = _historical_preflight(
        db_path=db_path,
        pre_campaign_backup=baseline,
        artifact_root=artifacts,
        contract=active,
        live_process_probe=live_process_probe,
        now=instant,
    )

    recovery_directory = Path(recovery_root).resolve()
    recovery_directory.mkdir(parents=True, exist_ok=False)
    backup_path = (
        recovery_directory / "printer_v1.pre-historical-reconciliation.sqlite3"
    )
    restore_path = (
        recovery_directory / "printer_v1.historical-restore-rehearsal.sqlite3"
    )
    backup = operational_backup_restore_preflight(
        db_path,
        expected_source_path=db_path,
        expected_source_identity=f"sha256:{active.expected_current_sha256}",
        backup_path=backup_path,
        disposable_restore_root=recovery_directory,
        restore_path=restore_path,
    )
    if _sha256(backup_path) != active.expected_current_sha256:
        raise OperationalCampaignRecoveryError(
            "historical reconciliation backup identity mismatch"
        )
    if _sha256(db_path) != active.expected_current_sha256:
        raise OperationalCampaignRecoveryError(
            "historical DB changed after backup preflight"
        )

    from printer_v1.operator_cli.four_token_factory_adapter import (
        reconcile_four_token_cycle_terminal,
    )

    phase_connection = sqlite3.connect(db_path)
    phase_connection.row_factory = sqlite3.Row
    phase_connection.execute("PRAGMA foreign_keys=ON")
    try:
        phase_a = reconcile_four_token_cycle_terminal(
            phase_connection,
            campaign_id=active.campaign_id,
            campaign_run_id=active.run_id,
            factory_run_id=active.factory_run_id,
            cycle_id=active.cycle_id,
            cause=active.original_terminal_cause,
            run_status="FAILED",
            now=instant,
            terminal_phase=None,
        )
    finally:
        phase_connection.close()
    if phase_a.get("pre_lifecycle_zero_attempt_provenance_recorded") is True:
        raise OperationalCampaignRecoveryError(
            "historical reconciliation fabricated migration-056 provenance"
        )

    cleanup = cleanup_campaign_supervision(
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
    reconciliation = reconcile_campaign_terminal(
        db_path,
        campaign_id=active.campaign_id,
        run_id=active.run_id,
        cycle_id=active.cycle_id,
        terminal_cause=active.original_terminal_cause,
        run_status="FAILED",
        factory_run_id=active.factory_run_id,
        lifecycle_started=False,
        now=_iso(instant),
    )

    connection = _read_only(db_path)
    try:
        after_locked_counts = _locked_counts(connection)
        after_locked_hashes = _locked_hashes(connection)
        after_table_hashes = _historical_table_hashes(connection)
        after_identity_maps = _historical_identity_maps(connection)
        changed = _historical_changed_identities(
            preflight["identity_maps"], after_identity_maps
        )
        expected_changed = {
            "printer_memory_factory_campaigns": {active.campaign_id},
            "printer_memory_factory_campaign_runs": {active.run_id},
            "printer_memory_factory_campaign_cycles": {active.cycle_id},
            "printer_memory_factory_campaign_token_slots": set(
                preflight["slot_ids"]
            ),
            "printer_memory_factory_campaign_supervision": {
                active.supervision_id
            },
            "printer_tracking_queue": {
                str(item) for item in active.expected_queue_ids
            },
            "printer_memory_factory_runs": {active.factory_run_id},
        }
        if changed != expected_changed:
            raise OperationalCampaignRecoveryError(
                f"historical reconciliation row mutation set mismatch: {changed}"
            )
        allowed_tables = set(expected_changed)
        unexpected_tables = sorted(
            table
            for table, digest in preflight["table_hashes"].items()
            if table not in allowed_tables
            and after_table_hashes.get(table) != digest
        )
        if unexpected_tables:
            raise OperationalCampaignRecoveryError(
                "historical reconciliation changed unexpected tables: "
                f"{unexpected_tables}"
            )
        if (
            after_locked_counts != preflight["locked_counts"]
            or after_locked_hashes != preflight["locked_hashes"]
        ):
            raise OperationalCampaignRecoveryError(
                "retrieval or financial lock content changed"
            )
        integrity = tuple(
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        provenance_rows = _historical_provenance_rows(connection, active)
        active_jobs = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN') "
                "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
        )
        windows = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
                "WHERE campaign_id=? AND run_id=? AND cycle_id=?",
                (active.campaign_id, active.run_id, active.cycle_id),
            ).fetchone()[0]
        )
        steps = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id=?",
                (active.factory_run_id,),
            ).fetchone()[0]
        )
        attempts = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
                "WHERE campaign_id=? AND campaign_run_id=?",
                (active.campaign_id, active.run_id),
            ).fetchone()[0]
        )
    finally:
        connection.close()

    if integrity != ("ok",) or foreign_keys:
        raise OperationalCampaignRecoveryError(
            "historical post-reconciliation database checks failed"
        )
    if provenance_rows or active_jobs or windows or steps or attempts:
        raise OperationalCampaignRecoveryError(
            "historical reconciliation left forbidden active/provenance residue"
        )
    if not _historical_already_reconciled(
        db_path=db_path,
        artifact_root=artifacts,
        contract=active,
    ):
        raise OperationalCampaignRecoveryError(
            "historical reconciliation did not reach exact terminal state"
        )
    _historical_reject_sidecars(db_path)
    changed_count = sum(len(items) for items in expected_changed.values())
    return {
        "status": "V2_9_8B_HISTORICAL_FOUR_TOKEN_RECONCILED",
        "execution_id": active.execution_id,
        "first_terminal_cause": active.original_terminal_cause,
        "changed_database_row_identities": changed_count,
        "database_writes": changed_count,
        "migration_056_provenance_rows": provenance_rows,
        "backup_path": str(backup_path),
        "backup_sha256": _sha256(backup_path),
        "backup_preflight": backup,
        "phase_a": phase_a,
        "cleanup": cleanup,
        "reconciliation": reconciliation,
        "final_database_sha256": _sha256(db_path),
        "integrity": "ok",
        "foreign_key_violations": 0,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "restart_created": False,
        "successor_created": False,
    }


def historical_four_token_reconciliation_paths() -> dict[str, Path]:
    """Resolve only the exact paths for the consumed historical execution."""
    repository = Path(__file__).resolve().parents[3]
    artifacts = (
        Path.home()
        / "PrinterOperations"
        / "v2-9-8"
        / _HISTORICAL_FOUR_TOKEN_EXECUTION_ID
    ).resolve()
    recovery = (
        Path.home()
        / "PrinterOperations"
        / "v2-9-8-historical-reconciliation"
        / (
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{uuid.uuid4().hex[:12]}"
        )
    ).resolve()
    return {
        "current_db": repository / "data" / "printer_v1.sqlite3",
        "pre_campaign_backup": artifacts / "printer_v1.pre-campaign.backup.sqlite3",
        "artifact_root": artifacts,
        "recovery_root": recovery,
    }
'''

text = TARGET.read_text(encoding="utf-8")
if MARKER in text:
    raise SystemExit("historical reconciliation implementation already present")
TARGET.write_text(text.rstrip() + IMPLEMENTATION + "\n", encoding="utf-8")
