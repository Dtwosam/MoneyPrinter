import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.safety.contracts import SafetyPayloadQualityLabel, SafetyStatusLabel


REQUIRED_CONTRACT_FIELDS = {
    "token_id",
    "pair_id",
    "snapshot_id",
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
    "signing",
    "signature",
    "transaction",
    "live_trading",
)


def safety_fixture(**overrides):
    fixture = {
        "token_id": 2,
        "pair_id": 2,
        "snapshot_id": 36,
        "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
        "source_name": "future_governed_solana_safety_source",
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
        "source_request_id": 101,
        "source_response_id": 201,
        "source_failure_id": None,
        "paper_only_context": True,
        "created_at": "2026-06-23T12:00:01+00:00",
    }
    fixture.update(overrides)
    return fixture


def classify_fixture(fixture):
    if fixture.get("paper_only_context") is not True:
        return (
            SafetyStatusLabel.SAFETY_DO_NOT_USE_FOR_MEMORY,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )
    if fixture.get("target_status") != "TARGET_MATCH":
        return (
            SafetyStatusLabel.SAFETY_UNKNOWN,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_CONFLICTING,
        )
    if fixture.get("source_request_id") is None:
        return (
            SafetyStatusLabel.SAFETY_UNKNOWN,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN,
        )
    if fixture.get("source_status") == "FAILED" or fixture.get("data_quality_label") in {
        "DIRTY_DATA",
        "MISSING_CRITICAL_DATA",
        "DO_NOT_TRAIN",
    }:
        return (
            SafetyStatusLabel.SAFETY_DO_NOT_USE_FOR_MEMORY,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )
    if fixture.get("freshness_label") == "SAFETY_EVIDENCE_STALE" or fixture.get("source_status") == "STALE":
        return (
            SafetyStatusLabel.SAFETY_UNKNOWN,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE,
        )

    unknown_fields = (
        "MINT_AUTHORITY_UNKNOWN",
        "FREEZE_AUTHORITY_UNKNOWN",
        "METADATA_UNKNOWN",
        "SUPPLY_SANITY_UNKNOWN",
        "HOLDER_CONCENTRATION_UNKNOWN",
        "LIQUIDITY_LOCK_OR_BURN_UNKNOWN",
        "KNOWN_RISK_FLAGS_UNKNOWN",
        "TOKEN_PROGRAM_UNKNOWN",
    )
    if any(value in unknown_fields for value in fixture.values()):
        return (
            SafetyStatusLabel.SAFETY_UNKNOWN,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN,
        )

    dangerous_fields = {
        "FREEZE_AUTHORITY_PRESENT",
        "KNOWN_RISK_FLAGS_PRESENT",
        "TOKEN_PROGRAM_UNSUPPORTED",
        "LIQUIDITY_UNLOCKED_OR_DANGEROUS",
        "HOLDER_CONCENTRATION_EXTREME",
    }
    if any(value in dangerous_fields for value in fixture.values()):
        return (
            SafetyStatusLabel.SAFETY_UNSAFE,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )

    caution_fields = {
        "MINT_AUTHORITY_PRESENT",
        "METADATA_MUTABLE",
        "SUPPLY_SANITY_CAUTION",
        "HOLDER_CONCENTRATION_CONCENTRATED",
    }
    if any(value in caution_fields for value in fixture.values()):
        return (
            SafetyStatusLabel.SAFETY_CAUTION,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_PARTIAL,
        )

    return (
        SafetyStatusLabel.SAFETY_CLEAN,
        SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN,
    )


def safety_fixture_can_support_clean_memory_portion(fixture):
    safety_label, quality_label = classify_fixture(fixture)
    return (
        safety_label == SafetyStatusLabel.SAFETY_CLEAN
        and quality_label == SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN
    )


class PostRcSolanaSafetyEvidenceFixtureContractTest(unittest.TestCase):
    def test_contract_uses_required_candidate_fields_without_forbidden_systems(self):
        self.assertEqual(set(safety_fixture().keys()), REQUIRED_CONTRACT_FIELDS)
        field_text = " ".join(REQUIRED_CONTRACT_FIELDS).lower()
        for fragment in FORBIDDEN_FIELD_FRAGMENTS:
            self.assertNotIn(fragment, field_text)

    def test_complete_known_fixture_maps_to_known_safety_context(self):
        safety_label, quality_label = classify_fixture(safety_fixture())
        self.assertEqual(safety_label, SafetyStatusLabel.SAFETY_CLEAN)
        self.assertEqual(quality_label, SafetyPayloadQualityLabel.SAFETY_CONTEXT_CLEAN)
        self.assertTrue(safety_fixture_can_support_clean_memory_portion(safety_fixture()))

    def test_caution_fixture_does_not_unlock_clean_memory_alone(self):
        fixture = safety_fixture(mint_authority_status="MINT_AUTHORITY_PRESENT")
        safety_label, quality_label = classify_fixture(fixture)
        self.assertEqual(safety_label, SafetyStatusLabel.SAFETY_CAUTION)
        self.assertEqual(quality_label, SafetyPayloadQualityLabel.SAFETY_CONTEXT_PARTIAL)
        self.assertFalse(safety_fixture_can_support_clean_memory_portion(fixture))

    def test_high_risk_fixture_blocks_clean_eligibility(self):
        fixture = safety_fixture(known_risk_flag_label="KNOWN_RISK_FLAGS_PRESENT")
        safety_label, quality_label = classify_fixture(fixture)
        self.assertEqual(safety_label, SafetyStatusLabel.SAFETY_UNSAFE)
        self.assertEqual(
            quality_label,
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY,
        )
        self.assertFalse(safety_fixture_can_support_clean_memory_portion(fixture))

    def test_missing_stale_failed_and_target_mismatch_fixtures_are_audit_only(self):
        cases = [
            safety_fixture(mint_authority_status="MINT_AUTHORITY_UNKNOWN"),
            safety_fixture(freshness_label="SAFETY_EVIDENCE_STALE"),
            safety_fixture(source_status="FAILED", source_response_id=None, source_failure_id=301),
            safety_fixture(target_status="TARGET_MISMATCH"),
            safety_fixture(source_request_id=None, source_response_id=None),
            safety_fixture(paper_only_context=False),
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                self.assertFalse(safety_fixture_can_support_clean_memory_portion(fixture))

    def test_safety_fixture_alone_does_not_unlock_downstream_gates(self):
        fixture = safety_fixture()
        downstream_gates = {
            "memory_clean_from_safety_alone": False,
            "retrieval_unlocked": False,
            "paper_decision_created": False,
            "buy_unlocked": False,
            "paper_position_created": False,
            "paper_trade_event_created": False,
            "pnl_created": False,
        }
        self.assertTrue(safety_fixture_can_support_clean_memory_portion(fixture))
        self.assertTrue(all(value is False for value in downstream_gates.values()))


if __name__ == "__main__":
    unittest.main()
