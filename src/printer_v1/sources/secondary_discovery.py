"""Fixture-only secondary discovery adapters (V2-9.7D.7B.4B).

Implements adopted GeckoTerminal trending/active-pool and Solana Tracker free
REST trending/top discovery against synthetic fixtures only.

There is deliberately no network client, credential materialization, database
mutation, campaign execution, tracking handoff, or financial capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from printer_v1.scheduler.contracts import JobKind
from printer_v1.sources.governor import can_request_source


# ---------------------------------------------------------------------------
# Source / scheduler ownership (adopted 7B.2 / 7B.3B)
# ---------------------------------------------------------------------------

SCHEDULER_JOB_KIND = JobKind.DISCOVERY_REFRESH.value
SECONDARY_DISCOVERY_CONTRACT_VERSION = "V2-9.7D.7B.4B"

GECKO_SOURCE_NAME = "geckoterminal"
GECKO_TRENDING_REQUEST = "geckoterminal_trending_pool_reference"
GECKO_ACTIVE_REQUEST = "geckoterminal_active_pool_reference"
GECKO_WORK_TYPE = "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE"
GECKO_BASE_URL = "https://api.geckoterminal.com/api/v2"
GECKO_TRENDING_PATH = "/networks/solana/trending_pools"
GECKO_TRENDING_PARAMS = MappingProxyType(
    {"include": "base_token,quote_token,dex", "page": 1, "duration": "1h"}
)
GECKO_ACTIVE_PATH_TEMPLATE = "/networks/solana/pools/{pool_address}"
GECKO_ACTIVE_PARAMS = MappingProxyType(
    {"include": "base_token,quote_token,dex"}
)
GECKO_STALE_AFTER_SECONDS = 180
GECKO_PAGE_POOL_CEILING = 20
GECKO_CYCLE_REQUEST_CEILING = 2
GECKO_RATE_CEILING_PER_MINUTE = 10

DEXSCREENER_SOURCE_NAME = "dexscreener"
DEXSCREENER_FRESH_REQUEST = "dexscreener_fresh_profiles"
# The live adapter has one exact fresh-profile callsite per enrichment pass.
DEXSCREENER_FRESH_REQUEST_CEILING = 1

TRACKER_SOURCE_NAME = "solana_tracker"
TRACKER_TRENDING_REQUEST = "solana_tracker_pumpfun_trending"
TRACKER_TOP_REQUEST = "solana_tracker_pumpfun_top"
TRACKER_WORK_TYPE = "DISCOVERY_SOLANA_TRACKER_TRENDING_TOP"
TRACKER_BASE_URL = "https://data.solanatracker.io"
TRACKER_TRENDING_PATH = "/tokens/trending/1h"
TRACKER_TOP_PATH = "/top-performers/1h"
TRACKER_STALE_AFTER_SECONDS = 180
TRACKER_BODY_CEILING = 100
TRACKER_CYCLE_REQUEST_CEILING = 2
TRACKER_FREE_REQUESTS_PER_MONTH = 10_000
TRACKER_FREE_REQUESTS_PER_SECOND = 3
TRACKER_AUTH_HEADER = "x-api-key"

PUMPFUN_ORIGIN_STATUS = "PROVIDER_LABEL_UNVERIFIED"
NETWORK = "solana"

IDENTITY_KEYS = (
    "provider",
    "channel",
    "network",
    "mint",
    "pool",
    "quote_mint",
    "venue",
    "observed_at",
    "pumpfun_origin_status",
)

DISCARDED_NON_AUTHORITATIVE_FIELDS = (
    "response_order",
    "rank",
    "score",
    "gt_score",
    "risk",
    "risk.score",
    "rugged",
    "promoted",
    "sponsored",
    "popularity",
    "performanceRank",
    "jupiterVerified",
    "holders",
    "buys",
    "sells",
    "volume",
    "volume_usd",
    "price_change_percentage",
    "price",
    "marketCap",
    "reserve_in_usd",
    "name",
    "symbol",
    "image",
    "socials",
)

REQUEST_CEILINGS = MappingProxyType(
    {
        GECKO_TRENDING_REQUEST: 1,
        GECKO_ACTIVE_REQUEST: 1,
        DEXSCREENER_FRESH_REQUEST: DEXSCREENER_FRESH_REQUEST_CEILING,
        TRACKER_TRENDING_REQUEST: 1,
        TRACKER_TOP_REQUEST: 1,
    }
)

REQUEST_TO_SOURCE = MappingProxyType(
    {
        GECKO_TRENDING_REQUEST: GECKO_SOURCE_NAME,
        GECKO_ACTIVE_REQUEST: GECKO_SOURCE_NAME,
        DEXSCREENER_FRESH_REQUEST: DEXSCREENER_SOURCE_NAME,
        TRACKER_TRENDING_REQUEST: TRACKER_SOURCE_NAME,
        TRACKER_TOP_REQUEST: TRACKER_SOURCE_NAME,
    }
)

REQUEST_TO_WORK_TYPE = MappingProxyType(
    {
        GECKO_TRENDING_REQUEST: GECKO_WORK_TYPE,
        GECKO_ACTIVE_REQUEST: GECKO_WORK_TYPE,
        TRACKER_TRENDING_REQUEST: TRACKER_WORK_TYPE,
        TRACKER_TOP_REQUEST: TRACKER_WORK_TYPE,
    }
)


class SecondaryDiscoveryError(RuntimeError):
    """Fail-closed secondary discovery contract violation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True, order=True)
