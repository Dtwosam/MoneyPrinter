"""V2-9.7E.4C synthetic proofs for direct Pump create-capture productivity."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import struct
import unittest

from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    BACKFILL_REQUEST,
    CREATE_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    ContinuityState,
    CursorBoundary,
    EARLY_CREATE_STOP,
    EVENT_AUTHORITY_ID,
    FinalizedCursor,
    FixtureOperation,
    GLOBAL_ID,
    MINT_AUTHORITY_ID,
    ORIGIN_SCHEDULER_WORK_TYPE,
    ORIGIN_SIGNATURE_REQUEST,
    ORIGIN_TRANSACTION_REQUEST,
    PUMP_PROGRAM_ID,
    PumpContractError,
    RENT_SYSVAR_ID,
    SESSION_REQUEST,
    SYSTEM_PROGRAM_ID,
    TOKEN_METADATA_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    TRANSACTION_DECODE_CEILING,
    TRANSACTION_REQUEST,
    decode_finalized_create,
    derive_program_address,
    run_fixture_cycle,
    run_mint_origin_lookup,
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


def origin_operation(
    request_id: str,
    request_kind: str,
    rpc_operation: str,
    response: object,
) -> FixtureOperation:
    return operation(
        request_id,
        request_kind,
        rpc_operation,
        response,
        scheduler_work_type=ORIGIN_SCHEDULER_WORK_TYPE,
    )


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
    mint_label: str | None = None,
) -> tuple[dict, dict]:
    label = mint_label or f"mint-{signature}"
    mint, mint_raw = pubkey(label)
    creator, _ = pubkey(f"creator-{signature}")
    user, _ = pubkey(f"user-{signature}")
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
        + hashlib.sha256(f"creator-{signature}".encode("ascii")).digest()
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
                        "programIdIndex": 13,
                        "accounts": list(range(14)),
                        "data": b58encode(create_data),
                    }
                ],
            },
        },
    }
    expected = {
        "mint": mint,
        "bonding_curve": curve,
        "associated_bonding_curve": associated_curve,
        "creator_address": b58encode(
            hashlib.sha256(f"creator-{signature}".encode("ascii")).digest()
        ),
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
    }
    return transaction, expected


def non_create_transaction(signature: str, slot: int, block_time: int) -> dict:
    transaction, _ = valid_transaction(signature, slot, block_time)
    # Replace create discriminator with buy-like non-create bytes (not create_v2).
    raw = bytearray(b58decode(transaction["transaction"]["message"]["instructions"][0]["data"]))
    raw[0:8] = bytes((1, 2, 3, 4, 5, 6, 7, 8))
    transaction["transaction"]["message"]["instructions"][0]["data"] = b58encode(bytes(raw))
    # V2-9.7E.6: ordinary Pump traffic (buy/sell) does not reference the
    # create-exclusive mint authority. Drop account index 1 so this fixture is
    # a realistic non-create rather than an unknown create-family layout.
    transaction["transaction"]["message"]["instructions"][0]["accounts"] = [
        index for index in range(14) if index != 1
    ]
    return transaction


def prior_contiguous() -> FinalizedCursor:
    return FinalizedCursor(CursorBoundary(100, "sig-prior"), ContinuityState.CONTIGUOUS)


class ProductivityDirectCycleTests(unittest.TestCase):
    def test_failed_signatures_skip_decode_budget_and_do_not_gap_alone(self) -> None:
        create_tx, expected = valid_transaction("sig-ok", 110, 1700000110)
        # 3 failed + 1 create; failed must not consume getTransaction budget.
        rows = [
            signature_row("sig-fail-a", 107, err={"InstructionError": [0, "Custom"]}),
            signature_row("sig-fail-b", 108, err={"InstructionError": [0, "Custom"]}),
            signature_row("sig-fail-c", 109, err={"InstructionError": [0, "Custom"]}),
            signature_row("sig-ok", 110),
        ]
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 110),
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
                {"rows": rows, "complete_to_prior_cursor": True},
            ),
            operation("tx-ok", TRANSACTION_REQUEST, "getTransaction", create_tx),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.failed_signature_count, 3)
        self.assertEqual(result.decode_attempts, 1)
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.observations[0].mint, expected["mint"])
        self.assertEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual(
            result.accounting.governed_requests[TRANSACTION_REQUEST], 1
        )

    def test_non_create_alone_is_not_continuity_emergency(self) -> None:
        non_create = non_create_transaction("sig-trade", 105, 1700000105)
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 105),
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
                    "rows": [signature_row("sig-trade", 105)],
                    "complete_to_prior_cursor": True,
                },
            ),
            operation("tx-trade", TRANSACTION_REQUEST, "getTransaction", non_create),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.observations, ())
        self.assertEqual(result.non_create_count, 1)
        self.assertEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertIn("NOT_SUPPORTED_CREATE", [r.code for r in result.rejections])

    def test_deterministic_admission_independent_of_response_order(self) -> None:
        tx_a, exp_a = valid_transaction("sig-b", 102, 1700000102)
        tx_b, exp_b = valid_transaction("sig-a", 101, 1700000101)
        # Page returns higher slot first; decode order must still be (slot, signature).
        rows = [signature_row("sig-b", 102), signature_row("sig-a", 101)]
        ops = (
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
                {"rows": rows, "complete_to_prior_cursor": True},
            ),
            # Fixture port is sequential: first take is earliest (sig-a @ 101).
            operation("tx-a", TRANSACTION_REQUEST, "getTransaction", tx_b),
            operation("tx-b", TRANSACTION_REQUEST, "getTransaction", tx_a),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(
            [obs.signature for obs in result.observations],
            ["sig-a", "sig-b"],
        )
        self.assertEqual(result.observations[0].mint, exp_b["mint"])
        self.assertEqual(result.observations[1].mint, exp_a["mint"])
        self.assertEqual(
            run_fixture_cycle(ops, prior_cursor=prior_contiguous()).canonical(),
            result.canonical(),
        )

    def test_two_page_enumeration_and_decode_ceiling(self) -> None:
        # 18 successful finalized rows → ceiling trims to 16 decode-eligible;
        # early-create stop then consumes only EARLY_CREATE_STOP getTransaction.
        rows_page1 = [signature_row(f"sig-{i:02d}", 100 + i) for i in range(1, 17)]
        rows_page2 = [signature_row("sig-17", 117), signature_row("sig-18", 118)]
        txs = []
        for i in range(1, EARLY_CREATE_STOP + 1):
            tx, _ = valid_transaction(f"sig-{i:02d}", 100 + i, 1700000000 + i)
            txs.append(
                operation(
                    f"tx-{i}",
                    TRANSACTION_REQUEST,
                    "getTransaction",
                    tx,
                )
            )
        ops = (
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
                {"rows": rows_page1, "complete_to_prior_cursor": False},
            ),
            operation(
                "page-2",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {"rows": rows_page2, "complete_to_prior_cursor": True},
            ),
            *txs,
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.backfill_pages, 2)
        self.assertEqual(result.decode_attempts, EARLY_CREATE_STOP)
        self.assertEqual(len(result.observations), EARLY_CREATE_STOP)
        self.assertEqual(result.cursor.continuity, ContinuityState.GAPPED)
        codes = [r.code for r in result.rejections]
        self.assertIn("TRANSACTION_DECODE_CEILING", codes)
        self.assertIn("EARLY_CREATE_STOP", codes)
        self.assertEqual(TRANSACTION_DECODE_CEILING, 16)

    def test_early_create_stop_without_fault_when_interval_complete_and_under_ceiling(
        self,
    ) -> None:
        # 10 creates, complete interval, no overflow beyond 16 → early stop only.
        rows = [signature_row(f"sig-{i:02d}", 100 + i) for i in range(1, 11)]
        txs = []
        for i in range(1, 11):
            if i <= EARLY_CREATE_STOP:
                tx, _ = valid_transaction(f"sig-{i:02d}", 100 + i, 1700000000 + i)
                txs.append(
                    operation(f"tx-{i}", TRANSACTION_REQUEST, "getTransaction", tx)
                )
        ops = (
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
                {"rows": rows, "complete_to_prior_cursor": True},
            ),
            *txs,
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(len(result.observations), EARLY_CREATE_STOP)
        self.assertEqual(result.decode_attempts, EARLY_CREATE_STOP)
        self.assertEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual(
            sum(1 for r in result.rejections if r.code == "EARLY_CREATE_STOP"), 2
        )

    def test_create_v2_remains_blocked_and_gaps(self) -> None:
        tx, _ = valid_transaction("sig-v2", 103, 1700000103)
        raw = bytearray(
            b58decode(tx["transaction"]["message"]["instructions"][0]["data"])
        )
        raw[0:8] = CREATE_V2_DISCRIMINATOR
        tx["transaction"]["message"]["instructions"][0]["data"] = b58encode(bytes(raw))
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 103),
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
                    "rows": [signature_row("sig-v2", 103)],
                    "complete_to_prior_cursor": True,
                },
            ),
            operation("tx-v2", TRANSACTION_REQUEST, "getTransaction", tx),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.observations, ())
        self.assertEqual(result.cursor.continuity, ContinuityState.GAPPED)
        # V2-9.7E.6: create_v2 is now adopted. This fixture is a legacy-shaped
        # body carrying the create_v2 discriminator, which is fail-closed as
        # MALFORMED_TRANSACTION. Genuine create_v2 support is proven in
        # tests/test_v2_9_7e_6_pump_create_classification.py.
        self.assertIn("MALFORMED_TRANSACTION", [r.code for r in result.rejections])

    def test_unavailable_history_is_genuine_gap(self) -> None:
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 104),
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
                    "rows": [signature_row("sig-null", 104)],
                    "complete_to_prior_cursor": True,
                },
            ),
            operation("tx-null", TRANSACTION_REQUEST, "getTransaction", None),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.cursor.continuity, ContinuityState.GAPPED)
        self.assertIn("UNAVAILABLE_HISTORY", [r.code for r in result.rejections])

    def test_cutoff_and_cold_unknown_cursor(self) -> None:
        ops = (
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
        result = run_fixture_cycle(
            ops,
            prior_cursor=FinalizedCursor(None, ContinuityState.UNKNOWN),
        )
        self.assertEqual(result.cursor.continuity, ContinuityState.UNKNOWN)
        self.assertIn("POST_CUTOFF", [r.code for r in result.rejections])

    def test_governor_and_scheduler_bypass_prevention(self) -> None:
        for kind in (
            SESSION_REQUEST,
            BACKFILL_REQUEST,
            TRANSACTION_REQUEST,
            ORIGIN_SIGNATURE_REQUEST,
            ORIGIN_TRANSACTION_REQUEST,
        ):
            self.assertTrue(can_request_source("solana_rpc", kind, 0).allowed)

        with self.assertRaises(PumpContractError) as raised:
            run_fixture_cycle(
                (
                    operation(
                        "bad",
                        SESSION_REQUEST,
                        "getSlot",
                        1,
                        source_name="helius_free",
                    ),
                ),
                prior_cursor=prior_contiguous(),
            )
        self.assertEqual(raised.exception.code, "SOURCE_GOVERNOR_BYPASS")

        with self.assertRaises(PumpContractError) as raised2:
            run_mint_origin_lookup(
                (
                    operation(
                        "sig",
                        ORIGIN_SIGNATURE_REQUEST,
                        "getSignaturesForAddress",
                        {"rows": []},
                        scheduler_work_type="DISCOVERY_PUMPFUN_LATEST",
                    ),
                ),
                expected_mint="Mint111111111111111111111111111111111111111",
                cutoff_slot=1,
            )
        self.assertEqual(raised2.exception.code, "CENTRAL_SCHEDULER_BYPASS")


class MintOriginLookupTests(unittest.TestCase):
    def test_bounded_mint_origin_success(self) -> None:
        mint_label = "secondary-mint-ok"
        tx, expected = valid_transaction("sig-origin", 200, 1700000200, mint_label=mint_label)
        mint = expected["mint"]
        ops = (
            origin_operation(
                "origin-sig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-fail", 199, err={"err": 1}),
                        signature_row("sig-origin", 200),
                    ]
                },
            ),
            origin_operation(
                "origin-tx",
                ORIGIN_TRANSACTION_REQUEST,
                "getTransaction",
                tx,
            ),
        )
        result = run_mint_origin_lookup(ops, expected_mint=mint, cutoff_slot=200)
        self.assertIsNotNone(result.observation)
        assert result.observation is not None
        self.assertEqual(result.observation.mint, mint)
        self.assertEqual(result.decode_attempts, 1)
        self.assertEqual(result.accounting.governed_requests[ORIGIN_SIGNATURE_REQUEST], 1)
        self.assertEqual(result.accounting.governed_requests[ORIGIN_TRANSACTION_REQUEST], 1)
        self.assertEqual(
            run_mint_origin_lookup(ops, expected_mint=mint, cutoff_slot=200).canonical(),
            result.canonical(),
        )

    def test_mint_mismatch_rejection(self) -> None:
        tx, expected = valid_transaction("sig-mm", 201, 1700000201, mint_label="real-mint")
        other, _ = pubkey("other-mint")
        ops = (
            origin_operation(
                "origin-sig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-mm", 201)]},
            ),
            origin_operation(
                "origin-tx",
                ORIGIN_TRANSACTION_REQUEST,
                "getTransaction",
                tx,
            ),
        )
        result = run_mint_origin_lookup(ops, expected_mint=other, cutoff_slot=201)
        self.assertIsNone(result.observation)
        self.assertIn("MINT_MISMATCH", [r.code for r in result.rejections])

    def test_failed_only_mint_history_no_transaction_budget(self) -> None:
        ops = (
            origin_operation(
                "origin-sig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-f1", 190, err=1),
                        signature_row("sig-f2", 191, err=1),
                    ]
                },
            ),
        )
        result = run_mint_origin_lookup(
            ops,
            expected_mint=pubkey("any")[0],
            cutoff_slot=200,
        )
        self.assertIsNone(result.observation)
        self.assertEqual(result.decode_attempts, 0)
        self.assertEqual(result.accounting.governed_requests.get(ORIGIN_TRANSACTION_REQUEST, 0), 0)

    def test_create_v2_blocked_on_mint_lookup(self) -> None:
        tx, expected = valid_transaction("sig-v2m", 202, 1700000202, mint_label="v2-mint")
        raw = bytearray(
            b58decode(tx["transaction"]["message"]["instructions"][0]["data"])
        )
        raw[0:8] = CREATE_V2_DISCRIMINATOR
        tx["transaction"]["message"]["instructions"][0]["data"] = b58encode(bytes(raw))
        ops = (
            origin_operation(
                "origin-sig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-v2m", 202)]},
            ),
            origin_operation(
                "origin-tx",
                ORIGIN_TRANSACTION_REQUEST,
                "getTransaction",
                tx,
            ),
        )
        result = run_mint_origin_lookup(
            ops, expected_mint=expected["mint"], cutoff_slot=202
        )
        self.assertIsNone(result.observation)
        # V2-9.7E.6: create_v2 is now adopted. This fixture is a legacy-shaped
        # body carrying the create_v2 discriminator, which is fail-closed as
        # MALFORMED_TRANSACTION. Genuine create_v2 support is proven in
        # tests/test_v2_9_7e_6_pump_create_classification.py.
        self.assertIn("MALFORMED_TRANSACTION", [r.code for r in result.rejections])


class DecoderStillExact(unittest.TestCase):
    def test_supported_create_normalizes(self) -> None:
        tx, expected = valid_transaction("sig-norm", 150, 1700000150)
        observed = decode_finalized_create(
            tx,
            reference=__import__(
                "printer_v1.sources.pumpfun_direct", fromlist=["SignatureReference"]
            ).SignatureReference("sig-norm", 150, "finalized", None),
            cutoff_slot=150,
        )
        for field, value in expected.items():
            self.assertEqual(getattr(observed, field), value)


if __name__ == "__main__":
    unittest.main()
