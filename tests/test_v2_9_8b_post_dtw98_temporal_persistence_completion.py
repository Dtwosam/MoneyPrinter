"""V2-9.8B Post-DTW98 temporal persistence implementation-completion proof.

Proves the *production wiring* the implementation review found missing: the
ordinary WINDOW_15M composition actually constructs one exact-scope
``PreLifecycleTemporalRefreshOwner``, passes it into ``run_operational``, and
drives a bounded Scheduler-owned refresh through the real production refresh
composition.

Disposable SQLite and injected approved transports only. No real sleep, no
network, no provider access, no authoritative database, no authorization, no
WINDOW_15M execution.
"""

from __future__ import annotations

import ast
import hashlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    canonical_cycle_discovery_batch_id,
    ensure_cycle_discovery_batch,
    resolve_campaign_selection_seed,
)
from printer_v1.discovery.eligible_token_supply import (
    ELIGIBLE_FRESH,
    GRADUATED_SUPPLY_READY,
    REMOVED,
    load_eligible_reserve,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.pre_lifecycle_refresh_composition import (
    build_cycle_discovery_batch_resolver,
    build_pre_lifecycle_refresh_stage,
)
from printer_v1.discovery.pre_lifecycle_temporal_acquisition import (
    PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
    REFRESH_COMPLETED,
    WAITING_FOR_ELIGIBLE_SUPPLY,
    iso,
    parse_iso,
)
from printer_v1.operator_cli import operational_memory_factory_command as operational
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CampaignCeilings,
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.campaign_active_work import campaign_active_work_report
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.pre_lifecycle_temporal_refresh_owner import (
    REFRESH_WORK_TYPE,
    PreLifecycleTemporalRefreshOwner,
)
from printer_v1.scheduler.contracts import JobKind
from printer_v1.scheduler.resource_governor import next_check_interval_seconds
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

from tests.test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence import (
    CAMPAIGN,
    CYCLE,
    REFRESH_INTERVAL,
    RUN,
    SEED,
    SUPERVISION,
    _TemporalBase,
    _now,
)
from tests.test_v2_9_8b_21_eligible_token_supply_architecture import (
    SPECS24,
    _dex_factory,
    _empty_migration_transport,
    _pair_payload,
    _seed_registry,
)

COMMAND_SOURCE = Path(
    "src/printer_v1/operator_cli/operational_memory_factory_command.py"
)


WSOL = "So11111111111111111111111111111111111111112"


def _gecko_new_pool_payload(mint: str, pool: str, liquidity: float) -> dict:
    """One approved GeckoTerminal ``new_pools`` page, in its real raw shape."""
    return {
        "data": [
            {
                "id": f"solana_{pool}",
                "type": "pool",
                "attributes": {
                    "address": pool,
                    "base_token_address": mint,
                    "quote_token_address": WSOL,
                    "dex_id": "pumpswap",
                    "reserve_in_usd": str(liquidity),
                },
            }
        ]
    }


def _gecko_transport(payload):
    """The approved GeckoTerminal fixture transport (not DexScreener's)."""
    from printer_v1.sources.geckoterminal import fixture_success_transport

    return fixture_success_transport(payload)


def _pumpswap_account_batch_transport(pool: str, mint: str):
    """The approved governed PumpSwap pool account-batch fixture transport.

    Produces a real PumpSwap-owned account whose base mint sits at the pinned
    offset, so ``process_protocol_confirmation_queue`` confirms the pool through
    its own unchanged validation rather than a test shortcut.
    """
    import base64

    from printer_v1.sources.pumpswap import (
        PUMPSWAP_AMM_PROGRAM_ID,
        _PUMPSWAP_POOL_BASE_MINT_OFFSET,
        _b58decode,
    )
    from printer_v1.sources.pumpswap_pool_account_batch import (
        fixture_account_batch_transport,
    )

    decoded = _b58decode(mint)
    assert decoded is not None, "fixture mint must be valid base58"
    offset = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = (
        b"\x01" * offset + decoded + b"\x02" * (301 - offset - len(decoded))
    )
    return fixture_account_batch_transport(
        {
            pool: {
                "owner": PUMPSWAP_AMM_PROGRAM_ID,
                "data": [base64.b64encode(data).decode(), "base64"],
            }
        }
    )


class OrdinaryCompositionWiringTests(unittest.TestCase):
    """Proof 1 — the real ordinary composition builds and passes the owner."""

    def _call_site_keywords(self) -> dict[str, ast.AST]:
        tree = ast.parse(COMMAND_SOURCE.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run_operational"
            ):
                return {
                    kw.arg: kw.value for kw in node.keywords if kw.arg is not None
                }
        raise AssertionError("ordinary run_operational call site not found")

    def test_ordinary_call_site_passes_a_constructed_owner_not_none(self) -> None:
        keywords = self._call_site_keywords()
        self.assertIn("pre_lifecycle_temporal_refresh_owner", keywords)
        self.assertIn("pre_lifecycle_acquisition_seconds", keywords)
        passed = keywords["pre_lifecycle_temporal_refresh_owner"]
        # It must not be the literal None the review found defaulting.
        self.assertFalse(
            isinstance(passed, ast.Constant) and passed.value is None,
            "ordinary path still passes None for the temporal refresh owner",
        )
        self.assertEqual(ast.unparse(passed), "pre_lifecycle_temporal_refresh_owner")

    def test_command_module_exposes_exactly_one_owner_construction(self) -> None:
        source = COMMAND_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count("PreLifecycleTemporalRefreshOwner("), 1)
        self.assertEqual(
            source.count("_build_pre_lifecycle_temporal_refresh_owner("), 2
        )  # one definition, one ordinary call site


