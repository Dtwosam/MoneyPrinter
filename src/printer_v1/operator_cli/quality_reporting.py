"""Read-only quality and memory-authority summaries for Printer V1 reports.

These helpers expose existing evidence. They do not promote memory, unlock
retrieval, change decisions, or infer missing facts.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence


MEMORY_AUTHORITY_RULE = (
    "PARENT_WINDOW_PROVENANCE_ONLY;"
    "CLEAN_EPISODE_AND_FINGERPRINT_AUTHORITATIVE_WHEN_PROMOTED"
)


def _window_id(window: Mapping[str, Any]) -> int | None:
    try:
        value = window.get("id")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def build_window_blocker_summary(
    windows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Expose exact persisted remaining blockers for attached memory windows."""
    blocking_reasons: list[str] = []
    per_window: list[dict[str, Any]] = []
    for window in windows:
        raw = window.get("supporting_context_json")
        context_status = "ABSENT"
        context: Mapping[str, Any] = {}
        if isinstance(raw, Mapping):
            context = raw
            context_status = "PARSED"
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                context_status = "MALFORMED"
            else:
                if isinstance(parsed, Mapping):
                    context = parsed
                    context_status = "PARSED"
                else:
                    context_status = "MALFORMED"
        raw_blockers = context.get("remaining_blockers") if context_status == "PARSED" else None
        blockers = (
            [str(item) for item in raw_blockers if str(item).strip()]
            if isinstance(raw_blockers, (list, tuple))
            else []
        )
        for blocker in blockers:
            if blocker not in blocking_reasons:
                blocking_reasons.append(blocker)
        per_window.append(
            {
                "window_id": _window_id(window),
                "window_kind": window.get("window_kind"),
                "memory_status": window.get("memory_status"),
                "memory_quality_label": window.get("memory_quality_label"),
                "data_quality_label": window.get("data_quality_label"),
                "do_not_train": int(window.get("do_not_train") or 0),
                "supporting_context_status": context_status,
                "remaining_blockers": blockers,
            }
        )
    return {
        "has_blockers": bool(blocking_reasons),
        "blocking_reasons": blocking_reasons,
        "per_window": per_window,
    }


def build_memory_authority_summary(
    windows: Sequence[Mapping[str, Any]],
    promotions_by_window_id: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe parent-window provenance versus authoritative clean artifacts.

    The parent memory window intentionally remains its persisted status (often
    PARTIAL_MEMORY after a clean E2Q candidate). A clean E2Z episode plus its
    fingerprint is the authoritative clean object. Retrieval remains locked.
    """
    per_window: list[dict[str, Any]] = []
    clean_count = 0
    for window in windows:
        window_id = _window_id(window)
        promotion = (
            promotions_by_window_id.get(window_id)
            if window_id is not None
            else None
        )
        episode_id = promotion.get("id") if promotion else None
        fingerprint_id = promotion.get("fingerprint_id") if promotion else None
        complete_clean = bool(
            promotion
            and episode_id is not None
            and fingerprint_id is not None
            and promotion.get("memory_status") == "CLEAN_MEMORY"
            and promotion.get("memory_quality_label") == "CLEAN_MEMORY"
            and promotion.get("data_quality_label") == "CLEAN_DATA"
            and int(promotion.get("do_not_train") or 0) == 0
        )
        if complete_clean:
            clean_count += 1
        per_window.append(
            {
                "parent_window_id": window_id,
                "window_kind": window.get("window_kind"),
                "parent_memory_status": window.get("memory_status"),
                "parent_memory_quality_label": window.get("memory_quality_label"),
                "parent_status_is_authoritative_clean_object": False,
                "authoritative_clean_artifact": (
                    "EPISODE_AND_FINGERPRINT" if complete_clean else None
                ),
                "episode_id": int(episode_id) if complete_clean else None,
                "fingerprint_id": int(fingerprint_id) if complete_clean else None,
            }
        )
    return {
        "authority_rule": MEMORY_AUTHORITY_RULE,
        "retrieval_status": "LOCKED",
        "retrieval_or_decision_use_enabled": False,
        "authoritative_clean_artifact_count": clean_count,
        "per_window": per_window,
    }
