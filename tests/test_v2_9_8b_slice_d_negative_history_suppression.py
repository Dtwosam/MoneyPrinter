"""V2-9.8B Slice D: exact-pair negative-history source suppression proofs.

Durable no-match history for one exact ``network + mint + pool`` identity must
deterministically control when another exact-pair market-source request is
lawful, and a trustworthy response proving the historical exact pool absent must
retire stale current ``LIQUIDITY_PROVEN`` truth.

Disposable SQLite and fixture transports only. No network, no provider contact,
no operational campaign, no authorization, retrieval, decision, position, trade,
audit or PnL surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH,
    LIQUIDITY_NO_EXACT_PAIR,
    LIQUIDITY_PROVEN,
    LIQUIDITY_UNPROVEN,
    SELECTION_FLOOR_USD,
    load_market_floor_state,
)
from printer_v1.discovery.permanent_discovery_availability import (
    BELOW_LIQUIDITY_FLOOR,
    CURRENT_POOL_CONFIRMED,
    CURRENT_VISIBLE,
    EXACT_POOL_NO_MATCH,
    EXACT_POOL_POLL_BACKOFF_ACTIVE,
    EXACT_POOL_POLL_HISTORY_INCOMPLETE,
    EXACT_POOL_POLL_NOT_NO_MATCH,
    EXACT_POOL_POLL_RECONCILIATION_DUE,
    NEW_POOL_PENDING_PROOF,
    SOURCE_UNAVAILABLE,
    ExactMarketObservation,
    decide_exact_pool_poll,
    exact_pool_no_match_backoff_seconds,
    load_exact_market_states,
    record_exact_market_transition,
    run_dexscreener_batch_market_resolution,
    should_poll_exact_pool,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    PUMPSWAP_AMM_PROGRAM_ID,
    PUMPSWAP_VENUE,
    record_graduated_candidate,
)


NETWORK = "solana-mainnet"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
POOL_PROGRAM = PUMPSWAP_AMM_PROGRAM_ID
WSOL = "So11111111111111111111111111111111111111112"
CONTRACT_VERSION = "DEXSCREENER_TOKENS_V1_2026_08_04"

T10 = "2026-08-17T10:00:00+00:00"
T11 = "2026-08-17T11:00:00+00:00"
T12 = "2026-08-17T12:00:00+00:00"


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _shift(value: str, seconds: int) -> str:
    return (_iso(value) + timedelta(seconds=seconds)).isoformat()


@pytest.fixture
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "slice-d.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _seed_inventory(connection, count: int = 1, *, start: int = 0):
    """Register graduated candidates and return canonical inventory rows."""
    rows = []
    for index in range(start, start + count):
        mint = f"Mint{index:02d}"
        pool = f"Pool{index:02d}"
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=f"Signature{index:02d}",
            pumpswap_pool=pool,
            graduation_block_time=1_700_000_000 + index,
            graduation_slot=index,
            now=T10,
        )
        rows.append(
            {
                "mint_identity": mint,
                "pumpswap_pool": pool,
                "market_identity": f"{NETWORK}:{PUMPSWAP_VENUE}:{pool}",
                "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
                "graduation_block_time": 1_700_000_000 + index,
                "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
                "latest_channel": "PERSISTED_GRADUATED",
            }
        )
    connection.commit()
    return rows


def _seed_exact_state(
    connection,
    *,
    mint: str,
    pool: str,
    state: str = EXACT_POOL_NO_MATCH,
    reason: str = "LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
    no_match_count: int = 0,
    no_match_streak: int = 0,
    last_no_match_at: str | None = None,
    next_lawful_action_at: str | None = None,
    observed_at: str = T10,
) -> None:
    """Write one durable exact projection row verbatim.

    Raw insertion is deliberate: these proofs must pin legacy/hand-written
    history (including old flat 30-minute boundaries) that the write path would
    otherwise recalculate.
    """
    connection.execute(
        """INSERT INTO printer_exact_market_states(
            network,mint_identity,pool_address,token_program_id,pool_program_id,
            base_mint,quote_mint,venue,current_state,current_reason,
            last_observed_at,last_visible_at,last_no_match_at,no_match_count,
            no_match_streak,next_lawful_action_at,latest_source_provenance_json,
            contract_version,created_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            NETWORK,
            mint,
            pool,
            TOKEN_PROGRAM,
            POOL_PROGRAM,
            mint,
            WSOL,
            PUMPSWAP_VENUE,
            state,
            reason,
            observed_at,
            None,
            last_no_match_at,
            no_match_count,
            no_match_streak,
            next_lawful_action_at,
            '{"source":"seeded_history"}',
            CONTRACT_VERSION,
            observed_at,
            observed_at,
        ),
    )
    connection.commit()


