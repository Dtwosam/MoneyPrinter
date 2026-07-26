import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES,
    _classify_first_memory_review,
)
from printer_v1.safety.composite import (
    composite_row_is_acceptable,
    persist_safety_composite,
)
from printer_v1.safety.goplus_normalizer import safety_memory_policy_summary
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)
from printer_v1.sources.helius_holder import normalize_helius_holder_response
from printer_v1.sources.solana_rpc_holder import (
    normalize_solana_rpc_holder_response,
)


MINT = "H" * 32
PAIR = "J" * 32
FORBIDDEN_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _snapshots(count=6):
    return [
        {
            "id": index + 1,
            "price_usd": 1.0,
            "liquidity_usd": 50_000.0,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        for index in range(count)
    ]


def _labels(**overrides):
    labels = {
        "market_regime_label": "MARKET_RISK_ON",
        "chain_heat_label": "SOLANA_HOT",
        "safety_status_label": "SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY",
        "rug_risk_label": "RUG_RISK_ACCEPTABLE_FOR_15M",
        "liquidity_state_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
        "entry_realism_label": "ENTRY_REALISTIC",
        "exit_realism_label": "EXIT_REALISTIC",
        "realism_gate_label": "REALISM_ACCEPTABLE",
        "flow_direction_label": "FLOW_BUY_DOMINANT",
        "flow_pressure_label": "PRESSURE_BALANCED",
        "trend_structure_label": "TREND_PARABOLIC_DOWN",
        "volatility_label": "VOLATILITY_EXTREME",
        "held_to_15m_result_label": "HELD_TO_15M_DEAD",
    }
    labels.update(overrides)
    return labels


def _classify(*, snapshots=None, labels=None, blockers=None, outcome="DEAD"):
    return _classify_first_memory_review(
        snapshots if snapshots is not None else _snapshots(),
        {engine: {"id": 1} for engine in REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES},
        "WINDOW_15M",
        None,
        effective_labels=labels if labels is not None else _labels(),
        evidence_blockers=blockers,
        outcome_label=outcome,
    )


class HolderConditionMemoryQualitySeparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) "
            "VALUES (?,'solana','TRACK_FAST')",
            (MINT,),
        )
        self.token_id = self.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?)",
            (self.token_id, PAIR, MINT),
        )
        self.pair_id = self.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]
        self.evaluated = datetime.now(timezone.utc) + timedelta(seconds=5)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def _snapshot(self):
        self.conn.execute(
            """
            INSERT INTO printer_token_snapshots (
                token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                price_usd,liquidity_usd,source_status,data_quality_label
            ) VALUES (?,?,?,?,?,1.0,50000,'COMPLETE','CLEAN_DATA')
            """,
            (
                self.token_id,
                self.pair_id,
                self.evaluated.isoformat(),
                "TRACK_FAST",
                "TOKEN_SNAPSHOT",
            ),
        )
        return self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def _execute(self, source, kind, payload):
        request = build_governed_source_request(
            source,
            kind,
            request_key=f"e48:{source}:{self.conn.execute('SELECT COUNT(*) FROM printer_source_requests').fetchone()[0]}",
            payload={"token_mint": MINT, "pair_address": PAIR},
        )
        return execute_source_request_with_governor(
            self.conn,
            request,
            build_fixture_source_adapter(
                source, fixture_kind="fixture_success", fixture_payload=payload
            ),
        )

    def _goplus(self, holder_percent):
        holders = (
            []
            if holder_percent is None
            else [{"balance": str(holder_percent / 10)} for _ in range(10)]
        )
        return self._execute(
            "goplus",
            "safety_reference",
            {
                "token_mint": MINT,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "100",
                "holders": holders,
                "risk_flags": [],
            },
        )

    def _composite(self, *, goplus_percent, holder=None):
        snapshot_id = self._snapshot()
        result = persist_safety_composite(
            self.conn,
            token_id=self.token_id,
            pair_id=self.pair_id,
            snapshot_id=snapshot_id,
            token_mint=MINT,
            pair_address=PAIR,
            evaluated_at=self.evaluated.isoformat(),
            goplus_execution=self._goplus(goplus_percent),
            holder_execution=holder,
        )
        row = dict(
            self.conn.execute(
                "SELECT * FROM printer_safety_evidence_composites WHERE id=?",
                (result["composite_id"],),
            ).fetchone()
        )
        return result, row

    def test_all_six_holder_states_preserve_truthful_clean_memory(self):
        cases = (
            ("healthy", 30.0, None, "HOLDER_CONCENTRATION_HEALTHY"),
            ("concentrated", 60.0, None, "HOLDER_CONCENTRATION_CONCENTRATED"),
            ("extreme", 99.0, None, "HOLDER_CONCENTRATION_EXTREME"),
            ("unknown", None, "unknown", "HOLDER_CONCENTRATION_UNKNOWN"),
            ("unavailable", None, None, "HOLDER_CONCENTRATION_UNKNOWN"),
            ("conflicting", 30.0, "extreme", "HOLDER_CONCENTRATION_UNKNOWN"),
        )
        before = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in FORBIDDEN_TABLES
        }
        for state, goplus_percent, holder_kind, expected_label in cases:
            with self.subTest(state=state):
                holder = None
                if holder_kind:
                    holder = self._execute(
                        "helius_free",
                        "holder_concentration_reference",
                        {
                            "token_mint": MINT,
                            "holder_concentration_label": (
                                "HOLDER_CONCENTRATION_UNKNOWN"
                                if holder_kind == "unknown"
                                else "HOLDER_CONCENTRATION_EXTREME"
                            ),
                            "top_10_holder_percent": (
                                None if holder_kind == "unknown" else 99.0
                            ),
                        },
                    )
                result, row = self._composite(
                    goplus_percent=goplus_percent, holder=holder
                )
                self.assertEqual(
                    row["holder_concentration_label"], expected_label
                )
                self.assertTrue(composite_row_is_acceptable(row))
                self.assertNotIn(
                    "holder_concentration_label",
                    safety_memory_policy_summary(row)[
                        "hard_blocking_safety_fields"
                    ],
                )
                memory = _classify(outcome="DEAD")
                self.assertEqual(memory["outcome_label"], "DEAD")
                self.assertEqual(memory["memory_quality_label"], "CLEAN_MEMORY")
                self.assertEqual(memory["do_not_train"], 0)
                if state == "conflicting":
                    self.assertIn(
                        "HOLDER_CONCENTRATION_SOURCE_CONFLICT",
                        json.loads(row["conflicts_json"]),
                    )
                if holder_kind:
                    binding = json.loads(row["field_bindings_json"]).get(
                        "holder_concentration_label"
                    )
                    if state == "unknown" or state == "conflicting":
                        self.assertIsNone(binding)
                    else:
                        self.assertEqual(binding, "helius_free")
        after = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in FORBIDDEN_TABLES
        }
        self.assertEqual(before, after)

    def test_holder_percentage_source_and_limitations_are_persisted(self):
        holder = self._execute(
            "helius_free",
            "holder_concentration_reference",
            {
                "token_mint": MINT,
                "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
                "top_10_holder_percent": 99.0,
                "holder_measurement_basis": "SOLANA_GET_TOKEN_LARGEST_ACCOUNTS",
                "holder_measurement_limitations": [
                    "POOL_VAULT_BURN_AND_PROGRAM_ACCOUNTS_ARE_NOT_IDENTIFIED_OR_EXCLUDED"
                ],
            },
        )
        result, row = self._composite(goplus_percent=None, holder=holder)
        contribution = self.conn.execute(
            "SELECT source_name,fields_supplied_json "
            "FROM printer_safety_evidence_contributions "
            "WHERE composite_id=? AND evidence_category='HOLDER_CONCENTRATION'",
            (result["composite_id"],),
        ).fetchone()
        fields = json.loads(contribution["fields_supplied_json"])
        self.assertEqual(contribution["source_name"], "helius_free")
        self.assertEqual(
            json.loads(row["field_bindings_json"])[
                "holder_concentration_label"
            ],
            "helius_free",
        )
        self.assertEqual(fields["top_10_holder_percent"], 99.0)
        self.assertIn(
            "POOL_VAULT_BURN_AND_PROGRAM_ACCOUNTS_ARE_NOT_IDENTIFIED_OR_EXCLUDED",
            fields["holder_measurement_limitations"],
        )

    def test_rpc_top_ten_semantics_and_helius_source_are_truthful(self):
        raw = {
            "token_mint": MINT,
            "largest_accounts_result": {
                "result": {
                    "value": [{"amount": "9"} for _ in range(10)]
                }
            },
            "token_supply_result": {
                "result": {"value": {"amount": "100"}}
            },
        }
        rpc = normalize_solana_rpc_holder_response(
            raw, request_kind="holder_concentration_reference"
        )
        self.assertEqual(
            rpc.normalized_payload["holder_concentration_label"],
            "HOLDER_CONCENTRATION_EXTREME",
        )
        self.assertEqual(rpc.normalized_payload["top_10_holder_percent"], 90.0)
        self.assertIn(
            "GET_TOKEN_LARGEST_ACCOUNTS_RETURNS_TOKEN_ACCOUNTS_NOT_BENEFICIAL_OWNERS",
            rpc.normalized_payload["holder_measurement_limitations"],
        )
        helius = normalize_helius_holder_response(
            raw, request_kind="holder_concentration_reference"
        )
        self.assertEqual(helius.source_name, "helius_free")
        self.assertEqual(
            helius.normalized_payload["source_name"], "helius_free"
        )

    def test_negative_core_evidence_controls_remain_dirty(self):
        cases = {
            "wrong_target": {"blockers": ["CLOSING_EVIDENCE_TARGET_MISMATCH"]},
            "incomplete_duration": {"blockers": ["WINDOW_DURATION_INCOMPLETE"]},
            "missing_snapshot": {"snapshots": _snapshots(5)},
            "stale_core": {
                "snapshots": [
                    *_snapshots(5),
                    {
                        **_snapshots(1)[0],
                        "id": 6,
                        "source_status": "STALE",
                        "data_quality_label": "STALE_DATA",
                    },
                ]
            },
            "broken_provenance": {
                "blockers": ["SNAPSHOT_SOURCE_TRACE_MISSING_OR_INVALID"]
            },
            "missing_outcome": {"outcome": "UNKNOWN_OUTCOME"},
            "missing_realism": {
                "labels": _labels(exit_realism_label="EXIT_UNKNOWN")
            },
        }
        for name, kwargs in cases.items():
            with self.subTest(name=name):
                memory = _classify(**kwargs)
                self.assertNotEqual(
                    memory["memory_quality_label"], "CLEAN_MEMORY"
                )
                self.assertEqual(memory["do_not_train"], 1)

    def test_wrong_target_and_invalid_holder_provenance_still_block(self):
        for blocker in (
            "HOLDER_EVIDENCE_TARGET_MISMATCH",
            "HOLDER_EVIDENCE_PROVENANCE_INVALID",
        ):
            with self.subTest(blocker=blocker):
                memory = _classify(blockers=[blocker])
                self.assertNotEqual(
                    memory["memory_quality_label"], "CLEAN_MEMORY"
                )
                self.assertEqual(memory["do_not_train"], 1)


if __name__ == "__main__":
    unittest.main()
