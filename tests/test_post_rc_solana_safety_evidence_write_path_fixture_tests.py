"""Fixture-only tests for the future Solana safety evidence write path.

These tests intentionally do not import or call any production write helper.
They define the future write-path guard contract with in-memory dictionaries
only, so no persistent DB, source adapter, scheduler runtime, or paper-trading
state can be touched.
"""

from __future__ import annotations

import unittest


ALLOWED_NORMALIZED_LABELS = {
    "SAFETY_CLEAR",
    "SAFETY_CAUTION",
    "SAFETY_BLOCKED",
    "SAFETY_UNKNOWN",
}

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "rank",
    "confidence",
    "weight",
    "weighted",
    "buy_signal",
    "sell_signal",
    "trade_signal",
    "wallet",
    "private_key",
    "signature",
    "signer",
    "live_execution",
    "buy_unlock",
    "pnl",
    "retrieval_ready",
)

FORBIDDEN_DIRECT_WRITE_ENGINES = {
    "memory_engine",
    "retrieval_engine",
    "paper_decision_engine",
    "paper_position_engine",
    "pnl_engine",
}


def safety_write_fixture(**overrides: object) -> dict[str, object]:
    fixture: dict[str, object] = {
        "token_id": 2,
        "pair_id": 2,
        "snapshot_id": 36,
        "memory_window_id": 8,
        "expected_token_id": 2,
        "expected_snapshot_id": 36,
        "source_request_id": 101,
        "source_response_id": 201,
        "source_failure_id": None,
        "scheduled_collection_boundary": True,
        "operator_approved_manual_proof": True,
        "write_origin": "source_governor_scheduler",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
        "quote_or_trade_purpose": "MEMORY_CONTEXT_ONLY",
        "safety_fixture_state": "CLEAR",
        "paper_only_context": True,
        "fixture_only": True,
    }
    fixture.update(overrides)
    return fixture


def has_source_governor_trace(fixture: dict[str, object]) -> bool:
    has_request = fixture.get("source_request_id") is not None
    has_terminal_trace = (
        fixture.get("source_response_id") is not None
        or fixture.get("source_failure_id") is not None
    )
    return has_request and has_terminal_trace


def has_scheduler_operator_boundary(fixture: dict[str, object]) -> bool:
    return (
        fixture.get("scheduled_collection_boundary") is True
        and fixture.get("operator_approved_manual_proof") is True
    )


def target_matches_fixture(fixture: dict[str, object]) -> bool:
    return (
        fixture.get("target_status") == "TARGET_MATCH"
        and fixture.get("token_id") == fixture.get("expected_token_id")
        and fixture.get("snapshot_id") == fixture.get("expected_snapshot_id")
    )


def write_eligible_fixture(fixture: dict[str, object]) -> bool:
    return (
        has_source_governor_trace(fixture)
        and has_scheduler_operator_boundary(fixture)
        and target_matches_fixture(fixture)
        and fixture.get("paper_only_context") is True
    )


def normalized_safety_label(fixture: dict[str, object]) -> str:
    state = fixture.get("safety_fixture_state")
    if state == "CLEAR":
        return "SAFETY_CLEAR"
    if state == "CAUTION":
        return "SAFETY_CAUTION"
    if state == "BLOCKED":
        return "SAFETY_BLOCKED"
    return "SAFETY_UNKNOWN"


def safety_context_can_support_clean_memory(fixture: dict[str, object]) -> bool:
    return (
        write_eligible_fixture(fixture)
        and normalized_safety_label(fixture) == "SAFETY_CLEAR"
        and fixture.get("source_status") == "COMPLETE"
        and fixture.get("data_quality_label") == "CLEAN_DATA"
        and fixture.get("freshness_label") == "SAFETY_EVIDENCE_FRESH"
    )


