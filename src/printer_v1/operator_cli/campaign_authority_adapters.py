"""Read-only B.1 promotion and B.2 safety adapters for campaign ownership."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping

from printer_v1.operator_cli.one_command_15m_factory import (
    ALREADY_EXISTS_IDEMPOTENT,
    CLEAN_PROMOTED,
    _authoritative_promotions_for_run,
    _per_token_outcomes,
)
from printer_v1.safety.composite import (
    MAX_AGE_SECONDS,
    SAFETY_CONTEXT_UNKNOWN,
    composite_row_is_acceptable,
    effective_safety_context_report,
)


MAIN_WINDOW_KINDS = frozenset({"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"})
_CLOSE_STEP_KINDS = {
    "WINDOW_15M": "WINDOW_CLOSE",
    "WINDOW_1H": "CONTINUATION_CLOSE",
    "WINDOW_4H": "LONG_CONTINUATION_CLOSE",
}
_PROMOTED = frozenset({CLEAN_PROMOTED, ALREADY_EXISTS_IDEMPOTENT})


class CampaignAuthorityAdapterError(ValueError):
    """Raised when campaign ownership or authoritative linkage fails closed."""


@contextmanager
def _read_only_database(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise CampaignAuthorityAdapterError(f"database missing: {path}")
    connection = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
        if connection.total_changes != 0:
            raise CampaignAuthorityAdapterError("read-only adapter created database writes")
    finally:
        connection.close()


def _graph_window(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT c.campaign_id, r.run_id, r.authoritative_run_id,
               y.cycle_id, s.token_slot_id, s.token_identity,
               s.mint_identity, s.pair_identity, s.lifecycle_identity,
               w.window_id, w.window_kind, w.window_state,
               w.token_row_id, w.pair_row_id, w.memory_window_row_id,
               w.checkpoint_cutoff, w.support_only
        FROM printer_memory_factory_campaigns AS c
        JOIN printer_memory_factory_campaign_runs AS r
          ON r.campaign_id = c.campaign_id
        JOIN printer_memory_factory_campaign_cycles AS y
          ON y.campaign_id = r.campaign_id AND y.run_id = r.run_id
        JOIN printer_memory_factory_campaign_token_slots AS s
          ON s.campaign_id = y.campaign_id AND s.run_id = y.run_id
         AND s.cycle_id = y.cycle_id
        JOIN printer_memory_factory_campaign_windows AS w
          ON w.campaign_id = s.campaign_id AND w.run_id = s.run_id
         AND w.cycle_id = s.cycle_id AND w.token_slot_id = s.token_slot_id
        WHERE c.campaign_id=? AND r.run_id=? AND y.cycle_id=?
          AND s.token_slot_id=? AND w.window_id=?
        """,
        (campaign_id, run_id, cycle_id, token_slot_id, window_id),
    ).fetchall()
    if len(rows) != 1:
        raise CampaignAuthorityAdapterError(
            "campaign/run/cycle/token-slot/window ownership mismatch"
        )
    graph = dict(rows[0])
    if graph["window_kind"] not in MAIN_WINDOW_KINDS or graph["support_only"] != 0:
        raise CampaignAuthorityAdapterError("adapter requires one authoritative main window")
    if graph["memory_window_row_id"] is None:
        raise CampaignAuthorityAdapterError("main window lacks an exact memory-window row")
    return graph


