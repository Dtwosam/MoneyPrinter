"""V2-9.7E.6 Phase 2 — independent Pump create outcome classification.

Replaces the ambiguous combined ``UNSUPPORTED_VERSION`` code, which conflated a
rejected Solana transaction envelope with a Pump instruction-layout problem and
made the V2-9.7E.5A live evidence undecidable.

Envelope validation is proven to be strictly prior to, and independent of, Pump
discriminator classification.
"""

from __future__ import annotations

import unittest

from printer_v1.sources.pumpfun_direct import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    CREATE_DISCRIMINATOR,
    CREATE_LAYOUT_LEGACY,
    CREATE_LAYOUT_V2,
    CREATE_V2_ACCOUNT_COUNT,
    CREATE_V2_DISCRIMINATOR,
    EVENT_AUTHORITY_ID,
    GLOBAL_ID,
    MAYHEM_PROGRAM_ID,
    MINT_AUTHORITY_ID,
    PUMP_PROGRAM_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    PumpContractError,
    SignatureReference,
    decode_finalized_create,
    derive_program_address,
)
from tests.test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    b58decode,
    b58encode,
    borsh_string,
    create_transaction,
    pubkey,
)
import hashlib


def create_v2_transaction(
    signature: str,
    slot: int = SLOT if False else 5000,
    block_time: int = 1_700_200_000,
    *,
    mint_label: str | None = None,
    is_mayhem_mode: bool = False,
    is_cashback_enabled: bool = False,
    token_program: str = TOKEN_2022_PROGRAM_ID,
) -> tuple[dict, str]:
    """Build one supported finalized Pump `create_v2` transaction (pinned layout).

    16 accounts, Token-2022, mayhem PDAs, no metadata/rent account.
    """
    label = mint_label or f"mint-v2-{signature}"
    mint, mint_raw = pubkey(label)
    creator_raw = hashlib.sha256(f"creator-{signature}".encode("ascii")).digest()
    user, _ = pubkey(f"user-{signature}")
    vault, _ = pubkey(f"mayhem-vault-{signature}")
    curve = derive_program_address((b"bonding-curve", mint_raw), PUMP_PROGRAM_ID)
    associated_curve = derive_program_address(
        (b58decode(curve), b58decode(token_program), mint_raw),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    global_params = derive_program_address((b"global-params",), MAYHEM_PROGRAM_ID)
    sol_vault = derive_program_address((b"sol-vault",), MAYHEM_PROGRAM_ID)
    mayhem_state = derive_program_address((b"mayhem-state", mint_raw), MAYHEM_PROGRAM_ID)
    data = (
        CREATE_V2_DISCRIMINATOR
        + borsh_string("Fixture Coin V2")
        + borsh_string("FIXV2")
        + borsh_string("https://example.invalid/v2.json")
        + creator_raw
        + bytes((1 if is_mayhem_mode else 0,))
        + bytes((1 if is_cashback_enabled else 0,))
    )
    keys = [
        mint,
        MINT_AUTHORITY_ID,
        curve,
        associated_curve,
        GLOBAL_ID,
        user,
        SYSTEM_PROGRAM_ID,
        token_program,
        ASSOCIATED_TOKEN_PROGRAM_ID,
        MAYHEM_PROGRAM_ID,
        global_params,
        sol_vault,
        mayhem_state,
        vault,
        EVENT_AUTHORITY_ID,
        PUMP_PROGRAM_ID,
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
                "accountKeys": keys,
                "instructions": [
                    {
                        "programIdIndex": 15,
                        "accounts": list(range(CREATE_V2_ACCOUNT_COUNT)),
                        "data": b58encode(data),
                    }
                ],
            },
        },
    }
    return transaction, mint

SLOT = 5000
BLOCK_TIME = 1_700_200_000


def reference(signature: str = "sigC", slot: int = SLOT) -> SignatureReference:
    return SignatureReference(signature, slot, "finalized", None)


def envelope(
    instructions: list[dict],
    keys: list[str],
    *,
    signature: str = "sigC",
    slot: int = SLOT,
    version: object = 0,
) -> dict:
    return {
        "version": version,
        "slot": slot,
        "blockTime": BLOCK_TIME,
        "meta": {
            "err": None,
            "loadedAddresses": {"writable": [], "readonly": []},
            "innerInstructions": [],
        },
        "transaction": {
            "signatures": [signature],
            "message": {"accountKeys": keys, "instructions": instructions},
        },
    }