def _exact_row(connection, mint: str, pool: str) -> dict:
    row = connection.execute(
        """SELECT * FROM printer_exact_market_states
           WHERE network=? AND mint_identity=? AND pool_address=?""",
        (NETWORK, mint, pool),
    ).fetchone()
    assert row is not None
    return dict(row)


def _pair(mint: str, pool: str, liquidity: float) -> dict:
    return {
        "chainId": "solana",
        "pairAddress": pool,
        "dexId": "pumpswap",
        "baseToken": {"address": mint},
        "quoteToken": {"address": WSOL},
        "liquidity": {"usd": liquidity},
    }


class _CountingTransport:
    """Fixture transport that proves whether any source call was made."""

    def __init__(self, payload=None):
        self.call_count = 0
        self.payloads = []
        self._payload = payload if payload is not None else {"pairs": []}

    def __call__(self, context):
        self.call_count += 1
        self.payloads.append(dict(context.request.payload))
        return dict(self._payload)


def _source_request_count(connection) -> int:
    return int(
        connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
    )


def _observation(
    *,
    mint: str,
    pool: str,
    state: str,
    reason: str,
    observed_at: str,
    next_lawful_action_at: str | None = None,
) -> ExactMarketObservation:
    return ExactMarketObservation(
        network=NETWORK,
        mint=mint,
        pool=pool,
        token_program=TOKEN_PROGRAM,
        pool_program=POOL_PROGRAM,
        base_mint=mint,
        quote_mint=WSOL,
        venue=PUMPSWAP_VENUE,
        state=state,
        reason=reason,
        observed_at=observed_at,
        next_lawful_action_at=next_lawful_action_at,
        source_provenance={"source": "dexscreener", "request_id": 1},
        contract_version=CONTRACT_VERSION,
    )


# ---------------------------------------------------------------------------
# TEST 1 — backoff function
# ---------------------------------------------------------------------------


class TestBackoffFunction:
    def test_categorical_streak_mapping_caps_at_twenty_four_hours(self):
        assert exact_pool_no_match_backoff_seconds(1) == 1_800
        assert exact_pool_no_match_backoff_seconds(2) == 7_200
        assert exact_pool_no_match_backoff_seconds(3) == 14_400
        assert exact_pool_no_match_backoff_seconds(4) == 28_800
        assert exact_pool_no_match_backoff_seconds(5) == 57_600
        assert exact_pool_no_match_backoff_seconds(6) == 86_400
        assert exact_pool_no_match_backoff_seconds(7) == 86_400
        assert exact_pool_no_match_backoff_seconds(20) == 86_400

    @pytest.mark.parametrize("invalid", [0, -1, True, 1.0, "2"])
    def test_invalid_history_raises_instead_of_creating_suppression(self, invalid):
        with pytest.raises(ValueError):
            exact_pool_no_match_backoff_seconds(invalid)


# ---------------------------------------------------------------------------
# TESTS 2-6 — decision law
# ---------------------------------------------------------------------------


