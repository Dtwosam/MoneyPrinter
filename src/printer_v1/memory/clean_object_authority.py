"""Explicit current E2Q/E2Z clean-memory object authority.

This is a semantics helper only.  It does not enable retrieval and does not
mutate parent memory-window quality labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

E2Q_CLEAN_CANDIDATE = "E2Q_CLEAN_CANDIDATE"
E2Z_CLEAN_OBJECT = "E2Z_CLEAN_OBJECT"
LEGACY_WINDOW_CLEAN = "LEGACY_WINDOW_CLEAN"
NOT_CLEAN_ELIGIBLE = "NOT_CLEAN_ELIGIBLE"


@dataclass(frozen=True)
class CleanMemoryAuthority:
    authority: str
    parent_window_is_candidate: bool
    episode_is_clean_object: bool
    future_retrieval_candidate: bool
    retrieval_enabled: bool = False


def classify_clean_memory_authority(
    *,
    window: Mapping[str, Any],
    episode: Mapping[str, Any] | None = None,
    fingerprint: Mapping[str, Any] | None = None,
) -> CleanMemoryAuthority:
    """Classify current object authority without unlocking retrieval."""
    window_quality = str(window.get("memory_quality_label") or "")
    window_status = str(window.get("memory_status") or "")
    data_quality = str(window.get("data_quality_label") or "")
    do_not_train = int(window.get("do_not_train") or 0)
    audited = bool(window.get("e2q_audited") or False)

    if window_quality == "CLEAN_MEMORY" or window_status == "CLEAN_MEMORY":
        return CleanMemoryAuthority(
            authority=LEGACY_WINDOW_CLEAN,
            parent_window_is_candidate=False,
            episode_is_clean_object=False,
            future_retrieval_candidate=False,
        )

    candidate = (
        window_quality == "PARTIAL_MEMORY"
        and window_status == "PARTIAL_MEMORY"
        and data_quality == "CLEAN_DATA"
        and do_not_train == 0
        and audited
    )
    if not candidate:
        return CleanMemoryAuthority(
            authority=NOT_CLEAN_ELIGIBLE,
            parent_window_is_candidate=False,
            episode_is_clean_object=False,
            future_retrieval_candidate=False,
        )

    if episode is None or fingerprint is None:
        return CleanMemoryAuthority(
            authority=E2Q_CLEAN_CANDIDATE,
            parent_window_is_candidate=True,
            episode_is_clean_object=False,
            future_retrieval_candidate=False,
        )

    episode_clean = (
        str(episode.get("memory_quality_label") or "") == "CLEAN_MEMORY"
        and str(episode.get("memory_status") or "") == "CLEAN_MEMORY"
        and int(episode.get("do_not_train") or 0) == 0
        and str(fingerprint.get("memory_status") or fingerprint.get("memory_quality_label") or "")
        == "CLEAN_MEMORY"
    )
    return CleanMemoryAuthority(
        authority=E2Z_CLEAN_OBJECT if episode_clean else E2Q_CLEAN_CANDIDATE,
        parent_window_is_candidate=True,
        episode_is_clean_object=episode_clean,
        future_retrieval_candidate=episode_clean,
        retrieval_enabled=False,
    )
