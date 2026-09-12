from __future__ import annotations

import json
import sqlite3

from printer_v1.discovery.later_cycle_fresh_inventory import (
    load_campaign_fresh_moe_candidates,
)


def test_cycle2_fresh_moe_rehydrates_market_observation_role_ids() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE printer_discovery_reserve_layers(
          network TEXT,mint_identity TEXT,pool_address TEXT,reserve_layer TEXT,
          reserve_state TEXT,observed_at TEXT,evidence_expires_at TEXT,
          source_provenance_json TEXT,evidence_json TEXT,last_campaign_id TEXT
        );
        CREATE TABLE printer_exact_market_states(
          network TEXT,mint_identity TEXT,pool_address TEXT,token_program_id TEXT,
          pool_program_id TEXT,base_mint TEXT,quote_mint TEXT,venue TEXT,
          current_state TEXT,last_observed_at TEXT
        );
        """
    )
    evidence = {
        "liquidity": {
            "liquidity_usd": 12_106.0,
            "liquidity_observed_at": "2026-09-12T12:53:55+00:00",
            "source_name": "geckoterminal",
            "source_request_id": 5988,
            "source_response_id": 5516,
            "source_failure_id": None,
            "source_status": "COMPLETE",
        },
        "memory_observation_eligible": True,
    }
    provenance = {
        "observations": [
            {
                "source": "geckoterminal",
                "request_id": 5988,
                "response_id": 5516,
                "stage": "protocol_confirmation_direct_promotion",
            }
        ]
    }
    connection.execute(
        "INSERT INTO printer_discovery_reserve_layers VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "solana-mainnet", "MINT", "POOL", "MEMORY_OBSERVATION_ELIGIBLE",
            "ACTIVE", "2026-09-12T12:53:55+00:00",
            "2026-09-12T13:23:55+00:00", json.dumps(provenance),
            json.dumps(evidence), "campaign-1",
        ),
    )
    connection.execute(
        "INSERT INTO printer_exact_market_states VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "solana-mainnet", "MINT", "POOL",
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            "GenericPoolProgram1111111111111111111111111",
            "MINT", "So11111111111111111111111111111111111111112",
            "generic", "CURRENT_VISIBLE",
            "2026-09-12T12:53:55+00:00",
        ),
    )

    rows = load_campaign_fresh_moe_candidates(
        connection,
        campaign_id="campaign-1",
        at="2026-09-12T12:58:14+00:00",
    )

    assert len(rows) == 1
    assert rows[0]["liquidity"] == evidence["liquidity"]
    assert rows[0]["liquidity"]["source_request_id"] == 5988
    assert rows[0]["liquidity"]["source_response_id"] == 5516
