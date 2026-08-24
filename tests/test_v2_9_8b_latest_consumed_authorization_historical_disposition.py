"""Exact historical-disposition adoption for the latest consumed authority.

Read-only against immutable operator evidence.  No authorization is created,
no runtime owner is called, and the authoritative database is never opened.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import stat
import tempfile
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli.authorization_temporal_validity import (
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    ChildTerminalError,
    read_child_terminal_envelope,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_ROOT = (
    "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd"
)
AUTHORIZATION_RELATIVE_PATH = (
    f"{AUTHORIZATION_ROOT}/{AUTHORIZATION_ID}/final_authorization.json"
)
AUTHORIZATION_SHA256 = (
    "d76470f33838f4d3d05a3ea865940a2d52e96597b30d61d2ef3c19a99ef50a32"
)
FUTURE_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_DISPOSITION_TESTONLY"
)
OLDER_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436"
)
EXPIRED_UNCONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a"
)
APPLICATION_ROOT = Path(
    "/Users/Dtwo1/PrinterOperations/v2-9-8/"
    "four-token-standard-four-hour-one-shot-applications"
) / AUTHORIZATION_ID
MARKER_SHA256 = (
    "1ecb94577b08a1ab7cb5546a2f09a65f81373a9b819a9b1d21756f80632993f4"
)


class LatestConsumedAuthorizationHistoricalDispositionTests(unittest.TestCase):
    """Production-path proof for one exact immutable historical package."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.authorization_path = REPOSITORY_ROOT / AUTHORIZATION_RELATIVE_PATH
        cls.authorization_bytes = cls.authorization_path.read_bytes()
        cls.authorization_document = json.loads(cls.authorization_bytes)
        cls.future_ids = tuple(
            sorted(
                [
                    *cls.authorization_document[
                        "prior_authorizations_non_reusable"
                    ],
                    AUTHORIZATION_ID,
                ]
            )
        )
        cls.marker_path = APPLICATION_ROOT / "application-marker.json"
        cls.manifest_path = APPLICATION_ROOT / "git-provenance-manifest.json"
        cls.child_terminal_path = APPLICATION_ROOT / "child-terminal.json"
        cls.wrapper_terminal_path = APPLICATION_ROOT / "wrapper-terminal.json"
        cls.marker = json.loads(cls.marker_path.read_bytes())
        cls.child_terminal = json.loads(cls.child_terminal_path.read_bytes())
        cls.wrapper_terminal = json.loads(cls.wrapper_terminal_path.read_bytes())

    @classmethod
    def _real_history(cls) -> tuple[dict[str, object], ...]:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        return git_auth.enumerate_historical_authorization_evidence(
            repository_root=REPOSITORY_ROOT,
            current_authorization_id=FUTURE_AUTHORIZATION_ID,
            approved_historical_authorization_ids=cls.future_ids,
            authorization_package_roots=profile.historical_authorization_package_roots,
            current_authorization_package_root=profile.authorization_package_root,
        )

    def test_exact_latest_consumed_package_has_approved_historical_disposition(
        self,
    ) -> None:
        """Break caught: the canonical exact-ID owner omits this disposition."""
        self.assertEqual(
            self.authorization_document["authorization_id"], AUTHORIZATION_ID
        )
        self.assertEqual(len(self.authorization_bytes), 4281)
        self.assertEqual(
            hashlib.sha256(self.authorization_bytes).hexdigest(),
            AUTHORIZATION_SHA256,
        )
        self.assertEqual(
            stat.S_IMODE(self.authorization_path.stat().st_mode), 0o444
        )
        self.assertEqual(
            hashlib.sha256(self.marker_path.read_bytes()).hexdigest(),
            MARKER_SHA256,
        )
        self.assertEqual(self.marker["authorization_id"], AUTHORIZATION_ID)
        self.assertEqual(
            self.marker["authorization_sha256"], AUTHORIZATION_SHA256
        )
        self.assertEqual(
            hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            self.marker["manifest_sha256"],
        )
        self.assertEqual(self.child_terminal["process_exit_code"], 1)
        self.assertIs(self.child_terminal["success"], False)
        self.assertEqual(
            self.wrapper_terminal["terminal_classification"],
            "CHILD_EXITED_NONZERO",
        )
        records = [
            record
            for record in self._real_history()
            if record["authorization_id"] == AUTHORIZATION_ID
        ]
        self.assertEqual(
            records,
            [
                {
                    "path": AUTHORIZATION_RELATIVE_PATH,
                    "sha256": AUTHORIZATION_SHA256,
                    "size": 4281,
                    "evidence_class": (
                        git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS
                    ),
                    "authorization_id": AUTHORIZATION_ID,
                    "terminal_disposition": "CONSUMED_CHILD_EXITED_NONZERO",
                }
            ],
        )

    def test_wrong_id_with_equivalent_package_bytes_keeps_default_disposition(
        self,
    ) -> None:
        """Break caught: an exact policy entry generalizes to a lookalike ID."""
        wrong_id = f"{AUTHORIZATION_ID}_LOOKALIKE"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied = (
                root
                / AUTHORIZATION_ROOT
                / wrong_id
                / "final_authorization.json"
            )
            copied.parent.mkdir(parents=True)
            shutil.copy2(self.authorization_path, copied)
            records = git_auth.enumerate_historical_authorization_evidence(
                repository_root=root,
                current_authorization_id=FUTURE_AUTHORIZATION_ID,
                approved_historical_authorization_ids=[wrong_id],
                tracked_operator_runs_paths=set(),
                authorization_package_roots=(AUTHORIZATION_ROOT,),
                current_authorization_package_root=AUTHORIZATION_ROOT,
            )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["authorization_id"], wrong_id)
        self.assertEqual(
            records[0]["terminal_disposition"],
            git_auth.DEFAULT_TERMINAL_DISPOSITION,
        )

    def test_omitting_latest_id_from_future_trust_root_fails_closed(self) -> None:
        """Break caught: policy registration creates directory-discovery trust."""
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        approved_without_latest = tuple(
            self.authorization_document["prior_authorizations_non_reusable"]
        )
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "unapproved historical authorization package",
        ):
            git_auth.enumerate_historical_authorization_evidence(
                repository_root=REPOSITORY_ROOT,
                current_authorization_id=FUTURE_AUTHORIZATION_ID,
                approved_historical_authorization_ids=approved_without_latest,
                authorization_package_roots=(
                    profile.historical_authorization_package_roots
                ),
                current_authorization_package_root=(
                    profile.authorization_package_root
                ),
            )

    def test_policy_entry_does_not_bypass_package_marker_or_child_bindings(
        self,
    ) -> None:
        """Break caught: diagnostic adoption weakens an immutable binding."""
        latest_record = next(
            record
            for record in self._real_history()
            if record["authorization_id"] == AUTHORIZATION_ID
        )
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied_package = root / AUTHORIZATION_RELATIVE_PATH
            copied_package.parent.mkdir(parents=True)
            shutil.copy2(self.authorization_path, copied_package)
            manifest = {"historical_authorization_evidence": [latest_record]}
            validated_paths = git_auth._validate_historical_authorization_evidence(
                manifest,
                root=root,
                authorization_id=FUTURE_AUTHORIZATION_ID,
                approved_historical_authorization_ids=[AUTHORIZATION_ID],
                tracked_paths=set(),
                current_manifest_paths=set(),
                profile=profile,
            )
            self.assertEqual(validated_paths, (AUTHORIZATION_RELATIVE_PATH,))

            wrong_sha = json.loads(json.dumps(latest_record))
            wrong_sha["sha256"] = "0" * 64
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError, "SHA-256 mismatch"
            ):
                git_auth._validate_historical_authorization_evidence(
                    {"historical_authorization_evidence": [wrong_sha]},
                    root=root,
                    authorization_id=FUTURE_AUTHORIZATION_ID,
                    approved_historical_authorization_ids=[AUTHORIZATION_ID],
                    tracked_paths=set(),
                    current_manifest_paths=set(),
                    profile=profile,
                )

            wrong_size = json.loads(json.dumps(latest_record))
            wrong_size["size"] = 4282
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError, "size mismatch"
            ):
                git_auth._validate_historical_authorization_evidence(
                    {"historical_authorization_evidence": [wrong_size]},
                    root=root,
                    authorization_id=FUTURE_AUTHORIZATION_ID,
                    approved_historical_authorization_ids=[AUTHORIZATION_ID],
                    tracked_paths=set(),
                    current_manifest_paths=set(),
                    profile=profile,
                )

            marker_path = root / "application-marker.json"
            shutil.copy2(self.marker_path, marker_path)
            git_auth._validate_marker(
                marker_path,
                marker_sha256=MARKER_SHA256,
                authorization_id=AUTHORIZATION_ID,
                authorization_sha256=AUTHORIZATION_SHA256,
                manifest_sha256=self.marker["manifest_sha256"],
                allowed_file_set_sha256=self.marker["allowed_file_set_sha256"],
                branch=self.marker["repository_branch"],
                head=self.marker["repository_head"],
                required_mode="four-token-standard-four-hour-run",
            )
            tampered_marker = json.loads(json.dumps(self.marker))
            tampered_marker["manifest_sha256"] = "0" * 64
            marker_path.chmod(0o644)
            marker_path.write_text(
                json.dumps(tampered_marker, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError,
                "manifest_sha256 mismatch",
            ):
                git_auth._validate_marker(
                    marker_path,
                    marker_sha256=hashlib.sha256(marker_path.read_bytes()).hexdigest(),
                    authorization_id=AUTHORIZATION_ID,
                    authorization_sha256=AUTHORIZATION_SHA256,
                    manifest_sha256=self.marker["manifest_sha256"],
                    allowed_file_set_sha256=(
                        self.marker["allowed_file_set_sha256"]
                    ),
                    branch=self.marker["repository_branch"],
                    head=self.marker["repository_head"],
                    required_mode="four-token-standard-four-hour-run",
                )

            shutil.copy2(self.marker_path, marker_path)
            child_path = root / "child-terminal.json"
            copied_child = json.loads(json.dumps(self.child_terminal))
            copied_child["marker_path"] = str(marker_path.resolve())
            child_path.write_text(
                json.dumps(copied_child, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            read_child_terminal_envelope(
                child_path,
                expected_authorization_id=AUTHORIZATION_ID,
                expected_marker_path=marker_path,
                expected_marker_sha256=MARKER_SHA256,
                expected_exit_code=1,
                expected_mode="four-token-standard-four-hour-run",
            )
            copied_child["marker_sha256"] = "0" * 64
            child_path.write_text(
                json.dumps(copied_child, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ChildTerminalError, "marker SHA-256 binding mismatch"
            ):
                read_child_terminal_envelope(
                    child_path,
                    expected_authorization_id=AUTHORIZATION_ID,
                    expected_marker_path=marker_path,
                    expected_marker_sha256=MARKER_SHA256,
                    expected_exit_code=1,
                    expected_mode="four-token-standard-four-hour-run",
                )

    def test_three_historical_authorizations_keep_distinct_dispositions(self) -> None:
        """Break caught: a generic fallback collapses distinct histories."""
        by_id = {
            record["authorization_id"]: record["terminal_disposition"]
            for record in self._real_history()
        }
        self.assertEqual(
            by_id[OLDER_CONSUMED_AUTHORIZATION_ID],
            git_auth.DEFAULT_TERMINAL_DISPOSITION,
        )
        self.assertEqual(
            by_id[EXPIRED_UNCONSUMED_AUTHORIZATION_ID],
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )
        self.assertEqual(
            by_id[AUTHORIZATION_ID], "CONSUMED_CHILD_EXITED_NONZERO"
        )

    def test_latest_authorization_remains_historical_only_and_disjoint(self) -> None:
        """Break caught: diagnostic history becomes current execution evidence."""
        latest_record = next(
            record
            for record in self._real_history()
            if record["authorization_id"] == AUTHORIZATION_ID
        )
        path = latest_record["path"]
        self.assertEqual(
            latest_record["evidence_class"],
            git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
        )
        self.assertNotIn("campaign_authorized", latest_record)
        self.assertNotIn("reusable", latest_record)
        self.assertNotIn("migration_execution_id", latest_record)
        git_auth._reconcile_evidence_sets(
            current_manifest_paths=set(),
            historical_paths={path},
            visible_paths={path},
            ignored_paths=set(),
            tracked_paths=set(),
            inventory_paths={path},
            current_package_roots=(
                "operator-runs/current-migration/current",
                "operator-runs/current-authorization/current",
            ),
            sidecar_untracked_paths=(),
        )
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "duplicate path across current files and historical authorization",
        ):
            git_auth._reconcile_evidence_sets(
                current_manifest_paths={path},
                historical_paths={path},
                visible_paths={path},
                ignored_paths=set(),
                tracked_paths=set(),
                inventory_paths={path},
                current_package_roots=(
                    "operator-runs/current-migration/current",
                    "operator-runs/current-authorization/current",
                ),
                sidecar_untracked_paths=(),
            )

    def test_temporal_validity_never_reactivates_consumed_authorization(self) -> None:
        """Break caught: remaining clock validity overrides consumed history."""
        consumed_at = datetime.fromisoformat(
            self.marker["authorization_consumed_at"]
        )
        temporal = validate_authorization_temporal_validity(
            self.authorization_document,
            now=consumed_at + timedelta(minutes=1),
        )
        self.assertEqual(temporal["status"], "TEMPORALLY_VALID")
        self.assertGreater(temporal["remaining_seconds"], 0)
        self.assertEqual(self.marker["allowed_invocation_count"], 1)
        self.assertTrue(bool(self.marker["authorization_consumed_at"]))
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(self.marker[flag], False, flag)
        latest_record = next(
            record
            for record in self._real_history()
            if record["authorization_id"] == AUTHORIZATION_ID
        )
        self.assertEqual(
            latest_record["terminal_disposition"],
            "CONSUMED_CHILD_EXITED_NONZERO",
        )

    def test_future_trust_root_is_derived_sorted_unique_and_complete(self) -> None:
        """Break caught: prospective history omits or duplicates an exact ID."""
        validated = git_auth.validate_prior_authorizations_non_reusable(
            list(self.future_ids),
            current_authorization_id=FUTURE_AUTHORIZATION_ID,
        )
        self.assertEqual(validated, tuple(sorted(validated)))
        self.assertEqual(len(validated), len(set(validated)))
        self.assertEqual(len(validated), 43)
        for required in (
            OLDER_CONSUMED_AUTHORIZATION_ID,
            EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
            AUTHORIZATION_ID,
        ):
            self.assertIn(required, validated)


if __name__ == "__main__":
    unittest.main()
