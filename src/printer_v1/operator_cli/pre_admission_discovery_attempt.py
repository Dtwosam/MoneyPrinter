"""Durable one-shot ownership for discovery before proposed cycle 2 exists."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import re
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.contracts.rules import PRINTER_CHAIN
from printer_v1.discovery.classifier import (
    choose_tracking_lane,
    classify_discovery_candidate,
)
from printer_v1.discovery.contracts import DiscoveryChannelLabel
from printer_v1.discovery.parser import normalize_candidates
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


PERSISTENCE_DIAGNOSTIC_SCHEMA = "PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1"
PERSISTENCE_FAILURE_CODE = "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED"
DIAGNOSTIC_UNAVAILABLE = "DIAGNOSTIC_UNAVAILABLE"
_DIAGNOSTIC_FIELDS = frozenset(
    {
        "diagnostic_schema",
        "failure_code",
        "producer_code",
        "failure_category",
        "operation_phase",
        "exception_type",
        "reason_code",
    }
)
_PERSISTENCE_PRODUCERS = frozenset(
    {
        "RUNNING_ATTEMPT_FAILURE_TERMINALIZATION",
        "SOURCE_EVIDENCE_LINK_ARGUMENT",
        "SOURCE_EVIDENCE_LINK_INSERT",
        "FROZEN_EVIDENCE_PROJECTION",
        "FROZEN_LANE_CLASSIFICATION",
        "PAIR_SHAPE_VALIDATION",
        "FROZEN_LANE_FIELD_VALIDATION",
        "PAIR_ATTEMPT_RUNNING_PREREQUISITE",
        "PAIR_ITEM_INSERT",
        "PAIR_READY_TRANSITION",
        "PRE_ADMISSION_PERSISTENCE_UNKNOWN",
    }
)
_PERSISTENCE_CATEGORIES = frozenset(
    {
        "APPLICATION_VALIDATION",
        "PREREQUISITE_MISSING",
        "CONSTRAINT_OR_INTEGRITY",
        "SQLITE_BUSY_OR_LOCK",
        "SQLITE_IO_OR_OPERATIONAL",
        "UNKNOWN_PERSISTENCE_FAILURE",
    }
)
_PERSISTENCE_PHASES = frozenset(
    {
        "TERMINALIZATION",
        "SOURCE_LINK",
        "FROZEN_CARRIER",
        "PAIR_PRECHECK",
        "PAIR_ITEM_1",
        "PAIR_ITEM_2",
        "PAIR_READY",
        "UNKNOWN_PHASE",
    }
)
_EXCEPTION_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,96}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class PreAdmissionPersistenceDiagnostic:
    diagnostic_schema: str
    failure_code: str
    producer_code: str
    failure_category: str
    operation_phase: str
    exception_type: str
    reason_code: str

    def __post_init__(self) -> None:
        if self.diagnostic_schema != PERSISTENCE_DIAGNOSTIC_SCHEMA:
            raise ValueError("invalid diagnostic schema")
        if self.failure_code != PERSISTENCE_FAILURE_CODE:
            raise ValueError("invalid diagnostic failure code")
        if self.producer_code not in _PERSISTENCE_PRODUCERS:
            raise ValueError("invalid diagnostic producer")
        if self.failure_category not in _PERSISTENCE_CATEGORIES:
            raise ValueError("invalid diagnostic failure category")
        if self.operation_phase not in _PERSISTENCE_PHASES:
            raise ValueError("invalid diagnostic operation phase")
        if _EXCEPTION_TYPE_PATTERN.fullmatch(self.exception_type) is None:
            raise ValueError("invalid diagnostic exception type")
        if _REASON_CODE_PATTERN.fullmatch(self.reason_code) is None:
            raise ValueError("invalid diagnostic reason code")
        if len(self.canonical_json()) > 1536:
            raise ValueError("diagnostic exceeds Scheduler last_error bound")

    def as_dict(self) -> dict[str, str]:
        return {
            "diagnostic_schema": self.diagnostic_schema,
            "failure_code": self.failure_code,
            "producer_code": self.producer_code,
            "failure_category": self.failure_category,
            "operation_phase": self.operation_phase,
            "exception_type": self.exception_type,
            "reason_code": self.reason_code,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_mapping(cls, value: object) -> "PreAdmissionPersistenceDiagnostic":
        if (
            not isinstance(value, Mapping)
            or set(value) != _DIAGNOSTIC_FIELDS
            or any(not isinstance(value[key], str) for key in _DIAGNOSTIC_FIELDS)
        ):
            raise ValueError("diagnostic key set invalid")
        return cls(**{key: value[key] for key in _DIAGNOSTIC_FIELDS})  # type: ignore[arg-type]


class PreAdmissionAttemptError(ValueError):
    """Fail-closed pre-admission persistence contract violation."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic: PreAdmissionPersistenceDiagnostic | None = None,
    ) -> None:
        super().__init__(message)
        self._diagnostic = diagnostic

    @property
    def diagnostic(self) -> PreAdmissionPersistenceDiagnostic | None:
        return self._diagnostic


def _safe_exception_type(exc: BaseException) -> str:
    name = exc.__class__.__name__
    return name if _EXCEPTION_TYPE_PATTERN.fullmatch(name) else "Exception"


def _safe_reason_code(exc: BaseException) -> str:
    if isinstance(exc, sqlite3.Error):
        name = getattr(exc, "sqlite_errorname", None)
        if isinstance(name, str) and _REASON_CODE_PATTERN.fullmatch(name):
            return name
        return "SQLITE_ERROR_NAME_UNAVAILABLE"
    if isinstance(exc, PreAdmissionAttemptError):
        code = str(exc)
        if _REASON_CODE_PATTERN.fullmatch(code):
            return code
        return "UNCLASSIFIED_PRE_ADMISSION_ERROR"
    return "UNKNOWN_PERSISTENCE_REASON"


def _failure_category(exc: BaseException) -> str:
    if isinstance(exc, sqlite3.IntegrityError):
        return "CONSTRAINT_OR_INTEGRITY"
    if isinstance(exc, sqlite3.Error):
        primary = int(getattr(exc, "sqlite_errorcode", 0) or 0) & 0xFF
        if primary in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
            return "SQLITE_BUSY_OR_LOCK"
        return "SQLITE_IO_OR_OPERATIONAL"
    if isinstance(exc, PreAdmissionAttemptError):
        return "APPLICATION_VALIDATION"
    return "UNKNOWN_PERSISTENCE_FAILURE"


