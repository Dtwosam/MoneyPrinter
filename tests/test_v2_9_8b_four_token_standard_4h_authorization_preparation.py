"""Offline contract for non-consuming four-token Standard-4H preparation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess

import pytest

from printer_v1.operator_cli import (
    four_token_standard_four_hour_one_shot_wrapper as operational,
)
from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth


MODULE_NAME = (
    "printer_v1.operator_cli.four_token_standard_four_hour_authorization_preparation"
)
AUTHORIZATION_ID = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260905T010101Z_00000001"
MIGRATION_EXECUTION_ID = "MIGRATION_062_TESTONLY"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_production_preparation_owner_exists_for_four_token_standard_4h() -> None:
    """Catches removal of the production, non-fixture preparation boundary."""
    assert importlib.util.find_spec(MODULE_NAME) is not None
    preparation = importlib.import_module(MODULE_NAME)
    assert callable(
        getattr(
            preparation,
            "prepare_four_token_standard_four_hour_authorization",
            None,
        )
    )


class DisposableFourTokenPreparationRepository:
    """A disposable Git repository with one profile-pinned migration package."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "repo"
        self.root.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Preparation Tests")
        (self.root / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("branch", "--show-current").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()
        self.db_path = tmp_path / "disposable-printer.sqlite3"
        self.db_path.write_bytes(b"disposable authorization binding only")

        production = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        migration_dir = (
            self.root
            / production.migration_package_root
            / MIGRATION_EXECUTION_ID
        )
        migration_dir.mkdir(parents=True)
        (migration_dir / "migration-result.json").write_text(
            '{"migration":"062-testonly"}\n', encoding="utf-8"
        )
        migration_file = migration_dir / "migration-result.json"
        migration_inventory = [
            {
                "path": migration_file.relative_to(self.root).as_posix(),
                "sha256": _sha256(migration_file),
                "size": migration_file.stat().st_size,
            }
        ]
        historical_root = "operator-runs/v2-9-8b-test-historical-migration"
        historical_id = "MIGRATION_061_TESTONLY"
        historical_dir = self.root / historical_root / historical_id
        historical_dir.mkdir(parents=True)
        (historical_dir / "historical-result.json").write_text(
            '{"migration":"061-testonly"}\n', encoding="utf-8"
        )
        historical_file = historical_dir / "historical-result.json"
        historical_inventory = [
            {
                "path": historical_file.relative_to(self.root).as_posix(),
                "sha256": _sha256(historical_file),
                "size": historical_file.stat().st_size,
            }
        ]
        self.profile = git_auth.GitAuthorizationProfile(
            command_mode=production.command_mode,
            authorization_package_root=production.authorization_package_root,
            authorization_package_kind=production.authorization_package_kind,
            manifest_schema_version=production.manifest_schema_version,
            historical_authorization_package_roots=(
                production.authorization_package_root,
            ),
            migration_package_root=production.migration_package_root,
            migration_package_kind=production.migration_package_kind,
            current_migration_execution_id=MIGRATION_EXECUTION_ID,
            current_migration_expected_file_count=1,
            current_migration_expected_inventory_sha256=(
                git_auth.compute_historical_migration_inventory_sha256(
                    package_root=production.migration_package_root,
                    execution_id=MIGRATION_EXECUTION_ID,
                    evidence_class=production.migration_package_kind,
                    files=migration_inventory,
                )
            ),
            historical_migration_packages=(
                git_auth.HistoricalMigrationPackage(
                    package_root=historical_root,
                    execution_id=historical_id,
                    expected_file_count=1,
                    expected_inventory_sha256=(
                        git_auth.compute_historical_migration_inventory_sha256(
                            package_root=historical_root,
                            execution_id=historical_id,
                            evidence_class=production.migration_package_kind,
                            files=historical_inventory,
                        )
                    ),
                    evidence_class=production.migration_package_kind,
                ),
            ),
        )

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        )

    def database_binding(self) -> dict[str, object]:
        info = self.db_path.stat()
        return {
            "path": str(self.db_path),
            "sha256": _sha256(self.db_path),
            "size": info.st_size,
            "inode": info.st_ino,
            "mtime_ns": info.st_mtime_ns,
            "migration_count": 62,
            "migration_head": "062_pre_admission_attempt_evidence.sql",
        }


