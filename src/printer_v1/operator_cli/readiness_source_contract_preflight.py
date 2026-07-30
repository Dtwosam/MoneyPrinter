"""Zero-I/O complete source preflight for the ordinary restored factory graph."""

from __future__ import annotations

from copy import deepcopy
import math
import os
from typing import Any, Mapping

from printer_v1.operator_cli.holder_reliability_budget_control import (
    COMBINED_ZERO_TRANSPORT_VALIDATION,
    HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    OPERATION_CEILING,
    REQUIRED_READINESS_SNAPSHOT_RESERVATION,
)
from printer_v1.operator_cli.snapshot_readiness_contract import (
    READINESS_15M_SOURCE,
    READINESS_OPERATION_RESERVATION,
    READINESS_PRIMARY_SOURCE,
    READINESS_WINDOW_SECONDS,
)
from printer_v1.sources.operational_source_contracts import (
    CONTRACT_REGISTRY_VERSION,
    HELIUS_API_KEY_ENVIRONMENT_NAME,
    JUPITER_KEYLESS_QUOTE_URL,
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    ORDINARY_OPERATIONAL_SOURCE_CONTRACTS,
    SOLANA_RPC_ENVIRONMENT_NAME,
    SOURCE_CLASSIFICATIONS,
    SolanaRpcConfigurationError,
    ordinary_runtime_dependency_names,
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_contracts import (
    OFFICIAL_REPOSITORY_COMMIT,
    PUMP_IDL_SHA256,
    PUMP_PROGRAM_ID,
    PUMPSWAP_AMM_PROGRAM_ID,
    PUMPSWAP_IDL_SHA256,
)
from printer_v1.sources.pumpfun_origin import (
    CREATE_INDEX_DECODE_CEILING,
    CREATE_INDEX_PAGE_CEILING,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


PUMP_WORST_CASE_OPERATIONS = (
    CREATE_INDEX_PAGE_CEILING + CREATE_INDEX_DECODE_CEILING
)
READINESS_SELECTED_TOKEN_COUNT = 2
READINESS_CANDIDATE_CAP = max(
    0,
    (
        OPERATION_CEILING
        - PUMP_WORST_CASE_OPERATIONS
        - COMBINED_ZERO_TRANSPORT_VALIDATION
        - REQUIRED_READINESS_SNAPSHOT_RESERVATION
    )
    // HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
)
_PROHIBITED_MARKERS = (
    "wallet",
    "private_key",
    "private key",
    "funding",
    "paid_dependency",
    "metered",
)
_PLACEHOLDER_MARKERS = ("your_", "changeme", "placeholder", "<", ">")


class ReadinessSourceContractPreflightError(RuntimeError):
    pass


def _merge_overrides(target: dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _merge_overrides(target[key], value)
        else:
            target[key] = value


def _runtime_constant_snapshot() -> dict[str, Any]:
    """Read the actual active-module values that must equal the shared owner."""

    from printer_v1.sources.coingecko import COINGECKO_MARKET_URL
    from printer_v1.sources.dexscreener import (
        DEXSCREENER_PAIR_URL_TEMPLATE,
        DEXSCREENER_TOKEN_PROFILES_URL,
        DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE,
    )
    from printer_v1.sources.geckoterminal import GECKOTERMINAL_POOL_URL_TEMPLATE
    from printer_v1.sources.goplus import GOPLUS_SOLANA_TOKEN_SECURITY_URL
    from printer_v1.sources.jupiter_quote import JUPITER_QUOTE_API_URL
    from printer_v1.sources.solana_rpc_holder import SOLANA_PUBLIC_RPC_URL

    contracts = ORDINARY_OPERATIONAL_SOURCE_CONTRACTS
    return {
        "solana_public_rpc": SOLANA_PUBLIC_RPC_URL,
        "jupiter_quote": JUPITER_QUOTE_API_URL,
        "dexscreener_profiles": DEXSCREENER_TOKEN_PROFILES_URL,
        "dexscreener_batch": DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE,
        "dexscreener_pair": DEXSCREENER_PAIR_URL_TEMPLATE,
        "geckoterminal_pair": GECKOTERMINAL_POOL_URL_TEMPLATE,
        "goplus": GOPLUS_SOLANA_TOKEN_SECURITY_URL,
        "coingecko": COINGECKO_MARKET_URL,
        "expected": {
            "solana_public_rpc": OFFICIAL_SOLANA_PUBLIC_RPC_URL,
            "jupiter_quote": JUPITER_KEYLESS_QUOTE_URL,
            "dexscreener_profiles": contracts[
                "dexscreener_latest_profiles"
            ].endpoints[0],
            "dexscreener_batch": contracts["dexscreener_token_batch"].endpoints[0],
            "dexscreener_pair": contracts["dexscreener_exact_pair"].endpoints[0],
            "geckoterminal_pair": contracts[
                "geckoterminal_exact_pair_and_15m"
            ].endpoints[0],
            "goplus": contracts["goplus_safety"].endpoints[0],
            "coingecko": contracts["coingecko_context"].endpoints[0],
        },
    }


def _source_profiles(
    *,
    environment: Mapping[str, str],
    solana_redacted_identity: str,
    solana_origin: str,
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    helius_value = str(
        environment.get(HELIUS_API_KEY_ENVIRONMENT_NAME, "") or ""
    ).strip()
    for name, contract in ORDINARY_OPERATIONAL_SOURCE_CONTRACTS.items():
        profile = contract.as_dict()
        endpoints = list(contract.endpoints)
        if "SOLANA_RPC_RESOLVED" in endpoints:
            endpoints = [solana_redacted_identity]
        profile["endpoints"] = endpoints
        profile["environment_state"] = {}
        for env_name in contract.required_environment:
            value = str(environment.get(env_name, "") or "").strip()
            profile["environment_state"][env_name] = (
                "PRESENT_REDACTED" if value else "MISSING_CONDITIONAL"
            )
        profile["solana_rpc_origin"] = (
            solana_origin if "SOLANA_RPC_RESOLVED" in contract.endpoints else None
        )
        profile["registered_request_kinds"] = {
            source: list(SOURCE_REGISTRY[source].allowed_request_kinds)
            for source in contract.source_names
            if source in SOURCE_REGISTRY
        }
        profile["automatic_retries"] = 0
        profile["endpoint_rotation"] = False
        profile["scheduler_owner"] = "CENTRAL_SCHEDULER"
        profile["source_owner"] = "SOURCE_GOVERNOR"
        profiles[name] = profile
    profiles["helius_holder_backup"]["available"] = bool(helius_value)
    return profiles


def build_readiness_source_contract_preflight(
    *,
    secret_present: bool | None = None,
    runtime_overrides: Mapping[str, Any] | None = None,
    budget_overrides: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return one complete deterministic, redacted, zero-transport report."""

    env = dict(os.environ if environment is None else environment)
    if secret_present is not None:
        if secret_present:
            env[HELIUS_API_KEY_ENVIRONMENT_NAME] = "PRESENT_REDACTED_TEST_VALUE"
        else:
            env.pop(HELIUS_API_KEY_ENVIRONMENT_NAME, None)

    issues: list[str] = []
    try:
        solana = resolve_solana_rpc_configuration(env)
        solana_report = {
            "status": "VALID",
            "origin": solana.origin,
            "endpoint_identity": solana.redacted_identity,
            "authentication": solana.authentication,
            "environment_name": SOLANA_RPC_ENVIRONMENT_NAME,
            "secret_material_recorded": False,
        }
    except SolanaRpcConfigurationError as exc:
        issues.append(f"SOLANA_RPC_CONFIGURATION_INVALID:{exc}")
        solana_report = {
            "status": "INVALID",
            "origin": "UNRESOLVED",
            "endpoint_identity": None,
            "authentication": "UNRESOLVED",
            "environment_name": SOLANA_RPC_ENVIRONMENT_NAME,
            "secret_material_recorded": False,
        }

    profiles = _source_profiles(
        environment=env,
        solana_redacted_identity=str(
            solana_report["endpoint_identity"] or "INVALID_REDACTED"
        ),
        solana_origin=str(solana_report["origin"]),
    )
    runtime = {
        "source_contracts": profiles,
        "runtime_dependency_names": list(ordinary_runtime_dependency_names()),
        "runtime_constants": _runtime_constant_snapshot(),
        "owner_contract": {
            "source_governor": "SOURCE_GOVERNOR",
            "central_scheduler": "CENTRAL_SCHEDULER",
            "direct_source_bypass": False,
        },
    }
    if runtime_overrides:
        _merge_overrides(runtime, deepcopy(dict(runtime_overrides)))

    source_contracts = runtime.get("source_contracts")
    if not isinstance(source_contracts, Mapping):
        source_contracts = {}
        issues.append("SOURCE_PREFLIGHT_GRAPH_MISSING")
    expected_active = set(ordinary_runtime_dependency_names())
    runtime_names = set(runtime.get("runtime_dependency_names") or ())
    preflight_names = {
        name
        for name, profile in source_contracts.items()
        if isinstance(profile, Mapping) and profile.get("active_runtime")
    }
    if runtime_names != expected_active:
        issues.append("ACTIVE_RUNTIME_DEPENDENCY_GRAPH_DRIFT")
    missing = expected_active - preflight_names
    if missing:
        issues.extend(
            f"ACTIVE_RUNTIME_DEPENDENCY_MISSING_FROM_PREFLIGHT:{name}"
            for name in sorted(missing)
        )

    for name, adopted in ORDINARY_OPERATIONAL_SOURCE_CONTRACTS.items():
        profile = source_contracts.get(name)
        if not isinstance(profile, Mapping):
            if adopted.classification == "MANDATORY":
                issues.append(f"MANDATORY_SOURCE_CONTRACT_MISSING:{name}")
            continue
        classification = profile.get("classification")
        if classification not in SOURCE_CLASSIFICATIONS:
            issues.append(f"SOURCE_CLASSIFICATION_INVALID:{name}")
        if classification != adopted.classification:
            issues.append(f"SOURCE_CLASSIFICATION_DRIFT:{name}")
        if adopted.classification == "MANDATORY":
            if not profile.get("free_public_compatible"):
                issues.append(f"MANDATORY_FREE_PUBLIC_CONTRACT_INVALID:{name}")
            if not profile.get("contract_version"):
                issues.append(f"MANDATORY_CONTRACT_VERSION_MISSING:{name}")
            if not profile.get("endpoints"):
                issues.append(f"MANDATORY_ENDPOINT_CONTRACT_MISSING:{name}")
        if profile.get("wallet_or_private_key"):
            issues.append(f"PROHIBITED_WALLET_OR_PRIVATE_KEY_CONTRACT:{name}")
        if profile.get("paid_dependency"):
            issues.append(f"PROHIBITED_PAID_DEPENDENCY:{name}")
        active_contract_text = " ".join(
            [
                str(profile.get("authentication") or ""),
                " ".join(str(value) for value in profile.get("endpoints") or ()),
                " ".join(
                    str(value)
                    for value in profile.get("required_environment") or ()
                ),
            ]
        ).casefold()
        if adopted.active_runtime and any(
            marker in active_contract_text for marker in _PROHIBITED_MARKERS
        ):
            issues.append(f"PROHIBITED_ACTIVE_AUTH_OR_ENDPOINT_CONTRACT:{name}")
        if profile.get("automatic_retries") != 0:
            issues.append(f"AUTOMATIC_RETRY_CONTRACT_DRIFT:{name}")
        if profile.get("endpoint_rotation") is not False:
            issues.append(f"ENDPOINT_ROTATION_CONTRACT_DRIFT:{name}")
        if profile.get("source_owner") != "SOURCE_GOVERNOR":
            issues.append(f"SOURCE_GOVERNOR_BYPASS:{name}")
        if profile.get("scheduler_owner") != "CENTRAL_SCHEDULER":
            issues.append(f"CENTRAL_SCHEDULER_BYPASS:{name}")
        rate = int(profile.get("printer_rate_limit_per_minute") or 0)
        if adopted.active_runtime and adopted.classification != "MANDATORY" and rate < 0:
            issues.append(f"SOURCE_PACING_INVALID:{name}")
        registered_union: set[str] = set()
        for kinds in (profile.get("registered_request_kinds") or {}).values():
            registered_union.update(str(kind) for kind in kinds or ())
        required = set(str(kind) for kind in profile.get("request_kinds") or ())
        if required and not required.issubset(registered_union):
            issues.append(f"SOURCE_REQUEST_KIND_DRIFT:{name}")

    helius_value = str(
        env.get(HELIUS_API_KEY_ENVIRONMENT_NAME, "") or ""
    ).strip()
    if helius_value and any(
        marker in helius_value.casefold() for marker in _PLACEHOLDER_MARKERS
    ):
        issues.append("CONDITIONAL_ENVIRONMENT_PLACEHOLDER:helius_holder_backup")

    constants = runtime.get("runtime_constants") or {}
    expected_constants = constants.get("expected") or {}
    for key, expected_value in expected_constants.items():
        if constants.get(key) != expected_value:
            issues.append(f"RUNTIME_PREFLIGHT_CONSTANT_DRIFT:{key}")
    owners = runtime.get("owner_contract") or {}
    if (
        owners.get("source_governor") != "SOURCE_GOVERNOR"
        or owners.get("central_scheduler") != "CENTRAL_SCHEDULER"
        or owners.get("direct_source_bypass") is not False
    ):
        issues.append("RUNTIME_SOURCE_OWNER_CONTRACT_DRIFT")

    jupiter_rate = int(
        (source_contracts.get("jupiter_entry_exit_quotes") or {}).get(
            "printer_rate_limit_per_minute"
        )
        or 0
    )
    if jupiter_rate != 30 or math.ceil(60 / max(1, jupiter_rate)) < 2:
        issues.append("JUPITER_KEYLESS_PACING_DRIFT")

    budget = {
        "operation_ceiling": OPERATION_CEILING,
        "candidate_cap": READINESS_CANDIDATE_CAP,
        "snapshot_reservation": REQUIRED_READINESS_SNAPSHOT_RESERVATION,
        "contract_snapshot_reservation": READINESS_OPERATION_RESERVATION,
        "pump_worst_case_operations": PUMP_WORST_CASE_OPERATIONS,
        "zero_transport_operations": COMBINED_ZERO_TRANSPORT_VALIDATION,
        "holder_worst_case_operations": (
            READINESS_CANDIDATE_CAP * HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
        ),
    }
    if budget_overrides:
        budget.update(dict(budget_overrides))
    budget["derived_candidate_cap"] = max(
        0,
        (
            budget["operation_ceiling"]
            - budget["pump_worst_case_operations"]
            - budget["zero_transport_operations"]
            - budget["snapshot_reservation"]
        )
        // HOLDER_WORST_CASE_TRANSPORT_OPERATIONS,
    )
    budget["worst_case_total"] = (
        budget["pump_worst_case_operations"]
        + budget["zero_transport_operations"]
        + budget["holder_worst_case_operations"]
        + budget["snapshot_reservation"]
    )
    if (
        budget["operation_ceiling"] != 45
        or budget["pump_worst_case_operations"] != PUMP_WORST_CASE_OPERATIONS
        or budget["candidate_cap"] != budget["derived_candidate_cap"]
        or budget["holder_worst_case_operations"]
        != budget["candidate_cap"] * HOLDER_WORST_CASE_TRANSPORT_OPERATIONS
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
        "primary_source": "geckoterminal",
        "supplemental_15m_source": "geckoterminal",
        "exact_window_seconds": 900,
    }:
        issues.append("READINESS_PROVENANCE_CONTRACT_DRIFT")

    pins = {
        "official_repository_commit": OFFICIAL_REPOSITORY_COMMIT,
        "pump_program_id": PUMP_PROGRAM_ID,
        "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "pump_idl_sha256": PUMP_IDL_SHA256,
        "pumpswap_idl_sha256": PUMPSWAP_IDL_SHA256,
    }
    if any(not value for value in pins.values()):
        issues.append("PUMP_PUMPSWAP_PIN_MISSING")

    return {
        "status": "READY" if not issues else "BLOCKED",
        "issues": sorted(set(issues)),
        "contract_registry_version": CONTRACT_REGISTRY_VERSION,
        "ordinary_runtime_dependencies": sorted(expected_active),
        "sources": dict(source_contracts),
        "solana_rpc": solana_report,
        "pump_pumpswap_pins": pins,
        "owner_contract": owners,
        "runtime_constants": constants,
        "budget": budget,
        "provenance": provenance,
        "helius_secret_present": bool(helius_value),
        "secret_material_recorded": False,
        "external_requests": 0,
    }


def assert_readiness_source_contract_preflight(**kwargs: Any) -> dict[str, Any]:
    report = build_readiness_source_contract_preflight(**kwargs)
    if report["status"] != "READY":
        raise ReadinessSourceContractPreflightError(";".join(report["issues"]))
    return report


__all__ = [
    "PUMP_WORST_CASE_OPERATIONS",
    "READINESS_SELECTED_TOKEN_COUNT",
    "READINESS_CANDIDATE_CAP",
    "ReadinessSourceContractPreflightError",
    "build_readiness_source_contract_preflight",
    "assert_readiness_source_contract_preflight",
]
