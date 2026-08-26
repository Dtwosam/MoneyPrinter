from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
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
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf"
)
AUTHORIZATION_RELATIVE_PATH = (
    f"{AUTHORIZATION_ROOT}/{AUTHORIZATION_ID}/final_authorization.json"
)
AUTHORIZATION_SHA256 = (
    "cb73dc97f4f9c23cbdfa25b945a35b2026db1fff0ecf9955222cd3394b476a13"
)
AUTHORIZATION_SIZE = 4407
FUTURE_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_07D92ADF_DISPOSITION_TESTONLY"
)

OLDER_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436"
)
EXPIRED_UNCONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a"
)
PRIOR_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T123555Z_95dc47dd"
)
SUPERSEDED_UNCONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260824T222638Z_17181afc"
)
AUG25_CONSUMED_AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd"
)

APPLICATION_ROOT = (
    Path.home()
    / "PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications"
    / AUTHORIZATION_ID
)
MARKER_SHA256 = (
    "49d4511d9b5ea189cf7a7477a3e472eefb77f8033c28c97fcc9fa2a5d0f40f31"
)
CHILD_TERMINAL_SHA256 = (
    "3ad233f8ab23296a7e6b49a6016edc12bb29aa5b27e83b3ba009013a4631da58"
)
WRAPPER_TERMINAL_SHA256 = (
    "bbb6ee316c89c82b0e7f63b383572ab39bf2cf60892ad58c0083f86ab36993ca"
)


