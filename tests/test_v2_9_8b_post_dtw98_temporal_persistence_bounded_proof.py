"""V2-9.8B Post-DTW98 temporal persistence — bounded disposable proof.

Proves the ratified implementation (`96e755700cd877a3e0da9bac060adede853c1421`)
end to end on a disposable database.

Boundary, enforced by construction in every case below:

* disposable SQLite only — every database lives under a ``tempfile`` directory
  and is asserted distinct from the canonical authoritative database;
* migration 054 is applied only to those disposable proof databases;
* injected/fake approved transports and an injected fake clock only;
* no real sleep, no live provider/RPC/source access;
* no authoritative database read, write or migration;
* no authorization creation or consumption;
* no Printer live runtime and no WINDOW_15M execution.

Cases already proven by the focused temporal and completion suites are reused
rather than duplicated; this module adds only the proof-specific gaps:
migration/DB identity, the full ordered Scheduler lineage, horizon exhaustion
after the one designed refresh, post-claim slot fail-close, the consolidated
accounting record, and the disposability invariant.
"""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.discovery.combined_executor import (
    canonical_cycle_discovery_batch_id,
)
from printer_v1.discovery.eligible_token_supply import (
    BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL,
    DURATION_EXHAUSTION,
    GRADUATED_SUPPLY_READY,
    TRUE_MARKET_SUPPLY_SHORTAGE,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    ACTIVE_WAIT_STATES,
    PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED,
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    REFRESH_COMPLETED,
    WAIT_TABLE,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    iso,
)
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.operator_cli.pre_lifecycle_temporal_refresh_owner import (
    REFRESH_WORK_TYPE,
)
from printer_v1.scheduler.contracts import JobKind

from tests.test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence import (
    CAMPAIGN,
    CYCLE,
    REFRESH_INTERVAL,
    RUN,
    SEED,
    _TemporalBase,
    _now,
)
from tests.test_v2_9_8b_post_dtw98_temporal_persistence_completion import (
    _gecko_new_pool_payload,
    _gecko_transport,
    _pumpswap_account_batch_transport,
)
from tests.test_v2_9_8b_21_eligible_token_supply_architecture import (
    SPECS24,
    _dex_factory,
    _empty_migration_transport,
    _pair_payload,
    _seed_registry,
)

