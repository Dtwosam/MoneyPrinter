"""Raw offline transports through the disposable public four-token coordinator."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess


def test_raw_four_token_public_completion(tmp_path, monkeypatch):
    from printer_v1.operator_cli import operational_memory_factory_command as public
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli.campaign_supervision import renew_campaign_lease

    harness_path = Path(__file__).resolve().parents[1] / "scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py"
    spec = importlib.util.spec_from_file_location("four_token_offline_transports", harness_path)
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    fixture_call = harness._Checkpoint8DeterministicFixture.__call__

    def fixture_market_only(self, *args, **kwargs):
        # Lawful empty finalized-migration page; market nomination still
        # discovers the four exact pools and must verify their account bytes.
        if self.route == "top_level.migration_transport":
            self._count()
            return {"jsonrpc": "2.0", "id": 1, "result": [],
                    "response_bytes": 36, "transport_operations_used": 1}
        return fixture_call(self, *args, **kwargs)

    monkeypatch.setattr(harness._Checkpoint8DeterministicFixture, "__call__", fixture_market_only)
    gecko_body = harness._checkpoint8_gecko_pool_body

    def consistent_gecko(candidate):
        body = gecko_body(candidate)
        body["data"]["relationships"]["dex"]["data"]["id"] = "pumpswap"
        return body

    monkeypatch.setattr(harness, "_checkpoint8_gecko_pool_body", consistent_gecko)
    # New pools arrive before the scheduled second-cycle admission. Keep the
    # full identity catalog for account and ongoing lifecycle lookups.
    phase = {"elapsed": 0.0}

    def visible_nominees(candidates):
        if len(candidates) == 4:
            return candidates[:2] if phase["elapsed"] < 300 else candidates[2:]
        return candidates

    gecko_list = harness._checkpoint8_gecko_list_payload
    monkeypatch.setattr(
        harness, "_checkpoint8_gecko_list_payload",
        lambda candidates: gecko_list(visible_nominees(candidates)),
    )
    dex_body = harness._checkpoint8_dex_payload

    def dated_dex(candidates):
        body = dex_body(visible_nominees(candidates))
        for pair in body["pairs"]:
            pair["pairCreatedAt"] = int(datetime(2026, 8, 7, 11, tzinfo=timezone.utc).timestamp() * 1000)
        return body

    monkeypatch.setattr(harness, "_checkpoint8_dex_payload", dated_dex)
    source_root = tmp_path / "source"
    subprocess.run(
        ["git", "clone", "--quiet", "--local", "--shared",
         str(harness_path.parents[1]), str(source_root)], check=True,
    )
    source_patch = subprocess.check_output(
        ["git", "-C", str(harness_path.parents[1]), "diff", "--binary", "HEAD", "--", "src"],
    )
    if source_patch:
        subprocess.run(
            ["git", "-C", str(source_root), "apply", "--index"],
            input=source_patch, check=True,
        )
        subprocess.run(
            ["git", "-C", str(source_root), "-c", "user.name=Offline fixture",
             "-c", "user.email=offline@example.invalid", "commit", "--quiet",
             "-m", "Capture exact development source under test"], check=True,
        )
    head = subprocess.check_output(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True,
    ).strip()
    prepared = harness.prepare_checkpoint8_controlling_entry(
        tmp_path / "proof", proof_id="four-token-public-offline", git_head=head,
    )
    real_preflight = public.build_disposable_public_composition_preflight
    monkeypatch.setattr(
        public, "build_disposable_public_composition_preflight",
        lambda runtime: real_preflight(runtime, repository_root=source_root),
    )

    class Clock:
        elapsed = 0.0
        heartbeat = None
        next_renewal = 30.0

        def now(self):
            return datetime(2026, 8, 7, 12, tzinfo=timezone.utc) + timedelta(seconds=self.elapsed)

        def sleep(self, seconds):
            while seconds > 30:
                self.sleep(30)
                seconds -= 30
            self.elapsed += seconds
            phase["elapsed"] = self.elapsed
            if self.heartbeat is None or self.elapsed < self.next_renewal:
                return
            command = self.heartbeat.command
            renewal = renew_campaign_lease(
                command.db_path, supervision_id=command.supervision_id,
                campaign_id=command.campaign_id, configuration_id=command.configuration_id,
                run_id=command.run_id, owner_id=command.owner_id,
                lease_seconds=public.LEASE_SECONDS, now=self.now(),
            )
            assert renewal["renewal_confirmed"], renewal
            self.next_renewal = self.elapsed + 30

    clock = Clock()

    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = clock.now()
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    class DeterministicHeartbeat(public._CampaignHeartbeat):
        def start(self):
            clock.heartbeat = self

        def stop(self):
            clock.heartbeat = None
            super().stop()

    for module in (
        "operational_memory_factory_command", "campaign_supervision",
        "standard_4h_progression", "one_token_4h_runtime",
        "authoritative_live_operational_campaign",
    ):
        monkeypatch.setattr(f"printer_v1.operator_cli.{module}.datetime", ClockDateTime)
    monkeypatch.setattr("printer_v1.sources.contracts.datetime", ClockDateTime)
    monkeypatch.setattr("printer_v1.discovery.eligible_token_supply.datetime", ClockDateTime)

    def wait(seconds, abort_event):
        if abort_event is not None and abort_event.is_set():
            return True
        clock.sleep(seconds)
        return bool(abort_event is not None and abort_event.is_set())

    monkeypatch.setattr(
        "printer_v1.operator_cli.pre_lifecycle_persistent_refresh_owner.bounded_interruptible_wait",
        wait,
    )
    from printer_v1.discovery import memory_observation_activation as activation
    real_measure = activation.measure_freeze_ready_candidates

    def observe_measure(*args, **kwargs):
        result = real_measure(*args, **kwargs)
        with (tmp_path / "freeze-measurements.jsonl").open("a") as output:
            output.write(json.dumps(result.__dict__, default=str) + "\n")
        return result

    monkeypatch.setattr(activation, "measure_freeze_ready_candidates", observe_measure)
    monkeypatch.setattr(public, "_CampaignHeartbeat", DeterministicHeartbeat)
    monkeypatch.setattr(factory, "_now", clock.now)
    real_factory = factory.run_one_command_15m_factory

    def timed_factory(*args, **kwargs):
        kwargs.update(_sleep=clock.sleep, _monotonic=lambda: clock.elapsed)
        return real_factory(*args, **kwargs)

    monkeypatch.setattr(factory, "run_one_command_15m_factory", timed_factory)
    monkeypatch.setattr(
        "printer_v1.operator_cli.origin_lifecycle_campaign.run_one_command_15m_factory",
        timed_factory,
    )
    from printer_v1.operator_cli import later_cycle_graduated_supply as later_supply
    real_later_supply = later_supply.build_later_cycle_graduated_supply

    def observe_later_supply(*args, **kwargs):
        result = real_later_supply(*args, **kwargs)
        with (tmp_path / "later-supply.jsonl").open("a") as output:
            output.write(json.dumps(result.__dict__, default=str) + "\n")
        return result

    monkeypatch.setattr(later_supply, "build_later_cycle_graduated_supply", observe_later_supply)
    terminal = public.run_four_token_standard_four_hour_campaign(
        operator_approved=True, git_provenance_authorization=None,
        disposable_proof=prepared.runtime,
    )
    (tmp_path / "terminal.json").write_text(json.dumps(terminal, indent=2, default=str))
    assert terminal.get("campaign_pass") is True, terminal
    _assert_complete_proof(
        prepared.runtime.plan.resolved_db_path,
        prepared.runtime.plan.resolved_artifact_root,
    )


def _assert_complete_proof(db_path, artifact_root):
    from printer_v1.operator_cli import operational_memory_factory_command as public

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        assert dict(connection.execute(
            "SELECT window_kind, COUNT(*) FROM printer_episodes "
            "WHERE memory_quality_label='CLEAN_MEMORY' GROUP BY window_kind"
        ).fetchall()) == {"WINDOW_15M": 4, "WINDOW_1H": 4, "WINDOW_4H": 4}
        fingerprints = connection.execute(
            "SELECT e.id,COUNT(f.id) FROM printer_episodes e "
            "LEFT JOIN printer_memory_fingerprints f ON f.episode_id=e.id "
            "AND f.fingerprint_kind='STATIC_CONDITION_SUMMARY' "
            "WHERE e.memory_status='CLEAN_MEMORY' GROUP BY e.id"
        ).fetchall()
        assert len(fingerprints) == 12
        assert all(row[1] == 1 for row in fingerprints)
        assert connection.execute(
            "SELECT COUNT(*),COUNT(DISTINCT token_row_id),COUNT(DISTINCT cycle_id) "
            "FROM printer_memory_factory_campaign_token_slots"
        ).fetchone()[:] == (4, 4, 2)
        assert connection.execute(
            "SELECT attempt_state FROM printer_pre_admission_discovery_attempts"
        ).fetchall()[0][0] == "CONSUMED"
        for table, predicate in (
            ("printer_scheduler_jobs", "status IN ('PENDING','RUNNING','COOLDOWN') "
             "OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"),
            ("printer_memory_factory_run_steps", "step_status IN ('PENDING','RUNNING')"),
            ("printer_memory_factory_campaign_scheduler_work", "work_state IN ('PENDING','RUNNING','COOLDOWN')"),
            ("printer_memory_factory_campaign_windows", "window_kind IN ('WINDOW_12H','WINDOW_24H')"),
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}").fetchone()[0] == 0
        for table in (
            "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
            "printer_paper_decisions", "printer_paper_positions",
            "printer_paper_trade_events", "printer_paper_trade_audits",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        supervision = connection.execute(
            "SELECT supervision_state,terminal_status,cleanup_completed_at,lease_released_at "
            "FROM printer_memory_factory_campaign_supervision"
        ).fetchone()
        assert tuple(supervision[:2]) == ("TERMINAL", "COMPLETED")
        assert all(supervision[2:])
        rows = connection.execute(
            "SELECT report_json FROM printer_memory_factory_campaign_reports "
            "WHERE report_kind='TERMINAL'"
        ).fetchall()
        assert len(rows) == 1
        stored_report = json.loads(rows[0][0])
        report = stored_report["full_run_terminal_evidence"]
        assert report["campaign_pass"] is True
        accounting = report["terminal_accounting"]
        assert accounting["accounting_complete"] is True
        assert accounting["campaign_pass_eligible"] is True
        assert len(report["per_cycle_six_unit_reconciliation"]) == 2
        assert all(item["equal"] is True for item in report["per_cycle_six_unit_reconciliation"])
        campaign_id, run_id = connection.execute(
            "SELECT campaign_id,run_id FROM printer_memory_factory_campaign_runs"
        ).fetchone()
    digest_before = hashlib.sha256(Path(db_path).read_bytes()).hexdigest()
    artifacts_before = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path(artifact_root).rglob("*") if path.is_file()
    }
    replay = public.report_only(
        campaign_id=campaign_id, run_id=run_id,
        db_path=db_path, artifact_root=artifact_root,
    )
    assert replay["status"] == "REPORT_ONLY_COMPLETE", replay
    for counter in ("source_calls", "scheduler_runtime_calls", "database_writes"):
        assert replay[counter] == 0
    assert hashlib.sha256(Path(db_path).read_bytes()).hexdigest() == digest_before
    assert {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path(artifact_root).rglob("*") if path.is_file()
    } == artifacts_before
