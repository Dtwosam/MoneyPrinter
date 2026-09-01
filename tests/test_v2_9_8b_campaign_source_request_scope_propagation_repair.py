"""V2-9.8B freeze-ready CampaignSourceRequestScope propagation repair.

Disposable databases and fixture transports only. No live providers, no
authoritative DB, no authorization, no campaign retry, no retrieval/financial
unlock.
"""

from __future__ import annotations

import inspect
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery import eligible_token_supply as eligible_supply_module
from printer_v1.discovery.eligible_token_supply import (
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH,
    CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED,
    LEGACY_STATIC_REQUEST_KEY_ROOT,
    LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY,
    MINIMUM_FREEZE_DEPTH,
    assemble_and_reconcile_campaign_source_requests,
    build_campaign_source_request_scope,
    validate_campaign_source_request_scope,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    build_graduated_supply,
)


NOW = "2026-09-01T19:14:51+00:00"
EXECUTION = "20260901T191450Z-520d6a348621"
CAMPAIGN = "20260901T191450Z-520d6a348621-campaign"
RUN = "20260901T191450Z-520d6a348621-campaign-run"
CYCLE = "20260901T191450Z-520d6a348621-cycle"
FOREIGN_EXECUTION = "20260830T113652Z-a89ed6bc"


def _scope(**overrides: str):
    payload = {
        "execution_id": EXECUTION,
        "campaign_id": CAMPAIGN,
        "run_id": RUN,
        "cycle_id": CYCLE,
    }
    payload.update(overrides)
    return build_campaign_source_request_scope(**payload)


def _empty_migration_transport():
    from printer_v1.sources.direct_pump_migration import (
        SIGNATURE_PAGE_REQUEST_KIND,
        TRANSACTION_REQUEST_KIND,
    )

    def transport(context):
        kind = context.request.request_kind
        if kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {"result": []}
        if kind == TRANSACTION_REQUEST_KIND:
            return {"result": None}
        raise AssertionError(kind)

    return transport


@pytest.fixture
def database(tmp_path: Path):
    path = tmp_path / "scope-propagation.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield path, connection
    finally:
        connection.close()


def _insert_request(connection: sqlite3.Connection, *, key: str, source: str = "dexscreener") -> int:
    connection.execute(
        """
        INSERT INTO printer_source_requests(
            source_name, request_kind, requested_at, request_key,
            tracking_priority, source_status, data_quality_label
        ) VALUES (?, ?, ?, ?, 0, 'COMPLETE', 'CLEAN_DATA')
        """,
        (source, "fixture_stage", NOW, key),
    )
    connection.commit()
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def _current_root_keys(connection: sqlite3.Connection, root: str) -> list[str]:
    rows = connection.execute(
        "SELECT request_key FROM printer_source_requests ORDER BY id"
    ).fetchall()
    keys = [str(row["request_key"]) for row in rows]
    assert keys
    assert all(key == root or key.startswith(f"{root}-") for key in keys)
    return keys


def _capture_persistent_kwargs() -> tuple[dict[str, Any], Any]:
    captured: dict[str, Any] = {}
    real = eligible_supply_module.run_persistent_eligible_token_supply

    def wrapped(*args: Any, **kwargs: Any):
        captured.clear()
        captured.update(kwargs)
        return real(*args, **kwargs)

    return captured, wrapped


def _permanent_kwargs(scope, **extra: Any) -> dict[str, Any]:
    payload = {
        "cycle_seed": EXECUTION,
        "migration_transport": _empty_migration_transport(),
        "now": NOW,
        "run_locator": False,
        "run_geckoterminal_nomination": False,
        "enable_geckoterminal_reconciliation": False,
        "permanent_availability": True,
        "campaign_id": scope.campaign_id,
        "execution_id": scope.execution_id,
        "run_id": scope.run_id,
        "cycle_id": scope.cycle_id,
        "discovery_request_key_prefix": scope.request_key_root,
        "front_door_request_key_prefix": scope.request_key_root,
        "campaign_source_request_scope": scope,
    }
    payload.update(extra)
    return payload


