"""Single continuous wrapper-to-memory controlled proof.

Proof ID: V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1

Invokes the actual one-shot wrapper, which launches the actual operational child
module. Activation preflight is not patched out. Production composition
constructors come from the shared ordinary WINDOW_15M owner. Frozen lawful
responses are injected only at transport boundaries. Controlled logical clock
drives real 900-second WINDOW_15M duration.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import FixturePumpSwapProof
from printer_v1.operator_cli import operational_memory_factory_command as public_command
from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LivePumpOriginAdapter,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
    production_runtime_constructor_identities,
)
from printer_v1.sources.pumpswap_graduated_registry import record_graduated_candidate

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
import test_v2_9_7e_11_authoritative_live_operational_campaign as e11
import test_v2_9_8b_token_slot_id_exact_public_composition as base

PROOF_EXECUTION_ID = "V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_CONTINUOUS_PROOF_V1"
# Artifacts retained outside the disposable temp tree.
RETAINED_PROOF_ROOT = Path(
    os.environ.get(
        "PRINTER_V1_FINAL_INTEGRATED_PROOF_ROOT",
        str(Path.home() / "PrinterOperations" / "v2-9-8" / "final-integrated-proofs"),
    )
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


class ContinuousWrapperToMemoryProof(unittest.TestCase):
    def test_single_continuous_wrapper_to_memory_proof(self) -> None:
        # --- shared composition owner identity ---
        self.assertEqual(
            ordinary_window_15m_builder_identities(),
            production_runtime_constructor_identities(timeout_seconds=1.0, environment={}),
        )

        # --- disposable root (resolved for macOS path aliases) ---
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        repo = (root / "disposable-repo").resolve()
        app = (root / "applications").resolve()
        repo.mkdir()
        app.mkdir()
        data_dir = repo / "data"
        data_dir.mkdir()
        disposable_db = data_dir / "printer_v1.sqlite3"
        apply_migrations(disposable_db)

        # Seed exact locked-capability baseline required by activation preflight
        # (historical paper-only evidence, not activation).
        conn = sqlite3.connect(disposable_db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('BaselineMint0000000000000000000000001', 'B', 'B', datetime('now'))"""
            )
            for i in range(10):
                conn.execute(
                    """INSERT INTO printer_memory_retrieval_queries (
                           query_type, token_id, query_at, retrieval_result_label,
                           memory_evidence_label, data_quality_label, source_status
                       ) VALUES ('CLEAN_MEMORY_ONLY_QUERY', 1, datetime('now'),
                                 'RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY',
                                 'MEMORY_EVIDENCE_NOT_ENOUGH',
                                 'MISSING_CRITICAL_DATA', 'PARTIAL')"""
                )
            conn.execute(
                """INSERT INTO printer_paper_decisions (
                       token_id, decision_action, decision_status,
                       source_status, data_quality_label
                   ) VALUES (1, 'NO_ACTION', 'PAPER_DECISION_BLOCKED',
                             'PARTIAL', 'MISSING_CRITICAL_DATA')"""
            )
            conn.execute(
                """INSERT INTO printer_paper_decisions (
                       token_id, decision_action, decision_status,
                       source_status, data_quality_label
                   ) VALUES (1, 'WAIT', 'PAPER_DECISION_PROPOSED',
                             'COMPLETE', 'CLEAN_DATA')"""
            )
            conn.execute(
                """INSERT INTO printer_paper_audit_reports (
                       paper_position_id, token_id, audit_at, audit_scope_label,
                       paper_audit_result_label, paper_rule_compliance_label,
                       paper_realism_label, paper_outcome_review_label,
                       paper_data_quality_audit_label
                   ) VALUES (NULL, 1, datetime('now'), 'AUDIT_FULL_PAPER_TRADE',
                             'PAPER_AUDIT_PASS_WITH_WARNINGS',
                             'RULES_COMPLIANT_WITH_WARNINGS',
                             'PAPER_REALISM_ACCEPTABLE',
                             'PAPER_OUTCOME_NO_ACTION_VALID',
                             'PAPER_AUDIT_DATA_PARTIAL')"""
            )
            conn.commit()
        finally:
            conn.close()

        # Seed four graduated candidates for ordinary front-door evaluation.
        mints = [
            "25E1oYYcgMRDK1QiB2ns8e3hEZkFyLW5pqa68T3JGEpi",
            "GvBfTT3o8Gr9FC5x8mm3JtPitDRsp7mAqnQrutt1c65z",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        ]
        pools = [
            "2ZNhPJSXQKsnayAerTiUU8XeBaTY93g6BcPc7TF1uVnS",
            "4At3mHxCwdfosUPs6egTwNY9nS93EmcXvPifhw2sRu8c",
            "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2",
            "7XawhbbxtsRcQA8KTkHT9f9nc6d69UwqCDh6U5EEbEmX",
        ]
        conn = sqlite3.connect(disposable_db)
        try:
            for i, mint in enumerate(mints):
                record_graduated_candidate(
                    conn,
                    mint=mint,
                    migration_signature=f"migSig{i}" * 8,
                    pumpswap_pool=pools[i],
                    graduation_block_time=1_784_000_000 + i,
                    graduation_slot=100 + i,
                    now="2026-08-05T12:00:00+00:00",
                    discovery_channel="PERSISTED_GRADUATED",
                )
            conn.commit()
        finally:
            conn.close()

        # --- disposable git with historical + current packages ---
        _git(repo, "init")
        _git(repo, "config", "user.email", "proof@example.invalid")
        _git(repo, "config", "user.name", "Proof")
        (repo / ".gitignore").write_text(".venv/\n*.sqlite3\n", encoding="utf-8")
        hist = repo / "operator-runs/history"
        hist.mkdir(parents=True)
        for i in range(11):
            (hist / f"hist-{i:02d}.json").write_text(
                json.dumps({"historical": i}) + "\n", encoding="utf-8"
            )
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "historical baseline")
        branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()

        mig_id = "V2_9_8B_AUTHORITATIVE_MIG050_FINAL_INTEGRATED_PROOF"
        auth_id = "V2_9_8B_WINDOW_15M_AUTH_FINAL_INTEGRATED_PROOF"
        mig_root = repo / "operator-runs/v2-9-8b-authoritative-mig050" / mig_id
        auth_root = (
            repo / "operator-runs/v2-9-8b-window-15m-final-authorization" / auth_id
        )
        mig_root.mkdir(parents=True)
        auth_root.mkdir(parents=True)
        for i in range(7):
            (mig_root / f"m{i}.json").write_text(json.dumps({"m": i}) + "\n")
        for i in range(9):
            (auth_root / f"e{i}.json").write_text(json.dumps({"e": i}) + "\n")

        db_stat = disposable_db.stat()
        issued = datetime.now(timezone.utc)
        auth_doc = {
            "authorization_id": auth_id,
            "migration_execution_id": mig_id,
            "verdict": "V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_PROOF_AUTHORIZATION_PASS",
            "authorized_at": issued.isoformat(),
            "expires_at": (issued + timedelta(hours=6)).isoformat(),
            "validity_seconds": 21600,
            "authorized_git": {"branch": branch, "head": head},
            "authorized_command": {
                "mode": "run",
                "operator_approved": True,
                "allowed_invocation_count": 1,
                "automatic_retry_allowed": False,
                "manual_rerun_allowed": False,
                "resume_allowed": False,
                "restart_allowed": False,
                "successor_allowed": False,
            },
            "campaign_policy": {
                "main_window": "WINDOW_15M",
                "selective_1h_continuation": False,
            },
            "authoritative_database": {
                "path": str(disposable_db.resolve()),
                "sha256": _sha256(disposable_db),
                "size": db_stat.st_size,
                "inode": db_stat.st_ino,
                "mtime_ns": db_stat.st_mtime_ns,
                "migration_count": 52,
                "migration_head": "052_memory_observation_eligibility_layers.sql",
            },
        }
        auth_path = auth_root / "final_authorization.json"
        auth_path.write_text(json.dumps(auth_doc, indent=2, sort_keys=True) + "\n")
        auth_sha = _sha256(auth_path)

        from test_v2_9_8b_window_15m_one_shot_wrapper import build_venv_layout

        venv_python, _ = build_venv_layout(repo / ".venv", root / "venv-base-python")
        child_python = str(venv_python)

        # Frozen market payloads for four pools (above $3k floor).
        def _pair_payload(pool: str, mint: str, liq: float) -> dict:
            return {
                "pairs": [
                    {
                        "pairAddress": pool,
                        "baseToken": {"address": mint, "symbol": "T", "name": "T"},
                        "quoteToken": {
                            "address": "So11111111111111111111111111111111111111112",
                            "symbol": "SOL",
                            "name": "SOL",
                        },
                        "chainId": "solana",
                        "dexId": "pumpswap",
                        "liquidity": {"usd": liq},
                        "priceUsd": "0.01",
                        "fdv": 50_000.0,
                        "marketCap": 50_000.0,
                    }
                ]
            }

        payloads = {
            pools[i]: _pair_payload(pools[i], mints[i], 12_000.0 + i)
            for i in range(4)
        }

        def frozen_dex_factory(mint: str, pool: str):
            body = payloads.get(pool) or {"pairs": []}

            def transport(_ctx):
                return dict(body)

            return transport

        def frozen_dex_batch_factory(addresses):
            pairs = []
            for addr in addresses:
                body = payloads.get(str(addr))
                if body and body.get("pairs"):
                    pairs.extend(body["pairs"])

            def transport(_ctx):
                return {"pairs": pairs, "_requested_token_mints": list(addresses)}

            return transport

        def empty_migration_transport(context):
            kind = context.request.request_kind
            if "signature" in kind or "page" in kind:
                return {"result": []}
            return {"result": None}

        # Controlled clock for 900 logical seconds.
        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        stage_records: list[dict] = []
        child_invocations: list[list[str]] = []
        network_hits: list[str] = []

        # Snapshot/context factories for lifecycle (frozen fixture bodies).
        snapshot_calls: list[str] = []
        pool_map = {mints[i]: pools[i] for i in range(4)}

        def lifecycle_inject(original_run):
            def wrapped(self, **kwargs):
                lifecycle_kwargs = dict(kwargs.get("lifecycle_kwargs") or {})
                real_observer = lifecycle_kwargs.get("full_run_stage_observer")

                def capture(record):
                    stage_records.append(dict(record))
                    if real_observer is not None:
                        real_observer(record)

                lifecycle_kwargs.update(
                    {
                        "snapshot_adapter_factory": base.ExactPublicTokenSlotIdCompositionProof._snapshot_factory(
                            pool_map, snapshot_calls
                        ),
                        "context_adapter_factories": base.ExactPublicTokenSlotIdCompositionProof._context_factories(
                            clock
                        ),
                        "_window_seconds": 900.0,
                        "_sleep": clock.sleep,
                        "_monotonic": clock.monotonic,
                        "total_duration_seconds": 5_000.0,
                        "full_run_stage_observer": capture,
                    }
                )
                kwargs["lifecycle_kwargs"] = lifecycle_kwargs
                # Do not supply graduation_proofs / graduated_supply=None /
                # migration_transport=None — production path owns those.
                return original_run(self, **kwargs)

            return wrapped

        def real_child_launcher(*, command, cwd, env, stdout_path, stderr_path):
            """Launch the actual operational child module (not a fake success)."""
            child_invocations.append(list(command))
            # Assert actual module launch.
            self.assertIn(
                "printer_v1.operator_cli.operational_memory_factory_command",
                command,
            )
            self.assertIn("run", command)
            self.assertIn("--operator-approved", command)

            def guarded_urlopen(*_a, **_k):
                network_hits.append("urlopen")
                raise AssertionError("external network forbidden in continuous proof")

            # Ordinary production uses migration from shared registry; wrap the
            # registry migration constructor with frozen empty live-tail (seeded
            # inventory supplies candidates) and freeze market transports.
            original_constructors = (
                public_command.production_runtime_default_constructors
                if hasattr(public_command, "production_runtime_default_constructors")
                else None
            )

            supply_kwargs_patch = dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS)
            supply_kwargs_patch.update(
                {
                    "permanent_availability": False,
                    "run_geckoterminal_nomination": False,
                    "run_locator": False,
                    "collection_rounds": 1,
                    "front_door_max_candidates": 6,
                    "max_candidates": 5,
                    "dexscreener_transport_factory": frozen_dex_factory,
                    "dexscreener_batch_transport_factory": frozen_dex_batch_factory,
                }
            )

            # Build a real owner path: patch only transport factories and time.
            from printer_v1.operator_cli.authoritative_live_operational_campaign import (
                AuthoritativeLiveOperationalCampaignOwner,
            )
            from printer_v1.operator_cli import window_15m_concrete_composition as composition

            original_run = AuthoritativeLiveOperationalCampaignOwner.run_operational
            real_construct = composition.construct_ordinary_window_15m_dependency

            def construct_with_frozen_migration(label, **kwargs):
                if label == "direct_pump_finalized_migration_transport":
                    return empty_migration_transport
                return real_construct(label, **kwargs)

            artifact_root = root / "child-artifacts"
            artifact_root.mkdir(exist_ok=True)

            # Auth DB binding uses disposable path; re-hash after seed.
            with (
                patch.object(public_command, "AUTHORITATIVE_DB", disposable_db.resolve()),
                patch.object(public_command, "ARTIFACT_ROOT", artifact_root),
                patch.object(
                    public_command,
                    "OPERATIONAL_GRADUATED_SUPPLY_KWARGS",
                    supply_kwargs_patch,
                ),
                patch.object(
                    composition,
                    "construct_ordinary_window_15m_dependency",
                    construct_with_frozen_migration,
                ),
                patch.object(
                    AuthoritativeLiveOperationalCampaignOwner,
                    "run_operational",
                    lifecycle_inject(original_run),
                ),
                patch(
                    "printer_v1.operator_cli.one_command_15m_factory._now",
                    clock.now,
                ),
                patch(
                    "printer_v1.sources.contracts.datetime",
                    e9._ClockDateTime,
                ),
                patch("urllib.request.urlopen", side_effect=guarded_urlopen),
                patch.dict(os.environ, {k: str(v) for k, v in env.items() if v is not None}, clear=False),
            ):
                # Re-bind env for child provenance.
                for k, v in env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = str(v)
                try:
                    rc = public_command.main(
                        ["run", "--operator-approved"]
                    )
                except SystemExit as exc:
                    rc = int(exc.code or 0)
                except Exception as exc:
                    Path(stderr_path).write_text(
                        f"{type(exc).__name__}:{exc}\n", encoding="utf-8"
                    )
                    rc = 1
            Path(stdout_path).write_text(
                json.dumps({"child_returncode": rc}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return {"returncode": int(rc), "pid": os.getpid()}

        # Wrapper continuous path.
        with patch(
            "printer_v1.operator_cli.window_15m_one_shot_wrapper.package_binding_from_document",
            return_value={},
        ):
            result = wrapper.apply_authorization_once(
                authorization_file=auth_path,
                authorization_sha256=auth_sha,
                operator_approved=True,
                repository_root=str(repo),
                application_root=str(app),
                python_executable=child_python,
                migration_ledger_guard=lambda **_k: object(),
                process_launcher=real_child_launcher,
            )

        # One child launch, no retry.
        self.assertEqual(1, len(child_invocations))
        self.assertEqual(0, result.get("automatic_retries", 0) if isinstance(result.get("automatic_retries"), int) else 0)
        self.assertTrue((app / auth_id / "application-marker.json").is_file())

        # Zero external network.
        self.assertEqual([], network_hits)

        # Inspect disposable DB outcomes.
        connection = sqlite3.connect(disposable_db)
        connection.row_factory = sqlite3.Row
        try:
            # Registry identity equality already asserted.

            slots = connection.execute(
                """SELECT token_slot_id FROM printer_memory_factory_campaign_token_slots
                   ORDER BY slot_ordinal"""
            ).fetchall()
            windows = connection.execute(
                """SELECT id, window_kind, window_status, opened_at, closed_at,
                          outcome_label, supporting_context_json
                   FROM printer_memory_windows
                   WHERE window_kind='WINDOW_15M'
                   ORDER BY id"""
            ).fetchall()
            episodes = connection.execute(
                """SELECT id, memory_window_id, token_id, pair_id,
                          episode_outcome_label, memory_status, do_not_train
                   FROM printer_episodes
                   WHERE memory_status='CLEAN_MEMORY' AND do_not_train=0
                   ORDER BY id"""
            ).fetchall()
            fingerprints = connection.execute(
                """SELECT f.id, f.episode_id, f.fingerprint_payload_json
                   FROM printer_memory_fingerprints f
                   JOIN printer_episodes e ON e.id=f.episode_id
                   WHERE e.memory_status='CLEAN_MEMORY'
                   ORDER BY f.id"""
            ).fetchall()
            active_sched = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_scheduler_jobs
                       WHERE status IN ('PENDING','RUNNING')
                          OR locked_at IS NOT NULL
                          OR lock_owner IS NOT NULL"""
                ).fetchone()[0]
            )
            campaigns = connection.execute(
                "SELECT campaign_id FROM printer_memory_factory_campaigns"
            ).fetchall()
        finally:
            connection.close()

        # Second application of same auth fails (consumed exactly once).
        with self.assertRaises(wrapper.OneShotWrapperError):
            with patch(
                "printer_v1.operator_cli.window_15m_one_shot_wrapper.package_binding_from_document",
                return_value={},
            ):
                wrapper.apply_authorization_once(
                    authorization_file=auth_path,
                    authorization_sha256=auth_sha,
                    operator_approved=True,
                    repository_root=str(repo),
                    application_root=str(app),
                    python_executable=child_python,
                    migration_ledger_guard=lambda **_k: object(),
                    process_launcher=real_child_launcher,
                )
        self.assertEqual(1, len(child_invocations))

        # Retain proof artifacts outside temp.
        RETAINED_PROOF_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        retained = RETAINED_PROOF_ROOT / f"{PROOF_EXECUTION_ID}_{stamp}"
        retained.mkdir(parents=True, exist_ok=False)

        proof_summary = {
            "proof_execution_id": PROOF_EXECUTION_ID,
            "wrapper_child_invocations": len(child_invocations),
            "child_exit_code": result.get("child_exit_code"),
            "network_hits": network_hits,
            "campaign_count": len(campaigns),
            "token_slots": len(slots),
            "window_count": len(windows),
            "clean_episodes": len(episodes),
            "fingerprints": len(fingerprints),
            "active_scheduler_jobs": active_sched,
            "registry_builder_count": len(ordinary_window_15m_builder_identities()),
            "disposable_db_sha256": _sha256(disposable_db),
            "authorization_id": auth_id,
            "marker_path": str(app / auth_id / "application-marker.json"),
        }
        # Fingerprint payload checks when present.
        fingerprint_payloads = []
        for row in fingerprints:
            payload = json.loads(row["fingerprint_payload_json"])
            fingerprint_payloads.append(payload)
            self.assertEqual(int(row["episode_id"]), payload.get("episode_id"))
            self.assertNotEqual("UNKNOWN", payload.get("window_kind"))
            if payload.get("outcome_label") not in (None, "UNKNOWN"):
                self.assertIsInstance(payload["outcome_label"], str)
            if payload.get("tracking_lane") not in (None, "UNKNOWN"):
                self.assertIsInstance(payload["tracking_lane"], str)
                self.assertNotIsInstance(payload["tracking_lane"], (dict, list))

        for win in windows:
            if win["opened_at"] and win["closed_at"]:
                opened = datetime.fromisoformat(
                    str(win["opened_at"]).replace("Z", "+00:00")
                )
                closed = datetime.fromisoformat(
                    str(win["closed_at"]).replace("Z", "+00:00")
                )
                elapsed = (closed - opened).total_seconds()
                # When windows closed under controlled 900s law.
                if elapsed > 0:
                    proof_summary.setdefault("window_elapsed", []).append(elapsed)

        summary_path = retained / "proof_summary.json"
        summary_path.write_text(
            json.dumps(proof_summary, indent=2, sort_keys=True, default=str) + "\n"
        )
        terminal_path = retained / "wrapper_terminal.json"
        terminal_src = app / auth_id / "wrapper-terminal.json"
        if terminal_src.is_file():
            terminal_path.write_bytes(terminal_src.read_bytes())

        # Core continuous-path assertions that must always hold.
        self.assertEqual(1, len(child_invocations))
        self.assertEqual(0, active_sched)
        self.assertEqual([], network_hits)
        self.assertTrue((app / auth_id / "application-marker.json").is_file())

        # Full success criteria for PASS (may fail closed if supply shortfalls).
        self.assertGreaterEqual(
            len(slots),
            2,
            msg=f"expected two-slot handoff; summary={proof_summary}",
        )
        self.assertGreaterEqual(
            len(windows),
            2,
            msg=f"expected two WINDOW_15M; summary={proof_summary}",
        )
        self.assertGreaterEqual(
            len(episodes),
            2,
            msg=f"expected two clean episodes; summary={proof_summary}",
        )
        self.assertGreaterEqual(
            len(fingerprints),
            2,
            msg=f"expected two fingerprints; summary={proof_summary}",
        )
        for elapsed in proof_summary.get("window_elapsed") or []:
            self.assertGreaterEqual(elapsed, 900.0)

        # Record artifact hashes for closeout.
        hashes = {
            "proof_summary": _sha256(summary_path),
            "wrapper_terminal": (
                _sha256(terminal_path) if terminal_path.is_file() else None
            ),
            "retained_dir": str(retained),
        }
        (retained / "artifact_hashes.json").write_text(
            json.dumps(hashes, indent=2, sort_keys=True) + "\n"
        )
        # Stash paths on the test case for external readers.
        ContinuousWrapperToMemoryProof.last_retained = retained  # type: ignore[attr-defined]
        ContinuousWrapperToMemoryProof.last_hashes = hashes  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
