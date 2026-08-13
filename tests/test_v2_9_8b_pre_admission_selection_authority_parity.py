from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    DiscoverySelectionCandidate,
    apply_existing_discovery_gate_and_selection,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _candidate(
    name: str,
    *,
    channels: set[str],
    gaps: list[dict[str, str]] | None = None,
    mint: str | None = None,
) -> DiscoverySelectionCandidate:
    exact_mint = mint or f"mint-{name}"
    return DiscoverySelectionCandidate(
        merged_candidate_id=f"merged-{name}",
        mint=exact_mint,
        market_identity=f"solana-mainnet:pumpswap:pool-{name}",
        lifecycle="PUMP_GRADUATED_TO_PUMPSWAP",
        channels=channels,
        observation_ids=[f"observation-{name}"],
        conflicts=[],
        gaps=list(gaps or ()),
        origin_state="CONFIRMED",
        pumpswap_state="CONFIRMED",
    )


def test_shared_owner_preserves_gate_causes_and_uniform_exact_pair(tmp_path) -> None:
    path = tmp_path / "selection-parity.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        latest = _candidate("latest", channels={"LATEST_PUMPFUN"})
        active = _candidate("active", channels={"ACTIVE_PUMPFUN"})
        dirty = _candidate(
            "dirty",
            channels={"TOP_PUMPFUN"},
            gaps=[{"kind": "HOLDER_EVIDENCE_INELIGIBLE"}],
        )
        infrastructure = _candidate(
            "infrastructure",
            channels={"TRENDING_PUMPFUN"},
            mint="So11111111111111111111111111111111111111112",
        )

        outcome = apply_existing_discovery_gate_and_selection(
            connection,
            candidates=(latest, active, dirty, infrastructure),
            discovery_batch_id="pre-admission:attempt-1",
            evaluated_at=NOW,
            mode="INITIAL",
            vacant_slot_ordinals=(1, 2),
            batch_seq=1,
            cycle_seed="seed-2",
            handoffs_used=0,
        )

        assert tuple(item.mint for item in outcome.eligible) == (
            "mint-latest",
            "mint-active",
        )
        assert tuple(item.mint for item in outcome.selected) == (
            "mint-latest",
            "mint-active",
        )
        assert dict(outcome.rejection_causes) == {
            "merged-dirty": "EVIDENCE_QUALITY",
            "merged-infrastructure": "INFRASTRUCTURE_EXCLUSION",
        }
    finally:
        connection.close()


def test_same_seed_is_deterministic_without_scoring_or_ranking(tmp_path) -> None:
    path = tmp_path / "selection-determinism.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        candidates = tuple(
            _candidate(str(index), channels={"TOP_PUMPFUN"})
            for index in range(1, 5)
        )
        first = apply_existing_discovery_gate_and_selection(
            connection,
            candidates=candidates,
            discovery_batch_id="pre-admission:attempt-1",
            evaluated_at=NOW,
            mode="INITIAL",
            vacant_slot_ordinals=(1, 2),
            batch_seq=3,
            cycle_seed="literal-seed",
            handoffs_used=0,
        )
        second = apply_existing_discovery_gate_and_selection(
            connection,
            candidates=tuple(
                _candidate(str(index), channels={"TOP_PUMPFUN"})
                for index in range(4, 0, -1)
            ),
            discovery_batch_id="pre-admission:attempt-1",
            evaluated_at=NOW,
            mode="INITIAL",
            vacant_slot_ordinals=(1, 2),
            batch_seq=3,
            cycle_seed="literal-seed",
            handoffs_used=0,
        )
        assert tuple(item.mint for item in first.selected) == tuple(
            item.mint for item in second.selected
        )
        assert len(first.selected) == 2
    finally:
        connection.close()
