"""V2-9.8B second-correction focused proofs: real full-run accounting semantics.

Disposable databases and injected transports only. These prove the corrected
evidence semantics: real lifecycle source transport identities (nonzero, exact),
per-step transport reservations distinct from Scheduler work, validations that
arise only from executed observations, exact distinct token/pair identity, the
real terminal/authorization gate inputs, all four mandatory stages independently
required, real Scheduler ownership state, quality consistency against real
episodes, and report/gate/verdict agreement. No operational command, no live
campaign, no authoritative database, no migration.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_ownership import (
    bind_authoritative_run_id,
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_full_run_accounting import (
    PRECLOSE_CONTEXT_REQUEST_COUNT,
    PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND,
    OperationalLifecycleOwnershipContext,
    VERDICT_BLOCKED_UNSAFE,
    VERDICT_PASS,
    build_lifecycle_action_local_observer,
    finalize_full_run_ownership_and_report,
    reservation_identities_for_step,
)
from printer_v1.operator_cli import one_command_15m_factory as factory_mod
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger


NOW = "2026-07-31T00:00:00+00:00"
CAMPAIGN = "campaign-s"
CONFIG = "configuration-s"
RUN = "run-s"
CYCLE = "cycle-s"
FACTORY_RUN = "factory-run-s"
SNAPSHOTS_PER_TOKEN = 3
# Distinct token vs pair identity: pair ids are deliberately not the token ids.
TOKENS = (1, 2)
PAIR_OF = {1: 101, 2: 102}
MINT_OF = {1: "mintaaaa1", 2: "mintbbbb2"}
PAIR_ADDR = {101: "pairaddr01", 102: "pairaddr02"}
PAYLOAD = json.dumps({"pairs": [{"chain": "solana", "price_usd": 1.0}]})


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class _SemanticsFixture(unittest.TestCase):
    """Disposable two-token terminal WINDOW_15M graph with real source rows.

    Every lifecycle step carries a distinct scheduler job (state controllable),
    and a linked source request/response (so transports/bytes are real). Token
    and pair identities are deliberately different values.
    """

    # sub-classes may override for specific fault injections
    JOB_STATUS_OVERRIDES: dict = {}
    MEMORY: dict = {
        1: ("CLEAN_MEMORY", "CLEAN_DATA", 0),
        2: ("DIRTY_MEMORY", "MISSING_CRITICAL_DATA", 1),
    }
    EPISODES: dict = {}

    def setUp(self) -> None:
        temp_parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=temp_parent)
        self.db = Path(self.temp.name) / "semantics.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db, campaign_id=CAMPAIGN, configuration_id=CONFIG,
            configuration={"slots": 2}, launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED, db_target_identity="isolated-s",
            proof_source_db_identity="source-s", policy_version="v2-9.8b",
        )
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        # (token, kind, key, job_id, source_request_id, source_response_id)
        self.steps: list[tuple[int, str, str, int, int, int]] = []
        self.close_step_id: dict[int, int] = {}
        self._seed()
        self.context = OperationalLifecycleOwnershipContext(
            campaign_id=CAMPAIGN, campaign_run_id=RUN, cycle_id=CYCLE,
            configuration_id=CONFIG, factory_run_id=FACTORY_RUN,
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _seed(self) -> None:
        job_id = 0
        source_id = 0
        with self.conn:
            for token in TOKENS:
                pair = PAIR_OF[token]
                self.conn.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token, MINT_OF[token]),
                )
                self.conn.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
                    (pair, token, PAIR_ADDR[pair]),
                )
                mem_status, mem_label, dnt = self.MEMORY[token]
                self.conn.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,memory_status,
                        data_quality_label,do_not_train
                    ) VALUES (?,?,?,'WINDOW_15M',?,?,?,?)""",
                    (token, token, pair, NOW, mem_status, mem_label, dnt),
                )
                for kind, ep in self.EPISODES.get(token, []):
                    self.conn.execute(
                        """INSERT INTO printer_episodes(
                            memory_window_id,token_id,pair_id,episode_kind,
                            episode_status,memory_status,data_quality_label,do_not_train
                        ) VALUES (?,?,?,?,'CREATED',?,?,?)""",
                        (token, token, pair, kind, ep, "CLEAN_DATA", 0),
                    )
            self.conn.execute(
                """INSERT INTO printer_memory_factory_runs(
                    run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at
                ) VALUES (?,'COMPLETED','WINDOW_15M','PROOF_ONLY','h','{}',?)""",
                (FACTORY_RUN, NOW),
            )
        create_campaign_run(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, run_ordinal=1, now=NOW
        )
        bind_authoritative_run_id(
            self.conn, campaign_run_id=RUN, factory_run_id=FACTORY_RUN, now=NOW
        )
        create_cycle_with_two_slots(
            self.conn, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE,
            cycle_ordinal=1, now=NOW,
            slots=[
                {
                    "token_slot_id": f"slot-{token}", "slot_ordinal": ordinal,
                    "token_identity": f"token-{token}", "token_row_id": token,
                    "mint_identity": MINT_OF[token], "pair_identity": PAIR_ADDR[PAIR_OF[token]],
                    "pair_row_id": PAIR_OF[token], "lifecycle_identity": f"lifecycle-{token}",
                }
                for ordinal, token in enumerate(TOKENS, start=1)
            ],
        )
        with self.conn:
            for token in TOKENS:
                pair = PAIR_OF[token]
                plan = [
                    (f"t{token}_snapshot_{i:02d}", "SNAPSHOT")
                    for i in range(SNAPSHOTS_PER_TOKEN)
                ] + [(f"t{token}_window_close", "WINDOW_CLOSE")]
                for step_key, kind in plan:
                    source_id += 1
                    self.conn.execute(
                        """INSERT INTO printer_source_requests(
                            id,source_name,request_kind,requested_at,request_key,
                            source_status,data_quality_label
                        ) VALUES (?,?,?,?,?,?,?)""",
                        (source_id, "dexscreener", "pair_market_snapshot", NOW,
                         f"{FACTORY_RUN}:{step_key}", "COMPLETE", "CLEAN_DATA"),
                    )
                    self.conn.execute(
                        """INSERT INTO printer_source_responses(
                            id,source_request_id,source_name,received_at,status_code,
                            source_status,data_quality_label,normalized_payload_json
                        ) VALUES (?,?,?,?,?,?,?,?)""",
                        (source_id, source_id, "dexscreener", NOW, 200, "COMPLETE",
                         "CLEAN_DATA", PAYLOAD),
                    )
                    job_id += 1
                    status = self.JOB_STATUS_OVERRIDES.get(step_key, "SUCCEEDED")
                    self.conn.execute(
                        """INSERT INTO printer_scheduler_jobs(
                            id,job_name,job_kind,status,scheduled_for
                        ) VALUES (?,?,?,?,?)""",
                        (job_id, step_key, kind, status, NOW),
                    )
                    mem_window = token if kind == "WINDOW_CLOSE" else None
                    cur = self.conn.execute(
                        """INSERT INTO printer_memory_factory_run_steps(
                            run_id,step_key,step_kind,step_status,token_id,pair_id,
                            token_mint,pair_address,tracking_lane,scheduler_job_id,
                            source_request_id,source_response_id,memory_window_id
                        ) VALUES (?,?,?,'SUCCEEDED',?,?,?,?,'TRACK_NORMAL',?,?,?,?)""",
                        (FACTORY_RUN, step_key, kind, token, pair, MINT_OF[token],
                         PAIR_ADDR[pair], job_id, source_id, source_id, mem_window),
                    )
                    self.steps.append(
                        (token, kind, step_key, job_id, source_id, source_id)
                    )
                    if kind == "WINDOW_CLOSE":
                        self.close_step_id[token] = int(cur.lastrowid)

    def _action_local(self) -> CampaignActionLocalLedger:
        ledger = CampaignActionLocalLedger(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE, lifecycle_started=True
        )
        observe = build_lifecycle_action_local_observer(self.context, ledger)
        for token, kind, key, job, req, resp in self.steps:
            base = {
                "run_id": FACTORY_RUN, "scheduler_job_id": job, "step_key": key,
                "step_kind": kind, "token_id": token, "pair_id": PAIR_OF[token],
            }
            observe({**base, "boundary": "SCHEDULER_ENQUEUE"})
            observe({
                **base, "boundary": "SOURCE_TRANSPORT",
                "source_request_id": req, "source_response_id": resp,
                "source_name": "dexscreener", "request_kind": "pair_market_snapshot",
            })
        return ledger

    def _finalize(self, *, action_local=None, **overrides):
        defaults = dict(
            execution_id="exec-s", supervision_id=1,
            launch_git_provenance=_provenance(), db_target_identity="isolated-s",
            authorized_invocation_count=1,
            runtime_terminal_status="TERMINAL_COMPLETED",
            lease_released=True,
            forbidden_capability_deltas={
                "retrieval_queries": 0, "paper_decisions": 0, "paper_trades": 0,
            },
            now=NOW,
        )
        defaults.update(overrides)
        return finalize_full_run_ownership_and_report(
            self.conn, context=self.context,
            action_local=action_local if action_local is not None else self._action_local(),
            **defaults,
        )


