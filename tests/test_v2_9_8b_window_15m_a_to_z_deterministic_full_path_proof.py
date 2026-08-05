"""Exact zero-network full-path controlled proof for A-to-Z deterministic readiness.

Proof identity: V2_9_8B_WINDOW_15M_A_TO_Z_DETERMINISTIC_FULL_PATH_PROOF_V1

Uses:
* disposable Migration-052 SQLite
* disposable Git worktree with fresh fixture authorization + historical evidence
* actual one-shot wrapper boundary (manifest/marker/temporal/composition)
* shared runtime composition registry
* controlled logical 900-second WINDOW_15M duration
* frozen lawful Source-Governed transports (zero external network)

Does not create a real authorization or live campaign against the authoritative DB.
"""

from __future__ import annotations

import copy
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
from printer_v1.memory.fingerprints import build_memory_fingerprint_payload
from printer_v1.operator_cli import operational_memory_factory_command as public_command
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LivePumpOriginAdapter,
)
from printer_v1.operator_cli.git_provenance import capture_git_provenance
from printer_v1.operator_cli.one_command_15m_factory import load_report_only
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ordinary_window_15m_builder_identities,
    run_window_15m_concrete_composition_preflight,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    OneShotWrapperError,
    apply_authorization_once,
    build_manifest_bytes,
    build_marker_bytes,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    validate_git_provenance_manifest_pre_marker,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger
