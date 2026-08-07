#!/usr/bin/env python3
"""Checkpoint 8 controlling-proof safety shell.

This file intentionally owns only the proof-only safety envelope at this stage:
the process-local network tripwire and the atomic one-shot attempt claim.

It does not construct fixtures, start Printer runtime work, or execute the
controlling proof. Those entry responsibilities remain fail-closed until the
subsequent Checkpoint 8 harness-wiring slice is proven.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import struct
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


def _checkpoint8_candidate_records() -> tuple[dict[str, Any], ...]:
    rows = []
    for ordinal, label in enumerate(("alpha", "bravo")):
        slot = 1_700_000 + ordinal
        block_time = 1_800_000_000 + ordinal * 60
        transaction = _checkpoint8_create_transaction(
            label=label,
            slot=slot,
            block_time=block_time,
        )
        mint = transaction["transaction"]["message"]["accountKeys"][0]
        curve = transaction["transaction"]["message"]["accountKeys"][2]
        signature = transaction["transaction"]["signatures"][0]
        rows.append(
            {
                "label": label,
                "mint": mint,
                "pool": curve,
                "signature": signature,
                "slot": slot,
                "block_time": block_time,
                "transaction": transaction,
            }
        )
    return tuple(rows)


def _checkpoint8_gecko_pool_body(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": {
            "id": f"solana_{candidate['pool']}",
            "type": "pool",
            "attributes": {
                "address": candidate["pool"],
                "transactions": {"m5": {"buys": 6, "sells": 4}},
            },
            "relationships": {
                "base_token": {
                    "data": {
                        "id": f"solana_{candidate['mint']}",
                        "type": "token",
                    }
                },
                "quote_token": {
                    "data": {
                        "id": (
                            "solana_"
                            "So11111111111111111111111111111111111111112"
                        ),
                        "type": "token",
                    }
                },
                "dex": {"data": {"id": "pump-fun", "type": "dex"}},
            },
        }
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
    """Zero-provider fixture with explicit route-shaped response contracts."""

    def __init__(self, route: str) -> None:
        self.route = str(route)
        self.operation_count = 0

    def _count(self) -> None:
        self.operation_count += 1

    def __call__(self, *args, **kwargs):
        self._count()
        del args, kwargs
        return self

    def execute(self, *args, **kwargs):
        self._count()
        del args, kwargs
        candidates = _checkpoint8_candidate_records()
        if self.route == "lifecycle.context_adapter_factories.coingecko":
            return {
                "captured_at": "2026-08-07T12:00:00+00:00",
                "assets": {
                    "bitcoin": {"price_usd": 65000, "change_24h": 1.0},
                    "ethereum": {"price_usd": 3500, "change_24h": 1.0},
                    "solana": {
                        "price_usd": 150,
                        "change_24h": 2.0,
                        "volume_24h": 2_000_000_000,
                    },
                },
            }
        if self.route == "lifecycle.context_adapter_factories.goplus":
            return {
                "token_mint": candidates[0]["mint"],
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
            }
        if self.route == "lifecycle.context_adapter_factories.jupiter_quote":
            return {
                "route_available": True,
                "route_plan_present": True,
                "slippage_bps": 50,
                "price_impact_bps": 5,
                "freshness_label": "QUOTE_FRESH",
                "target_status": "TARGET_MATCH",
                "paper_only_context": True,
                "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
            }
        if self.route in {
            "lifecycle.context_adapter_factories.solana_rpc_holder",
            "lifecycle.context_adapter_factories.helius_holder_backup",
        }:
            return {
                "holder_count": 20,
                "top_10_percent": 30.0,
                "largest_holder_percent": 5.0,
            }
        if self.route in {
            "lifecycle.snapshot_adapter_factory",
            "lifecycle.fallback_snapshot_adapter_factory",
        }:
            return {
                "pairs": [
                    {
                        "chain": "solana",
                        "token_mint": row["mint"],
                        "pair_address": row["pool"],
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
                    for row in candidates
                ]
            }
        return {"fixture_route": self.route, "status": "READY"}

    def json_get(self, url, *args, **kwargs):
        self._count()
        del args, kwargs
        candidates = _checkpoint8_candidate_records()
        url_text = str(url)
        if self.route == "top_level.secondary_transport":
            if "trending_pools" in url_text:
                return {"data": []}
            if "token-profiles" in url_text:
                return []
            for candidate in candidates:
                if candidate["pool"] in url_text:
                    return _checkpoint8_gecko_pool_body(candidate)
            return {"data": []}
        return {"fixture_route": self.route, "url": url_text, "data": []}

    def json_rpc(self, method, params=None, *args, **kwargs):
        self._count()
        del args, kwargs
        candidates = _checkpoint8_candidate_records()
        if isinstance(method, dict):
            return {"fixture": True, "route": self.route}
        method_text = str(method)
        if self.route == "top_level.pump_transport":
            if method_text == "getSignaturesForAddress":
                return [
                    {
                        "signature": row["signature"],
                        "slot": row["slot"],
                        "confirmationStatus": "finalized",
                        "err": None,
                    }
                    for row in reversed(candidates)
                ]
            if method_text == "getTransaction":
                signature = str((params or [""])[0])
                for row in candidates:
                    if row["signature"] == signature:
                        return row["transaction"]
                return None
        return {
            "fixture_route": self.route,
            "method": method_text,
            "result": [],
        }


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



def execute_checkpoint8_public_sequence(
    prepared,
    *,
    git_head: str,
):
    """Fail closed until the separate one-shot execution slice is GREEN."""
    del git_head
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
    raise Checkpoint8ControllingProofError(
        "CHECKPOINT8_EXECUTION_ENTRY_NOT_YET_WIRED"
    )


def main(argv: list[str] | None = None) -> int:
    del argv
    raise Checkpoint8ControllingProofError(
        "CHECKPOINT8_CONTROLLING_PROOF_ENTRY_NOT_YET_WIRED"
    )


if __name__ == "__main__":
    raise SystemExit(main())
