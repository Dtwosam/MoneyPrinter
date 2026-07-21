"""Focused synthetic proof for V2-9.7D.7B.4A."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    BACKFILL_REQUEST,
    CREATE_DISCRIMINATOR,
    CREATE_EVENT_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    ContinuityState,
    CursorBoundary,
    EVENT_AUTHORITY_ID,
    EVENT_CPI_WRAPPER,
    FinalizedCursor,
    FixtureOperation,
    FixtureOperationPort,
    GLOBAL_ID,
    MINT_AUTHORITY_ID,
    PUMP_IDL_SHA256,
    PUMP_PROGRAM_ID,
    PUMP_REPOSITORY_COMMIT,
    PumpContractError,
    RENT_SYSVAR_ID,
    SCHEDULER_JOB_KIND,
    SCHEDULER_WORK_TYPE,
    SESSION_REQUEST,
    SignatureReference,
    SYSTEM_PROGRAM_ID,
    TOKEN_METADATA_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    TRANSACTION_REQUEST,
    decode_finalized_create,
    derive_program_address,
    enforce_underlying_operation_ceiling,
    run_fixture_cycle,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "pumpfun_direct_adapter_continuity.json"
)
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(value: bytes) -> str:
    number = int.from_bytes(value, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = ALPHABET[remainder] + encoded
    return "1" * (len(value) - len(value.lstrip(bytes(1)))) + (encoded or "")


def b58decode(value: str) -> bytes:
    number = 0
    for character in value:
        number = number * 58 + ALPHABET.index(character)
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return bytes(len(value) - len(value.lstrip("1"))) + raw


def pubkey(label: str) -> tuple[str, bytes]:
    raw = hashlib.sha256(label.encode("ascii")).digest()
    return b58encode(raw), raw


def borsh_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def operation(
    request_id: str,
    request_kind: str,
    rpc_operation: str,
    response: object,
    **overrides: object,
) -> FixtureOperation:
    values = {
        "request_id": request_id,
        "request_kind": request_kind,
        "rpc_operation": rpc_operation,
        "response": response,
    }
    values.update(overrides)
    return FixtureOperation(**values)


def signature_row(signature: str, slot: int, *, status: str = "finalized", err=None):
    return {
        "signature": signature,
        "slot": slot,
        "confirmationStatus": status,
        "err": err,
    }


def valid_transaction(
    signature: str,
    slot: int,
    block_time: int,
    *,
    with_event: bool = False,
) -> tuple[dict, dict]:
    mint, mint_raw = pubkey(f"mint-{signature}")
    creator, creator_raw = pubkey(f"creator-{signature}")
    user, user_raw = pubkey(f"user-{signature}")
    quote_mint, quote_raw = pubkey("quote-mint")
    curve = derive_program_address((b"bonding-curve", mint_raw), PUMP_PROGRAM_ID)
    associated_curve = derive_program_address(
        (b58decode(curve), b58decode(TOKEN_PROGRAM_ID), mint_raw),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )
    metadata = derive_program_address(
        (b"metadata", b58decode(TOKEN_METADATA_PROGRAM_ID), mint_raw),
        TOKEN_METADATA_PROGRAM_ID,
    )
    name, symbol, uri = "Fixture Coin", "FIX", "https://example.invalid/meta.json"
    create_data = (
        CREATE_DISCRIMINATOR
        + borsh_string(name)
        + borsh_string(symbol)
        + borsh_string(uri)
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
    instructions = [
        {
            "programIdIndex": 13,
            "accounts": list(range(14)),
            "data": b58encode(create_data),
        }
    ]
    inner = []
    if with_event:
        event_data = (
            EVENT_CPI_WRAPPER
            + CREATE_EVENT_DISCRIMINATOR
            + borsh_string(name)
            + borsh_string(symbol)
            + borsh_string(uri)
            + mint_raw
            + b58decode(curve)
            + user_raw
            + creator_raw
            + struct.pack("<qQQQQ", block_time, 1000, 2000, 3000, 4000)
            + b58decode(TOKEN_PROGRAM_ID)
            + bytes((0, 1))
            + quote_raw
            + struct.pack("<Q", 5000)
        )
        inner = [
            {
                "index": 0,
                "instructions": [
                    {
                        "programIdIndex": 13,
                        "accounts": [],
                        "data": b58encode(event_data),
                    }
                ],
            }
        ]
    transaction = {
        "version": 0,
        "slot": slot,
        "blockTime": block_time,
        "meta": {
            "err": None,
            "loadedAddresses": {"writable": [], "readonly": []},
            "innerInstructions": inner,
        },
        "transaction": {
            "signatures": [signature],
            "message": {"accountKeys": keys, "instructions": instructions},
        },
    }
    expected = {
        "mint": mint,
        "bonding_curve": curve,
        "associated_bonding_curve": associated_curve,
        "creator_address": creator,
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
    }
    return transaction, expected


def reference(signature: str, slot: int, *, status: str = "finalized", err=None):
    return SignatureReference(signature, slot, status, err)


def cycle_operations(
    signature: str,
    slot: int,
    block_time: int,
    *,
    cutoff: int,
    disconnected: bool = False,
    duplicate_live: bool = True,
) -> tuple[FixtureOperation, ...]:
    transaction, _ = valid_transaction(signature, slot, block_time)
    row = signature_row(signature, slot)
    notifications = [row] if duplicate_live else []
    return (
        operation("session", SESSION_REQUEST, "getSlot", cutoff),
        operation(
            "session",
            SESSION_REQUEST,
            "logsSubscribe",
            {"notifications": notifications, "disconnected": disconnected},
        ),
        operation("session", SESSION_REQUEST, "logsUnsubscribe", True),
        operation(
            "page-1",
            BACKFILL_REQUEST,
            "getSignaturesForAddress",
            {"rows": [row], "complete_to_prior_cursor": True},
        ),
        operation(f"tx-{signature}", TRANSACTION_REQUEST, "getTransaction", transaction),
    )


class DirectPumpDecoderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.signature = self.fixture["cycles"]["first"]["signature"]
        self.slot = self.fixture["cycles"]["first"]["cutoff_slot"]
        self.block_time = self.fixture["cycles"]["first"]["block_time"]
        self.transaction, self.expected = valid_transaction(
            self.signature, self.slot, self.block_time, with_event=True
        )
        self.reference = reference(self.signature, self.slot)

    def assert_code(self, code: str, callback) -> None:
        with self.assertRaises(PumpContractError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def decode(self, transaction=None, ref=None, **kwargs):
        return decode_finalized_create(
            transaction or self.transaction,
            reference=ref or self.reference,
            cutoff_slot=kwargs.pop("cutoff_slot", self.slot),
            **kwargs,
        )

    def test_contract_identity_pdas_and_valid_finalized_create(self) -> None:
        self.assertEqual(self.fixture["program_id"], PUMP_PROGRAM_ID)
        self.assertEqual(self.fixture["official_repository_commit"], PUMP_REPOSITORY_COMMIT)
        self.assertEqual(self.fixture["official_idl_sha256"], PUMP_IDL_SHA256)
        self.assertEqual(self.fixture["create_discriminator_hex"], CREATE_DISCRIMINATOR.hex())
        self.assertEqual(
            derive_program_address((b"global",), PUMP_PROGRAM_ID), GLOBAL_ID
        )
        self.assertEqual(
            derive_program_address((b"mint-authority",), PUMP_PROGRAM_ID),
            MINT_AUTHORITY_ID,
        )
        self.assertEqual(
            derive_program_address((b"__event_authority",), PUMP_PROGRAM_ID),
            EVENT_AUTHORITY_ID,
        )
        observed = self.decode()
        for field, value in self.expected.items():
            self.assertEqual(getattr(observed, field), value)
        self.assertEqual(observed.creator_evidence_scope, "OBSERVED_EVIDENCE_ONLY")

        legacy = deepcopy(self.transaction)
        legacy["version"] = "legacy"
        self.assertEqual(self.decode(legacy), observed)

        loaded_address = deepcopy(self.transaction)
        pump_key = loaded_address["transaction"]["message"]["accountKeys"].pop()
        loaded_address["meta"]["loadedAddresses"]["readonly"].append(pump_key)
        self.assertEqual(self.decode(loaded_address), observed)

    def test_failed_wrong_program_and_malformed_accounts_fail_closed(self) -> None:
        failed = deepcopy(self.transaction)
        failed["meta"]["err"] = {"InstructionError": [0, "Custom"]}
        self.assert_code("FAILED_TRANSACTION", lambda: self.decode(failed))

        wrong = deepcopy(self.transaction)
        wrong["transaction"]["message"]["accountKeys"][13] = SYSTEM_PROGRAM_ID
        self.assert_code("WRONG_PROGRAM", lambda: self.decode(wrong))

        malformed = deepcopy(self.transaction)
        malformed["transaction"]["message"]["instructions"][0]["accounts"].pop()
        self.assert_code("MALFORMED_TRANSACTION", lambda: self.decode(malformed))

    def test_unsupported_version_create_v2_ambiguity_and_mint_mismatch(self) -> None:
        unsupported = deepcopy(self.transaction)
        unsupported["version"] = 1
        self.assert_code("UNSUPPORTED_TRANSACTION_VERSION", lambda: self.decode(unsupported))

        create_v2 = deepcopy(self.transaction)
        create_v2["transaction"]["message"]["instructions"][0]["data"] = b58encode(
            CREATE_V2_DISCRIMINATOR
        )
        # V2-9.7E.6: create_v2 is now adopted. This fixture is a legacy-shaped
        # body carrying the create_v2 discriminator, which is fail-closed as
        # MALFORMED_TRANSACTION. Genuine create_v2 support is proven in
        # tests/test_v2_9_7e_6_pump_create_classification.py.
        self.assert_code("MALFORMED_TRANSACTION", lambda: self.decode(create_v2))

        ambiguous = deepcopy(self.transaction)
        instruction = deepcopy(ambiguous["transaction"]["message"]["instructions"][0])
        ambiguous["transaction"]["message"]["instructions"].append(instruction)
        self.assert_code("AMBIGUOUS_CREATE", lambda: self.decode(ambiguous))

        other_mint, _ = pubkey("other-mint")
        self.assert_code(
            "MINT_MISMATCH",
            lambda: self.decode(expected_mint=other_mint),
        )

    def test_missing_finality_post_cutoff_and_event_mismatch_fail_closed(self) -> None:
        self.assert_code(
            "MISSING_FINALITY",
            lambda: self.decode(ref=reference(self.signature, self.slot, status="confirmed")),
        )
        self.assert_code(
            "POST_CUTOFF",
            lambda: self.decode(cutoff_slot=self.slot - 1),
        )
        mismatched_event = deepcopy(self.transaction)
        event_instruction = mismatched_event["meta"]["innerInstructions"][0]["instructions"][0]
        raw = bytearray(b58decode(event_instruction["data"]))
        token_offset = raw.find(b58decode(TOKEN_PROGRAM_ID))
        self.assertGreaterEqual(token_offset, 0)
        raw[token_offset] ^= 1
        event_instruction["data"] = b58encode(bytes(raw))
        self.assert_code("EVENT_MISMATCH", lambda: self.decode(mismatched_event))


class DirectPumpContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        prior = self.fixture["prior_cursor"]
        self.prior = FinalizedCursor(
            CursorBoundary(prior["slot"], prior["signature"]),
            ContinuityState(prior["continuity"]),
        )

    def test_duplicate_is_idempotent_and_contiguous_cursor_advances(self) -> None:
        cycle = self.fixture["cycles"]["first"]
        result = run_fixture_cycle(
            cycle_operations(
                cycle["signature"],
                cycle["cutoff_slot"],
                cycle["block_time"],
                cutoff=cycle["cutoff_slot"],
            ),
            prior_cursor=self.prior,
        )
        self.assertEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual(result.cursor.boundary, CursorBoundary(101, "sig-101"))
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.duplicate_signatures, 1)
        self.assertEqual(
            dict(result.accounting.governed_requests),
            {SESSION_REQUEST: 1, BACKFILL_REQUEST: 1, TRANSACTION_REQUEST: 1},
        )
        self.assertEqual(result.accounting.underlying_rpc_operations, 5)

    def test_interrupted_live_session_runs_backfill_but_preserves_gap(self) -> None:
        cycle = self.fixture["cycles"]["first"]
        result = run_fixture_cycle(
            cycle_operations(
                cycle["signature"],
                cycle["cutoff_slot"],
                cycle["block_time"],
                cutoff=cycle["cutoff_slot"],
                disconnected=True,
            ),
            prior_cursor=self.prior,
        )
        self.assertTrue(result.live_disconnected)
        self.assertEqual(result.backfill_pages, 1)
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.cursor, FinalizedCursor(self.prior.boundary, ContinuityState.GAPPED))

    def test_two_page_bound_is_gapped_and_next_cycle_uses_last_contiguous_cursor(self) -> None:
        gap_transaction, _ = valid_transaction("sig-gap", 119, 1700000119)
        gap_row = signature_row("sig-gap", 119)
        two_pages = (
            operation("session", SESSION_REQUEST, "getSlot", 120),
            operation(
                "session",
                SESSION_REQUEST,
                "logsSubscribe",
                {"notifications": [], "disconnected": False},
            ),
            operation("session", SESSION_REQUEST, "logsUnsubscribe", True),
            operation(
                "page-1",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {"rows": [gap_row], "complete_to_prior_cursor": False},
            ),
            operation(
                "page-2",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {"rows": [gap_row], "complete_to_prior_cursor": False},
            ),
            operation(
                "tx-gap",
                TRANSACTION_REQUEST,
                "getTransaction",
                gap_transaction,
            ),
        )
        gapped = run_fixture_cycle(two_pages, prior_cursor=self.prior)
        self.assertEqual(gapped.backfill_pages, 2)
        self.assertEqual(gapped.cursor, FinalizedCursor(self.prior.boundary, ContinuityState.GAPPED))

        first = self.fixture["cycles"]["first"]
        contiguous = run_fixture_cycle(
            cycle_operations(
                first["signature"],
                first["cutoff_slot"],
                first["block_time"],
                cutoff=first["cutoff_slot"],
            ),
            prior_cursor=self.prior,
        )
        next_cycle = self.fixture["cycles"]["next"]
        continued = run_fixture_cycle(
            cycle_operations(
                next_cycle["signature"],
                next_cycle["cutoff_slot"],
                next_cycle["block_time"],
                cutoff=next_cycle["cutoff_slot"],
            ),
            prior_cursor=contiguous.cursor,
        )
        self.assertEqual(continued.cursor.boundary, CursorBoundary(102, "sig-102"))
        self.assertEqual(continued.cursor.continuity, ContinuityState.CONTIGUOUS)

    def test_unknown_cursor_post_cutoff_and_deterministic_replay(self) -> None:
        cycle = self.fixture["cycles"]["first"]
        operations = cycle_operations(
            cycle["signature"],
            cycle["cutoff_slot"],
            cycle["block_time"],
            cutoff=cycle["cutoff_slot"],
        )
        unknown = run_fixture_cycle(
            operations,
            prior_cursor=FinalizedCursor(None, ContinuityState.UNKNOWN),
        )
        self.assertEqual(unknown.cursor, FinalizedCursor(None, ContinuityState.UNKNOWN))
        self.assertEqual(
            run_fixture_cycle(operations, prior_cursor=self.prior).canonical(),
            run_fixture_cycle(operations, prior_cursor=self.prior).canonical(),
        )

        post_cutoff = (
            operation("session", SESSION_REQUEST, "getSlot", 100),
            operation(
                "session",
                SESSION_REQUEST,
                "logsSubscribe",
                {
                    "notifications": [signature_row("sig-later", 101)],
                    "disconnected": False,
                },
            ),
            operation("session", SESSION_REQUEST, "logsUnsubscribe", True),
            operation(
                "page-1",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {"rows": [], "complete_to_prior_cursor": True},
            ),
        )
        result = run_fixture_cycle(post_cutoff, prior_cursor=self.prior)
        self.assertEqual([item.code for item in result.rejections], ["POST_CUTOFF"])
        self.assertEqual(result.cursor.continuity, ContinuityState.UNKNOWN)
        self.assertEqual(result.cursor.boundary, self.prior.boundary)

    def test_conflicting_duplicate_is_a_visible_gap_and_no_claim(self) -> None:
        first = signature_row("sig-conflict", 101)
        conflicting = signature_row("sig-conflict", 102)
        operations = (
            operation("session", SESSION_REQUEST, "getSlot", 102),
            operation(
                "session",
                SESSION_REQUEST,
                "logsSubscribe",
                {"notifications": [], "disconnected": False},
            ),
            operation("session", SESSION_REQUEST, "logsUnsubscribe", True),
            operation(
                "page-1",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [first, conflicting],
                    "complete_to_prior_cursor": True,
                },
            ),
        )
        result = run_fixture_cycle(operations, prior_cursor=self.prior)
        self.assertEqual(result.cursor.continuity, ContinuityState.GAPPED)
        self.assertEqual(result.cursor.boundary, self.prior.boundary)
        self.assertEqual(result.observations, ())
        self.assertIn("CONFLICTING_DUPLICATE", [item.code for item in result.rejections])


class DirectPumpOwnershipAndCeilingTests(unittest.TestCase):
    def assert_code(self, code: str, callback) -> None:
        with self.assertRaises(PumpContractError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)

    def test_governor_registry_and_owner_bypass_prevention(self) -> None:
        for request_kind in (SESSION_REQUEST, BACKFILL_REQUEST, TRANSACTION_REQUEST):
            self.assertTrue(can_request_source("solana_rpc", request_kind, 0).allowed)

        wrong_governor = FixtureOperationPort(
            (
                operation(
                    "session",
                    SESSION_REQUEST,
                    "getSlot",
                    1,
                    source_name="pumpportal",
                ),
            )
        )
        self.assert_code(
            "SOURCE_GOVERNOR_BYPASS",
            lambda: wrong_governor.take("getSlot", SESSION_REQUEST),
        )
        wrong_scheduler = FixtureOperationPort(
            (
                operation(
                    "session",
                    SESSION_REQUEST,
                    "getSlot",
                    1,
                    scheduler_work_type="UNOWNED",
                ),
            )
        )
        self.assert_code(
            "CENTRAL_SCHEDULER_BYPASS",
            lambda: wrong_scheduler.take("getSlot", SESSION_REQUEST),
        )
        self.assertEqual(SCHEDULER_JOB_KIND, "DISCOVERY_REFRESH")
        self.assertEqual(SCHEDULER_WORK_TYPE, "DISCOVERY_PUMPFUN_LATEST")

    def test_request_rpc_and_underlying_operation_ceilings(self) -> None:
        self.assertEqual(enforce_underlying_operation_ceiling(44), 45)
        self.assert_code(
            "UNDERLYING_OPERATION_CEILING",
            lambda: enforce_underlying_operation_ceiling(45),
        )

        reconnect = FixtureOperationPort(
            (
                operation("session", SESSION_REQUEST, "logsSubscribe", {}),
                operation("session", SESSION_REQUEST, "logsSubscribe", {}),
            )
        )
        reconnect.take("logsSubscribe", SESSION_REQUEST)
        self.assert_code(
            "RPC_OPERATION_CEILING",
            lambda: reconnect.take("logsSubscribe", SESSION_REQUEST),
        )

        mutable_cutoff = FixtureOperationPort(
            (
                operation("session", SESSION_REQUEST, "getSlot", 1),
                operation("session", SESSION_REQUEST, "getSlot", 2),
            )
        )
        mutable_cutoff.take("getSlot", SESSION_REQUEST)
        self.assert_code(
            "RPC_OPERATION_CEILING",
            lambda: mutable_cutoff.take("getSlot", SESSION_REQUEST),
        )

        third_page = FixtureOperationPort(
            tuple(
                operation(
                    f"page-{number}",
                    BACKFILL_REQUEST,
                    "getSignaturesForAddress",
                    {},
                )
                for number in range(3)
            )
        )
        third_page.take("getSignaturesForAddress", BACKFILL_REQUEST)
        third_page.take("getSignaturesForAddress", BACKFILL_REQUEST)
        self.assert_code(
            "GOVERNED_REQUEST_CEILING",
            lambda: third_page.take("getSignaturesForAddress", BACKFILL_REQUEST),
        )

    def test_fixture_module_has_no_network_or_persistence_surface(self) -> None:
        source = (
            Path(__file__).parents[1]
            / "src"
            / "printer_v1"
            / "sources"
            / "pumpfun_direct.py"
        ).read_text(encoding="utf-8")
        forbidden = (
            "import requests",
            "import websockets",
            "urllib",
            "sqlite3",
            "socket.",
            "httpx",
            "aiohttp",
        )
        self.assertFalse(any(term in source for term in forbidden))
        self.assertNotIn("retry", source.lower())
        self.assertNotIn("endpoint", source.lower())


if __name__ == "__main__":
    unittest.main()