def pre_admission_persistence_diagnostic_for_exception(
    exc: BaseException,
    *,
    producer_code: str = "PRE_ADMISSION_PERSISTENCE_UNKNOWN",
    operation_phase: str = "UNKNOWN_PHASE",
    failure_category: str | None = None,
) -> PreAdmissionPersistenceDiagnostic:
    if isinstance(exc, PreAdmissionAttemptError) and exc.diagnostic is not None:
        return exc.diagnostic
    unknown_boundary = (
        producer_code == "PRE_ADMISSION_PERSISTENCE_UNKNOWN"
        and failure_category is None
    )
    return PreAdmissionPersistenceDiagnostic(
        diagnostic_schema=PERSISTENCE_DIAGNOSTIC_SCHEMA,
        failure_code=PERSISTENCE_FAILURE_CODE,
        producer_code=producer_code,
        failure_category=(
            "UNKNOWN_PERSISTENCE_FAILURE"
            if unknown_boundary
            else failure_category or _failure_category(exc)
        ),
        operation_phase=operation_phase,
        exception_type=_safe_exception_type(exc),
        reason_code=(
            "UNKNOWN_PERSISTENCE_REASON"
            if unknown_boundary
            else _safe_reason_code(exc)
        ),
    )


def _annotate_persistence_error(
    exc: BaseException,
    *,
    producer_code: str,
    operation_phase: str,
    failure_category: str | None = None,
) -> PreAdmissionAttemptError:
    if isinstance(exc, PreAdmissionAttemptError) and exc.diagnostic is not None:
        return exc
    diagnostic = pre_admission_persistence_diagnostic_for_exception(
        exc,
        producer_code=producer_code,
        operation_phase=operation_phase,
        failure_category=failure_category,
    )
    message = str(exc) if isinstance(exc, PreAdmissionAttemptError) else diagnostic.reason_code
    return PreAdmissionAttemptError(message, diagnostic=diagnostic)


class PreAdmissionAttemptState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAIR_READY = "PAIR_READY"
    NO_PAIR = "NO_PAIR"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    CONSUMED = "CONSUMED"


FROZEN_LANE_DECISION_OWNER = "classify_discovery_candidate+choose_tracking_lane"
_ALLOWED_FROZEN_TRACKING_LANES = frozenset(
    {
        TokenLifecycleState.TRACK_FAST.value,
        TokenLifecycleState.TRACK_NORMAL.value,
    }
)
_DISCOVERY_CHANNEL_VALUES = frozenset(label.value for label in DiscoveryChannelLabel)
_PROVENANCE_TO_SOURCE_CHANNEL = {
    "LATEST_PUMPFUN": DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
    "TOP_PUMPFUN": DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
    "TRENDING_PUMPFUN": DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
    "ACTIVE_PUMPFUN": DiscoveryChannelLabel.PUMPFUN_MIGRATION.value,
    "LATEST_GRADUATED": DiscoveryChannelLabel.PUMPSWAP_GRADUATED.value,
    "PERSISTED_GRADUATED": DiscoveryChannelLabel.PUMPSWAP_GRADUATED.value,
    "FRESH_AGGREGATOR_PROTOCOL_CONFIRMED": (
        DiscoveryChannelLabel.DEXSCREENER_LATEST_PROFILES.value
    ),
}


@dataclass(frozen=True)
class PreAdmissionDiscoveryAttempt:
    attempt_id: str
    campaign_id: str
    campaign_run_id: str
    configuration_id: str
    authoritative_factory_run_id: str
    proposed_cycle_ordinal: int
    proposed_cycle_id: str
    scheduler_job_id: int
    cycle_cutoff: datetime
    evaluated_at: datetime
    selection_seed_identity: str
    state: PreAdmissionAttemptState
    first_terminal_cause: str | None
    terminal_at: datetime | None
    consumed_cycle_id: str | None
    consumed_at: datetime | None


