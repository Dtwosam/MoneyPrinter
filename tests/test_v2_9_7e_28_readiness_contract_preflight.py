from __future__ import annotations

import pytest

from printer_v1.operator_cli.readiness_source_contract_preflight import (
    ReadinessSourceContractPreflightError,
    assert_readiness_source_contract_preflight,
    build_readiness_source_contract_preflight,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_PUBLIC_API_HEADERS,
    GECKOTERMINAL_PUBLIC_API_VERSION,
    GT15M_OHLCV_URL_TEMPLATE,
    GT15M_TRADES_URL_TEMPLATE,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


def test_all_readiness_source_contracts_and_budget_are_ready_offline() -> None:
    report = assert_readiness_source_contract_preflight(secret_present=True)
    assert report["status"] == "READY"
    assert report["issues"] == []
    assert report["external_requests"] == 0
    assert report["secret_material_recorded"] is False
    assert report["budget"] == {
        "operation_ceiling": 45,
        "candidate_cap": 3,
        "snapshot_reservation": 6,
        "contract_snapshot_reservation": 6,
        "pump_worst_case_operations": 12,
        "zero_transport_operations": 9,
        "holder_worst_case_operations": 15,
        "worst_case_total": 42,
    }
    assert report["provenance"] == {
        "primary_source": "dexscreener",
        "supplemental_15m_source": "geckoterminal",
        "exact_window_seconds": 900,
    }


def test_geckoterminal_header_endpoints_limit_retry_and_pacing_are_exact() -> None:
    report = build_readiness_source_contract_preflight(secret_present=True)
    gt = report["sources"]["geckoterminal"]
    assert GECKOTERMINAL_PUBLIC_API_VERSION == "20230203"
    assert GECKOTERMINAL_PUBLIC_API_HEADERS["Accept"] == "application/json;version=20230203"
    assert gt["endpoints"] == (GT15M_OHLCV_URL_TEMPLATE, GT15M_TRADES_URL_TEMPLATE)
    assert gt["provider_rate_limit_per_minute"] == 10
    assert gt["printer_rate_limit_per_minute"] == 10
    assert gt["minimum_spacing_seconds"] == 6
    assert gt["registry_max_retries"] == 0
    assert gt["attempts_per_request"] == 1
    assert gt["endpoint_rotation"] is False
    assert SOURCE_REGISTRY["geckoterminal"].default_rate_limit_per_minute == 10


@pytest.mark.parametrize(
    ("overrides", "expected_issue"),
    [
        ({"geckoterminal": {"endpoints": ("https://wrong.invalid",)}},
         "SOURCE_CONTRACT_DRIFT:geckoterminal:endpoints"),
        ({"geckoterminal": {"required_headers": {"Accept": "application/json"}}},
         "SOURCE_CONTRACT_DRIFT:geckoterminal:required_headers"),
        ({"helius_free": {"authentication": "KEYLESS_PUBLIC"}},
         "SOURCE_CONTRACT_DRIFT:helius_free:authentication"),
        ({"dexscreener": {"printer_rate_limit_per_minute": 301}},
         "SOURCE_RATE_LIMIT_DRIFT:dexscreener"),
        ({"geckoterminal": {"minimum_spacing_seconds": 5}},
         "SOURCE_PACING_DRIFT:geckoterminal"),
        ({"solana_rpc": {"registered_request_kinds": ()}},
         "SOURCE_REQUEST_KIND_DRIFT:solana_rpc"),
        ({"goplus": {"operation_costs": {"safety_reference": 0}}},
         "SOURCE_CONTRACT_DRIFT:goplus:operation_costs"),
    ],
)
def test_consolidated_preflight_catches_source_drift(overrides, expected_issue) -> None:
    report = build_readiness_source_contract_preflight(
        secret_present=True, runtime_overrides=overrides
    )
    assert report["status"] == "BLOCKED"
    assert expected_issue in report["issues"]


def test_consolidated_preflight_catches_auth_and_budget_drift() -> None:
    missing_secret = build_readiness_source_contract_preflight(secret_present=False)
    assert "SOURCE_AUTH_DRIFT:helius_free:secret_missing" in missing_secret["issues"]
    bad_budget = build_readiness_source_contract_preflight(
        secret_present=True, budget_overrides={"operation_ceiling": 41}
    )
    assert "READINESS_BUDGET_CONTRACT_DRIFT" in bad_budget["issues"]
    with pytest.raises(ReadinessSourceContractPreflightError):
        assert_readiness_source_contract_preflight(secret_present=False)


def test_all_printer_limits_are_at_or_below_provider_limits() -> None:
    report = build_readiness_source_contract_preflight(secret_present=True)
    for source in report["sources"].values():
        assert source["printer_rate_limit_per_minute"] <= source["provider_rate_limit_per_minute"]
        assert source["attempts_per_request"] == 1
        assert source["endpoint_rotation"] is False