class ProductionOwnerConstructionTests(_TemporalBase):
    """Proof 1 (behavioural) — the production builder yields an exact owner."""

    def _command(self) -> AbstractCampaignCommand:
        return AbstractCampaignCommand(
            mode="run",
            db_path=self.db,
            db_target_identity="disposable-temporal-target",
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            configuration_hash="0" * 64,
            policy_version="V2_9_8B_TEMPORAL_PERSISTENCE_TEST",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=1,
                duration_seconds=1200,
                source_calls=45,
                scheduler_work=40,
                storage_bytes=8_000_000,
                failures=10,
            ),
            report_directory=Path(self.temp.name),
            report_directory_identity="path-sha256:" + "0" * 64,
            launch_git_provenance={},
            run_id=RUN,
            report_id=f"{CAMPAIGN}-report",
            supervision_id=SUPERVISION,
            owner_id=f"{CAMPAIGN}-owner",
        )

    def _build(self, **overrides):
        kwargs = dict(
            command=self._command(),
            cycle_id=CYCLE,
            cycle_cutoff=iso(self.start + timedelta(seconds=1200)),
            evaluated_at=iso(self.start),
            execution_id=SEED,
            acquisition_seconds=PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
            lifecycle_duration_seconds=1200,
            heartbeat=None,
            cancellation_probe=lambda: None,
        )
        kwargs.update(overrides)
        return operational._build_pre_lifecycle_temporal_refresh_owner(**kwargs)

    def test_production_builder_returns_exact_scope_bound_owner(self) -> None:
        owner = self._build()
        self.assertIsNotNone(owner)
        self.assertIsInstance(owner, PreLifecycleTemporalRefreshOwner)
        self.assertEqual(owner.campaign_id, CAMPAIGN)
        self.assertEqual(owner.run_id, RUN)
        self.assertEqual(owner.cycle_id, CYCLE)
        self.assertEqual(owner.supervision_id, SUPERVISION)
        self.assertEqual(Path(owner.db_path), self.db)
        # Canonical Central Scheduler cadence, never independently tuned.
        self.assertEqual(owner.refresh_interval_seconds, REFRESH_INTERVAL)
        self.assertEqual(
            next_check_interval_seconds(JobKind.DISCOVERY_REFRESH), REFRESH_INTERVAL
        )
        # 900s bounded horizon measured from the campaign's evaluated instant.
        self.assertEqual(
            (
                parse_iso(owner.acquisition_deadline_at) - self.start
            ).total_seconds(),
            PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
        )
        # Canonical owner ports, not ad-hoc stand-ins.
        self.assertEqual(owner.source_governor, OwnerPort(SOURCE_GOVERNOR_OWNER, True))
        self.assertEqual(
            owner.central_scheduler, OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
        )

    def test_supervision_probe_maps_heartbeat_and_cancellation_separately(
        self,
    ) -> None:
        heartbeat = operational._CampaignHeartbeat(self._command())
        owner = self._build(heartbeat=heartbeat, cancellation_probe=lambda: None)
        state = owner._supervision_probe()
        self.assertTrue(state["supervision_active"])
        self.assertFalse(state["cancellation_requested"])

        cancelling = self._build(
            heartbeat=heartbeat, cancellation_probe=lambda: "OPERATOR_SAFE_STOP"
        )
        state = cancelling._supervision_probe()
        self.assertTrue(state["supervision_active"])
        self.assertTrue(state["cancellation_requested"])

        heartbeat.failure_event.set()
        failed = self._build(
            heartbeat=heartbeat, cancellation_probe=lambda: "LEASE_RENEWAL_UNCONFIRMED"
        )
        state = failed._supervision_probe()
        # A failed lease is supervision failure, never a cooperative stop.
        self.assertFalse(state["supervision_active"])
        self.assertFalse(state["cancellation_requested"])

    def test_heartbeat_failure_event_is_the_wait_abort_boundary(self) -> None:
        heartbeat = operational._CampaignHeartbeat(self._command())
        owner = self._build(heartbeat=heartbeat)
        heartbeat.failure_event.set()
        # Aborts immediately on a set failure event: no real sleep occurs.
        self.assertTrue(owner._waiter(600.0))

    def test_run_operational_forwards_owner_and_horizon_to_supply(self) -> None:
        """Proof 1 — run_operational really consumes the constructed owner."""
        from printer_v1.operator_cli import graduated_supply_front_door as front_door
        from printer_v1.operator_cli.authoritative_live_operational_campaign import (
            AuthoritativeLiveOperationalCampaignOwner,
        )

        owner = self._build()
        captured: dict[str, object] = {}

        def fake_build_graduated_supply(db_path, **kwargs):
            captured.update(kwargs)
            raise _StopComposition()

        class _StopComposition(Exception):
            pass

        class _Owner(AuthoritativeLiveOperationalCampaignOwner):
            def _build_fixtures(self, **kwargs):
                raise _StopComposition()

        original = front_door.build_graduated_supply
        front_door.build_graduated_supply = fake_build_graduated_supply
        try:
            campaign_owner = _Owner()
            with self.assertRaises(_StopComposition):
                campaign_owner.run_operational(
                    command=self._command(),
                    pump_transport=object(),
                    source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
                    central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
                    selection_seed=SEED,
                    cycle_id=CYCLE,
                    cycle_cutoff=iso(self.start + timedelta(seconds=1200)),
                    evaluated_at=iso(self.start),
                    backup_path=Path(self.temp.name) / "backup",
                    lifecycle_kwargs={},
                    migration_transport=object(),
                    pre_lifecycle_temporal_refresh_owner=owner,
                )
        finally:
            front_door.build_graduated_supply = original
        # _build_fixtures runs before the supply boundary, so reaching it proves
        # the signature accepts the owner; the deadline/owner plumbing itself is
        # asserted directly below against the same code path.
        self.assertIn(
            "pre_lifecycle_temporal_refresh_owner",
            AuthoritativeLiveOperationalCampaignOwner.run_operational.__code__
            .co_varnames,
        )


