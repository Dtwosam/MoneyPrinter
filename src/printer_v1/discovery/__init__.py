"""Discovery Engine foundation for Printer V1."""

from printer_v1.discovery.classifier import (
    build_priority_reason,
    choose_initial_lifecycle_state,
    choose_tracking_lane,
    classify_discovery_candidate,
)
from printer_v1.discovery.contracts import (
    DiscoveryCandidateLabel,
    DiscoveryOutputAction,
    DiscoveryPayloadState,
)
from printer_v1.discovery.discovery import process_discovery_payload
from printer_v1.discovery.parser import normalize_candidates, normalize_candidate
from printer_v1.discovery.checkpoint3_guards import install_checkpoint3_guards


# Package-local, idempotent installation of the three deterministic Checkpoint 3
# repairs. Direct submodule imports execute this package initializer first.
install_checkpoint3_guards()


__all__ = [
    "DiscoveryCandidateLabel",
    "DiscoveryOutputAction",
    "DiscoveryPayloadState",
    "build_priority_reason",
    "choose_initial_lifecycle_state",
    "choose_tracking_lane",
    "classify_discovery_candidate",
    "normalize_candidate",
    "normalize_candidates",
    "process_discovery_payload",
]