@pytest.fixture
def disposable_repository(tmp_path: Path) -> DisposableFourTokenPreparationRepository:
    return DisposableFourTokenPreparationRepository(tmp_path)


def test_prepare_creates_one_valid_non_consuming_package(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches a preparation path that creates a marker, skips parity, or writes a bad document."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    db_before = disposable_repository.db_path.read_bytes()
    result = preparation.prepare_four_token_standard_four_hour_authorization(
        repository_root=disposable_repository.root,
        branch=disposable_repository.branch,
        head=disposable_repository.head,
        authoritative_database=disposable_repository.database_binding(),
        migration_execution_id=MIGRATION_EXECUTION_ID,
        prior_authorizations_non_reusable=(),
        authorization_id=AUTHORIZATION_ID,
        authorized_at=datetime.now(timezone.utc).isoformat(),
        validity_seconds=600,
        operator_approved=True,
        application_root=tmp_path / "applications",
        temporary_parent=tmp_path,
    )

    authorization_file = Path(result["authorization_file"])
    package_root = authorization_file.parent
    assert package_root == (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    )
    assert {item.name for item in package_root.iterdir()} == {"final_authorization.json"}
    assert result["authorization_id"] == AUTHORIZATION_ID
    assert result["authorization_sha256"] == _sha256(authorization_file)
    assert result["schema_version"] == (
        "PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1"
    )
    assert result["repository_branch"] == disposable_repository.branch
    assert result["repository_head"] == disposable_repository.head
    assert result["migration_execution_id"] == MIGRATION_EXECUTION_ID
    assert result["marker_created"] is False
    assert result["consumed"] is False
    assert result["application_created"] is False
    assert result["child_launched"] is False
    assert result["inventory_pre_marker_parity_PASS"] is True
    assert db_before == disposable_repository.db_path.read_bytes()
    assert not (tmp_path / "applications").exists()
    assert authorization_file.stat().st_mode & 0o222 == 0

    document = json.loads(authorization_file.read_text(encoding="utf-8"))
    validated = operational.validate_four_token_standard_four_hour_authorization_document(
        document
    )
    assert validated["authorized_command"] == {
        "mode": "four-token-standard-four-hour-run",
        "operator_approved": True,
    }
    assert validated["operational_policy"] == operational.exact_operational_policy()
    assert validated["one_shot_policy"] == {
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    payload, _ = operational.build_manifest_bytes(
        repository_root=disposable_repository.root,
        authorization_file=authorization_file,
        authorization_sha256=result["authorization_sha256"],
        created_at=document["authorized_at"],
    )
    assert payload["authorization_id"] == AUTHORIZATION_ID


def test_prepare_rejects_wrong_profile_migration_and_malformed_history(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches caller substitution of Migration-062 or the canonical history inventory."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    common = {
        "repository_root": disposable_repository.root,
        "branch": disposable_repository.branch,
        "head": disposable_repository.head,
        "authoritative_database": disposable_repository.database_binding(),
        "authorization_id": AUTHORIZATION_ID,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "validity_seconds": 600,
        "operator_approved": True,
        "application_root": tmp_path / "applications",
        "temporary_parent": tmp_path,
    }
    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            **common,
            migration_execution_id="MIGRATION_062_CALLER_SUBSTITUTION",
            prior_authorizations_non_reusable=(),
        )
    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            **common,
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=("PREVIOUS", "PREVIOUS"),
        )
    assert not (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    ).exists()


def test_prepare_rejects_omitted_historical_authorization_package(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches a prior-inventory omission that would reinterpret history as absent."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    prior_id = "V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260905T010102Z_00000002"
    prior_file = (
        disposable_repository.root
        / profile.authorization_package_root
        / prior_id
        / "final_authorization.json"
    )
    prior_file.parent.mkdir(parents=True)
    prior_file.write_text('{"historical":true}\n', encoding="utf-8")

    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=disposable_repository.database_binding(),
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )
    assert not (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    ).exists()