class TestFreezeReadyScopePropagation:
    def test_front_door_forwards_owner_scope_into_freeze_ready_assemble(
        self, database, monkeypatch
    ):
        path, connection = database
        scope = _scope()
        captured, wrapped = _capture_persistent_kwargs()
        observed: dict[str, Any] = {}
        real_assemble = assemble_and_reconcile_campaign_source_requests

        def capturing_assemble(*args: Any, **kwargs: Any):
            observed["kwargs"] = dict(kwargs)
            observed["scope"] = kwargs.get("campaign_source_request_scope")
            return real_assemble(*args, **kwargs)

        monkeypatch.setattr(
            eligible_supply_module,
            "run_persistent_eligible_token_supply",
            wrapped,
        )
        monkeypatch.setattr(
            "printer_v1.discovery.permanent_discovery_availability.assemble_and_reconcile_campaign_source_requests",
            capturing_assemble,
        )

        supply = build_graduated_supply(
            path,
            **_permanent_kwargs(scope),
        )

        assert captured["discovery_request_key_prefix"] == scope.request_key_root
        assert captured["front_door_request_key_prefix"] == scope.request_key_root
        forwarded = captured.get("campaign_source_request_scope")
        assert forwarded is scope or forwarded == scope.as_dict()
        received = observed.get("scope")
        assert received is not None
        validated = validate_campaign_source_request_scope(
            received,
            execution_id=scope.execution_id,
            campaign_id=scope.campaign_id,
            run_id=scope.run_id,
            cycle_id=scope.cycle_id,
        )
        assert validated.request_key_root == scope.request_key_root
        assert validated.as_dict() == scope.as_dict()
        keys = _current_root_keys(connection, scope.request_key_root)
        assert any("-migration-page-live-tail" in key for key in keys)
        assert supply.diagnostics["campaign_source_request_scope"] == scope.as_dict()
        assert supply.diagnostics["request_key_root"] == scope.request_key_root

    def test_missing_scope_still_fails_closed_when_root_is_present(self, database):
        path, _connection = database
        scope = _scope()
        kwargs = _permanent_kwargs(scope)
        kwargs.pop("campaign_source_request_scope")
        with pytest.raises(ValueError) as exc:
            run_persistent_eligible_token_supply(path, **kwargs)
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED

    def test_invalid_scope_still_fails_closed(self, database):
        path, _connection = database
        scope = _scope()
        kwargs = _permanent_kwargs(scope)
        kwargs["campaign_source_request_scope"] = {
            "scope_version": "NOT_A_SUPPORTED_SCOPE",
            "request_key_root": scope.request_key_root,
            "execution_id": scope.execution_id,
            "campaign_id": scope.campaign_id,
            "run_id": scope.run_id,
            "cycle_id": scope.cycle_id,
        }
        with pytest.raises(ValueError) as exc:
            run_persistent_eligible_token_supply(path, **kwargs)
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID

    def test_foreign_scope_still_fails_closed(self, database):
        path, _connection = database
        current = _scope()
        foreign = _scope(
            execution_id=FOREIGN_EXECUTION,
            campaign_id="foreign-campaign",
            run_id="foreign-run",
            cycle_id="foreign-cycle",
        )
        kwargs = _permanent_kwargs(current)
        kwargs["campaign_source_request_scope"] = foreign
        with pytest.raises(ValueError) as exc:
            run_persistent_eligible_token_supply(path, **kwargs)
        assert str(exc.value) == CAMPAIGN_SOURCE_REQUEST_SCOPE_PREFIX_MISMATCH

    def test_legacy_static_root_still_rejected(self, database):
        path, _connection = database
        scope = _scope()
        kwargs = _permanent_kwargs(scope)
        kwargs["campaign_source_request_scope"] = {
            "scope_version": scope.scope_version,
            "request_key_root": LEGACY_STATIC_REQUEST_KEY_ROOT,
            "execution_id": scope.execution_id,
            "campaign_id": scope.campaign_id,
            "run_id": scope.run_id,
            "cycle_id": scope.cycle_id,
        }
        kwargs["discovery_request_key_prefix"] = LEGACY_STATIC_REQUEST_KEY_ROOT
        kwargs["front_door_request_key_prefix"] = LEGACY_STATIC_REQUEST_KEY_ROOT
        with pytest.raises(ValueError) as exc:
            run_persistent_eligible_token_supply(path, **kwargs)
        assert str(exc.value) in {
            CAMPAIGN_SOURCE_REQUEST_SCOPE_INVALID,
            LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY,
        }

    def test_historical_foreign_root_rows_cannot_substitute_for_current_scope(
        self, database, monkeypatch
    ):
        path, connection = database
        scope = _scope()
        foreign = _scope(
            execution_id=FOREIGN_EXECUTION,
            campaign_id="foreign-campaign",
            run_id="foreign-run",
            cycle_id="foreign-cycle",
        )
        historical_id = _insert_request(
            connection, key=f"{foreign.request_key_root}-locator"
        )
        captured, wrapped = _capture_persistent_kwargs()
        observed: dict[str, Any] = {}
        real_assemble = assemble_and_reconcile_campaign_source_requests

        def capturing_assemble(*args: Any, **kwargs: Any):
            observed["scope"] = kwargs.get("campaign_source_request_scope")
            recon = real_assemble(*args, **kwargs)
            observed["recon"] = recon
            return recon

        monkeypatch.setattr(
            eligible_supply_module,
            "run_persistent_eligible_token_supply",
            wrapped,
        )
        monkeypatch.setattr(
            "printer_v1.discovery.permanent_discovery_availability.assemble_and_reconcile_campaign_source_requests",
            capturing_assemble,
        )
        supply = build_graduated_supply(
            path,
            **_permanent_kwargs(scope),
        )

        received = validate_campaign_source_request_scope(observed["scope"])
        assert received.as_dict() == scope.as_dict()
        durable = [
            int(value)
            for value in (
                (observed["recon"] or {}).get("durable_campaign_request_ids") or ()
            )
        ]
        assert historical_id not in durable
        assert captured["campaign_source_request_scope"] is scope or (
            captured["campaign_source_request_scope"] == scope.as_dict()
        )
        assert supply.diagnostics["campaign_source_request_scope"] == scope.as_dict()


