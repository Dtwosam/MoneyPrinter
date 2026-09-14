"""Dedicated exact-one-migration authorization authority.

This module owns no Printer, campaign, Scheduler, or source authority.  Its
only mutating operation is an explicitly approved, marker-first application of
one immediate canonical SQLite migration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Callable, Mapping, Sequence

from printer_v1.db.migrate import (
    MIGRATIONS_DIR,
    apply_exact_migration,
    canonical_migration_names,
    parse_migration_ordinal,
)
from printer_v1.operator_cli.authorization_temporal_validity import (
    AuthorizationTemporalError,
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli.four_token_proof_zero_state_gate import (
    active_printer_runtime_processes,
    project_four_token_proof_zero_state,
)
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    inspect_authoritative_database,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    MIGRATION_064_REQUIRED_INDEXES,
    MIGRATION_064_REQUIRED_TABLES,
    MIGRATION_064_REQUIRED_TRIGGERS,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    _canonical_json_bytes,
    _fsync_directory,
    _make_read_only,
    _sha256_file,
    _write_exclusive,
)
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    validate_prior_authorizations_non_reusable,
)


MIGRATION_AUTHORIZATION_SCHEMA_VERSION = "PRINTER_V1_MIGRATION_ONE_SHOT_AUTHORIZATION_V1"
MIGRATION_AUTHORIZATION_KIND = "MIGRATION_ONLY_EXACT_ONE"
MIGRATION_AUTHORIZATION_VERDICT = "MIGRATION_ONE_SHOT_AUTHORIZATION_PASS"
MIGRATION_APPLICATION_MARKER_SCHEMA_VERSION = "PRINTER_V1_MIGRATION_ONE_SHOT_MARKER_V1"
MIGRATION_TERMINAL_EVIDENCE_SCHEMA_VERSION = "PRINTER_V1_MIGRATION_ONE_SHOT_TERMINAL_V1"
AUTHORIZATION_FILENAME = "migration_authorization.json"
MARKER_FILENAME = "migration_application_marker.json"
TERMINAL_FILENAME = "migration_terminal_evidence.json"
DEFAULT_PACKAGE_ROOT = Path.home() / "PrinterOperations" / "v2-9-8" / "migration-one-shot-authorizations"
DEFAULT_MARKER_ROOT = Path.home() / "PrinterOperations" / "v2-9-8" / "migration-one-shot-markers"
DEFAULT_TERMINAL_ROOT = Path.home() / "PrinterOperations" / "v2-9-8" / "migration-one-shot-terminal-evidence"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_DATABASE_KEYS = {"path", "sha256", "size", "inode", "mtime_ns", "migration_count", "migration_head"}
_ONE_SHOT_POLICY = {"allowed_application_count": 1, "automatic_retry_allowed": False, "manual_rerun_allowed": False, "resume_allowed": False, "restart_allowed": False, "successor_inferred": False}
_DOCUMENT_KEYS = {"schema_version", "authorization_kind", "authorization_id", "verdict", "authorized_at", "expires_at", "validity_seconds", "repository", "authoritative_database", "target_migration", "expected_postcondition", "one_shot_policy", "prior_authorizations_non_reusable"}


class MigrationAuthorizationError(RuntimeError):
    """Fail-closed migration-only authorization fault."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MigrationAuthorizationError(message)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _object_contract(name: str) -> dict[str, list[str]]:
    if name == "064_four_token_started_lifecycle_zero_attempt_provenance.sql":
        return {"tables": sorted(MIGRATION_064_REQUIRED_TABLES), "triggers": sorted(MIGRATION_064_REQUIRED_TRIGGERS), "indexes": sorted(MIGRATION_064_REQUIRED_INDEXES)}
    return {"tables": [], "triggers": [], "indexes": []}


def _live_git_facts(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, timeout=5, check=False)
        if result.returncode:
            raise MigrationAuthorizationError(f"Git inspection failed: {result.stderr.strip()}")
        return result.stdout.strip()
    branch = run("branch", "--show-current")
    head = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    tracked_clean = not any(not line.startswith("?? ") for line in status.splitlines() if line)
    remote_head = run("ls-remote", "--heads", "origin", branch).split()[0]
    return {"branch": branch, "head": head, "remote_head": remote_head, "tracked_clean": tracked_clean}


