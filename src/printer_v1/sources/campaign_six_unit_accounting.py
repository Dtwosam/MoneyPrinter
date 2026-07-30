"""Campaign-wide six-unit accounting owner for ordinary discovery/selection.

Durable evidence is the ordered transport identities plus non-transport unit
counters. Report totals are derived from that evidence. Replay reconstructs
totals only from durable evidence and compares them to stored report totals —
never self-compares the same totals field.
"""

from __future__ import annotations

import copy
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
    stage_evidence_count: int = field(default=0, init=False)
    pre_operation_no_work: bool = field(default=False, init=False)
    pre_operation_no_work_reason: str | None = field(default=None, init=False)
    accounting_block_reason: str | None = field(default=None, init=False)

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

    def ingest_stage_evidence(self, evidence: Mapping[str, Any] | None) -> None:
        """Aggregate one active stage's durable evidence onto this owner.

        The top-level owner is the single accounting authority: stage results
        may *expose* evidence, but only the owner aggregates it. A missing,
        malformed, duplicate, or negative stage evidence block fails closed
        (raising) before it can contribute silently. Rehydrated transport
        identities are recorded (the ledger enforces duplicate detection); the
        three non-transport counters are summed.
        """
        if not isinstance(evidence, Mapping):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")
        if not evidence:
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_EMPTY")
        required_fields = {
            "evidence_kind",
            "transport_operations",
            "local_validations",
            "scheduler_work_items",
            "lifecycle_reservations",
        }
        if (
            evidence.get("evidence_kind") != "CAMPAIGN_SIX_UNIT_EVIDENCE_V1"
            or not required_fields.issubset(evidence)
        ):
            raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")
        for field_name, owner_value in (
            ("campaign_id", self.campaign_id),
            ("run_id", self.run_id),
            ("cycle_id", self.cycle_id),
        ):
            evidence_value = evidence.get(field_name)
            if (
                owner_value is not None
                and evidence_value is not None
                and str(evidence_value) != str(owner_value)
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_IDENTITY_MISMATCH:"
                    f"{field_name}:{evidence_value!r}!={owner_value!r}"
                )
        # Structural validation (malformed / duplicate-within-stage / negative).
        try:
            stage_totals = reconstruct_six_unit_totals_from_evidence(evidence)
        except CampaignSixUnitError as exc:
            if str(exc).startswith("SIX_UNIT_STAGE_EVIDENCE_"):
                raise
            raise CampaignSixUnitError(
                f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
            ) from exc
        is_pre_operation_no_work = evidence.get("phase") == "PRE_OPERATION_NO_WORK"
        if is_pre_operation_no_work:
            if (
                self.stage_evidence_count != 0
                or self.pre_operation_no_work
                or evidence.get("source_transport_attempted") is not False
                or int(evidence.get("source_governor_requests") or 0) != 0
                or evidence.get("scheduler_work_exists") is not False
                or evidence.get("lifecycle_began") is not False
                or not str(evidence.get("no_work_reason") or "").strip()
                or any(int(value) != 0 for value in stage_totals.values())
            ):
                raise CampaignSixUnitError(
                    "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:"
                    "PRE_OPERATION_NO_WORK_CONTRACT"
                )
        elif self.pre_operation_no_work:
            raise CampaignSixUnitError(
                "SIX_UNIT_STAGE_EVIDENCE_MALFORMED:"
                "PRE_OPERATION_NO_WORK_MIXED_WITH_OPERATION"
            )
        stage_ledger = MeasuredTransportLedger(
            campaign_id=self.campaign_id,
            run_id=self.run_id,
            cycle_id=self.cycle_id,
        )
        transports = evidence.get("transport_operations") or ()
        for raw in transports:
            if not isinstance(raw, Mapping):
                raise CampaignSixUnitError("SIX_UNIT_STAGE_IDENTITY_MALFORMED")
            try:
                stage_ledger.record_transport(
                    TransportOperationIdentity(
                        stage=str(raw.get("stage") or ""),
                        source_name=str(raw.get("source_name") or ""),
                        endpoint_owner=str(raw.get("endpoint_owner") or ""),
                        governed_request_kind=str(
                            raw.get("governed_request_kind") or ""
                        ),
                        method_or_endpoint=str(
                            raw.get("method_or_endpoint") or ""
                        ),
                        within_request_ordinal=int(
                            raw.get("within_request_ordinal") or 0
                        ),
                        target_category=str(raw.get("target_category") or ""),
                        target_identity=(
                            None
                            if raw.get("target_identity") is None
                            else str(raw.get("target_identity"))
                        ),
                        response_bytes=int(raw.get("response_bytes") or 0),
                        normalized_rows=int(raw.get("normalized_rows") or 0),
                        result=str(raw.get("result") or "ATTEMPTED"),
                        reserved_from=(
                            None
                            if raw.get("reserved_from") is None
                            else str(raw.get("reserved_from"))
                        ),
                    )
                )
            except (TypeError, ValueError, MeasuredTransportError) as exc:
                raise CampaignSixUnitError(
                    f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
                ) from exc
        stage_ledger.record_local_validation(
            int(evidence.get("local_validations") or 0)
        )
        stage_ledger.record_scheduler_work_item(
            int(evidence.get("scheduler_work_items") or 0)
        )
        stage_ledger.reserve_lifecycle_transports(
            int(evidence.get("lifecycle_reservations") or 0)
        )
        # Make one stage atomic in memory. A duplicate against an earlier stage
        # or a combined ceiling failure must not partially alter the owner.
        candidate_ledger = copy.deepcopy(self.ledger)
        try:
            candidate_ledger.extend(stage_ledger)
        except MeasuredTransportError as exc:
            raise CampaignSixUnitError(
                f"SIX_UNIT_STAGE_EVIDENCE_MALFORMED:{exc}"
            ) from exc
        self.ledger = candidate_ledger
        self.stage_evidence_count += 1
        self.pre_operation_no_work = is_pre_operation_no_work
        self.pre_operation_no_work_reason = (
            str(evidence["no_work_reason"])
            if is_pre_operation_no_work
            else None
        )

    def close(self, *, ended_at: str | None = None) -> None:
        self.ended_at = ended_at or _utc_now_iso()

    def block(self, reason: str) -> None:
        candidate = str(reason or "").strip()
        if not candidate:
            raise CampaignSixUnitError("SIX_UNIT_ACCOUNTING_BLOCKED")
        if self.accounting_block_reason is None:
            self.accounting_block_reason = candidate

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
            "stage_evidence_count": self.stage_evidence_count,
            "pre_operation_no_work": self.pre_operation_no_work,
            "pre_operation_no_work_reason": self.pre_operation_no_work_reason,
            "accounting_block_reason": self.accounting_block_reason,
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


