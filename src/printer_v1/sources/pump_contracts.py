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


# Official pump-fun/pump-public-docs pin. Digest recomputed 2026-08-17 from the
# exact raw idl/pump.json bytes at this commit (not copied from a prior pin).
OFFICIAL_REPOSITORY_COMMIT = "3c6721a67c0b206b39130b454c8ba22a83ce972e"
PUMP_IDL_SHA256 = "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"
PUMPSWAP_IDL_SHA256 = "6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56"
PUMP_CREATE_DISCRIMINATOR = bytes.fromhex("181ec828051c0777")
PUMP_CREATE_V2_DISCRIMINATOR = bytes.fromhex("d6904cec5f8b31b4")
PUMP_MIGRATE_DISCRIMINATOR = bytes.fromhex("9beae792ec9ea21e")
PUMP_MIGRATE_V2_DISCRIMINATOR = bytes.fromhex("bbcb121fceedfe29")
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

# Fixed / PDA-derived migrate role constants (pinned IDL + official mainnet).
PUMP_GLOBAL_ID = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
# Mainnet Global.withdraw_authority used by the pinned Pump migrate contract.
# A valid-but-wrong pubkey must not pass relationship validation.
PUMP_WITHDRAW_AUTHORITY_ID = "27m9co5M6RLMFdHXzJz6ktUvN9Dm3GAmttmNrqvnEnjN"
PUMP_EVENT_AUTHORITY_ID = "Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1"
PUMPSWAP_GLOBAL_CONFIG_ID = "ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw"
PUMPSWAP_EVENT_AUTHORITY_ID = "GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR"

MIGRATE_ACCOUNT_ROLES: tuple[str, ...] = (
    "global",
    "withdraw_authority",
    "mint",
    "bonding_curve",
    "associated_bonding_curve",
    "user",
    "system_program",
    "token_program",
    "pump_amm",
    "pool",
    "pool_authority",
    "pool_authority_mint_account",
    "pool_authority_wsol_account",
    "amm_global_config",
    "wsol_mint",
    "lp_mint",
    "user_pool_token_account",
    "pool_base_token_account",
    "pool_quote_token_account",
    "token_2022_program",
    "associated_token_program",
    "pump_amm_event_authority",
    "event_authority",
    "program",
    "rent",
)

# Official IDL migrate_v2 declared accounts 0..26. Never append these to
# MIGRATE_ACCOUNT_ROLES. Witnessed 29-meta envelopes may carry two trailing
# remaining_accounts; those two have no Printer names, roles, or evidence.
MIGRATE_V2_DECLARED_ACCOUNT_ROLES: tuple[str, ...] = (
    "global",
    "withdraw_authority",
    "base_mint",
    "quote_mint",
    "bonding_curve",
    "associated_base_bonding_curve",
    "associated_quote_bonding_curve",
    "user",
    "system_program",
    "pump_amm",
    "pool",
    "pool_authority",
    "pool_authority_mint_account",
    "pool_authority_quote_account",
    "amm_global_config",
    "lp_mint",
    "user_pool_token_account",
    "pool_base_token_account",
    "pool_quote_token_account",
    "base_token_program",
    "quote_token_program",
    "token_2022_program",
    "associated_token_program",
    "pump_amm_event_authority",
    "rent",
    "event_authority",
    "program",
)
MIGRATE_V2_DECLARED_ACCOUNT_COUNT = 27
MIGRATE_V2_WITNESSED_ACCOUNT_COUNTS = frozenset({27, 29})
MIGRATE_V2_REMAINING_ACCOUNT_COUNT = 2

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


