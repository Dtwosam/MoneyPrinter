from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.candidate_acquisition import (
    CandidateAcquisitionError,
    legacy_two_token_runtime_projection,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import live_candidate_acquisition_transport as live_transport
from printer_v1.operator_cli.candidate_acquisition_integration import (
    CLI_MODE_N2,
    CLI_MODE_N7,
    MODE_N2,
    MODE_N7,
    MODE_POLICIES,
    AcquisitionSourceOperation,
    CandidateAcquisitionIntegrationError,
    FrozenAcquisitionTransportOwner,
    replay_candidate_acquisition_integration_report,
    run_candidate_acquisition_integration,
)
from printer_v1.operator_cli.live_candidate_acquisition_transport import (
    LiveAcquisitionConfigurationError,
    LiveAcquisitionTransportError,
    LiveCandidateAcquisitionTransportOwner,
    TransportResponse,
    UrllibCandidateAcquisitionOneShotTransport,
    build_live_candidate_acquisition_transport_owner,
)
from printer_v1.sources.contracts import NormalizedSourceResult
from printer_v1.sources.dexscreener import (
    build_dexscreener_adapter,
    fixture_success_transport as dexscreener_fixture_success_transport,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)
from printer_v1.sources.geckoterminal import (
    build_geckoterminal_adapter,
    fixture_failure_transport as geckoterminal_fixture_failure_transport,
    fixture_success_transport as geckoterminal_fixture_success_transport,
)
from printer_v1.sources.pump_contracts import (
    PUMPSWAP_POOL_DISCRIMINATOR,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
)
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/candidate_acquisition_capacity_v1.json").read_text()
)
NOW = "2026-07-29T12:00:00+00:00"
EXPIRES = "2026-07-29T14:00:00+00:00"
POOL_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeuycG6t58pk8Rai7Lb"


def _pumpswap_account(mint: str, ordinal: int) -> dict:
    keys = [item for row in FIXTURE["candidates"] for item in row]
    creator = keys[(ordinal * 5) % len(keys)]
    remaining = [keys[(ordinal * 5 + offset) % len(keys)] for offset in range(1, 4)]
    raw = (
        PUMPSWAP_POOL_DISCRIMINATOR
        + b"\1"
        + (ordinal + 1).to_bytes(2, "little")
        + b"".join(_b58decode(item) for item in (
            creator, mint, WSOL_MINT, remaining[0], remaining[1], remaining[2]
        ))
        + (1_000_000).to_bytes(8, "little")
        + _b58decode(creator)
        + b"\0\0"
        + (0).to_bytes(16, "little", signed=True)
    )
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


class _CanonicalMockNetworkTransport:
    """Frozen responses at the live owner's one-shot HTTP/RPC boundary."""

    def __init__(self, count: int) -> None:
        self.rows = _candidate_rows(count)
        self.mints = {row["mint"] for row in self.rows}
        self.pools = {
            row["pool"]: _pumpswap_account(row["mint"], ordinal)
            for ordinal, row in enumerate(self.rows)
        }
        self.calls: list[tuple[str, str]] = []

    def _result(self, payload, operation_kind: str, endpoint_role: str) -> TransportResponse:
        self.calls.append((operation_kind, endpoint_role))
        size = len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        return TransportResponse(payload, size, operation_kind, endpoint_role)

    def http_json(self, *, url, headers, timeout_seconds, byte_ceiling, endpoint_role):
        del url, headers, timeout_seconds, byte_ceiling
        if endpoint_role == "DEXSCREENER_PROFILES":
            payload = [
                {"chainId": "solana", "tokenAddress": row["mint"]}
                for row in self.rows
            ]
        elif endpoint_role == "DEXSCREENER_MARKET_BATCH":
            payload = [
                {
                    "chainId": "solana", "pairAddress": row["pool"],
                    "baseToken": {"address": row["mint"], "symbol": "MEME"},
                    "liquidity": {"usd": 10_000.0},
                    "volume": {"m5": 1_000.0, "h1": 4_000.0},
                    "txns": {"m5": {"buys": 2, "sells": 1}},
                    "pairCreatedAt": 1_785_326_000_000,
                }
                for row in self.rows
            ]
        elif endpoint_role == "GECKOTERMINAL_NEW_POOLS":
            row = self.rows[0]
            payload = {"data": [{
                "id": f"solana_{row['pool']}",
                "attributes": {
                    "chain": "solana", "address": row["pool"],
                    "base_token_address": row["mint"],
                    "reserve_in_usd": 10_000.0,
                    "volume_usd": {"m5": 1_000.0, "h1": 4_000.0},
                    "transactions": {"m5": {"buys": 2, "sells": 1}},
                    "pool_created_at": "2026-07-29T10:00:00+00:00",
                },
            }]}
        elif endpoint_role.startswith("GOPLUS_SAFETY_REFERENCE_"):
            payload = {"result": {}}
        else:
            raise AssertionError(f"unexpected HTTP role: {endpoint_role}")
        return self._result(payload, "HTTP_GET", endpoint_role)

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        del rpc_url, timeout_seconds, byte_ceiling
        if method == "getSignaturesForAddress":
            payload = []
        elif method == "getMultipleAccounts":
            addresses = list(params[0])
            values = []
            for address in addresses:
                if address in self.mints:
                    mint_data = bytearray(82)
                    mint_data[45] = 1
                    values.append({
                        "owner": TOKEN_PROGRAM_ID,
                        "data": [base64.b64encode(mint_data).decode(), "base64"],
                    })
                else:
                    values.append(self.pools[address])
            payload = {"context": {"slot": 420_000_000}, "value": values}
        elif method == "getTokenLargestAccounts":
            payload = {"context": {"slot": 420_000_000}, "value": [
                {"address": self.rows[0]["pool"], "amount": "1", "decimals": 0}
            ]}
        elif method == "getTokenSupply":
            payload = {"context": {"slot": 420_000_000}, "value": {
                "amount": "1000", "decimals": 0, "uiAmount": 1000,
                "uiAmountString": "1000",
            }}
        else:
            raise AssertionError(f"unexpected RPC method: {method}")
        return self._result(payload, method, endpoint_role)


