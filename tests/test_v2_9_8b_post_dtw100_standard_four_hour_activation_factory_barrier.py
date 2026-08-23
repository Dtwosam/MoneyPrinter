from __future__ import annotations

import inspect
import json
import sqlite3
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli import one_token_4h_runtime as four
from printer_v1.operator_cli import operational_standard_4h as standard
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from printer_v1.operator_cli.operational_database_target_binding import (
    PRODUCTION_AUTHORITATIVE,
    build_operational_database_target_binding,
)
from tests import test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning as planning_fixture
from tests.test_v2_9_8b_operational_selective_1h import T1H, _iso


class StandardFourHourActivationFactoryBarrierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx, self.candidates = (
            planning_fixture.StandardFourHourCampaignPlanningTests()._prepared()
        )
        self.fx.connection.execute(
            "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id='factory-run-1'",
            (json.dumps({
                "standard_four_hour_campaign": True,
                "campaign_id": "campaign-1h",
                "campaign_run_id": "run-1h",
                "cycle_id": "cycle-1h",
            }, sort_keys=True),),
        )
        self.fx.connection.execute(
            "UPDATE printer_memory_factory_campaign_cycles SET cycle_state='TRACKING' "
            "WHERE cycle_id='cycle-1h'"
        )
        self._attach_authoritative_clean_fingerprint(self.candidates[0])
        self._attach_authoritative_clean_fingerprint(self.candidates[1])
        self._attach_acceptable_safety(1, self.candidates[0])
        self._attach_acceptable_safety(2, self.candidates[1])
        self.fx.connection.commit()
        acquire_campaign_supervision(
            self.fx.db,
            lock_path=self.fx.db.with_suffix(".lease.json"),
            supervision_id="lane3-supervision",
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            owner_id="lane3-owner",
            lease_seconds=3600,
        )
        self.binding = build_operational_database_target_binding(
            target_kind=PRODUCTION_AUTHORITATIVE,
            resolved_db_path=self.fx.db,
            authorized_pre_mutation_sha256="a" * 64,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
            authorization_id="lane3-authorization",
            authorization_marker_sha256="b" * 64,
            application_marker_sha256="c" * 64,
            execution_id="lane3-execution",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            configuration_id="config-1h",
            authorization_consumed_once=True,
            invocation_count=1,
            allowed_invocation_count=1,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
        )

    def tearDown(self) -> None:
        self.fx.close()

    def _attach_authoritative_clean_fingerprint(self, candidate: dict[str, object]) -> int:
        connection = self.fx.connection
        memory_window_id = int(candidate["memory_window_1h_id"])
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        rows = connection.execute(
            """SELECT id FROM printer_episodes
               WHERE memory_window_id=? AND token_id=? AND pair_id=?
                 AND episode_status='COMPLETE' AND memory_status='CLEAN_MEMORY'
                 AND data_quality_label='CLEAN_DATA' AND do_not_train=0
                 AND window_kind='WINDOW_1H' AND memory_quality_label='CLEAN_MEMORY'
               ORDER BY id""",
            (memory_window_id, token_id, pair_id),
        ).fetchall()
        self.assertEqual(len(rows), 1)
        episode_id = int(rows[0][0])
        payload = {
            "episode_id": episode_id,
            "window_id": memory_window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "window_kind": "WINDOW_1H",
        }
        cursor = connection.execute(
            """INSERT INTO printer_memory_fingerprints(
                episode_id,fingerprint_kind,fingerprint_payload_json,
                memory_status,data_quality_label,do_not_train
            ) VALUES (?,'STATIC_CONDITION_SUMMARY',?,'CLEAN_MEMORY','CLEAN_DATA',0)""",
            (episode_id, json.dumps(payload, sort_keys=True)),
        )
        return int(cursor.lastrowid)

    def _attach_acceptable_safety(self, ordinal: int, candidate: dict[str, object]) -> int:
        connection = self.fx.connection
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        mint = str(candidate["mint_identity"])
        pair = str(candidate["pair_identity"])
        memory_window_id = int(candidate["memory_window_1h_id"])
        snapshot_id = 12011 if ordinal == 1 else 12021
        captured_at = _iso(T1H)
        request_id = 9100 + ordinal
        response_id = 9200 + ordinal
        connection.execute(
            """INSERT INTO printer_source_requests(
                id,source_name,request_kind,requested_at,source_status,data_quality_label
            ) VALUES (?,'goplus','SAFETY',?,'COMPLETE','CLEAN_DATA')""",
            (request_id, captured_at),
        )
        connection.execute(
            """INSERT INTO printer_source_responses(
                id,source_request_id,source_name,received_at,source_status,data_quality_label
            ) VALUES (?,?,'goplus',?,'COMPLETE','CLEAN_DATA')""",
            (response_id, request_id, captured_at),
        )
        cursor = connection.execute(
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
            ) VALUES (?,?,?,?,? ,?,?,?,'COMPLETE','CLEAN_DATA','TARGET_MATCH',
                'SAFETY_EVIDENCE_FRESH','MINT_AUTHORITY_RENOUNCED',
                'FREEZE_AUTHORITY_DISABLED','METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
                'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
                'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
                'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',1,
                '[]','[]','["liquidity_lock_or_burn_label"]','{}',1)""",
            (
                token_id,
                pair_id,
                snapshot_id,
                memory_window_id,
                f"standard-4h-policy-{ordinal}",
                mint,
                pair,
                captured_at,
            ),
        )
        composite_id = int(cursor.lastrowid)
        connection.execute(
            """INSERT INTO printer_safety_evidence_contributions(
                composite_id,source_name,evidence_category,source_request_id,
                source_response_id,captured_at,freshness_label,token_mint,
                pair_address,fields_supplied_json,source_status,
                data_quality_label,target_status
            ) VALUES (?,'goplus','TOKEN_SAFETY',?,?,?,'SAFETY_EVIDENCE_FRESH',
                ?,?,'{}','COMPLETE','CLEAN_DATA','TARGET_MATCH')""",
            (composite_id, request_id, response_id, captured_at, mint, pair),
        )
        row = connection.execute(
            "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
            (memory_window_id,),
        ).fetchone()
        context = json.loads(str(row[0] or "{}")) if row is not None else {}
        overlays = dict(context.get("memory_build_evidence_overlays") or {})
        overlays["safety_composite_id"] = composite_id
        context["memory_build_evidence_overlays"] = overlays
        context["continuity"] = {
            "stage": "15M_TO_1H",
            "continuity_status": "CONTINUITY_CONTINUOUS",
            "do_not_train": False,
            "can_be_quality_memory": True,
            "reasons": [],
            "details": {},
        }
        connection.execute(
            "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
            (json.dumps(context, sort_keys=True), memory_window_id),
        )
        return composite_id

    def _barrier(self):
        return standard.run_standard_four_hour_campaign_barrier(
            self.fx.connection,
            db_path=self.fx.db,
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            operational_db_binding=self.binding,
            canonical_authoritative_db_path=self.fx.db,
            cancellation_probe=lambda: None,
            now=_iso(T1H),
        )

    def _long_counts(self) -> tuple[int, int, int]:
        connection = self.fx.connection
        windows = int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0])
        steps = int(connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE step_kind LIKE 'LONG_CONTINUATION_%'"
        ).fetchone()[0])
        manifests = int(connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_standard_4h_progression_tokens
               WHERE token_disposition <> 'WAITING_FOR_PREDECESSOR'"""
        ).fetchone()[0])
        return windows, steps, manifests

    def test_first_successful_close_waits_for_peer_without_four_hour_mutation(self) -> None:
        self.fx.connection.execute(
            """UPDATE printer_memory_factory_run_steps SET step_status='RUNNING'
               WHERE run_id='factory-run-1' AND token_id=2
                 AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')"""
        )
        self.fx.connection.commit()
        before = self._long_counts()
        result = self._barrier()
        self.assertFalse(result["barrier_reached"])
        self.assertEqual(result["status"], "AWAITING_PEER_FIRST_HOUR_CLOSE")
        self.assertEqual(self._long_counts(), before)
        self.assertEqual(before, (0, 0, 0))

    def test_second_successful_close_releases_both_eligible_plan_once(self) -> None:
        result = self._barrier()
        self.assertTrue(result["barrier_reached"])
        self.assertEqual(result["eligible_token_slot_ids"], ["slot-1", "slot-2"])
        self.assertEqual(result["continuation_count"], 2)
        self.assertEqual(result["subset_budget"]["request_ceiling"], 190)
        self.assertEqual(result["subset_budget"]["scheduler_ceiling"], 174)
        self.assertEqual(self._long_counts(), (2, 98, 2))
        replay = self._barrier()
        self.assertTrue(replay["barrier_reached"])
        self.assertEqual(replay["eligible_token_slot_ids"], ["slot-1", "slot-2"])
        self.assertEqual(self._long_counts(), (2, 98, 2))

    def test_one_hard_gate_blocked_continues_only_eligible_peer(self) -> None:
        memory_window_id = int(self.candidates[1]["memory_window_1h_id"])
        self.fx.connection.execute(
            "UPDATE printer_memory_windows SET supporting_context_json='{}' WHERE id=?",
            (memory_window_id,),
        )
        self.fx.connection.commit()
        result = self._barrier()
        self.assertTrue(result["barrier_reached"])
        self.assertEqual(result["eligible_token_slot_ids"], ["slot-1"])
        self.assertEqual(result["continuation_count"], 1)
        verdicts = {row["token_slot_id"]: row["verdict"] for row in result["verdicts"]}
        self.assertEqual(verdicts["slot-1"], "CONTINUE_TO_WINDOW_4H")
        self.assertEqual(verdicts["slot-2"], "BLOCK_CONTINUATION")
        self.assertEqual(result["subset_budget"]["request_ceiling"], 151)
        self.assertEqual(result["subset_budget"]["scheduler_ceiling"], 140)
        self.assertEqual(self._long_counts(), (1, 64, 2))

    def test_zero_eligible_is_valid_manifested_noop(self) -> None:
        for candidate in self.candidates:
            self.fx.connection.execute(
                "UPDATE printer_memory_windows SET supporting_context_json='{}' WHERE id=?",
                (int(candidate["memory_window_1h_id"]),),
            )
        self.fx.connection.commit()
        result = self._barrier()
        self.assertTrue(result["barrier_reached"])
        self.assertEqual(result["eligible_token_slot_ids"], [])
        self.assertEqual(result["continuation_count"], 0)
        self.assertEqual(result["subset_budget"]["request_ceiling"], 82)
        self.assertEqual(result["subset_budget"]["scheduler_ceiling"], 76)
        self.assertEqual(self._long_counts(), (0, 0, 2))

    def test_failed_first_hour_peer_is_ineligible_without_blocking_valid_peer(self) -> None:
        self.fx.connection.execute(
            """UPDATE printer_memory_factory_run_steps SET step_status='FAILED'
               WHERE run_id='factory-run-1' AND token_id=2
                 AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')"""
        )
        self.fx.connection.commit()
        result = self._barrier()
        self.assertEqual(result["eligible_token_slot_ids"], ["slot-1"])
        verdicts = {row["token_slot_id"]: row for row in result["verdicts"]}
        self.assertEqual(verdicts["slot-2"]["disposition"], "INELIGIBLE")
        self.assertIn("PREDECESSOR_1H_FAILED", verdicts["slot-2"]["reasons"])
        self.assertEqual(self._long_counts(), (1, 64, 2))

    def test_factory_has_distinct_standard_authority_not_proof_flag(self) -> None:
        parameters = inspect.signature(factory.run_one_command_15m_factory).parameters
        self.assertIn("standard_four_hour_campaign", parameters)
        self.assertIn("four_hour_proof_mode", parameters)
        self.assertFalse(parameters["standard_four_hour_campaign"].default)
        source = inspect.getsource(factory.run_one_command_15m_factory)
        self.assertIn("standard_four_hour_campaign", source)
        self.assertIn("run_standard_four_hour_campaign_barrier", source)
        self.assertIn("not standard_four_hour_campaign", source)
        self.assertNotIn(
            "explicit_proof_mode=standard_four_hour_campaign",
            source,
        )

    def test_barrier_uses_explicit_standard_campaign_authority(self) -> None:
        from printer_v1.operator_cli import standard_4h_progression

        source = inspect.getsource(
            standard_4h_progression.commit_standard_4h_progression_handoff
        )
        self.assertIn("FourHourExecutionAuthority.STANDARD_CAMPAIGN", source)
        self.assertIn("plan_standard_campaign_4h_handoff", source)
        self.assertNotIn("plan_current_run_4h", source)
        self.assertTrue(
            four.runtime_budget("TRACK_FAST")["enabled_for_real_collection"]
        )

    def test_missing_persisted_continuity_blocks_only_that_slot(self) -> None:
        candidate = self.candidates[1]
        window_id = int(candidate["memory_window_1h_id"])
        row = self.fx.connection.execute(
            "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
            (window_id,),
        ).fetchone()
        context = json.loads(str(row[0] or "{}"))
        context.pop("continuity", None)
        self.fx.connection.execute(
            "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
            (json.dumps(context, sort_keys=True), window_id),
        )
        self.fx.connection.commit()
        result = self._barrier()
        self.assertEqual(result["eligible_token_slot_ids"], ["slot-1"])
        verdicts = {row["token_slot_id"]: row for row in result["verdicts"]}
        self.assertEqual(verdicts["slot-2"]["verdict"], "BLOCK_CONTINUATION")
        self.assertIn(
            "predecessor_continuity_not_eligible",
            verdicts["slot-2"]["reasons"],
        )

    def test_standard_execution_budget_matches_both_eligible_manifest(self) -> None:
        result = self._barrier()
        budget = factory._standard_four_hour_cumulative_budget_for_run(
            self.fx.connection, "factory-run-1"
        )
        self.assertEqual(budget["request_ceiling"], result["subset_budget"]["request_ceiling"])
        self.assertEqual(budget["scheduler_ceiling"], result["subset_budget"]["scheduler_ceiling"])
        self.assertEqual(budget["continuing_mask"], (True, True))

    def test_standard_execution_budget_matches_one_eligible_manifest(self) -> None:
        candidate = self.candidates[1]
        self.fx.connection.execute(
            "UPDATE printer_memory_windows SET supporting_context_json='{}' WHERE id=?",
            (int(candidate["memory_window_1h_id"]),),
        )
        self.fx.connection.commit()
        result = self._barrier()
        budget = factory._standard_four_hour_cumulative_budget_for_run(
            self.fx.connection, "factory-run-1"
        )
        self.assertEqual(result["eligible_token_slot_ids"], ["slot-1"])
        self.assertEqual(budget["request_ceiling"], 151)
        self.assertEqual(budget["scheduler_ceiling"], 140)
        self.assertEqual(budget["continuing_mask"], (True, False))

    def test_long_execution_uses_progression_not_legacy_close_result_manifest(self) -> None:
        self._barrier()
        rows = self.fx.connection.execute(
            """SELECT id,result_json FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
               ORDER BY id"""
        ).fetchall()
        self.assertEqual(len(rows), 2)
        for row in rows:
            payload = json.loads(str(row["result_json"] or "{}"))
            payload.pop("standard_four_hour_eligibility", None)
            self.fx.connection.execute(
                "UPDATE printer_memory_factory_run_steps SET result_json=? WHERE id=?",
                (json.dumps(payload, sort_keys=True), int(row["id"])),
            )
        step = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1'
                 AND step_kind LIKE 'LONG_CONTINUATION_%'
               ORDER BY id LIMIT 1"""
        ).fetchone()
        self.fx.connection.commit()
        factory._enforce_budgets_before_step(
            self.fx.connection, "factory-run-1", step
        )


if __name__ == "__main__":
    unittest.main()
