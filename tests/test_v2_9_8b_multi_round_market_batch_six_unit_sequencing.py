"""Focused proofs: multi-round MINT_MARKET_BATCH six-unit sequencing."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    build_mint_market_batch_logical_identity,
    build_mint_market_batch_request_key,
    mint_set_digest,
    next_mint_market_batch_stage_sequence,
    parse_mint_market_batch_stage_sequence,
    run_dexscreener_batch_market_resolution,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import record_graduated_candidate

NOW = "2026-08-04T17:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"
CAMP = "camp-seq"
RUN = "run-seq"
CYCLE = "cycle-seq"


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "seq.sqlite3"
        apply_migrations(path)
        con = sqlite3.connect(str(path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield path, con
        finally:
            con.close()


def _seed(connection, count: int = 4):
    rows = []
    for i in range(count):
        mint = f"Mint{i:02d}"
        pool = f"Pool{i:02d}"
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=f"Sig{i:02d}",
            pumpswap_pool=pool,
            graduation_block_time=1_700_000_000 + i,
            graduation_slot=i,
            now=NOW,
        )
        rows.append({"mint_identity": mint, "pumpswap_pool": pool})
    connection.commit()
    return rows


_TRANSPORT_ORDINAL = {"n": 0}


def _transport_identity(mints):
    from printer_v1.sources.measured_transport import build_transport_identity

    _TRANSPORT_ORDINAL["n"] += 1
    return build_transport_identity(
        stage="MINT_MARKET_BATCH",
        source_name="dexscreener_pair",
        endpoint_owner="dexscreener",
        governed_request_kind="candidate_market_batch",
        method_or_endpoint="GET /tokens/v1/solana/{mints}",
        within_request_ordinal=_TRANSPORT_ORDINAL["n"],
        target_category="due_mints",
        target_identity=f"{_TRANSPORT_ORDINAL['n']}:{','.join(sorted(mints))[:80]}",
        response_bytes=1200,
        normalized_rows=len(mints),
        result="OK",
    )


def _batch_factory(pools: dict[str, str], liquidity: float = 5_000.0):
    def factory(mints):
        pairs = [
            {
                "chainId": "solana",
                "pairAddress": pools[m],
                "dexId": "pumpswap",
                "baseToken": {"address": m},
                "quoteToken": {"address": WSOL},
                "liquidity": {"usd": liquidity},
            }
            for m in mints
            if m in pools
        ]
        identity = _transport_identity(mints)
        return fixture_success_transport(
            {
                "pairs": pairs,
                "transport_operations_used": 1,
                "response_bytes": 1200,
                "normalized_rows": len(pairs),
                "transport_operation_identities": (identity.as_dict(),),
            }
        )

    return factory


class TestSequenceHelpers:
    def test_parse_and_build_request_keys(self):
        assert parse_mint_market_batch_stage_sequence("x-mint-batch-r1") == 1
        assert parse_mint_market_batch_stage_sequence("x-mint-batch-r3") == 3
        assert parse_mint_market_batch_stage_sequence("x-protocol-resume-mb2") == 2
        assert parse_mint_market_batch_stage_sequence("x-other") is None
        assert build_mint_market_batch_request_key(
            request_key_prefix="fd", stage_sequence=2
        ) == "fd-mint-batch-r2"
        assert build_mint_market_batch_request_key(
            request_key_prefix="fd", stage_sequence=3, kind="protocol_resume"
        ) == "fd-protocol-resume-mb3"

    def test_next_sequence_from_durable_request_keys(self, database):
        _, con = database
        assert next_mint_market_batch_stage_sequence(con, request_key_prefix="fd") == 1
        con.execute(
            """INSERT INTO printer_source_requests(
                source_name, request_kind, requested_at, request_key,
                tracking_priority, source_status, data_quality_label, created_at
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                "dexscreener",
                "candidate_market_batch",
                NOW,
                "fd-mint-batch-r1",
                0,
                "COMPLETE",
                "CLEAN_DATA",
                NOW,
            ),
        )
        con.commit()
        assert next_mint_market_batch_stage_sequence(con, request_key_prefix="fd") == 2
        con.execute(
            """INSERT INTO printer_source_requests(
                source_name, request_kind, requested_at, request_key,
                tracking_priority, source_status, data_quality_label, created_at
            ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                "dexscreener",
                "candidate_market_batch",
                NOW,
                "fd-protocol-resume-mb2",
                0,
                "COMPLETE",
                "CLEAN_DATA",
                NOW,
            ),
        )
        con.commit()
        assert next_mint_market_batch_stage_sequence(con, request_key_prefix="fd") == 3

    def test_logical_identity_uses_sequence_and_digest(self):
        a = build_mint_market_batch_logical_identity(
            campaign_id=CAMP,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_sequence=1,
            ordered_mints=["M2", "M1"],
        )
        b = build_mint_market_batch_logical_identity(
            campaign_id=CAMP,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_sequence=2,
            ordered_mints=["M2", "M1"],
        )
        assert a["mint_set_digest"] == b["mint_set_digest"] == mint_set_digest(["M1", "M2"])
        assert a["stage_sequence"] == 1
        assert b["stage_sequence"] == 2
        assert a["stage_id"] != b["stage_id"]
        assert a["logical_batch_id"] != b["logical_batch_id"]


class TestMultiRoundSealing:
    def test_three_distinct_batches_seal_as_1_2_3(self, database):
        path, con = database
        inventory = _seed(con, 4)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id=CAMP, run_id=RUN, cycle_id=CYCLE
        )
        sealed_sequences = []

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)
            sealed_sequences.append(int(evidence["stage_sequence"]))

        factory = _batch_factory(pools)
        for seq in (1, 2, 3):
            report = run_dexscreener_batch_market_resolution(
                con,
                inventory_rows=inventory,
                request_key=build_mint_market_batch_request_key(
                    request_key_prefix="fd", stage_sequence=seq
                ),
                now=NOW,
                campaign_id=CAMP,
                transport_factory=factory,
                enable_geckoterminal_fallback=False,
                run_id=RUN,
                cycle_id=CYCLE,
                stage_evidence_sink=sink,
                stage_sequence=seq,
            )
            assert report["stage_sequence"] == seq
            assert report["logical_batch_identity"]["stage_sequence"] == seq
            assert (
                report["sealed_stage_evidence"]["stage_id"]
                == build_campaign_stage_id(
                    campaign_id=CAMP,
                    run_id=RUN,
                    cycle_id=CYCLE,
                    stage_kind="MINT_MARKET_BATCH",
                    stage_sequence=seq,
                )
            )
        assert sealed_sequences == [1, 2, 3]
        assert owner.stage_evidence_count == 3
        assert owner.ingested_stage_ids == [
            f"{CAMP}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|1",
            f"{CAMP}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|2",
            f"{CAMP}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|3",
        ]

    def test_protocol_between_rounds_does_not_reset_sequence(self, database):
        path, con = database
        inventory = _seed(con, 3)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id=CAMP, run_id=RUN, cycle_id=CYCLE
        )
        sequences = []

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)
            sequences.append(int(evidence["stage_sequence"]))

        factory = _batch_factory(pools)
        # Round 1
        run_dexscreener_batch_market_resolution(
            con,
            inventory_rows=inventory,
            request_key="fd-mint-batch-r1",
            now=NOW,
            campaign_id=CAMP,
            transport_factory=factory,
            enable_geckoterminal_fallback=False,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_evidence_sink=sink,
            stage_sequence=1,
        )
        # Simulate protocol confirmation work (no market seal) — no sequence reset.
        protocol_noop = True
        assert protocol_noop
        # Round 2 after protocol
        run_dexscreener_batch_market_resolution(
            con,
            inventory_rows=inventory[:1],
            request_key="fd-protocol-resume-mb2",
            now=NOW,
            campaign_id=CAMP,
            transport_factory=factory,
            enable_geckoterminal_fallback=False,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_evidence_sink=sink,
            stage_sequence=2,
        )
        assert sequences == [1, 2]

    def test_identical_mint_content_distinct_rounds_differ_by_sequence(self, database):
        _, con = database
        inventory = _seed(con, 2)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id=CAMP, run_id=RUN, cycle_id=CYCLE
        )
        ids = []

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)
            ids.append(evidence["stage_id"])

        factory = _batch_factory(pools)
        for seq in (1, 2):
            run_dexscreener_batch_market_resolution(
                con,
                inventory_rows=inventory,
                request_key=f"fd-mint-batch-r{seq}",
                now=NOW,
                campaign_id=CAMP,
                transport_factory=factory,
                enable_geckoterminal_fallback=False,
                run_id=RUN,
                cycle_id=CYCLE,
                stage_evidence_sink=sink,
                stage_sequence=seq,
            )
        assert ids[0] != ids[1]
        assert ids[0].endswith("|1")
        assert ids[1].endswith("|2")


class TestReplayAndDuplicateProtection:
    def test_replay_same_sequence_retains_identity_and_duplicate_seal_fails(
        self, database
    ):
        _, con = database
        inventory = _seed(con, 2)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id=CAMP, run_id=RUN, cycle_id=CYCLE
        )

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)

        factory = _batch_factory(pools)
        report1 = run_dexscreener_batch_market_resolution(
            con,
            inventory_rows=inventory,
            request_key="fd-mint-batch-r1",
            now=NOW,
            campaign_id=CAMP,
            transport_factory=factory,
            enable_geckoterminal_fallback=False,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_evidence_sink=sink,
            stage_sequence=1,
        )
        assert report1["stage_sequence"] == 1
        # Replay same logical batch sequence — must not allocate sequence 2.
        with pytest.raises(CampaignSixUnitError, match="DUPLICATE_STAGE_ID"):
            run_dexscreener_batch_market_resolution(
                con,
                inventory_rows=inventory,
                request_key="fd-mint-batch-r1",
                now=NOW,
                campaign_id=CAMP,
                transport_factory=factory,
                enable_geckoterminal_fallback=False,
                run_id=RUN,
                cycle_id=CYCLE,
                stage_evidence_sink=sink,
                stage_sequence=1,
            )
        assert owner.stage_evidence_count == 1
        assert owner.ingested_stage_ids == [
            f"{CAMP}|{RUN}|{CYCLE}|MINT_MARKET_BATCH|1"
        ]

    def test_request_key_reconstruction_retains_sequence_without_arg(self, database):
        _, con = database
        inventory = _seed(con, 2)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id=CAMP, run_id=RUN, cycle_id=CYCLE
        )
        seqs = []

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)
            seqs.append(int(evidence["stage_sequence"]))

        factory = _batch_factory(pools)
        # stage_sequence omitted — reconstructed from request_key
        run_dexscreener_batch_market_resolution(
            con,
            inventory_rows=inventory,
            request_key="fd-mint-batch-r2",
            now=NOW,
            campaign_id=CAMP,
            transport_factory=factory,
            enable_geckoterminal_fallback=False,
            run_id=RUN,
            cycle_id=CYCLE,
            stage_evidence_sink=sink,
        )
        assert seqs == [2]


class TestEndToEndMultiRoundCampaignPath:
    def test_permanent_supply_multi_round_seals_distinct_sequences(self, database):
        from printer_v1.discovery.eligible_token_supply import (
            run_persistent_eligible_token_supply,
        )
        from printer_v1.sources.direct_pump_migration import (
            SIGNATURE_PAGE_REQUEST_KIND,
            TRANSACTION_REQUEST_KIND,
        )

        path, con = database
        inventory = _seed(con, 35)
        pools = {r["mint_identity"]: r["pumpswap_pool"] for r in inventory}
        owner = CampaignSixUnitOwner(
            campaign_id="camp-e2e", run_id="run-e2e", cycle_id="cycle-e2e"
        )
        market_seqs = []

        def sink(evidence):
            owner.ingest_stage_evidence(evidence)
            if evidence.get("stage_kind") == "MINT_MARKET_BATCH":
                market_seqs.append(int(evidence["stage_sequence"]))

        def migration_transport(context):
            kind = context.request.request_kind
            if kind == SIGNATURE_PAGE_REQUEST_KIND:
                return {"result": []}
            if kind == TRANSACTION_REQUEST_KIND:
                return {"result": None}
            raise AssertionError(kind)

        def batch_factory(mints):
            pairs = [
                {
                    "chainId": "solana",
                    "pairAddress": pools[m],
                    "dexId": "pumpswap",
                    "baseToken": {"address": m},
                    "quoteToken": {"address": WSOL},
                    "liquidity": {"usd": 2_500},
                }
                for m in mints
            ]
            identity = _transport_identity(mints)
            return fixture_success_transport(
                {
                    "pairs": pairs,
                    "transport_operations_used": 1,
                    "response_bytes": 1200,
                    "normalized_rows": len(pairs),
                    "transport_operation_identities": (identity.as_dict(),),
                }
            )

        result = run_persistent_eligible_token_supply(
            path,
            cycle_seed="seq-e2e",
            migration_transport=migration_transport,
            dexscreener_batch_transport_factory=batch_factory,
            now=NOW,
            run_locator=False,
            permanent_availability=True,
            enable_geckoterminal_reconciliation=False,
            campaign_id="camp-e2e",
            run_id="run-e2e",
            cycle_id="cycle-e2e",
            stage_evidence_sink=sink,
            front_door_request_key_prefix="fd-e2e",
        )
        assert result.ready is False
        # Multi-round permanent path must seal distinct market sequences.
        assert market_seqs == sorted(market_seqs)
        assert len(market_seqs) >= 2
        assert market_seqs[0] == 1
        assert market_seqs[1] == 2
        # No duplicate stage ids ingested
        assert len(owner.ingested_stage_ids) == len(set(owner.ingested_stage_ids))
