"""V2-9.7E.4G synthetic proofs: cutoff-bound pagination + historical mint origin."""

from __future__ import annotations

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


def origin_op(
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
        # Reuse request ids so governed ceiling stays 1 per kind across pages/txs.
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
    creator_raw = hashlib.sha256(f"creator-{signature}".encode("ascii")).digest()
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
    create_data = (
        CREATE_DISCRIMINATOR
        + borsh_string("Fixture Coin")
        + borsh_string("FIX")
        + borsh_string("https://example.invalid/meta.json")
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
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
    }
    return transaction, expected


def non_create_transaction(signature: str, slot: int, block_time: int) -> dict:
    transaction, _ = valid_transaction(signature, slot, block_time)
    raw = bytearray(
        b58decode(transaction["transaction"]["message"]["instructions"][0]["data"])
    )
    raw[0:8] = bytes((9, 9, 9, 9, 9, 9, 9, 9))
    transaction["transaction"]["message"]["instructions"][0]["data"] = b58encode(bytes(raw))
    # V2-9.7E.6: ordinary Pump traffic (buy/sell) does not reference the
    # create-exclusive mint authority. Drop account index 1 so this fixture is
    # a realistic non-create rather than an unknown create-family layout.
    transaction["transaction"]["message"]["instructions"][0]["accounts"] = [
        index for index in range(14) if index != 1
    ]
    return transaction


def prior_contiguous() -> FinalizedCursor:
    return FinalizedCursor(CursorBoundary(50, "sig-prior"), ContinuityState.CONTIGUOUS)


class CutoffPaginationTests(unittest.TestCase):
    def test_first_page_all_post_cutoff_second_page_in_cutoff_create(self) -> None:
        """Page1 newer than cutoff; page2 older in-cutoff create is admitted."""
        cutoff = 100
        create_tx, expected = valid_transaction("sig-old-create", 90, 1700000090)
        # Page1: all post-cutoff (slots 105-106)
        page1 = [
            signature_row("sig-new-b", 106),
            signature_row("sig-new-a", 105),
        ]
        # Page2: older in-cutoff (as if before=walk)
        page2 = [signature_row("sig-old-create", 90)]
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", cutoff),
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
                {"rows": page1, "complete_to_prior_cursor": False},
            ),
            operation(
                "page-2",
                BACKFILL_REQUEST,
                "getSignaturesForAddress",
                {"rows": page2, "complete_to_prior_cursor": True},
            ),
            operation("tx", TRANSACTION_REQUEST, "getTransaction", create_tx),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.post_cutoff_count, 2)
        self.assertEqual(result.decode_attempts, 1)
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.observations[0].mint, expected["mint"])
        # Post-cutoff alone is not a continuity fault; complete interval → CONTIGUOUS
        self.assertEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual(result.accounting.governed_requests[TRANSACTION_REQUEST], 1)

    def test_mixed_pre_post_cutoff_post_cutoff_skips_decode_budget(self) -> None:
        cutoff = 100
        tx, _ = valid_transaction("sig-ok", 95, 1700000095)
        rows = [
            signature_row("sig-new", 110),  # post
            signature_row("sig-fail", 96, err={"e": 1}),  # failed, no decode
            signature_row("sig-ok", 95),
        ]
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", cutoff),
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
            operation("tx", TRANSACTION_REQUEST, "getTransaction", tx),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(result.post_cutoff_count, 1)
        self.assertEqual(result.failed_signature_count, 1)
        self.assertEqual(result.decode_attempts, 1)
        self.assertEqual(len(result.observations), 1)

    def test_all_post_cutoff_does_not_claim_contiguous(self) -> None:
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 100),
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
                    "rows": [signature_row("sig-a", 101), signature_row("sig-b", 102)],
                    "complete_to_prior_cursor": True,
                },
            ),
        )
        cold = run_fixture_cycle(
            ops, prior_cursor=FinalizedCursor(None, ContinuityState.UNKNOWN)
        )
        self.assertEqual(cold.post_cutoff_count, 2)
        self.assertEqual(cold.decode_attempts, 0)
        self.assertEqual(cold.cursor.continuity, ContinuityState.UNKNOWN)

        trusted = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        # complete_to_prior_cursor true but no admitted rows — still not inventing
        # contiguous advance over empty admitted set; continuity_fault false if complete
        # admitted_ordered empty → boundary falls back to prior
        self.assertEqual(trusted.post_cutoff_count, 2)
        self.assertEqual(trusted.observations, ())

    def test_cold_start_and_persisted_cursor_continuation(self) -> None:
        tx1, _ = valid_transaction("sig-101", 101, 1700000101)
        ops1 = (
            operation("session", SESSION_REQUEST, "getSlot", 101),
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
                    "rows": [signature_row("sig-101", 101)],
                    "complete_to_prior_cursor": True,
                },
            ),
            operation("tx", TRANSACTION_REQUEST, "getTransaction", tx1),
        )
        cold = run_fixture_cycle(
            ops1, prior_cursor=FinalizedCursor(None, ContinuityState.UNKNOWN)
        )
        self.assertEqual(cold.cursor.continuity, ContinuityState.UNKNOWN)
        self.assertEqual(len(cold.observations), 1)

        contiguous = run_fixture_cycle(ops1, prior_cursor=prior_contiguous())
        self.assertEqual(contiguous.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual(
            contiguous.cursor.boundary, CursorBoundary(101, "sig-101")
        )

        tx2, _ = valid_transaction("sig-102", 102, 1700000102)
        ops2 = (
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
                    "rows": [signature_row("sig-102", 102)],
                    "complete_to_prior_cursor": True,
                },
            ),
            operation("tx2", TRANSACTION_REQUEST, "getTransaction", tx2),
        )
        continued = run_fixture_cycle(ops2, prior_cursor=contiguous.cursor)
        self.assertEqual(continued.cursor.boundary, CursorBoundary(102, "sig-102"))
        self.assertEqual(
            run_fixture_cycle(ops2, prior_cursor=contiguous.cursor).canonical(),
            continued.canonical(),
        )

    def test_deterministic_page_order_independent_of_row_order(self) -> None:
        tx_a, _ = valid_transaction("sig-a", 91, 1700000091)
        tx_b, _ = valid_transaction("sig-b", 92, 1700000092)
        # Unsorted page rows; decode order must be slot/signature ascending.
        rows = [signature_row("sig-b", 92), signature_row("sig-a", 91)]
        ops = (
            operation("session", SESSION_REQUEST, "getSlot", 100),
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
            operation("tx-a", TRANSACTION_REQUEST, "getTransaction", tx_a),
            operation("tx-b", TRANSACTION_REQUEST, "getTransaction", tx_b),
        )
        result = run_fixture_cycle(ops, prior_cursor=prior_contiguous())
        self.assertEqual(
            [o.signature for o in result.observations], ["sig-a", "sig-b"]
        )


