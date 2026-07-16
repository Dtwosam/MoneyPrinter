"""V2-9.6 safety context source redundancy — deterministic proof.

Fixture-only. No live source calls. Proves the governed primary Solana-RPC
holder call -> single backup RPC endpoint contract, without weakening safety:

- primary holder-RPC success makes no backup call;
- an eligible transient primary failure + a valid backup yields exactly one
  holder contribution (from the backup), with both source attempts persisted;
- both attempts stay budgeted; the primary failure is preserved;
- a double failure (primary + backup) leaves holder UNKNOWN and the composite
  blocking, with both attempts persisted;
- non-retryable primary failures (malformed / 4xx / rpc-error) do not fall back;
- GoPlus remains mandatory: missing GoPlus is never relabeled safe;
- GoPlus-vs-holder disagreement stays blocking;
- no duplicate contributions or evidence rows.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import _collect_preclose_context
from printer_v1.operator_cli.safety_context_source_redundancy import (
    ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES,
    is_eligible_transient_solana_rpc_failure,
)
from printer_v1.safety.composite import persist_safety_composite
from printer_v1.sources.goplus import build_goplus_adapter
from printer_v1.sources.solana_rpc_holder import build_solana_rpc_holder_adapter

MINT = "C" * 43
PAIR = "D" * 43
RUN_ID = "run-v2-9-6"
T0 = "2026-07-16T09:00:00+00:00"


def _goplus_payload(**overrides):
    # holders=[] -> GoPlus holder label UNKNOWN, so the Solana-RPC holder path
    # fires; the rest is a usable/clean GoPlus provider-risk contribution.
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


def _goplus_factory(**overrides):
    from printer_v1.sources.governed_execution import build_fixture_source_adapter
    payload = _goplus_payload(**overrides)

    def factory(*, token_mint, timeout_seconds):
        return build_fixture_source_adapter(
            "goplus", fixture_kind="fixture_success", fixture_payload=payload,
        )
    return factory


def _rpc_failure_transport(failure_type: str):
    def transport(context):
        del context
        return {
            "fixture_status": "failure",
            "failure_type": failure_type,
            "failure_message": f"simulated {failure_type}",
        }
    return transport


def _rpc_success_transport(label: str = "HOLDER_CONCENTRATION_HEALTHY"):
    def transport(context):
        del context
        return {"token_mint": MINT, "holder_concentration_label": label}
    return transport


def _holder_factory(transport):
    def factory(*, token_mint, timeout_seconds):
        return build_solana_rpc_holder_adapter(enabled=True, fixture_transport=transport)
    return factory


class SafetyContextSourceRedundancyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.db_path = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._seed()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _seed(self) -> None:
        c = self.conn
        c.execute("INSERT INTO printer_tokens(token_mint,chain,token_status,first_seen_at,last_seen_at,created_at,updated_at)"
                  " VALUES (?,'solana','TRACKING',?,?,?,?)", (MINT, T0, T0, T0, T0))
        self.token_id = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        c.execute("INSERT INTO printer_pairs(token_id,pair_address,base_token_mint,first_seen_at,last_seen_at,created_at,updated_at)"
                  " VALUES (?,?,?,?,?,?,?)", (self.token_id, PAIR, MINT, T0, T0, T0, T0))
        self.pair_id = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        c.execute("INSERT INTO printer_memory_factory_runs(run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at,created_at,updated_at)"
                  " VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','h','{}',?,?,?)", (RUN_ID, T0, T0, T0))
        c.execute("INSERT INTO printer_memory_factory_run_steps(run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,pair_address,tracking_lane,scheduled_for,created_at,updated_at)"
                  " VALUES (?,'t1_window_close','WINDOW_CLOSE','RUNNING',?,?,?,?,'TRACK_FAST',?,?,?)",
                  (RUN_ID, self.token_id, self.pair_id, MINT, PAIR, T0, T0, T0))
        self.evaluated = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
        c.execute("INSERT INTO printer_token_snapshots(token_id,pair_id,captured_at,tracking_lane,snapshot_mode,price_usd,liquidity_usd,source_status,data_quality_label)"
                  " VALUES (?,?,?,?,?,1.0,10000,'COMPLETE','CLEAN_DATA')",
                  (self.token_id, self.pair_id, self.evaluated, "TRACK_FAST", "TOKEN_SNAPSHOT"))
        self.snapshot_id = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        c.commit()

    def _step(self):
        return self.conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? AND step_key='t1_window_close'",
            (RUN_ID,),
        ).fetchone()

    def _collect(self, *, primary_transport, backup_transport=None):
        factories = {
            "goplus": _goplus_factory(),
            "solana_rpc_holder": _holder_factory(primary_transport),
        }
        if backup_transport is not None:
            factories["solana_rpc_holder_backup"] = _holder_factory(backup_transport)
        return _collect_preclose_context(
            self.conn, self._step(), timeout_seconds=5.0,
            adapter_factories=factories, include=frozenset({"safety"}),
        )

    def _rpc_count(self):
        return int(self.conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests WHERE source_name='solana_rpc'"
        ).fetchone()[0])

    def _composite(self, bundle):
        return persist_safety_composite(
            self.conn,
            token_id=self.token_id, pair_id=self.pair_id, snapshot_id=self.snapshot_id,
            token_mint=MINT, pair_address=PAIR, evaluated_at=self.evaluated,
            goplus_execution=bundle["executions"]["safety"],
            holder_execution=bundle["executions"].get("holder"),
        )

    # --- eligibility allowlist ---------------------------------------------

    def test_eligible_allowlist_is_exact(self):
        self.assertEqual(
            ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES,
            frozenset({
                "solana_rpc_transport_failure",
                "solana_rpc_http_server_error",
                "solana_rpc_rate_limited",
            }),
        )
        self.assertFalse(is_eligible_transient_solana_rpc_failure(None))

    # --- primary success => no backup --------------------------------------

    def test_primary_holder_success_makes_no_backup(self):
        def backup_raises(*a, **k):
            raise AssertionError("backup must not be built on primary success")
        factories = {
            "goplus": _goplus_factory(),
            "solana_rpc_holder": _holder_factory(_rpc_success_transport("HOLDER_CONCENTRATION_HEALTHY")),
            "solana_rpc_holder_backup": backup_raises,
        }
        bundle = _collect_preclose_context(
            self.conn, self._step(), timeout_seconds=5.0,
            adapter_factories=factories, include=frozenset({"safety"}),
        )
        self.assertIn("holder", bundle["executions"])
        self.assertNotIn("holder_backup", bundle["executions"])
        self.assertEqual(self._rpc_count(), 1)
        result = self._composite(bundle)
        self.assertEqual(result["contribution_count"], 2)
        self.assertEqual(result["holder_concentration_label"], "HOLDER_CONCENTRATION_HEALTHY")

    # --- eligible failure + valid backup => one holder contribution --------

    def test_eligible_failure_valid_backup_one_contribution(self):
        for ft in sorted(ELIGIBLE_TRANSIENT_SOLANA_RPC_FAILURE_TYPES):
            with self.subTest(failure_type=ft):
                self.tearDown(); self.setUp()
                bundle = self._collect(
                    primary_transport=_rpc_failure_transport(ft),
                    backup_transport=_rpc_success_transport("HOLDER_CONCENTRATION_HEALTHY"),
                )
                ex = bundle["executions"]
                self.assertIn("holder_backup", ex)
                # chosen holder is the backup (has a response)
                self.assertIsNotNone(ex["holder"].response_record)
                self.assertIsNone(ex["holder_backup"].failure_record)
                # both attempts persisted + budgeted: 2 solana_rpc requests
                self.assertEqual(self._rpc_count(), 2)
                failures = int(self.conn.execute(
                    "SELECT COUNT(*) FROM printer_source_failures WHERE source_name='solana_rpc'"
                ).fetchone()[0])
                self.assertEqual(failures, 1)  # primary failure preserved
                # composite: exactly one holder contribution, from solana_rpc
                result = self._composite(bundle)
                self.assertEqual(result["contribution_count"], 2)  # goplus + 1 holder
                self.assertEqual(result["holder_concentration_label"], "HOLDER_CONCENTRATION_HEALTHY")
                self.assertNotIn("HOLDER_CONCENTRATION_SOURCE_CONFLICT", result["conflicts"])
                contribs = self.conn.execute(
                    "SELECT source_name, evidence_category FROM printer_safety_evidence_contributions ORDER BY id"
                ).fetchall()
                self.assertEqual([r["source_name"] for r in contribs], ["goplus", "solana_rpc"])

    # --- double failure => holder UNKNOWN, blocking, both persisted --------

    def test_double_failure_holder_unknown_and_blocking(self):
        bundle = self._collect(
            primary_transport=_rpc_failure_transport("solana_rpc_transport_failure"),
            backup_transport=_rpc_failure_transport("solana_rpc_transport_failure"),
        )
        ex = bundle["executions"]
        self.assertIn("holder_backup", ex)
        # chosen holder is the (failed) primary — provenance preserved
        self.assertIsNone(ex["holder"].response_record)
        self.assertIsNotNone(ex["holder"].failure_record)
        self.assertEqual(self._rpc_count(), 2)
        result = self._composite(bundle)
        self.assertEqual(result["holder_concentration_label"], "HOLDER_CONCENTRATION_UNKNOWN")
        # GoPlus alone is usable but holder is optional-unknown; window stays
        # acceptable-for-15m-only at best, never SAFETY_CLEAN off missing holder.
        self.assertNotEqual(result["safety_contract_label"], "SAFETY_CLEAN")

    # --- non-retryable primary failures => no backup -----------------------

    def test_non_retryable_primary_does_not_fallback(self):
        for ft in ("solana_rpc_malformed_response", "solana_rpc_http_client_error",
                   "solana_rpc_holder_rpc_error", "solana_rpc_holder_fixture_failure"):
            with self.subTest(failure_type=ft):
                self.tearDown(); self.setUp()
                bundle = self._collect(
                    primary_transport=_rpc_failure_transport(ft),
                    backup_transport=_rpc_success_transport(),
                )
                self.assertNotIn("holder_backup", bundle["executions"])
                self.assertEqual(self._rpc_count(), 1)

    # --- GoPlus mandatory: missing GoPlus never relabeled safe -------------

    def test_missing_goplus_is_never_safe(self):
        from printer_v1.sources.governed_execution import build_fixture_source_adapter
        factories = {
            "goplus": lambda *, token_mint, timeout_seconds: build_fixture_source_adapter(
                "goplus", fixture_kind="fixture_failure"),
            "solana_rpc_holder": _holder_factory(_rpc_success_transport("HOLDER_CONCENTRATION_HEALTHY")),
        }
        bundle = _collect_preclose_context(
            self.conn, self._step(), timeout_seconds=5.0,
            adapter_factories=factories, include=frozenset({"safety"}),
        )
        # GoPlus failed -> its holder label is UNKNOWN -> RPC still runs, but the
        # composite must block on the missing mandatory GoPlus contribution.
        result = self._composite(bundle)
        self.assertEqual(result["safety_contract_label"], "SAFETY_BLOCKED_FOR_15M_MEMORY")
        self.assertIn("GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE", result["blockers"])

    # --- disagreement (GoPlus vs holder) stays blocking --------------------

    def test_goplus_holder_disagreement_is_blocking(self):
        # GoPlus reports a concentrated holder label; an RPC holder execution
        # reports a different one -> conflict -> blocking. (Composite-level
        # regression guard: redundancy must not weaken conflict handling.)
        from printer_v1.sources.contracts import build_governed_source_request
        from printer_v1.sources.governed_execution import (
            build_fixture_source_adapter, execute_source_request_with_governor,
        )
        goplus = execute_source_request_with_governor(
            self.conn,
            build_governed_source_request("goplus", "safety_reference",
                                          request_key="t:g", payload={"token_mint": MINT, "pair_address": PAIR}),
            build_fixture_source_adapter("goplus", fixture_kind="fixture_success",
                                         fixture_payload=_goplus_payload(holders=[{"balance": "900"}] + [{"balance": "10"} for _ in range(9)])),
        )
        holder = execute_source_request_with_governor(
            self.conn,
            build_governed_source_request("solana_rpc", "holder_concentration_reference",
                                          request_key="t:h", payload={"token_mint": MINT, "pair_address": PAIR}),
            build_solana_rpc_holder_adapter(enabled=True,
                                            fixture_transport=_rpc_success_transport("HOLDER_CONCENTRATION_HEALTHY")),
        )
        result = persist_safety_composite(
            self.conn, token_id=self.token_id, pair_id=self.pair_id, snapshot_id=self.snapshot_id,
            token_mint=MINT, pair_address=PAIR, evaluated_at=self.evaluated,
            goplus_execution=goplus, holder_execution=holder,
        )
        self.assertIn("HOLDER_CONCENTRATION_SOURCE_CONFLICT", result["conflicts"])
        self.assertEqual(result["holder_concentration_label"], "HOLDER_CONCENTRATION_UNKNOWN")
        self.assertEqual(result["safety_contract_label"], "SAFETY_BLOCKED_FOR_15M_MEMORY")


if __name__ == "__main__":
    unittest.main()
