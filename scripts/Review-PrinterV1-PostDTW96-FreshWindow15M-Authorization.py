from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw96-window15m-authorization-preparation"
HEAD = "a64d109b043ba86d73b82276fb34ba28561de093"
AUTH_ID = "V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z"
AUTH_SHA256 = "d64f2b4285aeebf93a4369350da960a9398f38a4123a160ce8e53cb505c66de1"
AUTH_FILE = (
    REPO
    / "operator-runs"
    / "v2-9-8b-window-15m-final-authorization"
    / AUTH_ID
    / "final_authorization.json"
)
DB = REPO / "data" / "printer_v1.sqlite3"
EXPECTED_DB = {
    "path": str(DB),
    "sha256": "274e3d660e45f1c872e633847f5bf87a2fcdca102ca35e2a8605c1516d9711ae",
    "size": 73138176,
    "inode": 1230526,
    "mtime_ns": 1786269650301884824,
    "migration_count": 53,
    "migration_head": "053_pilot_input_readiness_route_domain.sql",
}
EXPECTED_ALLOWED_FILE_COUNT = 25
EXPECTED_ALLOWED_FILE_SET_SHA256 = "21204a6df8ded425f35c36726552578387ce9d898ae9f8d9521b16672489da1c"
APP_DIR = (
    Path.home()
    / "PrinterOperations"
    / "v2-9-8"
    / "window-15m-one-shot-applications"
    / AUTH_ID
)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def no_dupes(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RuntimeError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def db_fingerprint() -> dict:
    stat = DB.stat()
    return {
        "path": str(DB),
        "sha256": sha256_file(DB),
        "size": int(stat.st_size),
        "inode": int(stat.st_ino),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def main() -> int:
    phase = "START"
    try:
        phase = "GIT_IDENTITY"
        if git("branch", "--show-current") != BRANCH:
            raise RuntimeError("authorization preparation branch mismatch")
        if git("rev-parse", "HEAD") != HEAD:
            raise RuntimeError("authorization preparation HEAD mismatch")
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked worktree/index is not clean")

        sys.path.insert(0, str(REPO / "src"))
        from printer_v1.operator_cli.authorization_temporal_validity import (
            validate_authorization_temporal_validity,
        )
        from printer_v1.operator_cli.git_provenance_authorization_manifest import (
            validate_git_provenance_manifest_pre_marker,
        )
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            build_operational_budget_preflight,
        )
        from printer_v1.operator_cli.operational_memory_factory_command import (
            ADMISSION_OPERATION_CEILING,
            DISCOVERY_REQUEST_CEILING,
            GOVERNED_15M_REQUEST_CEILING,
            GOVERNED_REQUESTS_PER_TOKEN,
            _active_counts,
            _locked_capability_counts,
            _read_only,
            _validate_locked_baseline,
        )
        from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
            PACKAGE_BINDING_FIELDS,
            assert_migration_ledger_ready,
            package_binding_from_document,
        )
        from printer_v1.operator_cli.readiness_source_contract_preflight import (
            build_readiness_source_contract_preflight,
        )
        from printer_v1.operator_cli.unified_terminal_closure import (
            assert_runtime_dependency_preflight,
        )
        from printer_v1.operator_cli.window_15m_concrete_composition import (
            run_window_15m_concrete_composition_preflight,
            window_15m_preflight_builders,
        )
        from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
            build_manifest_bytes,
        )

        phase = "AUTHORIZATION_FILE"
        if not AUTH_FILE.is_file():
            raise RuntimeError(f"authorization file missing: {AUTH_FILE}")
        auth_bytes = AUTH_FILE.read_bytes()
        observed_auth_sha = sha256_bytes(auth_bytes)
        if observed_auth_sha != AUTH_SHA256:
            raise RuntimeError(
                f"authorization SHA mismatch: {observed_auth_sha}"
            )
        document = json.loads(auth_bytes, object_pairs_hook=no_dupes)
        if document.get("schema_version") != "PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2":
            raise RuntimeError("authorization schema mismatch")
        if document.get("authorization_id") != AUTH_ID:
            raise RuntimeError("authorization identity mismatch")
        if document.get("verdict") != "V2_9_8B_POST_DTW96_FRESH_WINDOW_15M_ONE_USE_FINAL_AUTHORIZATION_PASS":
            raise RuntimeError("authorization verdict mismatch")
        if document.get("authorized_git") != {"branch": BRANCH, "head": HEAD}:
            raise RuntimeError("authorization Git binding mismatch")
        if document.get("authoritative_database") != EXPECTED_DB:
            raise RuntimeError("authorization database binding mismatch")

        phase = "ONE_USE_POLICY"
        command = document.get("authorized_command") or {}
        if command.get("mode") != "run" or command.get("operator_approved") is not True:
            raise RuntimeError("authorized command mode/operator approval mismatch")
        if int(command.get("allowed_invocation_count") or 0) != 1:
            raise RuntimeError("authorization is not exactly one-use")
        for flag in (
            "automatic_retry_allowed",
            "manual_rerun_allowed",
            "resume_allowed",
            "restart_allowed",
            "successor_allowed",
        ):
            if command.get(flag) is not False:
                raise RuntimeError(f"forbidden authorization flag enabled: {flag}")
        policy = document.get("campaign_policy") or {}
        if policy.get("main_window") != "WINDOW_15M":
            raise RuntimeError("main window is not WINDOW_15M")
        if policy.get("selective_1h_continuation") is not False:
            raise RuntimeError("1h continuation is not locked off")

        history = document.get("prior_authorizations_non_reusable") or []
        if len(history) != 25 or len(set(history)) != 25:
            raise RuntimeError("historical non-reuse list is not exactly 25 unique IDs")
        if "V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z" not in history:
            raise RuntimeError("DTW96 predecessor missing from non-reuse history")
        if AUTH_ID in history:
            raise RuntimeError("fresh authorization incorrectly appears in predecessor history")

        phase = "TEMPORAL_VALIDITY"
        temporal = validate_authorization_temporal_validity(document)
        authorized_at = datetime.fromisoformat(
            str(document["authorized_at"]).replace("Z", "+00:00")
        )
        expires_at = datetime.fromisoformat(
            str(document["expires_at"]).replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        if not (authorized_at <= now < expires_at):
            raise RuntimeError(
                f"authorization not temporally valid at review time: now={now.isoformat()}"
            )
        if int(document.get("validity_seconds") or 0) != 86400:
            raise RuntimeError("authorization validity_seconds mismatch")

        phase = "UNCONSUMED_MARKER"
        if APP_DIR.exists():
            raise RuntimeError(
                f"authorization application directory already exists: {APP_DIR}"
            )

        phase = "DATABASE_BINDING"
        sidecars = [
            str(path)
            for path in (
                Path(str(DB) + "-wal"),
                Path(str(DB) + "-shm"),
                Path(str(DB) + "-journal"),
            )
            if path.exists()
        ]
        if sidecars:
            raise RuntimeError(f"authoritative DB sidecars present: {sidecars}")
        before_db = db_fingerprint()
        if before_db != {k: EXPECTED_DB[k] for k in before_db}:
            raise RuntimeError(f"authoritative DB filesystem identity mismatch: {before_db}")
        review = assert_migration_ledger_ready(
            mode="review",
            db_path=DB,
            migrations_dir=REPO / "migrations",
            package_binding=package_binding_from_document(document),
        )
        observed_binding = {
            key: review.database.get(key) for key in PACKAGE_BINDING_FIELDS
        }
        if observed_binding != EXPECTED_DB:
            raise RuntimeError(
                f"migration/package DB binding mismatch: {observed_binding}"
            )

        phase = "ZERO_IO_READINESS"
        source = build_readiness_source_contract_preflight()
        if source.get("status") != "READY" or int(source.get("external_requests") or 0) != 0:
            raise RuntimeError(f"source contract not zero-I/O READY: {source}")
        composition = run_window_15m_concrete_composition_preflight(
            repository_root=str(REPO), timeout_seconds=5.0
        )
        if composition.get("status") != "READY":
            raise RuntimeError(f"concrete composition not READY: {composition}")
        dependency = assert_runtime_dependency_preflight(
            repository_root=REPO,
            adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
        )
        if dependency.status != "READY":
            raise RuntimeError(f"dependency preflight not READY: {dependency.to_dict()}")
        budget = build_operational_budget_preflight(
            admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
            discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
            governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
            governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
        )
        if budget.get("status") != "READY":
            raise RuntimeError(f"holder budget not READY: {budget}")

        conn = _read_only(DB)
        try:
            active = dict(_active_counts(conn))
            locked = dict(_locked_capability_counts(conn))
            historical_paper_audit = int(
                conn.execute(
                    "SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        if any(active.values()):
            raise RuntimeError(f"active operational residue: {active}")
        _validate_locked_baseline(locked)
        if historical_paper_audit != 1:
            raise RuntimeError(
                f"historical paper-audit baseline changed: {historical_paper_audit}"
            )

        phase = "PRE_MARKER_PROVENANCE"
        manifest, manifest_bytes = build_manifest_bytes(
            repository_root=REPO,
            authorization_file=AUTH_FILE,
            authorization_sha256=AUTH_SHA256,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        manifest_sha = sha256_bytes(manifest_bytes)
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix="printer-dtw96-auth-review-", suffix=".json", delete=False
        ) as handle:
            handle.write(manifest_bytes)
            manifest_path = Path(handle.name)
        try:
            prepared = validate_git_provenance_manifest_pre_marker(
                repository_root=REPO,
                manifest_path=str(manifest_path),
                manifest_sha256=manifest_sha,
            )
            prepared_summary = prepared.summary()
        finally:
            manifest_path.unlink(missing_ok=True)
        if int(prepared_summary.get("allowed_file_count") or 0) != EXPECTED_ALLOWED_FILE_COUNT:
            raise RuntimeError(
                f"pre-marker allowed file count drift: {prepared_summary}"
            )
        if prepared_summary.get("allowed_file_set_sha256") != EXPECTED_ALLOWED_FILE_SET_SHA256:
            raise RuntimeError(
                f"pre-marker allowed file set drift: {prepared_summary}"
            )

        phase = "FINAL_UNCHANGED_CHECK"
        if sha256_file(AUTH_FILE) != AUTH_SHA256:
            raise RuntimeError("authorization file changed during review")
        after_db = db_fingerprint()
        if after_db != before_db:
            raise RuntimeError(
                f"authoritative DB changed during review: before={before_db} after={after_db}"
            )
        if APP_DIR.exists():
            raise RuntimeError("application directory appeared during review")
        if git("branch", "--show-current") != BRANCH or git("rev-parse", "HEAD") != HEAD:
            raise RuntimeError("Git identity changed during review")
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked Git state changed during review")

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "verdict": "V2_9_8B_POST_DTW96_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_INDEPENDENT_REVIEW_PASS",
                    "authorization_id": AUTH_ID,
                    "authorization_file": AUTH_FILE.relative_to(REPO).as_posix(),
                    "authorization_sha256": AUTH_SHA256,
                    "authorized_at": document["authorized_at"],
                    "expires_at": document["expires_at"],
                    "temporal_status": getattr(temporal, "status", "TEMPORALLY_VALID"),
                    "authorized_git": {"branch": BRANCH, "head": HEAD},
                    "authoritative_database": EXPECTED_DB,
                    "database_unchanged_during_review": True,
                    "historical_non_reusable_authorization_count": len(history),
                    "allowed_invocation_count": 1,
                    "main_window": policy.get("main_window"),
                    "selective_1h_continuation": policy.get("selective_1h_continuation"),
                    "application_marker_present": False,
                    "wrapper_invoked": False,
                    "printer_runtime_started": False,
                    "scheduler_runtime_started": False,
                    "window_15m_started": False,
                    "source_contract_status": source.get("status"),
                    "source_contract_external_requests": int(source.get("external_requests") or 0),
                    "concrete_composition_status": composition.get("status"),
                    "dependency_status": dependency.status,
                    "holder_budget_status": budget.get("status"),
                    "active_counts": active,
                    "historical_paper_audit_rows_preserved": historical_paper_audit,
                    "migration_guard_review": review.verdict,
                    "pre_marker_allowed_file_count": prepared_summary.get("allowed_file_count"),
                    "pre_marker_allowed_file_set_sha256": prepared_summary.get("allowed_file_set_sha256"),
                    "review_source_calls": 0,
                    "review_scheduler_runtime_calls": 0,
                    "review_database_writes": 0,
                    "next_step": "AUTHORIZATION_CLOSEOUT_BEFORE_WRAPPER_INVOCATION",
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "verdict": "V2_9_8B_POST_DTW96_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_INDEPENDENT_REVIEW_BLOCKED",
                    "phase": phase,
                    "error": f"{type(exc).__name__}:{exc}",
                    "authorization_id": AUTH_ID,
                    "wrapper_invoked": False,
                    "printer_runtime_started": False,
                    "scheduler_runtime_started": False,
                    "window_15m_started": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
