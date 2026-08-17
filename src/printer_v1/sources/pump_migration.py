"""Exact pinned Pump migration proof + combined graduation verifier.

The authoritative graduation evidence is the finalized Solana transaction plus
the PumpSwap account confirmation. The active locator supplies only a bounded,
stateless direct-Solana observation; it is not graduation authority. This
module adds the exact **Pump migration** proof layer on top of the
already-adopted PumpSwap signature→pool resolution and pool confirmation.

`prove_pump_migration_transaction` is pure and deterministic: it proves the
finalized migration transaction is the applicable Pump migration for the exact mint
using only **adopted** program identities:

  * the transaction succeeded (`meta.err is None`);
  * the exact mint is referenced in the transaction account keys (static + ALT);
  * the adopted Pump.fun program is invoked (present in account keys);
  * the adopted PumpSwap AMM program is invoked (present in account keys — the
    graduation pool is created/touched in this same transaction);
  * a finalized block time is present (graduation evidence only).

The active verifier reuses the pinned official Pump/PumpSwap IDLs and exact
instruction/account/PDA/pool-layout checks. Read-only. No execution, signing or
fund movement.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.sources.contracts import SourceAdapterContext
from printer_v1.sources.operational_source_contracts import (
    resolve_solana_rpc_configuration,
)
from printer_v1.sources.pump_contracts import verify_pinned_pump_migration
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.measured_transport import (
    MeasuredTransportError,
    build_transport_identity,
    measured_payload_fields,
    pumpswap_verification_transport_count,
)
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _rpc_post,
    collect_transaction_account_keys,
    confirm_pumpswap_pool_from_account,
    resolve_pumpswap_pool_from_transaction,
)

MIGRATION_PROVENANCE = "DIRECT_PUMP_FINALIZED_LIVE_TAIL"

# Optional tolerance for a block time slightly ahead of the caller's clock.
_FUTURE_BLOCK_TIME_TOLERANCE_SECONDS = 300


def prove_pump_migration_transaction(
    tx_result: Mapping[str, Any] | None,
    *,
    expected_mint: str,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    """Prove a finalized transaction is the applicable Pump migration for a mint.

    Pure/deterministic. Every check is a hard categorical equality/membership; no
    numeric magnitude is compared. Never raises. Returns a dict with ``proven`` and
    a ``reason``; migration block time / slot are captured as graduation evidence
    only and never become token creation time.
    """
    result: dict[str, Any] = {
        "proven": False,
        "reason": None,
        "expected_mint": expected_mint,
        "pump_program_id": PUMP_PROGRAM_ID,
        "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "account_keys_total": 0,
        "mint_present": False,
        "pump_program_present": False,
        "pumpswap_program_present": False,
        "migration_block_time": None,
        "migration_slot": None,
    }
    if not isinstance(expected_mint, str) or not expected_mint:
        result["reason"] = "expected_mint_invalid"
        return result
    if not tx_result:
        result["reason"] = "migration_transaction_not_found"
        return result
    meta = tx_result.get("meta")
    if not isinstance(meta, Mapping):
        result["reason"] = "migration_transaction_meta_missing"
        return result
    if meta.get("err") is not None:
        result["reason"] = "migration_transaction_failed"
        return result

    keys = collect_transaction_account_keys(tx_result)
    result["account_keys_total"] = len(keys)
    keyset = set(keys)
    result["mint_present"] = expected_mint in keyset
    result["pump_program_present"] = PUMP_PROGRAM_ID in keyset
    result["pumpswap_program_present"] = PUMPSWAP_AMM_PROGRAM_ID in keyset

    bt = tx_result.get("blockTime")
    result["migration_block_time"] = int(bt) if isinstance(bt, (int, float)) else None
    sl = tx_result.get("slot")
    result["migration_slot"] = int(sl) if isinstance(sl, (int, float)) else None

    if not result["mint_present"]:
        result["reason"] = "mint_not_referenced"
        return result
    if not result["pump_program_present"]:
        result["reason"] = "pump_program_not_present"
        return result
    if not result["pumpswap_program_present"]:
        result["reason"] = "pumpswap_program_not_invoked"
        return result
    if result["migration_block_time"] is None:
        result["reason"] = "migration_block_time_missing"
        return result
    if now_epoch is not None and result["migration_block_time"] > int(now_epoch) + _FUTURE_BLOCK_TIME_TOLERANCE_SECONDS:
        result["reason"] = "migration_block_time_in_future"
        return result

    result["proven"] = True
    result["reason"] = "proven_pump_migration"
    return result


def verify_graduation_from_transaction(
    tx_result: Mapping[str, Any] | None,
    account_infos: Mapping[str, Mapping[str, Any] | None],
    *,
    expected_mint: str,
    now_epoch: int | None = None,
) -> dict[str, Any]:
    """Full graduation verification over a fetched migration transaction.

    Pure/deterministic. Runs the exact Pump migration proof, then the existing
    unique-or-fail PumpSwap pool resolution, then pool confirmation. Fails closed at
    the first failing stage. Returns a dict with ``verified`` and the per-stage
    evidence.
    """
    strict = verify_pinned_pump_migration(
        tx_result,
        account_infos,
        expected_mint=expected_mint,
        finalized=True,
    )
    if not strict["verified"]:
        return {
            "verified": False,
            "stage": "PUMP_MIGRATION_PROOF",
            "reason": strict["reason"],
            "pump_migration_proof": strict,
            "pumpswap_resolution": None,
            "pumpswap_confirmation": None,
        }
    if (
        now_epoch is not None
        and int(strict["migration_block_time"])
        > int(now_epoch) + _FUTURE_BLOCK_TIME_TOLERANCE_SECONDS
    ):
        return {
            "verified": False,
            "stage": "PUMP_MIGRATION_PROOF",
            "reason": "migration_block_time_in_future",
            "pump_migration_proof": strict,
            "pumpswap_resolution": None,
            "pumpswap_confirmation": None,
        }

    pool = str(strict["pool_address"])
    decoded_pool = dict(strict["pool"])
    resolution = {
        "resolved": True,
        "reason": "pinned_exact_pumpswap_pool_join",
        "pool_address": pool,
        "expected_mint": expected_mint,
        "program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "mint_matched_count": 1,
        "migration_block_time": strict["migration_block_time"],
        "migration_slot": strict["migration_slot"],
    }
    confirmation = {
        "confirmed": True,
        "reason": "pinned_exact_pumpswap_pool_join",
        "pool_address": pool,
        "expected_mint": expected_mint,
        "program_id": PUMPSWAP_AMM_PROGRAM_ID,
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "base_mint": decoded_pool["base_mint"],
        "quote_mint": decoded_pool["quote_mint"],
        "pool_contract_hash": decoded_pool["contract_hash"],
    }

    return {
        "verified": True,
        "stage": "CONFIRMED",
        "reason": "pumpswap_graduated_confirmed",
        "pump_migration_proof": strict,
        "pumpswap_resolution": resolution,
        "pumpswap_confirmation": confirmation,
        "pool_address": pool,
        "migration_block_time": strict["migration_block_time"],
        "migration_slot": strict["migration_slot"],
    }


GRADUATION_VERIFIER_TIMEOUT_SECONDS = 20.0


def build_graduation_verifier_transport(
    *,
    migration_signature: str,
    expected_mint: str,
    rpc_url: str | None = None,
    timeout_seconds: float = GRADUATION_VERIFIER_TIMEOUT_SECONDS,
    now_epoch: int | None = None,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Bounded governed transport: verify a Pump graduation from a migration sig.

    Read-only sequence (same governed operations as the PumpSwap signature
    resolver): ``getTransaction(signature)`` then batched ``getMultipleAccounts``.
    Then the pure exact Pump migration proof + unique PumpSwap pool resolution +
    pool confirmation. On success returns the payload consumed by
    ``normalize_pumpswap_confirmation_payload`` plus the Pump migration proof and
    provenance. On any failing stage returns a fail-closed ``fixture_status`` failure
    that the confirmation normalizer rejects. No DexScreener dependency. No writes,
    no execution, no signing. Migration block time is graduation evidence only.
    """

    endpoint = rpc_url or resolve_solana_rpc_configuration().url

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        identities = []
        ordinal = 0

        def _record(method: str, payload: Mapping[str, Any], *, rows: int = 0) -> None:
            nonlocal ordinal
            ordinal += 1
            identities.append(
                build_transport_identity(
                    stage="PUMPSWAP_EXACT_VERIFICATION",
                    source_name="solana_rpc",
                    endpoint_owner="solana",
                    governed_request_kind="pumpswap_signature_pool_resolution",
                    method_or_endpoint=method,
                    within_request_ordinal=ordinal,
                    target_category="migration_signature"
                    if method == "getTransaction"
                    else "account_batch",
                    target_identity=migration_signature
                    if method == "getTransaction"
                    else expected_mint,
                    response_bytes=int(payload.get("response_bytes") or 0),
                    normalized_rows=int(rows),
                    result=(
                        "FAILED"
                        if payload.get("fixture_status") == "failure"
                        else "OK"
                    ),
                )
            )

        tx = _rpc_post(
            endpoint,
            "getTransaction",
            [
                migration_signature,
                {
                    "maxSupportedTransactionVersion": 0,
                    "encoding": "json",
                    "commitment": "finalized",
                },
            ],
            timeout_seconds=timeout_seconds,
        )
        _record("getTransaction", tx, rows=1 if isinstance(tx.get("result"), Mapping) else 0)
        if tx.get("fixture_status") == "failure":
            failed = dict(tx)
            failed.update(measured_payload_fields(identities))
            return MappingProxyType(failed)
        tx_result = tx.get("result")
        if not isinstance(tx_result, Mapping):
            payload = {
                "fixture_status": "failure",
                "failure_type": "pump_migration_transaction_not_found",
                "failure_message": "getTransaction returned no result for migration signature",
            }
            payload.update(measured_payload_fields(identities))
            return MappingProxyType(payload)

        keys = collect_transaction_account_keys(tx_result)
        try:
            expected_transport_operations = pumpswap_verification_transport_count(
                len(keys)
            )
        except MeasuredTransportError as exc:
            payload = {
                "fixture_status": "failure",
                "failure_type": "pumpswap_account_batch_ceiling",
                "failure_message": str(exc),
            }
            payload.update(measured_payload_fields(identities))
            return MappingProxyType(payload)
        account_infos: dict[str, Any] = {}
        for i in range(0, len(keys), 100):
            chunk = keys[i : i + 100]
            res = _rpc_post(
                endpoint,
                "getMultipleAccounts",
                [chunk, {"encoding": "base64", "commitment": "finalized"}],
                timeout_seconds=timeout_seconds,
            )
            _record("getMultipleAccounts", res, rows=len(chunk))
            if res.get("fixture_status") == "failure":
                failed = dict(res)
                failed.update(measured_payload_fields(identities))
                failed["expected_transport_operations"] = expected_transport_operations
                return MappingProxyType(failed)
            values = (res.get("result") or {}).get("value") or []
            for k, v in zip(chunk, values):
                account_infos[k] = v

        verification = verify_graduation_from_transaction(
            tx_result, account_infos, expected_mint=expected_mint, now_epoch=now_epoch
        )
        measured = measured_payload_fields(identities)
        measured["expected_transport_operations"] = expected_transport_operations
        if not verification["verified"]:
            return MappingProxyType({
                "fixture_status": "failure",
                "failure_type": (
                    f"graduation_verification_failed_"
                    f"{verification['stage'].lower()}_{verification.get('reason') or 'unknown'}"
                ),
                "failure_message": (
                    f"Pump graduation not verified at {verification['stage']}: "
                    f"{verification.get('reason')}"
                ),
                "pump_migration_proof": verification["pump_migration_proof"],
                "pumpswap_resolution": verification["pumpswap_resolution"],
                **measured,
            })

        return MappingProxyType({
            "pumpswap_confirmation": verification["pumpswap_confirmation"],
            "pumpswap_resolution": verification["pumpswap_resolution"],
            "pump_migration_proof": verification["pump_migration_proof"],
            "migration_provenance": MIGRATION_PROVENANCE,
            "migration_signature": migration_signature,
            "migration_block_time": verification["migration_block_time"],
            "migration_slot": verification["migration_slot"],
            **measured,
        })

    return transport
