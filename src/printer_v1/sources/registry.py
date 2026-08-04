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
            "candidate_nomination",
            "candidate_market_batch",
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
            "candidate_nomination",
            "candidate_market_batch",
            "geckoterminal_new_pool_discovery",
            "geckoterminal_trending_pool_reference",
            # V2-9.7D.7B.4B: exact active-pool m5 enrichment (fixture-only).
            "geckoterminal_active_pool_reference",
            "geckoterminal_ohlcv_15m",
            "geckoterminal_pool_trades_15m",
            "geckoterminal_readiness_base_snapshot",
            # V2-9.5: exact-pair snapshot fallback for a single Solana pool.
            # Same request kind as DexScreener's primary snapshot; the
            # source_name distinguishes the provider. Attempted at most once
            # after an eligible transient DexScreener transport failure.
            "pair_market_snapshot",
        ),
        default_rate_limit_per_minute=10,
        stale_after_seconds=180,
        retry_after_seconds=60,
        max_retries=0,
        priority_class="discovery",
        notes=(
            "Keyless Public API v2; current public throttling is dynamic/IP-based; "
            "Printer retains a fixed stricter 10/min ceiling, six-second spacing "
            "and zero retries. Token-pools reconciliation is exact-mint-bound."
        ),
    ),
    "birdeye": SourceDefinition(
        source_name="birdeye",
        purpose="optional free Standard-plan Solana new-listing nomination",
        dependency_type="free_account_api_key_optional",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=("birdeye_new_listing_nomination",),
        default_rate_limit_per_minute=30,
        stale_after_seconds=90,
        retry_after_seconds=60,
        max_retries=0,
        priority_class="discovery",
        restriction="free_standard_plan_nomination_only",
        notes=(
            "Optional Birdeye Standard ($0) route; account API-key secret-ref "
            "required, no wallet, no paid fallback, new-listing nomination only."
        ),
    ),
    "solana_tracker": SourceDefinition(
        source_name="solana_tracker",
        purpose="free REST Pump.fun trending and top secondary discovery reference",
        dependency_type="free_public",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=(
            "solana_tracker_pumpfun_trending",
            "solana_tracker_pumpfun_top",
        ),
        # Free plan is 3 rps; local cycle ceiling is 2 requests. Keep a
        # conservative per-minute governor budget for fixture/admission work.
        default_rate_limit_per_minute=10,
        stale_after_seconds=180,
        retry_after_seconds=60,
        max_retries=0,
        priority_class="discovery",
        notes=(
            "Free Data API REST only. Requires secret-ref x-api-key; never paid "
            "Datastream/RPC/swap. Fixture-only until later live-proof lane."
        ),
    ),
    "pumpportal": SourceDefinition(
        source_name="pumpportal",
        purpose="historical Pump.fun locator contract; unavailable to the new foundation",
        dependency_type="unavailable_current_contract",
        requires_paid_plan=False,
        supports_solana=True,
        allowed_request_kinds=("pumpfun_launch_stream", "pumpfun_migration_stream"),
        default_rate_limit_per_minute=30,
        stale_after_seconds=60,
        retry_after_seconds=30,
        max_retries=0,
        priority_class="discovery",
        restriction="candidate_foundation_prohibited_current_contract",
        notes=(
            "Historical request kinds remain reproducible. New foundation use is "
            "prohibited under the current API-key/wallet product contract."
        ),
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
            # V2-9.7E.5 primary: signature-anchored finalized create acquisition
            # on the create-exclusive Pump mint-authority index address.
            "pumpfun_create_index_signature_page",
            "pumpfun_create_index_transaction",
            # Retired primary paths (V2-9.7D.7B.3A .. V2-9.7E.4G). Kept
            # registered so 4A-4H evidence stays reproducible; never consumed
            # on the primary path after V2-9.7E.5.
            "pumpfun_create_event_subscription",
            "pumpfun_create_signature_backfill",
            "pumpfun_create_transaction_reference",
            "pumpfun_origin_signature_reference",
            "pumpfun_origin_transaction_reference",
            # V2-9.8B capacity-neutral candidate-acquisition foundation.
            "candidate_mint_account_batch",
            "pumpfun_migration_signature_page",
            "pumpfun_migration_transaction",
            "pumpswap_pool_account_batch",
            "candidate_pump_migration_signature_lookup",
            "candidate_pump_migration_transaction",
            "candidate_pumpswap_pool_verification",
            # V2-9.8B restored-factory narrow stateless live-tail locator.
            # These are ordinary-run inputs only: no cursor, backfill, recovery
            # or candidate-acquisition authority.
            "restored_pump_migration_signature_page",
            "restored_pump_migration_transaction",
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
            "holder_concentration_reference",
        ),
        default_rate_limit_per_minute=30,
        stale_after_seconds=120,
        retry_after_seconds=60,
        max_retries=0,
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
        max_retries=0,
        priority_class="paper_realism",
        restriction="paper_simulation_only",
        notes=(
            "Keyless api.jup.ag quote realism only at 0.5 RPS; exact identity "
            "validation, no retry, key, wallet, transaction build or execution."
        ),
    ),
}

ALLOWED_SOURCE_NAMES = frozenset(SOURCE_REGISTRY)
