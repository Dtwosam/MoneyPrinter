"""V2-9.7E.45 Repair 2C proof — DexScreener fresh-profiles locator (locator-only)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import MappingProxyType

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.graduated_supply_front_door import (
    LOCATOR_MATCHED_REGISTRY,
    LOCATOR_ONLY_NO_GRADUATION_PROOF,
    run_fresh_profile_locator,
)
from printer_v1.sources.pumpswap_graduated_registry import record_graduated_candidate

NOW = "2026-07-24T15:00:00+00:00"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


def _profiles_payload(*mints: str):
    # Provider recency/rank order deliberately reversed to prove order confers no
    # advantage; the locator sorts to canonical identity order.
    return MappingProxyType(
        {
            "pairs": [
                {
                    "baseToken": {"address": m},
                    "pairAddress": _pool(m[:1]),
                    "chainId": "solana",
                }
                for m in reversed(mints)
            ]
        }
    )


class FreshProfileLocatorTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "locator.sqlite3"
        apply_migrations(self.db)
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            record_graduated_candidate(
                conn,
                mint=_mint("A"),
                migration_signature="MigSigA" + "z" * 30,
                pumpswap_pool=_pool("A"),
                graduation_block_time=1_700_000_000,
                graduation_slot=500,
                now=NOW,
            )
        conn.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_registry_match_proceeds_unmatched_is_locator_only(self) -> None:
        # MINT_A is a known graduated candidate; MINT_Z is only surfaced by profiles.
        payload = _profiles_payload(_mint("A"), _mint("Z"))
        report = run_fresh_profile_locator(self.db, transport=lambda _c: payload)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["surfaced_count"], 2)
        self.assertEqual(report["matched_count"], 1)
        self.assertEqual(report["locator_only_count"], 1)
        self.assertEqual(report["matched_mints"], [_mint("A")])
        dispo = {d["mint"]: d["disposition"] for d in report["dispositions"]}
        self.assertEqual(dispo[_mint("A")], LOCATOR_MATCHED_REGISTRY)
        self.assertEqual(dispo[_mint("Z")], LOCATOR_ONLY_NO_GRADUATION_PROOF)

    def test_unverified_profile_never_matched(self) -> None:
        # No surfaced mint is in the registry -> nothing proceeds to selection.
        payload = _profiles_payload(_mint("X"), _mint("Y"))
        report = run_fresh_profile_locator(self.db, transport=lambda _c: payload)
        self.assertEqual(report["matched_count"], 0)
        self.assertEqual(report["matched_mints"], [])
        for d in report["dispositions"]:
            self.assertEqual(d["disposition"], LOCATOR_ONLY_NO_GRADUATION_PROOF)

    def test_provider_order_confers_no_advantage(self) -> None:
        forward = run_fresh_profile_locator(
            self.db, transport=lambda _c: _profiles_payload(_mint("A"), _mint("Z"))
        )
        reversed_ = run_fresh_profile_locator(
            self.db, transport=lambda _c: _profiles_payload(_mint("Z"), _mint("A"))
        )
        self.assertEqual(forward["matched_mints"], reversed_["matched_mints"])
        self.assertEqual(
            [d["mint"] for d in forward["dispositions"]],
            [d["mint"] for d in reversed_["dispositions"]],
        )

    def test_transport_failure_returns_status(self) -> None:
        payload = MappingProxyType(
            {"fixture_status": "rate_limited", "retry_after_seconds": 60}
        )
        report = run_fresh_profile_locator(self.db, transport=lambda _c: payload)
        self.assertEqual(report["status"], "rate_limited")
        self.assertEqual(report["matched_count"], 0)
        self.assertEqual(report["surfaced_count"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