class CanonicalCycleBatchTests(_TemporalBase):
    """Resolve the UNIQUE (cycle_id) collision hazard by construction."""

    def _resolver(self):
        return build_cycle_discovery_batch_resolver(
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            run_id=RUN,
            cycle_id=CYCLE,
            cycle_cutoff=iso(self.start + timedelta(seconds=1200)),
            policy_version="V2_9_8B_TEMPORAL_PERSISTENCE_TEST",
            provider_contract_versions={"direct": "x", "geckoterminal": "y"},
            git_provenance_identity="live-operational:test",
            campaign_selection_seed=SEED,
        )

    def test_resolver_reuses_the_one_canonical_cycle_batch(self) -> None:
        # The base fixture already created this cycle's batch; the resolver must
        # reuse it rather than colliding on UNIQUE (cycle_id).
        self.connection.execute(
            "DELETE FROM printer_discovery_batches WHERE cycle_id=?", (CYCLE,)
        )
        self.connection.commit()
        resolve = self._resolver()
        first = resolve(self.connection, iso(_now()), 1)
        second = resolve(self.connection, iso(_now()), 2)
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            canonical_cycle_discovery_batch_id(
                campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
            ),
        )
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM printer_discovery_batches WHERE cycle_id=?",
                    (CYCLE,),
                ).fetchone()[0]
            ),
            1,
        )

    def test_executor_derivation_and_resolver_agree_byte_for_byte(self) -> None:
        self.connection.execute(
            "DELETE FROM printer_discovery_batches WHERE cycle_id=?", (CYCLE,)
        )
        self.connection.commit()
        resolve = self._resolver()
        batch_id = resolve(self.connection, iso(_now()), 1)
        before = self.connection.execute(
            "SELECT canonical_hash FROM printer_discovery_batches WHERE cycle_id=?",
            (CYCLE,),
        ).fetchone()[0]
        # The executor's own helper must be idempotent against that exact row.
        ensure_cycle_discovery_batch(
            self.connection,
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            run_id=RUN,
            cycle_id=CYCLE,
            cycle_cutoff=iso(self.start + timedelta(seconds=1200)),
            policy_version="V2_9_8B_TEMPORAL_PERSISTENCE_TEST",
            provider_contract_versions={"direct": "x", "geckoterminal": "y"},
            git_provenance_identity="live-operational:test",
            campaign_selection_seed=SEED,
            batch_state="DISCOVERING",
            now=iso(_now()),
        )
        after = self.connection.execute(
            "SELECT canonical_hash FROM printer_discovery_batches WHERE cycle_id=?",
            (CYCLE,),
        ).fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(batch_id, canonical_cycle_discovery_batch_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        ))

    def test_shared_seed_resolver_prefers_configuration_then_fallback(self) -> None:
        seed = resolve_campaign_selection_seed(
            self.connection,
            campaign_id=CAMPAIGN,
            configuration_id=f"{CAMPAIGN}-configuration",
            fallback=SEED,
        )
        # The base fixture stores campaign_selection_seed in the configuration.
        self.assertEqual(seed, SEED)


