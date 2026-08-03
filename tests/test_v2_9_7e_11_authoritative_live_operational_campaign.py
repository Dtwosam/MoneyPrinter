"""V2-9.7E.11 authoritative live operational campaign proof.

Transport-shaped raw responses only. No continuation identity, learning-need,
trigger family or precomputed disposition is injected; the existing classifiers
and policies derive every disposition. Disposable SQLite through migration 036
via the E.8 integration base; a deterministic clock advances the real
15m/1h/4h/5m deadlines (the production wall-clock contract is not compressed).
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
    LivePumpOriginAdapter,
    LiveSecondaryDiscoveryAdapter,
    LiveTransportError,
    NaturalEvidenceDispositionOwner,
    _LivePumpAcquisitionSource,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    _authoritative_promotions_for_run,
    load_report_only,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)
from printer_v1.sources import secondary_discovery as _sd
from printer_v1.sources.pumpfun_origin import (
    CREATE_INDEX_PAGE_SIZE,
    PumpContractError,
    SignatureReference,
    plan_finalized_decode_queue,
    run_acquisition_cycle,
    run_acquisition_from_source,
)
from printer_v1.discovery.combined_executor import FixturePumpSwapProof

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    page_op,
    signature_row,
    tx_op,
    two_create_plan,
)


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)


# ---------------------------------------------------------------------------
# Transport-shaped fakes (raw responses only)
# ---------------------------------------------------------------------------


class _FakePumpTransport:
    """One finalized-create signature page and its create transactions."""

    def __init__(self, page_rows, tx_by_sig, *, empty_after_first=True):
        self.page_rows = page_rows
        self.tx_by_sig = tx_by_sig
        self.empty_after_first = empty_after_first
        self.sig_calls = 0
        self.tx_calls: list[str] = []

    def json_rpc(self, method, params, *, timeout_seconds, byte_ceiling):
        if method == "getSignaturesForAddress":
            self.sig_calls += 1
            before = params[1].get("before")
            if before is not None and self.empty_after_first:
                return []
            return self.page_rows
        if method == "getTransaction":
            self.tx_calls.append(params[0])
            return self.tx_by_sig.get(params[0])
        raise LiveTransportError("UNADOPTED_METHOD", method)


class _RaisingPumpTransport:
    def __init__(self, code):
        self.code = code

    def json_rpc(self, method, params, *, timeout_seconds, byte_ceiling):
        if method == "getSignaturesForAddress":
            raise LiveTransportError(self.code)
        raise AssertionError("transaction fetch must not run after a page fault")


def _two_create_transport():
    tx_a, mint_a = create_transaction("liveSigA", 700, 1_700_000_000, mint_label="liveAlpha")
    tx_b, mint_b = create_transaction("liveSigB", 701, 1_700_000_060, mint_label="liveBravo")
    page = [signature_row("liveSigB", 701), signature_row("liveSigA", 700)]
    return _FakePumpTransport(page, {"liveSigA": tx_a, "liveSigB": tx_b}), [mint_a, mint_b]


# ===========================================================================
# 1. Pump-origin refactor equivalence + gate (fixture path unchanged, live lazy)
# ===========================================================================


class PumpAcquisitionRefactorGateTests(unittest.TestCase):
    def test_fixture_cycle_result_is_unchanged_by_the_shared_kernel(self) -> None:
        operations, mints = two_create_plan()
        result = run_acquisition_cycle(operations)
        self.assertEqual(sorted(o.mint for o in result.observations), sorted(mints))
        self.assertEqual(result.cursor.boundary.signature, "sigB")
        self.assertEqual(result.decode_attempts, 2)

    def test_plan_is_invariant_under_signature_response_order(self) -> None:
        rows = [
            SignatureReference("sigB", 701, "finalized", None),
            SignatureReference("sigA", 700, "finalized", None),
            SignatureReference("sigC", 702, "finalized", None),
        ]
        forward = plan_finalized_decode_queue(rows)
        reordered = plan_finalized_decode_queue(list(reversed(rows)))
        self.assertEqual(
            [r.signature for r in forward.decode_queue],
            [r.signature for r in reordered.decode_queue],
        )
        self.assertEqual([r.signature for r in forward.decode_queue], ["sigA", "sigB", "sigC"])

    def test_failed_and_non_finalized_rows_never_enter_decode(self) -> None:
        rows = [
            SignatureReference("ok", 700, "finalized", None),
            SignatureReference("failed", 701, "finalized", {"InstructionError": []}),
            SignatureReference("unconfirmed", 702, "confirmed", None),
        ]
        plan = plan_finalized_decode_queue(rows)
        self.assertEqual([r.signature for r in plan.decode_queue], ["ok"])
        codes = {r.code for r in plan.rejections}
        self.assertIn("FAILED_TRANSACTION", codes)
        self.assertIn("MISSING_FINALITY", codes)

    def test_live_lazy_mode_fetches_one_transaction_per_admitted_row_only(self) -> None:
        transport, mints = _two_create_transport()
        acquisition = LivePumpOriginAdapter(transport).acquire(
            source_governor=GOV, central_scheduler=SCH
        )
        self.assertEqual(len(acquisition.origin_proofs), 2)
        self.assertEqual(sorted(p.mint for p in acquisition.origin_proofs), sorted(mints))
        # Exactly one getTransaction per admitted finalized create — no prefetch.
        self.assertEqual(len(transport.tx_calls), 2)
        # Fetched in the deterministic (slot, signature) plan order.
        self.assertEqual(transport.tx_calls, ["liveSigA", "liveSigB"])

    def test_live_lazy_mode_makes_no_transaction_call_for_rejected_rows(self) -> None:
        tx_a, _ = create_transaction("keepSig", 700, 1_700_000_000, mint_label="keep")
        page = [
            signature_row("keepSig", 700),
            signature_row("failSig", 701, err={"InstructionError": []}),
            signature_row("pendSig", 702, status="confirmed"),
        ]
        transport = _FakePumpTransport(page, {"keepSig": tx_a})
        acquisition = LivePumpOriginAdapter(transport).acquire(
            source_governor=GOV, central_scheduler=SCH
        )
        self.assertEqual(len(acquisition.origin_proofs), 1)
        self.assertEqual(transport.tx_calls, ["keepSig"])

    def test_fixture_leftover_operations_still_fail_closed(self) -> None:
        operations, _ = two_create_plan()
        with self.assertRaises(PumpContractError) as caught:
            run_acquisition_cycle(operations + (tx_op("tx-extra", {}),))
        self.assertEqual(caught.exception.code, "UNPLANNED_OPERATION")

    def test_malformed_live_signature_response_fails_closed(self) -> None:
        class _BadPages:
            accounting = None

            def __init__(self):
                from printer_v1.sources.pumpfun_origin import _Accounting

                self.accounting = _Accounting()

            def next_signature_page(self):
                return {"rows": "not-a-list"}

            def next_transaction(self, reference):
                raise AssertionError("decode must not run")

            def finalize(self):
                return None

        with self.assertRaises(PumpContractError):
            run_acquisition_from_source(_BadPages())

    def test_live_governor_and_scheduler_bypass_fail_closed(self) -> None:
        transport, _ = _two_create_transport()
        adapter = LivePumpOriginAdapter(transport)
        with self.assertRaises(LiveOperationalError):
            adapter.acquire(
                source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=SCH,
            )
        with self.assertRaises(LiveOperationalError):
            adapter.acquire(
                source_governor=GOV,
                central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, False),
            )

    def test_signature_page_size_ceiling_is_exact(self) -> None:
        rows = [signature_row(f"s{i}", 900 - i) for i in range(CREATE_INDEX_PAGE_SIZE + 1)]
        transport = _FakePumpTransport(rows, {})
        with self.assertRaises(PumpContractError) as caught:
            LivePumpOriginAdapter(transport).acquire(
                source_governor=GOV, central_scheduler=SCH
            )
        self.assertEqual(caught.exception.code, "SIGNATURE_PAGE_SIZE_CEILING")

    def test_unavailable_history_empty_page_fails_closed_to_no_origins(self) -> None:
        transport = _FakePumpTransport([], {})
        acquisition = LivePumpOriginAdapter(transport).acquire(
            source_governor=GOV, central_scheduler=SCH
        )
        self.assertEqual(acquisition.origin_proofs, ())


# ===========================================================================
# 2. Natural-evidence disposition owner (pure categorical map)
# ===========================================================================


class NaturalDispositionOwnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = NaturalEvidenceDispositionOwner()

    def test_ordinary_consolidation_is_a_no_learning_need_stop(self) -> None:
        d = self.owner.derive_from_labels(
            memory_quality_label="CLEAN_MEMORY", outcome_label="CONSOLIDATION"
        )
        self.assertFalse(d.should_continue)
        self.assertTrue(d.ordinary_movement)
        self.assertIsNone(d.trigger_family)
        self.assertEqual(d.evidence_label, "NO_UNRESOLVED_LEARNING_NEED")

    def test_pump_outcome_is_a_natural_continuation_with_trigger(self) -> None:
        d = self.owner.derive_from_labels(
            memory_quality_label="PARTIAL_MEMORY", outcome_label="SHORT_TERM_PUMP"
        )
        self.assertTrue(d.should_continue)
        self.assertTrue(d.meaningful_transition_proven)
        self.assertEqual(d.trigger_family, "FAST_COORDINATED_PUMP")

    def test_dump_and_bleed_and_dead_map_to_distinct_trigger_families(self) -> None:
        mapping = {
            "DUMP": "FAST_DUMP_OR_COLLAPSE",
            "SLOW_BLEED": "FAST_BREAKDOWN_OR_RECLAIM",
            "DEAD": "LIQUIDITY_SHOCK",
        }
        for outcome, family in mapping.items():
            d = self.owner.derive_from_labels(
                memory_quality_label="CLEAN_MEMORY", outcome_label=outcome
            )
            self.assertTrue(d.should_continue, outcome)
            self.assertEqual(d.trigger_family, family, outcome)

    def test_unknown_or_missing_outcome_blocks_rather_than_guesses(self) -> None:
        for outcome in ("OUTCOME_UNKNOWN", "", None):
            d = self.owner.derive_from_labels(
                memory_quality_label="DIRTY_MEMORY", outcome_label=outcome
            )
            self.assertFalse(d.should_continue)
            self.assertIsNone(d.trigger_family)
            self.assertFalse(d.meaningful_transition_proven)


# ===========================================================================
# 3. Bounded live secondary adapter (existing normalizer input shape)
# ===========================================================================


class _FakeSecondaryTransport:
    def __init__(self, bodies, *, fail=()):
        self.bodies = bodies
        self.fail = set(fail)
        self.calls: list[str] = []

    def json_get(self, url, *, params, headers, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        for token, code in self.fail:
            if token in url:
                raise LiveTransportError(code)
        for token, body in self.bodies.items():
            if token in url:
                return body
        raise LiveTransportError("MISSING_FROZEN_FIXTURE", url)


def _lawful_gecko_active_body(*, pool: str, mint: str) -> dict:
    """Return one minimal adopted exact-pool GeckoTerminal response."""
    return {
        "data": {
            "id": f"solana_{pool}",
            "type": "pool",
            "attributes": {
                "address": pool,
                "transactions": {"m5": {"buys": 1, "sells": 1}},
            },
            "relationships": {
                "base_token": {
                    "data": {"id": f"solana_{mint}", "type": "token"}
                },
                "quote_token": {
                    "data": {
                        "id": (
                            "solana_"
                            "So11111111111111111111111111111111111111112"
                        ),
                        "type": "token",
                    }
                },
                "dex": {"data": {"id": "pump-fun", "type": "dex"}},
            },
        }
    }


def _lawful_secondary_bodies(
    pools_by_mint,
    *,
    contract_version: str = _sd.SECONDARY_DISCOVERY_CONTRACT_VERSION,
):
    """Build every decoded frozen body planned by the live adapter."""
    if contract_version != _sd.SECONDARY_DISCOVERY_CONTRACT_VERSION:
        raise ValueError("STALE_FROZEN_SECONDARY_CONTRACT")
    bodies = {"trending_pools": {"data": []}, "token-profiles": []}
    for mint, pool in sorted(dict(pools_by_mint).items()):
        bodies[f"/pools/{pool}"] = _lawful_gecko_active_body(
            pool=str(pool),
            mint=str(mint),
        )
    return bodies


class LiveSecondaryAdapterTests(unittest.TestCase):
    def test_enrichment_emits_governed_source_facts_and_isolates_failures(self) -> None:
        transport = _FakeSecondaryTransport(
            _lawful_secondary_bodies({"MintFixture111": "pool-1"}),
            fail=[("dexscreener", "TIMEOUT")],
        )
        enrichment = LiveSecondaryDiscoveryAdapter(transport).enrich(
            source_governor=GOV,
            central_scheduler=SCH,
            receipt_time="2026-07-21T17:00:00+00:00",
            active_pools=["pool-1"],
        )
        # Gecko trending + one exact pool + one dexscreener attempted.
        self.assertEqual(enrichment.requested, 3)
        self.assertEqual(enrichment.failures, 1)
        dex = enrichment.dexscreener_ops[0]
        self.assertEqual(dex.fixture_status, "failure")
        self.assertEqual(dex.failure_type, "TIMEOUT")
        self.assertEqual(enrichment.gecko_ops[0].source_name, "geckoterminal")

    def test_secondary_owner_bypass_fails_closed(self) -> None:
        transport = _FakeSecondaryTransport({})
        with self.assertRaises(LiveOperationalError):
            LiveSecondaryDiscoveryAdapter(transport).enrich(
                source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=SCH,
                receipt_time="2026-07-21T17:00:00+00:00",
            )


# ===========================================================================
# 4. Full natural operational lifecycle proof + negative matrix
# ===========================================================================


class _OperationalBase(e8._IntegrationBase):
    def _origins_and_pools(self):
        transport, _ = _two_create_transport()
        acquisition = LivePumpOriginAdapter(transport).acquire(
            source_governor=GOV, central_scheduler=SCH
        )
        pools = {p.mint: p.bonding_curve for p in acquisition.origin_proofs}
        mints = sorted(pools)
        return mints[0], mints[1], pools

    def _context_factories(self, clock, continue_mint):
        phase = {"close": 0}

        def market(**_kwargs):
            phase["close"] += 1
            return build_fixture_source_adapter(
                "coingecko",
                fixture_payload={
                    "captured_at": clock.now().isoformat(),
                    "assets": {
                        "bitcoin": {"price_usd": 65000, "change_24h": 2.5},
                        "ethereum": {"price_usd": 3500, "change_24h": 1.5},
                        "solana": {"price_usd": 150, "change_24h": 4.0, "volume_24h": 2_000_000_000},
                    },
                },
            )

        def safety(**kwargs):
            mint = kwargs.get("token_mint")
            return build_fixture_source_adapter(
                "goplus",
                fixture_payload={
                    "token_mint": mint,
                    "mint_authority": None,
                    "freeze_authority": None,
                    "metadata_mutable": False,
                    "total_supply": "1000000000",
                    "top_10_holders": [{"percent": "3"} for _ in range(10)],
                    "lp_info": [{"locked": True}],
                    "risk_flags": [],
                },
            )

        def quote(**kwargs):
            return build_fixture_source_adapter(
                "jupiter_quote",
                fixture_payload={
                    "route_available": True,
                    "route_plan_present": True,
                    "slippage_bps": 50,
                    "price_impact_bps": 5,
                    "freshness_label": "QUOTE_FRESH",
                    "target_status": "TARGET_MATCH",
                    "paper_only_context": True,
                    "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                    "input_mint": kwargs["input_mint"],
                    "output_mint": kwargs["output_mint"],
                },
            )

        return {"coingecko": market, "goplus": safety, "jupiter_quote": quote}

    def _snapshot_factory(self, pools, continue_mint, *, fail_mint=None):
        counts = {mint: 0 for mint in pools}

        def build(*, token_mint, timeout_seconds):
            if fail_mint is not None and token_mint == fail_mint:
                return build_fixture_source_adapter("dexscreener", fixture_kind=FIXTURE_FAILURE)
            counts[token_mint] += 1
            n = counts[token_mint]
            # The continuation token rises across its 15m window (a natural
            # SHORT_TERM_PUMP) then holds; the peer stays flat.
            price = (1.0 + 0.05 * min(n - 1, 8)) if token_mint == continue_mint else 1.0
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": token_mint,
                            "pair_address": pools[token_mint],
                            "price_usd": price,
                            "liquidity_usd": 10000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2000.0,
                            "volume_24h": 10000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 7,
                            "sells_5m": 3,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 1.0,
                            "price_change_1h": 2.0,
                            "price_change_24h": 3.0,
                        }
                    ]
                },
            )

        return build

    def _run(self, *, pump_transport, secondary_transport=None, fail_mint=None,
             pump_is_a=False, fifteen_minute_only=False):
        continue_mint, stop_mint, pools = None, None, None
        # Discover which activated mint will be the pump (continuation) target.
        _a, _b, pools = self._origins_and_pools()
        # The pump target is deterministic: the later-sorted mint gets the pump
        # price path; the earlier-sorted mint stays flat/ordinary. ``pump_is_a``
        # swaps the two roles so the barrier's per-token attribution can be
        # proven independent of which token closes first.
        if pump_is_a:
            stop_mint, continue_mint = _b, _a
        else:
            stop_mint, continue_mint = _a, _b
        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        owner = AuthoritativeLiveOperationalCampaignOwner()
        kwargs = {
            "snapshot_adapter_factory": self._snapshot_factory(
                pools, continue_mint, fail_mint=fail_mint
            ),
            "context_adapter_factories": self._context_factories(clock, continue_mint),
            "_window_seconds": 900.0,
            "_continuation_seconds": 2700.0,
            "_sleep": clock.sleep,
            "_monotonic": clock.monotonic,
            "total_duration_seconds": 20_000.0,
            "launch_provenance": e8._provenance(),
        }
        # V2-9.7E.41 graduation-only law: the two candidates are graduated to
        # their confirmed PumpSwap pools (the origin bonding-curve address, keeping
        # the mint-keyed lifecycle consistent) so the operational campaign selects
        # lawful graduated candidates.
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        with (
            patch("printer_v1.operator_cli.one_command_15m_factory._now", clock.now),
            patch("printer_v1.sources.contracts.datetime", e9._ClockDateTime),
        ):
            result = owner.run_operational(
                command=self.command,
                pump_transport=pump_transport,
                secondary_transport=secondary_transport,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="e11-natural-seed",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=self.backup,
                lifecycle_kwargs=kwargs,
                graduation_proofs=graduation_proofs,
                fifteen_minute_only=fifteen_minute_only,
            )
        return result, continue_mint, stop_mint


class NaturalOperationalLifecycleProofTests(_OperationalBase):
    def test_natural_two_token_operational_campaign_full_proof(self) -> None:
        transport, mints = _two_create_transport()
        result, continue_mint, stop_mint = self._run(pump_transport=transport)
        report = result.lifecycle
        self.assertTrue(result.lifecycle_started)
        self.assertEqual(report["run_status"], "COMPLETED")

        # Two finalized origins → two atomic activations.
        self.assertEqual(len(result.activation.activated_slots), 2)
        self.assertEqual(
            {s["mint_identity"] for s in result.activation.activated_slots},
            set(mints),
        )

        closes = [
            (s["step_kind"], s["token_mint"], s["step_status"])
            for s in report["steps"]
            if s["step_kind"] in {"WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
        ]
        # Both terminal 15m closes; one natural continuation to terminal 1h/4h.
        self.assertIn(("WINDOW_CLOSE", stop_mint, "SUCCEEDED"), closes)
        self.assertIn(("WINDOW_CLOSE", continue_mint, "SUCCEEDED"), closes)
        self.assertIn(("CONTINUATION_CLOSE", continue_mint, "SUCCEEDED"), closes)
        self.assertIn(("LONG_CONTINUATION_CLOSE", continue_mint, "SUCCEEDED"), closes)
        self.assertNotIn(("CONTINUATION_CLOSE", stop_mint, "SUCCEEDED"), closes)

        close_results = {
            s["token_mint"]: json.loads(s["result_json"])
            for s in report["steps"]
            if s["step_kind"] == "WINDOW_CLOSE"
        }
        # Natural stop: valid no-5m case, derived (no predeclared disposition).
        stop = close_results[stop_mint]
        self.assertEqual(stop["support_5m"]["verdict"], "VALID_NO_CAPTURE")
        self.assertIsNone(stop["support_5m"]["window_5m_id"])
        self.assertEqual(stop["continuation_plan"]["verdict"], "STOP_AFTER_15M")
        # Natural continuation: one naturally eligible support-only 5m capture.
        cont = close_results[continue_mint]
        self.assertIsNotNone(cont["support_5m"]["window_5m_id"])
        self.assertEqual(cont["support_5m"]["proof_evidence"], "SHORT_TERM_PUMP_OBSERVED")
        self.assertEqual(cont["support_5m"]["trigger_family"], "FAST_COORDINATED_PUMP")
        self.assertTrue(cont["continuation_plan"]["enqueue_ok"])

        # E.19 valid clean contexts preserve both clean terminal 15m memories
        # plus the continuing token's clean terminal 4h memory.
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            promotions = _authoritative_promotions_for_run(connection, report["run_id"])
            dirty = connection.execute(
                """SELECT COUNT(*) FROM printer_episodes e
                   JOIN printer_memory_factory_run_steps s
                     ON s.memory_window_id=e.memory_window_id
                   WHERE s.run_id=? AND e.memory_quality_label!='CLEAN_MEMORY'""",
                (report["run_id"],),
            ).fetchone()[0]
            support_windows = connection.execute(
                "SELECT window_kind FROM printer_memory_windows "
                "WHERE window_kind='WINDOW_5M_MICRO_EVENT'"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(len(promotions), 3)
        self.assertEqual(
            sorted(p["window_kind"] for p in promotions.values()),
            ["WINDOW_15M", "WINDOW_15M", "WINDOW_4H"],
        )
        self.assertEqual(dirty, 0)
        self.assertEqual(len(support_windows), 1)  # support-only, never promoted

        # Terminal 4h validation, complete cleanup, zero retrieval/financial deltas.
        self.assertTrue(report["four_hour_terminal_validation"]["complete"])
        self.assertEqual(report["pending_or_running_run_steps"], 0)
        self.assertEqual(report["running_jobs_after_stop"], 0)
        self.assertTrue(all(v == 0 for v in report["forbidden_deltas"].values()))

        # Deterministic report and zero-source replay.
        replay_a = load_report_only(self.db, report["run_id"])
        replay_b = load_report_only(self.db, report["run_id"])
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(replay_a["replay"]["new_source_calls"], 0)

    def test_governed_secondary_enrichment_flows_through_existing_normalizers(self) -> None:
        transport, _ = _two_create_transport()
        secondary = _FakeSecondaryTransport(
            {"trending_pools": {"data": []}, "token-profiles": []},
            fail=[("/pools/", "UNAVAILABLE")],  # exact-pool lane fault is isolated
        )
        result, _cont, _stop = self._run(
            pump_transport=transport, secondary_transport=secondary
        )
        self.assertEqual(result.lifecycle["run_status"], "COMPLETED")
        # Secondary transport was actually exercised (governed enrichment).
        self.assertTrue(any("geckoterminal" in url for url in secondary.calls))

    def test_token_local_failure_isolates_and_does_not_corrupt_peer(self) -> None:
        transport, _ = _two_create_transport()
        _a, _b, _pools = self._origins_and_pools()
        # Fail the peer (stop) token's snapshots; the continuation token survives.
        result, continue_mint, stop_mint = self._run(
            pump_transport=transport, fail_mint=_a
        )
        report = result.lifecycle
        a_steps = [s for s in report["steps"] if s["token_mint"] == stop_mint]
        self.assertTrue(any(s["step_status"] == "FAILED" for s in a_steps))
        self.assertEqual(report["pending_or_running_run_steps"], 0)
        self.assertEqual(report["running_jobs_after_stop"], 0)


class OperationalNegativeMatrixTests(_OperationalBase):
    def _minimal_lifecycle_kwargs(self):
        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        return {
            "snapshot_adapter_factory": self._snapshot_factory({}, None),
            "context_adapter_factories": self._context_factories(clock, None),
            "_window_seconds": 900.0,
            "_continuation_seconds": 2700.0,
            "_sleep": clock.sleep,
            "_monotonic": clock.monotonic,
            "total_duration_seconds": 20_000.0,
            "launch_provenance": e8._provenance(),
        }

    def test_insufficient_pool_one_origin_activates_nothing(self) -> None:
        tx_a, _ = create_transaction("soloSig", 700, 1_700_000_000, mint_label="solo")
        transport = _FakePumpTransport([signature_row("soloSig", 700)], {"soloSig": tx_a})
        owner = AuthoritativeLiveOperationalCampaignOwner()
        result = owner.run_operational(
            command=self.command,
            pump_transport=transport,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e11-natural-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs=self._minimal_lifecycle_kwargs(),
        )
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(len(result.activation.activated_slots), 0)

    def test_origin_miss_no_creates_activates_nothing(self) -> None:
        transport = _FakePumpTransport([], {})
        owner = AuthoritativeLiveOperationalCampaignOwner()
        result = owner.run_operational(
            command=self.command,
            pump_transport=transport,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e11-natural-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs=self._minimal_lifecycle_kwargs(),
        )
        self.assertFalse(result.lifecycle_started)

    def test_liquidity_source_unavailability_binds_ownership_and_starts_nothing(self) -> None:
        supply = SimpleNamespace(
            graduation_proofs={},
            holder_reserve_supply=(),
            graduated_supply=(),
            front_door_report={
                "candidates": [{
                    "mint": "mint-a",
                    "pool": "pool-a",
                    "eligible": False,
                    "rejection": "LIQUIDITY_SOURCE_dexscreener_transport_failure",
                    "liquidity": {
                        "status": "LIQUIDITY_UNPROVEN",
                        "liquidity_usd": None,
                        "mint": "mint-a",
                        "pool": "pool-a",
                        "reason": "LIQUIDITY_SOURCE_dexscreener_transport_failure",
                        "detailed_reason": "No route to host",
                        "source_status": "FAILED",
                        "outcome_category": "LIQUIDITY_SOURCE_UNAVAILABLE",
                        "source_request_id": 101,
                        "source_response_id": None,
                        "source_failure_id": 51,
                        "failure_type": "dexscreener_transport_failure",
                    },
                }],
                "source_operation_ledger": {"liquidity_requests": 1},
            },
            discovery_report={"source_operation_ledger": {"source_requests": 0}},
            diagnostics={
                "stage_local_source_requests": 1,
                "shortage_classification": "SOURCE_AVAILABILITY_FAILURE",
                "exhaustion_certificate": {
                    "campaign_id": self.command.campaign_id,
                    "execution_id": "execution-liquidity-blocked",
                    "run_id": self.command.run_id,
                    "cycle_id": "cyc",
                    "provider_failures": 1,
                },
                "eligible_reserve_count": 0,
                "discovery_rounds": 1,
            },
        )
        owner = AuthoritativeLiveOperationalCampaignOwner()
        with patch(
            "printer_v1.operator_cli.graduated_supply_front_door.build_graduated_supply",
            return_value=supply,
        ) as build_supply:
            result = owner.run_operational(
                command=self.command,
                pump_transport=_FakePumpTransport([], {}),
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="execution-liquidity-blocked",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=self.backup,
                lifecycle_kwargs=self._minimal_lifecycle_kwargs(),
                migration_transport=lambda _context: {},
            )
        kwargs = build_supply.call_args.kwargs
        self.assertEqual(kwargs["campaign_id"], self.command.campaign_id)
        self.assertEqual(kwargs["execution_id"], "execution-liquidity-blocked")
        self.assertEqual(kwargs["run_id"], self.command.run_id)
        self.assertEqual(kwargs["cycle_id"], "cyc")
        self.assertEqual(
            result.activation.first_terminal_cause,
            "SOURCE_AVAILABILITY_FAILURE",
        )
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(result.lifecycle["run_status"], "NOT_STARTED")
        self.assertEqual(
            result.lifecycle["terminal_reporting"]["campaign_scheduler_calls"],
            0,
        )

    def test_transport_faults_fail_closed_without_retry(self) -> None:
        for code in ("TIMEOUT", "HTTP_429", "UNAVAILABLE", "MALFORMED"):
            transport = _RaisingPumpTransport(code)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            with self.assertRaises(LiveTransportError):
                owner.run_operational(
                    command=self.command,
                    pump_transport=transport,
                    source_governor=GOV,
                    central_scheduler=SCH,
                    selection_seed="e11-natural-seed",
                    cycle_id="cyc",
                    cycle_cutoff=e8.CUTOFF,
                    evaluated_at=e8.NOW,
                    backup_path=self.backup,
                    lifecycle_kwargs=self._minimal_lifecycle_kwargs(),
                )

    def test_governor_or_scheduler_unavailable_fails_closed(self) -> None:
        transport, _ = _two_create_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        with self.assertRaises(LiveOperationalError):
            owner.run_operational(
                command=self.command,
                pump_transport=transport,
                source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=SCH,
                selection_seed="e11-natural-seed",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=self.backup,
                lifecycle_kwargs=self._minimal_lifecycle_kwargs(),
            )

    def test_fixture_plan_is_rejected_in_operational_mode(self) -> None:
        transport, _ = _two_create_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        for forbidden in (
            {"compressed_two_token_proof_plan": object()},
            {"operational_natural_disposition": True},
        ):
            kwargs = self._minimal_lifecycle_kwargs()
            kwargs.update(forbidden)
            with self.assertRaises(LiveOperationalError) as caught:
                owner.run_operational(
                    command=self.command,
                    pump_transport=transport,
                    source_governor=GOV,
                    central_scheduler=SCH,
                    selection_seed="e11-natural-seed",
                    cycle_id="cyc",
                    cycle_cutoff=e8.CUTOFF,
                    evaluated_at=e8.NOW,
                    backup_path=self.backup,
                    lifecycle_kwargs=kwargs,
                )
            self.assertEqual(caught.exception.code, "FIXTURE_PLAN_REJECTED_OPERATIONALLY")


# ===========================================================================
# 5. Readiness-only mode (no lifecycle windows)
# ===========================================================================


class ReadinessOnlyModeTests(_OperationalBase):
    def test_readiness_reaches_handoff_but_starts_no_lifecycle(self) -> None:
        transport, mints = _two_create_transport()
        secondary = _FakeSecondaryTransport(
            {"trending_pools": {"data": []}, "token-profiles": []},
            fail=[("/pools/", "UNAVAILABLE")],  # exact-pool lane fault is isolated
        )
        owner = AuthoritativeLiveOperationalCampaignOwner()
        _a, _b, pools = self._origins_and_pools()
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        readiness = owner.run_readiness_only(
            command=self.command,
            pump_transport=transport,
            secondary_transport=secondary,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e11-readiness-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            graduation_proofs=graduation_proofs,
        )
        self.assertEqual(readiness.status, "READY")
        self.assertEqual(len(readiness.activated_slots), 2)
        self.assertEqual(readiness.summary["origins_confirmed"], 2)
        self.assertFalse(readiness.summary["lifecycle_started"])
        self.assertEqual(readiness.replay_new_source_calls, 0)

        # No lifecycle windows or run steps were ever scheduled.
        connection = sqlite3.connect(self.db)
        try:
            run_steps = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0]
            memory_windows = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
            ).fetchone()[0]
            active_first_15m = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE job_name LIKE 'window15m:%' AND status IN "
                "('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(run_steps, 0)
        self.assertEqual(memory_windows, 0)
        self.assertEqual(active_first_15m, 0)
        self.assertEqual(readiness.summary["active_lifecycle_jobs_after_cleanup"], 0)


# ===========================================================================
# 6. V2-9.7E.11 fail-closed repair proofs (four defects)
# ===========================================================================


class _RecordingGovernor:
    """Source Governor owner port exposing an explicit per-request admission hook.

    ``admit`` is consulted immediately before each secondary transport call; a
    falsy return fails closed with zero HTTP.
    """

    owner_kind = SOURCE_GOVERNOR_OWNER

    def __init__(self, *, available: bool = True, approve: bool = True) -> None:
        self.available = available
        self._approve = approve
        self.admitted: list[tuple[str, str]] = []

    def admit(self, *, source_name: str, request_kind: str) -> bool:
        self.admitted.append((source_name, request_kind))
        return self._approve


class GovernorApprovalBeforeSecondaryTransportTests(unittest.TestCase):
    """Defect 1 — explicit Governor approval + Scheduler ownership before transport."""

    def test_governor_denial_makes_zero_secondary_http_calls(self) -> None:
        transport = _FakeSecondaryTransport({"trending_pools": {"data": []}})
        gov = _RecordingGovernor(approve=False)
        with self.assertRaises(LiveOperationalError) as caught:
            LiveSecondaryDiscoveryAdapter(transport).enrich(
                source_governor=gov,
                central_scheduler=SCH,
                receipt_time="2026-07-21T17:00:00+00:00",
                active_pools=["pool-1"],
            )
        self.assertEqual(caught.exception.code, "SECONDARY_REQUEST_DENIED")
        # Zero transport, and approval was sought before any transport.
        self.assertEqual(transport.calls, [])
        self.assertEqual(len(gov.admitted), 1)

    def test_missing_scheduler_ownership_makes_zero_http_calls(self) -> None:
        transport = _FakeSecondaryTransport({"trending_pools": {"data": []}})
        with self.assertRaises(LiveOperationalError):
            LiveSecondaryDiscoveryAdapter(transport).enrich(
                source_governor=GOV,
                central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, False),
                receipt_time="2026-07-21T17:00:00+00:00",
                active_pools=["pool-1"],
            )
        self.assertEqual(transport.calls, [])

    def test_unavailable_governor_makes_zero_http_calls(self) -> None:
        transport = _FakeSecondaryTransport({"trending_pools": {"data": []}})
        with self.assertRaises(LiveOperationalError):
            LiveSecondaryDiscoveryAdapter(transport).enrich(
                source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=SCH,
                receipt_time="2026-07-21T17:00:00+00:00",
            )
        self.assertEqual(transport.calls, [])

    def test_every_transport_is_individually_admitted(self) -> None:
        transport = _FakeSecondaryTransport(
            {"trending_pools": {"data": []}, "token-profiles": []}
        )
        gov = _RecordingGovernor(approve=True)
        enrichment = LiveSecondaryDiscoveryAdapter(transport).enrich(
            source_governor=gov,
            central_scheduler=SCH,
            receipt_time="2026-07-21T17:00:00+00:00",
            active_pools=["pool-1"],
        )
        # One admission per transport call; admissions == governed requests.
        self.assertEqual(len(gov.admitted), enrichment.requested)
        self.assertEqual(len(gov.admitted), len(transport.calls))


class RejectDirtyAndDoNotTrainEvidenceTests(unittest.TestCase):
    """Defect 2 — ineligible memory quality fails closed regardless of outcome."""

    def setUp(self) -> None:
        self.owner = NaturalEvidenceDispositionOwner()

    def test_dirty_memory_with_pump_outcome_does_not_continue_or_capture(self) -> None:
        d = self.owner.derive_from_labels(
            memory_quality_label="DIRTY_MEMORY", outcome_label="SHORT_TERM_PUMP"
        )
        self.assertFalse(d.should_continue)
        self.assertIsNone(d.trigger_family)
        self.assertFalse(d.meaningful_transition_proven)
        self.assertEqual(d.evidence_label, "INELIGIBLE_15M_MEMORY_QUALITY")

    def test_do_not_train_memory_with_mapped_outcome_does_not_continue(self) -> None:
        for quality in ("DO_NOT_TRAIN", "DO_NOT_TRAIN_MEMORY"):
            d = self.owner.derive_from_labels(
                memory_quality_label=quality, outcome_label="DUMP"
            )
            self.assertFalse(d.should_continue, quality)
            self.assertIsNone(d.trigger_family, quality)

    def test_other_ineligible_quality_fails_closed(self) -> None:
        for quality in ("AUDIT_ONLY_MEMORY", "STALE_MEMORY", "", None, "UNKNOWN"):
            d = self.owner.derive_from_labels(
                memory_quality_label=quality, outcome_label="SHORT_TERM_PUMP"
            )
            self.assertFalse(d.should_continue, quality)
            self.assertIsNone(d.trigger_family, quality)

    def test_clean_eligible_pump_evidence_may_continue(self) -> None:
        for quality in ("CLEAN_MEMORY", "PARTIAL_MEMORY"):
            d = self.owner.derive_from_labels(
                memory_quality_label=quality, outcome_label="SHORT_TERM_PUMP"
            )
            self.assertTrue(d.should_continue, quality)
            self.assertTrue(d.meaningful_transition_proven, quality)
            self.assertEqual(d.trigger_family, "FAST_COORDINATED_PUMP", quality)


class ReadinessFailClosedTests(_OperationalBase):
    """Defect 3 — readiness starts non-ready and only becomes READY on full success."""

    def _readiness(self, transport, **kwargs):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_readiness_only(
            command=self.command,
            pump_transport=transport,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e11-readiness-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            **kwargs,
        )

    def test_zero_origin_activation_is_not_ready(self) -> None:
        readiness = self._readiness(_FakePumpTransport([], {}))
        self.assertNotEqual(readiness.status, "READY")
        self.assertEqual(len(readiness.activated_slots), 0)
        self.assertFalse(readiness.summary["readiness_gates"]["exactly_two_atomic_slots"])

    def test_single_origin_activation_is_not_ready(self) -> None:
        tx_a, _ = create_transaction("soloSig", 700, 1_700_000_000, mint_label="solo")
        transport = _FakePumpTransport([signature_row("soloSig", 700)], {"soloSig": tx_a})
        readiness = self._readiness(transport)
        self.assertNotEqual(readiness.status, "READY")
        self.assertLess(len(readiness.activated_slots), 2)

    def test_transport_fault_fails_closed_without_ready(self) -> None:
        with self.assertRaises(LiveTransportError):
            self._readiness(_RaisingPumpTransport("TIMEOUT"))

    def test_ready_only_after_exact_two_slot_atomic_handoff_and_cleanup(self) -> None:
        transport, mints = _two_create_transport()
        _a, _b, pools = self._origins_and_pools()
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        readiness = self._readiness(transport, graduation_proofs=graduation_proofs)
        self.assertEqual(readiness.status, "READY")
        self.assertEqual(len(readiness.activated_slots), 2)
        gates = readiness.summary["readiness_gates"]
        self.assertTrue(all(gates.values()))
        self.assertEqual(readiness.summary["blocked_reasons"], ())
        self.assertEqual(
            {s["mint_identity"] for s in readiness.activated_slots}, set(mints)
        )
        self.assertEqual(readiness.summary["active_lifecycle_jobs_after_cleanup"], 0)


class TwoTerminalCloseBarrierTests(_OperationalBase):
    """Defect 4 — operational disposition waits for both terminal 15m closes."""

    def _assert_pump_continues(self, report, cont, stop) -> None:
        close_results = {
            s["token_mint"]: json.loads(s["result_json"])
            for s in report["steps"]
            if s["step_kind"] == "WINDOW_CLOSE"
        }
        self.assertTrue(close_results[cont]["continuation_plan"]["enqueue_ok"])
        self.assertIsNotNone(close_results[cont]["support_5m"]["window_5m_id"])
        self.assertEqual(
            close_results[stop]["continuation_plan"]["verdict"], "STOP_AFTER_15M"
        )
        self.assertEqual(
            close_results[stop]["support_5m"]["verdict"], "VALID_NO_CAPTURE"
        )
        # No lingering deferred markers once the barrier has released.
        for cr in close_results.values():
            self.assertNotIn("DEFERRED", cr["continuation_plan"].get("verdict", ""))
            self.assertNotIn("DEFERRED", cr["support_5m"].get("verdict", ""))

    def test_first_close_alone_schedules_no_continuation(self) -> None:
        import printer_v1.operator_cli.one_command_15m_factory as factory

        transport, _ = _two_create_transport()
        real = factory._natural_disposition_schedule
        observed = []

        def spy(conn, *, run_id, close_step, window_id, continuation_seconds):
            attached = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE run_id=? AND step_kind='WINDOW_CLOSE' "
                "AND memory_window_id IS NOT NULL",
                (run_id,),
            ).fetchone()[0]
            observed.append(int(attached))
            return real(
                conn,
                run_id=run_id,
                close_step=close_step,
                window_id=window_id,
                continuation_seconds=continuation_seconds,
            )

        with patch.object(factory, "_natural_disposition_schedule", spy):
            result, cont, stop = self._run(pump_transport=transport)
        self.assertEqual(result.lifecycle["run_status"], "COMPLETED")
        # Disposition scheduling only ever runs once BOTH terminal 15m closes
        # exist — the first close alone never schedules continuation or support.
        self.assertTrue(observed)
        self.assertTrue(all(count == 2 for count in observed), observed)
        self._assert_pump_continues(result.lifecycle, cont, stop)

    def test_both_terminal_closes_resolve_with_no_deferred_markers(self) -> None:
        # After the full campaign, the barrier has released: neither token's
        # persisted close carries a lingering deferred marker, and the pump token
        # continued while the peer stopped.
        transport, _ = _two_create_transport()
        result, cont, stop = self._run(pump_transport=transport)
        self.assertEqual(result.lifecycle["run_status"], "COMPLETED")
        self._assert_pump_continues(result.lifecycle, cont, stop)


class BarrierPerTokenOrderIndependenceTests(unittest.TestCase):
    """Defect 4 — the per-token evaluator used at barrier release is order-free.

    The barrier evaluates each closed token via ``derive_natural_disposition``,
    reading only that token's own 15m window. Deriving the two tokens in either
    order therefore yields identical per-token continuation, stop and support
    decisions, so close-arrival order cannot change the outcome.
    """

    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE printer_memory_windows "
            "(id INTEGER PRIMARY KEY, memory_quality_label TEXT, "
            " outcome_label TEXT, window_kind TEXT)"
        )
        conn.execute(
            "INSERT INTO printer_memory_windows VALUES "
            "(1,'CLEAN_MEMORY','SHORT_TERM_PUMP','WINDOW_15M')"
        )
        conn.execute(
            "INSERT INTO printer_memory_windows VALUES "
            "(2,'CLEAN_MEMORY','CONSOLIDATION','WINDOW_15M')"
        )
        return conn

    def test_per_window_disposition_is_close_order_independent(self) -> None:
        from printer_v1.operator_cli.authoritative_live_operational_campaign import (
            derive_natural_disposition,
        )

        conn = self._conn()
        try:
            forward = [derive_natural_disposition(conn, 1), derive_natural_disposition(conn, 2)]
            reverse = [derive_natural_disposition(conn, 2), derive_natural_disposition(conn, 1)]
        finally:
            conn.close()
        pump_fwd, stop_fwd = forward
        stop_rev, pump_rev = reverse
        # Pump token continues with its trigger; peer stops — identical either order.
        self.assertEqual(
            (pump_fwd.should_continue, pump_fwd.trigger_family),
            (pump_rev.should_continue, pump_rev.trigger_family),
        )
        self.assertEqual(
            (stop_fwd.should_continue, stop_fwd.trigger_family),
            (stop_rev.should_continue, stop_rev.trigger_family),
        )
        self.assertTrue(pump_fwd.should_continue)
        self.assertEqual(pump_fwd.trigger_family, "FAST_COORDINATED_PUMP")
        self.assertFalse(stop_fwd.should_continue)
        self.assertIsNone(stop_fwd.trigger_family)


if __name__ == "__main__":
    unittest.main()