def _migration_catalogue_is_clean(root: Path) -> bool:
    """Require migrations/ to exactly match the working tree's Git view."""
    commands = (
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "migrations"],
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", "migrations"],
    )
    for command in commands:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=5, check=False)
        if result.returncode or result.stdout.strip():
            return False
    return True


def _immutable_connection(path: Path):
    import sqlite3
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True, timeout=0.0)


def _zero_state(path: Path) -> dict[str, int]:
    connection = _immutable_connection(path)
    try:
        connection.execute("PRAGMA query_only=ON")
        return project_four_token_proof_zero_state(connection)
    finally:
        connection.close()


def _migration_objects(path: Path, names: Sequence[str]) -> list[str]:
    connection = _immutable_connection(path)
    try:
        connection.execute("PRAGMA query_only=ON")
        if not names:
            return []
        placeholders = ",".join("?" for _ in names)
        return [str(row[0]) for row in connection.execute(f"SELECT name FROM sqlite_master WHERE name IN ({placeholders}) ORDER BY name", tuple(names)).fetchall()]
    finally:
        connection.close()


def _database_binding(path: Path) -> dict[str, Any]:
    result = inspect_authoritative_database(path)
    _require(result.get("readable") is True and not result.get("sidecars"), "authoritative database is not sidecar-safe/readable")
    _require(result.get("integrity") == ["ok"], "authoritative database integrity failed")
    _require(int(result.get("foreign_key_violations") or 0) == 0, "authoritative database foreign-key check failed")
    return {key: result[key] for key in _DATABASE_KEYS}


def _target_facts(name: str, *, repository_root: Path, head: str) -> dict[str, Any]:
    _require(_HEAD.fullmatch(head) is not None, "authorized Git HEAD is malformed")
    _require(_migration_catalogue_is_clean(repository_root), "migration catalogue has tracked, untracked, or ignored drift")
    catalogue = list(canonical_migration_names())
    _require(name in catalogue and catalogue.index(name) > 0, "target migration is not a non-foundation canonical migration")
    file = MIGRATIONS_DIR / name
    _require(file.is_file() and not file.is_symlink(), "target migration file is unavailable")
    blob = subprocess.run(["git", "hash-object", str(file)], cwd=repository_root, text=True, capture_output=True, check=False).stdout.strip()
    _require(_HEAD.fullmatch(blob) is not None, "target migration Git blob is unavailable")
    relative = f"migrations/{name}"
    tree = subprocess.run(["git", "ls-tree", "-r", head, "--", relative], cwd=repository_root, text=True, capture_output=True, timeout=5, check=False)
    _require(tree.returncode == 0 and tree.stdout.count("\n") == 1, "target migration is not tracked at authorized HEAD")
    fields = tree.stdout.rstrip("\n").split("\t", 1)
    _require(len(fields) == 2 and fields[1] == relative, "target migration HEAD path mismatch")
    tree_fields = fields[0].split()
    _require(len(tree_fields) == 3 and tree_fields[1] == "blob" and tree_fields[2] == blob, "target migration working blob differs from authorized HEAD")
    contract = _object_contract(name)
    return {"ordinal": parse_migration_ordinal(name), "filename": name, "sha256": _sha256_file(file), "size": file.stat().st_size, "git_blob_sha": blob, "canonical_count": len(catalogue), "canonical_head": catalogue[-1], "required_schema_objects": contract}


