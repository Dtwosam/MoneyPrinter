from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

REPO = Path.home() / "Developer" / "MoneyPrinter"
APP_ROOT = Path.home() / "PrinterOperations" / "v2-9-8" / "window-15m-one-shot-applications"
STAGING_ROOT = APP_ROOT / ".staging"
EXPECTED_BRANCH = "agent/v2-9-8b-post-dtw100-ordinary-staging-residue-audit"
AUTH_STAGING = re.compile(r"^(V2_9_8B_WINDOW_15M_AUTH_[0-9]{8}T[0-9]{6}Z)-([0-9a-f]{32})$")
PROCESS_NEEDLES = (
    "printer_v1.operator_cli.operational_memory_factory_command",
    "printer_v1.operator_cli.window_15m_one_shot_wrapper",
    "printer_v1.operator_cli.standard_four_hour_one_shot_wrapper",
    "printer_v1.operator_cli.one_command_15m_factory",
    "Start-PrinterV1-Window15M-OneShot",
    "Start-PrinterV1-StandardFourHour-OneShot",
)


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def git(*args: str) -> str:
    result = run(["git", *args], cwd=REPO)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    mode = os.lstat(path).st_mode
    kind = (
        "symlink" if stat.S_ISLNK(mode)
        else "regular" if stat.S_ISREG(mode)
        else "directory" if stat.S_ISDIR(mode)
        else "other"
    )
    result: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "kind": kind,
        "mode": oct(stat.S_IMODE(mode)),
        "size": int(os.lstat(path).st_size),
        "mtime_ns": int(os.lstat(path).st_mtime_ns),
    }
    if kind == "regular":
        result["sha256"] = sha256_file(path)
    elif kind == "symlink":
        result["link_target"] = os.readlink(path)
    return result


def inspect_tree(root: Path) -> dict[str, Any]:
    root_identity = file_identity(root)
    if root_identity["kind"] != "directory":
        return {"root": root_identity, "entries": [], "safe_shape": False}
    entries: list[dict[str, Any]] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for child in sorted(current.iterdir(), key=lambda p: p.name):
            identity = file_identity(child)
            identity["relative_path"] = child.relative_to(root).as_posix()
            entries.append(identity)
            if identity["kind"] == "directory":
                stack.append(child)
    safe_shape = bool(
        all(entry["kind"] == "regular" for entry in entries)
        and {entry["relative_path"] for entry in entries}.issubset({"git-provenance-manifest.json"})
    )
    return {"root": root_identity, "entries": entries, "safe_shape": safe_shape}


def active_process_matches() -> list[str]:
    result = run(["ps", "-axo", "pid=,command="])
    if result.returncode != 0:
        raise RuntimeError(f"process inspection failed: {result.stderr.strip()}")
    return [
        line.strip() for line in result.stdout.splitlines()
        if any(needle in line for needle in PROCESS_NEEDLES)
    ]


def database_open_handles() -> list[str]:
    db = REPO / "data" / "printer_v1.sqlite3"
    result = run(["lsof", "-n", str(db)])
    if result.returncode not in (0, 1):
        raise RuntimeError(f"lsof failed: {result.stderr.strip()}")
    if result.returncode == 1 or not result.stdout.strip():
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[1:] if lines and lines[0].startswith("COMMAND") else lines


def repository_evidence(auth_id: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for path in REPO.rglob("*"):
        if auth_id not in path.as_posix():
            continue
        try:
            rel = path.relative_to(REPO).as_posix()
            identity = file_identity(path)
        except OSError as exc:
            matches.append({"path": str(path), "error": f"{type(exc).__name__}:{exc}"})
            continue
        identity["repository_relative_path"] = rel
        matches.append(identity)
    return sorted(matches, key=lambda item: str(item.get("repository_relative_path") or item.get("path")))


def canonical_application(auth_id: str) -> dict[str, Any]:
    path = APP_ROOT / auth_id
    if not os.path.lexists(path):
        return {"path": str(path), "exists": False}
    tree = inspect_tree(path)
    marker = path / "application-marker.json"
    tree["exists"] = True
    tree["marker_present"] = marker.is_file() and not marker.is_symlink()
    if tree["marker_present"]:
        tree["marker_sha256"] = sha256_file(marker)
    return tree


def main() -> int:
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "verdict": "V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_AUDIT_BLOCKED",
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "authoritative_database_writes": 0,
        "filesystem_mutations": 0,
        "authorization_created": False,
        "printer_runtime_started": False,
        "cleanup_authorized": False,
    }
    try:
        if not REPO.is_dir():
            raise RuntimeError(f"repository missing: {REPO}")
        branch = git("branch", "--show-current")
        head = git("rev-parse", "HEAD")
        tracked = git("status", "--porcelain=v1", "-uno")
        if branch != EXPECTED_BRANCH:
            raise RuntimeError(f"branch mismatch: {branch}")
        if tracked:
            raise RuntimeError("tracked worktree/index is not clean")

        processes = active_process_matches()
        if processes:
            raise RuntimeError(f"active Printer process matches: {processes}")
        handles = database_open_handles()
        if handles:
            raise RuntimeError(f"authoritative database has open handles: {handles}")
        if not STAGING_ROOT.is_dir():
            raise RuntimeError(f"ordinary staging root missing: {STAGING_ROOT}")

        staging_dirs = sorted(STAGING_ROOT.iterdir(), key=lambda p: p.name)
        inspected: list[dict[str, Any]] = []
        for staging in staging_dirs:
            tree = inspect_tree(staging)
            match = AUTH_STAGING.fullmatch(staging.name)
            auth_id = match.group(1) if match else None
            item: dict[str, Any] = {
                "staging": tree,
                "recognized_authorization_staging": auth_id is not None,
                "authorization_id": auth_id,
                "canonical_application": canonical_application(auth_id) if auth_id else None,
                "repository_evidence": repository_evidence(auth_id) if auth_id else [],
                "wrapper_cleanup_shape_compatible": bool(tree["safe_shape"]),
                "classification": (
                    "RECOGNIZED_AUTH_STAGING_REQUIRES_EVIDENCE_REVIEW"
                    if auth_id else "NON_AUTH_STAGING_REQUIRES_MANUAL_PROVENANCE_REVIEW"
                ),
            }
            inspected.append(item)

        result.update({
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_READONLY_AUDIT_CAPTURE_PASS",
            "branch": branch,
            "head": head,
            "tracked_tree_clean": True,
            "staging_root": str(STAGING_ROOT),
            "staging_entry_count": len(staging_dirs),
            "staging_entries": inspected,
            "active_process_matches": processes,
            "database_open_handles": handles,
            "cleanup_authorized": False,
            "next_step": "REVIEW_EACH_STAGING_IDENTITY_BEFORE_ANY_CLEANUP_DESIGN",
        })
        code = 0
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        result["next_step"] = "STOP_AND_REVIEW_AUDIT_BLOCKER"
        code = 3
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