def load_authoritative_promotion_outcome(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
) -> dict[str, Any]:
    """Load one exact B.1 promotion outcome without inferring promotion."""
    with _read_only_database(db_path) as connection:
        graph = _graph_window(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            window_id=window_id,
        )
        authoritative_run_id = graph["authoritative_run_id"]
        if not authoritative_run_id:
            raise CampaignAuthorityAdapterError(
                "campaign run lacks B.1 authoritative run identity"
            )
        memory_window_id = int(graph["memory_window_row_id"])
        expected_step_kind = _CLOSE_STEP_KINDS[str(graph["window_kind"])]
        close_steps = connection.execute(
            """
            SELECT * FROM printer_memory_factory_run_steps
            WHERE run_id=? AND memory_window_id=? AND token_id=? AND pair_id=?
              AND step_kind=?
            ORDER BY id
            """,
            (
                authoritative_run_id,
                memory_window_id,
                graph["token_row_id"],
                graph["pair_row_id"],
                expected_step_kind,
            ),
        ).fetchall()
        if len(close_steps) != 1:
            raise CampaignAuthorityAdapterError(
                "exactly one authoritative close step is required"
            )
        close_step = dict(close_steps[0])
        window_row = connection.execute(
            "SELECT * FROM printer_memory_windows WHERE id=?",
            (memory_window_id,),
        ).fetchone()
        if window_row is None:
            raise CampaignAuthorityAdapterError("authoritative memory window is missing")
        window = dict(window_row)
        if (
            int(window["token_id"]) != int(graph["token_row_id"])
            or int(window["pair_id"]) != int(graph["pair_row_id"])
            or str(window["window_kind"]) != str(graph["window_kind"])
        ):
            raise CampaignAuthorityAdapterError(
                "authoritative memory window identity mismatch"
            )

        promotions = _authoritative_promotions_for_run(
            connection, str(authoritative_run_id)
        )
        outcomes = _per_token_outcomes(
            [close_step], {memory_window_id: window}, promotions
        )
        if len(outcomes) != 1:
            raise CampaignAuthorityAdapterError("B.1 returned an ambiguous outcome")
        outcome = outcomes[0]
        if (
            int(outcome["token_id"]) != int(graph["token_row_id"])
            or int(outcome["pair_id"]) != int(graph["pair_row_id"])
            or int(outcome["memory_window_id"]) != memory_window_id
        ):
            raise CampaignAuthorityAdapterError("B.1 outcome identity mismatch")

        return {
            "authority": "B.1_AUTHORITATIVE_PROMOTION",
            "campaign_id": campaign_id,
            "run_id": run_id,
            "authoritative_run_id": str(authoritative_run_id),
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "window_id": window_id,
            "window_kind": graph["window_kind"],
            "memory_window_row_id": memory_window_id,
            "close_step_id": int(close_step["id"]),
            "close_step_kind": close_step["step_kind"],
            "close_step_status": close_step["step_status"],
            "close_step_result_json": close_step["result_json"],
            "promotion_status": outcome["promotion_status"],
            "authoritative_episode_id": outcome["authoritative_episode_id"],
            "memory_quality_label": outcome["memory_quality_label"],
            "source_memory_window_status": outcome["source_memory_window_status"],
            "read_only": True,
        }


