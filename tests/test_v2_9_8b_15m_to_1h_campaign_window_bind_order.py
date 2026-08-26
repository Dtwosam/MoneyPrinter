"""Regression for 15m campaign-window identity bind before Lane Q.

TDD owner for V2-9.8B OPTION B: bind pre-created WINDOW_15M memory_window_row_id
after physical close and before E2Z/Lane Q. Identity only. No live sources.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    create_campaign_run,
    create_cycle_with_two_slots,
    project_campaign_scheduler_work,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.close_phases import close_phase_metadata
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
from printer_v1.operator_cli.one_command_15m_factory import (
    _audit_15m_close_from_evidence,
)
from printer_v1.operator_cli.operational_selective_1h import (
    SELECTIVE_1H_POLICY_VERSION,
    ensure_authoritative_factory_link,
    evaluate_selective_1h_for_cycle,
    persist_15m_campaign_window,
    precreate_15m_campaign_window,
    Selective1hError,
)
from printer_v1.scheduler.contracts import JOB_PRIORITY_VALUE, JobKind


T0 = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
T15 = T0 + timedelta(minutes=15)
NOW = T15.isoformat()
CAMPAIGN_ID = "campaign-bind-order"
RUN_ID = "run-bind-order"
CYCLE_ID = "cycle-bind-order"
FACTORY_RUN_ID = "factory-bind-order"
SLOT_1 = "slot-bind-1"
SLOT_2 = "slot-bind-2"


def _iso(value: datetime) -> str:
    return value.isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "b" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class BindOrderFixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bind-order.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign(
            self.db,
            campaign_id=CAMPAIGN_ID,
            configuration_id="config-bind-order",
            configuration={
                "policy": SELECTIVE_1H_POLICY_VERSION,
                "token_capacity": 2,
                "main_window": "WINDOW_15M",
                "selective_1h_continuation": True,
            },
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="proof-bind-order",
            proof_source_db_identity="proof-source-bind-order",
            policy_version=SELECTIVE_1H_POLICY_VERSION,
        )
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    selected_token_count,started_at
                ) VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash',?,2,?)""",
                (
                    FACTORY_RUN_ID,
                    json.dumps({"selective_1h_continuation": True}),
                    NOW,
                ),
            )
            for identity in (1, 2):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?,?)",
                    (identity, f"mint-{identity}", "solana"),
                )
                self.connection.execute(
                    """INSERT INTO printer_pairs(id,token_id,pair_address)
                       VALUES (?,?,?)""",
                    (identity, identity, f"pair-{identity}"),
                )
                self.connection.execute(
                    """INSERT INTO printer_tracking_queue(
                           id,token_id,pair_id,tracking_lane,tracking_action,
                           priority_reason,next_check_at,queue_status,
                           source_status,data_quality_label
                       ) VALUES (?,?,?,'TRACK_FAST','PROMOTE_TO_TRACK_FAST',
                           'bind-order-fixture',?,'ACTIVE',
                           'COMPLETE','CLEAN_DATA')""",
                    (identity, identity, identity, NOW),
                )
        create_campaign_run(
            self.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            run_ordinal=1,
            now=NOW,
        )
        ensure_authoritative_factory_link(
            self.connection,
            campaign_run_id=RUN_ID,
            factory_run_id=FACTORY_RUN_ID,
            now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": SLOT_1,
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "mint-1",
                    "pair_identity": "pair-1",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                    "tracking_queue_id": 1,
                },
                {
                    "token_slot_id": SLOT_2,
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "mint-2",
                    "pair_identity": "pair-2",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                    "tracking_queue_id": 2,
                },
            ),
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_factory_campaigns "
                "SET campaign_state='RUNNING' WHERE campaign_id=?",
                (CAMPAIGN_ID,),
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_runs "
                "SET run_state='RUNNING' WHERE run_id=?",
                (RUN_ID,),
            )
        self.window_id_1 = precreate_15m_campaign_window(
            self.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            lifecycle_identity="lifecycle-1",
            checkpoint_cutoff=NOW,
            now=NOW,
        )
        self.window_id_2 = precreate_15m_campaign_window(
            self.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_2,
            token_row_id=2,
            pair_row_id=2,
            lifecycle_identity="lifecycle-2",
            checkpoint_cutoff=NOW,
            now=NOW,
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()
        self.tmp.cleanup()

    def insert_snapshots(
        self,
        *,
        token_id: int,
        count: int,
        span_seconds: float,
        tracking_lane: str = "TRACK_FAST",
    ) -> list[int]:
        ids: list[int] = []
        if count < 2:
            raise ValueError("need at least two snapshots")
        for index in range(count):
            captured = T0 + timedelta(
                seconds=(span_seconds * index / (count - 1))
            )
            cursor = self.connection.execute(
                """INSERT INTO printer_token_snapshots(
                       token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                       source_status,data_quality_label,price_usd,liquidity_usd
                   ) VALUES (?,?,?,?,?,'COMPLETE','CLEAN_DATA',?,?)""",
                (
                    token_id,
                    token_id,
                    _iso(captured),
                    tracking_lane,
                    "FIRST_15M_CYCLE",
                    1.0 + index,
                    10_000.0,
                ),
            )
            snapshot_id = int(cursor.lastrowid)
            ids.append(snapshot_id)
            self.connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                       run_id,step_key,step_kind,step_status,token_id,pair_id,
                       token_mint,pair_address,tracking_lane,scheduled_for,
                       snapshot_id,created_at,updated_at
                   ) VALUES (?,?, 'SNAPSHOT','SUCCEEDED',?,?,?,?,?,?,?,?,?)""",
                (
                    FACTORY_RUN_ID,
                    f"t{token_id}_snapshot_{index:02d}",
                    token_id,
                    token_id,
                    f"mint-{token_id}",
                    f"pair-{token_id}",
                    tracking_lane,
                    _iso(captured),
                    snapshot_id,
                    _iso(captured),
                    _iso(captured),
                ),
            )
        self.connection.commit()
        return ids

    def insert_audit_step(
        self,
        *,
        token_id: int,
        campaign_window_id: str,
        token_slot_id: str,
        closing_snapshot_id: int,
    ) -> sqlite3.Row:
        metadata = close_phase_metadata(
            family="WINDOW_CLOSE",
            phase="AUDIT",
            preclose_step_key=f"t{token_id}_window_close_pre_close_critical",
            evidence_step_key=f"t{token_id}_window_close_evidence",
            context_step_key=f"t{token_id}_window_close_context",
        )
        job = self.connection.execute(
            """INSERT INTO printer_scheduler_jobs(
                   job_name,job_kind,target_table,priority,status,scheduled_for,
                   created_at,updated_at
               ) VALUES (?,?,'printer_tracking_queue',?,'PENDING',?,?,?)""",
            (
                f"job-t{token_id}-audit",
                JobKind.MEMORY_WINDOW_CLOSE.value,
                JOB_PRIORITY_VALUE[JobKind.MEMORY_WINDOW_CLOSE],
                NOW,
                NOW,
                NOW,
            ),
        )
        job_id = int(job.lastrowid)
        cursor = self.connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                   run_id,step_key,step_kind,step_status,token_id,pair_id,
                   token_mint,pair_address,tracking_lane,scheduled_for,
                   scheduler_job_id,snapshot_id,result_json,created_at,updated_at
               ) VALUES (?,?, 'WINDOW_CLOSE_AUDIT','RUNNING',?,?,?,?,?,?,?,?,?,?,?)""",
            (
                FACTORY_RUN_ID,
                f"t{token_id}_window_close_audit",
                token_id,
                token_id,
                f"mint-{token_id}",
                f"pair-{token_id}",
                "TRACK_FAST",
                NOW,
                job_id,
                closing_snapshot_id,
                json.dumps(metadata, sort_keys=True),
                NOW,
                NOW,
            ),
        )
        self.connection.commit()
        project_campaign_scheduler_work(
            self.connection,
            scheduler_work_id=f"work-audit-{token_id}",
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            work_scope="WINDOW_LIFECYCLE",
            stage_id="WINDOW_15M",
            work_intent="WINDOW_15M_WINDOW_CLOSE_AUDIT",
            deadline_at=NOW,
            scheduler_job_id=job_id,
            target_category="CAMPAIGN_WINDOW",
            target_identity=campaign_window_id,
            token_slot_id=token_slot_id,
            window_id=campaign_window_id,
            factory_run_id=FACTORY_RUN_ID,
            now=NOW,
        )
        return self.connection.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
            (int(cursor.lastrowid),),
        ).fetchone()

    def insert_optional_unknown_composite(
        self, *, token_id: int, snapshot_id: int
    ) -> None:
        self.connection.execute(
            """INSERT INTO printer_safety_evidence_composites(
                   token_id,pair_id,snapshot_id,policy_version,token_mint,
                   pair_address,evidence_captured_at,source_status,
                   data_quality_label,target_status,freshness_label,
                   mint_authority_status,freeze_authority_status,
                   metadata_mutability_status,supply_sanity_label,
                   holder_concentration_label,liquidity_lock_or_burn_label,
                   known_risk_flag_label,token_program_label,safety_context_label,
                   safety_contract_label,provenance_complete,conflicts_json,
                   blockers_json,optional_unknowns_json,field_bindings_json,
                   paper_only_context
               ) VALUES (?,?,?,'V2_4_1_COMPOSITE_SAFETY_V1',?,?,?,'COMPLETE',
                   'CLEAN_DATA','TARGET_MATCH','SAFETY_EVIDENCE_FRESH',
                   'MINT_AUTHORITY_RENOUNCED','FREEZE_AUTHORITY_DISABLED',
                   'METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
                   'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
                   'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                   'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',
                   1,'[]','[]',?,?,1)""",
            (
                token_id,
                token_id,
                snapshot_id,
                f"mint-{token_id}",
                f"pair-{token_id}",
                NOW,
                json.dumps(
                    [
                        "liquidity_lock_or_burn_label",
                        "known_risk_flag_label",
                    ]
                ),
                json.dumps(
                    {
                        "liquidity_lock_or_burn_label": "goplus",
                        "known_risk_flag_label": "goplus",
                    }
                ),
            ),
        )
        self.connection.commit()


class BindOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = BindOrderFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def _run_production_close(
        self,
        *,
        snapshot_count: int = 16,
        span_seconds: float = 900.0,
        capture_before_e2z: dict[str, object] | None = None,
    ) -> dict[str, object]:
        snapshot_ids = self.fx.insert_snapshots(
            token_id=1, count=snapshot_count, span_seconds=span_seconds
        )
        closing_id = snapshot_ids[-1]
        self.fx.insert_optional_unknown_composite(
            token_id=1, snapshot_id=closing_id
        )
        step = self.fx.insert_audit_step(
            token_id=1,
            campaign_window_id=self.fx.window_id_1,
            token_slot_id=SLOT_1,
            closing_snapshot_id=closing_id,
        )
        context_result = {
            "ok": True,
            "closing_snapshot_id": closing_id,
            "governed_context_collection": {},
            "governed_context_persistence": {},
        }
        real_e2z = run_e2z_pipeline

        def _spy(db_path, **kwargs):
            probe = sqlite3.connect(db_path)
            probe.row_factory = sqlite3.Row
            try:
                row = probe.execute(
                    """SELECT memory_window_row_id,window_state,
                              first_terminal_cause,terminal_at
                       FROM printer_memory_factory_campaign_windows
                       WHERE window_id=?""",
                    (self.fx.window_id_1,),
                ).fetchone()
                if capture_before_e2z is not None:
                    capture_before_e2z["campaign_bind"] = (
                        None if row is None else row["memory_window_row_id"]
                    )
                    capture_before_e2z["window_state"] = (
                        None if row is None else row["window_state"]
                    )
                    capture_before_e2z["first_terminal_cause"] = (
                        None if row is None else row["first_terminal_cause"]
                    )
                    capture_before_e2z["terminal_at"] = (
                        None if row is None else row["terminal_at"]
                    )
                    mem = probe.execute(
                        """SELECT data_quality_label,memory_quality_label,
                                  memory_status,do_not_train
                           FROM printer_memory_windows
                           ORDER BY id DESC LIMIT 1"""
                    ).fetchone()
                    capture_before_e2z["physical"] = (
                        None if mem is None else dict(mem)
                    )
            finally:
                probe.close()
            return real_e2z(db_path, **kwargs)

        with patch(
            "printer_v1.operator_cli.lane_k_e2z_pipeline_wiring.run_e2z_pipeline",
            side_effect=_spy,
        ):
            result = _audit_15m_close_from_evidence(
                self.fx.connection,
                step,
                closing_snapshot_id=closing_id,
                minimum_evidence_seconds=1.0 if span_seconds < 900 else 900.0,
                context_result=context_result,
                cancellation_probe=None,
            )
        return result

    def test_production_close_binds_before_lane_q_and_does_not_false_dirty(self) -> None:
        before_e2z: dict[str, object] = {}
        result = self._run_production_close(capture_before_e2z=before_e2z)
        self.assertTrue(result.get("ok"))
        self.assertIsNotNone(result.get("memory_window_id"))
        self.assertEqual(before_e2z.get("campaign_bind"), result["memory_window_id"])
        self.assertEqual(before_e2z.get("window_state"), "PLANNED")
        self.assertIsNone(before_e2z.get("first_terminal_cause"))
        self.assertIsNone(before_e2z.get("terminal_at"))
        pipeline = result["memory_pipeline"]
        blocked = []
        for item in pipeline.get("e2z_window_results") or ():
            blocked.extend(item.get("lane_q_blocked_reasons") or ())
        self.assertFalse(
            any("CAMPAIGN_WINDOW_BINDING_MISSING" in str(reason) for reason in blocked)
        )
        physical = self.fx.connection.execute(
            """SELECT data_quality_label,do_not_train,memory_status
               FROM printer_memory_windows WHERE id=?""",
            (int(result["memory_window_id"]),),
        ).fetchone()
        pre = before_e2z.get("physical") or {}
        if (
            str(pre.get("data_quality_label")) == "CLEAN_DATA"
            and int(pre.get("do_not_train") or 0) == 0
        ):
            self.assertEqual(physical["data_quality_label"], "CLEAN_DATA")
            self.assertEqual(int(physical["do_not_train"]), 0)
        overlays = json.loads(
            self.fx.connection.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
                (int(result["memory_window_id"]),),
            ).fetchone()[0]
            or "{}"
        ).get("memory_build_evidence_overlays") or {}
        pending = overlays.get("source_coverage_pending_fields") or []
        if pending:
            self.assertIn("liquidity_lock_or_burn_label", pending)
            self.assertIn("known_risk_flag_label", pending)

    def test_null_bind_is_idempotent_and_does_not_duplicate_or_overwrite(self) -> None:
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_15m_campaign_window_memory_row,
        )
        memory_id = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status
                   ) VALUES (1,1,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                             'WINDOW_CLOSED')""",
                (_iso(T0), NOW),
            ).lastrowid
        )
        first = bind_precreated_15m_campaign_window_memory_row(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=self.fx.window_id_1,
            memory_window_row_id=memory_id,
            now=NOW,
        )
        self.assertTrue(first["bound"] or first["idempotent"])
        replay = bind_precreated_15m_campaign_window_memory_row(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=self.fx.window_id_1,
            memory_window_row_id=memory_id,
            now=NOW,
        )
        self.assertTrue(replay["idempotent"])
        other = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status
                   ) VALUES (1,1,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                             'WINDOW_CLOSED')""",
                (_iso(T0), NOW),
            ).lastrowid
        )
        with self.assertRaises(Selective1hError):
            bind_precreated_15m_campaign_window_memory_row(
                self.fx.connection,
                campaign_id=CAMPAIGN_ID,
                run_id=RUN_ID,
                cycle_id=CYCLE_ID,
                token_slot_id=SLOT_1,
                token_row_id=1,
                pair_row_id=1,
                campaign_window_id=self.fx.window_id_1,
                memory_window_row_id=other,
                now=NOW,
            )
        bound = self.fx.connection.execute(
            """SELECT memory_window_row_id,window_state,COUNT(*)
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND token_slot_id=? AND window_kind='WINDOW_15M'
               GROUP BY memory_window_row_id,window_state""",
            (CAMPAIGN_ID, SLOT_1),
        ).fetchone()
        self.assertEqual(int(bound["memory_window_row_id"]), memory_id)
        self.assertEqual(str(bound["window_state"]), "PLANNED")
        self.assertEqual(int(bound[2]), 1)

    def test_absent_and_mismatched_identity_fail_closed(self) -> None:
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_15m_campaign_window_memory_row,
        )
        memory_id = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status
                   ) VALUES (1,1,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                             'WINDOW_CLOSED')""",
                (_iso(T0), NOW),
            ).lastrowid
        )
        with self.assertRaises(Selective1hError):
            bind_precreated_15m_campaign_window_memory_row(
                self.fx.connection,
                campaign_id=CAMPAIGN_ID,
                run_id=RUN_ID,
                cycle_id=CYCLE_ID,
                token_slot_id="missing-slot",
                token_row_id=1,
                pair_row_id=1,
                campaign_window_id="cw:missing",
                memory_window_row_id=memory_id,
                now=NOW,
            )
        with self.assertRaises(Selective1hError):
            bind_precreated_15m_campaign_window_memory_row(
                self.fx.connection,
                campaign_id=CAMPAIGN_ID,
                run_id=RUN_ID,
                cycle_id=CYCLE_ID,
                token_slot_id=SLOT_1,
                token_row_id=2,
                pair_row_id=2,
                campaign_window_id=self.fx.window_id_1,
                memory_window_row_id=memory_id,
                now=NOW,
            )
        unbound = self.fx.connection.execute(
            "SELECT memory_window_row_id FROM printer_memory_factory_campaign_windows "
            "WHERE window_id=?",
            (self.fx.window_id_1,),
        ).fetchone()
        self.assertIsNone(unbound["memory_window_row_id"])

    def test_genuine_lane_q_blocker_after_bind_still_dirties(self) -> None:
        before_e2z: dict[str, object] = {}
        result = self._run_production_close(
            snapshot_count=3,
            span_seconds=60.0,
            capture_before_e2z=before_e2z,
        )
        self.assertEqual(before_e2z.get("campaign_bind"), result.get("memory_window_id"))
        pipeline = result["memory_pipeline"]
        blocked = []
        for item in pipeline.get("e2z_window_results") or ():
            blocked.extend(item.get("lane_q_blocked_reasons") or ())
        self.assertTrue(blocked)
        self.assertFalse(
            any("CAMPAIGN_WINDOW_BINDING_MISSING" in str(reason) for reason in blocked)
        )
        physical = self.fx.connection.execute(
            """SELECT data_quality_label,do_not_train FROM printer_memory_windows
               WHERE id=?""",
            (int(result["memory_window_id"]),),
        ).fetchone()
        self.assertEqual(physical["data_quality_label"], "MISSING_CRITICAL_DATA")
        self.assertEqual(int(physical["do_not_train"]), 1)

    def test_dirty_predecessor_does_not_force_window_1h(self) -> None:
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_15m_campaign_window_memory_row,
        )
        memory_id = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status,
                       memory_quality_label,outcome_label,supporting_context_json
                   ) VALUES (1,1,'WINDOW_15M',?,?,'DIRTY_MEMORY','MISSING_CRITICAL_DATA',1,
                             'WINDOW_CLOSED','DIRTY_MEMORY','DUMP',?)""",
                (
                    _iso(T0),
                    NOW,
                    json.dumps({"e2q_audited": True, "snapshot_id": 1}),
                ),
            ).lastrowid
        )
        bind_precreated_15m_campaign_window_memory_row(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=self.fx.window_id_1,
            memory_window_row_id=memory_id,
            now=NOW,
        )
        other = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status,
                       memory_quality_label
                   ) VALUES (2,2,'WINDOW_15M',?,?,'DIRTY_MEMORY','MISSING_CRITICAL_DATA',1,
                             'WINDOW_CLOSED','DIRTY_MEMORY')""",
                (_iso(T0), NOW),
            ).lastrowid
        )
        bind_precreated_15m_campaign_window_memory_row(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_2,
            token_row_id=2,
            pair_row_id=2,
            campaign_window_id=self.fx.window_id_2,
            memory_window_row_id=other,
            now=NOW,
        )
        persist_15m_campaign_window(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            lifecycle_identity="lifecycle-1",
            memory_window_row_id=memory_id,
            checkpoint_cutoff=NOW,
            window_state="DIRTY",
            now=NOW,
        )
        persist_15m_campaign_window(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_2,
            token_row_id=2,
            pair_row_id=2,
            lifecycle_identity="lifecycle-2",
            memory_window_row_id=other,
            checkpoint_cutoff=NOW,
            window_state="DIRTY",
            now=NOW,
        )
        evaluation = evaluate_selective_1h_for_cycle(
            self.fx.connection,
            db_path=str(self.fx.db),
            campaign_id=CAMPAIGN_ID,
            configuration_id="config-bind-order",
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            campaign_state="RUNNING",
            now=NOW,
        )
        self.assertEqual(evaluation["continue_count"], 0)
        self.assertEqual(
            self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows WHERE window_kind='WINDOW_1H'"
            ).fetchone()[0],
            0,
        )

    def test_terminal_registration_reuses_exact_early_bind(self) -> None:
        from printer_v1.operator_cli.operational_selective_1h import (
            bind_precreated_15m_campaign_window_memory_row,
        )
        memory_id = int(
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                       token_id,pair_id,window_kind,opened_at,closed_at,
                       memory_status,data_quality_label,do_not_train,window_status
                   ) VALUES (1,1,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                             'WINDOW_CLOSED')""",
                (_iso(T0), NOW),
            ).lastrowid
        )
        bind_precreated_15m_campaign_window_memory_row(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            campaign_window_id=self.fx.window_id_1,
            memory_window_row_id=memory_id,
            now=NOW,
        )
        persisted = persist_15m_campaign_window(
            self.fx.connection,
            campaign_id=CAMPAIGN_ID,
            run_id=RUN_ID,
            cycle_id=CYCLE_ID,
            token_slot_id=SLOT_1,
            token_row_id=1,
            pair_row_id=1,
            lifecycle_identity="lifecycle-1",
            memory_window_row_id=memory_id,
            checkpoint_cutoff=NOW,
            window_state="AUDITING",
            now=NOW,
        )
        self.assertEqual(persisted["window_id"], self.fx.window_id_1)
        self.assertEqual(int(persisted["memory_window_row_id"]), memory_id)
        row = self.fx.connection.execute(
            """SELECT window_id,memory_window_row_id,COUNT(*)
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND token_slot_id=? AND window_kind='WINDOW_15M'""",
            (CAMPAIGN_ID, SLOT_1),
        ).fetchone()
        self.assertEqual(str(row["window_id"]), self.fx.window_id_1)
        self.assertEqual(int(row["memory_window_row_id"]), memory_id)
        self.assertEqual(int(row[2]), 1)


if __name__ == "__main__":
    unittest.main()