class TestExactPoolPollDecision:
    def test_streak_two_suppresses_for_exactly_two_hours(self):
        decision = decide_exact_pool_poll(
            {
                "current_state": EXACT_POOL_NO_MATCH,
                "no_match_streak": 2,
                "last_no_match_at": T10,
                "next_lawful_action_at": None,
            },
            at=T11,
        )
        assert decision.should_poll is False
        assert decision.reason == EXACT_POOL_POLL_BACKOFF_ACTIVE
        assert decision.no_match_streak == 2
        assert _iso(decision.effective_next_lawful_action_at) == _iso(T12)

    def test_boundary_is_exact_with_no_off_by_one_delay(self):
        state = {
            "current_state": EXACT_POOL_NO_MATCH,
            "no_match_streak": 2,
            "last_no_match_at": T10,
            "next_lawful_action_at": None,
        }
        before = decide_exact_pool_poll(state, at="2026-08-17T11:59:59+00:00")
        assert before.should_poll is False
        assert before.reason == EXACT_POOL_POLL_BACKOFF_ACTIVE

        at_boundary = decide_exact_pool_poll(state, at=T12)
        assert at_boundary.should_poll is True
        assert at_boundary.reason == EXACT_POOL_POLL_RECONCILIATION_DUE

    def test_legacy_thirty_minute_row_is_governed_by_derived_history(self, database):
        """An old flat +30m boundary with streak 4 must still suppress at +2h."""
        _, connection = database
        _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=4,
            no_match_streak=4,
            last_no_match_at=T10,
            next_lawful_action_at="2026-08-17T10:30:00+00:00",
        )
        row = _exact_row(connection, "Mint00", "Pool00")
        # No migration ran; the legacy column value is untouched on disk.
        assert row["next_lawful_action_at"] == "2026-08-17T10:30:00+00:00"

        decision = decide_exact_pool_poll(row, at=T12)
        assert decision.should_poll is False
        assert decision.reason == EXACT_POOL_POLL_BACKOFF_ACTIVE
        assert _iso(decision.effective_next_lawful_action_at) == _iso(
            "2026-08-17T18:00:00+00:00"
        )
        assert should_poll_exact_pool(row, at=T12) is False

    def test_existing_stronger_boundary_is_never_shortened(self):
        decision = decide_exact_pool_poll(
            {
                "current_state": EXACT_POOL_NO_MATCH,
                "no_match_streak": 2,
                "last_no_match_at": T10,
                "next_lawful_action_at": "2026-08-17T13:00:00+00:00",
            },
            at=T12,
        )
        assert decision.should_poll is False
        assert decision.reason == EXACT_POOL_POLL_BACKOFF_ACTIVE
        assert _iso(decision.effective_next_lawful_action_at) == _iso(
            "2026-08-17T13:00:00+00:00"
        )

    @pytest.mark.parametrize(
        "state",
        [
            {"no_match_streak": 3, "last_no_match_at": None},
            {"no_match_streak": 3, "last_no_match_at": ""},
            {"no_match_streak": 3, "last_no_match_at": "not-a-timestamp"},
            {"no_match_streak": 0, "last_no_match_at": T10},
            {"no_match_streak": None, "last_no_match_at": T10},
            {"no_match_streak": "many", "last_no_match_at": T10},
        ],
    )
    def test_incomplete_history_never_invents_suppression(self, state):
        decision = decide_exact_pool_poll(
            {
                "current_state": EXACT_POOL_NO_MATCH,
                "next_lawful_action_at": None,
                **state,
            },
            at=T11,
        )
        assert decision.should_poll is True
        assert decision.reason == EXACT_POOL_POLL_HISTORY_INCOMPLETE

    def test_malformed_existing_boundary_is_not_trusted(self):
        decision = decide_exact_pool_poll(
            {
                "current_state": EXACT_POOL_NO_MATCH,
                "no_match_streak": 1,
                "last_no_match_at": T10,
                "next_lawful_action_at": "garbage",
            },
            at="2026-08-17T10:45:00+00:00",
        )
        assert decision.should_poll is True
        assert decision.reason == EXACT_POOL_POLL_RECONCILIATION_DUE
        assert _iso(decision.effective_next_lawful_action_at) == _iso(
            "2026-08-17T10:30:00+00:00"
        )

    @pytest.mark.parametrize(
        "state", [CURRENT_VISIBLE, BELOW_LIQUIDITY_FLOOR, CURRENT_POOL_CONFIRMED]
    )
    def test_negative_history_never_applies_to_other_states(self, state):
        decision = decide_exact_pool_poll(
            {
                "current_state": state,
                "no_match_streak": 6,
                "last_no_match_at": T10,
                "next_lawful_action_at": "2026-08-18T10:00:00+00:00",
            },
            at=T11,
        )
        assert decision.should_poll is True
        assert decision.reason == EXACT_POOL_POLL_NOT_NO_MATCH


