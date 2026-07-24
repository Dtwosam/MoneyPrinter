"""V2-9.7E.45 Repair 1 — canonical graduated-registry bootstrap and isolated export.

Two bounded, fail-closed helpers around the single canonical graduated-candidate
registry (``printer_pumpswap_graduated_candidate_registry``, migration 040). Both
reuse the registry owner's export/import; neither adds a second registry, a source
call, a score/rank, or crosses any campaign/lifecycle/memory boundary.

* ``bootstrap_from_prior_registry`` — one bounded governed import of proven prior
  graduated evidence from a retained prior registry DB into the canonical registry.
  Every row must pass exact-mint, exact-signature, exact-pool, exact
  provenance/evidence-hash recomputation, source-policy compatibility and integrity
  checks, or it is skipped with an explicit reason (never a partial/forced import).
* ``export_isolated_attempt_registry`` — a deterministic, replayable, candidate-only
  immutable export of the canonical registry into a fresh isolated attempt DB, with
  provenance hashes and an export identity, crossing no campaign/lifecycle/memory row.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from printer_v1.db import apply_migrations
from printer_v1.sources.pumpswap_graduated_registry import (
    CONTRACT_VERSION,
    GraduatedCandidateError,
    _EXPORT_COLUMNS,
    export_graduated_candidates,
    graduated_registry_exists,
    graduation_evidence_hash,
    import_graduated_candidate_row,
)

# Contract versions whose stored evidence is policy-compatible with the current
# canonical registry. Extend only with a deliberate, reviewed policy decision.
COMPATIBLE_CONTRACT_VERSIONS = frozenset({CONTRACT_VERSION})

# Columns that must never appear in a graduated-registry export row: any of these
# would mean campaign/lifecycle/memory state is crossing the candidate boundary.
FORBIDDEN_IMPORT_COLUMNS = frozenset(
    {
        "campaign_id",
        "run_id",
        "cycle_id",
        "authorization_id",
        "slot_ordinal",
        "token_state",
        "lifecycle_state_forward",
        "snapshot_id",
        "memory_id",
        "retrieval_id",
        "decision_id",
        "position_id",
        "trade_id",
        "pnl",
        "paper_audit_id",
    }
)


class BootstrapError(RuntimeError):
    """Fail-closed bootstrap fault."""


@dataclass
class BootstrapReport:
    imported: int = 0
    skipped: int = 0
    already_present: int = 0
    skip_reasons: list[dict[str, str]] = field(default_factory=list)
    source_row_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported": self.imported,
            "skipped": self.skipped,
            "already_present": self.already_present,
            "source_row_count": self.source_row_count,
            "skip_reasons": list(self.skip_reasons),
        }


def _row_is_valid(row: Mapping[str, Any]) -> tuple[bool, str]:
    mint = str(row.get("mint_identity") or "").strip()
    signature = str(row.get("migration_signature") or "").strip()
    pool = str(row.get("pumpswap_pool") or "").strip()
    if not mint:
        return False, "MISSING_MINT_IDENTITY"
    if not signature:
        return False, "MISSING_MIGRATION_SIGNATURE"
    if not pool:
        return False, "MISSING_PUMPSWAP_POOL"
    if row.get("graduation_block_time") is None:
        return False, "MISSING_GRADUATION_BLOCK_TIME"
    contract = str(row.get("contract_version") or "")
    if contract not in COMPATIBLE_CONTRACT_VERSIONS:
        return False, f"INCOMPATIBLE_CONTRACT_VERSION:{contract}"
    stored_hash = str(row.get("confirmation_evidence_hash") or "")
    try:
        recomputed = graduation_evidence_hash(
            mint=mint,
            migration_signature=signature,
            pumpswap_pool=pool,
            graduation_block_time=int(row["graduation_block_time"]),
            graduation_slot=(
                None
                if row.get("graduation_slot") is None
                else int(row["graduation_slot"])
            ),
            base_mint_offset=int(row["base_mint_offset"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"EVIDENCE_HASH_RECOMPUTE_ERROR:{type(exc).__name__}"
    if recomputed != stored_hash:
        return False, "EVIDENCE_HASH_MISMATCH"
    return True, "OK"


def _source_columns(source: sqlite3.Connection) -> set[str]:
    cols = source.execute(
        "SELECT name FROM pragma_table_info('printer_pumpswap_graduated_candidate_registry')"
    ).fetchall()
    return {str(c[0]) for c in cols}


def bootstrap_from_prior_registry(
    canonical: sqlite3.Connection, source_db_path: str | Path
) -> BootstrapReport:
    """Import proven prior graduated evidence from ``source_db_path``.

    Fail-closed: an integrity failure, a foreign-key violation, a forbidden
    campaign/lifecycle/memory column, or a missing registry table aborts the whole
    import (nothing is written). Individual rows failing provenance validation are
    skipped with a recorded reason; valid rows are imported idempotently.
    """
    source_path = Path(source_db_path)
    if not source_path.exists():
        raise BootstrapError(f"SOURCE_DB_NOT_FOUND:{source_path}")
    if not graduated_registry_exists(canonical):
        raise BootstrapError("CANONICAL_REGISTRY_MISSING")

    source = sqlite3.connect(str(source_path))
    source.row_factory = sqlite3.Row
    report = BootstrapReport()
    try:
        if not graduated_registry_exists(source):
            raise BootstrapError("SOURCE_REGISTRY_MISSING")
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BootstrapError("SOURCE_INTEGRITY_FAILED")
        if source.execute("PRAGMA foreign_key_check").fetchall():
            raise BootstrapError("SOURCE_FOREIGN_KEY_VIOLATION")
        forbidden = _source_columns(source) & FORBIDDEN_IMPORT_COLUMNS
        if forbidden:
            raise BootstrapError(f"FORBIDDEN_COLUMN_PRESENT:{sorted(forbidden)}")

        rows = export_graduated_candidates(source)
        report.source_row_count = len(rows)
        for row in rows:
            ok, reason = _row_is_valid(row)
            if not ok:
                report.skipped += 1
                report.skip_reasons.append(
                    {"mint": str(row.get("mint_identity")), "reason": reason}
                )
                continue
            clean = {col: row[col] for col in _EXPORT_COLUMNS}
            try:
                newly = import_graduated_candidate_row(canonical, clean)
            except GraduatedCandidateError as exc:
                report.skipped += 1
                report.skip_reasons.append(
                    {"mint": str(row.get("mint_identity")), "reason": exc.code}
                )
                continue
            if newly:
                report.imported += 1
            else:
                report.already_present += 1
        canonical.commit()
    finally:
        source.close()
    return report


@dataclass
class IsolatedExportReport:
    export_identity: str
    exported: int
    provenance_hash: str
    attempt_db_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "export_identity": self.export_identity,
            "exported": self.exported,
            "provenance_hash": self.provenance_hash,
            "attempt_db_path": self.attempt_db_path,
        }


def export_isolated_attempt_registry(
    source_db_path: str | Path,
    attempt_db_path: str | Path,
    *,
    export_identity: str,
) -> IsolatedExportReport:
    """Copy the canonical registry into a fresh isolated attempt DB (candidate-only).

    Deterministic and replayable: rows are exported in the registry's canonical
    ``(graduation_block_time, mint_identity)`` order and imported verbatim. The
    provenance hash is the sha256 of the ordered evidence-hash sequence, binding the
    export identity to the exact set of candidate rows. No campaign/lifecycle/memory
    row is copied.
    """
    if not str(export_identity or "").strip():
        raise BootstrapError("MISSING_EXPORT_IDENTITY")
    attempt_path = Path(attempt_db_path)
    apply_migrations(attempt_path)

    source = sqlite3.connect(str(source_db_path))
    source.row_factory = sqlite3.Row
    attempt = sqlite3.connect(str(attempt_path))
    attempt.row_factory = sqlite3.Row
    attempt.execute("PRAGMA foreign_keys = ON")
    try:
        rows = export_graduated_candidates(source)
        hasher = hashlib.sha256(export_identity.encode("utf-8"))
        exported = 0
        for row in rows:
            clean = {col: row[col] for col in _EXPORT_COLUMNS}
            import_graduated_candidate_row(attempt, clean)
            hasher.update(str(row["confirmation_evidence_hash"]).encode("utf-8"))
            exported += 1
        attempt.commit()
        provenance_hash = hasher.hexdigest()
    finally:
        source.close()
        attempt.close()
    return IsolatedExportReport(
        export_identity=export_identity,
        exported=exported,
        provenance_hash=provenance_hash,
        attempt_db_path=str(attempt_path),
    )