def aggregate_campaign_six_unit_owner(
    *,
    campaign_id: str | None = None,
    run_id: str | None = None,
    cycle_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    stage_evidences: Sequence[Mapping[str, Any] | None] | None,
) -> CampaignSixUnitOwner:
    """Build one top-level owner that reconciles every active stage's evidence.

    This is the single accounting authority for a campaign attempt. Each active
    stage (direct Pump, PumpSwap, DexScreener, holder/safety, local validations,
    Scheduler work, response bytes, normalized rows, lifecycle reservations)
    contributes exactly one durable evidence block. An omitted or malformed
    block fails closed via ``ingest_stage_evidence``.
    """
    if stage_evidences is None:
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MISSING")
    if (
        not isinstance(stage_evidences, Sequence)
        or isinstance(stage_evidences, (str, bytes))
    ):
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")
    if len(stage_evidences) == 0:
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_EMPTY")
    owner = CampaignSixUnitOwner(
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        started_at=started_at or _utc_now_iso(),
    )
    for evidence in stage_evidences:
        owner.ingest_stage_evidence(evidence)
    owner.close(ended_at=ended_at)
    return owner


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

    def _integer(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError) as exc:
            raise CampaignSixUnitError(
                "SIX_UNIT_EVIDENCE_MALFORMED_COUNTER"
            ) from exc

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
        response_bytes += _integer(raw.get("response_bytes"))
        normalized_rows += _integer(raw.get("normalized_rows"))
        if _integer(raw.get("response_bytes")) < 0 or _integer(
            raw.get("normalized_rows")
        ) < 0:
            raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_NEGATIVE_MEASURE")

    counters = {
        "local_validations": _integer(evidence.get("local_validations")),
        "scheduler_work_items": _integer(evidence.get("scheduler_work_items")),
        "lifecycle_reservations": _integer(
            evidence.get("lifecycle_reservations")
        ),
    }
    if any(value < 0 for value in counters.values()):
        raise CampaignSixUnitError("SIX_UNIT_EVIDENCE_NEGATIVE_MEASURE")

    return {
        "SOURCE_TRANSPORT_OPERATION": len(transports),
        "LOCAL_VALIDATION_STEP": counters["local_validations"],
        "SCHEDULER_WORK_ITEM": counters["scheduler_work_items"],
        "SOURCE_RESPONSE_BYTES": response_bytes,
        "NORMALIZED_SOURCE_ROWS": normalized_rows,
        "LIFECYCLE_RESERVED_TRANSPORT_OPERATION": counters[
            "lifecycle_reservations"
        ],
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


def pre_operation_no_work_evidence(
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    reason: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Deliberate zero evidence for a proven pre-operation no-work terminal."""
    if not all(str(value).strip() for value in (campaign_id, run_id, cycle_id, reason)):
        raise CampaignSixUnitError("SIX_UNIT_STAGE_EVIDENCE_MALFORMED")
    stamp = observed_at or _utc_now_iso()
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "campaign_id": campaign_id,
        "run_id": run_id,
        "cycle_id": cycle_id,
        "phase": "PRE_OPERATION_NO_WORK",
        "no_work_reason": reason,
        "source_transport_attempted": False,
        "source_governor_requests": 0,
        "scheduler_work_exists": False,
        "lifecycle_began": False,
        "started_at": stamp,
        "ended_at": stamp,
        "elapsed_seconds": 0.0,
        "transport_operations": [],
        "local_validations": 0,
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


__all__ = [
    "CampaignSixUnitError",
    "CampaignSixUnitOwner",
    "aggregate_campaign_six_unit_owner",
    "assert_identity_count_matches_claimed",
    "compare_report_totals_to_evidence",
    "empty_six_unit_evidence",
    "empty_six_unit_totals",
    "pre_operation_no_work_evidence",
    "reconstruct_six_unit_totals_from_evidence",
]