class ProviderObservation:
    """Exact provider-observed identity. No score/rank/order authority."""

    mint: str
    pool: str
    channel: str
    provider: str
    quote_mint: str
    venue: str
    observed_at: str
    network: str = NETWORK
    pumpfun_origin_status: str = PUMPFUN_ORIGIN_STATUS
    activity_interval: str | None = None
    activity_count: int | None = None
    raw_payload_hash: str = ""
    provenance_count: int = 1

    def identity_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "provider": self.provider,
            "channel": self.channel,
            "network": self.network,
            "mint": self.mint,
            "pool": self.pool,
            "quote_mint": self.quote_mint,
            "venue": self.venue,
            "observed_at": self.observed_at,
            "pumpfun_origin_status": self.pumpfun_origin_status,
        }
        if self.activity_interval is not None:
            row["activity_interval"] = self.activity_interval
            row["activity_count"] = self.activity_count
        return row

    def authority_key(self) -> tuple[str, str, str, str]:
        """Canonical candidate authority key (duplicates do not multiply)."""
        return (self.provider, self.channel, self.mint, self.pool)


@dataclass(frozen=True)
class ProviderFailure:
    code: str
    request_kind: str
    detail: str = ""
    request_id: str | None = None
    status_code: int | None = None


@dataclass(frozen=True)
class AccountingSnapshot:
    governed_requests: Mapping[str, int]
    transport_operations: int


@dataclass(frozen=True)
class ProviderLaneResult:
    provider: str
    work_type: str
    status: str
    observations: tuple[ProviderObservation, ...]
    failures: tuple[ProviderFailure, ...]
    discarded_non_authoritative_fields: tuple[str, ...]
    accounting: AccountingSnapshot
    unique_authority_keys: tuple[tuple[str, str, str, str], ...]

    def canonical(self) -> tuple[object, ...]:
        return (
            self.provider,
            self.work_type,
            self.status,
            tuple(obs.identity_dict() for obs in self.observations),
            tuple((f.code, f.request_kind, f.detail, f.status_code) for f in self.failures),
            self.discarded_non_authoritative_fields,
            tuple(sorted(self.accounting.governed_requests.items())),
            self.accounting.transport_operations,
            self.unique_authority_keys,
        )


@dataclass(frozen=True)
class CombinedSecondaryResult:
    geckoterminal: ProviderLaneResult
    solana_tracker: ProviderLaneResult

    def canonical(self) -> tuple[object, ...]:
        return (self.geckoterminal.canonical(), self.solana_tracker.canonical())