class HistoricalMintOriginTests(unittest.TestCase):
    def test_create_found_on_later_page(self) -> None:
        mint_label = "hist-mint"
        create_tx, expected = valid_transaction(
            "sig-create", 10, 1700000010, mint_label=mint_label
        )
        mint = expected["mint"]
        non_create = non_create_transaction("sig-trade", 50, 1700000050)
        # Page1 newest trades only; page2 older includes create.
        ops = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-trade", 50),
                        signature_row("sig-trade2", 49, err=1),
                    ]
                },
            ),
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-create", 10)]},
            ),
            # Oldest-first attempts: first candidate after sort may be create at 10,
            # then trades — only plan txs that will be consumed.
            # Candidates in-cutoff sorted: create@10, trade@50 (trade2 failed).
            # Attempts: first create succeeds → only one tx.
            origin_op(
                "otx",
                ORIGIN_TRANSACTION_REQUEST,
                "getTransaction",
                create_tx,
            ),
        )
        result = run_mint_origin_lookup(ops, expected_mint=mint, cutoff_slot=100)
        self.assertIsNotNone(result.observation)
        assert result.observation is not None
        self.assertEqual(result.observation.mint, mint)
        self.assertEqual(result.pages_used, 2)
        self.assertEqual(result.decode_attempts, 1)

    def test_non_create_then_create_within_attempt_budget(self) -> None:
        mint_label = "hist-mint-2"
        create_tx, expected = valid_transaction(
            "sig-c", 5, 1700000005, mint_label=mint_label
        )
        mint = expected["mint"]
        non_create = non_create_transaction("sig-t", 6, 1700000006)
        ops = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-t", 6),
                        signature_row("sig-c", 5),
                    ]
                },
            ),
            # Oldest first: sig-c then sig-t
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", create_tx),
        )
        result = run_mint_origin_lookup(ops, expected_mint=mint, cutoff_slot=100)
        self.assertIsNotNone(result.observation)
        self.assertEqual(result.decode_attempts, 1)

        # Non-create first in slot order (both same page): slot 5 create, slot 6 trade
        # Already covered. Reverse: only trade then create with 2 attempts.
        ops2 = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-t", 6),
                        signature_row("sig-c", 5),
                    ]
                },
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", non_create),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", create_tx),
        )
        # Wait — oldest first is sig-c@5 first, so first tx must be create.
        # For non-create-first attempt order use higher slot for create? create is older.
        # Use same slot order: attempt non-create at slot 5 by labeling trade as older.
        trade_old = non_create_transaction("sig-old-trade", 4, 1700000004)
        create_newish, expected2 = valid_transaction(
            "sig-create2", 5, 1700000005, mint_label=mint_label
        )
        mint2 = expected2["mint"]
        ops3 = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {
                    "rows": [
                        signature_row("sig-create2", 5),
                        signature_row("sig-old-trade", 4),
                    ]
                },
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", trade_old),
            origin_op(
                "otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", create_newish
            ),
        )
        result3 = run_mint_origin_lookup(ops3, expected_mint=mint2, cutoff_slot=100)
        self.assertIsNotNone(result3.observation)
        self.assertEqual(result3.decode_attempts, 2)
        self.assertIn("NOT_SUPPORTED_CREATE", [r.code for r in result3.rejections])

    def test_mint_mismatch_and_create_v2_blocked(self) -> None:
        tx, expected = valid_transaction("sig-mm", 20, 1700000020, mint_label="real")
        other, _ = pubkey("other")
        ops = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-mm", 20)]},
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", tx),
        )
        result = run_mint_origin_lookup(ops, expected_mint=other, cutoff_slot=100)
        self.assertIsNone(result.observation)
        self.assertIn("MINT_MISMATCH", [r.code for r in result.rejections])

        v2 = dict(tx)
        # deep copy instruction data
        import copy

        v2 = copy.deepcopy(tx)
        raw = bytearray(
            b58decode(v2["transaction"]["message"]["instructions"][0]["data"])
        )
        raw[0:8] = CREATE_V2_DISCRIMINATOR
        v2["transaction"]["message"]["instructions"][0]["data"] = b58encode(bytes(raw))
        ops_v2 = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-mm", 20)]},
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", v2),
        )
        result_v2 = run_mint_origin_lookup(
            ops_v2, expected_mint=expected["mint"], cutoff_slot=100
        )
        self.assertIsNone(result_v2.observation)
        # V2-9.7E.6: create_v2 is now adopted. This fixture is a legacy-shaped
        # body carrying the create_v2 discriminator, which is fail-closed as
        # MALFORMED_TRANSACTION. Genuine create_v2 support is proven in
        # tests/test_v2_9_7e_6_pump_create_classification.py.
        self.assertIn("MALFORMED_TRANSACTION", [r.code for r in result_v2.rejections])

    def test_exhausted_history_and_unavailable_tx(self) -> None:
        ops_empty = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": []},
            ),
        )
        empty = run_mint_origin_lookup(
            ops_empty, expected_mint=pubkey("x")[0], cutoff_slot=100
        )
        self.assertIsNone(empty.observation)
        self.assertEqual(empty.pages_used, 1)
        codes = [r.code for r in empty.rejections]
        self.assertTrue(
            "UNAVAILABLE_HISTORY" in codes or "NOT_SUPPORTED_CREATE" in codes
        )

        ops_null = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-null", 10)]},
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", None),
        )
        null_r = run_mint_origin_lookup(
            ops_null, expected_mint=pubkey("y")[0], cutoff_slot=100
        )
        self.assertIsNone(null_r.observation)
        self.assertIn("UNAVAILABLE_HISTORY", [r.code for r in null_r.rejections])

    def test_governor_scheduler_and_replay(self) -> None:
        for kind in (
            SESSION_REQUEST,
            BACKFILL_REQUEST,
            TRANSACTION_REQUEST,
            ORIGIN_SIGNATURE_REQUEST,
            ORIGIN_TRANSACTION_REQUEST,
        ):
            self.assertTrue(can_request_source("solana_rpc", kind, 0).allowed)

        tx, expected = valid_transaction(
            "sig-r", 11, 1700000011, mint_label="replay-mint"
        )
        ops = (
            origin_op(
                "osig",
                ORIGIN_SIGNATURE_REQUEST,
                "getSignaturesForAddress",
                {"rows": [signature_row("sig-r", 11)]},
            ),
            origin_op("otx", ORIGIN_TRANSACTION_REQUEST, "getTransaction", tx),
        )
        a = run_mint_origin_lookup(
            ops, expected_mint=expected["mint"], cutoff_slot=100
        )
        b = run_mint_origin_lookup(
            ops, expected_mint=expected["mint"], cutoff_slot=100
        )
        self.assertEqual(a.canonical(), b.canonical())

        with self.assertRaises(PumpContractError) as raised:
            run_mint_origin_lookup(
                (
                    operation(
                        "osig",
                        ORIGIN_SIGNATURE_REQUEST,
                        "getSignaturesForAddress",
                        {"rows": []},
                        scheduler_work_type="DISCOVERY_PUMPFUN_LATEST",
                    ),
                ),
                expected_mint="x",
                cutoff_slot=1,
            )
        self.assertEqual(raised.exception.code, "CENTRAL_SCHEDULER_BYPASS")


if __name__ == "__main__":
    unittest.main()
