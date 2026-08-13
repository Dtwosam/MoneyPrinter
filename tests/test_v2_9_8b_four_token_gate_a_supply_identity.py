from __future__ import annotations

import inspect
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import CombinedPumpfunCampaignExecutor
from printer_v1.discovery.token_pair_identity import (
    TokenPairIdentityError,
    ensure_neutral_token_pair_identity,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
from printer_v1.operator_cli.later_cycle_graduated_supply import (
    build_later_cycle_graduated_supply,
)


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "printer_tracking_queue",
        "printer_scheduler_jobs",
        "printer_memory_factory_campaign_cycles",
        "printer_memory_factory_campaign_windows",
        "printer_memory_windows",
    )
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def test_identity_projection_is_neutral_and_combined_handoff_reuses_it(tmp_path) -> None:
    path = tmp_path / "gate-a.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    before = _counts(connection)

    projected = ensure_neutral_token_pair_identity(
        connection,
        mint_identity="mint-c",
        pair_identity="pool-c",
    )
    connection.commit()

    assert projected.mint_identity == "mint-c"
    assert projected.pair_identity == "pool-c"
    assert connection.execute(
        "SELECT token_status FROM printer_tokens WHERE id=?", (projected.token_row_id,)
    ).fetchone()[0] is None
    assert tuple(connection.execute(
        "SELECT token_id,base_token_mint FROM printer_pairs WHERE id=?",
        (projected.pair_row_id,),
    ).fetchone()) == (projected.token_row_id, "mint-c")
    assert _counts(connection) == before
    assert "ensure_neutral_token_pair_identity" in inspect.getsource(
        CombinedPumpfunCampaignExecutor._handoff_one_slot
    )
    connection.close()


def test_identity_projection_fails_closed_on_pair_owner_mismatch(tmp_path) -> None:
    path = tmp_path / "gate-a-mismatch.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO printer_tokens(token_mint) VALUES ('mint-existing')")
    token_id = int(connection.execute(
        "SELECT id FROM printer_tokens WHERE token_mint='mint-existing'"
    ).fetchone()[0])
    connection.execute(
        "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
        (token_id, "pool-shared", "mint-existing"),
    )
    connection.commit()

    with pytest.raises(TokenPairIdentityError, match="PAIR_TOKEN_IDENTITY_MISMATCH"):
        ensure_neutral_token_pair_identity(
            connection,
            mint_identity="mint-other",
            pair_identity="pool-shared",
        )
    connection.close()


def test_later_cycle_adapter_uses_permanent_supply_scope_and_exact_lineage(tmp_path) -> None:
    path = tmp_path / "gate-a-supply.sqlite3"
    apply_migrations(path)
    observed: dict[str, object] = {}

    def canonical_builder(db_path, **kwargs):
        observed.update(kwargs)
        root = kwargs["campaign_source_request_scope"].request_key_root
        connection = sqlite3.connect(db_path)
        request_id = int(connection.execute(
            "INSERT INTO printer_source_requests("
            "source_name,request_kind,requested_at,request_key,source_status,data_quality_label) "
            "VALUES ('dexscreener','pair_market_snapshot',?,?, 'COMPLETE','CLEAN_DATA')",
            ("2026-08-13T12:05:00+00:00", f"{root}-market-1"),
        ).lastrowid)
        connection.execute(
            "INSERT INTO printer_source_responses("
            "source_request_id,source_name,received_at,source_status,data_quality_label) "
            "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
            (request_id, "2026-08-13T12:05:00+00:00"),
        )
        connection.commit()
        connection.close()
        candidates = tuple(
            SimpleNamespace(
                mint=f"mint-{ordinal}",
                pool_address=f"pool-{ordinal}",
                market_identity=f"solana-mainnet:pumpswap:pool-{ordinal}",
                temporal_context=SimpleNamespace(
                    admission_observed_at_utc="2026-08-13T12:05:00+00:00"
                ),
            )
            for ordinal in (3, 4)
        )
        mappings = {
            item.mint: {
                "mint": item.mint,
                "pool": item.pool_address,
                "market_identity": item.market_identity,
                "provenance": "LATEST_GRADUATED" if item.mint == "mint-3" else "PERSISTED_GRADUATED",
                "holder_evidence_eligible": True,
            }
            for item in candidates
        }
        return GraduatedSupply(
            ready=True,
            terminal="CANDIDATE_SUPPLY_READY",
            graduated_supply=candidates,
            graduation_proofs={},
            candidate_a=mappings["mint-3"],
            candidate_b=mappings["mint-4"],
            two_candidate_selection={"selected": list(mappings.values())},
            handoff_readiness={},
            discovery_report={},
            front_door_report={},
            holder_reserve_supply=candidates,
            holder_reserve_candidates={key.lower(): value for key, value in mappings.items()},
            diagnostics={"permanent_availability": True},
        )

    with patch(
        "printer_v1.operator_cli.later_cycle_graduated_supply.build_graduated_supply",
        side_effect=canonical_builder,
    ):
        result = build_later_cycle_graduated_supply(
            path,
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            authoritative_factory_run_id="factory-1",
            proposed_cycle_id="cycle-2",
            proposed_cycle_ordinal=2,
            evaluated_at=datetime(2026, 8, 13, 12, 5, tzinfo=timezone.utc),
            selection_seed="factory-1-cycle-2",
            migration_transport=object(),
            graduated_supply_kwargs={},
        )

    assert observed["permanent_availability"] is True
    assert observed["tracking_precheck"] is True
    assert observed["required_token_capacity"] == 2
    scope = observed["campaign_source_request_scope"]
    assert scope.cycle_id == "cycle-2"
    assert scope.run_id == "campaign-run-1"
    assert scope.execution_id == "factory-1-cycle-2"
    assert len(result.candidates) == 2
    assert len(result.source_evidence) == 1
    assert result.source_evidence[0].source_response_id is not None
    connection = sqlite3.connect(path)
    assert connection.execute(
        "SELECT group_concat(COALESCE(token_status,'NULL'),',') FROM printer_tokens ORDER BY id"
    ).fetchone()[0] == "NULL,NULL"
    assert _counts(connection) == {
        "printer_tracking_queue": 0,
        "printer_scheduler_jobs": 0,
        "printer_memory_factory_campaign_cycles": 0,
        "printer_memory_factory_campaign_windows": 0,
        "printer_memory_windows": 0,
    }
    connection.close()