class SemanticsCorrectionTests(_SemanticsFixture):
    # 1. real lifecycle source transports, bytes and rows are nonzero and exact.
    def test_lifecycle_source_transports_bytes_rows_nonzero_and_exact(self) -> None:
        outcome = self._finalize()
        self.assertEqual(outcome["verdict"], VERDICT_PASS, outcome["blocked_reasons"])
        totals = outcome["report"]["full_run_accounting"]["six_unit_totals"]
        n_steps = len(self.steps)  # 2 tokens * (3 snapshots + 1 close) = 8
        self.assertEqual(totals["SOURCE_TRANSPORT_OPERATION"], n_steps)
        self.assertEqual(totals["NORMALIZED_SOURCE_ROWS"], n_steps)
        self.assertEqual(totals["SOURCE_RESPONSE_BYTES"], n_steps * len(PAYLOAD))
        self.assertGreater(totals["SOURCE_RESPONSE_BYTES"], 0)

    # 2. removing one measured transport identity blocks.
    def test_removing_one_measured_transport_identity_blocks(self) -> None:
        ledger = self._action_local()
        self.assertTrue(ledger.transport_identities)
        ledger.transport_identities.pop()  # drop one observed outbound call
        outcome = self._finalize(action_local=ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["reconciliation"]["equal"])
        self.assertIn(
            "SOURCE_TRANSPORT_OPERATION", outcome["reconciliation"]["mismatch_reason"]
        )

    # 3. reservation totals reflect actual per-step request reservations.
    def test_reservation_totals_reflect_per_step_reservations(self) -> None:
        outcome = self._finalize()
        totals = outcome["report"]["full_run_accounting"]["six_unit_totals"]
        snapshots = 2 * SNAPSHOTS_PER_TOKEN
        closes = 2
        expected_reservations = (
            snapshots * PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND["SNAPSHOT"]
            + closes * PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND["WINDOW_CLOSE"]
        )
        self.assertEqual(
            totals["LIFECYCLE_RESERVED_TRANSPORT_OPERATION"], expected_reservations
        )
        # A close reserves many calls but is still exactly one Scheduler job.
        self.assertGreater(
            totals["LIFECYCLE_RESERVED_TRANSPORT_OPERATION"],
            totals["SCHEDULER_WORK_ITEM"],
        )
        self.assertEqual(totals["SCHEDULER_WORK_ITEM"], len(self.steps))
        # The reservation count per step derives from projected governed operations.
        close_reservations = reservation_identities_for_step(
            self.context, slot_ordinal=1, scheduler_job_id=999,
            step_kind="WINDOW_CLOSE", token_id=1, pair_id=101,
        )
        self.assertEqual(
            len(close_reservations), 1 + PRECLOSE_CONTEXT_REQUEST_COUNT
        )

    # 4. validation identities arise only from executed observations.
    def test_validations_only_from_executed_observations(self) -> None:
        ledger = self._action_local()
        # Slot validations equal the number of executed source-transport steps.
        self.assertEqual(len(ledger.local_validation_identities), len(self.steps))
        # Dropping one source-transport observation drops its validation and blocks.
        ledger.local_validation_identities.pop()
        outcome = self._finalize(action_local=ledger)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertIn(
            "LOCAL_VALIDATION_STEP", outcome["reconciliation"]["mismatch_reason"]
        )

    # 5. token id differs from pair id and remains exact.
    def test_token_id_differs_from_pair_id_and_is_exact(self) -> None:
        outcome = self._finalize()
        selected = outcome["report"]["selection_and_lifecycle"]["selected_tokens"]
        by_token = {item["token_id"]: item for item in selected}
        for token in TOKENS:
            self.assertEqual(by_token[token]["pair_id"], PAIR_OF[token])
            self.assertNotEqual(by_token[token]["pair_id"], token)
            self.assertEqual(by_token[token]["pair_address"], PAIR_ADDR[PAIR_OF[token]])
            self.assertEqual(by_token[token]["token_mint"], MINT_OF[token])
            self.assertEqual(by_token[token]["tracking_lane"], "TRACK_NORMAL")
            self.assertEqual(by_token[token]["memory_window_row_id"], token)

    # 6. authorization count 0 or 2 blocks; exactly 1 passes.
    def test_authorization_count_zero_or_two_blocks(self) -> None:
        self.assertEqual(self._finalize()["verdict"], VERDICT_PASS)
        for bad in (0, 2):
            with self.subTest(count=bad):
                # fresh graph per finalize (registration is idempotent, gate re-runs)
                outcome = self._finalize(authorized_invocation_count=bad)
                self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
                self.assertFalse(
                    outcome["campaign_acceptance"]["checks"][
                        "exactly_one_authorized_invocation"
                    ]
                )

    # 7. an unreleased lease blocks.
    def test_unreleased_lease_blocks(self) -> None:
        outcome = self._finalize(lease_released=False)
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["report"]["terminal_safety"]["lease_released"])
        self.assertFalse(outcome["campaign_acceptance"]["checks"]["lease_released"])

    # 8. a non-completed runtime status cannot be represented as completed.
    def test_non_completed_runtime_status_blocks_and_is_not_masked(self) -> None:
        outcome = self._finalize(runtime_terminal_status="FAILED")
        self.assertEqual(outcome["report"]["runtime_terminal_status"], "FAILED")
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(
            outcome["campaign_acceptance"]["checks"]["runtime_terminal_completed"]
        )

    # 12. report, gate and top-level verdict cannot disagree.
    def test_report_gate_and_verdict_cannot_disagree(self) -> None:
        # PASS case.
        ok = self._finalize()
        self.assertEqual(ok["verdict"], VERDICT_PASS)
        self.assertEqual(ok["campaign_acceptance"]["verdict"], VERDICT_PASS)
        self.assertEqual(ok["report"]["campaign_acceptance_verdict"], VERDICT_PASS)
        self.assertTrue(ok["campaign_acceptance"]["pass"])
        # Blocked case: an unreleased lease. No surface may still say CAMPAIGN_PASS.
        blocked = self._finalize(lease_released=False)
        self.assertNotEqual(blocked["verdict"], VERDICT_PASS)
        self.assertEqual(
            blocked["verdict"], blocked["campaign_acceptance"]["verdict"]
        )
        self.assertEqual(
            blocked["verdict"], blocked["report"]["campaign_acceptance_verdict"]
        )
        self.assertFalse(blocked["campaign_acceptance"]["pass"])
        self.assertFalse(blocked["report"]["campaign_pass"])