@dataclass(frozen=True)
class PreAdmissionAttemptItem:
    attempt_id: str
    slot_ordinal: int
    token_identity: str
    token_row_id: int
    mint_identity: str
    pair_identity: str
    pair_row_id: int
    lifecycle_identity: str
    canonical_market_identity: str
    canonical_pool_identity: str
    canonical_evidence_json: str
    canonical_evidence_hash: str
    evidence_version: str
    observed_at: datetime
    channel_labels: tuple[str, ...] = ()
    # Frozen cadence-lane provenance. Optional only until
    # attach_frozen_tracking_lane / persist validation; PAIR_READY rows require
    # a complete set (migration 060 + persist fail-closed checks).
    frozen_tracking_lane: str | None = None
    frozen_discovery_action: str | None = None
    frozen_discovery_label: str | None = None
    frozen_classification_reason: str | None = None
    frozen_lane_evidence_hash: str | None = None
    frozen_lane_decided_at: datetime | None = None
    frozen_lane_decision_owner: str | None = None


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PreAdmissionAttemptError(f"{label.upper()}_INVALID")
    return value


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PreAdmissionAttemptError(f"{label.upper()}_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime, label: str) -> str:
    return _utc(value, label).isoformat()


def _parse_timestamp(value: object, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise PreAdmissionAttemptError(f"{label.upper()}_MALFORMED") from exc
    return _utc(parsed, label)


def _optional_timestamp(value: object, label: str) -> datetime | None:
    return None if value is None else _parse_timestamp(value, label)


def _decode_evidence_candidate(canonical_evidence_json: str) -> dict[str, Any]:
    try:
        decoded = json.loads(canonical_evidence_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PreAdmissionAttemptError("FROZEN_LANE_EVIDENCE_INVALID") from exc
    if not isinstance(decoded, dict):
        raise PreAdmissionAttemptError("FROZEN_LANE_EVIDENCE_INVALID")
    nested = decoded.get("candidate")
    if isinstance(nested, dict):
        return dict(nested)
    return dict(decoded)


def _mapped_source_channel(
    candidate: Mapping[str, Any], *, channel_labels: Sequence[str]
) -> str | None:
    raw_channel = candidate.get("source_channel")
    if isinstance(raw_channel, str) and raw_channel.strip():
        return raw_channel.strip()
    provenance = candidate.get("provenance")
    if isinstance(provenance, str) and provenance.strip():
        exact = provenance.strip()
        if exact in _DISCOVERY_CHANNEL_VALUES:
            return exact
        mapped = _PROVENANCE_TO_SOURCE_CHANNEL.get(exact)
        if mapped is not None:
            return mapped
    for label in channel_labels:
        if not isinstance(label, str) or not label.strip():
            continue
        exact = label.strip()
        if exact in _DISCOVERY_CHANNEL_VALUES:
            return exact
        mapped = _PROVENANCE_TO_SOURCE_CHANNEL.get(exact)
        if mapped is not None:
            return mapped
    return None


def _candidate_liquidity_usd(candidate: Mapping[str, Any]) -> Any:
    liquidity_usd = candidate.get("liquidity_usd")
    if liquidity_usd is not None:
        return liquidity_usd
    liquidity = candidate.get("liquidity")
    if isinstance(liquidity, Mapping):
        return liquidity.get("liquidity_usd")
    return None


def _reject_liquidity_evidence_time_before_proving_response(
    connection: sqlite3.Connection,
    *,
    candidate: Mapping[str, Any],
) -> None:
    """Fail closed when retained liquidity claims unusable proving provenance.

    A claimed proving response must bind the exact
    ``(source_name, source_request_id, source_response_id)`` tuple, and Dex/Gecko
    exact-pool claims must match mint/pair via the existing
    ``normalize_candidates`` helper. Invalid provenance fails closed and must not
    fall through to WATCH_ONLY. When observed time is present, it must not
    precede the proving response. Linked-market temporal eligibility is unchanged.
    """
    from printer_v1.discovery.permanent_discovery_availability import (
        require_proving_liquidity_response_received_at,
    )

    liquidity = candidate.get("liquidity")
    blob: Mapping[str, Any]
    if isinstance(liquidity, Mapping):
        blob = liquidity
    else:
        blob = candidate
    response_id_raw = blob.get("source_response_id")
    if response_id_raw is None:
        return
    observed_raw = blob.get("liquidity_observed_at")
    mint = str(
        blob.get("mint")
        or blob.get("base_mint")
        or candidate.get("token_mint")
        or candidate.get("mint_identity")
        or ""
    ).strip() or None
    pair = str(
        blob.get("pool")
        or blob.get("pair_address")
        or candidate.get("pair_address")
        or candidate.get("pair_identity")
        or ""
    ).strip() or None
    try:
        received_raw = require_proving_liquidity_response_received_at(
            connection,
            source_response_id=response_id_raw,
            source_request_id=blob.get("source_request_id"),
            source_name=blob.get("source_name") or blob.get("source"),
            mint_identity=mint,
            pair_identity=pair,
            observed_at=(
                None if observed_raw is None else str(observed_raw)
            ),
        )
    except ValueError as exc:
        raise PreAdmissionAttemptError(
            "LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"
        ) from exc
    if observed_raw is None:
        return
    try:
        observed = _parse_timestamp(observed_raw, "liquidity_observed_at")
        received = _parse_timestamp(received_raw, "source_response_received_at")
    except PreAdmissionAttemptError as exc:
        raise PreAdmissionAttemptError(
            "LIQUIDITY_PROVING_SOURCE_RESPONSE_INVALID"
        ) from exc
    if observed < received:
        raise PreAdmissionAttemptError(
            "LIQUIDITY_EVIDENCE_TIME_PRECEDES_SOURCE_RESPONSE"
        )


_CLASSIFIER_MARKET_FIELDS = (
    "price_usd",
    "liquidity_usd",
    "volume_5m",
    "volume_1h",
    "volume_24h",
    "txns_5m",
    "txns_1h",
    "txns_24h",
)
_LINKED_MARKET_SOURCES = frozenset({"dexscreener", "geckoterminal"})


def _linked_exact_market_candidate_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    mint_identity: str,
    pair_identity: str,
    observed_at: datetime,
) -> dict[str, Any] | None:
    """Read the newest already-linked exact-pair market response, if any.

    This is a projection-only helper. It performs no source request and no DB
    write. Only COMPLETE DexScreener/GeckoTerminal responses already linked to
    this exact pre-admission attempt may supplement missing classifier fields.
    """
    exact_attempt = _required(attempt_id, "attempt_id")
    mint = _required(mint_identity, "mint_identity")
    pair = _required(pair_identity, "pair_identity")
    instant = _utc(observed_at, "observed_at")
    rows = connection.execute(
        """
        SELECT l.link_ordinal, q.source_name, r.normalized_payload_json,
               r.received_at, r.source_status
          FROM printer_pre_admission_discovery_attempt_source_links AS l
          JOIN printer_source_requests AS q ON q.id=l.source_request_id
          JOIN printer_source_responses AS r ON r.id=l.source_response_id
         WHERE l.attempt_id=?
           AND l.source_response_id IS NOT NULL
         ORDER BY r.received_at ASC, l.link_ordinal ASC, r.id ASC
        """,
        (exact_attempt,),
    ).fetchall()
    exact_candidates: list[tuple[datetime, int, dict[str, Any]]] = []
    for row in rows:
        source_name = str(row[1] or "").strip()
        source_status = str(row[4] or "").strip().upper()
        if source_name not in _LINKED_MARKET_SOURCES or source_status != "COMPLETE":
            continue
        try:
            payload = json.loads(str(row[2]))
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        try:
            normalized = normalize_candidates(source_name, payload, now=instant)
        except (TypeError, ValueError):
            continue
        exact = [
            dict(candidate)
            for candidate in normalized
            if str(candidate.get("chain") or "").casefold() == PRINTER_CHAIN
            and str(candidate.get("token_mint") or "") == mint
            and str(candidate.get("pair_address") or "") == pair
        ]
        # Ambiguous exact identity is never a lawful supplement.
        if len(exact) != 1:
            continue
        try:
            received = _parse_timestamp(row[3], "linked_source_response_received_at")
        except PreAdmissionAttemptError:
            continue
        if received > instant:
            continue
        exact_candidates.append((received, int(row[0]), exact[0]))
    if not exact_candidates:
        return None
    exact_candidates.sort(key=lambda entry: (entry[0], entry[1]))
    return dict(exact_candidates[-1][2])


def _merge_missing_classifier_evidence(
    candidate: Mapping[str, Any],
    supplemental: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(candidate)
    if not isinstance(supplemental, Mapping):
        return merged
    for field in _CLASSIFIER_MARKET_FIELDS:
        if field == "liquidity_usd":
            if _candidate_liquidity_usd(merged) is not None:
                continue
        elif merged.get(field) is not None:
            continue
        if supplemental.get(field) is not None:
            merged[field] = supplemental.get(field)
    # Supplemental linked responses contribute market facts only. Source/capture
    # provenance remains owned by the frozen carrier/attempt projection so the
    # generic discovery parser cannot synthesize a missing capture timestamp.
    return merged


def project_classifier_candidate_from_pre_admission_evidence(
    *,
    mint_identity: str,
    pair_identity: str,
    canonical_evidence_json: str,
    channel_labels: Sequence[str] = (),
    observed_at: datetime | None = None,
    supplemental_candidate_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project exact mint/pair frozen evidence into classifier input shape."""
    mint = _required(mint_identity, "mint_identity")
    pair = _required(pair_identity, "pair_identity")
    evidence = _required(canonical_evidence_json, "canonical_evidence_json")
    candidate = _merge_missing_classifier_evidence(
        _decode_evidence_candidate(evidence), supplemental_candidate_evidence
    )
    labels = tuple(
        label
        for label in channel_labels
        if isinstance(label, str) and label and label == label.strip()
    )
    source_name = candidate.get("source_name")
    if not isinstance(source_name, str) or not source_name.strip():
        source_name = "later_cycle_frozen_evidence"
    captured_at = candidate.get("captured_at")
    if not isinstance(captured_at, str) or not captured_at.strip():
        captured_at = candidate.get("observed_at")
    if not isinstance(captured_at, str) or not captured_at.strip():
        if observed_at is None:
            raise PreAdmissionAttemptError("FROZEN_LANE_EVIDENCE_INVALID")
        captured_at = _timestamp(observed_at, "observed_at")
    return {
        "token_mint": mint,
        "pair_address": pair,
        "chain": PRINTER_CHAIN,
        "source_name": source_name,
        "captured_at": captured_at,
        "price_usd": candidate.get("price_usd"),
        "liquidity_usd": _candidate_liquidity_usd(candidate),
        "volume_5m": candidate.get("volume_5m"),
        "volume_1h": candidate.get("volume_1h"),
        "volume_24h": candidate.get("volume_24h"),
        "txns_5m": candidate.get("txns_5m"),
        "txns_1h": candidate.get("txns_1h"),
        "txns_24h": candidate.get("txns_24h"),
        "source_channel": _mapped_source_channel(candidate, channel_labels=labels),
    }


def _frozen_lane_evidence_hash(classifier_input: Mapping[str, Any]) -> str:
    encoded = json.dumps(classifier_input, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def classify_tracking_lane_from_candidate_evidence(
    *,
    mint_identity: str,
    pair_identity: str,
    canonical_evidence_json: str,
    channel_labels: Sequence[str] = (),
    observed_at: datetime,
    supplemental_candidate_evidence: Mapping[str, Any] | None = None,
) -> tuple[str, Any]:
    """Return (TRACK_FAST|TRACK_NORMAL, classification) or raise if unavailable."""
    classifier_input = project_classifier_candidate_from_pre_admission_evidence(
        mint_identity=mint_identity,
        pair_identity=pair_identity,
        canonical_evidence_json=canonical_evidence_json,
        channel_labels=channel_labels,
        observed_at=observed_at,
        supplemental_candidate_evidence=supplemental_candidate_evidence,
    )
    classification = classify_discovery_candidate(classifier_input)
    lane = choose_tracking_lane(classifier_input, classification)
    lane_value = None if lane is None else str(lane.value)
    if lane_value not in _ALLOWED_FROZEN_TRACKING_LANES:
        raise PreAdmissionAttemptError("FROZEN_TRACKING_LANE_UNAVAILABLE")
    if classification.discovery_action.value != lane_value:
        raise PreAdmissionAttemptError("FROZEN_TRACKING_LANE_UNAVAILABLE")
    return lane_value, classification


def attach_frozen_tracking_lane(
    item: PreAdmissionAttemptItem,
    *,
    now: datetime,
    connection: sqlite3.Connection | None = None,
) -> PreAdmissionAttemptItem:
    """Classify exact current evidence and freeze TRACK_FAST/TRACK_NORMAL provenance."""
    supplemental = None
    if connection is not None:
        supplemental = _linked_exact_market_candidate_evidence(
            connection,
            attempt_id=item.attempt_id,
            mint_identity=item.mint_identity,
            pair_identity=item.pair_identity,
            observed_at=item.observed_at,
        )
    try:
        if connection is not None:
            _reject_liquidity_evidence_time_before_proving_response(
                connection,
                candidate=_decode_evidence_candidate(item.canonical_evidence_json),
            )
        classifier_input = project_classifier_candidate_from_pre_admission_evidence(
            mint_identity=item.mint_identity,
            pair_identity=item.pair_identity,
            canonical_evidence_json=item.canonical_evidence_json,
            channel_labels=item.channel_labels,
            observed_at=item.observed_at,
            supplemental_candidate_evidence=supplemental,
        )
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="FROZEN_EVIDENCE_PROJECTION",
            operation_phase="FROZEN_CARRIER",
        ) from exc
    try:
        lane_value, classification = classify_tracking_lane_from_candidate_evidence(
            mint_identity=item.mint_identity,
            pair_identity=item.pair_identity,
            canonical_evidence_json=item.canonical_evidence_json,
            channel_labels=item.channel_labels,
            observed_at=item.observed_at,
            supplemental_candidate_evidence=supplemental,
        )
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="FROZEN_LANE_CLASSIFICATION",
            operation_phase="FROZEN_CARRIER",
        ) from exc
    return replace(
        item,
        frozen_tracking_lane=lane_value,
        frozen_discovery_action=classification.discovery_action.value,
        frozen_discovery_label=classification.discovery_label.value,
        frozen_classification_reason=classification.reason,
        frozen_lane_evidence_hash=_frozen_lane_evidence_hash(classifier_input),
        frozen_lane_decided_at=_utc(now, "now"),
        frozen_lane_decision_owner=FROZEN_LANE_DECISION_OWNER,
    )


def _require_frozen_tracking_lane_fields(
    item: PreAdmissionAttemptItem, *, missing_code: str
) -> None:
    if (
        item.frozen_tracking_lane is None
        or item.frozen_discovery_action is None
        or item.frozen_discovery_label is None
        or item.frozen_classification_reason is None
        or item.frozen_lane_evidence_hash is None
        or item.frozen_lane_decided_at is None
        or item.frozen_lane_decision_owner is None
    ):
        raise PreAdmissionAttemptError(missing_code)
    lane = _required(item.frozen_tracking_lane, "frozen_tracking_lane")
    action = _required(item.frozen_discovery_action, "frozen_discovery_action")
    if lane not in _ALLOWED_FROZEN_TRACKING_LANES:
        raise PreAdmissionAttemptError(missing_code)
    if action != lane:
        raise PreAdmissionAttemptError(missing_code)
    _required(item.frozen_discovery_label, "frozen_discovery_label")
    _required(item.frozen_classification_reason, "frozen_classification_reason")
    evidence_hash = _required(item.frozen_lane_evidence_hash, "frozen_lane_evidence_hash")
    if len(evidence_hash) != 64 or any(ch not in "0123456789abcdef" for ch in evidence_hash):
        raise PreAdmissionAttemptError(missing_code)
    _utc(item.frozen_lane_decided_at, "frozen_lane_decided_at")
    owner = _required(item.frozen_lane_decision_owner, "frozen_lane_decision_owner")
    if owner != FROZEN_LANE_DECISION_OWNER:
        raise PreAdmissionAttemptError(missing_code)


def _attempt_from_row(row: sqlite3.Row) -> PreAdmissionDiscoveryAttempt:
    return PreAdmissionDiscoveryAttempt(
        attempt_id=str(row["attempt_id"]),
        campaign_id=str(row["campaign_id"]),
        campaign_run_id=str(row["campaign_run_id"]),
        configuration_id=str(row["configuration_id"]),
        authoritative_factory_run_id=str(row["authoritative_factory_run_id"]),
        proposed_cycle_ordinal=int(row["proposed_cycle_ordinal"]),
        proposed_cycle_id=str(row["proposed_cycle_id"]),
        scheduler_job_id=int(row["scheduler_job_id"]),
        cycle_cutoff=_parse_timestamp(row["cycle_cutoff"], "cycle_cutoff"),
        evaluated_at=_parse_timestamp(row["evaluated_at"], "evaluated_at"),
        selection_seed_identity=str(row["selection_seed_identity"]),
        state=PreAdmissionAttemptState(str(row["attempt_state"])),
        first_terminal_cause=(
            None if row["first_terminal_cause"] is None else str(row["first_terminal_cause"])
        ),
        terminal_at=_optional_timestamp(row["terminal_at"], "terminal_at"),
        consumed_cycle_id=(
            None if row["consumed_cycle_id"] is None else str(row["consumed_cycle_id"])
        ),
        consumed_at=_optional_timestamp(row["consumed_at"], "consumed_at"),
    )


def load_pre_admission_attempt(
    connection: sqlite3.Connection, *, attempt_id: str
) -> PreAdmissionDiscoveryAttempt:
    connection.row_factory = sqlite3.Row
    exact_id = _required(attempt_id, "attempt_id")
    row = connection.execute(
        "SELECT * FROM printer_pre_admission_discovery_attempts WHERE attempt_id=?",
        (exact_id,),
    ).fetchone()
    if row is None:
        raise PreAdmissionAttemptError("ATTEMPT_NOT_FOUND")
    return _attempt_from_row(row)


def create_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    authoritative_factory_run_id: str,
    proposed_cycle_ordinal: int,
    proposed_cycle_id: str,
    scheduler_job_id: int,
    cycle_cutoff: datetime,
    evaluated_at: datetime,
    selection_seed_identity: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    values = {
        "attempt_id": _required(attempt_id, "attempt_id"),
        "campaign_id": _required(campaign_id, "campaign_id"),
        "campaign_run_id": _required(campaign_run_id, "campaign_run_id"),
        "configuration_id": _required(configuration_id, "configuration_id"),
        "factory_run_id": _required(
            authoritative_factory_run_id, "authoritative_factory_run_id"
        ),
        "proposed_cycle_id": _required(proposed_cycle_id, "proposed_cycle_id"),
        "selection_seed": _required(selection_seed_identity, "selection_seed_identity"),
    }
    if type(proposed_cycle_ordinal) is not int or proposed_cycle_ordinal != 2:
        raise PreAdmissionAttemptError("PROPOSED_CYCLE_ORDINAL_INVALID")
    if type(scheduler_job_id) is not int or scheduler_job_id <= 0:
        raise PreAdmissionAttemptError("SCHEDULER_JOB_ID_INVALID")
    owner = connection.execute(
        """SELECT 1
           FROM printer_memory_factory_campaign_runs AS r
           JOIN printer_memory_factory_campaign_configurations AS c
             ON c.campaign_id=r.campaign_id AND c.configuration_id=?
           JOIN printer_memory_factory_runs AS f
             ON f.run_id=r.authoritative_run_id
           WHERE r.run_id=? AND r.campaign_id=? AND f.run_id=?""",
        (
            values["configuration_id"],
            values["campaign_run_id"],
            values["campaign_id"],
            values["factory_run_id"],
        ),
    ).fetchone()
    if owner is None:
        raise PreAdmissionAttemptError("OWNERSHIP_MISMATCH")
    scheduler = connection.execute(
        "SELECT job_kind FROM printer_scheduler_jobs WHERE id=?",
        (scheduler_job_id,),
    ).fetchone()
    if scheduler is None or str(scheduler[0]) != "PRE_ADMISSION_DISCOVERY_SELECTION":
        raise PreAdmissionAttemptError("SCHEDULER_OWNERSHIP_MISMATCH")
    created_at = _timestamp(now, "now")
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempts(
                   attempt_id,campaign_id,campaign_run_id,configuration_id,
                   authoritative_factory_run_id,proposed_cycle_ordinal,
                   proposed_cycle_id,scheduler_job_id,cycle_cutoff,evaluated_at,
                   selection_seed_identity,attempt_state,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'PLANNED',?,?)""",
            (
                values["attempt_id"], values["campaign_id"],
                values["campaign_run_id"], values["configuration_id"],
                values["factory_run_id"], proposed_cycle_ordinal,
                values["proposed_cycle_id"], scheduler_job_id,
                _timestamp(cycle_cutoff, "cycle_cutoff"),
                _timestamp(evaluated_at, "evaluated_at"),
                values["selection_seed"], created_at, created_at,
            ),
        )
    except sqlite3.IntegrityError as exc:
        message = str(exc)
        if "UNIQUE constraint failed" in message:
            raise PreAdmissionAttemptError("ATTEMPT_ALREADY_EXISTS") from exc
        raise PreAdmissionAttemptError("ATTEMPT_PERSISTENCE_FAILED") from exc
    return load_pre_admission_attempt(connection, attempt_id=values["attempt_id"])


def _transition(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    expected: PreAdmissionAttemptState,
    target: PreAdmissionAttemptState,
    now: datetime,
    cause: str | None = None,
) -> PreAdmissionDiscoveryAttempt:
    instant = _timestamp(now, "now")
    terminal = target not in {PreAdmissionAttemptState.PLANNED, PreAdmissionAttemptState.RUNNING}
    cursor = connection.execute(
        """UPDATE printer_pre_admission_discovery_attempts
           SET attempt_state=?,first_terminal_cause=?,terminal_at=?,updated_at=?
           WHERE attempt_id=? AND attempt_state=?""",
        (
            target.value,
            _required(cause, "cause") if terminal else None,
            instant if terminal else None,
            instant,
            _required(attempt_id, "attempt_id"),
            expected.value,
        ),
    )
    if cursor.rowcount != 1:
        raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    return load_pre_admission_attempt(connection, attempt_id=attempt_id)


def mark_pre_admission_attempt_running(
    connection: sqlite3.Connection, *, attempt_id: str, now: datetime
) -> PreAdmissionDiscoveryAttempt:
    attempt = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    job = connection.execute(
        "SELECT job_kind,status,lock_owner FROM printer_scheduler_jobs WHERE id=?",
        (attempt.scheduler_job_id,),
    ).fetchone()
    expected_owner = pre_admission_attempt_lock_owner(attempt.attempt_id)
    if (
        job is None
        or str(job["job_kind"]) != JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value
        or str(job["status"]) != JobStatus.RUNNING.value
        or str(job["lock_owner"] or "") != expected_owner
    ):
        raise PreAdmissionAttemptError("SCHEDULER_CLAIM_MISMATCH")
    return _transition(
        connection,
        attempt_id=attempt_id,
        expected=PreAdmissionAttemptState.PLANNED,
        target=PreAdmissionAttemptState.RUNNING,
        now=now,
    )


def pre_admission_attempt_lock_owner(attempt_id: str) -> str:
    return f"pre-admission-discovery:{_required(attempt_id, 'attempt_id')}"


def create_scheduled_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    authoritative_factory_run_id: str,
    proposed_cycle_ordinal: int,
    proposed_cycle_id: str,
    cycle_cutoff: datetime,
    evaluated_at: datetime,
    selection_seed_identity: str,
    scheduled_for: datetime,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    """Atomically create the one exact Scheduler job and PLANNED attempt."""
    if connection.in_transaction:
        raise PreAdmissionAttemptError("OPEN_TRANSACTION_FORBIDDEN")
    exact_id = _required(attempt_id, "attempt_id")
    existing = connection.execute(
        """SELECT 1 FROM printer_pre_admission_discovery_attempts
           WHERE campaign_id=? AND campaign_run_id=?
             AND authoritative_factory_run_id=? AND proposed_cycle_ordinal=?""",
        (
            campaign_id, campaign_run_id, authoritative_factory_run_id,
            proposed_cycle_ordinal,
        ),
    ).fetchone()
    if existing is not None:
        raise PreAdmissionAttemptError("ATTEMPT_ALREADY_EXISTS")
    owner = connection.execute(
        """SELECT 1 FROM printer_memory_factory_campaign_runs AS r
           JOIN printer_memory_factory_campaign_configurations AS c
             ON c.campaign_id=r.campaign_id AND c.configuration_id=?
           WHERE r.run_id=? AND r.campaign_id=? AND r.authoritative_run_id=?""",
        (
            configuration_id, campaign_run_id, campaign_id,
            authoritative_factory_run_id,
        ),
    ).fetchone()
    if owner is None:
        raise PreAdmissionAttemptError("OWNERSHIP_MISMATCH")
    connection.execute("BEGIN IMMEDIATE")
    try:
        result, scheduler_job_id = enqueue_job(
            connection,
            job_name=f"pre-admission-discovery-selection:{exact_id}",
            job_kind=JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
            target_table="printer_pre_admission_discovery_attempts",
            target_id=None,
            scheduled_for=_utc(scheduled_for, "scheduled_for"),
        )
        if result is not LockResult.ACQUIRED or scheduler_job_id is None:
            raise PreAdmissionAttemptError("SCHEDULER_OWNERSHIP_CREATE_FAILED")
        attempt = create_pre_admission_attempt(
            connection,
            attempt_id=exact_id,
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            configuration_id=configuration_id,
            authoritative_factory_run_id=authoritative_factory_run_id,
            proposed_cycle_ordinal=proposed_cycle_ordinal,
            proposed_cycle_id=proposed_cycle_id,
            scheduler_job_id=scheduler_job_id,
            cycle_cutoff=cycle_cutoff,
            evaluated_at=evaluated_at,
            selection_seed_identity=selection_seed_identity,
            now=now,
        )
        connection.commit()
        return attempt
    except Exception:
        connection.rollback()
        raise


def _terminalize_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    state: PreAdmissionAttemptState,
    cause: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    try:
        target = PreAdmissionAttemptState(state)
    except ValueError as exc:
        raise PreAdmissionAttemptError("TERMINAL_STATE_INVALID") from exc
    if target not in {
        PreAdmissionAttemptState.NO_PAIR,
        PreAdmissionAttemptState.BLOCKED,
        PreAdmissionAttemptState.FAILED,
        PreAdmissionAttemptState.CANCELLED,
    }:
        raise PreAdmissionAttemptError("TERMINAL_STATE_INVALID")
    current = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    allowed_from = {
        PreAdmissionAttemptState.NO_PAIR: {PreAdmissionAttemptState.RUNNING},
        PreAdmissionAttemptState.FAILED: {PreAdmissionAttemptState.RUNNING},
        PreAdmissionAttemptState.BLOCKED: {
            PreAdmissionAttemptState.PLANNED,
            PreAdmissionAttemptState.RUNNING,
        },
        PreAdmissionAttemptState.CANCELLED: {
            PreAdmissionAttemptState.PLANNED,
            PreAdmissionAttemptState.RUNNING,
        },
    }[target]
    if current.state not in allowed_from:
        raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    return _transition(
        connection,
        attempt_id=attempt_id,
        expected=current.state,
        target=target,
        cause=cause,
        now=now,
    )


def terminalize_pre_admission_attempt(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    state: PreAdmissionAttemptState,
    cause: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    try:
        return _terminalize_pre_admission_attempt(
            connection,
            attempt_id=attempt_id,
            state=state,
            cause=cause,
            now=now,
        )
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="RUNNING_ATTEMPT_FAILURE_TERMINALIZATION",
            operation_phase="TERMINALIZATION",
        ) from exc


def _validate_pair(attempt_id: str, items: Sequence[PreAdmissionAttemptItem]) -> tuple[PreAdmissionAttemptItem, PreAdmissionAttemptItem]:
    if len(items) != 2:
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    ordered = tuple(sorted(items, key=lambda item: item.slot_ordinal))
    if tuple(item.slot_ordinal for item in ordered) != (1, 2):
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    if any(item.attempt_id != attempt_id for item in ordered):
        raise PreAdmissionAttemptError("ITEM_ATTEMPT_ID_MISMATCH")
    distinct_fields = (
        "token_identity", "token_row_id", "mint_identity", "pair_identity",
        "pair_row_id", "canonical_market_identity", "canonical_pool_identity",
    )
    if any(len({getattr(item, field) for item in ordered}) != 2 for field in distinct_fields):
        raise PreAdmissionAttemptError("PAIR_IDENTITIES_NOT_DISTINCT")
    for item in ordered:
        labels = tuple(sorted(set(item.channel_labels)))
        if not labels or any(
            not isinstance(label, str) or not label or label != label.strip()
            for label in labels
        ):
            raise PreAdmissionAttemptError("CHANNEL_LABELS_INVALID")
    return ordered  # type: ignore[return-value]


def persist_pre_admission_pair(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    items: Sequence[PreAdmissionAttemptItem],
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    try:
        exact_id = _required(attempt_id, "attempt_id")
        ordered = _validate_pair(exact_id, items)
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="PAIR_SHAPE_VALIDATION",
            operation_phase="PAIR_PRECHECK",
        ) from exc
    try:
        for item in ordered:
            _require_frozen_tracking_lane_fields(
                item, missing_code="FROZEN_TRACKING_LANE_MISSING"
            )
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="FROZEN_LANE_FIELD_VALIDATION",
            operation_phase="PAIR_PRECHECK",
            failure_category="PREREQUISITE_MISSING",
        ) from exc
    try:
        if load_pre_admission_attempt(
            connection, attempt_id=exact_id
        ).state is not PreAdmissionAttemptState.RUNNING:
            raise PreAdmissionAttemptError("INVALID_ATTEMPT_TRANSITION")
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="PAIR_ATTEMPT_RUNNING_PREREQUISITE",
            operation_phase="PAIR_PRECHECK",
            failure_category="PREREQUISITE_MISSING",
        ) from exc
    instant = _timestamp(now, "now")
    connection.execute("SAVEPOINT persist_pre_admission_pair")
    try:
        for item in ordered:
            try:
                connection.execute(
                    """INSERT INTO printer_pre_admission_discovery_attempt_items(
                       attempt_id,slot_ordinal,token_identity,token_row_id,mint_identity,
                       pair_identity,pair_row_id,lifecycle_identity,
                       canonical_market_identity,canonical_pool_identity,channel_labels_json,
                       canonical_evidence_json,canonical_evidence_hash,evidence_version,
                       observed_at,created_at,
                       frozen_tracking_lane,frozen_discovery_action,frozen_discovery_label,
                       frozen_classification_reason,frozen_lane_evidence_hash,
                       frozen_lane_decided_at,frozen_lane_decision_owner
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        exact_id, item.slot_ordinal, _required(item.token_identity, "token_identity"),
                        item.token_row_id, _required(item.mint_identity, "mint_identity"),
                        _required(item.pair_identity, "pair_identity"), item.pair_row_id,
                        _required(item.lifecycle_identity, "lifecycle_identity"),
                        _required(item.canonical_market_identity, "canonical_market_identity"),
                        _required(item.canonical_pool_identity, "canonical_pool_identity"),
                        json.dumps(sorted(set(item.channel_labels)), separators=(",", ":")),
                        _required(item.canonical_evidence_json, "canonical_evidence_json"),
                        _required(item.canonical_evidence_hash, "canonical_evidence_hash"),
                        _required(item.evidence_version, "evidence_version"),
                        _timestamp(item.observed_at, "observed_at"), instant,
                        _required(item.frozen_tracking_lane, "frozen_tracking_lane"),
                        _required(item.frozen_discovery_action, "frozen_discovery_action"),
                        _required(item.frozen_discovery_label, "frozen_discovery_label"),
                        _required(
                            item.frozen_classification_reason, "frozen_classification_reason"
                        ),
                        _required(item.frozen_lane_evidence_hash, "frozen_lane_evidence_hash"),
                        _timestamp(item.frozen_lane_decided_at, "frozen_lane_decided_at"),
                        _required(
                            item.frozen_lane_decision_owner, "frozen_lane_decision_owner"
                        ),
                    ),
                )
            except Exception as exc:
                raise _annotate_persistence_error(
                    exc,
                    producer_code="PAIR_ITEM_INSERT",
                    operation_phase=f"PAIR_ITEM_{item.slot_ordinal}",
                ) from exc
        try:
            result = _transition(
                connection,
                attempt_id=exact_id,
                expected=PreAdmissionAttemptState.RUNNING,
                target=PreAdmissionAttemptState.PAIR_READY,
                cause="EXACT_PAIR_FROZEN",
                now=now,
            )
        except Exception as exc:
            raise _annotate_persistence_error(
                exc,
                producer_code="PAIR_READY_TRANSITION",
                operation_phase="PAIR_READY",
            ) from exc
        connection.execute("RELEASE SAVEPOINT persist_pre_admission_pair")
        return result
    except PreAdmissionAttemptError as primary:
        try:
            connection.execute("ROLLBACK TO SAVEPOINT persist_pre_admission_pair")
            connection.execute("RELEASE SAVEPOINT persist_pre_admission_pair")
        except sqlite3.Error as cleanup_exc:
            try:
                connection.rollback()
            except Exception as rollback_exc:
                raise primary from rollback_exc
            raise primary from cleanup_exc
        raise


def load_pre_admission_pair(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    require_frozen_lane: bool = True,
) -> tuple[PreAdmissionAttemptItem, PreAdmissionAttemptItem]:
    attempt = load_pre_admission_attempt(connection, attempt_id=attempt_id)
    if attempt.state not in {
        PreAdmissionAttemptState.PAIR_READY, PreAdmissionAttemptState.CONSUMED
    }:
        raise PreAdmissionAttemptError("PAIR_NOT_READY")
    rows = connection.execute(
        """SELECT * FROM printer_pre_admission_discovery_attempt_items
           WHERE attempt_id=? ORDER BY slot_ordinal""",
        (attempt_id,),
    ).fetchall()
    if len(rows) != 2 or tuple(int(row["slot_ordinal"]) for row in rows) != (1, 2):
        raise PreAdmissionAttemptError("EXACT_TWO_ITEMS_REQUIRED")
    loaded: list[PreAdmissionAttemptItem] = []
    for row in rows:
        keys = set(row.keys())
        item = PreAdmissionAttemptItem(
            attempt_id=str(row["attempt_id"]), slot_ordinal=int(row["slot_ordinal"]),
            token_identity=str(row["token_identity"]), token_row_id=int(row["token_row_id"]),
            mint_identity=str(row["mint_identity"]), pair_identity=str(row["pair_identity"]),
            pair_row_id=int(row["pair_row_id"]), lifecycle_identity=str(row["lifecycle_identity"]),
            canonical_market_identity=str(row["canonical_market_identity"]),
            canonical_pool_identity=str(row["canonical_pool_identity"]),
            canonical_evidence_json=str(row["canonical_evidence_json"]),
            canonical_evidence_hash=str(row["canonical_evidence_hash"]),
            evidence_version=str(row["evidence_version"]),
            observed_at=_parse_timestamp(row["observed_at"], "observed_at"),
            channel_labels=tuple(json.loads(str(row["channel_labels_json"]))),
            frozen_tracking_lane=(
                None
                if "frozen_tracking_lane" not in keys or row["frozen_tracking_lane"] is None
                else str(row["frozen_tracking_lane"])
            ),
            frozen_discovery_action=(
                None
                if "frozen_discovery_action" not in keys
                or row["frozen_discovery_action"] is None
                else str(row["frozen_discovery_action"])
            ),
            frozen_discovery_label=(
                None
                if "frozen_discovery_label" not in keys
                or row["frozen_discovery_label"] is None
                else str(row["frozen_discovery_label"])
            ),
            frozen_classification_reason=(
                None
                if "frozen_classification_reason" not in keys
                or row["frozen_classification_reason"] is None
                else str(row["frozen_classification_reason"])
            ),
            frozen_lane_evidence_hash=(
                None
                if "frozen_lane_evidence_hash" not in keys
                or row["frozen_lane_evidence_hash"] is None
                else str(row["frozen_lane_evidence_hash"])
            ),
            frozen_lane_decided_at=(
                None
                if "frozen_lane_decided_at" not in keys
                else _optional_timestamp(
                    row["frozen_lane_decided_at"], "frozen_lane_decided_at"
                )
            ),
            frozen_lane_decision_owner=(
                None
                if "frozen_lane_decision_owner" not in keys
                or row["frozen_lane_decision_owner"] is None
                else str(row["frozen_lane_decision_owner"])
            ),
        )
        # Admit must fail closed on missing frozen provenance. Cancel/terminal
        # paths may pass require_frozen_lane=False for pre-060 historical rows.
        if require_frozen_lane:
            _require_frozen_tracking_lane_fields(
                item, missing_code="FROZEN_TRACKING_LANE_MISSING"
            )
        loaded.append(item)
    return (loaded[0], loaded[1])


def cancel_pair_ready_pre_admission_attempt_for_terminal_parent(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    authoritative_factory_run_id: str,
    now: datetime,
) -> PreAdmissionDiscoveryAttempt:
    """Revoke frozen pair authority only when its exact owning parent terminalizes.

    PAIR_READY already durably records EXACT_PAIR_FROZEN and the freeze time.
    Parent-terminal cancellation therefore changes only ``attempt_state`` and
    ``updated_at``. The generic terminalizer intentionally remains unable to
    cancel PAIR_READY so ordinary callers cannot discard valid admission authority.
    """
    exact_id = _required(attempt_id, "attempt_id")
    exact_campaign_id = _required(campaign_id, "campaign_id")
    exact_run_id = _required(campaign_run_id, "campaign_run_id")
    exact_factory_id = _required(
        authoritative_factory_run_id, "authoritative_factory_run_id"
    )
    current = load_pre_admission_attempt(connection, attempt_id=exact_id)
    if (
        current.state is not PreAdmissionAttemptState.PAIR_READY
        or current.first_terminal_cause != "EXACT_PAIR_FROZEN"
        or current.terminal_at is None
        or current.consumed_cycle_id is not None
        or current.consumed_at is not None
    ):
        raise PreAdmissionAttemptError("PAIR_READY_PARENT_TERMINAL_SHAPE_INVALID")
    if (
        current.campaign_id != exact_campaign_id
        or current.campaign_run_id != exact_run_id
        or current.authoritative_factory_run_id != exact_factory_id
    ):
        raise PreAdmissionAttemptError("PARENT_TERMINAL_OWNERSHIP_MISMATCH")

    # Canonical pair load proves the exact two immutable frozen items/ordinals
    # still exist before the admission authority is revoked. Pre-060 historical
    # rows may lack frozen-lane columns; cancel must still revoke them.
    load_pre_admission_pair(
        connection, attempt_id=exact_id, require_frozen_lane=False
    )
    instant = _timestamp(now, "now")
    cursor = connection.execute(
        """UPDATE printer_pre_admission_discovery_attempts
           SET attempt_state='CANCELLED', updated_at=?
           WHERE attempt_id=?
             AND campaign_id=?
             AND campaign_run_id=?
             AND authoritative_factory_run_id=?
             AND attempt_state='PAIR_READY'
             AND first_terminal_cause='EXACT_PAIR_FROZEN'
             AND terminal_at IS NOT NULL
             AND consumed_cycle_id IS NULL
             AND consumed_at IS NULL""",
        (
            instant,
            exact_id,
            exact_campaign_id,
            exact_run_id,
            exact_factory_id,
        ),
    )
    if cursor.rowcount != 1:
        raise PreAdmissionAttemptError("PAIR_READY_PARENT_TERMINAL_CANCEL_FAILED")
    return load_pre_admission_attempt(connection, attempt_id=exact_id)


def link_pre_admission_source_evidence(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    link_ordinal: int,
    logical_stage: str,
    source_request_id: int,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: datetime,
) -> None:
    try:
        if source_response_id is not None and source_failure_id is not None:
            raise PreAdmissionAttemptError("AMBIGUOUS_SOURCE_EVIDENCE")
        if type(link_ordinal) is not int or link_ordinal <= 0:
            raise PreAdmissionAttemptError("LINK_ORDINAL_INVALID")
        if type(source_request_id) is not int or source_request_id <= 0:
            raise PreAdmissionAttemptError("SOURCE_REQUEST_ID_INVALID")
        exact_attempt_id = _required(attempt_id, "attempt_id")
        exact_stage = _required(logical_stage, "logical_stage")
        created_at = _timestamp(now, "now")
    except PreAdmissionAttemptError as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="SOURCE_EVIDENCE_LINK_ARGUMENT",
            operation_phase="SOURCE_LINK",
        ) from exc
    try:
        connection.execute(
            """INSERT INTO printer_pre_admission_discovery_attempt_source_links(
                   attempt_id,link_ordinal,logical_stage,source_request_id,
                   source_response_id,source_failure_id,created_at
            ) VALUES (?,?,?,?,?,?,?)""",
            (
                exact_attempt_id, link_ordinal, exact_stage, source_request_id,
                source_response_id, source_failure_id, created_at,
            ),
        )
    except Exception as exc:
        raise _annotate_persistence_error(
            exc,
            producer_code="SOURCE_EVIDENCE_LINK_INSERT",
            operation_phase="SOURCE_LINK",
        ) from exc


def load_pre_admission_persistence_diagnostic(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
) -> PreAdmissionPersistenceDiagnostic | str:
    """Decode exact durable terminal evidence without mutation or policy authority."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT a.attempt_state,a.first_terminal_cause,a.scheduler_job_id,
                  j.job_kind,j.status,j.locked_at,j.lock_owner,j.last_error
           FROM printer_pre_admission_discovery_attempts AS a
           JOIN printer_scheduler_jobs AS j ON j.id=a.scheduler_job_id
           WHERE a.attempt_id=?""",
        (attempt_id,),
    ).fetchone()
    if (
        row is None
        or str(row["attempt_state"]) != PreAdmissionAttemptState.FAILED.value
        or str(row["first_terminal_cause"] or "") != PERSISTENCE_FAILURE_CODE
        or str(row["job_kind"]) != JobKind.PRE_ADMISSION_DISCOVERY_SELECTION.value
        or str(row["status"]) != JobStatus.FAILED.value
        or row["locked_at"] is not None
        or row["lock_owner"] is not None
        or not isinstance(row["last_error"], str)
        or len(row["last_error"]) > 1536
    ):
        return DIAGNOSTIC_UNAVAILABLE
    try:
        decoded = json.loads(row["last_error"])
        diagnostic = PreAdmissionPersistenceDiagnostic.from_mapping(decoded)
    except (TypeError, ValueError, json.JSONDecodeError):
        return DIAGNOSTIC_UNAVAILABLE
    if diagnostic.failure_code != str(row["first_terminal_cause"]):
        return DIAGNOSTIC_UNAVAILABLE
    return diagnostic


__all__ = [
    "DIAGNOSTIC_UNAVAILABLE",
    "FROZEN_LANE_DECISION_OWNER",
    "PERSISTENCE_DIAGNOSTIC_SCHEMA", "PERSISTENCE_FAILURE_CODE",
    "PreAdmissionAttemptError", "PreAdmissionAttemptItem",
    "PreAdmissionPersistenceDiagnostic",
    "PreAdmissionAttemptState", "PreAdmissionDiscoveryAttempt",
    "attach_frozen_tracking_lane",
    "cancel_pair_ready_pre_admission_attempt_for_terminal_parent",
    "create_pre_admission_attempt", "create_scheduled_pre_admission_attempt",
    "link_pre_admission_source_evidence",
    "load_pre_admission_attempt", "load_pre_admission_pair",
    "load_pre_admission_persistence_diagnostic",
    "mark_pre_admission_attempt_running", "persist_pre_admission_pair",
    "pre_admission_attempt_lock_owner",
    "project_classifier_candidate_from_pre_admission_evidence",
    "pre_admission_persistence_diagnostic_for_exception",
    "terminalize_pre_admission_attempt",
]