class _StaticFailureAdapter:
    def __init__(self, source_name: str, request_kind: str, failure_type: str) -> None:
        self.source_name = source_name
        self.request_kind = request_kind
        self.failure_type = failure_type
        self.call_count = 0

    def execute(self, context):
        assert context.governor_approved
        self.call_count += 1
        return NormalizedSourceResult(
            source_name=self.source_name,
            request_kind=self.request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type=self.failure_type,
            failure_message=self.failure_type,
        )


def _db() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory()
    path = Path(temp.name) / "integration.sqlite3"
    apply_migrations(path)
    return temp, path


def _preflight(path: Path) -> dict:
    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": str(path.resolve()),
        "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "latest_migration": "049_candidate_acquisition_integration.sql",
        "integrity": "ok",
        "foreign_key_violations": 0,
        "git_provenance": {
            "git_head": "164dcd5e570d7de19a84bfa651e0320850f03348",
            "git_tracked_tree_clean": True,
        },
    }


def _candidate_rows(count: int) -> list[dict]:
    return [
        {
            "mint": mint,
            "pool": pool,
            "pool_program_id": POOL_PROGRAM,
            "base_mint": mint,
            "quote_mint": WSOL_MINT,
            "token_program_id": TOKEN_PROGRAM_ID,
            "venue_label": "FROZEN_SUPPORTED_POOL",
            "lineage_claim": "UNKNOWN_ORIGIN",
        }
        for mint, pool, _ in FIXTURE["candidates"][:count]
    ]


def _adapter(source: str, payload: dict, *, kind: str = FIXTURE_SUCCESS):
    return build_fixture_source_adapter(
        source, fixture_kind=kind, fixture_payload=payload
    )


def _operation(
    source: str,
    request_kind: str,
    rows: list[dict],
    facts: dict,
    *,
    required: bool = True,
    transport_operations: int = 1,
    cursor: dict | None = None,
    fixture_kind: str = FIXTURE_SUCCESS,
    expires_at: str = EXPIRES,
    observed_at: str = NOW,
) -> AcquisitionSourceOperation:
    observations = []
    for row in rows:
        observations.append({
            **row,
            "facts": dict(facts),
            "observed_at": observed_at,
            "expires_at": expires_at,
        })
    payload = {
        "candidate_observations": observations,
        "underlying_operation_count": transport_operations,
    }
    return AcquisitionSourceOperation(
        source_name=source,
        request_kind=request_kind,
        adapter=_adapter(source, payload, kind=fixture_kind),
        required=required,
        expected_transport_operations=transport_operations,
        cursor_range=cursor,
    )


def _dex_nomination_operation(
    rows: list[dict], *, transport_operations: int = 1, stale: bool = False
) -> AcquisitionSourceOperation:
    pairs = [
        {
            "chainId": "solana",
            "pairAddress": row["pool"],
            "baseToken": {"address": row["mint"], "symbol": "MEME"},
            "liquidity": {"usd": 10_000.0},
            "volume": {"m5": 1_000.0, "h1": 4_000.0},
            "txns": {"m5": {"buys": 2, "sells": 1}},
            "pairCreatedAt": 1_700_000_000_000,
        }
        for row in rows
    ]
    adapter = build_dexscreener_adapter(
        enabled=True,
        fixture_transport=dexscreener_fixture_success_transport(
            {"pairs": pairs, "fixture_stale": stale}
        ),
    )
    return AcquisitionSourceOperation(
        source_name="dexscreener",
        request_kind="candidate_nomination",
        adapter=adapter,
        required=False,
        expected_transport_operations=transport_operations,
    )