@dataclass(frozen=True)
class SolanaTrackerAuthConfig:
    """Secret reference + free-plan quota validation. Never stores a raw key."""

    api_key_secret_ref: str
    free_requests_remaining_month: int
    free_requests_per_second: int = TRACKER_FREE_REQUESTS_PER_SECOND
    free_requests_per_month: int = TRACKER_FREE_REQUESTS_PER_MONTH

    def validate(self) -> None:
        ref = str(self.api_key_secret_ref or "").strip()
        if not ref:
            raise SecondaryDiscoveryError("BLOCKED_AUTH", "missing api_key_secret_ref")
        if ref.lower() in {"redacted", "none", "null", "undefined"}:
            raise SecondaryDiscoveryError("BLOCKED_AUTH", "invalid api_key_secret_ref")
        # Reject values that look like materialised secrets rather than refs.
        if any(ch in ref for ch in (" ", "\n", "\t")):
            raise SecondaryDiscoveryError("BLOCKED_AUTH", "secret material in ref")
        if len(ref) > 128:
            raise SecondaryDiscoveryError("BLOCKED_AUTH", "secret material in ref")
        if type(self.free_requests_remaining_month) is not int:
            raise SecondaryDiscoveryError("BLOCKED_QUOTA", "quota not integer")
        if self.free_requests_remaining_month < TRACKER_CYCLE_REQUEST_CEILING:
            raise SecondaryDiscoveryError("BLOCKED_QUOTA", "insufficient monthly capacity")
        if self.free_requests_per_second != TRACKER_FREE_REQUESTS_PER_SECOND:
            raise SecondaryDiscoveryError("BLOCKED_QUOTA", "free rps contract mismatch")
        if self.free_requests_per_month != TRACKER_FREE_REQUESTS_PER_MONTH:
            raise SecondaryDiscoveryError("BLOCKED_QUOTA", "free monthly contract mismatch")


@dataclass(frozen=True)
class FixtureOperation:
    """One synthetic transport response with explicit Governor/Scheduler ownership."""

    request_id: str
    source_name: str
    request_kind: str
    transport_operation: str
    response: Any
    scheduler_job_kind: str = SCHEDULER_JOB_KIND
    scheduler_work_type: str = ""
    endpoint: str = ""
    receipt_time: str | None = None


def _epoch(value: str) -> float:
    if not isinstance(value, str) or not value:
        raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "missing timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _relationship_mint(resource: Mapping[str, Any], name: str) -> str:
    try:
        value = resource["relationships"][name]["data"]["id"]
    except (KeyError, TypeError) as exc:
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", f"missing {name}") from exc
    if not isinstance(value, str):
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", f"bad {name}")
    prefix = "solana_"
    if not value.startswith(prefix) or len(value) == len(prefix):
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", f"wrong {name}")
    return value[len(prefix) :]


def _gecko_identity(
    resource: Mapping[str, Any],
    *,
    channel: str,
    observed_at: str,
    raw_hash: str,
) -> ProviderObservation:
    if not isinstance(resource, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "pool not object")
    if resource.get("type") != "pool":
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "type not pool")
    attrs = resource.get("attributes")
    if not isinstance(attrs, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing attributes")
    pool = attrs.get("address")
    if not isinstance(pool, str) or not pool:
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "missing pool address")
    if resource.get("id") != f"solana_{pool}":
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "wrong_pool_identity")
    try:
        venue = resource["relationships"]["dex"]["data"]["id"]
    except (KeyError, TypeError) as exc:
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "missing dex") from exc
    if not isinstance(venue, str) or not venue:
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "bad dex")
    mint = _relationship_mint(resource, "base_token")
    quote = _relationship_mint(resource, "quote_token")
    return ProviderObservation(
        mint=mint,
        pool=pool,
        channel=channel,
        provider=GECKO_SOURCE_NAME,
        quote_mint=quote,
        venue=venue,
        observed_at=observed_at,
        raw_payload_hash=raw_hash,
    )


