"""DTW-87 bounded deterministic proof of the DTW-86 activation-route repair.

Offline only.  This proof exercises the repaired seam from the canonical frozen
activation contract through the operational authority projector and immutable
MEMORY_OBSERVATION readiness bundle.  It performs no provider call, operational
campaign run, authorization, real WINDOW_15M, memory generation, retrieval, or
paper-trading work.
"""

from __future__ import annotations

from dataclasses import replace
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import (
    ActivationPurpose,
    AdmissionAuthority,
    EvidenceRole,
    FrozenMemoryActivationCandidate,
    FrozenMemoryActivationSet,
    TrackingFeasibility,
    required_evidence_roles_for_candidate,
)
from printer_v1.operator_cli import authoritative_live_operational_campaign as live_campaign
from printer_v1.operator_cli.pilot_input_readiness import (
    BLOCKED_ACTIVATION,
    READINESS_PURPOSE_FUTURE_ACTION,
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    READINESS_READY,
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
    evaluate_readiness_gates,
)

NOW = "2026-08-08T18:30:00+00:00"
EXPIRES = "2099-01-01T00:00:00+00:00"

MARKET_MINT = "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump"
MARKET_POOL = "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p"
DIRECT_MINT = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
DIRECT_POOL = "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo"
ALT1_MINT = "5tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK2pump"
ALT1_POOL = "CDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ22q"
ALT2_MINT = "6FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDRpump"
ALT2_POOL = "AyuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fp"


def _tracking() -> TrackingFeasibility:
    return TrackingFeasibility(
        eligible=True,
        reason_code="DTW87_BOUNDED_FIXTURE",
        tracking_queue_id=None,
        tracking_queue_status=None,
        requalification_required=False,
        cooldown_until=None,
        assessed_at=NOW,
    )


def _frozen(
    *,
    ordinal: int,
    mint: str,
    pool: str,
    authority: AdmissionAuthority,
    route: str,
) -> FrozenMemoryActivationCandidate:
    direct = authority is AdmissionAuthority.DIRECT_PUMP_PUMPSWAP
    return FrozenMemoryActivationCandidate(
        slot_ordinal=ordinal,
        mint=mint,
        pool=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        lifecycle_identity=("GRADUATED_MEMECOIN" if direct else "PRESENT_POOL_CONFIRMED"),
        activation_route=route,
        provenance=("LATEST_GRADUATED" if ordinal % 2 else "PERSISTED_GRADUATED"),
        memory_observation_eligible=True,
        fully_eligible=False,
        holder_condition="HOLDER_CONCENTRATION_EXTREME",
        holder_evidence_status="CONTEXT_ONLY",
        future_action_eligibility="BLOCKED_OR_UNKNOWN",
        evidence_expires_at=EXPIRES,
        liquidity_observed_at=NOW,
        tracking_feasibility=_tracking(),
        retained_evidence_references=(),
        admission_authority=authority,
        claims_pump_origin=direct,
        claims_pumpswap_graduation=direct,
    )


def _activation_set() -> FrozenMemoryActivationSet:
    market = _frozen(
        ordinal=1,
        mint=MARKET_MINT,
        pool=MARKET_POOL,
        authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        route="MARKET_PRESENT_POOL",
    )
    direct = _frozen(
        ordinal=2,
        mint=DIRECT_MINT,
        pool=DIRECT_POOL,
        authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        route="PUMP_CREATE",
    )
    alt1 = _frozen(
        ordinal=3,
        mint=ALT1_MINT,
        pool=ALT1_POOL,
        authority=AdmissionAuthority.MARKET_PRESENT_POOL,
        route="MARKET_PRESENT_POOL",
    )
    alt2 = _frozen(
        ordinal=4,
        mint=ALT2_MINT,
        pool=ALT2_POOL,
        authority=AdmissionAuthority.DIRECT_PUMP_PUMPSWAP,
        route="GRADUATION_NATIVE",
    )
    return FrozenMemoryActivationSet(
        activation_purpose=ActivationPurpose.MEMORY_OBSERVATION,
        readiness_id="DTW87_BOUNDED_PROOF",
        selection_seed="dtw87-seed",
        selected=(market, direct),
        alternates=(alt1, alt2),
        manifest_request_ids=(),
        manifest_transport_identity_keys=(),
        frozen_at=NOW,
        expires_at=EXPIRES,
    )


