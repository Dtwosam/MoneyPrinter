"""Campaign-wide six-unit accounting owner for ordinary discovery/selection.

Durable evidence is the ordered transport identities plus non-transport unit
counters. Report totals are derived from that evidence. Replay reconstructs
totals only from durable evidence and compares them to stored report totals —
never self-compares the same totals field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from printer_v1.sources.measured_transport import (
    SIX_UNITS,
    MeasuredTransportError,
    MeasuredTransportLedger,
    TransportOperationIdentity,
    empty_six_unit_totals,
    reconcile_six_unit_totals,
)


class CampaignSixUnitError(RuntimeError):
    """Fail-closed campaign six-unit accounting fault."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@dataclass
class CampaignSixUnitOwner:
    """Single owner for one ordinary campaign/discovery attempt's six units."""

    campaign_id: str | None = None
    run_id: str | None = None
    cycle_id: str | None = None
    started_at: str = field(default_factory=_utc_now_iso)
    ended_at: str | None = None
    ledger: MeasuredTransportLedger = field(default_factory=MeasuredTransportLedger)

    def __post_init__(self) -> None:
        self.ledger.campaign_id = self.campaign_id
        self.ledger.run_id = self.run_id
        self.ledger.cycle_id = self.cycle_id

    def extend_ledger(self, other: MeasuredTransportLedger) -> None:
        self.ledger.extend(other)

    def record_transport(self, identity: TransportOperationIdentity) -> None:
        self.ledger.record_transport(identity)

    def record_local_validation(self, count: int = 1) -> None:
        self.ledger.record_local_validation(count)

    def record_scheduler_work_item(self, count: int = 1) -> None:
        self.ledger.record_scheduler_work_item(count)

    def reserve_lifecycle_transports(self, count: int) -> None:
        self.ledger.reserve_lifecycle_transports(count)

    def close(self, *, ended_at: str | None = None) -> None:
        self.ended_at = ended_at or _utc_now_iso()

    def elapsed_seconds(self) -> float:
        end = self.ended_at or _utc_now_iso()
        return max(0.0, (_parse_iso(end) - _parse_iso(self.started_at)).total_seconds())

    def durable_evidence(self) -> dict[str, Any]:
        """Return durable six-unit evidence (not the derived totals alone)."""
        if self.ended_at is None:
            self.close()
        return {
            "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
            "campaign_id": self.campaign_id,
            "run_id": self.run_id,
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_seconds": round(self.elapsed_seconds(), 6),
            "transport_operations": [
                item.as_dict() for item in self.ledger.transports
            ],
            "local_validations": int(self.ledger.local_validations),
            "scheduler_work_items": int(self.ledger.scheduler_work_items),
            "lifecycle_reservations": int(self.ledger.lifecycle_reservations),
        }

    def six_unit_totals(self) -> dict[str, int]:
        return self.ledger.six_unit_totals()


def reconstruct_six_unit_totals_from_evidence(
    evidence: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Independently rebuild six-unit totals from durable evidence only."""
    if not isinstance(evidence, Mapping):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_MISSING")
    if str(evidence.get("evidence_kind") or "") not in {
        "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "",
    } and "transport_operations" not in evidence:
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_KIND_UNSUPPORTED")

    transports = evidence.get("transport_operations") or ()
    if not isinstance(transports, Sequence) or isinstance(transports, (str, bytes)):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_TRANSPORTS_MALFORMED")

    seen: set[tuple[Any, ...]] = set()
    response_bytes = 0
    normalized_rows = 0
    for raw in transports:
        if not isinstance(raw, Mapping):
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_IDENTITY_MALFORMED")
        key = (
            raw.get("stage"),
            raw.get("source_name"),
            raw.get("governed_request_kind"),
            raw.get("method_or_endpoint"),
            raw.get("within_request_ordinal"),
            raw.get("target_category"),
            raw.get("target_identity"),
        )
        if key in seen:
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_DUPLICATE_IDENTITY")
        seen.add(key)
        response_bytes += int(raw.get("response_bytes") or 0)
        normalized_rows += int(raw.get("normalized_rows") or 0)
        if int(raw.get("response_bytes") or 0) < 0 or int(raw.get("normalized_rows") or 0) < 0:
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_NEGATIVE_MEASURE")

    return {
        "SOURCE_TRANSPORT_OPERATION": len(transports),
        "LOCAL_VALIDATION_STEP": int(evidence.get("local_validations") or 0),
        "SCHEDULER_WORK_ITEM": int(evidence.get("scheduler_work_items") or 0),
        "SOURCE_RESPONSE_BYTES": response_bytes,
        "NORMALIZED_SOURCE_ROWS": normalized_rows,
        "LIFECYCLE_RESERVED_TRANSPORT_OPERATION": int(
            evidence.get("lifecycle_reservations") or 0
        ),
    }


def compare_report_totals_to_evidence(
    report_totals: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Compare stored report totals to independent evidence reconstruction."""
    reconstructed = reconstruct_six_unit_totals_from_evidence(evidence)
    stored = dict(report_totals or {})
    if "six_unit_totals" in stored:
        stored = dict(stored["six_unit_totals"])
    comparison = reconcile_six_unit_totals(
        {"six_unit_totals": {unit: int(stored.get(unit) or 0) for unit in SIX_UNITS}},
        {"six_unit_totals": reconstructed},
    )
    return {
        "equal": bool(comparison["equal"]),
        "mismatches": comparison["mismatches"],
        "report_totals": comparison["left"],
        "reconstructed_from_evidence": comparison["right"],
        "self_comparison": False,
    }


def assert_identity_count_matches_claimed(
    *,
    claimed_transport_operations: int,
    identities: Sequence[Mapping[str, Any] | TransportOperationIdentity],
) -> None:
    count = len(identities)
    if int(claimed_transport_operations) != count:
        raise MeasuredTransportError(
            f"TRANSPORT_IDENTITY_COUNT_MISMATCH:claimed={claimed_transport_operations}:identities={count}"
        )


def empty_six_unit_evidence() -> dict[str, Any]:
    now = _utc_now_iso()
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "campaign_id": None,
        "run_id": None,
        "cycle_id": None,
        "started_at": now,
        "ended_at": now,
        "elapsed_seconds": 0.0,
        "transport_operations": [],
        "local_validations": 0,
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


__all__ = [
    "CampaignSixUnitError",
    "CampaignSixUnitOwner",
    "assert_identity_count_matches_claimed",
    "compare_report_totals_to_evidence",
    "empty_six_unit_evidence",
    "empty_six_unit_totals",
    "reconstruct_six_unit_totals_from_evidence",
]
