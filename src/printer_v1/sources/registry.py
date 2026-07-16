"""Allowed free-first source registry for Printer V1."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    source_name: str
    purpose: str
    dependency_type: str
    requires_paid_plan: bool
    supports_solana: bool | str
    allowed_request_kinds: tuple[str, ...]
    default_rate_limit_per_minute: int
    stale_after_seconds: int
    retry_after_seconds: int
    max_retries: int
    priority_class: str
    restriction: str | None = None
    notes: str = ""


SOURCE_REGISTRY: dict[str, SourceDefinition] = {
    "dexscreener": SourceDefinition(
        source_name="dexscreener",
        purpose="token/pair discovery and market snapshot reference",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "token_discovery",
            "dexscreener_fresh_profiles",
            "pair_market_snapshot",
            "token_market_snapshot",
            "boosted_token_reference",
        ),
        default_rate_limit_per_minute=60,
        stale_after_seconds=90,
        retry_after_seconds=30,
        max_retries=3,
        priority_class="token_level",
        notes="Free/public reference only; no live client in Phase 2.",
    ),
    "geckoterminal": SourceDefinition(
        source_name="geckoterminal",
        purpose="Solana pool discovery and market confirmation reference",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "geckoterminal_new_pool_discovery",
            "geckoterminal_trending_pool_reference",
            "geckoterminal_ohlcv_15m",
            "geckoterminal_pool_trades_15m",
            # V2-9.5: exact-pair snapshot fallback for a single Solana pool.
            # Same request kind as DexScreener's primary snapshot; the
            # source_name distinguishes the provider. Attempted at most once
            # after an eligible transient DexScreener transport failure.
            "pair_market_snapshot",
        ),
        default_rate_limit_per_minute=30,
        stale_after_seconds=180,
        retry_after_seconds=60,
        max_retries=2,
        priority_class="discovery",
        notes="Free/public Solana pool discovery and exact-pair snapshot fallback; conservative rate limits; no paid tier.",
    ),
    "pumpportal": SourceDefinition(
        source_name="pumpportal",
        purpose="Pump.fun launches and migration stream reference",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=("pumpfun_launch_stream", "pumpfun_migration_stream"),
        default_rate_limit_per_minute=30,
        stale_after_seconds=60,
        retry_after_seconds=30,
        max_retries=3,
        priority_class="discovery",
        notes="Only free launch and migration stream references are allowed.",
    ),
    "alternative_me": SourceDefinition(
        source_name="alternative_me",
        purpose="broad market fear/greed context",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana="not_chain_specific",
        allowed_request_kinds=("fear_greed_context",),
        default_rate_limit_per_minute=10,
        stale_after_seconds=86400,
        retry_after_seconds=300,
        max_retries=2,
        priority_class="broad_context",
        notes="Broad context only; not a token-level source.",
    ),
    "coingecko": SourceDefinition(
        source_name="coingecko",
        purpose="broad market and asset context",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana="not_chain_specific",
        allowed_request_kinds=("broad_market_context", "asset_context"),
        default_rate_limit_per_minute=20,
        stale_after_seconds=300,
        retry_after_seconds=120,
        max_retries=2,
        priority_class="broad_context",
        notes="Free/public or demo context only; no paid dependency.",
    ),
    "defillama": SourceDefinition(
        source_name="defillama",
        purpose="broad market/liquidity/chain context",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana="not_chain_specific",
        allowed_request_kinds=(
            "chain_liquidity_context",
            "tvl_context",
            "dex_volume_context",
        ),
        default_rate_limit_per_minute=20,
        stale_after_seconds=900,
        retry_after_seconds=120,
        max_retries=2,
        priority_class="broad_context",
        notes="Broad liquidity context only.",
    ),
    "goplus": SourceDefinition(
        source_name="goplus",
        purpose="token safety reference where available",
        dependency_type="free_public_or_limited",
        requires_paid_plan=False,
        supports_solana="where_available",
        allowed_request_kinds=("safety_reference",),
        default_rate_limit_per_minute=20,
        stale_after_seconds=300,
        retry_after_seconds=120,
        max_retries=2,
        priority_class="protection",
        notes="Used only where free Solana safety data is available.",
    ),
    "solana_rpc": SourceDefinition(
        source_name="solana_rpc",
        purpose="Solana onchain reference",
        dependency_type="free_or_user_supplied",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "onchain_reference",
            "mint_account_reference",
            "pool_reference",
            "holder_concentration_reference",
            "mint_creation_time_reference",
        ),
        default_rate_limit_per_minute=30,
        stale_after_seconds=120,
        retry_after_seconds=60,
        max_retries=2,
        priority_class="token_level",
        notes="Public or user-supplied free RPC only.",
    ),
    "helius_free": SourceDefinition(
        source_name="helius_free",
        purpose="Solana onchain reference where free tier is available",
        dependency_type="free_tier_optional",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "onchain_reference",
            "mint_account_reference",
            "pool_reference",
        ),
        default_rate_limit_per_minute=30,
        stale_after_seconds=120,
        retry_after_seconds=60,
        max_retries=2,
        priority_class="token_level",
        notes="Optional free-tier source; never required as a paid dependency.",
    ),
    "pumpswap": SourceDefinition(
        source_name="pumpswap",
        purpose="PumpSwap post-migration pool read-only confirmation reference",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "pumpswap_pool_confirmation",
            "pumpswap_migration_pool_reference",
            "pumpswap_liquidity_reference",
            "pumpswap_onchain_pool_confirmation",
            "pumpswap_signature_pool_resolution",
        ),
        default_rate_limit_per_minute=20,
        stale_after_seconds=120,
        retry_after_seconds=60,
        max_retries=2,
        priority_class="discovery",
        restriction="read_only_confirmation",
        notes="Read-only pool confirmation only. No swap, buy, sell, transaction, instruction, or wallet operations allowed.",
    ),
    "jupiter_quote": SourceDefinition(
        source_name="jupiter_quote",
        purpose="paper quote realism reference only",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=("paper_quote_realism",),
        default_rate_limit_per_minute=30,
        stale_after_seconds=30,
        retry_after_seconds=30,
        max_retries=2,
        priority_class="paper_realism",
        restriction="paper_simulation_only",
        notes="Quote realism only; never live execution.",
    ),
}

ALLOWED_SOURCE_NAMES = frozenset(SOURCE_REGISTRY)