class TestNoCapabilityExpansion:
    def test_persistent_signature_and_freeze_ready_call_forward_scope(self):
        signature = inspect.signature(run_persistent_eligible_token_supply)
        assert "campaign_source_request_scope" in signature.parameters
        source = inspect.getsource(run_persistent_eligible_token_supply)
        assert "campaign_source_request_scope=campaign_source_request_scope" in source
        from printer_v1.operator_cli._graduated_supply_front_door_base import (
            build_graduated_supply as build_base_graduated_supply,
        )

        front = inspect.getsource(build_base_graduated_supply)
        assert "campaign_source_request_scope=scope_obj" in front

    def test_capacity_and_lock_invariants_unchanged(self):
        from printer_v1.discovery.eligible_token_supply import REQUIRED_TOKEN_CAPACITY
        from printer_v1.operator_cli._graduated_supply_front_door_base import (
            OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
        )

        assert REQUIRED_TOKEN_CAPACITY == 2
        assert MINIMUM_FREEZE_DEPTH == 4
        assert OPERATIONAL_GRADUATED_SUPPLY_KWARGS["front_door_max_candidates"] == 6
        text = Path("src/printer_v1/discovery/eligible_token_supply.py").read_text()
        assert "WINDOW_12H" not in text
        assert "WINDOW_24H" not in text
        assert "BUY_SIGNAL" not in text
        assert "paper_trade_execute" not in text
        campaign = Path(
            "src/printer_v1/operator_cli/authoritative_live_operational_campaign.py"
        ).read_text()
        assert "build_campaign_source_request_scope" in campaign
        assert "CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED" in Path(
            "src/printer_v1/discovery/permanent_discovery_availability.py"
        ).read_text()