class Consumed07d92adfHistoricalDispositionTests(unittest.TestCase):
    """Exact production-path historical disposition adoption for 07d92adf."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._portable_history = None
        real_authorization_path = REPOSITORY_ROOT / AUTHORIZATION_RELATIVE_PATH
        real_marker_path = APPLICATION_ROOT / "application-marker.json"
        real_child_path = APPLICATION_ROOT / "child-terminal.json"
        real_wrapper_path = APPLICATION_ROOT / "wrapper-terminal.json"
        if all(
            path.is_file()
            for path in (
                real_authorization_path,
                real_marker_path,
                real_child_path,
                real_wrapper_path,
            )
        ):
            cls.authorization_path = real_authorization_path
            cls.history_repository_root = REPOSITORY_ROOT
            cls.marker_path = real_marker_path
            cls.child_terminal_path = real_child_path
            cls.wrapper_terminal_path = real_wrapper_path
            cls.authorization_sha256 = AUTHORIZATION_SHA256
            cls.authorization_size = AUTHORIZATION_SIZE
            cls.marker_sha256 = MARKER_SHA256
            cls.child_terminal_sha256 = CHILD_TERMINAL_SHA256
            cls.wrapper_terminal_sha256 = WRAPPER_TERMINAL_SHA256
            cls.synthetic_untracked_history = False
        else:
            cls._portable_history = build_portable_four_token_history(
                target_id=AUTHORIZATION_ID,
                prior_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
                    PRIOR_CONSUMED_AUTHORIZATION_ID,
                    SUPERSEDED_UNCONSUMED_AUTHORIZATION_ID,
                ],
                package_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
                    PRIOR_CONSUMED_AUTHORIZATION_ID,
                    SUPERSEDED_UNCONSUMED_AUTHORIZATION_ID,
                    AUTHORIZATION_ID,
                ],
                application_consumed_ids=[
                    OLDER_CONSUMED_AUTHORIZATION_ID,
                    PRIOR_CONSUMED_AUTHORIZATION_ID,
                ],
                target_consumed=True,
                authorized_at="2026-08-25T10:58:52+00:00",
            )
            cls.authorization_path = cls._portable_history.authorization_path
            cls.history_repository_root = cls._portable_history.root
            cls.marker_path = cls._portable_history.marker_path
            cls.child_terminal_path = cls._portable_history.child_terminal_path
            cls.wrapper_terminal_path = cls._portable_history.wrapper_terminal_path
            cls.authorization_sha256 = cls._portable_history.authorization_sha256
            cls.authorization_size = cls._portable_history.authorization_size
            cls.marker_sha256 = cls._portable_history.marker_sha256
            cls.child_terminal_sha256 = cls._portable_history.child_terminal_sha256
            cls.wrapper_terminal_sha256 = cls._portable_history.wrapper_terminal_sha256
            cls.synthetic_untracked_history = True

        cls.authorization_bytes = cls.authorization_path.read_bytes()
        cls.authorization_document = json.loads(cls.authorization_bytes)
        cls.marker = json.loads(cls.marker_path.read_bytes())
        cls.child_terminal = json.loads(cls.child_terminal_path.read_bytes())
        cls.wrapper_terminal = json.loads(cls.wrapper_terminal_path.read_bytes())

        cls.future_ids = git_auth.validate_prior_authorizations_non_reusable(
            sorted(
                [
                    *cls.authorization_document[
                        "prior_authorizations_non_reusable"
                    ],
                    AUTHORIZATION_ID,
                    AUG25_CONSUMED_AUTHORIZATION_ID,
                ]
            ),
            current_authorization_id=FUTURE_AUTHORIZATION_ID,
        )

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
            tracked_operator_runs_paths=(
                set() if cls.synthetic_untracked_history else None
            ),
        )

    def test_exact_consumed_package_resolves_to_child_exited_nonzero(self) -> None:
        """RED before exact-ID adoption; GREEN only through production policy."""
        self.assertEqual(
            self.authorization_document["authorization_id"], AUTHORIZATION_ID
        )
        self.assertEqual(len(self.authorization_bytes), self.authorization_size)
        self.assertEqual(
            hashlib.sha256(self.authorization_bytes).hexdigest(),
            self.authorization_sha256,
        )
        self.assertEqual(
            stat.S_IMODE(self.authorization_path.stat().st_mode), 0o444
        )

        self.assertEqual(
            hashlib.sha256(self.marker_path.read_bytes()).hexdigest(),
            self.marker_sha256,
        )
        self.assertEqual(
            hashlib.sha256(self.child_terminal_path.read_bytes()).hexdigest(),
            self.child_terminal_sha256,
        )
        self.assertEqual(
            hashlib.sha256(self.wrapper_terminal_path.read_bytes()).hexdigest(),
            self.wrapper_terminal_sha256,
        )

        self.assertEqual(self.marker["authorization_id"], AUTHORIZATION_ID)
        self.assertEqual(
            self.marker["authorization_sha256"], self.authorization_sha256
        )
        self.assertEqual(self.child_terminal["authorization_id"], AUTHORIZATION_ID)
        self.assertTrue(self.child_terminal["marker_consumed"])
        self.assertEqual(self.child_terminal["process_exit_code"], 1)
        self.assertFalse(self.child_terminal["success"])
        self.assertEqual(
            self.wrapper_terminal["authorization_id"], AUTHORIZATION_ID
        )
        self.assertEqual(
            self.wrapper_terminal["terminal_classification"],
            "CHILD_EXITED_NONZERO",
        )
        self.assertEqual(self.wrapper_terminal["child_exit_code"], 1)

        self.assertEqual(
            git_auth._terminal_disposition_for(AUTHORIZATION_ID),
            "CONSUMED_CHILD_EXITED_NONZERO",
        )

        records = [
            record
            for record in self._real_history()
            if record["authorization_id"] == AUTHORIZATION_ID
        ]
        self.assertGreaterEqual(len(records), 1)
        for record in records:
            self.assertEqual(record["path"], AUTHORIZATION_RELATIVE_PATH)
            self.assertEqual(record["sha256"], self.authorization_sha256)
            self.assertEqual(record["size"], self.authorization_size)
            self.assertEqual(
                record["evidence_class"],
                git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
            )
            self.assertEqual(
                record["terminal_disposition"],
                "CONSUMED_CHILD_EXITED_NONZERO",
            )

    def test_unknown_lookalike_id_keeps_default_disposition(self) -> None:
        lookalike = f"{AUTHORIZATION_ID}_LOOKALIKE"
        self.assertEqual(
            git_auth._terminal_disposition_for(lookalike),
            git_auth.DEFAULT_TERMINAL_DISPOSITION,
        )

    def test_prior_exact_historical_dispositions_remain_distinct(self) -> None:
        expected = {
            OLDER_CONSUMED_AUTHORIZATION_ID: git_auth.DEFAULT_TERMINAL_DISPOSITION,
            EXPIRED_UNCONSUMED_AUTHORIZATION_ID: "BLOCKED_UNCONSUMED_SUPERSEDED",
            PRIOR_CONSUMED_AUTHORIZATION_ID: "CONSUMED_CHILD_EXITED_NONZERO",
            SUPERSEDED_UNCONSUMED_AUTHORIZATION_ID: "BLOCKED_UNCONSUMED_SUPERSEDED",
            AUTHORIZATION_ID: "CONSUMED_CHILD_EXITED_NONZERO",
        }
        for authorization_id, disposition in expected.items():
            with self.subTest(authorization_id=authorization_id):
                self.assertEqual(
                    git_auth._terminal_disposition_for(authorization_id),
                    disposition,
                )

    def test_future_non_reuse_root_is_derived_sorted_unique_and_complete(self) -> None:
        self.assertEqual(self.future_ids, tuple(sorted(self.future_ids)))
        self.assertEqual(len(self.future_ids), len(set(self.future_ids)))
        # Do not pin the historical trust-root cardinality; exact immutable IDs
        # are the contract and the set grows as new consumed packages are preserved.
        for required in (
            OLDER_CONSUMED_AUTHORIZATION_ID,
            EXPIRED_UNCONSUMED_AUTHORIZATION_ID,
            PRIOR_CONSUMED_AUTHORIZATION_ID,
            SUPERSEDED_UNCONSUMED_AUTHORIZATION_ID,
            AUTHORIZATION_ID,
            AUG25_CONSUMED_AUTHORIZATION_ID,
        ):
            self.assertIn(required, self.future_ids)

    def test_omitting_consumed_id_from_future_trust_root_fails_closed(self) -> None:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        approved_without_current = tuple(
            self.authorization_document["prior_authorizations_non_reusable"]
        )
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "unapproved historical authorization package",
        ):
            git_auth.enumerate_historical_authorization_evidence(
                repository_root=self.history_repository_root,
                current_authorization_id=FUTURE_AUTHORIZATION_ID,
                approved_historical_authorization_ids=approved_without_current,
                authorization_package_roots=profile.historical_authorization_package_roots,
                current_authorization_package_root=profile.authorization_package_root,
                tracked_operator_runs_paths=(
                    set() if self.synthetic_untracked_history else None
                ),
            )


if __name__ == "__main__":
    unittest.main()
