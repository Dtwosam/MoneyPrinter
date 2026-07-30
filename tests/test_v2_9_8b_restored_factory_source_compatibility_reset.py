"""Frozen offline proof for the restored-factory source compatibility reset."""

from __future__ import annotations

import ast
import base64
from copy import deepcopy
import inspect
from pathlib import Path
import sqlite3

import pytest

from printer_v1.contracts.enums import SourceStatus
from printer_v1.db.migrate import apply_migrations, canonical_migration_names
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.readiness_source_contract_preflight import (
    build_readiness_source_contract_preflight,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
    build_direct_pump_migration_transport,
    normalize_direct_pump_migration_response,
)
from printer_v1.sources.jupiter_quote import (
    JUPITER_QUOTE_API_URL,
    normalize_jupiter_quote_response,
)
from printer_v1.sources.operational_source_contracts import (
    JUPITER_KEYLESS_QUOTE_URL,
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    ORDINARY_OPERATIONAL_SOURCE_CONTRACTS,
    SolanaRpcConfigurationError,
    redact_https_url,
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_migration import (
    MIGRATION_PROVENANCE,
    verify_graduation_from_transaction,
)
from printer_v1.sources.pumpfun_direct import _b58decode
from printer_v1.sources.pumpswap_graduated_registry import (
    lookup_graduated_candidate,
)
from test_v2_9_8b_candidate_acquisition_foundation import (
    _pinned_migration_fixture,
)


_SIGNATURE = (
    "5NarrowDirectPumpMigrationFinalizedSignature"
    "111111111111111111111111111111111111111111111111"
)
_NOW = "2026-07-30T18:00:00+00:00"
_OTHER_MINT = "GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump"


def _wrong_program_payload(payload: dict) -> dict:
    changed = deepcopy(payload)
    changed["result"]["transaction"]["message"]["accountKeys"][23] = (
        "11111111111111111111111111111111"
    )
    return changed


def _quote(
    input_mint: str,
    output_mint: str,
    *,
    amount: str = "1000000",
    slippage: int = 50,
) -> dict:
    return {
        "inputMint": input_mint,
        "inAmount": amount,
        "outputMint": output_mint,
        "outAmount": "900000",
        "otherAmountThreshold": "895500",
        "swapMode": "ExactIn",
        "slippageBps": slippage,
        "platformFee": None,
        "priceImpactPct": "0.001",
        "routePlan": [
            {
                "swapInfo": {
                    "ammKey": "AMM111111111111111111111111111111111111111",
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "inAmount": amount,
                    "outAmount": "900000",
                },
                "percent": 100,
            }
        ],
        "_requested_input_mint": input_mint,
        "_requested_output_mint": output_mint,
        "_requested_amount": amount,
        "_requested_slippage_bps": slippage,
    }


def _verifier_factory(tx: dict, infos: dict):
    def factory(mint: str, signature: str):
        verification = verify_graduation_from_transaction(
            tx, infos, expected_mint=mint
        )

        def transport(_context):
            if not verification["verified"]:
                return {
                    "fixture_status": "failure",
                    "failure_type": "frozen_exact_verification_failed",
                    "failure_message": str(verification["reason"]),
                }
            return {
                "pumpswap_confirmation": verification[
                    "pumpswap_confirmation"
                ],
                "pumpswap_resolution": verification["pumpswap_resolution"],
                "pump_migration_proof": verification["pump_migration_proof"],
                "migration_provenance": MIGRATION_PROVENANCE,
                "migration_signature": signature,
                "migration_block_time": verification[
                    "migration_block_time"
                ],
                "migration_slot": verification["migration_slot"],
            }

        return transport

    return factory


def test_ordinary_runtime_has_no_pumpportal_dependency_or_secret_path() -> None:
    source = inspect.getsource(command)
    tree = ast.parse(source)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    assert not any("pumpportal" in value.casefold() for value in imports)
    assert "build_pumpportal_migration_transport" not in source
    ordinary = ORDINARY_OPERATIONAL_SOURCE_CONTRACTS["pumpportal"]
    assert ordinary.classification == "DEFERRED"
    assert ordinary.active_runtime is False
    for forbidden in (
        "PUMPPORTAL_API_KEY",
        "PUMPPORTAL_WALLET",
        "PRIVATE_KEY",
        "FUND_WALLET",
    ):
        assert forbidden not in source.upper()


def test_direct_pump_event_reaches_exact_verification_and_registry(tmp_path) -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    db = tmp_path / "frozen-migration-049.sqlite3"
    apply_migrations(db)

    calls: list[str] = []

    def transport(context):
        calls.append(context.request.request_kind)
        if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {
                "result": [
                    {
                        "signature": _SIGNATURE,
                        "slot": tx["slot"],
                        "err": None,
                        "confirmationStatus": "finalized",
                    }
                ]
            }
        if context.request.request_kind == TRANSACTION_REQUEST_KIND:
            assert context.request.payload["signature"] == _SIGNATURE
            return {"result": tx}
        raise AssertionError(context.request.request_kind)

    report = run_direct_migration_discovery(
        db,
        migration_transport=transport,
        verifier_transport_factory=_verifier_factory(tx, infos),
        now=_NOW,
        collection_rounds=1,
        settle_seconds=0.0,
        reverify_on_transient=False,
        reverify_settle_seconds=0.0,
    )
    assert calls == [SIGNATURE_PAGE_REQUEST_KIND, TRANSACTION_REQUEST_KIND]
    assert report["confirmed_count"] == 1
    assert report["migration_intake"]["cursor_used"] is False
    assert report["source_operation_ledger"]["source_requests"] == 3
    assert report["source_operation_ledger"]["transport_operations"] == 4
    assert report["source_operation_ledger"][
        "operation_accounting_reconciled"
    ]
    assert report["forbidden_delta_total"] == 0

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        row = lookup_graduated_candidate(connection, mint)
        assert row["pumpswap_pool"] == pool
        assert row["migration_provenance"] == MIGRATION_PROVENANCE
        for table in (
            "printer_candidate_acquisition_runs",
            "printer_candidate_acquisition_cursors",
            "printer_candidate_recovery_attempts",
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists:
                assert connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0] == 0
        assert [
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ] == list(canonical_migration_names())
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: None,
        lambda payload: {"result": None},
        lambda payload: {"result": "malformed"},
        lambda payload: {"error": {"code": -32000}},
        lambda payload: {
            "result": {
                **payload["result"],
                "transaction": {
                    "message": {
                        **payload["result"]["transaction"]["message"],
                        "instructions": [],
                    }
                },
            }
        },
        _wrong_program_payload,
    ],
)
def test_direct_pump_null_malformed_and_unsupported_fail_closed(mutator) -> None:
    tx, _infos, _mint, _pool = _pinned_migration_fixture()
    result = normalize_direct_pump_migration_response(
        mutator({"result": deepcopy(tx)}),
        request_kind=TRANSACTION_REQUEST_KIND,
        expected_signature=_SIGNATURE,
    )
    assert result.source_status == SourceStatus.FAILED
    assert result.failure_type


