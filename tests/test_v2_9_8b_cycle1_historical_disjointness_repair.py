"""V2-9.8B Cycle-1 historical-disjointness repair regression.

Exercises the real production freeze-gate path:

AuthoritativeLiveOperationalCampaignOwner.run
-> run_operational
-> production pre-lifecycle path
-> freeze_eligible_reserve_for_campaign

Reproduces real persistence-before-freeze ordering: Cycle 1 row exists before
freeze. Enforcement must follow current cycle_ordinal, never COUNT(*).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from unittest.mock import patch

import pytest

from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.permanent_discovery_availability import (
    freeze_eligible_reserve_for_campaign,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LiveOperationalError,
    PILOT_INPUT_READINESS,
    _resolve_current_cycle_ordinal_for_historical_disjointness,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCoordinatorError,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_8b_remaining_runtime_blocker_repair import (
    EXPIRES,
    GOV,
    SCH,
    _CampaignBase,
    _clean_goplus_extreme,
    _force_holder_extreme_ineligible,
    _permanent_supply,
    _seed_exact_markets_for_supply,
)


NOW = "2026-08-26T19:03:49+00:00"
GKUNJ_MINT = "GkUnjBvGx9sXf5jEpXWSucgNoT8G1xUo2Dq9vryApump"
GKUNJ_POOL = "D1n2af8QrDpMY1VCgNPEBUXP83uhJZoqq4b7CURbLNvz"
HQKH_MINT = "HQKhWkrPtdLyRxWGVZAajfxoja2y8FMJeckKqZEFpump"
HQKH_POOL = "E2JdpLaxZhKCUG9DJJqj2EWmuz3acJpKJNZMPKCEa6Mq"
FRESH_A_MINT = "FreshMintAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_A_POOL = "FreshPoolAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_B_MINT = "FreshMintBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_B_POOL = "FreshPoolBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_C_MINT = "FreshMintCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_C_POOL = "FreshPoolCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_D_MINT = "FreshMintDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_D_POOL = "FreshPoolDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
GRADUATED = "PUMPSWAP_GRADUATED_CONFIRMED"


def _assert_cycle1_persisted_before_freeze(db_path: str, *, cycle_id: str = "cyc") -> None:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """SELECT cycle_ordinal
               FROM printer_memory_factory_campaign_cycles
               WHERE campaign_id=? AND run_id=? AND cycle_id=?""",
            ("camp", "run", cycle_id),
        ).fetchone()
        assert row is not None
        assert type(row[0]) is int
        assert row[0] == 1
        count = int(
            conn.execute(
                """SELECT COUNT(*)
                   FROM printer_memory_factory_campaign_cycles
                   WHERE campaign_id=? AND run_id=?""",
                ("camp", "run"),
            ).fetchone()[0]
        )
        # Real production ordering: Cycle-1 row already exists (COUNT >= 1)
        # before freeze. The repaired gate must ignore this COUNT proxy.
        assert count >= 1
    finally:
        conn.close()


def _insert_token_pair(conn: sqlite3.Connection, *, row_id: int, mint: str, pool: str) -> None:
    conn.execute(
        "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
        (row_id, mint),
    )
    conn.execute(
        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
        "VALUES (?,?,?,?)",
        (100 + row_id, row_id, pool, mint),
    )


def _seed_cycle1_admitted_slots(db_path: str) -> None:
    """Attach Cycle-1 admitted slots onto the already-persisted Cycle-1 row."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        _insert_token_pair(conn, row_id=90, mint=HQKH_MINT, pool=HQKH_POOL)
        _insert_token_pair(conn, row_id=91, mint=GKUNJ_MINT, pool=GKUNJ_POOL)
        for ordinal, row_id, mint, pool in (
            (1, 90, HQKH_MINT, HQKH_POOL),
            (2, 91, GKUNJ_MINT, GKUNJ_POOL),
        ):
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_token_slots(
                    token_slot_id,campaign_id,run_id,cycle_id,slot_ordinal,
                    token_identity,token_row_id,mint_identity,pair_identity,
                    pair_row_id,lifecycle_identity,tracking_queue_id,
                    replacement_predecessor_slot_id,token_state,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'SELECTED',?,?)""",
                (
                    f"t{ordinal}_c0001_slot",
                    "camp",
                    "run",
                    "cyc",
                    ordinal,
                    f"solana-mainnet:{mint}",
                    row_id,
                    mint,
                    pool,
                    100 + row_id,
                    GRADUATED,
                    None,
                    None,
                    NOW,
                    NOW,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _insert_cycle2_row(db_path: str, *, cycle_id: str = "cyc-2") -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        conn.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                created_at,updated_at
            ) VALUES (?,?,?,2,'PLANNED',?,?)""",
            (cycle_id, "camp", "run", NOW, NOW),
        )
        conn.commit()
    finally:
        conn.close()


