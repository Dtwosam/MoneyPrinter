"""Focused contract for the dedicated four-token proof authorization profile.

Offline only. This file creates no authorization, starts no Printer process,
performs no source call, and mutates no authoritative database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import standard_four_hour_one_shot_wrapper as standard
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)


ORDINARY_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2"

NOW = datetime(2026, 8, 13, 22, 0, tzinfo=timezone.utc)

DATABASE = {
    "path": "/tmp/printer.sqlite3",
    "sha256": "6" * 64,
    "size": 4096,
    "inode": 7,
    "mtime_ns": 11,
    "migration_count": 55,
    "migration_head": "055_pre_admission_discovery_attempt_ownership.sql",
}


def _document(**overrides):
    document = four_token.fixture_authorization_document(
        branch="agent/test-branch",
        head="a" * 40,
        database=dict(DATABASE),
        authorized_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=12)).isoformat(),
    )
    document.update(overrides)
    return document


class FourTokenProofAuthorizationProfileTests(unittest.TestCase):
    def test_dedicated_proof_identities_are_exact(self) -> None:
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        self.assertEqual(
            profile.command_mode, "four-token-bounded-capacity-proof-run"
        )
        self.assertEqual(
            profile.authorization_package_root,
            "operator-runs/v2-9-8b-four-token-final-authorization",
        )
        self.assertEqual(
            profile.authorization_package_kind,
            "FOUR_TOKEN_PROOF_AUTHORIZATION_EVIDENCE",
        )
        self.assertEqual(
            profile.manifest_schema_version,
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V1",
        )
        self.assertEqual(
            four_token.FINAL_AUTHORIZATION_SCHEMA_VERSION,
            "PRINTER_V1_FOUR_TOKEN_PROOF_FINAL_AUTHORIZATION_V1",
        )
        self.assertEqual(
            four_token.WRAPPER_SCHEMA_VERSION,
            "PRINTER_V1_FOUR_TOKEN_PROOF_ONE_SHOT_WRAPPER_V1",
        )
        self.assertEqual(
            four_token.AUTHORIZED_COMMAND_MODE,
            "four-token-bounded-capacity-proof-run",
        )

    def test_proof_profile_is_resolvable_without_widening_existing_profiles(
        self,
    ) -> None:
        self.assertIs(
            git_auth._resolved_profile(
                git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
            ),
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
        )
        self.assertIs(
            git_auth._resolved_profile(None), git_auth.ORDINARY_AUTHORIZATION_PROFILE
        )
        self.assertEqual(
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.command_mode,
            "standard-four-hour-run",
        )
        self.assertNotEqual(
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.authorization_package_root,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE.authorization_package_root,
        )

    def test_exact_four_token_fixture_document_validates(self) -> None:
        validated = four_token.validate_four_token_proof_authorization_document(
            _document()
        )
        self.assertEqual(
            validated["authorized_command"]["mode"],
            "four-token-bounded-capacity-proof-run",
        )
        self.assertEqual(validated["proof_policy"]["configured_through_4h_tokens"], 4)
        self.assertEqual(validated["proof_policy"]["total_cycle_admission_ceiling"], 2)
        self.assertEqual(validated["proof_policy"]["tokens_per_cycle"], 2)

    def test_ordinary_and_standard_four_hour_documents_are_rejected(self) -> None:
        standard_document = standard.fixture_authorization_document(
            branch="agent/test-branch",
            head="a" * 40,
            database=dict(DATABASE),
            authorized_at=NOW.isoformat(),
            expires_at=(NOW + timedelta(hours=12)).isoformat(),
        )
        with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
            four_token.validate_four_token_proof_authorization_document(
                standard_document
            )
        ordinary_document = dict(standard_document)
        ordinary_document["schema_version"] = ORDINARY_SCHEMA_VERSION
        with self.assertRaises(four_token.FourTokenProofOneShotWrapperError):
            four_token.validate_four_token_proof_authorization_document(
                ordinary_document
            )

    def test_standard_four_hour_document_rejects_the_four_token_document(self) -> None:
        with self.assertRaises(standard.StandardFourHourOneShotWrapperError):
            standard.validate_standard_four_hour_authorization_document(_document())


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
