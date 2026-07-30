from __future__ import annotations

import pytest

from printer_v1.operator_cli.readiness_source_contract_preflight import (
    ReadinessSourceContractPreflightError,
    assert_readiness_source_contract_preflight,
    build_readiness_source_contract_preflight,
)
from printer_v1.sources.operational_source_contracts import (
    GECKOTERMINAL_EXACT_PAIR_URL,
    GECKOTERMINAL_OHLCV_15M_URL,
    GECKOTERMINAL_TRADES_15M_URL,
    ORDINARY_OPERATIONAL_SOURCE_CONTRACTS,
    ordinary_runtime_dependency_names,
)


def test_complete_ordinary_graph_and_budget_are_ready_offline() -> None:
    report = assert_readiness_source_contract_preflight(environment={})
    assert report["status"] == "READY"
    assert report["issues"] == []
    assert report["external_requests"] == 0
    assert report["secret_material_recorded"] is False
    assert set(report["ordinary_runtime_dependencies"]) == set(
        ordinary_runtime_dependency_names()
    )
    assert len(
        [
            profile
            for profile in report["sources"].values()
            if profile["active_runtime"]
        ]
    ) == len(ordinary_runtime_dependency_names())
    assert report["budget"] == {
        "operation_ceiling": 45,
        "candidate_cap": 3,
        "snapshot_reservation": 6,
        "contract_snapshot_reservation": 6,
        "pump_worst_case_operations": 13,
        "zero_transport_operations": 9,
        "holder_worst_case_operations": 15,
        "derived_candidate_cap": 3,
        "worst_case_total": 43,
    }


def test_geckoterminal_contract_is_conditional_exact_and_zero_retry() -> None:
    report = build_readiness_source_contract_preflight(environment={})
    gt = report["sources"]["geckoterminal_exact_pair_and_15m"]
    assert gt["classification"] == "CONDITIONAL"
    assert gt["endpoints"] == [
        GECKOTERMINAL_EXACT_PAIR_URL,
        GECKOTERMINAL_OHLCV_15M_URL,
        GECKOTERMINAL_TRADES_15M_URL,
    ]
    assert gt["printer_rate_limit_per_minute"] == 10
    assert gt["automatic_retries"] == 0
    assert gt["endpoint_rotation"] is False


@pytest.mark.parametrize(
    ("overrides", "expected_issue"),
    [
        (
            {
                "source_contracts": {
                    "direct_pump_migration_locator": {"contract_version": ""}
                }
            },
            "MANDATORY_CONTRACT_VERSION_MISSING:direct_pump_migration_locator",
        ),
        (
            {
                "source_contracts": {
                    "jupiter_entry_exit_quotes": {"wallet_or_private_key": True}
                }
            },
            "PROHIBITED_WALLET_OR_PRIVATE_KEY_CONTRACT:jupiter_entry_exit_quotes",
        ),
        (
            {
                "source_contracts": {
                    "dexscreener_exact_pair": {"source_owner": "DIRECT"}
                }
            },
            "SOURCE_GOVERNOR_BYPASS:dexscreener_exact_pair",
        ),
        (
            {
                "source_contracts": {
                    "coingecko_context": {"scheduler_owner": "DIRECT"}
                }
            },
            "CENTRAL_SCHEDULER_BYPASS:coingecko_context",
        ),
        (
            {
                "runtime_constants": {
                    "jupiter_quote": "https://stale.invalid/quote"
                }
            },
            "RUNTIME_PREFLIGHT_CONSTANT_DRIFT:jupiter_quote",
        ),
    ],
)
def test_complete_preflight_catches_contract_drift(
    overrides, expected_issue
) -> None:
    report = build_readiness_source_contract_preflight(
        environment={}, runtime_overrides=overrides
    )
    assert report["status"] == "BLOCKED"
    assert expected_issue in report["issues"]


def test_conditional_helius_absence_does_not_hide_mandatory_failure() -> None:
    ready = build_readiness_source_contract_preflight(environment={})
    assert ready["status"] == "READY"
    assert ready["sources"]["helius_holder_backup"]["available"] is False
    blocked = build_readiness_source_contract_preflight(
        environment={},
        runtime_overrides={
            "source_contracts": {
                "direct_pump_migration_locator": {
                    "free_public_compatible": False
                }
            }
        },
    )
    assert blocked["status"] == "BLOCKED"
    assert (
        "MANDATORY_FREE_PUBLIC_CONTRACT_INVALID:"
        "direct_pump_migration_locator"
    ) in blocked["issues"]
    with pytest.raises(ReadinessSourceContractPreflightError):
        assert_readiness_source_contract_preflight(
            environment={},
            runtime_overrides={
                "source_contracts": {
                    "direct_pump_migration_locator": {"endpoints": []}
                }
            },
        )


def test_shared_registry_is_the_preflight_source() -> None:
    report = build_readiness_source_contract_preflight(environment={})
    for name, adopted in ORDINARY_OPERATIONAL_SOURCE_CONTRACTS.items():
        observed = report["sources"][name]
        assert observed["classification"] == adopted.classification
        assert observed["contract_version"] == adopted.contract_version
