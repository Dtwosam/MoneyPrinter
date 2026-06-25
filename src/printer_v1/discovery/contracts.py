"""Discovery labels for Printer V1 Phase 5."""

from enum import StrEnum


class DiscoveryPayloadState(StrEnum):
    VALID_PAYLOAD = "VALID_PAYLOAD"
    PARTIAL_PAYLOAD = "PARTIAL_PAYLOAD"
    MISSING_CRITICAL_FIELDS = "MISSING_CRITICAL_FIELDS"
    UNSUPPORTED_CHAIN = "UNSUPPORTED_CHAIN"
    UNSUPPORTED_PAIR = "UNSUPPORTED_PAIR"
    STALE_SOURCE_DATA = "STALE_SOURCE_DATA"
    CONFLICTING_SOURCE_DATA = "CONFLICTING_SOURCE_DATA"


class DiscoveryCandidateLabel(StrEnum):
    NEW_CANDIDATE = "NEW_CANDIDATE"
    EXISTING_TOKEN_NEW_PAIR = "EXISTING_TOKEN_NEW_PAIR"
    EXISTING_TOKEN_EXISTING_PAIR = "EXISTING_TOKEN_EXISTING_PAIR"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"
    INSTANT_REJECT = "INSTANT_REJECT"
    WATCH_ONLY_CANDIDATE = "WATCH_ONLY_CANDIDATE"
    TRACK_NORMAL_CANDIDATE = "TRACK_NORMAL_CANDIDATE"
    TRACK_FAST_CANDIDATE = "TRACK_FAST_CANDIDATE"


class DiscoveryOutputAction(StrEnum):
    IGNORE = "IGNORE"
    WATCH_ONLY = "WATCH_ONLY"
    TRACK_NORMAL = "TRACK_NORMAL"
    TRACK_FAST = "TRACK_FAST"
    INSTANT_REJECT_MEMORY_ONLY = "INSTANT_REJECT_MEMORY_ONLY"


class DiscoveryChannelLabel(StrEnum):
    """Source channel labels for discovery candidates.

    These are informational labels that record how and from which channel a
    candidate arrived. A channel label is a fact about intake origin, not a
    selection criterion. Hard numeric gates in the classifier determine
    eligibility; channel labels are stored for audit and context only.
    """

    DEXSCREENER_SEARCH = "DEXSCREENER_SEARCH"
    DEXSCREENER_LATEST_BOOSTED = "DEXSCREENER_LATEST_BOOSTED"
    DEXSCREENER_TOP_BOOSTED = "DEXSCREENER_TOP_BOOSTED"
    GECKOTERMINAL_NEW_POOL = "GECKOTERMINAL_NEW_POOL"
    GECKOTERMINAL_TRENDING_POOL = "GECKOTERMINAL_TRENDING_POOL"
    PUMPFUN_NEW_TOKEN = "PUMPFUN_NEW_TOKEN"
    PUMPFUN_MIGRATION = "PUMPFUN_MIGRATION"
    PUMPSWAP_GRADUATED = "PUMPSWAP_GRADUATED"
    RAYDIUM_POOL_CONFIRMATION = "RAYDIUM_POOL_CONFIRMATION"
    MANUAL_BASELINE = "MANUAL_BASELINE"
    BASELINE_MEMORY = "BASELINE_MEMORY"
    # Pump.fun public surface labels — metadata/provenance only.
    # These are audit labels for operator-supplied fixture data.
    # They never become selection criteria, numeric measurements, or
    # ordering keys. Hard eligibility gates apply regardless of label.
    PUMPFUN_TRENDING_NOW = "PUMPFUN_TRENDING_NOW"
    PUMPFUN_TOP_COINS = "PUMPFUN_TOP_COINS"
    PUMPFUN_MOVERS = "PUMPFUN_MOVERS"
    PUMPFUN_MAYHEM = "PUMPFUN_MAYHEM"
    PUMPFUN_NEW = "PUMPFUN_NEW"
    PUMPFUN_LIVE = "PUMPFUN_LIVE"
    PUMPFUN_MARKET_CAP = "PUMPFUN_MARKET_CAP"
    PUMPFUN_AGENTS = "PUMPFUN_AGENTS"
    PUMPFUN_OLDEST = "PUMPFUN_OLDEST"
    PUMPFUN_LAST_TRADE = "PUMPFUN_LAST_TRADE"
    PUMPFUN_CHARITIES = "PUMPFUN_CHARITIES"


DISCOVERY_PAYLOAD_STATES = tuple(DiscoveryPayloadState)
DISCOVERY_CANDIDATE_LABELS = tuple(DiscoveryCandidateLabel)
DISCOVERY_OUTPUT_ACTIONS = tuple(DiscoveryOutputAction)
DISCOVERY_CHANNEL_LABELS = tuple(DiscoveryChannelLabel)
