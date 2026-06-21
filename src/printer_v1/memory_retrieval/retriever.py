"""Local DB memory retrieval without recommendations or numeric scoring."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.memory.contracts import MemoryQualityLabel
from printer_v1.memory_retrieval.contracts import MatchStrengthLabel, MemoryEvidenceLabel, RetrievalResultLabel
from printer_v1.memory_retrieval.fingerprint_builder import build_current_setup_fingerprint
from printer_v1.memory_retrieval.matcher import compare_fingerprints, memory_match_can_be_clean_evidence


STRENGTH_ORDER = {
    MatchStrengthLabel.EXACT_CONDITION_MATCH.value: 0,
    MatchStrengthLabel.STRONG_CONDITION_MATCH.value: 1,
    MatchStrengthLabel.PARTIAL_CONDITION_MATCH.value: 2,
    MatchStrengthLabel.WEAK_CONDITION_MATCH.value: 3,
    MatchStrengthLabel.NO_USABLE_MATCH.value: 4,
}


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


def retrieve_candidate_memory_episodes(db_path_or_conn: str | Path | sqlite3.Connection, query_payload: Mapping[str, Any]) -> list[sqlite3.Row]:
    del query_payload
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT e.*, f.fingerprint_payload_json,
                   w.evidence_identity_hash AS evidence_identity_hash,
                   w.evidence_role AS evidence_role,
                   w.snapshot_start_id AS snapshot_start_id,
                   w.snapshot_end_id AS snapshot_end_id,
                   w.memory_diversity_label AS memory_diversity_label,
                   w.concentration_audit_reason AS concentration_audit_reason
            FROM printer_episodes e
            LEFT JOIN printer_memory_windows w ON w.id = e.memory_window_id
            LEFT JOIN printer_memory_fingerprints f ON f.episode_id = e.id
            ORDER BY e.created_at DESC, e.id DESC
            """
        ).fetchall()


def build_match(row: sqlite3.Row, current_fingerprint: Mapping[str, Any]) -> dict[str, Any]:
    memory_fingerprint = json.loads(row["fingerprint_payload_json"] or "{}")
    comparison = compare_fingerprints(current_fingerprint, memory_fingerprint)
    quality = row["memory_quality_label"]
    if quality == MemoryQualityLabel.DIRTY_MEMORY.value:
        comparison["match_strength_label"] = MatchStrengthLabel.DIRTY_MEMORY_EXCLUDED.value
    if quality == MemoryQualityLabel.DO_NOT_TRAIN_MEMORY.value:
        comparison["match_strength_label"] = MatchStrengthLabel.DO_NOT_TRAIN_EXCLUDED.value
    payload = {
        "episode_id": row["id"],
        "memory_window_id": row["memory_window_id"],
        "token_id": row["token_id"],
        "pair_id": row["pair_id"],
        "window_kind": row["window_kind"],
        "outcome_label": row["episode_outcome_label"],
        "action_lesson_label": row["action_lesson_label"],
        "memory_quality_label": quality,
        "evidence_identity_hash": row["evidence_identity_hash"],
        "evidence_role": row["evidence_role"],
        "snapshot_start_id": row["snapshot_start_id"],
        "snapshot_end_id": row["snapshot_end_id"],
        "memory_diversity_label": row["memory_diversity_label"],
        "concentration_audit_reason": row["concentration_audit_reason"],
        "memory_fingerprint": memory_fingerprint,
        "comparison_payload": comparison,
        **comparison,
    }
    payload["retrieval_group_key"] = row["evidence_identity_hash"] or f"{row['token_id']}:{row['pair_id']}:{row['window_kind']}:{row['id']}"
    payload["included_as_clean_evidence"] = memory_match_can_be_clean_evidence(payload)
    payload["included_as_audit_context"] = quality in {
        MemoryQualityLabel.PARTIAL_MEMORY.value,
        MemoryQualityLabel.AUDIT_ONLY_MEMORY.value,
    }
    return payload


