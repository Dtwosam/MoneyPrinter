"""Shared source contracts for the restored ordinary operational graph.

This is the narrow owner for endpoint/configuration literals consumed by both
runtime transports and the zero-I/O source preflight.  It deliberately contains
no source execution and no secret material.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from types import MappingProxyType
from typing import Mapping
from urllib import parse as url_parse


CONTRACT_REGISTRY_VERSION = "V2_9_8B_SOURCE_COMPATIBILITY_RESET_V1"
SOLANA_RPC_ENVIRONMENT_NAME = "PRINTER_SOLANA_RPC_URL"
HELIUS_API_KEY_ENVIRONMENT_NAME = "PRINTER_HELIUS_API_KEY"

OFFICIAL_SOLANA_PUBLIC_RPC_URL = "https://api.mainnet.solana.com"
JUPITER_KEYLESS_QUOTE_URL = "https://api.jup.ag/swap/v1/quote"
DEXSCREENER_PROFILES_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
DEXSCREENER_TOKEN_BATCH_URL = (
    "https://api.dexscreener.com/tokens/v1/solana/{addresses}"
)
DEXSCREENER_EXACT_PAIR_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
)
GECKOTERMINAL_EXACT_PAIR_URL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}"
    "?include=base_token,quote_token,dex"
)
GECKOTERMINAL_OHLCV_15M_URL = (
    "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}"
    "/ohlcv/minute?aggregate=15&limit=2&currency=usd&token=base"
)
GECKOTERMINAL_TRADES_15M_URL = (
    "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}"
    "/trades"
)
GOPLUS_SOLANA_SECURITY_URL = (
    "https://api.gopluslabs.io/api/v1/solana/token_security"
    "?contract_addresses={token_mint}"
)
COINGECKO_MARKET_CONTEXT_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,solana"
    "&vs_currencies=usd"
    "&include_24hr_change=true"
    "&include_24hr_vol=true"
)
HELIUS_FIXED_MAINNET_URL = "https://mainnet.helius-rpc.com/"

SOURCE_CLASSIFICATIONS = frozenset(
    {"MANDATORY", "CONDITIONAL", "DORMANT", "DEFERRED"}
)


class SolanaRpcConfigurationError(ValueError):
    """Raised when the operator RPC configuration cannot be used safely."""


@dataclass(frozen=True)
class SolanaRpcConfiguration:
    url: str
    redacted_identity: str
    origin: str
    authentication: str


@dataclass(frozen=True)
class OperationalSourceContract:
    dependency_name: str
    classification: str
    source_names: tuple[str, ...]
    authentication: str
    endpoints: tuple[str, ...]
    free_public_compatible: bool
    required_environment: tuple[str, ...]
    request_kinds: tuple[str, ...]
    contract_version: str
    printer_rate_limit_per_minute: int
    operation_budget: str
    failure_effect: str
    active_runtime: bool = True
    wallet_or_private_key: bool = False
    paid_dependency: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


_PLACEHOLDER_MARKERS = (
    "your_",
    "changeme",
    "placeholder",
    "<",
    ">",
    "example.com",
)


def _validate_https_url(value: str) -> url_parse.ParseResult:
    text = str(value or "").strip()
    if not text:
        raise SolanaRpcConfigurationError("SOLANA_RPC_URL_EMPTY")
    lowered = text.casefold()
    if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
        raise SolanaRpcConfigurationError("SOLANA_RPC_URL_PLACEHOLDER")
    try:
        parsed = url_parse.urlparse(text)
        port = parsed.port
    except ValueError as exc:
        raise SolanaRpcConfigurationError("SOLANA_RPC_URL_MALFORMED") from exc
    if parsed.scheme.casefold() != "https":
        raise SolanaRpcConfigurationError("SOLANA_RPC_HTTPS_REQUIRED")
    if not parsed.hostname or parsed.fragment:
        raise SolanaRpcConfigurationError("SOLANA_RPC_URL_MALFORMED")
    if parsed.username is not None or parsed.password is not None:
        raise SolanaRpcConfigurationError("SOLANA_RPC_USERINFO_FORBIDDEN")
    if port is not None and not 1 <= port <= 65535:
        raise SolanaRpcConfigurationError("SOLANA_RPC_PORT_INVALID")
    return parsed


def redact_https_url(value: str) -> str:
    """Return a stable secret-free endpoint identity.

    Paths and query values can contain provider account/API-key material, so
    they are represented only by presence flags.
    """

    parsed = _validate_https_url(value)
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = "/<redacted-path>" if parsed.path not in ("", "/") else ""
    query = "?<redacted-query>" if parsed.query else ""
    return f"https://{parsed.hostname}{port}{path}{query}"


def resolve_solana_rpc_configuration(
    environment: Mapping[str, str] | None = None,
) -> SolanaRpcConfiguration:
    env = os.environ if environment is None else environment
    configured = str(env.get(SOLANA_RPC_ENVIRONMENT_NAME, "") or "").strip()
    if configured:
        _validate_https_url(configured)
        return SolanaRpcConfiguration(
            url=configured,
            redacted_identity=redact_https_url(configured),
            origin="OPERATOR_CONFIGURED_APPROVED_HTTPS",
            authentication="ENDPOINT_EMBEDDED_REDACTED_IF_PRESENT",
        )
    _validate_https_url(OFFICIAL_SOLANA_PUBLIC_RPC_URL)
    return SolanaRpcConfiguration(
        url=OFFICIAL_SOLANA_PUBLIC_RPC_URL,
        redacted_identity=OFFICIAL_SOLANA_PUBLIC_RPC_URL,
        origin="BOUNDED_OFFICIAL_PUBLIC_FALLBACK",
        authentication="KEYLESS_PUBLIC",
    )


_CONTRACTS = (
    OperationalSourceContract(
        "direct_pump_migration_locator",
        "MANDATORY",
        ("solana_rpc",),
        "KEYLESS_OR_OPERATOR_ENDPOINT",
        ("SOLANA_RPC_RESOLVED",),
        True,
        (),
        (
            "restored_pump_migration_signature_page",
            "restored_pump_migration_transaction",
        ),
        "PUMP_IDL_PINNED_EXACT_MIGRATE_V1",
        30,
        "one finalized page; at most twelve finalized transaction reads",
        "BLOCKS_BEFORE_LIFECYCLE_OR_HONEST_SUPPLY_STOP",
    ),
    OperationalSourceContract(
        "pump_program_contract",
        "MANDATORY",
        ("solana_rpc",),
        "NONE",
        ("OFFICIAL_PUMP_PROGRAM_ID_AND_PINNED_IDL",),
        True,
        (),
        (),
        "PUMP_IDL_PINNED_EXACT_MIGRATE_V1",
        0,
        "zero transport; pinned static contract",
        "BLOCKS_PREFLIGHT",
    ),
    OperationalSourceContract(
        "pumpswap_exact_join",
        "MANDATORY",
        ("pumpswap", "solana_rpc"),
        "KEYLESS_OR_OPERATOR_ENDPOINT",
        ("SOLANA_RPC_RESOLVED",),
        True,
        (),
        ("pumpswap_signature_pool_resolution",),
        "PUMPSWAP_IDL_PINNED_POOL_JOIN_V1",
        30,
        "one finalized transaction plus bounded account batch per candidate",
        "BLOCKS_CANDIDATE",
    ),
    OperationalSourceContract(
        "solana_transaction_account_verification",
        "MANDATORY",
        ("solana_rpc",),
        "KEYLESS_OR_OPERATOR_ENDPOINT",
        ("SOLANA_RPC_RESOLVED",),
        True,
        (),
        (
            "holder_concentration_reference",
            "restored_pump_migration_transaction",
        ),
        "SOLANA_JSON_RPC_FINALIZED_V1",
        30,
        "admission ceiling 45; no automatic retry",
        "BLOCKS_LOCATOR_OR_CANDIDATE",
    ),
    OperationalSourceContract(
        "dexscreener_latest_profiles",
        "MANDATORY",
        ("dexscreener",),
        "KEYLESS_PUBLIC",
        (DEXSCREENER_PROFILES_URL,),
        True,
        (),
        ("dexscreener_fresh_profiles",),
        "DEXSCREENER_PUBLIC_API_V1",
        60,
        "one request",
        "BLOCKS_DISCOVERY_VISIBILITY_NOT_MIGRATION_AUTHORITY",
    ),
    OperationalSourceContract(
        "dexscreener_token_batch",
        "MANDATORY",
        ("dexscreener",),
        "KEYLESS_PUBLIC",
        (DEXSCREENER_TOKEN_BATCH_URL,),
        True,
        (),
        ("candidate_market_batch",),
        "DEXSCREENER_TOKENS_V1",
        60,
        "one bounded Solana batch",
        "BLOCKS_CANDIDATE_SUPPLY",
    ),
    OperationalSourceContract(
        "dexscreener_exact_pair",
        "MANDATORY",
        ("dexscreener",),
        "KEYLESS_PUBLIC",
        (DEXSCREENER_EXACT_PAIR_URL,),
        True,
        (),
        ("pair_market_snapshot",),
        "DEXSCREENER_LATEST_PAIR_V1",
        60,
        "bounded per-candidate exact-pair requests",
        "PERMITS_ONLY_GOVERNED_GECKOTERMINAL_FALLBACK",
    ),
    OperationalSourceContract(
        "geckoterminal_exact_pair_and_15m",
        "CONDITIONAL",
        ("geckoterminal",),
        "KEYLESS_PUBLIC",
        (
            GECKOTERMINAL_EXACT_PAIR_URL,
            GECKOTERMINAL_OHLCV_15M_URL,
            GECKOTERMINAL_TRADES_15M_URL,
        ),
        True,
        (),
        (
            "pair_market_snapshot",
            "geckoterminal_readiness_base_snapshot",
            "geckoterminal_ohlcv_15m",
            "geckoterminal_pool_trades_15m",
        ),
        "GECKOTERMINAL_API_V2_20230203",
        10,
        "one attempt per endpoint; six-second spacing",
        "BLOCKS_CANDIDATE_OR_DIRTIES_WINDOW",
    ),
    OperationalSourceContract(
        "goplus_safety",
        "CONDITIONAL",
        ("goplus",),
        "KEYLESS_PUBLIC",
        (GOPLUS_SOLANA_SECURITY_URL,),
        True,
        (),
        ("safety_reference",),
        "GOPLUS_SOLANA_SECURITY_V1",
        20,
        "one request per evaluated token",
        "EXPLICIT_RISK_BLOCKS_CANDIDATE_OTHERWISE_UNKNOWN",
    ),
    OperationalSourceContract(
        "solana_holder_evidence",
        "CONDITIONAL",
        ("solana_rpc",),
        "KEYLESS_OR_OPERATOR_ENDPOINT",
        ("SOLANA_RPC_RESOLVED",),
        True,
        (),
        ("holder_concentration_reference",),
        "SOLANA_HOLDER_FINALIZED_V1",
        30,
        "two finalized methods per candidate",
        "PERMITS_ONLY_CONDITIONAL_HELIUS_BACKUP",
    ),
    OperationalSourceContract(
        "helius_holder_backup",
        "CONDITIONAL",
        ("helius_free",),
        "QUERY_API_KEY_WHEN_SELECTED",
        (HELIUS_FIXED_MAINNET_URL,),
        True,
        (HELIUS_API_KEY_ENVIRONMENT_NAME,),
        ("holder_concentration_reference",),
        "HELIUS_STANDARD_RPC_HOLDER_V1",
        30,
        "two methods; zero retry",
        "CANDIDATE_REMAINS_UNKNOWN_OR_BLOCKED",
    ),
    OperationalSourceContract(
        "coingecko_context",
        "MANDATORY",
        ("coingecko",),
        "KEYLESS_PUBLIC",
        (COINGECKO_MARKET_CONTEXT_URL,),
        True,
        (),
        ("broad_market_context",),
        "COINGECKO_PUBLIC_API_V3",
        20,
        "one request per governed context collection",
        "DIRTIES_WINDOW_OR_FAILS_CLOSED",
    ),
    OperationalSourceContract(
        "jupiter_entry_exit_quotes",
        "MANDATORY",
        ("jupiter_quote",),
        "KEYLESS_PUBLIC",
        (JUPITER_KEYLESS_QUOTE_URL,),
        True,
        (),
        ("paper_quote_realism",),
        "JUPITER_METIS_QUOTE_V1_KEYLESS_2026_07",
        30,
        "entry and exit; minimum two-second spacing; zero retry",
        "DIRTIES_PAPER_REALISM_EVIDENCE",
    ),
    OperationalSourceContract(
        "pumpportal",
        "DEFERRED",
        ("pumpportal",),
        "PROHIBITED_IN_ORDINARY_RUN",
        (),
        False,
        (),
        (),
        "HISTORICAL_ONLY",
        0,
        "zero ordinary-run operations",
        "NO_FALLBACK",
        active_runtime=False,
    ),
    OperationalSourceContract(
        "candidate_acquisition_cursor_recovery",
        "DEFERRED",
        (),
        "NOT_APPLICABLE",
        (),
        True,
        (),
        (),
        "DEFERRED_EXPERIMENTAL",
        0,
        "zero ordinary-run operations",
        "NO_RUNTIME_AUTHORITY",
        active_runtime=False,
    ),
    OperationalSourceContract(
        "alternative_me_defillama",
        "DORMANT",
        ("alternative_me", "defillama"),
        "KEYLESS_PUBLIC",
        (),
        True,
        (),
        (),
        "REGISTERED_NOT_IN_ORDINARY_GRAPH",
        0,
        "zero ordinary-run operations",
        "NO_ORDINARY_RUN_EFFECT",
        active_runtime=False,
    ),
)

ORDINARY_OPERATIONAL_SOURCE_CONTRACTS = MappingProxyType(
    {contract.dependency_name: contract for contract in _CONTRACTS}
)


def ordinary_runtime_dependency_names() -> tuple[str, ...]:
    return tuple(
        contract.dependency_name
        for contract in _CONTRACTS
        if contract.active_runtime
    )


__all__ = [
    "CONTRACT_REGISTRY_VERSION",
    "SOLANA_RPC_ENVIRONMENT_NAME",
    "HELIUS_API_KEY_ENVIRONMENT_NAME",
    "OFFICIAL_SOLANA_PUBLIC_RPC_URL",
    "JUPITER_KEYLESS_QUOTE_URL",
    "DEXSCREENER_PROFILES_URL",
    "DEXSCREENER_TOKEN_BATCH_URL",
    "DEXSCREENER_EXACT_PAIR_URL",
    "GECKOTERMINAL_EXACT_PAIR_URL",
    "GECKOTERMINAL_OHLCV_15M_URL",
    "GECKOTERMINAL_TRADES_15M_URL",
    "GOPLUS_SOLANA_SECURITY_URL",
    "COINGECKO_MARKET_CONTEXT_URL",
    "HELIUS_FIXED_MAINNET_URL",
    "SOURCE_CLASSIFICATIONS",
    "SolanaRpcConfigurationError",
    "SolanaRpcConfiguration",
    "OperationalSourceContract",
    "redact_https_url",
    "resolve_solana_rpc_configuration",
    "ORDINARY_OPERATIONAL_SOURCE_CONTRACTS",
    "ordinary_runtime_dependency_names",
]
