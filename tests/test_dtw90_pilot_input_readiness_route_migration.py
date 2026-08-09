"""DTW-90 — migration 053 readiness-route persistence repair proof."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import (
    MIGRATIONS_DIR,
    apply_migrations,
    canonical_migration_count,
    canonical_migration_names,
    validate_migration_ledger,
)
from printer_v1.operator_cli.pilot_input_readiness import (
    BLOCKED_ACTIVATION,
    READINESS_PURPOSE_FUTURE_ACTION,
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    READINESS_READY,
    PilotInputReadinessError,
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
    evaluate_readiness_gates,
    load_pilot_input_ready_bundle,
)

NOW = "2026-08-08T18:50:00+00:00"
EXPIRES = "2026-08-08T19:00:00+00:00"
MIGRATION_053 = "053_pilot_input_readiness_route_domain.sql"


def _candidate(
    label: str,
    *,
    route: str,
    authority: str,
    holder_eligible: bool = False,
) -> ReadinessCandidate:
    pool = (label + "Pool" + "2" * 44)[:44]
    return ReadinessCandidate(
        mint=(label + "Mint" + "1" * 44)[:44],
        pool=pool,
        market_identity=f"solana-mainnet:{pool}",
        liquidity_usd=12_345.67,
        liquidity_observed_at=NOW,
        activation_route=route,
        holder_eligible=holder_eligible,
        provenance="LATEST_GRADUATED" if label == "Market" else "PERSISTED_GRADUATED",
        memory_observation_eligible=True,
        holder_condition="SOURCE_NOT_EVALUATED_BUDGET_BOUND",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        admission_authority=authority,
        slot_ordinal=1 if label == "Market" else 2,
        tracking_eligible=True,
        tracking_reason="TRACKING_FEASIBLE",
        tracking_requalification_required=False,
    )


def _build_bundle(connection: sqlite3.Connection, *, readiness_id: str = "dtw90-ready"):
    market = _candidate(
        "Market",
        route="MARKET_PRESENT_POOL",
        authority="MARKET_PRESENT_POOL",
    )
    direct = _candidate(
        "Direct",
        route="PUMP_CREATE",
        authority="DIRECT_PUMP_PUMPSWAP",
    )
    return build_pilot_input_ready_bundle(
        connection,
        readiness_id=readiness_id,
        latest=market,
        persisted=direct,
        holder_evidence={},
        source_ledger={"proof": "DTW90"},
        selection_seed="dtw90-seed",
        git_provenance_identity="dtw90-fixture",
        configuration_hash="0" * 64,
        expires_at=EXPIRES,
        now=NOW,
        readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
    )


class DTW90Migration053Proof(unittest.TestCase):
    def _fresh_db(self) -> tuple[tempfile.TemporaryDirectory[str], Path, sqlite3.Connection]:
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "printer.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return tmp, path, connection

    def test_canonical_ledger_advances_to_053(self) -> None:
        names = canonical_migration_names()
        # DTW90's durable claim is that 053 landed at ordinal 53 and applies
        # cleanly. The catalogue is forward-only, so later lanes append beyond
        # it (V2-9.8B Post-DTW98 added 054). Anchor 053 exactly by position and
        # keep the live count exact rather than frozen at this lane's head.
        self.assertEqual(names[52], MIGRATION_053)
        self.assertEqual(canonical_migration_count(), len(names))
        self.assertGreaterEqual(canonical_migration_count(), 53)
        tmp, _path, connection = self._fresh_db()
        try:
            applied = [
                str(row[0])
                for row in connection.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY rowid"
                ).fetchall()
            ]
            report = validate_migration_ledger(applied)
            self.assertTrue(report["matches"], report)
            self.assertEqual(report["applied_count"], len(names))
            self.assertEqual(applied[52], MIGRATION_053)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()
            tmp.cleanup()

    def test_mixed_authority_memory_observation_persists_truthful_route(self) -> None:
        tmp, _path, connection = self._fresh_db()
        try:
            market = _candidate(
                "Market",
                route="MARKET_PRESENT_POOL",
                authority="MARKET_PRESENT_POOL",
            )
            direct = _candidate(
                "Direct",
                route="PUMP_CREATE",
                authority="DIRECT_PUMP_PUMPSWAP",
            )
            self.assertEqual(
                evaluate_readiness_gates(
                    market,
                    direct,
                    discovery_universe_evaluated=True,
                    readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
                ),
                READINESS_READY,
            )
            try:
                first = _build_bundle(connection)
            except sqlite3.IntegrityError as exc:
                self.fail(f"migration 053 must make MARKET_PRESENT_POOL durable: {exc}")
            second = _build_bundle(connection)
            self.assertEqual(first["bundle_hash"], second["bundle_hash"])
            self.assertIsNone(second["created_at"])

            loaded = load_pilot_input_ready_bundle(connection, "dtw90-ready")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["latest_activation_route"], "MARKET_PRESENT_POOL")
            self.assertEqual(loaded["persisted_activation_route"], "PUMP_CREATE")
            ledger = json.loads(str(loaded["source_ledger_json"]))
            ordered = ledger["ordered_selected_candidates"]
            self.assertEqual(
                [item["admission_authority"] for item in ordered],
                ["MARKET_PRESENT_POOL", "DIRECT_PUMP_PUMPSWAP"],
            )
            self.assertEqual(
                [item["activation_route"] for item in ordered],
                ["MARKET_PRESENT_POOL", "PUMP_CREATE"],
            )

            for table in (
                "printer_source_requests",
                "printer_source_responses",
                "printer_source_failures",
                "printer_memory_windows",
                "printer_episodes",
                "printer_episode_outcomes",
                "printer_memory_retrieval_queries",
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
                "printer_paper_trade_audits",
            ):
                exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if exists:
                    self.assertEqual(
                        connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                        0,
                        table,
                    )
        finally:
            connection.close()
            tmp.cleanup()

    def test_future_action_market_present_pool_still_fails_before_insert(self) -> None:
        tmp, _path, connection = self._fresh_db()
        try:
            market = _candidate(
                "Market",
                route="MARKET_PRESENT_POOL",
                authority="MARKET_PRESENT_POOL",
                holder_eligible=True,
            )
            direct = _candidate(
                "Direct",
                route="PUMP_CREATE",
                authority="DIRECT_PUMP_PUMPSWAP",
                holder_eligible=True,
            )
            self.assertEqual(
                evaluate_readiness_gates(
                    market,
                    direct,
                    discovery_universe_evaluated=True,
                    readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
                ),
                BLOCKED_ACTIVATION,
            )
            with self.assertRaises(PilotInputReadinessError) as ctx:
                build_pilot_input_ready_bundle(
                    connection,
                    readiness_id="dtw90-future-action",
                    latest=market,
                    persisted=direct,
                    holder_evidence={},
                    source_ledger={},
                    selection_seed="dtw90-future",
                    git_provenance_identity="dtw90-fixture",
                    configuration_hash="1" * 64,
                    expires_at=EXPIRES,
                    now=NOW,
                    readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
                )
            self.assertEqual(ctx.exception.code, "READINESS_GATE_UNMET")
            self.assertEqual(ctx.exception.detail, BLOCKED_ACTIVATION)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_pilot_input_readiness_bundle"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()
            tmp.cleanup()

    def test_053_preserves_legacy_row_and_restores_immutability_contract(self) -> None:
        migration = MIGRATIONS_DIR / MIGRATION_053
        self.assertTrue(migration.is_file(), f"missing {MIGRATION_053}")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pre053.sqlite3"
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                # Build canonical schema only through 052.
                connection.execute(
                    "CREATE TABLE printer_schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
                )
                for name in canonical_migration_names():
                    if name == MIGRATION_053:
                        break
                    connection.executescript((MIGRATIONS_DIR / name).read_text(encoding="utf-8"))
                    connection.execute(
                        "INSERT INTO printer_schema_migrations(version) VALUES (?)", (name,)
                    )
                connection.commit()

                columns = [
                    str(row[1])
                    for row in connection.execute(
                        "PRAGMA table_info(printer_pilot_input_readiness_bundle)"
                    ).fetchall()
                ]
                legacy_values = {
                    "readiness_id": "legacy-immutable",
                    "readiness_state": "PILOT_INPUT_READY",
                    "latest_mint": "LegacyMintA",
                    "latest_pool": "LegacyPoolA",
                    "latest_market_identity": "solana-mainnet:LegacyPoolA",
                    "latest_liquidity_usd": 5000.0,
                    "latest_liquidity_observed_at": NOW,
                    "latest_activation_route": "GRADUATION_NATIVE",
                    "persisted_mint": "LegacyMintB",
                    "persisted_pool": "LegacyPoolB",
                    "persisted_market_identity": "solana-mainnet:LegacyPoolB",
                    "persisted_liquidity_usd": 6000.0,
                    "persisted_liquidity_observed_at": NOW,
                    "persisted_activation_route": "PUMP_CREATE",
                    "holder_evidence_json": "{}",
                    "source_ledger_json": "{}",
                    "latest_persisted_provenance_json": "{}",
                    "selection_seed": "legacy-seed",
                    "git_provenance_identity": "legacy-git",
                    "configuration_hash": "2" * 64,
                    "expires_at": EXPIRES,
                    "bundle_hash": "3" * 64,
                    "created_at": NOW,
                }
                placeholders = ",".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO printer_pilot_input_readiness_bundle ({','.join(columns)}) VALUES ({placeholders})",
                    [legacy_values[column] for column in columns],
                )
                connection.commit()
                before = dict(
                    connection.execute(
                        "SELECT * FROM printer_pilot_input_readiness_bundle WHERE readiness_id='legacy-immutable'"
                    ).fetchone()
                )

                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.commit()
                after = dict(
                    connection.execute(
                        "SELECT * FROM printer_pilot_input_readiness_bundle WHERE readiness_id='legacy-immutable'"
                    ).fetchone()
                )
                self.assertEqual(after, before)
                self.assertEqual(after["bundle_hash"], "3" * 64)

                indexes = {
                    str(row[1])
                    for row in connection.execute(
                        "PRAGMA index_list(printer_pilot_input_readiness_bundle)"
                    ).fetchall()
                }
                self.assertIn("printer_pilot_input_readiness_created", indexes)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE printer_pilot_input_readiness_bundle SET selection_seed='changed' WHERE readiness_id='legacy-immutable'"
                    )
                connection.rollback()
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "DELETE FROM printer_pilot_input_readiness_bundle WHERE readiness_id='legacy-immutable'"
                    )
                connection.rollback()
            finally:
                connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