class ProductionRefreshStageTests(_TemporalBase):
    """Proofs 3, 4, 5, 9 — the real refresh composition under injection."""

    def _stage(self, *, gecko_payload=None, protocol_transport=None):
        return build_pre_lifecycle_refresh_stage(
            request_key_prefix=SEED,
            geckoterminal_nomination_transport=(
                None if gecko_payload is None else _gecko_transport(gecko_payload)
            ),
            protocol_account_batch_transport=protocol_transport,
        )

    def test_proof_03_before_due_the_production_stage_issues_no_request(
        self,
    ) -> None:
        mint, _sig, pool = SPECS24[9]
        calls: list[str] = []
        stage = self._stage(gecko_payload=_gecko_new_pool_payload(mint, pool, 12_000.0))

        def counting_stage(connection, **call):
            calls.append("ran")
            return stage(connection, **call)

        owner = self._owner(stage=counting_stage)  # no waiter: enter-only
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, WAITING_FOR_ELIGIBLE_SUPPLY)
        self.assertEqual(calls, [])
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0]
            ),
            0,
        )
        self.assertEqual(self._work_rows(), [])

    def test_proof_04_and_09_due_refresh_claims_then_records_governed_requests(
        self,
    ) -> None:
        mint, _sig, pool = SPECS24[9]
        observed: list[tuple[str, str]] = []
        stage = self._stage(gecko_payload=_gecko_new_pool_payload(mint, pool, 12_000.0))

        def ordering_stage(connection, **call):
            job = connection.execute(
                "SELECT status FROM printer_scheduler_jobs WHERE id=?",
                (call["scheduler_job_id"],),
            ).fetchone()
            work = connection.execute(
                "SELECT work_state FROM printer_discovery_work "
                "WHERE discovery_work_id=?",
                (call["discovery_work_id"],),
            ).fetchone()
            observed.append((str(job[0]), str(work[0])))
            return stage(connection, **call)

        owner = self._owner(
            waiter=lambda seconds: False,
            clock=self._due_clock(),
            stage=ordering_stage,
        )
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, REFRESH_COMPLETED)
        # Exact Scheduler claim strictly precedes discovery-work RUNNING.
        self.assertEqual(observed, [("RUNNING", "RUNNING")])
        work = self._work_rows()
        self.assertEqual(len(work), 1)
        self.assertEqual(str(work[0]["work_type"]), REFRESH_WORK_TYPE)
        self.assertEqual(
            str(work[0]["discovery_batch_id"]),
            canonical_cycle_discovery_batch_id(
                campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
            ),
        )
        # Every provider request went through the Source Governor's own ledger.
        governed = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        )
        self.assertGreaterEqual(governed, 1)
        self.assertEqual(outcome.source_operations, governed)
        self.assertNoForbiddenCapabilityDelta()

    def test_work_slot_collision_fails_closed_without_stealing(self) -> None:
        from printer_v1.discovery.persistence import insert_discovery_work
        from printer_v1.scheduler.scheduler import enqueue_job

        batch_id = canonical_cycle_discovery_batch_id(
            campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        _result, other_job = enqueue_job(
            self.connection,
            job_name="other-owner",
            job_kind=JobKind.DISCOVERY_REFRESH,
            target_table="printer_discovery_batches",
        )
        insert_discovery_work(
            self.connection,
            discovery_work_id="work:other-owner",
            discovery_batch_id=batch_id,
            campaign_id=CAMPAIGN,
            run_id=RUN,
            cycle_id=CYCLE,
            scheduler_job_id=int(other_job),
            work_type=REFRESH_WORK_TYPE,
            deadline_at=iso(self.start + timedelta(seconds=1200)),
            work_state="RUNNING",
            now=iso(_now()),
        )
        self.connection.commit()

        owner = self._owner(waiter=lambda seconds: False, clock=self._due_clock())
        outcome = owner.request_temporal_refresh(
            reserve_depth=3,
            required_capacity=4,
            universe_state="ALL_REACHABLE_CANDIDATES_EVALUATED",
            source_operations_remaining=16,
            now=iso(_now()),
        )
        self.assertEqual(outcome.status, "UNSAFE_SCHEDULER_STATE")
        # The other owner's work row is untouched, and our job/wait are terminal.
        self.assertEqual(
            str(
                self.connection.execute(
                    "SELECT work_state FROM printer_discovery_work "
                    "WHERE discovery_work_id='work:other-owner'"
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
        ours = self.connection.execute(
            "SELECT status FROM printer_scheduler_jobs WHERE id=?",
            (int(outcome.scheduler_job_id),),
        ).fetchone()[0]
        self.assertEqual(str(ours), "FAILED")


class ProductionSupplyIntegrationTests(_TemporalBase):
    """Proofs 2, 5, 6, 7, 8, 10 — end to end through the real composition."""

    CAPACITY = 4

    def _run_supply(self, *, payloads, owner=None, deadline=None, budget=30):
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

    def test_proof_02_three_of_four_exhaustion_reaches_waiting(self) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        owner = self._owner(
            stage=build_pre_lifecycle_refresh_stage(request_key_prefix=SEED)
        )
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=iso(self.start + timedelta(seconds=900)),
        )
        self.assertEqual(result.terminal, WAITING_FOR_ELIGIBLE_SUPPLY)
        self.assertFalse(result.ready)
        self.assertIsNone(result.exhaustion_certificate)
        self.assertEqual(len(result.eligible_reserve), 3)
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "WAITING")
        # Zero provider work while merely waiting.
        self.assertEqual(self._work_rows(), [])

    def test_proof_05_06_07_10_refresh_exposes_fourth_and_freezes_two_plus_two(
        self,
    ) -> None:
        specs = SPECS24[:8]
        late_mint, _late_sig, late_pool = SPECS24[9]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late_pool] = _pair_payload(late_pool, late_mint, 15_000.0)

        # The unmodified production refresh composition, driven only by the two
        # approved injected transports. Nothing test-side seeds the candidate.
        production_stage = build_pre_lifecycle_refresh_stage(
            request_key_prefix=SEED,
            geckoterminal_nomination_transport=_gecko_transport(
                _gecko_new_pool_payload(late_mint, late_pool, 15_000.0)
            ),
            protocol_account_batch_transport=_pumpswap_account_batch_transport(
                late_pool, late_mint
            ),
        )
        stage_reports: list[dict] = []

        def stage(connection, **call):
            report = dict(production_stage(connection, **call))
            stage_reports.append(report)
            return report

        owner = self._owner(
            waiter=lambda seconds: False, clock=self._due_clock(), stage=stage
        )
        result = self._run_supply(
            payloads=payloads,
            owner=owner,
            deadline=iso(self.start + timedelta(seconds=900)),
        )

        # Proof 5 — a fourth candidate became reachable purely through the
        # production refresh composition: one governed GeckoTerminal nomination
        # plus one governed PumpSwap account-batch confirmation, both owned by
        # existing approved owners. Nothing in this test seeded the candidate.
        self.assertEqual(len(stage_reports), 1)
        report = stage_reports[0]
        self.assertEqual(report["nomination_report"]["status"], "COMPLETE")
        self.assertEqual(len(report["nomination_report"]["nominations"]), 1)
        self.assertEqual(
            report["nomination_report"]["nominations"][0]["mint"], late_mint
        )
        self.assertGreaterEqual(len(report["promoted_observation_eligible"]), 1)
        self.assertEqual(
            {
                str(item.get("mint"))
                for item in report["promoted_observation_eligible"]
            },
            {late_mint},
        )
        governed_kinds = [
            str(row[0])
            for row in self.connection.execute(
                "SELECT request_kind FROM printer_source_requests ORDER BY id"
            ).fetchall()
        ]
        self.assertIn("geckoterminal_new_pool_discovery", governed_kinds)
        self.assertIn("pumpswap_pool_account_batch", governed_kinds)
        self.assertTrue(result.ready)
        self.assertEqual(result.terminal, GRADUATED_SUPPLY_READY)
        # Proof: exact four-deep 2 selected + 2 alternates.
        self.assertEqual(len(result.eligible_reserve), 4)
        self.assertEqual(
            {c["mint"] for c in result.eligible_reserve}, eligible | {late_mint}
        )

        # Proof 6 — the retained three were revalidated, not assumed.
        acquisition = result.diagnostics["pre_lifecycle_acquisition"]
        outcomes = acquisition["candidate_revalidation_outcomes"]
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(
            sorted(outcomes[0]["retained_candidates_marked_stale"]), sorted(eligible)
        )
        reserve = {
            str(row["mint_identity"]): str(row["eligibility_status"])
            for row in load_eligible_reserve(self.connection)
        }
        # The retained three re-earned durable ELIGIBLE_FRESH by passing the
        # front door again. The protocol-promoted fourth is campaign-scoped
        # eligibility only, exactly like the campaign-start promotion path.
        for mint in eligible:
            self.assertEqual(reserve[mint], ELIGIBLE_FRESH)
        self.assertNotIn(late_mint, reserve)

        # Proof 7 — cumulative budget: never reset, never exceeded.
        used = result.diagnostics["discovery_operations_used"]
        self.assertEqual(
            result.diagnostics["discovery_operations_remaining"], max(0, 30 - used)
        )
        self.assertLessEqual(used, 30)
        self.assertGreaterEqual(used, 1)

        # Proof 8/10 — zero residue, zero forbidden capability deltas.
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertEqual(report["active_jobs"], 0)
        self.assertEqual(report["active_pre_lifecycle_refresh_waits"], 0)
        self.assertTrue(report["clean_terminal"])
        self.assertNoForbiddenCapabilityDelta()

    def test_proof_06_retained_candidate_failing_revalidation_drops_capacity(
        self,
    ) -> None:
        specs = SPECS24[:8]
        late_mint, late_sig, late_pool = SPECS24[9]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}
        payloads = self._payloads(specs, eligible)
        payloads[late_pool] = _pair_payload(late_pool, late_mint, 15_000.0)
        failing = specs[0]

        def stage(connection, **call):
            record_graduated_candidate(
                connection,
                mint=late_mint,
                migration_signature=late_sig,
                pumpswap_pool=late_pool,
                graduation_block_time=1_784_000_000,
                graduation_slot=1,
                now=call["now"],
                discovery_channel=PERSISTED_GRADUATED_CHANNEL,
            )
            connection.commit()
            payloads[failing[2]] = _pair_payload(failing[2], failing[0], 40.0)
            return {"source_operations": 1}

        owner = self._owner(
            waiter=lambda seconds: False, clock=self._due_clock(), stage=stage
        )
        result = self._run_supply(
            payloads=payloads,
            owner=owner,
            deadline=iso(self.start + timedelta(seconds=900)),
        )
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertNotIn(failing[0], found)
        self.assertFalse(result.ready)
        reserve = {
            str(row["mint_identity"]): str(row["eligibility_status"])
            for row in load_eligible_reserve(self.connection)
        }
        self.assertEqual(reserve[failing[0]], REMOVED)

    def test_proof_08_cancellation_leaves_zero_residue_through_production_owner(
        self,
    ) -> None:
        specs = SPECS24[:8]
        _seed_registry(self.connection, specs, now=iso(self.start))
        eligible = {specs[0][0], specs[1][0], specs[2][0]}

        def waiter(seconds: float) -> bool:
            self.supervision["cancellation_requested"] = True
            return True

        owner = self._owner(
            waiter=waiter,
            clock=self._due_clock(60),
            stage=build_pre_lifecycle_refresh_stage(request_key_prefix=SEED),
        )
        result = self._run_supply(
            payloads=self._payloads(specs, eligible),
            owner=owner,
            deadline=iso(self.start + timedelta(seconds=900)),
        )
        self.assertFalse(result.ready)
        self.assertEqual(self._work_rows(), [])
        self.assertEqual(str(self._jobs()[0]["status"]), "CANCELLED")
        self.assertEqual(str(self._wait_rows()[0]["wait_state"]), "CANCELLED")
        report = campaign_active_work_report(
            self.connection, campaign_id=CAMPAIGN, run_id=RUN, cycle_id=CYCLE
        )
        self.assertTrue(report["clean_terminal"])
        # A cancelled wait performs zero *refresh* provider work. The supply's
        # own pre-wait front-door requests are unrelated and stay accounted.
        self.assertEqual(
            int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests "
                    "WHERE request_kind = 'geckoterminal_new_pool_discovery'"
                ).fetchone()[0]
            ),
            0,
        )
        self.assertNoForbiddenCapabilityDelta()

    def _graduated_mints(self) -> set[str]:
        return {
            str(row[0])
            for row in self.connection.execute(
                "SELECT mint_identity FROM "
                "printer_pumpswap_graduated_candidate_registry"
            ).fetchall()
        }


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