def _supply_with_historical_reuse() -> GraduatedSupply:
    """Inventory that still contains Cycle-1 GkUnj plus four fresh identities."""
    proofs: dict[str, FixturePumpSwapProof] = {}
    origins: list[FixtureOriginProof] = []
    candidates: dict[str, dict[str, object]] = {}
    inventory = (
        (GKUNJ_MINT, GKUNJ_POOL),
        (FRESH_A_MINT, FRESH_A_POOL),
        (FRESH_B_MINT, FRESH_B_POOL),
        (FRESH_C_MINT, FRESH_C_POOL),
        (FRESH_D_MINT, FRESH_D_POOL),
    )
    epoch = int(datetime.fromisoformat(e8.NOW.replace("Z", "+00:00")).timestamp())
    for i, (mint, pool) in enumerate(inventory):
        proofs[mint] = FixturePumpSwapProof(mint=mint, pool_address=pool)
        origins.append(
            FixtureOriginProof(
                mint=mint,
                signature=f"sig{i}" + "1" * 80,
                slot=432_499_500 + i,
                block_time=epoch,
                bonding_curve=pool,
                confirmed=True,
            )
        )
        candidates[mint.lower()] = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "mint_identity": mint,
            "pair_identity": pool,
            "market_identity": f"solana-mainnet:pumpswap:{pool}",
            "provenance": "LATEST_GRADUATED" if i % 2 == 0 else "PERSISTED_GRADUATED",
            "admission_authority": "MARKET_PRESENT_POOL",
            "liquidity": {
                "liquidity_usd": 5000.0 + i * 100,
            },
            "liquidity_usd": 5000.0 + i * 100,
            "evidence_expires_at": EXPIRES,
            "memory_observation_eligible": True,
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
            "holder_condition": "HOLDER_CONCENTRATION_EXTREME",
        }
    return GraduatedSupply(
        ready=True,
        terminal="GRADUATED_SUPPLY_READY",
        graduated_supply=tuple(origins),
        graduation_proofs=proofs,
        candidate_a={"mint": origins[1].mint, "pair_address": FRESH_A_POOL},
        candidate_b={"mint": origins[2].mint, "pair_address": FRESH_B_POOL},
        two_candidate_selection={"ready": True},
        handoff_readiness={"atomic_two_slot_ready": True},
        discovery_report={},
        front_door_report={"generated_at": e8.NOW},
        diagnostics={
            "permanent_availability": True,
            "selection_floor_usd": 3000.0,
            "stage_local_source_requests": 0,
            "stage_operations_used": {},
        },
        holder_reserve_supply=tuple(origins),
        holder_reserve_candidates=candidates,
    )


def _supply_diagnostics(lifecycle: dict[str, object]) -> dict[str, object]:
    """Permanent mode publishes candidate_supply_diagnostics on pre-lifecycle returns."""
    return dict(
        lifecycle.get("candidate_supply_diagnostics")
        or lifecycle.get("graduated_supply_diagnostics")
        or {}
    )


