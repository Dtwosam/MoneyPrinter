"""Isolated end-to-end proof for completed V2-9.7D Slice 6."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_authority_adapters import (
    load_authoritative_checkpoint_safety,
    load_authoritative_promotion_outcome,
)
from printer_v1.operator_cli.campaign_lifecycle_rotation_adapter import (
    CampaignTerminalOutcome,
    TerminalCampaignToken,
    evaluate_slot_replacement,
    reconcile_terminal_campaign_token,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_immutable_object,
    persist_scheduler_work,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    CampaignSupervisionError,
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    request_campaign_cancellation,
)
from printer_v1.operator_cli.final_campaign_report import (
    LOCKED_CAPABILITY_TABLES,
    persist_final_campaign_report,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    CLEAN_PROMOTED,
    NO_PROMOTION,
)
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    MIGRATION_032,
    operational_backup_restore_preflight,
    source_identity,
)
from printer_v1.operator_cli.zero_source_campaign_replay import (
    REPLAY_VERIFIED,
    replay_terminal_campaign_report,
)
from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.support_only_5m_capture import (
    ExpectedSupportCaptureIdentity,
    GovernedSourceProvenance,
    SupportCaptureBudgets,
    SupportCaptureRequest,
    SupportCaptureVerdict,
    SupportTriggerFamily,
    TriggeringSnapshot,
    evaluate_support_only_5m_capture,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)
from printer_v1.scheduler.two_token_fairness import (
    SchedulerSelectionStatus,
    SchedulerWorkIntent,
    SchedulerWorkItem,
    TwoTokenSlot,
    select_two_token_scheduler_work,
)
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


T0 = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
T15 = T0 + timedelta(minutes=15)
T1H = T0 + timedelta(hours=1)
T4H = T0 + timedelta(hours=4)
TEND = T4H + timedelta(minutes=5)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "e" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": _iso(T0),
    }


def _apply_through_031(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                   version TEXT PRIMARY KEY,
                   applied_at TEXT NOT NULL DEFAULT (datetime('now'))
               )"""
        )
        for migration in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(migration.name.split("_", 1)[0]) > 31:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (migration.name,),
            )
        connection.commit()
    finally:
        connection.close()


