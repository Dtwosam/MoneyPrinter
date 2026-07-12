"""V2-2AK — T3 Solana RPC Token-Age Implementation Fixture Proof.

Fixture-only proof covering:
  A. Adapter contract validates; disabled by default; governor context enforced
  B. SPL Token success path: tier T3, all evidence fields set
  C. Token-2022 success path: tier T3, token_program = token_2022
  D. All 14 failure types: each leaves token_created_at/age_seconds/tier unset
  E. All 15 t3_* provenance fields survive to extract_candidate_metadata()
  F. normalize_candidate("solana_rpc", ...) stamps tier T3 correctly
  G. Block-time fallback: block_time_source "getBlockTime" vs "getTransaction"
  H. Prohibited age fallbacks: pair_age/captured_at never become token_created_at
  I. T2 and OBSERVED_LIVE_LAUNCH tier derivation completely unchanged
  J. A3 does not fire when T3 fails (token_age_seconds remains None)
  K. Registry has mint_creation_time_reference; contract passes governor check

Hard rules verified:
  - token_created_at never set from captured_at, pair age, or migration time
  - token_age_seconds never computed from pair age or OBSERVED_LIVE_LAUNCH
  - A3 requires token_age_seconds is not None (unchanged)
  - T2 is unchanged; OBSERVED_LIVE_LAUNCH is unchanged
  - No live RPC calls; no DB mutation; no paper decisions

No live source calls, no DB mutation, no memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, scheduler, or runtime.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import datetime, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.discovery.parser import normalize_candidate
from printer_v1.discovery.selection_batch import (
    BUCKET_A3,
    assign_bucket,
    extract_candidate_metadata,
    _METADATA_FIELDS,
)
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    SourceAdapterContext,
    SourceRequest,
    SourceRequestRecord,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)
from printer_v1.sources.governor import SourceRequestDecision
from printer_v1.sources.registry import SOURCE_REGISTRY
from printer_v1.sources.solana_rpc_token_age import (
    SOLANA_RPC_SOURCE_NAME,
    SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
    SolanaRpcTokenAgeAdapter,
    SolanaRpcTokenAgeAdapterMetadata,
    _T3_MAX_BLOCK_TIME_CALLS,
    _T3_FAIL_PROVENANCE_FIELDS,
    _SPL_TOKEN_MINT_SIZE,
    _SPL_TOKEN_ACCOUNT_SIZE,
    _SPL_MINT_IS_INITIALIZED_OFFSET,
    _TOKEN_2022_ACCOUNT_TYPE_MINT,
    _TOKEN_2022_ACCOUNT_TYPE_OFFSET,
    _TOKEN_2022_EXTENSION_DATA_START,
    _decode_spl_token_base_mint_state,
    _decode_token_2022_mint_state,
    build_solana_rpc_token_age_adapter,
    build_solana_rpc_token_age_adapter_contract,
    fixture_t3_failure_transport,
    fixture_t3_success_transport,
    normalize_solana_rpc_token_age_response,
    redacted_rpc_host,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_NOW_ISO = "2026-07-11T12:00:00+00:00"

# One hour before capture → 3600s age
_T3_CREATED_ISO = "2026-07-11T11:00:00+00:00"
_T3_AGE_SECONDS = 3600.0
_T3_BLOCK_TIME_RAW = int(datetime(2026, 7, 11, 11, 0, 0, tzinfo=timezone.utc).timestamp())

_SPL_TOKEN_MINT = "TokenMintSPL111111111111111111111111111111"
_TOKEN_2022_MINT = "TokenMint2022222222222222222222222222222222"

_T3_SPL_SUCCESS_PAYLOAD = {
    "t3_status": "success",
    "token_mint": _SPL_TOKEN_MINT,
    "captured_at": _FIXED_NOW_ISO,
    "token_created_at": _T3_CREATED_ISO,
    "token_age_seconds": _T3_AGE_SECONDS,
    "token_age_evidence_tier": "T3",
    "t3_requested_mint": _SPL_TOKEN_MINT,
    "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
    "t3_rpc_methods_attempted": ["getAccountInfo", "getSignaturesForAddress", "getTransaction"],
    "t3_request_ids": [1, 2, 3],
    "t3_pages_fetched": 1,
    "t3_signatures_inspected": 1,
    "t3_accepted_signature": "5abc1234sig",
    "t3_accepted_slot": 12345678,
    "t3_block_time_raw": _T3_BLOCK_TIME_RAW,
    "t3_block_time_source": "getTransaction",
    "t3_instruction_type": "initializeMint",
    "t3_token_program": "spl_token",
    "t3_derived_token_created_at": _T3_CREATED_ISO,
    "t3_derived_token_age_seconds": _T3_AGE_SECONDS,
    "t3_captured_at": _FIXED_NOW_ISO,
    "t3_commitment": "finalized",
    "t3_finality_status": "finalized",
}

_T3_TOKEN_2022_SUCCESS_PAYLOAD = {
    **_T3_SPL_SUCCESS_PAYLOAD,
    "token_mint": _TOKEN_2022_MINT,
    "t3_requested_mint": _TOKEN_2022_MINT,
    "t3_instruction_type": "initializeMint2",
    "t3_token_program": "token_2022",
}

_ALL_T3_PROVENANCE_FIELDS = (
    "t3_requested_mint",
    "t3_rpc_host_redacted",
    "t3_rpc_methods_attempted",
    "t3_request_ids",
    "t3_pages_fetched",
    "t3_signatures_inspected",
    "t3_accepted_signature",
    "t3_accepted_slot",
    "t3_block_time_raw",
    "t3_block_time_source",
    "t3_instruction_type",
    "t3_token_program",
    "t3_derived_token_created_at",
    "t3_derived_token_age_seconds",
    "t3_captured_at",
    "t3_commitment",
    "t3_finality_status",
)


def _make_t3_context(request_kind: str = SOLANA_RPC_TOKEN_AGE_REQUEST_KIND) -> SourceAdapterContext:
    request = SourceRequest(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        requested_at=_FIXED_NOW_ISO,
    )
    decision = SourceRequestDecision(
        allowed=True,
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        reason="fixture_approved",
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )
    record = SourceRequestRecord(
        id=1,
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=request_kind,
        requested_at=_FIXED_NOW_ISO,
        request_key=None,
        tracking_priority=None,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )
    return SourceAdapterContext(
        request=request,
        request_record=record,
        decision=decision,
        governor_approved=True,
    )


def _make_ungoverned_context() -> SourceAdapterContext:
    request = SourceRequest(
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        requested_at=_FIXED_NOW_ISO,
    )
    decision = SourceRequestDecision(
        allowed=False,
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        reason="fixture_denied",
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
    )
    record = SourceRequestRecord(
        id=2,
        source_name=SOLANA_RPC_SOURCE_NAME,
        request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        requested_at=_FIXED_NOW_ISO,
        request_key=None,
        tracking_priority=None,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
    )
    return SourceAdapterContext(
        request=request,
        request_record=record,
        decision=decision,
        governor_approved=False,
    )


def _make_enabled_adapter_with_payload(payload: dict) -> SolanaRpcTokenAgeAdapter:
    return build_solana_rpc_token_age_adapter(
        enabled=True,
        fixture_transport=fixture_t3_success_transport(payload),
    )


def _make_enabled_failing_adapter(failure_type: str, msg: str = "fixture") -> SolanaRpcTokenAgeAdapter:
    return build_solana_rpc_token_age_adapter(
        enabled=True,
        fixture_transport=fixture_t3_failure_transport(failure_type, msg),
    )


# ---------------------------------------------------------------------------
# Class 1: Contract and governance
# ---------------------------------------------------------------------------

class TestT3AdapterContractAndGovernance(unittest.TestCase):

    def test_registry_has_mint_creation_time_reference(self):
        kinds = SOURCE_REGISTRY["solana_rpc"].allowed_request_kinds
        self.assertIn("mint_creation_time_reference", kinds)

    def test_contract_validates_against_source_governor(self):
        contract = build_solana_rpc_token_age_adapter_contract()
        self.assertTrue(validate_source_adapter_contract(contract))
        self.assertFalse(contract.enabled_by_default)
        self.assertTrue(contract.fixture_only)
        self.assertFalse(contract.supports_network_execution)
        self.assertTrue(contract.requires_governor_context)

    def test_adapter_disabled_by_default(self):
        adapter = build_solana_rpc_token_age_adapter()
        self.assertFalse(adapter.enabled)
        ctx = _make_t3_context()
        with self.assertRaises(PermissionError):
            adapter.execute(ctx)

    def test_adapter_requires_explicit_transport(self):
        adapter = build_solana_rpc_token_age_adapter(enabled=True)
        ctx = _make_t3_context()
        with self.assertRaises(PermissionError):
            adapter.execute(ctx)

    def test_adapter_rejects_ungoverned_context(self):
        adapter = _make_enabled_adapter_with_payload(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_ungoverned_context()
        with self.assertRaises(PermissionError):
            adapter.execute(ctx)

    def test_adapter_rejects_wrong_execution_path(self):
        from dataclasses import replace
        ctx = _make_t3_context()
        bad_ctx = SourceAdapterContext(
            request=ctx.request,
            request_record=ctx.request_record,
            decision=ctx.decision,
            governor_approved=True,
            execution_path="wrong_path",
        )
        adapter = _make_enabled_adapter_with_payload(_T3_SPL_SUCCESS_PAYLOAD)
        with self.assertRaises(PermissionError):
            adapter.execute(bad_ctx)

    def test_adapter_rejects_wrong_request_kind(self):
        adapter = _make_enabled_adapter_with_payload(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_t3_context(request_kind="holder_concentration_reference")
        with self.assertRaises(ValueError):
            adapter.execute(ctx)

    def test_adapter_contract_includes_all_solana_rpc_kinds(self):
        contract = build_solana_rpc_token_age_adapter_contract()
        for kind in ("onchain_reference", "mint_account_reference",
                     "holder_concentration_reference", "mint_creation_time_reference"):
            self.assertIn(kind, contract.allowed_request_kinds)


# ---------------------------------------------------------------------------
# Class 2: SPL Token success path
# ---------------------------------------------------------------------------

class TestT3NormalizerSplTokenSuccess(unittest.TestCase):

    def setUp(self):
        self.result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD,
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )

    def test_source_status_is_complete(self):
        self.assertEqual(self.result.source_status, SourceStatus.COMPLETE)

    def test_data_quality_is_clean(self):
        self.assertEqual(self.result.data_quality_label, DataQualityLabel.CLEAN_DATA)

    def test_token_created_at_is_set(self):
        self.assertEqual(self.result.normalized_payload["token_created_at"], _T3_CREATED_ISO)

    def test_token_age_seconds_is_set(self):
        self.assertEqual(self.result.normalized_payload["token_age_seconds"], _T3_AGE_SECONDS)

    def test_tier_is_t3(self):
        self.assertEqual(self.result.normalized_payload["token_age_evidence_tier"], "T3")

    def test_instruction_type_is_initialize_mint(self):
        self.assertEqual(self.result.normalized_payload["t3_instruction_type"], "initializeMint")

    def test_token_program_is_spl_token(self):
        self.assertEqual(self.result.normalized_payload["t3_token_program"], "spl_token")

    def test_rpc_methods_recorded(self):
        methods = self.result.normalized_payload["t3_rpc_methods_attempted"]
        self.assertIn("getAccountInfo", methods)
        self.assertIn("getSignaturesForAddress", methods)
        self.assertIn("getTransaction", methods)

    def test_adapter_executes_and_returns_complete_result(self):
        adapter = _make_enabled_adapter_with_payload(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_t3_context()
        result = adapter.execute(ctx)
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(result.normalized_payload["token_age_evidence_tier"], "T3")
        self.assertEqual(adapter.call_count, 1)


# ---------------------------------------------------------------------------
# Class 3: Token-2022 success path
# ---------------------------------------------------------------------------

class TestT3NormalizerToken2022Success(unittest.TestCase):

    def setUp(self):
        self.result = normalize_solana_rpc_token_age_response(
            _T3_TOKEN_2022_SUCCESS_PAYLOAD,
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )

    def test_source_status_is_complete(self):
        self.assertEqual(self.result.source_status, SourceStatus.COMPLETE)

    def test_tier_is_t3(self):
        self.assertEqual(self.result.normalized_payload["token_age_evidence_tier"], "T3")

    def test_token_created_at_is_set(self):
        self.assertEqual(self.result.normalized_payload["token_created_at"], _T3_CREATED_ISO)

    def test_instruction_type_is_initialize_mint2(self):
        self.assertEqual(self.result.normalized_payload["t3_instruction_type"], "initializeMint2")

    def test_token_program_is_token_2022(self):
        self.assertEqual(self.result.normalized_payload["t3_token_program"], "token_2022")

    def test_requested_mint_matches(self):
        self.assertEqual(
            self.result.normalized_payload["t3_requested_mint"], _TOKEN_2022_MINT
        )


# ---------------------------------------------------------------------------
# Class 4: Failure cases — fail-closed, no evidence set
# ---------------------------------------------------------------------------

class TestT3FailureCases(unittest.TestCase):

    def _assert_fail_closed(self, failure_type: str, message: str = "fixture failure") -> None:
        result = normalize_solana_rpc_token_age_response(
            {"fixture_status": "failure", "failure_type": failure_type, "failure_message": message},
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.data_quality_label, DataQualityLabel.MISSING_CRITICAL_DATA)
        self.assertEqual(result.failure_type, failure_type)
        self.assertIsNone(result.normalized_payload.get("token_created_at"))
        self.assertIsNone(result.normalized_payload.get("token_age_seconds"))
        self.assertIsNone(result.normalized_payload.get("token_age_evidence_tier"))

    def test_account_not_found_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_account_not_found")

    def test_not_a_mint_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_not_a_mint")

    def test_rate_limited_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_rate_limited")

    def test_transport_error_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_transport_error")

    def test_no_signatures_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_no_signatures")

    def test_page_cap_exhausted_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_page_cap_exhausted")

    def test_history_pruned_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_history_pruned")

    def test_transaction_not_found_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_transaction_not_found")

    def test_no_init_instruction_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_no_init_instruction")

    def test_mint_mismatch_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_mint_mismatch")

    def test_null_block_time_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_null_block_time")

    def test_future_block_time_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_future_block_time")

    def test_budget_exhausted_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_budget_exhausted")

    def test_malformed_response_fails_closed(self):
        self._assert_fail_closed("solana_rpc_token_age_malformed_response")

    def test_missing_t3_status_field_fails_closed(self):
        # Payload has neither t3_status=success nor fixture_status=failure
        result = normalize_solana_rpc_token_age_response(
            {"some_field": "some_value"},
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertIsNone(result.normalized_payload.get("token_created_at"))

    def test_wrong_request_kind_fails_closed(self):
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD,
            request_kind="holder_concentration_reference",
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)

    def test_adapter_with_failure_transport_returns_failed_result(self):
        adapter = _make_enabled_failing_adapter(
            "solana_rpc_token_age_rate_limited", "HTTP 429"
        )
        ctx = _make_t3_context()
        result = adapter.execute(ctx)
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.failure_type, "solana_rpc_token_age_rate_limited")

    def test_success_payload_missing_token_created_at_fails_closed(self):
        bad = {**_T3_SPL_SUCCESS_PAYLOAD}
        del bad["token_created_at"]
        result = normalize_solana_rpc_token_age_response(
            bad, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)

    def test_success_payload_negative_age_fails_closed(self):
        bad = {**_T3_SPL_SUCCESS_PAYLOAD, "token_age_seconds": -1.0}
        result = normalize_solana_rpc_token_age_response(
            bad, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)


# ---------------------------------------------------------------------------
# Class 5: Provenance persistence — all 15 t3_* fields survive to metadata
# ---------------------------------------------------------------------------

class TestT3ProvenancePersistence(unittest.TestCase):

    def _build_enriched_candidate(self) -> dict:
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD,
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        candidate: dict = {
            "token_mint": _SPL_TOKEN_MINT,
            "pair_address": "SomePair111",
            "chain": "solana",
            "source_name": SOLANA_RPC_SOURCE_NAME,
            "captured_at": _FIXED_NOW_ISO,
            "token_created_at": None,
            "token_age_seconds": None,
            "token_age_evidence_tier": None,
        }
        # Merge T3 evidence into candidate (post-normalization enrichment step)
        for key, value in result.normalized_payload.items():
            candidate[key] = value
        return candidate

    def test_all_15_t3_provenance_fields_in_metadata_fields_tuple(self):
        for field in _ALL_T3_PROVENANCE_FIELDS:
            self.assertIn(field, _METADATA_FIELDS, f"{field!r} missing from _METADATA_FIELDS")

    def test_all_15_t3_provenance_fields_survive_extract_candidate_metadata(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        for field in _ALL_T3_PROVENANCE_FIELDS:
            self.assertIn(field, meta, f"{field!r} missing from candidate metadata")

    def test_t3_requested_mint_value_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_requested_mint"], _SPL_TOKEN_MINT)

    def test_t3_accepted_signature_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_accepted_signature"], "5abc1234sig")

    def test_t3_block_time_raw_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_block_time_raw"], _T3_BLOCK_TIME_RAW)

    def test_t3_instruction_type_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_instruction_type"], "initializeMint")

    def test_t3_token_program_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_token_program"], "spl_token")

    def test_t3_rpc_methods_attempted_persists(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertIn("getTransaction", meta["t3_rpc_methods_attempted"])

    def test_t3_derived_fields_match_primary_evidence(self):
        candidate = self._build_enriched_candidate()
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta["t3_derived_token_created_at"], _T3_CREATED_ISO)
        self.assertEqual(meta["t3_derived_token_age_seconds"], _T3_AGE_SECONDS)

    def test_t3_fields_absent_for_failed_t3_candidate(self):
        result = normalize_solana_rpc_token_age_response(
            {"fixture_status": "failure", "failure_type": "solana_rpc_token_age_no_init_instruction",
             "failure_message": "no init"},
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        # Failure result has no normalized_payload with t3_* fields
        for field in _ALL_T3_PROVENANCE_FIELDS:
            self.assertIsNone(result.normalized_payload.get(field))


# ---------------------------------------------------------------------------
# Class 6: Parser tier derivation for T3
# ---------------------------------------------------------------------------

class TestT3ParserTierDerivation(unittest.TestCase):

    def _t3_payload(self, *, created_at: str | None = _T3_CREATED_ISO) -> dict:
        return {
            "token_mint": _SPL_TOKEN_MINT,
            "pair_address": "TestPair789",
            "chain": "solana",
            "source_name": SOLANA_RPC_SOURCE_NAME,
            "captured_at": _FIXED_NOW_ISO,
            "token_created_at": created_at,
            "request_kind": SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        }

    def test_normalize_candidate_sets_t3_tier(self):
        result = normalize_candidate(
            SOLANA_RPC_SOURCE_NAME,
            self._t3_payload(),
            _FIXED_NOW,
        )
        self.assertEqual(result["token_age_evidence_tier"], "T3")

    def test_normalize_candidate_sets_token_age_seconds(self):
        result = normalize_candidate(
            SOLANA_RPC_SOURCE_NAME,
            self._t3_payload(),
            _FIXED_NOW,
        )
        self.assertAlmostEqual(result["token_age_seconds"], _T3_AGE_SECONDS, places=0)

    def test_normalize_candidate_sets_token_created_at(self):
        result = normalize_candidate(
            SOLANA_RPC_SOURCE_NAME,
            self._t3_payload(),
            _FIXED_NOW,
        )
        self.assertIsNotNone(result["token_created_at"])

    def test_normalize_candidate_returns_none_tier_without_created_at(self):
        result = normalize_candidate(
            SOLANA_RPC_SOURCE_NAME,
            self._t3_payload(created_at=None),
            _FIXED_NOW,
        )
        self.assertIsNone(result["token_age_evidence_tier"])

    def test_normalize_candidate_returns_none_tier_without_request_kind(self):
        payload = {**self._t3_payload()}
        del payload["request_kind"]
        result = normalize_candidate(SOLANA_RPC_SOURCE_NAME, payload, _FIXED_NOW)
        self.assertIsNone(result["token_age_evidence_tier"])

    def test_normalize_candidate_returns_none_tier_for_wrong_request_kind(self):
        payload = {**self._t3_payload(), "request_kind": "holder_concentration_reference"}
        result = normalize_candidate(SOLANA_RPC_SOURCE_NAME, payload, _FIXED_NOW)
        self.assertIsNone(result["token_age_evidence_tier"])

    def test_normalize_candidate_solana_rpc_other_source_no_t3_tier(self):
        payload = {**self._t3_payload(), "request_kind": SOLANA_RPC_TOKEN_AGE_REQUEST_KIND}
        result = normalize_candidate("geckoterminal", payload, _FIXED_NOW)
        self.assertIsNone(result["token_age_evidence_tier"])


# ---------------------------------------------------------------------------
# Class 7: Block-time fallback
# ---------------------------------------------------------------------------

class TestT3BlockTimeFallback(unittest.TestCase):

    def test_block_time_source_from_get_transaction(self):
        payload = {**_T3_SPL_SUCCESS_PAYLOAD, "t3_block_time_source": "getTransaction"}
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.normalized_payload["t3_block_time_source"], "getTransaction")
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)

    def test_block_time_source_from_get_block_time_fallback(self):
        payload = {
            **_T3_SPL_SUCCESS_PAYLOAD,
            "t3_block_time_source": "getBlockTime",
            "t3_rpc_methods_attempted": [
                "getAccountInfo", "getSignaturesForAddress", "getTransaction", "getBlockTime"
            ],
            "t3_request_ids": [1, 2, 3, 4],
        }
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.normalized_payload["t3_block_time_source"], "getBlockTime")
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertIn("getBlockTime", result.normalized_payload["t3_rpc_methods_attempted"])

    def test_null_block_time_without_fallback_fails_closed(self):
        result = normalize_solana_rpc_token_age_response(
            {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_null_block_time",
                "failure_message": "blockTime is null and getBlockTime fallback failed",
            },
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertIsNone(result.normalized_payload.get("token_created_at"))

    def test_future_block_time_fails_closed(self):
        result = normalize_solana_rpc_token_age_response(
            {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_future_block_time",
                "failure_message": "block time is in the future",
            },
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertIsNone(result.normalized_payload.get("token_age_seconds"))


# ---------------------------------------------------------------------------
# Class 8: Prohibited age fallbacks
# ---------------------------------------------------------------------------

class TestT3BoundaryViolations(unittest.TestCase):

    def test_pair_age_never_becomes_token_created_at(self):
        # Even if the payload has pair_created_at, T3 should only use token_created_at
        payload = {
            **_T3_SPL_SUCCESS_PAYLOAD,
            "pair_created_at": "2026-07-01T00:00:00+00:00",  # older pair
        }
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        # token_created_at must be from T3 evidence, NOT pair_created_at
        self.assertEqual(result.normalized_payload["token_created_at"], _T3_CREATED_ISO)
        self.assertNotEqual(result.normalized_payload["token_created_at"], "2026-07-01T00:00:00+00:00")

    def test_captured_at_never_becomes_token_created_at(self):
        # captured_at is collection time only; T3 must NOT use it as token_created_at
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertNotEqual(
            result.normalized_payload.get("token_created_at"),
            _FIXED_NOW_ISO,  # captured_at
        )

    def test_observed_live_launch_not_in_t3_payload(self):
        # T3 evidence must not include live_observed_launch semantics
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertIsNone(result.normalized_payload.get("live_observed_launch"))

    def test_t3_failure_never_sets_token_created_at_from_captured_at(self):
        # When T3 fails, no token_created_at should be set at all
        result = normalize_solana_rpc_token_age_response(
            {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_no_init_instruction",
                "failure_message": "no init",
                "captured_at": _FIXED_NOW_ISO,  # must NOT become token_created_at
            },
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertIsNone(result.normalized_payload.get("token_created_at"))
        self.assertIsNone(result.normalized_payload.get("token_age_seconds"))

    def test_migration_time_not_used_as_token_creation_time(self):
        # T3 adapter normalizer should ignore migration_time field entirely
        payload = {
            **_T3_SPL_SUCCESS_PAYLOAD,
            "migration_time": "2026-06-01T00:00:00+00:00",
        }
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.normalized_payload["token_created_at"], _T3_CREATED_ISO)


# ---------------------------------------------------------------------------
# Class 9: T2 and OBSERVED_LIVE_LAUNCH unchanged
# ---------------------------------------------------------------------------

class TestT2AndObservedLiveLaunchUnchanged(unittest.TestCase):

    def _t2_payload(self) -> dict:
        return {
            "token_mint": "PumpTokenMint111",
            "pair_address": "PumpPair222",
            "chain": "solana",
            "source_name": "pumpportal",
            "captured_at": _FIXED_NOW_ISO,
            "tokenCreatedAt": _T3_CREATED_ISO,
            "request_kind": "pumpfun_launch_stream",
        }

    def _obs_live_payload(self) -> dict:
        return {
            "token_mint": "PumpTokenMint333",
            "pair_address": "PumpPair444",
            "chain": "solana",
            "source_name": "pumpportal",
            "captured_at": _FIXED_NOW_ISO,
            "live_observed_launch": True,
            "request_kind": "pumpfun_launch_stream",
        }

    def test_t2_tier_still_set_for_pumpportal_with_timestamp(self):
        result = normalize_candidate("pumpportal", self._t2_payload(), _FIXED_NOW)
        self.assertEqual(result["token_age_evidence_tier"], "T2")
        self.assertIsNotNone(result["token_created_at"])
        self.assertIsNotNone(result["token_age_seconds"])

    def test_observed_live_launch_tier_still_set_for_pumpportal_no_timestamp(self):
        result = normalize_candidate("pumpportal", self._obs_live_payload(), _FIXED_NOW)
        self.assertEqual(result["token_age_evidence_tier"], "OBSERVED_LIVE_LAUNCH")
        self.assertIsNone(result["token_created_at"])
        self.assertIsNone(result["token_age_seconds"])

    def test_t2_takes_precedence_over_obs_live_for_pumpportal(self):
        # Event with both explicit timestamp AND live_observed_launch → T2 wins
        payload = {**self._t2_payload(), "live_observed_launch": True}
        result = normalize_candidate("pumpportal", payload, _FIXED_NOW)
        self.assertEqual(result["token_age_evidence_tier"], "T2")

    def test_geckoterminal_source_still_returns_none_tier(self):
        payload = {
            "token_mint": "GeckoMint555",
            "pair_address": "GeckoPair666",
            "chain": "solana",
            "captured_at": _FIXED_NOW_ISO,
        }
        result = normalize_candidate("geckoterminal", payload, _FIXED_NOW)
        self.assertIsNone(result["token_age_evidence_tier"])

    def test_pumpportal_migration_still_returns_none_tier(self):
        payload = {
            "token_mint": "PumpTokenMint777",
            "pair_address": "PumpPair888",
            "chain": "solana",
            "source_name": "pumpportal",
            "captured_at": _FIXED_NOW_ISO,
            "request_kind": "pumpfun_migration_stream",
        }
        result = normalize_candidate("pumpportal", payload, _FIXED_NOW)
        self.assertIsNone(result["token_age_evidence_tier"])


# ---------------------------------------------------------------------------
# Class 10: A3 locked on failed T3
# ---------------------------------------------------------------------------

class TestA3LockedOnFailedT3(unittest.TestCase):

    def _candidate_no_age(self, **overrides) -> dict:
        base = {
            "token_mint": _SPL_TOKEN_MINT,
            "pair_address": "SomePair999",
            "chain": "solana",
            "source_name": SOLANA_RPC_SOURCE_NAME,
            "captured_at": _FIXED_NOW_ISO,
            "token_created_at": None,
            "token_age_seconds": None,
            "price_change_1h": -50.0,
            "price_change_5m": None,
            "price_change_15m": None,
            "price_change_24h": None,
            "volume_1h": 10000.0,
            "volume_5m": 1000.0,
            "volume_15m": 2000.0,
            "volume_24h": 50000.0,
            "txns_5m": 10,
            "txns_1h": 50,
            "liquidity_usd": 5000.0,
            "market_cap": 100000.0,
            "fdv": 200000.0,
            "price_usd": 0.01,
            "token_age_evidence_tier": None,
        }
        base.update(overrides)
        return base

    def test_a3_does_not_fire_when_token_age_seconds_is_none(self):
        candidate = self._candidate_no_age()
        bucket, reason = assign_bucket(candidate)
        self.assertNotEqual(bucket, BUCKET_A3)

    def test_a3_does_not_fire_after_t3_failure(self):
        # Simulate T3 adapter returned failure: token_age_seconds remains None
        result = normalize_solana_rpc_token_age_response(
            {"fixture_status": "failure", "failure_type": "solana_rpc_token_age_rate_limited",
             "failure_message": "429"},
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertIsNone(result.normalized_payload.get("token_age_seconds"))

        # Build candidate without T3 evidence (failed path)
        candidate = self._candidate_no_age()
        bucket, reason = assign_bucket(candidate)
        self.assertNotEqual(bucket, BUCKET_A3)

    def test_a3_fires_when_t3_evidence_present_and_conditions_met(self):
        # Confirm A3 WOULD fire if T3 success produced valid evidence and conditions pass
        candidate = self._candidate_no_age(
            token_age_seconds=7200.0,  # 2 hours old
            token_created_at=_T3_CREATED_ISO,
            price_change_1h=-15.0,  # negative → A3 condition
        )
        bucket, reason = assign_bucket(candidate)
        self.assertEqual(bucket, BUCKET_A3)

    def test_t3_evidence_tier_alone_does_not_unlock_a3(self):
        # OBSERVED_LIVE_LAUNCH tier set, but token_age_seconds still None → A3 locked
        candidate = self._candidate_no_age(
            token_age_evidence_tier="OBSERVED_LIVE_LAUNCH",
            token_age_seconds=None,
        )
        bucket, reason = assign_bucket(candidate)
        self.assertNotEqual(bucket, BUCKET_A3)


# ---------------------------------------------------------------------------
# Class 11: Fixture transport helpers and misc
# ---------------------------------------------------------------------------

class TestT3FixtureTransportHelpers(unittest.TestCase):

    def test_fixture_success_transport_returns_payload(self):
        transport = fixture_t3_success_transport(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_t3_context()
        result = transport(ctx)
        self.assertEqual(result["t3_status"], "success")
        self.assertEqual(result["token_created_at"], _T3_CREATED_ISO)

    def test_fixture_failure_transport_returns_failure_payload(self):
        transport = fixture_t3_failure_transport(
            "solana_rpc_token_age_rate_limited", "HTTP 429"
        )
        ctx = _make_t3_context()
        result = transport(ctx)
        self.assertEqual(result["fixture_status"], "failure")
        self.assertEqual(result["failure_type"], "solana_rpc_token_age_rate_limited")

    def test_fixture_transport_payload_is_immutable_proxy(self):
        transport = fixture_t3_success_transport(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_t3_context()
        result = transport(ctx)
        with self.assertRaises((TypeError, AttributeError)):
            result["injected_field"] = "evil"  # type: ignore[index]

    def test_redacted_rpc_host_strips_path_and_key(self):
        host = redacted_rpc_host("https://api.mainnet-beta.solana.com/v1?apikey=secret")
        self.assertEqual(host, "api.mainnet-beta.solana.com")

    def test_redacted_rpc_host_handles_none(self):
        host = redacted_rpc_host(None)
        self.assertEqual(host, "api.mainnet-beta.solana.com")

    def test_adapter_call_count_increments(self):
        adapter = _make_enabled_adapter_with_payload(_T3_SPL_SUCCESS_PAYLOAD)
        ctx = _make_t3_context()
        self.assertEqual(adapter.call_count, 0)
        adapter.execute(ctx)
        self.assertEqual(adapter.call_count, 1)
        adapter.execute(ctx)
        self.assertEqual(adapter.call_count, 2)

    def test_paper_only_context_flag_set_in_success_payload(self):
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertTrue(result.normalized_payload.get("paper_only_context"))


# ---------------------------------------------------------------------------
# V2-2AK.2 Class 12: Live-capability adapter metadata
# ---------------------------------------------------------------------------

class TestLiveCapabilityMetadata(unittest.TestCase):
    """Verify that V2-2AK.2 repaired adapter metadata reflects live-capable intent."""

    def setUp(self):
        self.meta = SolanaRpcTokenAgeAdapterMetadata()

    def test_fixture_transport_only_is_false(self):
        # Adapter has a live transport; fixture_transport_only must be False
        self.assertFalse(self.meta.fixture_transport_only)

    def test_supports_network_execution_is_true(self):
        # Live transport defined per V2-2AJ Section 3.1
        self.assertTrue(self.meta.supports_network_execution)

    def test_enabled_by_default_is_false(self):
        # Must stay disabled until operator enables for a proof lane
        self.assertFalse(self.meta.enabled_by_default)

    def test_requires_governor_context_is_true(self):
        # All T3 calls must go through Source Governor
        self.assertTrue(self.meta.requires_governor_context)

    def test_metadata_and_contract_are_separate_objects(self):
        # The adapter contract (fixture_only=True, supports_network_execution=False)
        # must differ from the metadata object (supports_network_execution=True)
        contract = build_solana_rpc_token_age_adapter_contract()
        self.assertTrue(self.meta.supports_network_execution)
        self.assertFalse(contract.supports_network_execution)
        self.assertFalse(self.meta.fixture_transport_only)
        self.assertTrue(contract.fixture_only)

    def test_source_name_matches_constant(self):
        self.assertEqual(self.meta.source_name, SOLANA_RPC_SOURCE_NAME)

    def test_read_only_is_true(self):
        self.assertTrue(self.meta.read_only)


# ---------------------------------------------------------------------------
# V2-2AK.2 Class 13: SPL Token mint-state decoding
# ---------------------------------------------------------------------------

def _make_spl_mint_bytes(*, is_initialized: int = 1, length: int = _SPL_TOKEN_MINT_SIZE) -> bytes:
    """Return a minimal SPL Token mint byte buffer with is_initialized at offset 45."""
    buf = bytearray(length)
    if _SPL_MINT_IS_INITIALIZED_OFFSET < length:
        buf[_SPL_MINT_IS_INITIALIZED_OFFSET] = is_initialized
    return bytes(buf)


class TestSplTokenMintStateDecoding(unittest.TestCase):
    """Unit tests for _decode_spl_token_base_mint_state() — V2-2AK.2 repair."""

    def test_valid_82_byte_initialized_mint_passes(self):
        raw = _make_spl_mint_bytes(is_initialized=1)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_uninitialized_mint_byte_zero_rejected(self):
        raw = _make_spl_mint_bytes(is_initialized=0)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("not initialized", err)

    def test_uninitialized_mint_byte_nonzero_nonone_rejected(self):
        raw = _make_spl_mint_bytes(is_initialized=2)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("not initialized", err)

    def test_too_short_buffer_rejected(self):
        raw = _make_spl_mint_bytes(length=44)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("Too short", err)

    def test_empty_buffer_rejected(self):
        ok, err = _decode_spl_token_base_mint_state(b"")
        self.assertFalse(ok)
        self.assertIn("Too short", err)

    def test_81_bytes_rejected(self):
        raw = _make_spl_mint_bytes(length=81)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("Too short", err)

    def test_83_bytes_still_valid_base_decode(self):
        # Extra byte beyond 82 is acceptable for the base check (Token-2022 case)
        raw = _make_spl_mint_bytes(length=83)
        ok, err = _decode_spl_token_base_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)


# ---------------------------------------------------------------------------
# V2-2AK.2 / V2-2AL.1 Class 14: Token-2022 mint-state decoding (corrected layout)
# ---------------------------------------------------------------------------

def _make_token_2022_mint_bytes(
    *,
    is_initialized: int = 1,
    padding: bytes | None = None,
    account_type: int = _TOKEN_2022_ACCOUNT_TYPE_MINT,
    extensions: bytes = b"",
) -> bytes:
    """Return a Token-2022 extended mint buffer with the correct V2-2AL layout.

    Authoritative layout (SPL token-2022 extension/mod.rs, BASE_ACCOUNT_LENGTH = 165):
      [0..82]:    Base SPL Token Mint (Mint::LEN = 82 bytes)
      [82..165]:  Padding region (Account::LEN - Mint::LEN = 83 zero bytes)
      [165]:      AccountType byte (BASE_ACCOUNT_LENGTH = Account::LEN = 165)
      [166..]:    Extension TLV data
    Minimum valid size: 166 bytes (BASE_ACCOUNT_AND_TYPE_LENGTH = Account::LEN + 1).
    """
    base = _make_spl_mint_bytes(is_initialized=is_initialized)  # 82 bytes
    pad = padding if padding is not None else bytes(_SPL_TOKEN_ACCOUNT_SIZE - _SPL_TOKEN_MINT_SIZE)  # 83 zeros
    return base + pad + bytes([account_type]) + extensions


def _make_tlv_extension(ext_type: int, data: bytes) -> bytes:
    """Encode a single TLV extension entry (little-endian type u16, length u16, data)."""
    import struct
    return struct.pack("<HH", ext_type, len(data)) + data


class TestToken2022MintStateDecoding(unittest.TestCase):
    """Unit tests for _decode_token_2022_mint_state() — V2-2AL.1 layout repair.

    Correct Token-2022 extended mint layout per SPL token-2022 extension/mod.rs:
      [0..82]:   Base SPL Token Mint (Mint::LEN = 82 bytes)
      [82..165]: Padding region (83 zero bytes = Account::LEN - Mint::LEN)
      [165]:     AccountType = 1 (Mint) at BASE_ACCOUNT_LENGTH
      [166..]:   Extension TLV entries (2-byte LE type + 2-byte LE length + data)
    Minimum valid size: 166 bytes (BASE_ACCOUNT_AND_TYPE_LENGTH = Account::LEN + 1).

    V2-2AL finding: byte 82 is PADDING (zero), not AccountType. AccountType is at 165.
    """

    def test_valid_no_extensions_passes(self):
        """Minimal 166-byte Token-2022 mint (no extensions) must be accepted."""
        raw = _make_token_2022_mint_bytes()
        self.assertEqual(len(raw), 166)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_v2_2al_byte_82_is_zero_and_is_valid_padding(self):
        """Byte 82 = 0 is correct padding — must NOT cause rejection.

        V2-2AL live proof failed because the decoder read AccountType from
        byte 82 (which is padding = 0). With corrected layout, byte 82 = 0
        is expected padding and AccountType is read from byte 165.
        """
        raw = _make_token_2022_mint_bytes()
        self.assertEqual(raw[_SPL_TOKEN_MINT_SIZE], 0, "byte 82 must be zero (padding)")
        self.assertEqual(raw[_TOKEN_2022_ACCOUNT_TYPE_OFFSET], _TOKEN_2022_ACCOUNT_TYPE_MINT, "byte 165 must be AccountType=1")
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertTrue(ok, f"byte 82 = 0 is valid padding, not invalid AccountType; got: {err}")
        self.assertIsNone(err)

    def test_valid_with_one_extension_passes(self):
        ext = _make_tlv_extension(1, b"\x01\x02\x03\x04")
        raw = _make_token_2022_mint_bytes(extensions=ext)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_valid_with_two_extensions_passes(self):
        ext = _make_tlv_extension(1, b"abcdef") + _make_tlv_extension(2, b"xyz")
        raw = _make_token_2022_mint_bytes(extensions=ext)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_trailing_zero_padding_after_extensions_allowed(self):
        ext = _make_tlv_extension(1, b"data") + b"\x00\x00\x00"
        raw = _make_token_2022_mint_bytes(extensions=ext)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_invalid_padding_byte_rejected(self):
        """Non-zero byte in padding region [82..165] must be rejected."""
        bad_padding = bytearray(83)
        bad_padding[5] = 0xFF  # corrupts byte at offset 87 in the full buffer
        raw = _make_token_2022_mint_bytes(padding=bytes(bad_padding))
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("padding", err.lower())

    def test_wrong_account_type_byte_0_rejected(self):
        """AccountType = 0 at offset 165 must be rejected (was old V2-2AK.2 byte-82 bug)."""
        raw = _make_token_2022_mint_bytes(account_type=0)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("AccountType", err)
        self.assertIn("165", err)  # error references the correct offset

    def test_account_type_2_rejected(self):
        """AccountType = 2 (Token Account, not Mint) at offset 165 must be rejected."""
        raw = _make_token_2022_mint_bytes(account_type=2)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("AccountType", err)

    def test_too_short_missing_account_type_rejected(self):
        """165 bytes (base + full padding, no AccountType byte) must be rejected."""
        raw = _make_spl_mint_bytes() + bytes(83)  # 82 + 83 = 165 bytes, missing AccountType
        self.assertEqual(len(raw), 165)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("too short", err.lower())

    def test_tlv_overflow_rejected(self):
        """TLV entry claiming more bytes than remain in buffer must be rejected."""
        import struct as _struct
        bad_ext = _struct.pack("<HH", 1, 100) + b"\x00" * 4  # claims 100 bytes, only 4 available
        raw = _make_token_2022_mint_bytes(extensions=bad_ext)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("overflows", err)

    def test_partial_tlv_header_with_non_zero_bytes_rejected(self):
        """3 non-zero bytes at extension region end (too short for a 4-byte TLV header) must fail."""
        raw = _make_token_2022_mint_bytes(extensions=b"\x01\x00\x02")
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("Partial TLV header", err)

    def test_uninitialized_base_mint_fails_before_account_type_check(self):
        """is_initialized=0 in base Mint must fail before AccountType or padding is checked."""
        raw = _make_token_2022_mint_bytes(is_initialized=0)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("not initialized", err)

    def test_base_mint_too_short_fails_before_account_type_check(self):
        """Buffer shorter than 82 bytes must fail at base Mint check (not padding/AccountType)."""
        raw = bytes(81)
        ok, err = _decode_token_2022_mint_state(raw)
        self.assertFalse(ok)
        self.assertIn("Too short", err)

    def test_account_type_offset_is_165(self):
        """AccountType must be read from offset 165 (= Account::LEN = BASE_ACCOUNT_LENGTH)."""
        self.assertEqual(_TOKEN_2022_ACCOUNT_TYPE_OFFSET, 165)
        self.assertEqual(_TOKEN_2022_EXTENSION_DATA_START, 166)
        self.assertEqual(_TOKEN_2022_ACCOUNT_TYPE_OFFSET, _SPL_TOKEN_ACCOUNT_SIZE)


# ---------------------------------------------------------------------------
# V2-2AK.2 Class 15: getBlockTime call limit
# ---------------------------------------------------------------------------

class TestGetBlockTimeLimit(unittest.TestCase):
    """Verify _T3_MAX_BLOCK_TIME_CALLS == 1 and that block_time_source values are accepted."""

    def test_max_block_time_calls_constant_is_one(self):
        self.assertEqual(_T3_MAX_BLOCK_TIME_CALLS, 1)

    def test_block_time_source_get_transaction_accepted_by_normalizer(self):
        payload = {**_T3_SPL_SUCCESS_PAYLOAD, "t3_block_time_source": "getTransaction"}
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(result.normalized_payload["t3_block_time_source"], "getTransaction")

    def test_block_time_source_get_block_time_accepted_by_normalizer(self):
        payload = {
            **_T3_SPL_SUCCESS_PAYLOAD,
            "t3_block_time_source": "getBlockTime",
            "t3_rpc_methods_attempted": [
                "getAccountInfo", "getSignaturesForAddress", "getTransaction", "getBlockTime"
            ],
        }
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        self.assertEqual(result.normalized_payload["t3_block_time_source"], "getBlockTime")

    def test_null_block_time_with_budget_exhausted_fails_closed(self):
        result = normalize_solana_rpc_token_age_response(
            {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_token_age_null_block_time",
                "failure_message": "blockTime null, getBlockTime limit=1 exhausted",
            },
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertIsNone(result.normalized_payload.get("token_age_seconds"))

    def test_block_time_limit_is_tracked_separately_from_total_budget(self):
        # Verify the constant names are distinct (static check — ensures code is intentional)
        from printer_v1.sources.solana_rpc_token_age import (
            _T3_MAX_BLOCK_TIME_CALLS,
            _T3_MAX_REQUESTS_PER_TOKEN,
            _T3_MAX_TRANSACTION_CALLS,
        )
        self.assertLess(_T3_MAX_BLOCK_TIME_CALLS, _T3_MAX_TRANSACTION_CALLS)
        self.assertLess(_T3_MAX_BLOCK_TIME_CALLS, _T3_MAX_REQUESTS_PER_TOKEN)


# ---------------------------------------------------------------------------
# V2-2AL.4A Class 16: T3 failure provenance repair
# ---------------------------------------------------------------------------

# Partial failure provenance fixture — simulates what _fetch_token_age_data() now returns
_FAIL_PROV_ACCOUNT_VALIDATION = {
    "t3_requested_mint": _SPL_TOKEN_MINT,
    "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
    "t3_rpc_methods_attempted": ["getAccountInfo"],
    "t3_request_ids": [1],
    "t3_pages_fetched": 0,
    "t3_tx_calls_attempted": 0,
    "t3_block_time_calls_attempted": 0,
    "t3_failure_stage": "account_validation",
}

_FAIL_PROV_PAGE_CAP = {
    "t3_requested_mint": _SPL_TOKEN_MINT,
    "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
    "t3_rpc_methods_attempted": [
        "getAccountInfo",
        "getSignaturesForAddress",
        "getSignaturesForAddress",
        "getSignaturesForAddress",
    ],
    "t3_request_ids": [1, 2, 3, 4],
    "t3_pages_fetched": 3,
    "t3_tx_calls_attempted": 0,
    "t3_block_time_calls_attempted": 0,
    "t3_failure_stage": "signature_history",
}

_FAIL_PROV_TX_NO_INIT = {
    "t3_requested_mint": _SPL_TOKEN_MINT,
    "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
    "t3_rpc_methods_attempted": [
        "getAccountInfo", "getSignaturesForAddress", "getTransaction", "getTransaction",
    ],
    "t3_request_ids": [1, 2, 3, 4],
    "t3_pages_fetched": 1,
    "t3_tx_calls_attempted": 2,
    "t3_block_time_calls_attempted": 0,
    "t3_failure_stage": "transaction_inspection",
}

_FAIL_PROV_NULL_BLOCK_TIME = {
    "t3_requested_mint": _SPL_TOKEN_MINT,
    "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
    "t3_rpc_methods_attempted": [
        "getAccountInfo", "getSignaturesForAddress", "getTransaction", "getBlockTime",
    ],
    "t3_request_ids": [1, 2, 3, 4],
    "t3_pages_fetched": 1,
    "t3_tx_calls_attempted": 1,
    "t3_block_time_calls_attempted": 1,
    "t3_failure_stage": "block_time_fallback",
}


def _fail_payload(failure_type: str, provenance: dict) -> dict:
    return {
        "fixture_status": "failure",
        "failure_type": failure_type,
        "failure_message": "fixture",
        **provenance,
    }


class TestT3FailureProvenance(unittest.TestCase):
    """V2-2AL.4A — T3 failure-provenance repair.

    Verifies that bounded RPC failures carry safe partial trace fields in
    NormalizedSourceResult.normalized_payload for audit, without populating
    token_created_at, token_age_seconds, token_age_evidence_tier, or unlocking A3.
    """

    # 1 — Mint-account validation failure carries partial provenance
    def test_mint_validation_failure_carries_partial_provenance(self):
        payload = _fail_payload("solana_rpc_token_age_not_a_mint", _FAIL_PROV_ACCOUNT_VALIDATION)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        p = result.normalized_payload
        self.assertEqual(p.get("t3_requested_mint"), _SPL_TOKEN_MINT)
        self.assertEqual(p.get("t3_rpc_host_redacted"), "api.mainnet-beta.solana.com")
        self.assertEqual(p.get("t3_rpc_methods_attempted"), ["getAccountInfo"])
        self.assertEqual(p.get("t3_request_ids"), [1])
        self.assertEqual(p.get("t3_pages_fetched"), 0)
        self.assertEqual(p.get("t3_tx_calls_attempted"), 0)
        self.assertEqual(p.get("t3_block_time_calls_attempted"), 0)
        self.assertEqual(p.get("t3_failure_stage"), "account_validation")

    # 2 — Rate limit / transport failure carries partial provenance
    def test_rate_limit_failure_carries_partial_provenance(self):
        prov = {**_FAIL_PROV_ACCOUNT_VALIDATION, "t3_failure_stage": "account_validation"}
        payload = _fail_payload("solana_rpc_token_age_rate_limited", prov)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.failure_type, "solana_rpc_token_age_rate_limited")
        self.assertIsNotNone(result.normalized_payload.get("t3_requested_mint"))
        self.assertIsNotNone(result.normalized_payload.get("t3_failure_stage"))

    # 3 — Page-cap exhaustion carries pages_fetched = 3 and correct stage
    def test_page_cap_exhaustion_carries_pages_fetched(self):
        payload = _fail_payload("solana_rpc_token_age_page_cap_exhausted", _FAIL_PROV_PAGE_CAP)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        p = result.normalized_payload
        self.assertEqual(p.get("t3_pages_fetched"), 3)
        self.assertEqual(p.get("t3_failure_stage"), "signature_history")
        self.assertIn("getSignaturesForAddress", p.get("t3_rpc_methods_attempted", []))
        self.assertEqual(p.get("t3_tx_calls_attempted"), 0)

    # 4 — Transaction no-init failure carries tx_calls_attempted
    def test_transaction_no_init_failure_carries_tx_calls_attempted(self):
        payload = _fail_payload("solana_rpc_token_age_no_init_instruction", _FAIL_PROV_TX_NO_INIT)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        p = result.normalized_payload
        self.assertEqual(p.get("t3_tx_calls_attempted"), 2)
        self.assertEqual(p.get("t3_failure_stage"), "transaction_inspection")
        self.assertIn("getTransaction", p.get("t3_rpc_methods_attempted", []))

    # 5 — Null block-time failure carries block_time_calls_attempted = 1
    def test_null_block_time_failure_carries_block_time_calls_attempted(self):
        payload = _fail_payload("solana_rpc_token_age_null_block_time", _FAIL_PROV_NULL_BLOCK_TIME)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        p = result.normalized_payload
        self.assertEqual(p.get("t3_block_time_calls_attempted"), 1)
        self.assertEqual(p.get("t3_failure_stage"), "block_time_fallback")
        self.assertIn("getBlockTime", p.get("t3_rpc_methods_attempted", []))

    # 6 — Budget exhaustion carries exact method/request counts
    def test_budget_exhausted_failure_carries_exact_method_count(self):
        budget_prov = {
            "t3_requested_mint": _SPL_TOKEN_MINT,
            "t3_rpc_host_redacted": "api.mainnet-beta.solana.com",
            "t3_rpc_methods_attempted": [
                "getAccountInfo",
                "getSignaturesForAddress",
                "getSignaturesForAddress",
                "getSignaturesForAddress",
                "getTransaction",
                "getTransaction",
                "getTransaction",
                "getBlockTime",
            ],
            "t3_request_ids": [1, 2, 3, 4, 5, 6, 7, 8],
            "t3_pages_fetched": 3,
            "t3_tx_calls_attempted": 3,
            "t3_block_time_calls_attempted": 1,
            "t3_failure_stage": "transaction_inspection",
        }
        payload = _fail_payload("solana_rpc_token_age_budget_exhausted", budget_prov)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        p = result.normalized_payload
        self.assertEqual(len(p.get("t3_rpc_methods_attempted", [])), 8)
        self.assertEqual(len(p.get("t3_request_ids", [])), 8)
        self.assertEqual(p.get("t3_tx_calls_attempted"), 3)
        self.assertEqual(p.get("t3_block_time_calls_attempted"), 1)

    # 7 — Failure provenance carries redacted RPC host (no path, no key)
    def test_failure_provenance_carries_redacted_rpc_host(self):
        prov = {**_FAIL_PROV_ACCOUNT_VALIDATION}
        payload = _fail_payload("solana_rpc_token_age_not_a_mint", prov)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        host = result.normalized_payload.get("t3_rpc_host_redacted")
        self.assertIsNotNone(host)
        self.assertNotIn("http", str(host))
        self.assertNotIn("?", str(host))
        self.assertNotIn("apikey", str(host))

    # 8 — t3_failure_stage is present and non-empty string
    def test_failure_stage_field_present_and_non_empty(self):
        for stage_prov in (_FAIL_PROV_ACCOUNT_VALIDATION, _FAIL_PROV_PAGE_CAP,
                           _FAIL_PROV_TX_NO_INIT, _FAIL_PROV_NULL_BLOCK_TIME):
            payload = _fail_payload("solana_rpc_token_age_no_init_instruction", stage_prov)
            result = normalize_solana_rpc_token_age_response(
                payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
            )
            stage = result.normalized_payload.get("t3_failure_stage")
            self.assertIsInstance(stage, str, f"expected str stage for prov={stage_prov}")
            self.assertGreater(len(stage), 0)

    # 9 — Failure provenance never sets token-age evidence fields
    def test_failure_provenance_never_sets_token_age_fields(self):
        for prov in (_FAIL_PROV_ACCOUNT_VALIDATION, _FAIL_PROV_PAGE_CAP,
                     _FAIL_PROV_TX_NO_INIT, _FAIL_PROV_NULL_BLOCK_TIME):
            payload = _fail_payload("solana_rpc_token_age_no_init_instruction", prov)
            result = normalize_solana_rpc_token_age_response(
                payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
            )
            p = result.normalized_payload
            self.assertIsNone(p.get("token_created_at"),
                              f"token_created_at must be absent in failure result")
            self.assertIsNone(p.get("token_age_seconds"),
                              f"token_age_seconds must be absent in failure result")
            self.assertIsNone(p.get("token_age_evidence_tier"),
                              f"token_age_evidence_tier must be absent in failure result")

    # 10 — Failure provenance never unlocks A3
    def test_failure_provenance_never_unlocks_a3(self):
        from printer_v1.discovery.selection_batch import BUCKET_A3, assign_bucket
        for prov in (_FAIL_PROV_ACCOUNT_VALIDATION, _FAIL_PROV_PAGE_CAP,
                     _FAIL_PROV_TX_NO_INIT, _FAIL_PROV_NULL_BLOCK_TIME):
            candidate = {
                "token_mint": _SPL_TOKEN_MINT,
                "pair_address": "SomePairXXX",
                "chain": "solana",
                "source_name": SOLANA_RPC_SOURCE_NAME,
                "captured_at": _FIXED_NOW_ISO,
                "token_created_at": None,
                "token_age_seconds": None,
                "price_change_1h": -50.0,
                "token_age_evidence_tier": None,
            }
            candidate.update(prov)
            bucket, _ = assign_bucket(candidate)
            self.assertNotEqual(bucket, BUCKET_A3,
                                f"A3 must not fire from failure provenance: {prov}")

    # 11 — Success path completely unchanged (regression)
    def test_success_path_unchanged_after_provenance_repair(self):
        result = normalize_solana_rpc_token_age_response(
            _T3_SPL_SUCCESS_PAYLOAD, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)
        p = result.normalized_payload
        self.assertEqual(p["token_created_at"], _T3_CREATED_ISO)
        self.assertEqual(p["token_age_seconds"], _T3_AGE_SECONDS)
        self.assertEqual(p["token_age_evidence_tier"], "T3")
        self.assertEqual(p["t3_requested_mint"], _SPL_TOKEN_MINT)
        self.assertIn("getTransaction", p["t3_rpc_methods_attempted"])

    # 12 — Bare failure (no provenance) → empty normalized_payload (backward compat)
    def test_bare_failure_no_provenance_fields_has_empty_payload(self):
        result = normalize_solana_rpc_token_age_response(
            {"fixture_status": "failure",
             "failure_type": "solana_rpc_token_age_not_a_mint",
             "failure_message": "no mint"},
            request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND,
        )
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        # No t3_fail provenance fields because none were in the input
        for field in _T3_FAIL_PROVENANCE_FIELDS:
            self.assertIsNone(result.normalized_payload.get(field),
                              f"unexpected field {field!r} in bare failure result")

    # 13 — fixture_t3_failure_transport with failure_provenance kwarg
    def test_fixture_failure_transport_with_provenance_kwarg(self):
        adapter = build_solana_rpc_token_age_adapter(
            enabled=True,
            fixture_transport=fixture_t3_failure_transport(
                "solana_rpc_token_age_page_cap_exhausted",
                "page cap hit",
                failure_provenance=_FAIL_PROV_PAGE_CAP,
            ),
        )
        ctx = _make_t3_context()
        result = adapter.execute(ctx)
        self.assertEqual(result.source_status, SourceStatus.FAILED)
        self.assertEqual(result.failure_type, "solana_rpc_token_age_page_cap_exhausted")
        self.assertEqual(result.normalized_payload.get("t3_pages_fetched"), 3)
        self.assertEqual(result.normalized_payload.get("t3_failure_stage"), "signature_history")

    # 14 — _T3_FAIL_PROVENANCE_FIELDS constant has all expected fields
    def test_fail_provenance_constant_has_all_required_fields(self):
        required = {
            "t3_requested_mint",
            "t3_rpc_host_redacted",
            "t3_rpc_methods_attempted",
            "t3_request_ids",
            "t3_pages_fetched",
            "t3_tx_calls_attempted",
            "t3_block_time_calls_attempted",
            "t3_failure_stage",
        }
        self.assertEqual(set(_T3_FAIL_PROVENANCE_FIELDS), required)

    # 15 — Methods list in provenance reflects only actually attempted methods
    def test_failure_provenance_methods_list_reflects_actual_calls(self):
        # Account validation failure: only getAccountInfo was called
        payload = _fail_payload("solana_rpc_token_age_not_a_mint", _FAIL_PROV_ACCOUNT_VALIDATION)
        result = normalize_solana_rpc_token_age_response(
            payload, request_kind=SOLANA_RPC_TOKEN_AGE_REQUEST_KIND
        )
        methods = result.normalized_payload.get("t3_rpc_methods_attempted", [])
        self.assertEqual(methods, ["getAccountInfo"])
        self.assertNotIn("getSignaturesForAddress", methods)
        self.assertNotIn("getTransaction", methods)
        self.assertNotIn("getBlockTime", methods)


if __name__ == "__main__":
    unittest.main()
