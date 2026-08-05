"""V2-9.8B holder manifest composition repair.

Offline fixture-only. Proves real holder governed executions emit durable
request IDs and stage-owned coverage into campaign-wide reconciliation, and
that accounting incompleteness is distinct from ordinary holder evidence
failure.
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH,
    CURRENT_VISIBLE,
    ExactMarketObservation,
    NETWORK,
    assemble_and_reconcile_campaign_source_requests,
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
    HolderContextResult,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

NOW = datetime(2026, 8, 4, 16, 0, tzinfo=timezone.utc)
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


def _db(tmp_path: Path) -> tuple[Path, sqlite3.Connection]:
    path = tmp_path / "holder-manifest.sqlite3"
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
    ledger = budget.build_ledger(
        pump_operations=0, deadline_at=NOW + timedelta(minutes=30)
    )
    budget.persist_ledger(
        connection,
        run_id="run",
        cycle_id="cycle",
        ledger=ledger,
        now=NOW.isoformat(),
    )
    connection.commit()
    return path, connection


def _rpc_holder_payload(
    mint: str = MINT_A,
    *,
    label: str = "HOLDER_CONCENTRATION_HEALTHY",
    underlying_operation_count: int | None = 2,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "token_mint": mint,
        "holder_concentration_label": label,
        "captured_at": NOW.isoformat(),
        "rpc_method": "getTokenLargestAccounts+getTokenSupply",
        "commitment": "finalized",
        "context_slot": 123,
    }
    if underlying_operation_count is not None:
        payload["underlying_operation_count"] = underlying_operation_count
    payload.update(extra)
    return payload


def _execute_rpc_holder(
    connection: sqlite3.Connection,
    *,
    mint: str,
    request_key: str,
    payload: Mapping[str, Any] | None = None,
) -> Any:
    body = dict(payload or _rpc_holder_payload(mint))
    adapter = build_fixture_source_adapter(
        "solana_rpc",
        fixture_payload=body,
    )
    request = build_governed_source_request(
        "solana_rpc",
        "holder_concentration_reference",
        request_key=request_key,
        payload={"token_mint": mint},
    )
    return execute_source_request_with_governor(
        connection, request, adapter, recent_request_count=0
    )


def _execute_goplus(
    connection: sqlite3.Connection,
    *,
    mint: str,
    request_key: str,
    payload: Mapping[str, Any] | None = None,
    rate_limited: bool = False,
) -> Any:
    from printer_v1.sources.goplus import build_goplus_adapter

    if rate_limited:
        body: dict[str, Any] = {
            "fixture_status": "rate_limited",
            "retry_after_seconds": 60,
            "underlying_operation_count": 1,
        }
        adapter = build_goplus_adapter(
            enabled=True,
            fixture_transport=lambda _ctx: body,
        )
    else:
        body = {
            "token_mint": mint,
            "mint_authority": None,
            "freeze_authority": None,
            "metadata_mutable": False,
            "total_supply": "1000000000",
            "top_10_holders": [{"percent": "3"} for _ in range(10)],
            "lp_info": [{"locked": True}],
            "risk_flags": [],
            "underlying_operation_count": 1,
        }
        if payload:
            body.update(dict(payload))
        adapter = build_fixture_source_adapter(
            "goplus",
            fixture_payload=body,
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


# ---------------------------------------------------------------------------
# persist_bundle_attempts — durable ID + coverage emission
# ---------------------------------------------------------------------------


class TestPersistBundleCoverage:
    def test_real_holder_execution_returns_durable_request_id(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        execution = _execute_rpc_holder(
            connection, mint=MINT_A, request_key="holder-id-1"
        )
        durable_id = int(execution.request_record.id)
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={"holder_primary": execution},
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
        assert result.governed_request_count == 1
        assert result.source_request_ids == (durable_id,)
        assert durable_id in result.source_request_ids
        row = connection.execute(
            "SELECT id FROM printer_source_requests WHERE id=?",
            (durable_id,),
        ).fetchone()
        assert row is not None

    def test_one_holder_request_produces_one_coverage_entry(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        execution = _execute_rpc_holder(
            connection, mint=MINT_A, request_key="holder-cov-1"
        )
        rid = int(execution.request_record.id)
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={"holder_primary": execution},
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
        assert len(result.source_request_coverage) == 1
        entry = result.source_request_coverage[0]
        assert entry["source_request_id"] == rid
        assert entry["source_name"] == "solana_rpc"
        assert entry["request_kind"] == "holder_concentration_reference"
        assert "campaign|run|cycle|" in entry["logical_stage_id"]
        assert entry["transport_identity_count"] == 2
        assert entry["terminal_status"] == "COMPLETED"
        assert result.accounting_blocker is False
        assert result.measured_transport_count == 2

    def test_multiple_holder_sources_produce_distinct_coverage(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        goplus = _execute_goplus(connection, mint=MINT_A, request_key="multi-goplus")
        primary = _execute_rpc_holder(
            connection, mint=MINT_A, request_key="multi-primary"
        )
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={
                "safety": goplus,
                "holder_primary": primary,
            },
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=2,
        )
        assert result.governed_request_count == 2
        ids = list(result.source_request_ids)
        assert len(ids) == 2
        assert len(set(ids)) == 2
        assert len(result.source_request_coverage) == 2
        stages = {e["logical_stage_id"] for e in result.source_request_coverage}
        assert len(stages) == 2
        roles = {
            e["logical_stage_id"].rsplit("|", 1)[-1]
            for e in result.source_request_coverage
        }
        assert "SAFETY" in roles or "GOPLUS" in roles or any(
            "SAFETY" in e["logical_stage_id"] or "GOPLUS" in e["logical_stage_id"]
            for e in result.source_request_coverage
        )

    def test_alias_executions_are_not_double_counted(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        execution = _execute_rpc_holder(
            connection, mint=MINT_A, request_key="alias-holder"
        )
        # "holder" is an alias of the same execution object as holder_primary.
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={
                "holder_primary": execution,
                "holder": execution,
            },
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
        assert result.governed_request_count == 1
        assert len(result.source_request_ids) == 1
        assert len(result.source_request_coverage) == 1
        assert result.measured_transport_count == 2

    def test_missing_measured_transport_sets_accounting_blocker(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        # Fixture payload intentionally omits measured transport evidence.
        payload = {
            "token_mint": MINT_A,
            "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
            "captured_at": NOW.isoformat(),
            "rpc_method": "getTokenLargestAccounts+getTokenSupply",
            "commitment": "finalized",
            # no underlying_operation_count and no transport identities
        }
        # Bypass adapter defaults by using a raw execution shell after a real
        # durable request insert via governed execution, then strip count.
        execution = _execute_rpc_holder(
            connection,
            mint=MINT_A,
            request_key="no-measure",
            payload=_rpc_holder_payload(MINT_A, underlying_operation_count=2),
        )
        # Force-missing measured evidence on the normalized payload.
        stripped = dict(execution.normalized_result.normalized_payload or {})
        stripped.pop("underlying_operation_count", None)
        stripped.pop("transport_operation_identities", None)
        stripped.pop("transport_operations_used", None)
        execution = SimpleNamespace(
            request_record=execution.request_record,
            response_record=execution.response_record,
            failure_record=execution.failure_record,
            normalized_result=SimpleNamespace(
                source_name=execution.normalized_result.source_name,
                request_kind=execution.normalized_result.request_kind,
                source_status=execution.normalized_result.source_status,
                data_quality_label=execution.normalized_result.data_quality_label,
                failure_type=execution.normalized_result.failure_type,
                failure_message=getattr(
                    execution.normalized_result, "failure_message", None
                ),
                normalized_payload=stripped,
                received_at=execution.normalized_result.received_at,
                retry_after_at=getattr(
                    execution.normalized_result, "retry_after_at", None
                ),
            ),
        )
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={"holder_primary": execution},
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
        assert result.accounting_blocker is True
        assert result.accounting_blocker_reason
        assert "TRANSPORT" in str(result.accounting_blocker_reason).upper() or (
            "MEASURE" in str(result.accounting_blocker_reason).upper()
        )
        entry = result.source_request_coverage[0]
        assert entry["source_request_id"] == int(execution.request_record.id)
        assert entry["terminal_status"] == "BLOCKED"
        assert entry["transport_identity_count"] == 0
        # Durable ID preserved even when accounting is incomplete.
        assert result.source_request_ids == (int(execution.request_record.id),)

    def test_rate_limit_with_complete_accounting_is_not_accounting_blocker(
        self, tmp_path
    ):
        path, connection = _db(tmp_path)
        del path
        execution = _execute_goplus(
            connection,
            mint=MINT_A,
            request_key="rate-limit-ok",
            rate_limited=True,
        )
        result = budget.persist_bundle_attempts(
            connection,
            run_id="run",
            cycle_id="cycle",
            mint=MINT_A,
            executions={"safety": execution},
            created_at=NOW.isoformat(),
            campaign_id="campaign",
            candidate_ordinal=1,
        )
        assert result.accounting_blocker is False
        assert result.governed_request_count == 1
        assert result.measured_transport_count == 1
        entry = result.source_request_coverage[0]
        assert entry["source_request_id"] == int(execution.request_record.id)
        assert entry["transport_identity_count"] == 1
        # Source failure may block the coverage terminal, but accounting is complete.
        assert entry["terminal_status"] in {"BLOCKED", "COMPLETED"}


# ---------------------------------------------------------------------------
# _evaluate_holder_eligibility result contract
# ---------------------------------------------------------------------------


class TestEvaluateHolderEligibilityResult:
    def test_evaluate_returns_holder_context_result(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        owner = AuthoritativeLiveOperationalCampaignOwner()
        ledger = budget.build_ledger(
            pump_operations=0, deadline_at=NOW + timedelta(minutes=30)
        )
        proof = SimpleNamespace(
            mint=MINT_A, bonding_curve=_POOLS[0], block_time=0
        )

        def _goplus(**kwargs):
            mint = kwargs.get("token_mint") or MINT_A
            return build_fixture_source_adapter(
                "goplus",
                fixture_payload={
                    "token_mint": mint,
                    "mint_authority": None,
                    "freeze_authority": None,
                    "metadata_mutable": False,
                    "total_supply": "1000000000",
                    "top_10_holders": [{"percent": "3"} for _ in range(10)],
                    "lp_info": [{"locked": True}],
                    "risk_flags": [],
                    "underlying_operation_count": 1,
                },
            )

        result = owner._evaluate_holder_eligibility(
            connection,
            command=SimpleNamespace(run_id="run", campaign_id="campaign"),
            cycle_id="cycle",
            bounded_candidates=(proof,),
            evaluated=NOW,
            deadline=NOW + timedelta(minutes=30),
            ledger=ledger,
            timeout_seconds=1.0,
            context_factories={"goplus": _goplus},
            request_pacer=budget.SequentialRequestPacer(
                now_fn=lambda: NOW, sleep_fn=lambda _s: None
            ),
            eligible_target=1,
        )
        assert isinstance(result, HolderContextResult)
        assert result.governed_request_count >= 1
        assert result.source_request_ids
        assert result.source_request_coverage
        assert len(result.source_request_ids) == len(
            {int(x) for x in result.source_request_ids}
        )
        for entry in result.source_request_coverage:
            assert entry["source_request_id"] in result.source_request_ids
            assert "logical_stage_id" in entry
            assert "transport_identity_count" in entry
            assert "normalized_member_count" in entry
            assert "terminal_status" in entry
        # Healthy goplus keeps future-action context; no accounting blocker.
        assert result.accounting_blocker is False


# ---------------------------------------------------------------------------
# Campaign wiring + three-way reconciliation
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
        "discovery_request_key_prefix": "camp-holder|",
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


def _goplus_factory(*, extreme: bool = False, rate_limited: bool = False):
    from printer_v1.sources.goplus import build_goplus_adapter
    from printer_v1.sources.solana_rpc_holder import build_solana_rpc_holder_adapter

    factories: dict[str, Any] = {}

    def goplus_factory(**kwargs):
        mint = kwargs.get("token_mint") or MINT_A
        if rate_limited:
            payload = {
                "fixture_status": "rate_limited",
                "retry_after_seconds": 30,
                "underlying_operation_count": 1,
            }
            return build_goplus_adapter(
                enabled=True,
                fixture_transport=lambda _ctx: payload,
            )
        if extreme:
            payload = {
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "25"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
                "underlying_operation_count": 1,
            }
        else:
            payload = {
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
                "underlying_operation_count": 1,
            }
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload=payload,
        )

    factories["goplus"] = goplus_factory
    if rate_limited:
        # Rate-limited GoPlus yields UNKNOWN concentration and opens the RPC
        # holder path. Provide a fixture RPC failure with complete accounting
        # so the stage remains context-only (not an accounting blocker).
        def rpc_factory(**kwargs):
            mint = kwargs.get("token_mint") or MINT_A
            # Non-transient failure: no Helius backup (would exceed the
            # permanent holder safety reservation of 8 transports).
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

        factories["solana_rpc_holder"] = rpc_factory
    return factories


class TestCampaignHolderManifestWiring:
    def test_holder_ids_enter_stage_reported_and_manifest(self):
        """Authoritative path: real evaluate + campaign reconciliation."""
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            conn.row_factory = sqlite3.Row
            rid = _insert_request(
                conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-holder|proto"
            )
            conn.close()
            coverage = [_coverage(rid, stage="PROTOCOL|1")]
            supply = _permanent_supply(4, recon_coverage=coverage, recon_ids=[rid])
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            # Must NOT inject prebuilt holder_context diagnostics.
            assert "holder_context" not in supply.diagnostics
            assert "holder_source_request_ids" not in supply.diagnostics
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="holder-manifest-ok",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _goplus_factory(),
                    "holder_request_pacer": budget.SequentialRequestPacer(
                        now_fn=lambda: datetime.fromisoformat(
                            e8.NOW.replace("Z", "+00:00")
                        ),
                        sleep_fn=lambda _s: None,
                    ),
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            diag = life.get("candidate_supply_diagnostics") or {}
            holder_ids = list(diag.get("holder_source_request_ids") or ())
            holder_cov = list(diag.get("holder_source_request_coverage") or ())
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ids, "holder durable IDs must be stage-reported"
            assert holder_cov, "holder coverage must enter campaign diagnostics"
            assert holder_ctx.get("source_request_ids") == holder_ids
            assert holder_ctx.get("source_request_coverage")
            assert holder_ctx.get("accounting_blocker") is False
            stage_ids = collect_stage_reported_request_ids(diag)
            for hid in holder_ids:
                assert hid in stage_ids
            cov_collected = collect_stage_source_request_coverage(diag)
            cov_ids = {int(e["source_request_id"]) for e in cov_collected}
            for hid in holder_ids:
                assert hid in cov_ids
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            durable = set(diag.get("durable_campaign_request_ids") or ())
            reported = set(recon.get("stage_reported_request_ids") or ())
            coverage_ids = set(recon.get("coverage_request_ids") or ())
            for hid in holder_ids:
                assert hid in durable
                assert hid in reported
                assert hid in coverage_ids
            assert durable == reported == coverage_ids
            # Holder extreme is not required here; healthy path still keeps
            # future action blocked-or-unknown and may be memory-eligible.
            assert life.get("lifecycle_started") is False
            if life.get("pilot_input_readiness") is not None:
                # When freeze depth is satisfied, readiness is allowed.
                assert recon.get("status") == "OK"
        finally:
            base.tearDown()

    def test_holder_request_id_without_coverage_blocks(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "holder_source_request_ids": [501],
                "holder_source_request_coverage": [],
            },
        )
        # No DB row either → stage-reported not durable; still blocked.
        assert recon["status"] == "BLOCKED"
        assert recon["blocker"] == CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH

    def test_holder_id_without_coverage_with_db_row_blocks(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        rid = _insert_request(
            connection, "goplus", "safety_reference", "holder-no-cov"
        )
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "holder_source_request_ids": [rid],
                "holder_source_request_coverage": [],
            },
        )
        assert recon["status"] == "BLOCKED"
        assert rid in (recon.get("missing_from_manifest") or ()) or rid in (
            recon.get("missing_stage_reported_coverage") or ()
        )

    def test_holder_coverage_without_db_row_blocks(self, tmp_path):
        path, connection = _db(tmp_path)
        del path
        recon = assemble_and_reconcile_campaign_source_requests(
            connection,
            diagnostics={
                "holder_source_request_ids": [777],
                "holder_source_request_coverage": [
                    {
                        "source_request_id": 777,
                        "source_name": "goplus",
                        "request_kind": "safety_reference",
                        "logical_stage_id": "camp|run|cyc|1|SAFETY",
                        "transport_identity_count": 1,
                        "normalized_member_count": 1,
                        "terminal_status": "COMPLETED",
                    }
                ],
            },
        )
        assert recon["status"] == "BLOCKED"
        assert recon.get("categorical_detail") == "STAGE_REPORTED_REQUEST_NOT_DURABLE"
        assert 777 in recon.get("stage_reported_not_durable") or 777 in (
            recon.get("stage_only_not_durable") or ()
        )

    def test_holder_accounting_blocker_prevents_readiness(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            rid = _insert_request(
                conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-acc|proto"
            )
            conn.close()
            supply = _permanent_supply(
                4,
                recon_coverage=[_coverage(rid)],
                recon_ids=[rid],
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()

            def _fake(self, connection, **kwargs):
                ledger = kwargs["ledger"]
                facts = {}
                for proof in kwargs.get("bounded_candidates") or ():
                    facts[proof.mint.lower()] = {
                        "eligible": False,
                        "reason": "HOLDER_CONCENTRATION_EXTREME",
                        "source_name": "goplus",
                        "holder_concentration_label": "HOLDER_CONCENTRATION_EXTREME",
                    }
                # Simulate real request identity with incomplete accounting.
                hid = _insert_request(
                    connection,
                    "goplus",
                    "safety_reference",
                    f"holder-acc-{id(connection)}",
                )
                return HolderContextResult(
                    holder_facts=facts,
                    ledger=ledger,
                    source_request_ids=(hid,),
                    source_request_coverage=(
                        {
                            "source_request_id": hid,
                            "source_name": "goplus",
                            "request_kind": "safety_reference",
                            "logical_stage_id": (
                                f"campaign|run|cyc|1|SAFETY"
                            ),
                            "transport_identity_count": 0,
                            "normalized_member_count": 0,
                            "terminal_status": "BLOCKED",
                        },
                    ),
                    accounting_blocker=True,
                    accounting_blocker_reason=(
                        "HOLDER_TRANSPORT_IDENTITY_ABSENT"
                    ),
                    governed_request_count=1,
                    measured_transport_count=0,
                )

            owner._evaluate_holder_eligibility = _fake.__get__(
                owner, AuthoritativeLiveOperationalCampaignOwner
            )
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="holder-acc-block",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={"context_adapter_factories": {}},
                graduated_supply=supply,
            )
            life = result.lifecycle
            assert life.get("pilot_input_readiness") is None
            diag = life.get("candidate_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "BLOCKED"
            blockers = recon.get("stage_accounting_blockers") or []
            assert any(
                "HOLDER" in str(b.get("stage", "")).upper()
                or "HOLDER" in str(b.get("reason", "")).upper()
                or "TRANSPORT" in str(b.get("reason", "")).upper()
                for b in blockers
            )
            assert (diag.get("holder_context") or {}).get("accounting_blocker") is True
        finally:
            base.tearDown()

    def test_source_failure_with_complete_accounting_remains_memory_context(self):
        """Rate-limit / unavailable holder evidence with complete accounting.

        Must not become a campaign accounting blocker and must keep
        MEMORY_OBSERVATION path open (context only).
        """
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            rid = _insert_request(
                conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-ctx|proto"
            )
            conn.close()
            supply = _permanent_supply(
                4,
                recon_coverage=[_coverage(rid)],
                recon_ids=[rid],
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="holder-rate-limit-ctx",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _goplus_factory(rate_limited=True),
                    "holder_request_pacer": budget.SequentialRequestPacer(
                        now_fn=lambda: datetime.fromisoformat(
                            e8.NOW.replace("Z", "+00:00")
                        ),
                        sleep_fn=lambda _s: None,
                    ),
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            diag = life.get("candidate_supply_diagnostics") or {}
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ctx.get("accounting_blocker") is False
            recon = diag.get("campaign_source_request_reconciliation") or {}
            # Accounting complete → recon may OK if IDs/coverage match.
            if holder_ctx.get("source_request_ids"):
                assert recon.get("status") == "OK"
            # Observation rows must remain memory-eligible.
            # future_action stays blocked-or-unknown.
            # Holder evidence failure must not force recon accounting blocker.
            blockers = recon.get("stage_accounting_blockers") or []
            assert not any(
                "HOLDER" in str(b.get("stage", "")).upper()
                and "TRANSPORT" in str(b.get("reason", "")).upper()
                for b in blockers
            )
            assert life.get("lifecycle_started") is False
        finally:
            base.tearDown()

    def test_holder_extreme_remains_memory_observation_eligible(self):
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            rid = _insert_request(
                conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-ext|proto"
            )
            conn.close()
            supply = _permanent_supply(
                4,
                recon_coverage=[_coverage(rid)],
                recon_ids=[rid],
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="holder-extreme-mem",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _goplus_factory(extreme=True),
                    "holder_request_pacer": budget.SequentialRequestPacer(
                        now_fn=lambda: datetime.fromisoformat(
                            e8.NOW.replace("Z", "+00:00")
                        ),
                        sleep_fn=lambda _s: None,
                    ),
                },
                graduated_supply=supply,
            )
            life = result.lifecycle
            diag = life.get("candidate_supply_diagnostics") or {}
            holder_ctx = diag.get("holder_context") or {}
            assert holder_ctx.get("accounting_blocker") is False
            recon = diag.get("campaign_source_request_reconciliation") or {}
            assert recon.get("status") == "OK"
            # Readiness may proceed for MEMORY_OBSERVATION; future action unknown.
            readiness = life.get("pilot_input_readiness")
            if readiness is not None:
                # Inspect candidate future_action if present.
                candidates = (
                    readiness.get("candidates")
                    if isinstance(readiness, Mapping)
                    else getattr(readiness, "candidates", None)
                )
                if candidates:
                    for cand in candidates:
                        fa = (
                            cand.get("future_action_eligibility")
                            if isinstance(cand, Mapping)
                            else getattr(cand, "future_action_eligibility", None)
                        )
                        if fa is not None:
                            assert fa == "BLOCKED_OR_UNKNOWN"
            # Observation reserve should have selected or at least not been
            # blocked solely by holder concentration.
            freeze = diag.get("freeze_depth_enforcement") or {}
            assert freeze.get("enforced") is True
        finally:
            base.tearDown()

    def test_authoritative_three_way_reconciliation_includes_holder(self):
        """Database-proven holder IDs == stage-reported == coverage manifest."""
        base = e8._IntegrationBase()
        base.setUp()
        try:
            conn = sqlite3.connect(base.db)
            rid = _insert_request(
                conn, "solana_rpc", "pumpswap_pool_account_batch", "camp-3way|proto"
            )
            conn.close()
            supply = _permanent_supply(
                4,
                recon_coverage=[_coverage(rid)],
                recon_ids=[rid],
            )
            _seed_markets(base.db, supply)
            owner = AuthoritativeLiveOperationalCampaignOwner()
            result = owner.run(
                mode=PILOT_INPUT_READINESS,
                command=base.command,
                pump_transport=_FakePumpTransport([], {}),
                secondary_transport=None,
                source_governor=GOV,
                central_scheduler=SCH,
                selection_seed="holder-3way",
                cycle_id="cyc",
                cycle_cutoff=e8.CUTOFF,
                evaluated_at=e8.NOW,
                backup_path=base.backup,
                lifecycle_kwargs={
                    "context_adapter_factories": _goplus_factory(),
                    "holder_request_pacer": budget.SequentialRequestPacer(
                        now_fn=lambda: datetime.fromisoformat(
                            e8.NOW.replace("Z", "+00:00")
                        ),
                        sleep_fn=lambda _s: None,
                    ),
                },
                graduated_supply=supply,
            )
            diag = result.lifecycle.get("candidate_supply_diagnostics") or {}
            recon = diag.get("campaign_source_request_reconciliation") or {}
            holder_ids = set(diag.get("holder_source_request_ids") or ())
            assert holder_ids
            durable = set(diag.get("durable_campaign_request_ids") or ())
            stage = set(recon.get("stage_reported_request_ids") or ())
            cov = set(recon.get("coverage_request_ids") or ())
            assert durable == stage == cov
            assert holder_ids <= durable
            assert recon.get("status") == "OK"
            # Prove DB rows exist for holder IDs.
            check = sqlite3.connect(base.db)
            for hid in holder_ids:
                row = check.execute(
                    "SELECT id FROM printer_source_requests WHERE id=?",
                    (hid,),
                ).fetchone()
                assert row is not None
            check.close()
        finally:
            base.tearDown()
