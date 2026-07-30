"""Canonical discovery/selection authority for ordinary two-token campaigns.

One deterministic owner replaces fragmented mixed-two-slot, holder-pair and
reserve-slice selectors. Provenance is a truthful attribute, never a compulsory
pair quota and never a score/rank/weight/confidence.

Ordinary product is a neutral two-candidate contract (or none). Latest/persisted
readiness columns are not selection authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from printer_v1.discovery.combined_executor import _fisher_yates, _token_identity
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
)


SELECTION_AUTHORITY_VERSION = "V2_9_8B_DISCOVERY_SELECTION_AUTHORITY_V1"
COMBINED_TWO_TOKEN_DOMAIN = "CANONICAL_COMBINED_TWO_TOKEN"

TERMINAL_TWO_READY = "SELECTION_TWO_TOKEN_READY"
TERMINAL_INSUFFICIENT = "DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT"
TERMINAL_CAPACITY = "DISCOVERY_SELECTION_CAPACITY_EXHAUSTED"
TERMINAL_HOLDER_SOURCE = "SELECTION_HOLDER_SOURCE_BLOCKED"
TERMINAL_NONE = "SELECTION_NONE"

HOLDER_SOURCE_UNAVAILABLE_PREFIXES = (
    "HOLDER_EVIDENCE_UNAVAILABLE",
    "HOLDER_EVIDENCE_FAILED",
    "HOLDER_EVIDENCE_STALE",
    "HOLDER_EVIDENCE_COLLECTION_FAILED",
    "MISSING_CRITICAL_DATA",
)


class SelectionAuthorityError(RuntimeError):
    """Fail-closed canonical selection fault."""


@dataclass(frozen=True)
class SelectionCandidate:
    """One eligible or rejected selection candidate."""

    mint: str
    pair_address: str
    market_identity: str
    provenance: str
    lifecycle_state: str = "GRADUATED"
    graduation_block_time: int | None = None
    liquidity_usd: float | None = None
    attributes: Mapping[str, Any] | None = None

    def identity_key(self) -> tuple[str, str, str]:
        return (
            _token_identity(self.mint),
            str(self.market_identity or ""),
            str(self.lifecycle_state or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "mint": self.mint,
            "pair_address": self.pair_address,
            "pool": self.pair_address,
            "market_identity": self.market_identity,
            "provenance": self.provenance,
            "lifecycle_state": self.lifecycle_state,
            "graduation_block_time": self.graduation_block_time,
            "liquidity_usd": self.liquidity_usd,
        }
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        return payload


@dataclass(frozen=True)
class TwoCandidateSelection:
    """Neutral two-candidate contract (exactly two or none)."""

    ready: bool
    terminal: str
    candidate_a: SelectionCandidate | None
    candidate_b: SelectionCandidate | None
    composition_label: str
    funnel: tuple[Mapping[str, Any], ...]
    evaluated_count: int
    pool_size: int
    authority_version: str = SELECTION_AUTHORITY_VERSION

    @property
    def selected(self) -> tuple[SelectionCandidate, ...]:
        if self.candidate_a is None or self.candidate_b is None:
            return ()
        return (self.candidate_a, self.candidate_b)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "terminal": self.terminal,
            "authority_version": self.authority_version,
            "candidate_a": None if self.candidate_a is None else self.candidate_a.as_dict(),
            "candidate_b": None if self.candidate_b is None else self.candidate_b.as_dict(),
            "selected": [item.as_dict() for item in self.selected],
            "selected_count": len(self.selected),
            "composition_label": self.composition_label,
            "funnel": [dict(item) for item in self.funnel],
            "evaluated_count": self.evaluated_count,
            "pool_size": self.pool_size,
            # Diagnostic only — never selection authority columns.
            "provenance_summary": {
                "latest_count": sum(
                    1
                    for item in self.selected
                    if item.provenance == LATEST_GRADUATED_CHANNEL
                ),
                "persisted_count": sum(
                    1
                    for item in self.selected
                    if item.provenance == PERSISTED_GRADUATED_CHANNEL
                ),
            },
        }


def composition_label(selected: Sequence[SelectionCandidate]) -> str:
    if len(selected) < 2:
        return "NONE" if not selected else "SINGLE"
    latest = sum(1 for item in selected if item.provenance == LATEST_GRADUATED_CHANNEL)
    persisted = sum(
        1 for item in selected if item.provenance == PERSISTED_GRADUATED_CHANNEL
    )
    if latest == 2:
        return "LATEST+LATEST"
    if persisted == 2:
        return "PERSISTED+PERSISTED"
    if latest == 1 and persisted == 1:
        return "LATEST+PERSISTED"
    return "MIXED_OTHER"


def deterministic_candidate_order(
    candidates: Sequence[SelectionCandidate],
    *,
    cycle_seed: str,
    domain: str = COMBINED_TWO_TOKEN_DOMAIN,
) -> list[SelectionCandidate]:
    """Identity-stable order then seeded Fisher-Yates. No score/rank/lex preference."""
    if not cycle_seed or not str(cycle_seed).strip():
        raise SelectionAuthorityError("MISSING_SELECTION_SEED")
    # Identity sort is only the stable preimage for the seeded shuffle. It does
    # not confer selection preference; the shuffle domain owns the order.
    ordered = sorted(candidates, key=lambda item: item.identity_key())
    return list(_fisher_yates(ordered, f"{cycle_seed}|{domain}"))


def select_two_candidates(
    candidates: Sequence[SelectionCandidate],
    *,
    cycle_seed: str,
    evaluator: Callable[[SelectionCandidate], tuple[bool, str]] | None = None,
    candidate_cap: int | None = None,
    source_unavailable_prefixes: Sequence[str] = HOLDER_SOURCE_UNAVAILABLE_PREFIXES,
) -> TwoCandidateSelection:
    """Canonical two-or-none selection over one combined pool.

    Walks the deterministic seeded order. Optional evaluator (holder/safety) may
    reject candidates; rejections never become scores. Stops at two distinct
    mint+pair identities or when the pool/cap is exhausted.
    """
    if candidate_cap is not None and candidate_cap < 0:
        raise SelectionAuthorityError("INVALID_CANDIDATE_CAP")

    # Deduplicate by mint+pair while preserving first occurrence for attributes.
    unique: list[SelectionCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        mint = str(item.mint or "").strip()
        pair = str(item.pair_address or "").strip()
        if not mint or not pair:
            continue
        key = (mint, pair)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    order = deterministic_candidate_order(unique, cycle_seed=cycle_seed)
    cap = len(order) if candidate_cap is None else int(candidate_cap)
    selected: list[SelectionCandidate] = []
    funnel: list[dict[str, Any]] = []
    ops = 0
    saw_source_outage = False
    prefixes = tuple(source_unavailable_prefixes)

    for candidate in order:
        if len(selected) >= 2:
            break
        if ops >= cap:
            break
        ops += 1
        if evaluator is None:
            ok, reason = True, "ELIGIBLE"
        else:
            ok, reason = evaluator(candidate)
        if not ok and str(reason).startswith(prefixes):
            saw_source_outage = True
        funnel.append(
            {
                "mint": candidate.mint,
                "pair_address": candidate.pair_address,
                "provenance": candidate.provenance,
                "eligible": bool(ok),
                "reason": reason,
                "operation_ordinal": ops,
            }
        )
        if ok:
            # Distinct mint and distinct pair required for the two slots.
            if any(
                item.mint == candidate.mint or item.pair_address == candidate.pair_address
                for item in selected
            ):
                funnel[-1]["eligible"] = False
                funnel[-1]["reason"] = "DUPLICATE_MINT_OR_PAIR"
                continue
            selected.append(candidate)

    fully_covered = ops >= len(order) and ops <= cap
    cap_reached = ops >= cap and len(selected) < 2 and ops < len(order)
    if len(selected) == 2:
        terminal = TERMINAL_TWO_READY
        ready = True
    elif saw_source_outage:
        terminal = TERMINAL_HOLDER_SOURCE
        ready = False
    elif cap_reached:
        terminal = TERMINAL_CAPACITY
        ready = False
    elif not selected:
        terminal = TERMINAL_NONE if not order else TERMINAL_INSUFFICIENT
        ready = False
    else:
        terminal = TERMINAL_INSUFFICIENT
        ready = False

    return TwoCandidateSelection(
        ready=ready,
        terminal=terminal,
        candidate_a=selected[0] if len(selected) > 0 else None,
        candidate_b=selected[1] if len(selected) > 1 else None,
        composition_label=composition_label(selected),
        funnel=tuple(funnel),
        evaluated_count=ops,
        pool_size=len(order),
    )


def candidate_from_front_door_mapping(item: Mapping[str, Any]) -> SelectionCandidate:
    """Adapt a front-door / reserve mapping into a SelectionCandidate."""
    mint = str(item.get("mint") or item.get("mint_identity") or "").strip()
    pool = str(
        item.get("pair_address")
        or item.get("pumpswap_pool")
        or item.get("pool")
        or ""
    ).strip()
    market = str(
        item.get("market_identity")
        or (f"solana-mainnet:pumpswap:{pool}" if pool else "")
    )
    provenance = str(item.get("provenance") or PERSISTED_GRADUATED_CHANNEL)
    liquidity = item.get("liquidity_usd")
    if liquidity is None and isinstance(item.get("liquidity"), Mapping):
        liquidity = item["liquidity"].get("liquidity_usd")
    return SelectionCandidate(
        mint=mint,
        pair_address=pool,
        market_identity=market,
        provenance=provenance,
        lifecycle_state=str(item.get("lifecycle_state") or "GRADUATED"),
        graduation_block_time=(
            None
            if item.get("graduation_block_time") is None
            else int(item["graduation_block_time"])
        ),
        liquidity_usd=None if liquidity is None else float(liquidity),
        attributes={
            key: item[key]
            for key in item
            if key
            not in {
                "mint",
                "mint_identity",
                "pair_address",
                "pumpswap_pool",
                "pool",
                "market_identity",
                "provenance",
                "lifecycle_state",
                "graduation_block_time",
                "liquidity_usd",
                "liquidity",
            }
        },
    )


__all__ = [
    "COMBINED_TWO_TOKEN_DOMAIN",
    "HOLDER_SOURCE_UNAVAILABLE_PREFIXES",
    "SELECTION_AUTHORITY_VERSION",
    "SelectionAuthorityError",
    "SelectionCandidate",
    "TERMINAL_CAPACITY",
    "TERMINAL_HOLDER_SOURCE",
    "TERMINAL_INSUFFICIENT",
    "TERMINAL_NONE",
    "TERMINAL_TWO_READY",
    "TwoCandidateSelection",
    "candidate_from_front_door_mapping",
    "composition_label",
    "deterministic_candidate_order",
    "select_two_candidates",
]