def _gecko_nomination_operation(
    rows: list[dict], *, failure: bool = False
) -> AcquisitionSourceOperation:
    payload = {
        "data": [
            {
                "id": f"solana_{row['pool']}",
                "attributes": {
                    "chain": "solana",
                    "address": row["pool"],
                    "base_token_address": row["mint"],
                    "reserve_in_usd": 10_000.0,
                    "volume_usd": {"m5": 1_000.0, "h1": 4_000.0},
                    "transactions": {"m5": {"buys": 2, "sells": 1}},
                    "pool_created_at": "2026-07-29T10:00:00+00:00",
                },
            }
            for row in rows
        ]
    }
    transport = (
        geckoterminal_fixture_failure_transport("optional outage")
        if failure
        else geckoterminal_fixture_success_transport(payload)
    )
    return AcquisitionSourceOperation(
        source_name="geckoterminal",
        request_kind="candidate_nomination",
        adapter=build_geckoterminal_adapter(
            enabled=True, fixture_transport=transport
        ),
        required=False,
    )


def _cursor(indexed: str, *, continuity: str = "CONTIGUOUS") -> dict:
    return {
        "indexed_address": indexed,
        "contract_pin": "9c82f61cb711b044a17f770ab8ce9f9bdf78f333",
        "decoder_version": "candidate-integration-v1",
        "direction": "BACKWARD",
        "start_slot": None,
        "start_signature": None,
        "end_slot": 420_000_000,
        "end_signature": f"sig-{indexed}",
        "continuity_state": continuity,
        "cursor_advanced": continuity == "CONTIGUOUS",
        "unresolved_reason": None if continuity == "CONTIGUOUS" else continuity,
    }


def _owner(
    count: int,
    *,
    optional_gecko_failure: bool = False,
    required_pool_failure: str | None = None,
    cursor_continuity: str = "CONTIGUOUS",
    stale_first: bool = False,
    identity_conflict: bool = False,
) -> FrozenAcquisitionTransportOwner:
    rows = _candidate_rows(count)
    dex_rows = deepcopy(rows)
    if identity_conflict and dex_rows:
        dex_rows[0]["pool"] = FIXTURE["candidates"][-1][1]
    operations: list[AcquisitionSourceOperation] = [
        _dex_nomination_operation(
            dex_rows, stale=stale_first
        ),
        _gecko_nomination_operation(
            rows[:1], failure=optional_gecko_failure
        ),
        _operation(
            "solana_rpc", "pumpfun_create_index_signature_page", [], {},
            cursor=_cursor("pump-create-index", continuity=cursor_continuity),
        ),
        _operation(
            "solana_rpc", "pumpfun_migration_signature_page", [], {},
            cursor=_cursor("pump-program", continuity=cursor_continuity),
        ),
        _operation(
            "solana_rpc", "candidate_mint_account_batch", rows,
            {"mint_status": "PASS", "token_program_status": "PASS"},
        ),
    ]
    pool_op = _operation(
        "solana_rpc", "pumpswap_pool_account_batch", rows,
        {"pool_status": "PASS"},
    )
    if required_pool_failure:
        pool_op = AcquisitionSourceOperation(
            source_name="solana_rpc",
            request_kind="pumpswap_pool_account_batch",
            adapter=_StaticFailureAdapter(
                "solana_rpc", "pumpswap_pool_account_batch", required_pool_failure
            ),
            required=True,
        )
    operations.append(pool_op)
    for row in rows:
        operations.append(_operation(
            "solana_rpc", "holder_concentration_reference", [row],
            {"holder_status": "PASS"}, transport_operations=2,
        ))
        operations.append(_operation(
            "goplus", "safety_reference", [row], {"safety_status": "PASS"},
            required=False,
        ))
    return FrozenAcquisitionTransportOwner(tuple(operations))


def _run(
    path: Path,
    *,
    mode: str,
    execution_id: str,
    owner: FrozenAcquisitionTransportOwner,
    renewal_hook=None,
    cancellation_probe=None,
) -> dict:
    return run_candidate_acquisition_integration(
        path,
        mode=mode,
        operator_approved=True,
        transport_owner=owner,
        preflight=_preflight(path),
        execution_id=execution_id,
        owner_id=f"owner:{execution_id}",
        now=NOW,
        renewal_hook=renewal_hook,
        cancellation_probe=cancellation_probe,
    )


def _seed_lease(path: Path, *, execution_id: str, expires_at: str) -> None:
    integration_id = f"seed-integration:{execution_id}"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_integrations(
                   integration_id,execution_id,mode,selection_capacity,owner_id,
                   authorization_confirmed,preflight_hash,policy_json,
                   integration_state,started_at,created_at,updated_at
               ) VALUES (?,?,?,2,?,1,?,'{}','RUNNING',?,?,?)""",
            (
                integration_id, execution_id, MODE_N2, f"owner:{execution_id}",
                "a" * 64, NOW, NOW, NOW,
            ),
        )
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_leases(
                   lease_id,integration_id,execution_id,owner_id,mode,lease_state,
                   heartbeat_at,lease_expires_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?)""",
            (
                f"seed-lease:{execution_id}", integration_id, execution_id,
                f"owner:{execution_id}", MODE_N2, NOW, expires_at, NOW, NOW,
            ),
        )


