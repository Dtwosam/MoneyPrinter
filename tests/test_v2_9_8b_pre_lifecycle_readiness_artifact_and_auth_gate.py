"""V2-9.8B pre-lifecycle readiness artifact + authorization preparation gate."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.pre_lifecycle_readiness_artifact import (
    PreLifecycleReadinessArtifactError,
    build_pre_lifecycle_readiness_artifact,
    compute_db_identity,
    validate_pre_lifecycle_readiness_artifact,
)
from printer_v1.operator_cli.pre_lifecycle_readiness_authorization_gate import (
    evaluate_authorization_preparation_readiness_gate,
)


def _gates_pass() -> dict[str, str]:
    return {
        "pump_pumpswap_graduation_and_pool_identity": "PASS",
        "exact_pool_liquidity_at_or_above_3000": "PASS",
        "tracking_cooldown_eligibility": "PASS",
        "holder_eligibility": "PASS",
        "neutral_two_candidate_selection": "PASS",
        "source_quality_gates": "PASS",
    }


def _candidate(
    mint: str,
    pool: str,
    *,
    t0: datetime,
    gates: dict[str, str] | None = None,
    request_ids: list[int] | None = None,
    response_ids: list[int] | None = None,
) -> dict:
    return {
        "mint": mint,
        "pool": pool,
        "gates": gates or _gates_pass(),
        "source_lineage": {
            "source_request_ids": request_ids or [10, 11],
            "source_response_ids": response_ids or [20, 21],
            "source_failure_ids": [],
        },
        "liquidity_evidence_at": t0.isoformat(),
        "holder_evidence_at": t0.isoformat(),
        "liquidity_source_name": "dexscreener",
        "holder_source_name": "solana_rpc",
        "eligible": True,
    }


class PreLifecycleReadinessArtifactMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "ready.sqlite3"
        apply_migrations(self.db)
        self.db_identity = compute_db_identity(self.db)
        self.head = "abc123def4567890abc123def4567890abc123de"
        self.t0 = datetime(2026, 8, 3, 12, 0, 0, tzinfo=timezone.utc)
        self.candidates = [
            _candidate("MintOne", "PoolOne", t0=self.t0),
            _candidate("MintTwo", "PoolTwo", t0=self.t0),
        ]

    def _build(self, **kwargs):
        params = dict(
            qualification_execution_id="qual-exec-1",
            implementation_head=self.head,
            db_path=self.db,
            created_at=self.t0.isoformat(),
            candidates=self.candidates,
            db_identity=self.db_identity,
        )
        params.update(kwargs)
        return build_pre_lifecycle_readiness_artifact(**params)

    def test_two_eligible_candidates_produce_valid_artifact(self) -> None:
        artifact = self._build()
        self.assertEqual(artifact["candidate_count"], 2)
        self.assertEqual(
            artifact["verdict"], "PRE_LIFECYCLE_READINESS_ARTIFACT_PASS"
        )
        self.assertFalse(artifact["downstream"]["lifecycle_started"])
        self.assertFalse(artifact["downstream"]["tracking_started"])
        self.assertFalse(artifact["downstream"]["memory_window_created"])
        self.assertFalse(artifact["downstream"]["scheduler_runtime_started"])
        self.assertTrue(
            all(v == 0 for v in artifact["capability_deltas"].values())
        )
        # dexscreener stale_after=90 → expiry at t0+90s
        expected_exp = (self.t0 + timedelta(seconds=90)).isoformat()
        self.assertEqual(artifact["expires_at"], expected_exp)

        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=30),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
            expected_candidates=self.candidates,
            candidate_state=[
                {"eligible": True},
                {"eligible": True},
            ],
        )
        self.assertTrue(validation["valid"])
        gate = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=artifact,
            now=self.t0 + timedelta(seconds=30),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
            expected_candidates=self.candidates,
            candidate_state=[{"eligible": True}, {"eligible": True}],
        )
        self.assertTrue(gate["valid"])
        self.assertTrue(gate["status"].endswith("_PASS"))
        self.assertFalse(gate["authorization_emitted"])

    def test_one_eligible_candidate_blocks_build(self) -> None:
        with self.assertRaises(PreLifecycleReadinessArtifactError):
            self._build(candidates=[self.candidates[0]])

    def test_holder_failure_blocks_build(self) -> None:
        bad_gates = _gates_pass()
        bad_gates["holder_eligibility"] = "FAIL"
        with self.assertRaises(PreLifecycleReadinessArtifactError):
            self._build(
                candidates=[
                    self.candidates[0],
                    _candidate("MintTwo", "PoolTwo", t0=self.t0, gates=bad_gates),
                ]
            )

    def test_holder_source_unavailable_blocks_expiry(self) -> None:
        bad = dict(self.candidates[1])
        bad["holder_source_name"] = "not_a_registered_source"
        with self.assertRaises(PreLifecycleReadinessArtifactError):
            self._build(candidates=[self.candidates[0], bad])

    def test_expired_evidence_blocks_validation(self) -> None:
        artifact = self._build()
        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=120),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(validation["valid"])
        self.assertTrue(
            any(
                b in validation["blockers"]
                for b in ("artifact_expired",)
            )
            or any(b.startswith("evidence_row_") for b in validation["blockers"])
        )

    def test_head_mismatch_blocks(self) -> None:
        artifact = self._build()
        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=10),
            expected_head="0" * 40,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(validation["valid"])
        self.assertIn("head_mismatch", validation["blockers"])

    def test_db_mismatch_blocks(self) -> None:
        artifact = self._build()
        bad_db = dict(self.db_identity)
        bad_db["sha256"] = "0" * 64
        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=10),
            expected_head=self.head,
            expected_db_identity=bad_db,
        )
        self.assertFalse(validation["valid"])
        self.assertIn("db_sha256_mismatch", validation["blockers"])

    def test_pool_mismatch_blocks(self) -> None:
        artifact = self._build()
        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=10),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
            expected_candidates=[
                {"mint": "MintOne", "pool": "PoolOne"},
                {"mint": "MintTwo", "pool": "OtherPool"},
            ],
        )
        self.assertFalse(validation["valid"])
        self.assertIn("mint_or_pool_identity_differs", validation["blockers"])

    def test_missing_source_lineage_blocks_build(self) -> None:
        bad = dict(self.candidates[0])
        bad["source_lineage"] = {
            "source_request_ids": [],
            "source_response_ids": [1],
            "source_failure_ids": [],
        }
        with self.assertRaises(PreLifecycleReadinessArtifactError):
            self._build(candidates=[bad, self.candidates[1]])

    def test_candidate_state_change_blocks(self) -> None:
        artifact = self._build()
        validation = validate_pre_lifecycle_readiness_artifact(
            artifact,
            now=self.t0 + timedelta(seconds=10),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
            candidate_state=[{"eligible": True}, {"eligible": False}],
        )
        self.assertFalse(validation["valid"])
        self.assertIn("candidate_state_1_not_eligible", validation["blockers"])

    def test_no_tracking_lifecycle_memory_retrieval_financial_rows(self) -> None:
        artifact = self._build()
        for flag in (
            "tracking_started",
            "lifecycle_started",
            "memory_window_created",
            "scheduler_runtime_started",
            "factory_run_created",
        ):
            self.assertIs(artifact["downstream"][flag], False)
        for key in (
            "retrieval",
            "paper_decisions",
            "positions",
            "trade_events",
            "trade_audits",
            "pnl",
        ):
            self.assertEqual(artifact["capability_deltas"][key], 0)
        # Disposable DB still has no forbidden operational rows from artifact build.
        import sqlite3

        conn = sqlite3.connect(self.db)
        try:
            for table in (
                "printer_memory_windows",
                "printer_paper_decisions",
                "printer_paper_positions",
            ):
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_auth_gate_refuses_every_invalid_artifact(self) -> None:
        cases = [
            None,
            self._build(),  # will mutate checks via kwargs
        ]
        # absent
        gate = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=None,
            now=self.t0,
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(gate["valid"])
        self.assertFalse(gate["authorization_emitted"])

        artifact = self._build()
        # expired
        gate = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=artifact,
            now=self.t0 + timedelta(hours=1),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(gate["valid"])
        self.assertFalse(gate["authorization_emitted"])

        # head mismatch
        gate = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=artifact,
            now=self.t0 + timedelta(seconds=5),
            expected_head="f" * 40,
            expected_db_identity=self.db_identity,
        )
        self.assertFalse(gate["valid"])
        self.assertFalse(gate["authorization_emitted"])

    def test_no_actual_authorization_produced(self) -> None:
        artifact = self._build()
        gate = evaluate_authorization_preparation_readiness_gate(
            readiness_artifact=artifact,
            now=self.t0 + timedelta(seconds=5),
            expected_head=self.head,
            expected_db_identity=self.db_identity,
            expected_candidates=self.candidates,
            candidate_state=[{"eligible": True}, {"eligible": True}],
        )
        self.assertTrue(gate["valid"])
        self.assertFalse(gate["authorization_emitted"])
        self.assertFalse(gate["wrapper_invoked"])
        self.assertFalse(gate["provider_contacted"])
        self.assertNotIn("final_authorization", gate)
        self.assertNotIn("authorization_id", gate)


if __name__ == "__main__":
    unittest.main()
