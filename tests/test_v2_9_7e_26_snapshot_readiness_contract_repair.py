from __future__ import annotations

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import json
import sqlite3

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.bounded_readiness_report import (
    build_bounded_readiness_report,
    canonical_report_bytes,
)
from printer_v1.operator_cli.e2m_snapshot_persistence import (
    E2M_STATUS_BLOCKED,
    E2M_STATUS_PERSISTED,
    persist_snapshot_from_source_response,
)
from printer_v1.operator_cli.holder_reliability_budget_control import build_ledger
from printer_v1.operator_cli.snapshot_readiness_contract import (
    READINESS_OPERATION_RESERVATION,
    readiness_base_blockers,
    merge_exact_15m_evidence,
    snapshot_readiness_blockers,
)
from printer_v1.operator_cli.snapshot_readiness_owner import (
    execute_readiness_snapshot_bundle,
)
from printer_v1.sources.geckoterminal import (
    normalize_geckoterminal_payload,
    GECKOTERMINAL_POOL_URL_TEMPLATE,
    build_geckoterminal_adapter,
    fixture_success_transport as gt_fixture,
    GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
)
from printer_v1.sources.geckoterminal_15m import (
    GECKOTERMINAL_OHLCV_REQUEST_KIND,
    GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
    TRADE_HISTORY_TRUNCATED,
    build_gt15m_trades_url,
    count_txns_15m_from_trades,
)


MINT = "e26-exact-mint"
PAIR = "e26-exact-pair"


class _NoSleepPacer:
    def __init__(self):
        self.trace = []

    def pace(self, source_name):
        self.trace.append(source_name)
        return None


def _connection(tmp_path) -> tuple[sqlite3.Connection, str]:
    path = tmp_path / "e26.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection, str(path)


def _gt_base_payload(*, liquidity=25_000.0, wider_volume=1_200.0, wider_txns=12):
    return {
        "_requested_pool_address": PAIR,
        "_requested_token_mint": MINT,
        "_requested_network": "solana",
        "_requested_endpoint": f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{PAIR}",
        "data": {
            "id": f"solana_{PAIR}",
            "type": "pool",
            "attributes": {
                "address": PAIR,
                "base_token_price_usd": "0.001",
                "reserve_in_usd": (str(liquidity) if liquidity is not None else None),
                "volume_usd": {"m5": "100", "h1": str(wider_volume), "h24": "4000"},
                "transactions": {
                    "m5": {"buys": 2, "sells": 1},
                    "h1": {"buys": wider_txns, "sells": 0},
                    "h24": {"buys": 20, "sells": 10},
                },
                "price_change_percentage": {"m5": "1", "h1": "2", "h24": "3"},
                "fdv_usd": "100000",
                "pool_created_at": "2026-07-22T22:20:00Z",
            },
            "relationships": {
                "base_token": {"data": {"id": f"solana_{MINT}", "type": "token"}},
            },
        },
    }


def _gt_base_factory(payload):
    def factory(**_kwargs):
        return build_geckoterminal_adapter(
            enabled=True, fixture_transport=gt_fixture(payload)
        )
    return factory