def _run_production_pre_lifecycle(
    *,
    command,
    backup_path: str,
    supply: GraduatedSupply,
    cycle_id: str,
    selection_seed: str,
    observed_calls: list[dict[str, object]],
):
    owner = AuthoritativeLiveOperationalCampaignOwner()
    _force_holder_extreme_ineligible(owner, supply.holder_reserve_supply)
    real_freeze = freeze_eligible_reserve_for_campaign

    def _spy(connection, candidates, **kwargs):
        call = {
            "enforce": bool(
                kwargs.get("enforce_campaign_historical_disjointness")
            ),
            "campaign_id": kwargs.get("campaign_id"),
            "campaign_run_id": kwargs.get("campaign_run_id"),
            "candidate_mints": tuple(
                str(item.get("mint") or "") for item in candidates
            ),
            "selected_mints": (),
            "campaign_historical_exclusion_count": 0,
            "campaign_historical_exclusions": [],
        }
        # Record the enforcement decision before the freeze body may fail closed.
        observed_calls.append(call)
        result = real_freeze(connection, candidates, **kwargs)
        authority = dict(result.selection_authority or {})
        call["selected_mints"] = tuple(
            str(item.get("mint") or "")
            for item in (authority.get("selected") or ())
        )
        call["campaign_historical_exclusion_count"] = int(
            authority.get("campaign_historical_exclusion_count") or 0
        )
        call["campaign_historical_exclusions"] = list(
            authority.get("campaign_historical_exclusions") or ()
        )
        return result

    with patch(
        "printer_v1.discovery.permanent_discovery_availability."
        "freeze_eligible_reserve_for_campaign",
        side_effect=_spy,
    ):
        return owner.run(
            mode=PILOT_INPUT_READINESS,
            command=command,
            pump_transport=_FakePumpTransport([], {}),
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed=selection_seed,
            cycle_id=cycle_id,
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=backup_path,
            lifecycle_kwargs={
                "context_adapter_factories": _clean_goplus_extreme()
            },
            graduated_supply=supply,
        )


def test_case_a_real_cycle1_enforcement_off_with_empty_history() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        _assert_cycle1_persisted_before_freeze(base.db)
        supply = _permanent_supply(4)
        _seed_exact_markets_for_supply(
            base.db,
            supply,
            request_key_root="v2-9-8b-window15m-cycle1-hist-a",
            campaign_id=str(base.command.campaign_id),
            run_id=str(base.command.run_id),
            cycle_id="cyc",
        )
        observed: list[dict[str, object]] = []
        result = _run_production_pre_lifecycle(
            command=base.command,
            backup_path=base.backup,
            supply=supply,
            cycle_id="cyc",
            selection_seed="cycle1-hist-a",
            observed_calls=observed,
        )
        assert len(observed) == 1
        assert observed[0]["enforce"] is False
        life = result.lifecycle
        diag = _supply_diagnostics(life)
        freeze = diag.get("freeze_depth_enforcement") or {}
        assert freeze.get("selected_count") == 2
        assert len(observed[0]["selected_mints"]) == 2
        assert life["lifecycle_started"] is False
        # Empty prior admitted history is valid for Cycle 1.
        assert "INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE" not in str(
            life.get("stop_reason") or ""
        )
    finally:
        base.tearDown()


