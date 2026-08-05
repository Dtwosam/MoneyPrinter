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
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
    production_runtime_constructor_identities,
)
from printer_v1.operator_cli.continuous_proof_evidence_retention import (
    FailureSafeProofRetention,
    capture_public_command_main,
    extract_proof_diagnostics,
    write_proof_diagnostic_artifacts,
)

import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
import test_v2_9_8b_token_slot_id_exact_public_composition as base
from tests.support.window_15m_measured_frozen_transports import (
    NetworkFreezeBundle,
    build_four_migration_cases,
)

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

        # Four ordinary-path migration cases (not pre-seeded graduated registry).
        migration_cases = build_four_migration_cases()
        mints = [str(case["mint"]) for case in migration_cases]
        pools = [str(case["pool"]) for case in migration_cases]
        network_freeze = NetworkFreezeBundle(migration_cases)

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

        # Controlled clock for 900 logical seconds.
        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        stage_records: list[dict] = []
        child_invocations: list[list[str]] = []
        network_hits: list[str] = []

        # Snapshot/context factories for lifecycle (frozen fixture bodies).
        snapshot_calls: list[str] = []
        pool_map = {mints[i]: pools[i] for i in range(4)}

        def _measured_context_factories(clock_obj):
            """Production-shaped context factories with holder-stage measured costs.

            The shared token-slot composition helpers omit
            ``underlying_operation_count``. Holder-stage accounting then fails
            closed with HOLDER_TRANSPORT_IDENTITY_ABSENT and blocks recon.
            """
            from printer_v1.sources.governed_execution import build_fixture_source_adapter

            base_factories = base.ExactPublicTokenSlotIdCompositionProof._context_factories(
                clock_obj
            )

            def safety(**kwargs):
                return build_fixture_source_adapter(
                    "goplus",
                    fixture_payload={
                        "token_mint": kwargs.get("token_mint"),
                        "mint_authority": None,
                        "freeze_authority": None,
                        "metadata_mutable": False,
                        "total_supply": "1000000000",
                        "top_10_holders": [{"percent": "3"} for _ in range(10)],
                        "lp_info": [{"locked": True}],
                        "risk_flags": [],
                        # Single GoPlus HTTP cost for holder-stage measurement.
                        "underlying_operation_count": 1,
                    },
                )

            def solana_rpc_holder(**kwargs):
                mint = kwargs.get("token_mint")
                return build_fixture_source_adapter(
                    "solana_rpc",
                    fixture_payload={
                        "token_mint": mint,
                        "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
                        "top_10_holder_percent": 40.0,
                        "holder_measurement_basis": "SOLANA_GET_TOKEN_LARGEST_ACCOUNTS",
                        "holder_measurement_limitations": [],
                        "holder_condition_reason": "HOLDER_CONDITION_MEASURED",
                        "rpc_method": "getTokenLargestAccounts+getTokenSupply",
                        "commitment": "finalized",
                        "underlying_operation_count": 2,
                        "request_kind": "holder_concentration_reference",
                    },
                )

            factories = dict(base_factories)
            factories["goplus"] = safety
            factories["solana_rpc_holder"] = solana_rpc_holder
            return factories

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
                        "context_adapter_factories": _measured_context_factories(clock),
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
            self.assertIn(
                "printer_v1.operator_cli.operational_memory_factory_command",
                command,
            )
            self.assertIn("run", command)
            self.assertIn("--operator-approved", command)

            from contextlib import ExitStack

            from printer_v1.operator_cli.authoritative_live_operational_campaign import (
                AuthoritativeLiveOperationalCampaignOwner,
            )

            original_run = AuthoritativeLiveOperationalCampaignOwner.run_operational
            artifact_root = root / "child-artifacts"
            artifact_root.mkdir(exist_ok=True)

            # Production network freezes: production transports emit measured
            # identities. Do not replace migration with a plain callable.
            freeze_patches = network_freeze.freeze()

            def counting_urlopen(*args, **kwargs):
                # Frozen lawful bodies only. Record unhandled hosts as escapes.
                request = args[0] if args else kwargs.get("url")
                url = (
                    getattr(request, "full_url", None)
                    or (
                        request.get_full_url()
                        if hasattr(request, "get_full_url")
                        else str(request or "")
                    )
                )
                text = str(url)
                known = (
                    "dexscreener.com",
                    "geckoterminal.com",
                    "coingecko.com",
                    "gopluslabs.io",
                    "jup.ag",
                    "helius",
                    "mainnet",
                    "solana.com",
                )
                if not any(host in text.lower() for host in known):
                    network_hits.append(text or "urlopen-unknown")
                return network_freeze._urlopen(*args, **kwargs)

            with ExitStack() as stack:
                stack.enter_context(
                    patch.object(
                        public_command, "AUTHORITATIVE_DB", disposable_db.resolve()
                    )
                )
                stack.enter_context(
                    patch.object(public_command, "ARTIFACT_ROOT", artifact_root)
                )
                stack.enter_context(
                    patch.object(
                        AuthoritativeLiveOperationalCampaignOwner,
                        "run_operational",
                        lifecycle_inject(original_run),
                    )
                )
                stack.enter_context(
                    patch(
                        "printer_v1.operator_cli.one_command_15m_factory._now",
                        clock.now,
                    )
                )
                stack.enter_context(
                    patch(
                        "printer_v1.sources.contracts.datetime",
                        e9._ClockDateTime,
                    )
                )
                for freeze_patch in freeze_patches:
                    # urlopen freeze is applied below with counting wrapper.
                    target = getattr(freeze_patch, "attribute", None) or str(
                        freeze_patch
                    )
                    if "urlopen" in str(getattr(freeze_patch, "target", target)):
                        continue
                    stack.enter_context(freeze_patch)
                stack.enter_context(
                    patch("urllib.request.urlopen", side_effect=counting_urlopen)
                )
                for k, v in env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = str(v)
                rc = capture_public_command_main(
                    public_command.main,
                    ["run", "--operator-approved"],
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    launcher_metadata_path=(
                        Path(stdout_path).parent / "child-launcher-metadata.json"
                    ),
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

        # Start external retention immediately after the one child returns.  The
        # unittest cleanup owner finalizes it before the disposable temp owner.
        RETAINED_PROOF_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        retained = RETAINED_PROOF_ROOT / f"{PROOF_EXECUTION_ID}_{stamp}"
        retention = FailureSafeProofRetention(
            retained_directory=retained,
            initial_artifact_sources={
                "child-stdout.txt": app / auth_id / "child-stdout.txt",
                "child-stderr.txt": app / auth_id / "child-stderr.txt",
                "wrapper-terminal.json": app / auth_id / "wrapper-terminal.json",
            },
        )
        retention.__enter__()
        ContinuousWrapperToMemoryProof.last_retained = retained  # type: ignore[attr-defined]

        def _finalize_retention_after_test() -> None:
            first_failure = None
            outcome = getattr(self, "_outcome", None)
            result_owner = getattr(outcome, "result", None)
            for collection_name in ("failures", "errors"):
                for failed_test, traceback_text in getattr(
                    result_owner, collection_name, ()
                ):
                    if failed_test is self:
                        first_failure = str(traceback_text).strip().splitlines()[-1]
                        break
                if first_failure is not None:
                    break
            package = retention.finalize(
                first_failure=first_failure,
                raise_on_missing=first_failure is None,
            )
            ContinuousWrapperToMemoryProof.last_hashes = package  # type: ignore[attr-defined]

        self.addCleanup(_finalize_retention_after_test)

        # One child launch, no retry.
        self.assertEqual(1, len(child_invocations))
        if int(result.get("child_exit_code") or 0) != 0:
            raise AssertionError(
                f"CHILD_NONZERO_RETURN:{result.get('child_exit_code')}"
            )
        self.assertEqual(0, result.get("automatic_retries", 0) if isinstance(result.get("automatic_retries"), int) else 0)
        self.assertTrue((app / auth_id / "application-marker.json").is_file())
        child_stdout_path = app / auth_id / "child-stdout.txt"
        child_terminal = retention.parse_and_preserve_child_terminal()

        # Zero unhandled external network escapes (frozen known hosts are allowed).
        self.assertEqual([], network_hits)

        # Capture freeze/RPC diagnostics for closeout when handoff is short.
        ContinuousWrapperToMemoryProof.last_freeze_rpc = list(  # type: ignore[attr-defined]
            network_freeze.rpc_calls
        )
        ContinuousWrapperToMemoryProof.last_freeze_http = list(  # type: ignore[attr-defined]
            network_freeze.http_calls
        )

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

        # Build later diagnostics in disposable staging; the retention owner has
        # already preserved raw streams and wrapper terminal externally.
        retention_staging = root / "retention-staging"
        retention_staging.mkdir(parents=True, exist_ok=False)

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

        summary_path = retention_staging / "proof-summary.json"
        summary_path.write_text(
            json.dumps(proof_summary, indent=2, sort_keys=True, default=str) + "\n"
        )
        terminal_path = app / auth_id / "wrapper-terminal.json"
        terminal_src = app / auth_id / "wrapper-terminal.json"
        self.assertTrue(terminal_src.is_file())

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

        report_reference = child_terminal.get("report") or {}
        campaign_report_path = Path(str(report_reference.get("artifact_path") or ""))
        self.assertTrue(campaign_report_path.is_file())
        campaign_report = json.loads(campaign_report_path.read_text(encoding="utf-8"))
        diagnostic_paths = write_proof_diagnostic_artifacts(
            extract_proof_diagnostics(campaign_report),
            output_directory=retention_staging,
        )
        artifact_sources = {
            "child-stdout.txt": app / auth_id / "child-stdout.txt",
            "child-stderr.txt": app / auth_id / "child-stderr.txt",
            "child-terminal.json": app / auth_id / "child-terminal.json",
            "wrapper-terminal.json": terminal_path,
            "campaign-terminal-report.json": campaign_report_path,
            "proof-summary.json": summary_path,
            **diagnostic_paths,
        }
        retention.add_artifacts(artifact_sources)
        hashes = retention.finalize()
        ContinuousWrapperToMemoryProof.last_hashes = hashes  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