def test_wrong_pool_owner_and_base_mint_fail_exact_join() -> None:
    tx, infos, mint, pool = _pinned_migration_fixture()
    wrong_owner = deepcopy(infos)
    wrong_owner[pool]["owner"] = "11111111111111111111111111111111"
    assert not verify_graduation_from_transaction(
        tx, wrong_owner, expected_mint=mint
    )["verified"]

    wrong_pool = deepcopy(tx)
    wrong_pool["transaction"]["message"]["accountKeys"][9] = (
        "11111111111111111111111111111111"
    )
    assert not verify_graduation_from_transaction(
        wrong_pool, infos, expected_mint=mint
    )["verified"]

    wrong_base = deepcopy(infos)
    raw = bytearray(base64.b64decode(wrong_base[pool]["data"][0]))
    raw[43:75] = _b58decode(_OTHER_MINT)
    wrong_base[pool]["data"][0] = base64.b64encode(bytes(raw)).decode()
    assert not verify_graduation_from_transaction(
        tx, wrong_base, expected_mint=mint
    )["verified"]


def test_jupiter_entry_exit_exact_and_fail_closed() -> None:
    wsol = "So11111111111111111111111111111111111111112"
    mint = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
    entry = normalize_jupiter_quote_response(
        _quote(wsol, mint), request_kind="paper_quote_realism"
    )
    exit_quote = normalize_jupiter_quote_response(
        _quote(mint, wsol), request_kind="paper_quote_realism"
    )
    assert entry.source_status == SourceStatus.COMPLETE
    assert exit_quote.source_status == SourceStatus.COMPLETE
    assert entry.normalized_payload["input_mint"] == wsol
    assert exit_quote.normalized_payload["output_mint"] == wsol
    assert JUPITER_QUOTE_API_URL == JUPITER_KEYLESS_QUOTE_URL

    intermediate = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    linear_multi_hop = _quote(wsol, mint)
    linear_multi_hop["routePlan"] = [
        {
            "swapInfo": {
                "ammKey": "AMM111111111111111111111111111111111111111",
                "inputMint": wsol,
                "outputMint": intermediate,
                "inAmount": "1000000",
                "outAmount": "950000",
            },
            "percent": 100,
        },
        {
            "swapInfo": {
                "ammKey": "AMM222222222222222222222222222222222222222",
                "inputMint": intermediate,
                "outputMint": mint,
                "inAmount": "950000",
                "outAmount": "900000",
            },
            "percent": 100,
        },
    ]
    assert normalize_jupiter_quote_response(
        linear_multi_hop, request_kind="paper_quote_realism"
    ).source_status == SourceStatus.COMPLETE

    malformed_cases = [
        None,
        {"fixture_status": "rate_limited"},
        {"fixture_status": "no_route"},
        {**_quote(wsol, mint), "inputMint": mint},
        {**_quote(wsol, mint), "routePlan": []},
        {
            **linear_multi_hop,
            "routePlan": [
                linear_multi_hop["routePlan"][0],
                {
                    **linear_multi_hop["routePlan"][1],
                    "swapInfo": {
                        **linear_multi_hop["routePlan"][1]["swapInfo"],
                        "inAmount": "949999",
                    },
                },
            ],
        },
    ]
    for payload in malformed_cases:
        result = normalize_jupiter_quote_response(
            payload, request_kind="paper_quote_realism"
        )
        assert result.source_status == SourceStatus.FAILED