def retrieve_memory_matches_for_current_setup(db_path_or_conn: str | Path | sqlite3.Connection, query_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    current = build_current_setup_fingerprint(query_payload)
    matches = [
        build_match(row, current)
        for row in retrieve_candidate_memory_episodes(db_path_or_conn, query_payload)
    ]
    sorted_matches = sorted(
        matches,
        key=lambda match: (
            STRENGTH_ORDER.get(match["match_strength_label"], 9),
            0 if match.get("window_kind") == current.get("window_kind") else 1,
            0 if match.get("outcome_label") == current.get("outcome_label") else 1,
            -int(match["episode_id"]),
        ),
    )
    seen_clean_groups: set[str] = set()
    for match in sorted_matches:
        group_key = str(match.get("retrieval_group_key") or "")
        if match.get("included_as_clean_evidence") and group_key in seen_clean_groups:
            match["included_as_clean_evidence"] = False
            match["included_as_audit_context"] = True
            match["match_strength_label"] = MatchStrengthLabel.NO_USABLE_MATCH.value
            reasons = list(match.get("mismatch_reasons") or [])
            reasons.append("DUPLICATE_EVIDENCE_EXCLUDED")
            match["mismatch_reasons"] = list(dict.fromkeys(reasons))
            match["duplicate_guard_status"] = "DUPLICATE_EVIDENCE_EXCLUDED"
        elif match.get("included_as_clean_evidence"):
            seen_clean_groups.add(group_key)
            match["duplicate_guard_status"] = "UNIQUE_CLEAN_EVIDENCE"
    return sorted_matches


def retrieve_clean_memory_matches(db_path_or_conn: str | Path | sqlite3.Connection, query_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        match for match in retrieve_memory_matches_for_current_setup(db_path_or_conn, query_payload)
        if match["included_as_clean_evidence"]
    ]


def retrieve_audit_memory_context(db_path_or_conn: str | Path | sqlite3.Connection, query_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        match for match in retrieve_memory_matches_for_current_setup(db_path_or_conn, query_payload)
        if match["included_as_audit_context"]
    ]


def group_matches_by_outcome(matches: list[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, int] = {}
    for match in matches:
        label = match.get("outcome_label") or "OUTCOME_UNKNOWN"
        grouped[label] = grouped.get(label, 0) + 1
    return grouped


def build_memory_diversity_summary(matches: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean = [match for match in matches if match.get("included_as_clean_evidence")]
    token_pair_counts: dict[str, int] = {}
    for match in clean:
        key = f"{match.get('token_id')}:{match.get('pair_id')}"
        token_pair_counts[key] = token_pair_counts.get(key, 0) + 1
    distinct_token_count = len({match.get("token_id") for match in clean})
    dominant_token_pair_count = max(token_pair_counts.values(), default=0)
    clean_count = len(clean)
    if clean_count == 0:
        label = "NO_CLEAN_MEMORY_DIVERSITY"
        reason = "no_clean_memory_available"
    elif distinct_token_count <= 1 and clean_count >= 2:
        label = "TOKEN_MEMORY_CONCENTRATED"
        reason = "clean_memory_heavily_concentrated_in_one_token_pair"
    elif dominant_token_pair_count > max(1, clean_count // 2) and clean_count >= 3:
        label = "TOKEN_MEMORY_OVERREPRESENTED"
        reason = "dominant_token_pair_exceeds_broad_market_context"
    else:
        label = "NORMAL_TOKEN_MEMORY_DISTRIBUTION"
        reason = "clean_memory_distribution_normal"
    return {
        "memory_diversity_label": label,
        "concentration_audit_reason": reason,
        "clean_memory_count": clean_count,
        "distinct_token_count": distinct_token_count,
        "dominant_token_pair_count": dominant_token_pair_count,
        "token_pair_clean_memory_counts": token_pair_counts,
    }


def build_retrieval_result_label(matches: list[Mapping[str, Any]]) -> RetrievalResultLabel:
    if any(match.get("included_as_clean_evidence") for match in matches):
        return RetrievalResultLabel.RETRIEVAL_HAS_CLEAN_MATCHES
    if not matches:
        return RetrievalResultLabel.RETRIEVAL_NO_MATCHES
    if all(match.get("match_strength_label") in {MatchStrengthLabel.DIRTY_MEMORY_EXCLUDED.value, MatchStrengthLabel.DO_NOT_TRAIN_EXCLUDED.value} for match in matches):
        return RetrievalResultLabel.RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY
    if any(match.get("included_as_audit_context") for match in matches):
        return RetrievalResultLabel.RETRIEVAL_HAS_AUDIT_ONLY_MATCHES
    return RetrievalResultLabel.RETRIEVAL_HAS_PARTIAL_MATCHES_ONLY


def build_memory_evidence_label(matches: list[Mapping[str, Any]]) -> MemoryEvidenceLabel:
    clean = [match for match in matches if match.get("included_as_clean_evidence")]
    if not clean:
        return MemoryEvidenceLabel.MEMORY_EVIDENCE_NOT_ENOUGH
    outcomes = {match.get("outcome_label") for match in clean}
    if len(outcomes) > 1:
        return MemoryEvidenceLabel.MEMORY_EVIDENCE_MIXED
    if any(match["match_strength_label"] == MatchStrengthLabel.EXACT_CONDITION_MATCH.value for match in clean):
        return MemoryEvidenceLabel.MEMORY_EVIDENCE_STRONG
    if any(match["match_strength_label"] == MatchStrengthLabel.PARTIAL_CONDITION_MATCH.value for match in clean):
        return MemoryEvidenceLabel.MEMORY_EVIDENCE_WEAK
    return MemoryEvidenceLabel.MEMORY_EVIDENCE_STRONG
