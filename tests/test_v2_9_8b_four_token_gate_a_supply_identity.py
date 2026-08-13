from __future__ import annotations

import inspect
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import CombinedPumpfunCampaignExecutor
from printer_v1.discovery.token_pair_identity import (
    TokenPairIdentityError,
    ensure_neutral_token_pair_identity,
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
