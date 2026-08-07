from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from printer_v1.discovery.permanent_discovery_availability import (
    validate_campaign_transport_identity_manifest,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    persist_bundle_attempts,
)
from printer_v1.sources.measured_transport import (
    TransportOperationIdentity,
    canonical_transport_identity_key,
)


MINT = "5aNJBy3n3AjsGZ2qvQFKfV6BhKSTQU6MXxN2sjGu8nei"
NOW = "2026-08-07T19:00:00+00:00"


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE printer_holder_evidence_attempts(
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            cycle_id TEXT,
            mint_identity TEXT,
            request_purpose TEXT,
            source_name TEXT,
            endpoint_role TEXT,
            redacted_host TEXT,
            source_request_id INTEGER,
            source_response_id INTEGER,
            source_failure_id INTEGER,
            lineage_response_id INTEGER,
            reused_evidence_id INTEGER,
            captured_at TEXT,
            received_at TEXT,
            parser_version TEXT,
            policy_version TEXT,
            source_status TEXT,
            data_quality_label TEXT,
            exact_target INTEGER,
            holder_concentration_label TEXT,
            rpc_method TEXT,
            commitment TEXT,
            context_slot INTEGER,
            underlying_operation_count INTEGER,
            failure_subtype TEXT,
            retry_after_at TEXT,
            created_at TEXT
        )
        """
    )
    return connection


def _execution(*, request_id: int, with_transport: bool) -> SimpleNamespace:
    identities = []
    used = 0
    underlying = 0
    if with_transport:
        identity = TransportOperationIdentity(
            stage="HOLDER_SAFETY",
            source_name="goplus",
            endpoint_owner="api.gopluslabs.io",
            governed_request_kind="safety_reference",
            method_or_endpoint="GET_TOKEN_SECURITY",
            within_request_ordinal=1,
            target_category="TOKEN_MINT",
            target_identity=MINT,
            response_bytes=128,
            normalized_rows=1,
            result="COMPLETED",
        )
        identities = [identity.as_dict()]
        used = 1
        underlying = 1

    payload = {
        "token_mint": MINT,
        "mint_authority": None,
        "freeze_authority": None,
        "metadata_mutable": False,
        "total_supply": "1000000000",
        "top_10_holders": [{"percent": "3"} for _ in range(10)],
        "lp_info": [{"locked": True}],
        "risk_flags": [],
        "transport_operation_identities": identities,
        "transport_operations_used": used,
        "underlying_operation_count": underlying,
    }
    normalized = SimpleNamespace(
        source_name="goplus",
        request_kind="safety_reference",
        normalized_payload=payload,
        source_status=SimpleNamespace(value="COMPLETE"),
        data_quality_label=SimpleNamespace(value="CLEAN_DATA"),
        failure_type=None,
        retry_after_at=None,
        received_at=NOW,
    )
    return SimpleNamespace(
        request_record=SimpleNamespace(
            id=request_id,
            request_kind="safety_reference",
        ),
        response_record=None,
        failure_record=None,
        normalized_result=normalized,
    )


def test_dtw49_holder_coverage_carries_exact_transport_identity_key() -> None:
    connection = _connection()
    try:
        execution = _execution(request_id=16, with_transport=True)
        result = persist_bundle_attempts(
            connection,
            run_id="dtw49-run",
            cycle_id="dtw49-cycle",
            mint=MINT,
            executions={"safety": execution},
            created_at=NOW,
            campaign_id="dtw49-campaign",
            candidate_ordinal=1,
            require_exact_transport_identities=True,
        )
    finally:
        connection.close()

    assert result.governed_request_count == 1
    assert result.measured_transport_count == 1
    assert result.accounting_blocker is False
    assert len(result.source_request_coverage) == 1

    coverage = dict(result.source_request_coverage[0])
    expected_identity = execution.normalized_result.normalized_payload[
        "transport_operation_identities"
    ][0]
    expected_key = list(canonical_transport_identity_key(expected_identity))

    assert coverage["source_request_id"] == 16
    assert coverage["transport_identity_count"] == 1
    assert coverage["transport_identity_keys"] == [expected_key]
    assert coverage["logical_stage_id"].startswith("dtw49-campaign|")

    manifest = validate_campaign_transport_identity_manifest(
        result.source_request_coverage,
        require_exact=True,
    )
    assert manifest["status"] == "OK"
    assert manifest["transport_identity_completeness_status"] == "OK"
    assert manifest["transport_identity_blockers"] == []
    assert manifest["transport_identity_count_total"] == 1


def test_dtw49_lawful_zero_transport_coverage_has_explicit_empty_keys() -> None:
    connection = _connection()
    try:
        result = persist_bundle_attempts(
            connection,
            run_id="dtw49-zero-run",
            cycle_id="dtw49-zero-cycle",
            mint=MINT,
            executions={"safety": _execution(request_id=17, with_transport=False)},
            created_at=NOW,
            campaign_id="dtw49-zero-campaign",
            candidate_ordinal=1,
            require_exact_transport_identities=True,
        )
    finally:
        connection.close()

    assert result.governed_request_count == 1
    assert result.measured_transport_count == 0
    assert result.accounting_blocker is False
    coverage = dict(result.source_request_coverage[0])
    assert coverage["transport_identity_count"] == 0
    assert coverage["transport_identity_keys"] == []

    manifest = validate_campaign_transport_identity_manifest(
        result.source_request_coverage,
        require_exact=True,
    )
    assert manifest["status"] == "OK"
    assert manifest["transport_identity_completeness_status"] == "OK"
    assert manifest["transport_identity_count_total"] == 0
