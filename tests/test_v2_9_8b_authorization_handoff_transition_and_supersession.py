"""Exact historical supersession and durable prospective handoff authority.

Read-only against immutable operator evidence. No authorization is created,
no runtime owner is called, and the authoritative database is never opened.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth

from tests.support.four_token_historical_authorization_portable import (
    build_portable_four_token_history,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHORIZATION_ROOT = (
    "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc"
)
AUTHORIZATION_RELATIVE_PATH = (
    f"{AUTHORIZATION_ROOT}/{AUTHORIZATION_ID}/final_authorization.json"
)
AUTHORIZATION_SHA256 = (
    "99d2759e14da7d50ac301699a021d92bd3be0e024d36ec2a171ef23ff78a3f80"
)
AUTHORIZATION_SIZE = 4344
AUTHORIZATION_MODE = 0o444
BOUND_HEAD = "ec59f29c79533a4b3612cce467ae604e70b5904b"
FUTURE_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_HANDOFF_TESTONLY"
)
OLDER_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436"
)
EXPIRED_UNCONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a"
)
LATEST_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd"
)
NEWER_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf"
)
AUG25_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd"
)
APPLICATION_NAMESPACE = Path(
    "/Users/Dtwo1/PrinterOperations/v2-9-8/"
    "four-token-standard-four-hour-one-shot-applications"
)
PRODUCTION_MANIFEST = (
    REPOSITORY_ROOT
    / "src/printer_v1/operator_cli/git_provenance_authorization_manifest.py"
)
HANDOFF_PATH = REPOSITORY_ROOT / "CURRENT_HANDOFF.md"
REQUIRED_NEXT_ACTION = (
    "V2-9.8B AUTHORIZATION HANDOFF-TRANSITION AND SUPERSESSION\n"
    "INDEPENDENT BOUNDED PROOF / ACTUAL PATCH INSPECTION ONLY"
)


class AuthorizationHandoffTransitionAndSupersessionTests(unittest.TestCase):
    """Production-path proof for one exact unconsumed superseded package."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._portable_history = None
        real_path = REPOSITORY_ROOT / AUTHORIZATION_RELATIVE_PATH
        if real_path.is_file():
            cls.authorization_path = real_path
            cls.history_repository_root = REPOSITORY_ROOT
            cls.application_namespace = APPLICATION_NAMESPACE
            cls.authorization_sha256 = AUTHORIZATION_SHA256
            cls.authorization_size = AUTHORIZATION_SIZE
        else:
            cls._portable_history = build_portable_four_token_history(
                target_id=AUTHORIZATION_ID,
                prior_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
                    LATEST_CONSUMED_AUTHORIZATION_ID,
                ],
                package_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
                    LATEST_CONSUMED_AUTHORIZATION_ID,
                    AUTHORIZATION_ID,
                ],
                application_consumed_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    LATEST_CONSUMED_AUTHORIZATION_ID,
                ],
                bound_head=BOUND_HEAD,
            )
            cls.authorization_path = cls._portable_history.authorization_path
            cls.history_repository_root = cls._portable_history.root
            cls.application_namespace = cls._portable_history.applications
            cls.authorization_sha256 = cls._portable_history.authorization_sha256
            cls.authorization_size = cls._portable_history.authorization_size
        cls.authorization_bytes = cls.authorization_path.read_bytes()
        cls.authorization_document = json.loads(cls.authorization_bytes)
        cls.future_ids = tuple(
            sorted(
                [
                    *cls.authorization_document[
                        "prior_authorizations_non_reusable"
                    ],
                    AUTHORIZATION_ID,
                    NEWER_CONSUMED_AUTHORIZATION_ID,
                    AUG25_CONSUMED_AUTHORIZATION_ID,
                ]
            )
        )
        cls.handoff_text = HANDOFF_PATH.read_text(encoding="utf-8")
        cls.production_source = PRODUCTION_MANIFEST.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._portable_history is not None:
            cls._portable_history.close()

    @classmethod
    def _real_history(cls) -> tuple[dict[str, object], ...]:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        return git_auth.enumerate_historical_authorization_evidence(
            repository_root=cls.history_repository_root,
            current_authorization_id=FUTURE_AUTHORIZATION_ID,
            approved_historical_authorization_ids=cls.future_ids,
            authorization_package_roots=profile.historical_authorization_package_roots,
            current_authorization_package_root=profile.authorization_package_root,
            tracked_operator_runs_paths=set(),
        )

    def _record(self, authorization_id: str) -> dict[str, object]:
        matches = [
            record
            for record in self._real_history()
            if record["authorization_id"] == authorization_id
        ]
        self.assertEqual(len(matches), 1, authorization_id)
        return matches[0]

    def test_exact_unconsumed_package_has_superseded_historical_disposition(
        self,
    ) -> None:
        """Break caught: the canonical exact-ID owner omits this disposition."""
        self.assertEqual(
            self.authorization_document["authorization_id"], AUTHORIZATION_ID
        )
        self.assertEqual(len(self.authorization_bytes), self.authorization_size)
        self.assertEqual(
            hashlib.sha256(self.authorization_bytes).hexdigest(),
            self.authorization_sha256,
        )
        self.assertEqual(
            stat.S_IMODE(self.authorization_path.stat().st_mode),
            AUTHORIZATION_MODE,
        )
        self.assertEqual(
            self.authorization_document["repository"]["head"], BOUND_HEAD
        )
        self.assertIn(
            "BLOCKED_UNCONSUMED_SUPERSEDED",
            git_auth.TERMINAL_DISPOSITION_VOCABULARY,
        )
        self.assertEqual(
            git_auth._POLICY_TERMINAL_DISPOSITIONS[AUTHORIZATION_ID],
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )
        self.assertEqual(
            self._record(AUTHORIZATION_ID),
            {
                "path": AUTHORIZATION_RELATIVE_PATH,
                "sha256": self.authorization_sha256,
                "size": self.authorization_size,
                "evidence_class": git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
                "authorization_id": AUTHORIZATION_ID,
                "terminal_disposition": "BLOCKED_UNCONSUMED_SUPERSEDED",
            },
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
        self.assertEqual(
            git_auth._terminal_disposition_for(wrong_id),
            git_auth.DEFAULT_TERMINAL_DISPOSITION,
        )

    def test_omitting_superseded_id_from_future_trust_root_fails_closed(
        self,
    ) -> None:
        """Break caught: policy registration creates directory-discovery trust."""
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        approved_without_target = tuple(
            self.authorization_document["prior_authorizations_non_reusable"]
        )
        self.assertNotIn(AUTHORIZATION_ID, approved_without_target)
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "unapproved historical authorization package",
        ):
            git_auth.enumerate_historical_authorization_evidence(
                repository_root=self.history_repository_root,
                current_authorization_id=FUTURE_AUTHORIZATION_ID,
                approved_historical_authorization_ids=approved_without_target,
                authorization_package_roots=(
                    profile.historical_authorization_package_roots
                ),
                current_authorization_package_root=(
                    profile.authorization_package_root
                ),
            )

    def test_policy_entry_does_not_bypass_package_sha_or_size_bindings(
        self,
    ) -> None:
        """Break caught: diagnostic adoption weakens an immutable binding."""
        latest_record = self._record(AUTHORIZATION_ID)
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            copied_package = root / AUTHORIZATION_RELATIVE_PATH
            copied_package.parent.mkdir(parents=True)
            shutil.copy2(self.authorization_path, copied_package)
            validated_paths = git_auth._validate_historical_authorization_evidence(
                {"historical_authorization_evidence": [latest_record]},
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
            wrong_size["size"] = self.authorization_size + 1
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

            copied_package.chmod(0o644)
            tampered = bytearray(self.authorization_bytes)
            tampered[0] = ord("[")
            copied_package.write_bytes(tampered)
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError, "SHA-256 mismatch"
            ):
                git_auth._validate_historical_authorization_evidence(
                    {"historical_authorization_evidence": [latest_record]},
                    root=root,
                    authorization_id=FUTURE_AUTHORIZATION_ID,
                    approved_historical_authorization_ids=[AUTHORIZATION_ID],
                    tracked_paths=set(),
                    current_manifest_paths=set(),
                    profile=profile,
                )

    def test_four_historical_authorizations_keep_distinct_records(self) -> None:
        """Break caught: a shared diagnostic collapses distinct histories."""
        older = self._record(OLDER_CONSUMED_AUTHORIZATION_ID)
        expired = self._record(EXPIRED_UNCONSUMED_AUTHORIZATION_ID)
        consumed = self._record(LATEST_CONSUMED_AUTHORIZATION_ID)
        superseded = self._record(AUTHORIZATION_ID)
        self.assertEqual(
            older["terminal_disposition"], git_auth.DEFAULT_TERMINAL_DISPOSITION
        )
        self.assertEqual(
            expired["terminal_disposition"], "BLOCKED_UNCONSUMED_SUPERSEDED"
        )
        self.assertEqual(
            consumed["terminal_disposition"], "CONSUMED_CHILD_EXITED_NONZERO"
        )
        self.assertEqual(
            superseded["terminal_disposition"], "BLOCKED_UNCONSUMED_SUPERSEDED"
        )
        identities = {
            older["authorization_id"],
            expired["authorization_id"],
            consumed["authorization_id"],
            superseded["authorization_id"],
        }
        self.assertEqual(len(identities), 4)
        paths = {
            older["path"],
            expired["path"],
            consumed["path"],
            superseded["path"],
        }
        self.assertEqual(len(paths), 4)
        hashes = {
            older["sha256"],
            expired["sha256"],
            consumed["sha256"],
            superseded["sha256"],
        }
        self.assertEqual(len(hashes), 4)
        sizes = {
            older["size"],
            expired["size"],
            consumed["size"],
            superseded["size"],
        }
        self.assertEqual(len(sizes), 4)
        self.assertTrue(
            (self.application_namespace / OLDER_CONSUMED_AUTHORIZATION_ID).is_dir()
        )
        self.assertTrue(
            (self.application_namespace / LATEST_CONSUMED_AUTHORIZATION_ID).is_dir()
        )
        self.assertFalse(
            (self.application_namespace / EXPIRED_UNCONSUMED_AUTHORIZATION_ID).exists()
        )
        self.assertFalse((self.application_namespace / AUTHORIZATION_ID).exists())

    def test_unconsumed_isolation_does_not_fabricate_marker_child_or_campaign(
        self,
    ) -> None:
        """Break caught: policy mapping invents consumption or runtime evidence."""
        package_dir = self.authorization_path.parent
        self.assertEqual(
            sorted(path.name for path in package_dir.iterdir()),
            ["final_authorization.json"],
        )
        application_dir = self.application_namespace / AUTHORIZATION_ID
        self.assertFalse(application_dir.exists())
        for name in (
            "application-marker.json",
            "git-provenance-manifest.json",
            "child-terminal.json",
            "wrapper-terminal.json",
        ):
            self.assertFalse((application_dir / name).exists(), name)
        record = self._record(AUTHORIZATION_ID)
        for forbidden in (
            "campaign_authorized",
            "reusable",
            "migration_execution_id",
            "marker_path",
            "child_terminal",
            "application_root",
        ):
            self.assertNotIn(forbidden, record)
        one_shot = self.authorization_document["one_shot_policy"]
        self.assertEqual(one_shot["allowed_invocation_count"], 1)
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(one_shot[flag], False, flag)

    def test_superseded_authorization_remains_historical_only(self) -> None:
        """Break caught: diagnostic history becomes current execution evidence."""
        record = self._record(AUTHORIZATION_ID)
        path = record["path"]
        self.assertEqual(
            record["evidence_class"],
            git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
        )
        live_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertNotEqual(live_head, BOUND_HEAD)
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

    def test_future_trust_root_is_derived_sorted_unique_and_complete(self) -> None:
        """Break caught: prospective history omits or duplicates an exact ID."""
        validated = git_auth.validate_prior_authorizations_non_reusable(
            list(self.future_ids),
            current_authorization_id=FUTURE_AUTHORIZATION_ID,
        )
        self.assertEqual(validated, tuple(sorted(validated)))
        self.assertEqual(len(validated), len(set(validated)))
        duplicate_count = len(validated) - len(set(validated))
        self.assertEqual(duplicate_count, 0)
        # Completeness is expressed by exact required identities, not a brittle
        # snapshot count that changes whenever a new consumed package is preserved.
        self.assertNotIn("TRUST_ROOT_COUNT", self.production_source)
        self.assertNotRegex(
            self.production_source,
            r"prior_authorizations_non_reusable.*=.*\b45\b",
        )
        for required in (
            OLDER_CONSUMED_AUTHORIZATION_ID,
            EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
            LATEST_CONSUMED_AUTHORIZATION_ID,
            AUTHORIZATION_ID,
            NEWER_CONSUMED_AUTHORIZATION_ID,
            AUG25_CONSUMED_AUTHORIZATION_ID,
        ):
            self.assertIn(required, validated)

    def test_terminal_disposition_owner_remains_exact_id_policy_map(self) -> None:
        """Break caught: a generic classifier or prefix matcher is introduced."""
        tree = ast.parse(self.production_source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_terminal_disposition_for"
        )
        source = ast.get_source_segment(self.production_source, function)
        self.assertIsNotNone(source)
        self.assertIn("_POLICY_TERMINAL_DISPOSITIONS.get(", source)
        self.assertNotIn("re.", source)
        self.assertNotIn("startswith", source)
        self.assertNotIn("regex", source.lower())
        self.assertEqual(
            git_auth._POLICY_TERMINAL_DISPOSITIONS[AUTHORIZATION_ID],
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )
        self.assertEqual(
            git_auth._POLICY_TERMINAL_DISPOSITIONS[
                EXPIRED_UNCONSUMED_AUTHORIZATION_ID
            ],
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )
        self.assertNotIn(
            OLDER_CONSUMED_AUTHORIZATION_ID,
            git_auth._POLICY_TERMINAL_DISPOSITIONS,
        )

    def test_handoff_encodes_transition_a_without_tracked_mutation(self) -> None:
        """Break caught: preparation PASS still requires a tracked rewrite."""
        self.assertIn("TRANSITION_A_INDEPENDENT_REVIEW_ONLY", self.handoff_text)
        self.assertIn("WITHOUT tracked mutation", self.handoff_text)
        self.assertIn(
            "FRESH EXACT-HEAD FOUR-TOKEN STANDARD-FOUR-HOUR 4/2/2\n"
            "AUTHORIZATION INDEPENDENT REVIEW ONLY",
            self.handoff_text,
        )
        self.assertIn("PREPARED / NOT_CONSUMED", self.handoff_text)
        self.assertIn("no marker exists", self.handoff_text)
        self.assertIn("no child exists", self.handoff_text)
        self.assertIn("no campaign exists", self.handoff_text)

    def test_handoff_encodes_transition_b_without_tracked_mutation(self) -> None:
        """Break caught: review PASS still requires a tracked rewrite."""
        self.assertIn("TRANSITION_B_SEPARATE_OPERATOR_START_ONLY", self.handoff_text)
        self.assertIn(
            "SEPARATE OPERATOR START OF THAT EXACT REVIEWED AUTHORIZATION",
            self.handoff_text,
        )
        self.assertIn("exact HEAD remains unchanged", self.handoff_text)
        self.assertIn("package integrity remains exact", self.handoff_text)
        self.assertIn("DB binding remains exact", self.handoff_text)
        self.assertIn("temporal validity remains true", self.handoff_text)
        self.assertGreaterEqual(self.handoff_text.count("WITHOUT tracked mutation"), 2)

    def test_handoff_encodes_fail_closed_block_forbidding_operator_start(
        self,
    ) -> None:
        """Break caught: drift or BLOCK still leaves start permitted."""
        self.assertIn(
            "TRANSITION_BLOCK_OPERATOR_START_FORBIDDEN", self.handoff_text
        )
        self.assertIn("must forbid operator start", self.handoff_text)
        for phrase in (
            "preparation BLOCKED",
            "review BLOCKED",
            "HEAD drift",
            "package drift",
            "DB drift",
            "evidence/trust-root drift",
            "schema blocker",
            "zero-state blocker",
            "host blocker",
            "temporal expiry",
            "existing marker/application/child/campaign",
        ):
            self.assertIn(phrase, self.handoff_text)
        self.assertIn(
            "No automatic replacement/retry/rerun/resume/restart/successor",
            self.handoff_text,
        )

    def test_transitions_do_not_apply_retroactively_to_17181afc(self) -> None:
        """Break caught: A/B become authority for the blocked historical package."""
        self.assertEqual(
            self.authorization_document["repository"]["head"], BOUND_HEAD
        )
        bound_handoff = subprocess.run(
            ["git", "show", f"{BOUND_HEAD}:CURRENT_HANDOFF.md"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertNotIn("TRANSITION_A_INDEPENDENT_REVIEW_ONLY", bound_handoff)
        self.assertNotIn("TRANSITION_B_SEPARATE_OPERATOR_START_ONLY", bound_handoff)
        self.assertIn(
            "AUTHORIZATION PREPARATION ONLY",
            bound_handoff,
        )
        live_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertNotEqual(live_head, BOUND_HEAD)
        self.assertIn(
            "Transitions A and B MUST NOT apply retroactively",
            self.handoff_text,
        )
        self.assertIn(AUTHORIZATION_ID, self.handoff_text)
        self.assertIn(BOUND_HEAD, self.handoff_text)
        self.assertIn(
            "That HEAD did not contain this prospective authority chain",
            self.handoff_text,
        )
        self.assertIn(
            "This handoff must not be read as authority to review, mark, apply, "
            "or start",
            self.handoff_text,
        )
        self.assertEqual(
            git_auth._POLICY_TERMINAL_DISPOSITIONS[AUTHORIZATION_ID],
            "BLOCKED_UNCONSUMED_SUPERSEDED",
        )

    def test_future_path_requires_no_tracked_handoff_mutation_after_preparation(
        self,
    ) -> None:
        """Break caught: later start still depends on a post-package rewrite."""
        self.assertIn(
            "IMMEDIATE NEXT ACTION AFTER THIS IMPLEMENTATION LANE IS LATER "
            "CLOSED/REREADIED",
            self.handoff_text,
        )
        self.assertIn("fresh authorization preparation only", self.handoff_text)
        self.assertIn(
            "later rereadiness checkpoint containing prospective A/B/BLOCK clauses",
            self.handoff_text,
        )
        self.assertIn("replacement authorization preparation", self.handoff_text)
        self.assertIn("package binds that exact unchanged HEAD", self.handoff_text)
        self.assertIn("create-once marker", self.handoff_text)
        self.assertIn("exactly one child", self.handoff_text)
        self.assertIn(
            "No tracked handoff mutation is required between package "
            "preparation and\noperator start.",
            self.handoff_text,
        )
        self.assertIn(REQUIRED_NEXT_ACTION, self.handoff_text)
        self.assertIn(
            "It may not change implementation, prepare a\n"
            "replacement authorization, independently review, mark, apply, or run",
            self.handoff_text,
        )

    def test_runtime_authority_remains_isolated_from_handoff_and_disposition(
        self,
    ) -> None:
        """Break caught: historical policy or handoff text drives runtime."""
        src_root = REPOSITORY_ROOT / "src" / "printer_v1"
        current_handoff_hits = []
        superseded_hits = []
        for path in sorted(src_root.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            relative = str(path.relative_to(REPOSITORY_ROOT))
            if "CURRENT_HANDOFF.md" in text:
                current_handoff_hits.append(relative)
            if AUTHORIZATION_ID in text:
                superseded_hits.append(relative)
        self.assertEqual(current_handoff_hits, [])
        self.assertEqual(
            superseded_hits,
            ["src/printer_v1/operator_cli/git_provenance_authorization_manifest.py"],
        )
        self.assertIn(
            f'"{AUTHORIZATION_ID}": (\n'
            '        "BLOCKED_UNCONSUMED_SUPERSEDED"\n'
            "    )",
            self.production_source,
        )
        self.assertNotIn("CURRENT_HANDOFF.md", self.production_source)
        self.assertNotIn("TRANSITION_A_INDEPENDENT_REVIEW_ONLY", self.production_source)
        self.assertNotIn("state machine", self.production_source.lower())
        for owner in (
            "src/printer_v1/scheduler",
            "src/printer_v1/source_governor",
            "src/printer_v1/memory",
            "src/printer_v1/retrieval",
            "src/printer_v1/paper",
        ):
            owner_path = REPOSITORY_ROOT / owner
            if not owner_path.exists():
                continue
            for path in owner_path.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(AUTHORIZATION_ID, text)
                self.assertNotIn("_POLICY_TERMINAL_DISPOSITIONS", text)
                self.assertNotIn("CURRENT_HANDOFF.md", text)
        self.assertIn("validate_git_provenance_manifest_pre_marker", self.production_source)
        self.assertIn("validate_git_provenance_authorization", self.production_source)

    def test_permanent_locks_remain_encoded_in_handoff(self) -> None:
        """Break caught: implementation text loosens a V1 lock."""
        self.assertIn(
            "Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/\n"
            "signing/real funds/live execution. No paid API dependency. No scoring/ranking/\n"
            "confidence/weighted logic. No embeddings/vectors. No Source Governor or Central\n"
            "Scheduler bypass. Dirty memory remains excluded from retrieval and decisions.\n"
            "`WINDOW_5M_MICRO_EVENT` remains support-only. Cycle 3, 12h/24h, retrieval,\n"
            "BUY/SELL/HOLD, positions, trade events, paper audits, and PnL remain locked.",
            self.handoff_text,
        )


if __name__ == "__main__":
    unittest.main()
