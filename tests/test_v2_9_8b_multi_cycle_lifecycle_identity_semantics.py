from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_cycle_with_two_slots
from printer_v1.operator_cli.four_token_proof_integration import (
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleCampaignBinding,
    MultiCycleCoordinatorError,
    admit_two_token_cycle,
    load_multi_cycle_campaign_snapshot,
    multi_cycle_configuration_contract,
)


START = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
GRADUATED = "PUMPSWAP_GRADUATED_CONFIRMED"
POLICY = build_four_token_proof_policy()
BINDING = MultiCycleCampaignBinding(
    campaign_id="campaign-1",
    campaign_run_id="campaign-run-1",
    configuration_id="configuration-1",
    authoritative_factory_run_id="factory-1",
)
TRUE_IDENTITY_FIELDS = (
    "token_slot_id",
    "token_identity",
    "token_row_id",
    "mint_identity",
    "pair_identity",
    "pair_row_id",
)


def _slot(row_id: int, ordinal: int, cycle_ordinal: int) -> dict[str, object]:
    return {
        "token_slot_id": f"t{ordinal}_c{cycle_ordinal:04d}_slot",
        "slot_ordinal": ordinal,
        "token_identity": f"solana-mainnet:mint-{row_id}",
        "token_row_id": row_id,
        "mint_identity": f"mint-{row_id}",
        "pair_identity": f"pool-{row_id}",
        "pair_row_id": 100 + row_id,
        "lifecycle_identity": GRADUATED,
        "tracking_queue_id": None,
        "replacement_predecessor_slot_id": None,
    }


@pytest.fixture()
def connection(tmp_path):
    path = tmp_path / "lifecycle-semantics.sqlite3"
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
    for row_id in range(1, 5):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (row_id, f"mint-{row_id}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (100 + row_id, row_id, f"pool-{row_id}", f"mint-{row_id}"),
        )
    create_cycle_with_two_slots(
        connection,
        campaign_id=BINDING.campaign_id,
        run_id=BINDING.campaign_run_id,
        cycle_id="cycle-1",
        cycle_ordinal=1,
        slots=(_slot(1, 1, 1), _slot(2, 2, 1)),
        now=START.isoformat(),
    )
    connection.commit()
    try:
        yield connection
    finally:
        connection.close()


def test_snapshot_accepts_two_distinct_targets_with_shared_canonical_lifecycle(connection) -> None:
    snapshot = load_multi_cycle_campaign_snapshot(
        connection,
        binding=BINDING,
        policy=POLICY,
        now=START,
    )
    assert snapshot.cycle_ids == ("cycle-1",)
    assert snapshot.session.active_through_4h_tokens == 2
    assert [row[0] for row in connection.execute(
        "SELECT lifecycle_identity FROM printer_memory_factory_campaign_token_slots "
        "ORDER BY slot_ordinal"
    )] == [GRADUATED, GRADUATED]


@pytest.mark.parametrize("field", TRUE_IDENTITY_FIELDS)
def test_fresh_pair_still_rejects_duplicate_true_identity(connection, field) -> None:
    slots = [dict(_slot(3, 1, 2)), dict(_slot(4, 2, 2))]
    slots[1][field] = slots[0][field]
    with pytest.raises(
        MultiCycleCoordinatorError,
        match="candidate two-token slot identities must be distinct",
    ):
        admit_two_token_cycle(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=START + timedelta(minutes=5),
            slots=tuple(slots),
        )


@pytest.mark.parametrize("field", TRUE_IDENTITY_FIELDS)
def test_fresh_pair_still_rejects_historical_true_identity_reuse(connection, field) -> None:
    slots = [dict(_slot(3, 1, 2)), dict(_slot(4, 2, 2))]
    slots[0][field] = _slot(1, 1, 1)[field]
    with pytest.raises(MultiCycleCoordinatorError, match="historical identity reuse"):
        admit_two_token_cycle(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=START + timedelta(minutes=5),
            slots=tuple(slots),
        )


def test_lifecycle_identity_remains_required_and_validated(connection) -> None:
    slots = [dict(_slot(3, 1, 2)), dict(_slot(4, 2, 2))]
    slots[0]["lifecycle_identity"] = ""
    with pytest.raises(MultiCycleCoordinatorError, match="lifecycle"):
        admit_two_token_cycle(
            connection,
            binding=BINDING,
            policy=POLICY,
            now=START + timedelta(minutes=5),
            slots=tuple(slots),
        )
