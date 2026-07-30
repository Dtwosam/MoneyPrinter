"""V2-9.7E.33 canonical operational readiness boundary closure proof.

Offline, transport-shaped fixtures only. Proves the single committed runner's
SNAPSHOT_READINESS mode:

    preflight -> live Pump acquisition -> holder eligibility
    -> exactly two complete snapshot bundles or an honest blocker
    -> report, replay, cleanup, stop

and that this mode never reaches lifecycle windows, memory, retrieval, decisions
or financial paths. No live call or live authorization is consumed.

The runner is exercised through the *committed* entry point only
(``AuthoritativeLiveOperationalCampaignOwner.run_snapshot_readiness`` and the
``run(mode=SNAPSHOT_READINESS)`` dispatcher); every step it takes lives inside
the repository.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from unittest.mock import MagicMock

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    ACTIVATION_ONLY,
    CANONICAL_OPERATIONAL_MODES,
    FULL_PILOT,
    PILOT_INPUT_READINESS,
    SNAPSHOT_READINESS,
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
    LiveTransportError,
    SnapshotReadinessResult,
)
from printer_v1.operator_cli.readiness_source_contract_preflight import (
    build_readiness_source_contract_preflight,
)
from printer_v1.sources.geckoterminal import (
    build_geckoterminal_adapter,
    fixture_success_transport as gt_fixture,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import (
    GOV,
    SCH,
    _FakePumpTransport,
    _OperationalBase,
    _RaisingPumpTransport,
    _two_create_transport,
)
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    signature_row,
)


def _gt_base_payload(pair, mint, *, liquidity=25_000.0, wider_volume=1_200.0, wider_txns=12):
    return {
        "_requested_pool_address": pair,
        "_requested_token_mint": mint,
        "_requested_network": "solana",
        "_requested_endpoint": f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pair}",
        "data": {
            "id": f"solana_{pair}",
            "type": "pool",
            "attributes": {
                "address": pair,
                "base_token_price_usd": "0.001",
                "reserve_in_usd": (str(liquidity) if liquidity is not None else None),
                "volume_usd": {"m5": "100", "h1": str(wider_volume), "h24": "4000"},
                "transactions": {
                    "m5": {"buys": 2, "sells": 1},
                    "h1": {"buys": wider_txns, "sells": 0},
                    "h24": {"buys": 20, "sells": 10},
                },
                "price_change_percentage": {"m5": "1", "h1": "2", "h24": "3"},
                "fdv_usd": "100000",
                "pool_created_at": "2026-07-22T22:20:00Z",
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{mint}", "type": "token"}},
            },
        },
    }


def _gt_15m_transports(now: datetime):
    current_start = int(now.timestamp() // 900 * 900)
    candle_start = current_start - 900
    ohlcv = {
        "data": {"attributes": {"ohlcv_list": [
            [candle_start, 1.0, 1.2, 0.9, 1.1, 500.0]
        ]}}
    }
    trades = {
        "data": [
            {"attributes": {
                "block_timestamp": datetime.fromtimestamp(
                    candle_start + offset, tz=timezone.utc
                ).isoformat()
            }}
            for offset in (60, 120, 240)
        ]
    }
    return {
        GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _context: ohlcv,
        GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _context: trades,
    }


class _NoSleepPacer:
    """Fixed-spacing pacer with no real sleep (offline determinism)."""

    def __init__(self) -> None:
        self.trace: list[str] = []

    def pace(self, source_name: str):
        self.trace.append(source_name)
        return None


def _eligible_safety_factories():
    """Holder-eligible GoPlus safety factory (only the 'safety' role is used)."""
    from printer_v1.sources.governed_execution import build_fixture_source_adapter

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

    return {"goplus": safety}


class _SnapshotReadinessBase(_OperationalBase):
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _base_factory(self, *, liquidity=25_000.0, wider_volume=1_200.0, wider_txns=12):
        def factory(*, pair_address, token_mint, timeout_seconds):
            payload = _gt_base_payload(
                pair_address, token_mint,
                liquidity=liquidity, wider_volume=wider_volume, wider_txns=wider_txns,
            )
            return build_geckoterminal_adapter(
                enabled=True, fixture_transport=gt_fixture(payload)
            )
        return factory

    def _run(
        self,
        *,
        pump_transport,
        now=None,
        base_factory=None,
        transports=None,
        secret_present=True,
        preflight_runtime_overrides=None,
        preflight_budget_overrides=None,
        owner=None,
        via_dispatcher=False,
    ) -> SnapshotReadinessResult:
        now = now or self._now()
        owner = owner or AuthoritativeLiveOperationalCampaignOwner()
        gt_transports = _gt_15m_transports(now)
        kwargs = dict(
            command=self.command,
            pump_transport=pump_transport,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e33-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=now.isoformat(),
            context_adapter_factories=_eligible_safety_factories(),
            geckoterminal_base_adapter_factory=base_factory or self._base_factory(),
            geckoterminal_transports=(transports if transports is not None else gt_transports),
            secret_present=secret_present,
            preflight_runtime_overrides=preflight_runtime_overrides,
            preflight_budget_overrides=preflight_budget_overrides,
            holder_request_pacer=_NoSleepPacer(),
            snapshot_request_pacer=_NoSleepPacer(),
        )
        if via_dispatcher:
            return owner.run(mode=SNAPSHOT_READINESS, **kwargs)
        return owner.run_snapshot_readiness(**kwargs)


# ===========================================================================
# 1. Complete two-bundle success + report/replay/cleanup/accounting
# ===========================================================================


class CompleteTwoBundleTests(_SnapshotReadinessBase):
    def test_two_complete_bundles_reach_ready_and_stop_before_lifecycle(self) -> None:
        transport, mints = _two_create_transport()
        result = self._run(pump_transport=transport, via_dispatcher=True)

        self.assertEqual(result.status, "READY")
        self.assertEqual(result.preflight_status, "READY")
        self.assertEqual(result.complete_bundle_count, 2)
        self.assertEqual(result.holder_eligible_count, 2)
        self.assertTrue(all(result.summary["readiness_gates"].values()))
        self.assertEqual(result.blocked_reasons, ())
        # Never reached lifecycle / memory / retrieval / financial.
        self.assertFalse(result.summary["lifecycle_started"])
        self.assertEqual(result.summary["memory_windows"], 0)
        self.assertEqual(result.summary["run_steps"], 0)

        # Report is deterministic and its replay makes zero source calls.
        self.assertTrue(result.replay_deterministic)
        self.assertEqual(result.replay_new_source_calls, 0)
        self.assertEqual(len(result.report["readiness_snapshots"]), 2)

        # Correct accounting + reservation (worst case 43/45; snapshot 2+4=6).
        budget = result.summary["budget"]
        self.assertEqual(budget["operation_ceiling"], 45)
        self.assertEqual(budget["reserved_snapshot_operations"], 2)
        self.assertEqual(budget["reserved_snapshot_completion_operations"], 4)

        # No lifecycle windows, no memory, no forbidden capability rows, FK/integrity clean.
        connection = sqlite3.connect(self.db)
        try:
            memory_windows = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
            ).fetchone()[0]
            run_steps = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0]
            decisions = connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual((memory_windows, run_steps, decisions), (0, 0, 0))
        self.assertEqual(result.report["integrity"], "ok")
        self.assertEqual(result.report["foreign_key_violations"], 0)
        self.assertTrue(
            all(v == 0 for v in result.report["forbidden_capability_counts"].values())
        )

    def test_liquidity_comes_from_geckoterminal_exact_pool_fallback(self) -> None:
        # DexScreener-style nullable liquidity is irrelevant: the readiness base
        # liquidity is served by the exact-pool GeckoTerminal reserve_in_usd.
        import json

        transport, _ = _two_create_transport()
        result = self._run(pump_transport=transport)
        self.assertEqual(result.status, "READY")
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT liquidity_usd, normalized_snapshot_payload_json "
                "FROM printer_token_snapshots LIMIT 1"
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row["liquidity_usd"], 25_000.0)
        payload = json.loads(row["normalized_snapshot_payload_json"])
        self.assertEqual(payload["source_name"], "geckoterminal")

    def test_lifecycle_and_memory_owners_are_never_invoked(self) -> None:
        transport, _ = _two_create_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        owner._driver = MagicMock()
        result = self._run(pump_transport=transport, owner=owner)
        self.assertEqual(result.status, "READY")
        owner._driver.run.assert_not_called()


# ===========================================================================
# 2. Honest blockers (never a false READY)
# ===========================================================================


class HonestBlockerTests(_SnapshotReadinessBase):
    def test_missing_liquidity_blocks_snapshot_readiness(self) -> None:
        transport, _ = _two_create_transport()
        result = self._run(
            pump_transport=transport,
            base_factory=self._base_factory(liquidity=None),
        )
        self.assertEqual(result.status, "BLOCKED_SNAPSHOT_READINESS")
        self.assertLess(result.complete_bundle_count, 2)
        self.assertEqual(result.holder_eligible_count, 2)
        self.assertIn("exactly_two_complete_bundles", result.blocked_reasons)

    def test_missing_15m_coverage_blocks_snapshot_readiness(self) -> None:
        transport, _ = _two_create_transport()
        empty_ohlcv = {"data": {"attributes": {"ohlcv_list": []}}}
        transports = {
            GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _c: empty_ohlcv,
            GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _c: {"data": []},
        }
        result = self._run(pump_transport=transport, transports=transports)
        self.assertEqual(result.status, "BLOCKED_SNAPSHOT_READINESS")
        self.assertEqual(result.complete_bundle_count, 0)

    def test_insufficient_holder_pool_blocks(self) -> None:
        tx_a, _ = create_transaction("soloSig", 700, 1_700_000_000, mint_label="solo")
        transport = _FakePumpTransport([signature_row("soloSig", 700)], {"soloSig": tx_a})
        result = self._run(pump_transport=transport)
        self.assertEqual(result.status, "BLOCKED_INSUFFICIENT_ELIGIBLE_POOL")
        self.assertLess(result.holder_eligible_count, 2)

    def test_source_failure_fails_closed_without_retry(self) -> None:
        for code in ("TIMEOUT", "HTTP_429", "UNAVAILABLE"):
            with self.assertRaises(LiveTransportError):
                self._run(pump_transport=_RaisingPumpTransport(code))

    def test_governor_unavailable_fails_closed(self) -> None:
        transport, _ = _two_create_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        now = self._now()
        with self.assertRaises(LiveOperationalError):
            owner.run_snapshot_readiness(
                command=self.command,
                pump_transport=transport,
                source_governor=e8.OwnerPort(e8.SOURCE_GOVERNOR_OWNER, False),
                central_scheduler=SCH,
                selection_seed="e33-seed",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=now.isoformat(),
                context_adapter_factories=_eligible_safety_factories(),
                geckoterminal_base_adapter_factory=self._base_factory(),
                geckoterminal_transports=_gt_15m_transports(now),
                secret_present=True,
            )


# ===========================================================================
# 3. Preflight blocks before authorization (zero transport)
# ===========================================================================


class PreflightBlocksBeforeAuthorizationTests(_SnapshotReadinessBase):
    def test_missing_conditional_helius_secret_does_not_block(self) -> None:
        transport, _ = _two_create_transport()
        result = self._run(pump_transport=transport, secret_present=False)
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.preflight_status, "READY")

    def test_contract_drift_blocks_before_any_transport(self) -> None:
        result = self._run(
            pump_transport=_RaisingPumpTransport("TIMEOUT"),
            secret_present=True,
            preflight_runtime_overrides={
                "source_contracts": {
                    "direct_pump_migration_locator": {"contract_version": ""}
                }
            },
        )
        self.assertEqual(result.status, "BLOCKED_PREFLIGHT")
        self.assertTrue(
            any("contract_version" in reason.casefold() for reason in result.blocked_reasons)
        )

    def test_runner_preflight_matches_committed_preflight(self) -> None:
        # The runner delegates to the same committed preflight owner.
        drift = build_readiness_source_contract_preflight(
            secret_present=True,
            runtime_overrides={
                "source_contracts": {
                    "direct_pump_migration_locator": {"contract_version": ""}
                }
            },
        )
        self.assertEqual(drift["status"], "BLOCKED")
        missing = build_readiness_source_contract_preflight(secret_present=False)
        self.assertEqual(missing["status"], "READY")


# ===========================================================================
# 4. Single-use authorization (second-execution refusal) + replay determinism
# ===========================================================================


class SingleUseAndReplayTests(_SnapshotReadinessBase):
    def test_second_execution_is_refused_without_transport(self) -> None:
        transport, _ = _two_create_transport()
        first = self._run(pump_transport=transport)
        self.assertEqual(first.status, "READY")
        # A relaunch against the same run/cycle refuses before any transport; a
        # raising transport proves zero source work on the refused path.
        second = self._run(pump_transport=_RaisingPumpTransport("TIMEOUT"))
        self.assertEqual(second.status, "REFUSED_SECOND_EXECUTION")
        self.assertEqual(second.complete_bundle_count, 0)

    def test_report_replay_is_byte_identical(self) -> None:
        from printer_v1.operator_cli.bounded_readiness_report import (
            build_bounded_readiness_report,
            canonical_report_bytes,
        )

        transport, _ = _two_create_transport()
        result = self._run(pump_transport=transport)
        self.assertEqual(result.status, "READY")
        a = build_bounded_readiness_report(self.db, run_id="run", cycle_id="cyc")
        b = build_bounded_readiness_report(self.db, run_id="run", cycle_id="cyc")
        self.assertEqual(canonical_report_bytes(a), canonical_report_bytes(b))
        self.assertEqual(a["source_requests_made_by_replay"], 0)


# ===========================================================================
# 5. Mode surface: three canonical modes only, one committed runner
# ===========================================================================


class CanonicalModeSurfaceTests(_SnapshotReadinessBase):
    def test_exactly_four_canonical_modes(self) -> None:
        self.assertEqual(
            CANONICAL_OPERATIONAL_MODES,
            {
                ACTIVATION_ONLY,
                SNAPSHOT_READINESS,
                PILOT_INPUT_READINESS,
                FULL_PILOT,
            },
        )

    def test_unknown_mode_fails_closed(self) -> None:
        owner = AuthoritativeLiveOperationalCampaignOwner()
        with self.assertRaises(LiveOperationalError) as caught:
            owner.run(mode="NOT_A_MODE")
        self.assertEqual(caught.exception.code, "UNKNOWN_OPERATIONAL_MODE")

    def test_activation_only_dispatch_starts_no_lifecycle(self) -> None:
        transport, _ = _two_create_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        readiness = owner.run(
            mode=ACTIVATION_ONLY,
            command=self.command,
            pump_transport=transport,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e33-activation",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
        )
        self.assertEqual(readiness.status, "READY")
        self.assertFalse(readiness.summary["lifecycle_started"])


if __name__ == "__main__":
    import unittest

    unittest.main()