def test_prepare_never_overwrites_a_current_package(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches collision handling that overwrites or silently chooses a successor."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    existing = (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    )
    existing.mkdir(parents=True)
    sentinel = existing / "final_authorization.json"
    sentinel.write_text('{"sentinel":true}\n', encoding="utf-8")
    before = sentinel.read_bytes()

    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=disposable_repository.database_binding(),
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )
    assert sentinel.read_bytes() == before
    assert sorted(item.name for item in existing.parent.iterdir()) == [AUTHORIZATION_ID]


def test_preparation_api_has_no_policy_override_parameter() -> None:
    """Catches an API widening that lets callers supply a different operational policy."""
    preparation = importlib.import_module(MODULE_NAME)
    assert "operational_policy" not in inspect.signature(
        preparation.prepare_four_token_standard_four_hour_authorization
    ).parameters


def test_prepare_fails_if_final_authorization_cannot_be_made_read_only(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches a successful result whose final authorization remains writable."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    monkeypatch.setattr(preparation, "_make_read_only", lambda _path: None)

    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=disposable_repository.database_binding(),
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )


def test_prepare_removes_package_when_pre_marker_parity_fails(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches an applyable authorization left behind by a failed preparation."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )

    def reject_pre_marker(**_kwargs):
        raise git_auth.GitProvenanceAuthorizationError("forced parity failure")

    monkeypatch.setattr(
        preparation.git_auth,
        "validate_git_provenance_manifest_pre_marker",
        reject_pre_marker,
    )
    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=disposable_repository.database_binding(),
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )
    assert not (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    ).exists()


@pytest.mark.parametrize("path_kind", ("relative", "ancestor_symlink"))
def test_prepare_rejects_noncanonical_database_paths(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    path_kind: str,
) -> None:
    """Catches relative and symlinked DB paths that weaken exact binding."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    database = disposable_repository.database_binding()
    if path_kind == "relative":
        monkeypatch.chdir(tmp_path)
        database["path"] = disposable_repository.db_path.name
    else:
        alias = tmp_path / "database-alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        database["path"] = str(alias / disposable_repository.db_path.name)

    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=database,
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )


def test_prepare_rechecks_database_identity_before_publication(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Catches a DB replacement after initial binding but before package publication."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    real_validate = preparation._validate_database_binding
    call_count = 0

    def mutate_after_first_binding(raw):
        nonlocal call_count
        call_count += 1
        result = real_validate(raw)
        if call_count == 1:
            disposable_repository.db_path.write_bytes(b"changed after initial bind")
        return result

    monkeypatch.setattr(
        preparation, "_validate_database_binding", mutate_after_first_binding
    )
    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=disposable_repository.head,
            authoritative_database=disposable_repository.database_binding(),
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )
    assert call_count >= 2
    assert not (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    ).exists()


@pytest.mark.parametrize(
    ("field", "value"),
    (("head", "0" * 40), ("sha256", "0" * 64), ("size", -1)),
)
def test_prepare_rejects_dishonest_git_or_database_bindings(
    disposable_repository: DisposableFourTokenPreparationRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    """Catches trusting supplied Git/DB facts before a final package is created."""
    preparation = importlib.import_module(MODULE_NAME)
    profile = disposable_repository.profile
    monkeypatch.setattr(
        git_auth, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        operational, "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE", profile
    )
    monkeypatch.setattr(
        preparation,
        "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE",
        profile,
    )
    database = disposable_repository.database_binding()
    head = disposable_repository.head
    if field == "head":
        head = str(value)
    else:
        database[field] = value

    with pytest.raises(preparation.FourTokenAuthorizationPreparationError):
        preparation.prepare_four_token_standard_four_hour_authorization(
            repository_root=disposable_repository.root,
            branch=disposable_repository.branch,
            head=head,
            authoritative_database=database,
            migration_execution_id=MIGRATION_EXECUTION_ID,
            prior_authorizations_non_reusable=(),
            authorization_id=AUTHORIZATION_ID,
            authorized_at=datetime.now(timezone.utc).isoformat(),
            validity_seconds=600,
            operator_approved=True,
            application_root=tmp_path / "applications",
            temporary_parent=tmp_path,
        )
    assert not (
        disposable_repository.root
        / profile.authorization_package_root
        / AUTHORIZATION_ID
    ).exists()