def normalize_gecko_trending(
    body: Any,
    *,
    receipt_time: str,
    evaluated_at: str,
    params: Mapping[str, Any] | None = None,
) -> tuple[ProviderObservation, ...]:
    expected = dict(GECKO_TRENDING_PARAMS)
    if params is not None and dict(params) != expected:
        raise SecondaryDiscoveryError("SCHEMA_OR_LIMIT_DRIFT", "unadopted_trending_request")
    if _epoch(evaluated_at) - _epoch(receipt_time) > GECKO_STALE_AFTER_SECONDS:
        raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "stale_receipt")
    if not isinstance(body, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "body not object")
    data = body.get("data")
    if not isinstance(data, list):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing data list")
    if len(data) > GECKO_PAGE_POOL_CEILING:
        raise SecondaryDiscoveryError("SCHEMA_OR_LIMIT_DRIFT", "page exceeds 20")
    raw_hash = _payload_hash(body)
    rows: dict[tuple[str, str, str, str], ProviderObservation] = {}
    for item in data:
        observation = _gecko_identity(
            item,
            channel="TRENDING_PUMPFUN",
            observed_at=receipt_time,
            raw_hash=raw_hash,
        )
        key = observation.authority_key()
        if key in rows:
            previous = rows[key]
            if previous.identity_dict() != observation.identity_dict():
                raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "conflicting_duplicate")
            rows[key] = ProviderObservation(
                mint=previous.mint,
                pool=previous.pool,
                channel=previous.channel,
                provider=previous.provider,
                quote_mint=previous.quote_mint,
                venue=previous.venue,
                observed_at=previous.observed_at,
                network=previous.network,
                pumpfun_origin_status=previous.pumpfun_origin_status,
                raw_payload_hash=previous.raw_payload_hash,
                provenance_count=previous.provenance_count + 1,
            )
        else:
            rows[key] = observation
    ordered = sorted(rows.values(), key=lambda row: (row.mint, row.pool))
    return tuple(ordered)


def normalize_gecko_active(
    body: Any,
    *,
    receipt_time: str,
    evaluated_at: str,
    requested_pool: str,
) -> ProviderObservation:
    if _epoch(evaluated_at) - _epoch(receipt_time) > GECKO_STALE_AFTER_SECONDS:
        raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "stale_receipt")
    if not isinstance(body, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "body not object")
    resource = body.get("data")
    if not isinstance(resource, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing pool object")
    raw_hash = _payload_hash(body)
    observation = _gecko_identity(
        resource,
        channel="ACTIVE_PUMPFUN",
        observed_at=receipt_time,
        raw_hash=raw_hash,
    )
    if observation.pool != requested_pool:
        raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "requested_pool_mismatch")
    attrs = resource.get("attributes")
    if not isinstance(attrs, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing attributes")
    transactions = attrs.get("transactions")
    if not isinstance(transactions, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing transactions")
    activity = transactions.get("m5")
    if not isinstance(activity, Mapping):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "missing m5")
    buys = activity.get("buys")
    sells = activity.get("sells")
    if type(buys) is not int or type(sells) is not int or min(buys, sells) < 0:
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "malformed_activity")
    if buys + sells <= 0:
        raise SecondaryDiscoveryError("NOT_ACTIVE", "zero m5 activity")
    return ProviderObservation(
        mint=observation.mint,
        pool=observation.pool,
        channel=observation.channel,
        provider=observation.provider,
        quote_mint=observation.quote_mint,
        venue=observation.venue,
        observed_at=observation.observed_at,
        network=observation.network,
        pumpfun_origin_status=observation.pumpfun_origin_status,
        activity_interval="m5",
        activity_count=buys + sells,
        raw_payload_hash=observation.raw_payload_hash,
        provenance_count=observation.provenance_count,
    )


