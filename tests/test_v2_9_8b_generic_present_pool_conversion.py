from __future__ import annotations

import base64
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.memory_observation_activation import freeze_memory_activation_set
from printer_v1.discovery.permanent_discovery_availability import (
    CONTRACT_BLOCKED,
    MEMORY_OBSERVATION_ELIGIBLE,
    MINIMUM_FREEZE_DEPTH,
    StageBudget,
    load_protocol_confirmation_due,
    process_protocol_confirmation_queue,
    record_fresh_pool_nominations,
)
from printer_v1.discovery.later_cycle_fresh_inventory import (
    load_campaign_fresh_moe_candidates,
)
from printer_v1.sources.generic_present_pool_account_batch import (
    REQUEST_KIND,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    fixture_generic_present_pool_account_batch_transport,
)

NOW = "2026-09-09T12:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "generic-present-pool.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _mint_account(program: str) -> dict[str, object]:
    if program == TOKEN_PROGRAM_ID:
        raw = bytearray(82)
    else:
        raw = bytearray(166)
        raw[165] = 1
    raw[45] = 1
    return {
        "owner": program,
        "executable": False,
        "data": [base64.b64encode(bytes(raw)).decode(), "base64"],
    }


def _pool_account(owner: str) -> dict[str, object]:
    return {
        "owner": owner,
        "executable": False,
        "data": [base64.b64encode(b"pool").decode(), "base64"],
    }


def _program_account(*, executable: bool) -> dict[str, object]:
    return {
        "owner": "BPFLoaderUpgradeab1e11111111111111111111111",
        "executable": executable,
        "data": [base64.b64encode(b"program").decode(), "base64"],
    }


def _nominate(connection, *, count: int, campaign_id: str = "campaign") -> list[dict[str, str]]:
    observations = []
    for index in range(count):
        observations.append(
            {
                "mint": f"GenericMint{index}",
                "pool": f"GenericPool{index}",
                "base_mint": f"GenericMint{index}",
                "quote_mint": WSOL if index % 2 == 0 else USDC,
                "venue": "meteora-damm-v2" if index % 2 == 0 else "raydium",
                "liquidity_usd": 7_500.0,
            }
        )
    report = record_fresh_pool_nominations(
        connection,
        observations=observations,
        source="geckoterminal",
        request_id=99,
        now=NOW,
        campaign_id=campaign_id,
    )
    assert len(report["accepted"]) == count
    return observations


def _generic_transport(observations, *, executable: bool = True, token2022: bool = False):
    accounts = {}
    owner_programs = {}
    for index, item in enumerate(observations):
        program = TOKEN_2022_PROGRAM_ID if token2022 and index == 0 else TOKEN_PROGRAM_ID
        accounts[item["mint"]] = _mint_account(program)
        owner = f"GenericAmmProgram{index}"
        accounts[item["pool"]] = _pool_account(owner)
        owner_programs[owner] = _program_account(executable=executable)
    return fixture_generic_present_pool_account_batch_transport(
        accounts_by_address=accounts,
        owner_program_accounts=owner_programs,
    )


def test_non_pump_nomination_stays_protocol_due_not_unsupported(database):
    _path, connection = database
    observations = _nominate(connection, count=1)
    row = connection.execute(
        "SELECT current_state,current_reason,venue FROM printer_exact_market_states"
    ).fetchone()
    assert row["current_state"] == CONTRACT_BLOCKED
    assert row["current_reason"] == "ABOVE_FLOOR_NOMINATION_REQUIRES_PROTOCOL_CONFIRMATION"
    assert row["venue"] == observations[0]["venue"]
    assert load_protocol_confirmation_due(connection) == [
        {
            "mint": observations[0]["mint"],
            "pool": observations[0]["pool"],
            "venue": observations[0]["venue"],
        }
    ]


def test_generic_present_pool_promotes_exact_programs_and_two_measured_transports(database):
    _path, connection = database
    observations = _nominate(connection, count=2, campaign_id="cycle-1-campaign")
    budget = StageBudget.permanent_discovery_default()
    report = process_protocol_confirmation_queue(
        connection,
        stage_budget=budget,
        now=NOW,
        campaign_id="cycle-1-campaign",
        generic_account_batch_transport=_generic_transport(
            observations, token2022=True
        ),
    )
    assert report["source_requests"] == 1
    assert report["transport_operations"] == 2
    assert report["outcome_counts"]["GENERIC_POOL_CONFIRMED"] == 2
    request = connection.execute(
        "SELECT request_kind FROM printer_source_requests ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert request[0] == REQUEST_KIND
    rows = connection.execute(
        "SELECT mint_identity,token_program_id,pool_program_id,current_state "
        "FROM printer_exact_market_states ORDER BY mint_identity"
    ).fetchall()
    assert rows[0]["token_program_id"] == TOKEN_2022_PROGRAM_ID
    assert rows[1]["token_program_id"] == TOKEN_PROGRAM_ID
    assert all(str(row["pool_program_id"]).startswith("GenericAmmProgram") for row in rows)
    moe = connection.execute(
        "SELECT COUNT(*) FROM printer_discovery_reserve_layers "
        "WHERE reserve_layer=? AND reserve_state='ACTIVE'",
        (MEMORY_OBSERVATION_ELIGIBLE,),
    ).fetchone()[0]
    assert moe == 2


def test_non_executable_pool_owner_program_fails_closed(database):
    _path, connection = database
    observations = _nominate(connection, count=1)
    report = process_protocol_confirmation_queue(
        connection,
        stage_budget=StageBudget.permanent_discovery_default(),
        now=NOW,
        campaign_id="campaign",
        generic_account_batch_transport=_generic_transport(
            observations, executable=False
        ),
    )
    assert report["outcome_counts"]["POOL_OWNER_PROGRAM_NOT_EXECUTABLE"] == 1
    assert not report["promoted_observation_eligible"]
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_discovery_reserve_layers WHERE reserve_layer=?",
        (MEMORY_OBSERVATION_ELIGIBLE,),
    ).fetchone()[0] == 0


def test_four_generic_present_pools_reach_freeze_floor_and_rehydrate_for_cycle(database):
    _path, connection = database
    observations = _nominate(connection, count=4, campaign_id="two-cycle-campaign")
    report = process_protocol_confirmation_queue(
        connection,
        stage_budget=StageBudget.permanent_discovery_default(),
        now=NOW,
        campaign_id="two-cycle-campaign",
        generic_account_batch_transport=_generic_transport(observations),
    )
    assert len(report["promoted_observation_eligible"]) == MINIMUM_FREEZE_DEPTH
    carriers = load_campaign_fresh_moe_candidates(
        connection,
        campaign_id="two-cycle-campaign",
        at=NOW,
    )
    assert len(carriers) == MINIMUM_FREEZE_DEPTH
    assert {item["venue_label"] for item in carriers} == {
        "meteora-damm-v2",
        "raydium",
    }
    frozen = freeze_memory_activation_set(
        carriers,
        cycle_seed="cycle-1",
        at=NOW,
    )
    assert len(frozen.selected) == 2
    assert len(frozen.alternates) == 2
    assert all(item["admission_authority"] == "MARKET_PRESENT_POOL" for item in carriers)