# ---------------------------------------------------------------------------
# TESTS 7-9 — write path owns the derived boundary
# ---------------------------------------------------------------------------


class TestExactMarketWritePath:
    def test_first_no_match_stores_thirty_minute_boundary(self, database):
        _, connection = database
        _seed_inventory(connection, 1)
        record_exact_market_transition(
            connection,
            _observation(
                mint="Mint00",
                pool="Pool00",
                state=EXACT_POOL_NO_MATCH,
                reason="LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                observed_at=T10,
            ),
            now=T10,
        )
        connection.commit()
        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["no_match_count"] == 1
        assert row["no_match_streak"] == 1
        assert row["last_no_match_at"] == T10
        assert _iso(row["next_lawful_action_at"]) == _iso(_shift(T10, 1_800))

    def test_second_no_match_stores_two_hour_boundary_not_thirty_minutes(
        self, database
    ):
        _, connection = database
        _seed_inventory(connection, 1)
        record_exact_market_transition(
            connection,
            _observation(
                mint="Mint00",
                pool="Pool00",
                state=EXACT_POOL_NO_MATCH,
                reason="LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                observed_at=T10,
            ),
            now=T10,
        )
        second_at = "2026-08-17T10:40:00+00:00"
        record_exact_market_transition(
            connection,
            _observation(
                mint="Mint00",
                pool="Pool00",
                state=EXACT_POOL_NO_MATCH,
                reason="LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                observed_at=second_at,
                # A caller supplying the old flat 30-minute boundary can no
                # longer shorten the derived streak boundary.
                next_lawful_action_at=_shift(second_at, 1_800),
            ),
            now=second_at,
        )
        connection.commit()
        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["no_match_count"] == 2
        assert row["no_match_streak"] == 2
        assert row["last_no_match_at"] == second_at
        assert _iso(row["next_lawful_action_at"]) == _iso(_shift(second_at, 7_200))
        assert _iso(row["next_lawful_action_at"]) != _iso(_shift(second_at, 1_800))

    def test_streak_six_and_seven_cap_at_twenty_four_hours(self, database):
        _, connection = database
        _seed_inventory(connection, 1)
        observed = T10
        for streak in range(1, 8):
            record_exact_market_transition(
                connection,
                _observation(
                    mint="Mint00",
                    pool="Pool00",
                    state=EXACT_POOL_NO_MATCH,
                    reason="LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                    observed_at=observed,
                ),
                now=observed,
            )
            connection.commit()
            row = _exact_row(connection, "Mint00", "Pool00")
            assert row["no_match_streak"] == streak
            expected = exact_pool_no_match_backoff_seconds(streak)
            assert _iso(row["next_lawful_action_at"]) == _iso(_shift(observed, expected))
            if streak >= 6:
                assert expected == 86_400
            observed = _shift(observed, expected + 60)
        assert _exact_row(connection, "Mint00", "Pool00")["no_match_count"] == 7

    def test_caller_may_only_make_the_boundary_stricter(self, database):
        _, connection = database
        _seed_inventory(connection, 1)
        stricter = _shift(T10, 200_000)
        record_exact_market_transition(
            connection,
            _observation(
                mint="Mint00",
                pool="Pool00",
                state=EXACT_POOL_NO_MATCH,
                reason="LAWFUL_BATCH_EXACT_POOL_NO_MATCH",
                observed_at=T10,
                next_lawful_action_at=stricter,
            ),
            now=T10,
        )
        connection.commit()
        row = _exact_row(connection, "Mint00", "Pool00")
        assert _iso(row["next_lawful_action_at"]) == _iso(stricter)

    def test_reappearance_resets_streak_but_preserves_historical_count(
        self, database
    ):
        _, connection = database
        _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=4,
            no_match_streak=4,
            last_no_match_at=T10,
            next_lawful_action_at=_shift(T10, 28_800),
        )
        record_exact_market_transition(
            connection,
            _observation(
                mint="Mint00",
                pool="Pool00",
                state=CURRENT_POOL_CONFIRMED,
                reason="AT_OR_ABOVE_3000_FLOOR",
                observed_at=T12,
            ),
            now=T12,
        )
        connection.commit()
        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["no_match_streak"] == 0
        assert row["no_match_count"] == 4


