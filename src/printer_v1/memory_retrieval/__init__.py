"""Memory Retrieval + Similarity Engine foundation for Printer V1."""

from printer_v1.memory_retrieval.contracts import (
    MatchReasonLabel,
    MatchStrengthLabel,
    MemoryEvidenceLabel,
    RetrievalQueryTypeLabel,
    RetrievalResultLabel,
)
from printer_v1.memory_retrieval.fingerprint_builder import build_current_setup_fingerprint
from printer_v1.memory_retrieval.matcher import compare_fingerprints
from printer_v1.memory_retrieval.retriever import retrieve_memory_matches_for_current_setup

__all__ = [
    "MatchReasonLabel",
    "MatchStrengthLabel",
    "MemoryEvidenceLabel",
    "RetrievalQueryTypeLabel",
    "RetrievalResultLabel",
    "build_current_setup_fingerprint",
    "compare_fingerprints",
    "retrieve_memory_matches_for_current_setup",
]