def normalize_tracker_list(
    body: Any,
    *,
    channel: str,
    receipt_time: str,
    evaluated_at: str,
) -> tuple[ProviderObservation, ...]:
    if _epoch(evaluated_at) - _epoch(receipt_time) > TRACKER_STALE_AFTER_SECONDS:
        raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "stale_receipt")
    if not isinstance(body, list):
        raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "body not array")
    if len(body) > TRACKER_BODY_CEILING:
        raise SecondaryDiscoveryError("SCHEMA_OR_LIMIT_DRIFT", "body exceeds 100")
    raw_hash = _payload_hash(body)
    rows: dict[tuple[str, str, str, str], ProviderObservation] = {}
    for item in body:
        if not isinstance(item, Mapping):
            raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "malformed_token_info")
        token = item.get("token")
        pools = item.get("pools")
        if not isinstance(token, Mapping) or not isinstance(pools, list):
            raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "malformed_token_info")
        mint = token.get("mint")
        if not isinstance(mint, str) or not mint:
            raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "missing_mint")
        for pool in pools:
            if not isinstance(pool, Mapping):
                raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "malformed_pool")
            if pool.get("market") != "pumpfun":
                continue
            if pool.get("tokenAddress") != mint:
                continue
            required = ("poolId", "quoteToken", "lastUpdated")
            if any(pool.get(key) in (None, "") for key in required):
                raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "missing_pool_identity")
            updated = pool["lastUpdated"]
            if type(updated) is not int:
                raise SecondaryDiscoveryError("MALFORMED_RESPONSE", "malformed_last_updated")
            # Row-level freshness: stale or materially future pumpfun pools
            # contribute nothing. They must not abort the rest of the body.
            # Receipt-level staleness remains a response-level failure above.
            age = _epoch(evaluated_at) - updated / 1000
            if age < -5 or age > TRACKER_STALE_AFTER_SECONDS:
                continue
            observation = ProviderObservation(
                mint=mint,
                pool=str(pool["poolId"]),
                channel=channel,
                provider=TRACKER_SOURCE_NAME,
                quote_mint=str(pool["quoteToken"]),
                venue="pumpfun",
                observed_at=receipt_time,
                raw_payload_hash=raw_hash,
            )
            key = observation.authority_key()
            if key in rows:
                previous = rows[key]
                if previous.identity_dict() != observation.identity_dict():
                    raise SecondaryDiscoveryError("AMBIGUOUS_IDENTITY", "conflicting_duplicate")
                rows[key] = ProviderObservation(
                    mint=previous.mint,
                    pool=previous.pool,
                    channel=previous.channel,
                    provider=previous.provider,
                    quote_mint=previous.quote_mint,
                    venue=previous.venue,
                    observed_at=previous.observed_at,
                    network=previous.network,
                    pumpfun_origin_status=previous.pumpfun_origin_status,
                    raw_payload_hash=previous.raw_payload_hash,
                    provenance_count=previous.provenance_count + 1,
                )
            else:
                rows[key] = observation
    ordered = sorted(rows.values(), key=lambda row: (row.mint, row.pool))
    return tuple(ordered)


def _classify_transport_failure(
    response: Mapping[str, Any],
    request_kind: str,
    request_id: str,
) -> ProviderFailure:
    status = response.get("status_code")
    failure_type = str(response.get("failure_type") or "")
    if status == 429 or failure_type in {"rate_limited", "RATE_LIMITED"}:
        return ProviderFailure(
            "BLOCKED_QUOTA",
            request_kind,
            "rate_limited",
            request_id=request_id,
            status_code=int(status) if status is not None else 429,
        )
    if status in (401, 403) or failure_type in {"auth", "BLOCKED_AUTH"}:
        return ProviderFailure(
            "BLOCKED_AUTH",
            request_kind,
            "auth_blocked",
            request_id=request_id,
            status_code=int(status) if status is not None else None,
        )
    if failure_type in {"timeout", "transport", "provider_error"} or (
        isinstance(status, int) and status >= 400
    ):
        return ProviderFailure(
            "FAILED_PROVIDER",
            request_kind,
            failure_type or f"http_{status}",
            request_id=request_id,
            status_code=int(status) if status is not None else None,
        )
    return ProviderFailure(
        "FAILED_PROVIDER",
        request_kind,
        failure_type or "transport_failure",
        request_id=request_id,
        status_code=int(status) if isinstance(status, int) else None,
    )


