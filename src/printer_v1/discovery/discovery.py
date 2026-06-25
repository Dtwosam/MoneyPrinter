"""DB-backed Discovery Engine routing for local payloads only."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.discovery.classifier import (
    DiscoveryClassification,
    build_priority_reason,
    choose_initial_lifecycle_state,
    choose_tracking_lane,
    classify_discovery_candidate,
)
from printer_v1.discovery.contracts import DiscoveryOutputAction
from printer_v1.discovery.parser import normalize_candidates, validate_discovery_payload
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState
from printer_v1.lifecycle.tracking_queue import (
    enqueue_tracking_item,
    record_lifecycle_event,
    sync_tracking_state_with_scheduler,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return
    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def process_discovery_payload(
    db_path_or_conn: str | Path | sqlite3.Connection,
    source_name: str,
    payload: Mapping[str, Any],
    now: datetime | None = None,
    source_channel: str | None = None,
    source_channel_reason: str | None = None,
) -> list[dict[str, Any]]:
    current_time = now or utc_now()
    validate_discovery_payload(source_name, payload, current_time)
    results = []
    for raw_candidate, candidate in zip(
        payload_candidates(source_name, payload),
        normalize_candidates(source_name, payload),
    ):
        candidate["source_channel"] = source_channel
        candidate["source_channel_reason"] = source_channel_reason
        classification = classify_discovery_candidate(candidate)
        token_id = None
        pair_id = None
        if (
            classification.discovery_action != DiscoveryOutputAction.IGNORE
            and candidate.get("token_mint")
            and candidate.get("chain") == "solana"
        ):
            token_id = upsert_discovered_token(db_path_or_conn, candidate, classification)
            if candidate.get("pair_address"):
                pair_id = upsert_discovered_pair(db_path_or_conn, token_id, candidate)
        lifecycle_state = choose_initial_lifecycle_state(candidate, classification)
        tracking_lane = choose_tracking_lane(candidate, classification)
        priority_reason = build_priority_reason(candidate, classification)
        record_id = record_discovery_candidate(
            db_path_or_conn,
            source_response_id=payload.get("source_response_id"),
            token_id=token_id,
            pair_id=pair_id,
            source_name=source_name,
            classification=classification,
            raw_candidate_payload=raw_candidate,
            normalized_candidate=candidate,
            lifecycle_state=lifecycle_state,
            tracking_lane=tracking_lane,
            priority_reason=priority_reason,
            source_channel=candidate.get("source_channel"),
            source_channel_reason=candidate.get("source_channel_reason"),
        )
        if token_id is not None:
            route_candidate_to_lifecycle(
                db_path_or_conn,
                token_id=token_id,
                pair_id=pair_id,
                lifecycle_state=lifecycle_state,
                classification=classification,
                priority_reason=priority_reason,
                candidate=candidate,
            )
        queue_id = None
        scheduler_job_id = None
        if token_id is not None and pair_id is not None and tracking_lane is not None:
            queue_id = route_candidate_to_tracking_queue(
                db_path_or_conn,
                token_id=token_id,
                pair_id=pair_id,
                tracking_lane=tracking_lane,
                classification=classification,
                priority_reason=priority_reason,
                current_time=current_time,
            )
            if queue_id is not None:
                scheduler_job_id = enqueue_discovery_followup_jobs(
                    db_path_or_conn,
                    queue_id=queue_id,
                    current_time=current_time,
                )
        results.append(
            {
                "discovery_candidate_id": record_id,
                "token_id": token_id,
                "pair_id": pair_id,
                "tracking_queue_id": queue_id,
                "scheduler_job_id": scheduler_job_id,
                "classification": classification,
                "lifecycle_state": lifecycle_state,
                "tracking_lane": tracking_lane,
            }
        )
    return results


def payload_candidates(source_name: str, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    from printer_v1.discovery.parser import extract_candidate_items

    return extract_candidate_items(source_name, payload)


def upsert_discovered_token(
    db_or_connection: str | Path | sqlite3.Connection,
    candidate: Mapping[str, Any],
    classification: DiscoveryClassification,
) -> int:
    lifecycle_state = choose_initial_lifecycle_state(candidate, classification)
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT id FROM printer_tokens WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        if row:
            connection.execute(
                """
                UPDATE printer_tokens
                SET last_seen_at = ?,
                    token_status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    candidate["captured_at"],
                    lifecycle_state.value,
                    to_timestamp(utc_now()),
                    row["id"],
                ),
            )
            return int(row["id"])
        cursor = connection.execute(
            """
            INSERT INTO printer_tokens (
                token_mint,
                chain,
                symbol,
                name,
                first_seen_at,
                last_seen_at,
                token_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate["token_mint"],
                candidate["chain"],
                candidate.get("symbol"),
                candidate.get("name"),
                candidate["captured_at"],
                candidate["captured_at"],
                lifecycle_state.value,
            ),
        )
        return int(cursor.lastrowid)


def upsert_discovered_pair(
    db_or_connection: str | Path | sqlite3.Connection,
    token_id: int,
    candidate: Mapping[str, Any],
) -> int:
    with connect(db_or_connection) as connection:
        row = connection.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ?",
            (candidate["pair_address"],),
        ).fetchone()
        if row:
            connection.execute(
                """
                UPDATE printer_pairs
                SET last_seen_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (candidate["captured_at"], to_timestamp(utc_now()), row["id"]),
            )
            return int(row["id"])
        cursor = connection.execute(
            """
            INSERT INTO printer_pairs (
                token_id,
                pair_address,
                dex,
                pool_source,
                base_token_mint,
                quote_token_mint,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                candidate["pair_address"],
                candidate.get("dex"),
                candidate.get("pool_source"),
                candidate.get("base_token_mint"),
                candidate.get("quote_token_mint"),
                candidate["captured_at"],
                candidate["captured_at"],
            ),
        )
        return int(cursor.lastrowid)


def record_discovery_candidate(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    source_response_id: int | None,
    token_id: int | None,
    pair_id: int | None,
    source_name: str,
    classification: DiscoveryClassification,
    raw_candidate_payload: Mapping[str, Any],
    normalized_candidate: Mapping[str, Any],
    lifecycle_state: TokenLifecycleState,
    tracking_lane: TokenLifecycleState | None,
    priority_reason: str,
    source_channel: str | None = None,
    source_channel_reason: str | None = None,
) -> int:
    with connect(db_or_connection) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_discovery_candidates (
                source_response_id,
                token_id,
                pair_id,
                source_name,
                discovery_label,
                discovery_action,
                source_status,
                data_quality_label,
                raw_candidate_payload_json,
                normalized_candidate_payload_json,
                lifecycle_state,
                tracking_lane,
                priority_reason,
                source_channel,
                source_channel_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_response_id,
                token_id,
                pair_id,
                source_name,
                classification.discovery_label.value,
                classification.discovery_action.value,
                SourceStatus.COMPLETE.value,
                DataQualityLabel.CLEAN_DATA.value,
                json.dumps(dict(raw_candidate_payload), sort_keys=True),
                json.dumps(dict(normalized_candidate), sort_keys=True),
                lifecycle_state.value,
                tracking_lane.value if tracking_lane else None,
                priority_reason,
                source_channel,
                source_channel_reason,
            ),
        )
        return int(cursor.lastrowid)


def route_candidate_to_lifecycle(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int | None,
    lifecycle_state: TokenLifecycleState,
    classification: DiscoveryClassification,
    priority_reason: str,
    candidate: Mapping[str, Any],
) -> int:
    event = {
        DiscoveryOutputAction.TRACK_FAST: LifecycleEvent.PROMOTE_TO_TRACK_FAST,
        DiscoveryOutputAction.TRACK_NORMAL: LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
        DiscoveryOutputAction.WATCH_ONLY: LifecycleEvent.WATCH_ONLY_REFRESH,
        DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY: LifecycleEvent.INSTANT_REJECT_BAD_DATA,
        DiscoveryOutputAction.IGNORE: LifecycleEvent.NEW_DISCOVERY,
    }[classification.discovery_action]
    return record_lifecycle_event(
        db_or_connection,
        token_id=token_id,
        pair_id=pair_id,
        previous_state=TokenLifecycleState.DISCOVERED,
        new_state=lifecycle_state,
        lifecycle_event=event,
        priority_reason=priority_reason,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        event_payload={"token_mint": candidate.get("token_mint")},
    )


def route_candidate_to_tracking_queue(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    tracking_lane: TokenLifecycleState,
    classification: DiscoveryClassification,
    priority_reason: str,
    current_time: datetime,
) -> int | None:
    if classification.discovery_action == DiscoveryOutputAction.INSTANT_REJECT_MEMORY_ONLY:
        return None
    created, queue_id = enqueue_tracking_item(
        db_or_connection,
        token_id=token_id,
        pair_id=pair_id,
        tracking_lane=tracking_lane,
        tracking_action=LifecycleEvent.NEW_DISCOVERY,
        priority_reason=priority_reason,
        next_check_at=current_time,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
    )
    return queue_id if created else None


def enqueue_discovery_followup_jobs(
    db_or_connection: str | Path | sqlite3.Connection,
    *,
    queue_id: int,
    current_time: datetime,
) -> int | None:
    result, job_id = sync_tracking_state_with_scheduler(
        db_or_connection,
        queue_id=queue_id,
        scheduled_for=current_time + timedelta(seconds=30),
    )
    return job_id if result.value == "ACQUIRED" else None
