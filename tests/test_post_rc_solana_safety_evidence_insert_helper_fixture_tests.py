"""Fixture-only tests for the future Solana safety evidence insert helper.

These tests intentionally define an in-memory contract evaluator instead of a
production helper. They do not import sqlite3, do not write persistent data,
and do not call any source, scheduler, memory, retrieval, paper, or runtime
code.
"""

from __future__ import annotations

from dataclasses import dataclass
import unittest


REQUIRED_INPUT_FIELDS = {
    "token_id",
    "snapshot_id",
    "safety_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "safety_context_label",
    "source_request_id",
    "paper_only_context",
    "scheduler_boundary_label",
    "operator_approval_label",
}

ALLOWED_SUMMARY_LABELS = {
    "SAFETY_CLEAR",
    "SAFETY_CAUTION",
    "SAFETY_BLOCKED",
    "SAFETY_UNKNOWN",
}

CLEAN_SOURCE_STATUSES = {"COMPLETE", "PARTIAL"}
CLEAN_DATA_QUALITY_LABELS = {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
CLEAN_FRESHNESS_LABELS = {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
CLEAN_STORAGE_SAFETY_LABELS = {"SAFETY_CLEAN"}
CAUTION_STORAGE_SAFETY_LABELS = {"SAFETY_CAUTION", "SAFETY_SUSPICIOUS"}
BLOCKED_STORAGE_SAFETY_LABELS = {
    "SAFETY_UNSAFE",
    "SAFETY_DO_NOT_USE_FOR_MEMORY",
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

FORBIDDEN_DIRECT_CALLERS = {
    "memory_engine",
    "retrieval_engine",
    "paper_decision_engine",
    "paper_position_engine",
    "pnl_engine",
}

ALLOWED_CALLER = "source_governor_scheduler_operator_flow"


@dataclass(frozen=True)
class InsertFixtureResult:
    inserted: bool
    evidence_id: int | None
    audit_status: str
    clean_eligible: bool
    clean_memory_created: bool
    retrieval_ready: bool
    rejection_reasons: tuple[str, ...]
    source_trace_status: str
    scheduler_boundary_status: str
    downstream_unlocks: dict[str, bool]


def future_insert_input_fixture(**overrides: object) -> dict[str, object]:
    fixture: dict[str, object] = {
        "token_id": 2,
        "pair_id": 2,
        "snapshot_id": 36,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
        "source_name": "governed_safety_fixture",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "target_status": "TARGET_MATCH",
        "evidence_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
        "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
        "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
        "metadata_mutability_status": "METADATA_IMMUTABLE",
        "supply_sanity_label": "SUPPLY_SANITY_OK",
        "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
        "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
        "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
        "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
        "safety_context_label": "SAFETY_CLEAN",
        "source_request_id": 101,
        "source_response_id": 201,
        "source_failure_id": None,
        "paper_only_context": True,
        "scheduler_boundary_label": "SCHEDULER_BOUNDARY_PRESENT",
        "operator_approval_label": "OPERATOR_APPROVED_MANUAL_PROOF",
        "caller": ALLOWED_CALLER,
        "created_at": "2026-06-23T12:00:01+00:00",
    }
    fixture.update(overrides)
    return fixture


def summarize_safety_label(fixture: dict[str, object]) -> str:
    safety_label = fixture.get("safety_context_label")
    if safety_label in CLEAN_STORAGE_SAFETY_LABELS:
        return "SAFETY_CLEAR"
    if safety_label in CAUTION_STORAGE_SAFETY_LABELS:
        return "SAFETY_CAUTION"
    if safety_label in BLOCKED_STORAGE_SAFETY_LABELS:
        return "SAFETY_BLOCKED"
    return "SAFETY_UNKNOWN"


def has_source_trace(fixture: dict[str, object]) -> bool:
    return (
        fixture.get("source_request_id") is not None
        and (
            fixture.get("source_response_id") is not None
            or fixture.get("source_failure_id") is not None
        )
    )


def source_trace_status(fixture: dict[str, object]) -> str:
    if not has_source_trace(fixture):
        return "SOURCE_TRACE_MISSING"
    if fixture.get("source_failure_id") is not None:
        return "SOURCE_TRACE_FAILED_VISIBLE"
    return "SOURCE_TRACE_PRESENT"


def scheduler_boundary_status(fixture: dict[str, object]) -> str:
    if fixture.get("scheduler_boundary_label") != "SCHEDULER_BOUNDARY_PRESENT":
        return "SCHEDULER_BOUNDARY_MISSING"
    if fixture.get("operator_approval_label") != "OPERATOR_APPROVED_MANUAL_PROOF":
        return "OPERATOR_APPROVAL_MISSING"
    return "SCHEDULER_OPERATOR_BOUNDARY_PRESENT"


def forbidden_fields_present(fixture: dict[str, object]) -> tuple[str, ...]:
    field_names = " ".join(str(field_name).lower() for field_name in fixture.keys())
    return tuple(
        fragment for fragment in FORBIDDEN_FIELD_FRAGMENTS if fragment in field_names
    )


def evaluate_future_insert_fixture(fixture: dict[str, object]) -> InsertFixtureResult:
    rejection_reasons: list[str] = []

    for field_name in sorted(REQUIRED_INPUT_FIELDS):
        if fixture.get(field_name) is None:
            rejection_reasons.append(f"MISSING_{field_name.upper()}")

    if not has_source_trace(fixture):
        rejection_reasons.append("SOURCE_TRACE_MISSING")
    if fixture.get("paper_only_context") is not True:
        rejection_reasons.append("PAPER_ONLY_CONTEXT_REQUIRED")
    if scheduler_boundary_status(fixture) == "SCHEDULER_BOUNDARY_MISSING":
        rejection_reasons.append("SCHEDULER_BOUNDARY_MISSING")
    if scheduler_boundary_status(fixture) == "OPERATOR_APPROVAL_MISSING":
        rejection_reasons.append("OPERATOR_APPROVAL_MISSING")
    if fixture.get("target_status") != "TARGET_MATCH":
        rejection_reasons.append("TARGET_MISMATCH")
    if fixture.get("caller") in FORBIDDEN_DIRECT_CALLERS:
        rejection_reasons.append("DIRECT_CALLER_FORBIDDEN")
    if fixture.get("caller") != ALLOWED_CALLER:
        rejection_reasons.append("SOURCE_GOVERNOR_SCHEDULER_BOUNDARY_REQUIRED")

    forbidden = forbidden_fields_present(fixture)
    if forbidden:
        rejection_reasons.append("FORBIDDEN_FIELDS_PRESENT")

    clean_eligible = (
        not rejection_reasons
        and fixture.get("source_status") in CLEAN_SOURCE_STATUSES
        and fixture.get("data_quality_label") in CLEAN_DATA_QUALITY_LABELS
        and fixture.get("freshness_label") in CLEAN_FRESHNESS_LABELS
        and fixture.get("safety_context_label") in CLEAN_STORAGE_SAFETY_LABELS
    )

    audit_only = not clean_eligible and not rejection_reasons and has_source_trace(fixture)
    inserted = not rejection_reasons
    audit_status = "INSERTED_AUDITABLE"
    if rejection_reasons:
        audit_status = "REJECTED_GUARD_FAILED"
    elif audit_only:
        audit_status = "AUDIT_ONLY_EVIDENCE"

    return InsertFixtureResult(
        inserted=inserted,
        evidence_id=999 if inserted else None,
        audit_status=audit_status,
        clean_eligible=clean_eligible,
        clean_memory_created=False,
        retrieval_ready=False,
        rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
        source_trace_status=source_trace_status(fixture),
        scheduler_boundary_status=scheduler_boundary_status(fixture),
        downstream_unlocks={
            "clean_memory": False,
            "retrieval": False,
            "paper_decision": False,
            "buy": False,
            "paper_position": False,
            "paper_trade_event": False,
            "pnl": False,
            "lane7": False,
        },
    )


class SolanaSafetyEvidenceInsertHelperFixtureTests(unittest.TestCase):
    def test_valid_future_helper_fixture_includes_required_inputs(self) -> None:
        fixture = future_insert_input_fixture()

        self.assertTrue(REQUIRED_INPUT_FIELDS.issubset(fixture.keys()))
        self.assertIsNotNone(fixture["source_request_id"])
        self.assertTrue(
            fixture["source_response_id"] is not None
            or fixture["source_failure_id"] is not None
        )
        self.assertTrue(fixture["paper_only_context"])
        self.assertEqual(
            fixture["scheduler_boundary_label"],
            "SCHEDULER_BOUNDARY_PRESENT",
        )
        self.assertEqual(
            fixture["operator_approval_label"],
            "OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def test_missing_critical_fields_are_rejected_or_marked_ineligible(self) -> None:
        cases = {
            "token": future_insert_input_fixture(token_id=None),
            "snapshot": future_insert_input_fixture(snapshot_id=None),
            "source_request": future_insert_input_fixture(source_request_id=None),
            "terminal_source_trace": future_insert_input_fixture(
                source_response_id=None,
                source_failure_id=None,
            ),
            "paper_only": future_insert_input_fixture(paper_only_context=False),
            "scheduler_boundary": future_insert_input_fixture(
                scheduler_boundary_label=None,
            ),
            "operator_approval": future_insert_input_fixture(
                operator_approval_label=None,
            ),
        }

        for case_name, fixture in cases.items():
            with self.subTest(case_name=case_name):
                result = evaluate_future_insert_fixture(fixture)
                self.assertFalse(result.clean_eligible)
                self.assertEqual(result.audit_status, "REJECTED_GUARD_FAILED")
                self.assertTrue(result.rejection_reasons)

    def test_target_freshness_source_and_data_quality_guards(self) -> None:
        cases = {
            "target_mismatch": future_insert_input_fixture(
                target_status="TARGET_MISMATCH"
            ),
            "stale": future_insert_input_fixture(
                freshness_label="SAFETY_EVIDENCE_STALE"
            ),
            "failed_source": future_insert_input_fixture(
                source_status="FAILED",
                source_response_id=None,
                source_failure_id=301,
            ),
            "bad_quality": future_insert_input_fixture(
                data_quality_label="MISSING_CRITICAL_DATA"
            ),
            "missing_trace": future_insert_input_fixture(
                source_request_id=None,
                source_response_id=None,
            ),
        }

        self.assertIn(
            "TARGET_MISMATCH",
            evaluate_future_insert_fixture(cases["target_mismatch"]).rejection_reasons,
        )
        for case_name, fixture in cases.items():
            with self.subTest(case_name=case_name):
                result = evaluate_future_insert_fixture(fixture)
                self.assertFalse(result.clean_eligible)
                self.assertFalse(result.clean_memory_created)

    def test_safety_label_behavior_is_categorical_and_guarded(self) -> None:
        clear = future_insert_input_fixture(safety_context_label="SAFETY_CLEAN")
        caution = future_insert_input_fixture(safety_context_label="SAFETY_CAUTION")
        blocked = future_insert_input_fixture(safety_context_label="SAFETY_UNSAFE")
        unknown = future_insert_input_fixture(safety_context_label="SAFETY_UNKNOWN")
        stale = future_insert_input_fixture(
            safety_context_label="SAFETY_CLEAN",
            freshness_label="SAFETY_EVIDENCE_STALE",
        )
        mismatched = future_insert_input_fixture(
            safety_context_label="SAFETY_CLEAN",
            target_status="TARGET_MISMATCH",
        )

        self.assertEqual(
            {
                summarize_safety_label(clear),
                summarize_safety_label(caution),
                summarize_safety_label(blocked),
                summarize_safety_label(unknown),
            },
            ALLOWED_SUMMARY_LABELS,
        )
        self.assertTrue(evaluate_future_insert_fixture(clear).clean_eligible)

        for fixture in (caution, blocked, unknown, stale, mismatched):
            with self.subTest(label=fixture["safety_context_label"]):
                result = evaluate_future_insert_fixture(fixture)
                self.assertFalse(result.clean_eligible)
                self.assertNotEqual(result.audit_status, "INSERTED_AUDITABLE")

    def test_forbidden_fields_are_rejected_from_input_fixtures(self) -> None:
        valid = future_insert_input_fixture()

        self.assertEqual(forbidden_fields_present(valid), ())
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            with self.subTest(fragment=fragment):
                result = evaluate_future_insert_fixture(
                    future_insert_input_fixture(**{f"{fragment}_field": "forbidden"})
                )
                self.assertIn("FORBIDDEN_FIELDS_PRESENT", result.rejection_reasons)

    def test_direct_caller_boundaries(self) -> None:
        for caller in FORBIDDEN_DIRECT_CALLERS:
            with self.subTest(caller=caller):
                result = evaluate_future_insert_fixture(
                    future_insert_input_fixture(caller=caller)
                )
                self.assertIn("DIRECT_CALLER_FORBIDDEN", result.rejection_reasons)
                self.assertFalse(result.clean_eligible)

        allowed = evaluate_future_insert_fixture(
            future_insert_input_fixture(caller=ALLOWED_CALLER)
        )
        self.assertTrue(allowed.clean_eligible)

    def test_return_shape_guardrails(self) -> None:
        accepted = evaluate_future_insert_fixture(future_insert_input_fixture())
        rejected = evaluate_future_insert_fixture(
            future_insert_input_fixture(source_request_id=None)
        )
        audit_only = evaluate_future_insert_fixture(
            future_insert_input_fixture(safety_context_label="SAFETY_CAUTION")
        )

        self.assertEqual(
            set(accepted.downstream_unlocks.values()),
            {False},
        )
        self.assertTrue(accepted.inserted)
        self.assertTrue(accepted.clean_eligible)
        self.assertFalse(accepted.clean_memory_created)
        self.assertFalse(accepted.retrieval_ready)
        self.assertIsNotNone(accepted.evidence_id)

        self.assertFalse(rejected.inserted)
        self.assertEqual(rejected.evidence_id, None)
        self.assertTrue(rejected.rejection_reasons)

        self.assertTrue(audit_only.inserted)
        self.assertEqual(audit_only.audit_status, "AUDIT_ONLY_EVIDENCE")
        self.assertFalse(audit_only.clean_eligible)
        self.assertEqual(set(audit_only.downstream_unlocks.values()), {False})

    def test_downstream_gate_preservation(self) -> None:
        result = evaluate_future_insert_fixture(future_insert_input_fixture())

        self.assertFalse(result.clean_memory_created)
        self.assertFalse(result.retrieval_ready)
        self.assertEqual(
            result.downstream_unlocks,
            {
                "clean_memory": False,
                "retrieval": False,
                "paper_decision": False,
                "buy": False,
                "paper_position": False,
                "paper_trade_event": False,
                "pnl": False,
                "lane7": False,
            },
        )

    def test_fixture_tests_do_not_define_runtime_or_production_helper(self) -> None:
        self.assertNotIn("insert_solana_safety_evidence", globals())
        self.assertNotIn("runtime_scheduler_entrypoint", globals())
        self.assertNotIn("source_adapter", globals())


if __name__ == "__main__":
    unittest.main()