# ---------------------------------------------------------------------------
# TESTS 10, 18 — all suppressed means zero source work
# ---------------------------------------------------------------------------


class TestAllSuppressedZeroSource:
    def test_thirty_suppressed_rows_create_no_source_work(self, database):
        _, connection = database
        inventory = _seed_inventory(connection, 30)
        for row in inventory:
            _seed_exact_state(
                connection,
                mint=row["mint_identity"],
                pool=row["pumpswap_pool"],
                no_match_count=3,
                no_match_streak=3,
                last_no_match_at=T10,
            )
        before_requests = _source_request_count(connection)
        before_responses = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_source_responses"
            ).fetchone()[0]
        )
        before_failures = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_source_failures"
            ).fetchone()[0]
        )
        transport = _CountingTransport()

        # Streak 3 buys four hours; two hours later every identity is suppressed.
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="slice-d-all-suppressed",
            now=T12,
            campaign_id="campaign-d",
        )

        assert transport.call_count == 0
        assert report["source_request_ids"] == []
        assert report["source_response_ids"] == []
        assert report["source_failure_ids"] == []
        assert report["batch_sizes"] == []
        assert report["provider_failures"] == 0
        assert report["negative_history_suppressed_count"] == 30
        assert len(report["negative_history_suppressed"]) == 30
        assert report["source_request_coverage"] == []
        assert report["calls_by_stage"] == {
            "market_batching": 0,
            "reconciliation": 0,
        }

        connection.commit()
        assert _source_request_count(connection) - before_requests == 0
        assert (
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_responses"
                ).fetchone()[0]
            )
            - before_responses
            == 0
        )
        assert (
            int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_source_failures"
                ).fetchone()[0]
            )
            - before_failures
            == 0
        )

        record = report["negative_history_suppressed"][0]
        assert set(record) == {
            "mint",
            "pool",
            "no_match_streak",
            "last_no_match_at",
            "effective_next_lawful_action_at",
            "reason",
        }
        assert record["reason"] == EXACT_POOL_POLL_BACKOFF_ACTIVE
        assert record["no_match_streak"] == 3
        assert record["last_no_match_at"] == T10
        assert _iso(record["effective_next_lawful_action_at"]) == _iso(
            _shift(T10, 14_400)
        )

    def test_suppressed_rows_are_not_transitioned(self, database):
        _, connection = database
        inventory = _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=3,
            no_match_streak=3,
            last_no_match_at=T10,
        )
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=_CountingTransport(),
            request_key="slice-d-no-transition",
            now=T11,
            campaign_id="campaign-d",
        )
        assert report["state_transition_ids"] == []
        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["current_state"] == EXACT_POOL_NO_MATCH
        assert row["no_match_streak"] == 3


# ---------------------------------------------------------------------------
# TEST 11 — mixed batch payload carries only due mints
# ---------------------------------------------------------------------------


class TestMixedBatch:
    def test_twenty_four_suppressed_six_due_builds_one_six_mint_request(
        self, database
    ):
        _, connection = database
        inventory = _seed_inventory(connection, 30)
        suppressed_rows = inventory[:24]
        due_rows = inventory[24:]
        for row in suppressed_rows:
            _seed_exact_state(
                connection,
                mint=row["mint_identity"],
                pool=row["pumpswap_pool"],
                no_match_count=3,
                no_match_streak=3,
                last_no_match_at=T10,
            )
        transport = _CountingTransport(
            {
                "pairs": [
                    _pair(row["mint_identity"], row["pumpswap_pool"], 4_000.0)
                    for row in due_rows
                ]
            }
        )

        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="slice-d-mixed",
            now=T12,
            campaign_id="campaign-d",
        )

        assert transport.call_count == 1
        assert report["negative_history_suppressed_count"] == 24
        assert report["batch_sizes"] == [6]
        assert len(report["source_request_ids"]) == 1

        token_mints = transport.payloads[0]["token_mints"]
        due_mints = {row["mint_identity"] for row in due_rows}
        suppressed_mints = {row["mint_identity"] for row in suppressed_rows}
        assert len(token_mints) == 6
        assert set(token_mints) == due_mints
        assert not (set(token_mints) & suppressed_mints)

        covered = {
            entry["source_request_id"] for entry in report["source_request_coverage"]
        }
        assert covered == set(report["source_request_ids"])
        assert report["source_request_coverage"][0]["normalized_member_count"] == 6

        # No suppressed identity produced any durable source request row.
        keys = {
            str(row[0])
            for row in connection.execute(
                "SELECT request_key FROM printer_source_requests"
            )
        }
        assert all(not any(mint in key for mint in suppressed_mints) for key in keys)


