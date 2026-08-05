"""Fail-closed evidence capture and retention for a future bounded proof.

This module performs no provider, Scheduler, campaign, or database work.  It
only preserves bytes that an independently authorized proof already produced.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
from typing import Any, Callable, Mapping, Sequence


MANDATORY_RETAINED_ARTIFACTS = (
    "child-stdout.txt",
    "child-stderr.txt",
    "child-terminal.json",
    "wrapper-terminal.json",
    "campaign-terminal-report.json",
    "proof-summary.json",
    "holder-context.json",
    "pre-holder-budget-snapshot.json",
    "campaign-source-request-reconciliation.json",
    "campaign-six-unit-evidence.json",
    "action-local-six-unit-evidence.json",
    "selected-and-alternate-identities.json",
)

DIAGNOSTIC_ARTIFACT_FIELDS = {
    "holder-context.json": "holder_context",
    "pre-holder-budget-snapshot.json": "pre_holder_budget_snapshot",
    "campaign-source-request-reconciliation.json": (
        "campaign_source_request_reconciliation"
    ),
    "campaign-six-unit-evidence.json": "campaign_six_unit_evidence",
    "action-local-six-unit-evidence.json": "action_local_six_unit_evidence",
    "selected-and-alternate-identities.json": "selected_and_alternate_identities",
}


class ContinuousProofEvidenceError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def capture_public_command_main(
    main: Callable[[Sequence[str]], Any],
    arguments: Sequence[str],
    *,
    stdout_path: str | Path,
    stderr_path: str | Path,
    launcher_metadata_path: str | Path,
) -> int:
    """Capture the callable's real streams; keep launcher metadata separate."""
    started = datetime.now(timezone.utc)
    stdout = io.StringIO()
    stderr = io.StringIO()
    return_code = 0
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            value = main(list(arguments))
            return_code = int(value or 0)
    except SystemExit as exc:
        return_code = int(exc.code or 0)
    except BaseException as exc:
        stderr.write(f"{type(exc).__name__}:{exc}\n")
        return_code = 1
    ended = datetime.now(timezone.utc)
    Path(stdout_path).write_text(stdout.getvalue(), encoding="utf-8")
    Path(stderr_path).write_text(stderr.getvalue(), encoding="utf-8")
    Path(launcher_metadata_path).write_text(
        json.dumps(
            {
                "return_code": return_code,
                "invocation_arguments": list(arguments),
                "process_identity": "IN_PROCESS",
                "started_at": started.isoformat(),
                "ended_at": ended.isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return return_code


def parse_final_child_terminal(stdout_text: str) -> dict[str, Any]:
    """Return the final JSON object printed by the child, or fail categorically."""
    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for index, character in enumerate(stdout_text):
        if character != "{":
            continue
        try:
            value, relative_end = decoder.raw_decode(stdout_text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append((index + relative_end, -index, value))
    if not candidates:
        raise ContinuousProofEvidenceError("CHILD_TERMINAL_JSON_UNPARSEABLE")
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def terminal_truth_projection(terminal: Mapping[str, Any]) -> dict[str, Any]:
    """Retain the public terminal fields required for independent review."""
    keys = (
        "status",
        "execution_id",
        "campaign_id",
        "campaign_run_id",
        "run_id",
        "cycle_id",
        "first_terminal_cause",
        "blocked_reasons",
        "orchestration_error",
        "fault_details",
        "campaign_acceptance_verdict",
        "lifecycle_verdict",
        "clean_memory_verdict",
        "report_path",
        "report_identity",
    )
    projection = {key: terminal.get(key) for key in keys}
    report = terminal.get("report")
    if isinstance(report, Mapping):
        projection["report_path"] = (
            projection.get("report_path") or report.get("artifact_path")
        )
        projection["report_identity"] = (
            projection.get("report_identity") or report.get("report_hash")
        )
        projection["campaign_id"] = (
            projection.get("campaign_id") or report.get("campaign_id")
        )
    projection["campaign_run_id"] = (
        projection.get("campaign_run_id") or projection.get("run_id")
    )
    projection["lifecycle_verdict"] = (
        projection.get("lifecycle_verdict")
        if projection.get("lifecycle_verdict") is not None
        else terminal.get("operational_lifecycle_pass")
    )
    projection["clean_memory_verdict"] = (
        projection.get("clean_memory_verdict")
        if projection.get("clean_memory_verdict") is not None
        else terminal.get("clean_memory_outcome_pass")
    )
    return projection


def write_proof_diagnostic_artifacts(
    diagnostics: Mapping[str, Any], *, output_directory: str | Path
) -> dict[str, Path]:
    """Materialize non-empty projections of evidence already in terminal reports."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    absent: list[str] = []
    for filename, field in DIAGNOSTIC_ARTIFACT_FIELDS.items():
        value = diagnostics.get(field)
        if value in (None, {}, [], ()):
            absent.append(field)
            continue
        path = output / filename
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        written[filename] = path
    if absent:
        raise ContinuousProofEvidenceError(
            "MANDATORY_DIAGNOSTIC_ABSENT:" + ",".join(sorted(absent))
        )
    return written


def extract_proof_diagnostics(
    campaign_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Locate already-produced diagnostics without inventing absent evidence."""
    def find(*names: str) -> Any:
        queue: list[Any] = [campaign_report]
        while queue:
            value = queue.pop(0)
            if isinstance(value, Mapping):
                for name in names:
                    if value.get(name) not in (None, {}, [], ()):
                        return value[name]
                queue.extend(value.values())
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                queue.extend(value)
        return None

    holder = find("holder_context")
    selection = find("selected_and_alternate_identities")
    if selection is None:
        selection = {
            "ordered_candidate_universe": find("ordered_candidate_universe"),
            "selected_identities": find("selected_identities"),
            "alternate_identities": find("alternate_identities"),
            "selection_seed": find("selection_seed"),
            "freeze_authority": find("freeze_authority"),
            "handoff_slots": find("handoff_slots", "token_slots"),
            "lifecycle_target_identities": find("lifecycle_target_identities"),
        }
        if any(value is None for value in selection.values()):
            selection = None
    return {
        "holder_context": holder,
        "pre_holder_budget_snapshot": find("pre_holder_budget_snapshot"),
        "campaign_source_request_reconciliation": find(
            "campaign_source_request_reconciliation"
        ),
        "campaign_six_unit_evidence": find(
            "campaign_six_unit_evidence", "six_unit_evidence"
        ),
        "action_local_six_unit_evidence": find(
            "action_local_six_unit_evidence", "action_local_evidence"
        ),
        "selected_and_alternate_identities": selection,
    }


def retain_required_artifacts(
    artifact_sources: Mapping[str, str | Path],
    *,
    retained_directory: str | Path,
) -> dict[str, Any]:
    """Copy, hash, and reread all mandatory artifacts before cleanup is allowed."""
    destination = Path(retained_directory)
    destination.mkdir(parents=True, exist_ok=False)
    hashes: dict[str, dict[str, Any]] = {}
    copied: dict[str, bytes] = {}
    missing: list[str] = []
    for name in MANDATORY_RETAINED_ARTIFACTS:
        if name not in artifact_sources or not Path(artifact_sources[name]).is_file():
            missing.append(name)
            hashes[name] = {
                "status": "ABSENT_MANDATORY",
                "reason": "MANDATORY_ARTIFACT_MISSING",
            }
            continue
        source = Path(artifact_sources[name])
        target = destination / name
        shutil.copyfile(source, target)
        payload = target.read_bytes()
        copied[name] = payload
        hashes[name] = {
            "status": "PRESENT",
            "sha256": _sha256_bytes(payload),
            "size": len(payload),
        }
    hash_path = destination / "artifact-hashes.json"
    status = "BLOCKED" if missing else "COMPLETE"
    hash_path.write_text(
        json.dumps(
            {
                "status": status,
                "reason": "MANDATORY_ARTIFACT_MISSING" if missing else None,
                "absent_artifacts": sorted(missing),
                "artifacts": hashes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for name, expected_bytes in copied.items():
        actual = (destination / name).read_bytes()
        if actual != expected_bytes or _sha256_bytes(actual) != hashes[name]["sha256"]:
            raise ContinuousProofEvidenceError(f"RETAINED_ARTIFACT_REREAD_MISMATCH:{name}")
    if missing:
        raise ContinuousProofEvidenceError(
            "MANDATORY_ARTIFACT_MISSING:" + ",".join(sorted(missing))
        )
    return {"status": "COMPLETE", "artifacts": hashes, "hash_path": str(hash_path)}
