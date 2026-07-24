"""V2-9.7E.45 Repair 1 proof — canonical graduated-registry bootstrap + isolated export."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.sources.graduated_registry_bootstrap import (
    BootstrapError,
    _row_is_valid,
    bootstrap_from_prior_registry,
    export_isolated_attempt_registry,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    export_graduated_candidates,
    record_graduated_candidate,
)

NOW = "2026-07-24T15:00:00+00:00"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


class GraduatedRegistryBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.prior = self.root / "prior.sqlite3"
        self.canonical = self.root / "canonical.sqlite3"
        apply_migrations(self.prior)
        apply_migrations(self.canonical)
        self._seed_prior()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_prior(self) -> None:
        conn = sqlite3.connect(self.prior)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            for label, slot, bt in (("A", 500, 1_700_000_000), ("B", 501, 1_700_000_100)):
                record_graduated_candidate(
                    conn,
                    mint=_mint(label),
                    migration_signature=f"MigSig{label}" + "z" * 30,
                    pumpswap_pool=_pool(label),
                    graduation_block_time=bt,
                    graduation_slot=slot,
                    now=NOW,
                )
        conn.close()

    def _canonical_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.canonical)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def test_valid_prior_imports_exactly_once(self) -> None:
        conn = self._canonical_conn()
        try:
            report = bootstrap_from_prior_registry(conn, self.prior)
            self.assertEqual(report.imported, 2)
            self.assertEqual(report.skipped, 0)
            self.assertEqual(len(export_graduated_candidates(conn)), 2)
            # Idempotent re-import: nothing new, no duplicates.
            again = bootstrap_from_prior_registry(conn, self.prior)
            self.assertEqual(again.imported, 0)
            self.assertEqual(again.already_present, 2)
            self.assertEqual(len(export_graduated_candidates(conn)), 2)
        finally:
            conn.close()

    def test_validator_fails_closed_on_tamper_and_gaps(self) -> None:
        # The registry itself is immutable (evidence cannot be UPDATEd), so
        # fail-closed validation is proved directly against the row validator: a
        # tampered evidence hash, a missing mint, and a stale contract version all
        # fail closed with an explicit reason.
        conn = self._canonical_conn()
        try:
            bootstrap_from_prior_registry(conn, self.prior)
            good = export_graduated_candidates(conn)[0]
        finally:
            conn.close()
        ok, reason = _row_is_valid(good)
        self.assertTrue(ok, reason)

        tampered = dict(good)
        tampered["confirmation_evidence_hash"] = "0" * 64
        ok, reason = _row_is_valid(tampered)
        self.assertFalse(ok)
        self.assertEqual(reason, "EVIDENCE_HASH_MISMATCH")

        no_mint = dict(good)
        no_mint["mint_identity"] = ""
        ok, reason = _row_is_valid(no_mint)
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_MINT_IDENTITY")

        bad_contract = dict(good)
        bad_contract["contract_version"] = "V0-LEGACY"
        ok, reason = _row_is_valid(bad_contract)
        self.assertFalse(ok)
        self.assertTrue(reason.startswith("INCOMPATIBLE_CONTRACT_VERSION"))

    def test_missing_source_registry_table_aborts(self) -> None:
        empty = self.root / "empty.sqlite3"
        # A DB with no registry table at all.
        sqlite3.connect(empty).close()
        conn = self._canonical_conn()
        try:
            with self.assertRaises(BootstrapError):
                bootstrap_from_prior_registry(conn, empty)
        finally:
            conn.close()

    def test_forbidden_column_aborts_whole_import(self) -> None:
        # A prior registry carrying a campaign column must abort (nothing imported).
        conn = sqlite3.connect(self.prior)
        with conn:
            conn.execute(
                "ALTER TABLE printer_pumpswap_graduated_candidate_registry "
                "ADD COLUMN campaign_id TEXT"
            )
        conn.close()
        cconn = self._canonical_conn()
        try:
            with self.assertRaises(BootstrapError):
                bootstrap_from_prior_registry(cconn, self.prior)
            self.assertEqual(len(export_graduated_candidates(cconn)), 0)
        finally:
            cconn.close()

    def test_isolated_export_is_deterministic_and_candidate_only(self) -> None:
        conn = self._canonical_conn()
        try:
            bootstrap_from_prior_registry(conn, self.prior)
        finally:
            conn.close()
        attempt1 = self.root / "attempt1.sqlite3"
        attempt2 = self.root / "attempt2.sqlite3"
        rep1 = export_isolated_attempt_registry(
            self.canonical, attempt1, export_identity="e45-attempt-1"
        )
        rep2 = export_isolated_attempt_registry(
            self.canonical, attempt2, export_identity="e45-attempt-1"
        )
        self.assertEqual(rep1.exported, 2)
        # Same export identity + same source cohort -> identical provenance hash.
        self.assertEqual(rep1.provenance_hash, rep2.provenance_hash)
        # A fresh attempt receives a genuine persisted cohort.
        aconn = sqlite3.connect(attempt1)
        aconn.row_factory = sqlite3.Row
        try:
            cohort = {r["mint_identity"] for r in export_graduated_candidates(aconn)}
            self.assertEqual(cohort, {_mint("A"), _mint("B")})
            # No campaign/lifecycle/memory tables were populated by the export.
            for tbl in (
                "printer_memory_factory_campaign_token_slots",
                "printer_tracking_queue",
            ):
                self.assertEqual(
                    aconn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0], 0
                )
        finally:
            aconn.close()

    def test_different_export_identity_changes_provenance_hash(self) -> None:
        conn = self._canonical_conn()
        try:
            bootstrap_from_prior_registry(conn, self.prior)
        finally:
            conn.close()
        rep_a = export_isolated_attempt_registry(
            self.canonical, self.root / "a.sqlite3", export_identity="id-a"
        )
        rep_b = export_isolated_attempt_registry(
            self.canonical, self.root / "b.sqlite3", export_identity="id-b"
        )
        self.assertNotEqual(rep_a.provenance_hash, rep_b.provenance_hash)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