# ---------------------------------------------------------------------------
# TESTS 12, 13, 14 — response truth vs source failure
# ---------------------------------------------------------------------------


class TestValidResponseExactPoolAbsent:
    def test_absent_exact_pool_increments_streak_and_derives_four_hour_boundary(
        self, database
    ):
        _, connection = database
        inventory = _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=2,
            no_match_streak=2,
            last_no_match_at=T10,
            next_lawful_action_at=_shift(T10, 7_200),
        )
        # Boundary expired: a lawful recheck runs and the response is complete
        # for the mint but returns a different pool only.
        transport = _CountingTransport(
            {"pairs": [_pair("Mint00", "OtherPool00", 9_000.0)]}
        )

        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="slice-d-absent",
            now=T12,
            campaign_id="campaign-d",
        )

        assert transport.call_count == 1
        assert report["provider_failures"] == 0
        assert report["negative_history_suppressed_count"] == 0

        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["current_state"] == EXACT_POOL_NO_MATCH
        assert row["no_match_streak"] == 3
        assert row["no_match_count"] == 3
        assert row["last_no_match_at"] == T12
        assert _iso(row["next_lawful_action_at"]) == _iso(_shift(T12, 14_400))

    def test_alternate_pool_never_substitutes_the_historical_exact_pool(
        self, database
    ):
        _, connection = database
        inventory = _seed_inventory(connection, 1)
        transport = _CountingTransport(
            {"pairs": [_pair("Mint00", "OtherPool00", 9_000.0)]}
        )
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="slice-d-substitution",
            now=T12,
            campaign_id="campaign-d",
        )

        historical = _exact_row(connection, "Mint00", "Pool00")
        assert historical["current_state"] == EXACT_POOL_NO_MATCH
        assert historical["pool_address"] == "Pool00"

        alternate = _exact_row(connection, "Mint00", "OtherPool00")
        assert alternate["current_state"] == NEW_POOL_PENDING_PROOF

        candidates = [c for c in report["candidates"] if c["mint"] == "Mint00"]
        assert len(candidates) == 1
        assert candidates[0]["pool"] == "Pool00"
        assert candidates[0]["eligible"] is False
        assert candidates[0]["rejection"] == LIQUIDITY_UNPROVEN

    def test_absent_exact_pool_retires_stale_liquidity_proven(self, database):
        """A valid absence replaces stale current LIQUIDITY_PROVEN.

        Blocker noted for audit: ``printer_graduated_market_floor_state``
        constrains ``liquidity_status`` to the three adopted admission values
        (migration 043), so ``LIQUIDITY_NO_EXACT_PAIR`` is carried as the
        durable categorical *reason* on the current evidence while the stored
        status becomes ``LIQUIDITY_UNPROVEN``. Making it a fourth stored status
        would require a schema migration, which Slice D forbids. Crucially the
        stale ``LIQUIDITY_PROVEN``/5000 truth is gone and liquidity is NULL,
        never 0.
        """
        _, connection = database
        inventory = _seed_inventory(connection, 1)
        connection.execute(
            """INSERT INTO printer_graduated_market_floor_state(
                mint_identity, pumpswap_pool, liquidity_status, liquidity_usd,
                last_checked_at, cooldown_until, updated_at
            ) VALUES (?,?,?,?,?,?,?)""",
            ("Mint00", "Pool00", LIQUIDITY_PROVEN, 5_000.0, T10, None, T10),
        )
        connection.commit()

        before = load_market_floor_state(connection, "Mint00")
        assert before["liquidity_status"] == LIQUIDITY_PROVEN
        assert before["liquidity_usd"] == 5_000.0

        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=_CountingTransport(
                {"pairs": [_pair("Mint00", "OtherPool00", 9_000.0)]}
            ),
            request_key="slice-d-stale-liquidity",
            now=T12,
            campaign_id="campaign-d",
        )
        connection.commit()

        assert _exact_row(connection, "Mint00", "Pool00")["current_state"] == (
            EXACT_POOL_NO_MATCH
        )

        after = load_market_floor_state(connection, "Mint00")
        assert after["liquidity_status"] != LIQUIDITY_PROVEN
        assert after["liquidity_status"] == LIQUIDITY_UNPROVEN
        assert after["liquidity_usd"] is None
        assert after["liquidity_usd"] != 0
        assert after["cooldown_until"] is None
        assert after["last_checked_at"] == T12

        evidence = report["candidates"][0]["liquidity"]
        assert evidence["reason"] == LIQUIDITY_NO_EXACT_PAIR
        assert evidence["outcome_category"] == (
            LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH
        )
        assert evidence["liquidity_usd"] is None

        # The old measured evidence stays historically inspectable.
        history = connection.execute(
            """SELECT COUNT(*) FROM printer_exact_market_state_transitions
               WHERE mint_identity=? AND pool_address=?""",
            ("Mint00", "Pool00"),
        ).fetchone()[0]
        assert history >= 1

    def test_provider_failure_never_becomes_a_no_match(self, database):
        _, connection = database
        inventory = _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=2,
            no_match_streak=2,
            last_no_match_at=T10,
            next_lawful_action_at=_shift(T10, 7_200),
        )

        def broken(_context):
            raise RuntimeError("offline")

        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=broken,
            request_key="slice-d-source-failure",
            now=T12,
            campaign_id="campaign-d",
        )
        connection.commit()

        assert report["provider_failures"] == 1
        assert report["reconciliation_due_count"] == 0

        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["current_state"] == SOURCE_UNAVAILABLE
        assert row["no_match_streak"] == 2
        assert row["no_match_count"] == 2
        assert row["last_no_match_at"] == T10

        new_no_match = connection.execute(
            """SELECT COUNT(*) FROM printer_exact_market_state_transitions
               WHERE mint_identity=? AND pool_address=? AND new_state=?""",
            ("Mint00", "Pool00", EXACT_POOL_NO_MATCH),
        ).fetchone()[0]
        assert new_no_match == 0

        # Existing F source-failure semantics are preserved.
        assert len(report["source_failure_ids"]) == 1
        assert report["source_request_coverage"][0]["terminal_status"] == "BLOCKED"

        # Current liquidity truth is not rewritten by a source failure.
        assert load_market_floor_state(connection, "Mint00") is None


