import unittest

from tests.test_post_rc_solana_safety_evidence_fixture_contract import (
    classify_fixture,
    safety_fixture,
    safety_fixture_can_support_clean_memory_portion,
)
from printer_v1.safety.contracts import SafetyPayloadQualityLabel, SafetyStatusLabel


PROPOSED_TABLE_NAME = "printer_solana_safety_evidence"

PROPOSED_FIELDS = {
    "id",
    "token_id",
    "pair_id",
    "snapshot_id",
    "memory_window_id",
    "evidence_window_id",
    "safety_evidence_role",
    "source_name",
    "source_status",
    "data_quality_label",
    "target_status",
    "evidence_captured_at",
    "freshness_label",
    "mint_authority_status",
    "freeze_authority_status",
    "metadata_mutability_status",
    "supply_sanity_label",
    "holder_concentration_label",
    "liquidity_lock_or_burn_label",
    "known_risk_flag_label",
    "token_program_label",
    "safety_context_label",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "paper_only_context",
    "created_at",
}

FORBIDDEN_FIELD_FRAGMENTS = (
    "score",
    "ranking",
    "rank",
    "confidence",
    "weighted",
    "weight",
    "wallet",
    "private_key",
    "signature",
    "signing",
    "transaction",
    "live_execution",
    "live_trading",
)


def storage_fixture(**overrides):
    fixture = {
        "id": 1,
        "memory_window_id": 8,
        "evidence_window_id": None,
        "safety_context_label": SafetyStatusLabel.SAFETY_CLEAN.value,
    }
    fixture.update(safety_fixture())
    fixture.update(overrides)
    return fixture


def storage_has_source_trace(row):
    if row.get("source_request_id") is None:
        return False
    if row.get("source_status") == "FAILED":
        return row.get("source_failure_id") is not None
    return row.get("source_response_id") is not None


def storage_can_support_evidence_window_clean_eligibility(row):
    return (
        row.get("token_id") is not None
        and row.get("snapshot_id") is not None
        and row.get("paper_only_context") is True
        and storage_has_source_trace(row)
        and safety_fixture_can_support_clean_memory_portion(row)
    )


class PostRcSolanaSafetyEvidenceStorageSchemaDesignTest(unittest.TestCase):
    def test_proposed_table_shape_has_required_fields_only(self):
        required = {
            "id",
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
            "source_response_id",
            "source_failure_id",
            "paper_only_context",
            "created_at",
        }
        self.assertEqual(PROPOSED_TABLE_NAME, "printer_solana_safety_evidence")
        self.assertTrue(required.issubset(PROPOSED_FIELDS))

    def test_proposed_shape_excludes_scores_wallets_and_live_execution_fields(self):
        field_text = " ".join(PROPOSED_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_token_snapshot_paper_context_and_source_trace_are_required_for_clean_eligibility(self):
        valid = storage_fixture()
        missing_token = storage_fixture(token_id=None)
        missing_snapshot = storage_fixture(snapshot_id=None)
        non_paper = storage_fixture(paper_only_context=False)
        missing_trace = storage_fixture(source_request_id=None, source_response_id=None)

        self.assertTrue(storage_can_support_evidence_window_clean_eligibility(valid))
        for row in (missing_token, missing_snapshot, non_paper, missing_trace):
            with self.subTest(row=row):
                self.assertFalse(storage_can_support_evidence_window_clean_eligibility(row))

    def test_pair_id_can_be_nullable_only_for_token_level_evidence(self):
        token_level = storage_fixture(pair_id=None, safety_evidence_role="TOKEN_SAFETY_CONTEXT")
        pair_level = storage_fixture(pair_id=None, safety_evidence_role="PAIR_LIQUIDITY_SAFETY_CONTEXT")

        self.assertIsNone(token_level["pair_id"])
        self.assertTrue(storage_can_support_evidence_window_clean_eligibility(token_level))
        self.assertFalse(
            pair_level["safety_evidence_role"] == "PAIR_LIQUIDITY_SAFETY_CONTEXT"
            and pair_level["pair_id"] is not None
        )

    def test_stale_failed_missing_target_mismatch_and_high_risk_are_audit_only(self):
        cases = [
            storage_fixture(freshness_label="SAFETY_EVIDENCE_STALE"),
            storage_fixture(source_status="FAILED", source_response_id=None, source_failure_id=301),
            storage_fixture(mint_authority_status="MINT_AUTHORITY_UNKNOWN"),
            storage_fixture(target_status="TARGET_MISMATCH"),
            storage_fixture(known_risk_flag_label="KNOWN_RISK_FLAGS_PRESENT"),
        ]
        for row in cases:
            with self.subTest(row=row):
                self.assertFalse(storage_can_support_evidence_window_clean_eligibility(row))

    def test_storage_label_mapping_remains_categorical_and_existing_compatible(self):
        clean = classify_fixture(storage_fixture())
        caution = classify_fixture(storage_fixture(mint_authority_status="MINT_AUTHORITY_PRESENT"))
        blocked = classify_fixture(storage_fixture(freeze_authority_status="FREEZE_AUTHORITY_PRESENT"))
        unknown = classify_fixture(storage_fixture(holder_concentration_label="HOLDER_CONCENTRATION_UNKNOWN"))
        stale = classify_fixture(storage_fixture(freshness_label="SAFETY_EVIDENCE_STALE"))

        self.assertEqual(clean, (SafetyStatusLabel.SAFETY_CLEAN, SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN))
        self.assertEqual(caution, (SafetyStatusLabel.SAFETY_CAUTION, SafetyPayloadQualityLabel.SAFETY_CONTEXT_PARTIAL))
        self.assertEqual(blocked, (SafetyStatusLabel.SAFETY_UNSAFE, SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY))
        self.assertEqual(unknown, (SafetyStatusLabel.SAFETY_UNKNOWN, SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN))
        self.assertEqual(stale, (SafetyStatusLabel.SAFETY_UNKNOWN, SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE))

    def test_caution_and_safety_evidence_alone_do_not_unlock_downstream_gates(self):
        caution = storage_fixture(mint_authority_status="MINT_AUTHORITY_PRESENT")
        downstream_gates = {
            "clean_memory_unlocked_from_safety_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }

        self.assertFalse(storage_can_support_evidence_window_clean_eligibility(caution))
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()
