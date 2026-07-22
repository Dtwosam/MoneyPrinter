"""Consolidated offline contract/configuration gate for bounded readiness.

This module performs no transport and no database write.  It compares the
fixed production configuration for every readiness source with the officially
adopted contract and the campaign budget before any live authorization may be
consumed.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import math
import os
from typing import Any, Mapping

from printer_v1.operator_cli.holder_reliability_budget_control import (
    COMBINED_ZERO_TRANSPORT_VALIDATION,
    HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    OPERATION_CEILING,
    REQUIRED_READINESS_SNAPSHOT_RESERVATION,
    deterministic_spacing_seconds,
)
from printer_v1.operator_cli.snapshot_readiness_contract import (
    READINESS_15M_SOURCE,
    READINESS_OPERATION_RESERVATION,
    READINESS_PRIMARY_SOURCE,
    READINESS_WINDOW_SECONDS,
)
from printer_v1.sources.dexscreener import (
    DEXSCREENER_PAIR_PROVIDER_RATE_LIMIT_PER_MINUTE,
    DEXSCREENER_PAIR_URL_TEMPLATE,
    DEXSCREENER_PUBLIC_API_HEADERS,
    DEXSCREENER_TRANSPORT_OPERATION_COST,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    GECKOTERMINAL_PROVIDER_RATE_LIMIT_PER_MINUTE,
    GECKOTERMINAL_PUBLIC_API_HEADERS,
    GECKOTERMINAL_PUBLIC_API_VERSION,
    GECKOTERMINAL_TRANSPORT_OPERATION_COST,
    GT15M_OHLCV_URL_TEMPLATE,
    GT15M_TRADES_URL_TEMPLATE,
)
from printer_v1.sources.goplus import (
    GOPLUS_PROVIDER_RATE_LIMIT_PER_MINUTE,
    GOPLUS_PUBLIC_API_HEADERS,
    GOPLUS_SOLANA_TOKEN_SECURITY_URL,
    GOPLUS_TRANSPORT_OPERATION_COST,
)
from printer_v1.sources.helius_holder import (
    HELIUS_API_KEY_ENV,
    HELIUS_FIXED_MAINNET_URL,
    HELIUS_FREE_RPC_RATE_LIMIT_PER_SECOND,
    HELIUS_STANDARD_RPC_CREDITS_PER_OPERATION,
)
from printer_v1.sources.registry import SOURCE_REGISTRY
from printer_v1.sources.solana_rpc_holder import (
    SOLANA_PUBLIC_RPC_URL,
    SOLANA_RPC_HOLDER_TRANSPORT_OPERATION_COST,
    SOLANA_RPC_PROVIDER_GLOBAL_LIMIT_PER_10_SECONDS,
    SOLANA_RPC_PROVIDER_PER_METHOD_LIMIT_PER_10_SECONDS,
    SOLANA_RPC_PUBLIC_HEADERS,
)


PUMP_WORST_CASE_OPERATIONS = 12
READINESS_SELECTED_TOKEN_COUNT = 2
READINESS_CANDIDATE_CAP = 3


@dataclass(frozen=True)
class AdoptedReadinessSourceContract:
    source_name: str
    endpoints: tuple[str, ...]
    required_headers: Mapping[str, str]
    authentication: str
    request_kinds: tuple[str, ...]
    provider_rate_limit_per_minute: int
    printer_rate_limit_per_minute: int
    minimum_spacing_seconds: int
    operation_costs: Mapping[str, int]
    required_response_fields: tuple[str, ...]
    attempts_per_request: int = 1
    endpoint_rotation: bool = False


# Independent official values.  These literals must not be sourced from the
# runtime constants they validate.
_OFFICIAL_CONFIGURATION: dict[str, dict[str, Any]] = {
    "goplus": {
        "endpoints": ("https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={token_mint}",),
        "required_headers": {"User-Agent": "PrinterV1/0.1 (+paper-only safety check)", "Accept": "application/json"},
        "authentication": "KEYLESS_PUBLIC_OPTIONAL_BEARER",
        "request_kinds": ("safety_reference",),
        "provider_rate_limit_per_minute": 30,
        "printer_rate_limit_per_minute": 20,
        "minimum_spacing_seconds": 3,
        "operation_costs": {"safety_reference": 1},
        "required_response_fields": ("code", "result", "exact_mint"),
    },
    "solana_rpc": {
        "endpoints": ("https://api.mainnet-beta.solana.com",),
        "required_headers": {"User-Agent": "PrinterV1/0.1 (+paper-only holder check)", "Content-Type": "application/json", "Accept": "application/json"},
        "authentication": "KEYLESS_PUBLIC",
        "request_kinds": ("holder_concentration_reference",),
        "provider_rate_limit_per_minute": 240,
        "printer_rate_limit_per_minute": 30,
        "minimum_spacing_seconds": 2,
        "operation_costs": {"holder_concentration_reference": 2},
        "required_response_fields": ("getTokenLargestAccounts", "getTokenSupply", "finalized", "context.slot"),
    },
    "helius_free": {
        "endpoints": ("https://mainnet.helius-rpc.com/",),
        "required_headers": {"User-Agent": "PrinterV1/0.1 (+paper-only holder check)", "Content-Type": "application/json", "Accept": "application/json"},
        "authentication": "QUERY_API_KEY_REQUIRED_REDACTED",
        "request_kinds": ("holder_concentration_reference",),
        "provider_rate_limit_per_minute": 600,
        "printer_rate_limit_per_minute": 30,
        "minimum_spacing_seconds": 2,
        "operation_costs": {"holder_concentration_reference": 2},
        "required_response_fields": ("getTokenLargestAccounts", "getTokenSupply", "finalized", "context.slot"),
    },
    "dexscreener": {
        "endpoints": ("https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}",),
        "required_headers": {"User-Agent": "PrinterV1/0.1 (+paper-only source check)", "Accept": "application/json"},
        "authentication": "KEYLESS_PUBLIC",
        "request_kinds": ("pair_market_snapshot",),
        "provider_rate_limit_per_minute": 300,
        "printer_rate_limit_per_minute": 60,
        "minimum_spacing_seconds": 1,
        "operation_costs": {"pair_market_snapshot": 1},
        "required_response_fields": ("chainId", "pairAddress", "baseToken.address", "priceUsd", "liquidity.usd", "m5", "h1"),
    },
    "geckoterminal": {
        "endpoints": (
            "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/minute?aggregate=15&limit=2&currency=usd&token=base",
            "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/trades",
        ),
        "required_headers": {"User-Agent": "PrinterV1/0.1 (+paper-only source check)", "Accept": "application/json;version=20230203"},
        "authentication": "KEYLESS_PUBLIC",
        "request_kinds": ("geckoterminal_ohlcv_15m", "geckoterminal_pool_trades_15m"),
        "provider_rate_limit_per_minute": 10,
        "printer_rate_limit_per_minute": 10,
        "minimum_spacing_seconds": 6,
        "operation_costs": {"geckoterminal_ohlcv_15m": 1, "geckoterminal_pool_trades_15m": 1},
        "required_response_fields": ("ohlcv_list", "timestamp/open/close/volume", "trade.attributes.block_timestamp", "exact_pool"),
    },
}

class ReadinessSourceContractPreflightError(RuntimeError):
    pass


def _contracts() -> dict[str, AdoptedReadinessSourceContract]:
    solana_per_method_per_minute = (
        SOLANA_RPC_PROVIDER_PER_METHOD_LIMIT_PER_10_SECONDS * 6
    )
    solana_global_per_minute = SOLANA_RPC_PROVIDER_GLOBAL_LIMIT_PER_10_SECONDS * 6
    solana_provider_limit = min(solana_per_method_per_minute, solana_global_per_minute)
    helius_provider_limit = HELIUS_FREE_RPC_RATE_LIMIT_PER_SECOND * 60
    return {
        "goplus": AdoptedReadinessSourceContract(
            source_name="goplus",
            endpoints=(GOPLUS_SOLANA_TOKEN_SECURITY_URL,),
            required_headers=dict(GOPLUS_PUBLIC_API_HEADERS),
            authentication="KEYLESS_PUBLIC_OPTIONAL_BEARER",
            request_kinds=("safety_reference",),
            provider_rate_limit_per_minute=GOPLUS_PROVIDER_RATE_LIMIT_PER_MINUTE,
            printer_rate_limit_per_minute=SOURCE_REGISTRY["goplus"].default_rate_limit_per_minute,
            minimum_spacing_seconds=deterministic_spacing_seconds("goplus"),
            operation_costs={"safety_reference": GOPLUS_TRANSPORT_OPERATION_COST},
            required_response_fields=("code", "result", "exact_mint"),
        ),
        "solana_rpc": AdoptedReadinessSourceContract(
            source_name="solana_rpc",
            endpoints=(SOLANA_PUBLIC_RPC_URL,),
            required_headers=dict(SOLANA_RPC_PUBLIC_HEADERS),
            authentication="KEYLESS_PUBLIC",
            request_kinds=("holder_concentration_reference",),
            provider_rate_limit_per_minute=solana_provider_limit,
            printer_rate_limit_per_minute=SOURCE_REGISTRY["solana_rpc"].default_rate_limit_per_minute,
            minimum_spacing_seconds=deterministic_spacing_seconds("solana_rpc"),
            operation_costs={"holder_concentration_reference": SOLANA_RPC_HOLDER_TRANSPORT_OPERATION_COST},
            required_response_fields=("getTokenLargestAccounts", "getTokenSupply", "finalized", "context.slot"),
        ),
        "helius_free": AdoptedReadinessSourceContract(
            source_name="helius_free",
            endpoints=(HELIUS_FIXED_MAINNET_URL,),
            required_headers=dict(SOLANA_RPC_PUBLIC_HEADERS),
            authentication="QUERY_API_KEY_REQUIRED_REDACTED",
            request_kinds=("holder_concentration_reference",),
            provider_rate_limit_per_minute=helius_provider_limit,
            printer_rate_limit_per_minute=SOURCE_REGISTRY["helius_free"].default_rate_limit_per_minute,
            minimum_spacing_seconds=deterministic_spacing_seconds("helius_free"),
            operation_costs={"holder_concentration_reference": 2 * HELIUS_STANDARD_RPC_CREDITS_PER_OPERATION},
            required_response_fields=("getTokenLargestAccounts", "getTokenSupply", "finalized", "context.slot"),
        ),
        "dexscreener": AdoptedReadinessSourceContract(
            source_name="dexscreener",
            endpoints=(DEXSCREENER_PAIR_URL_TEMPLATE,),
            required_headers=dict(DEXSCREENER_PUBLIC_API_HEADERS),
            authentication="KEYLESS_PUBLIC",
            request_kinds=("pair_market_snapshot",),
            provider_rate_limit_per_minute=DEXSCREENER_PAIR_PROVIDER_RATE_LIMIT_PER_MINUTE,
            printer_rate_limit_per_minute=SOURCE_REGISTRY["dexscreener"].default_rate_limit_per_minute,
            minimum_spacing_seconds=deterministic_spacing_seconds("dexscreener"),
            operation_costs={"pair_market_snapshot": DEXSCREENER_TRANSPORT_OPERATION_COST},
            required_response_fields=("chainId", "pairAddress", "baseToken.address", "priceUsd", "liquidity.usd", "m5", "h1"),
        ),
        "geckoterminal": AdoptedReadinessSourceContract(
            source_name="geckoterminal",
            endpoints=(GT15M_OHLCV_URL_TEMPLATE, GT15M_TRADES_URL_TEMPLATE),
            required_headers=dict(GECKOTERMINAL_PUBLIC_API_HEADERS),
            authentication="KEYLESS_PUBLIC",
            request_kinds=(GECKOTERMINAL_OHLCV_REQUEST_KIND, GECKOTERMINAL_POOL_TRADES_REQUEST_KIND),
            provider_rate_limit_per_minute=GECKOTERMINAL_PROVIDER_RATE_LIMIT_PER_MINUTE,
            printer_rate_limit_per_minute=SOURCE_REGISTRY["geckoterminal"].default_rate_limit_per_minute,
            minimum_spacing_seconds=deterministic_spacing_seconds("geckoterminal"),
            operation_costs={
                GECKOTERMINAL_OHLCV_REQUEST_KIND: GECKOTERMINAL_TRANSPORT_OPERATION_COST,
                GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: GECKOTERMINAL_TRANSPORT_OPERATION_COST,
            },
            required_response_fields=("ohlcv_list", "timestamp/open/close/volume", "trade.attributes.block_timestamp", "exact_pool"),
        ),
    }


def _runtime_profiles() -> dict[str, dict[str, Any]]:
    profiles = {name: asdict(contract) for name, contract in _contracts().items()}
    for name, profile in profiles.items():
        profile["registered_request_kinds"] = tuple(SOURCE_REGISTRY[name].allowed_request_kinds)
        profile["registry_max_retries"] = SOURCE_REGISTRY[name].max_retries
        profile["pacing_derived_from_registry"] = True
    profiles["geckoterminal"]["api_version"] = GECKOTERMINAL_PUBLIC_API_VERSION
    profiles["geckoterminal"]["registry_max_retries"] = SOURCE_REGISTRY["geckoterminal"].max_retries
    profiles["helius_free"]["secret_environment_name"] = HELIUS_API_KEY_ENV
    return profiles


def _merge_overrides(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_overrides(target[key], value)
        else:
            target[key] = value


def build_readiness_source_contract_preflight(
    *,
    secret_present: bool | None = None,
    runtime_overrides: Mapping[str, Any] | None = None,
    budget_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one deterministic, secret-free readiness admission report."""
    expected = {name: asdict(contract) for name, contract in _contracts().items()}
    for source_name, official in _OFFICIAL_CONFIGURATION.items():
        expected[source_name].update(deepcopy(official))
    runtime = _runtime_profiles()
    if runtime_overrides:
        _merge_overrides(runtime, deepcopy(dict(runtime_overrides)))
    if secret_present is None:
        secret_present = bool(os.environ.get(HELIUS_API_KEY_ENV, "").strip())

    issues: list[str] = []
    for source_name, contract in expected.items():
        observed = runtime.get(source_name)
        if not isinstance(observed, Mapping):
            issues.append(f"SOURCE_PROFILE_MISSING:{source_name}")
            continue
        for field in (
            "endpoints",
            "required_headers",
            "authentication",
            "request_kinds",
            "provider_rate_limit_per_minute",
            "printer_rate_limit_per_minute",
            "minimum_spacing_seconds",
            "operation_costs",
            "required_response_fields",
        ):
            if observed.get(field) != contract[field]:
                issues.append(f"SOURCE_CONTRACT_DRIFT:{source_name}:{field}")
        request_kinds = set(observed.get("request_kinds") or ())
        registered = set(observed.get("registered_request_kinds") or ())
        if not request_kinds.issubset(registered):
            issues.append(f"SOURCE_REQUEST_KIND_DRIFT:{source_name}")
        provider_rate = int(observed.get("provider_rate_limit_per_minute") or 0)
        printer_rate = int(observed.get("printer_rate_limit_per_minute") or 0)
        if provider_rate <= 0 or printer_rate <= 0 or printer_rate > provider_rate:
            issues.append(f"SOURCE_RATE_LIMIT_DRIFT:{source_name}")
        required_spacing = max(1, math.ceil(60 / printer_rate)) if printer_rate else 0
        if int(observed.get("minimum_spacing_seconds") or 0) < required_spacing:
            issues.append(f"SOURCE_PACING_DRIFT:{source_name}")
        if observed.get("attempts_per_request") != 1 or observed.get("endpoint_rotation") is not False:
            issues.append(f"SOURCE_RETRY_OR_ROTATION_DRIFT:{source_name}")

    if not secret_present:
        issues.append("SOURCE_AUTH_DRIFT:helius_free:secret_missing")
    if runtime["geckoterminal"].get("api_version") != "20230203":
        issues.append("SOURCE_HEADER_DRIFT:geckoterminal:api_version")
    if runtime["geckoterminal"].get("registry_max_retries") != 0:
        issues.append("SOURCE_RETRY_OR_ROTATION_DRIFT:geckoterminal:registry")

    budget = {
        "operation_ceiling": OPERATION_CEILING,
        "candidate_cap": READINESS_CANDIDATE_CAP,
        "snapshot_reservation": REQUIRED_READINESS_SNAPSHOT_RESERVATION,
        "contract_snapshot_reservation": READINESS_OPERATION_RESERVATION,
        "pump_worst_case_operations": PUMP_WORST_CASE_OPERATIONS,
        "zero_transport_operations": COMBINED_ZERO_TRANSPORT_VALIDATION,
        "holder_worst_case_operations": READINESS_CANDIDATE_CAP * HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    }
    if budget_overrides:
        budget.update(dict(budget_overrides))
    budget["worst_case_total"] = (
        budget["pump_worst_case_operations"]
        + budget["zero_transport_operations"]
        + budget["holder_worst_case_operations"]
        + budget["snapshot_reservation"]
    )
    if (
        budget["operation_ceiling"] != 45
        or budget["candidate_cap"] != 3
        or budget["snapshot_reservation"] != 6
        or budget["contract_snapshot_reservation"] != 6
        or budget["worst_case_total"] > budget["operation_ceiling"]
    ):
        issues.append("READINESS_BUDGET_CONTRACT_DRIFT")
    provenance = {
        "primary_source": READINESS_PRIMARY_SOURCE,
        "supplemental_15m_source": READINESS_15M_SOURCE,
        "exact_window_seconds": READINESS_WINDOW_SECONDS,
    }
    if provenance != {
        "primary_source": "dexscreener",
        "supplemental_15m_source": "geckoterminal",
        "exact_window_seconds": 900,
    }:
        issues.append("READINESS_PROVENANCE_CONTRACT_DRIFT")

    return {
        "status": "READY" if not issues else "BLOCKED",
        "issues": sorted(set(issues)),
        "sources": runtime,
        "budget": budget,
        "provenance": provenance,
        "helius_secret_present": bool(secret_present),
        "secret_material_recorded": False,
        "external_requests": 0,
    }


def assert_readiness_source_contract_preflight(**kwargs: Any) -> dict[str, Any]:
    report = build_readiness_source_contract_preflight(**kwargs)
    if report["status"] != "READY":
        raise ReadinessSourceContractPreflightError(
            ";".join(report["issues"])
        )
    return report
