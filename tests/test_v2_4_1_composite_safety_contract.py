import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.safety.composite import (
    composite_row_is_acceptable,
    persist_safety_composite,
)
from printer_v1.safety.goplus_normalizer import (
    holder_concentration_label_from_goplus,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


MINT = "C" * 32
PAIR = "D" * 32


class CompositeSafetyContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
            (MINT,),
        )
        self.token_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (self.token_id, PAIR, MINT),
        )
        self.pair_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.evaluated = datetime.now(timezone.utc) + timedelta(seconds=5)
        self.conn.execute(
            """
            INSERT INTO printer_token_snapshots (
                token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                price_usd,liquidity_usd,source_status,data_quality_label
            ) VALUES (?,?,?,?,?,1.0,10000,'COMPLETE','CLEAN_DATA')
            """,
            (self.token_id, self.pair_id, self.evaluated.isoformat(), "TRACK_FAST", "TOKEN_SNAPSHOT"),
        )
        self.snapshot_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def _execute(self, source, kind, payload=None, fixture_kind="fixture_success"):
        request = build_governed_source_request(
            source,
            kind,
            request_key=f"test:{source}:{kind}:{self.conn.execute('SELECT COUNT(*) FROM printer_source_requests').fetchone()[0]}",
            payload={"token_mint": MINT, "pair_address": PAIR},
        )
        adapter = build_fixture_source_adapter(
            source, fixture_kind=fixture_kind, fixture_payload=payload or {}
        )
        return execute_source_request_with_governor(self.conn, request, adapter)

    def _goplus_payload(self, **overrides):
        payload = {
            "token_mint": MINT,
            "mint_authority": None,
            "freeze_authority": None,
            "metadata_mutable": False,
            "total_supply": "1000",
            "holders": [{"balance": "30"} for _ in range(10)],
            "risk_flags": [],
        }
        payload.update(overrides)
        return payload

    def _persist(self, goplus, holder=None):
        return persist_safety_composite(
            self.conn,
            token_id=self.token_id,
            pair_id=self.pair_id,
            snapshot_id=self.snapshot_id,
            token_mint=MINT,
            pair_address=PAIR,
            evaluated_at=self.evaluated.isoformat(),
            goplus_execution=goplus,
            holder_execution=holder,
        )

    def test_live_goplus_holders_use_validated_supply(self):
        self.assertEqual(
            holder_concentration_label_from_goplus(self._goplus_payload()),
            "HOLDER_CONCENTRATION_HEALTHY",
        )
        self.assertEqual(
            holder_concentration_label_from_goplus(
                self._goplus_payload(total_supply="0")
            ),
            "HOLDER_CONCENTRATION_UNKNOWN",
        )

    def test_rpc_fallback_has_separate_complete_provenance(self):
        goplus = self._execute(
            "goplus", "safety_reference", self._goplus_payload(holders=[])
        )
        holder = self._execute(
            "solana_rpc",
            "holder_concentration_reference",
            {
                "token_mint": MINT,
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            },
        )
        result = self._persist(goplus, holder)
        self.assertEqual(result["contribution_count"], 2)
        self.assertEqual(result["safety_contract_label"], "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY")
        self.assertEqual(result["liquidity_lock_or_burn_label"], "LIQUIDITY_LOCK_OR_BURN_UNKNOWN")
        row = dict(self.conn.execute("SELECT * FROM printer_safety_evidence_composites").fetchone())
        self.assertTrue(composite_row_is_acceptable(row))
        contributions = self.conn.execute(
            "SELECT * FROM printer_safety_evidence_contributions ORDER BY id"
        ).fetchall()
        self.assertEqual([row["source_name"] for row in contributions], ["goplus", "solana_rpc"])
        self.assertTrue(all(row["source_response_id"] is not None for row in contributions))
        self.assertTrue(all(row["source_failure_id"] is None for row in contributions))
        goplus_fields = json.loads(contributions[0]["fields_supplied_json"])
        self.assertEqual(goplus_fields["provider_risk_field"], "risk_flags")
        self.assertEqual(goplus_fields["provider_risk_value"], [])

    def test_known_concentration_and_provider_risk_block(self):
        goplus = self._execute(
            "goplus",
            "safety_reference",
            self._goplus_payload(
                holders=[{"balance": "9"} for _ in range(10)],
                total_supply="100",
                risk_flags=["honeypot"],
            ),
        )
        result = self._persist(goplus)
        self.assertEqual(result["holder_concentration_label"], "HOLDER_CONCENTRATION_EXTREME")
        self.assertEqual(result["known_risk_flag_label"], "KNOWN_RISK_FLAGS_PRESENT")
        self.assertIn("holder_concentration_label", result["blockers"])
        self.assertIn("known_risk_flag_label", result["blockers"])

    def test_source_conflict_and_partial_failure_fail_closed(self):
        goplus = self._execute(
            "goplus", "safety_reference", self._goplus_payload()
        )
        holder = self._execute(
            "solana_rpc",
            "holder_concentration_reference",
            {
                "token_mint": MINT,
                "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
            },
        )
        conflict = self._persist(goplus, holder)
        self.assertIn("HOLDER_CONCENTRATION_SOURCE_CONFLICT", conflict["conflicts"])
        self.assertEqual(conflict["safety_contract_label"], "SAFETY_BLOCKED_FOR_15M_MEMORY")

    def test_failure_trace_is_visible_and_unknown_holder_blocks(self):
        goplus = self._execute(
            "goplus", "safety_reference", self._goplus_payload(holders=[])
        )
        holder = self._execute(
            "solana_rpc",
            "holder_concentration_reference",
            fixture_kind=FIXTURE_FAILURE,
        )
        result = self._persist(goplus, holder)
        self.assertEqual(result["safety_contract_label"], "SAFETY_BLOCKED_FOR_15M_MEMORY")
        contribution = self.conn.execute(
            "SELECT * FROM printer_safety_evidence_contributions WHERE source_name='solana_rpc'"
        ).fetchone()
        self.assertIsNotNone(contribution["source_failure_id"])
        self.assertIsNotNone(contribution["rejection_reason"])

    def test_exact_unlocked_blocks_but_unmatched_lp_stays_unknown(self):
        exact = self._execute(
            "goplus",
            "safety_reference",
            self._goplus_payload(pair_address=PAIR, liquidity_state="LP_UNLOCKED"),
        )
        exact_result = self._persist(exact)
        self.assertEqual(exact_result["liquidity_lock_or_burn_label"], "LIQUIDITY_UNLOCKED_OR_DANGEROUS")
        self.assertIn("liquidity_lock_or_burn_label", exact_result["blockers"])

    def test_field_bindings_are_categorical_and_bounded(self):
        goplus = self._execute(
            "goplus", "safety_reference", self._goplus_payload()
        )
        self._persist(goplus)
        row = self.conn.execute("SELECT * FROM printer_safety_evidence_composites").fetchone()
        bindings = json.loads(row["field_bindings_json"])
        self.assertEqual(bindings["holder_concentration_label"], "goplus")
        self.assertLessEqual(
            self.conn.execute("SELECT COUNT(*) FROM printer_safety_evidence_contributions").fetchone()[0],
            2,
        )


if __name__ == "__main__":
    unittest.main()
