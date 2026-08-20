from __future__ import annotations

import base64
import importlib
import importlib.util
import inspect
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.safety.composite import persist_safety_composite
from printer_v1.safety.goplus_normalizer import (
    HARD_SAFETY_FIELD_EXPECTATIONS,
    SOURCE_COVERAGE_PENDING_VALUES,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)
from printer_v1.sources.measured_transport import (
    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,
    PRECLOSE_CONTEXT_REQUEST_COUNT,
)


MINT = "C" * 32
PAIR = "D" * 32
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


class SolanaNativeSafetyRedundancyTests(unittest.TestCase):
    def setUp(self) -> None:
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
            (
                self.token_id,
                self.pair_id,
                self.evaluated.isoformat(),
                "TRACK_FAST",
                "TOKEN_SNAPSHOT",
            ),
        )
        self.snapshot_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _execute(self, source: str, kind: str, payload=None, *, failure: bool = False):
        request = build_governed_source_request(
            source,
            kind,
            request_key=(
                f"test:{source}:{kind}:"
                f"{self.conn.execute('SELECT COUNT(*) FROM printer_source_requests').fetchone()[0]}"
            ),
            payload={"token_mint": MINT, "pair_address": PAIR},
        )
        adapter = build_fixture_source_adapter(
            source,
            fixture_kind=FIXTURE_FAILURE if failure else "fixture_success",
            fixture_payload=payload or {},
        )
        return execute_source_request_with_governor(self.conn, request, adapter)

    def _goplus_payload(self, **overrides):
        payload = {
            "token_mint": MINT,
            "mint_authority": None,
            "freeze_authority": None,
            "metadata_mutable": False,
            "total_supply": "1000",
            "holders": [],
            "risk_flags": [],
        }
        payload.update(overrides)
        return payload

    def _solana_core_payload(self, **overrides):
        payload = {
            "token_mint": MINT,
            "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
            "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
            "supply_sanity_label": "SUPPLY_SANITY_OK",
            "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        }
        payload.update(overrides)
        return payload

    def _persist(self, goplus, core, holder=None):
        self.assertIn(
            "core_solana_execution",
            inspect.signature(persist_safety_composite).parameters,
            "composite must accept an independent Solana-native core-safety contribution",
        )
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
            core_solana_execution=core,
        )

    def test_metadata_unknown_is_optional_coverage_not_a_hard_15m_gate(self) -> None:
        self.assertNotIn("metadata_mutability_status", HARD_SAFETY_FIELD_EXPECTATIONS)
        self.assertEqual(
            SOURCE_COVERAGE_PENDING_VALUES["metadata_mutability_status"],
            "METADATA_UNKNOWN",
        )

    def test_goplus_failure_with_clean_solana_core_facts_is_acceptable(self) -> None:
        goplus = self._execute("goplus", "safety_reference", failure=True)
        core = self._execute(
            "solana_rpc", "mint_account_reference", self._solana_core_payload()
        )
        result = self._persist(goplus, core)
        self.assertEqual(result["mint_authority_status"], "MINT_AUTHORITY_RENOUNCED")
        self.assertEqual(result["freeze_authority_status"], "FREEZE_AUTHORITY_DISABLED")
        self.assertEqual(result["supply_sanity_label"], "SUPPLY_SANITY_OK")
        self.assertEqual(result["token_program_label"], "SPL_TOKEN_OR_TOKEN_2022_VERIFIED")
        self.assertEqual(result["metadata_mutability_status"], "METADATA_UNKNOWN")
        self.assertNotIn("GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE", result["blockers"])
        self.assertEqual(
            result["safety_contract_label"],
            "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        )
        self.assertEqual(result["field_bindings"]["mint_authority_status"], "solana_rpc")
        self.assertEqual(result["field_bindings"]["freeze_authority_status"], "solana_rpc")
        self.assertEqual(result["field_bindings"]["supply_sanity_label"], "solana_rpc")
        self.assertEqual(result["field_bindings"]["token_program_label"], "solana_rpc")

    def test_conflicting_core_fact_fails_closed(self) -> None:
        goplus = self._execute(
            "goplus",
            "safety_reference",
            self._goplus_payload(mint_authority="authority-present"),
        )
        core = self._execute(
            "solana_rpc", "mint_account_reference", self._solana_core_payload()
        )
        result = self._persist(goplus, core)
        self.assertIn("MINT_AUTHORITY_SOURCE_CONFLICT", result["conflicts"])
        self.assertEqual(result["mint_authority_status"], "MINT_AUTHORITY_UNKNOWN")
        self.assertIn("mint_authority_status", result["blockers"])

    def test_missing_core_fact_stays_blocked_when_goplus_is_unusable(self) -> None:
        goplus = self._execute("goplus", "safety_reference", failure=True)
        core = self._execute(
            "solana_rpc",
            "mint_account_reference",
            self._solana_core_payload(freeze_authority_status="FREEZE_AUTHORITY_UNKNOWN"),
        )
        result = self._persist(goplus, core)
        self.assertIn("freeze_authority_status", result["blockers"])
        self.assertEqual(result["safety_contract_label"], "SAFETY_BLOCKED_FOR_15M_MEMORY")

    def test_mint_account_normalizer_derives_only_chain_provable_core_facts(self) -> None:
        spec = importlib.util.find_spec("printer_v1.sources.solana_rpc_token_safety")
        self.assertIsNotNone(spec, "Solana-native core safety adapter module must exist")
        module = importlib.import_module("printer_v1.sources.solana_rpc_token_safety")

        raw = bytearray(82)
        raw[0:4] = (0).to_bytes(4, "little")
        raw[36:44] = (1_000_000).to_bytes(8, "little")
        raw[44] = 6
        raw[45] = 1
        raw[46:50] = (0).to_bytes(4, "little")
        payload = {
            "token_mint": MINT,
            "account_info_result": {
                "result": {
                    "context": {"slot": 123},
                    "value": {
                        "owner": TOKEN_PROGRAM_ID,
                        "data": [base64.b64encode(bytes(raw)).decode("ascii"), "base64"],
                    },
                }
            },
            "captured_at": self.evaluated.isoformat(),
            "underlying_operation_count": 1,
        }
        normalized = module.normalize_solana_rpc_token_safety_response(
            payload, request_kind="mint_account_reference"
        )
        facts = dict(normalized.normalized_payload)
        self.assertEqual(facts["token_mint"], MINT)
        self.assertEqual(facts["mint_authority_status"], "MINT_AUTHORITY_RENOUNCED")
        self.assertEqual(facts["freeze_authority_status"], "FREEZE_AUTHORITY_DISABLED")
        self.assertEqual(facts["supply_sanity_label"], "SUPPLY_SANITY_OK")
        self.assertEqual(facts["token_program_label"], "SPL_TOKEN_OR_TOKEN_2022_VERIFIED")
        self.assertNotIn("metadata_mutability_status", facts)
        self.assertNotIn("known_risk_flag_label", facts)
        self.assertNotIn("liquidity_lock_or_burn_label", facts)

    def test_factory_wires_one_core_solana_safety_request_into_composite(self) -> None:
        from printer_v1.operator_cli import one_command_15m_factory as factory

        source = inspect.getsource(factory._collect_preclose_context)
        persist_source = inspect.getsource(factory._persist_preclose_context)
        self.assertIn("mint_account_reference", source)
        self.assertIn("core_solana_safety", source)
        self.assertIn(
            'core_solana_execution=executions.get("core_solana_safety")',
            persist_source,
        )

    def test_lifecycle_budget_reserves_the_extra_governed_core_safety_request(self) -> None:
        self.assertEqual(PRECLOSE_CONTEXT_REQUEST_COUNT, 6)
        self.assertEqual(FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT, 4)
        self.assertEqual(LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND["WINDOW_CLOSE"], 7)
        self.assertEqual(LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND["CONTINUATION_CLOSE"], 5)


if __name__ == "__main__":
    unittest.main()
