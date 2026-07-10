"""V2-2AB — Minimal PumpPortal Live Transport Implementation Tests.

Verifies:
  A. build_pumpportal_live_transport() raises RuntimeError without websockets
  B. Live transport contract using mocked WebSocket (no real network)
  C. Max-events bound enforced
  D. Duration/timeout bound enforced
  E. Zero reconnects — single attempt only
  F. Fixture transports still work unchanged
  G. pumpfun_launch_stream is READY in plan catalog
  H. pumpfun_migration_stream remains NOT_READY
  I. Governor can execute PumpPortalAdapter with mocked transport + record rows
  J. No memory/retrieval/paper/trading rows created
  K. Metadata flags correct (supports_network_execution=True, fixture_transport_only=False)
  L. T2 fixture tests: migration events never T2, captured_at never token_created_at

No live WebSocket connections. No real network calls. No DB migration outside
isolated temp DBs. No paper decisions, memory, retrieval, BUY/SELL/HOLD,
positions, trades, audits, PnL, scheduler, runtime, scoring, ranking,
confidence, weighted logic, embeddings, or vectors.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import tempfile
import types
import unittest
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import _PLAN_STATUS_NOT_READY, _PLAN_STATUS_READY, _SOURCE_REQUEST_PLAN_CATALOG
from printer_v1.sources import (
    SOURCE_REGISTRY,
    build_governed_source_request,
    execute_source_request_with_governor,
)
from printer_v1.sources.pumpportal import (
    ALLOWED_REQUEST_KINDS,
    PUMPPORTAL_SOURCE_NAME,
    PumpPortalAdapter,
    PumpPortalAdapterMetadata,
    _PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT,
    _PUMPPORTAL_DURATION_SECONDS_DEFAULT,
    _PUMPPORTAL_MAX_EVENTS_DEFAULT,
    _PUMPPORTAL_WS_URL,
    build_pumpportal_adapter,
    build_pumpportal_live_transport,
    fixture_failure_transport,
    fixture_success_transport,
    normalize_pumpportal_payload,
)


DOWNSTREAM_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


def _make_isolated_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    apply_migrations(tmp.name)
    return tmp.name


def _count_downstream(db_path: str) -> dict[str, int]:
    import sqlite3
    conn = sqlite3.connect(db_path)
    counts = {}
    for t in DOWNSTREAM_TABLES:
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            counts[t] = 0
    conn.close()
    return counts


# ---------------------------------------------------------------------------
# A. build_pumpportal_live_transport() raises when websockets missing
# ---------------------------------------------------------------------------

class TestLiveTransportDependencyGuard(unittest.TestCase):
    def test_raises_runtime_error_without_websockets(self):
        """build_pumpportal_live_transport must raise RuntimeError if websockets absent."""
        import sys
        original = sys.modules.get("websockets")
        sys.modules["websockets"] = None  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError) as ctx:
                build_pumpportal_live_transport()
            self.assertIn("websockets", str(ctx.exception))
        finally:
            if original is None:
                del sys.modules["websockets"]
            else:
                sys.modules["websockets"] = original

    def test_error_message_mentions_dependencies(self):
        """Error message must guide operator to add websockets to dependencies."""
        import sys
        original = sys.modules.get("websockets")
        sys.modules["websockets"] = None  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError) as ctx:
                build_pumpportal_live_transport()
            msg = str(ctx.exception).lower()
            self.assertIn("websockets", msg)
        finally:
            if original is None:
                del sys.modules["websockets"]
            else:
                sys.modules["websockets"] = original


# ---------------------------------------------------------------------------
# B/C/D/E. Live transport contract with mocked WebSocket
# ---------------------------------------------------------------------------

def _make_fake_ws_module(events: list[dict], *, fail_connect: bool = False) -> types.ModuleType:
    """Build a fake 'websockets' module that yields the given events."""
    mod = types.ModuleType("websockets")

    async def _mock_recv_sequence(event_list: list[dict]):
        for ev in event_list:
            yield json.dumps(ev)
        # After exhausting events, block forever (simulate waiting for more)
        await asyncio.sleep(9999)

    class _FakeWs:
        def __init__(self, event_list: list[dict]) -> None:
            self._gen = _mock_recv_sequence(event_list)
            self.closed = False
            self.send_calls: list[str] = []

        async def send(self, msg: str) -> None:
            self.send_calls.append(msg)

        async def recv(self) -> str:
            return await self._gen.__anext__()

        async def close(self) -> None:
            self.closed = True

    if fail_connect:
        async def connect(url: str):
            raise OSError("mock connect failure")
    else:
        async def connect(url: str):  # type: ignore[misc]
            return _FakeWs(events)

    mod.connect = connect  # type: ignore[attr-defined]
    return mod


class TestLiveTransportMockedWebSocket(unittest.TestCase):
    """Tests using a fake websockets module injected via sys.modules."""

    def _run_transport_with_fake_ws(
        self,
        events: list[dict],
        *,
        max_events: int = 5,
        duration_seconds: float = 30.0,
        connect_timeout_seconds: float = 10.0,
        fail_connect: bool = False,
    ) -> MappingProxyType:
        fake_ws = _make_fake_ws_module(events, fail_connect=fail_connect)
        with patch.dict(sys.modules, {"websockets": fake_ws}):
            transport_fn = build_pumpportal_live_transport(
                max_events=max_events,
                duration_seconds=duration_seconds,
                connect_timeout_seconds=connect_timeout_seconds,
            )
        ctx = MagicMock()
        with patch.dict(sys.modules, {"websockets": fake_ws}):
            return transport_fn(ctx)

    def test_returns_events_list_and_subscription_method(self):
        events = [{"mint": "TOKEN1"}, {"mint": "TOKEN2"}]
        result = self._run_transport_with_fake_ws(events, max_events=5)
        self.assertIn("events", result)
        self.assertIn("subscription_method", result)
        self.assertEqual(result["subscription_method"], "subscribeNewToken")

    def test_max_events_bound_enforced(self):
        """Transport must stop after max_events, even if more are available."""
        many_events = [{"mint": f"T{i}"} for i in range(20)]
        result = self._run_transport_with_fake_ws(many_events, max_events=3)
        self.assertEqual(len(result["events"]), 3)

    def test_max_events_default_is_5(self):
        self.assertEqual(_PUMPPORTAL_MAX_EVENTS_DEFAULT, 5)

    def test_duration_default_is_30s(self):
        self.assertEqual(_PUMPPORTAL_DURATION_SECONDS_DEFAULT, 30.0)

    def test_connect_timeout_default_is_10s(self):
        self.assertEqual(_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT, 10.0)

    def test_connect_failure_returns_empty_events(self):
        """If WebSocket connect fails, transport returns empty events list (no reconnect)."""
        result = self._run_transport_with_fake_ws([], fail_connect=True)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["subscription_method"], "subscribeNewToken")

    def test_no_reconnect_on_connect_failure(self):
        """Connect failure returns immediately; no retry loop."""
        connect_call_count = []

        async def failing_connect(url: str):
            connect_call_count.append(1)
            raise OSError("mock connect failure")

        fake_ws = types.ModuleType("websockets")
        fake_ws.connect = failing_connect  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"websockets": fake_ws}):
            transport_fn = build_pumpportal_live_transport()
            ctx = MagicMock()
            result = transport_fn(ctx)

        self.assertEqual(len(connect_call_count), 1, "Must attempt connect exactly once; no reconnect")
        self.assertEqual(result["events"], [])

    def test_zero_events_returned_when_stream_empty(self):
        result = self._run_transport_with_fake_ws([])
        self.assertEqual(result["events"], [])

    def test_ws_url_is_correct(self):
        self.assertEqual(_PUMPPORTAL_WS_URL, "wss://pumpportal.fun/api/data")

    def test_subscribe_new_token_sent(self):
        """Transport must send subscribeNewToken subscription message."""
        sent_messages: list[str] = []

        async def _recv_once():
            yield json.dumps({"mint": "T1"})
            await asyncio.sleep(9999)

        class _Ws:
            def __init__(self):
                self._gen = _recv_once()

            async def send(self, msg: str) -> None:
                sent_messages.append(msg)

            async def recv(self) -> str:
                return await self._gen.__anext__()

            async def close(self) -> None:
                pass

        fake_ws = types.ModuleType("websockets")

        async def connect(url: str):
            return _Ws()
        fake_ws.connect = connect  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"websockets": fake_ws}):
            transport_fn = build_pumpportal_live_transport(max_events=1)
            ctx = MagicMock()
            transport_fn(ctx)

        self.assertEqual(len(sent_messages), 1)
        parsed = json.loads(sent_messages[0])
        self.assertEqual(parsed, {"method": "subscribeNewToken"})

    def test_non_dict_events_skipped(self):
        """Non-dict payloads from the stream are silently skipped."""
        mixed_events: list = ["not_a_dict", 42, {"mint": "VALID"}, None]

        sent_raw: list[str] = []

        async def _recv_sequence():
            for ev in mixed_events:
                yield json.dumps(ev) if not isinstance(ev, str) else ev
            await asyncio.sleep(9999)

        class _Ws:
            def __init__(self):
                self._gen = _recv_sequence()

            async def send(self, msg: str) -> None:
                sent_raw.append(msg)

            async def recv(self) -> str:
                return await self._gen.__anext__()

            async def close(self) -> None:
                pass

        fake_ws = types.ModuleType("websockets")

        async def connect(url: str):
            return _Ws()
        fake_ws.connect = connect  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"websockets": fake_ws}):
            transport_fn = build_pumpportal_live_transport(max_events=5)
            ctx = MagicMock()
            result = transport_fn(ctx)

        collected = result["events"]
        for ev in collected:
            self.assertIsInstance(ev, dict)


# ---------------------------------------------------------------------------
# F. Fixture transports still work
# ---------------------------------------------------------------------------

class TestFixtureTransportsUnchanged(unittest.TestCase):
    def test_fixture_success_transport_returns_payload(self):
        payload = {"tokens": [{"chain": "solana", "mint": "AAA"}]}
        fn = fixture_success_transport(payload)
        ctx = MagicMock()
        result = fn(ctx)
        self.assertEqual(result["tokens"][0]["mint"], "AAA")

    def test_fixture_failure_transport_returns_failure_status(self):
        fn = fixture_failure_transport("test failure")
        ctx = MagicMock()
        result = fn(ctx)
        self.assertEqual(result["fixture_status"], "failure")
        self.assertIn("test failure", result["failure_message"])

    def test_adapter_with_fixture_success_transport_normalizes(self):
        payload = {
            "tokens": [{"chain": "solana", "mint": "BBB", "tokenMint": "BBB"}]
        }
        fn = fixture_success_transport(payload)
        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=fn)
        from printer_v1.sources.contracts import build_source_adapter_contract, SourceAdapterContext
        from printer_v1.sources.governed_execution import build_fixture_source_adapter

        contract = build_source_adapter_contract("pumpportal")
        from printer_v1.sources.contracts import (
            GOVERNOR_ONLY_EXECUTION_PATH,
            build_governor_decision,
            SourceRequest,
        )

        sr = build_governed_source_request(
            "pumpportal",
            "pumpfun_launch_stream",
            request_key="fixture-test",
            tracking_priority=0,
            payload={},
        )
        from printer_v1.sources.contracts import build_governor_decision
        decision = build_governor_decision(sr, recent_request_count=0)
        ctx = SourceAdapterContext(
            request=sr,
            request_record=MagicMock(),
            decision=decision,
            governor_approved=True,
        )
        result = adapter.execute(ctx)
        from printer_v1.contracts.enums import SourceStatus
        self.assertEqual(result.source_status, SourceStatus.COMPLETE)


# ---------------------------------------------------------------------------
# G/H. Plan catalog status
# ---------------------------------------------------------------------------

class TestPlanCatalogStatus(unittest.TestCase):
    def test_pumpfun_launch_stream_is_ready(self):
        catalog = _SOURCE_REQUEST_PLAN_CATALOG.get("pumpportal", [])
        launch_status = next((s for k, s in catalog if k == "pumpfun_launch_stream"), None)
        self.assertEqual(launch_status, _PLAN_STATUS_READY)

    def test_pumpfun_migration_stream_is_not_ready(self):
        catalog = _SOURCE_REQUEST_PLAN_CATALOG.get("pumpportal", [])
        migration_status = next((s for k, s in catalog if k == "pumpfun_migration_stream"), None)
        self.assertEqual(migration_status, _PLAN_STATUS_NOT_READY)

    def test_pumpfun_launch_stream_in_allowed_request_kinds(self):
        self.assertIn("pumpfun_launch_stream", ALLOWED_REQUEST_KINDS)

    def test_pumpfun_migration_stream_in_allowed_request_kinds(self):
        self.assertIn("pumpfun_migration_stream", ALLOWED_REQUEST_KINDS)

    def test_no_trading_kinds_in_catalog(self):
        forbidden = {"subscribeTokenTrade", "subscribeAccountTrade", "token_trade", "swap"}
        catalog = _SOURCE_REQUEST_PLAN_CATALOG.get("pumpportal", [])
        catalog_kinds = {k for k, _ in catalog}
        self.assertFalse(catalog_kinds & forbidden, "No trading kinds in pumpportal catalog")


# ---------------------------------------------------------------------------
# I. Governor can execute PumpPortalAdapter + records rows
# ---------------------------------------------------------------------------

class TestGovernorExecutesPumpPortalAdapter(unittest.TestCase):
    def test_governor_records_request_and_response_with_fixture(self):
        """Governor path works with PumpPortalAdapter; request + response rows created."""
        db_path = _make_isolated_db()
        payload = {
            "tokens": [{"chain": "solana", "mint": "GOVTEST", "tokenMint": "GOVTEST"}]
        }
        fn = fixture_success_transport(payload)
        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=fn)
        sr = build_governed_source_request(
            "pumpportal",
            "pumpfun_launch_stream",
            request_key="gov-test-launch",
            tracking_priority=0,
            payload={"chain": "solana"},
        )
        result = execute_source_request_with_governor(db_path, sr, adapter, recent_request_count=0)
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.response_record)
        self.assertIsNone(result.failure_record)

        import sqlite3
        conn = sqlite3.connect(db_path)
        req_count = conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
        resp_count = conn.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0]
        conn.close()
        self.assertEqual(req_count, 1)
        self.assertEqual(resp_count, 1)

    def test_governor_records_failure_row_on_fixture_failure(self):
        db_path = _make_isolated_db()
        fn = fixture_failure_transport("intentional failure")
        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=fn)
        sr = build_governed_source_request(
            "pumpportal",
            "pumpfun_launch_stream",
            request_key="gov-test-failure",
            tracking_priority=0,
            payload={},
        )
        result = execute_source_request_with_governor(db_path, sr, adapter, recent_request_count=0)
        self.assertIsNotNone(result.request_record)
        self.assertIsNotNone(result.failure_record)


# ---------------------------------------------------------------------------
# J. No downstream rows created
# ---------------------------------------------------------------------------

class TestNoDownstreamRowsCreated(unittest.TestCase):
    def test_governor_execution_creates_no_memory_or_trading_rows(self):
        db_path = _make_isolated_db()
        before = _count_downstream(db_path)

        payload = {
            "tokens": [{"chain": "solana", "mint": "CLEAN", "tokenMint": "CLEAN"}]
        }
        fn = fixture_success_transport(payload)
        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=fn)
        sr = build_governed_source_request(
            "pumpportal",
            "pumpfun_launch_stream",
            request_key="downstream-check",
            tracking_priority=0,
            payload={},
        )
        execute_source_request_with_governor(db_path, sr, adapter, recent_request_count=0)

        after = _count_downstream(db_path)
        for t in DOWNSTREAM_TABLES:
            self.assertEqual(before[t], after[t], f"Row count changed in {t}")


# ---------------------------------------------------------------------------
# K. Metadata flags
# ---------------------------------------------------------------------------

class TestMetadataFlags(unittest.TestCase):
    def test_supports_network_execution_is_true(self):
        m = PumpPortalAdapterMetadata()
        self.assertTrue(m.supports_network_execution)

    def test_fixture_transport_only_is_false(self):
        m = PumpPortalAdapterMetadata()
        self.assertFalse(m.fixture_transport_only)

    def test_enabled_by_default_is_false(self):
        m = PumpPortalAdapterMetadata()
        self.assertFalse(m.enabled_by_default)

    def test_source_name_is_pumpportal(self):
        m = PumpPortalAdapterMetadata()
        self.assertEqual(m.source_name, PUMPPORTAL_SOURCE_NAME)

    def test_requires_governor_context_is_true(self):
        m = PumpPortalAdapterMetadata()
        self.assertTrue(m.requires_governor_context)


# ---------------------------------------------------------------------------
# L. T2 safety: migration events never T2, captured_at never token_created_at
# ---------------------------------------------------------------------------

class TestT2SafetyRules(unittest.TestCase):
    def _normalize(self, event: dict, request_kind: str) -> dict | None:
        from printer_v1.sources.pumpportal import _normalize_pumpportal_event
        return _normalize_pumpportal_event(event, request_kind)

    def test_migration_event_token_created_at_is_none(self):
        """Migration events must never produce token_created_at (T2)."""
        event = {
            "mint": "MIGTOKEN",
            "tokenCreatedAt": 1700000000,
            "newRaydiumPool": "POOL1",
        }
        result = self._normalize(event, "pumpfun_migration_stream")
        self.assertIsNotNone(result)
        self.assertIsNone(result["token_created_at"])

    def test_launch_event_token_created_at_set_when_valid(self):
        """Launch events with valid timestamp produce non-null token_created_at."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        recent_ts = int((now - timedelta(minutes=2)).timestamp())
        event = {
            "mint": "LAUNCHTOKEN",
            "tokenCreatedAt": recent_ts,
        }
        result = self._normalize(event, "pumpfun_launch_stream")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result["token_created_at"])

    def test_launch_event_stale_timestamp_rejected(self):
        """Launch events older than staleness threshold produce null token_created_at."""
        stale_ts = 1000000000  # Year 2001 — far too old
        event = {
            "mint": "STALETOKEN",
            "tokenCreatedAt": stale_ts,
        }
        result = self._normalize(event, "pumpfun_launch_stream")
        self.assertIsNotNone(result)
        self.assertIsNone(result["token_created_at"])

    def test_captured_at_not_used_as_token_created_at(self):
        """captured_at field must never propagate to token_created_at."""
        event = {
            "mint": "CATOKEN",
            "captured_at": "2026-07-09T12:00:00+00:00",
            # No tokenCreatedAt / createdTimestamp / timestamp
        }
        result = self._normalize(event, "pumpfun_launch_stream")
        self.assertIsNotNone(result)
        self.assertIsNone(result["token_created_at"])

    def test_priority_tokenCreatedAt_over_timestamp(self):
        """tokenCreatedAt takes priority over timestamp for T2 extraction."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        good_ts = int((now - timedelta(minutes=1)).timestamp())
        stale_ts = 1000000000
        event = {
            "mint": "PRIOTOKEN",
            "tokenCreatedAt": good_ts,
            "timestamp": stale_ts,
        }
        result = self._normalize(event, "pumpfun_launch_stream")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result["token_created_at"])

    def test_future_timestamp_rejected(self):
        """Timestamps in the future relative to observation are rejected."""
        from datetime import datetime, timezone, timedelta
        future_ts = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        event = {
            "mint": "FUTURETOKEN",
            "tokenCreatedAt": future_ts,
        }
        result = self._normalize(event, "pumpfun_launch_stream")
        self.assertIsNotNone(result)
        self.assertIsNone(result["token_created_at"])


# ---------------------------------------------------------------------------
# V2-2AC: websockets dependency declaration
# ---------------------------------------------------------------------------

class TestWebsocketsDependencyDeclaration(unittest.TestCase):
    """V2-2AC: websockets must be declared in pyproject.toml project dependencies."""

    def test_websockets_declared_in_pyproject_dependencies(self):
        import re
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.exists(), "pyproject.toml must exist")
        text = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'dependencies\s*=\s*\[([^\]]*)\]', text)
        self.assertIsNotNone(match, "No dependencies list found in pyproject.toml")
        deps_str = match.group(1)
        self.assertIn("websockets", deps_str, "websockets must be in project dependencies")

    def test_websockets_minimum_version_specified(self):
        """The declared websockets dependency must include a minimum version constraint."""
        import re
        text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'dependencies\s*=\s*\[([^\]]*)\]', text)
        deps_str = match.group(1)
        self.assertRegex(deps_str, r'websockets\s*>=\s*\d')


# ---------------------------------------------------------------------------
# V2-2AC: transport bound hardening
# ---------------------------------------------------------------------------

class TestBoundHardening(unittest.TestCase):
    """V2-2AC: build_pumpportal_live_transport must reject unsafe bound overrides."""

    def test_max_events_above_limit_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            build_pumpportal_live_transport(max_events=_PUMPPORTAL_MAX_EVENTS_DEFAULT + 1)
        self.assertIn("max_events", str(ctx.exception))

    def test_duration_above_limit_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            build_pumpportal_live_transport(duration_seconds=_PUMPPORTAL_DURATION_SECONDS_DEFAULT + 1.0)
        self.assertIn("duration_seconds", str(ctx.exception))

    def test_connect_timeout_above_limit_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            build_pumpportal_live_transport(connect_timeout_seconds=_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT + 1.0)
        self.assertIn("connect_timeout_seconds", str(ctx.exception))

    def test_bound_error_raised_before_websockets_import(self):
        """Bound validation must fire even when websockets is absent."""
        with patch.dict(sys.modules, {"websockets": None}):
            with self.assertRaises(ValueError):
                build_pumpportal_live_transport(max_events=_PUMPPORTAL_MAX_EVENTS_DEFAULT + 1)

    def test_exact_defaults_are_accepted(self):
        """Exact default bound values must be accepted (not off-by-one rejected)."""
        fake_ws = _make_fake_ws_module([])
        with patch.dict(sys.modules, {"websockets": fake_ws}):
            fn = build_pumpportal_live_transport(
                max_events=_PUMPPORTAL_MAX_EVENTS_DEFAULT,
                duration_seconds=_PUMPPORTAL_DURATION_SECONDS_DEFAULT,
                connect_timeout_seconds=_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT,
            )
        self.assertIsNotNone(fn)

    def test_below_default_max_events_accepted(self):
        """max_events below the limit must be accepted."""
        fake_ws = _make_fake_ws_module([])
        with patch.dict(sys.modules, {"websockets": fake_ws}):
            fn = build_pumpportal_live_transport(max_events=_PUMPPORTAL_MAX_EVENTS_DEFAULT - 1)
        self.assertIsNotNone(fn)


if __name__ == "__main__":
    unittest.main()