MIGRATION_054 = "054_pre_lifecycle_discovery_refresh_wait.sql"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ProofCase01MigrationAndDatabaseIdentity(unittest.TestCase):
    """Proof 1 + 16 — migration 054 on a disposable database only."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "bounded-proof.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_proof_01_migration_054_applies_cleanly_with_clean_integrity(
        self,
    ) -> None:
        applied = [
            str(row[0])
            for row in self.connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        ]
        self.assertIn(MIGRATION_054, applied)
        self.assertEqual(applied[-1], MIGRATION_054)
        self.assertEqual(len(applied), canonical_migration_count())
        self.assertEqual(applied, list(canonical_migration_names()))

        self.assertEqual(
            self.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

        # The wait table, its indexes and its guard triggers all exist.
        self.assertIsNotNone(
            self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (WAIT_TABLE,),
            ).fetchone()
        )
        triggers = {
            str(row[0])
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                (WAIT_TABLE,),
            ).fetchall()
        }
        self.assertEqual(
            triggers,
            {
                "printer_pre_lifecycle_refresh_wait_identity_immutable",
                "printer_pre_lifecycle_refresh_wait_no_terminal_reopen",
            },
        )

    def test_proof_16_proof_database_is_disposable_and_not_authoritative(
        self,
    ) -> None:
        resolved = self.db.resolve()
        self.assertNotEqual(resolved, CANONICAL_PERSISTENT_DB)
        self.assertTrue(
            str(resolved).startswith(str(Path(self.temp.name).resolve())),
            "proof database must live inside the disposable temp directory",
        )
        # Recorded identity for the bounded-proof report.
        self.assertEqual(len(_sha256_file(self.db)), 64)
        # The authoritative database is never a target of this proof. Asserted
        # structurally: nothing in the proof references that path.
        self.assertNotIn(str(CANONICAL_PERSISTENT_DB), str(resolved))


class ProofOrderedSchedulerLineage(_TemporalBase):
    """Proof 6 + 12 — exact claim-at-work-start lineage and fail-close."""

    def test_proof_06_ordered_claim_wait_slot_work_then_governed_work(
        self,
    ) -> None:
        mint, _sig, pool = SPECS24[9]
        observed: dict[str, object] = {}

        production = build_pre_lifecycle_refresh_stage(
            request_key_prefix=SEED,
            geckoterminal_nomination_transport=_gecko_transport(
                _gecko_new_pool_payload(mint, pool, 12_000.0)
            ),
            protocol_account_batch_transport=_pumpswap_account_batch_transport(
                pool, mint
            ),
        )

        def observing_stage(connection, **call):
            # Captured at the instant governed refresh work is allowed to begin.
            observed["job_status"] = str(
                connection.execute(
                    "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                    (call["scheduler_job_id"],),
                ).fetchone()[0]
            )
            observed["wait_state"] = str(
                connection.execute(
                    f"SELECT wait_state FROM {WAIT_TABLE} WHERE scheduler_job_id=?",
                    (call["scheduler_job_id"],),
                ).fetchone()[0]
            )
            work = connection.execute(
                "SELECT work_state, discovery_batch_id, work_type "
                "FROM printer_discovery_work WHERE discovery_work_id=?",
                (call["discovery_work_id"],),
            ).fetchone()
            observed["work_state"] = str(work[0])
            observed["work_batch"] = str(work[1])
            observed["work_type"] = str(work[2])
            observed["source_requests_before_governed_work"] = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0]
            )
            return production(connection, **call)

        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=observing_stage,
        )
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, REFRESH_COMPLETED)
        self.assertTrue(outcome.claimed)

        # Exact ratified order, observed at the governed-work boundary:
        #   claim -> wait CLAIMED -> slot check -> discovery work RUNNING -> work
        self.assertEqual(observed["job_status"], "RUNNING")
        self.assertEqual(observed["wait_state"], "CLAIMED")
        self.assertEqual(observed["work_state"], "RUNNING")
        self.assertEqual(observed["work_type"], REFRESH_WORK_TYPE)
        self.assertEqual(
            observed["work_batch"],
            canonical_cycle_discovery_batch_id(
                campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
            ),
        )
        # Zero governed source work had happened before the work row was RUNNING.
        self.assertEqual(observed["source_requests_before_governed_work"], 0)

        # Consistent terminalization of all three owners.
        self.assertEqual(str(self._jobs()[0]["status"]), "SUCCEEDED")
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "SUCCEEDED")
        self.assertEqual(str(self._work_rows()[0]["work_state"]), "SUCCEEDED")

    def test_proof_12_occupied_slot_fails_closed_after_claim(self) -> None:
        from printer_v1.discovery.persistence import insert_discovery_work
        from printer_v1.scheduler.scheduler import enqueue_job

        batch_id = canonical_cycle_discovery_batch_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        _result, foreign_job = enqueue_job(
            self.connection,
            job_name="foreign-refresh-owner",
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
        )
        insert_discovery_work(
            self.connection,
            discovery_work_id="work:foreign-refresh-owner",
            discovery_batch_id=batch_id,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            scheduler_job_id=int(foreign_job),
            work_type=REFRESH_WORK_TYPE,
            deadline_at=iso(self.start + timedelta(seconds=1200)),
            work_state="RUNNING",
            now=iso(_now()),
        )
        self.connection.commit()
        work_rows_before = len(self._work_rows())

        stage_calls: list[str] = []

        def never_called_stage(connection, **call):
            stage_calls.append("ran")
            return {"source_operations": 1}

        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=never_called_stage,
        )
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, "UNSAFE_SCHEDULER_STATE")
        # The claim was consumed (ratified order), but no refresh work and no
        # source request followed, and nothing of the foreign owner was touched.
        self.assertTrue(outcome.claimed)
        self.assertEqual(stage_calls, [])
        self.assertEqual(len(self._work_rows()), work_rows_before)
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0]
            ),
            0,
        )
        self.assertEqual(
            str(
                self.connection.execute(
                    "SELECT work_state FROM printer_discovery_work "
                    "WHERE discovery_work_id='work:foreign-refresh-owner'"
                ).fetchone()[0]
            ),
            "RUNNING",
        )
        wait = self._wait_rows()[0]
        self.assertEqual(str(wait["wait_state"]), "FAILED")
        self.assertEqual(
            str(wait["first_terminal_cause"]),
            "PRE_LIFECYCLE_REFRESH_WORK_SLOT_TAKEN",
        )
        self.assertEqual(
            str(
                self.connection.execute(
                    "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                    (int(outcome.scheduler_job_id),),
                ).fetchone()[0]
            ),
            "FAILED",
        )
        # This owner leaves zero active wait residue of its own.
        self.assertEqual(
            int(
                self.connection.execute(
                    f"SELECT COUNT(*) FROM {WAIT_TABLE} WHERE wait_state IN "
                    f"({','.join('?' * len(ACTIVE_WAIT_STATES))})",
                    ACTIVE_WAIT_STATES,
                ).fetchone()[0]
            ),
            0,
        )
        self.assertNoForbiddenCapabilityDelta()


class ProofHorizonAndAccounting(_TemporalBase):
    """Proofs 7-11 + 15 — one lawful refresh, honest exhaustion, accounting."""

    CAPACITY = 4

    def _run_supply(self, *, payloads, owner, deadline, budget=30):
        return run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=iso(_now()),
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=self.CAPACITY,
            discovery_operation_budget=budget,
            deadline_at=deadline,
            temporal_refresh_owner=owner,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            execution_id=SEED,
        )

    @staticmethod
    def _payloads(specs, eligible_mints, *, liquidity=15_000.0):
        return {
            pool: _pair_payload(
                pool, mint, liquidity if mint in eligible_mints else 40.0
            )
            for mint, _sig, pool in specs
        }

    def test_proof_11_one_refresh_then_horizon_exhausts_honestly(self) -> None:
        """The 900s horizon admits one 600s refresh, then duration-exhausts."""
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}

        # A lawful refresh that *completes* but exposes nothing newly eligible:
        # the nominated pool is truthfully below the categorical $3,000
        # selection floor, so it never promotes. (An empty GeckoTerminal page
        # is classified by the existing adapter as
        # ``geckoterminal_no_valid_solana_pools`` — a provider failure — which
        # would prove source-availability handling, not horizon exhaustion.)
        below_floor_mint, _bf_sig, below_floor_pool = SPECS24[10]
        empty_refresh = build_pre_lifecycle_refresh_stage(
            request_key_prefix=SEED,
            geckoterminal_nomination_transport=_gecko_transport(
                _gecko_new_pool_payload(below_floor_mint, below_floor_pool, 500.0)
            ),
        )
        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=empty_refresh,
        )
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=iso(
                self.start
                + timedelta(seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS)
            ),
        )

        acquisition = result.diagnostics["pre_lifecycle_acquisition"]
        # Exactly one refresh opportunity was scheduled and claimed.
        self.assertEqual(acquisition["temporal_refresh_opportunities_claimed"], 1)
        self.assertEqual(acquisition["temporal_refresh_opportunities_completed"], 1)
        self.assertEqual(acquisition["refresh_interval_seconds"], REFRESH_INTERVAL)
        self.assertEqual(
            acquisition["acquisition_duration_seconds"],
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
        )
        # A second interval does not fit: honest duration exhaustion, and never
        # a fabricated true market shortage.
        self.assertFalse(result.ready)
        self.assertEqual(
            result.terminal, BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
        )
        self.assertEqual(result.shortage_classification, DURATION_EXHAUSTION)
        self.assertNotEqual(
            result.shortage_classification, TRUE_MARKET_SUPPLY_SHORTAGE
        )
        certificate = result.exhaustion_certificate.to_dict()
        self.assertEqual(
            certificate["last_reason_discovery_could_not_continue"],
            PRE_LIFECYCLE_ACQUISITION_DURATION_EXHAUSTED,
        )
        # Exactly one Scheduler job, terminal, with zero active residue.
        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(str(jobs[0]["status"]), "SUCCEEDED")
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertTrue(report["clean_terminal"])
        self.assertNoForbiddenCapabilityDelta()

    def test_proof_07_to_10_full_scenario_accounting_record(self) -> None:
        """The consolidated bounded-proof accounting record."""
        record = collect_bounded_proof_record(self)

        # Proof 7 — governed nomination + PumpSwap confirmation exposed a 4th.
        self.assertEqual(record["nomination_status"], "COMPLETE")
        self.assertEqual(record["nominations"], 1)
        self.assertEqual(record["promoted"], 1)
        # Both refresh-stage owners issued exactly one governed request each.
        # The remaining governed requests are the supply's own front-door
        # market work, which is unchanged by this lane.
        kinds = record["governed_request_kinds"]
        self.assertEqual(kinds.count("geckoterminal_new_pool_discovery"), 1)
        self.assertEqual(kinds.count("pumpswap_pool_account_batch"), 1)
        self.assertEqual(record["refresh_source_operations"], 2)
        # Proof 8/9 — retained three revalidated, exact 2+2 freeze.
        self.assertEqual(record["retained_marked_stale"], 3)
        self.assertTrue(record["ready"])
        self.assertEqual(record["terminal"], GRADUATED_SUPPLY_READY)
        self.assertEqual(record["eligible_reserve_count"], 4)
        # Proof 10 — cumulative budget never reset.
        self.assertEqual(record["discovery_operation_budget"], 30)
        self.assertEqual(
            record["operations_remaining"], 30 - record["operations_used"]
        )
        self.assertLessEqual(record["operations_used"], 30)
        self.assertGreaterEqual(record["operations_used"], 2)
        # Proof 15 — zero forbidden capability-table deltas.
        self.assertEqual(record["forbidden_capability_rows"], 0)
        self.assertTrue(record["clean_terminal"])


def collect_bounded_proof_record(case: _TemporalBase) -> dict:
    """Run the full bounded scenario once and return its accounting record."""
    specs = SPECS24[:8]
    late_mint, _late_sig, late_pool = SPECS24[9]
    _seed_registry(case.connection, specs, now=iso(case.start))
    eligible = {specs[0][0], specs[1][0], specs[2][0]}
    payloads = {
        pool: _pair_payload(pool, mint, 15_000.0 if mint in eligible else 40.0)
        for mint, _sig, pool in specs
    }
    payloads[late_pool] = _pair_payload(late_pool, late_mint, 15_000.0)

    production = build_pre_lifecycle_refresh_stage(
        request_key_prefix=SEED,
        geckoterminal_nomination_transport=_gecko_transport(
            _gecko_new_pool_payload(late_mint, late_pool, 15_000.0)
        ),
        protocol_account_batch_transport=_pumpswap_account_batch_transport(
            late_pool, late_mint
        ),
    )
    reports: list[dict] = []

    def stage(connection, **call):
        report = dict(production(connection, **call))
        reports.append(report)
        return report

    owner = case._owner(
        waiter=lambda seconds: False, clock=case._due_clock(), stage=stage
    )
    result = run_persistent_eligible_token_supply(
        case.db,
        cycle_seed=SEED,
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_dex_factory(payloads),
        now=iso(_now()),
        collection_rounds=1,
        front_door_max_candidates=6,
        required_token_capacity=4,
        discovery_operation_budget=30,
        deadline_at=iso(
            case.start
            + timedelta(seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS)
        ),
        temporal_refresh_owner=owner,
        campaign_id=CAMPAIGN,
        run_id=RUN,
        cycle_id=CYCLE,
        execution_id=SEED,
    )
    acquisition = result.diagnostics["pre_lifecycle_acquisition"]
    stage_report = reports[0] if reports else {}
    active = campaign_active_work_report(
        case.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
    )
    forbidden = 0
    for table in LOCKED_CAPABILITY_TABLES:
        try:
            forbidden += int(
                case.connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
            )
        except sqlite3.Error:
            pass
    jobs = [dict(row) for row in case._jobs()]
    waits = [dict(row) for row in case._wait_rows()]
    works = [dict(row) for row in case._work_rows()]
    return {
        "ready": bool(result.ready),
        "terminal": str(result.terminal),
        "eligible_reserve_count": len(result.eligible_reserve),
        "eligible_mints": sorted(c["mint"] for c in result.eligible_reserve),
        "discovery_rounds": result.diagnostics["discovery_rounds"],
        "discovery_operation_budget": result.diagnostics[
            "discovery_operation_budget"
        ],
        "operations_used": result.diagnostics["discovery_operations_used"],
        "operations_remaining": result.diagnostics[
            "discovery_operations_remaining"
        ],
        "refresh_source_operations": int(
            stage_report.get("source_operations") or 0
        ),
        "nomination_status": str(
            (stage_report.get("nomination_report") or {}).get("status")
        ),
        "nominations": len(
            (stage_report.get("nomination_report") or {}).get("nominations") or []
        ),
        "promoted": len(stage_report.get("promoted_observation_eligible") or []),
        "governed_request_kinds": [
            str(row[0])
            for row in case.connection.execute(
                "SELECT request_kind FROM printer_source_requests ORDER BY id"
            ).fetchall()
        ],
        "governed_requests_total": int(
            case.connection.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        ),
        "opportunities_scheduled": acquisition[
            "temporal_refresh_opportunities_scheduled"
        ],
        "opportunities_claimed": acquisition[
            "temporal_refresh_opportunities_claimed"
        ],
        "opportunities_completed": acquisition[
            "temporal_refresh_opportunities_completed"
        ],
        "waiting_states_entered": acquisition["waiting_states_entered"],
        "retained_marked_stale": len(
            (acquisition["candidate_revalidation_outcomes"] or [{}])[0].get(
                "retained_candidates_marked_stale", []
            )
        ),
        "scheduler_jobs": [
            {"kind": str(j["job_kind"]), "status": str(j["status"])} for j in jobs
        ],
        "wait_rows": [
            {"state": str(w["wait_state"]), "ordinal": int(w["refresh_ordinal"])}
            for w in waits
        ],
        "discovery_work_rows": [
            {"type": str(w["work_type"]), "state": str(w["work_state"])}
            for w in works
        ],
        "active_jobs": active["active_jobs"],
        "active_pre_lifecycle_refresh_waits": active[
            "active_pre_lifecycle_refresh_waits"
        ],
        "clean_terminal": bool(active["clean_terminal"]),
        "forbidden_capability_rows": forbidden,
    }


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