def audit_visibility_label(fixture: dict[str, object]) -> str:
    if not has_source_governor_trace(fixture):
        return "AUDIT_ONLY_MISSING_SOURCE_TRACE"
    if not has_scheduler_operator_boundary(fixture):
        return "AUDIT_ONLY_MISSING_COLLECTION_BOUNDARY"
    if not target_matches_fixture(fixture):
        return "AUDIT_ONLY_TARGET_MISMATCH"
    if fixture.get("source_status") == "FAILED":
        return "AUDIT_ONLY_FAILED_SOURCE"
    if fixture.get("freshness_label") == "SAFETY_EVIDENCE_STALE":
        return "AUDIT_ONLY_STALE_EVIDENCE"
    if normalized_safety_label(fixture) in {"SAFETY_BLOCKED", "SAFETY_UNKNOWN"}:
        return "AUDIT_ONLY_UNSAFE_OR_UNKNOWN"
    return "WRITE_PATH_FIXTURE_ACCEPTED"


def downstream_gate_effects(_fixture: dict[str, object]) -> dict[str, bool]:
    return {
        "clean_memory_created": False,
        "retrieval_unlocked": False,
        "paper_decision_created": False,
        "buy_unlocked": False,
        "paper_position_created": False,
        "paper_trade_event_created": False,
        "pnl_created": False,
        "lane7_activated": False,
    }


def direct_write_allowed(engine_name: str) -> bool:
    return engine_name == "source_governor_scheduler"


