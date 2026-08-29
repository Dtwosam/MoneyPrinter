from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli.authorization_temporal_validity import (
    validate_authorization_temporal_validity,
)
from tests.support.four_token_historical_authorization_portable import (
    build_portable_four_token_history,
)


TARGET_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5"
OLDER_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7"
FUTURE_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_AUG28_DISPOSITION_TESTONLY"
EXPECTED_DISPOSITION = "CONSUMED_CHILD_EXITED_NONZERO"
EXPECTED_MIGRATION_ID = "MIGRATION_062_20260828T182504Z"
EXPECTED_MIGRATION_DIGEST = "fa617f77f288705e7e8a4d3676f78feee041f098292a59d431a60e66624bcd02"


class Aug28ConsumedAuthorizationHistoricalDispositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.history = build_portable_four_token_history(
            target_id=TARGET_ID,
            prior_ids=[OLDER_ID],
            package_ids=[OLDER_ID, TARGET_ID],
            application_consumed_ids=[OLDER_ID],
            target_consumed=True,
            authorized_at="2026-08-28T21:19:24+00:00",
        )
        cls.document = json.loads(cls.history.authorization_path.read_bytes())
        cls.marker = json.loads(cls.history.marker_path.read_bytes())
        cls.marker_sha_before = hashlib.sha256(cls.history.marker_path.read_bytes()).hexdigest()
        cls.future_ids = tuple(sorted([OLDER_ID, TARGET_ID]))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.history.close()

    @classmethod
    def _records(cls, *, approved_ids: tuple[str, ...] | None = None):
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        return git_auth.enumerate_historical_authorization_evidence(
            repository_root=cls.history.root,
            current_authorization_id=FUTURE_ID,
            approved_historical_authorization_ids=(
                cls.future_ids if approved_ids is None else approved_ids
            ),
            authorization_package_roots=profile.historical_authorization_package_roots,
            current_authorization_package_root=profile.authorization_package_root,
            tracked_operator_runs_paths=set(),
        )

    def test_exact_aug28_consumed_id_has_nonzero_child_disposition(self) -> None:
        records = [record for record in self._records() if record["authorization_id"] == TARGET_ID]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["terminal_disposition"], EXPECTED_DISPOSITION)

    def test_lookalike_id_keeps_default_disposition(self) -> None:
        lookalike = TARGET_ID + "_LOOKALIKE"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            auth_root = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root
            target = root / auth_root / lookalike / "final_authorization.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(self.history.authorization_path.read_bytes())
            records = git_auth.enumerate_historical_authorization_evidence(
                repository_root=root,
                current_authorization_id=FUTURE_ID,
                approved_historical_authorization_ids=(lookalike,),
                authorization_package_roots=(auth_root,),
                current_authorization_package_root=auth_root,
                tracked_operator_runs_paths=set(),
            )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["authorization_id"], lookalike)
        self.assertEqual(records[0]["terminal_disposition"], git_auth.DEFAULT_TERMINAL_DISPOSITION)

    def test_omitting_aug28_id_from_future_trust_root_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            git_auth.GitProvenanceAuthorizationError,
            "unapproved historical authorization package",
        ):
            self._records(approved_ids=(OLDER_ID,))

    def test_consumed_marker_and_temporal_validity_do_not_create_reuse(self) -> None:
        self.assertEqual(self.marker["authorization_id"], TARGET_ID)
        self.assertEqual(self.marker["allowed_invocation_count"], 1)
        for key in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            self.assertIs(self.marker[key], False)

        validity = validate_authorization_temporal_validity(
            self.document,
            now=datetime(2026, 8, 28, 22, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(validity["status"], "TEMPORALLY_VALID")
        self.assertEqual(
            hashlib.sha256(self.history.marker_path.read_bytes()).hexdigest(),
            self.marker_sha_before,
        )
        records = [record for record in self._records() if record["authorization_id"] == TARGET_ID]
        self.assertEqual(records[0]["terminal_disposition"], EXPECTED_DISPOSITION)

    def test_historical_ids_remain_distinct_and_current_migration_is_062(self) -> None:
        records = self._records()
        ids = {record["authorization_id"] for record in records}
        self.assertEqual(ids, {OLDER_ID, TARGET_ID})
        self.assertEqual(len({record["path"] for record in records}), len(records))

        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.current_migration_execution_id, EXPECTED_MIGRATION_ID)
        self.assertEqual(
            profile.current_migration_expected_inventory_sha256,
            EXPECTED_MIGRATION_DIGEST,
        )


if __name__ == "__main__":
    unittest.main()