class _Accounting:
    def __init__(self, request_kinds: Sequence[str]) -> None:
        self.request_ids: dict[str, set[str]] = {
            kind: set() for kind in request_kinds
        }
        self.transport_operations = 0

    def consume(self, operation: FixtureOperation) -> None:
        if operation.request_kind not in REQUEST_CEILINGS:
            raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS", "unadopted request kind")
        expected_source = REQUEST_TO_SOURCE[operation.request_kind]
        if operation.source_name != expected_source:
            raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS", "source mismatch")
        recent = len(self.request_ids[operation.request_kind])
        decision = can_request_source(
            operation.source_name,
            operation.request_kind,
            recent,
        )
        if not decision.allowed:
            raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS", decision.reason)
        ids = self.request_ids[operation.request_kind]
        if operation.request_id not in ids:
            if len(ids) >= REQUEST_CEILINGS[operation.request_kind]:
                raise SecondaryDiscoveryError("GOVERNED_REQUEST_CEILING")
            ids.add(operation.request_id)
        self.transport_operations += 1

    def snapshot(self) -> AccountingSnapshot:
        return AccountingSnapshot(
            governed_requests=MappingProxyType(
                {kind: len(ids) for kind, ids in self.request_ids.items()}
            ),
            transport_operations=self.transport_operations,
        )


class FixtureOperationPort:
    """Sequential fixture port that rejects owner bypass before consumption."""

    def __init__(
        self,
        operations: Iterable[FixtureOperation],
        *,
        expected_work_type: str,
        request_kinds: Sequence[str],
    ) -> None:
        self._operations = tuple(operations)
        self._index = 0
        self.expected_work_type = expected_work_type
        self.accounting = _Accounting(request_kinds)

    def peek(self) -> FixtureOperation | None:
        if self._index < len(self._operations):
            return self._operations[self._index]
        return None

    def take(self, request_kind: str, transport_operation: str = "http_get") -> FixtureOperation:
        operation = self.peek()
        if operation is None:
            raise SecondaryDiscoveryError("UNAVAILABLE", f"missing {request_kind} fixture")
        expected_source = REQUEST_TO_SOURCE.get(request_kind)
        if expected_source is None:
            raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS", "unadopted request kind")
        if (
            operation.source_name != expected_source
            or operation.request_kind != request_kind
        ):
            raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS")
        if (
            operation.scheduler_job_kind != SCHEDULER_JOB_KIND
            or operation.scheduler_work_type != self.expected_work_type
        ):
            raise SecondaryDiscoveryError("CENTRAL_SCHEDULER_BYPASS")
        if operation.transport_operation != transport_operation:
            raise SecondaryDiscoveryError(
                "MALFORMED_FIXTURE_OPERATION",
                f"expected {transport_operation}, got {operation.transport_operation}",
            )
        # Ordinary retries and endpoint rotation are forbidden.
        if operation.transport_operation not in {"http_get"}:
            raise SecondaryDiscoveryError("UNADOPTED_TRANSPORT")
        self.accounting.consume(operation)
        self._index += 1
        return operation

    def assert_consumed(self) -> None:
        if self.peek() is not None:
            raise SecondaryDiscoveryError(
                "UNPLANNED_OPERATION",
                self.peek().request_kind if self.peek() else "",
            )


def _lane_status(observations: Sequence[ProviderObservation], failures: Sequence[ProviderFailure]) -> str:
    if observations and not failures:
        return "SUCCEEDED"
    if observations and failures:
        return "PARTIAL"
    if failures:
        return "FAILED"
    return "SUCCEEDED_EMPTY"


