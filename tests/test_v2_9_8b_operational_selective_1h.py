"""V2-9.8B operational selective WINDOW_1H — bounded non-live proofs.

Temporary DBs, fixtures, and mocked source boundaries only. No real source
fetching, no authoritative DB mutation, no operational 1h activation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    bind_authoritative_run_id,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.e2y_15m_candidate_set_gate import _build_set_gate
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_ALREADY_EXISTS,
    E2Z_STATUS_BLOCKED,
    E2Z_STATUS_CREATED,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.operational_selective_1h import (
    SELECTIVE_1H_POLICY_VERSION,
    bind_1h_memory_window,
    campaign_window_id_for,
    ensure_authoritative_factory_link,
    evaluate_selective_1h_for_cycle,
    persist_15m_campaign_window,
    should_continue_token,
    summarize_selective_1h_reporting,
)
from printer_v1.scheduler.token_local_continuation import ContinuationVerdict
from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE


T0 = datetime(2026, 7, 28, 0, 0, tzinfo=timezone.utc)
T15 = T0 + timedelta(minutes=15)
T1H = T0 + timedelta(hours=1)
NOW = T15.isoformat()
LOCKED = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _apply_all_migrations(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                   version TEXT PRIMARY KEY,
                   applied_at TEXT NOT NULL DEFAULT (datetime('now'))
               )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for migration in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if migration.name in applied:
                continue
            connection.executescript(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (migration.name,),
            )
        connection.commit()
    finally:
        connection.close()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "b" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class Selective1hFixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "proof.sqlite3"
        _apply_all_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign(
            self.db,
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            configuration={
                "policy": SELECTIVE_1H_POLICY_VERSION,
                "token_capacity": 2,
                "main_window": "WINDOW_15M",
            },
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="proof-1h",
            proof_source_db_identity="proof-source-1h",
            policy_version=SELECTIVE_1H_POLICY_VERSION,
        )
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    selected_token_count,started_at
                ) VALUES ('factory-run-1','RUNNING','WINDOW_15M','PROOF_ONLY',
                    'hash','{}',2,?)""",
                (NOW,),
            )
            for identity in (1, 2):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (identity, f"mint-{identity}"),
                )
                self.connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                    (identity, identity, f"pair-{identity}"),
                )
        create_campaign_run(
            self.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            run_ordinal=1,
            now=NOW,
        )
        ensure_authoritative_factory_link(
            self.connection,
            campaign_run_id="run-1h",
            factory_run_id="factory-run-1",
            now=NOW,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "slot-1",
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "mint-1",
                    "pair_identity": "pair-1",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                },
                {
                    "token_slot_id": "slot-2",
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "mint-2",
                    "pair_identity": "pair-2",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                },
            ),
            now=NOW,
        )
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_factory_campaigns "
                "SET campaign_state='RUNNING' WHERE campaign_id='campaign-1h'"
            )
            self.connection.execute(
                "UPDATE printer_memory_factory_campaign_runs "
                "SET run_state='RUNNING' WHERE run_id='run-1h'"
            )

    def close(self) -> None:
        self.connection.close()
        self.tmp.cleanup()

    def insert_15m_window(
        self,
        *,
        window_id: int,
        token_id: int,
        pair_id: int,
        outcome: str = "SHORT_TERM_PUMP",
        quality: str = "PARTIAL_MEMORY",
        data_quality: str = "CLEAN_DATA",
        do_not_train: int = 0,
        continuity: str = "CONTINUITY_CONTINUOUS",
    ) -> None:
        ctx = {
            "snapshot_id": 9000 + window_id,
            "e2q_audited": True,
            "e2q_audited_by": "lane_e2q",
            "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
            "continuity": {"status": continuity},
            "continuity_status": continuity,
        }
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,outcome_label,do_not_train,
                    supporting_context_json
                ) VALUES (?,?,?,'WINDOW_15M',?,?,?,?, 'WINDOW_CLOSED',?,?,?,?)""",
                (
                    window_id,
                    token_id,
                    pair_id,
                    _iso(T0),
                    _iso(T15),
                    quality,
                    data_quality,
                    quality,
                    outcome,
                    do_not_train,
                    json.dumps(ctx),
                ),
            )

    def insert_close_step(
        self, *, window_id: int, token_id: int, pair_id: int, episode_id: int | None
    ) -> None:
        pipeline = {"e2z_window_results": []}
        if episode_id is not None:
            pipeline["e2z_window_results"].append(
                {
                    "window_id": window_id,
                    "e2z_status": "E2Z_MEMORY_CREATED",
                    "episode_id": episode_id,
                }
            )
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                    run_id,step_key,step_kind,step_status,token_id,pair_id,
                    token_mint,pair_address,tracking_lane,memory_window_id,
                    result_json
                ) VALUES ('factory-run-1',?,?, 'SUCCEEDED',?,?,?,?, 'TRACK_NORMAL',?,?)""",
                (
                    f"close-{token_id}",
                    "WINDOW_CLOSE",
                    token_id,
                    pair_id,
                    f"mint-{token_id}",
                    f"pair-{token_id}",
                    window_id,
                    json.dumps({"memory_pipeline": pipeline, "ok": True}),
                ),
            )

    def insert_episode(self, *, window_id: int, token_id: int, pair_id: int) -> int:
        with self.connection:
            cur = self.connection.execute(
                """INSERT INTO printer_episodes(
                    memory_window_id,token_id,pair_id,episode_kind,
                    episode_status,memory_status,data_quality_label,do_not_train,
                    window_kind,memory_quality_label
                ) VALUES (?,?,?,'WINDOW_15M_CLEAN_MEMORY','COMPLETE','CLEAN_MEMORY',
                    'CLEAN_DATA',0,'WINDOW_15M','CLEAN_MEMORY')""",
                (window_id, token_id, pair_id),
            )
            return int(cur.lastrowid)

    def insert_safety(self, *, window_id: int, token_id: int, pair_id: int, suffix: int) -> int:
        snap = 5000 + suffix
        req = 6000 + suffix
        resp = 7000 + suffix
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_source_requests(
                    id,source_name,request_kind,requested_at,source_status,
                    data_quality_label
                ) VALUES (?,'goplus','SAFETY',?,'COMPLETE','CLEAN_DATA')""",
                (req, NOW),
            )
            self.connection.execute(
                """INSERT INTO printer_source_responses(
                    id,source_request_id,source_name,received_at,source_status,
                    data_quality_label
                ) VALUES (?,?,'goplus',?,'COMPLETE','CLEAN_DATA')""",
                (resp, req, NOW),
            )
            self.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (?,?,?,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (snap, token_id, pair_id, NOW),
            )
            cur = self.connection.execute(
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
                ) VALUES (?,?,?,?,?,?,?,?, 'COMPLETE','CLEAN_DATA','TARGET_MATCH',
                    'SAFETY_EVIDENCE_FRESH',
                    'MINT_AUTHORITY_RENOUNCED','FREEZE_AUTHORITY_DISABLED',
                    'METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
                    'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
                    'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                    'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',
                    1,'[]','[]','[]','{}',1)""",
                (
                    token_id,
                    pair_id,
                    snap,
                    window_id,
                    f"policy-{suffix}",
                    f"mint-{token_id}",
                    f"pair-{token_id}",
                    NOW,
                ),
            )
            return int(cur.lastrowid)

    def prepare_eligible(
        self,
        *,
        token_id: int,
        window_id: int,
        outcome: str = "SHORT_TERM_PUMP",
        promote: bool = True,
    ) -> int | None:
        self.insert_15m_window(
            window_id=window_id,
            token_id=token_id,
            pair_id=token_id,
            outcome=outcome,
        )
        episode_id = None
        if promote:
            episode_id = self.insert_episode(
                window_id=window_id, token_id=token_id, pair_id=token_id
            )
        self.insert_close_step(
            window_id=window_id,
            token_id=token_id,
            pair_id=token_id,
            episode_id=episode_id,
        )
        self.insert_safety(
            window_id=window_id, token_id=token_id, pair_id=token_id, suffix=token_id
        )
        persist_15m_campaign_window(
            self.connection,
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            token_slot_id=f"slot-{token_id}",
            token_row_id=token_id,
            pair_row_id=token_id,
            lifecycle_identity=f"lifecycle-{token_id}",
            memory_window_row_id=window_id,
            checkpoint_cutoff=NOW,
            window_state="AUDITING",
            now=NOW,
        )
        return episode_id

    def evaluate(self) -> dict:
        return evaluate_selective_1h_for_cycle(
            self.connection,
            db_path=str(self.db),
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            now=NOW,
        )

    def locked_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for table in LOCKED:
            out[table] = int(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
        return out


class OperationalSelective1hTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()

    def tearDown(self) -> None:
        self.fx.close()

    def test_authoritative_run_bind_idempotent_and_immutable(self) -> None:
        again = ensure_authoritative_factory_link(
            self.fx.connection,
            campaign_run_id="run-1h",
            factory_run_id="factory-run-1",
        )
        self.assertFalse(again["bound"])
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    selected_token_count,started_at
                ) VALUES ('factory-run-2','RUNNING','WINDOW_15M','PROOF_ONLY',
                    'hash','{}',2,?)""",
                (NOW,),
            )
        with self.assertRaises(CampaignOwnershipError):
            bind_authoritative_run_id(
                self.fx.connection,
                campaign_run_id="run-1h",
                factory_run_id="factory-run-2",
            )

    def test_zero_eligible_tokens_zero_continuation(self) -> None:
        # Both windows exist but ordinary outcomes → STOP, no CONTINUE.
        self.fx.prepare_eligible(token_id=1, window_id=101, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=102, outcome="NO_PUMP")
        before = self.fx.locked_counts()
        result = self.fx.evaluate()
        self.assertEqual(result["continue_count"], 0)
        self.assertEqual(result["stop_count"], 2)
        self.assertFalse(should_continue_token(result, token_id=1))
        self.assertFalse(should_continue_token(result, token_id=2))
        self.assertEqual(self.fx.locked_counts(), before)
        windows_1h = self.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_1H'"
        ).fetchone()[0]
        self.assertEqual(int(windows_1h), 0)

    def test_one_eligible_token_exactly_one_continuation(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=111, outcome="SHORT_TERM_PUMP")
        self.fx.prepare_eligible(token_id=2, window_id=112, outcome="CONSOLIDATION")
        result = self.fx.evaluate()
        self.assertEqual(result["continue_count"], 1)
        self.assertTrue(should_continue_token(result, token_id=1))
        self.assertFalse(should_continue_token(result, token_id=2))
        plans = {p["token_row_id"]: p for p in result["token_plans"]}
        self.assertEqual(
            plans[1]["verdict"], ContinuationVerdict.CONTINUE_TO_WINDOW_1H
        )
        self.assertEqual(
            plans[2]["verdict"], ContinuationVerdict.STOP_AFTER_WINDOW_15M
        )
        self.assertIsNotNone(plans[1]["campaign_window_1h_id"])
        self.assertIsNone(plans[2]["campaign_window_1h_id"])

    def test_two_eligible_tokens_fair_bounded_continuation(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=121, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=122, outcome="SLOW_BLEED")
        result = self.fx.evaluate()
        self.assertEqual(result["continue_count"], 2)
        self.assertTrue(should_continue_token(result, token_id=1))
        self.assertTrue(should_continue_token(result, token_id=2))
        # Fair: both get independent 1h campaign windows; no ranking fields.
        for plan in result["token_plans"]:
            self.assertNotIn("score", plan)
            self.assertNotIn("rank", plan)
            self.assertNotIn("confidence", plan)
            self.assertIsNotNone(plan["campaign_window_1h_id"])

    def test_dirty_ineligible_predecessor_rejected(self) -> None:
        self.fx.prepare_eligible(
            token_id=1, window_id=131, outcome="SHORT_TERM_PUMP", promote=False
        )
        self.fx.prepare_eligible(token_id=2, window_id=132, outcome="CONSOLIDATION")
        result = self.fx.evaluate()
        plans = {p["token_row_id"]: p for p in result["token_plans"]}
        self.assertEqual(plans[1]["verdict"], ContinuationVerdict.BLOCK_CONTINUATION)
        reasons = list(plans[1]["reasons"])
        self.assertTrue(
            "predecessor_memory_not_clean" in reasons
            or "predecessor_evidence_not_eligible" in reasons
            or any("clean" in r or "eligible" in r for r in reasons),
            msg=f"unexpected block reasons: {reasons}",
        )

    def test_authoritative_episode_not_raw_partial_label(self) -> None:
        # Window stays PARTIAL; episode is CLEAN — continuation must see CLEAN.
        self.fx.prepare_eligible(token_id=1, window_id=141, outcome="SHORT_TERM_PUMP")
        self.fx.prepare_eligible(token_id=2, window_id=142, outcome="CONSOLIDATION")
        partial = self.fx.connection.execute(
            "SELECT memory_quality_label FROM printer_memory_windows WHERE id=141"
        ).fetchone()[0]
        self.assertEqual(partial, "PARTIAL_MEMORY")
        result = self.fx.evaluate()
        self.assertTrue(should_continue_token(result, token_id=1))
        self.assertIsNotNone(result["token_plans"][0]["authoritative_episode_id"])

    def test_missing_lineage_fails_closed(self) -> None:
        # Only one slot has a campaign window → evaluation fails closed.
        self.fx.prepare_eligible(token_id=1, window_id=151)
        with self.assertRaises(Exception):
            self.fx.evaluate()

    def test_duplicate_continuation_idempotent(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=161, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=162, outcome="DUMP")
        first = self.fx.evaluate()
        second = self.fx.evaluate()
        self.assertEqual(first["continue_count"], second["continue_count"])
        obj_count = self.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_objects "
            "WHERE object_kind='CONTINUATION_4A'"
        ).fetchone()[0]
        self.assertEqual(int(obj_count), 2)
        self.assertFalse(second["continuation_objects"][0]["created"])
        self.assertFalse(second["continuation_objects"][1]["created"])

    def test_separate_1h_periods_remain_distinct(self) -> None:
        id_a = campaign_window_id_for(
            campaign_id="c",
            run_id="r",
            cycle_id="y",
            token_slot_id="s",
            window_kind="WINDOW_1H",
            period_key="101",
        )
        id_b = campaign_window_id_for(
            campaign_id="c",
            run_id="r",
            cycle_id="y",
            token_slot_id="s",
            window_kind="WINDOW_1H",
            period_key="202",
        )
        self.assertNotEqual(id_a, id_b)
        gate = _build_set_gate(
            [
                {
                    "id": 1,
                    "window_kind": "WINDOW_1H",
                    "snapshot_start_id": 10,
                    "window_status": "WINDOW_CLOSED",
                    "data_quality_label": "CLEAN_DATA",
                    "memory_status": "PARTIAL_MEMORY",
                    "memory_quality_label": "PARTIAL_MEMORY",
                    "do_not_train": False,
                    "e2q_audited": True,
                    "parsed_snapshot_link": 10,
                    "review_only": True,
                    "creates_clean_memory": False,
                    "activates_retrieval": False,
                    "activates_paper_decision": False,
                    "unlocks_buy": False,
                    "token_id": 1,
                    "pair_id": 1,
                },
                {
                    "id": 2,
                    "window_kind": "WINDOW_1H",
                    "snapshot_start_id": 20,
                    "window_status": "WINDOW_CLOSED",
                    "data_quality_label": "CLEAN_DATA",
                    "memory_status": "PARTIAL_MEMORY",
                    "memory_quality_label": "PARTIAL_MEMORY",
                    "do_not_train": False,
                    "e2q_audited": True,
                    "parsed_snapshot_link": 20,
                    "review_only": True,
                    "creates_clean_memory": False,
                    "activates_retrieval": False,
                    "activates_paper_decision": False,
                    "unlocks_buy": False,
                    "token_id": 1,
                    "pair_id": 1,
                },
            ]
        )
        self.assertTrue(gate["all_same_window_kind"])
        self.assertTrue(gate["distinct_period_identities"])
        self.assertTrue(gate["period_awareness"]["all_window_1h"])

    def test_e2z_promotes_clean_1h_once(self) -> None:
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (1,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (_iso(T0),),
            )
            self.fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (2,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (_iso(T1H),),
            )
            ctx = {
                "snapshot_id": 2,
                "e2q_audited": True,
                "e2q_audited_by": "lane_e2q",
                "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                "snapshot_ids": [1, 2],
            }
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,do_not_train,supporting_context_json
                ) VALUES (201,1,1,'WINDOW_1H',?,?,?,?,1,2,'PARTIAL_MEMORY',
                    'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY',0,?)""",
                (
                    _iso(T0),
                    _iso(T1H),
                    _iso(T0),
                    _iso(T1H),
                    json.dumps(ctx),
                ),
            )
        first = create_clean_memory_from_window(
            self.fx.db, 201, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
        second = create_clean_memory_from_window(
            self.fx.db, 201, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
        self.assertEqual(first["episode_id"], second["episode_id"])
        kind = self.fx.connection.execute(
            "SELECT episode_kind, memory_status FROM printer_episodes WHERE id=?",
            (first["episode_id"],),
        ).fetchone()
        self.assertEqual(kind[0], "WINDOW_1H_CLEAN_MEMORY")
        self.assertEqual(kind[1], "CLEAN_MEMORY")

    def test_dirty_1h_remains_unpromoted(self) -> None:
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,do_not_train,supporting_context_json
                ) VALUES (202,1,1,'WINDOW_1H',?,?,'DIRTY_MEMORY','DIRTY_DATA',
                    'WINDOW_CLOSED','DIRTY_MEMORY',1,?)""",
                (
                    _iso(T0),
                    _iso(T1H),
                    json.dumps({"snapshot_id": 1, "e2q_audited": True}),
                ),
            )
        blocked = create_clean_memory_from_window(
            self.fx.db, 202, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(blocked["e2z_status"], E2Z_STATUS_BLOCKED)
        episodes = self.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=202"
        ).fetchone()[0]
        self.assertEqual(int(episodes), 0)

    def test_5m_cannot_satisfy_1h_or_e2z(self) -> None:
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,do_not_train,supporting_context_json
                ) VALUES (203,1,1,'WINDOW_5M_MICRO_EVENT',?,?,'PARTIAL_MEMORY',
                    'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY',0,?)""",
                (
                    _iso(T0),
                    _iso(T0 + timedelta(minutes=5)),
                    json.dumps({"snapshot_id": 1, "e2q_audited": True}),
                ),
            )
        blocked = create_clean_memory_from_window(
            self.fx.db, 203, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(blocked["e2z_status"], E2Z_STATUS_BLOCKED)
        self.assertTrue(
            any("window_kind" in r for r in blocked.get("blocked_reasons", []))
        )

    def test_reporting_contains_linkage_and_windows(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=171, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=172, outcome="DUMP")
        self.fx.evaluate()
        report = summarize_selective_1h_reporting(
            self.fx.connection, campaign_id="campaign-1h", run_id="run-1h"
        )
        self.assertEqual(report["authoritative_run_id"], "factory-run-1")
        self.assertGreaterEqual(report["window_counts_by_kind"]["WINDOW_15M"], 2)
        self.assertEqual(report["window_counts_by_kind"]["WINDOW_1H"], 2)
        self.assertEqual(len(report["continuation_objects"]), 2)
        self.assertFalse(report["locked_downstream"]["retrieval_activated"])
        self.assertFalse(report["locked_downstream"]["window_4h_enabled"])

    def test_bind_1h_memory_and_terminalize(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=181, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=182, outcome="DUMP")
        result = self.fx.evaluate()
        plan = next(p for p in result["token_plans"] if p["token_row_id"] == 1)
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,do_not_train
                ) VALUES (281,1,1,'WINDOW_1H',?,?,'PARTIAL_MEMORY','CLEAN_DATA',
                    'WINDOW_CLOSED','PARTIAL_MEMORY',0)""",
                (_iso(T0), _iso(T1H)),
            )
        bound = bind_1h_memory_window(
            self.fx.connection,
            campaign_window_1h_id=plan["campaign_window_1h_id"],
            memory_window_row_id=281,
            terminal_state="CLEAN_PROMOTED",
            terminal_cause="1H_CLEAN_PROMOTED",
            now=_iso(T1H),
        )
        self.assertEqual(bound["window_state"], "CLEAN_PROMOTED")
        # Idempotent re-bind of same row.
        again = bind_1h_memory_window(
            self.fx.connection,
            campaign_window_1h_id=plan["campaign_window_1h_id"],
            memory_window_row_id=281,
            terminal_state="CLEAN_PROMOTED",
            terminal_cause="1H_CLEAN_PROMOTED",
            now=_iso(T1H),
        )
        self.assertEqual(again["memory_window_row_id"], 281)

    def test_production_defaults_lock_1h(self) -> None:
        from printer_v1.operator_cli.operational_memory_factory_command import (
            LOCKED_WINDOWS,
            MAIN_WINDOW,
            TOTAL_DURATION_SECONDS,
        )
        self.assertIn("WINDOW_1H", LOCKED_WINDOWS)
        self.assertIn("WINDOW_4H", LOCKED_WINDOWS)
        self.assertEqual(MAIN_WINDOW, "WINDOW_15M")
        self.assertEqual(TOTAL_DURATION_SECONDS, 1200)

    def test_selective_two_token_factory_ceilings_are_cadence_derived(self) -> None:
        from printer_v1.operator_cli import one_command_15m_factory as factory

        self.assertEqual(factory._MAX_SNAPSHOTS_PER_TOKEN, 16)
        self.assertEqual(factory._continuation_expected_snapshots("TRACK_FAST"), 24)
        self.assertEqual(factory._SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN, 45)
        self.assertEqual(factory._SELECTIVE_1H_MAX_REQUESTS_RUN, 92)
        self.assertEqual(factory._SELECTIVE_1H_MAX_SCHEDULER_ROWS, 82)
        self.assertTrue(
            factory._selective_1h_lifecycle(
                {
                    "selective_1h_continuation": True,
                    "continuous_four_hour": False,
                }
            )
        )

    def test_selective_factory_enforces_source_and_scheduler_ceilings(self) -> None:
        from printer_v1.operator_cli import one_command_15m_factory as factory

        config = {
            "continuous_first_hour": True,
            "selective_1h_continuation": True,
        }
        step = {
            "step_kind": "CONTINUATION_SNAPSHOT",
            "step_key": "t1_1h_snapshot_999",
        }
        with (
            patch.object(factory, "_load_run_config", return_value=config),
            patch.object(
                factory,
                "_run_request_count",
                return_value=factory._SELECTIVE_1H_MAX_REQUESTS_RUN,
            ),
            patch.object(factory, "_token_request_count", return_value=0),
        ):
            with self.assertRaises(factory._GlobalStop):
                factory._enforce_budgets_before_step(object(), "run", step)

        with (
            patch.object(factory, "_load_run_config", return_value=config),
            patch.object(
                factory,
                "_run_step_job_count",
                return_value=factory._SELECTIVE_1H_MAX_SCHEDULER_ROWS - 2,
            ),
        ):
            with self.assertRaises(factory._GlobalStop):
                factory._insert_step_and_job(
                    object(),
                    run_id="run",
                    target={"tracking_lane": "TRACK_FAST"},
                    step_key="t1_1h_snapshot_999",
                    step_kind="CONTINUATION_SNAPSHOT",
                    scheduled_for=T0,
                )

    def test_no_retry_restart_successor_fields(self) -> None:
        self.fx.prepare_eligible(token_id=1, window_id=191, outcome="DUMP")
        self.fx.prepare_eligible(token_id=2, window_id=192, outcome="DUMP")
        result = self.fx.evaluate()
        payload = result["continuation_objects"][0]["payload"]
        self.assertNotIn("retry", payload)
        self.assertNotIn("restart", payload)
        self.assertNotIn("successor_campaign", payload)
        self.assertFalse(payload["locked_downstream"]["buy_sell_hold"])


if __name__ == "__main__":
    unittest.main()
