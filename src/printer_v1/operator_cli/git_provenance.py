"""Bounded, shell-safe launch-time Git provenance capture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Iterable, Mapping


GIT_COMMAND_TIMEOUT_SECONDS = 5.0
_HEAD_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
GIT_PROVENANCE_FIELDS = (
    "git_head",
    "git_tracked_tree_clean",
    "git_staged_changes_present",
    "git_unstaged_changes_present",
    "git_untracked_present",
    "git_provenance_captured_at",
)


class GitProvenanceError(RuntimeError):
    """Fail-closed Git provenance error."""


def _utc_text(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _run_git(
    project_root: Path,
    arguments: list[str],
    *,
    git_executable: str,
    timeout_seconds: float,
    runner: Callable[..., Any],
) -> Any:
    try:
        return runner(
            [git_executable, *arguments],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise GitProvenanceError("Git executable is unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitProvenanceError("Git provenance command timed out") from exc
    except OSError as exc:
        raise GitProvenanceError(f"Git provenance command failed: {exc}") from exc


def _require_return_code(result: Any, *, command: str, allowed: set[int]) -> int:
    return_code = getattr(result, "returncode", None)
    if type(return_code) is not int or return_code not in allowed:
        raise GitProvenanceError(f"Git {command} could not be verified")
    return return_code


def validate_launch_provenance(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the minimal immutable provenance payload accepted by a run."""
    if not isinstance(value, Mapping):
        raise GitProvenanceError("launch Git provenance must be an object")
    if set(value) != set(GIT_PROVENANCE_FIELDS):
        raise GitProvenanceError("launch Git provenance fields are malformed")
    head = value.get("git_head")
    if not isinstance(head, str) or _HEAD_PATTERN.fullmatch(head) is None:
        raise GitProvenanceError("launch Git HEAD is malformed")
    boolean_fields = GIT_PROVENANCE_FIELDS[1:5]
    if any(type(value.get(field)) is not bool for field in boolean_fields):
        raise GitProvenanceError("launch Git status fields are malformed")
    staged = bool(value["git_staged_changes_present"])
    unstaged = bool(value["git_unstaged_changes_present"])
    clean = bool(value["git_tracked_tree_clean"])
    if clean != (not staged and not unstaged):
        raise GitProvenanceError("launch Git tracked-tree status is inconsistent")
    if not clean:
        raise GitProvenanceError("launch Git tracked tree is dirty")
    captured_at = value.get("git_provenance_captured_at")
    if not isinstance(captured_at, str):
        raise GitProvenanceError("launch Git capture time is malformed")
    try:
        parsed = datetime.fromisoformat(captured_at)
    except ValueError as exc:
        raise GitProvenanceError("launch Git capture time is malformed") from exc
    if parsed.tzinfo is None:
        raise GitProvenanceError("launch Git capture time must be timezone-aware")
    return {field: value[field] for field in GIT_PROVENANCE_FIELDS}


def capture_git_provenance(
    project_root: str | Path,
    *,
    git_executable: str = "git",
    timeout_seconds: float = GIT_COMMAND_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture exact HEAD and tracked/untracked state without storing file names."""
    if not 0 < timeout_seconds <= GIT_COMMAND_TIMEOUT_SECONDS:
        raise GitProvenanceError("Git provenance timeout is outside the fixed ceiling")
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise GitProvenanceError("Git project root is unavailable")

    head_result = _run_git(
        root,
        ["rev-parse", "--verify", "HEAD^{commit}"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    _require_return_code(head_result, command="HEAD", allowed={0})
    head_output = getattr(head_result, "stdout", None)
    if not isinstance(head_output, str):
        raise GitProvenanceError("Git HEAD output is malformed")
    head = head_output.strip().lower()
    if _HEAD_PATTERN.fullmatch(head) is None:
        raise GitProvenanceError("Git HEAD output is malformed")

    staged_result = _run_git(
        root,
        ["diff", "--cached", "--quiet", "--no-ext-diff", "--"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    staged = _require_return_code(
        staged_result, command="staged status", allowed={0, 1}
    ) == 1

    unstaged_result = _run_git(
        root,
        ["diff", "--quiet", "--no-ext-diff", "--"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    unstaged = _require_return_code(
        unstaged_result, command="unstaged status", allowed={0, 1}
    ) == 1

    untracked_result = _run_git(
        root,
        ["ls-files", "--others", "--exclude-standard", "-z"],
        git_executable=git_executable,
        timeout_seconds=timeout_seconds,
        runner=runner,
    )
    _require_return_code(untracked_result, command="untracked status", allowed={0})
    untracked_output = getattr(untracked_result, "stdout", None)
    if not isinstance(untracked_output, str):
        raise GitProvenanceError("Git untracked output is malformed")

    provenance = {
        "git_head": head,
        "git_tracked_tree_clean": not staged and not unstaged,
        "git_staged_changes_present": staged,
        "git_unstaged_changes_present": unstaged,
        "git_untracked_present": bool(untracked_output),
        "git_provenance_captured_at": _utc_text(now),
    }
    return validate_launch_provenance(provenance)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture launch-time Git provenance.")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        provenance = capture_git_provenance(args.project_root)
    except GitProvenanceError as exc:
        print(
            json.dumps({"status": "GIT_PROVENANCE_BLOCKED", "error": str(exc)}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(provenance, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())