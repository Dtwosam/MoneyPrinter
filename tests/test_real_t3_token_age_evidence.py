from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from printer_v1.sources import solana_rpc_token_age as t3
from printer_v1.discovery.parser import normalize_candidate
from printer_v1.discovery.selection_batch import extract_candidate_metadata
from printer_v1.db.migrate import apply_migrations
from printer_v1.sources.contracts import SourceRequest
from printer_v1.sources.governed_execution import execute_source_request_with_governor


MINT = "6LsqJCJ1p98UG3HYx1UuPgqNjTzAcYFdw4nSzfPzpump"
CAPTURED_AT = "2026-07-12T12:00:00+00:00"
BLOCK_TIME = int(datetime(2026, 7, 12, 11, 55, tzinfo=timezone.utc).timestamp())


def _mint_account() -> dict:
    raw = bytearray(82)
    raw[45] = 1
    return {
        "result": {
            "value": {
                "owner": t3._SPL_TOKEN_PROGRAM_ID,
                "data": [base64.b64encode(raw).decode("ascii"), "base64"],
            }
        }
    }


def _signature(signature: str = "sig-init") -> dict:
    return {
        "signature": signature,
        "err": None,
        "confirmationStatus": "finalized",
        "slot": 42,
    }


def _transaction(instructions: list[dict], *, inner: list[dict] | None = None,
                 account_keys: list | None = None, loaded: dict | None = None) -> dict:
    return {
        "result": {
            "slot": 42,
            "blockTime": BLOCK_TIME,
            "version": 0 if loaded else "legacy",
            "meta": {
                "err": None,
                "innerInstructions": inner or [],
                "loadedAddresses": loaded or {"writable": [], "readonly": []},
            },
            "transaction": {
                "message": {
                    "accountKeys": account_keys or [MINT, t3._SPL_TOKEN_PROGRAM_ID],
                    "instructions": instructions,
                }
            },
        }
    }


def _parsed(mint: str = MINT, *, program_id: str = t3._SPL_TOKEN_PROGRAM_ID) -> dict:
    return {
        "program": "spl-token",
        "programId": program_id,
        "parsed": {"type": "initializeMint2", "info": {"mint": mint}},
    }


class RealT3TransactionParsingTests(unittest.TestCase):
    def test_inner_parsed_instruction_matches_exact_mint(self) -> None:
        tx = _transaction([], inner=[{"index": 0, "instructions": [_parsed()]}])
        self.assertEqual(t3._transaction_init_matches(tx["result"], MINT), [("initializeMint2", "spl_token")])

    def test_versioned_compiled_instruction_resolves_alt_loaded_mint(self) -> None:
        tx = _transaction(
            [{"programIdIndex": 0, "accounts": [1], "data": "M"}],
            account_keys=[t3._SPL_TOKEN_PROGRAM_ID],
            loaded={"writable": [MINT], "readonly": []},
        )
        self.assertEqual(t3._transaction_init_matches(tx["result"], MINT), [("initializeMint2", "spl_token")])

    def test_wrong_mint_and_unknown_program_fail_closed(self) -> None:
        self.assertEqual(t3._transaction_init_matches(_transaction([_parsed("wrong")])["result"], MINT), [])
        unknown = _parsed(program_id="Unknown111111111111111111111111111111111")
        unknown["program"] = "unknown"
        self.assertEqual(t3._transaction_init_matches(_transaction([unknown])["result"], MINT), [])

    def test_malformed_compiled_indices_fail_closed(self) -> None:
        tx = _transaction([{"programIdIndex": 9, "accounts": [0], "data": "1"}])
        self.assertEqual(t3._transaction_init_matches(tx["result"], MINT), [])


class RealT3PipelineTests(unittest.TestCase):
    def _run(self, tx: dict, *, signature: dict | None = None) -> tuple[dict, list[tuple[str, list]]]:
        responses = [_mint_account(), {"result": [signature or _signature()]}, tx]
        calls: list[tuple[str, list]] = []

        def rpc(_url, method, params, **_kwargs):
            calls.append((method, params))
            return responses.pop(0)

        with patch.object(t3, "_rpc_post", side_effect=rpc):
            result = dict(t3._fetch_token_age_data(MINT, CAPTURED_AT))
        return result, calls

    def test_finalized_inner_instruction_produces_complete_t3(self) -> None:
        result, calls = self._run(
            _transaction([], inner=[{"index": 0, "instructions": [_parsed()]}])
        )
        self.assertEqual(result["t3_status"], "success")
        self.assertEqual(result["token_age_evidence_tier"], "T3")
        self.assertEqual(result["t3_commitment"], "finalized")
        self.assertEqual(result["t3_finality_status"], "finalized")
        self.assertGreaterEqual(result["token_age_seconds"], 0)
        for method, params in calls:
            if method != "getBlockTime":
                self.assertEqual(params[-1]["commitment"], "finalized")

    def test_non_finalized_signature_never_produces_t3(self) -> None:
        signature = _signature()
        signature["confirmationStatus"] = "confirmed"
        result, _ = self._run(_transaction([_parsed()]), signature=signature)
        self.assertEqual(result["fixture_status"], "failure")
        self.assertNotIn("token_created_at", result)

    def test_ambiguous_instruction_never_produces_t3(self) -> None:
        result, _ = self._run(_transaction([_parsed(), _parsed()]))
        self.assertEqual(result["failure_type"], "solana_rpc_token_age_ambiguous_init_instruction")
        self.assertNotIn("token_created_at", result)

    def test_finalized_provenance_reaches_selection_metadata(self) -> None:
        result, _ = self._run(_transaction([_parsed()]))
        result["pair_address"] = "pair-proof"
        result["chain"] = "solana"
        candidate = normalize_candidate(
            "solana_rpc", result, datetime.fromisoformat(CAPTURED_AT)
        )
        metadata = extract_candidate_metadata(candidate)
        self.assertEqual(metadata["t3_requested_mint"], MINT)
        self.assertEqual(metadata["t3_commitment"], "finalized")
        self.assertEqual(metadata["t3_finality_status"], "finalized")
        self.assertEqual(metadata["t3_accepted_signature"], "sig-init")

    def test_governed_failure_persists_bounded_provenance(self) -> None:
        provenance = {
            "t3_requested_mint": MINT,
            "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
            "t3_rpc_methods_attempted": ["getAccountInfo"],
            "t3_request_ids": [1],
            "t3_pages_fetched": 0,
            "t3_tx_calls_attempted": 0,
            "t3_block_time_calls_attempted": 0,
            "t3_failure_stage": "account_validation",
        }
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/t3.sqlite3"
            apply_migrations(db_path)
            adapter = t3.build_solana_rpc_token_age_adapter(
                enabled=True,
                fixture_transport=t3.fixture_t3_failure_transport(
                    "solana_rpc_token_age_not_a_mint",
                    failure_provenance=provenance,
                ),
            )
            governed = execute_source_request_with_governor(
                db_path,
                SourceRequest(
                    source_name="solana_rpc",
                    request_kind="mint_creation_time_reference",
                    request_key="real-t3-failure-proof",
                ),
                adapter,
            )
            self.assertIsNotNone(governed.failure_record)
            connection = sqlite3.connect(db_path)
            try:
                row = connection.execute(
                    "SELECT normalized_payload_json FROM printer_source_failures"
                ).fetchone()
            finally:
                connection.close()
            stored = json.loads(row[0])
            self.assertEqual(stored["t3_requested_mint"], MINT)
            self.assertEqual(stored["t3_failure_stage"], "account_validation")
            self.assertNotIn("token_created_at", stored)


if __name__ == "__main__":
    unittest.main()