def test_case_b_real_cycle2_enforcement_on_filters_before_selection() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        _assert_cycle1_persisted_before_freeze(base.db)
        _seed_cycle1_admitted_slots(base.db)
        _insert_cycle2_row(base.db, cycle_id="cyc-2")
        supply = _supply_with_historical_reuse()
        _seed_exact_markets_for_supply(
            base.db,
            supply,
            request_key_root="v2-9-8b-window15m-cycle2-hist-b",
            campaign_id=str(base.command.campaign_id),
            run_id=str(base.command.run_id),
            cycle_id="cyc-2",
        )
        observed: list[dict[str, object]] = []
        result = _run_production_pre_lifecycle(
            command=base.command,
            backup_path=base.backup,
            supply=supply,
            cycle_id="cyc-2",
            selection_seed="cycle2-hist-b",
            observed_calls=observed,
        )
        assert len(observed) == 1
        assert observed[0]["enforce"] is True
        # Historical mint may remain visible in freeze input.
        assert GKUNJ_MINT in observed[0]["candidate_mints"]
        assert int(observed[0]["campaign_historical_exclusion_count"]) >= 1
        excluded_mints = {
            str(item.get("mint") or "")
            for item in observed[0]["campaign_historical_exclusions"]
        }
        assert GKUNJ_MINT in excluded_mints
        selected_mints = set(observed[0]["selected_mints"])
        assert GKUNJ_MINT not in selected_mints
        assert len(selected_mints) == 2
        life = result.lifecycle
        diag = _supply_diagnostics(life)
        freeze = diag.get("observation_reserve") or {}
        assert int(freeze.get("campaign_historical_exclusion_count") or 0) >= 1
        # Keep historical mint visible in the original supply input.
        assert GKUNJ_MINT.lower() in supply.holder_reserve_candidates
        assert life["lifecycle_started"] is False
    finally:
        base.tearDown()


def test_case_c_cycle2_missing_history_still_fails_closed() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        _assert_cycle1_persisted_before_freeze(base.db)
        _insert_cycle2_row(base.db, cycle_id="cyc-2")
        # No admitted Cycle-1 slots -> structurally empty history.
        supply = _permanent_supply(4)
        _seed_exact_markets_for_supply(base.db, supply)
        observed: list[dict[str, object]] = []
        with pytest.raises(
            MultiCycleCoordinatorError,
            match="INTERNAL_CAMPAIGN_HISTORICAL_IDENTITY_UNAVAILABLE",
        ):
            _run_production_pre_lifecycle(
                command=base.command,
                backup_path=base.backup,
                supply=supply,
                cycle_id="cyc-2",
                selection_seed="cycle2-hist-c",
                observed_calls=observed,
            )
        # Enforcement remained TRUE; fail closed happened inside freeze.
        assert len(observed) == 1
        assert observed[0]["enforce"] is True
    finally:
        base.tearDown()


def test_case_d_invalid_current_cycle_fails_closed_before_freeze() -> None:
    base = _CampaignBase()
    base.setUp()
    try:
        _assert_cycle1_persisted_before_freeze(base.db)
        supply = _permanent_supply(4)
        _seed_exact_markets_for_supply(base.db, supply)
        observed: list[dict[str, object]] = []
        with pytest.raises(LiveOperationalError) as exc_info:
            _run_production_pre_lifecycle(
                command=base.command,
                backup_path=base.backup,
                supply=supply,
                cycle_id="missing-cycle-identity",
                selection_seed="cycle-invalid-d",
                observed_calls=observed,
            )
        assert exc_info.value.code == "CURRENT_CYCLE_IDENTITY_INVALID"
        # Must not fall back to Cycle-1 semantics or reach freeze.
        assert observed == []
    finally:
        base.tearDown()


def test_case_d_invalid_cycle_ordinal_values_fail_closed() -> None:
    """Schema CHECK blocks ordinal < 1; helper still fails closed on bad payloads."""

    class _Row:
        def __init__(self, value):
            self._value = value

        def __getitem__(self, index):
            assert index == 0
            return self._value

    class _Connection:
        def __init__(self, value):
            self._value = value

        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return _Row(self._value)

    for bad in (0, -1, "1", 1.5, None, True):
        with pytest.raises(LiveOperationalError) as exc_info:
            _resolve_current_cycle_ordinal_for_historical_disjointness(
                _Connection(bad),
                campaign_id="camp",
                campaign_run_id="run",
                cycle_id="cyc",
            )
        assert exc_info.value.code == "CURRENT_CYCLE_IDENTITY_INVALID"