def run_geckoterminal_fixture_lane(
    operations: Iterable[FixtureOperation],
    *,
    evaluated_at: str,
    requested_active_pool: str | None = None,
) -> ProviderLaneResult:
    """Run one governed Gecko trending (+ optional active) fixture lane."""
    port = FixtureOperationPort(
        operations,
        expected_work_type=GECKO_WORK_TYPE,
        request_kinds=(GECKO_TRENDING_REQUEST, GECKO_ACTIVE_REQUEST),
    )
    observations: list[ProviderObservation] = []
    failures: list[ProviderFailure] = []

    try:
        trending_op = port.take(GECKO_TRENDING_REQUEST)
        response = trending_op.response
        if isinstance(response, Mapping) and (
            response.get("fixture_status") in {"failure", "rate_limited", "error"}
            or response.get("status_code") not in (None, 200)
        ):
            failures.append(
                _classify_transport_failure(
                    response, GECKO_TRENDING_REQUEST, trending_op.request_id
                )
            )
        else:
            body = response.get("body") if isinstance(response, Mapping) else response
            receipt = (
                trending_op.receipt_time
                or (response.get("receipt_time") if isinstance(response, Mapping) else None)
            )
            params = response.get("params") if isinstance(response, Mapping) else None
            if receipt is None:
                raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "missing receipt_time")
            observations.extend(
                normalize_gecko_trending(
                    body,
                    receipt_time=str(receipt),
                    evaluated_at=evaluated_at,
                    params=params if isinstance(params, Mapping) else dict(GECKO_TRENDING_PARAMS),
                )
            )
    except SecondaryDiscoveryError as exc:
        failures.append(
            ProviderFailure(exc.code, GECKO_TRENDING_REQUEST, exc.detail)
        )

    if requested_active_pool:
        try:
            active_op = port.take(GECKO_ACTIVE_REQUEST)
            response = active_op.response
            if isinstance(response, Mapping) and (
                response.get("fixture_status") in {"failure", "rate_limited", "error"}
                or response.get("status_code") not in (None, 200)
            ):
                failures.append(
                    _classify_transport_failure(
                        response, GECKO_ACTIVE_REQUEST, active_op.request_id
                    )
                )
            else:
                body = response.get("body") if isinstance(response, Mapping) else response
                receipt = (
                    active_op.receipt_time
                    or (response.get("receipt_time") if isinstance(response, Mapping) else None)
                )
                if receipt is None:
                    raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "missing receipt_time")
                observations.append(
                    normalize_gecko_active(
                        body,
                        receipt_time=str(receipt),
                        evaluated_at=evaluated_at,
                        requested_pool=requested_active_pool,
                    )
                )
        except SecondaryDiscoveryError as exc:
            failures.append(ProviderFailure(exc.code, GECKO_ACTIVE_REQUEST, exc.detail))

    try:
        port.assert_consumed()
    except SecondaryDiscoveryError as exc:
        failures.append(ProviderFailure(exc.code, GECKO_TRENDING_REQUEST, exc.detail))

    unique = tuple(sorted({obs.authority_key() for obs in observations}))
    return ProviderLaneResult(
        provider=GECKO_SOURCE_NAME,
        work_type=GECKO_WORK_TYPE,
        status=_lane_status(observations, failures),
        observations=tuple(observations),
        failures=tuple(failures),
        discarded_non_authoritative_fields=DISCARDED_NON_AUTHORITATIVE_FIELDS,
        accounting=port.accounting.snapshot(),
        unique_authority_keys=unique,
    )