def pump_instruction(data: bytes, account_indices: list[int], program_index: int) -> dict:
    return {
        "programIdIndex": program_index,
        "accounts": account_indices,
        "data": b58encode(data),
    }


class ClassificationSeparationTests(unittest.TestCase):
    """Each unsupported outcome must be independently identifiable."""

    def test_unsupported_transaction_version_fires_on_envelope_alone(self) -> None:
        # A create_v2 payload is present, but the envelope is rejected first.
        other, _ = pubkey("acct")
        keys = [other, MINT_AUTHORITY_ID, PUMP_PROGRAM_ID]
        transaction = envelope(
            [pump_instruction(CREATE_V2_DISCRIMINATOR + b"\x00", [0, 1], 2)],
            keys,
            version=1,
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(transaction, reference=reference(), cutoff_slot=SLOT)
        # Envelope wins: the Pump layout is never classified.
        self.assertEqual(caught.exception.code, "UNSUPPORTED_TRANSACTION_VERSION")

    def test_unsupported_transaction_version_on_missing_version_field(self) -> None:
        other, _ = pubkey("acct")
        transaction = envelope([], [other], version=None)
        del transaction["version"]
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(transaction, reference=reference(), cutoff_slot=SLOT)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_TRANSACTION_VERSION")

    def test_legacy_and_v0_envelopes_are_accepted(self) -> None:
        # Envelope acceptance must not depend on Pump content.
        for version in ("legacy", 0):
            transaction, _ = create_transaction("sigOK", SLOT, BLOCK_TIME)
            transaction["version"] = version
            observation = decode_finalized_create(
                transaction, reference=reference("sigOK"), cutoff_slot=SLOT
            )
            self.assertEqual(observation.program_id, PUMP_PROGRAM_ID)

    def test_legacy_shaped_create_v2_is_fail_closed_malformed(self) -> None:
        # A create_v2 discriminator on a legacy 14-account/SPL-Token body is not
        # a valid create_v2. It must be rejected, never coerced.
        transaction, _ = create_transaction(
            "sigV2bad", SLOT, BLOCK_TIME, discriminator=CREATE_V2_DISCRIMINATOR
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigV2bad"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "MALFORMED_TRANSACTION")

    def test_unsupported_pump_create_layout_for_unknown_create_family(self) -> None:
        # Unknown Pump discriminator that still touches the create-exclusive
        # mint authority: an unrecognised create layout, not ordinary traffic.
        other, _ = pubkey("acct")
        keys = [other, MINT_AUTHORITY_ID, PUMP_PROGRAM_ID]
        unknown = bytes((9, 9, 9, 9, 9, 9, 9, 9))
        transaction = envelope(
            [pump_instruction(unknown, [0, 1], 2)], keys
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(transaction, reference=reference(), cutoff_slot=SLOT)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PUMP_CREATE_LAYOUT")

    def test_not_supported_create_for_ordinary_pump_traffic(self) -> None:
        # Buy/sell shape: Pump program, no mint authority, unknown discriminator.
        other, _ = pubkey("acct")
        keys = [other, PUMP_PROGRAM_ID]
        transaction = envelope(
            [pump_instruction(bytes((1, 2, 3, 4, 5, 6, 7, 8)), [0], 1)], keys
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(transaction, reference=reference(), cutoff_slot=SLOT)
        self.assertEqual(caught.exception.code, "NOT_SUPPORTED_CREATE")

    def test_all_four_outcomes_are_distinct(self) -> None:
        codes = {
            "UNSUPPORTED_TRANSACTION_VERSION",
            "UNSUPPORTED_PUMP_CREATE_V2",
            "UNSUPPORTED_PUMP_CREATE_LAYOUT",
            "NOT_SUPPORTED_CREATE",
        }
        self.assertEqual(len(codes), 4)
        # The retired conflated code must no longer be raised anywhere.
        source = __import__(
            "printer_v1.sources.pumpfun_direct", fromlist=["decode_finalized_create"]
        )
        import inspect

        self.assertNotIn(
            'PumpContractError("UNSUPPORTED_VERSION")',
            inspect.getsource(source.decode_finalized_create),
        )

    def test_legacy_create_still_decodes_unchanged(self) -> None:
        transaction, mint = create_transaction("sigLegacy", SLOT, BLOCK_TIME)
        observation = decode_finalized_create(
            transaction, reference=reference("sigLegacy"), cutoff_slot=SLOT
        )
        self.assertEqual(observation.mint, mint)
        self.assertEqual(observation.slot, SLOT)
        self.assertEqual(observation.block_time, BLOCK_TIME)


class AdoptedCreateV2LayoutTests(unittest.TestCase):
    """Phase 4/5 proofs for the pinned `create_v2` contract adoption."""

    def test_create_v2_decodes_and_is_labelled(self) -> None:
        transaction, mint = create_v2_transaction("sigV2ok")
        observation = decode_finalized_create(
            transaction, reference=reference("sigV2ok"), cutoff_slot=SLOT
        )
        self.assertEqual(observation.mint, mint)
        self.assertEqual(observation.create_layout, CREATE_LAYOUT_V2)
        self.assertEqual(observation.program_id, PUMP_PROGRAM_ID)

    def test_legacy_create_keeps_its_own_label(self) -> None:
        transaction, mint = create_transaction("sigLegacy2", SLOT, BLOCK_TIME)
        observation = decode_finalized_create(
            transaction, reference=reference("sigLegacy2"), cutoff_slot=SLOT
        )
        self.assertEqual(observation.mint, mint)
        self.assertEqual(observation.create_layout, CREATE_LAYOUT_LEGACY)

    def test_both_layouts_are_distinguishable(self) -> None:
        legacy, _ = create_transaction("sigL", SLOT, BLOCK_TIME)
        v2, _ = create_v2_transaction("sigV")
        a = decode_finalized_create(legacy, reference=reference("sigL"), cutoff_slot=SLOT)
        b = decode_finalized_create(v2, reference=reference("sigV"), cutoff_slot=SLOT)
        self.assertNotEqual(a.create_layout, b.create_layout)
        self.assertNotEqual(a.mint, b.mint)

    def test_spl_token_program_rejected_for_create_v2(self) -> None:
        # Token-2022 is mandatory in the pinned create_v2 layout.
        from printer_v1.sources.pumpfun_direct import TOKEN_PROGRAM_ID

        transaction, _ = create_v2_transaction("sigTok", token_program=TOKEN_PROGRAM_ID)
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigTok"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "MALFORMED_TRANSACTION")

    def test_mayhem_flags_round_trip(self) -> None:
        for mayhem, cashback in ((False, False), (True, False), (False, True), (True, True)):
            transaction, mint = create_v2_transaction(
                f"sigF{int(mayhem)}{int(cashback)}",
                is_mayhem_mode=mayhem,
                is_cashback_enabled=cashback,
            )
            observation = decode_finalized_create(
                transaction,
                reference=reference(f"sigF{int(mayhem)}{int(cashback)}"),
                cutoff_slot=SLOT,
            )
            self.assertEqual(observation.mint, mint)

    def test_wrong_fixed_identity_rejected(self) -> None:
        for index in (1, 4, 6, 7, 8, 9, 14, 15):
            transaction, _ = create_v2_transaction("sigId")
            other, _ = pubkey(f"wrong-{index}")
            transaction["transaction"]["message"]["accountKeys"][index] = other
            with self.assertRaises(PumpContractError, msg=f"index {index}"):
                decode_finalized_create(
                    transaction, reference=reference("sigId"), cutoff_slot=SLOT
                )

    def test_wrong_pda_rejected(self) -> None:
        # bonding_curve, ATA, global_params, sol_vault, mayhem_state
        for index in (2, 3, 10, 11, 12):
            transaction, _ = create_v2_transaction("sigPda")
            other, _ = pubkey(f"badpda-{index}")
            transaction["transaction"]["message"]["accountKeys"][index] = other
            with self.assertRaises(PumpContractError, msg=f"index {index}"):
                decode_finalized_create(
                    transaction, reference=reference("sigPda"), cutoff_slot=SLOT
                )

    def test_wrong_account_count_rejected(self) -> None:
        transaction, _ = create_v2_transaction("sigCount")
        transaction["transaction"]["message"]["instructions"][0]["accounts"] = list(
            range(14)
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigCount"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "MALFORMED_TRANSACTION")

    def test_trailing_argument_bytes_rejected(self) -> None:
        transaction, _ = create_v2_transaction("sigTrail")
        data = b58decode(
            transaction["transaction"]["message"]["instructions"][0]["data"]
        )
        transaction["transaction"]["message"]["instructions"][0]["data"] = b58encode(
            data + b"\x00"
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigTrail"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "MALFORMED_TRANSACTION")

    def test_create_v2_on_wrong_program_is_wrong_program(self) -> None:
        transaction, _ = create_v2_transaction("sigWrongProg")
        other, _ = pubkey("not-pump")
        # Point the instruction at a non-Pump program id.
        transaction["transaction"]["message"]["accountKeys"].append(other)
        transaction["transaction"]["message"]["instructions"][0]["programIdIndex"] = 16
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigWrongProg"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "WRONG_PROGRAM")

    def test_both_layouts_in_one_transaction_is_ambiguous(self) -> None:
        transaction, _ = create_v2_transaction("sigAmb")
        legacy, _ = create_transaction("sigAmbL", SLOT, BLOCK_TIME)
        legacy_instruction = legacy["transaction"]["message"]["instructions"][0]
        base = len(transaction["transaction"]["message"]["accountKeys"])
        transaction["transaction"]["message"]["accountKeys"].extend(
            legacy["transaction"]["message"]["accountKeys"]
        )
        transaction["transaction"]["message"]["instructions"].append(
            {
                "programIdIndex": base + 13,
                "accounts": [base + i for i in range(14)],
                "data": legacy_instruction["data"],
            }
        )
        with self.assertRaises(PumpContractError) as caught:
            decode_finalized_create(
                transaction, reference=reference("sigAmb"), cutoff_slot=SLOT
            )
        self.assertEqual(caught.exception.code, "AMBIGUOUS_CREATE")


class RegistryLayoutProvenanceTests(unittest.TestCase):
    """Durable registry must record which adopted layout established an origin."""

    def setUp(self) -> None:
        import sqlite3
        import tempfile
        from pathlib import Path

        from printer_v1.db.migrate import apply_migrations

        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.db_path = Path(self._dir.name) / "layout.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.addCleanup(self.connection.close)

    def _decode(self, transaction: dict, signature: str):
        return decode_finalized_create(
            transaction, reference=reference(signature), cutoff_slot=SLOT
        )

    def test_both_layouts_persist_with_distinct_provenance(self) -> None:
        from printer_v1.sources.pumpfun_direct import TOKEN_PROGRAM_ID
        from printer_v1.sources.pumpfun_origin import (
            lookup_confirmed_origin,
            record_confirmed_origin,
        )

        legacy_tx, legacy_mint = create_transaction("sigRegL", SLOT, BLOCK_TIME)
        v2_tx, v2_mint = create_v2_transaction("sigRegV")
        for transaction, signature in ((legacy_tx, "sigRegL"), (v2_tx, "sigRegV")):
            record_confirmed_origin(
                self.connection,
                self._decode(transaction, signature),
                now="2026-07-21T00:00:00Z",
            )
        self.connection.commit()

        legacy = lookup_confirmed_origin(self.connection, legacy_mint)
        v2 = lookup_confirmed_origin(self.connection, v2_mint)
        self.assertEqual(legacy["create_layout"], CREATE_LAYOUT_LEGACY)
        self.assertEqual(legacy["token_program"], TOKEN_PROGRAM_ID)
        self.assertEqual(legacy["create_discriminator_hex"], CREATE_DISCRIMINATOR.hex())
        self.assertEqual(v2["create_layout"], CREATE_LAYOUT_V2)
        self.assertEqual(v2["token_program"], TOKEN_2022_PROGRAM_ID)
        self.assertEqual(v2["create_discriminator_hex"], CREATE_V2_DISCRIMINATOR.hex())

    def test_registry_rejects_unknown_layout(self) -> None:
        import sqlite3

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO printer_pumpfun_finalized_origin_registry(
                    mint_identity, transaction_signature, slot, block_time,
                    program_id, bonding_curve, associated_bonding_curve,
                    creator_address, creator_evidence_scope, origin_state,
                    acquisition_mode, create_layout, create_discriminator_hex,
                    token_program, index_address, contract_version, idl_sha256,
                    evidence_hash, first_confirmed_at
                ) VALUES ('m','s',1,1,?,'c','a','cr','OBSERVED_EVIDENCE_ONLY',
                    'PUMPFUN_ORIGIN_CONFIRMED','SIGNATURE_ANCHORED_PROSPECTIVE',
                    'PUMP_CREATE_V9','0000000000000000','t','i','v','h',?,'n')
                """,
                (PUMP_PROGRAM_ID, "0" * 64),
            )


if __name__ == "__main__":
    unittest.main()