def _assert_preconditions(path: Path, target: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    binding = _database_binding(path)
    catalogue = list(canonical_migration_names())
    ordinal = int(target["ordinal"])
    _require(catalogue[ordinal - 1] == target["filename"], "target ordinal/catalogue mismatch")
    _require(binding["migration_count"] == ordinal - 1 and binding["migration_head"] == catalogue[ordinal - 2], "target is not the immediate successor of the authoritative ledger")
    identity = inspect_authoritative_database(path)
    _require(identity.get("migration_ledger") == catalogue[: ordinal - 1], "migration ledger is not an exact canonical prefix")
    objects = target["required_schema_objects"]
    expected = [*objects["tables"], *objects["triggers"], *objects["indexes"]]
    _require(not _migration_objects(path, expected), "target migration objects are already or partially present")
    zero = _zero_state(path)
    _require(all(count == 0 for count in zero.values()), "zero-state gate is blocked")
    _require(not active_printer_runtime_processes(path), "live Printer runtime blocks migration authorization")
    return binding, zero


def _validate_document(document: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    _require(isinstance(document, Mapping) and set(document) == _DOCUMENT_KEYS, "migration authorization schema keys are malformed")
    _require(document.get("schema_version") == MIGRATION_AUTHORIZATION_SCHEMA_VERSION, "migration authorization schema version mismatch")
    _require(document.get("authorization_kind") == MIGRATION_AUTHORIZATION_KIND, "migration authorization kind mismatch")
    auth_id = document.get("authorization_id")
    _require(type(auth_id) is str and _SAFE_ID.fullmatch(auth_id) is not None, "migration authorization ID is malformed")
    _require(document.get("verdict") == MIGRATION_AUTHORIZATION_VERDICT, "migration authorization verdict mismatch")
    try:
        validate_authorization_temporal_validity(document, now=now)
    except AuthorizationTemporalError as exc:
        raise MigrationAuthorizationError(f"migration authorization temporal validity failed: {exc}") from exc
    repo = document.get("repository")
    _require(isinstance(repo, Mapping) and set(repo) == {"identity", "branch", "head", "remote_head", "tracked_clean"}, "repository binding is malformed")
    _require(type(repo.get("identity")) is str and bool(repo["identity"]), "repository identity is malformed")
    _require(type(repo.get("branch")) is str and bool(repo["branch"]) and _HEAD.fullmatch(str(repo.get("head"))) is not None and _HEAD.fullmatch(str(repo.get("remote_head"))) is not None and repo.get("tracked_clean") is True, "repository binding is invalid")
    database = document.get("authoritative_database")
    _require(isinstance(database, Mapping) and set(database) == _DATABASE_KEYS and _SHA256.fullmatch(str(database.get("sha256"))) is not None, "authoritative database binding is malformed")
    target = document.get("target_migration")
    _require(isinstance(target, Mapping) and set(target) == {"ordinal", "filename", "sha256", "size", "git_blob_sha", "canonical_count", "canonical_head", "required_schema_objects"}, "target migration binding is malformed")
    _require(type(target["ordinal"]) is int and target["ordinal"] > 1 and type(target["filename"]) is str and _SHA256.fullmatch(str(target["sha256"])) is not None and type(target["size"]) is int and target["size"] >= 0 and _HEAD.fullmatch(str(target["git_blob_sha"])) is not None, "target migration identity is malformed")
    _require(isinstance(document.get("expected_postcondition"), Mapping), "postcondition is malformed")
    _require(document.get("one_shot_policy") == _ONE_SHOT_POLICY, "migration one-shot policy mismatch")
    try:
        validate_prior_authorizations_non_reusable(document.get("prior_authorizations_non_reusable"), current_authorization_id=auth_id)
    except Exception as exc:
        raise MigrationAuthorizationError(f"prior non-reuse evidence is malformed: {exc}") from exc
    return json.loads(json.dumps(document))


def _safe_file(path: Path) -> None:
    _require(path.is_file() and not path.is_symlink(), "authorization artifact is unsafe")
    for part in (path, *path.parents):
        _require(not part.is_symlink(), "authorization artifact path contains a symlink")


def prepare_migration_authorization(*, repository_root: str | Path, database_path: str | Path, target_migration: str, authorization_id: str, authorized_at: str, validity_seconds: int, prior_authorizations_non_reusable: Sequence[str], repository_identity: str = "Dtwosam/MoneyPrinter", now: datetime | None = None) -> dict[str, Any]:
    """Prepare one immutable migration-only package without consuming it."""
    root, db, package = Path(repository_root).resolve(), Path(database_path).resolve(), DEFAULT_PACKAGE_ROOT
    facts = _live_git_facts(root)
    _require(facts["tracked_clean"] is True and facts["head"] == facts["remote_head"], "repository is not clean and remote-parity bound")
    target = _target_facts(target_migration, repository_root=root, head=facts["head"])
    binding, zero = _assert_preconditions(db, target)
    issued = datetime.fromisoformat(authorized_at.replace("Z", "+00:00"))
    _require(issued.tzinfo is not None and validity_seconds > 0, "authorization time inputs are malformed")
    document = _validate_document({"schema_version": MIGRATION_AUTHORIZATION_SCHEMA_VERSION, "authorization_kind": MIGRATION_AUTHORIZATION_KIND, "authorization_id": authorization_id, "verdict": MIGRATION_AUTHORIZATION_VERDICT, "authorized_at": authorized_at, "expires_at": (issued + timedelta(seconds=validity_seconds)).isoformat(), "validity_seconds": validity_seconds, "repository": {"identity": repository_identity, **facts}, "authoritative_database": binding, "target_migration": target, "expected_postcondition": {"migration_count": binding["migration_count"] + 1, "migration_head": target["filename"], "target_ledger_entry": target["filename"], "required_schema_objects": target["required_schema_objects"], "integrity": "ok", "foreign_key_violations": 0}, "one_shot_policy": dict(_ONE_SHOT_POLICY), "prior_authorizations_non_reusable": list(prior_authorizations_non_reusable)}, now=now)
    package_dir = package / authorization_id
    _require(not package_dir.exists(), "migration authorization package already exists")
    package_dir.mkdir(parents=True, mode=0o700)
    authorization_file = package_dir / AUTHORIZATION_FILENAME
    try:
        payload = _canonical_json_bytes(document)
        _write_exclusive(authorization_file, payload)
        _make_read_only(authorization_file)
        package_dir.chmod(0o555)
        _fsync_directory(package_dir)
        _fsync_directory(package_dir.parent)
    except Exception:
        # This directory is not a finalized authorization until its immutable
        # document has been sealed.  Remove only this just-created empty/partial
        # package; a finalized package is never altered by this path.
        try:
            if authorization_file.exists() and authorization_file.is_file():
                authorization_file.chmod(0o600)
                authorization_file.unlink()
            package_dir.chmod(0o700)
            package_dir.rmdir()
            _fsync_directory(package_dir.parent)
        except OSError as cleanup:
            raise MigrationAuthorizationError(
                f"authorization publication failed and cleanup was blocked: {cleanup}"
            )
        raise
    return {"authorization_id": authorization_id, "authorization_file": str(authorization_file), "authorization_sha256": hashlib.sha256(payload).hexdigest(), "database": binding, "zero_state": zero, "marker_created": False, "consumed": False}


def review_migration_authorization(*, repository_root: str | Path, database_path: str | Path, authorization_file: str | Path, authorization_sha256: str, now: datetime | None = None) -> dict[str, Any]:
    """Independently re-derive all pre-marker migration-only bindings."""
    root, db, path = Path(repository_root).resolve(), Path(database_path).resolve(), Path(authorization_file).resolve()
    _safe_file(path)
    _require(_SHA256.fullmatch(authorization_sha256) is not None and _sha256_file(path) == authorization_sha256, "authorization SHA-256 mismatch")
    document = _validate_document(json.loads(path.read_text(encoding="utf-8")), now=now)
    expected_authorization_path = (
        DEFAULT_PACKAGE_ROOT / document["authorization_id"] / AUTHORIZATION_FILENAME
    )
    _require(
        path == expected_authorization_path.resolve(),
        "authorization file is outside the canonical migration package namespace",
    )
    marker = DEFAULT_MARKER_ROOT / document["authorization_id"]
    _require(not marker.exists(), "authorization is already consumed by an application marker")
    facts = _live_git_facts(root); repo = document["repository"]
    _require(facts == {key: repo[key] for key in facts}, "repository binding changed")
    target = _target_facts(document["target_migration"]["filename"], repository_root=root, head=repo["head"])
    _require(target == document["target_migration"], "target migration binding changed")
    binding, zero = _assert_preconditions(db, target)
    _require(binding == document["authoritative_database"], "authoritative database binding changed")
    return {"verdict": "MIGRATION_ONE_SHOT_REVIEW_PASS", "document": document, "zero_state": zero, "authorization_file": str(path), "authorization_sha256": authorization_sha256, "consumed": False}


def _write_marker(*, root: Path, document: Mapping[str, Any], authorization_sha256: str, now: str) -> tuple[Path, str]:
    target = document["target_migration"]; marker_dir = root / document["authorization_id"]
    _require(not marker_dir.exists(), "application marker namespace already exists")
    marker_dir.mkdir(parents=True, mode=0o700)
    _fsync_directory(marker_dir.parent)
    marker = marker_dir / MARKER_FILENAME
    payload = _canonical_json_bytes({"schema_version": MIGRATION_APPLICATION_MARKER_SCHEMA_VERSION, "authorization_id": document["authorization_id"], "authorization_sha256": authorization_sha256, "repository_head": document["repository"]["head"], "pre_database": document["authoritative_database"], "target_migration": {"filename": target["filename"], "sha256": target["sha256"]}, "consumed_at": now, "application_count": 1})
    try:
        _write_exclusive(marker, payload); _make_read_only(marker); marker_dir.chmod(0o555); _fsync_directory(marker_dir); _fsync_directory(marker_dir.parent)
    except Exception as exc:
        # The durable, sealed namespace is a consumption tombstone: SQL never
        # starts, but the authorization can never be redirected or retried.
        try:
            marker_dir.chmod(0o555); _fsync_directory(marker_dir); _fsync_directory(marker_dir.parent)
        except OSError as seal:
            raise MigrationAuthorizationError(f"marker publication and tombstone sealing failed: {seal}") from exc
        raise MigrationAuthorizationError("marker publication failed; authorization tombstoned") from exc
    return marker, hashlib.sha256(payload).hexdigest()


def _write_terminal(*, root: Path, document: Mapping[str, Any], marker: Path, marker_sha256: str, started_at: str, success: bool, error: str | None, pre: Mapping[str, Any], applied: Sequence[str]) -> Path:
    directory = root / document["authorization_id"]; directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    path = directory / TERMINAL_FILENAME
    post = inspect_authoritative_database(Path(pre["path"]))
    payload = _canonical_json_bytes({"schema_version": MIGRATION_TERMINAL_EVIDENCE_SCHEMA_VERSION, "authorization_id": document["authorization_id"], "application_marker_path": str(marker), "application_marker_sha256": marker_sha256, "started_at": started_at, "ended_at": _utc_now(), "success": success, "failure": error, "pre_database": dict(pre), "observed_post_database": {key: post.get(key) for key in _DATABASE_KEYS}, "pre_migration_count": pre["migration_count"], "pre_migration_head": pre["migration_head"], "post_migration_count": post.get("migration_count"), "post_migration_head": post.get("migration_head"), "integrity": post.get("integrity"), "foreign_key_violations": post.get("foreign_key_violations"), "target_migration": document["target_migration"]["filename"], "migrations_applied": list(applied), "application_marker_consumed": True, "retry_rerun_resume_restart_successor_counts": 0})
    _write_exclusive(path, payload); _make_read_only(path); directory.chmod(0o555); _fsync_directory(directory); _fsync_directory(directory.parent)
    return path


def consume_and_apply_migration_authorization(*, repository_root: str | Path, database_path: str | Path, authorization_file: str | Path, authorization_sha256: str, operator_approved: bool, now: datetime | None = None) -> dict[str, Any]:
    """Consume a valid migration-only authorization before one SQL attempt."""
    _require(operator_approved is True, "explicit operator approval is required")
    review = review_migration_authorization(repository_root=repository_root, database_path=database_path, authorization_file=authorization_file, authorization_sha256=authorization_sha256, now=now)
    document, started = review["document"], _utc_now()
    marker, marker_sha256 = _write_marker(root=DEFAULT_MARKER_ROOT, document=document, authorization_sha256=authorization_sha256, now=started)
    applied: Sequence[str] = (); failure: str | None = None; success = False
    try:
        result = apply_exact_migration(database_path, document["target_migration"]["filename"], expected_sha256=document["target_migration"]["sha256"])
        applied = result["applied_migrations"]
        post = inspect_authoritative_database(Path(database_path))
        required = document["expected_postcondition"]["required_schema_objects"]
        expected_names = [*required["tables"], *required["triggers"], *required["indexes"]]
        _require(set(_migration_objects(Path(database_path), expected_names)) == set(expected_names), "target schema-object postcondition failed")
        _require(post.get("migration_count") == document["expected_postcondition"]["migration_count"] and post.get("migration_head") == document["expected_postcondition"]["migration_head"] and post.get("integrity") == ["ok"] and not post.get("foreign_key_violations"), "postcondition failed")
        success = True
    except Exception as exc:
        failure = str(exc)
    terminal = _write_terminal(root=DEFAULT_TERMINAL_ROOT, document=document, marker=marker, marker_sha256=marker_sha256, started_at=started, success=success, error=failure, pre=document["authoritative_database"], applied=applied)
    if not success:
        raise MigrationAuthorizationError(f"migration application failed after consumption: {failure}")
    return {"success": True, "marker": str(marker), "terminal_evidence": str(terminal), "applied_migrations": list(applied), "consumed": True}


__all__ = ["MIGRATION_AUTHORIZATION_SCHEMA_VERSION", "MIGRATION_AUTHORIZATION_KIND", "MigrationAuthorizationError", "prepare_migration_authorization", "review_migration_authorization", "consume_and_apply_migration_authorization"]
