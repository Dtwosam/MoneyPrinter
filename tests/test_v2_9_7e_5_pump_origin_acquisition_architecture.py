"""V2-9.7E.5 synthetic + integration proofs for the Pump origin architecture reset.

Covers the signature-anchored finalized acquisition owner, the durable
prospective origin registry, retirement of the pre-reset primary paths, and
entry of registry-confirmed origins into the unchanged fixed gates.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from printer_v1.db.migrate import apply_migrations
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    CREATE_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    EVENT_AUTHORITY_ID,
    GLOBAL_ID,
    MINT_AUTHORITY_ID,
    PUMP_PROGRAM_ID,
    PumpCreateObservation,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_METADATA_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    derive_program_address,
    run_fixture_cycle,
    run_mint_origin_lookup,
)
from printer_v1.sources.pumpfun_direct import (
    RetiredPrimaryPathError as DirectRetiredPrimaryPathError,
)
from printer_v1.sources.pumpfun_origin import (
    ACQUISITION_MODE_PROSPECTIVE,
    CREATE_INDEX_DECODE_CEILING,
    CREATE_INDEX_PAGE_CEILING,
    CREATE_INDEX_PAGE_SIZE,
    PUMP_CREATE_INDEX_ADDRESS,
    REQUEST_CEILINGS,
    SIGNATURE_PAGE_REQUEST,
    TRANSACTION_REQUEST,
    ContinuityState,
    CursorBoundary,
    FinalizedOriginCursor,
    FixtureOperation,
    OriginRegistryError,
    PumpContractError,
    load_origin_cursor,
    lookup_confirmed_origin,
    record_confirmed_origin,
    run_acquisition_cycle,
    save_origin_cursor,
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


def page_op(request_id: str, rows: list, **extra) -> FixtureOperation:
    response = {"rows": rows}
    response.update(extra)
    return FixtureOperation(
        request_id=request_id,
        request_kind=SIGNATURE_PAGE_REQUEST,
        rpc_operation="getSignaturesForAddress",
        response=response,
    )


def tx_op(request_id: str, response: object) -> FixtureOperation:
    return FixtureOperation(
        request_id=request_id,
        request_kind=TRANSACTION_REQUEST,
        rpc_operation="getTransaction",
        response=response,
    )


def signature_row(signature: str, slot: int, *, status: str = "finalized", err=None):
    return {
        "signature": signature,
        "slot": slot,
        "confirmationStatus": status,
        "err": err,
    }


def create_transaction(
    signature: str,
    slot: int,
    block_time: int,
    *,
    mint_label: str | None = None,
    discriminator: bytes = CREATE_DISCRIMINATOR,
) -> tuple[dict, str]:
    """Build one supported finalized Pump create transaction plus its mint."""
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
    data = (
        discriminator
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
                        "data": b58encode(data),
                    }
                ],
            },
        },
    }
    return transaction, mint


def non_create_transaction(signature: str, slot: int, block_time: int) -> dict:
    """A finalized Pump transaction that is not a create (buy/sell shape)."""
    other, _ = pubkey(f"other-{signature}")
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
                "accountKeys": [other, PUMP_PROGRAM_ID],
                "instructions": [
                    {
                        "programIdIndex": 1,
                        "accounts": [0],
                        "data": b58encode(bytes(8) + b"\x00"),
                    }
                ],
            },
        },
    }


def two_create_plan(*, base_slot: int = 500) -> tuple[tuple[FixtureOperation, ...], list[str]]:
    """Cold-start plan yielding two distinct finalized supported creates."""
    tx_a, mint_a = create_transaction("sigA", base_slot, 1_700_000_000)
    tx_b, mint_b = create_transaction("sigB", base_slot + 1, 1_700_000_060)
    operations = (
        page_op(
            "page-1",
            [
                signature_row("sigB", base_slot + 1),
                signature_row("sigA", base_slot),
            ],
        ),
        tx_op("tx-1", tx_a),
        tx_op("tx-2", tx_b),
    )
    return operations, [mint_a, mint_b]


class SignatureAnchoredAcquisitionTests(unittest.TestCase):
    """Phase 5 synthetic proofs for the primary acquisition owner."""

    def test_index_address_is_the_create_exclusive_mint_authority(self) -> None:
        # The architecture rests on this identity; it must equal the pinned
        # create account[1] enforced by the decoder.
        self.assertEqual(PUMP_CREATE_INDEX_ADDRESS, MINT_AUTHORITY_ID)

    def test_cold_start_two_distinct_finalized_creates(self) -> None:
        operations, mints = two_create_plan()
        result = run_acquisition_cycle(operations)

        self.assertEqual(len(result.observations), 2)
        self.assertEqual(
            sorted(obs.mint for obs in result.observations), sorted(mints)
        )
        self.assertEqual(len({obs.mint for obs in result.observations}), 2)
        # Cold start: the interval before this page was never observed.
        self.assertIs(result.cursor.continuity, ContinuityState.UNKNOWN)
        # ...but the boundary still advances, unlike the retired path.
        self.assertIsNotNone(result.cursor.boundary)
        self.assertEqual(result.cursor.boundary.signature, "sigB")
        self.assertEqual(result.anchor, CursorBoundary(501, "sigB"))

    def test_no_get_slot_operation_exists_in_the_primary_path(self) -> None:
        # RC-1: the cross-backend cutoff race is removed by construction.
        # getSlot is not an adopted operation, so it cannot be consumed.
        self.assertNotIn("getSlot", REQUEST_CEILINGS)
        with self.assertRaises(PumpContractError):
            run_acquisition_cycle(
                (
                    FixtureOperation(
                        request_id="slot-1",
                        request_kind=SIGNATURE_PAGE_REQUEST,
                        rpc_operation="getSlot",
                        response=434338676,
                    ),
                )
            )

    def test_post_cutoff_rejection_is_unreachable_from_the_primary_path(self) -> None:
        # Decode is anchored to the row's own slot, so slot > cutoff cannot
        # arise. This is the 4D/4H failure made structurally impossible.
        operations, _ = two_create_plan(base_slot=434_338_676 + 10_000)
        result = run_acquisition_cycle(operations)
        self.assertNotIn("POST_CUTOFF", [item.code for item in result.rejections])
        self.assertEqual(len(result.observations), 2)

    def test_finalized_row_newer_than_any_external_slot_is_still_admitted(self) -> None:
        # The exact 4D/4H failure: rows far ahead of a lagging backend's slot.
        operations, _ = two_create_plan(base_slot=999_999_999)
        result = run_acquisition_cycle(operations)
        self.assertEqual(len(result.observations), 2)
        self.assertEqual(
            [item.code for item in result.rejections if item.code == "POST_CUTOFF"], []
        )

    def test_restart_with_bounded_backfill_reaches_boundary(self) -> None:
        tx_a, _ = create_transaction("sigC", 610, 1_700_000_200)
        prior = FinalizedOriginCursor(
            CursorBoundary(600, "sigOld"), ContinuityState.CONTIGUOUS
        )
        # A full first page means more history exists; the walk continues older
        # with `before` until the stored boundary signature appears.
        full_page = [
            signature_row(f"s{i}", 640 - i, status="confirmed")
            for i in range(CREATE_INDEX_PAGE_SIZE)
        ]
        operations = (
            page_op("page-1", full_page),
            page_op("page-2", [signature_row("sigC", 610), signature_row("sigOld", 600)]),
            tx_op("tx-1", tx_a),
        )
        result = run_acquisition_cycle(operations, prior_cursor=prior)
        self.assertEqual(result.pages_used, 2)
        self.assertIs(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        self.assertEqual([obs.signature for obs in result.observations], ["sigC"])
        # Boundary advanced past the restart point.
        self.assertEqual(result.cursor.boundary, CursorBoundary(610, "sigC"))

    def test_boundary_not_found_within_page_ceiling_is_gapped(self) -> None:
        prior = FinalizedOriginCursor(
            CursorBoundary(1, "sigUnreachable"), ContinuityState.CONTIGUOUS
        )
        pages = tuple(
            page_op(
                f"page-{index}",
                [signature_row(f"s{index}-{i}", 900 - index * 20 - i, status="confirmed")
                 for i in range(CREATE_INDEX_PAGE_SIZE)],
            )
            for index in range(CREATE_INDEX_PAGE_CEILING)
        )
        result = run_acquisition_cycle(pages, prior_cursor=prior)
        self.assertEqual(result.pages_used, CREATE_INDEX_PAGE_CEILING)
        self.assertIs(result.cursor.continuity, ContinuityState.GAPPED)
        # Honest gap: never a fabricated CONTIGUOUS.
        self.assertNotEqual(result.cursor.continuity, ContinuityState.CONTIGUOUS)

    def test_short_page_without_boundary_is_gapped_not_contiguous(self) -> None:
        prior = FinalizedOriginCursor(
            CursorBoundary(1, "sigAgedOut"), ContinuityState.CONTIGUOUS
        )
        result = run_acquisition_cycle(
            (page_op("page-1", [signature_row("sigX", 800, status="confirmed")]),),
            prior_cursor=prior,
        )
        self.assertIs(result.cursor.continuity, ContinuityState.GAPPED)

    def test_duplicate_signatures_admitted_once(self) -> None:
        tx_a, _ = create_transaction("sigD", 700, 1_700_000_300)
        operations = (
            page_op(
                "page-1",
                [signature_row("sigD", 700), signature_row("sigD", 700)],
            ),
            tx_op("tx-1", tx_a),
        )
        result = run_acquisition_cycle(operations)
        self.assertEqual(result.duplicate_signatures, 1)
        self.assertEqual(result.admitted_rows, 1)
        self.assertEqual(len(result.observations), 1)

    def test_fork_conflicting_duplicate_is_dropped_and_gapped(self) -> None:
        prior = FinalizedOriginCursor(
            CursorBoundary(690, "sigPrev"), ContinuityState.CONTIGUOUS
        )
        operations = (
            page_op(
                "page-1",
                [
                    signature_row("sigE", 701),
                    signature_row("sigE", 702),
                    signature_row("sigPrev", 690),
                ],
            ),
        )
        result = run_acquisition_cycle(operations, prior_cursor=prior)
        codes = [item.code for item in result.rejections]
        self.assertIn("CONFLICTING_DUPLICATE", codes)
        self.assertIs(result.cursor.continuity, ContinuityState.GAPPED)
        self.assertNotIn("sigE", [obs.signature for obs in result.observations])

    def test_non_finalized_row_is_never_admitted(self) -> None:
        result = run_acquisition_cycle(
            (page_op("page-1", [signature_row("sigF", 710, status="confirmed")]),)
        )
        self.assertEqual(result.observations, ())
        self.assertIn("MISSING_FINALITY", [item.code for item in result.rejections])

    def test_failed_transaction_is_noise_not_a_continuity_fault(self) -> None:
        prior = FinalizedOriginCursor(
            CursorBoundary(700, "sigPrev"), ContinuityState.CONTIGUOUS
        )
        result = run_acquisition_cycle(
            (
                page_op(
                    "page-1",
                    [
                        signature_row("sigG", 711, err={"InstructionError": []}),
                        signature_row("sigPrev", 700),
                    ],
                ),
            ),
            prior_cursor=prior,
        )
        self.assertEqual(result.failed_signature_count, 1)
        self.assertIs(result.cursor.continuity, ContinuityState.CONTIGUOUS)
        # The boundary row itself is never re-decoded.
        self.assertEqual(result.decode_attempts, 0)

    def test_non_create_transaction_counted_without_fault(self) -> None:
        operations = (
            page_op("page-1", [signature_row("sigH", 720)]),
            tx_op("tx-1", non_create_transaction("sigH", 720, 1_700_000_400)),
        )
        result = run_acquisition_cycle(operations)
        self.assertEqual(result.non_create_count, 1)
        self.assertEqual(result.observations, ())

    def test_create_v2_is_blocked_and_counted(self) -> None:
        transaction, _ = create_transaction(
            "sigI", 730, 1_700_000_500, discriminator=CREATE_V2_DISCRIMINATOR
        )
        result = run_acquisition_cycle(
            (
                page_op("page-1", [signature_row("sigI", 730)]),
                tx_op("tx-1", transaction),
            )
        )
        self.assertEqual(result.observations, ())
        # V2-9.7E.6: create_v2 is now adopted. This fixture is a legacy-shaped
        # body carrying the create_v2 discriminator, which is fail-closed as
        # MALFORMED_TRANSACTION. Genuine create_v2 support is proven in
        # tests/test_v2_9_7e_6_pump_create_classification.py.
        self.assertIn("MALFORMED_TRANSACTION", [item.code for item in result.rejections])

    def test_empty_page_is_unavailable_history(self) -> None:
        result = run_acquisition_cycle((page_op("page-1", []),))
        self.assertIs(result.cursor.continuity, ContinuityState.UNAVAILABLE)
        self.assertEqual(result.observations, ())

    def test_stale_page_older_than_boundary_does_not_rewind_cursor(self) -> None:
        prior = FinalizedOriginCursor(
            CursorBoundary(900, "sigNewest"), ContinuityState.CONTIGUOUS
        )
        result = run_acquisition_cycle(
            (page_op("page-1", [signature_row("sigOlder", 800)]),),
            prior_cursor=prior,
        )
        self.assertTrue(result.stale_page)
        self.assertEqual(result.cursor.boundary, prior.boundary)

    def test_decode_ceiling_is_finite_and_reported(self) -> None:
        rows = [signature_row(f"sigJ{i}", 1000 + i) for i in range(CREATE_INDEX_PAGE_SIZE)]
        result = run_acquisition_cycle((page_op("page-1", rows),))
        over = [item for item in result.rejections if item.code == "DECODE_CEILING"]
        self.assertEqual(len(over), CREATE_INDEX_PAGE_SIZE - CREATE_INDEX_DECODE_CEILING)

    def test_deterministic_replay(self) -> None:
        operations, _ = two_create_plan()
        first = run_acquisition_cycle(operations)
        second = run_acquisition_cycle(operations)
        self.assertEqual(first.canonical(), second.canonical())

    def test_finite_request_and_operation_accounting(self) -> None:
        operations, _ = two_create_plan()
        result = run_acquisition_cycle(operations)
        self.assertEqual(result.accounting.underlying_rpc_operations, 3)
        self.assertEqual(
            dict(result.accounting.governed_requests),
            {SIGNATURE_PAGE_REQUEST: 1, TRANSACTION_REQUEST: 2},
        )
        # Worst case stays far under the unchanged 45-operation ceiling.
        self.assertLessEqual(
            CREATE_INDEX_PAGE_CEILING + CREATE_INDEX_DECODE_CEILING, 45
        )

    def test_governor_bypass_is_rejected(self) -> None:
        bad = FixtureOperation(
            request_id="page-1",
            request_kind="token_discovery",
            rpc_operation="getSignaturesForAddress",
            response={"rows": []},
        )
        with self.assertRaises(PumpContractError) as caught:
            run_acquisition_cycle((bad,))
        self.assertEqual(caught.exception.code, "SOURCE_GOVERNOR_BYPASS")

    def test_scheduler_bypass_is_rejected(self) -> None:
        bad = FixtureOperation(
            request_id="page-1",
            request_kind=SIGNATURE_PAGE_REQUEST,
            rpc_operation="getSignaturesForAddress",
            response={"rows": []},
            scheduler_work_type="UNOWNED_WORK",
        )
        with self.assertRaises(PumpContractError) as caught:
            run_acquisition_cycle((bad,))
        self.assertEqual(caught.exception.code, "CENTRAL_SCHEDULER_BYPASS")

    def test_adopted_request_kinds_are_governor_allowed(self) -> None:
        for kind in (SIGNATURE_PAGE_REQUEST, TRANSACTION_REQUEST):
            self.assertTrue(can_request_source("solana_rpc", kind, 0).allowed)

    def test_unplanned_operation_is_rejected(self) -> None:
        operations, _ = two_create_plan()
        with self.assertRaises(PumpContractError) as caught:
            run_acquisition_cycle(operations + (tx_op("tx-extra", {}),))
        self.assertEqual(caught.exception.code, "UNPLANNED_OPERATION")

    def test_no_transport_subscription_or_loop_surface_exists(self) -> None:
        # Structural, not textual: the module must contain no networking
        # import, no unbounded loop, and no sleep.
        tree = ast.parse(
            Path(
                inspect.getsourcefile(run_acquisition_cycle)  # type: ignore[arg-type]
            ).read_text(encoding="utf-8")
        )
        banned_modules = {
            "requests",
            "urllib",
            "http",
            "socket",
            "asyncio",
            "websockets",
            "websocket",
            "time",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], banned_modules)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".")[0], banned_modules)
            elif isinstance(node, ast.While):
                # Every loop must be bounded by a real condition, never `True`.
                self.assertNotIsInstance(node.test, ast.Constant)

    def test_only_two_rpc_operations_are_adopted(self) -> None:
        self.assertEqual(
            set(REQUEST_CEILINGS), {SIGNATURE_PAGE_REQUEST, TRANSACTION_REQUEST}
        )


class DurableOriginRegistryTests(unittest.TestCase):
    """Phase 5 proofs for durable prospective origin persistence."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.db_path = Path(self._dir.name) / "registry.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.addCleanup(self.connection.close)

    def _observation(self, signature: str = "sigA", slot: int = 500) -> PumpCreateObservation:
        _, mint = create_transaction(signature, slot, 1_700_000_000)
        return PumpCreateObservation(
            mint=mint,
            bonding_curve="curve",
            associated_bonding_curve="ata",
            creator_address="creator",
            signature=signature,
            slot=slot,
            block_time=1_700_000_000,
        )

    def test_confirmed_origin_persists_and_is_readable_by_exact_mint(self) -> None:
        observation = self._observation()
        self.assertTrue(
            record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        )
        found = lookup_confirmed_origin(self.connection, observation.mint)
        self.assertIsNotNone(found)
        self.assertEqual(found["transaction_signature"], "sigA")
        self.assertEqual(found["slot"], 500)
        self.assertEqual(found["program_id"], PUMP_PROGRAM_ID)
        self.assertEqual(found["acquisition_mode"], ACQUISITION_MODE_PROSPECTIVE)

    def test_registry_survives_a_new_connection(self) -> None:
        # The whole point of RC-3: origins outlive the cycle that found them.
        observation = self._observation()
        record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        self.connection.commit()
        other = sqlite3.connect(self.db_path)
        other.row_factory = sqlite3.Row
        self.addCleanup(other.close)
        self.assertIsNotNone(lookup_confirmed_origin(other, observation.mint))

    def test_registry_miss_returns_none_without_any_rpc(self) -> None:
        self.assertIsNone(lookup_confirmed_origin(self.connection, "unknown-mint"))

    def test_mint_mismatch_lookup_returns_none(self) -> None:
        observation = self._observation()
        record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        self.assertIsNone(
            lookup_confirmed_origin(self.connection, observation.mint + "x")
        )

    def test_identical_reconfirmation_is_idempotent(self) -> None:
        observation = self._observation()
        self.assertTrue(
            record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        )
        self.assertFalse(
            record_confirmed_origin(self.connection, observation, now="2026-07-21T01:00:00Z")
        )

    def test_conflicting_origin_is_fail_closed(self) -> None:
        observation = self._observation()
        record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        conflicting = PumpCreateObservation(
            mint=observation.mint,
            bonding_curve="curve",
            associated_bonding_curve="ata",
            creator_address="creator",
            signature="sigDIFFERENT",
            slot=999,
            block_time=1_700_000_000,
        )
        with self.assertRaises(OriginRegistryError) as caught:
            record_confirmed_origin(self.connection, conflicting, now="2026-07-21T02:00:00Z")
        self.assertEqual(caught.exception.code, "ORIGIN_REGISTRY_CONFLICT")

    def test_confirmed_rows_are_immutable(self) -> None:
        observation = self._observation()
        record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE printer_pumpfun_finalized_origin_registry SET slot = 1"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "DELETE FROM printer_pumpfun_finalized_origin_registry"
            )

    def test_registry_stores_no_raw_payload(self) -> None:
        observation = self._observation()
        record_confirmed_origin(self.connection, observation, now="2026-07-21T00:00:00Z")
        row = dict(
            self.connection.execute(
                "SELECT * FROM printer_pumpfun_finalized_origin_registry"
            ).fetchone()
        )
        self.assertEqual(len(row["evidence_hash"]), 64)
        for value in row.values():
            self.assertNotIn("accountKeys", str(value))
            self.assertNotIn("private_key", str(value))

    def test_cursor_round_trip_and_cold_start(self) -> None:
        self.assertEqual(
            load_origin_cursor(self.connection),
            FinalizedOriginCursor(None, ContinuityState.UNKNOWN, PUMP_CREATE_INDEX_ADDRESS),
        )
        cursor = FinalizedOriginCursor(
            CursorBoundary(900, "sigNewest"), ContinuityState.CONTIGUOUS
        )
        save_origin_cursor(self.connection, cursor, now="2026-07-21T00:00:00Z")
        self.assertEqual(load_origin_cursor(self.connection), cursor)
        # Cursor is mutable state; only the registry is immutable.
        save_origin_cursor(
            self.connection,
            FinalizedOriginCursor(CursorBoundary(950, "sigNewer"), ContinuityState.GAPPED),
            now="2026-07-21T01:00:00Z",
        )
        self.assertIs(
            load_origin_cursor(self.connection).continuity, ContinuityState.GAPPED
        )

    def test_acquisition_to_registry_to_later_cycle_lookup(self) -> None:
        # End-to-end: prospective capture now, exact-mint verification later,
        # with no historical rediscovery in between.
        operations, mints = two_create_plan()
        result = run_acquisition_cycle(operations)
        for observation in result.observations:
            record_confirmed_origin(
                self.connection, observation, now="2026-07-21T00:00:00Z"
            )
        save_origin_cursor(self.connection, result.cursor, now="2026-07-21T00:00:00Z")
        self.connection.commit()

        for mint in mints:
            found = lookup_confirmed_origin(self.connection, mint)
            self.assertIsNotNone(found)
            self.assertEqual(found["program_id"], PUMP_PROGRAM_ID)


