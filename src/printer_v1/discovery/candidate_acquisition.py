"""Capacity-neutral, frozen-input candidate-acquisition foundation.

This owner is intentionally transport-free. It validates Central Scheduler and
Source Governor ownership for frozen observations, builds immutable candidate
certificates, a durable reserve, and an exact-N runtime-neutral manifest. It
never creates tracking, campaign, lifecycle, memory, retrieval, or financial
rows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from printer_v1.scheduler.contracts import JobKind
from printer_v1.sources.governor import can_request_source
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.lifecycle.tracking_queue import assess_tracking_handoff_by_identity
from printer_v1.discovery.selection_batch import (
    check_pair_selection_cooldown,
    check_token_selection_cooldown,
)


SCHEMA_VERSION = "V2_9_8B_CANDIDATE_ACQUISITION_V1"
CERTIFICATE_VERSION = "V2_9_8B_CANDIDATE_CERTIFICATE_V1"
SEED_DOMAIN = "PrinterV1|candidate-acquisition-foundation-v1|"
APPROVED_ACTIVE_MEMORY_CAPACITY = 2
MIN_SELECTION_CAPACITY = 1
MAX_SELECTION_CAPACITY = 16
SCHEDULER_OWNER = "Central Scheduler"
SCHEDULER_JOB_KIND = JobKind.DISCOVERY_REFRESH.value
RELIABILITY_STATUS = "UNPROVEN_NO_INDEPENDENT_SAMPLE"
PROHIBITED_FOUNDATION_SOURCES = frozenset({"dextools", "pumpportal"})

ALLOWED_LINEAGE_STATES = frozenset(
    {
        "PUMP_ORIGIN_CONFIRMED",
        "PUMP_GRADUATION_CONFIRMED",
        "NON_PUMP_POOL_CONFIRMED",
        "UNKNOWN_ORIGIN",
        "CONFLICTING_LINEAGE",
        "UNSUPPORTED_LINEAGE",
    }
)
SUPPORTED_TOKEN_PROGRAMS = frozenset(
    {
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    }
)
ALLOWED_QUOTE_MINTS = frozenset(
    {
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    }
)
PUMP_IDL_SHA256 = "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"
PUMPSWAP_IDL_SHA256 = "6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56"
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

STAGES: tuple[tuple[str, str], ...] = (
    ("CHAIN_MINT_VALID", "mint_status"),
    ("TOKEN_PROGRAM_VALID", "token_program_status"),
    ("IDENTITY_AVAILABLE", "tracking_status"),
    ("POOL_QUOTE_VALID", "pool_status"),
    ("MARKET_FRESH", "market_status"),
    ("AGE_VALID", "age_status"),
    ("HOLDER_ACCEPTABLE", "holder_status"),
    ("SAFETY_ACCEPTABLE", "safety_status"),
    ("LIQUIDITY_TRADEABILITY_VALID", "liquidity_status"),
    ("ROUTE_TRADEABILITY_VALID", "tradeability_status"),
    ("LINEAGE_VALID", "lineage_status"),
)

FAILURE_PRECEDENCE: tuple[tuple[str, str], ...] = (
    ("UNSUPPORTED_CONTRACT", "UNSUPPORTED_CONTRACT"),
    ("PROVIDER_FAILURE", "SOURCE_PROVIDER_FAILURE"),
    ("BUDGET_EXHAUSTED", "BUDGET_EXHAUSTION"),
    ("COVERAGE_INCOMPLETE", "COVERAGE_FAILURE"),
    ("STALE", "STALE_OR_INCOMPLETE_EVIDENCE"),
    ("MALFORMED", "STALE_OR_INCOMPLETE_EVIDENCE"),
)

FORBIDDEN_CAPABILITY_TABLES = (
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
    "printer_memory_factory_runs",
    "printer_memory_factory_campaign_token_slots",
    "printer_tracking_queue",
    "printer_scheduler_jobs",
)

FORBIDDEN_CERTIFICATE_KEYS = frozenset(
    {
        "buy",
        "sell",
        "hold",
        "position",
        "trade_action",
        "paper_decision",
        "pnl",
        "profit",
        "score",
        "rank",
        "confidence",
        "weight",
        "expected_return",
    }
)


class CandidateAcquisitionError(RuntimeError):
    """Fail-closed foundation contract violation."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(value: Any) -> str:
    encoded = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _iso(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise CandidateAcquisitionError("INVALID_TIMESTAMP", str(value)) from exc
    if result.tzinfo is None:
        raise CandidateAcquisitionError("NAIVE_TIMESTAMP", str(value))
    return result.astimezone(timezone.utc)


def _identifier(prefix: str, payload: Any) -> str:
    return f"{prefix}-{_sha(payload)[:32]}"


def build_acquisition_plan(
    *,
    selection_capacity: int,
    execution_id: str,
    selection_seed: str,
    window_start: str,
    window_end: str,
    cutoff_at: str,
    finalized_cutoff_slot: int,
    git_provenance: str,
    source_budgets: Mapping[str, Mapping[str, int]],
    allowed_sources: Sequence[str] = (
        "solana_rpc",
        "dexscreener",
        "geckoterminal",
        "birdeye",
        "goplus",
        "helius_free",
    ),
) -> dict[str, Any]:
    """Build the only supported capacity-neutral immutable plan shape."""
    if type(selection_capacity) is not int or not (
        MIN_SELECTION_CAPACITY <= selection_capacity <= MAX_SELECTION_CAPACITY
    ):
        raise CandidateAcquisitionError("INVALID_SELECTION_CAPACITY")
    if not str(execution_id).strip() or not str(selection_seed).strip():
        raise CandidateAcquisitionError("MISSING_PLAN_IDENTITY")
    start, end, cutoff = _iso(window_start), _iso(window_end), _iso(cutoff_at)
    if not start <= end <= cutoff:
        raise CandidateAcquisitionError("INVALID_FROZEN_WINDOW")
    if type(finalized_cutoff_slot) is not int or finalized_cutoff_slot < 0:
        raise CandidateAcquisitionError("INVALID_FINALIZED_CUTOFF")
    sources = tuple(sorted({str(item) for item in allowed_sources}))
    if not sources:
        raise CandidateAcquisitionError("EMPTY_ALLOWED_SOURCE_SET")
    if prohibited := sorted(set(sources) & PROHIBITED_FOUNDATION_SOURCES):
        raise CandidateAcquisitionError(
            "FOUNDATION_SOURCE_CONTRACT_PROHIBITED", ",".join(prohibited)
        )
    n = selection_capacity
    plan = {
        "schema_version": SCHEMA_VERSION,
        "execution_id": str(execution_id),
        "network": "solana-mainnet",
        "selection_capacity": n,
        "candidate_acquisition_capacity": 2 * n,
        "candidate_reserve_target": n + ((n + 1) // 2),
        "approved_active_memory_capacity": APPROVED_ACTIVE_MEMORY_CAPACITY,
        "selection_seed": str(selection_seed),
        "seed_domain": SEED_DOMAIN,
        "window_start": str(window_start),
        "window_end": str(window_end),
        "cutoff_at": str(cutoff_at),
        "finalized_cutoff_slot": finalized_cutoff_slot,
        "allowed_sources": sources,
        "source_budgets": dict(source_budgets),
        "scheduler_owner": SCHEDULER_OWNER,
        "scheduler_job_kind": SCHEDULER_JOB_KIND,
        "source_governor_required": True,
        "no_retry": True,
        "no_reconnect": True,
        "git_provenance": str(git_provenance),
    }
    policy_payload = {
        key: value
        for key, value in plan.items()
        if key not in {"execution_id", "window_start", "window_end", "cutoff_at", "finalized_cutoff_slot"}
    }
    plan["policy_hash"] = _sha(policy_payload)
    plan["policy_id"] = _identifier("capol", policy_payload)
    return plan


def _validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "execution_id",
        "network",
        "selection_capacity",
        "candidate_acquisition_capacity",
        "candidate_reserve_target",
        "approved_active_memory_capacity",
        "selection_seed",
        "seed_domain",
        "window_start",
        "window_end",
        "cutoff_at",
        "finalized_cutoff_slot",
        "allowed_sources",
        "source_budgets",
        "scheduler_owner",
        "scheduler_job_kind",
        "source_governor_required",
        "no_retry",
        "no_reconnect",
        "git_provenance",
        "policy_hash",
        "policy_id",
    }
    if missing := sorted(required - set(plan)):
        raise CandidateAcquisitionError("INCOMPLETE_PLAN", ",".join(missing))
    n = plan["selection_capacity"]
    if type(n) is not int or not (1 <= n <= 16):
        raise CandidateAcquisitionError("INVALID_SELECTION_CAPACITY")
    if plan["candidate_acquisition_capacity"] != 2 * n:
        raise CandidateAcquisitionError("INVALID_ACQUISITION_CAPACITY")
    if plan["candidate_reserve_target"] != n + ((n + 1) // 2):
        raise CandidateAcquisitionError("INVALID_RESERVE_TARGET")
    if plan["approved_active_memory_capacity"] != 2:
        raise CandidateAcquisitionError("ACTIVE_CAPACITY_UNLOCK_ATTEMPT")
    if plan["scheduler_owner"] != SCHEDULER_OWNER or plan["scheduler_job_kind"] != SCHEDULER_JOB_KIND:
        raise CandidateAcquisitionError("CENTRAL_SCHEDULER_OWNERSHIP_REQUIRED")
    if not plan["source_governor_required"] or not plan["no_retry"] or not plan["no_reconnect"]:
        raise CandidateAcquisitionError("UNBOUNDED_SOURCE_PLAN")
    if plan["network"] != "solana-mainnet" or plan["schema_version"] != SCHEMA_VERSION:
        raise CandidateAcquisitionError("UNSUPPORTED_PLAN_CONTRACT")
    start = _iso(str(plan["window_start"]))
    end = _iso(str(plan["window_end"]))
    cutoff = _iso(str(plan["cutoff_at"]))
    if not start <= end <= cutoff:
        raise CandidateAcquisitionError("INVALID_FROZEN_WINDOW")
    if type(plan["finalized_cutoff_slot"]) is not int or plan["finalized_cutoff_slot"] < 0:
        raise CandidateAcquisitionError("INVALID_FINALIZED_CUTOFF")
    sources = plan["allowed_sources"]
    if not isinstance(sources, (list, tuple)) or tuple(sources) != tuple(sorted(set(sources))):
        raise CandidateAcquisitionError("NONCANONICAL_ALLOWED_SOURCES")
    if prohibited := sorted(set(sources) & PROHIBITED_FOUNDATION_SOURCES):
        raise CandidateAcquisitionError(
            "FOUNDATION_SOURCE_CONTRACT_PROHIBITED", ",".join(prohibited)
        )
    policy_payload = {
        key: value
        for key, value in plan.items()
        if key not in {
            "execution_id", "window_start", "window_end", "cutoff_at",
            "finalized_cutoff_slot", "policy_hash", "policy_id",
        }
    }
    expected_hash = _sha(policy_payload)
    if plan["policy_hash"] != expected_hash or plan["policy_id"] != _identifier("capol", policy_payload):
        raise CandidateAcquisitionError("POLICY_IDENTITY_MISMATCH")
    return dict(plan)


def _normalize_observations(
    plan: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    allowed_sources = set(plan["allowed_sources"])
    seen_rounds: dict[int, tuple[Any, ...]] = {}
    for raw in observations:
        source = str(raw.get("source_name") or "")
        request_kind = str(raw.get("request_kind") or "")
        if source not in allowed_sources:
            raise CandidateAcquisitionError("SOURCE_NOT_IN_FROZEN_PLAN", source)
        decision = can_request_source(source, request_kind, recent_request_count=0)
        if not decision.allowed:
            raise CandidateAcquisitionError(
                "SOURCE_GOVERNOR_REJECTED", f"{source}:{request_kind}:{decision.reason}"
            )
        ordinal = raw.get("round_ordinal")
        if type(ordinal) is not int or ordinal < 1:
            raise CandidateAcquisitionError("INVALID_ROUND_ORDINAL")
        round_mode = str(raw.get("round_mode") or "FROZEN_OFFLINE")
        source_status = str(raw.get("source_status") or "COMPLETE")
        if round_mode not in {"FROZEN_OFFLINE", "LIVE_TAIL", "BACKFILL"}:
            raise CandidateAcquisitionError("UNSUPPORTED_ROUND_MODE", round_mode)
        if source_status not in {
            "COMPLETE", "STALE", "PROVIDER_FAILURE", "BUDGET_EXHAUSTED",
            "COVERAGE_INCOMPLETE", "UNSUPPORTED_CONTRACT", "MALFORMED",
        }:
            raise CandidateAcquisitionError("UNSUPPORTED_SOURCE_STATUS", source_status)
        governed_requests = int(raw.get("governed_requests_used") or 1)
        transport_operations = int(raw.get("transport_operations_used") or 1)
        bytes_used = int(raw.get("bytes_used") or 0)
        rows_used = int(raw.get("rows_used") or 1)
        duration_milliseconds = int(raw.get("duration_milliseconds") or 0)
        identity = (
            source, request_kind, round_mode, source_status, raw.get("failure_reason"),
            governed_requests, transport_operations, bytes_used, rows_used,
            duration_milliseconds,
        )
        if ordinal in seen_rounds and seen_rounds[ordinal] != identity:
            raise CandidateAcquisitionError("ROUND_ORDINAL_CONFLICT", str(ordinal))
        seen_rounds[ordinal] = identity
        observed_at = str(raw.get("observed_at") or "")
        expires_at = str(raw.get("expires_at") or "")
        observed_time, expires_time = _iso(observed_at), _iso(expires_at)
        if expires_time < observed_time:
            raise CandidateAcquisitionError("EVIDENCE_EXPIRY_BEFORE_OBSERVATION")
        facts = raw.get("facts") or {}
        if not isinstance(facts, Mapping):
            raise CandidateAcquisitionError("MALFORMED_OBSERVATION_FACTS")
        cursor_range = raw.get("cursor_range")
        if round_mode in {"LIVE_TAIL", "BACKFILL"} and not isinstance(cursor_range, Mapping):
            raise CandidateAcquisitionError("CURSOR_RANGE_REQUIRED", str(ordinal))
        if cursor_range is not None:
            if not isinstance(cursor_range, Mapping):
                raise CandidateAcquisitionError("MALFORMED_CURSOR_RANGE")
            continuity = str(cursor_range.get("continuity_state") or "")
            if continuity not in {"CONTIGUOUS", "GAPPED", "UNKNOWN", "BLOCKED_CONTRACT"}:
                raise CandidateAcquisitionError("UNSUPPORTED_CONTINUITY_STATE", continuity)
            advanced = bool(cursor_range.get("cursor_advanced"))
            if advanced and continuity != "CONTIGUOUS":
                raise CandidateAcquisitionError("CURSOR_ADVANCED_PAST_UNRESOLVED_EVIDENCE")
            required_cursor = {
                "indexed_address", "contract_pin", "decoder_version", "direction",
                "continuity_state", "cursor_advanced",
            }
            if required_cursor - set(cursor_range):
                raise CandidateAcquisitionError("INCOMPLETE_CURSOR_RANGE")
            if cursor_range["direction"] not in {"FORWARD", "BACKWARD"}:
                raise CandidateAcquisitionError("UNSUPPORTED_CURSOR_DIRECTION")
        item = {
            "round_ordinal": ordinal,
            "round_mode": round_mode,
            "source_name": source,
            "request_kind": request_kind,
            "source_status": source_status,
            "failure_reason": raw.get("failure_reason"),
            "observed_at": observed_at,
            "expires_at": expires_at,
            "mint": str(raw.get("mint") or "").strip() or None,
            "pool": str(raw.get("pool") or "").strip() or None,
            "pool_program_id": str(raw.get("pool_program_id") or "").strip() or None,
            "base_mint": str(raw.get("base_mint") or "").strip() or None,
            "quote_mint": str(raw.get("quote_mint") or "").strip() or None,
            "token_program_id": str(raw.get("token_program_id") or "").strip() or None,
            "venue_label": str(raw.get("venue_label") or "").strip() or None,
            "lineage_claim": str(raw.get("lineage_claim") or "").strip() or None,
            "facts": dict(facts),
            "governed_requests_used": governed_requests,
            "transport_operations_used": transport_operations,
            "bytes_used": bytes_used,
            "rows_used": rows_used,
            "duration_milliseconds": duration_milliseconds,
            "scheduler_job_kind": SCHEDULER_JOB_KIND,
            "source_governor_allowed": True,
            "cursor_range": dict(cursor_range) if cursor_range is not None else None,
        }
        for key in (
            "governed_requests_used", "transport_operations_used", "bytes_used",
            "rows_used", "duration_milliseconds",
        ):
            if item[key] < 0:
                raise CandidateAcquisitionError("NEGATIVE_OPERATION_ACCOUNTING", key)
        content_payload = {key: value for key, value in item.items() if key != "source_governor_allowed"}
        item["content_hash"] = _sha(content_payload)
        item["observation_id"] = _identifier(
            "caobs", (plan["execution_id"], content_payload)
        )
        normalized.append(item)
    normalized.sort(key=lambda item: (item["round_ordinal"], item["source_name"], item["content_hash"]))
    round_usage: dict[int, tuple[str, str, int]] = {}
    for item in normalized:
        round_usage.setdefault(
            int(item["round_ordinal"]),
            (str(item["source_name"]), str(item["request_kind"]), int(item["governed_requests_used"])),
        )
    usage: Counter[tuple[str, str]] = Counter()
    for source, request_kind, count in round_usage.values():
        usage[(source, request_kind)] += count
    budgets = plan["source_budgets"]
    if not isinstance(budgets, Mapping):
        raise CandidateAcquisitionError("MALFORMED_SOURCE_BUDGETS")
    for (source, request_kind), count in usage.items():
        source_budget = budgets.get(source)
        limit = source_budget.get(request_kind) if isinstance(source_budget, Mapping) else None
        if type(limit) is not int or limit < 0:
            raise CandidateAcquisitionError("SOURCE_BUDGET_NOT_DEFINED", f"{source}:{request_kind}")
        if count > limit:
            raise CandidateAcquisitionError(
                "SOURCE_BUDGET_EXHAUSTED", f"{source}:{request_kind}:{count}>{limit}"
            )
    return normalized


def _categorical_status(facts: Iterable[Mapping[str, Any]], key: str) -> tuple[str, str]:
    values = {str(fact.get(key)) for fact in facts if fact.get(key) is not None}
    if not values:
        return "FAIL", f"{key.upper()}_MISSING"
    if "CONFLICT" in values or ("PASS" in values and "FAIL" in values):
        return "FAIL", f"{key.upper()}_CONFLICT"
    if "FAIL" in values:
        return "FAIL", f"{key.upper()}_FAILED"
    if values == {"PASS"}:
        return "PASS", f"{key.upper()}_PASS"
    return "FAIL", f"{key.upper()}_UNSUPPORTED"


def _mint_categorical_status(
    facts: Iterable[Mapping[str, Any]], *, candidate_mint: str
) -> tuple[str, str]:
    """Validate exact mint-evidence merge before evaluating chain-mint status."""
    materialized = [dict(fact) for fact in facts]
    for fact in materialized:
        if fact.get("mint_account_evidence_version") is None:
            continue
        request_target = str(fact.get("mint_request_target") or "")
        response_address = fact.get("mint_response_address")
        if request_target != candidate_mint:
            return "FAIL", "MINT_EVIDENCE_MERGE_KEY_MISMATCH"
        if response_address is not None and str(response_address) != request_target:
            return "FAIL", "MINT_TARGET_MISMATCH"
    outcome, generic_reason = _categorical_status(materialized, "mint_status")
    if outcome == "PASS":
        return outcome, generic_reason
    precise = {
        str(fact["mint_failure_reason"])
        for fact in materialized
        if fact.get("mint_status") == "FAIL" and fact.get("mint_failure_reason")
    }
    if len(precise) == 1:
        return "FAIL", next(iter(precise))
    if len(precise) > 1:
        return "FAIL", "MINT_EVIDENCE_REASON_CONFLICT"
    return outcome, generic_reason


def _pool_categorical_status(
    facts: Iterable[Mapping[str, Any]], *, candidate_pool: str | None
) -> tuple[str, str]:
    """Preserve the earliest exact pool-target/role/program failure."""
    materialized = [dict(fact) for fact in facts]
    for fact in materialized:
        target = fact.get("pool_evidence_target")
        if target is not None and candidate_pool is not None and str(target) != candidate_pool:
            return "FAIL", "POOL_TARGET_MISMATCH"
    outcome, generic_reason = _categorical_status(materialized, "pool_status")
    if outcome == "PASS":
        return outcome, generic_reason
    precise = {
        str(fact["pool_failure_reason"])
        for fact in materialized
        if fact.get("pool_status") == "FAIL" and fact.get("pool_failure_reason")
    }
    if len(precise) == 1:
        return "FAIL", next(iter(precise))
    if len(precise) > 1:
        return "FAIL", "POOL_EVIDENCE_REASON_CONFLICT"
    return outcome, generic_reason


def _atomic_tracking_and_cooldown_recheck(
    connection: sqlite3.Connection,
    observations: Sequence[Mapping[str, Any]],
    *,
    assessed_at: str,
    execution_id: str,
) -> list[dict[str, Any]]:
    """Bind the tracking gate to current authoritative state under one write lock."""
    instant = _iso(assessed_at)
    row = connection.execute(
        "SELECT COALESCE(MAX(last_selected_batch_seq), 0) "
        "FROM printer_selection_rotation_state"
    ).fetchone()
    next_batch_seq = int(row[0] or 0) + 1
    decisions: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}
    result: list[dict[str, Any]] = []
    for source_item in observations:
        item = dict(source_item)
        facts = dict(item.get("facts") or {})
        mint = str(item.get("mint") or "")
        pool = str(item.get("pool") or "")
        if mint and pool:
            key = (mint, pool)
            decision = decisions.get(key)
            if decision is None:
                reasons: list[str] = []
                for lane in (
                    TokenLifecycleState.TRACK_FAST,
                    TokenLifecycleState.TRACK_NORMAL,
                ):
                    assessment = assess_tracking_handoff_by_identity(
                        connection,
                        token_mint=mint,
                        pair_address=pool,
                        tracking_lane=lane,
                        assessed_at=instant,
                    )
                    if not assessment.eligible:
                        reasons.append(str(assessment.reason_code or "TRACKING_STATE_BLOCKED"))
                token_ok, token_reason = check_token_selection_cooldown(
                    connection, mint, next_batch_seq
                )
                pair_ok, pair_reason = check_pair_selection_cooldown(
                    connection, pool, next_batch_seq
                )
                if not token_ok:
                    reasons.append(token_reason)
                if not pair_ok:
                    reasons.append(pair_reason)
                decision = ("PASS" if not reasons else "FAIL", tuple(sorted(set(reasons))))
                decisions[key] = decision
            facts["tracking_status"] = decision[0]
            facts["tracking_atomic_recheck"] = decision[0]
            facts["tracking_atomic_recheck_reasons"] = list(decision[1])
            facts["tracking_atomic_recheck_at"] = assessed_at
            facts["selection_cooldown_batch_seq"] = next_batch_seq
            item["facts"] = facts
            content_payload = {
                key_name: value
                for key_name, value in item.items()
                if key_name not in {"source_governor_allowed", "content_hash", "observation_id"}
            }
            item["content_hash"] = _sha(content_payload)
            item["observation_id"] = _identifier(
                "caobs", (execution_id, content_payload)
            )
        result.append(item)
    result.sort(
        key=lambda value: (
            value["round_ordinal"], value["source_name"], value["content_hash"]
        )
    )
    return result


def _cursor_table_exists(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='printer_candidate_acquisition_cursors'"
    ).fetchone() is not None


def _validate_current_cursor_heads(
    connection: sqlite3.Connection, observations: Sequence[Mapping[str, Any]]
) -> None:
    if not _cursor_table_exists(connection):
        return
    seen: dict[tuple[str, str, str, str, str], tuple[Any, ...]] = {}
    for item in observations:
        cursor = item.get("cursor_range")
        if not cursor:
            continue
        namespace = (
            "solana-mainnet",
            str(cursor["indexed_address"]),
            str(cursor["contract_pin"]),
            str(cursor["decoder_version"]),
            str(cursor["direction"]),
        )
        range_identity = (
            cursor.get("start_slot"), cursor.get("start_signature"),
            cursor.get("end_slot"), cursor.get("end_signature"),
            cursor.get("continuity_state"), bool(cursor.get("cursor_advanced")),
            cursor.get("unresolved_reason"), cursor.get("range_mode"),
        )
        if namespace in seen and seen[namespace] != range_identity:
            raise CandidateAcquisitionError(
                "CURSOR_NAMESPACE_RANGE_CONFLICT", str(cursor["indexed_address"])
            )
        if namespace in seen:
            continue
        seen[namespace] = range_identity
        prior = connection.execute(
            """SELECT boundary_slot,boundary_signature
               FROM printer_candidate_acquisition_cursors
               WHERE network=? AND indexed_address=? AND contract_pin=?
                 AND decoder_version=? AND direction=?""",
            namespace,
        ).fetchone()
        if prior is None:
            continue
        if (
            cursor.get("start_slot") != prior["boundary_slot"]
            or cursor.get("start_signature") != prior["boundary_signature"]
        ):
            raise CandidateAcquisitionError(
                "CURSOR_START_MISMATCH", str(cursor["indexed_address"])
            )


def _advance_current_cursor_heads(
    connection: sqlite3.Connection,
    *,
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> None:
    if not _cursor_table_exists(connection):
        return
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in observations:
        ordinal = int(item["round_ordinal"])
        cursor = item.get("cursor_range")
        if not cursor:
            continue
        namespace = (
            str(plan["network"]), str(cursor["indexed_address"]),
            str(cursor["contract_pin"]), str(cursor["decoder_version"]),
            str(cursor["direction"]),
        )
        if namespace in seen:
            continue
        seen.add(namespace)
        if not bool(cursor.get("cursor_advanced")):
            continue
        if cursor.get("continuity_state") != "CONTIGUOUS":
            raise CandidateAcquisitionError("CURSOR_ADVANCED_PAST_UNRESOLVED_EVIDENCE")
        if cursor.get("end_slot") is None and not cursor.get("end_signature"):
            raise CandidateAcquisitionError("CURSOR_END_BOUNDARY_REQUIRED")
        cursor_payload = {
            "execution_id": plan["execution_id"],
            "round_ordinal": ordinal,
            **cursor,
        }
        range_id = _identifier("cange", cursor_payload)
        prior = connection.execute(
            """SELECT cursor_version FROM printer_candidate_acquisition_cursors
               WHERE network=? AND indexed_address=? AND contract_pin=?
                 AND decoder_version=? AND direction=?""",
            namespace,
        ).fetchone()
        version = 1 if prior is None else int(prior[0]) + 1
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_cursors(
                   network,indexed_address,contract_pin,decoder_version,direction,
                   boundary_slot,boundary_signature,last_range_id,last_execution_id,
                   cursor_version,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(network,indexed_address,contract_pin,decoder_version,direction)
               DO UPDATE SET boundary_slot=excluded.boundary_slot,
                   boundary_signature=excluded.boundary_signature,
                   last_range_id=excluded.last_range_id,
                   last_execution_id=excluded.last_execution_id,
                   cursor_version=excluded.cursor_version,
                   updated_at=excluded.updated_at""",
            (
                *namespace, cursor.get("end_slot"),
                cursor.get("end_signature"), range_id, plan["execution_id"], version,
                plan["cutoff_at"],
            ),
        )


def _lineage_state(group: Sequence[Mapping[str, Any]]) -> str:
    claims = {str(item["lineage_claim"]) for item in group if item.get("lineage_claim")}
    branch_facts = {
        str((item.get("facts") or {}).get("pump_migration_branch") or "")
        for item in group
    }
    if "CONFLICTING_LINEAGE" in claims:
        return "CONFLICTING_LINEAGE"
    if "PUMP_LINEAGE_CONFLICT" in branch_facts:
        return "CONFLICTING_LINEAGE"
    pump = "PUMP_GRADUATION_CONFIRMED" in claims or "PUMP_ORIGIN_CONFIRMED" in claims
    non_pump = "NON_PUMP_POOL_CONFIRMED" in claims
    if pump and non_pump:
        return "CONFLICTING_LINEAGE"
    if "PUMP_GRADUATION_CONFIRMED" in claims:
        return "PUMP_GRADUATION_CONFIRMED"
    # A categorical Pump graduation claim with incomplete/failed exact proof
    # must remain a rejected Pump branch. It cannot downgrade to a generic or
    # unknown-origin lineage merely because current-pool evidence also exists.
    if "PUMP_GRADUATION_CLAIMED" in branch_facts:
        return "UNSUPPORTED_LINEAGE"
    if "PUMP_ORIGIN_CONFIRMED" in claims:
        return "PUMP_ORIGIN_CONFIRMED"
    if non_pump:
        return "NON_PUMP_POOL_CONFIRMED"
    if "UNSUPPORTED_LINEAGE" in claims:
        return "UNSUPPORTED_LINEAGE"
    return "UNKNOWN_ORIGIN"


def _lineage_gate(lineage: str, facts: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    values: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        for key, value in fact.items():
            if value is not None:
                values[str(key)].add(_canonical(value))
    if any(len(items) > 1 for key, items in values.items() if key.startswith("pump")):
        return "FAIL", "PUMP_LINEAGE_FACT_CONFLICT"
    merged = {
        key: json.loads(next(iter(items)))
        for key, items in values.items() if len(items) == 1
    }
    if lineage == "PUMP_GRADUATION_CONFIRMED":
        required = {
            "pump_origin_signature",
            "pump_origin_contract_hash",
            "pump_migration_signature",
            "pump_migration_contract_hash",
            "pumpswap_account_hash",
            "pumpswap_contract_hash",
        }
        if required - set(merged):
            return "FAIL", "PUMP_PROOF_INCOMPLETE"
        if merged.get("pump_origin_contract_hash") != PUMP_IDL_SHA256:
            return "FAIL", "PUMP_ORIGIN_CONTRACT_MISMATCH"
        if merged.get("pump_migration_contract_hash") != PUMP_IDL_SHA256:
            return "FAIL", "PUMP_MIGRATION_CONTRACT_MISMATCH"
        if merged.get("pumpswap_contract_hash") != PUMPSWAP_IDL_SHA256:
            return "FAIL", "PUMPSWAP_CONTRACT_MISMATCH"
        if merged.get("pumpswap_index") != 0:
            return "FAIL", "PUMP_CANONICAL_POOL_INDEX_REQUIRED"
        return "PASS", "PUMP_EXACT_LINEAGE_PASS"
    if lineage == "PUMP_ORIGIN_CONFIRMED":
        required = {
            "pump_origin_signature",
            "pump_origin_contract_hash",
            "pump_bonding_curve_address",
            "pump_bonding_curve_account_hash",
            "pump_bonding_curve_contract_hash",
            "pump_bonding_curve_complete",
        }
        if required - set(merged):
            return "FAIL", "PUMP_BONDING_CURVE_PROOF_INCOMPLETE"
        if (
            merged.get("pump_origin_contract_hash") != PUMP_IDL_SHA256
            or merged.get("pump_bonding_curve_contract_hash") != PUMP_IDL_SHA256
        ):
            return "FAIL", "PUMP_BONDING_CURVE_CONTRACT_MISMATCH"
        if merged.get("pump_bonding_curve_complete") is not False:
            return "FAIL", "PUMP_BONDING_CURVE_COMPLETE_REQUIRES_GRADUATION"
        return "PASS", "PUMP_EXACT_BONDING_CURVE_LINEAGE_PASS"
    if lineage in {"NON_PUMP_POOL_CONFIRMED", "UNKNOWN_ORIGIN"}:
        return "PASS", f"{lineage}_PRESENT_POOL_PASS"
    if lineage in {"UNSUPPORTED_LINEAGE", "CONFLICTING_LINEAGE"}:
        reasons = {
            str(fact.get("pump_migration_failure_reason") or "")
            for fact in facts
            if fact.get("pump_migration_failure_reason")
        }
        if len(reasons) == 1:
            return "FAIL", next(iter(reasons))
        if reasons:
            return "FAIL", "PUMP_MIGRATION_MULTIPLE_FAILURE_REASONS"
    return "FAIL", f"{lineage}_REJECTED"


def _build_candidates(plan: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    pool_mints: dict[str, set[str]] = defaultdict(set)
    for observation in observations:
        if observation.get("mint"):
            mint_identity = str(observation["mint"])
            groups[mint_identity].append(observation)
            if observation.get("pool"):
                pool_mints[str(observation["pool"])].add(mint_identity)
    cross_mint_pool_conflicts = {
        pool for pool, referenced_mints in pool_mints.items() if len(referenced_mints) > 1
    }
    mints = sorted(groups)
    if len(mints) > int(plan["candidate_acquisition_capacity"]):
        mints = mints[: int(plan["candidate_acquisition_capacity"])]
    cutoff = _iso(str(plan["cutoff_at"]))
    candidates: list[dict[str, Any]] = []
    for mint in mints:
        group = groups[mint]
        pools = {str(item["pool"]) for item in group if item.get("pool")}
        # Base/quote/program identity belongs to an exact pool relationship.
        # Mint, holder, and safety observations may repeat the candidate mint
        # as a convenience field but cannot create or conflict a pool role.
        pool_identity_observations = [item for item in group if item.get("pool")]
        programs = {
            str(item["pool_program_id"])
            for item in pool_identity_observations if item.get("pool_program_id")
        }
        bases = {
            str(item["base_mint"])
            for item in pool_identity_observations if item.get("base_mint")
        }
        quotes = {
            str(item["quote_mint"])
            for item in pool_identity_observations if item.get("quote_mint")
        }
        token_programs = {str(item["token_program_id"]) for item in group if item.get("token_program_id")}
        identity_conflict = (
            len(pools) > 1 or len(programs) > 1 or len(bases) > 1 or len(quotes) > 1
            or len(token_programs) > 1 or bool(pools & cross_mint_pool_conflicts)
        )
        pool = next(iter(sorted(pools)), None)
        pool_program = next(iter(sorted(programs)), None)
        base_mint = next(iter(sorted(bases)), None)
        quote_mint = next(iter(sorted(quotes)), None)
        token_program = next(iter(sorted(token_programs)), None)
        if identity_conflict:
            # The raw linked observations retain every conflicting value. A
            # conflicted selected-pool identity is deliberately NULL so two
            # mints claiming one pool cannot violate the canonical uniqueness
            # constraint before the structured identity rejection is stored.
            pool = None
        identity_available = bool(
            pool
            and base_mint
            and token_program in SUPPORTED_TOKEN_PROGRAMS
        )
        pool_quote_complete = bool(
            identity_available
            and pool_program
            and base_mint == mint
            and quote_mint in ALLOWED_QUOTE_MINTS
        )
        identity_status = (
            "IDENTITY_CONFLICT"
            if identity_conflict
            else "IDENTITY_MERGED" if identity_available else "IDENTITY_INCOMPLETE"
        )
        lineage = _lineage_state(group)
        facts = [dict(item["facts"]) for item in group]
        expires_at = min(str(item["expires_at"]) for item in group)
        stale = _iso(expires_at) <= cutoff or any(item["source_status"] == "STALE" for item in group)
        stages: list[dict[str, Any]] = []
        first_failure: str | None = None
        for ordinal, (stage_name, fact_key) in enumerate(STAGES, 1):
            if first_failure is not None:
                outcome, reason = "NOT_REACHED", "PRIOR_STAGE_FAILED"
            elif stage_name == "IDENTITY_AVAILABLE" and identity_status != "IDENTITY_MERGED":
                outcome, reason = "FAIL", identity_status
            elif stage_name == "TOKEN_PROGRAM_VALID" and token_program not in SUPPORTED_TOKEN_PROGRAMS:
                outcome, reason = "FAIL", "UNSUPPORTED_TOKEN_PROGRAM"
            elif stage_name == "POOL_QUOTE_VALID":
                outcome, reason = _pool_categorical_status(
                    facts, candidate_pool=pool
                )
                if outcome == "PASS" and base_mint != mint:
                    outcome, reason = "FAIL", "BASE_QUOTE_ORIENTATION_MISMATCH"
                elif outcome == "PASS" and not pool_quote_complete:
                    outcome, reason = "FAIL", "EXACT_POOL_QUOTE_IDENTITY_REQUIRED"
            elif stage_name == "MARKET_FRESH" and stale:
                outcome, reason = "FAIL", "STALE_OR_EXPIRED_EVIDENCE"
            elif stage_name == "LINEAGE_VALID":
                outcome, reason = _lineage_gate(lineage, facts)
            elif stage_name == "CHAIN_MINT_VALID":
                outcome, reason = _mint_categorical_status(
                    facts, candidate_mint=mint
                )
            else:
                outcome, reason = _categorical_status(facts, fact_key)
            if outcome == "FAIL" and first_failure is None:
                first_failure = reason
            stages.append(
                {
                    "stage_ordinal": ordinal,
                    "stage_name": stage_name,
                    "stage_outcome": outcome,
                    "reason_code": reason,
                }
            )
        admitted = first_failure is None
        identity_payload = {
            "execution_id": plan["execution_id"],
            "mint": mint,
            "pool": pool,
            "pool_program_id": pool_program,
            "base_mint": base_mint,
            "quote_mint": quote_mint,
            "token_program_id": token_program,
            "lineage_state": lineage,
            "identity_status": identity_status,
        }
        candidate_id = _identifier("candid", identity_payload)
        source_ids = sorted(item["observation_id"] for item in group)
        certificate_payload = {
            "certificate_version": CERTIFICATE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "policy_hash": plan["policy_hash"],
            "git_provenance": plan["git_provenance"],
            "execution_id": plan["execution_id"],
            "window": {
                "start": plan["window_start"],
                "end": plan["window_end"],
                "cutoff_at": plan["cutoff_at"],
                "finalized_cutoff_slot": plan["finalized_cutoff_slot"],
            },
            "identity": identity_payload,
            "source_observation_ids": source_ids,
            "source_provenance": sorted(
                {
                    (item["source_name"], item["request_kind"], item["content_hash"])
                    for item in group
                }
            ),
            "lineage_state": lineage,
            "market_and_freshness_facts": facts,
            "stage_outcomes": stages,
            "admission_outcome": "ADMITTED" if admitted else "REJECTED",
            "admission_reason": "ALL_CATEGORICAL_GATES_PASS" if admitted else str(first_failure),
            "issued_at": plan["cutoff_at"],
            "expires_at": expires_at,
            "invalidation_categories": (
                "EVIDENCE_EXPIRED",
                "IDENTITY_CHANGED",
                "TRACKING_STATE_CHANGED",
                "CONTRACT_PIN_CHANGED",
            ),
            "no_financial_or_action_fields": True,
        }
        _assert_no_forbidden_fields(certificate_payload)
        certificate_hash = _sha(certificate_payload)
        certificate_payload["certificate_hash"] = certificate_hash
        candidates.append(
            {
                **identity_payload,
                "candidate_id": candidate_id,
                "identity_hash": _sha(identity_payload),
                "observations": group,
                "stages": stages,
                "admitted": admitted,
                "admission_reason": certificate_payload["admission_reason"],
                "issued_at": plan["cutoff_at"],
                "expires_at": expires_at,
                "certificate_id": _identifier("cacert", certificate_hash),
                "certificate_hash": certificate_hash,
                "certificate_json": _canonical(certificate_payload),
            }
        )
    return candidates


def _assert_no_forbidden_fields(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_CERTIFICATE_KEYS:
                raise CandidateAcquisitionError("FORBIDDEN_CERTIFICATE_FIELD", normalized)
            _assert_no_forbidden_fields(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_forbidden_fields(item)


def _selection(plan: Mapping[str, Any], admitted: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    n = int(plan["selection_capacity"])
    if len(admitted) < n:
        return [], None, None
    ordered = sorted(
        admitted,
        key=lambda item: (
            _sha(
                f"{plan['seed_domain']}{plan['selection_seed']}|{item['mint']}|"
                f"{item['pool']}|{item['certificate_hash']}"
            ),
            str(item["mint"]),
            str(item["pool"]),
        ),
    )
    selected: list[dict[str, Any]] = []
    for ordinal, item in enumerate(ordered[:n], 1):
        item_payload = {
            "item_ordinal": ordinal,
            "certificate_id": item["certificate_id"],
            "certificate_hash": item["certificate_hash"],
            "mint": item["mint"],
            "pool": item["pool"],
        }
        selected.append({**item_payload, "item_hash": _sha(item_payload)})
    readiness = (
        "READY_WITH_RESERVE"
        if len(admitted) >= int(plan["candidate_reserve_target"])
        else "READY_EXACT_NO_SPARE"
    )
    manifest_payload = {
        "execution_id": plan["execution_id"],
        "policy_id": plan["policy_id"],
        "selection_capacity": n,
        "item_count": n,
        "readiness_status": readiness,
        "runtime_neutral": True,
        "approved_active_memory_capacity": 2,
        "selection_seed": plan["selection_seed"],
        "ordered_item_hashes": [item["item_hash"] for item in selected],
    }
    manifest_hash = _sha(manifest_payload)
    return selected, readiness, manifest_hash


def _failure_family(observations: Sequence[Mapping[str, Any]], candidates: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    statuses = {str(item["source_status"]) for item in observations}
    for status, family in FAILURE_PRECEDENCE:
        if status in statuses:
            return family, status
    pump_failures = [
        (
            str(fact.get("pump_migration_failure_family") or ""),
            str(fact.get("pump_migration_failure_reason") or ""),
        )
        for candidate in candidates
        for observation in candidate["observations"]
        for fact in (observation.get("facts") or {},)
        if fact.get("pump_migration_failure_family")
    ]
    pump_family_precedence = (
        "UNSUPPORTED_CONTRACT",
        "SOURCE_PROVIDER_FAILURE",
        "BUDGET_EXHAUSTION",
        "COVERAGE_FAILURE",
        "STALE_OR_INCOMPLETE_EVIDENCE",
        "IDENTITY_MERGE_FAILURE",
        "ADMISSION_FAILURE",
    )
    for family in pump_family_precedence:
        reasons = sorted({
            reason for failure_family, reason in pump_failures
            if failure_family == family and reason
        })
        if reasons:
            return family, reasons[0] if len(reasons) == 1 else "MULTIPLE_PUMP_MIGRATION_FAILURES"
    mint_reasons = {
        str(stage["reason_code"])
        for candidate in candidates
        for stage in candidate["stages"]
        if stage["stage_name"] == "CHAIN_MINT_VALID"
        and stage["stage_outcome"] == "FAIL"
    }
    if mint_reasons:
        if mint_reasons & {
            "MINT_EVIDENCE_MERGE_KEY_MISMATCH", "MINT_TARGET_MISMATCH"
        }:
            return "IDENTITY_MERGE_FAILURE", sorted(mint_reasons)[0]
        return (
            "ADMISSION_FAILURE",
            next(iter(mint_reasons))
            if len(mint_reasons) == 1
            else "CHAIN_MINT_VALID_MULTIPLE_REASONS",
        )
    if any(item["identity_status"] == "IDENTITY_CONFLICT" for item in candidates):
        return "IDENTITY_MERGE_FAILURE", "IDENTITY_CONFLICT"
    if candidates and any(not item["admitted"] for item in candidates):
        first_reasons = {
            str(stage["reason_code"])
            for candidate in candidates
            for stage in candidate["stages"]
            if stage["stage_outcome"] == "FAIL"
        }
        if first_reasons and all(
            reason.endswith("_MISSING")
            or reason in {
                "IDENTITY_INCOMPLETE",
                "EXACT_POOL_QUOTE_IDENTITY_REQUIRED",
                "PUMP_BONDING_CURVE_PROOF_INCOMPLETE",
                "PUMP_PROOF_INCOMPLETE",
            }
            for reason in first_reasons
        ):
            return (
                "STALE_OR_INCOMPLETE_EVIDENCE",
                next(iter(first_reasons))
                if len(first_reasons) == 1
                else "MULTIPLE_REQUIRED_EVIDENCE_GAPS",
            )
        return (
            "ADMISSION_FAILURE",
            next(iter(first_reasons))
            if len(first_reasons) == 1
            else "CATEGORICAL_ADMISSION_REJECTIONS",
        )
    return "INSUFFICIENT_ELIGIBLE_POOL", "COMPLETE_COVERAGE_FEWER_THAN_N"


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    existing = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    return {
        table: (
            int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            if table in existing else 0
        )
        for table in FORBIDDEN_CAPABILITY_TABLES
    }


def _source_report(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    observations_per_source = Counter(str(item["source_name"]) for item in observations)
    mint_sources: dict[str, set[str]] = defaultdict(set)
    governed_operations: dict[str, Counter[str]] = defaultdict(Counter)
    accounted_rounds: set[int] = set()
    for item in observations:
        if item.get("mint"):
            mint_sources[str(item["mint"])].add(str(item["source_name"]))
        ordinal = int(item["round_ordinal"])
        if ordinal not in accounted_rounds:
            accounted_rounds.add(ordinal)
            governed_operations[str(item["source_name"])][str(item["request_kind"])] += int(
                item["governed_requests_used"]
            )
    unique_contribution = Counter()
    for sources in mint_sources.values():
        if len(sources) == 1:
            unique_contribution[next(iter(sources))] += 1
    return {
        "observations_per_source": dict(sorted(observations_per_source.items())),
        "unique_candidate_contribution": dict(sorted(unique_contribution.items())),
        "cross_source_overlap_count": sum(1 for sources in mint_sources.values() if len(sources) > 1),
        "governed_operations": {
            source: dict(sorted(counter.items()))
            for source, counter in sorted(governed_operations.items())
        },
    }


def run_candidate_acquisition(
    db_path: str | Path,
    *,
    plan: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run one atomic frozen acquisition execution, or replay it idempotently."""
    frozen_plan = _validate_plan(plan)
    normalized = _normalize_observations(frozen_plan, observations)
    database = Path(db_path)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        normalized = _atomic_tracking_and_cooldown_recheck(
            connection, normalized, assessed_at=str(frozen_plan["cutoff_at"]),
            execution_id=str(frozen_plan["execution_id"]),
        )
        input_payload = {"plan": frozen_plan, "observations": normalized}
        input_hash = _sha(input_payload)
        replay_identity = _sha(
            {
                "execution_id": frozen_plan["execution_id"],
                "policy_hash": frozen_plan["policy_hash"],
                "input_hash": input_hash,
            }
        )
        prior = connection.execute(
            "SELECT input_hash, report_json, report_hash FROM printer_candidate_acquisition_reports WHERE execution_id=?",
            (frozen_plan["execution_id"],),
        ).fetchone()
        if prior is not None:
            if prior["input_hash"] != input_hash or _sha(json.loads(prior["report_json"])) != prior["report_hash"]:
                raise CandidateAcquisitionError("REPLAY_IDENTITY_CONFLICT")
            return json.loads(prior["report_json"])

        _validate_current_cursor_heads(connection, normalized)
        before = _table_counts(connection)
        candidates = _build_candidates(frozen_plan, normalized)
        admitted = [item for item in candidates if item["admitted"]]
        selected, readiness, manifest_hash = _selection(frozen_plan, admitted)
        success = len(selected) == int(frozen_plan["selection_capacity"])
        failure_family = failure_reason = None
        if not success:
            failure_family, failure_reason = _failure_family(normalized, candidates)
        manifest_id = _identifier("caman", manifest_hash) if manifest_hash else None
        exclusions = Counter(
            next(stage["stage_name"] for stage in item["stages"] if stage["stage_outcome"] == "FAIL")
            for item in candidates if not item["admitted"]
        )
        source_report = _source_report(normalized)
        cursor_states = Counter(
            str(item["cursor_range"]["continuity_state"])
            for item in normalized if item.get("cursor_range")
        )

        report = {
            "verdict": "EXACT_N_MANIFEST_READY" if success else "EXACT_N_MANIFEST_NOT_CREATED",
            "execution_id": frozen_plan["execution_id"],
            "policy_id": frozen_plan["policy_id"],
            "policy_hash": frozen_plan["policy_hash"],
            "input_hash": input_hash,
            "replay_identity": replay_identity,
            "capacity": {
                "candidate_acquisition_capacity": frozen_plan["candidate_acquisition_capacity"],
                "candidate_reserve_capacity": frozen_plan["candidate_reserve_target"],
                "selection_capacity": frozen_plan["selection_capacity"],
                "approved_active_memory_capacity": 2,
            },
            "source_contribution": source_report,
            "cursor_continuity": dict(sorted(cursor_states.items())),
            "source_failures": [
                {
                    "source_name": item["source_name"],
                    "source_status": item["source_status"],
                    "failure_reason": item["failure_reason"],
                }
                for item in normalized if item["source_status"] != "COMPLETE"
            ],
            "exclusions_by_funnel_stage": dict(sorted(exclusions.items())),
            "certificates_issued": len(candidates),
            "certificates_admitted": len(admitted),
            "certificates_rejected": len(candidates) - len(admitted),
            "stale_or_expired_evidence_count": sum(
                1 for item in candidates if item["admission_reason"] == "STALE_OR_EXPIRED_EVIDENCE"
            ),
            "reserve_size": len(admitted),
            "reserve_readiness": readiness,
            "exact_n_selection_result": "SUCCESS" if success else "ALL_OR_NONE_FAILURE",
            "selected_count": len(selected),
            "manifest_id": manifest_id,
            "manifest_hash": manifest_hash,
            "ordered_item_hashes": [item["item_hash"] for item in selected],
            "failure_family": failure_family,
            "failure_reason": failure_reason,
            "runtime_neutral": True,
            "runtime_handoff_count": 0,
            "active_capacity_lock": 2,
            "forbidden_capability_deltas": {},
            "reliability_claim_status": RELIABILITY_STATUS,
            "fixture_evidence_role": "SYNTHETIC_MECHANICS_ONLY",
        }

        with connection:
            connection.execute(
                """INSERT OR IGNORE INTO printer_candidate_acquisition_policies(
                    policy_id, policy_hash, schema_version, network,
                    selection_capacity, candidate_acquisition_capacity,
                    candidate_reserve_target, approved_active_memory_capacity,
                    selection_seed, seed_domain, allowed_sources_json,
                    source_budgets_json, scheduler_owner, scheduler_job_kind,
                    source_governor_required, no_retry, no_reconnect,
                    git_provenance, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    frozen_plan["policy_id"], frozen_plan["policy_hash"], SCHEMA_VERSION,
                    frozen_plan["network"], frozen_plan["selection_capacity"],
                    frozen_plan["candidate_acquisition_capacity"], frozen_plan["candidate_reserve_target"],
                    2, frozen_plan["selection_seed"], frozen_plan["seed_domain"],
                    _canonical(frozen_plan["allowed_sources"]), _canonical(frozen_plan["source_budgets"]),
                    SCHEDULER_OWNER, SCHEDULER_JOB_KIND, 1, 1, 1,
                    frozen_plan["git_provenance"], frozen_plan["cutoff_at"],
                ),
            )
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_executions(
                    execution_id, policy_id, input_hash, replay_identity,
                    window_start, window_end, cutoff_at, finalized_cutoff_slot,
                    execution_status, failure_family, observed_unique_count,
                    certificate_count, admitted_count, selected_count,
                    manifest_id, runtime_handoff_count, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    frozen_plan["execution_id"], frozen_plan["policy_id"], input_hash,
                    replay_identity, frozen_plan["window_start"], frozen_plan["window_end"],
                    frozen_plan["cutoff_at"], frozen_plan["finalized_cutoff_slot"],
                    "COMPLETED_SUCCESS" if success else "COMPLETED_FAILURE", failure_family,
                    len(candidates), len(candidates), len(admitted), len(selected),
                    manifest_id, 0, frozen_plan["cutoff_at"],
                ),
            )
            round_ids: dict[int, str] = {}
            for item in normalized:
                ordinal = int(item["round_ordinal"])
                if ordinal not in round_ids:
                    round_payload = {
                        "execution_id": frozen_plan["execution_id"], "ordinal": ordinal,
                        "source": item["source_name"], "kind": item["request_kind"],
                    }
                    round_id = _identifier("carnd", round_payload)
                    round_ids[ordinal] = round_id
                    connection.execute(
                        """INSERT INTO printer_candidate_source_rounds(
                            round_id, execution_id, round_ordinal, round_mode,
                            source_name, request_kind, source_status, failure_reason,
                            governed_requests_used, transport_operations_used,
                            bytes_used, rows_used, duration_milliseconds,
                            scheduler_job_kind, source_governor_allowed, content_hash, created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            round_id, frozen_plan["execution_id"], ordinal, item["round_mode"],
                            item["source_name"], item["request_kind"], item["source_status"],
                            item["failure_reason"], item["governed_requests_used"],
                            item["transport_operations_used"], item["bytes_used"], item["rows_used"],
                            item["duration_milliseconds"], SCHEDULER_JOB_KIND, 1,
                            _sha(round_payload), frozen_plan["cutoff_at"],
                        ),
                    )
                connection.execute(
                    """INSERT INTO printer_candidate_source_observations(
                        observation_id, execution_id, round_id, source_name,
                        request_kind, observed_at, expires_at, source_status,
                        mint_identity, pool_address, pool_program_id, base_mint,
                        quote_mint, venue_label, lineage_claim, facts_json,
                        content_hash, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item["observation_id"], frozen_plan["execution_id"], round_ids[ordinal],
                        item["source_name"], item["request_kind"], item["observed_at"],
                        item["expires_at"], item["source_status"], item["mint"], item["pool"],
                        item["pool_program_id"], item["base_mint"], item["quote_mint"],
                        item["venue_label"], item["lineage_claim"], _canonical(item["facts"]),
                        item["content_hash"], frozen_plan["cutoff_at"],
                    ),
                )
            persisted_cursor_rounds: set[int] = set()
            for item in normalized:
                cursor = item.get("cursor_range")
                ordinal = int(item["round_ordinal"])
                if cursor is None or ordinal in persisted_cursor_rounds:
                    continue
                persisted_cursor_rounds.add(ordinal)
                cursor_payload = {
                    "execution_id": frozen_plan["execution_id"],
                    "round_ordinal": ordinal,
                    **cursor,
                }
                connection.execute(
                    """INSERT INTO printer_candidate_cursor_ranges(
                        range_id,execution_id,network,indexed_address,contract_pin,
                        decoder_version,direction,start_slot,start_signature,end_slot,
                        end_signature,continuity_state,cursor_advanced,unresolved_reason,
                        range_hash,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        _identifier("cange", cursor_payload), frozen_plan["execution_id"],
                        frozen_plan["network"], cursor["indexed_address"], cursor["contract_pin"],
                        cursor["decoder_version"], cursor["direction"], cursor.get("start_slot"),
                        cursor.get("start_signature"), cursor.get("end_slot"),
                        cursor.get("end_signature"), cursor["continuity_state"],
                        int(bool(cursor["cursor_advanced"])), cursor.get("unresolved_reason"),
                        _sha(cursor_payload), frozen_plan["cutoff_at"],
                    ),
                )
            _advance_current_cursor_heads(
                connection, plan=frozen_plan, observations=normalized
            )
            for item in candidates:
                connection.execute(
                    """INSERT INTO printer_candidate_identities(
                        candidate_id, execution_id, mint_identity, pool_address,
                        pool_program_id, base_mint, quote_mint, token_program_id,
                        lineage_state, identity_status, identity_hash, created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item["candidate_id"], frozen_plan["execution_id"], item["mint"], item["pool"],
                        item["pool_program_id"], item["base_mint"], item["quote_mint"],
                        item["token_program_id"], item["lineage_state"], item["identity_status"],
                        item["identity_hash"], frozen_plan["cutoff_at"],
                    ),
                )
                for observation in item["observations"]:
                    connection.execute(
                        "INSERT INTO printer_candidate_observation_links(candidate_id,observation_id,contribution_role) VALUES (?,?,?)",
                        (item["candidate_id"], observation["observation_id"], "SOURCE_PROVENANCE"),
                    )
                for stage in item["stages"]:
                    evidence_payload = {"candidate_id": item["candidate_id"], **stage}
                    connection.execute(
                        """INSERT INTO printer_candidate_evidence(
                            evidence_id,candidate_id,stage_ordinal,stage_name,
                            stage_outcome,reason_code,evidence_hash,evidence_json,created_at
                        ) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (
                            _identifier("caevi", evidence_payload), item["candidate_id"],
                            stage["stage_ordinal"], stage["stage_name"], stage["stage_outcome"],
                            stage["reason_code"], _sha(evidence_payload), _canonical(evidence_payload),
                            frozen_plan["cutoff_at"],
                        ),
                    )
                connection.execute(
                    """INSERT INTO printer_candidate_certificates(
                        certificate_id,candidate_id,execution_id,certificate_version,
                        policy_hash,admission_outcome,admission_reason,issued_at,
                        expires_at,certificate_json,certificate_hash,
                        contains_financial_fields,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item["certificate_id"], item["candidate_id"], frozen_plan["execution_id"],
                        CERTIFICATE_VERSION, frozen_plan["policy_hash"],
                        "ADMITTED" if item["admitted"] else "REJECTED", item["admission_reason"],
                        item["issued_at"], item["expires_at"], item["certificate_json"],
                        item["certificate_hash"], 0, frozen_plan["cutoff_at"],
                    ),
                )
                if item["admitted"]:
                    prior_reserve = connection.execute(
                        "SELECT reserve_version FROM printer_candidate_reserve WHERE mint_identity=? AND pool_address=?",
                        (item["mint"], item["pool"]),
                    ).fetchone()
                    version = 1 if prior_reserve is None else int(prior_reserve[0]) + 1
                    connection.execute(
                        """INSERT INTO printer_candidate_reserve(
                            mint_identity,pool_address,current_certificate_id,
                            current_certificate_hash,reserve_version,reserve_status,
                            issued_at,expires_at,last_requalified_at,claimed_manifest_id,updated_at
                        ) VALUES (?,?,?,?,?,'ELIGIBLE_FRESH',?,?,?,?,?)
                        ON CONFLICT(mint_identity,pool_address) DO UPDATE SET
                            current_certificate_id=excluded.current_certificate_id,
                            current_certificate_hash=excluded.current_certificate_hash,
                            reserve_version=excluded.reserve_version,
                            reserve_status='ELIGIBLE_FRESH',issued_at=excluded.issued_at,
                            expires_at=excluded.expires_at,last_requalified_at=excluded.last_requalified_at,
                            claimed_manifest_id=NULL,updated_at=excluded.updated_at""",
                        (
                            item["mint"], item["pool"], item["certificate_id"], item["certificate_hash"],
                            version, item["issued_at"], item["expires_at"], frozen_plan["cutoff_at"],
                            None, frozen_plan["cutoff_at"],
                        ),
                    )
            if success and manifest_id and manifest_hash and readiness:
                connection.execute(
                    """INSERT INTO printer_candidate_manifests(
                        manifest_id,execution_id,policy_id,selection_capacity,
                        expected_item_count,item_count,readiness_status,runtime_neutral,
                        approved_active_memory_capacity,selection_seed,
                        ordered_item_hashes_json,manifest_hash,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        manifest_id, frozen_plan["execution_id"], frozen_plan["policy_id"],
                        frozen_plan["selection_capacity"], frozen_plan["selection_capacity"],
                        len(selected), readiness, 1, 2, frozen_plan["selection_seed"],
                        _canonical([item["item_hash"] for item in selected]), manifest_hash,
                        frozen_plan["cutoff_at"],
                    ),
                )
                for item in selected:
                    connection.execute(
                        """INSERT INTO printer_candidate_manifest_items(
                            manifest_id,item_ordinal,certificate_id,mint_identity,
                            pool_address,certificate_hash,item_hash
                        ) VALUES (?,?,?,?,?,?,?)""",
                        (
                            manifest_id, item["item_ordinal"], item["certificate_id"], item["mint"],
                            item["pool"], item["certificate_hash"], item["item_hash"],
                        ),
                    )
                    connection.execute(
                        """UPDATE printer_candidate_reserve SET
                            reserve_status='CLAIMED_NEUTRAL', claimed_manifest_id=?, updated_at=?
                            WHERE mint_identity=? AND pool_address=?""",
                        (manifest_id, frozen_plan["cutoff_at"], item["mint"], item["pool"]),
                    )
            if not success and failure_family and failure_reason:
                failure_payload = {
                    "execution_id": frozen_plan["execution_id"],
                    "failure_family": failure_family,
                    "reason_code": failure_reason,
                    "required_n": frozen_plan["selection_capacity"],
                    "admitted_count": len(admitted),
                }
                connection.execute(
                    """INSERT INTO printer_candidate_acquisition_failures(
                        failure_id,execution_id,failure_family,reason_code,
                        stage_name,source_name,failure_json,failure_hash,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        _identifier("cafail", failure_payload), frozen_plan["execution_id"],
                        failure_family, failure_reason, None, None, _canonical(failure_payload),
                        _sha(failure_payload), frozen_plan["cutoff_at"],
                    ),
                )
            after = _table_counts(connection)
            deltas = {table: after[table] - before[table] for table in before}
            if any(deltas.values()):
                raise CandidateAcquisitionError("FORBIDDEN_CAPABILITY_DELTA", _canonical(deltas))
            report["forbidden_capability_deltas"] = deltas
            report_hash = _sha(report)
            connection.execute(
                """INSERT INTO printer_candidate_acquisition_reports(
                    execution_id,policy_hash,input_hash,replay_identity,report_json,
                    report_hash,reliability_claim_status,created_at
                ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    frozen_plan["execution_id"], frozen_plan["policy_hash"], input_hash,
                    replay_identity, _canonical(report), report_hash, RELIABILITY_STATUS,
                    frozen_plan["cutoff_at"],
                ),
            )
        return report
    finally:
        connection.close()


def replay_candidate_acquisition_report(db_path: str | Path, execution_id: str) -> dict[str, Any]:
    """Read and verify one canonical report with zero writes/source/Scheduler work."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT * FROM printer_candidate_acquisition_reports WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if row is None:
            raise CandidateAcquisitionError("REPORT_NOT_FOUND", execution_id)
        payload = json.loads(row["report_json"])
        if _sha(payload) != row["report_hash"]:
            raise CandidateAcquisitionError("REPORT_HASH_MISMATCH", execution_id)
        execution = connection.execute(
            "SELECT input_hash,replay_identity FROM printer_candidate_acquisition_executions WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if execution is None or execution["input_hash"] != row["input_hash"] or execution["replay_identity"] != row["replay_identity"]:
            raise CandidateAcquisitionError("REPLAY_IDENTITY_MISMATCH", execution_id)
        return payload
    finally:
        connection.close()


def legacy_two_token_runtime_projection(db_path: str | Path, manifest_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and project exactly two neutral items; never activate runtime."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        manifest = connection.execute(
            "SELECT * FROM printer_candidate_manifests WHERE manifest_id=?", (manifest_id,)
        ).fetchone()
        if manifest is None:
            raise CandidateAcquisitionError("MANIFEST_NOT_FOUND")
        if (
            int(manifest["selection_capacity"]) != 2
            or int(manifest["item_count"]) != 2
            or int(manifest["runtime_neutral"]) != 1
            or int(manifest["approved_active_memory_capacity"]) != 2
        ):
            raise CandidateAcquisitionError("LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO")
        rows = connection.execute(
            "SELECT * FROM printer_candidate_manifest_items WHERE manifest_id=? ORDER BY item_ordinal",
            (manifest_id,),
        ).fetchall()
        if len(rows) != 2 or {int(row["item_ordinal"]) for row in rows} != {1, 2}:
            raise CandidateAcquisitionError("MANIFEST_ITEM_COUNT_MISMATCH")
        selected = [dict(row) for row in rows]
        payload = {
            "execution_id": manifest["execution_id"],
            "policy_id": manifest["policy_id"],
            "selection_capacity": 2,
            "item_count": 2,
            "readiness_status": manifest["readiness_status"],
            "runtime_neutral": True,
            "approved_active_memory_capacity": 2,
            "selection_seed": manifest["selection_seed"],
            "ordered_item_hashes": [row["item_hash"] for row in selected],
        }
        if _sha(payload) != manifest["manifest_hash"]:
            raise CandidateAcquisitionError("MANIFEST_HASH_MISMATCH")
        return tuple(selected)  # type: ignore[return-value]
    finally:
        connection.close()


__all__ = [
    "SCHEMA_VERSION",
    "CERTIFICATE_VERSION",
    "APPROVED_ACTIVE_MEMORY_CAPACITY",
    "PROHIBITED_FOUNDATION_SOURCES",
    "RELIABILITY_STATUS",
    "PUMP_IDL_SHA256",
    "PUMPSWAP_IDL_SHA256",
    "CandidateAcquisitionError",
    "build_acquisition_plan",
    "run_candidate_acquisition",
    "replay_candidate_acquisition_report",
    "legacy_two_token_runtime_projection",
]