# ---------------------------------------------------------------------------
# TESTS 15, 16, 17 — reappearance and exact identity scope
# ---------------------------------------------------------------------------


class TestReappearance:
    def _seeded_streak_four(self, connection):
        inventory = _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=4,
            no_match_streak=4,
            last_no_match_at=T10,
            next_lawful_action_at=_shift(T10, 28_800),
        )
        return inventory

    def test_exact_pool_reappears_above_floor(self, database):
        _, connection = database
        inventory = self._seeded_streak_four(connection)
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=_CountingTransport(
                {"pairs": [_pair("Mint00", "Pool00", 4_500.0)]}
            ),
            # Streak 4 expires at 18:00; recheck at 19:00.
            now="2026-08-17T19:00:00+00:00",
            request_key="slice-d-reappear-above",
            campaign_id="campaign-d",
        )
        connection.commit()

        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["current_state"] == CURRENT_POOL_CONFIRMED
        assert row["no_match_streak"] == 0
        assert row["no_match_count"] == 4

        candidate = report["candidates"][0]
        assert candidate["liquidity"]["status"] == LIQUIDITY_PROVEN
        assert candidate["liquidity"]["liquidity_usd"] == 4_500.0
        assert candidate["eligible"] is True

        floor = load_market_floor_state(connection, "Mint00")
        assert floor["liquidity_status"] == LIQUIDITY_PROVEN
        assert floor["liquidity_usd"] == 4_500.0

    def test_exact_pool_reappears_below_floor(self, database):
        _, connection = database
        inventory = self._seeded_streak_four(connection)
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=_CountingTransport(
                {"pairs": [_pair("Mint00", "Pool00", 2_500.0)]}
            ),
            now="2026-08-17T19:00:00+00:00",
            request_key="slice-d-reappear-below",
            campaign_id="campaign-d",
        )
        connection.commit()

        row = _exact_row(connection, "Mint00", "Pool00")
        assert row["current_state"] == BELOW_LIQUIDITY_FLOOR
        assert row["no_match_streak"] == 0
        assert row["no_match_count"] == 4

        candidate = report["candidates"][0]
        assert candidate["liquidity"]["status"] == LIQUIDITY_BELOW_SELECTION_FLOOR
        assert candidate["eligible"] is False
        assert SELECTION_FLOOR_USD == 3000.0

    def test_below_floor_is_never_written_as_exact_pool_no_match(self, database):
        _, connection = database
        inventory = self._seeded_streak_four(connection)
        run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=_CountingTransport(
                {"pairs": [_pair("Mint00", "Pool00", 2_500.0)]}
            ),
            now="2026-08-17T19:00:00+00:00",
            request_key="slice-d-below-floor-separate",
            campaign_id="campaign-d",
        )
        connection.commit()
        states = {
            str(row[0])
            for row in connection.execute(
                """SELECT new_state FROM printer_exact_market_state_transitions
                   WHERE mint_identity=? AND pool_address=? AND observed_at=?""",
                ("Mint00", "Pool00", "2026-08-17T19:00:00+00:00"),
            )
        }
        assert EXACT_POOL_NO_MATCH not in states
        assert BELOW_LIQUIDITY_FLOOR in states


