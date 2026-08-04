"""V2-9.8B holder partial accounting and snapshot readiness repair.

Offline fixture-only. Proves two shared-path repairs:

1. ``SNAPSHOT_READINESS`` inspects the complete ``HolderContextResult`` and
   fails closed on ``accounting_blocker`` (zero snapshot bundles, no ``READY``,
   typed ``BLOCKED_HOLDER_ACCOUNTING`` status, exposed holder evidence).
2. A governed holder request created before a later collection or persistence
   exception never disappears from holder IDs, coverage, or campaign
   reconciliation.

No providers, discovery runtime, Scheduler runtime, authorization,
``WINDOW_15M``, memory generation, retrieval, decisions, positions, trades,
audits, or PnL are run.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
from unittest.mock import MagicMock

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CURRENT_VISIBLE,
    ExactMarketObservation,
    NETWORK,
    collect_stage_reported_request_ids,
    collect_stage_source_request_coverage,
    record_exact_market_transition,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    PILOT_INPUT_READINESS,
)
from printer_v1.operator_cli.graduated_supply_front_door import GraduatedSupply
import printer_v1.operator_cli.holder_reliability_budget_control as budget
from printer_v1.operator_cli.holder_reliability_budget_control import (
    HolderBundlePersistPartialError,
    HolderContextResult,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    PrecloseContextPartialError,
    _collect_preclose_context,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_33_canonical_readiness_boundary as e33
import test_v2_9_7e_36_38_snapshot_maturity_boundary as e3638
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

NOW = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)
MINT_A = "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump"
MINT_B = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
MINT_C = "5tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK2pump"
MINT_D = "6FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDRpump"
_MINTS = [MINT_A, MINT_B, MINT_C, MINT_D]
_POOLS = [
    "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p",
    "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo",
    "CDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ22q",
    "AyuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fp",
]
EXPIRES = "2099-01-01T00:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"

FORBIDDEN_ACTIVITY_TABLES = (
    "printer_memory_windows",
    "printer_memory_factory_run_steps",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


# ---------------------------------------------------------------------------
# Shared offline fixtures
# ---------------------------------------------------------------------------


def _db(tmp_path: Path) -> sqlite3.Connection:
    path = tmp_path / "holder-partial.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign','RUNNING','OPERATIONAL_PERSISTENT','proof','v2-9-8b')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,created_at,updated_at) "
        "VALUES ('run','campaign',1,'RUNNING',?,?)",
        (NOW.isoformat(), NOW.isoformat()),
    )
    budget.persist_ledger(
        connection,
        run_id="run",
        cycle_id="cycle",
        ledger=budget.build_ledger(
            pump_operations=0, deadline_at=NOW + timedelta(minutes=30)
        ),
        now=NOW.isoformat(),
    )
    connection.commit()
    return connection


def _goplus_payload(
    mint: str,
    *,
    holders: list[dict[str, str]] | None,
    underlying_operation_count: int | None = 1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token_mint": mint,
        "mint_authority": None,
        "freeze_authority": None,
        "metadata_mutable": False,
        "total_supply": "1000000000",
        "lp_info": [{"locked": True}],
        "risk_flags": [],
    }
    if holders is not None:
        payload["top_10_holders"] = holders
    if underlying_operation_count is not None:
        payload["underlying_operation_count"] = underlying_operation_count
    return payload


def _goplus_execution(
    connection: sqlite3.Connection,
    *,
    mint: str,
    request_key: str,
    underlying_operation_count: int | None = 1,
) -> Any:
    adapter = build_fixture_source_adapter(
        "goplus",
        fixture_payload=_goplus_payload(
            mint,
            holders=[{"percent": "3"} for _ in range(10)],
            underlying_operation_count=underlying_operation_count,
        ),
    )
    request = build_governed_source_request(
        "goplus",
        "safety_reference",
        request_key=request_key,
        payload={"token_mint": mint},
    )
    return execute_source_request_with_governor(
        connection, request, adapter, recent_request_count=0
    )


def _healthy_goplus_factory(**_kwargs: Any):
    """GoPlus factory with a complete measured single-HTTP transport count."""

    def factory(**kwargs: Any):
        mint = kwargs.get("token_mint") or MINT_A
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload=_goplus_payload(
                mint, holders=[{"percent": "3"} for _ in range(10)]
            ),
        )

    return {"goplus": factory}


def _unmeasured_goplus_factory():
    """GoPlus factory whose payload carries NO measured transport evidence."""

    def factory(**kwargs: Any):
        mint = kwargs.get("token_mint") or MINT_A
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload=_goplus_payload(
                mint,
                holders=[{"percent": "3"} for _ in range(10)],
                underlying_operation_count=None,
            ),
        )

    return {"goplus": factory}


def _partial_holder_factories(
    *, raise_on_goplus: bool = False
) -> dict[str, Any]:
    """GoPlus succeeds (durable row) then the RPC holder stage raises.

    ``raise_on_goplus`` instead raises before any governed request exists.
    """

    def goplus(**kwargs: Any):
        if raise_on_goplus:
            raise RuntimeError("fixture goplus factory unavailable")
        mint = kwargs.get("token_mint") or MINT_A
        # UNKNOWN holder concentration opens the governed RPC holder path.
        return build_fixture_source_adapter(
            "goplus", fixture_payload=_goplus_payload(mint, holders=None)
        )

    def rpc_holder(**_kwargs: Any):
        raise RuntimeError("fixture rpc holder factory unavailable")

    return {"goplus": goplus, "solana_rpc_holder": rpc_holder}


def _extreme_goplus_factory():
    def factory(**kwargs: Any):
        mint = kwargs.get("token_mint") or MINT_A
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload=_goplus_payload(
                mint, holders=[{"percent": "25"} for _ in range(10)]
            ),
        )

    return {"goplus": factory}


def _rate_limited_goplus_factories():
    """Rate-limited GoPlus + failing RPC holder, both with measured counts."""
    from printer_v1.sources.goplus import build_goplus_adapter
    from printer_v1.sources.solana_rpc_holder import build_solana_rpc_holder_adapter

    def goplus(**_kwargs: Any):
        return build_goplus_adapter(
            enabled=True,
            fixture_transport=lambda _ctx: {
                "fixture_status": "rate_limited",
                "retry_after_seconds": 30,
                "underlying_operation_count": 1,
            },
        )

    def rpc_holder(**kwargs: Any):
        mint = kwargs.get("token_mint") or MINT_A
        return build_solana_rpc_holder_adapter(
            enabled=True,
            fixture_transport=lambda _ctx: {
                "fixture_status": "failure",
                "failure_type": "solana_rpc_http_client_error",
                "failure_message": "fixture holder unavailable",
                "token_mint": mint,
                "underlying_operation_count": 1,
                "rpc_method": "getTokenLargestAccounts",
                "status_code": 400,
            },
        )

    return {"goplus": goplus, "solana_rpc_holder": rpc_holder}


def _pacer():
    return budget.SequentialRequestPacer(
        now_fn=lambda: NOW, sleep_fn=lambda _s: None
    )


def _evaluate(
    connection: sqlite3.Connection,
    *,
    factories: Mapping[str, Any],
    mints: tuple[str, ...] = (MINT_A,),
    eligible_target: int = 1,
) -> HolderContextResult:
    owner = AuthoritativeLiveOperationalCampaignOwner()
    ledger = budget.build_ledger(
        pump_operations=0, deadline_at=NOW + timedelta(minutes=30)
    )
    proofs = tuple(
        SimpleNamespace(mint=mint, bonding_curve=_POOLS[index], block_time=0)
        for index, mint in enumerate(mints)
    )
    return owner._evaluate_holder_eligibility(
        connection,
        command=SimpleNamespace(run_id="run", campaign_id="campaign"),
        cycle_id="cycle",
        bounded_candidates=proofs,
        evaluated=NOW,
        deadline=NOW + timedelta(minutes=30),
        ledger=ledger,
        timeout_seconds=1.0,
        context_factories=dict(factories),
        request_pacer=_pacer(),
        eligible_target=eligible_target,
    )


# ---------------------------------------------------------------------------
# Campaign fixtures (PILOT_INPUT_READINESS)
# ---------------------------------------------------------------------------


def _permanent_supply(n: int = 4, *, recon_coverage=None, recon_ids=None):
    proofs = {}
    origins = []
    candidates = {}
    for i in range(n):
        mint = _MINTS[i]
        pool = _POOLS[i]
        proofs[mint] = FixturePumpSwapProof(mint=mint, pool_address=pool)
        origins.append(
            FixtureOriginProof(
                mint=mint,
                signature=f"sig{i}" + "1" * 80,
                slot=432_499_500 + i,
                block_time=int(
                    datetime.fromisoformat(e8.NOW.replace("Z", "+00:00")).timestamp()
                ),
                bonding_curve=pool,
                confirmed=True,
            )
        )
        candidates[mint.lower()] = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "market_identity": f"solana-mainnet:pumpswap:{pool}",
            "provenance": "LATEST_GRADUATED" if i % 2 == 0 else "PERSISTED_GRADUATED",
            "liquidity": {"liquidity_usd": 5000.0 + i * 100},
            "liquidity_usd": 5000.0 + i * 100,
            "evidence_expires_at": EXPIRES,
            "memory_observation_eligible": True,
            "future_action_eligibility": "BLOCKED_OR_UNKNOWN",
        }
    diagnostics: dict[str, Any] = {
        "permanent_availability": True,
        "stage_local_source_requests": 0,
        "stage_operations_used": {},
        "discovery_request_key_prefix": "camp-partial|",
    }
    if recon_coverage is not None:
        diagnostics["campaign_source_request_coverage"] = list(recon_coverage)
        diagnostics["source_request_ids"] = list(
            recon_ids or [e["source_request_id"] for e in recon_coverage]
        )
        diagnostics["protocol_confirmation"] = {
            "source_request_ids": list(
                recon_ids or [e["source_request_id"] for e in recon_coverage]
            ),
            "source_request_coverage": list(recon_coverage),
        }
    return GraduatedSupply(
        ready=True,
        terminal="GRADUATED_SUPPLY_READY",
        graduated_supply=tuple(origins),
        graduation_proofs=proofs,
        candidate_a={"mint": origins[0].mint, "pair_address": _POOLS[0]},
        candidate_b={"mint": origins[1].mint, "pair_address": _POOLS[1]},
        two_candidate_selection={"ready": True},
        handoff_readiness={},
        discovery_report={},
        front_door_report={"generated_at": e8.NOW},
        diagnostics=diagnostics,
        holder_reserve_supply=tuple(origins),
        holder_reserve_candidates=candidates,
    )


def _seed_markets(db_path, supply):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        for proof in supply.holder_reserve_supply:
            item = supply.holder_reserve_candidates[proof.mint.lower()]
            record_exact_market_transition(
                conn,
                ExactMarketObservation(
                    network=NETWORK,
                    mint=proof.mint,
                    pool=str(item["pool"]),
                    token_program="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                    pool_program=PUMPSWAP_AMM_PROGRAM_ID,
                    base_mint=proof.mint,
                    quote_mint=WSOL,
                    venue="pumpswap",
                    state=CURRENT_VISIBLE,
                    reason="FIXTURE",
                    observed_at=e8.NOW,
                    next_lawful_action_at=None,
                    source_provenance={"fixture": True},
                    contract_version="FIXTURE_V1",
                ),
                now=e8.NOW,
            )
        conn.commit()
    finally:
        conn.close()


def _insert_request(connection, source, kind, key):
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, request_key,
            tracking_priority, source_status, data_quality_label
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (source, kind, e8.NOW, key, 0, "COMPLETE", "CLEAN_DATA"),
    )
    connection.commit()
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def _coverage(rid, *, stage="PROTOCOL|1", transport=1, terminal="COMPLETED"):
    return {
        "source_request_id": rid,
        "source_name": "solana_rpc",
        "request_kind": "pumpswap_pool_account_batch",
        "logical_stage_id": stage,
        "transport_identity_count": transport,
        "normalized_member_count": 1 if transport else 0,
        "terminal_status": terminal,
    }


def _run_pilot_input_readiness(*, seed: str, factories: Mapping[str, Any]):
    """Run the authoritative PILOT_INPUT_READINESS path with real holder work."""
    base = e8._IntegrationBase()
    base.setUp()
    conn = sqlite3.connect(base.db)
    rid = _insert_request(
        conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-partial|proto"
    )
    conn.close()
    supply = _permanent_supply(4, recon_coverage=[_coverage(rid)], recon_ids=[rid])
    _seed_markets(base.db, supply)
    owner = AuthoritativeLiveOperationalCampaignOwner()
    result = owner.run(
        mode=PILOT_INPUT_READINESS,
        command=base.command,
        pump_transport=_FakePumpTransport([], {}),
        secondary_transport=None,
        source_governor=GOV,
        central_scheduler=SCH,
        selection_seed=seed,
        cycle_id="cyc",
        cycle_cutoff=e8.CUTOFF,
        evaluated_at=e8.NOW,
        backup_path=base.backup,
        lifecycle_kwargs={
            "context_adapter_factories": dict(factories),
            "holder_request_pacer": budget.SequentialRequestPacer(
                now_fn=lambda: datetime.fromisoformat(
                    e8.NOW.replace("Z", "+00:00")
                ),
                sleep_fn=lambda _s: None,
            ),
        },
        graduated_supply=supply,
    )
    return base, result


# ===========================================================================
# Repair 1 — SNAPSHOT_READINESS fails closed on holder accounting
# ===========================================================================


class TestSnapshotReadinessHolderAccounting(e33._SnapshotReadinessBase):
    def _mature_transport(self):
        now = self._now()
        return now, e3638._create_transport(
            [int(now.timestamp()) - 900, int(now.timestamp()) - 901]
        )

    def _run_readiness(self, *, factories, base_factory=None, now=None, transport=None):
        if transport is None:
            now, transport = self._mature_transport()
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_snapshot_readiness(
            command=self.command,
            pump_transport=transport,
            source_governor=e33.GOV,
            central_scheduler=e33.SCH,
            selection_seed="holder-partial-readiness",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=now.isoformat(),
            context_adapter_factories=dict(factories),
            geckoterminal_base_adapter_factory=(
                base_factory or self._base_factory()
            ),
            geckoterminal_transports=e33._gt_15m_transports(now),
            secret_present=True,
            holder_request_pacer=e33._NoSleepPacer(),
            snapshot_request_pacer=e33._NoSleepPacer(),
        )

    def test_1_accounting_blocker_attempts_zero_snapshot_bundles(self) -> None:
        base_factory = MagicMock(
            side_effect=AssertionError("readiness snapshot call forbidden")
        )
        result = self._run_readiness(
            factories=_unmeasured_goplus_factory(), base_factory=base_factory
        )
        base_factory.assert_not_called()
        self.assertEqual(result.snapshot_bundles, ())
        self.assertEqual(result.complete_bundle_count, 0)
        connection = sqlite3.connect(self.db)
        try:
            snapshots = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_token_snapshots"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        self.assertEqual(snapshots, 0)

    def test_2_accounting_incomplete_cannot_return_ready(self) -> None:
        result = self._run_readiness(factories=_unmeasured_goplus_factory())
        self.assertNotEqual(result.status, "READY")
        self.assertEqual(result.status, "BLOCKED_HOLDER_ACCOUNTING")
        gates = result.summary["readiness_gates"]
        self.assertIn("holder_accounting_complete", gates)
        self.assertFalse(gates["holder_accounting_complete"])
        self.assertIn("holder_accounting_complete", result.blocked_reasons)

    def test_3_report_exposes_holder_ids_coverage_reason_and_counts(self) -> None:
        result = self._run_readiness(factories=_unmeasured_goplus_factory())
        context = result.summary["holder_context"]
        self.assertTrue(context["accounting_blocker"])
        self.assertTrue(context["accounting_blocker_reason"])
        self.assertTrue(context["source_request_ids"])
        self.assertTrue(context["source_request_coverage"])
        self.assertGreaterEqual(context["governed_request_count"], 1)
        self.assertEqual(context["measured_transport_count"], 0)
        self.assertEqual(result.holder_context, context)
        # Every reported holder ID is a genuine durable request row.
        connection = sqlite3.connect(self.db)
        try:
            for rid in context["source_request_ids"]:
                row = connection.execute(
                    "SELECT id FROM printer_source_requests WHERE id=?", (rid,)
                ).fetchone()
                self.assertIsNotNone(row)
        finally:
            connection.close()
        for entry in context["source_request_coverage"]:
            self.assertIn(entry["source_request_id"], context["source_request_ids"])
            self.assertEqual(entry["terminal_status"], "BLOCKED")

    def test_10_snapshot_readiness_blocks_on_partial_holder_attempt(self) -> None:
        base_factory = MagicMock(
            side_effect=AssertionError("readiness snapshot call forbidden")
        )
        result = self._run_readiness(
            factories=_partial_holder_factories(), base_factory=base_factory
        )
        base_factory.assert_not_called()
        self.assertEqual(result.status, "BLOCKED_HOLDER_ACCOUNTING")
        self.assertEqual(result.snapshot_bundles, ())
        context = result.summary["holder_context"]
        self.assertTrue(context["accounting_blocker"])
        # The GoPlus request that really happened before the RPC failure is kept.
        self.assertTrue(context["source_request_ids"])
        self.assertTrue(context["source_request_coverage"])

    def test_15_no_lifecycle_memory_or_financial_activity_occurs(self) -> None:
        result = self._run_readiness(factories=_partial_holder_factories())
        self.assertFalse(result.summary["lifecycle_started"])
        connection = sqlite3.connect(self.db)
        try:
            for table in FORBIDDEN_ACTIVITY_TABLES:
                self.assertEqual(
                    int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                    ),
                    0,
                    table,
                )
        finally:
            connection.close()

    def test_12_complete_accounting_source_failure_stays_context_only(self) -> None:
        """Rate-limit / unavailable evidence with complete measured accounting."""
        result = self._run_readiness(factories=_rate_limited_goplus_factories())
        self.assertNotEqual(result.status, "BLOCKED_HOLDER_ACCOUNTING")
        context = result.summary["holder_context"]
        self.assertFalse(context["accounting_blocker"])
        self.assertIsNone(context["accounting_blocker_reason"])
        self.assertTrue(result.summary["readiness_gates"]["holder_accounting_complete"])


# ===========================================================================
# Repair 2 — partial holder attempts are preserved
# ===========================================================================


class TestPartialHolderCollection:
    def test_4_goplus_durable_id_survives_later_collection_failure(self, tmp_path):
        connection = _db(tmp_path)
        before = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        )
        result = _evaluate(connection, factories=_partial_holder_factories())
        rows = connection.execute(
            "SELECT id, source_name FROM printer_source_requests ORDER BY id"
        ).fetchall()
        assert len(rows) > before
        goplus_ids = [int(r["id"]) for r in rows if r["source_name"] == "goplus"]
        assert goplus_ids, "the real GoPlus governed request must exist"
        assert set(goplus_ids) <= set(result.source_request_ids)
        assert result.governed_request_count >= 1

    def test_6_partial_collection_sets_typed_accounting_blocker(self, tmp_path):
        connection = _db(tmp_path)
        result = _evaluate(connection, factories=_partial_holder_factories())
        assert result.accounting_blocker is True
        reason = str(result.accounting_blocker_reason or "")
        assert "HOLDER_PARTIAL_ATTEMPT" in reason
        for entry in result.source_request_coverage:
            assert entry["terminal_status"] == "BLOCKED"

    def test_11_failure_before_any_request_blocks_with_zero_ids(self, tmp_path):
        connection = _db(tmp_path)
        result = _evaluate(
            connection, factories=_partial_holder_factories(raise_on_goplus=True)
        )
        assert result.accounting_blocker is True
        assert result.accounting_blocker_reason
        assert result.source_request_ids == ()
        assert result.source_request_coverage == ()
        assert result.governed_request_count == 0
        assert result.measured_transport_count == 0

    def test_12_rate_limited_complete_accounting_is_context_only(self, tmp_path):
        connection = _db(tmp_path)
        result = _evaluate(connection, factories=_rate_limited_goplus_factories())
        assert result.accounting_blocker is False
        assert result.accounting_blocker_reason is None
        assert result.source_request_ids

    def test_collect_preclose_context_default_behaviour_unchanged(self, tmp_path):
        """Unrelated memory-close callers keep the raising default."""
        connection = _db(tmp_path)
        step = {
            "run_id": "run",
            "step_key": "default-mode",
            "token_mint": MINT_A,
            "pair_address": _POOLS[0],
        }
        with pytest.raises(RuntimeError) as excinfo:
            _collect_preclose_context(
                connection,
                step,
                timeout_seconds=1.0,
                adapter_factories=_partial_holder_factories(),
                include=frozenset({"safety"}),
                request_pacer=_pacer(),
            )
        assert not isinstance(excinfo.value, PrecloseContextPartialError)


class TestPartialHolderPersistence:
    def test_7_persistence_failure_preserves_existing_request_id(self, tmp_path, monkeypatch):
        connection = _db(tmp_path)
        first = _goplus_execution(connection, mint=MINT_A, request_key="persist-1")
        second = _goplus_execution(connection, mint=MINT_B, request_key="persist-2")
        first_id = int(first.request_record.id)
        second_id = int(second.request_record.id)

        real_record_attempt = budget.record_attempt
        calls = {"n": 0}

        def _flaky(conn, **values):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("fixture persistence failure")
            return real_record_attempt(conn, **values)

        monkeypatch.setattr(budget, "record_attempt", _flaky)

        with pytest.raises(HolderBundlePersistPartialError) as excinfo:
            budget.persist_bundle_attempts(
                connection,
                run_id="run",
                cycle_id="cycle",
                mint=MINT_A,
                executions={"safety": first, "safety_alt": second},
                created_at=NOW.isoformat(),
                campaign_id="campaign",
                candidate_ordinal=1,
            )
        partial = excinfo.value.partial
        assert first_id in partial.source_request_ids
        assert second_id in partial.source_request_ids
        assert partial.accounting_blocker is True
        assert partial.accounting_blocker_reason

    def test_8_persistence_failure_emits_blocked_coverage(self, tmp_path, monkeypatch):
        connection = _db(tmp_path)
        first = _goplus_execution(connection, mint=MINT_A, request_key="cov-1")
        second = _goplus_execution(connection, mint=MINT_B, request_key="cov-2")
        second_id = int(second.request_record.id)

        real_record_attempt = budget.record_attempt
        calls = {"n": 0}

        def _flaky(conn, **values):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("fixture persistence failure")
            return real_record_attempt(conn, **values)

        monkeypatch.setattr(budget, "record_attempt", _flaky)

        with pytest.raises(HolderBundlePersistPartialError) as excinfo:
            budget.persist_bundle_attempts(
                connection,
                run_id="run",
                cycle_id="cycle",
                mint=MINT_A,
                executions={"safety": first, "safety_alt": second},
                created_at=NOW.isoformat(),
                campaign_id="campaign",
                candidate_ordinal=1,
            )
        partial = excinfo.value.partial
        coverage_ids = {
            int(entry["source_request_id"])
            for entry in partial.source_request_coverage
        }
        assert second_id in coverage_ids
        failed = [
            entry
            for entry in partial.source_request_coverage
            if int(entry["source_request_id"]) == second_id
        ]
        assert failed and failed[0]["terminal_status"] == "BLOCKED"
        # Every preserved coverage entry names a real durable request row.
        for rid in coverage_ids:
            row = connection.execute(
                "SELECT id FROM printer_source_requests WHERE id=?", (rid,)
            ).fetchone()
            assert row is not None

    def test_evaluate_preserves_ids_when_persistence_fails(self, tmp_path, monkeypatch):
        connection = _db(tmp_path)
        real_record_attempt = budget.record_attempt

        def _always_fail(conn, **values):
            raise RuntimeError("fixture persistence failure")

        monkeypatch.setattr(budget, "record_attempt", _always_fail)
        result = _evaluate(connection, factories=_healthy_goplus_factory())
        monkeypatch.setattr(budget, "record_attempt", real_record_attempt)
        assert result.accounting_blocker is True
        assert result.source_request_ids, "durable holder IDs must survive"
        for entry in result.source_request_coverage:
            assert entry["terminal_status"] == "BLOCKED"


# ===========================================================================
# Campaign reconciliation on the partial holder attempt
# ===========================================================================


class TestCampaignReconciliationOnPartialAttempt:
    def test_5_partial_goplus_coverage_remains_in_campaign_manifest(self):
        base, result = _run_pilot_input_readiness(
            seed="holder-partial-manifest", factories=_partial_holder_factories()
        )
        try:
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            holder_ids = list(diag.get("holder_source_request_ids") or ())
            holder_cov = list(diag.get("holder_source_request_coverage") or ())
            assert holder_ids, "partial holder IDs must reach campaign diagnostics"
            assert holder_cov, "partial holder coverage must reach the manifest"
            stage_ids = collect_stage_reported_request_ids(diag)
            cov_ids = {
                int(entry["source_request_id"])
                for entry in collect_stage_source_request_coverage(diag)
            }
            for hid in holder_ids:
                assert hid in stage_ids
                assert hid in cov_ids
            manifest_ids = {
                int(entry["source_request_id"])
                for entry in (diag.get("campaign_source_request_manifest") or ())
            }
            for hid in holder_ids:
                assert hid in manifest_ids
            check = sqlite3.connect(base.db)
            try:
                for hid in holder_ids:
                    row = check.execute(
                        "SELECT id FROM printer_source_requests WHERE id=?", (hid,)
                    ).fetchone()
                    assert row is not None
            finally:
                check.close()
        finally:
            base.tearDown()

    def test_9_pilot_input_readiness_blocks_on_partial_holder_attempt(self):
        base, result = _run_pilot_input_readiness(
            seed="holder-partial-block", factories=_partial_holder_factories()
        )
        try:
            life = result.lifecycle
            assert life.get("pilot_input_readiness") is None
            diag = life.get("graduated_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            blockers = recon.get("stage_accounting_blockers") or []
            assert any(
                "holder" in str(b.get("stage", "")).lower()
                or "HOLDER" in str(b.get("reason", "")).upper()
                for b in blockers
            )
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ctx.get("accounting_blocker") is True
            assert holder_ctx.get("source_request_ids")
        finally:
            base.tearDown()

    def test_13_holder_extreme_remains_memory_observation_eligible(self):
        base, result = _run_pilot_input_readiness(
            seed="holder-partial-extreme", factories=_extreme_goplus_factory()
        )
        try:
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ctx.get("accounting_blocker") is False
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            freeze = diag.get("freeze_depth_enforcement") or {}
            assert freeze.get("enforced") is True
        finally:
            base.tearDown()

    def test_14_future_action_remains_blocked_or_unknown(self):
        base, result = _run_pilot_input_readiness(
            seed="holder-partial-future", factories=_extreme_goplus_factory()
        )
        try:
            diag = result.lifecycle.get("graduated_supply_diagnostics") or {}
            observed = 0
            for entry in diag.get("observation_reserve") or ():
                if isinstance(entry, Mapping) and (
                    "future_action_eligibility" in entry
                ):
                    observed += 1
                    assert entry["future_action_eligibility"] == "BLOCKED_OR_UNKNOWN"
            readiness = result.lifecycle.get("pilot_input_readiness")
            candidates = None
            if readiness is not None:
                candidates = (
                    readiness.get("candidates")
                    if isinstance(readiness, Mapping)
                    else getattr(readiness, "candidates", None)
                )
            for cand in candidates or ():
                fa = (
                    cand.get("future_action_eligibility")
                    if isinstance(cand, Mapping)
                    else getattr(cand, "future_action_eligibility", None)
                )
                if fa is not None:
                    observed += 1
                    assert fa == "BLOCKED_OR_UNKNOWN"
            # No surface may claim an unlocked future action.
            assert "BUY" not in str(diag.get("observation_reserve") or ())
        finally:
            base.tearDown()

    def test_15_partial_attempt_creates_no_forbidden_activity(self):
        base, result = _run_pilot_input_readiness(
            seed="holder-partial-locks", factories=_partial_holder_factories()
        )
        try:
            assert result.lifecycle.get("lifecycle_started") is False
            connection = sqlite3.connect(base.db)
            try:
                for table in FORBIDDEN_ACTIVITY_TABLES:
                    assert (
                        int(
                            connection.execute(
                                f"SELECT COUNT(*) FROM {table}"
                            ).fetchone()[0]
                        )
                        == 0
                    ), table
            finally:
                connection.close()
        finally:
            base.tearDown()