def test_solana_configuration_is_https_validated_and_secret_redacted() -> None:
    fallback = resolve_solana_rpc_configuration({})
    assert fallback.url == OFFICIAL_SOLANA_PUBLIC_RPC_URL
    configured = resolve_solana_rpc_configuration(
        {
            "PRINTER_SOLANA_RPC_URL": (
                "https://rpc.provider.invalid/account/private-token?api-key=secret"
            )
        }
    )
    assert configured.origin == "OPERATOR_CONFIGURED_APPROVED_HTTPS"
    assert "private-token" not in configured.redacted_identity
    assert "secret" not in configured.redacted_identity
    assert configured.redacted_identity.endswith(
        "/<redacted-path>?<redacted-query>"
    )
    with pytest.raises(SolanaRpcConfigurationError):
        redact_https_url("http://api.mainnet.solana.com")
    with pytest.raises(SolanaRpcConfigurationError):
        resolve_solana_rpc_configuration(
            {"PRINTER_SOLANA_RPC_URL": "https://user:secret@rpc.invalid"}
        )
    with pytest.raises(SolanaRpcConfigurationError):
        build_direct_pump_migration_transport(
            rpc_url="http://api.mainnet.solana.com"
        )


def test_complete_preflight_missing_mandatory_and_conditional_truth() -> None:
    ready = build_readiness_source_contract_preflight(environment={})
    assert ready["status"] == "READY"
    assert set(ready["ordinary_runtime_dependencies"]) == {
        name
        for name, contract in ORDINARY_OPERATIONAL_SOURCE_CONTRACTS.items()
        if contract.active_runtime
    }
    assert ready["sources"]["helius_holder_backup"]["classification"] == (
        "CONDITIONAL"
    )
    assert ready["sources"]["helius_holder_backup"]["available"] is False
    blocked = build_readiness_source_contract_preflight(
        environment={},
        runtime_overrides={
            "source_contracts": {"pump_program_contract": None}
        },
    )
    assert blocked["status"] == "BLOCKED"
    assert "MANDATORY_SOURCE_CONTRACT_MISSING:pump_program_contract" in blocked[
        "issues"
    ]
    assert any(
        issue.startswith("ACTIVE_RUNTIME_DEPENDENCY_MISSING_FROM_PREFLIGHT:")
        for issue in blocked["issues"]
    )