def _gt_fixtures(now: datetime):
    current_start = int(now.timestamp() // 900 * 900)
    candle_start = current_start - 900
    candle_end = current_start
    ohlcv = {
        "data": {"attributes": {"ohlcv_list": [
            [candle_start, 1.0, 1.2, 0.9, 1.1, 500.0]
        ]}}
    }
    trades = {
        "data": [
            {"attributes": {
                "block_timestamp": datetime.fromtimestamp(
                    candle_start + offset, tz=timezone.utc
                ).isoformat()
            }}
            for offset in (60, 120, 240)
        ]
    }
    return {
        GECKOTERMINAL_OHLCV_REQUEST_KIND: lambda _context: ohlcv,
        GECKOTERMINAL_POOL_TRADES_REQUEST_KIND: lambda _context: trades,
    }, candle_start, candle_end


def _step():
    return {
        "run_id": "e26-run",
        "step_key": "readiness-1",
        "token_mint": MINT,
        "pair_address": PAIR,
        "tracking_lane": "TRACK_FAST",
    }


def _insert_normalized_response(
    connection: sqlite3.Connection,
    pair: dict,
    *,
    received_at: datetime,
) -> int:
    pair = dict(pair)
    pair.setdefault("liquidity_provenance", {
        "source": "geckoterminal",
        "raw_field": "reserve_in_usd",
        "network": "solana",
        "pool_address": PAIR,
        "token_mint": MINT,
    })
    request = connection.execute(
        """INSERT INTO printer_source_requests(
            source_name,request_kind,requested_at,source_status,data_quality_label
        ) VALUES ('geckoterminal','geckoterminal_readiness_base_snapshot',?,'COMPLETE','CLEAN_DATA')""",
        (received_at.isoformat(),),
    )
    response = connection.execute(
        """INSERT INTO printer_source_responses(
            source_request_id,source_name,received_at,source_status,
            data_quality_label,normalized_payload_json
        ) VALUES (?,'geckoterminal',?,'COMPLETE','CLEAN_DATA',?)""",
        (
            int(request.lastrowid), received_at.isoformat(),
            json.dumps({"pairs": [pair]}),
        ),
    )
    connection.commit()
    return int(response.lastrowid)


def test_complete_exact_pair_bundle_accepts_three_governed_operations(tmp_path) -> None:
    connection, db_path = _connection(tmp_path)
    now = datetime.now(timezone.utc)
    transports, candle_start, candle_end = _gt_fixtures(now)
    pacer = _NoSleepPacer()
    result = execute_readiness_snapshot_bundle(
        connection,
        _step(),
        geckoterminal_base_adapter_factory=_gt_base_factory(_gt_base_payload()),
        timeout_seconds=2.0,
        geckoterminal_transports=transports,
        evaluated_at=now,
        request_pacer=pacer,
    )
    connection.commit()
    assert result["ok"]
    assert result["operations_attempted"] == 3
    assert pacer.trace == ["geckoterminal", "geckoterminal", "geckoterminal"]
    assert len(result["completion_records"]) == 2
    assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == 3
    row = connection.execute(
        """SELECT liquidity_usd,volume_5m,volume_15m,txns_5m,txns_15m,
                  price_change_5m,price_change_15m,
                  normalized_snapshot_payload_json
           FROM printer_token_snapshots"""
    ).fetchone()
    assert tuple(row[:7]) == (25_000.0, 100.0, 500.0, 3, 3, 1.0, 10.0)
    provenance = json.loads(row[7])
    assert provenance["snapshot_readiness_contract"]["label"] == "SNAPSHOT_READINESS_COMPLETE"
    assert provenance["price_change_15m_provenance"]["candle_start_iso"] == datetime.fromtimestamp(candle_start, tz=timezone.utc).isoformat()
    assert provenance["txns_15m_provenance"]["window_end_iso"] == datetime.fromtimestamp(candle_end, tz=timezone.utc).isoformat()
    first = build_bounded_readiness_report(db_path, run_id="none", cycle_id="none")
    second = build_bounded_readiness_report(db_path, run_id="none", cycle_id="none")
    assert canonical_report_bytes(first) == canonical_report_bytes(second)
    assert len(first["readiness_snapshots"]) == 1


def test_missing_liquidity_fails_before_15m_completion_calls(tmp_path) -> None:
    connection, _ = _connection(tmp_path)
    now = datetime.now(timezone.utc)
    transports, _, _ = _gt_fixtures(now)
    pacer = _NoSleepPacer()
    result = execute_readiness_snapshot_bundle(
        connection,
        _step(),
        geckoterminal_base_adapter_factory=_gt_base_factory(_gt_base_payload(liquidity=None)),
        timeout_seconds=2.0,
        geckoterminal_transports=transports,
        evaluated_at=now,
        request_pacer=pacer,
    )
    assert not result["ok"]
    assert result["operations_attempted"] == 1
    assert "geckoterminal_pair_snapshot_missing_mandatory_fields" in result["blocked_reasons"]
    assert pacer.trace == ["geckoterminal"]
    assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM printer_token_snapshots").fetchone()[0] == 0


def test_missing_15m_fields_fail_strict_persistence(tmp_path) -> None:
    connection, _ = _connection(tmp_path)
    now = datetime.now(timezone.utc)
    pair = {
        "chain": "solana", "token_mint": MINT, "pair_address": PAIR,
        "price_usd": 0.001, "liquidity_usd": 10_000.0,
        "price_change_5m": 1.0, "volume_5m": 10.0, "txns_5m": 2,
        "volume_1h": 100.0, "txns_1h": 10,
    }
    response_id = _insert_normalized_response(connection, pair, received_at=now)
    result = persist_snapshot_from_source_response(
        connection, response_id, MINT,
        expected_pair_address=PAIR,
        require_readiness_contract=True,
        evaluated_at=now,
    )
    assert result["e2m_status"] == E2M_STATUS_BLOCKED
    assert any("price_change_15m" in reason for reason in result["blocked_reasons"])
    assert connection.execute("SELECT COUNT(*) FROM printer_token_snapshots").fetchone()[0] == 0


def test_verified_inactivity_accepts_only_existing_e19_predicate(tmp_path) -> None:
    connection, _ = _connection(tmp_path)
    now = datetime.now(timezone.utc)
    pair = {
        "chain": "solana", "token_mint": MINT, "pair_address": PAIR,
        "price_usd": 0.001, "liquidity_usd": 10_000.0,
        "price_change_5m": None, "volume_5m": None, "txns_5m": None,
        "price_change_15m": None, "volume_15m": None, "txns_15m": None,
        "volume_1h": 0.0, "txns_1h": 0,
    }
    response_id = _insert_normalized_response(connection, pair, received_at=now)
    result = persist_snapshot_from_source_response(
        connection, response_id, MINT,
        expected_pair_address=PAIR,
        require_readiness_contract=True,
        evaluated_at=now,
    )
    assert result["e2m_status"] == E2M_STATUS_PERSISTED
    row = connection.execute(
        "SELECT volume_5m,volume_15m,txns_5m,txns_15m FROM printer_token_snapshots"
    ).fetchone()
    assert tuple(row) == (0.0, 0.0, 0, 0)


def test_invalid_zeros_positive_wider_activity_and_missing_liquidity_reject() -> None:
    now = datetime.now(timezone.utc)
    pair = {
        "chain": "solana", "token_mint": MINT, "pair_address": PAIR,
        "price_usd": 1.0, "liquidity_usd": 10.0,
        "price_change_5m": 0.0, "volume_5m": 0.0, "txns_5m": 0,
        "price_change_15m": 0.0, "volume_15m": 0.0, "txns_15m": 0,
        "volume_1h": 1.0, "txns_1h": 1,
    }
    blockers = snapshot_readiness_blockers(
        pair, expected_mint=MINT, expected_pair=PAIR, evaluated_at=now
    )
    assert any("15M_PROVENANCE" in reason for reason in blockers)
    no_liquidity = {**pair, "liquidity_usd": None, "volume_1h": 0.0, "txns_1h": 0}
    blockers = snapshot_readiness_blockers(
        no_liquidity, expected_mint=MINT, expected_pair=PAIR, evaluated_at=now
    )
    assert "READINESS_MISSING_OR_INVALID:liquidity_usd" in blockers


def test_mismatch_stale_and_conflicting_evidence_reject(tmp_path) -> None:
    base = {
        "chain": "solana", "token_mint": MINT, "pair_address": PAIR,
        "price_change_15m": 1.0,
    }
    merged, blockers = merge_exact_15m_evidence(
        base, {"price_change_15m": 2.0},
        expected_mint=MINT, expected_pair=PAIR,
    )
    assert merged["price_change_15m"] == 1.0
    assert "READINESS_EVIDENCE_CONFLICT:price_change_15m" in blockers
    _, blockers = merge_exact_15m_evidence(
        base,
        {"txns_15m_provenance": {"pool_address": "wrong"}},
        expected_mint=MINT, expected_pair=PAIR,
    )
    assert any("TARGET_MISMATCH" in reason for reason in blockers)

    connection, _ = _connection(tmp_path)
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    inactive = {
        "chain": "solana", "token_mint": MINT, "pair_address": PAIR,
        "price_usd": 1.0, "liquidity_usd": 10.0,
        "price_change_5m": None, "volume_5m": None, "txns_5m": None,
        "price_change_15m": None, "volume_15m": None, "txns_15m": None,
        "volume_1h": 0.0, "txns_1h": 0,
    }
    response_id = _insert_normalized_response(connection, inactive, received_at=old)
    result = persist_snapshot_from_source_response(
        connection, response_id, MINT,
        expected_pair_address=PAIR,
        require_readiness_contract=True,
        evaluated_at=datetime.now(timezone.utc),
    )
    assert "READINESS_PRIMARY_STALE" in result["blocked_reasons"]


def test_unfiltered_trade_contract_rejects_malformed_and_truncated() -> None:
    assert "trade_volume_in_usd_greater_than" not in build_gt15m_trades_url(PAIR)
    count, label, details = count_txns_15m_from_trades(
        [{"attributes": {}}],
        window_start_unix=0,
        window_end_unix=900,
    )
    assert count is None and label == TRADE_HISTORY_TRUNCATED
    assert details["error"] == "malformed_trade_timestamp"


def test_budget_reserves_complete_path_and_derives_three_candidates() -> None:
    now = datetime.now(timezone.utc)
    ledger = build_ledger(pump_operations=13, deadline_at=now + timedelta(minutes=6))
    assert READINESS_OPERATION_RESERVATION == 6
    assert ledger.reserved_snapshot_operations == 2
    assert ledger.reserved_snapshot_completion_operations == 4
    assert ledger.candidate_cap() == 3
    assert 13 + 9 + (3 * 5) + 6 == 43 <= 45


def test_integrity_cleanup_foreign_keys_and_forbidden_deltas_zero(tmp_path) -> None:
    connection, _ = _connection(tmp_path)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    for table in (
        "printer_memory_windows", "printer_paper_decisions",
        "printer_paper_positions", "printer_paper_trade_events",
        "printer_paper_trade_audits",
    ):
        assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status IN ('PENDING','RUNNING','COOLDOWN')"
    ).fetchone()[0] == 0


