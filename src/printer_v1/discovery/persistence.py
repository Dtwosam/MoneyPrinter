"""Discovery persistence ownership for V2-9.7D.7B.4C.

Cycle-rooted discovery batch/work/observation/merge/selection/report links.
Persistence only: no provider calls, no combined execution, no tracking
activation, and no financial capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence


class DiscoveryPersistenceError(ValueError):
    """Fail-closed discovery persistence contract violation."""


WORK_TYPES = frozenset(
    {
        "DISCOVERY_PUMPFUN_LATEST",
        "DISCOVERY_DEXSCREENER_ACTIVE",
        "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE",
        "DISCOVERY_SOLANA_TRACKER_TRENDING_TOP",
        "DISCOVERY_IDENTITY_MERGE",
        "DISCOVERY_ORIGIN_VERIFICATION",
        "DISCOVERY_PUMPSWAP_CONFIRMATION",
        "DISCOVERY_FIXED_ELIGIBILITY_GATES",
        "DISCOVERY_UNIFORM_SELECTION",
        "DISCOVERY_TRACKING_HANDOFF_SLOT_1",
        "DISCOVERY_TRACKING_HANDOFF_SLOT_2",
    }
)

CHANNELS = frozenset(
    {
        "LATEST_PUMPFUN",
        "TRENDING_PUMPFUN",
        "TOP_PUMPFUN",
        "ACTIVE_PUMPFUN",
    }
)

CONTINUITY_STATES = frozenset({"NONE", "CONTIGUOUS", "GAPPED", "UNKNOWN"})

# Non-authoritative fields must never enter factual observation payloads.
FORBIDDEN_FACTUAL_FIELDS = frozenset(
    {
        "rank",
        "score",
        "gt_score",
        "risk",
        "promoted",
        "popularity",
        "response_order",
        "performanceRank",
        "jupiterVerified",
        "holders",
        "boost",
        "sponsored",
    }
)

LOCKED_FINANCIAL_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: object, label: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise DiscoveryPersistenceError(f"{label} is required")
    return text


def _canonical_json(value: Mapping[str, Any] | Sequence[Any], label: str) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise DiscoveryPersistenceError(f"{label} is not canonical JSON") from exc


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_hex(value: object, label: str) -> str:
    text = _required(value, label).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise DiscoveryPersistenceError(f"{label} must be a 64-char lowercase hex digest")
    return text


def _assert_no_forbidden_fields(payload: Mapping[str, Any], label: str) -> None:
    for key in payload:
        if str(key) in FORBIDDEN_FACTUAL_FIELDS:
            raise DiscoveryPersistenceError(
                f"{label} must not store non-authoritative field: {key}"
            )


def candidate_identity_key(
    *,
    mint_identity: str,
    market_identity: str | None = None,
    lifecycle_identity: str | None = None,
) -> str:
    mint = _required(mint_identity, "mint_identity")
    market = (market_identity or "").strip()
    lifecycle = (lifecycle_identity or "").strip()
    return f"solana-mainnet:{mint}|{market}|{lifecycle}"


def discovery_batch_canonical_payload(
    *,
    discovery_batch_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    cycle_cutoff: str,
    policy_version: str,
    provider_contract_versions: Mapping[str, Any],
    git_provenance_identity: str,
    campaign_selection_seed_identity: str,
    cycle_seed_hash: str,
    pump_cursor_slot: int | None,
    pump_cursor_signature: str | None,
    pump_continuity_state: str,
) -> tuple[str, str]:
    payload = {
        "discovery_batch_id": discovery_batch_id,
        "campaign_id": campaign_id,
        "configuration_id": configuration_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "cycle_cutoff": cycle_cutoff,
        "policy_version": policy_version,
        "provider_contract_versions": dict(provider_contract_versions),
        "git_provenance_identity": git_provenance_identity,
        "campaign_selection_seed_identity": campaign_selection_seed_identity,
        "cycle_seed_hash": cycle_seed_hash,
        "pump_cursor_slot": pump_cursor_slot,
        "pump_cursor_signature": pump_cursor_signature,
        "pump_continuity_state": pump_continuity_state,
    }
    encoded = _canonical_json(payload, "discovery batch")
    return encoded, _sha256_text(encoded)


def observation_canonical_payload(
    *,
    discovery_batch_id: str,
    discovery_work_id: str,
    source_name: str,
    request_kind: str,
    channel: str,
    mint_identity: str,
    market_identity: str | None,
    lifecycle_identity: str | None,
    observed_at: str,
    captured_at: str,
    raw_payload_hash: str,
    factual_payload: Mapping[str, Any],
    source_request_id: int | None,
    source_response_id: int | None,
    source_failure_id: int | None,
) -> tuple[str, str]:
    _assert_no_forbidden_fields(factual_payload, "observation factual payload")
    payload = {
        "discovery_batch_id": discovery_batch_id,
        "discovery_work_id": discovery_work_id,
        "source_name": source_name,
        "request_kind": request_kind,
        "channel": channel,
        "mint_identity": mint_identity,
        "market_identity": market_identity,
        "lifecycle_identity": lifecycle_identity,
        "observed_at": observed_at,
        "captured_at": captured_at,
        "raw_payload_hash": raw_payload_hash,
        "factual_payload": dict(factual_payload),
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "source_failure_id": source_failure_id,
    }
    encoded = _canonical_json(payload, "provider observation")
    return encoded, _sha256_text(encoded)


def merged_candidate_canonical_payload(
    *,
    discovery_batch_id: str,
    candidate_identity_key: str,
    mint_identity: str,
    market_identity: str | None,
    lifecycle_identity: str | None,
    channel_labels: Sequence[str],
    identity_conflicts: Sequence[Any],
    evidence_gaps: Sequence[Any],
    origin_verification_state: str,
    pumpswap_confirmation_state: str,
    first_failed_eligibility_gate: str | None,
) -> tuple[str, str]:
    labels = sorted({_required(label, "channel label") for label in channel_labels})
    for label in labels:
        if label not in CHANNELS:
            raise DiscoveryPersistenceError(f"unsupported channel label: {label}")
    payload = {
        "discovery_batch_id": discovery_batch_id,
        "candidate_identity_key": candidate_identity_key,
        "mint_identity": mint_identity,
        "market_identity": market_identity,
        "lifecycle_identity": lifecycle_identity,
        "channel_labels": labels,
        "identity_conflicts": list(identity_conflicts),
        "evidence_gaps": list(evidence_gaps),
        "origin_verification_state": origin_verification_state,
        "pumpswap_confirmation_state": pumpswap_confirmation_state,
        "first_failed_eligibility_gate": first_failed_eligibility_gate,
    }
    encoded = _canonical_json(payload, "merged candidate")
    return encoded, _sha256_text(encoded)


def _owner_row(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM printer_memory_factory_campaign_cycles AS c
        JOIN printer_memory_factory_campaign_configurations AS cfg
          ON cfg.campaign_id = c.campaign_id
        WHERE c.cycle_id = ?
          AND c.run_id = ?
          AND c.campaign_id = ?
          AND cfg.configuration_id = ?
        """,
        (cycle_id, run_id, campaign_id, configuration_id),
    ).fetchone()
    if row is None:
        raise DiscoveryPersistenceError(
            "campaign/configuration/run/cycle ownership mismatch"
        )