class TestExactIdentityScope:
    def test_pool_suppression_never_leaks_to_another_pool_of_the_same_mint(
        self, database
    ):
        _, connection = database
        _seed_inventory(connection, 1)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=6,
            no_match_streak=6,
            last_no_match_at=T10,
        )
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="OtherPool00",
            state=CURRENT_VISIBLE,
            reason="EXACT_PROVIDER_ROW",
            observed_at=T10,
        )

        suppressed = decide_exact_pool_poll(
            _exact_row(connection, "Mint00", "Pool00"), at=T12
        )
        assert suppressed.should_poll is False
        assert suppressed.reason == EXACT_POOL_POLL_BACKOFF_ACTIVE
        assert suppressed.no_match_streak == 6

        unaffected = decide_exact_pool_poll(
            _exact_row(connection, "Mint00", "OtherPool00"), at=T12
        )
        assert unaffected.should_poll is True
        assert unaffected.reason == EXACT_POOL_POLL_NOT_NO_MATCH
        assert unaffected.no_match_streak == 0

        # No mint-wide negative-history column exists.
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(printer_exact_market_states)"
            )
        }
        assert {"no_match_count", "no_match_streak", "last_no_match_at",
                "next_lawful_action_at"} <= columns
        assert not any(
            name.startswith("mint_no_match") or name == "mint_negative_history"
            for name in columns
        )

    def test_suppressed_pool_does_not_remove_a_due_pool_from_the_payload(
        self, database
    ):
        _, connection = database
        inventory = _seed_inventory(connection, 2)
        _seed_exact_state(
            connection,
            mint="Mint00",
            pool="Pool00",
            no_match_count=6,
            no_match_streak=6,
            last_no_match_at=T10,
        )
        transport = _CountingTransport(
            {"pairs": [_pair("Mint01", "Pool01", 7_000.0)]}
        )
        report = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="slice-d-scope-payload",
            now=T12,
            campaign_id="campaign-d",
        )
        assert transport.call_count == 1
        assert transport.payloads[0]["token_mints"] == ["Mint01"]
        assert report["negative_history_suppressed_count"] == 1
        assert report["negative_history_suppressed"][0]["pool"] == "Pool00"


# ---------------------------------------------------------------------------
# No schema change
# ---------------------------------------------------------------------------


class TestNoSchemaChange:
    def test_required_durable_columns_already_exist(self, database):
        _, connection = database
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(printer_exact_market_states)"
            )
        }
        assert {
            "no_match_count",
            "no_match_streak",
            "last_no_match_at",
            "next_lawful_action_at",
        } <= columns
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            )
        ]
        assert not any(version.startswith("058") for version in applied)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