@pytest.mark.parametrize(
    ("mode", "count", "expected"),
    ((MODE_N2, 4, 2), (MODE_N7, 14, 7)),
)
def test_offline_end_to_end_exact_modes(mode: str, count: int, expected: int) -> None:
    temp, path = _db()
    try:
        report = _run(
            path, mode=mode, execution_id=f"e2e-{expected}", owner=_owner(count)
        )
        assert report["status"] == "COMPLETED"
        assert report["selected_count"] == expected
        assert report["scheduler_jobs_created"] == report["governed_requests_used"]
        assert report["transport_operations_used"] > report["governed_requests_used"]
        assert report["projection_count"] == (2 if expected == 2 else 0)
        assert report["runtime_handoff_count"] == 0
        assert report["lifecycle_started"] is False
        assert report["active_capacity_lock"] == 2
        assert report["active_lease_count"] == 0
        assert report["scheduler_residue_terminalized"] == 0
        assert not any(report["forbidden_table_deltas"].values())
        assert report["integrity"] == "ok"
        assert report["foreign_key_violations"] == 0
        with sqlite3.connect(path) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_transport_operations"
            ).fetchone()[0] == report["transport_operations_used"]
            assert connection.execute(
                "SELECT COALESCE(SUM(bytes_used),0) "
                "FROM printer_candidate_acquisition_transport_operations"
            ).fetchone()[0] == report["bytes_used"]
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*),MIN(cursor_version),MAX(cursor_version) "
                "FROM printer_candidate_acquisition_cursors"
            ).fetchone() == (2, 1, 1)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"e2e-{expected}"
        ) == report
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, report["manifest_id"])
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("cli_mode", "mode", "count", "expected", "expected_jobs", "expected_calls"),
    (
        (CLI_MODE_N2, MODE_N2, 4, 2, 16, 13),
        (CLI_MODE_N7, MODE_N7, 14, 7, 38, 28),
    ),
)
def test_public_command_dispatches_canonical_offline_path(
    capsys, monkeypatch, cli_mode: str, mode: str, count: int, expected: int,
    expected_jobs: int, expected_calls: int,
) -> None:
    temp, path = _db()
    try:
        seen = {}
        network = _CanonicalMockNetworkTransport(count)
        real_run = command.run_candidate_acquisition_only
        def capture_owner(**kwargs):
            seen["owner"] = kwargs["transport_owner"]
            return real_run(**kwargs)
        monkeypatch.setattr(command, "run_candidate_acquisition_only", capture_owner)
        rc = command.main(
            [cli_mode, "--operator-approved"],
            acquisition_environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?key=secret"},
            acquisition_one_shot_transport=network,
            acquisition_preflight=_preflight(path),
            acquisition_execution_id=f"cli-{expected}",
            acquisition_now=NOW,
            acquisition_db_path=path,
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["mode"] == mode
        assert payload["selected_count"] == expected, json.dumps(payload, indent=2)
        assert payload["projection_count"] == (2 if expected == 2 else 0)
        assert payload["runtime_handoff_count"] == 0
        assert payload["lifecycle_started"] is False
        assert payload["scheduler_jobs_created"] == expected_jobs
        assert payload["scheduler_jobs_created"] == payload["governed_requests_used"]
        assert payload["transport_operations_used"] == expected_calls
        assert payload["transport_operations_used"] == len(network.calls)
        assert payload["active_lease_count"] == 0
        assert payload["scheduler_residue_terminalized"] == 0
        assert not any(payload["forbidden_table_deltas"].values())
        assert isinstance(seen["owner"], LiveCandidateAcquisitionTransportOwner)
        assert "secret" not in json.dumps(payload)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"cli-{expected}"
        ) == payload
        call_count = len(network.calls)
        assert command.main(
            [cli_mode, "--operator-approved"],
            acquisition_environment={
                "PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?key=secret"
            },
            acquisition_one_shot_transport=network,
            acquisition_preflight=_preflight(path),
            acquisition_execution_id=f"cli-{expected}",
            acquisition_now=NOW,
            acquisition_db_path=path,
        ) == 0
        assert json.loads(capsys.readouterr().out) == payload
        assert len(network.calls) == call_count
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, payload["manifest_id"])
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("environment", "reason"),
    (
        ({}, "ACQUISITION_SOLANA_RPC_URL_REQUIRED"),
        ({"PRINTER_SOLANA_RPC_URL": "not a url"}, "ACQUISITION_SOLANA_RPC_URL_MALFORMED"),
        ({"PRINTER_SOLANA_RPC_URL": "http://rpc.example.invalid"}, "ACQUISITION_SOLANA_RPC_HTTPS_REQUIRED"),
        ({"PRINTER_SOLANA_RPC_URL": "https://user:secret@rpc.example.invalid"}, "ACQUISITION_SOLANA_RPC_URL_MALFORMED"),
    ),
)
def test_public_command_blocks_invalid_live_configuration_before_preflight(
    capsys, monkeypatch, environment: dict[str, str], reason: str
) -> None:
    monkeypatch.setattr(
        command, "build_activation_preflight",
        lambda **_kwargs: pytest.fail("preflight must not run for invalid transport configuration"),
    )
    rc = command.main(
        [CLI_MODE_N2, "--operator-approved"], acquisition_environment=environment
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error_message"] == reason
    assert payload["action_run_id"] is None
    assert payload["source_calls"] == 0
    assert payload["scheduler_runtime_calls"] == 0
    assert "secret" not in json.dumps(payload)


def test_public_command_requires_approval_before_configuration(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        command, "build_live_candidate_acquisition_transport_owner",
        lambda **_kwargs: pytest.fail("configuration must not load before approval"),
    )
    assert command.main([CLI_MODE_N2]) == 1
    assert json.loads(capsys.readouterr().err)["error_message"] == (
        "EXPLICIT_OPERATOR_APPROVAL_REQUIRED"
    )


def test_unresolved_required_transport_blocks_during_construction() -> None:
    with pytest.raises(
        LiveAcquisitionConfigurationError,
        match="ACQUISITION_REQUIRED_TRANSPORT_UNRESOLVED",
    ):
        build_live_candidate_acquisition_transport_owner(
            environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid"},
            transport=object(),
        )


def test_one_shot_transport_closes_response_and_reports_exact_bytes(monkeypatch) -> None:
    class Response:
        closed = False
        def __enter__(self): return self
        def __exit__(self, *_args): self.closed = True
        def read(self, _limit): return b'{"ok":true}'
    response = Response(); calls = []
    monkeypatch.setattr(
        live_transport.url_request, "urlopen",
        lambda _request, timeout: calls.append(timeout) or response,
    )
    result = UrllibCandidateAcquisitionOneShotTransport().http_json(
        url="https://provider.example.invalid/path", headers={}, timeout_seconds=3.0,
        byte_ceiling=100, endpoint_role="FIXED_PROVIDER_ROLE",
    )
    assert result.payload == {"ok": True}
    assert result.bytes_used == len(b'{"ok":true}')
    assert response.closed is True
    assert calls == [3.0]


@pytest.mark.parametrize(
    ("body", "expected"),
    ((b"{", "SOURCE_MALFORMED"), (b"x" * 11, "RESPONSE_BYTE_CEILING")),
)
def test_one_shot_transport_malformed_and_byte_failure_are_redacted(
    monkeypatch, body: bytes, expected: str
) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self, _limit): return body
    monkeypatch.setattr(live_transport.url_request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().http_json(
            url="https://provider.example.invalid/path?api-key=secret", headers={},
            timeout_seconds=1.0, byte_ceiling=10, endpoint_role="REDACTED_ROLE",
        )
    assert caught.value.code == expected
    assert "secret" not in str(caught.value)
    assert "provider.example" not in str(caught.value)


def test_one_shot_transport_timeout_has_one_attempt_and_no_url_secret(monkeypatch) -> None:
    calls = []
    def timeout(*_args, **_kwargs):
        calls.append(1)
        raise TimeoutError("api-key=secret")
    monkeypatch.setattr(live_transport.url_request, "urlopen", timeout)
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().rpc_json(
            rpc_url="https://rpc.example.invalid/path?api-key=secret",
            method="getMultipleAccounts", params=[[]], timeout_seconds=1.0,
            byte_ceiling=100, endpoint_role="RPC_BATCH",
        )
    assert caught.value.code == "SOURCE_TIMEOUT"
    assert calls == [1]
    assert "secret" not in str(caught.value)


def test_one_shot_transport_auth_failure_closes_and_accounts_redacted_body(
    monkeypatch,
) -> None:
    body = b"credential=secret"
    failure = live_transport.url_error.HTTPError(
        "https://rpc.example.invalid/path?api-key=secret", 401, "unauthorized", {},
        io.BytesIO(body),
    )
    monkeypatch.setattr(
        live_transport.url_request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().rpc_json(
            rpc_url="https://rpc.example.invalid/path?api-key=secret",
            method="getMultipleAccounts", params=[[]], timeout_seconds=1.0,
            byte_ceiling=100, endpoint_role="RPC_BATCH",
        )
    assert caught.value.code == "SOURCE_AUTH_UNAVAILABLE"
    assert caught.value.bytes_used == len(body)
    assert caught.value.operation_kind == "getMultipleAccounts"
    assert failure.fp is None or failure.fp.closed
    assert "secret" not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(("mode", "expected_cap"), ((MODE_N2, 4), (MODE_N7, 14)))
def test_live_owner_declares_same_approved_source_plan(mode: str, expected_cap: int) -> None:
    owner = build_live_candidate_acquisition_transport_owner(
        environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?api-key=secret"}
    )
    operations = owner.operations(mode=mode, policy=MODE_POLICIES[mode], execution_id="plan")
    assert [item.request_kind for item in operations[:4]] == [
        "candidate_nomination", "candidate_nomination",
        "candidate_market_batch", "candidate_market_batch",
    ]
    assert all(item.expected_transport_operations == 0 for item in operations[2:4])
    declared = {(item.source_name, item.request_kind) for item in operations}
    assert {
        ("dexscreener", "candidate_nomination"),
        ("geckoterminal", "candidate_nomination"),
        ("solana_rpc", "pumpfun_create_index_signature_page"),
        ("solana_rpc", "pumpfun_migration_signature_page"),
        ("solana_rpc", "candidate_mint_account_batch"),
        ("solana_rpc", "pumpswap_pool_account_batch"),
        ("solana_rpc", "holder_concentration_reference"),
        ("goplus", "safety_reference"),
    }.issubset(declared)
    assert all(source not in {"dextools", "pumpportal", "birdeye"} for source, _ in declared)
    holders = [item for item in operations if item.request_kind == "holder_concentration_reference"]
    expected_selection = MODE_POLICIES[mode]["selection_capacity"]
    assert len(holders) == expected_selection
    assert all(item.expected_transport_operations == 2 for item in holders)
    create_transactions = [
        item for item in operations if item.request_kind == "pumpfun_create_index_transaction"
    ]
    migration_transactions = [
        item for item in operations if item.request_kind == "pumpfun_migration_transaction"
    ]
    expected_transactions = expected_selection
    assert len(create_transactions) == expected_transactions
    assert len(migration_transactions) == expected_transactions
    solana_operations = [item for item in operations if item.source_name == "solana_rpc"]
    assert len(solana_operations) <= 30
    assert len(operations) <= MODE_POLICIES[mode]["scheduler_job_ceiling"]
    assert sum(item.expected_transport_operations for item in operations) <= (
        MODE_POLICIES[mode]["transport_operation_ceiling"]
    )
    # No operation owns a provider loop. The only two-call composites are the
    # fixed Dex nomination/market pair and fixed holder largest/supply pair.
    assert max(item.expected_transport_operations for item in operations) == 2
    assert owner.configuration.redacted_rpc_host == "rpc.example.invalid"
    assert "secret" not in repr(owner.configuration)


def test_response_byte_and_row_ceilings_fail_closed() -> None:
    temp_b, path_b = _db(); temp_r, path_r = _db()
    try:
        byte_ops = list(_owner(4).frozen_operations)
        byte_ops[0] = AcquisitionSourceOperation(
            source_name="dexscreener", request_kind="candidate_nomination",
            required=False, expected_transport_operations=1,
            adapter=_adapter("dexscreener", {
                "candidate_observations": [], "underlying_operation_count": 1,
                "response_bytes": 16 * 1024 * 1024 + 1,
            }),
        )
        byte_report = _run(path_b, mode=MODE_N2, execution_id="byte-ceiling",
                           owner=FrozenAcquisitionTransportOwner(tuple(byte_ops)))
        assert byte_report["first_terminal_cause"] == "RESPONSE_BYTE_CEILING"

        row_ops = list(_owner(4).frozen_operations)
        row_ops[0] = _operation(
            "dexscreener", "candidate_nomination",
            [{"mint": f"mint-{index}", "pool": f"pool-{index}"} for index in range(65)],
            {"market_status": "PASS"}, required=False,
        )
        row_report = _run(path_r, mode=MODE_N2, execution_id="row-ceiling",
                          owner=FrozenAcquisitionTransportOwner(tuple(row_ops)))
        assert row_report["first_terminal_cause"] == "OBSERVATION_ROW_CEILING"
    finally:
        temp_b.cleanup(); temp_r.cleanup()


@pytest.mark.parametrize(
    "failure_type",
    ("SOURCE_AUTH_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_MALFORMED"),
)
def test_required_source_failure_categories_do_not_retry(failure_type: str) -> None:
    temp, path = _db()
    try:
        report = _run(path, mode=MODE_N2, execution_id=f"failure-{failure_type}",
                      owner=_owner(4, required_pool_failure=failure_type))
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        assert report["automatic_retry_created"] is False
        assert report["successor_created"] is False
        assert report["restart_created"] is False
    finally:
        temp.cleanup()


def test_authorization_is_required_before_any_write() -> None:
    temp, path = _db()
    try:
        before = path.read_bytes()
        with pytest.raises(
            CandidateAcquisitionIntegrationError,
            match="EXPLICIT_OPERATOR_APPROVAL_REQUIRED",
        ):
            run_candidate_acquisition_integration(
                path, mode=MODE_N2, operator_approved=False,
                transport_owner=_owner(4), preflight=_preflight(path),
                execution_id="unauthorized", owner_id="owner", now=NOW,
            )
        assert path.read_bytes() == before

        invalid = _preflight(path)
        invalid["database_sha256"] = "0" * 64
        before = path.read_bytes()
        with pytest.raises(
            CandidateAcquisitionIntegrationError,
            match="PREFLIGHT_DATABASE_HASH_MISMATCH",
        ):
            run_candidate_acquisition_integration(
                path, mode=MODE_N2, operator_approved=True,
                transport_owner=_owner(4), preflight=invalid,
                execution_id="bad-preflight", owner_id="owner", now=NOW,
            )
        assert path.read_bytes() == before
    finally:
        temp.cleanup()


def test_concurrent_lease_blocks_cleanly_and_expired_lease_recovers_once() -> None:
    temp_h, path_h = _db()
    temp_e, path_e = _db()
    try:
        _seed_lease(
            path_h, execution_id="foreign-active",
            expires_at="2026-07-29T13:00:00+00:00",
        )
        blocked = _run(
            path_h, mode=MODE_N2, execution_id="lease-blocked", owner=_owner(4)
        )
        assert blocked["status"] == "BLOCKED"
        assert blocked["first_terminal_cause"] == "ACQUISITION_LEASE_ALREADY_HELD"
        assert blocked["lease_cleanup"]["lease_acquired"] is False
        with sqlite3.connect(path_h) as connection:
            assert connection.execute(
                "SELECT integration_state FROM printer_candidate_acquisition_integrations "
                "WHERE execution_id='lease-blocked'"
            ).fetchone()[0] == "TERMINAL"

        _seed_lease(
            path_e, execution_id="foreign-expired",
            expires_at="2026-07-29T11:00:00+00:00",
        )
        recovered = _run(
            path_e, mode=MODE_N2, execution_id="lease-recovered", owner=_owner(4)
        )
        assert recovered["status"] == "COMPLETED"
        assert recovered["active_lease_count"] == 0
        with sqlite3.connect(path_e) as connection:
            row = connection.execute(
                """SELECT terminal_status,first_terminal_cause
                   FROM printer_candidate_acquisition_integrations
                   WHERE execution_id='foreign-expired'"""
            ).fetchone()
            assert row == ("BLOCKED", "LEASE_EXPIRED_RECOVERED")
    finally:
        temp_h.cleanup(); temp_e.cleanup()


def test_n_minus_one_is_honest_insufficient_pool() -> None:
    temp, path = _db()
    try:
        report = _run(path, mode=MODE_N2, execution_id="n-minus-one", owner=_owner(1))
        assert report["status"] == "BLOCKED"
        assert report["foundation_report"]["failure_family"] == "INSUFFICIENT_ELIGIBLE_POOL"
        assert report["manifest_id"] is None
    finally:
        temp.cleanup()


def test_optional_outage_degrades_but_required_outage_stops() -> None:
    temp_a, path_a = _db()
    temp_b, path_b = _db()
    try:
        optional = _run(
            path_a, mode=MODE_N2, execution_id="optional-outage",
            owner=_owner(4, optional_gecko_failure=True),
        )
        assert optional["status"] == "COMPLETED"
        assert optional["foundation_report"]["source_failures"]
        required = _run(
            path_b, mode=MODE_N2, execution_id="required-outage",
            owner=_owner(4, required_pool_failure="rpc_transport_failure"),
        )
        assert required["status"] == "BLOCKED"
        assert required["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        assert required["manifest_id"] is None
    finally:
        temp_a.cleanup(); temp_b.cleanup()


def test_budget_gap_unsupported_identity_stale_and_shortage_are_distinct() -> None:
    cases = (
        ("gap", _owner(4, cursor_continuity="GAPPED"), "CURSOR_CONTINUITY_GAPPED"),
        (
            "unsupported", _owner(4, required_pool_failure="unsupported_contract_layout"),
            "UNSUPPORTED_CONTRACT",
        ),
    )
    for execution_id, owner, cause in cases:
        temp, path = _db()
        try:
            report = _run(path, mode=MODE_N2, execution_id=execution_id, owner=owner)
            assert report["status"] == "BLOCKED"
            assert report["first_terminal_cause"] == cause
            assert report["manifest_id"] is None
            if execution_id == "gap":
                with sqlite3.connect(path) as connection:
                    persisted = connection.execute(
                        """SELECT COUNT(*) FROM printer_candidate_acquisition_work
                           WHERE json_extract(cursor_range_json,'$.continuity_state')='GAPPED'"""
                    ).fetchone()[0]
                    assert persisted == 2
                    assert connection.execute(
                        "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors"
                    ).fetchone()[0] == 0
        finally:
            temp.cleanup()

    temp, path = _db()
    try:
        ops = list(_owner(4).frozen_operations)
        ops.insert(1, ops[0])
        report = _run(
            path, mode=MODE_N2, execution_id="budget",
            owner=FrozenAcquisitionTransportOwner(tuple(ops)),
        )
        assert report["first_terminal_cause"] == "SOURCE_REQUEST_BUDGET_EXHAUSTED"
        assert report["manifest_id"] is None
    finally:
        temp.cleanup()

    temp_i, path_i = _db()
    temp_s, path_s = _db()
    try:
        identity = _run(
            path_i, mode=MODE_N2, execution_id="identity",
            owner=_owner(2, identity_conflict=True),
        )
        assert identity["status"] == "BLOCKED"
        assert identity["foundation_report"]["failure_family"] == "IDENTITY_MERGE_FAILURE"
        stale = _run(
            path_s, mode=MODE_N2, execution_id="stale",
            owner=_owner(2, stale_first=True),
        )
        assert stale["status"] == "BLOCKED"
        assert stale["manifest_id"] is None
        assert stale["foundation_report"]["stale_or_expired_evidence_count"] >= 1
    finally:
        temp_i.cleanup(); temp_s.cleanup()


def test_cancellation_renewal_failure_and_idempotent_replay_release_lease() -> None:
    temp_c, path_c = _db()
    temp_r, path_r = _db()
    temp_i, path_i = _db()
    try:
        cancelled = _run(
            path_c, mode=MODE_N2, execution_id="cancelled", owner=_owner(4),
            cancellation_probe=lambda ordinal: "operator stop" if ordinal == 1 else None,
        )
        assert cancelled["status"] == "CANCELLED"
        assert cancelled["first_terminal_cause"] == "ACQUISITION_CANCELLED"
        assert cancelled["active_lease_count"] == 0

        def fail_renewal(ordinal: int) -> None:
            if ordinal == 1:
                raise CandidateAcquisitionIntegrationError("LEASE_RENEWAL_UNCONFIRMED")

        renewal = _run(
            path_r, mode=MODE_N2, execution_id="renewal", owner=_owner(4),
            renewal_hook=fail_renewal,
        )
        assert renewal["status"] == "BLOCKED"
        assert renewal["first_terminal_cause"] == "LEASE_RENEWAL_UNCONFIRMED"
        assert renewal["active_lease_count"] == 0

        first = _run(path_i, mode=MODE_N2, execution_id="idempotent", owner=_owner(4))
        with sqlite3.connect(path_i) as connection:
            source_before = connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
            jobs_before = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]
        second = _run(path_i, mode=MODE_N2, execution_id="idempotent", owner=_owner(4))
        assert second == first
        with sqlite3.connect(path_i) as connection:
            assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == source_before
            assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == jobs_before
    finally:
        temp_c.cleanup(); temp_r.cleanup(); temp_i.cleanup()


def test_atomic_selection_cooldown_recheck_blocks_manifest() -> None:
    temp, path = _db()
    try:
        mint, pool, _ = FIXTURE["candidates"][0]
        with sqlite3.connect(path) as connection:
            connection.execute(
                """INSERT INTO printer_selection_rotation_state(
                       token_mint,pair_address,last_selected_batch_id,
                       last_selected_batch_seq,last_selected_at,
                       last_evidence_fingerprint_json,selection_count,created_at,updated_at
                   ) VALUES (?,?,?,?,?,'{}',1,?,?)""",
                (mint, pool, "prior", 1, NOW, NOW, NOW),
            )
        report = _run(
            path, mode=MODE_N2, execution_id="cooldown", owner=_owner(2)
        )
        assert report["status"] == "BLOCKED"
        assert report["manifest_id"] is None
        assert report["foundation_report"]["exclusions_by_funnel_stage"]["IDENTITY_AVAILABLE"] >= 1
    finally:
        temp.cleanup()


def test_atomic_active_tracking_recheck_blocks_manifest() -> None:
    temp, path = _db()
    try:
        mint, pool, _ = FIXTURE["candidates"][0]
        with sqlite3.connect(path) as connection:
            token_id = connection.execute(
                "INSERT INTO printer_tokens(token_mint,token_status) "
                "VALUES (?,'TRACK_NORMAL')",
                (mint,),
            ).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) "
                "VALUES (?,?,?)",
                (token_id, pool, mint),
            ).lastrowid
            connection.execute(
                """INSERT INTO printer_tracking_queue(
                       token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                       next_check_at,last_checked_at,queue_status,source_status,
                       data_quality_label
                   ) VALUES (?,?,'TRACK_NORMAL','REFRESH','active fixture',?,?,
                             'READY','COMPLETE','CLEAN_DATA')""",
                (token_id, pair_id, NOW, NOW),
            )
        report = _run(
            path, mode=MODE_N2, execution_id="active-tracking", owner=_owner(2)
        )
        assert report["status"] == "BLOCKED"
        assert report["manifest_id"] is None
        assert report["foundation_report"]["exclusions_by_funnel_stage"][
            "IDENTITY_AVAILABLE"
        ] >= 1
    finally:
        temp.cleanup()
