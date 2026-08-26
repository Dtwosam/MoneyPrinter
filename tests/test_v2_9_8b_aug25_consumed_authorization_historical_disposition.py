from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth


AUTHORIZATION_ROOT = (
    "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization"
)
AUTHORIZATION_ID = (
    "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T134723Z_4563a9dd"
)
FUTURE_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_FUTURE_AUG25_TESTONLY"


def _write_package(root: Path) -> Path:
    operator_runs = root / "operator-runs"
    operator_runs.mkdir(parents=True)
    package = root / AUTHORIZATION_ROOT / AUTHORIZATION_ID
    package.mkdir(parents=True)
    authorization = package / "final_authorization.json"
    authorization.write_bytes(b'{"immutable":"test-carrier-only"}\n')
    return authorization


def test_exact_aug25_consumed_id_has_child_exited_zero_disposition() -> None:
    assert (
        git_auth._terminal_disposition_for(AUTHORIZATION_ID)
        == "CONSUMED_CHILD_EXITED_ZERO"
    )
    assert (
        git_auth._terminal_disposition_for(f"{AUTHORIZATION_ID}_LOOKALIKE")
        == git_auth.DEFAULT_TERMINAL_DISPOSITION
    )


def test_future_history_must_explicitly_approve_aug25_consumed_package() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        authorization = _write_package(root)
        with pytest.raises(
            git_auth.GitProvenanceAuthorizationError,
            match="unapproved historical authorization package",
        ):
            git_auth.enumerate_historical_authorization_evidence(
                repository_root=root,
                current_authorization_id=FUTURE_ID,
                approved_historical_authorization_ids=[],
                tracked_operator_runs_paths=set(),
                authorization_package_roots=(AUTHORIZATION_ROOT,),
                current_authorization_package_root=AUTHORIZATION_ROOT,
            )

        records = git_auth.enumerate_historical_authorization_evidence(
            repository_root=root,
            current_authorization_id=FUTURE_ID,
            approved_historical_authorization_ids=[AUTHORIZATION_ID],
            tracked_operator_runs_paths=set(),
            authorization_package_roots=(AUTHORIZATION_ROOT,),
            current_authorization_package_root=AUTHORIZATION_ROOT,
        )
        assert records == (
            {
                "path": str(authorization.relative_to(root)),
                "sha256": git_auth._sha256_file(authorization),
                "size": authorization.stat().st_size,
                "evidence_class": git_auth.HISTORICAL_AUTHORIZATION_EVIDENCE_CLASS,
                "authorization_id": AUTHORIZATION_ID,
                "terminal_disposition": "CONSUMED_CHILD_EXITED_ZERO",
            },
        )
