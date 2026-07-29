"""Pinned, transport-free Pump creation/migration and PumpSwap pool contracts.

The decoders in this module are deliberately strict and operate only on frozen
Solana RPC-shaped data. Unknown instruction/account layouts fail closed. The
module performs no RPC, WebSocket, persistence, signing, or execution.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Mapping, Sequence

from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode


OFFICIAL_REPOSITORY_COMMIT = "9c82f61cb711b044a17f770ab8ce9f9bdf78f333"
PUMP_IDL_SHA256 = "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"
PUMPSWAP_IDL_SHA256 = "6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56"
PUMP_CREATE_DISCRIMINATOR = bytes.fromhex("181ec828051c0777")
PUMP_CREATE_V2_DISCRIMINATOR = bytes.fromhex("d6904cec5f8b31b4")
PUMP_MIGRATE_DISCRIMINATOR = bytes.fromhex("9beae792ec9ea21e")
PUMP_BONDING_CURVE_DISCRIMINATOR = bytes.fromhex("17b7f83760d8ac60")
PUMPSWAP_POOL_DISCRIMINATOR = bytes.fromhex("f19a6d0411b16dbc")
PUMP_CREATE_EVENT_DISCRIMINATOR = bytes.fromhex("1b72a94ddeeb6376")
PUMP_COMPLETE_EVENT_DISCRIMINATOR = bytes.fromhex("5f72619cd42e9808")
PUMP_MIGRATION_EVENT_DISCRIMINATOR = bytes.fromhex("bde95db95c94ea94")
PUMPSWAP_CREATE_POOL_EVENT_DISCRIMINATOR = bytes.fromhex("b1310cd2a076a774")

TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM_ID = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
ASSOCIATED_TOKEN_PROGRAM_ID = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"
RENT_SYSVAR_ID = "SysvarRent111111111111111111111111111111111"
METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
MAYHEM_PROGRAM_ID = "MAyhSmzXzV1pTf7LsNkrNwkWKTo4ougAJ1PPg47MD4e"
WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
CANONICAL_POOL_INDEX = 0

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_PDA_MARKER = b"ProgramDerivedAddress"
_ED25519_P = 2**255 - 19
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P


def _b58encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = _BASE58_ALPHABET[remainder] + encoded
    leading = len(raw) - len(raw.lstrip(b"\0"))
    return "1" * leading + (encoded or ("" if leading else "1"))


def _is_ed25519_point(raw: bytes) -> bool:
    """Match Solana's PDA on-curve rejection for a compressed Edwards point."""
    if len(raw) != 32:
        return False
    encoded = int.from_bytes(raw, "little")
    sign = encoded >> 255
    y = encoded & ((1 << 255) - 1)
    if y >= _ED25519_P:
        return False
    y2 = y * y % _ED25519_P
    denominator = (_ED25519_D * y2 + 1) % _ED25519_P
    if denominator == 0:
        return False
    x2 = (y2 - 1) * pow(denominator, _ED25519_P - 2, _ED25519_P) % _ED25519_P
    x = pow(x2, (_ED25519_P + 3) // 8, _ED25519_P)
    if x * x % _ED25519_P != x2:
        x = x * pow(2, (_ED25519_P - 1) // 4, _ED25519_P) % _ED25519_P
    if x * x % _ED25519_P != x2 or (x == 0 and sign == 1):
        return False
    return True


def derive_program_address(seeds: Sequence[bytes], program_id: str) -> tuple[str, int]:
    """Derive a Solana PDA with the canonical descending bump search."""
    program = _b58decode(program_id)
    if program is None or len(program) != 32:
        raise ValueError("invalid program id")
    if len(seeds) > 16 or any(len(seed) > 32 for seed in seeds):
        raise ValueError("invalid PDA seed contract")
    for bump in range(255, -1, -1):
        digest = hashlib.sha256(b"".join((*seeds, bytes([bump]), program, _PDA_MARKER))).digest()
        if not _is_ed25519_point(digest):
            return _b58encode(digest), bump
    raise ValueError("no viable PDA bump")


def derive_canonical_pumpswap_pool(
    *, creator: str, base_mint: str, quote_mint: str = WSOL_MINT
) -> tuple[str, int]:
    creator_raw, base_raw, quote_raw = (
        _b58decode(creator), _b58decode(base_mint), _b58decode(quote_mint)
    )
    if any(value is None or len(value) != 32 for value in (creator_raw, base_raw, quote_raw)):
        raise ValueError("invalid canonical pool seed pubkey")
    return derive_program_address(
        (b"pool", CANONICAL_POOL_INDEX.to_bytes(2, "little"), creator_raw, base_raw, quote_raw),
        PUMPSWAP_AMM_PROGRAM_ID,
    )


def _derive_ata(*, owner: str, token_program: str, mint: str) -> str:
    owner_raw, program_raw, mint_raw = (
        _b58decode(owner), _b58decode(token_program), _b58decode(mint)
    )
    if any(value is None or len(value) != 32 for value in (owner_raw, program_raw, mint_raw)):
        raise ValueError("invalid ATA seed pubkey")
    return derive_program_address(
        (owner_raw, program_raw, mint_raw), ASSOCIATED_TOKEN_PROGRAM_ID
    )[0]


def _account_keys(tx_result: Mapping[str, Any]) -> list[str]:
    message = ((tx_result.get("transaction") or {}).get("message") or {})
    meta = tx_result.get("meta") or {}
    keys: list[str] = []
    for entry in message.get("accountKeys") or []:
        key = entry.get("pubkey") if isinstance(entry, Mapping) else entry
        if isinstance(key, str):
            keys.append(key)
    loaded = meta.get("loadedAddresses") or {}
    for kind in ("writable", "readonly"):
        keys.extend(key for key in loaded.get(kind) or [] if isinstance(key, str))
    return keys


def _instructions(tx_result: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    message = ((tx_result.get("transaction") or {}).get("message") or {})
    instructions = list(message.get("instructions") or [])
    for group in (tx_result.get("meta") or {}).get("innerInstructions") or []:
        instructions.extend(group.get("instructions") or [])
    return [item for item in instructions if isinstance(item, Mapping)]


def _instruction_data(item: Mapping[str, Any]) -> bytes | None:
    data = item.get("data")
    return _b58decode(data) if isinstance(data, str) else None


def decode_supported_pump_creation_instruction(
    item: Mapping[str, Any], account_keys: Sequence[str]
) -> dict[str, Any]:
    """Decode only the pinned `create` and `create_v2` instruction variants."""
    result: dict[str, Any] = {"supported": False, "reason": "unsupported_creation_layout"}
    try:
        program = account_keys[int(item["programIdIndex"])]
        accounts = [account_keys[int(index)] for index in item.get("accounts") or []]
    except (KeyError, TypeError, ValueError, IndexError):
        result["reason"] = "malformed_creation_instruction"
        return result
    data = _instruction_data(item)
    if program != PUMP_PROGRAM_ID or data is None or len(data) < 8:
        return result
    if data[:8] == PUMP_CREATE_DISCRIMINATOR and len(accounts) == 14:
        variant = "create"
        fixed = {
            5: METADATA_PROGRAM_ID, 8: SYSTEM_PROGRAM_ID, 9: TOKEN_PROGRAM_ID,
            10: ASSOCIATED_TOKEN_PROGRAM_ID, 11: RENT_SYSVAR_ID, 13: PUMP_PROGRAM_ID,
        }
    elif data[:8] == PUMP_CREATE_V2_DISCRIMINATOR and len(accounts) in {16, 19}:
        variant = "create_v2"
        fixed = {
            6: SYSTEM_PROGRAM_ID, 7: TOKEN_2022_PROGRAM_ID,
            8: ASSOCIATED_TOKEN_PROGRAM_ID, 9: MAYHEM_PROGRAM_ID,
            15: PUMP_PROGRAM_ID,
        }
        if len(accounts) == 19 and (
            accounts[16] not in {WSOL_MINT, USDC_MINT}
            or accounts[18] not in {TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID}
        ):
            return {**result, "reason": "unsupported_create_v2_quote_contract"}
    else:
        return result
    if any(accounts[position] != expected for position, expected in fixed.items()):
        return {**result, "reason": "creation_fixed_account_mismatch"}
    mint_raw = _b58decode(accounts[0])
    if mint_raw is None or len(mint_raw) != 32:
        return {**result, "reason": "creation_mint_invalid"}
    expected_mint_authority = derive_program_address((b"mint-authority",), PUMP_PROGRAM_ID)[0]
    expected_bonding_curve = derive_program_address(
        (b"bonding-curve", mint_raw), PUMP_PROGRAM_ID
    )[0]
    if accounts[1] != expected_mint_authority or accounts[2] != expected_bonding_curve:
        return {**result, "reason": "creation_pda_mismatch"}
    return {
        "supported": True,
        "reason": "supported_pump_creation",
        "variant": variant,
        "mint": accounts[0],
        "bonding_curve": accounts[2],
        "program_id": PUMP_PROGRAM_ID,
        "contract_hash": PUMP_IDL_SHA256,
    }


def decode_pumpswap_pool_account(
    account_value: Mapping[str, Any] | None, *, pool_address: str
) -> dict[str, Any]:
    """Decode the pinned Pool prefix and optional append-only extensions."""
    failed = {"decoded": False, "reason": "pool_account_missing", "pool_address": pool_address}
    if not account_value:
        return failed
    if account_value.get("owner") != PUMPSWAP_AMM_PROGRAM_ID:
        return {**failed, "reason": "pool_owner_mismatch"}
    data = account_value.get("data")
    if not isinstance(data, (list, tuple)) or not data or not isinstance(data[0], str):
        return {**failed, "reason": "pool_data_encoding_unsupported"}
    try:
        raw = base64.b64decode(data[0], validate=True)
    except (ValueError, TypeError):
        return {**failed, "reason": "pool_data_undecodable"}
    legacy_length = 8 + 1 + 2 + 32 * 6 + 8 + 32 + 1
    current_length = legacy_length + 1 + 16
    if len(raw) not in {legacy_length, current_length}:
        return {**failed, "reason": "unsupported_pool_account_length", "data_length": len(raw)}
    if raw[:8] != PUMPSWAP_POOL_DISCRIMINATOR:
        return {**failed, "reason": "pool_discriminator_mismatch"}
    offset = 8
    bump = raw[offset]; offset += 1
    index = int.from_bytes(raw[offset:offset + 2], "little"); offset += 2
    fields: dict[str, str] = {}
    for name in (
        "creator", "base_mint", "quote_mint", "lp_mint",
        "pool_base_token_account", "pool_quote_token_account",
    ):
        fields[name] = _b58encode(raw[offset:offset + 32]); offset += 32
    lp_supply = int.from_bytes(raw[offset:offset + 8], "little"); offset += 8
    coin_creator = _b58encode(raw[offset:offset + 32]); offset += 32
    is_mayhem_mode = bool(raw[offset]); offset += 1
    is_cashback_coin = False
    virtual_quote_reserves = 0
    if len(raw) == current_length:
        is_cashback_coin = bool(raw[offset]); offset += 1
        virtual_quote_reserves = int.from_bytes(raw[offset:offset + 16], "little", signed=True)
    return {
        "decoded": True,
        "reason": "pinned_pool_layout_decoded",
        "pool_address": pool_address,
        "pool_bump": bump,
        "index": index,
        **fields,
        "lp_supply": lp_supply,
        "coin_creator": coin_creator,
        "is_mayhem_mode": is_mayhem_mode,
        "is_cashback_coin": is_cashback_coin,
        "virtual_quote_reserves": virtual_quote_reserves,
        "append_only_extension": len(raw) == current_length,
        "contract_hash": PUMPSWAP_IDL_SHA256,
    }


def verify_pinned_pump_migration(
    tx_result: Mapping[str, Any] | None,
    account_infos: Mapping[str, Mapping[str, Any] | None],
    *, expected_mint: str, finalized: bool,
) -> dict[str, Any]:
    """Verify exact migrate discriminator/accounts plus canonical PumpSwap Pool."""
    result: dict[str, Any] = {"verified": False, "reason": "transaction_missing"}
    if not tx_result:
        return result
    if not finalized:
        return {**result, "reason": "finalized_commitment_required"}
    if tx_result.get("version") not in (None, "legacy", 0):
        return {**result, "reason": "unsupported_transaction_version"}
    meta = tx_result.get("meta")
    if not isinstance(meta, Mapping) or meta.get("err") is not None:
        return {**result, "reason": "transaction_failed_or_meta_missing"}
    if not isinstance(tx_result.get("blockTime"), (int, float)) or not isinstance(tx_result.get("slot"), int):
        return {**result, "reason": "finalized_slot_or_block_time_missing"}
    keys = _account_keys(tx_result)
    matches: list[list[str]] = []
    for instruction in _instructions(tx_result):
        try:
            program = keys[int(instruction["programIdIndex"])]
            accounts = [keys[int(index)] for index in instruction.get("accounts") or []]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        data = _instruction_data(instruction)
        if program == PUMP_PROGRAM_ID and data is not None and data[:8] == PUMP_MIGRATE_DISCRIMINATOR:
            if len(accounts) != 25:
                return {**result, "reason": "migrate_account_layout_mismatch"}
            matches.append(accounts)
    if len(matches) != 1:
        return {**result, "reason": "exactly_one_migrate_instruction_required"}
    accounts = matches[0]
    fixed = {
        2: expected_mint,
        6: SYSTEM_PROGRAM_ID,
        7: TOKEN_PROGRAM_ID,
        8: PUMPSWAP_AMM_PROGRAM_ID,
        14: WSOL_MINT,
        19: TOKEN_2022_PROGRAM_ID,
        20: ASSOCIATED_TOKEN_PROGRAM_ID,
        23: PUMP_PROGRAM_ID,
        24: RENT_SYSVAR_ID,
    }
    for ordinal, expected in fixed.items():
        if accounts[ordinal] != expected:
            return {**result, "reason": f"migrate_account_{ordinal}_mismatch"}
    pool_address, creator = accounts[9], accounts[10]
    decoded = decode_pumpswap_pool_account(account_infos.get(pool_address), pool_address=pool_address)
    if not decoded.get("decoded"):
        return {**result, "reason": decoded["reason"], "pool": decoded}
    if decoded["index"] != CANONICAL_POOL_INDEX:
        return {**result, "reason": "noncanonical_pool_index", "pool": decoded}
    if decoded["creator"] != creator or decoded["base_mint"] != expected_mint or decoded["quote_mint"] != WSOL_MINT:
        return {**result, "reason": "pool_identity_mismatch", "pool": decoded}
    try:
        expected_bonding_curve = derive_program_address(
            (b"bonding-curve", _b58decode(expected_mint)), PUMP_PROGRAM_ID
        )[0]
        expected_creator = derive_program_address(
            (b"pool-authority", _b58decode(expected_mint)), PUMP_PROGRAM_ID
        )[0]
        expected_pool, expected_bump = derive_canonical_pumpswap_pool(
            creator=creator, base_mint=expected_mint, quote_mint=WSOL_MINT
        )
        expected_lp_mint = derive_program_address(
            (b"pool_lp_mint", _b58decode(pool_address)), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        expected_base_vault = _derive_ata(
            owner=pool_address, token_program=TOKEN_PROGRAM_ID, mint=expected_mint
        )
        expected_quote_vault = _derive_ata(
            owner=pool_address, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
        )
    except ValueError:
        return {**result, "reason": "canonical_pool_seed_invalid", "pool": decoded}
    if accounts[3] != expected_bonding_curve or creator != expected_creator:
        return {**result, "reason": "pump_migration_pda_mismatch", "pool": decoded}
    if pool_address != expected_pool or decoded["pool_bump"] != expected_bump:
        return {**result, "reason": "canonical_pool_pda_mismatch", "pool": decoded}
    if (
        accounts[15] != expected_lp_mint
        or decoded["lp_mint"] != expected_lp_mint
        or accounts[17] != expected_base_vault
        or decoded["pool_base_token_account"] != expected_base_vault
        or accounts[18] != expected_quote_vault
        or decoded["pool_quote_token_account"] != expected_quote_vault
    ):
        return {**result, "reason": "canonical_pool_vault_or_lp_mismatch", "pool": decoded}
    return {
        "verified": True,
        "reason": "pinned_pump_migration_and_canonical_pool_verified",
        "mint": expected_mint,
        "pool_address": pool_address,
        "creator": creator,
        "migration_slot": int(tx_result["slot"]),
        "migration_block_time": int(tx_result["blockTime"]),
        "pump_contract_hash": PUMP_IDL_SHA256,
        "pumpswap_contract_hash": PUMPSWAP_IDL_SHA256,
        "pool": decoded,
    }


__all__ = [
    "OFFICIAL_REPOSITORY_COMMIT", "PUMP_IDL_SHA256", "PUMPSWAP_IDL_SHA256",
    "PUMP_CREATE_DISCRIMINATOR", "PUMP_CREATE_V2_DISCRIMINATOR",
    "PUMP_MIGRATE_DISCRIMINATOR", "PUMP_BONDING_CURVE_DISCRIMINATOR",
    "PUMPSWAP_POOL_DISCRIMINATOR", "TOKEN_PROGRAM_ID", "TOKEN_2022_PROGRAM_ID",
    "SYSTEM_PROGRAM_ID", "ASSOCIATED_TOKEN_PROGRAM_ID", "RENT_SYSVAR_ID",
    "METADATA_PROGRAM_ID", "MAYHEM_PROGRAM_ID", "WSOL_MINT", "USDC_MINT",
    "CANONICAL_POOL_INDEX", "derive_program_address",
    "derive_canonical_pumpswap_pool", "decode_supported_pump_creation_instruction",
    "decode_pumpswap_pool_account", "verify_pinned_pump_migration",
]