class SchedulerStateTests(_SemanticsFixture):
    # 10. failed Scheduler state is reported accurately and blocks.
    JOB_STATUS_OVERRIDES = {"t1_snapshot_01": "FAILED"}

    def test_failed_scheduler_state_reported_and_blocks(self) -> None:
        outcome = self._finalize()
        ownership = outcome["report"]["full_run_accounting"]["scheduler_ownership"]
        self.assertFalse(ownership["all_lifecycle_jobs_succeeded"])
        self.assertIn("FAILED", ownership["non_succeeded_states"].values())
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(
            outcome["campaign_acceptance"]["checks"][
                "all_lifecycle_scheduler_jobs_succeeded"
            ]
        )
        # The campaign scheduler ownership row carries the real FAILED state.
        states = {
            r["scheduler_job_id"]: r["work_state"]
            for r in self.conn.execute(
                "SELECT scheduler_job_id, work_state FROM "
                "printer_memory_factory_campaign_scheduler_work WHERE campaign_id=?",
                (CAMPAIGN,),
            ).fetchall()
        }
        self.assertIn("FAILED", states.values())


class SchedulerNonTerminalTests(_SemanticsFixture):
    JOB_STATUS_OVERRIDES = {"t2_snapshot_00": "PENDING"}

    def test_non_terminal_scheduler_job_blocks(self) -> None:
        outcome = self._finalize()
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertTrue(
            any(
                r.startswith("SCHEDULER_JOB_NOT_TERMINAL")
                for r in outcome["blocked_reasons"]
            )
        )
        self.assertFalse(
            outcome["report"]["full_run_accounting"]["scheduler_correspondence_exact"]
        )


