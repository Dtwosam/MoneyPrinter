"""Focused Slice A proofs for official Pump migrate_v2 plus legacy migrate."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from printer_v1.sources.pump_contracts import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    MIGRATE_ACCOUNT_ROLES,
    MIGRATE_V2_DECLARED_ACCOUNT_COUNT,
    MIGRATE_V2_DECLARED_ACCOUNT_ROLES,
    OFFICIAL_REPOSITORY_COMMIT,
    PUMP_EVENT_AUTHORITY_ID,
    PUMP_GLOBAL_ID,
    PUMP_WITHDRAW_AUTHORITY_ID,
    PUMP_IDL_SHA256,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMP_MIGRATE_V2_DISCRIMINATOR,
    PUMP_MIGRATION_EVENT_DISCRIMINATOR,
    PUMPSWAP_EVENT_AUTHORITY_ID,
    PUMPSWAP_GLOBAL_CONFIG_ID,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
    _b58encode,
    _derive_ata,
    decode_pumpswap_pool_account,
    decode_supported_pump_migration_transaction,
    derive_canonical_pumpswap_pool,
    derive_program_address,
    validate_migrate_account_roles,
    validate_migrate_v2_account_roles,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode
from test_v2_9_8b_candidate_acquisition_foundation import (
    _pinned_migration_fixture,
    _pool_account,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/candidate_acquisition_capacity_v1.json").read_text()
)
PINNED_COMMIT = "3c6721a67c0b206b39130b454c8ba22a83ce972e"
RECOMPUTED_IDL_DIGEST = "b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49"


def _opaque_remaining(label: bytes) -> str:
    return _b58encode(label.ljust(32, b"\x11"))


def _legacy_tx():
    return _pinned_migration_fixture()


def _v2_accounts(mint: str, user: str) -> tuple[list[str], dict, str]:
    creator = derive_program_address(
        (b"pool-authority", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    pool, account = _pool_account(creator, mint)
    decoded = decode_pumpswap_pool_account(account, pool_address=pool)
    bonding_curve = derive_program_address(
        (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    accounts = [""] * MIGRATE_V2_DECLARED_ACCOUNT_COUNT
    accounts[0] = PUMP_GLOBAL_ID
    accounts[1] = PUMP_WITHDRAW_AUTHORITY_ID
    accounts[2] = mint
    accounts[3] = WSOL_MINT
    accounts[4] = bonding_curve
    accounts[5] = _derive_ata(
        owner=bonding_curve, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    accounts[6] = _derive_ata(
        owner=bonding_curve, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
    )
    accounts[7] = user
    accounts[8] = SYSTEM_PROGRAM_ID
    accounts[9] = PUMPSWAP_AMM_PROGRAM_ID
    accounts[10] = pool
    accounts[11] = creator
    accounts[12] = _derive_ata(
        owner=creator, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    accounts[13] = _derive_ata(
        owner=creator, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
    )
    accounts[14] = PUMPSWAP_GLOBAL_CONFIG_ID
    accounts[15] = decoded["lp_mint"]
    accounts[16] = _derive_ata(
        owner=creator, token_program=TOKEN_2022_PROGRAM_ID, mint=decoded["lp_mint"]
    )
    accounts[17] = decoded["pool_base_token_account"]
    accounts[18] = decoded["pool_quote_token_account"]
    accounts[19] = TOKEN_PROGRAM_ID
    accounts[20] = TOKEN_PROGRAM_ID
    accounts[21] = TOKEN_2022_PROGRAM_ID
    accounts[22] = ASSOCIATED_TOKEN_PROGRAM_ID
    accounts[23] = PUMPSWAP_EVENT_AUTHORITY_ID
    accounts[24] = RENT_SYSVAR_ID
    accounts[25] = PUMP_EVENT_AUTHORITY_ID
    accounts[26] = PUMP_PROGRAM_ID
    return accounts, {pool: account}, pool


def _tx_from_accounts(
    accounts: list[str],
    *,
    discriminator: bytes,
    program_index: int | None = None,
    extra_keys: list[str] | None = None,
    inner: bool = False,
    loaded: dict[str, list[str]] | None = None,
    version=0,
    slot: int = 420_000_000,
    block_time: int = 1_785_326_400,
    err=None,
    account_indices: list[int] | None = None,
) -> dict:
    keys = list(accounts)
    if extra_keys:
        keys.extend(extra_keys)
    if program_index is None:
        program_index = keys.index(PUMP_PROGRAM_ID) if PUMP_PROGRAM_ID in keys else 0
    instruction = {
        "programIdIndex": program_index,
        "accounts": account_indices if account_indices is not None else list(range(len(accounts))),
        "data": _b58encode(discriminator),
    }
    message_instructions = [] if inner else [instruction]
    inner_groups = [{"index": 0, "instructions": [instruction]}] if inner else []
    return {
        "version": version,
        "slot": slot,
        "blockTime": block_time,
        "transaction": {
            "message": {
                "accountKeys": keys if loaded is None else keys,
                "instructions": message_instructions,
            }
        },
        "meta": {
            "err": err,
            "innerInstructions": inner_groups,
            "loadedAddresses": loaded or {"writable": [], "readonly": []},
        },
    }


def test_official_pin_and_role_tuples_stay_separate() -> None:
    assert OFFICIAL_REPOSITORY_COMMIT == PINNED_COMMIT
    assert PUMP_IDL_SHA256 == RECOMPUTED_IDL_DIGEST
    assert PUMP_MIGRATE_V2_DISCRIMINATOR == bytes.fromhex("bbcb121fceedfe29")
    assert PUMP_MIGRATE_DISCRIMINATOR == bytes.fromhex("9beae792ec9ea21e")
    assert len(MIGRATE_ACCOUNT_ROLES) == 25
    assert len(MIGRATE_V2_DECLARED_ACCOUNT_ROLES) == 27
    assert MIGRATE_V2_DECLARED_ACCOUNT_ROLES[2] == "base_mint"
    assert MIGRATE_V2_DECLARED_ACCOUNT_ROLES[10] == "pool"
    assert "remaining" not in " ".join(MIGRATE_V2_DECLARED_ACCOUNT_ROLES)


def test_well_formed_legacy_25_account_migrate_remains_pass() -> None:
    tx, infos, mint, pool = _legacy_tx()
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    assert decoded["variant"] == "migrate"
    assert decoded["mint"] == mint
    assert decoded["pool_address"] == pool
    assert decoded["remaining_account_count"] == 0
    assert validate_migrate_account_roles(
        tx["transaction"]["message"]["accountKeys"]
    )["valid"] is True
    verified = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert verified["verified"] is True
    assert verified["variant"] == "migrate"


def test_official_27_declared_migrate_v2_pass() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    assert len(accounts) == 27
    roles = validate_migrate_v2_account_roles(accounts)
    assert roles["valid"] is True
    assert roles["mint"] == mint
    assert roles["pool_address"] == pool
    assert roles["remaining_account_count"] == 0
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    assert decoded["variant"] == "migrate_v2"
    assert decoded["mint"] == mint
    assert decoded["pool_address"] == pool
    assert decoded["remaining_account_count"] == 0
    assert len(decoded["accounts"]) == 27
    verified = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert verified["verified"] is True
    assert verified["pool_address"] == pool


def test_witnessed_29_meta_envelope_pass_and_remaining_cannot_alter_identities() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    declared, infos, pool = _v2_accounts(mint, user)
    decoy_mint = FIXTURE["candidates"][4][0]
    decoy_pool = FIXTURE["candidates"][4][1]
    remaining = [decoy_mint, decoy_pool]
    accounts = declared + remaining
    roles = validate_migrate_v2_account_roles(accounts)
    assert roles["valid"] is True
    assert roles["remaining_account_count"] == 2
    assert roles["mint"] == mint
    assert roles["pool_address"] == pool
    assert "remaining" not in roles["roles"]
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    assert decoded["remaining_account_count"] == 2
    assert decoded["mint"] == mint
    assert decoded["pool_address"] == pool
    assert decoy_mint not in {decoded["mint"], decoded["pool_address"]}
    assert decoy_pool not in {decoded["mint"], decoded["pool_address"]}
    assert len(decoded["accounts"]) == 27
    verified = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert verified["verified"] is True
    assert verified["remaining_account_count"] == 2


def test_unadopted_28_and_30_account_v2_fail_closed() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    declared, _infos, _pool = _v2_accounts(mint, user)
    extra = _opaque_remaining(b"remain-a")
    for count, payload in (
        (28, declared + [extra]),
        (30, declared + [extra, extra, extra]),
    ):
        assert len(payload) == count
        result = validate_migrate_v2_account_roles(payload)
        assert result["valid"] is False
        assert result["reason"] == "migrate_v2_account_layout_mismatch"
        tx = _tx_from_accounts(payload, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
        decoded = decode_supported_pump_migration_transaction(tx)
        assert decoded["supported"] is False
        assert decoded["reason"] == "migrate_v2_account_layout_mismatch"


def test_legacy_discriminator_with_v2_layout_fails() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, _infos, _pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_DISCRIMINATOR)
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "migrate_account_layout_mismatch"


def test_v2_discriminator_with_legacy_layout_fails() -> None:
    tx, _infos, _mint, _pool = _legacy_tx()
    instruction = tx["transaction"]["message"]["instructions"][0]
    instruction["data"] = _b58encode(PUMP_MIGRATE_V2_DISCRIMINATOR)
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "migrate_v2_account_layout_mismatch"


def test_wrong_pump_program_fails() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, _infos, _pool = _v2_accounts(mint, user)
    accounts[26] = FIXTURE["candidates"][5][0]
    tx = _tx_from_accounts(
        accounts,
        discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR,
        program_index=26,
    )
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "exactly_one_migrate_instruction_required"


def test_wrong_expected_mint_fails_confirmation() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, _pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    other = FIXTURE["candidates"][6][0]
    assert other != mint
    roles = validate_migrate_v2_account_roles(accounts, expected_mint=other)
    assert roles["valid"] is False
    assert roles["reason"] == "migrate_v2_role_2_base_mint_mismatch"
    verified = verify_pinned_pump_migration(
        tx, infos, expected_mint=other, finalized=True
    )
    assert verified["verified"] is False
    assert verified["reason"] == "migrate_account_2_mismatch"


def test_malformed_account_index_fails() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, _infos, _pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(
        accounts,
        discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR,
        account_indices=list(range(26)) + [999],
    )
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "malformed_account_index"


def test_duplicate_supported_migration_instructions_fail() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, _infos, _pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    tx["transaction"]["message"]["instructions"].append(
        deepcopy(tx["transaction"]["message"]["instructions"][0])
    )
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "exactly_one_migrate_instruction_required"
    assert decoded["migration_rejection_digest"]["pump_migrate_match_count"] == 2


def test_inner_instruction_migrate_v2_is_accepted() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(
        accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR, inner=True
    )
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    assert decoded["pool_address"] == pool
    assert verify_pinned_pump_migration(
        tx, infos, expected_mint=mint, finalized=True
    )["verified"] is True


def test_v0_loaded_address_resolution_remains_correct() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    static = accounts[:24]
    loaded_readonly = accounts[24:]
    assert loaded_readonly == [RENT_SYSVAR_ID, PUMP_EVENT_AUTHORITY_ID, PUMP_PROGRAM_ID]
    instruction_accounts = list(range(24)) + [24, 25, 26]
    tx = {
        "version": 0,
        "slot": 420_000_111,
        "blockTime": 1_785_326_411,
        "transaction": {
            "message": {
                "accountKeys": static,
                "instructions": [{
                    "programIdIndex": 26,
                    "accounts": instruction_accounts,
                    "data": _b58encode(PUMP_MIGRATE_V2_DISCRIMINATOR),
                }],
            }
        },
        "meta": {
            "err": None,
            "innerInstructions": [],
            "loadedAddresses": {"writable": [], "readonly": loaded_readonly},
        },
    }
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    assert decoded["mint"] == mint
    assert decoded["pool_address"] == pool
    assert verify_pinned_pump_migration(
        tx, infos, expected_mint=mint, finalized=True
    )["verified"] is True


def test_migration_event_without_supported_instruction_cannot_promote() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATION_EVENT_DISCRIMINATOR)
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is False
    assert decoded["reason"] == "exactly_one_migrate_instruction_required"
    verified = verify_pinned_pump_migration(tx, infos, expected_mint=mint, finalized=True)
    assert verified["verified"] is False
    assert verified["reason"] == "exactly_one_migrate_instruction_required"
    assert pool not in {decoded.get("pool_address"), verified.get("pool_address")}


def test_pumpswap_confirmation_requirement_is_unchanged() -> None:
    mint = FIXTURE["candidates"][0][0]
    user = FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    missing = verify_pinned_pump_migration(tx, {}, expected_mint=mint, finalized=True)
    assert missing["verified"] is False
    assert missing["reason"] == "pool_account_missing"
    confirmed = verify_pinned_pump_migration(
        tx, infos, expected_mint=mint, finalized=True
    )
    assert confirmed["verified"] is True
    assert confirmed["pool_address"] == pool
    assert confirmed["pool"]["quote_mint"] == WSOL_MINT
    legacy_tx, legacy_infos, legacy_mint, _legacy_pool = _legacy_tx()
    legacy_missing = verify_pinned_pump_migration(
        legacy_tx, {}, expected_mint=legacy_mint, finalized=True
    )
    assert legacy_missing["verified"] is False
    assert legacy_missing["reason"] == "pool_account_missing"
    assert verify_pinned_pump_migration(
        legacy_tx, legacy_infos, expected_mint=legacy_mint, finalized=True
    )["verified"] is True