class SolanaSafetyEvidenceWritePathFixtureTests(unittest.TestCase):
    def test_valid_fixture_requires_source_governor_trace(self) -> None:
        fixture = safety_write_fixture()

        self.assertIsNotNone(fixture["source_request_id"])
        self.assertTrue(
            fixture["source_response_id"] is not None
            or fixture["source_failure_id"] is not None
        )
        self.assertTrue(has_source_governor_trace(fixture))

    def test_missing_source_request_blocks_clean_eligibility(self) -> None:
        fixture = safety_write_fixture(source_request_id=None)

        self.assertFalse(has_source_governor_trace(fixture))
        self.assertFalse(safety_context_can_support_clean_memory(fixture))
        self.assertEqual(audit_visibility_label(fixture), "AUDIT_ONLY_MISSING_SOURCE_TRACE")

    def test_missing_response_and_failure_blocks_clean_eligibility(self) -> None:
        fixture = safety_write_fixture(source_response_id=None, source_failure_id=None)

        self.assertFalse(has_source_governor_trace(fixture))
        self.assertFalse(safety_context_can_support_clean_memory(fixture))
        self.assertEqual(audit_visibility_label(fixture), "AUDIT_ONLY_MISSING_SOURCE_TRACE")

    def test_valid_fixture_requires_scheduler_and_operator_boundary(self) -> None:
        fixture = safety_write_fixture()

        self.assertTrue(fixture["scheduled_collection_boundary"])
        self.assertTrue(fixture["operator_approved_manual_proof"])
        self.assertTrue(has_scheduler_operator_boundary(fixture))

    def test_missing_scheduler_boundary_blocks_write_eligibility(self) -> None:
        fixture = safety_write_fixture(scheduled_collection_boundary=False)

        self.assertFalse(write_eligible_fixture(fixture))
        self.assertEqual(
            audit_visibility_label(fixture),
            "AUDIT_ONLY_MISSING_COLLECTION_BOUNDARY",
        )

    def test_missing_operator_approval_blocks_manual_proof_write_eligibility(self) -> None:
        fixture = safety_write_fixture(operator_approved_manual_proof=False)

        self.assertFalse(write_eligible_fixture(fixture))
        self.assertEqual(
            audit_visibility_label(fixture),
            "AUDIT_ONLY_MISSING_COLLECTION_BOUNDARY",
        )

    def test_target_and_freshness_validation(self) -> None:
        valid = safety_write_fixture()
        wrong_token = safety_write_fixture(token_id=999)
        wrong_snapshot = safety_write_fixture(snapshot_id=999)
        stale = safety_write_fixture(freshness_label="SAFETY_EVIDENCE_STALE")
        failed = safety_write_fixture(
            source_status="FAILED",
            source_response_id=None,
            source_failure_id=301,
        )
        bad_quality = safety_write_fixture(data_quality_label="BROKEN_DATA")

        self.assertTrue(target_matches_fixture(valid))
        self.assertFalse(write_eligible_fixture(wrong_token))
        self.assertFalse(write_eligible_fixture(wrong_snapshot))
        self.assertFalse(safety_context_can_support_clean_memory(stale))
        self.assertFalse(safety_context_can_support_clean_memory(failed))
        self.assertFalse(safety_context_can_support_clean_memory(bad_quality))
        self.assertEqual(audit_visibility_label(stale), "AUDIT_ONLY_STALE_EVIDENCE")
        self.assertEqual(audit_visibility_label(failed), "AUDIT_ONLY_FAILED_SOURCE")

    def test_categorical_normalization_only_and_forbidden_fields_absent(self) -> None:
        fixtures = [
            safety_write_fixture(safety_fixture_state="CLEAR"),
            safety_write_fixture(safety_fixture_state="CAUTION"),
            safety_write_fixture(safety_fixture_state="BLOCKED"),
            safety_write_fixture(safety_fixture_state="MISSING"),
        ]

        self.assertEqual(
            {normalized_safety_label(fixture) for fixture in fixtures},
            ALLOWED_NORMALIZED_LABELS,
        )

        field_names = set(safety_write_fixture().keys())
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertFalse(
                any(fragment in field_name.lower() for field_name in field_names),
                fragment,
            )

    def test_failed_missing_stale_and_mismatched_evidence_remain_audit_only(self) -> None:
        cases = {
            "failed": safety_write_fixture(
                source_status="FAILED",
                source_response_id=None,
                source_failure_id=301,
            ),
            "missing": safety_write_fixture(safety_fixture_state="MISSING"),
            "stale": safety_write_fixture(freshness_label="SAFETY_EVIDENCE_STALE"),
            "mismatched": safety_write_fixture(target_status="TARGET_MISMATCH"),
            "blocked": safety_write_fixture(safety_fixture_state="BLOCKED"),
        }

        self.assertEqual(normalized_safety_label(cases["missing"]), "SAFETY_UNKNOWN")
        for fixture in cases.values():
            self.assertFalse(safety_context_can_support_clean_memory(fixture))
            self.assertTrue(audit_visibility_label(fixture).startswith("AUDIT_ONLY_"))

    def test_caution_does_not_unlock_clean_memory_or_downstream_gates(self) -> None:
        fixture = safety_write_fixture(safety_fixture_state="CAUTION")

        self.assertEqual(normalized_safety_label(fixture), "SAFETY_CAUTION")
        self.assertFalse(safety_context_can_support_clean_memory(fixture))
        self.assertTrue(all(value is False for value in downstream_gate_effects(fixture).values()))

    def test_direct_writes_are_forbidden_from_downstream_engines(self) -> None:
        for engine_name in FORBIDDEN_DIRECT_WRITE_ENGINES:
            self.assertFalse(direct_write_allowed(engine_name), engine_name)

        self.assertTrue(direct_write_allowed("source_governor_scheduler"))

    def test_write_path_acceptance_preserves_downstream_gates(self) -> None:
        fixture = safety_write_fixture()

        self.assertTrue(write_eligible_fixture(fixture))
        self.assertTrue(safety_context_can_support_clean_memory(fixture))
        self.assertEqual(
            downstream_gate_effects(fixture),
            {
                "clean_memory_created": False,
                "retrieval_unlocked": False,
                "paper_decision_created": False,
                "buy_unlocked": False,
                "paper_position_created": False,
                "paper_trade_event_created": False,
                "pnl_created": False,
                "lane7_activated": False,
            },
        )

    def test_fixture_only_contract_does_not_define_runtime_write_path(self) -> None:
        fixture = safety_write_fixture()

        self.assertTrue(fixture["fixture_only"])
        self.assertNotIn("production_insert_helper", globals())
        self.assertNotIn("runtime_scheduler_entrypoint", globals())


if __name__ == "__main__":
    unittest.main()