class QualityConsistencyTests(_SemanticsFixture):
    # 11. a partial window with a clean episode blocks.
    MEMORY = {
        1: ("CLEAN_MEMORY", "CLEAN_DATA", 0),
        2: ("PARTIAL_MEMORY", "ACCEPTABLE_PARTIAL_DATA", 1),
    }
    EPISODES = {2: [("WINDOW_15M_CLEAN_MEMORY", "CLEAN_MEMORY")]}

    def test_partial_window_with_clean_episode_blocks(self) -> None:
        outcome = self._finalize()
        self.assertNotEqual(outcome["verdict"], VERDICT_PASS)
        self.assertFalse(outcome["report"]["quality_consistency"]["consistent"])
        self.assertFalse(
            outcome["campaign_acceptance"]["checks"]["memory_quality_consistent"]
        )
        # Lifecycle completion for the partial window itself is still valid.
        quality = outcome["report"]["selection_and_lifecycle"]["quality_results"]
        partial = next(q for q in quality if q["window_id"].endswith(":window:2"))
        self.assertTrue(partial["lifecycle_completion_valid"])
        self.assertEqual(partial["outcome"], "QUALITY_CONSISTENCY_BLOCKED")


class MandatoryStageTests(_SemanticsFixture):
    # 9. each of the four mandatory stages is independently required.
    def test_each_of_four_mandatory_stages_independently_required(self) -> None:
        outcome = self._finalize()
        sealed = {
            s["stage_kind"]
            for s in outcome["report"]["full_run_accounting"][
                "sealed_stage_diagnostics"
            ]
        }
        from printer_v1.operator_cli.campaign_full_run_accounting import (
            REQUIRED_LIFECYCLE_STAGE_KINDS,
            evaluate_campaign_acceptance_gate,
        )
        self.assertEqual(sealed, set(REQUIRED_LIFECYCLE_STAGE_KINDS))
        # Removing any one mandatory stage from the report blocks PASS.
        import copy
        for omitted in REQUIRED_LIFECYCLE_STAGE_KINDS:
            with self.subTest(omitted=omitted):
                report = copy.deepcopy(outcome["report"])
                report["full_run_accounting"]["sealed_stage_diagnostics"] = [
                    s
                    for s in report["full_run_accounting"]["sealed_stage_diagnostics"]
                    if s["stage_kind"] != omitted
                ]
                gate = evaluate_campaign_acceptance_gate(
                    report, authorized_invocation_count=1
                )
                self.assertFalse(gate["checks"]["all_mandatory_stages_sealed"])
                self.assertNotEqual(gate["verdict"], VERDICT_PASS)


class ProjectedReservationGuardTests(unittest.TestCase):
    def test_preclose_context_count_matches_factory_constant(self) -> None:
        # The projected close reservation must track the factory's real pre-close
        # context bundle size; drift would silently misstate reservations.
        self.assertEqual(
            PRECLOSE_CONTEXT_REQUEST_COUNT,
            factory_mod._CONTEXT_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(
            PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND["WINDOW_CLOSE"],
            1 + factory_mod._CONTEXT_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND["SNAPSHOT"], 1)


if __name__ == "__main__":
    unittest.main()