def decode_supported_pump_creation_transaction(
    tx_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Locate exactly one pinned Pump create instruction in a finalized tx body."""
    failed: dict[str, Any] = {"supported": False, "reason": "transaction_missing"}
    if not tx_result:
        return failed
    if tx_result.get("version") not in (None, "legacy", 0):
        return {**failed, "reason": "unsupported_transaction_version"}
    meta = tx_result.get("meta")
    if not isinstance(meta, Mapping) or meta.get("err") is not None:
        return {**failed, "reason": "transaction_failed_or_meta_missing"}
    keys = _account_keys(tx_result)
    matches = [
        decoded
        for item in _instructions(tx_result)
        if (decoded := decode_supported_pump_creation_instruction(item, keys)).get("supported")
    ]
    if len(matches) != 1:
        return {**failed, "reason": "exactly_one_supported_create_required"}
    if (
        not isinstance(tx_result.get("slot"), int)
        or int(tx_result["slot"]) < 0
        or not isinstance(tx_result.get("blockTime"), (int, float))
        or int(tx_result["blockTime"]) <= 0
    ):
        return {**failed, "reason": "finalized_slot_or_block_time_missing"}
    return {**matches[0], "slot": int(tx_result["slot"]),
            "block_time": int(tx_result["blockTime"])}


def decode_pump_bonding_curve_account(
    account_value: Mapping[str, Any] | None,
    *,
    bonding_curve_address: str,
    expected_mint: str,
) -> dict[str, Any]:
    """Decode the complete pinned Pump BondingCurve prefix.

    The account does not store the base mint.  The exact mint relationship is
    instead proved by the pinned PDA derivation ``[b"bonding-curve", mint]``;
    quote identity is read from the adopted account prefix.  Longer accounts
    are accepted only after that complete prefix decodes.
    """
    failed: dict[str, Any] = {
        "decoded": False,
        "reason": "bonding_curve_account_missing",
        "bonding_curve_address": bonding_curve_address,
    }
    if not isinstance(account_value, Mapping):
        return failed
    if account_value.get("owner") != PUMP_PROGRAM_ID:
        return {**failed, "reason": "bonding_curve_owner_mismatch"}
    mint_raw = _b58decode(expected_mint)
    if mint_raw is None or len(mint_raw) != 32:
        return {**failed, "reason": "bonding_curve_expected_mint_invalid"}
    expected_curve = derive_program_address(
        (b"bonding-curve", mint_raw), PUMP_PROGRAM_ID
    )[0]
    if bonding_curve_address != expected_curve:
        return {**failed, "reason": "bonding_curve_pda_mismatch"}
    data = account_value.get("data")
    if (
        not isinstance(data, (list, tuple))
        or len(data) < 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        return {**failed, "reason": "bonding_curve_data_encoding_unsupported"}
    try:
        raw = base64.b64decode(data[0], validate=True)
    except (TypeError, ValueError):
        return {**failed, "reason": "bonding_curve_data_undecodable"}
    prefix_length = 8 + (5 * 8) + 1 + 32 + 1 + 1 + 32
    if len(raw) < prefix_length:
        return {
            **failed,
            "reason": "unsupported_bonding_curve_account_length",
            "data_length": len(raw),
        }
    if raw[:8] != PUMP_BONDING_CURVE_DISCRIMINATOR:
        return {**failed, "reason": "bonding_curve_discriminator_mismatch"}
    offset = 8
    reserve_names = (
        "virtual_token_reserves",
        "virtual_quote_reserves",
        "real_token_reserves",
        "real_quote_reserves",
        "token_total_supply",
    )
    decoded: dict[str, Any] = {}
    for name in reserve_names:
        decoded[name] = int.from_bytes(raw[offset:offset + 8], "little")
        offset += 8
    complete_byte = raw[offset]
    offset += 1
    if complete_byte not in {0, 1}:
        return {**failed, "reason": "bonding_curve_complete_flag_invalid"}
    creator = _b58encode(raw[offset:offset + 32])
    offset += 32
    mayhem_byte, cashback_byte = raw[offset], raw[offset + 1]
    offset += 2
    if mayhem_byte not in {0, 1} or cashback_byte not in {0, 1}:
        return {**failed, "reason": "bonding_curve_flag_invalid"}
    quote_mint = _b58encode(raw[offset:offset + 32])
    return {
        "decoded": True,
        "reason": "pinned_bonding_curve_layout_decoded",
        "bonding_curve_address": bonding_curve_address,
        "base_mint": expected_mint,
        "quote_mint": quote_mint,
        "complete": bool(complete_byte),
        "creator": creator,
        "is_mayhem_mode": bool(mayhem_byte),
        "is_cashback_coin": bool(cashback_byte),
        "account_hash": hashlib.sha256(raw).hexdigest(),
        "contract_hash": PUMP_IDL_SHA256,
        "append_only_extension": len(raw) > prefix_length,
        **decoded,
    }


def _valid_pubkey(value: str) -> bool:
    raw = _b58decode(value)
    return raw is not None and len(raw) == 32


def validate_migrate_account_roles(
    accounts: Sequence[str],
    *,
    expected_mint: str | None = None,
) -> dict[str, Any]:
    """Validate all 25 ordered migrate roles and known fixed/PDA relationships.

    Fixed programs/sysvars, PDA/ATA relationships, the pinned mainnet
    withdraw_authority, and optional expected_mint equality each fail closed
    with a distinct reason. Valid-but-wrong substitutions must not pass.
    """
    if len(accounts) != 25:
        return {
            "valid": False,
            "reason": "migrate_account_layout_mismatch",
            "role": None,
            "position": None,
        }
    for index, role in enumerate(MIGRATE_ACCOUNT_ROLES):
        if not isinstance(accounts[index], str) or not accounts[index]:
            return {
                "valid": False,
                "reason": f"migrate_role_{index}_{role}_missing",
                "role": role,
                "position": index,
            }
        if not _valid_pubkey(accounts[index]):
            return {
                "valid": False,
                "reason": f"migrate_role_{index}_{role}_invalid_pubkey",
                "role": role,
                "position": index,
            }

    fixed = {
        0: PUMP_GLOBAL_ID,
        1: PUMP_WITHDRAW_AUTHORITY_ID,
        6: SYSTEM_PROGRAM_ID,
        7: TOKEN_PROGRAM_ID,
        8: PUMPSWAP_AMM_PROGRAM_ID,
        13: PUMPSWAP_GLOBAL_CONFIG_ID,
        14: WSOL_MINT,
        19: TOKEN_2022_PROGRAM_ID,
        20: ASSOCIATED_TOKEN_PROGRAM_ID,
        21: PUMPSWAP_EVENT_AUTHORITY_ID,
        22: PUMP_EVENT_AUTHORITY_ID,
        23: PUMP_PROGRAM_ID,
        24: RENT_SYSVAR_ID,
    }
    for index, expected in fixed.items():
        if accounts[index] != expected:
            role = MIGRATE_ACCOUNT_ROLES[index]
            return {
                "valid": False,
                "reason": f"migrate_role_{index}_{role}_mismatch",
                "role": role,
                "position": index,
                "expected": expected,
                "actual": accounts[index],
            }

    mint = accounts[2]
    user = accounts[5]
    pool = accounts[9]
    pool_authority = accounts[10]
    if expected_mint is not None and mint != expected_mint:
        return {
            "valid": False,
            "reason": "migrate_role_2_mint_mismatch",
            "role": "mint",
            "position": 2,
            "expected": expected_mint,
            "actual": mint,
        }
    # withdraw_authority is fixed above; also reject aliasing other roles.
    other_accounts = {accounts[i] for i in range(25) if i != 1}
    if accounts[1] in other_accounts:
        return {
            "valid": False,
            "reason": "migrate_role_1_withdraw_authority_relation_invalid",
            "role": "withdraw_authority",
            "position": 1,
        }
    if user in {
        accounts[0],
        accounts[1],
        SYSTEM_PROGRAM_ID,
        PUMP_PROGRAM_ID,
        PUMPSWAP_AMM_PROGRAM_ID,
        mint,
        pool,
        pool_authority,
    }:
        return {
            "valid": False,
            "reason": "migrate_role_5_user_invalid",
            "role": "user",
            "position": 5,
        }

    try:
        expected_bonding_curve = derive_program_address(
            (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        expected_associated_bonding = _derive_ata(
            owner=expected_bonding_curve,
            token_program=TOKEN_PROGRAM_ID,
            mint=mint,
        )
        expected_pool_authority = derive_program_address(
            (b"pool-authority", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        expected_pool, _expected_bump = derive_canonical_pumpswap_pool(
            creator=expected_pool_authority, base_mint=mint, quote_mint=WSOL_MINT
        )
        expected_pool_authority_mint = _derive_ata(
            owner=expected_pool_authority,
            token_program=TOKEN_PROGRAM_ID,
            mint=mint,
        )
        expected_pool_authority_wsol = _derive_ata(
            owner=expected_pool_authority,
            token_program=TOKEN_PROGRAM_ID,
            mint=WSOL_MINT,
        )
        expected_lp_mint = derive_program_address(
            (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        expected_user_lp = _derive_ata(
            owner=user, token_program=TOKEN_2022_PROGRAM_ID, mint=expected_lp_mint
        )
        expected_base_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=mint
        )
        expected_quote_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
        )
        expected_global = derive_program_address((b"global",), PUMP_PROGRAM_ID)[0]
        expected_event_authority = derive_program_address(
            (b"__event_authority",), PUMP_PROGRAM_ID
        )[0]
        expected_amm_event_authority = derive_program_address(
            (b"__event_authority",), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        expected_amm_global_config = derive_program_address(
            (b"global_config",), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
    except (TypeError, ValueError):
        return {
            "valid": False,
            "reason": "migrate_role_pda_derivation_failed",
            "role": None,
            "position": None,
        }

    relations = {
        0: expected_global,
        3: expected_bonding_curve,
        4: expected_associated_bonding,
        9: expected_pool,
        10: expected_pool_authority,
        11: expected_pool_authority_mint,
        12: expected_pool_authority_wsol,
        13: expected_amm_global_config,
        15: expected_lp_mint,
        16: expected_user_lp,
        17: expected_base_vault,
        18: expected_quote_vault,
        21: expected_amm_event_authority,
        22: expected_event_authority,
    }
    for index, expected in relations.items():
        if accounts[index] != expected:
            role = MIGRATE_ACCOUNT_ROLES[index]
            return {
                "valid": False,
                "reason": f"migrate_role_{index}_{role}_relationship_mismatch",
                "role": role,
                "position": index,
                "expected": expected,
                "actual": accounts[index],
            }

    return {
        "valid": True,
        "reason": "migrate_25_roles_validated",
        "variant": "migrate",
        "roles": {
            MIGRATE_ACCOUNT_ROLES[index]: accounts[index] for index in range(25)
        },
        "mint": mint,
        "pool_address": pool,
        "creator": pool_authority,
        "user": user,
        "bonding_curve": expected_bonding_curve,
        "lp_mint": expected_lp_mint,
        "remaining_account_count": 0,
    }


def validate_migrate_v2_account_roles(
    accounts: Sequence[str],
    *,
    expected_mint: str | None = None,
) -> dict[str, Any]:
    """Validate official migrate_v2 declared roles 0..26.

    Accepted total account counts are the official 27 declared accounts or the
    already-witnessed 29-meta envelope. Indices 27 and 28, when present, are
    opaque remaining_accounts: they are not named, role-mapped, or used as
    mint/pool/quote/program evidence. Unadopted counts fail closed.

    Printer V1 keeps the adopted WSOL / Tokenkeg / PumpSwap quote venue. The
    official instruction's generic quote and token-program fields are not used
    to broaden venue, quote mint, or token-program capability.
    """
    if len(accounts) not in MIGRATE_V2_WITNESSED_ACCOUNT_COUNTS:
        return {
            "valid": False,
            "reason": "migrate_v2_account_layout_mismatch",
            "role": None,
            "position": None,
            "variant": "migrate_v2",
            "remaining_account_count": max(len(accounts) - MIGRATE_V2_DECLARED_ACCOUNT_COUNT, 0),
        }
    remaining_account_count = (
        MIGRATE_V2_REMAINING_ACCOUNT_COUNT
        if len(accounts) == 29
        else 0
    )
    declared = list(accounts[:MIGRATE_V2_DECLARED_ACCOUNT_COUNT])
    for index, role in enumerate(MIGRATE_V2_DECLARED_ACCOUNT_ROLES):
        if not isinstance(declared[index], str) or not declared[index]:
            return {
                "valid": False,
                "reason": f"migrate_v2_role_{index}_{role}_missing",
                "role": role,
                "position": index,
                "variant": "migrate_v2",
                "remaining_account_count": remaining_account_count,
            }
        if not _valid_pubkey(declared[index]):
            return {
                "valid": False,
                "reason": f"migrate_v2_role_{index}_{role}_invalid_pubkey",
                "role": role,
                "position": index,
                "variant": "migrate_v2",
                "remaining_account_count": remaining_account_count,
            }

    # Official fixed addresses plus the adopted V1 WSOL/Tokenkeg venue.
    fixed = {
        0: PUMP_GLOBAL_ID,
        1: PUMP_WITHDRAW_AUTHORITY_ID,
        3: WSOL_MINT,
        8: SYSTEM_PROGRAM_ID,
        9: PUMPSWAP_AMM_PROGRAM_ID,
        14: PUMPSWAP_GLOBAL_CONFIG_ID,
        19: TOKEN_PROGRAM_ID,
        20: TOKEN_PROGRAM_ID,
        21: TOKEN_2022_PROGRAM_ID,
        22: ASSOCIATED_TOKEN_PROGRAM_ID,
        23: PUMPSWAP_EVENT_AUTHORITY_ID,
        24: RENT_SYSVAR_ID,
        25: PUMP_EVENT_AUTHORITY_ID,
        26: PUMP_PROGRAM_ID,
    }
    for index, expected in fixed.items():
        if declared[index] != expected:
            role = MIGRATE_V2_DECLARED_ACCOUNT_ROLES[index]
            return {
                "valid": False,
                "reason": f"migrate_v2_role_{index}_{role}_mismatch",
                "role": role,
                "position": index,
                "expected": expected,
                "actual": declared[index],
                "variant": "migrate_v2",
                "remaining_account_count": remaining_account_count,
            }

    mint = declared[2]
    quote_mint = declared[3]
    user = declared[7]
    pool = declared[10]
    pool_authority = declared[11]
    if expected_mint is not None and mint != expected_mint:
        return {
            "valid": False,
            "reason": "migrate_v2_role_2_base_mint_mismatch",
            "role": "base_mint",
            "position": 2,
            "expected": expected_mint,
            "actual": mint,
            "variant": "migrate_v2",
            "remaining_account_count": remaining_account_count,
        }
    other_declared = {declared[i] for i in range(MIGRATE_V2_DECLARED_ACCOUNT_COUNT) if i != 1}
    if declared[1] in other_declared:
        return {
            "valid": False,
            "reason": "migrate_v2_role_1_withdraw_authority_relation_invalid",
            "role": "withdraw_authority",
            "position": 1,
            "variant": "migrate_v2",
            "remaining_account_count": remaining_account_count,
        }
    if user in {
        declared[0],
        declared[1],
        SYSTEM_PROGRAM_ID,
        PUMP_PROGRAM_ID,
        PUMPSWAP_AMM_PROGRAM_ID,
        mint,
        pool,
        pool_authority,
    }:
        return {
            "valid": False,
            "reason": "migrate_v2_role_7_user_invalid",
            "role": "user",
            "position": 7,
            "variant": "migrate_v2",
            "remaining_account_count": remaining_account_count,
        }

    try:
        expected_bonding_curve = derive_program_address(
            (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        expected_associated_base = _derive_ata(
            owner=expected_bonding_curve,
            token_program=TOKEN_PROGRAM_ID,
            mint=mint,
        )
        expected_associated_quote = _derive_ata(
            owner=expected_bonding_curve,
            token_program=TOKEN_PROGRAM_ID,
            mint=quote_mint,
        )
        expected_pool_authority = derive_program_address(
            (b"pool-authority", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        expected_pool, _expected_bump = derive_canonical_pumpswap_pool(
            creator=expected_pool_authority, base_mint=mint, quote_mint=quote_mint
        )
        expected_pool_authority_mint = _derive_ata(
            owner=expected_pool_authority,
            token_program=TOKEN_PROGRAM_ID,
            mint=mint,
        )
        expected_pool_authority_quote = _derive_ata(
            owner=expected_pool_authority,
            token_program=TOKEN_PROGRAM_ID,
            mint=quote_mint,
        )
        expected_lp_mint = derive_program_address(
            (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        expected_user_lp = _derive_ata(
            owner=expected_pool_authority,
            token_program=TOKEN_2022_PROGRAM_ID,
            mint=expected_lp_mint,
        )
        expected_base_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=mint
        )
        expected_quote_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=quote_mint
        )
        expected_global = derive_program_address((b"global",), PUMP_PROGRAM_ID)[0]
        expected_event_authority = derive_program_address(
            (b"__event_authority",), PUMP_PROGRAM_ID
        )[0]
        expected_amm_event_authority = derive_program_address(
            (b"__event_authority",), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        expected_amm_global_config = derive_program_address(
            (b"global_config",), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
    except (TypeError, ValueError):
        return {
            "valid": False,
            "reason": "migrate_v2_role_pda_derivation_failed",
            "role": None,
            "position": None,
            "variant": "migrate_v2",
            "remaining_account_count": remaining_account_count,
        }

    relations = {
        0: expected_global,
        4: expected_bonding_curve,
        5: expected_associated_base,
        6: expected_associated_quote,
        10: expected_pool,
        11: expected_pool_authority,
        12: expected_pool_authority_mint,
        13: expected_pool_authority_quote,
        14: expected_amm_global_config,
        15: expected_lp_mint,
        16: expected_user_lp,
        17: expected_base_vault,
        18: expected_quote_vault,
        23: expected_amm_event_authority,
        25: expected_event_authority,
    }
    for index, expected in relations.items():
        if declared[index] != expected:
            role = MIGRATE_V2_DECLARED_ACCOUNT_ROLES[index]
            return {
                "valid": False,
                "reason": f"migrate_v2_role_{index}_{role}_relationship_mismatch",
                "role": role,
                "position": index,
                "expected": expected,
                "actual": declared[index],
                "variant": "migrate_v2",
                "remaining_account_count": remaining_account_count,
            }

    return {
        "valid": True,
        "reason": "migrate_v2_27_declared_roles_validated",
        "variant": "migrate_v2",
        "roles": {
            MIGRATE_V2_DECLARED_ACCOUNT_ROLES[index]: declared[index]
            for index in range(MIGRATE_V2_DECLARED_ACCOUNT_COUNT)
        },
        "mint": mint,
        "pool_address": pool,
        "creator": pool_authority,
        "user": user,
        "bonding_curve": expected_bonding_curve,
        "lp_mint": expected_lp_mint,
        "remaining_account_count": remaining_account_count,
    }


def _migration_rejection_digest(
    *,
    reason: str,
    signature: str | None = None,
    top_level_instruction_count: int = 0,
    inner_instruction_count: int = 0,
    pump_migrate_match_count: int = 0,
    candidate_mint_identities: Sequence[str] = (),
) -> dict[str, Any]:
    """Bounded, non-raw rejection digest for offline audit (no full tx body)."""
    mints = [
        str(item)
        for item in candidate_mint_identities
        if isinstance(item, str) and item
    ]
    # Stable unique order without ranking semantics.
    unique_mints = sorted(set(mints))
    return {
        "outcome": "MIGRATION_EVIDENCE_REJECTED",
        "rejection_reason": str(reason),
        "signature": signature,
        "top_level_instruction_count": int(top_level_instruction_count),
        "inner_instruction_count": int(inner_instruction_count),
        "pump_migrate_match_count": int(pump_migrate_match_count),
        "candidate_mint_identities": unique_mints,
    }


def decode_supported_pump_migration_transaction(
    tx_result: Mapping[str, Any] | None,
    *,
    expected_signature: str | None = None,
) -> dict[str, Any]:
    """Extract the exact pinned migrate identity before Pool account verification."""
    failed: dict[str, Any] = {"supported": False, "reason": "transaction_missing"}
    if not tx_result:
        failed["migration_rejection_digest"] = _migration_rejection_digest(
            reason="transaction_missing",
            signature=expected_signature,
        )
        return failed
    if tx_result.get("version") not in (None, "legacy", 0):
        reason = "unsupported_transaction_version"
        return {
            **failed,
            "reason": reason,
            "migration_rejection_digest": _migration_rejection_digest(
                reason=reason, signature=expected_signature
            ),
        }
    meta = tx_result.get("meta")
    if not isinstance(meta, Mapping) or meta.get("err") is not None:
        reason = "transaction_failed_or_meta_missing"
        return {
            **failed,
            "reason": reason,
            "migration_rejection_digest": _migration_rejection_digest(
                reason=reason, signature=expected_signature
            ),
        }
    message = ((tx_result.get("transaction") or {}).get("message") or {})
    top_level = list(message.get("instructions") or [])
    inner_count = 0
    for group in meta.get("innerInstructions") or []:
        inner_count += len(group.get("instructions") or [])
    keys = _account_keys(tx_result)
    matches: list[tuple[str, list[str]]] = []
    for instruction in _instructions(tx_result):
        try:
            program = keys[int(instruction["programIdIndex"])]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        data = _instruction_data(instruction)
        if program != PUMP_PROGRAM_ID or data is None or len(data) < 8:
            continue
        discriminator = data[:8]
        if discriminator == PUMP_MIGRATE_DISCRIMINATOR:
            variant = "migrate"
        elif discriminator == PUMP_MIGRATE_V2_DISCRIMINATOR:
            variant = "migrate_v2"
        else:
            continue
        try:
            accounts = [keys[int(index)] for index in instruction.get("accounts") or []]
        except (KeyError, TypeError, ValueError, IndexError):
            reason = "malformed_account_index"
            return {
                **failed,
                "reason": reason,
                "variant": variant,
                "migration_rejection_digest": _migration_rejection_digest(
                    reason=reason,
                    signature=expected_signature,
                    top_level_instruction_count=len(top_level),
                    inner_instruction_count=inner_count,
                    pump_migrate_match_count=len(matches),
                ),
            }
        if variant == "migrate" and len(accounts) != 25:
            reason = "migrate_account_layout_mismatch"
            return {
                **failed,
                "reason": reason,
                "variant": variant,
                "migration_rejection_digest": _migration_rejection_digest(
                    reason=reason,
                    signature=expected_signature,
                    top_level_instruction_count=len(top_level),
                    inner_instruction_count=inner_count,
                    pump_migrate_match_count=len(matches),
                ),
            }
        if variant == "migrate_v2" and len(accounts) not in MIGRATE_V2_WITNESSED_ACCOUNT_COUNTS:
            reason = "migrate_v2_account_layout_mismatch"
            return {
                **failed,
                "reason": reason,
                "variant": variant,
                "migration_rejection_digest": _migration_rejection_digest(
                    reason=reason,
                    signature=expected_signature,
                    top_level_instruction_count=len(top_level),
                    inner_instruction_count=inner_count,
                    pump_migrate_match_count=len(matches),
                ),
            }
        matches.append((variant, accounts))
    mint_identities = [
        accounts[2]
        for _variant, accounts in matches
        if len(accounts) > 2 and isinstance(accounts[2], str)
    ]
    if len(matches) != 1:
        reason = "exactly_one_migrate_instruction_required"
        return {
            **failed,
            "reason": reason,
            "migration_rejection_digest": _migration_rejection_digest(
                reason=reason,
                signature=expected_signature,
                top_level_instruction_count=len(top_level),
                inner_instruction_count=inner_count,
                pump_migrate_match_count=len(matches),
                candidate_mint_identities=mint_identities,
            ),
        }
    variant, accounts = matches[0]
    if variant == "migrate":
        role_check = validate_migrate_account_roles(accounts, expected_mint=None)
    else:
        role_check = validate_migrate_v2_account_roles(accounts, expected_mint=None)
    if not role_check.get("valid"):
        reason = str(role_check.get("reason") or "migrate_role_validation_failed")
        return {
            **failed,
            "reason": reason,
            "variant": variant,
            "role": role_check.get("role"),
            "position": role_check.get("position"),
            "accounts": list(accounts[:MIGRATE_V2_DECLARED_ACCOUNT_COUNT] if variant == "migrate_v2" else accounts),
            "remaining_account_count": role_check.get("remaining_account_count", 0),
            "migration_rejection_digest": _migration_rejection_digest(
                reason=reason,
                signature=expected_signature,
                top_level_instruction_count=len(top_level),
                inner_instruction_count=inner_count,
                pump_migrate_match_count=1,
                candidate_mint_identities=[accounts[2]] if len(accounts) > 2 else (),
            ),
        }
    if not isinstance(tx_result.get("slot"), int) or not isinstance(tx_result.get("blockTime"), (int, float)):
        reason = "finalized_slot_or_block_time_missing"
        return {
            **failed,
            "reason": reason,
            "variant": variant,
            "migration_rejection_digest": _migration_rejection_digest(
                reason=reason,
                signature=expected_signature,
                top_level_instruction_count=len(top_level),
                inner_instruction_count=inner_count,
                pump_migrate_match_count=1,
                candidate_mint_identities=[accounts[2]] if len(accounts) > 2 else (),
            ),
        }
    declared_accounts = (
        list(accounts[:MIGRATE_V2_DECLARED_ACCOUNT_COUNT])
        if variant == "migrate_v2"
        else list(accounts)
    )
    return {
        "supported": True,
        "reason": "supported_pump_migration",
        "variant": variant,
        "mint": role_check["mint"],
        "pool_address": role_check["pool_address"],
        "creator": role_check["creator"],
        "slot": int(tx_result["slot"]),
        "block_time": int(tx_result["blockTime"]),
        "accounts": declared_accounts,
        "roles": role_check["roles"],
        "remaining_account_count": int(role_check.get("remaining_account_count") or 0),
        "bonding_curve": role_check.get("bonding_curve"),
        "lp_mint": role_check.get("lp_mint"),
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
        "account_hash": hashlib.sha256(raw).hexdigest(),
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
    migration = decode_supported_pump_migration_transaction(tx_result)
    if not migration.get("supported"):
        return {**result, "reason": str(migration["reason"])}
    if migration["mint"] != expected_mint:
        return {**result, "reason": "migrate_account_2_mismatch"}
    roles = migration.get("roles") if isinstance(migration.get("roles"), Mapping) else {}
    pool_address = str(migration["pool_address"])
    creator = str(migration["creator"])
    bonding_curve = roles.get("bonding_curve")
    lp_mint_account = roles.get("lp_mint")
    base_vault_account = roles.get("pool_base_token_account")
    quote_vault_account = roles.get("pool_quote_token_account")
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
    if bonding_curve != expected_bonding_curve or creator != expected_creator:
        return {**result, "reason": "pump_migration_pda_mismatch", "pool": decoded}
    if pool_address != expected_pool or decoded["pool_bump"] != expected_bump:
        return {**result, "reason": "canonical_pool_pda_mismatch", "pool": decoded}
    if (
        lp_mint_account != expected_lp_mint
        or decoded["lp_mint"] != expected_lp_mint
        or base_vault_account != expected_base_vault
        or decoded["pool_base_token_account"] != expected_base_vault
        or quote_vault_account != expected_quote_vault
        or decoded["pool_quote_token_account"] != expected_quote_vault
    ):
        return {**result, "reason": "canonical_pool_vault_or_lp_mismatch", "pool": decoded}
    return {
        "verified": True,
        "reason": "pinned_pump_migration_and_canonical_pool_verified",
        "variant": migration.get("variant"),
        "mint": expected_mint,
        "pool_address": pool_address,
        "creator": creator,
        "migration_slot": int(tx_result["slot"]),
        "migration_block_time": int(tx_result["blockTime"]),
        "pump_contract_hash": PUMP_IDL_SHA256,
        "pumpswap_contract_hash": PUMPSWAP_IDL_SHA256,
        "remaining_account_count": int(migration.get("remaining_account_count") or 0),
        "pool": decoded,
    }


__all__ = [
    "OFFICIAL_REPOSITORY_COMMIT", "PUMP_IDL_SHA256", "PUMPSWAP_IDL_SHA256",
    "PUMP_CREATE_DISCRIMINATOR", "PUMP_CREATE_V2_DISCRIMINATOR",
    "PUMP_MIGRATE_DISCRIMINATOR", "PUMP_MIGRATE_V2_DISCRIMINATOR",
    "PUMP_BONDING_CURVE_DISCRIMINATOR",
    "PUMPSWAP_POOL_DISCRIMINATOR", "TOKEN_PROGRAM_ID", "TOKEN_2022_PROGRAM_ID",
    "SYSTEM_PROGRAM_ID", "ASSOCIATED_TOKEN_PROGRAM_ID", "RENT_SYSVAR_ID",
    "METADATA_PROGRAM_ID", "MAYHEM_PROGRAM_ID", "WSOL_MINT", "USDC_MINT",
    "CANONICAL_POOL_INDEX", "PUMP_GLOBAL_ID", "PUMP_WITHDRAW_AUTHORITY_ID",
    "PUMP_EVENT_AUTHORITY_ID",
    "PUMPSWAP_GLOBAL_CONFIG_ID", "PUMPSWAP_EVENT_AUTHORITY_ID",
    "MIGRATE_ACCOUNT_ROLES", "MIGRATE_V2_DECLARED_ACCOUNT_ROLES",
    "MIGRATE_V2_DECLARED_ACCOUNT_COUNT", "MIGRATE_V2_WITNESSED_ACCOUNT_COUNTS",
    "derive_program_address",
    "derive_canonical_pumpswap_pool", "decode_supported_pump_creation_instruction",
    "decode_supported_pump_creation_transaction", "decode_supported_pump_migration_transaction",
    "decode_pump_bonding_curve_account", "decode_pumpswap_pool_account",
    "validate_migrate_account_roles", "validate_migrate_v2_account_roles",
    "verify_pinned_pump_migration",
]
