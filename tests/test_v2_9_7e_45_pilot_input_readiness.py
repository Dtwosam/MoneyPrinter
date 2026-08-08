"""V2-9.7E.45 Repair 6 proof — immutable PILOT_INPUT_READY boundary."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import AdmissionAuthority
from printer_v1.operator_cli import authoritative_live_operational_campaign as live_campaign
from printer_v1.operator_cli.pilot_input_readiness import (
    BLOCKED_ACTIVATION,
    BLOCKED_HOLDER,
    BLOCKED_MARKET,
    BLOCKED_SELECTION,
    READINESS_PURPOSE_FUTURE_ACTION,
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    READINESS_READY,
    PilotInputReadinessError,
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
    evaluate_readiness_gates,
    load_pilot_input_ready_bundle,
)

NOW = "2026-07-24T15:00:00+00:00"
EXPIRES = "2026-07-24T15:10:00+00:00"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


def _latest(**over) -> ReadinessCandidate:
    base = ReadinessCandidate(
        mint=_mint("L"),
        pool=_pool("L"),
        market_identity=f"solana-mainnet:pumpswap:{_pool('L')}",
        liquidity_usd=9_723.71,
        liquidity_observed_at=NOW,
        activation_route="GRADUATION_NATIVE",
        holder_eligible=True,
        provenance="LATEST_GRADUATED",
    )
    return replace(base, **over)


def _persisted(**over) -> ReadinessCandidate:
    base = ReadinessCandidate(
        mint=_mint("P"),
        pool=_pool("P"),
        market_identity=f"solana-mainnet:pumpswap:{_pool('P')}",
        liquidity_usd=15_350.10,
        liquidity_observed_at=NOW,
        activation_route="GRADUATION_NATIVE",
        holder_eligible=True,
        provenance="PERSISTED_GRADUATED",
    )
    return replace(base, **over)


class PilotInputReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "readiness.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _build(self, **over):
        kwargs = dict(
            readiness_id="readiness-1",
            latest=_latest(),
            persisted=_persisted(),
            holder_evidence={"latest": "eligible", "persisted": "eligible"},
            source_ledger={"goplus": 2, "public_rpc": 2, "helius_backup": 0},
            selection_seed="seed-45",
            git_provenance_identity="git-45",
            configuration_hash="c" * 64,
            expires_at=EXPIRES,
            now=NOW,
        )
        kwargs.update(over)
        return build_pilot_input_ready_bundle(self.conn, **kwargs)

    def test_all_gates_pass_writes_immutable_bundle(self) -> None:
        bundle = self._build()
        self.assertEqual(bundle["readiness_state"], "PILOT_INPUT_READY")
        self.assertEqual(len(bundle["bundle_hash"]), 64)
        loaded = load_pilot_input_ready_bundle(self.conn, "readiness-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["latest_mint"], _mint("L"))
        self.assertEqual(loaded["persisted_mint"], _mint("P"))
        # Immutable: UPDATE and DELETE both abort.
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "UPDATE printer_pilot_input_readiness_bundle "
                "SET latest_liquidity_usd = 1.0 WHERE readiness_id = 'readiness-1'"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "DELETE FROM printer_pilot_input_readiness_bundle "
                "WHERE readiness_id = 'readiness-1'"
            )

    def test_idempotent_identical_rewrite(self) -> None:
        first = self._build()
        second = self._build()
        self.assertEqual(first["bundle_hash"], second["bundle_hash"])
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_pilot_input_readiness_bundle"
            ).fetchone()[0],
            1,
        )

    def test_conflicting_rewrite_fails_closed(self) -> None:
        self._build()
        with self.assertRaises(PilotInputReadinessError) as ctx:
            # Same id, different content -> immutable conflict.
            self._build(latest=_latest(liquidity_usd=4000.0))
        self.assertEqual(ctx.exception.code, "READINESS_BUNDLE_CONFLICT")

    def test_market_floor_boundary(self) -> None:
        # $2,999.99 fails MARKET; $3,000.00 passes.
        self.assertEqual(
            evaluate_readiness_gates(
                _latest(liquidity_usd=2999.99),
                _persisted(),
                discovery_universe_evaluated=True,
            ),
            BLOCKED_MARKET,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                _latest(liquidity_usd=3000.00),
                _persisted(),
                discovery_universe_evaluated=True,
            ),
            "PILOT_INPUT_READY",
        )

    def test_each_gate_fails_closed(self) -> None:
        self.assertEqual(
            evaluate_readiness_gates(None, _persisted(), discovery_universe_evaluated=True),
            BLOCKED_SELECTION,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                _latest(holder_eligible=False),
                _persisted(),
                discovery_universe_evaluated=True,
            ),
            BLOCKED_HOLDER,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                _latest(activation_route="FABRICATED_CREATE"),
                _persisted(),
                discovery_universe_evaluated=True,
            ),
            BLOCKED_ACTIVATION,
        )

    def test_readiness_candidate_exposes_optional_admission_authority_context(self) -> None:
        self.assertIn("admission_authority", ReadinessCandidate.__dataclass_fields__)

    def test_memory_observation_accepts_truthful_market_present_pool_authority(self) -> None:
        latest = _latest(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            READINESS_READY,
        )

    def test_memory_observation_accepts_truthful_direct_authority_with_carried_route(self) -> None:
        latest = _latest(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            READINESS_READY,
        )

    def test_memory_observation_legacy_candidate_keeps_legacy_route_behavior(self) -> None:
        latest = _latest(holder_eligible=False, memory_observation_eligible=True)
        persisted = _persisted(holder_eligible=False, memory_observation_eligible=True)
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            READINESS_READY,
        )

    def test_memory_observation_unknown_authority_fails_closed(self) -> None:
        latest = _latest(
            admission_authority="UNKNOWN_AUTHORITY",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            BLOCKED_ACTIVATION,
        )

    def test_memory_observation_contradictory_authority_route_fails_closed(self) -> None:
        latest = _latest(
            activation_route="GRADUATION_NATIVE",
            admission_authority="MARKET_PRESENT_POOL",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            BLOCKED_ACTIVATION,
        )

    def test_holder_false_is_memory_context_only_but_future_action_still_blocks(self) -> None:
        latest = _latest(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
            holder_eligible=False,
            memory_observation_eligible=True,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            READINESS_READY,
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
            ),
            BLOCKED_HOLDER,
        )

    def test_future_action_does_not_inherit_market_present_pool_route(self) -> None:
        latest = _latest(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
        )
        persisted = _persisted(
            activation_route="MARKET_PRESENT_POOL",
            admission_authority="MARKET_PRESENT_POOL",
        )
        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
            ),
            BLOCKED_ACTIVATION,
        )

    def test_bundle_surface_preserves_order_and_admission_authority(self) -> None:
        latest = _latest(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            memory_observation_eligible=True,
        )
        persisted = _persisted(
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            memory_observation_eligible=True,
        )
        bundle = self._build(
            latest=latest,
            persisted=persisted,
            readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
        )
        ordered = bundle["ordered_selected_candidates"]
        self.assertEqual([item["mint"] for item in ordered], [latest.mint, persisted.mint])
        self.assertEqual(
            [item["admission_authority"] for item in ordered],
            ["DIRECT_PUMP_PUMPSWAP", "DIRECT_PUMP_PUMPSWAP"],
        )

    def test_campaign_projection_uses_frozen_admission_authority_exactly(self) -> None:
        projector = getattr(live_campaign, "_readiness_admission_authority", None)
        self.assertTrue(callable(projector))
        market = SimpleNamespace(admission_authority=AdmissionAuthority.MARKET_PRESENT_POOL)
        direct = SimpleNamespace(admission_authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP)
        self.assertEqual(projector(market), "MARKET_PRESENT_POOL")
        self.assertEqual(projector(direct), "DIRECT_PUMP_PUMPSWAP")
        self.assertIsNone(projector(None))

    def test_build_raises_when_gate_unmet(self) -> None:
        with self.assertRaises(PilotInputReadinessError) as ctx:
            self._build(persisted=_persisted(holder_eligible=False))
        self.assertEqual(ctx.exception.code, "READINESS_GATE_UNMET")
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_pilot_input_readiness_bundle"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