class RetiredPrimaryPathTests(unittest.TestCase):
    """Phase 5 proofs that the failed primary path cannot reactivate."""

    def test_combined_executor_does_not_import_retired_owners(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "printer_v1"
            / "discovery"
            / "combined_executor.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("run_fixture_cycle", source)
        self.assertNotIn("run_mint_origin_lookup", source)
        self.assertIn("run_acquisition_cycle", source)

    def test_retired_cycle_rejects_primary_claim(self) -> None:
        with self.assertRaises(DirectRetiredPrimaryPathError):
            run_fixture_cycle((), prior_cursor=None, primary_path=True)

    def test_retired_mint_lookup_rejects_primary_claim(self) -> None:
        with self.assertRaises(DirectRetiredPrimaryPathError):
            run_mint_origin_lookup(
                (), expected_mint="m", cutoff_slot=1, primary_path=True
            )

    def test_historical_lookup_requires_explicit_support_only_opt_in(self) -> None:
        with self.assertRaises(DirectRetiredPrimaryPathError):
            run_mint_origin_lookup(
                (),
                expected_mint="m",
                cutoff_slot=1,
                allow_support_only_history=False,
            )

    def test_no_logs_subscription_in_the_primary_owner(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "printer_v1"
            / "sources"
            / "pumpfun_origin.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("SESSION_REQUEST", source)


if __name__ == "__main__":
    unittest.main()