class IsolatedSlice6IntegrationProofTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "preflight-source.sqlite3"
        backup_root = self.root / "backups"
        restore_root = self.root / "restores"
        backup_root.mkdir()
        restore_root.mkdir()
        _apply_through_031(source)
        self.preflight = operational_backup_restore_preflight(
            source,
            expected_source_path=source,
            expected_source_identity=source_identity(source),
            backup_path=backup_root / "verified.sqlite3",
            disposable_restore_root=restore_root,
            restore_path=restore_root / "slice-6.sqlite3",
        )
        self.db = restore_root / "slice-6.sqlite3"
        self.lock = self.root / "campaign.lock.json"
        create_campaign(
            self.db,
            campaign_id="campaign-s6",
            configuration_id="configuration-s6",
            configuration={
                "slots": 2,
                "backup_preflight_references": {
                    "preflight_status": self.preflight["status"],
                    "source_identity": self.preflight["source_identity"],
                    "backup_sha256": self.preflight["backup_hash"],
                    "required_migration": self.preflight[
                        "required_rehearsed_migration"
                    ],
                    "latest_migration": self.preflight[
                        "latest_rehearsed_migration"
                    ],
                },
            },
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="slice-6-disposable-restore",
            proof_source_db_identity=self.preflight["source_identity"],
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.queues: dict[int, int] = {}
        self.window_rows: dict[str, int] = {}
        self._seed_campaign_graph()

    def _slot(self, cycle: int, token: int) -> dict[str, object]:
        return {
            "token_slot_id": f"cycle-{cycle}-slot-{token}",
            "slot_ordinal": token,
            "token_identity": f"token-{token}",
            "token_row_id": token,
            "mint_identity": f"mint-{token}",
            "pair_identity": f"pair-{token}",
            "pair_row_id": token,
            "lifecycle_identity": f"lifecycle-{token}",
            "tracking_queue_id": self.queues[token],
        }

    def _seed_campaign_graph(self) -> None:
        zero = {table: 0 for table in LOCKED_CAPABILITY_TABLES}
        authority_report = {
            "counts_before": zero,
            "counts_after": zero,
            "forbidden_deltas": zero,
            "run_budgets": {
                "governed_requests_run": 6,
                "governed_requests_run_ceiling": 20,
                "scheduler_rows_total": 6,
                "scheduler_rows_ceiling": 40,
                "automatic_retries": 0,
            },
        }
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                       run_id,run_status,stop_reason,window_kind,db_mode,
                       config_hash,config_json,selected_token_count,started_at,
                       finished_at,final_report_json
                   ) VALUES ('authority-s6','SAFE_STOPPED','SHARED_INTEGRITY_FAILURE',
                       'WINDOW_15M','PROOF_ONLY','hash','{}',2,?,?,?)""",
                (_iso(T0), _iso(TEND), json.dumps(authority_report, sort_keys=True)),
            )
            for token in (1, 2, 3):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,token_status) VALUES (?,?,?)",
                    (token, f"mint-{token}", "TRACK_FAST"),
                )
                self.connection.execute(
                    """INSERT INTO printer_pairs(
                           id,token_id,pair_address,base_token_mint
                       ) VALUES (?,?,?,?)""",
                    (token, token, f"pair-{token}", f"mint-{token}"),
                )
            for token in (1, 2):
                queue = self.connection.execute(
                    """INSERT INTO printer_tracking_queue(
                           token_id,pair_id,tracking_lane,tracking_action,
                           priority_reason,next_check_at,queue_status,source_status,
                           data_quality_label
                       ) VALUES (?,?,'TRACK_FAST','TRACK','slice-6',?,'ACTIVE',
                           'COMPLETE','CLEAN_DATA')""",
                    (token, token, _iso(T0)),
                )
                self.queues[token] = int(queue.lastrowid)
        create_campaign_run(
            self.connection, campaign_id="campaign-s6", run_id="run-s6",
            run_ordinal=1, authoritative_run_id="authority-s6", now=_iso(T0),
        )
        for cycle in (1, 2):
            create_cycle_with_two_slots(
                self.connection,
                campaign_id="campaign-s6", run_id="run-s6",
                cycle_id=f"cycle-{cycle}", cycle_ordinal=cycle,
                slots=(self._slot(cycle, 1), self._slot(cycle, 2)),
                now=_iso(T0),
            )
        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_campaigns
                   SET campaign_state='RUNNING',updated_at=?
                   WHERE campaign_id='campaign-s6'""", (_iso(T0),),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_runs
                   SET run_state='RUNNING',updated_at=? WHERE run_id='run-s6'""",
                (_iso(T0),),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_cycles
                   SET cycle_state='TRACKING',updated_at=?""", (_iso(T0),),
            )

        windows = (
            ("c1-t1-15m", 1, 1, "WINDOW_15M", None, T15),
            ("c1-t1-1h", 1, 1, "WINDOW_1H", "c1-t1-15m", T1H),
            ("c1-t1-4h", 1, 1, "WINDOW_4H", "c1-t1-1h", T4H),
            ("c1-t2-15m", 1, 2, "WINDOW_15M", None, T15),
            ("c2-t1-15m", 2, 1, "WINDOW_15M", None, T15),
            ("c2-t2-15m", 2, 2, "WINDOW_15M", None, T15),
        )
        for index, (window_id, cycle, token, kind, predecessor, cutoff) in enumerate(
            windows, start=1
        ):
            row_id = 100 + index
            self.window_rows[window_id] = row_id
            clean = token == 1
            with self.connection:
                self.connection.execute(
                    """INSERT INTO printer_memory_windows(
                           id,token_id,pair_id,window_kind,opened_at,closed_at,
                           memory_status,data_quality_label,window_status,
                           memory_quality_label
                       ) VALUES (?,?,?,?,?,?,'PARTIAL_MEMORY','CLEAN_DATA',
                           'WINDOW_CLOSED',?)""",
                    (
                        row_id, token, token, kind, _iso(T0), _iso(cutoff),
                        "CLEAN_MEMORY" if clean else "PARTIAL_MEMORY",
                    ),
                )
                request = self.connection.execute(
                    """INSERT INTO printer_source_requests(
                           source_name,request_kind,requested_at,source_status,
                           data_quality_label
                       ) VALUES ('geckoterminal','SNAPSHOT',?,'COMPLETE','CLEAN_DATA')""",
                    (_iso(cutoff - timedelta(minutes=1)),),
                )
                request_id = int(request.lastrowid)
                response = self.connection.execute(
                    """INSERT INTO printer_source_responses(
                           source_request_id,source_name,received_at,source_status,
                           data_quality_label
                       ) VALUES (?,'geckoterminal',?,'COMPLETE','CLEAN_DATA')""",
                    (request_id, _iso(cutoff)),
                )
                response_id = int(response.lastrowid)
                job = self.connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                           job_name,job_kind,target_table,target_id,priority,status,
                           scheduled_for,finished_at
                       ) VALUES (?,'CAMPAIGN_WINDOW','printer_tracking_queue',?,1,
                           ?,?,?)""",
                    (
                        f"job-{window_id}", self.queues[token],
                        "PENDING" if cycle == 2 else "SUCCEEDED",
                        _iso(T0), None if cycle == 2 else _iso(cutoff),
                    ),
                )
                job_id = int(job.lastrowid)
                close_kind = {
                    "WINDOW_15M": "WINDOW_CLOSE",
                    "WINDOW_1H": "CONTINUATION_CLOSE",
                    "WINDOW_4H": "LONG_CONTINUATION_CLOSE",
                }[kind]
                result = {"memory_pipeline": {"e2z_window_results": []}}
                if clean:
                    result["memory_pipeline"]["e2z_window_results"].append({
                        "window_id": row_id, "e2z_status": "E2Z_MEMORY_CREATED",
                    })
                self.connection.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                           run_id,step_key,step_kind,step_status,token_id,pair_id,
                           token_mint,pair_address,tracking_lane,scheduler_job_id,
                           source_request_id,source_response_id,memory_window_id,
                           result_json,finished_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "authority-s6", f"close-{window_id}", close_kind,
                        "SUCCEEDED", token, token, f"mint-{token}",
                        f"pair-{token}", "TRACK_FAST", job_id, request_id,
                        response_id, row_id, json.dumps(result), _iso(cutoff),
                    ),
                )
                if clean:
                    self.connection.execute(
                        """INSERT INTO printer_episodes(
                               memory_window_id,token_id,pair_id,episode_kind,
                               episode_status,memory_status,data_quality_label,
                               do_not_train,window_kind,memory_quality_label
                           ) VALUES (?,?,?,'MEMORY_WINDOW','COMPLETE','CLEAN_MEMORY',
                               'CLEAN_DATA',0,?,'CLEAN_MEMORY')""",
                        (row_id, token, token, kind),
                    )
            persist_window(
                self.connection,
                window_id=window_id, campaign_id="campaign-s6", run_id="run-s6",
                cycle_id=f"cycle-{cycle}",
                token_slot_id=f"cycle-{cycle}-slot-{token}",
                token_row_id=token, pair_row_id=token, window_kind=kind,
                root_15m_lifecycle_identity=f"lifecycle-{token}",
                predecessor_window_id=predecessor,
                memory_window_row_id=row_id,
                checkpoint_cutoff=_iso(cutoff), now=_iso(T0),
            )
            persist_scheduler_work(
                self.connection,
                scheduler_work_id=f"work-{window_id}", campaign_id="campaign-s6",
                run_id="run-s6", cycle_id=f"cycle-{cycle}",
                token_slot_id=f"cycle-{cycle}-slot-{token}", window_id=window_id,
                work_intent="collect", deadline_at=_iso(cutoff),
                scheduler_job_id=job_id, source_request_id=request_id,
                source_response_id=response_id, now=_iso(T0),
            )
            with self.connection:
                self.connection.execute(
                    """UPDATE printer_memory_factory_campaign_scheduler_work
                       SET work_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
                       WHERE scheduler_work_id=?""",
                    (
                        "RUNNING" if cycle == 2 else "SUCCEEDED",
                        None if cycle == 2 else "WORK_COMPLETE",
                        None if cycle == 2 else _iso(cutoff),
                        _iso(cutoff), f"work-{window_id}",
                    ),
                )
        for token, verdict in ((1, "CAPTURE_SUPPORT"), (2, "VALID_NO_CAPTURE")):
            support_id = f"c1-t{token}-support"
            persist_window(
                self.connection,
                window_id=support_id, campaign_id="campaign-s6", run_id="run-s6",
                cycle_id="cycle-1", token_slot_id=f"cycle-1-slot-{token}",
                token_row_id=token, pair_row_id=token,
                window_kind="WINDOW_5M_MICRO_EVENT",
                root_15m_lifecycle_identity=f"lifecycle-{token}",
                containing_main_window_id=f"c1-t{token}-15m",
                checkpoint_cutoff=_iso(T15), now=_iso(T0),
            )
            persist_immutable_object(
                self.connection,
                object_id=f"4b-{token}", object_kind="SUPPORT_EVIDENCE_4B",
                campaign_id="campaign-s6", configuration_id="configuration-s6",
                run_id="run-s6", cycle_id="cycle-1",
                token_slot_id=f"cycle-1-slot-{token}", window_id=support_id,
                payload={
                    "verdict": verdict, "support_only": True,
                    "main_outcome_authority": False,
                    "gaps": [] if token == 1 else ["approved_trigger_not_present"],
                },
                now=_iso(T0),
            )
        self._seed_safety_and_objects()

    def _seed_safety_and_objects(self) -> None:
        for suffix, window_id in enumerate(
            ("c1-t1-15m", "c1-t1-1h", "c1-t1-4h"), start=1
        ):
            row_id = self.window_rows[window_id]
            cutoff = (T15, T1H, T4H)[suffix - 1]
            captured = cutoff - timedelta(minutes=5)
            with self.connection:
                request = self.connection.execute(
                    """INSERT INTO printer_source_requests(
                           source_name,request_kind,requested_at,source_status,
                           data_quality_label
                       ) VALUES ('goplus','SAFETY',?,'COMPLETE','CLEAN_DATA')""",
                    (_iso(captured),),
                )
                request_id = int(request.lastrowid)
                response = self.connection.execute(
                    """INSERT INTO printer_source_responses(
                           source_request_id,source_name,received_at,source_status,
                           data_quality_label
                       ) VALUES (?,'goplus',?,'COMPLETE','CLEAN_DATA')""",
                    (request_id, _iso(captured)),
                )
                response_id = int(response.lastrowid)
                snapshot = self.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                           token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                           source_status,data_quality_label
                       ) VALUES (1,1,?,'TRACK_FAST','TOKEN','COMPLETE','CLEAN_DATA')""",
                    (_iso(captured),),
                )
                composite = self.connection.execute(
                    """INSERT INTO printer_safety_evidence_composites(
                           token_id,pair_id,snapshot_id,memory_window_id,policy_version,
                           token_mint,pair_address,evidence_captured_at,source_status,
                           data_quality_label,target_status,freshness_label,
                           mint_authority_status,freeze_authority_status,
                           metadata_mutability_status,supply_sanity_label,
                           holder_concentration_label,liquidity_lock_or_burn_label,
                           known_risk_flag_label,token_program_label,
                           safety_context_label,safety_contract_label,
                           provenance_complete,conflicts_json,blockers_json,
                           optional_unknowns_json,field_bindings_json,paper_only_context
                       ) VALUES (1,1,?,?,?,'mint-1','pair-1',?,'COMPLETE','CLEAN_DATA',
                           'TARGET_MATCH','SAFETY_EVIDENCE_FRESH',
                           'MINT_AUTHORITY_RENOUNCED','FREEZE_AUTHORITY_DISABLED',
                           'METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
                           'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
                           'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                           'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',1,
                           '[]','[]','[\"liquidity_lock_or_burn_label\"]','{}',1)""",
                    (
                        int(snapshot.lastrowid), row_id, f"policy-{suffix}",
                        _iso(captured),
                    ),
                )
                composite_id = int(composite.lastrowid)
                self.connection.execute(
                    """INSERT INTO printer_safety_evidence_contributions(
                           composite_id,source_name,evidence_category,source_request_id,
                           source_response_id,captured_at,freshness_label,token_mint,
                           pair_address,fields_supplied_json,source_status,
                           data_quality_label,target_status
                       ) VALUES (?,'goplus','TOKEN_SAFETY',?,?,?,
                           'SAFETY_EVIDENCE_FRESH','mint-1','pair-1','{}',
                           'COMPLETE','CLEAN_DATA','TARGET_MATCH')""",
                    (composite_id, request_id, response_id, _iso(captured)),
                )
            persist_immutable_object(
                self.connection,
                object_id=f"checkpoint-{suffix}", object_kind="CHECKPOINT_5A",
                campaign_id="campaign-s6", configuration_id="configuration-s6",
                run_id="run-s6", cycle_id="cycle-1",
                token_slot_id="cycle-1-slot-1", window_id=window_id,
                payload={"checkpoint_id": f"checkpoint-{suffix}", "evidence_gaps": []},
                safety_composite_id=composite_id, now=_iso(captured),
            )
        objects = (
            ("4a-continue", "CONTINUATION_4A", "c1-t1-15m", "cycle-1-slot-1", {
                "verdict": "CONTINUE_TO_WINDOW_1H", "unknowns": [],
            }),
            ("4a-stop", "CONTINUATION_4A", "c1-t2-15m", "cycle-1-slot-2", {
                "verdict": "STOP_AFTER_WINDOW_15M", "unknowns": [],
            }),
            ("trajectory-1", "TRAJECTORY_5A", "c1-t1-4h", "cycle-1-slot-1", {
                "trajectory_id": "trajectory-1", "evidence_gaps": [],
            }),
            ("manipulation-1", "MANIPULATION_CONTEXT_5B", "c1-t1-4h", "cycle-1-slot-1", {
                "market_integrity": "MANIPULATION_PRESENT",
                "tradeability": "TRADEABILITY_UNKNOWN",
                "unknowns": ["wallet_control_unknown", "intent_unknown"],
            }),
            ("opportunity-1", "OPPORTUNITY_SEGMENT_5C", "c1-t1-4h", "cycle-1-slot-1", {
                "full_window_outcome": "DUMP",
                "internal_trade_opportunity_outcome": "SHORT_TERM_PUMP",
                "opportunity_class": "CHART_OPPORTUNITY",
                "evidence_gaps": ["quote_missing", "slippage_missing"],
            }),
        )
        for object_id, kind, window_id, slot_id, payload in objects:
            persist_immutable_object(
                self.connection,
                object_id=object_id, object_kind=kind,
                campaign_id="campaign-s6", configuration_id="configuration-s6",
                run_id="run-s6", cycle_id="cycle-1", token_slot_id=slot_id,
                window_id=window_id, payload=payload, now=_iso(T0),
            )

    @staticmethod
    def _policy_slot(token: int, *, served: int = 0, failed: bool = False) -> TwoTokenSlot:
        return TwoTokenSlot(
            slot_id=f"cycle-1-slot-{token}", token_id=f"token-{token}",
            mint_id=f"mint-{token}", pair_id=f"pair-{token}",
            lifecycle_id=f"lifecycle-{token}", token_state="TRACK_FAST",
            ordinary_service_count=served, token_local_failure=failed,
        )

    @staticmethod
    def _continuation(token: int, *, stage: str, learning: object) -> TokenContinuationInput:
        predecessor, successor = (
            ("WINDOW_15M", "WINDOW_1H")
            if stage == "15m_to_1h" else ("WINDOW_1H", "WINDOW_4H")
        )
        window_id = f"c1-t{token}-{'15m' if stage == '15m_to_1h' else '1h'}"
        expected = ExpectedTokenContinuationIdentity(
            token_slot_id=f"cycle-1-slot-{token}", token_id=f"token-{token}",
            mint_id=f"mint-{token}", pair_id=f"pair-{token}",
            lifecycle_id=f"lifecycle-{token}", predecessor_window_id=window_id,
        )
        return TokenContinuationInput(
            campaign_id="campaign-s6", configuration_id="configuration-s6",
            token_slot_id=expected.token_slot_id, token_id=expected.token_id,
            mint_id=expected.mint_id, pair_id=expected.pair_id,
            lifecycle_id=expected.lifecycle_id,
            predecessor_window_id=expected.predecessor_window_id,
            expected_identity=expected, predecessor_window_kind=predecessor,
            successor_window_kind=successor, predecessor_window_status="WINDOW_CLOSED",
            predecessor_memory_quality="CLEAN_MEMORY",
            predecessor_data_quality="CLEAN_DATA", predecessor_do_not_train=False,
            predecessor_evidence_eligible=True, predecessor_complete=True,
            freshness_within_contract=True, governed_provenance_traceable=True,
            safety_context_present=True,
            safety_context_result=SAFETY_CONTEXT_ACCEPTABLE,
            continuity_status=CONTINUITY_CONTINUOUS, learning_need=learning,
            token_budget_available=True, token_state="TRACK_FAST",
        )

    @staticmethod
    def _support_request(token: int, *, capture: bool) -> SupportCaptureRequest:
        expected = ExpectedSupportCaptureIdentity(
            campaign_id="campaign-s6", run_id="run-s6", cycle_id="cycle-1",
            token_slot_id=f"cycle-1-slot-{token}", token_id=f"token-{token}",
            mint_id=f"mint-{token}", pair_id=f"pair-{token}",
            root_15m_lifecycle_id=f"lifecycle-{token}",
            containing_main_window_id=f"c1-t{token}-15m",
            scheduler_work_id=f"work-c1-t{token}-15m",
        )
        provenance = GovernedSourceProvenance(
            source_name="geckoterminal", source_request_id=1,
            source_response_id=1, scheduler_work_id=expected.scheduler_work_id,
            source_status="COMPLETE", data_quality_label="CLEAN_DATA",
            governor_approved=True, traceable=True,
        )
        snapshots = tuple(
            TriggeringSnapshot(
                snapshot_id=900 + token * 10 + offset,
                campaign_id=expected.campaign_id, run_id=expected.run_id,
                cycle_id=expected.cycle_id, token_slot_id=expected.token_slot_id,
                token_id=expected.token_id, mint_id=expected.mint_id,
                pair_id=expected.pair_id,
                root_15m_lifecycle_id=expected.root_15m_lifecycle_id,
                containing_main_window_id=expected.containing_main_window_id,
                observed_at=T15 - timedelta(minutes=1 - offset),
                freshness_within_contract=True, provenance=provenance,
            )
            for offset in (0, 1)
        )
        return SupportCaptureRequest(
            campaign_id=expected.campaign_id, run_id=expected.run_id,
            cycle_id=expected.cycle_id, token_slot_id=expected.token_slot_id,
            token_id=expected.token_id, mint_id=expected.mint_id,
            pair_id=expected.pair_id,
            root_15m_lifecycle_id=expected.root_15m_lifecycle_id,
            containing_main_window_id=expected.containing_main_window_id,
            containing_main_window_kind="WINDOW_15M",
            containing_main_window_status="WINDOW_OPEN",
            scheduler_work_id=expected.scheduler_work_id,
            expected_identity=expected,
            trigger_family=SupportTriggerFamily.LIQUIDITY_SHOCK if capture else None,
            trigger_time=T15, evidence_cutoff=T15, triggering_snapshots=snapshots,
            budgets=SupportCaptureBudgets(), token_state="TRACK_FAST",
            meaningful_transition_proven=capture, ordinary_movement=not capture,
        )

    def _terminal_token(self, token: int, outcome: CampaignTerminalOutcome) -> TerminalCampaignToken:
        return TerminalCampaignToken(
            campaign_id="campaign-s6", run_id="run-s6", cycle_id="cycle-2",
            token_slot_id=f"cycle-2-slot-{token}", token_identity=f"token-{token}",
            mint_identity=f"mint-{token}", pair_identity=f"pair-{token}",
            lifecycle_identity=f"lifecycle-{token}", outcome=outcome,
        )

    def test_completed_slice_6_components_work_together(self) -> None:
        self.assertEqual(self.preflight["status"], "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY")
        self.assertEqual(self.preflight["required_rehearsed_migration"], MIGRATION_032)
        self.assertEqual(self.preflight["latest_rehearsed_migration"], "033_operational_campaign_supervision.sql")

        slots = (self._policy_slot(1), self._policy_slot(2))
        work = tuple(
            SchedulerWorkItem(
                scheduler_work_id=f"policy-work-{token}",
                token_slot_id=f"cycle-1-slot-{token}", token_id=f"token-{token}",
                job_kind=JobKind.TRACK_FAST_FIRST_15M,
                work_intent=SchedulerWorkIntent.ORDINARY,
                scheduled_for=T0, created_at=T0,
            )
            for token in (1, 2)
        )
        first = select_two_token_scheduler_work(token_slots=slots, work_items=work, now=T0)
        second = select_two_token_scheduler_work(
            token_slots=(self._policy_slot(1, served=1), self._policy_slot(2)),
            work_items=work, now=T0,
        )
        isolated = select_two_token_scheduler_work(
            token_slots=(self._policy_slot(1), self._policy_slot(2, failed=True)),
            work_items=work, now=T0,
        )
        shared = select_two_token_scheduler_work(
            token_slots=slots, work_items=work, now=T0,
            shared_stop_reasons=("SHARED_INTEGRITY_FAILURE",),
        )
        self.assertEqual(first.selected_work.token_id, "token-1")
        self.assertEqual(second.selected_work.token_id, "token-2")
        self.assertEqual(isolated.selected_work.token_id, "token-1")
        self.assertEqual(shared.status, SchedulerSelectionStatus.BLOCKED)

        context = CampaignContinuationContext("campaign-s6", "configuration-s6")
        at_15m = evaluate_token_local_continuations(
            campaign=context,
            tokens=(
                self._continuation(1, stage="15m_to_1h", learning=ContinuationLearningNeed.TRANSITION),
                self._continuation(2, stage="15m_to_1h", learning=None),
            ),
        )
        at_1h = evaluate_token_local_continuations(
            campaign=context,
            tokens=(
                self._continuation(1, stage="1h_to_4h", learning=ContinuationLearningNeed.SURVIVAL),
                replace(
                    self._continuation(2, stage="1h_to_4h", learning=ContinuationLearningNeed.SURVIVAL),
                    safety_context_result="SAFETY_CONTEXT_BLOCKED",
                ),
            ),
        )
        self.assertEqual(at_15m[0].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_1H)
        self.assertEqual(at_15m[1].verdict, ContinuationVerdict.STOP_AFTER_WINDOW_15M)
        self.assertEqual(at_1h[0].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_4H)
        self.assertEqual(at_1h[1].verdict, ContinuationVerdict.BLOCK_CONTINUATION)

        positive = evaluate_support_only_5m_capture(self._support_request(1, capture=True))
        negative = evaluate_support_only_5m_capture(self._support_request(2, capture=False))
        self.assertEqual(positive.verdict, SupportCaptureVerdict.CAPTURE_SUPPORT)
        self.assertEqual(negative.verdict, SupportCaptureVerdict.VALID_NO_CAPTURE)
        self.assertTrue(positive.capture.support_only)
        self.assertFalse(positive.capture.continuation_authority)

        promotion_1 = load_authoritative_promotion_outcome(
            self.db, campaign_id="campaign-s6", run_id="run-s6",
            cycle_id="cycle-1", token_slot_id="cycle-1-slot-1",
            window_id="c1-t1-15m",
        )
        promotion_2 = load_authoritative_promotion_outcome(
            self.db, campaign_id="campaign-s6", run_id="run-s6",
            cycle_id="cycle-1", token_slot_id="cycle-1-slot-2",
            window_id="c1-t2-15m",
        )
        self.assertEqual(promotion_1["promotion_status"], CLEAN_PROMOTED)
        self.assertEqual(promotion_2["promotion_status"], NO_PROMOTION)
        for suffix, window_id in enumerate(("c1-t1-15m", "c1-t1-1h", "c1-t1-4h"), 1):
            safety = load_authoritative_checkpoint_safety(
                self.db, campaign_id="campaign-s6", run_id="run-s6",
                cycle_id="cycle-1", token_slot_id="cycle-1-slot-1",
                window_id=window_id, checkpoint_object_id=f"checkpoint-{suffix}",
            )
            self.assertTrue(safety["gate_accepted"])
            self.assertEqual(safety["raw_composite"]["safety_context_label"], "SAFETY_UNKNOWN")

        acquired = acquire_campaign_supervision(
            self.db, lock_path=self.lock, supervision_id="supervision-s6",
            campaign_id="campaign-s6", configuration_id="configuration-s6",
            run_id="run-s6", owner_id="owner-s6", now=T0,
        )
        self.assertTrue(acquired["new_child_work_allowed"])
        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_token_slots
                   SET token_state='WINDOW_4H_CLOSED',updated_at=?
                   WHERE token_slot_id IN ('cycle-1-slot-1','cycle-2-slot-1')""",
                (_iso(T4H),),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_token_slots
                   SET token_state='WINDOW_15M_CLOSED',updated_at=?
                   WHERE token_slot_id='cycle-1-slot-2'""", (_iso(T15),),
            )
            self.connection.execute(
                """UPDATE printer_memory_factory_campaign_token_slots
                   SET token_state='FAILED',first_terminal_cause='TOKEN_LOCAL_BLOCKER',
                       terminal_at=?,updated_at=? WHERE token_slot_id='cycle-2-slot-2'""",
                (_iso(T15), _iso(T15)),
            )
        natural = reconcile_terminal_campaign_token(
            self.db, token=self._terminal_token(1, CampaignTerminalOutcome.NATURAL),
            stop_reason="TOKEN_COMPLETE",
        )
        blocked = reconcile_terminal_campaign_token(
            self.db, token=self._terminal_token(2, CampaignTerminalOutcome.BLOCKED),
            stop_reason="TOKEN_LOCAL_BLOCKER",
        )
        self.assertEqual(natural["active_associated_work"]["total"], 0)
        self.assertEqual(blocked["active_associated_work"]["total"], 0)
        replacement = evaluate_slot_replacement(
            self.db, token=self._terminal_token(1, CampaignTerminalOutcome.NATURAL),
            candidate_token_row_id=3, candidate_mint_identity="mint-3",
            candidate_pair_row_id=3, candidate_pair_identity="pair-3",
        )
        self.assertTrue(replacement["replacement_allowed"])

        cancellation = request_campaign_cancellation(
            self.db, supervision_id="supervision-s6", campaign_id="campaign-s6",
            configuration_id="configuration-s6", run_id="run-s6",
            owner_id="owner-s6", reason="SHARED_INTEGRITY_FAILURE", now=T4H,
        )
        self.assertFalse(cancellation["new_child_work_allowed"])
        cleanup = cleanup_campaign_supervision(
            self.db, supervision_id="supervision-s6", campaign_id="campaign-s6",
            configuration_id="configuration-s6", run_id="run-s6",
            owner_id="owner-s6", terminal_status="FAILED",
            first_terminal_cause="SHARED_INTEGRITY_FAILURE", now=TEND,
        )
        self.assertEqual(cleanup["active_owned_work_after"], 0)
        self.assertTrue(cleanup["lease_released"])
        self.assertFalse(cleanup["successor_created"])
        self.assertFalse(cleanup["restart_created"])
        repeated_cleanup = cleanup_campaign_supervision(
            self.db, supervision_id="supervision-s6", campaign_id="campaign-s6",
            configuration_id="configuration-s6", run_id="run-s6",
            owner_id="owner-s6", terminal_status="FAILED",
            first_terminal_cause="LATER_WORKER_FAULT",
            now=TEND + timedelta(seconds=1),
        )
        self.assertTrue(repeated_cleanup["idempotent_replay"])
        self.assertEqual(
            repeated_cleanup["first_terminal_cause"],
            "SHARED_INTEGRITY_FAILURE",
        )
        with self.assertRaisesRegex(CampaignSupervisionError, "already exists|RUNNING"):
            acquire_campaign_supervision(
                self.db, lock_path=self.root / "successor.lock",
                supervision_id="successor-s6", campaign_id="campaign-s6",
                configuration_id="configuration-s6", run_id="run-s6",
                owner_id="successor-owner", now=TEND + timedelta(minutes=1),
            )

        persisted = persist_final_campaign_report(
            self.db, report_id="report-s6", campaign_id="campaign-s6",
            configuration_id="configuration-s6", run_id="run-s6",
        )
        repeated = persist_final_campaign_report(
            self.db, report_id="report-s6", campaign_id="campaign-s6",
            configuration_id="configuration-s6", run_id="run-s6",
        )
        self.assertEqual(persisted["report_hash"], repeated["report_hash"])
        self.assertTrue(repeated["idempotent_replay"])
        report = json.loads(persisted["canonical_json"])
        self.assertEqual(len(report["identity"]["cycles"]), 2)
        self.assertTrue(all(
            sum(slot["cycle_id"] == cycle["cycle_id"] for slot in report["identity"]["two_token_slots"]) == 2
            for cycle in report["identity"]["cycles"]
        ))
        self.assertEqual(report["terminal"]["first_terminal_cause"], "SHARED_INTEGRITY_FAILURE")
        self.assertTrue(report["locked_capabilities"]["all_deltas_zero"])
        self.assertEqual(report["backup_preflight_references"]["latest_migration"], "033_operational_campaign_supervision.sql")
        self.assertNotEqual(
            report["opportunity_outcome_layers"][0]["full_window_outcome"],
            report["opportunity_outcome_layers"][0]["internal_trade_opportunity_outcome"],
        )

        replay = replay_terminal_campaign_report(
            self.db, campaign_id="campaign-s6", configuration_id="configuration-s6",
            report_id="report-s6", report_hash=persisted["report_hash"],
        )
        self.assertEqual(replay["replay_state"], REPLAY_VERIFIED)
        self.assertEqual(replay["zero_work_evidence"], {
            "source_calls": 0, "scheduler_work": 0,
            "memory_writes": 0, "database_writes": 0,
        })
        self.assertEqual(
            replay["database_read_only_evidence"]["before_sha256"],
            replay["database_read_only_evidence"]["after_sha256"],
        )
        self.assertEqual(self.connection.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
               WHERE work_state IN ('PENDING','RUNNING','COOLDOWN')"""
        ).fetchone()[0], 0)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision"
        ).fetchone()[0], 1)
        for table in LOCKED_CAPABILITY_TABLES:
            self.assertEqual(self.connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