def _existing_batch(
    connection: sqlite3.Connection, discovery_batch_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM printer_discovery_batches
        WHERE discovery_batch_id = ?
        """,
        (discovery_batch_id,),
    ).fetchone()


def insert_discovery_batch(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    cycle_cutoff: str,
    policy_version: str,
    provider_contract_versions: Mapping[str, Any],
    git_provenance_identity: str,
    campaign_selection_seed_identity: str,
    cycle_seed_hash: str,
    pump_continuity_state: str = "NONE",
    pump_cursor_slot: int | None = None,
    pump_cursor_signature: str | None = None,
    batch_state: str = "PLANNED",
    now: str | None = None,
) -> str:
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    campaign = _required(campaign_id, "campaign_id")
    configuration = _required(configuration_id, "configuration_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    cutoff = _required(cycle_cutoff, "cycle_cutoff")
    policy = _required(policy_version, "policy_version")
    git_id = _required(git_provenance_identity, "git_provenance_identity")
    seed_id = _required(
        campaign_selection_seed_identity, "campaign_selection_seed_identity"
    )
    seed_hash = _sha256_hex(cycle_seed_hash, "cycle_seed_hash")
    continuity = _required(pump_continuity_state, "pump_continuity_state")
    if continuity not in CONTINUITY_STATES:
        raise DiscoveryPersistenceError("invalid pump_continuity_state")
    versions_json = _canonical_json(
        dict(provider_contract_versions), "provider_contract_versions"
    )
    _, canonical_hash = discovery_batch_canonical_payload(
        discovery_batch_id=batch_id,
        campaign_id=campaign,
        configuration_id=configuration,
        run_id=run,
        cycle_id=cycle,
        cycle_cutoff=cutoff,
        policy_version=policy,
        provider_contract_versions=json.loads(versions_json),
        git_provenance_identity=git_id,
        campaign_selection_seed_identity=seed_id,
        cycle_seed_hash=seed_hash,
        pump_cursor_slot=pump_cursor_slot,
        pump_cursor_signature=pump_cursor_signature,
        pump_continuity_state=continuity,
    )
    timestamp = now or _utc_now()
    try:
        _owner_row(
            connection,
            campaign_id=campaign,
            configuration_id=configuration,
            run_id=run,
            cycle_id=cycle,
        )
        existing = _existing_batch(connection, batch_id)
        if existing is not None:
            if existing["canonical_hash"] == canonical_hash:
                return canonical_hash
            raise DiscoveryPersistenceError(
                "conflicting discovery batch repeat rejected"
            )
        connection.execute(
            """
            INSERT INTO printer_discovery_batches(
                discovery_batch_id, campaign_id, configuration_id, run_id, cycle_id,
                cycle_cutoff, policy_version, provider_contract_versions_json,
                git_provenance_identity, campaign_selection_seed_identity,
                cycle_seed_hash, pump_cursor_slot, pump_cursor_signature,
                pump_continuity_state, batch_state, canonical_hash, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                batch_id,
                campaign,
                configuration,
                run,
                cycle,
                cutoff,
                policy,
                versions_json,
                git_id,
                seed_id,
                seed_hash,
                pump_cursor_slot,
                pump_cursor_signature,
                continuity,
                batch_state,
                canonical_hash,
                timestamp,
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc
    return canonical_hash


def insert_discovery_work(
    connection: sqlite3.Connection,
    *,
    discovery_work_id: str,
    discovery_batch_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    scheduler_job_id: int,
    work_type: str,
    deadline_at: str,
    work_state: str = "PENDING",
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    now: str | None = None,
) -> None:
    work_id = _required(discovery_work_id, "discovery_work_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    kind = _required(work_type, "work_type")
    if kind not in WORK_TYPES:
        raise DiscoveryPersistenceError(f"unsupported discovery work_type: {kind}")
    deadline = _required(deadline_at, "deadline_at")
    state = _required(work_state, "work_state")
    timestamp = now or _utc_now()
    existing = connection.execute(
        """
        SELECT discovery_batch_id, campaign_id, run_id, cycle_id, scheduler_job_id,
               work_type, work_state, deadline_at, first_terminal_cause, terminal_at
        FROM printer_discovery_work
        WHERE discovery_work_id = ?
        """,
        (work_id,),
    ).fetchone()
    values = (
        batch_id,
        campaign,
        run,
        cycle,
        int(scheduler_job_id),
        kind,
        state,
        deadline,
        first_terminal_cause,
        terminal_at,
    )
    if existing is not None:
        current = (
            existing["discovery_batch_id"],
            existing["campaign_id"],
            existing["run_id"],
            existing["cycle_id"],
            int(existing["scheduler_job_id"]),
            existing["work_type"],
            existing["work_state"],
            existing["deadline_at"],
            existing["first_terminal_cause"],
            existing["terminal_at"],
        )
        if current == values:
            return
        raise DiscoveryPersistenceError("conflicting discovery work repeat rejected")
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_work(
                discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id,
                scheduler_job_id, work_type, work_state, deadline_at,
                first_terminal_cause, terminal_at, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (work_id, *values, timestamp, timestamp),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def link_discovery_work_source(
    connection: sqlite3.Connection,
    *,
    discovery_work_id: str,
    link_ordinal: int,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: str | None = None,
) -> None:
    work_id = _required(discovery_work_id, "discovery_work_id")
    if link_ordinal <= 0:
        raise DiscoveryPersistenceError("link_ordinal must be positive")
    if (
        source_request_id is None
        and source_response_id is None
        and source_failure_id is None
    ):
        raise DiscoveryPersistenceError("source link requires at least one source row")
    existing = connection.execute(
        """
        SELECT source_request_id, source_response_id, source_failure_id
        FROM printer_discovery_work_source_links
        WHERE discovery_work_id = ? AND link_ordinal = ?
        """,
        (work_id, link_ordinal),
    ).fetchone()
    values = (source_request_id, source_response_id, source_failure_id)
    if existing is not None:
        current = (
            existing["source_request_id"],
            existing["source_response_id"],
            existing["source_failure_id"],
        )
        if current == values:
            return
        raise DiscoveryPersistenceError(
            "conflicting discovery work source link rejected"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_work_source_links(
                discovery_work_id, link_ordinal, source_request_id,
                source_response_id, source_failure_id, created_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (work_id, link_ordinal, *values, now or _utc_now()),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def insert_provider_observation(
    connection: sqlite3.Connection,
    *,
    observation_id: str,
    discovery_batch_id: str,
    discovery_work_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    source_name: str,
    request_kind: str,
    channel: str,
    mint_identity: str,
    observed_at: str,
    captured_at: str,
    raw_payload_hash: str,
    factual_payload: Mapping[str, Any],
    market_identity: str | None = None,
    lifecycle_identity: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    now: str | None = None,
) -> str:
    obs_id = _required(observation_id, "observation_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    work_id = _required(discovery_work_id, "discovery_work_id")
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    source = _required(source_name, "source_name")
    kind = _required(request_kind, "request_kind")
    channel_value = _required(channel, "channel")
    if channel_value not in CHANNELS:
        raise DiscoveryPersistenceError(f"unsupported channel: {channel_value}")
    mint = _required(mint_identity, "mint_identity")
    observed = _required(observed_at, "observed_at")
    captured = _required(captured_at, "captured_at")
    raw_hash = _sha256_hex(raw_payload_hash, "raw_payload_hash")
    factual_json, observation_hash = observation_canonical_payload(
        discovery_batch_id=batch_id,
        discovery_work_id=work_id,
        source_name=source,
        request_kind=kind,
        channel=channel_value,
        mint_identity=mint,
        market_identity=market_identity,
        lifecycle_identity=lifecycle_identity,
        observed_at=observed,
        captured_at=captured,
        raw_payload_hash=raw_hash,
        factual_payload=factual_payload,
        source_request_id=source_request_id,
        source_response_id=source_response_id,
        source_failure_id=source_failure_id,
    )
    # Store only the factual payload object, not the full envelope.
    factual_only = _canonical_json(dict(factual_payload), "factual_payload")
    existing = connection.execute(
        """
        SELECT observation_hash, discovery_batch_id, mint_identity, channel
        FROM printer_discovery_provider_observations
        WHERE observation_id = ?
        """,
        (obs_id,),
    ).fetchone()
    if existing is not None:
        if existing["observation_hash"] == observation_hash:
            return observation_hash
        raise DiscoveryPersistenceError(
            "conflicting provider observation repeat rejected"
        )
    by_hash = connection.execute(
        """
        SELECT observation_id
        FROM printer_discovery_provider_observations
        WHERE discovery_batch_id = ? AND observation_hash = ?
        """,
        (batch_id, observation_hash),
    ).fetchone()
    if by_hash is not None:
        if by_hash["observation_id"] == obs_id:
            return observation_hash
        # Identical content under another id is treated as idempotent content
        # ownership: reject identity fork.
        raise DiscoveryPersistenceError(
            "identical observation content already owned by another id"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_provider_observations(
                observation_id, discovery_batch_id, discovery_work_id, campaign_id,
                run_id, cycle_id, source_name, request_kind, channel, mint_identity,
                market_identity, lifecycle_identity, observed_at, captured_at,
                raw_payload_hash, source_request_id, source_response_id,
                source_failure_id, factual_payload_json, observation_hash, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                obs_id,
                batch_id,
                work_id,
                campaign,
                run,
                cycle,
                source,
                kind,
                channel_value,
                mint,
                market_identity,
                lifecycle_identity,
                observed,
                captured,
                raw_hash,
                source_request_id,
                source_response_id,
                source_failure_id,
                factual_only,
                observation_hash,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc
    return observation_hash


def list_provider_observations(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
) -> list[dict[str, Any]]:
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    rows = connection.execute(
        """
        SELECT *
        FROM printer_discovery_provider_observations
        WHERE discovery_batch_id = ?
        ORDER BY source_name ASC, request_kind ASC, observed_at ASC,
                 observation_id ASC
        """,
        (batch_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def insert_merged_candidate(
    connection: sqlite3.Connection,
    *,
    merged_candidate_id: str,
    discovery_batch_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    mint_identity: str,
    channel_labels: Sequence[str],
    identity_conflicts: Sequence[Any] | None = None,
    evidence_gaps: Sequence[Any] | None = None,
    origin_verification_state: str = "PENDING",
    pumpswap_confirmation_state: str = "NOT_REQUIRED",
    market_identity: str | None = None,
    lifecycle_identity: str | None = None,
    first_failed_eligibility_gate: str | None = None,
    now: str | None = None,
) -> str:
    candidate_id = _required(merged_candidate_id, "merged_candidate_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    mint = _required(mint_identity, "mint_identity")
    identity_key = candidate_identity_key(
        mint_identity=mint,
        market_identity=market_identity,
        lifecycle_identity=lifecycle_identity,
    )
    conflicts = list(identity_conflicts or ())
    gaps = list(evidence_gaps or ())
    _, merged_hash = merged_candidate_canonical_payload(
        discovery_batch_id=batch_id,
        candidate_identity_key=identity_key,
        mint_identity=mint,
        market_identity=market_identity,
        lifecycle_identity=lifecycle_identity,
        channel_labels=channel_labels,
        identity_conflicts=conflicts,
        evidence_gaps=gaps,
        origin_verification_state=origin_verification_state,
        pumpswap_confirmation_state=pumpswap_confirmation_state,
        first_failed_eligibility_gate=first_failed_eligibility_gate,
    )
    labels_json = _canonical_json(
        sorted({_required(label, "channel label") for label in channel_labels}),
        "channel_labels",
    )
    conflicts_json = _canonical_json(conflicts, "identity_conflicts")
    gaps_json = _canonical_json(gaps, "evidence_gaps")
    existing = connection.execute(
        """
        SELECT merged_candidate_hash, candidate_identity_key
        FROM printer_discovery_merged_candidates
        WHERE merged_candidate_id = ?
        """,
        (candidate_id,),
    ).fetchone()
    if existing is not None:
        if existing["merged_candidate_hash"] == merged_hash:
            return merged_hash
        raise DiscoveryPersistenceError(
            "conflicting merged candidate repeat rejected"
        )
    by_key = connection.execute(
        """
        SELECT merged_candidate_id, merged_candidate_hash
        FROM printer_discovery_merged_candidates
        WHERE discovery_batch_id = ? AND candidate_identity_key = ?
        """,
        (batch_id, identity_key),
    ).fetchone()
    if by_key is not None:
        if (
            by_key["merged_candidate_id"] == candidate_id
            and by_key["merged_candidate_hash"] == merged_hash
        ):
            return merged_hash
        if by_key["merged_candidate_hash"] == merged_hash:
            return merged_hash
        raise DiscoveryPersistenceError(
            "duplicate candidate authority rejected for batch identity"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_merged_candidates(
                merged_candidate_id, discovery_batch_id, campaign_id, run_id, cycle_id,
                candidate_identity_key, mint_identity, market_identity,
                lifecycle_identity, channel_labels_json, identity_conflicts_json,
                evidence_gaps_json, origin_verification_state,
                pumpswap_confirmation_state, first_failed_eligibility_gate,
                merged_candidate_hash, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                candidate_id,
                batch_id,
                campaign,
                run,
                cycle,
                identity_key,
                mint,
                market_identity,
                lifecycle_identity,
                labels_json,
                conflicts_json,
                gaps_json,
                origin_verification_state,
                pumpswap_confirmation_state,
                first_failed_eligibility_gate,
                merged_hash,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc
    return merged_hash


def link_candidate_contribution(
    connection: sqlite3.Connection,
    *,
    merged_candidate_id: str,
    observation_id: str,
    contribution_ordinal: int,
    now: str | None = None,
) -> None:
    candidate_id = _required(merged_candidate_id, "merged_candidate_id")
    obs_id = _required(observation_id, "observation_id")
    if contribution_ordinal <= 0:
        raise DiscoveryPersistenceError("contribution_ordinal must be positive")
    existing = connection.execute(
        """
        SELECT contribution_ordinal
        FROM printer_discovery_candidate_contributions
        WHERE merged_candidate_id = ? AND observation_id = ?
        """,
        (candidate_id, obs_id),
    ).fetchone()
    if existing is not None:
        if int(existing["contribution_ordinal"]) == contribution_ordinal:
            return
        raise DiscoveryPersistenceError(
            "conflicting candidate contribution repeat rejected"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_candidate_contributions(
                merged_candidate_id, observation_id, contribution_ordinal, created_at
            ) VALUES (?,?,?,?)
            """,
            (candidate_id, obs_id, contribution_ordinal, now or _utc_now()),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def insert_origin_verification(
    connection: sqlite3.Connection,
    *,
    origin_verification_id: str,
    discovery_batch_id: str,
    merged_candidate_id: str,
    mint_identity: str,
    admission_state: str,
    verification_state: str,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    transaction_signature: str | None = None,
    program_id: str | None = None,
    slot: int | None = None,
    evidence_detail: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> None:
    row_id = _required(origin_verification_id, "origin_verification_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    candidate_id = _required(merged_candidate_id, "merged_candidate_id")
    mint = _required(mint_identity, "mint_identity")
    detail_json = _canonical_json(dict(evidence_detail or {}), "evidence_detail")
    existing = connection.execute(
        """
        SELECT admission_state, verification_state, transaction_signature,
               program_id, slot, evidence_detail_json
        FROM printer_discovery_origin_verifications
        WHERE origin_verification_id = ?
        """,
        (row_id,),
    ).fetchone()
    values = (
        admission_state,
        verification_state,
        transaction_signature,
        program_id,
        slot,
        detail_json,
    )
    if existing is not None:
        current = (
            existing["admission_state"],
            existing["verification_state"],
            existing["transaction_signature"],
            existing["program_id"],
            existing["slot"],
            existing["evidence_detail_json"],
        )
        if current == values:
            return
        raise DiscoveryPersistenceError(
            "conflicting origin verification repeat rejected"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_origin_verifications(
                origin_verification_id, discovery_batch_id, merged_candidate_id,
                mint_identity, admission_state, verification_state,
                source_request_id, source_response_id, source_failure_id,
                transaction_signature, program_id, slot, evidence_detail_json,
                created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row_id,
                batch_id,
                candidate_id,
                mint,
                admission_state,
                verification_state,
                source_request_id,
                source_response_id,
                source_failure_id,
                transaction_signature,
                program_id,
                slot,
                detail_json,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def insert_pumpswap_confirmation(
    connection: sqlite3.Connection,
    *,
    pumpswap_confirmation_id: str,
    discovery_batch_id: str,
    merged_candidate_id: str,
    mint_identity: str,
    admission_state: str,
    confirmation_state: str,
    market_identity: str | None = None,
    source_request_id: int | None = None,
    source_response_id: int | None = None,
    source_failure_id: int | None = None,
    pool_address: str | None = None,
    program_id: str | None = None,
    evidence_detail: Mapping[str, Any] | None = None,
    now: str | None = None,
) -> None:
    row_id = _required(pumpswap_confirmation_id, "pumpswap_confirmation_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    candidate_id = _required(merged_candidate_id, "merged_candidate_id")
    mint = _required(mint_identity, "mint_identity")
    detail_json = _canonical_json(dict(evidence_detail or {}), "evidence_detail")
    existing = connection.execute(
        """
        SELECT admission_state, confirmation_state, market_identity,
               pool_address, program_id, evidence_detail_json
        FROM printer_discovery_pumpswap_confirmations
        WHERE pumpswap_confirmation_id = ?
        """,
        (row_id,),
    ).fetchone()
    values = (
        admission_state,
        confirmation_state,
        market_identity,
        pool_address,
        program_id,
        detail_json,
    )
    if existing is not None:
        current = (
            existing["admission_state"],
            existing["confirmation_state"],
            existing["market_identity"],
            existing["pool_address"],
            existing["program_id"],
            existing["evidence_detail_json"],
        )
        if current == values:
            return
        raise DiscoveryPersistenceError(
            "conflicting pumpswap confirmation repeat rejected"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_pumpswap_confirmations(
                pumpswap_confirmation_id, discovery_batch_id, merged_candidate_id,
                mint_identity, market_identity, admission_state, confirmation_state,
                source_request_id, source_response_id, source_failure_id,
                pool_address, program_id, evidence_detail_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row_id,
                batch_id,
                candidate_id,
                mint,
                market_identity,
                admission_state,
                confirmation_state,
                source_request_id,
                source_response_id,
                source_failure_id,
                pool_address,
                program_id,
                detail_json,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def link_selection_batch(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
    selection_batch_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    now: str | None = None,
) -> None:
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    selection_id = _required(selection_batch_id, "selection_batch_id")
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    existing = connection.execute(
        """
        SELECT campaign_id, run_id, cycle_id
        FROM printer_discovery_selection_links
        WHERE discovery_batch_id = ? AND selection_batch_id = ?
        """,
        (batch_id, selection_id),
    ).fetchone()
    if existing is not None:
        if (
            existing["campaign_id"] == campaign
            and existing["run_id"] == run
            and existing["cycle_id"] == cycle
        ):
            return
        raise DiscoveryPersistenceError("conflicting selection batch link rejected")
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_selection_links(
                discovery_batch_id, selection_batch_id, campaign_id, run_id,
                cycle_id, created_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (batch_id, selection_id, campaign, run, cycle, now or _utc_now()),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def link_selected_item(
    connection: sqlite3.Connection,
    *,
    discovery_batch_id: str,
    selection_batch_id: str,
    selection_item_id: int,
    merged_candidate_id: str,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str | None = None,
    tracking_handoff_state: str = "NOT_ACTIVATED",
    first_window_15m_scheduler_job_id: int | None = None,
    now: str | None = None,
) -> None:
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    selection_id = _required(selection_batch_id, "selection_batch_id")
    candidate_id = _required(merged_candidate_id, "merged_candidate_id")
    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    existing = connection.execute(
        """
        SELECT selection_batch_id, merged_candidate_id, campaign_id, run_id,
               cycle_id, token_slot_id, tracking_handoff_state,
               first_window_15m_scheduler_job_id
        FROM printer_discovery_selected_item_links
        WHERE discovery_batch_id = ? AND selection_item_id = ?
        """,
        (batch_id, int(selection_item_id)),
    ).fetchone()
    values = (
        selection_id,
        candidate_id,
        campaign,
        run,
        cycle,
        token_slot_id,
        tracking_handoff_state,
        first_window_15m_scheduler_job_id,
    )
    if existing is not None:
        current = (
            existing["selection_batch_id"],
            existing["merged_candidate_id"],
            existing["campaign_id"],
            existing["run_id"],
            existing["cycle_id"],
            existing["token_slot_id"],
            existing["tracking_handoff_state"],
            existing["first_window_15m_scheduler_job_id"],
        )
        if current == values:
            return
        raise DiscoveryPersistenceError("conflicting selected item link rejected")
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_selected_item_links(
                discovery_batch_id, selection_batch_id, selection_item_id,
                merged_candidate_id, campaign_id, run_id, cycle_id, token_slot_id,
                tracking_handoff_state, first_window_15m_scheduler_job_id, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                batch_id,
                selection_id,
                int(selection_item_id),
                candidate_id,
                campaign,
                run,
                cycle,
                token_slot_id,
                tracking_handoff_state,
                first_window_15m_scheduler_job_id,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc


def insert_provider_report_link(
    connection: sqlite3.Connection,
    *,
    report_link_id: str,
    discovery_batch_id: str,
    campaign_id: str,
    configuration_id: str,
    report_payload: Mapping[str, Any],
    report_id: str | None = None,
    discovery_work_id: str | None = None,
    now: str | None = None,
) -> str:
    link_id = _required(report_link_id, "report_link_id")
    batch_id = _required(discovery_batch_id, "discovery_batch_id")
    campaign = _required(campaign_id, "campaign_id")
    configuration = _required(configuration_id, "configuration_id")
    payload = dict(report_payload)
    # Diagnostics only — never store ranking or scoring.
    for banned in ("provider_rank", "provider_score", "yield_rank", "quality_rank"):
        if banned in payload:
            raise DiscoveryPersistenceError(
                f"provider report must not store {banned}"
            )
    payload_json = _canonical_json(payload, "provider report payload")
    report_hash = _sha256_text(payload_json)
    existing = connection.execute(
        """
        SELECT report_hash
        FROM printer_discovery_provider_report_links
        WHERE report_link_id = ?
        """,
        (link_id,),
    ).fetchone()
    if existing is not None:
        if existing["report_hash"] == report_hash:
            return report_hash
        raise DiscoveryPersistenceError(
            "conflicting provider report link repeat rejected"
        )
    try:
        connection.execute(
            """
            INSERT INTO printer_discovery_provider_report_links(
                report_link_id, discovery_batch_id, campaign_id, configuration_id,
                report_id, discovery_work_id, report_payload_json, report_hash,
                created_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                link_id,
                batch_id,
                campaign,
                configuration,
                report_id,
                discovery_work_id,
                payload_json,
                report_hash,
                now or _utc_now(),
            ),
        )
    except sqlite3.Error as exc:
        raise DiscoveryPersistenceError(str(exc)) from exc
    return report_hash


def count_locked_financial_rows(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in LOCKED_FINANCIAL_TABLES:
        counts[table] = int(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        )
    return counts


@dataclass(frozen=True)
class DiscoveryBatchRecord:
    discovery_batch_id: str
    campaign_id: str
    run_id: str
    cycle_id: str
    canonical_hash: str
    batch_state: str
    pump_continuity_state: str


def get_discovery_batch(
    connection: sqlite3.Connection,
    discovery_batch_id: str,
) -> DiscoveryBatchRecord:
    row = _existing_batch(connection, _required(discovery_batch_id, "discovery_batch_id"))
    if row is None:
        raise DiscoveryPersistenceError("discovery batch not found")
    return DiscoveryBatchRecord(
        discovery_batch_id=row["discovery_batch_id"],
        campaign_id=row["campaign_id"],
        run_id=row["run_id"],
        cycle_id=row["cycle_id"],
        canonical_hash=row["canonical_hash"],
        batch_state=row["batch_state"],
        pump_continuity_state=row["pump_continuity_state"],
    )
