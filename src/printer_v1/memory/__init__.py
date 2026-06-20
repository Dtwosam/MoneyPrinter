"""Episode / Memory Engine foundation for Printer V1."""

from printer_v1.memory.assembler import assemble_episode, collect_episode_evidence
from printer_v1.memory.contracts import (
    ActionLessonLabel,
    EpisodeOutcomeLabel,
    EpisodeStatus,
    MemoryQualityLabel,
    MemoryRejectionReasonLabel,
    MemoryWindowKind,
    MemoryWindowStatus,
)
from printer_v1.memory.lookup import find_episode_by_window
from printer_v1.memory.recorder import build_and_record_episode
from printer_v1.memory.windowing import get_window_duration_seconds, open_memory_window

__all__ = [
    "ActionLessonLabel",
    "EpisodeOutcomeLabel",
    "EpisodeStatus",
    "MemoryQualityLabel",
    "MemoryRejectionReasonLabel",
    "MemoryWindowKind",
    "MemoryWindowStatus",
    "assemble_episode",
    "build_and_record_episode",
    "collect_episode_evidence",
    "find_episode_by_window",
    "get_window_duration_seconds",
    "open_memory_window",
]
