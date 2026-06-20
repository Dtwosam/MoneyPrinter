"""Locked Printer V1 rules for Phase 0."""

PRINTER_CHAIN = "solana"
PRINTER_MODE = "paper_only"

V1_BANS = frozenset(
    {
        "live_trading",
        "wallet_connection",
        "private_keys",
        "real_funds",
        "live_execution",
        "paid_api_dependency",
        "scoring_system",
        "multi_chain_logic",
        "engine_direct_external_source_calls",
        "engine_independent_timing_loops",
        "paper_buy_without_clean_memory_comparison",
    }
)


def is_banned_v1_capability(name: str) -> bool:
    """Return whether a capability is explicitly banned in Printer V1."""
    return name in V1_BANS