def _time(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unknown_safety(
    graph: Mapping[str, Any], *, checkpoint_object_id: str, reason: str,
) -> dict[str, Any]:
    effective = effective_safety_context_report(
        None, gate_accepted=None, window_kind=str(graph["window_kind"])
    )
    return {
        "authority": "B.2_EFFECTIVE_SAFETY",
        "campaign_id": graph["campaign_id"],
        "run_id": graph["run_id"],
        "cycle_id": graph["cycle_id"],
        "token_slot_id": graph["token_slot_id"],
        "window_id": graph["window_id"],
        "window_kind": graph["window_kind"],
        "checkpoint_object_id": checkpoint_object_id,
        "safety_composite_id": None,
        "gate_accepted": None,
        "effective_safety_context": effective,
        "raw_composite": None,
        "source_traces": [],
        "reasons": [reason],
        "read_only": True,
    }


def load_authoritative_checkpoint_safety(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    checkpoint_object_id: str,
) -> dict[str, Any]:
    """Load and validate the exact B.2 composite linked to one checkpoint."""
    with _read_only_database(db_path) as connection:
        graph = _graph_window(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            window_id=window_id,
        )
        object_row = connection.execute(
            """
            SELECT object_id, object_kind, safety_composite_id
            FROM printer_memory_factory_campaign_objects
            WHERE object_id=? AND object_kind='CHECKPOINT_5A'
              AND campaign_id=? AND run_id=? AND cycle_id=?
              AND token_slot_id=? AND window_id=?
            """,
            (
                checkpoint_object_id, campaign_id, run_id, cycle_id,
                token_slot_id, window_id,
            ),
        ).fetchone()
        if object_row is None or object_row["safety_composite_id"] is None:
            return _unknown_safety(
                graph,
                checkpoint_object_id=checkpoint_object_id,
                reason="checkpoint_safety_composite_missing_or_mismatched",
            )

        composite_id = int(object_row["safety_composite_id"])
        composite_row = connection.execute(
            "SELECT * FROM printer_safety_evidence_composites WHERE id=?",
            (composite_id,),
        ).fetchone()
        if composite_row is None:
            return _unknown_safety(
                graph,
                checkpoint_object_id=checkpoint_object_id,
                reason="persisted_safety_composite_missing",
            )
        composite = dict(composite_row)
        traces = [
            dict(row) for row in connection.execute(
                """
                SELECT contribution.*,
                       request.source_name AS request_source_name,
                       response.source_name AS response_source_name,
                       response.source_request_id AS response_request_id,
                       failure.source_name AS failure_source_name
                FROM printer_safety_evidence_contributions AS contribution
                LEFT JOIN printer_source_requests AS request
                  ON request.id=contribution.source_request_id
                LEFT JOIN printer_source_responses AS response
                  ON response.id=contribution.source_response_id
                LEFT JOIN printer_source_failures AS failure
                  ON failure.id=contribution.source_failure_id
                WHERE contribution.composite_id=?
                ORDER BY contribution.id
                """,
                (composite_id,),
            ).fetchall()
        ]

        reasons: list[str] = []
        if (
            int(composite["token_id"]) != int(graph["token_row_id"])
            or int(composite["pair_id"]) != int(graph["pair_row_id"])
            or str(composite["token_mint"]) != str(graph["mint_identity"])
            or str(composite["pair_address"]) != str(graph["pair_identity"])
            or composite["target_status"] != "TARGET_MATCH"
        ):
            reasons.append("safety_target_identity_mismatch")
        if (
            composite["memory_window_id"] is not None
            and int(composite["memory_window_id"])
            != int(graph["memory_window_row_id"])
        ):
            reasons.append("safety_memory_window_mismatch")

        cutoff = _time(graph["checkpoint_cutoff"])
        captured = _time(composite["evidence_captured_at"])
        age = (cutoff - captured).total_seconds() if cutoff and captured else None
        if age is None or age < 0 or age > MAX_AGE_SECONDS:
            reasons.append("safety_evidence_stale_or_post_cutoff")
        if composite["freshness_label"] not in {
            "SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"
        }:
            reasons.append("safety_freshness_label_not_acceptable")

        if not traces:
            reasons.append("safety_source_trace_missing")
        for trace in traces:
            trace_captured = _time(trace["captured_at"])
            trace_age = (
                (cutoff - trace_captured).total_seconds()
                if cutoff and trace_captured else None
            )
            trace_valid = (
                trace["request_source_name"] == trace["source_name"]
                and str(trace["token_mint"]) == str(graph["mint_identity"])
                and str(trace["pair_address"]) == str(graph["pair_identity"])
                and trace["target_status"] == "TARGET_MATCH"
                and trace["freshness_label"] in {
                    "SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"
                }
                and trace["source_status"] in {"COMPLETE", "PARTIAL"}
                and trace["data_quality_label"] in {
                    "CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"
                }
                and trace["rejection_reason"] is None
                and trace_age is not None
                and 0 <= trace_age <= MAX_AGE_SECONDS
                and (
                    trace["source_response_id"] is None
                    or (
                        trace["response_source_name"] == trace["source_name"]
                        and int(trace["response_request_id"])
                        == int(trace["source_request_id"])
                    )
                )
                and (
                    trace["source_failure_id"] is None
                    or trace["failure_source_name"] == trace["source_name"]
                )
            )
            if not trace_valid:
                reasons.append("safety_source_trace_mismatch")
                break

        try:
            gate_accepted = composite_row_is_acceptable(composite) and not reasons
        except (TypeError, ValueError, json.JSONDecodeError):
            gate_accepted = False
            reasons.append("safety_composite_payload_invalid")
        effective = effective_safety_context_report(
            composite,
            gate_accepted=gate_accepted,
            window_kind=str(graph["window_kind"]),
        )
        if not gate_accepted and not reasons:
            reasons.append("authoritative_safety_gate_blocked")
        return {
            "authority": "B.2_EFFECTIVE_SAFETY",
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "window_id": window_id,
            "window_kind": graph["window_kind"],
            "checkpoint_object_id": checkpoint_object_id,
            "safety_composite_id": composite_id,
            "gate_accepted": gate_accepted,
            "effective_safety_context": effective,
            "raw_composite": composite,
            "source_traces": traces,
            "reasons": list(dict.fromkeys(reasons)),
            "read_only": True,
        }


def load_authoritative_window_safety(
    db_path: str | Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    window_id: str,
    memory_window_close_cutoff: str | None = None,
) -> dict[str, Any]:
    """Load the exact safety composite retained by one memory-window context.

    The real producer is allowed to create the composite before the memory
    window exists, so ``memory_window_id`` on the composite may be null.  The
    immutable linkage is the exact composite id retained by the authoritative
    memory-window build context; no latest-evidence lookup is permitted here.
    """
    with _read_only_database(db_path) as connection:
        graph = _graph_window(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=token_slot_id,
            window_id=window_id,
        )
        memory_window = connection.execute(
            "SELECT * FROM printer_memory_windows WHERE id=?",
            (int(graph["memory_window_row_id"]),),
        ).fetchone()
        if memory_window is None:
            return _unknown_safety(
                graph,
                checkpoint_object_id="memory_window_context",
                reason="authoritative_memory_window_missing",
            )
        window = dict(memory_window)
        try:
            context = json.loads(str(window.get("supporting_context_json") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            context = {}
        overlays = (
            context.get("memory_build_evidence_overlays", {})
            if isinstance(context, dict)
            else {}
        )
        composite_id_raw = (
            overlays.get("safety_composite_id")
            if isinstance(overlays, dict)
            else None
        )
        try:
            composite_id = int(composite_id_raw)
        except (TypeError, ValueError):
            return _unknown_safety(
                graph,
                checkpoint_object_id="memory_window_context",
                reason="memory_window_safety_composite_id_missing_or_invalid",
            )

        composite_row = connection.execute(
            "SELECT * FROM printer_safety_evidence_composites WHERE id=?",
            (composite_id,),
        ).fetchone()
        if composite_row is None:
            return _unknown_safety(
                graph,
                checkpoint_object_id="memory_window_context",
                reason="persisted_safety_composite_missing",
            )
        composite = dict(composite_row)
        traces = [
            dict(row)
            for row in connection.execute(
                """
                SELECT contribution.*,
                       request.source_name AS request_source_name,
                       response.source_name AS response_source_name,
                       response.source_request_id AS response_request_id,
                       failure.source_name AS failure_source_name
                FROM printer_safety_evidence_contributions AS contribution
                LEFT JOIN printer_source_requests AS request
                  ON request.id=contribution.source_request_id
                LEFT JOIN printer_source_responses AS response
                  ON response.id=contribution.source_response_id
                LEFT JOIN printer_source_failures AS failure
                  ON failure.id=contribution.source_failure_id
                WHERE contribution.composite_id=?
                ORDER BY contribution.id
                """,
                (composite_id,),
            ).fetchall()
        ]

        reasons: list[str] = []
        if (
            int(window["token_id"]) != int(graph["token_row_id"])
            or int(window["pair_id"]) != int(graph["pair_row_id"])
        ):
            reasons.append("memory_window_target_identity_mismatch")
        if (
            int(composite["token_id"]) != int(graph["token_row_id"])
            or int(composite["pair_id"]) != int(graph["pair_row_id"])
            or str(composite["token_mint"]) != str(graph["mint_identity"])
            or str(composite["pair_address"]) != str(graph["pair_identity"])
            or composite["target_status"] != "TARGET_MATCH"
        ):
            reasons.append("safety_target_identity_mismatch")
        closing_snapshot_id = window.get("snapshot_end_id")
        if (
            closing_snapshot_id is None
            or int(composite["snapshot_id"]) != int(closing_snapshot_id)
        ):
            reasons.append("safety_closing_snapshot_mismatch")
        if (
            composite["memory_window_id"] is not None
            and int(composite["memory_window_id"])
            != int(graph["memory_window_row_id"])
        ):
            reasons.append("safety_memory_window_mismatch")

        if memory_window_close_cutoff is not None:
            authoritative_window_end = str(window.get("window_end_at") or "")
            if (
                not authoritative_window_end
                or str(memory_window_close_cutoff) != authoritative_window_end
            ):
                raise CampaignAuthorityAdapterError(
                    "memory-window safety cutoff must equal authoritative window_end_at"
                )
            cutoff_value = authoritative_window_end
        else:
            cutoff_value = str(graph["checkpoint_cutoff"])
        cutoff = _time(cutoff_value)
        captured = _time(composite["evidence_captured_at"])
        age = (cutoff - captured).total_seconds() if cutoff and captured else None
        if age is None or age < 0 or age > MAX_AGE_SECONDS:
            reasons.append("safety_evidence_stale_or_post_cutoff")
        if composite["freshness_label"] not in {
            "SAFETY_EVIDENCE_FRESH",
            "SAFETY_EVIDENCE_ACCEPTABLE",
        }:
            reasons.append("safety_freshness_label_not_acceptable")

        if not traces:
            reasons.append("safety_source_trace_missing")
        for trace in traces:
            trace_captured = _time(trace["captured_at"])
            trace_age = (
                (cutoff - trace_captured).total_seconds()
                if cutoff and trace_captured
                else None
            )
            trace_valid = (
                trace["request_source_name"] == trace["source_name"]
                and str(trace["token_mint"]) == str(graph["mint_identity"])
                and str(trace["pair_address"]) == str(graph["pair_identity"])
                and trace["target_status"] == "TARGET_MATCH"
                and trace["freshness_label"]
                in {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
                and trace["source_status"] in {"COMPLETE", "PARTIAL"}
                and trace["data_quality_label"]
                in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
                and trace["rejection_reason"] is None
                and trace_age is not None
                and 0 <= trace_age <= MAX_AGE_SECONDS
                and (
                    trace["source_response_id"] is None
                    or (
                        trace["response_source_name"] == trace["source_name"]
                        and int(trace["response_request_id"])
                        == int(trace["source_request_id"])
                    )
                )
                and (
                    trace["source_failure_id"] is None
                    or trace["failure_source_name"] == trace["source_name"]
                )
            )
            if not trace_valid:
                reasons.append("safety_source_trace_mismatch")
                break

        try:
            gate_accepted = composite_row_is_acceptable(composite) and not reasons
        except (TypeError, ValueError, json.JSONDecodeError):
            gate_accepted = False
            reasons.append("safety_composite_payload_invalid")
        if not gate_accepted and not reasons:
            reasons.append("authoritative_safety_gate_blocked")
        effective = effective_safety_context_report(
            composite,
            gate_accepted=gate_accepted,
            window_kind=str(graph["window_kind"]),
        )
        return {
            "authority": "B.2_EFFECTIVE_SAFETY",
            "campaign_id": campaign_id,
            "run_id": run_id,
            "cycle_id": cycle_id,
            "token_slot_id": token_slot_id,
            "window_id": window_id,
            "window_kind": graph["window_kind"],
            "checkpoint_object_id": "memory_window_context",
            "memory_window_row_id": int(graph["memory_window_row_id"]),
            "closing_snapshot_id": closing_snapshot_id,
            "safety_composite_id": composite_id,
            "gate_accepted": gate_accepted,
            "effective_safety_context": effective,
            "raw_composite": composite,
            "source_traces": traces,
            "reasons": list(dict.fromkeys(reasons)),
            "evidence_cutoff": cutoff_value,
            "evidence_cutoff_source": (
                "MEMORY_WINDOW_END"
                if memory_window_close_cutoff is not None
                else "CAMPAIGN_CHECKPOINT"
            ),
            "read_only": True,
        }


def build_4a_authority_facts(
    promotion: Mapping[str, Any], safety: Mapping[str, Any],
) -> dict[str, Any]:
    """Expose only authoritative B.1/B.2 facts consumed by 4A."""
    if promotion.get("authority") != "B.1_AUTHORITATIVE_PROMOTION":
        raise CampaignAuthorityAdapterError("4A promotion facts are not B.1 authoritative")
    if safety.get("authority") != "B.2_EFFECTIVE_SAFETY":
        raise CampaignAuthorityAdapterError("4A safety facts are not B.2 authoritative")
    identity_fields = ("campaign_id", "run_id", "cycle_id", "token_slot_id", "window_id")
    if any(promotion.get(field) != safety.get(field) for field in identity_fields):
        raise CampaignAuthorityAdapterError("B.1/B.2 authority identity mismatch")
    promoted = (
        promotion.get("promotion_status") in _PROMOTED
        and promotion.get("authoritative_episode_id") is not None
    )
    effective = safety.get("effective_safety_context") or {}
    return {
        "predecessor_evidence_eligible": promoted,
        "predecessor_memory_quality": "CLEAN_MEMORY" if promoted else "DO_NOT_TRAIN",
        "safety_context_present": safety.get("safety_composite_id") is not None,
        "safety_context_result": effective.get(
            "effective_safety_context_result", SAFETY_CONTEXT_UNKNOWN
        ),
        "authority_sources": ("B.1", "B.2"),
    }