def _project(candidate: FrozenMemoryActivationCandidate, provenance: str) -> ReadinessCandidate:
    return ReadinessCandidate(
        mint=candidate.mint,
        pool=candidate.pool,
        market_identity=candidate.market_identity,
        liquidity_usd=5_000.0 + candidate.slot_ordinal,
        liquidity_observed_at=candidate.liquidity_observed_at,
        activation_route=candidate.activation_route,
        holder_eligible=False,
        provenance=provenance,
        memory_observation_eligible=candidate.memory_observation_eligible,
        holder_condition=candidate.holder_condition,
        future_action_eligibility=candidate.future_action_eligibility,
        admission_authority=live_campaign._readiness_admission_authority(candidate),
        slot_ordinal=candidate.slot_ordinal,
        tracking_eligible=candidate.tracking_feasibility.eligible,
        tracking_reason=candidate.tracking_feasibility.reason_code,
        tracking_requalification_required=(
            candidate.tracking_feasibility.requalification_required
        ),
    )


class DTW87ActivationRouteBoundedProof(unittest.TestCase):
    def test_canonical_authority_role_matrix_and_projection_are_exact(self) -> None:
        activation = _activation_set()
        market, direct = activation.selected

        self.assertEqual(
            required_evidence_roles_for_candidate(market),
            (EvidenceRole.MARKET_OBSERVATION,),
        )
        self.assertEqual(
            required_evidence_roles_for_candidate(direct),
            (
                EvidenceRole.ORIGIN_LINEAGE,
                EvidenceRole.PUMPSWAP_CONFIRMATION,
                EvidenceRole.MARKET_OBSERVATION,
            ),
        )
        self.assertEqual(
            live_campaign._readiness_admission_authority(market),
            "MARKET_PRESENT_POOL",
        )
        self.assertEqual(
            live_campaign._readiness_admission_authority(direct),
            "DIRECT_PUMP_PUMPSWAP",
        )
        self.assertEqual(market.activation_route, "MARKET_PRESENT_POOL")
        self.assertEqual(direct.activation_route, "PUMP_CREATE")

    def test_mixed_authority_pair_reaches_immutable_memory_readiness_bundle(self) -> None:
        activation = _activation_set()
        latest = _project(activation.selected[0], "LATEST_GRADUATED")
        persisted = _project(activation.selected[1], "PERSISTED_GRADUATED")

        self.assertEqual(
            evaluate_readiness_gates(
                latest,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            READINESS_READY,
        )

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "dtw87.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                source_before = {
                    table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in (
                        "printer_source_requests",
                        "printer_source_responses",
                        "printer_source_failures",
                    )
                }
                bundle = build_pilot_input_ready_bundle(
                    connection,
                    readiness_id=activation.readiness_id,
                    latest=latest,
                    persisted=persisted,
                    holder_evidence={"status": "CONTEXT_ONLY"},
                    source_ledger={"proof": "NO_SOURCE_IO"},
                    selection_seed=activation.selection_seed,
                    git_provenance_identity="dtw87-bounded-proof",
                    configuration_hash="8" * 64,
                    expires_at=EXPIRES,
                    now=NOW,
                    readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
                )
                source_after = {
                    table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in source_before
                }

                self.assertEqual(source_after, source_before)
                self.assertEqual(bundle["readiness_state"], READINESS_READY)
                self.assertEqual(
                    bundle["readiness_purpose"], READINESS_PURPOSE_MEMORY_OBSERVATION
                )
                ordered = bundle["ordered_selected_candidates"]
                self.assertEqual(
                    [item["admission_authority"] for item in ordered],
                    ["MARKET_PRESENT_POOL", "DIRECT_PUMP_PUMPSWAP"],
                )
                self.assertEqual(
                    [item["activation_route"] for item in ordered],
                    ["MARKET_PRESENT_POOL", "PUMP_CREATE"],
                )
                self.assertEqual(
                    [item["holder_eligible"] for item in ordered], [False, False]
                )
                for table in (
                    "printer_memory_windows",
                    "printer_paper_decisions",
                    "printer_paper_positions",
                    "printer_paper_trade_events",
                    "printer_paper_trade_audits",
                ):
                    self.assertEqual(
                        int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]),
                        0,
                    )
            finally:
                connection.close()

    def test_future_action_and_contradictory_market_route_remain_fail_closed(self) -> None:
        activation = _activation_set()
        latest = _project(activation.selected[0], "LATEST_GRADUATED")
        persisted = _project(activation.selected[1], "PERSISTED_GRADUATED")

        # Holder passes are supplied here only to reach the unchanged FUTURE_ACTION
        # route gate. MARKET_PRESENT_POOL remains outside the legacy action routes.
        self.assertEqual(
            evaluate_readiness_gates(
                replace(latest, holder_eligible=True),
                replace(persisted, holder_eligible=True),
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_FUTURE_ACTION,
            ),
            BLOCKED_ACTIVATION,
        )

        contradictory = replace(
            latest,
            activation_route="GRADUATION_NATIVE",
            admission_authority="MARKET_PRESENT_POOL",
        )
        self.assertEqual(
            evaluate_readiness_gates(
                contradictory,
                persisted,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
            BLOCKED_ACTIVATION,
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
