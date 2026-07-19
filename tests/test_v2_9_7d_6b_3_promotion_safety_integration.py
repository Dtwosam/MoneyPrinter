"""Focused V2-9.7D.6B.3 read-only authority adapter tests."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_authority_adapters import (
    CampaignAuthorityAdapterError,
    build_4a_authority_facts,
    load_authoritative_checkpoint_safety,
    load_authoritative_promotion_outcome,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_immutable_object,
    persist_window,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    ALREADY_EXISTS_IDEMPOTENT,
    CLEAN_PROMOTED,
    DIRTY_OR_BLOCKED,
    NO_PROMOTION,
)
from printer_v1.safety.composite import (
    SAFETY_CONTEXT_ACCEPTABLE,
    SAFETY_CONTEXT_BLOCKED,
    SAFETY_CONTEXT_UNKNOWN,
)
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationLearningNeed,
    ContinuationVerdict,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)


CUTOFF = "2026-07-19T00:15:00+00:00"
CAPTURED = "2026-07-19T00:10:00+00:00"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": CUTOFF,
    }


class PromotionSafetyIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.db = Path(self.temp.name) / "adapter.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="adapter-fixture",
            proof_source_db_identity="adapter-source",
            policy_version="v2-9.7d",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._seed_graph()

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    @staticmethod
    def _slot(ordinal: int) -> dict[str, object]:
        return {
            "token_slot_id": f"slot-{ordinal}",
            "slot_ordinal": ordinal,
            "token_identity": f"token-{ordinal}",
            "token_row_id": ordinal,
            "mint_identity": f"mint-{ordinal}",
            "pair_identity": f"pair-{ordinal}",
            "pair_row_id": ordinal,
            "lifecycle_identity": f"lifecycle-{ordinal}",
        }

    def _seed_graph(self) -> None:
        with self.connection:
            for identity in (1, 2):
                self.connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (identity, f"mint-{identity}"),
                )
                self.connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                    (identity, identity, f"pair-{identity}"),
                )
            self.connection.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    selected_token_count,started_at
                ) VALUES ('authority-run','COMPLETED','WINDOW_15M','PROOF_ONLY',
                    'hash','{}',2,?)""",
                (CAPTURED,),
            )
            self.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label
                ) VALUES (101,1,1,'WINDOW_15M',?,?,'PARTIAL_MEMORY',
                    'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY')""",
                (CAPTURED, CUTOFF),
            )
        create_campaign_run(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            run_ordinal=1,
            authoritative_run_id="authority-run",
            now=CAPTURED,
        )
        create_cycle_with_two_slots(
            self.connection,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            cycle_ordinal=1,
            slots=(self._slot(1), self._slot(2)),
            now=CAPTURED,
        )
        persist_window(
            self.connection,
            window_id="window-15m",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            token_row_id=1,
            pair_row_id=1,
            window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-1",
            memory_window_row_id=101,
            checkpoint_cutoff=CUTOFF,
            now=CAPTURED,
        )

    def _insert_close(self, *, status: str = "SUCCEEDED", e2z: str | None = None) -> int:
        pipeline = {"e2z_window_results": []}
        if e2z:
            pipeline["e2z_window_results"].append(
                {"window_id": 101, "e2z_status": e2z}
            )
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO printer_memory_factory_run_steps(
                    run_id,step_key,step_kind,step_status,token_id,pair_id,
                    token_mint,pair_address,tracking_lane,memory_window_id,
                    result_json
                ) VALUES ('authority-run','close-1','WINDOW_CLOSE',?,1,1,
                    'mint-1','pair-1','TRACK_FAST',101,?)""",
                (status, json.dumps({"memory_pipeline": pipeline})),
            )
        return int(cursor.lastrowid)

    def _insert_episode(self) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """INSERT INTO printer_episodes(
                    memory_window_id,token_id,pair_id,episode_kind,
                    episode_status,memory_status,data_quality_label,do_not_train,
                    window_kind,memory_quality_label
                ) VALUES (101,1,1,'MEMORY_WINDOW','COMPLETE','CLEAN_MEMORY',
                    'CLEAN_DATA',0,'WINDOW_15M','CLEAN_MEMORY')"""
            )
        return int(cursor.lastrowid)

    def _promotion(self) -> dict[str, object]:
        return load_authoritative_promotion_outcome(
            self.db,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            window_id="window-15m",
        )

    def _ensure_window(self, kind: str) -> tuple[str, int]:
        if kind == "WINDOW_15M":
            return "window-15m", 101
        if kind == "WINDOW_1H":
            window_id, row_id, predecessor = "window-1h", 102, "window-15m"
        else:
            self._ensure_window("WINDOW_1H")
            window_id, row_id, predecessor = "window-4h", 103, "window-1h"
        exists = self.connection.execute(
            "SELECT 1 FROM printer_memory_windows WHERE id=?", (row_id,)
        ).fetchone()
        if not exists:
            with self.connection:
                self.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label
                    ) VALUES (?,?,?,?,?,?,'PARTIAL_MEMORY','CLEAN_DATA',
                        'WINDOW_CLOSED','PARTIAL_MEMORY')""",
                    (row_id, 1, 1, kind, CAPTURED, CUTOFF),
                )
            persist_window(
                self.connection,
                window_id=window_id,
                campaign_id="campaign-a",
                run_id="run-a",
                cycle_id="cycle-a",
                token_slot_id="slot-1",
                token_row_id=1,
                pair_row_id=1,
                window_kind=kind,
                root_15m_lifecycle_identity="lifecycle-1",
                predecessor_window_id=predecessor,
                memory_window_row_id=row_id,
                checkpoint_cutoff=CUTOFF,
                now=CAPTURED,
            )
        return window_id, row_id

    def _insert_safety(
        self,
        *,
        suffix: int,
        window_row_id: int,
        captured_at: str = CAPTURED,
        freshness: str = "SAFETY_EVIDENCE_FRESH",
        target_status: str = "TARGET_MATCH",
        pair_address: str = "pair-1",
    ) -> int:
        request_id = 100 + suffix
        response_id = 200 + suffix
        snapshot_id = 300 + suffix
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_source_requests(
                    id,source_name,request_kind,requested_at,source_status,
                    data_quality_label
                ) VALUES (?,'goplus','SAFETY',?,'COMPLETE','CLEAN_DATA')""",
                (request_id, captured_at),
            )
            self.connection.execute(
                """INSERT INTO printer_source_responses(
                    id,source_request_id,source_name,received_at,source_status,
                    data_quality_label
                ) VALUES (?,?,'goplus',?,'COMPLETE','CLEAN_DATA')""",
                (response_id, request_id, captured_at),
            )
            self.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (?,1,1,?,'TRACK_FAST','TOKEN','COMPLETE','CLEAN_DATA')""",
                (snapshot_id, captured_at),
            )
            cursor = self.connection.execute(
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
                ) VALUES (1,1,?,?,?,'mint-1',?,?,'COMPLETE','CLEAN_DATA',?,?,
                    'MINT_AUTHORITY_RENOUNCED','FREEZE_AUTHORITY_DISABLED',
                    'METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
                    'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
                    'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                    'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',
                    1,'[]','[]','["liquidity_lock_or_burn_label"]','{}',1)""",
                (
                    snapshot_id, window_row_id, f"policy-{suffix}", pair_address,
                    captured_at, target_status, freshness,
                ),
            )
            composite_id = int(cursor.lastrowid)
            self.connection.execute(
                """INSERT INTO printer_safety_evidence_contributions(
                    composite_id,source_name,evidence_category,source_request_id,
                    source_response_id,captured_at,freshness_label,token_mint,
                    pair_address,fields_supplied_json,source_status,
                    data_quality_label,target_status
                ) VALUES (?,'goplus','TOKEN_SAFETY',?,?,?,?,'mint-1',?,'{}',
                    'COMPLETE','CLEAN_DATA',?)""",
                (
                    composite_id, request_id, response_id, captured_at,
                    freshness, pair_address, target_status,
                ),
            )
        return composite_id

    def _checkpoint(
        self, *, object_id: str, window_id: str, composite_id: int | None,
    ) -> None:
        persist_immutable_object(
            self.connection,
            object_id=object_id,
            object_kind="CHECKPOINT_5A",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            window_id=window_id,
            payload={"checkpoint_id": object_id},
            safety_composite_id=composite_id,
            now=CAPTURED,
        )

    def _safety(self, *, window_id: str, checkpoint_id: str) -> dict[str, object]:
        return load_authoritative_checkpoint_safety(
            self.db,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            window_id=window_id,
            checkpoint_object_id=checkpoint_id,
        )

    def test_b1_clean_and_idempotent_preserve_episode_and_close_step(self) -> None:
        close_id = self._insert_close(e2z="E2Z_MEMORY_CREATED")
        episode_id = self._insert_episode()
        created = self._promotion()
        self.assertEqual(created["promotion_status"], CLEAN_PROMOTED)
        self.assertEqual(created["authoritative_episode_id"], episode_id)
        self.assertEqual(created["close_step_id"], close_id)
        self.assertEqual(created["authoritative_run_id"], "authority-run")

        with self.connection:
            self.connection.execute(
                """UPDATE printer_memory_factory_run_steps SET result_json=?
                   WHERE id=?""",
                (
                    json.dumps({"memory_pipeline": {"e2z_window_results": [
                        {"window_id": 101, "e2z_status": "E2Z_ALREADY_EXISTS"}
                    ]}}),
                    close_id,
                ),
            )
        idempotent = self._promotion()
        self.assertEqual(
            idempotent["promotion_status"], ALREADY_EXISTS_IDEMPOTENT
        )
        self.assertEqual(idempotent["authoritative_episode_id"], episode_id)

    def test_b1_dirty_blocked_no_promotion_and_isolation_fail_closed(self) -> None:
        self._insert_close()
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_windows SET memory_quality_label='DIRTY_MEMORY' WHERE id=101"
            )
        self.assertEqual(self._promotion()["promotion_status"], DIRTY_OR_BLOCKED)
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_windows SET memory_quality_label='PARTIAL_MEMORY' WHERE id=101"
            )
        self.assertEqual(self._promotion()["promotion_status"], NO_PROMOTION)
        with self.connection:
            self.connection.execute(
                "UPDATE printer_memory_factory_run_steps SET step_status='FAILED' WHERE step_key='close-1'"
            )
        self.assertEqual(self._promotion()["promotion_status"], DIRTY_OR_BLOCKED)
        with self.assertRaisesRegex(CampaignAuthorityAdapterError, "ownership mismatch"):
            load_authoritative_promotion_outcome(
                self.db, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-foreign", token_slot_id="slot-1",
                window_id="window-15m",
            )

    def test_b1_ignores_support_and_5a_to_5c_claims(self) -> None:
        self._insert_close()
        persist_immutable_object(
            self.connection,
            object_id="trajectory-claim",
            object_kind="TRAJECTORY_5A",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            window_id="window-15m",
            payload={"promotion_status": "CLEAN_PROMOTED"},
            now=CAPTURED,
        )
        self.assertEqual(self._promotion()["promotion_status"], NO_PROMOTION)
        with self.connection:
            self.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,memory_status,
                    data_quality_label
                ) VALUES (104,1,1,'WINDOW_5M_MICRO_EVENT',?,'PARTIAL_MEMORY',
                    'CLEAN_DATA')""",
                (CAPTURED,),
            )
        persist_window(
            self.connection,
            window_id="window-5m",
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            token_row_id=1,
            pair_row_id=1,
            window_kind="WINDOW_5M_MICRO_EVENT",
            root_15m_lifecycle_identity="lifecycle-1",
            containing_main_window_id="window-15m",
            memory_window_row_id=104,
            checkpoint_cutoff=CUTOFF,
            now=CAPTURED,
        )
        with self.assertRaisesRegex(CampaignAuthorityAdapterError, "main window"):
            load_authoritative_promotion_outcome(
                self.db, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", token_slot_id="slot-1",
                window_id="window-5m",
            )

    def test_b2_preserves_raw_and_effective_safety_for_all_main_windows(self) -> None:
        for suffix, kind in enumerate(
            ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H"), start=1
        ):
            with self.subTest(kind=kind):
                window_id, row_id = self._ensure_window(kind)
                composite_id = self._insert_safety(
                    suffix=suffix, window_row_id=row_id
                )
                checkpoint_id = f"checkpoint-{suffix}"
                self._checkpoint(
                    object_id=checkpoint_id,
                    window_id=window_id,
                    composite_id=composite_id,
                )
                result = self._safety(
                    window_id=window_id, checkpoint_id=checkpoint_id
                )
                self.assertTrue(result["gate_accepted"])
                self.assertEqual(
                    result["effective_safety_context"][
                        "effective_safety_context_result"
                    ],
                    SAFETY_CONTEXT_ACCEPTABLE,
                )
                self.assertEqual(
                    result["raw_composite"]["safety_context_label"],
                    "SAFETY_UNKNOWN",
                )
                self.assertEqual(
                    result["raw_composite"]["safety_contract_label"],
                    "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
                )
                self.assertEqual(result["source_traces"][0]["source_name"], "goplus")

    def test_b2_missing_stale_and_mismatched_evidence_fail_closed(self) -> None:
        persist_immutable_object(
            self.connection,
            object_id="manipulation-says-safe",
            object_kind="MANIPULATION_CONTEXT_5B",
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            run_id="run-a",
            cycle_id="cycle-a",
            token_slot_id="slot-1",
            window_id="window-15m",
            payload={"safety_context_result": "SAFETY_CONTEXT_ACCEPTABLE"},
            now=CAPTURED,
        )
        missing = self._safety(
            window_id="window-15m", checkpoint_id="manipulation-says-safe"
        )
        self.assertIsNone(missing["gate_accepted"])
        self.assertEqual(
            missing["effective_safety_context"]["effective_safety_context_result"],
            SAFETY_CONTEXT_UNKNOWN,
        )

        stale_id = self._insert_safety(
            suffix=10,
            window_row_id=101,
            captured_at="2026-07-18T00:00:00+00:00",
            freshness="SAFETY_EVIDENCE_STALE",
        )
        self._checkpoint(
            object_id="checkpoint-stale",
            window_id="window-15m",
            composite_id=stale_id,
        )
        stale = self._safety(
            window_id="window-15m", checkpoint_id="checkpoint-stale"
        )
        self.assertFalse(stale["gate_accepted"])
        self.assertEqual(
            stale["effective_safety_context"]["effective_safety_context_result"],
            SAFETY_CONTEXT_BLOCKED,
        )

        mismatch_id = self._insert_safety(
            suffix=11,
            window_row_id=101,
            target_status="TARGET_MISMATCH",
            pair_address="foreign-pair",
        )
        self._checkpoint(
            object_id="checkpoint-mismatch",
            window_id="window-15m",
            composite_id=mismatch_id,
        )
        mismatch = self._safety(
            window_id="window-15m", checkpoint_id="checkpoint-mismatch"
        )
        self.assertFalse(mismatch["gate_accepted"])
        self.assertIn("safety_target_identity_mismatch", mismatch["reasons"])

    def test_4a_uses_only_adapter_authority_and_adapters_create_no_writes(self) -> None:
        self._insert_close(e2z="E2Z_MEMORY_CREATED")
        self._insert_episode()
        composite_id = self._insert_safety(suffix=20, window_row_id=101)
        self._checkpoint(
            object_id="checkpoint-authority",
            window_id="window-15m",
            composite_id=composite_id,
        )
        database_hash = _hash(self.db)
        promotion = self._promotion()
        safety = self._safety(
            window_id="window-15m", checkpoint_id="checkpoint-authority"
        )
        facts = build_4a_authority_facts(promotion, safety)
        self.assertEqual(facts["authority_sources"], ("B.1", "B.2"))
        self.assertTrue(facts["predecessor_evidence_eligible"])
        self.assertEqual(facts["safety_context_result"], SAFETY_CONTEXT_ACCEPTABLE)
        with self.assertRaisesRegex(CampaignAuthorityAdapterError, "not B.1"):
            build_4a_authority_facts(
                {**promotion, "authority": "MANIPULATION_CONTEXT_5B"}, safety
            )

        def token(slot: int) -> TokenContinuationInput:
            expected = ExpectedTokenContinuationIdentity(
                token_slot_id=f"slot-{slot}", token_id=f"token-{slot}",
                mint_id=f"mint-{slot}", pair_id=f"pair-{slot}",
                lifecycle_id=f"lifecycle-{slot}",
                predecessor_window_id=f"window-{slot}",
            )
            return TokenContinuationInput(
                campaign_id="campaign-a", configuration_id="configuration-a",
                token_slot_id=expected.token_slot_id, token_id=expected.token_id,
                mint_id=expected.mint_id, pair_id=expected.pair_id,
                lifecycle_id=expected.lifecycle_id,
                predecessor_window_id=expected.predecessor_window_id,
                expected_identity=expected,
                predecessor_window_kind="WINDOW_15M",
                successor_window_kind="WINDOW_1H",
                predecessor_window_status="WINDOW_CLOSED",
                predecessor_memory_quality=facts["predecessor_memory_quality"],
                predecessor_data_quality="CLEAN_DATA",
                predecessor_do_not_train=False,
                predecessor_evidence_eligible=facts["predecessor_evidence_eligible"],
                predecessor_complete=True,
                freshness_within_contract=True,
                governed_provenance_traceable=True,
                safety_context_present=facts["safety_context_present"],
                safety_context_result=facts["safety_context_result"],
                continuity_status="CONTINUITY_CONTINUOUS",
                learning_need=ContinuationLearningNeed.COVERAGE,
                token_budget_available=True,
                token_state="TRACK_FAST",
            )

        results = evaluate_token_local_continuations(
            campaign=CampaignContinuationContext(
                campaign_id="campaign-a", configuration_id="configuration-a"
            ),
            tokens=(token(1), token(2)),
        )
        self.assertTrue(all(
            result.verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_1H
            for result in results
        ))
        self.assertEqual(_hash(self.db), database_hash)
        locked = (
            "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
            "printer_paper_decisions", "printer_paper_positions",
            "printer_paper_trade_events", "printer_paper_trade_audits",
            "printer_paper_audit_reports",
        )
        read_connection = sqlite3.connect(self.db)
        try:
            for table in locked:
                self.assertEqual(
                    read_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                    table,
                )
        finally:
            read_connection.close()


if __name__ == "__main__":
    unittest.main()