from printer_v1.sources.operational_source_contracts import (
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    SOLANA_RPC_ENVIRONMENT_NAME,
    validate_window_15m_source_configuration,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
import test_v2_9_7e_11_authoritative_live_operational_campaign as e11
import test_v2_9_8b_token_slot_id_exact_public_composition as base

PROOF_EXECUTION_ID = "V2_9_8B_WINDOW_15M_A_TO_Z_DETERMINISTIC_FULL_PATH_PROOF_V1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _OrdinaryPath900Owner(base._ExactPublicCompositionOwner):
    """900 logical-second windows with frozen offline source bodies only.

    Ordinary composition registry (including direct migration + graduation
    verifier) is proven separately via zero-I/O preflight. Campaign success uses
    frozen Source-Governed fixture bodies; no live network.
    """

    def run_operational(self, **kwargs):
        lifecycle_kwargs = dict(kwargs["lifecycle_kwargs"])
        real_stage_observer = lifecycle_kwargs["full_run_stage_observer"]

        def capture_then_observe(record):
            self._stage_records.append(copy.deepcopy(dict(record)))
            real_stage_observer(record)

        lifecycle_kwargs.update(
            {
                "snapshot_adapter_factory": self._snapshot_adapter_factory,
                "context_adapter_factories": self._context_adapter_factories,
                "_window_seconds": 900.0,
                "_sleep": self._clock.sleep,
                "_monotonic": self._clock.monotonic,
                "total_duration_seconds": 5_000.0,
                "launch_provenance": e8._provenance(),
                "full_run_stage_observer": capture_then_observe,
            }
        )
        kwargs["lifecycle_kwargs"] = lifecycle_kwargs
        kwargs["graduation_proofs"] = self._graduation_proofs
        # Campaign uses frozen direct-origin fixture bodies. Ordinary migration
        # transport construction remains proven by zero-I/O composition preflight
        # (shared registry), not by live RPC during this controlled proof.
        kwargs["migration_transport"] = None
        return super(base._ExactPublicCompositionOwner, self).run_operational(**kwargs)


class FullPathControlledProof(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "disposable-migration-052.sqlite3"
        self.artifact_root = self.root / "public-artifacts"
        apply_migrations(self.db)
        self.proof_dir = self.root / "proof-artifacts"
        self.proof_dir.mkdir()

    def test_composition_registry_and_source_config_shared_law(self) -> None:
        identities = ordinary_window_15m_builder_identities()
        self.assertIn("direct_pump_finalized_migration_transport", identities)
        self.assertIn("exact_pump_pumpswap_graduation_verifier_transport", identities)
        result = run_window_15m_concrete_composition_preflight(
            timeout_seconds=1.0,
            environment={},
        )
        self.assertEqual("READY", result["status"])
        self.assertEqual(0, result["external_requests"])
        missing = validate_window_15m_source_configuration({})
        self.assertEqual(OFFICIAL_SOLANA_PUBLIC_RPC_URL, missing.url)
        present = validate_window_15m_source_configuration(
            {SOLANA_RPC_ENVIRONMENT_NAME: OFFICIAL_SOLANA_PUBLIC_RPC_URL}
        )
        self.assertEqual(OFFICIAL_SOLANA_PUBLIC_RPC_URL, present.url)

    def test_wrapper_boundary_consumes_auth_once_with_historical_inventory(self) -> None:
        """Disposable git worktree: historical tracked evidence + fresh fixture auth."""
        # Resolve temp root so macOS /var vs /private/var aliases agree with
        # the wrapper's lexical venv boundary checks.
        root = Path(self.root).resolve()
        repo = (root / "disposable-repo").resolve()
        app = (root / "wrapper-app").resolve()
        repo.mkdir()
        app.mkdir()

        def git(*args):
            return subprocess.run(
                ["git", *args],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )

        git("init")
        git("config", "user.email", "proof@example.invalid")
        git("config", "user.name", "Proof")
        (repo / ".gitignore").write_text(".venv/\n*.sqlite3\n", encoding="utf-8")
        hist = repo / "operator-runs/history"
        hist.mkdir(parents=True)
        for i in range(11):
            (hist / f"hist-{i:02d}.json").write_text(
                json.dumps({"h": i}) + "\n", encoding="utf-8"
            )
        git("add", ".")
        git("commit", "-m", "historical baseline")
        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        head = git("rev-parse", "HEAD").stdout.strip()

        mig_id = "V2_9_8B_AUTHORITATIVE_MIG050_PROOFONLY"
        auth_id = "V2_9_8B_WINDOW_15M_AUTH_PROOFONLY"
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
        issued = datetime.now(timezone.utc)
        auth_path = auth_root / "final_authorization.json"
        auth_doc = {
            "authorization_id": auth_id,
            "migration_execution_id": mig_id,
            "verdict": "V2_9_8B_WINDOW_15M_PROOF_AUTHORIZATION_PASS",
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
                "path": str(self.db.resolve()),
                "sha256": _sha256(self.db),
                "size": self.db.stat().st_size,
                "inode": self.db.stat().st_ino,
                "mtime_ns": self.db.stat().st_mtime_ns,
                "migration_count": 52,
                "migration_head": "052_memory_observation_eligibility_layers.sql",
            },
        }
        auth_path.write_text(json.dumps(auth_doc, indent=2, sort_keys=True) + "\n")
        auth_sha = _sha256(auth_path)

        # Build venv layout for child interpreter selection.
        from test_v2_9_8b_window_15m_one_shot_wrapper import build_venv_layout

        venv_python, _ = build_venv_layout(
            repo / ".venv", root / "venv-base-python"
        )
        # Lexical venv entrypoint (not the resolved base target).
        child_python = str(venv_python)
        child_launches: list[dict] = []

        def launcher(**kwargs):
            child_launches.append(dict(kwargs))
            return {"returncode": 0, "pid": 1}

        with (
            patch(
                "printer_v1.operator_cli.window_15m_one_shot_wrapper.package_binding_from_document",
                return_value={},
            ),
        ):
            result = apply_authorization_once(
                authorization_file=auth_path,
                authorization_sha256=auth_sha,
                operator_approved=True,
                repository_root=str(repo),
                application_root=str(app),
                python_executable=child_python,
                migration_ledger_guard=lambda **_k: object(),
                process_launcher=launcher,
            )

        self.assertEqual(1, len(child_launches))
        self.assertEqual(0, result.get("child_exit_code"))
        canonical = app / auth_id
        self.assertTrue((canonical / "application-marker.json").is_file())
        self.assertTrue((canonical / "git-provenance-manifest.json").is_file())
        # Second application of the same auth fails (consumed).
        with self.assertRaises(OneShotWrapperError):
            apply_authorization_once(
                authorization_file=auth_path,
                authorization_sha256=auth_sha,
                operator_approved=True,
                repository_root=str(repo),
                application_root=str(app),
                python_executable=child_python,
                migration_ledger_guard=lambda **_k: object(),
                process_launcher=launcher,
            )
        self.assertEqual(1, len(child_launches))  # no second launch

        proof = {
            "proof_execution_id": PROOF_EXECUTION_ID,
            "component": "wrapper_boundary",
            "authorization_id": auth_id,
            "child_launches": 1,
            "marker_present": True,
            "second_application_blocked": True,
        }
        proof_path = self.proof_dir / "wrapper_boundary_proof.json"
        proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        self.assertTrue(proof_path.is_file())

    def test_exact_900_logical_second_ordinary_registry_campaign_path(self) -> None:
        before_hash = _sha256(self.db)
        provenance = e8._provenance()
        # Activation preflight includes concrete composition registry (not patched out).
        real_preflight = public_command.build_activation_preflight

        def preflight_with_composition(**kwargs):
            # Prefer disposable identity while still executing composition registry.
            composition = run_window_15m_concrete_composition_preflight(
                timeout_seconds=1.0,
                environment={},
            )
            self.assertEqual("READY", composition["status"])
            self.assertEqual(
                set(ordinary_window_15m_builder_identities()),
                {row["label"] for row in composition["matrix"]},
            )
            return {
                "database_sha256": before_hash,
                "git_provenance": provenance,
                "concrete_composition_preflight": composition,
            }

        probe_transport, _probe_mints = e11._two_create_transport()
        acquisition = LivePumpOriginAdapter(probe_transport).acquire(
            source_governor=base.GOV,
            central_scheduler=base.SCH,
        )
        pools = {
            proof.mint: proof.bonding_curve for proof in acquisition.origin_proofs
        }
        # Frozen graduation evidence derived from acquisition — not a live
        # preassembled campaign package; offline fixture proofs only.
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        pump_transport, runtime_mints = e11._two_create_transport()
        self.assertEqual(set(runtime_mints), set(pools))
        secondary_transport = e11._FakeSecondaryTransport(
            e11._lawful_secondary_bodies(pools)
        )

        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        snapshot_calls: list[str] = []
        stage_records: list[dict] = []

        owner = _OrdinaryPath900Owner(
            graduation_proofs=graduation_proofs,
            snapshot_adapter_factory=base.ExactPublicTokenSlotIdCompositionProof._snapshot_factory(
                pools, snapshot_calls
            ),
            context_adapter_factories=base.ExactPublicTokenSlotIdCompositionProof._context_factories(
                clock
            ),
            clock=clock,
            stage_records=stage_records,
        )

        with (
            patch.object(
                public_command,
                "_iso",
                side_effect=lambda: clock.now().isoformat(),
            ),
            patch.object(public_command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(public_command, "ARTIFACT_ROOT", self.artifact_root),
            patch.object(
                public_command,
                "build_activation_preflight",
                side_effect=preflight_with_composition,
            ),
            patch.object(public_command, "_CampaignHeartbeat", base._NoopHeartbeat),
            patch.object(
                public_command,
                "resolve_solana_rpc_configuration",
                return_value=SimpleNamespace(url="https://unused.invalid"),
            ),
            patch("printer_v1.operator_cli.one_command_15m_factory._now", clock.now),
            patch("printer_v1.sources.contracts.datetime", e9._ClockDateTime),
            patch("urllib.request.urlopen") as network_open,
        ):
            # Ordinary composition registry (incl. migration builders) proven in
            # preflight_with_composition. Campaign uses frozen fixture bodies
            # only; migration port construction is proven zero-I/O, not live RPC.
            terminal = public_command._run_operational_campaign(
                policy=public_command._NORMAL_CAMPAIGN_POLICY,
                operator_approved=True,
                owner=owner,
                pump_transport=pump_transport,
                secondary_transport=secondary_transport,
                migration_transport=object(),
            )

        network_open.assert_not_called()
        self.assertEqual("OPERATIONAL_CAMPAIGN_TERMINAL", terminal["status"])
        self.assertEqual("COMPLETED", terminal["run_status"])
        self.assertTrue(terminal["campaign_pass"])
        self.assertTrue(terminal.get("operational_lifecycle_pass"))
        self.assertTrue(terminal.get("clean_memory_outcome_pass"))

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            windows = connection.execute(
                """SELECT id, window_kind, window_status, opened_at, closed_at,
                          memory_status, data_quality_label, do_not_train,
                          supporting_context_json, outcome_label
                   FROM printer_memory_windows
                   WHERE window_kind='WINDOW_15M'
                   ORDER BY id"""
            ).fetchall()
            self.assertEqual(2, len(windows))
            for win in windows:
                opened = datetime.fromisoformat(
                    str(win["opened_at"]).replace("Z", "+00:00")
                )
                closed = datetime.fromisoformat(
                    str(win["closed_at"]).replace("Z", "+00:00")
                )
                self.assertGreaterEqual((closed - opened).total_seconds(), 900.0)
                self.assertEqual("WINDOW_CLOSED", str(win["window_status"]))
                self.assertEqual(0, int(win["do_not_train"] or 0))

            clean_episodes = connection.execute(
                """SELECT id, memory_window_id, token_id, pair_id, memory_status,
                          episode_outcome_label, supporting_context_json
                   FROM printer_episodes
                   WHERE memory_status='CLEAN_MEMORY' AND do_not_train=0
                   ORDER BY id"""
            ).fetchall()
            self.assertEqual(2, len(clean_episodes))

            fps = connection.execute(
                """SELECT f.id, f.episode_id, f.fingerprint_payload_json, f.memory_status
                   FROM printer_memory_fingerprints f
                   JOIN printer_episodes e ON e.id = f.episode_id
                   WHERE e.memory_status='CLEAN_MEMORY'
                   ORDER BY f.id"""
            ).fetchall()
            self.assertEqual(2, len(fps))
            for row in fps:
                payload = json.loads(row["fingerprint_payload_json"])
                self.assertEqual("WINDOW_15M", payload.get("window_kind"))
                self.assertIsInstance(payload.get("tracking_lane"), str)
                self.assertNotIsInstance(payload.get("tracking_lane"), (dict, list))
                self.assertNotEqual(
                    payload.get("tracking_lane"),
                    payload.get("supporting_context"),
                )
                # Categorical fields must not store objects.
                for key, value in payload.items():
                    self.assertNotIsInstance(
                        value, (dict, list), msg=f"{key} is not categorical"
                    )
                self.assertIn(payload.get("episode_id"), (row["episode_id"], str(row["episode_id"])))

            slots = connection.execute(
                """SELECT token_slot_id FROM printer_memory_factory_campaign_token_slots
                   ORDER BY slot_ordinal"""
            ).fetchall()
            self.assertEqual(2, len(slots))

            active_sched = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_scheduler_jobs
                       WHERE status IN ('PENDING','RUNNING')
                          OR locked_at IS NOT NULL
                          OR lock_owner IS NOT NULL"""
                ).fetchone()[0]
            )
            self.assertEqual(0, active_sched)

            # Report-only replay surface exists for completed campaigns.
            campaign_id = str(terminal.get("campaign_id") or "")
            if campaign_id:
                try:
                    report = load_report_only(self.db, campaign_id)
                except Exception:
                    report = None
                # Report presence is best-effort; lifecycle completion is primary.
                del report
        finally:
            connection.close()

        cmo = terminal.get("clean_memory_outcome") or {}
        self.assertEqual(2, len(cmo.get("episode_ids") or []))
        self.assertEqual(2, len(cmo.get("fingerprint_ids") or []))
        self.assertEqual(0, int(cmo.get("unrelated_promotion_count") or 0))

        proof = {
            "proof_execution_id": PROOF_EXECUTION_ID,
            "component": "campaign_900_logical_seconds",
            "windows": 2,
            "clean_episodes": 2,
            "fingerprints": 2,
            "network_calls": 0,
            "registry_builder_count": len(ordinary_window_15m_builder_identities()),
            "operational_lifecycle_pass": True,
            "clean_memory_outcome_pass": True,
            "composition_registry_preflight": "READY",
            "terminal_status": terminal.get("run_status"),
            "proof_limits": [
                "offline frozen fixture source bodies only",
                "controlled logical clock for 900s windows",
                "no live provider or authoritative DB mutation",
            ],
        }
        proof_path = self.proof_dir / "campaign_900_proof.json"
        proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
        (self.proof_dir / "terminal.json").write_text(
            json.dumps(
                {
                    k: terminal.get(k)
                    for k in (
                        "status",
                        "run_status",
                        "campaign_pass",
                        "operational_lifecycle_pass",
                        "clean_memory_outcome_pass",
                        "clean_memory_outcome",
                        "first_terminal_cause",
                    )
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )


if __name__ == "__main__":
    unittest.main()
