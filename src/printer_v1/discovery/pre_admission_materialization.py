"""Source-free cycle-rooted materialization of one consumed frozen pair."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

from printer_v1.discovery.combined_executor import (
    persist_cycle_rooted_selected_item,
    persist_cycle_rooted_selection_batch,
)
from printer_v1.discovery.persistence import (
    DiscoveryPersistenceError,
    insert_discovery_batch,
    insert_discovery_work,
    insert_merged_candidate,
    link_discovery_work_source,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptState,
    load_pre_admission_attempt,
    load_pre_admission_pair,
)


class PreAdmissionMaterializationError(RuntimeError):
    """Fail-closed frozen-evidence materialization contract violation."""


@dataclass(frozen=True)
class PreAdmissionMaterializationResult:
    attempt_id: str
    discovery_batch_id: str
    selection_batch_id: str
    materialized_item_count: int


def _required(value: object, code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PreAdmissionMaterializationError(code)
    return value


def _utc_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PreAdmissionMaterializationError("NOW_MUST_BE_TIMEZONE_AWARE")
    return value.astimezone(timezone.utc).isoformat()


def _channel_labels(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PreAdmissionMaterializationError("FROZEN_CHANNEL_EVIDENCE_INVALID") from exc
    if (
        not isinstance(decoded, list)
        or not decoded
        or any(
            not isinstance(label, str) or not label or label != label.strip()
            for label in decoded
        )
    ):
        raise PreAdmissionMaterializationError("FROZEN_CHANNEL_EVIDENCE_INVALID")
    return tuple(sorted(set(decoded)))


def _validate_source_evidence(
    connection: sqlite3.Connection, *, attempt_id: str
) -> tuple[sqlite3.Row, ...]:
    rows = tuple(
        connection.execute(
            """SELECT l.link_ordinal,l.source_request_id,l.source_response_id,
                      l.source_failure_id,r.source_name AS request_source,
                      response.source_request_id AS response_request_id,
                      response.source_name AS response_source,
                      failure.source_request_id AS failure_request_id,
                      failure.source_name AS failure_source
               FROM printer_pre_admission_discovery_attempt_source_links AS l
               LEFT JOIN printer_source_requests AS r ON r.id=l.source_request_id
               LEFT JOIN printer_source_responses AS response
                 ON response.id=l.source_response_id
               LEFT JOIN printer_source_failures AS failure
                 ON failure.id=l.source_failure_id
               WHERE l.attempt_id=? ORDER BY l.link_ordinal""",
            (attempt_id,),
        ).fetchall()
    )
    if not rows:
        raise PreAdmissionMaterializationError("SOURCE_EVIDENCE_MISSING")
    if tuple(int(row["link_ordinal"]) for row in rows) != tuple(range(1, len(rows) + 1)):
        raise PreAdmissionMaterializationError("SOURCE_EVIDENCE_DRIFT")
    for row in rows:
        request_id = int(row["source_request_id"])
        request_source = row["request_source"]
        if request_source is None:
            raise PreAdmissionMaterializationError("SOURCE_EVIDENCE_DRIFT")
        if row["source_response_id"] is not None and (
            row["response_request_id"] is None
            or int(row["response_request_id"]) != request_id
            or row["response_source"] != request_source
        ):
            raise PreAdmissionMaterializationError("SOURCE_EVIDENCE_DRIFT")
        if row["source_failure_id"] is not None and (
            row["failure_request_id"] is None
            or int(row["failure_request_id"]) != request_id
            or row["failure_source"] != request_source
        ):
            raise PreAdmissionMaterializationError("SOURCE_EVIDENCE_DRIFT")
    return rows


def _existing_result(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    discovery_batch_id: str,
    selection_batch_id: str,
    cycle_id: str,
) -> PreAdmissionMaterializationResult | None:
    row = connection.execute(
        """SELECT batch_state FROM printer_discovery_batches
           WHERE discovery_batch_id=? AND cycle_id=?""",
        (discovery_batch_id, cycle_id),
    ).fetchone()
    if row is None:
        return None
    count = int(
        connection.execute(
            """SELECT COUNT(*) FROM printer_discovery_selected_item_links
               WHERE discovery_batch_id=? AND selection_batch_id=?
                 AND cycle_id=? AND tracking_handoff_state='LINKED_ONLY'
                 AND first_window_15m_scheduler_job_id IS NULL""",
            (discovery_batch_id, selection_batch_id, cycle_id),
        ).fetchone()[0]
    )
    if str(row["batch_state"]) != "TERMINAL_COMPLETED" or count != 2:
        raise PreAdmissionMaterializationError("EXISTING_MATERIALIZATION_DRIFT")
    return PreAdmissionMaterializationResult(
        attempt_id=attempt_id,
        discovery_batch_id=discovery_batch_id,
        selection_batch_id=selection_batch_id,
        materialized_item_count=2,
    )


def materialize_consumed_pre_admission_pair(
    connection: sqlite3.Connection,
    *,
    attempt_id: str,
    campaign_id: str,
    campaign_run_id: str,
    configuration_id: str,
    authoritative_factory_run_id: str,
    cycle_id: str,
    now: datetime,
) -> PreAdmissionMaterializationResult:
    """Materialize frozen selection facts without source work or reselection."""
    if connection.in_transaction:
        raise PreAdmissionMaterializationError("OPEN_TRANSACTION_FORBIDDEN")
    connection.row_factory = sqlite3.Row
    exact_attempt_id = _required(attempt_id, "ATTEMPT_ID_INVALID")
    exact_cycle_id = _required(cycle_id, "CYCLE_ID_INVALID")
    timestamp = _utc_timestamp(now)
    attempt = load_pre_admission_attempt(connection, attempt_id=exact_attempt_id)
    if (
        attempt.campaign_id != campaign_id
        or attempt.campaign_run_id != campaign_run_id
        or attempt.configuration_id != configuration_id
        or attempt.authoritative_factory_run_id != authoritative_factory_run_id
    ):
        raise PreAdmissionMaterializationError("ATTEMPT_OWNERSHIP_MISMATCH")
    if attempt.state is not PreAdmissionAttemptState.CONSUMED:
        raise PreAdmissionMaterializationError("ATTEMPT_NOT_CONSUMED")
    if attempt.consumed_cycle_id != exact_cycle_id:
        raise PreAdmissionMaterializationError("CONSUMED_CYCLE_MISMATCH")
    if attempt.proposed_cycle_ordinal != 2 or attempt.proposed_cycle_id != exact_cycle_id:
        raise PreAdmissionMaterializationError("PROPOSED_CYCLE_IDENTITY_MISMATCH")

    discovery_batch_id = f"pre-admission-materialized:{exact_attempt_id}"
    selection_batch_id = f"selection:{discovery_batch_id}"
    existing = _existing_result(
        connection,
        attempt_id=exact_attempt_id,
        discovery_batch_id=discovery_batch_id,
        selection_batch_id=selection_batch_id,
        cycle_id=exact_cycle_id,
    )
    if existing is not None:
        return existing

    items = load_pre_admission_pair(connection, attempt_id=exact_attempt_id)
    slots = tuple(
        connection.execute(
            """SELECT token_slot_id,slot_ordinal,token_identity,token_row_id,
                      mint_identity,pair_identity,pair_row_id,lifecycle_identity
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
               ORDER BY slot_ordinal""",
            (campaign_id, campaign_run_id, exact_cycle_id),
        ).fetchall()
    )
    if len(slots) != 2 or tuple(int(row["slot_ordinal"]) for row in slots) != (1, 2):
        raise PreAdmissionMaterializationError("FROZEN_PAIR_CYCLE_DRIFT")
    for item, slot in zip(items, slots, strict=True):
        expected = (
            item.slot_ordinal,
            item.token_identity,
            item.token_row_id,
            item.mint_identity,
            item.pair_identity,
            item.pair_row_id,
            item.lifecycle_identity,
        )
        actual = (
            int(slot["slot_ordinal"]),
            str(slot["token_identity"]),
            int(slot["token_row_id"]),
            str(slot["mint_identity"]),
            str(slot["pair_identity"]),
            int(slot["pair_row_id"]),
            str(slot["lifecycle_identity"]),
        )
        if actual != expected or item.canonical_pool_identity != item.pair_identity:
            raise PreAdmissionMaterializationError("FROZEN_PAIR_CYCLE_DRIFT")
        _channel_labels(json.dumps(item.channel_labels))
        try:
            json.loads(item.canonical_evidence_json)
        except json.JSONDecodeError as exc:
            raise PreAdmissionMaterializationError("FROZEN_ITEM_EVIDENCE_DRIFT") from exc

    scheduler = connection.execute(
        "SELECT job_kind,status FROM printer_scheduler_jobs WHERE id=?",
        (attempt.scheduler_job_id,),
    ).fetchone()
    if scheduler is None or tuple(scheduler) != (
        "PRE_ADMISSION_DISCOVERY_SELECTION",
        "SUCCEEDED",
    ):
        raise PreAdmissionMaterializationError("SCHEDULER_OWNERSHIP_NOT_TERMINAL")
    source_rows = _validate_source_evidence(connection, attempt_id=exact_attempt_id)
    policy_row = connection.execute(
        "SELECT policy_version FROM printer_memory_factory_campaigns WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()
    if policy_row is None:
        raise PreAdmissionMaterializationError("CAMPAIGN_POLICY_MISSING")

    # This committed owner supplies the same machine-readable contract versions
    # and operational implementation identity used by normal discovery batches.
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        operational_discovery_batch_identity_inputs,
    )

    provider_versions, git_identity = operational_discovery_batch_identity_inputs()
    cycle_seed_hash = hashlib.sha256(
        attempt.selection_seed_identity.encode("utf-8")
    ).hexdigest()
    work_id = f"{discovery_batch_id}:frozen-selection"
    connection.execute("BEGIN IMMEDIATE")
    try:
        insert_discovery_batch(
            connection,
            discovery_batch_id=discovery_batch_id,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            run_id=campaign_run_id,
            cycle_id=exact_cycle_id,
            cycle_cutoff=attempt.cycle_cutoff.isoformat(),
            policy_version=str(policy_row["policy_version"]),
            provider_contract_versions=provider_versions,
            git_provenance_identity=git_identity,
            campaign_selection_seed_identity=attempt.selection_seed_identity,
            cycle_seed_hash=cycle_seed_hash,
            batch_state="SELECTING",
            now=timestamp,
        )
        insert_discovery_work(
            connection,
            discovery_work_id=work_id,
            discovery_batch_id=discovery_batch_id,
            campaign_id=campaign_id,
            run_id=campaign_run_id,
            cycle_id=exact_cycle_id,
            scheduler_job_id=attempt.scheduler_job_id,
            work_type="DISCOVERY_UNIFORM_SELECTION",
            work_state="SUCCEEDED",
            deadline_at=attempt.cycle_cutoff.isoformat(),
            first_terminal_cause="FROZEN_PRE_ADMISSION_SELECTION",
            terminal_at=timestamp,
            now=timestamp,
        )
        for link_ordinal, row in enumerate(source_rows, start=1):
            link_discovery_work_source(
                connection,
                discovery_work_id=work_id,
                link_ordinal=link_ordinal,
                source_request_id=int(row["source_request_id"]),
                source_response_id=(
                    None if row["source_response_id"] is None else int(row["source_response_id"])
                ),
                source_failure_id=(
                    None if row["source_failure_id"] is None else int(row["source_failure_id"])
                ),
                now=timestamp,
            )
        merged_ids: list[str] = []
        for item in items:
            merged_id = f"{discovery_batch_id}:candidate:{item.slot_ordinal}"
            insert_merged_candidate(
                connection,
                merged_candidate_id=merged_id,
                discovery_batch_id=discovery_batch_id,
                campaign_id=campaign_id,
                run_id=campaign_run_id,
                cycle_id=exact_cycle_id,
                mint_identity=item.mint_identity,
                market_identity=item.canonical_market_identity,
                lifecycle_identity=item.lifecycle_identity,
                channel_labels=item.channel_labels,
                identity_conflicts=(),
                evidence_gaps=(),
                origin_verification_state="CONFIRMED",
                pumpswap_confirmation_state="CONFIRMED",
                now=timestamp,
            )
            merged_ids.append(merged_id)
        persist_cycle_rooted_selection_batch(
            connection,
            discovery_batch_id=discovery_batch_id,
            selection_batch_id=selection_batch_id,
            campaign_id=campaign_id,
            run_id=campaign_run_id,
            cycle_id=exact_cycle_id,
            selected_count=2,
            now=timestamp,
        )
        for item, slot, merged_id in zip(items, slots, merged_ids, strict=True):
            persist_cycle_rooted_selected_item(
                connection,
                discovery_batch_id=discovery_batch_id,
                selection_batch_id=selection_batch_id,
                merged_candidate_id=merged_id,
                campaign_id=campaign_id,
                run_id=campaign_run_id,
                cycle_id=exact_cycle_id,
                token_slot_id=str(slot["token_slot_id"]),
                token_id=item.token_row_id,
                pair_id=item.pair_row_id,
                token_mint=item.mint_identity,
                pair_address=item.pair_identity,
                selection_reason=f"uniform:{attempt.selection_seed_identity[:12]}",
                tracking_handoff_state="LINKED_ONLY",
                first_window_15m_scheduler_job_id=None,
                now=timestamp,
            )
        connection.execute(
            """UPDATE printer_discovery_batches
               SET batch_state='TERMINAL_COMPLETED',
                   first_terminal_cause='FROZEN_PAIR_MATERIALIZED',terminal_at=?
               WHERE discovery_batch_id=? AND batch_state='SELECTING'""",
            (timestamp, discovery_batch_id),
        )
        connection.commit()
    except (sqlite3.Error, DiscoveryPersistenceError, PreAdmissionMaterializationError) as exc:
        connection.rollback()
        if isinstance(exc, PreAdmissionMaterializationError):
            raise
        raise PreAdmissionMaterializationError("MATERIALIZATION_PERSISTENCE_FAILED") from exc
    return PreAdmissionMaterializationResult(
        attempt_id=exact_attempt_id,
        discovery_batch_id=discovery_batch_id,
        selection_batch_id=selection_batch_id,
        materialized_item_count=2,
    )


__all__ = [
    "PreAdmissionMaterializationError",
    "PreAdmissionMaterializationResult",
    "materialize_consumed_pre_admission_pair",
]