def test_exact_pool_reserve_provenance_and_liquidity_conflict_reject() -> None:
    accepted = normalize_geckoterminal_payload(
        _gt_base_payload(),
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    pair = dict(accepted.normalized_payload["pairs"][0])
    assert pair["liquidity_usd"] == 25_000.0
    assert pair["liquidity_provenance"] == {
        "source": "geckoterminal",
        "raw_field": "reserve_in_usd",
        "network": "solana",
        "pool_address": PAIR,
        "token_mint": MINT,
        "endpoint": f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{PAIR}",
        "composition_checked": False,
    }
    conflict = deepcopy(_gt_base_payload())
    conflict["data"]["attributes"].update({
        "base_token_liquidity_usd": "10000",
        "quote_token_liquidity_usd": "10000",
    })
    rejected = normalize_geckoterminal_payload(
        conflict,
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    assert rejected.failure_type == "geckoterminal_pair_snapshot_liquidity_conflict"


def test_exact_pool_zero_stale_mismatch_and_malformed_fail_closed() -> None:
    zero = normalize_geckoterminal_payload(
        _gt_base_payload(liquidity=0),
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    zero_pair = dict(zero.normalized_payload["pairs"][0])
    assert "READINESS_MISSING_OR_INVALID:liquidity_usd" in readiness_base_blockers(zero_pair)

    stale_payload = deepcopy(_gt_base_payload())
    stale_payload["fixture_stale"] = True
    stale = normalize_geckoterminal_payload(
        stale_payload,
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    assert stale.failure_type == "geckoterminal_pair_snapshot_stale"

    resource_payload = deepcopy(_gt_base_payload())
    resource_payload["data"]["id"] = "solana_wrong"
    resource = normalize_geckoterminal_payload(
        resource_payload,
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    assert resource.failure_type == "geckoterminal_pair_snapshot_resource_mismatch"

    mismatch_payload = deepcopy(_gt_base_payload())
    mismatch_payload["data"]["relationships"]["base_token"]["data"]["id"] = "solana_wrong"
    mismatch = normalize_geckoterminal_payload(
        mismatch_payload,
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    assert mismatch.failure_type == "geckoterminal_pair_snapshot_identity_mismatch"

    malformed = normalize_geckoterminal_payload(
        {"_requested_pool_address": PAIR, "_requested_network": "solana", "data": []},
        request_kind=GECKOTERMINAL_READINESS_BASE_REQUEST_KIND,
        expected_pool_address=PAIR,
        expected_token_mint=MINT,
    )
    assert malformed.failure_type == "geckoterminal_pair_snapshot_missing_data"
    assert GECKOTERMINAL_POOL_URL_TEMPLATE.endswith("?include=base_token,quote_token,dex")
