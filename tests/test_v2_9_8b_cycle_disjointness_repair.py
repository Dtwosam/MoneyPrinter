"""V2-9.8B Cycle-1/Cycle-2 campaign historical disjointness repair tests.

Proves later-cycle fresh selection filters campaign/run historical admitted-slot
identities before the existing seeded freeze/selector runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    MINIMUM_FREEZE_DEPTH,
    freeze_eligible_reserve,
)
from printer_v1.discovery.selection_authority import (
    candidate_from_front_door_mapping,
    select_two_candidates,
)
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import (
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
    MultiCycleCoordinatorError,
    admit_two_token_cycle,
    filter_candidates_by_campaign_historical_disjointness,
    load_campaign_historical_slot_identity_sets,
    multi_cycle_configuration_contract,
)


START = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
NOW = "2026-08-26T13:00:00+00:00"
EXPIRY = "2026-08-26T14:00:00+00:00"
GRADUATED = "PUMPSWAP_GRADUATED_CONFIRMED"
POLICY = build_four_token_proof_policy()
BINDING = MultiCycleCampaignBinding(
    campaign_id="campaign-1",
    campaign_run_id="campaign-run-1",
    configuration_id="configuration-1",
    authoritative_factory_run_id="factory-1",
)

# Aug-26 regression shape: Cycle-1 mint that parent freeze/select could re-pick.
GKUNJ_MINT = "GkUnjBvGx9sXf5jEpXWSucgNoT8G1xUo2Dq9vryApump"
GKUNJ_POOL = "D1n2af8QrDpMY1VCgNPEBUXP83uhJZoqq4b7CURbLNvz"
CSVBN_MINT = "CsVBNQijeDY28yG4GLkeGE5p3Nic1BPv5M4mX6wTpump"
CSVBN_POOL = "88wJf9FYZ1CZgZg7KE3GFbQe2wGUacjmK14CGBsdC2Ww"
HQKH_MINT = "HQKhWkrPtdLyRxWGVZAajfxoja2y8FMJeckKqZEFpump"
HQKH_POOL = "E2JdpLaxZhKCUG9DJJqj2EWmuz3acJpKJNZMPKCEa6Mq"
FRESH_B_MINT = "FreshMintBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_B_POOL = "FreshPoolBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_C_MINT = "FreshMintCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_C_POOL = "FreshPoolCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_D_MINT = "FreshMintDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_D_POOL = "FreshPoolDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_E_MINT = "FreshMintExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
FRESH_E_POOL = "FreshPoolExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Deterministic parent defect seed: without the gate, GkUnj enters the pair.
PARENT_DEFECT_SEED = "seed-1"


def _slot(row_id: int, ordinal: int, cycle_ordinal: int, *, mint: str, pool: str) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c{cycle_ordinal:04d}_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:{mint}",
        "token_row_id": row_id,
        "mint_identity": mint,
        "pair_identity": pool,
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": GRADUATED,
        "tracking_queue_id": None,
        "replacement_predecessor_slot_id": None,
    }


def _moe(
    mint: str,
    pool: str,
    *,
    token_row_id: int | None = None,
    pair_row_id: int | None = None,
    token_identity: str | None = None,
    mint_identity: str | None = None,
    pair_identity: str | None = None,
) -> dict[str, object]:
    item: dict[str, object] = {
        "mint": mint,
        "pool": pool,
        "market_identity": f"solana-mainnet:eligible:{pool}",
        "provenance": "PERSISTED_GRADUATED",
        "memory_observation_eligible": True,
        "evidence_expires_at": EXPIRY,
        "tracking_handoff_eligible": True,
    }
    if mint_identity is not None:
        item["mint_identity"] = mint_identity
    if pair_identity is not None:
        item["pair_identity"] = pair_identity
    if token_row_id is not None:
        item["token_row_id"] = token_row_id
    if pair_row_id is not None:
        item["pair_row_id"] = pair_row_id
    if token_identity is not None:
        item["token_identity"] = token_identity
    return item


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "cycle-disjointness.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    configuration = {
        "token_capacity": 2,
        "ceilings": {"cycle_count": POLICY.total_cycle_admission_ceiling},
        "multi_cycle_capacity": multi_cycle_configuration_contract(
            POLICY, intake_started_at=START
        ),
    }
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        (
            "configuration-1",
            "campaign-1",
            "a" * 64,
            json.dumps(configuration, sort_keys=True),
            "{}",
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            START.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            START.isoformat(),
            START.isoformat(),
        ),
    )
    # Cycle-1 historical identities: HQKh + GkUnj (Aug-26 shape).
    tokens = (
        (90, HQKH_MINT, HQKH_POOL),
        (91, GKUNJ_MINT, GKUNJ_POOL),
        (92, CSVBN_MINT, CSVBN_POOL),
        (93, FRESH_B_MINT, FRESH_B_POOL),
        (94, FRESH_C_MINT, FRESH_C_POOL),
        (95, FRESH_D_MINT, FRESH_D_POOL),
        (96, FRESH_E_MINT, FRESH_E_POOL),
    )
    for row_id, mint, pool in tokens:
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, mint),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, pool, mint),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id=BINDING.campaign_id,
        run_id=BINDING.campaign_run_id,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(
            _slot(90, 1, 1, mint=HQKH_MINT, pool=HQKH_POOL),
            _slot(91, 2, 1, mint=GKUNJ_MINT, pool=GKUNJ_POOL),
        ),
        now=START.isoformat(),
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def _assert_db_ok(connection: sqlite3.Connection) -> None:
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_parent_characterization_without_gate_seed1_can_select_gkUnj() -> None:
    """Meaningful parent RED shape: old freeze/select can place GkUnj in the pair."""
    inventory = [
        _moe(GKUNJ_MINT, GKUNJ_POOL),
        _moe(CSVBN_MINT, CSVBN_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
        _moe(FRESH_D_MINT, FRESH_D_POOL),
        _moe(FRESH_E_MINT, FRESH_E_POOL),
    ]
    frozen = freeze_eligible_reserve(
        inventory, cycle_seed=PARENT_DEFECT_SEED, at=NOW
    )
    selected = {str(item["mint"]) for item in frozen.selected}
    assert GKUNJ_MINT in selected


def test_aug26_gkUnj_excluded_before_later_cycle_freeze_selection(connection) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    inventory = [
        _moe(GKUNJ_MINT, GKUNJ_POOL),
        _moe(CSVBN_MINT, CSVBN_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
        _moe(FRESH_D_MINT, FRESH_D_POOL),
        _moe(FRESH_E_MINT, FRESH_E_POOL),
    ]
    frozen = freeze_eligible_reserve(
        inventory,
        cycle_seed=PARENT_DEFECT_SEED,
        at=NOW,
        campaign_historical_identity_sets=historical,
        require_campaign_historical_identity_sets=True,
    )
    selected = {str(item["mint"]) for item in frozen.selected}
    assert GKUNJ_MINT not in selected
    assert len(frozen.selected) == 2
    assert frozen.selection_authority["campaign_historical_exclusion_count"] >= 1
    excluded_mints = {
        str(item.get("mint") or "")
        for item in frozen.selection_authority["campaign_historical_exclusions"]
    }
    assert GKUNJ_MINT in excluded_mints
    # Full inventory remains available for diagnostic evidence construction.
    assert any(str(item["mint"]) == GKUNJ_MINT for item in inventory)
    _assert_db_ok(connection)


@pytest.mark.parametrize(
    ("field", "colliding"),
    [
        (
            "mint_identity",
            _moe(GKUNJ_MINT, "UnrelatedPoolxxxxxxxxxxxxxxxxxxxxxxxxxx", mint_identity=GKUNJ_MINT),
        ),
        (
            "pair_identity",
            _moe(
                "UnrelatedMintxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "UnrelatedPoolForPairFieldxxxxxxxxxxxxxxx",
                pair_identity=GKUNJ_POOL,
            ),
        ),
        (
            "token_row_id",
            _moe(FRESH_B_MINT, FRESH_B_POOL, token_row_id=91),
        ),
        (
            "pair_row_id",
            _moe(FRESH_C_MINT, FRESH_C_POOL, pair_row_id=191),
        ),
        (
            "token_identity",
            _moe(
                FRESH_D_MINT,
                FRESH_D_POOL,
                token_identity=f"solana-mainnet:{GKUNJ_MINT}",
            ),
        ),
    ],
)
def test_each_historical_identity_field_blocks_later_cycle_selection(
    connection, field, colliding
) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    colliding_mint = str(colliding["mint"])
    fresh_pool = [
        colliding,
        _moe(CSVBN_MINT, CSVBN_POOL),
        _moe(FRESH_E_MINT, FRESH_E_POOL),
        _moe("ExtraFreshMint1xxxxxxxxxxxxxxxxxxxxxxxxx", "ExtraFreshPool1xxxxxxxxxxxxxxxxxxxxxxxxx"),
        _moe("ExtraFreshMint2xxxxxxxxxxxxxxxxxxxxxxxxx", "ExtraFreshPool2xxxxxxxxxxxxxxxxxxxxxxxxx"),
        _moe("ExtraFreshMint3xxxxxxxxxxxxxxxxxxxxxxxxx", "ExtraFreshPool3xxxxxxxxxxxxxxxxxxxxxxxxx"),
    ]
    fresh, excluded = filter_candidates_by_campaign_historical_disjointness(
        fresh_pool, historical=historical
    )
    assert any(
        item.get("campaign_historical_disjointness_field") == field for item in excluded
    )
    assert colliding_mint not in {str(item["mint"]) for item in fresh}
    selected = select_two_candidates(
        [candidate_from_front_door_mapping(item) for item in fresh],
        cycle_seed=PARENT_DEFECT_SEED,
    )
    assert colliding_mint not in {item.mint for item in selected.selected}
    _assert_db_ok(connection)


def test_all_fresh_identities_remain_eligible(connection) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    candidate = _moe(
        CSVBN_MINT,
        CSVBN_POOL,
        mint_identity=CSVBN_MINT,
        pair_identity=CSVBN_POOL,
        token_row_id=92,
        pair_row_id=192,
        token_identity=f"solana-mainnet:{CSVBN_MINT}",
    )
    fresh, excluded = filter_candidates_by_campaign_historical_disjointness(
        [candidate], historical=historical
    )
    assert excluded == ()
    assert len(fresh) == 1
    assert fresh[0]["mint"] == CSVBN_MINT


def test_selection_operates_over_fresh_only_never_historical_a(connection) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    inventory = [
        _moe(GKUNJ_MINT, GKUNJ_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
    ]
    fresh, excluded = filter_candidates_by_campaign_historical_disjointness(
        inventory, historical=historical
    )
    assert {item["mint"] for item in excluded} == {GKUNJ_MINT}
    assert {item["mint"] for item in fresh} == {FRESH_B_MINT, FRESH_C_MINT}
    selected = select_two_candidates(
        [candidate_from_front_door_mapping(item) for item in fresh],
        cycle_seed=PARENT_DEFECT_SEED,
    )
    assert selected.ready is True
    assert {item.mint for item in selected.selected} == {FRESH_B_MINT, FRESH_C_MINT}


def test_enough_fresh_alternates_do_not_false_insufficient(connection) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    inventory = [
        _moe(GKUNJ_MINT, GKUNJ_POOL),
        _moe(HQKH_MINT, HQKH_POOL),
        _moe(CSVBN_MINT, CSVBN_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
        _moe(FRESH_D_MINT, FRESH_D_POOL),
        _moe(FRESH_E_MINT, FRESH_E_POOL),
    ]
    frozen = freeze_eligible_reserve(
        inventory,
        cycle_seed=PARENT_DEFECT_SEED,
        at=NOW,
        campaign_historical_identity_sets=historical,
    )
    assert frozen.selection_authority.get("coverage_blocker") is False
    assert len(frozen.selected) == 2
    assert GKUNJ_MINT not in {item["mint"] for item in frozen.selected}
    assert HQKH_MINT not in {item["mint"] for item in frozen.selected}


def test_insufficient_fresh_after_exclusion_uses_existing_blocker_no_fallback(
    connection,
) -> None:
    historical = load_campaign_historical_slot_identity_sets(
        connection,
        campaign_id=BINDING.campaign_id,
        campaign_run_id=BINDING.campaign_run_id,
    )
    inventory = [
        _moe(GKUNJ_MINT, GKUNJ_POOL),
        _moe(HQKH_MINT, HQKH_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
    ]
    frozen = freeze_eligible_reserve(
        inventory,
        cycle_seed=PARENT_DEFECT_SEED,
        at=NOW,
        campaign_historical_identity_sets=historical,
    )
    assert frozen.selected == ()
    assert frozen.selection_authority.get("coverage_blocker") is True
    assert frozen.selection_authority.get("reason") == "INSUFFICIENT_OBSERVATION_COVERAGE"
    assert frozen.selection_authority["valid_fresh_unique_observation_depth"] < MINIMUM_FREEZE_DEPTH
    # No historical fallback into the selected pair.
    assert GKUNJ_MINT not in {item.get("mint") for item in frozen.selected}


def test_first_cycle_empty_history_behavior_unchanged() -> None:
    empty_history = {
        "token_slot_id": set(),
        "token_identity": set(),
        "token_row_id": set(),
        "mint_identity": set(),
        "pair_identity": set(),
        "pair_row_id": set(),
    }
    inventory = [
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
        _moe(FRESH_D_MINT, FRESH_D_POOL),
        _moe(FRESH_E_MINT, FRESH_E_POOL),
    ]
    without = freeze_eligible_reserve(inventory, cycle_seed="same-seed", at=NOW)
    with_empty = freeze_eligible_reserve(
        inventory,
        cycle_seed="same-seed",
        at=NOW,
        campaign_historical_identity_sets=empty_history,
    )
    assert [item["mint"] for item in without.selected] == [
        item["mint"] for item in with_empty.selected
    ]
    assert with_empty.selection_authority["campaign_historical_exclusion_count"] == 0


def test_admission_time_historical_identity_rejection_remains(connection) -> None:
    slots = [
        dict(_slot(92, 1, 2, mint=CSVBN_MINT, pool=CSVBN_POOL)),
        dict(_slot(93, 2, 2, mint=FRESH_B_MINT, pool=FRESH_B_POOL)),
    ]
    slots[0]["mint_identity"] = GKUNJ_MINT
    with pytest.raises(MultiCycleCoordinatorError, match="historical identity reuse"):
        admit_two_token_cycle(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=START + timedelta(minutes=5),
            slots=tuple(slots),
        )
    _assert_db_ok(connection)


def test_seeded_selection_unchanged_when_exclusions_empty() -> None:
    empty_history = {
        "token_slot_id": set(),
        "token_identity": set(),
        "token_row_id": set(),
        "mint_identity": set(),
        "pair_identity": set(),
        "pair_row_id": set(),
    }
    inventory = [
        _moe(CSVBN_MINT, CSVBN_POOL),
        _moe(FRESH_B_MINT, FRESH_B_POOL),
        _moe(FRESH_C_MINT, FRESH_C_POOL),
        _moe(FRESH_D_MINT, FRESH_D_POOL),
    ]
    baseline = select_two_candidates(
        [candidate_from_front_door_mapping(item) for item in inventory],
        cycle_seed="deterministic-empty",
    )
    filtered, excluded = filter_candidates_by_campaign_historical_disjointness(
        inventory, historical=empty_history
    )
    assert excluded == ()
    after = select_two_candidates(
        [candidate_from_front_door_mapping(item) for item in filtered],
        cycle_seed="deterministic-empty",
    )
    assert [item.mint for item in baseline.selected] == [item.mint for item in after.selected]


def test_require_history_fails_closed_when_sets_missing() -> None:
    inventory = [_moe(FRESH_B_MINT, FRESH_B_POOL), _moe(FRESH_C_MINT, FRESH_C_POOL)]
    with pytest.raises(MultiCycleCoordinatorError, match="historical identity sets"):
        freeze_eligible_reserve(
            inventory,
            cycle_seed="seed",
            at=NOW,
            require_campaign_historical_identity_sets=True,
        )


def test_later_cycle_supply_enforces_campaign_historical_disjointness_flag() -> None:
    import inspect

    from printer_v1.operator_cli import later_cycle_graduated_supply as module

    source = inspect.getsource(module.build_later_cycle_graduated_supply)
    assert "enforce_campaign_historical_disjointness=True" in source


def test_build_graduated_supply_accepts_enforce_flag() -> None:
    import inspect

    from printer_v1.operator_cli._graduated_supply_front_door_base import (
        build_graduated_supply,
    )

    signature = inspect.signature(build_graduated_supply)
    assert "enforce_campaign_historical_disjointness" in signature.parameters