def run_solana_tracker_fixture_lane(
    operations: Iterable[FixtureOperation],
    *,
    evaluated_at: str,
    auth: SolanaTrackerAuthConfig,
) -> ProviderLaneResult:
    """Run one governed Solana Tracker trending+top fixture lane."""
    observations: list[ProviderObservation] = []
    failures: list[ProviderFailure] = []
    try:
        auth.validate()
    except SecondaryDiscoveryError as exc:
        empty_accounting = AccountingSnapshot(
            governed_requests=MappingProxyType(
                {TRACKER_TRENDING_REQUEST: 0, TRACKER_TOP_REQUEST: 0}
            ),
            transport_operations=0,
        )
        return ProviderLaneResult(
            provider=TRACKER_SOURCE_NAME,
            work_type=TRACKER_WORK_TYPE,
            status="FAILED",
            observations=(),
            failures=(ProviderFailure(exc.code, TRACKER_TRENDING_REQUEST, exc.detail),),
            discarded_non_authoritative_fields=DISCARDED_NON_AUTHORITATIVE_FIELDS,
            accounting=empty_accounting,
            unique_authority_keys=(),
        )

    port = FixtureOperationPort(
        operations,
        expected_work_type=TRACKER_WORK_TYPE,
        request_kinds=(TRACKER_TRENDING_REQUEST, TRACKER_TOP_REQUEST),
    )

    for request_kind, channel in (
        (TRACKER_TRENDING_REQUEST, "TRENDING_PUMPFUN"),
        (TRACKER_TOP_REQUEST, "TOP_PUMPFUN"),
    ):
        if port.peek() is None:
            break
        try:
            operation = port.take(request_kind)
            response = operation.response
            if isinstance(response, Mapping) and (
                response.get("fixture_status") in {"failure", "rate_limited", "error"}
                or response.get("status_code") not in (None, 200)
            ):
                failures.append(
                    _classify_transport_failure(response, request_kind, operation.request_id)
                )
                continue
            body = response.get("body") if isinstance(response, Mapping) else response
            receipt = (
                operation.receipt_time
                or (response.get("receipt_time") if isinstance(response, Mapping) else None)
            )
            if receipt is None:
                raise SecondaryDiscoveryError("STALE_OR_UNKNOWN", "missing receipt_time")
            observations.extend(
                normalize_tracker_list(
                    body,
                    channel=channel,
                    receipt_time=str(receipt),
                    evaluated_at=evaluated_at,
                )
            )
        except SecondaryDiscoveryError as exc:
            failures.append(ProviderFailure(exc.code, request_kind, exc.detail))

    try:
        port.assert_consumed()
    except SecondaryDiscoveryError as exc:
        failures.append(ProviderFailure(exc.code, TRACKER_TRENDING_REQUEST, exc.detail))

    unique = tuple(sorted({obs.authority_key() for obs in observations}))
    return ProviderLaneResult(
        provider=TRACKER_SOURCE_NAME,
        work_type=TRACKER_WORK_TYPE,
        status=_lane_status(observations, failures),
        observations=tuple(observations),
        failures=tuple(failures),
        discarded_non_authoritative_fields=DISCARDED_NON_AUTHORITATIVE_FIELDS,
        accounting=port.accounting.snapshot(),
        unique_authority_keys=unique,
    )


def run_combined_secondary_fixture(
    *,
    gecko_operations: Iterable[FixtureOperation],
    tracker_operations: Iterable[FixtureOperation],
    evaluated_at: str,
    auth: SolanaTrackerAuthConfig,
    requested_active_pool: str | None = None,
) -> CombinedSecondaryResult:
    """Run both secondary providers independently; failures stay isolated."""
    gecko = run_geckoterminal_fixture_lane(
        gecko_operations,
        evaluated_at=evaluated_at,
        requested_active_pool=requested_active_pool,
    )
    tracker = run_solana_tracker_fixture_lane(
        tracker_operations,
        evaluated_at=evaluated_at,
        auth=auth,
    )
    return CombinedSecondaryResult(geckoterminal=gecko, solana_tracker=tracker)


def fixture_operation(
    *,
    request_id: str,
    request_kind: str,
    response: Any,
    receipt_time: str | None = None,
    endpoint: str = "",
    transport_operation: str = "http_get",
    scheduler_job_kind: str = SCHEDULER_JOB_KIND,
    scheduler_work_type: str | None = None,
    source_name: str | None = None,
) -> FixtureOperation:
    """Build one ownership-tagged fixture operation for tests and callers."""
    if request_kind not in REQUEST_TO_SOURCE:
        raise SecondaryDiscoveryError("SOURCE_GOVERNOR_BYPASS", "unadopted request kind")
    return FixtureOperation(
        request_id=request_id,
        source_name=source_name or REQUEST_TO_SOURCE[request_kind],
        request_kind=request_kind,
        transport_operation=transport_operation,
        response=response,
        scheduler_job_kind=scheduler_job_kind,
        scheduler_work_type=scheduler_work_type or REQUEST_TO_WORK_TYPE[request_kind],
        endpoint=endpoint,
        receipt_time=receipt_time,
    )
