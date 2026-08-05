"""Transactional clean episode + canonical fingerprint promotion owner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Callable, Mapping


class CleanObjectIntegrityError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class CleanObjectPromotionResult:
    status: str
    episode_id: int
    fingerprint_id: int
    window_id: int

    @property
    def created(self) -> bool:
        return self.status == "CREATED"

    @property
    def idempotent(self) -> bool:
        return self.status == "ALREADY_EXISTS"


FingerprintWriter = Callable[
    [sqlite3.Connection, int, Mapping[str, Any], str], int
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(raw: object) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        parsed = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _exact_identity(value: object, *, code: str) -> int:
    if value in (None, "", "UNKNOWN"):
        raise CleanObjectIntegrityError(code)
    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise CleanObjectIntegrityError(code, str(value)) from exc
    if resolved <= 0:
        raise CleanObjectIntegrityError(code, str(value))
    return resolved


def _fingerprint_payload(
    connection: sqlite3.Connection,
    *,
    episode: sqlite3.Row,
    window: sqlite3.Row,
) -> dict[str, Any]:
    from printer_v1.memory.fingerprints import build_memory_fingerprint_payload

    episode_id = _exact_identity(episode["id"], code="EPISODE_IDENTITY_UNKNOWN")
    window_id = _exact_identity(window["id"], code="WINDOW_IDENTITY_UNKNOWN")
    token_id = _exact_identity(window["token_id"], code="TOKEN_IDENTITY_UNKNOWN")
    pair_id = _exact_identity(window["pair_id"], code="PAIR_IDENTITY_UNKNOWN")
    if (
        int(episode["memory_window_id"]) != window_id
        or int(episode["token_id"]) != token_id
        or int(episode["pair_id"]) != pair_id
        or str(episode["window_kind"]) != str(window["window_kind"])
    ):
        raise CleanObjectIntegrityError("CLEAN_OBJECT_IDENTITY_MISMATCH")

    window_context = _load_json(window["supporting_context_json"])
    episode_context = _load_json(episode["supporting_context_json"])
    tracking_lane = window_context.get("tracking_lane")
    if not tracking_lane:
        token = connection.execute(
            "SELECT token_status FROM printer_tokens WHERE id=?", (token_id,)
        ).fetchone()
        if token is not None and str(token[0]) in {"TRACK_FAST", "TRACK_NORMAL"}:
            tracking_lane = str(token[0])
    payload = build_memory_fingerprint_payload(
        {
            "episode_id": episode_id,
            "window_id": window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "tracking_lane": tracking_lane,
            "window": {
                "id": window_id,
                "token_id": token_id,
                "pair_id": pair_id,
                "window_kind": str(window["window_kind"]),
                "supporting_context_json": window_context,
                "tracking_lane": tracking_lane,
            },
            "outcome_label": episode["episode_outcome_label"] or window["outcome_label"],
            "memory_quality_label": "CLEAN_MEMORY",
            "supporting_context": episode_context or window_context,
            "token_age_bucket": (episode_context or window_context).get("token_age_bucket"),
            "pair_age_bucket": (episode_context or window_context).get("pair_age_bucket"),
            "discovery_label": (episode_context or window_context).get("discovery_label"),
        },
        episode_id=episode_id,
    )
    for field, expected in (
        ("episode_id", episode_id),
        ("window_id", window_id),
        ("token_id", token_id),
        ("pair_id", pair_id),
    ):
        if payload.get(field) in (None, "", "UNKNOWN") or int(payload[field]) != expected:
            raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_MISMATCH", field)
    return payload


def _validate_complete_pair(
    connection: sqlite3.Connection,
    *,
    episode: sqlite3.Row,
    window: sqlite3.Row,
    fingerprint: sqlite3.Row,
) -> None:
    if (
        str(episode["memory_status"]) != "CLEAN_MEMORY"
        or str(episode["memory_quality_label"]) != "CLEAN_MEMORY"
        or int(episode["do_not_train"]) != 0
        or str(fingerprint["memory_status"]) != "CLEAN_MEMORY"
        or int(fingerprint["do_not_train"]) != 0
    ):
        raise CleanObjectIntegrityError("CLEAN_OBJECT_QUALITY_MISMATCH")
    payload = _load_json(fingerprint["fingerprint_payload_json"])
    expected = {
        "episode_id": int(episode["id"]),
        "window_id": int(window["id"]),
        "token_id": int(window["token_id"]),
        "pair_id": int(window["pair_id"]),
    }
    for field, value in expected.items():
        if payload.get(field) in (None, "", "UNKNOWN"):
            raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_UNKNOWN", field)
        if int(payload[field]) != value:
            raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_MISMATCH", field)
    if str(payload.get("window_kind")) != str(window["window_kind"]):
        raise CleanObjectIntegrityError("FINGERPRINT_IDENTITY_MISMATCH", "window_kind")


def promote_clean_object(
    connection: sqlite3.Connection,
    *,
    window_id: int,
    fingerprint_writer: FingerprintWriter | None = None,
) -> CleanObjectPromotionResult:
    """Create/verify one clean episode and fingerprint in one transaction."""
    from printer_v1.memory.fingerprints import record_memory_fingerprint
    from printer_v1.operator_cli.e2z_clean_memory_creation import _gate_window

    writer = fingerprint_writer or record_memory_fingerprint
    connection.row_factory = sqlite3.Row
    savepoint = "clean_object_promotion"
    connection.execute(f"SAVEPOINT {savepoint}")
    try:
        window = connection.execute(
            """SELECT id,token_id,pair_id,window_kind,window_status,memory_status,
                      memory_quality_label,data_quality_label,do_not_train,
                      supporting_context_json,opened_at,closed_at,outcome_label
               FROM printer_memory_windows WHERE id=?""",
            (int(window_id),),
        ).fetchone()
        if window is None:
            raise CleanObjectIntegrityError("WINDOW_NOT_FOUND", str(window_id))
        gate_failures = _gate_window(window)
        if gate_failures:
            raise CleanObjectIntegrityError("WINDOW_NOT_CLEAN_PROMOTION_ELIGIBLE", "; ".join(gate_failures))

        episodes = connection.execute(
            """SELECT id,memory_window_id,token_id,pair_id,episode_kind,
                      memory_status,memory_quality_label,data_quality_label,
                      do_not_train,window_kind,episode_outcome_label,
                      supporting_context_json
               FROM printer_episodes
               WHERE memory_window_id=? AND memory_status='CLEAN_MEMORY'
               ORDER BY id""",
            (int(window_id),),
        ).fetchall()
        if len(episodes) > 1:
            raise CleanObjectIntegrityError("DUPLICATE_CLEAN_EPISODES")
        if episodes:
            episode = episodes[0]
            fingerprints = connection.execute(
                """SELECT id,episode_id,fingerprint_kind,fingerprint_payload_json,
                          memory_status,data_quality_label,do_not_train
                   FROM printer_memory_fingerprints
                   WHERE episode_id=? AND fingerprint_kind='STATIC_CONDITION_SUMMARY'
                   ORDER BY id""",
                (int(episode["id"]),),
            ).fetchall()
            if len(fingerprints) != 1:
                raise CleanObjectIntegrityError("EXISTING_INCOMPLETE_CLEAN_OBJECT")
            _validate_complete_pair(
                connection, episode=episode, window=window, fingerprint=fingerprints[0]
            )
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            return CleanObjectPromotionResult(
                "ALREADY_EXISTS",
                int(episode["id"]),
                int(fingerprints[0]["id"]),
                int(window_id),
            )

        orphan = connection.execute(
            """SELECT id FROM printer_memory_fingerprints
               WHERE json_extract(fingerprint_payload_json,'$.window_id')=?
               LIMIT 1""",
            (int(window_id),),
        ).fetchone()
        if orphan is not None:
            raise CleanObjectIntegrityError("FINGERPRINT_WITHOUT_EXACT_EPISODE")

        now = _utc_now()
        context = _load_json(window["supporting_context_json"])
        episode_context = json.dumps(
            {
                "source_window_id": int(window_id),
                "snapshot_id": context.get("snapshot_id")
                or context.get("token_snapshot_id"),
                "e2q_audit_status": context.get("e2q_audit_status"),
                "tracking_lane": context.get("tracking_lane"),
                "created_by": "lane_e2z",
            },
            sort_keys=True,
        )
        cursor = connection.execute(
            """INSERT INTO printer_episodes(
                   memory_window_id,token_id,pair_id,episode_kind,episode_status,
                   memory_status,data_quality_label,do_not_train,window_kind,
                   memory_quality_label,supporting_context_json,created_at,updated_at
               ) VALUES (?,?,?,?,'COMPLETE','CLEAN_MEMORY','CLEAN_DATA',0,?,
                         'CLEAN_MEMORY',?,?,?)""",
            (
                int(window_id),
                int(window["token_id"]),
                int(window["pair_id"]),
                f"{window['window_kind']}_CLEAN_MEMORY",
                str(window["window_kind"]),
                episode_context,
                now,
                now,
            ),
        )
        episode_id = int(cursor.lastrowid)
        episode = connection.execute(
            """SELECT id,memory_window_id,token_id,pair_id,episode_kind,
                      memory_status,memory_quality_label,data_quality_label,
                      do_not_train,window_kind,episode_outcome_label,
                      supporting_context_json
               FROM printer_episodes WHERE id=?""",
            (episode_id,),
        ).fetchone()
        payload = _fingerprint_payload(connection, episode=episode, window=window)
        try:
            fingerprint_id = int(writer(connection, episode_id, payload, "CLEAN_MEMORY"))
        except Exception as exc:
            raise CleanObjectIntegrityError("FINGERPRINT_CREATION_FAILED", type(exc).__name__) from exc
        fingerprint = connection.execute(
            """SELECT id,episode_id,fingerprint_kind,fingerprint_payload_json,
                      memory_status,data_quality_label,do_not_train
               FROM printer_memory_fingerprints WHERE id=?""",
            (fingerprint_id,),
        ).fetchone()
        if fingerprint is None:
            raise CleanObjectIntegrityError("FINGERPRINT_CREATION_FAILED", "row missing")
        _validate_complete_pair(
            connection, episode=episode, window=window, fingerprint=fingerprint
        )
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        return CleanObjectPromotionResult(
            "CREATED", episode_id, fingerprint_id, int(window_id)
        )
    except Exception:
        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


__all__ = [
    "CleanObjectIntegrityError",
    "CleanObjectPromotionResult",
    "promote_clean_object",
]
