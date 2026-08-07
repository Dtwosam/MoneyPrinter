#!/usr/bin/env python3
"""Checkpoint 8 controlling-proof safety shell.

This file intentionally owns only the proof-only safety envelope at this stage:
the process-local network tripwire and the atomic one-shot attempt claim.

It does not construct fixtures, start Printer runtime work, or execute the
controlling proof. Those entry responsibilities remain fail-closed until the
subsequent Checkpoint 8 harness-wiring slice is proven.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import struct
import subprocess
from types import SimpleNamespace
from typing import Any

from printer_v1.db.migrate import (
    apply_migrations,
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)
from printer_v1.operator_cli import (
    window_15m_disposable_public_composition_proof as proof,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
)

from printer_v1.operator_cli.operational_memory_factory_command import (
    report_only,
    run_operational_campaign,
)

from printer_v1.sources.pumpfun_direct import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    CREATE_DISCRIMINATOR,
    EVENT_AUTHORITY_ID,
    GLOBAL_ID,
    MINT_AUTHORITY_ID,
    PUMP_PROGRAM_ID,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_METADATA_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    derive_program_address,
)

from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND as DIRECT_MIGRATION_SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND as DIRECT_MIGRATION_TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.pump_contracts import (
    PUMP_EVENT_AUTHORITY_ID,
    PUMP_GLOBAL_ID,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMP_WITHDRAW_AUTHORITY_ID,
    PUMPSWAP_AMM_PROGRAM_ID,
    PUMPSWAP_EVENT_AUTHORITY_ID,
    PUMPSWAP_GLOBAL_CONFIG_ID,
    TOKEN_2022_PROGRAM_ID,
    WSOL_MINT,
)


_ATTEMPT_SENTINEL_NAME = "checkpoint8-controlling-attempt.json"


class Checkpoint8ControllingProofError(RuntimeError):
    """Fail-closed controlling-proof harness fault."""


class Checkpoint8NetworkTripwireError(Checkpoint8ControllingProofError):
    """Raised when the proof process attempts an external network operation."""


class Checkpoint8NetworkAttempt:
    """Minimal import-safe record for one blocked network attempt."""

    __slots__ = ("operation", "target")

    def __init__(self, *, operation: str, target: str) -> None:
        self.operation = operation
        self.target = target


def _redacted_target(value: Any) -> str:
    if isinstance(value, tuple) and value:
        host = str(value[0])
        port = value[1] if len(value) > 1 else None
        family = "IPV6" if ":" in host else "IP"
        return f"{family}:{port if port is not None else 'UNKNOWN'}"
    return type(value).__name__


class Checkpoint8NetworkTripwire:
    """Process-local socket tripwire used only by the C8 controlling harness."""

    def __init__(self) -> None:
        self.attempts: list[Checkpoint8NetworkAttempt] = []
        self._installed = False
        self._original_create_connection = None
        self._original_connect = None
        self._original_connect_ex = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def _record_and_fail(self, operation: str, target: Any) -> None:
        self.attempts.append(
            Checkpoint8NetworkAttempt(
                operation=operation,
                target=_redacted_target(target),
            )
        )
        raise Checkpoint8NetworkTripwireError(
            "CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN"
        )

    def __enter__(self) -> "Checkpoint8NetworkTripwire":
        if self._installed:
            raise Checkpoint8NetworkTripwireError(
                "CHECKPOINT8_NETWORK_TRIPWIRE_ALREADY_INSTALLED"
            )

        self._original_create_connection = socket.create_connection
        self._original_connect = socket.socket.connect
        self._original_connect_ex = socket.socket.connect_ex
        tripwire = self

        def blocked_create_connection(address, *args, **kwargs):
            del args, kwargs
            tripwire._record_and_fail("socket.create_connection", address)

        def blocked_connect(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect", address)

        def blocked_connect_ex(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect_ex", address)

        socket.create_connection = blocked_create_connection
        socket.socket.connect = blocked_connect
        socket.socket.connect_ex = blocked_connect_ex
        self._installed = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._installed:
            socket.create_connection = self._original_create_connection
            socket.socket.connect = self._original_connect
            socket.socket.connect_ex = self._original_connect_ex
            self._installed = False
        return False


def claim_controlling_attempt_sentinel(
    proof_root: str | Path,
    *,
    proof_id: str,
    git_head: str,
) -> Path:
    """Atomically consume the single C8 controlling-attempt entitlement."""
    root = Path(proof_root).expanduser().resolve()
    if not root.is_dir():
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_PROOF_ROOT_MISSING"
        )

    proof = str(proof_id or "").strip()
    head = str(git_head or "").strip()
    if not proof:
        raise Checkpoint8ControllingProofError("CONTROLLING_PROOF_ID_MISSING")
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head.lower()):
        raise Checkpoint8ControllingProofError("CONTROLLING_GIT_HEAD_INVALID")

    sentinel = root / _ATTEMPT_SENTINEL_NAME
    payload = {
        "attempt_ordinal": 1,
        "git_head": head,
        "proof_id": proof,
        "sentinel_schema": "CHECKPOINT8_CONTROLLING_ATTEMPT_V1",
    }
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(sentinel, flags, 0o600)
    except FileExistsError as exc:
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_ATTEMPT_ALREADY_CONSUMED"
        ) from exc

    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        raise

    return sentinel



_PROTECTED_CAPABILITY_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)



_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_CHECKPOINT8_INFRASTRUCTURE_MINTS = frozenset(
    {
        "11111111111111111111111111111111",
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    }
)

_CHECKPOINT8_PAYLOAD_CONTRACT_BY_LABEL = {
    "pump_origin_solana_rpc_transport": "pump_finalized_create_signature_page_and_transactions",
    "direct_pump_finalized_migration_transport": "pump_finalized_migration_rpc",
    "exact_pump_pumpswap_graduation_verifier_transport": "pumpswap_onchain_graduation_confirmation",
    "secondary_discovery_http_transport": "secondary_gecko_dex_enrichment",
    "pumpswap_migration_pool_confirmation": "pumpswap_pool_confirmation",
    "pumpswap_account_batch_transport": "pumpswap_account_batch_rpc",
    "dexscreener_fresh_profiles_discovery": "dexscreener_fresh_profiles",
    "dexscreener_mint_batch_discovery": "dexscreener_two_mint_market_batch",
    "geckoterminal_fresh_nomination": "geckoterminal_fresh_pool_nomination",
    "geckoterminal_token_pools_discovery": "geckoterminal_two_mint_pool_batch",
    "unknown_liquidity_backup_dex_to_gecko": "geckoterminal_unknown_liquidity_backup",
    "unknown_liquidity_backup_gecko_to_dex": "dexscreener_unknown_liquidity_backup",
    "lifecycle_exact_pair_dexscreener_primary": "dexscreener_exact_pair_snapshot",
    "lifecycle_exact_pair_geckoterminal_fallback": "geckoterminal_exact_pair_snapshot",
    "preclose_coingecko_market_chain": "coingecko_broad_market_context",
    "preclose_goplus_safety": "goplus_sol_token_safety",
    "preclose_jupiter_entry_quote": "jupiter_paper_entry_quote",
    "preclose_jupiter_exit_quote": "jupiter_paper_exit_quote",
    "preclose_solana_rpc_holder_primary": "solana_rpc_holder_distribution",
    "preclose_helius_holder_backup": "helius_holder_distribution_backup",
}


def _b58encode(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _B58_ALPHABET[remainder] + encoded
    leading = len(value) - len(value.lstrip(bytes(1)))
    return "1" * leading + (encoded or "")


def _b58decode(value: str) -> bytes:
    number = 0
    for character in value:
        number = number * 58 + _B58_ALPHABET.index(character)
    raw = (
        number.to_bytes((number.bit_length() + 7) // 8, "big")
        if number
        else b""
    )
    leading = len(value) - len(value.lstrip("1"))
    return bytes(leading) + raw


def _fixture_pubkey(label: str) -> tuple[str, bytes]:
    raw = hashlib.sha256(label.encode("utf-8")).digest()
    return _b58encode(raw), raw


def _fixture_signature(label: str) -> str:
    return _b58encode(hashlib.sha512(label.encode("utf-8")).digest())


def _borsh_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def _checkpoint8_create_transaction(
    *,
    label: str,
    slot: int,
    block_time: int,
) -> dict[str, Any]:
    signature = _fixture_signature(f"signature:{label}")
    mint, mint_raw = _fixture_pubkey(f"mint:{label}")
    creator_raw = hashlib.sha256(f"creator:{label}".encode("utf-8")).digest()
    user, _ = _fixture_pubkey(f"user:{label}")
    curve = derive_program_address(
        (b"bonding-curve", mint_raw),
        PUMP_PROGRAM_ID,
    )
    associated_curve = derive_program_address(
        (_b58decode(curve), _b58decode(TOKEN_PROGRAM_ID), mint_raw),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    metadata = derive_program_address(
        (b"metadata", _b58decode(TOKEN_METADATA_PROGRAM_ID), mint_raw),
        TOKEN_METADATA_PROGRAM_ID,
    )
    data = (
        CREATE_DISCRIMINATOR
        + _borsh_string(f"Checkpoint 8 {label}")
        + _borsh_string("C8")
        + _borsh_string(f"https://fixture.invalid/{label}.json")
        + creator_raw
    )
    keys = [
        mint,
        MINT_AUTHORITY_ID,
        curve,
        associated_curve,
        GLOBAL_ID,
        TOKEN_METADATA_PROGRAM_ID,
        metadata,
        user,
        SYSTEM_PROGRAM_ID,
        TOKEN_PROGRAM_ID,
        ASSOCIATED_TOKEN_PROGRAM_ID,
        RENT_SYSVAR_ID,
        EVENT_AUTHORITY_ID,
        PUMP_PROGRAM_ID,
    ]
    return {
        "version": 0,
        "slot": slot,
        "blockTime": block_time,
        "meta": {
            "err": None,
            "loadedAddresses": {"writable": [], "readonly": []},
            "innerInstructions": [],
        },
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": keys,
                "instructions": [
                    {
                        "programIdIndex": 13,
                        "accounts": list(range(14)),
                        "data": _b58encode(data),
                    }
                ],
            },
        },
    }


def _checkpoint8_ata(*, owner: str, token_program: str, mint: str) -> str:
    return derive_program_address(
        (_b58decode(owner), _b58decode(token_program), _b58decode(mint)),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )


def _checkpoint8_migrate_transaction(
    *,
    label: str,
    mint: str,
    signature: str,
    slot: int,
    block_time: int,
) -> tuple[dict[str, Any], str]:
    mint_raw = _b58decode(mint)
    user, _ = _fixture_pubkey(f"migration-user:{label}")
    bonding_curve = derive_program_address((b"bonding-curve", mint_raw), PUMP_PROGRAM_ID)
    associated_bonding_curve = _checkpoint8_ata(
        owner=bonding_curve, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    pool_authority = derive_program_address((b"pool-authority", mint_raw), PUMP_PROGRAM_ID)
    pumpswap_pool = derive_program_address(
        (
            b"pool",
            (0).to_bytes(2, "little"),
            _b58decode(pool_authority),
            mint_raw,
            _b58decode(WSOL_MINT),
        ),
        PUMPSWAP_AMM_PROGRAM_ID,
    )
    pool_authority_mint = _checkpoint8_ata(
        owner=pool_authority, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    pool_authority_wsol = _checkpoint8_ata(
        owner=pool_authority, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
    )
    lp_mint = derive_program_address(
        (b"pool_lp_mint", _b58decode(pumpswap_pool)), PUMPSWAP_AMM_PROGRAM_ID
    )
    user_pool_token_account = _checkpoint8_ata(
        owner=user, token_program=TOKEN_2022_PROGRAM_ID, mint=lp_mint
    )
    pool_base_token_account = _checkpoint8_ata(
        owner=pumpswap_pool, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    pool_quote_token_account = _checkpoint8_ata(
        owner=pumpswap_pool, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
    )
    accounts = [
        PUMP_GLOBAL_ID,
        PUMP_WITHDRAW_AUTHORITY_ID,
        mint,
        bonding_curve,
        associated_bonding_curve,
        user,
        SYSTEM_PROGRAM_ID,
        TOKEN_PROGRAM_ID,
        PUMPSWAP_AMM_PROGRAM_ID,
        pumpswap_pool,
        pool_authority,
        pool_authority_mint,
        pool_authority_wsol,
        PUMPSWAP_GLOBAL_CONFIG_ID,
        WSOL_MINT,
        lp_mint,
        user_pool_token_account,
        pool_base_token_account,
        pool_quote_token_account,
        TOKEN_2022_PROGRAM_ID,
        ASSOCIATED_TOKEN_PROGRAM_ID,
        PUMPSWAP_EVENT_AUTHORITY_ID,
        PUMP_EVENT_AUTHORITY_ID,
        PUMP_PROGRAM_ID,
        RENT_SYSVAR_ID,
    ]
    transaction = {
        "version": 0,
        "slot": slot,
        "blockTime": block_time,
        "meta": {
            "err": None,
            "loadedAddresses": {"writable": [], "readonly": []},
            "innerInstructions": [],
        },
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": accounts,
                "instructions": [
                    {
                        "programIdIndex": 23,
                        "accounts": list(range(25)),
                        "data": _b58encode(PUMP_MIGRATE_DISCRIMINATOR),
                    }
                ],
            },
        },
    }
    return transaction, pumpswap_pool


def _checkpoint8_candidate_records() -> tuple[dict[str, Any], ...]:
    rows = []
    for ordinal, label in enumerate(("alpha", "bravo")):
        create_slot = 1_700_000 + ordinal
        create_block_time = 1_800_000_000 + ordinal * 60
        create_transaction = _checkpoint8_create_transaction(
            label=label, slot=create_slot, block_time=create_block_time
        )
        mint = create_transaction["transaction"]["message"]["accountKeys"][0]
        bonding_curve = create_transaction["transaction"]["message"]["accountKeys"][2]
        create_signature = create_transaction["transaction"]["signatures"][0]
        migration_signature = _fixture_signature(f"migration-signature:{label}")
        migration_slot = create_slot + 100
        migration_block_time = create_block_time + 600
        migration_transaction, pumpswap_pool = _checkpoint8_migrate_transaction(
            label=label,
            mint=mint,
            signature=migration_signature,
            slot=migration_slot,
            block_time=migration_block_time,
        )
        rows.append(
            {
                "label": label,
                "mint": mint,
                "pool": bonding_curve,
                "bonding_curve": bonding_curve,
                "pumpswap_pool": pumpswap_pool,
                "signature": create_signature,
                "create_signature": create_signature,
                "slot": create_slot,
                "block_time": create_block_time,
                "transaction": create_transaction,
                "create_transaction": create_transaction,
                "migration_signature": migration_signature,
                "migration_slot": migration_slot,
                "migration_block_time": migration_block_time,
                "migration_transaction": migration_transaction,
            }
        )
    return tuple(rows)


def _checkpoint8_market_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        **candidate,
        "pool": str(candidate.get("pumpswap_pool") or candidate.get("pool") or ""),
    }


def _checkpoint8_gecko_pool_body(candidate: dict[str, Any]) -> dict[str, Any]:
    row = _checkpoint8_market_candidate(candidate)
    return {
        "data": {
            "id": f"solana_{row['pool']}",
            "type": "pool",
            "attributes": {
                "address": row["pool"],
                "base_token_price_usd": "1.0",
                "reserve_in_usd": "10000",
                "fdv_usd": "1000000",
                "pool_created_at": "2026-08-07T11:00:00Z",
                "volume_usd": {"m5": "500", "h1": "2000", "h24": "10000"},
                "transactions": {
                    "m5": {"buys": 6, "sells": 4},
                    "h1": {"buys": 30, "sells": 20},
                    "h24": {"buys": 280, "sells": 220},
                },
                "price_change_percentage": {"m5": "0.5", "h1": "1.0", "h24": "2.0"},
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{row['mint']}", "type": "token"}},
                "quote_token": {
                    "data": {
                        "id": "solana_So11111111111111111111111111111111111111112",
                        "type": "token",
                    }
                },
                "dex": {"data": {"id": "pump-fun", "type": "dex"}},
            },
        }
    }


def _checkpoint8_gecko_list_payload(candidates: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    return {
        "data": [_checkpoint8_gecko_pool_body(item)["data"] for item in candidates],
        "_source_status_code": 200,
        "transport_operations_used": 1,
        "response_bytes": 1024,
        "normalized_rows": len(candidates),
    }


def _checkpoint8_dex_payload(candidates: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    pairs = []
    for candidate in candidates:
        row = _checkpoint8_market_candidate(candidate)
        pairs.append(
            {
                "chainId": "solana",
                "dexId": "pumpswap",
                "pairAddress": row["pool"],
                "baseToken": {"address": row["mint"], "symbol": "C8"},
                "quoteToken": {
                    "address": "So11111111111111111111111111111111111111112",
                    "symbol": "SOL",
                },
                "priceUsd": "1.0",
                "liquidity": {"usd": 10000.0},
                "fdv": 1000000.0,
                "marketCap": 900000.0,
                "volume": {"m5": 500.0, "h1": 2000.0, "h24": 10000.0},
                "txns": {
                    "m5": {"buys": 6, "sells": 4},
                    "h1": {"buys": 30, "sells": 20},
                    "h24": {"buys": 280, "sells": 220},
                },
                "priceChange": {"m5": 0.5, "h1": 1.0, "h24": 2.0},
                "pairCreatedAt": 1800000000000,
            }
        )
    return {
        "schemaVersion": "1.0",
        "pairs": pairs,
        "_source_status_code": 200,
        "transport_operations_used": 1,
        "response_bytes": 1024,
        "normalized_rows": len(pairs),
    }


def _checkpoint8_candidate_for_mint(mint: str) -> dict[str, Any] | None:
    target = str(mint or "")
    return next(
        (row for row in _checkpoint8_candidate_records() if row["mint"] == target),
        None,
    )


def _checkpoint8_pumpswap_confirmation(candidate: dict[str, Any]) -> dict[str, Any]:
    row = _checkpoint8_market_candidate(candidate)
    return {
        "pumpswap_confirmation": {
            "confirmed": True,
            "reason": "confirmed_pumpswap_pool",
            "pool_address": row["pool"],
            "expected_mint": row["mint"],
            "program_id": PUMPSWAP_AMM_PROGRAM_ID,
            "owner": PUMPSWAP_AMM_PROGRAM_ID,
            "base_mint_offset": 43,
        },
        "migration_signature": candidate["migration_signature"],
        "migration_block_time": candidate["migration_block_time"],
        "migration_slot": candidate["migration_slot"],
        "transport_operations_used": 1,
        "response_bytes": 512,
        "normalized_rows": 1,
    }


def _checkpoint8_pumpswap_account_value(candidate: dict[str, Any]) -> dict[str, Any]:
    import base64

    raw = bytearray(107)
    raw[43:75] = _b58decode(candidate["mint"])
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "lamports": 1,
        "executable": False,
        "rentEpoch": 0,
        "data": [base64.b64encode(bytes(raw)).decode("ascii"), "base64"],
    }


def _checkpoint8_account_batch_payload(context: Any) -> dict[str, Any]:
    payload = getattr(getattr(context, "request", None), "payload", {}) or {}
    addresses = list(payload.get("addresses") or ())
    values = []
    for address in addresses:
        candidate = next(
            (
                row
                for row in _checkpoint8_candidate_records()
                if str(row.get("pumpswap_pool") or "") == str(address)
            ),
            None,
        )
        values.append(
            None if candidate is None else _checkpoint8_pumpswap_account_value(candidate)
        )
    return {
        "result": {"context": {"slot": 1700200}, "value": values},
        "response_bytes": 1024,
        "transport_operations_used": 1,
    }


def checkpoint8_success_fixture_response_semantics() -> dict[str, Any]:
    labels = tuple(ordinary_window_15m_builder_identities())
    candidates = _checkpoint8_candidate_records()
    contract_labels = tuple(_CHECKPOINT8_PAYLOAD_CONTRACT_BY_LABEL)
    candidate_mints = tuple(row["mint"] for row in candidates)
    infrastructure_count = sum(
        1 for mint in candidate_mints if mint in _CHECKPOINT8_INFRASTRUCTURE_MINTS
    )
    all_contracts = (
        contract_labels == labels
        and all(
            bool(_CHECKPOINT8_PAYLOAD_CONTRACT_BY_LABEL.get(label))
            for label in labels
        )
    )
    return {
        "ready": (
            len(labels) == 20
            and len(candidates) == 2
            and len(set(candidate_mints)) == 2
            and infrastructure_count == 0
            and all_contracts
        ),
        "labels": labels,
        "candidate_count": len(candidates),
        "candidate_mints": candidate_mints,
        "infrastructure_mint_count": infrastructure_count,
        "all_routes_have_explicit_payload_contracts": all_contracts,
        "payload_contracts": dict(_CHECKPOINT8_PAYLOAD_CONTRACT_BY_LABEL),
    }



class _Checkpoint8DeterministicFixture:
    """Zero-provider fixture with exact port-specific response contracts."""

    def __init__(self, route: str) -> None:
        self.route = str(route)
        self.operation_count = 0

    def _count(self) -> None:
        self.operation_count += 1

    def _nested_transport(self, payload_builder):
        parent = self

        def transport(context):
            parent._count()
            return payload_builder(context)

        return transport

    def __call__(self, *args, **kwargs):
        self._count()
        candidates = _checkpoint8_candidate_records()

        if self.route == "top_level.migration_transport":
            context = args[0] if args else kwargs.get("context")
            request = getattr(context, "request", None)
            request_kind = str(getattr(request, "request_kind", "") or "")
            payload = getattr(request, "payload", {}) or {}
            if request_kind == DIRECT_MIGRATION_SIGNATURE_PAGE_REQUEST_KIND:
                result = [
                    {
                        "signature": row["migration_signature"],
                        "slot": row["migration_slot"],
                        "confirmationStatus": "finalized",
                        "err": None,
                    }
                    for row in reversed(candidates)
                ]
            elif request_kind == DIRECT_MIGRATION_TRANSACTION_REQUEST_KIND:
                signature = str(payload.get("signature") or "")
                result = next(
                    (
                        row["migration_transaction"]
                        for row in candidates
                        if row["migration_signature"] == signature
                    ),
                    None,
                )
            else:
                return {
                    "fixture_status": "failure",
                    "failure_type": "checkpoint8_direct_migration_request_kind_unsupported",
                    "failure_message": f"unsupported request kind: {request_kind}",
                    "response_bytes": 0,
                    "transport_operations_used": 1,
                }
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": result,
                "response_bytes": 512,
                "transport_operations_used": 1,
            }

        if self.route == "graduated_supply.verifier_transport_factory":
            context = args[0] if len(args) == 1 and hasattr(args[0], "request") else None
            if context is not None:
                request_kind = str(context.request.request_kind)
                if request_kind == "pumpswap_pool_account_batch":
                    return _checkpoint8_account_batch_payload(context)
                if request_kind == "pumpswap_onchain_pool_confirmation":
                    mint = str((context.request.payload or {}).get("expected_mint") or "")
                    candidate = _checkpoint8_candidate_for_mint(mint)
                    if candidate is None:
                        return {"fixture_status": "failure", "failure_type": "checkpoint8_candidate_missing"}
                    return _checkpoint8_pumpswap_confirmation(candidate)
            expected_mint = ""
            expected_signature = ""
            if len(args) >= 2:
                expected_mint = str(args[0] or "")
                expected_signature = str(args[1] or "")
            elif kwargs.get("expected_mint"):
                expected_mint = str(kwargs["expected_mint"])
                expected_signature = str(kwargs.get("migration_signature") or "")
            candidate = _checkpoint8_candidate_for_mint(expected_mint)
            if candidate is None:
                raise Checkpoint8ControllingProofError(
                    "CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING"
                )
            if (
                expected_signature
                and str(candidate.get("migration_signature") or "")
                != expected_signature
            ):
                raise Checkpoint8ControllingProofError(
                    "CHECKPOINT8_PUMPSWAP_FIXTURE_SIGNATURE_MISMATCH"
                )
            return self._nested_transport(
                lambda _context, candidate=candidate: _checkpoint8_pumpswap_confirmation(candidate)
            )

        if self.route == "graduated_supply.locator_transport":
            context = args[0] if args else kwargs.get("context")
            del context
            return _checkpoint8_dex_payload(candidates)

        if self.route == "graduated_supply.dexscreener_batch_transport_factory":
            requested = tuple(str(item) for item in (args[0] if args else kwargs.get("token_mints") or ()))
            chosen = tuple(row for row in candidates if row["mint"] in requested)
            return self._nested_transport(
                lambda _context, chosen=chosen: _checkpoint8_dex_payload(chosen)
            )

        if self.route == "graduated_supply.geckoterminal_nomination_transport":
            context = args[0] if args else kwargs.get("context")
            del context
            return _checkpoint8_gecko_list_payload(candidates)

        if self.route == "graduated_supply.geckoterminal_reconciliation_transport_factory":
            mint = str(args[0] if args else kwargs.get("token_mint") or "")
            candidate = _checkpoint8_candidate_for_mint(mint)
            chosen = () if candidate is None else (candidate,)
            return self._nested_transport(
                lambda _context, chosen=chosen: _checkpoint8_gecko_list_payload(chosen)
            )

        from printer_v1.sources.governed_execution import build_fixture_source_adapter

        first = candidates[0]
        market = _checkpoint8_market_candidate(first)
        if self.route == "lifecycle.snapshot_adapter_factory":
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": market["mint"],
                            "pair_address": market["pool"],
                            "price_usd": 1.0,
                            "liquidity_usd": 10000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2000.0,
                            "volume_24h": 10000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 6,
                            "sells_5m": 4,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 0.5,
                            "price_change_1h": 1.0,
                            "price_change_24h": 2.0,
                        }
                    ]
                },
            )
        if self.route == "lifecycle.fallback_snapshot_adapter_factory":
            return build_fixture_source_adapter(
                "geckoterminal",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": market["mint"],
                            "pair_address": market["pool"],
                            "price_usd": 1.0,
                            "liquidity_usd": 10000.0,
                        }
                    ]
                },
            )
        if self.route == "lifecycle.context_adapter_factories.coingecko":
            return build_fixture_source_adapter(
                "coingecko",
                fixture_payload={
                    "captured_at": "2026-08-07T12:00:00+00:00",
                    "assets": {
                        "bitcoin": {"price_usd": 65000, "change_24h": 1.0},
                        "ethereum": {"price_usd": 3500, "change_24h": 1.0},
                        "solana": {"price_usd": 150, "change_24h": 2.0, "volume_24h": 2000000000},
                    },
                },
            )
        if self.route == "lifecycle.context_adapter_factories.goplus":
            target_mint = str(kwargs.get("token_mint") or first["mint"])
            return build_fixture_source_adapter(
                "goplus",
                fixture_payload={
                    "token_mint": target_mint,
                    "mint_authority": None,
                    "freeze_authority": None,
                    "metadata_mutable": False,
                    "total_supply": "1000000000",
                    "top_10_holders": [{"percent": "3"} for _ in range(10)],
                    "lp_info": [{"locked": True}],
                    "risk_flags": [],
                },
            )
        if self.route == "lifecycle.context_adapter_factories.jupiter_quote":
            return build_fixture_source_adapter(
                "jupiter_quote",
                fixture_payload={
                    "route_available": True,
                    "route_plan_present": True,
                    "slippage_bps": 50,
                    "price_impact_bps": 5,
                    "freshness_label": "QUOTE_FRESH",
                    "target_status": "TARGET_MATCH",
                    "paper_only_context": True,
                    "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                    "input_mint": kwargs.get("input_mint"),
                    "output_mint": kwargs.get("output_mint"),
                },
            )
        if self.route == "lifecycle.context_adapter_factories.solana_rpc_holder":
            return build_fixture_source_adapter(
                "solana_rpc",
                fixture_payload={
                    "holder_count": 20,
                    "top_10_percent": 30.0,
                    "largest_holder_percent": 5.0,
                },
            )
        if self.route == "lifecycle.context_adapter_factories.helius_holder_backup":
            return build_fixture_source_adapter(
                "helius_free",
                fixture_payload={
                    "holder_count": 20,
                    "top_10_percent": 30.0,
                    "largest_holder_percent": 5.0,
                },
            )

        raise Checkpoint8ControllingProofError(
            f"CHECKPOINT8_FIXTURE_PORT_UNSUPPORTED:{self.route}"
        )

    def execute(self, *args, **kwargs):
        # Kept only for import/backward compatibility; real-consumer
        # compatibility requires factory/transport ports above.
        self._count()
        del args, kwargs
        raise Checkpoint8ControllingProofError(
            f"CHECKPOINT8_GENERIC_EXECUTE_FORBIDDEN:{self.route}"
        )

    def json_get(self, url, *args, **kwargs):
        self._count()
        del args, kwargs
        candidates = _checkpoint8_candidate_records()
        url_text = str(url)
        if self.route != "top_level.secondary_transport":
            raise Checkpoint8ControllingProofError(
                f"CHECKPOINT8_JSON_GET_PORT_UNSUPPORTED:{self.route}"
            )
        if "trending_pools" in url_text:
            return {"data": []}
        if "token-profiles" in url_text:
            return []
        if "dexscreener" in url_text:
            return _checkpoint8_dex_payload(candidates)
        for candidate in candidates:
            if str(candidate.get("pumpswap_pool") or "") in url_text:
                return _checkpoint8_gecko_pool_body(candidate)
        return {"data": []}

    def json_rpc(self, method, params=None, *args, **kwargs):
        self._count()
        del args, kwargs
        candidates = _checkpoint8_candidate_records()
        if isinstance(method, dict):
            return {"fixture": True, "route": self.route}
        method_text = str(method)
        if self.route != "top_level.pump_transport":
            raise Checkpoint8ControllingProofError(
                f"CHECKPOINT8_JSON_RPC_PORT_UNSUPPORTED:{self.route}"
            )
        if method_text == "getSignaturesForAddress":
            return [
                {
                    "signature": row["create_signature"],
                    "slot": row["slot"],
                    "confirmationStatus": "finalized",
                    "err": None,
                }
                for row in reversed(candidates)
            ]
        if method_text == "getTransaction":
            signature = str((params or [""])[0])
            return next(
                (
                    row["create_transaction"]
                    for row in candidates
                    if row["create_signature"] == signature
                ),
                None,
            )
        raise Checkpoint8ControllingProofError(
            f"CHECKPOINT8_PUMP_RPC_METHOD_UNSUPPORTED:{method_text}"
        )


def checkpoint8_real_consumer_compatibility_matrix(runtime):
    from printer_v1.operator_cli.checkpoint8_real_consumer_compatibility import (
        run_checkpoint8_real_consumer_compatibility,
    )

    return run_checkpoint8_real_consumer_compatibility(runtime)


def _checkpoint8_route_by_label() -> dict[str, str]:
    route_rows = getattr(proof, "_EXECUTION_ROUTE_BY_LABEL", None)
    if route_rows is None:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_ROUTE_OWNER_MISSING"
        )
    route_by_label = {
        str(label): str(route)
        for label, route in tuple(route_rows)
    }
    expected = tuple(ordinary_window_15m_builder_identities())
    if tuple(route_by_label) != expected:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_ROUTE_REGISTRY_MISMATCH"
        )
    return route_by_label


def build_checkpoint8_deterministic_success_fixture_composition():
    """Build the exact marked 20-label C8 registry with zero fallback.

    This slice proves registry/materialization readiness only. Exact response
    semantics are owned by the subsequent execution-entry RED contracts.
    """
    expected = tuple(ordinary_window_15m_builder_identities())
    if len(expected) != 20:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_CANONICAL_COMPOSITION_COUNT_MISMATCH"
        )

    route_by_label = _checkpoint8_route_by_label()
    fixture_by_route: dict[str, _Checkpoint8DeterministicFixture] = {}
    builders: dict[str, Any] = {}

    for label in expected:
        route = route_by_label[label]
        fixture = fixture_by_route.setdefault(
            route,
            _Checkpoint8DeterministicFixture(route),
        )

        def builder(label=label, fixture=fixture):
            return proof.mark_checkpoint8_fixture_output(
                fixture,
                label=label,
            )

        builders[label] = proof.mark_checkpoint8_fixture_builder(
            builder,
            label=label,
        )

    composition = proof.build_window_15m_fixture_composition(builders)
    if composition.provider_fallback_allowed is not False:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_PROVIDER_FALLBACK_FORBIDDEN"
        )
    return composition


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_preparation_git_head(git_head: str) -> str:
    head = str(git_head or "").strip().lower()
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_GIT_HEAD_INVALID"
        )
    return head


def _protected_capability_counts(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    counts = {
        table: int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        )
        for table in _PROTECTED_CAPABILITY_TABLES
        if table in existing
    }
    if not counts:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_PROTECTED_CAPABILITY_TABLES_MISSING"
        )
    return counts


def prepare_checkpoint8_controlling_entry(
    proof_root: str | Path,
    *,
    proof_id: str,
    git_head: str,
):
    """Prepare one fresh, still-unclaimed C8 controlling-proof target."""
    root = Path(proof_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    head = _validate_preparation_git_head(git_head)

    db_path = root / "checkpoint8-controlling-proof.sqlite3"
    artifact_root = root / "checkpoint8-artifacts"
    sentinel = root / _ATTEMPT_SENTINEL_NAME

    if sentinel.exists():
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_ATTEMPT_ALREADY_CONSUMED"
        )
    if db_path.exists() or artifact_root.exists():
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_ENTRY_TARGET_NOT_FRESH"
        )

    artifact_root.mkdir(parents=False, exist_ok=False)
    apply_migrations(db_path)

    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        integrity_check = str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        foreign_key_violations = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations "
                "ORDER BY rowid"
            ).fetchall()
        ]
        protected_counts = _protected_capability_counts(connection)
    finally:
        connection.close()

    canonical_names = tuple(canonical_migration_names())
    if tuple(applied) != canonical_names:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_MIGRATION_LEDGER_MISMATCH"
        )
    if integrity_check != "ok" or foreign_key_violations != 0:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_DISPOSABLE_DB_INTEGRITY_FAILED"
        )
    if any(protected_counts.values()):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_PROTECTED_CAPABILITY_BASELINE_NONZERO"
        )

    db_sha256 = _sha256_file(db_path)
    composition = build_checkpoint8_deterministic_success_fixture_composition()
    plan = proof.build_disposable_public_composition_proof_plan(
        proof_id=str(proof_id),
        db_path=db_path,
        db_sha256=db_sha256,
        migration_count=canonical_migration_count(),
        migration_head=canonical_names[-1],
        artifact_root=artifact_root,
        composition_labels=composition.labels,
        provider_execution_allowed=False,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
    )
    runtime = proof.build_disposable_public_composition_proof_runtime(
        plan,
        composition,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )

    materialized = proof.materialize_disposable_public_composition_execution(
        runtime
    )
    if (
        tuple(materialized.outputs_by_label)
        != tuple(ordinary_window_15m_builder_identities())
        or materialized.provider_fallback_allowed is not False
    ):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_MATERIALIZATION_MISMATCH"
        )

    semantics = checkpoint8_success_fixture_response_semantics()
    if semantics["ready"] is not True:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_RESPONSE_SEMANTICS_NOT_READY"
        )

    pre_run_evidence = {
        "db_path": str(db_path.resolve()),
        "fixture_response_semantics_ready": True,
        "fixture_candidate_count": semantics["candidate_count"],
        "fixture_candidate_mints": list(semantics["candidate_mints"]),
        "db_sha256": db_sha256,
        "artifact_root": str(artifact_root.resolve()),
        "migration_count": canonical_migration_count(),
        "migration_head": canonical_names[-1],
        "integrity_check": integrity_check,
        "foreign_key_violations": foreign_key_violations,
        "protected_capability_counts": protected_counts,
        "fixture_composition_manifest_sha256": (
            runtime.fixture_composition_manifest_sha256
        ),
        "composition_registry_sha256": (
            runtime.plan.composition_registry_sha256
        ),
        "git_head": head,
        "network_attempt_count": 0,
    }

    return SimpleNamespace(
        proof_root=root,
        runtime=runtime,
        pre_run_evidence=pre_run_evidence,
    )




def validate_checkpoint8_git_entry(
    repo_root: str | Path,
    *,
    expected_head: str,
) -> str:
    """Require the exact approved HEAD and a clean tracked worktree."""
    root = Path(repo_root).expanduser().resolve()
    if not (root / ".git").exists() and not (root / ".git").is_file():
        # Worktrees use a .git file, ordinary repos use a .git directory.
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_GIT_REPOSITORY_MISSING"
        )

    expected = _validate_preparation_git_head(expected_head)
    try:
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip().lower()
        tracked_status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_GIT_ENTRY_VALIDATION_FAILED"
        ) from exc

    if actual != expected:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_GIT_HEAD_MISMATCH"
        )
    if tracked_status.strip():
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_TRACKED_WORKTREE_NOT_CLEAN"
        )
    return actual


def _checkpoint8_materialized_fixture_objects(runtime) -> tuple[Any, ...]:
    materialized = proof.materialize_disposable_public_composition_execution(
        runtime
    )
    unique: list[Any] = []
    seen: set[int] = set()
    for output in materialized.outputs_by_label.values():
        identity = id(output)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(output)
    return tuple(unique)


def checkpoint8_fixture_transport_operation_count(runtime) -> int:
    """Count actual calls made through unique shared C8 fixture objects."""
    return sum(
        int(getattr(output, "operation_count", 0) or 0)
        for output in _checkpoint8_materialized_fixture_objects(runtime)
    )


def _checkpoint8_replay_zero_work(replay: Any) -> bool:
    if not isinstance(replay, dict):
        return False
    zero_keys = (
        "source_calls",
        "scheduler_runtime_calls",
        "database_writes",
        "replay_new_source_calls",
        "replay_new_scheduler_calls",
        "replay_database_writes",
    )
    return all(int(replay.get(key, 0) or 0) == 0 for key in zero_keys)


def _checkpoint8_longer_window_counts(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    locked = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")
    table = "printer_memory_windows"
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if exists is None:
        return {label: 0 for label in locked}

    columns = [
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    ]
    if not columns:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_MEMORY_WINDOW_SCHEMA_UNREADABLE"
        )

    where = " OR ".join(
        f'CAST("{column}" AS TEXT)=?'
        for column in columns
    )
    counts: dict[str, int] = {}
    for label in locked:
        params = tuple(label for _ in columns)
        counts[label] = int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE {where}',
                params,
            ).fetchone()[0]
        )
    return counts


def _checkpoint8_post_run_evidence(prepared) -> dict[str, Any]:
    db_path = Path(prepared.runtime.plan.resolved_db_path).resolve()
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        integrity_check = str(
            connection.execute("PRAGMA integrity_check").fetchone()[0]
        )
        foreign_key_violations = len(
            connection.execute("PRAGMA foreign_key_check").fetchall()
        )
        current_protected = _protected_capability_counts(connection)
        baseline = dict(
            prepared.pre_run_evidence.get(
                "protected_capability_counts",
                {},
            )
        )
        protected_deltas = {
            table: int(current_protected.get(table, 0))
            - int(baseline.get(table, 0))
            for table in sorted(set(current_protected) | set(baseline))
        }
        longer_window_counts = _checkpoint8_longer_window_counts(connection)
    finally:
        connection.close()

    return {
        "db_sha256": _sha256_file(db_path),
        "integrity_check": integrity_check,
        "foreign_key_violations": foreign_key_violations,
        "protected_capability_counts": current_protected,
        "protected_capability_deltas": protected_deltas,
        "longer_window_counts": longer_window_counts,
    }


def extract_checkpoint8_terminal_identity(
    terminal: dict[str, Any],
) -> tuple[str, str]:
    if not isinstance(terminal, dict):
        raise Checkpoint8ControllingProofError("CHECKPOINT8_TERMINAL_RESULT_INVALID")
    report = terminal.get("report")
    report = report if isinstance(report, dict) else {}
    cleanup = terminal.get("cleanup")
    cleanup = cleanup if isinstance(cleanup, dict) else {}
    reconciliation = terminal.get("reconciliation")
    reconciliation = reconciliation if isinstance(reconciliation, dict) else {}
    active_work = reconciliation.get("active_work")
    active_work = active_work if isinstance(active_work, dict) else {}
    active_scope = active_work.get("scope")
    active_scope = active_scope if isinstance(active_scope, dict) else {}
    discovery = reconciliation.get("discovery_parity")
    discovery = discovery if isinstance(discovery, dict) else {}
    discovery_scope = discovery.get("scope")
    discovery_scope = discovery_scope if isinstance(discovery_scope, dict) else {}
    exhaustion = report.get("exhaustion_certificate")
    exhaustion = exhaustion if isinstance(exhaustion, dict) else {}

    campaign_values = {
        str(value).strip()
        for value in (
            terminal.get("campaign_id"),
            report.get("campaign_id"),
            cleanup.get("campaign_id"),
            active_scope.get("campaign_id"),
            discovery_scope.get("campaign_id"),
            exhaustion.get("campaign_id"),
        )
        if value not in (None, "")
    }
    run_values = {
        str(value).strip()
        for value in (
            terminal.get("run_id"),
            report.get("run_id"),
            cleanup.get("run_id"),
            active_scope.get("run_id"),
            discovery_scope.get("run_id"),
            exhaustion.get("run_id"),
        )
        if value not in (None, "")
    }
    if len(campaign_values) > 1 or len(run_values) > 1:
        raise Checkpoint8ControllingProofError("CHECKPOINT8_TERMINAL_IDENTITY_CONFLICT")
    if len(campaign_values) != 1 or len(run_values) != 1:
        raise Checkpoint8ControllingProofError("CHECKPOINT8_TERMINAL_IDENTITY_MISSING")
    return next(iter(campaign_values)), next(iter(run_values))


def execute_checkpoint8_public_sequence(
    prepared,
    *,
    git_head: str,
):
    """Consume the one-shot entitlement around one public run and one replay."""
    head = _validate_preparation_git_head(git_head)
    evidence = getattr(prepared, "pre_run_evidence", None)
    if not isinstance(evidence, dict):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_RESPONSE_SEMANTICS_NOT_READY"
        )
    if (
        evidence.get("fixture_response_semantics_ready") is not True
        or int(evidence.get("fixture_candidate_count") or 0) != 2
    ):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_RESPONSE_SEMANTICS_NOT_READY"
        )
    if str(evidence.get("git_head") or "").lower() != head:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_PREPARED_GIT_HEAD_MISMATCH"
        )

    sentinel_path = claim_controlling_attempt_sentinel(
        prepared.proof_root,
        proof_id=prepared.runtime.plan.proof_id,
        git_head=head,
    )

    tripwire = Checkpoint8NetworkTripwire()
    with tripwire:
        terminal = run_operational_campaign(
            operator_approved=True,
            disposable_proof=prepared.runtime,
        )

        if not isinstance(terminal, dict):
            raise Checkpoint8ControllingProofError(
                "CHECKPOINT8_TERMINAL_RESULT_INVALID"
            )
        campaign_id, run_id = extract_checkpoint8_terminal_identity(terminal)

        replay = report_only(
            campaign_id=campaign_id,
            run_id=run_id,
            db_path=Path(
                prepared.runtime.plan.resolved_db_path
            ).resolve(),
            artifact_root=Path(
                prepared.runtime.plan.resolved_artifact_root
            ).resolve(),
        )

    return SimpleNamespace(
        sentinel_path=sentinel_path,
        terminal=terminal,
        replay=replay,
        network_attempt_count=tripwire.attempt_count,
        network_attempts=tuple(
            {
                "operation": attempt.operation,
                "target": attempt.target,
            }
            for attempt in tripwire.attempts
        ),
    )


def freeze_checkpoint8_controlling_proof_summary(
    prepared,
    sequence,
) -> Path:
    """Freeze the one-shot result and post-run safety evidence exactly once."""
    sentinel_path = Path(sequence.sentinel_path).resolve()
    if not sentinel_path.is_file():
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_CONTROLLING_ATTEMPT_SENTINEL_MISSING"
        )

    operation_count = checkpoint8_fixture_transport_operation_count(
        prepared.runtime
    )
    if operation_count <= 0:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FIXTURE_TRANSPORT_OPERATION_COUNT_REQUIRED"
        )

    network_attempt_count = int(sequence.network_attempt_count)
    if network_attempt_count != 0:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_NETWORK_ATTEMPTS_MUST_BE_ZERO"
        )

    replay_zero_work = _checkpoint8_replay_zero_work(sequence.replay)
    if not replay_zero_work:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_REPORT_ONLY_REPLAY_MUST_BE_ZERO_WORK"
        )

    post_run = _checkpoint8_post_run_evidence(prepared)
    if (
        post_run["integrity_check"] != "ok"
        or int(post_run["foreign_key_violations"]) != 0
    ):
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_POST_RUN_DB_INTEGRITY_FAILED"
        )

    terminal = dict(sequence.terminal)
    report = terminal.get("report")
    report = report if isinstance(report, dict) else {}
    campaign_id = str(
        terminal.get("campaign_id")
        or report.get("campaign_id")
        or ""
    ).strip()
    run_id = str(
        report.get("run_id")
        or terminal.get("run_id")
        or ""
    ).strip()

    payload: dict[str, Any] = {
        "summary_schema": "CHECKPOINT8_CONTROLLING_PROOF_SUMMARY_V1",
        "proof_id": prepared.runtime.plan.proof_id,
        "git_head": str(prepared.pre_run_evidence["git_head"]),
        "campaign_id": campaign_id,
        "run_id": run_id,
        "campaign_acceptance_verdict": terminal.get(
            "campaign_acceptance_verdict"
        ),
        "campaign_pass": bool(terminal.get("campaign_pass")),
        "fixture_composition_manifest_sha256": (
            prepared.runtime.fixture_composition_manifest_sha256
        ),
        "fixture_transport_operation_count": operation_count,
        "network_attempt_count": network_attempt_count,
        "network_attempts": list(sequence.network_attempts),
        "replay_zero_work": replay_zero_work,
        "pre_run_evidence": dict(prepared.pre_run_evidence),
        "post_run_evidence": post_run,
        "terminal": terminal,
        "report_only": dict(sequence.replay),
        "sentinel_path": str(sentinel_path),
    }

    digest_input = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload["frozen_evidence_sha256"] = hashlib.sha256(
        digest_input
    ).hexdigest()

    summary_path = (
        Path(prepared.proof_root).resolve()
        / "checkpoint8-controlling-proof-summary.json"
    )
    try:
        with summary_path.open("x", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise Checkpoint8ControllingProofError(
            "CHECKPOINT8_FROZEN_SUMMARY_ALREADY_EXISTS"
        ) from exc
    return summary_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "One-shot Checkpoint 8 disposable public-composition proof harness"
        )
    )
    parser.add_argument("--proof-root", required=True)
    parser.add_argument("--proof-id", required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    git_head = validate_checkpoint8_git_entry(
        repo_root,
        expected_head=args.expected_head,
    )
    prepared = prepare_checkpoint8_controlling_entry(
        args.proof_root,
        proof_id=args.proof_id,
        git_head=git_head,
    )
    sequence = execute_checkpoint8_public_sequence(
        prepared,
        git_head=git_head,
    )
    summary_path = freeze_checkpoint8_controlling_proof_summary(
        prepared,
        sequence,
    )
    print(str(summary_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
