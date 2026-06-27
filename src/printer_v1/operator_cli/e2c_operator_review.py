"""E2C-F Operator Token List Review -- final E2C closeout review.

Loads an operator-approved token list JSON file, validates all fields,
runs E2C-C readiness review, runs E2C-E fixture rehearsal, and
outputs READY_FOR_OPERATOR_DECISION or BLOCKED.

All operations are read-only. No source fetching. No scheduler runtime.
No persistent DB mutation. No snapshots, memory, context, or paper decisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from printer_v1.operator_cli.e2c_fixture_rehearsal import build_e2c_fixture_rehearsal_payload
from printer_v1.operator_cli.e2c_readiness import (
    HARD_LOCKS,
    RECOMMENDATION_LIMITED_GO,
    VALID_LIFECYCLE_LANES,
    build_e2c_readiness_payload,
    is_valid_solana_mint,
)


FINAL_RECOMMENDATION_READY: str = "READY_FOR_OPERATOR_DECISION"
E2C_STATUS_READY: str = "E2C_READY_TO_CLOSE_AFTER_COMMIT_TAG"
E2C_STATUS_BLOCKED: str = "E2C_REVIEW_BLOCKED"

# Exact placeholder mints from the example template that must be rejected.
_PLACEHOLDER_MINTS: frozenset[str] = frozenset({"A" * 43, "B" * 44})

# Case-insensitive substrings that identify placeholder or demo values.
_PLACEHOLDER_SUBSTRINGS: tuple[str, ...] = (
    "REPLACE_WITH_REAL_MINT",
    "PLACEHOLDER",
    "TOKEN_MINT",
    "example",
    "demo",
    "test",
)


def _is_placeholder_mint(mint: str) -> bool:
    """Return True if mint looks like a placeholder rather than a real token."""
    if mint in _PLACEHOLDER_MINTS:
        return True
    mint_lower = mint.lower()
    return any(sub.lower() in mint_lower for sub in _PLACEHOLDER_SUBSTRINGS)


def _review_token_file(
    token_file_path: str | Path | None,
) -> dict[str, Any]:
    """Load and validate the operator token list JSON file.

    Enforces: tokens[] present, 1-2 entries, all required fields, approved_by_operator
    is boolean True, non-blank operator_note, no placeholder mints, no duplicates,
    valid Solana base58 mint format, valid lifecycle_lane.

    Returns a dict including 'valid', 'errors', and 'clean_token_entries' for downstream use.
    """
    if token_file_path is None:
        return {
            "token_file_path": None,
            "file_readable": False,
            "tokens_parsed": [],
            "token_count": 0,
            "valid": False,
            "errors": ["no token_file_path provided"],
            "clean_token_entries": [],
        }

    resolved = Path(token_file_path)

    if not resolved.exists():
        return {
            "token_file_path": str(resolved),
            "file_readable": False,
            "tokens_parsed": [],
            "token_count": 0,
            "valid": False,
            "errors": [f"token file does not exist: {resolved}"],
            "clean_token_entries": [],
        }

    try:
        raw = resolved.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "token_file_path": str(resolved),
            "file_readable": False,
            "tokens_parsed": [],
            "token_count": 0,
            "valid": False,
            "errors": [f"token file could not be parsed: {exc}"],
            "clean_token_entries": [],
        }

    if not isinstance(data, dict) or "tokens" not in data:
        return {
            "token_file_path": str(resolved),
            "file_readable": True,
            "tokens_parsed": [],
            "token_count": 0,
            "valid": False,
            "errors": ["token file must contain a top-level 'tokens' array"],
            "clean_token_entries": [],
        }

    tokens_raw = data["tokens"]
    if not isinstance(tokens_raw, list):
        return {
            "token_file_path": str(resolved),
            "file_readable": True,
            "tokens_parsed": [],
            "token_count": 0,
            "valid": False,
            "errors": ["'tokens' must be a JSON array"],
            "clean_token_entries": [],
        }

    token_count = len(tokens_raw)
    errors: list[str] = []

    if token_count < 1:
        errors.append("tokens array must contain at least 1 entry; got 0")
    elif token_count > 2:
        errors.append(f"tokens array allows at most 2 entries; got {token_count}")

    tokens_parsed: list[dict[str, Any]] = []
    seen_mints: set[str] = set()

    for i, entry in enumerate(tokens_raw):
        if not isinstance(entry, dict):
            errors.append(f"tokens[{i}] must be a JSON object")
            continue

        tokens_parsed.append(entry)

        for field in ("token_mint", "lifecycle_lane", "operator_note", "approved_by_operator"):
            if field not in entry:
                errors.append(f"tokens[{i}] missing required field: {field!r}")

        mint = str(entry.get("token_mint", ""))
        lane = str(entry.get("lifecycle_lane", ""))
        note = entry.get("operator_note", "")
        approved = entry.get("approved_by_operator")

        if not isinstance(approved, bool):
            errors.append(
                f"tokens[{i}].approved_by_operator must be boolean true;"
                f" got {type(approved).__name__} {approved!r}"
            )
        elif approved is not True:
            errors.append(
                f"tokens[{i}].approved_by_operator is false;"
                " all tokens must be explicitly approved"
            )

        if not isinstance(note, str) or not note.strip():
            errors.append(f"tokens[{i}].operator_note must not be blank")

        if _is_placeholder_mint(mint):
            errors.append(
                f"tokens[{i}].token_mint {mint!r} appears to be a placeholder;"
                " replace with a real operator-approved Solana mint address"
            )
        elif not is_valid_solana_mint(mint):
            errors.append(
                f"tokens[{i}].token_mint {mint!r} is not a valid Solana base58 mint"
                " (43-44 chars, base58 alphabet only, no 0/O/I/l)"
            )
        else:
            if mint in seen_mints:
                errors.append(f"duplicate token_mint at tokens[{i}]: {mint!r}")
            else:
                seen_mints.add(mint)

        if lane not in VALID_LIFECYCLE_LANES:
            errors.append(
                f"tokens[{i}].lifecycle_lane {lane!r} is not supported;"
                " must be TRACK_FAST or TRACK_NORMAL"
            )

    clean_token_entries: list[dict[str, str]] = []
    if not errors and 1 <= token_count <= 2:
        for entry in tokens_raw:
            clean_token_entries.append({
                "token_mint": str(entry["token_mint"]),
                "lifecycle_lane": str(entry["lifecycle_lane"]),
            })

    return {
        "token_file_path": str(resolved),
        "file_readable": True,
        "tokens_parsed": tokens_parsed,
        "token_count": token_count,
        "valid": not errors,
        "errors": errors,
        "clean_token_entries": clean_token_entries,
    }


def _determine_final_recommendation(
    token_file_review: dict[str, Any],
    e2c_readiness_review: dict[str, Any],
    fixture_rehearsal_review: dict[str, Any],
) -> tuple[str, list[str], str]:
    """Determine BLOCKED or READY_FOR_OPERATOR_DECISION with reasons. Pure function."""
    reasons: list[str] = []

    if not token_file_review.get("valid"):
        reasons.append("token file review failed")
        for err in token_file_review.get("errors", []):
            reasons.append("  token file: " + err)

    readiness_rec = e2c_readiness_review.get("recommendation")
    if readiness_rec != RECOMMENDATION_LIMITED_GO:
        reasons.append(
            "E2C-C readiness recommendation is "
            + repr(readiness_rec)
            + "; must be LIMITED_GO_FOR_OPERATOR_REVIEW"
        )

    fixture_rec = fixture_rehearsal_review.get("recommendation")
    if fixture_rec != "FIXTURE_REHEARSAL_PASS":
        reasons.append(
            "E2C-E fixture rehearsal recommendation is "
            + repr(fixture_rec)
            + "; must be FIXTURE_REHEARSAL_PASS"
        )

    if reasons:
        return "BLOCKED", reasons, E2C_STATUS_BLOCKED

    return FINAL_RECOMMENDATION_READY, [
        "token file review passed"
        " (1-2 tokens, all fields valid, no placeholders, all approved_by_operator true)",
        "E2C-C readiness recommendation is LIMITED_GO_FOR_OPERATOR_REVIEW",
        "E2C-E fixture rehearsal recommendation is FIXTURE_REHEARSAL_PASS",
        "all 11 hard-lock flags are False",
        "no persistent DB mutation detected",
        "E2C-F operator review complete -- READY_FOR_OPERATOR_DECISION",
        "READY_FOR_OPERATOR_DECISION does NOT authorize real execution",
        "operator must commit and tag E2C-F, then approve a separately named next lane"
        " before any real bounded source-governed cycle can begin",
    ], E2C_STATUS_READY


def build_e2c_operator_review_payload(
    token_file_path: str | Path | None,
    db_path: str | Path | None,
    *,
    backup_confirmed: bool,
) -> dict[str, Any]:
    """Build the full E2C-F operator review payload.

    No persistent DB mutation. No source fetching. No scheduler execution.
    No snapshot creation. No memory creation. No paper decisions.
    """
    token_file_review = _review_token_file(token_file_path)
    clean_tokens = token_file_review.get("clean_token_entries", [])

    e2c_readiness_review = build_e2c_readiness_payload(
        clean_tokens, db_path, backup_confirmed=backup_confirmed
    )

    fixture_rehearsal_review = build_e2c_fixture_rehearsal_payload(
        clean_tokens, db_path, backup_confirmed=backup_confirmed
    )

    final_recommendation, final_reasons, e2c_status = _determine_final_recommendation(
        token_file_review, e2c_readiness_review, fixture_rehearsal_review
    )

    return {
        "command": "printer-review-bounded-15m-token-list-rehearsal",
        "dry_run": True,
        "operator_review_only": True,
        "e2c_closeout_candidate": True,
        "token_file_review": token_file_review,
        "e2c_readiness_review": e2c_readiness_review,
        "fixture_rehearsal_review": fixture_rehearsal_review,
        "hard_locks": dict(HARD_LOCKS),
        "final_recommendation": final_recommendation,
        "final_recommendation_reasons": final_reasons,
        "e2c_status": e2c_status,
    }
