"""Reviewed admission-schema pin and read-only coherence evaluator.

The ordered ``migrations/*.sql`` catalogue remains the source of migration
*names*. This module owns the reviewed *admission pin* as explicit literals so
a future catalogue file cannot silently re-authorize campaign admission.

``admission_schema_ready`` is a schema prerequisite only. It is never campaign
GO, never authorization, and never a reason to apply migrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from printer_v1.db.migrate import (
    canonical_migration_names,
    ordered_name_digest,
    validate_migration_ledger,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
    MIGRATION_060_REQUIRED_INDEXES,
    MIGRATION_060_REQUIRED_TABLES,
    MIGRATION_060_REQUIRED_TRIGGERS,
    MIGRATION_061_REQUIRED_INDEXES,
    MIGRATION_061_REQUIRED_TABLES,
    MIGRATION_061_REQUIRED_TRIGGERS,
    MIGRATION_062_REQUIRED_INDEXES,
    MIGRATION_062_REQUIRED_TABLES,
    MIGRATION_062_REQUIRED_TRIGGERS,
    inspect_required_schema_objects,
)


REQUIRED_MIGRATION_COUNT = 62
REQUIRED_MIGRATION_HEAD = (
    "062_pre_admission_attempt_evidence.sql"
)

SCHEMA_EXPECTATION_MISMATCH = "schema_expectation_mismatch"


@dataclass(frozen=True)
class SchemaAdmissionCoherenceResult:
    """Underlying schema-admission facts. Not a score and not campaign GO."""

    catalogue_valid: bool
    catalogue_count: int
    catalogue_head: str | None
    catalogue_digest: str | None
    expected_count: int
    expected_head: str
    pin_matches_catalogue: bool
    db_target_path: str
    expected_target_path: str
    db_target_matches_authoritative: bool
    db_readable: bool
    sidecars: tuple[str, ...]
    integrity: str | None
    foreign_key_violations: int | None
    applied_count: int | None
    applied_head: str | None
    applied_ledger: tuple[str, ...]
    ledger_digest: str | None
    ledger_matches_catalogue: bool
    ledger_is_canonical_prefix: bool
    migration_060_objects_ready: bool
    migration_061_objects_ready: bool
    migration_062_objects_ready: bool
    partial_application: bool
    admission_schema_ready: bool
    blocker_codes: tuple[str, ...]
    object_issues: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        if self.admission_schema_ready:
            return (
                "schema admission coherence: schema-ready "
                "(not campaign GO)"
            )
        codes = ", ".join(self.blocker_codes) or "blocked"
        return f"schema admission coherence blocked: {codes}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalogue_valid": self.catalogue_valid,
            "catalogue_count": self.catalogue_count,
            "catalogue_head": self.catalogue_head,
            "catalogue_digest": self.catalogue_digest,
            "expected_count": self.expected_count,
            "expected_head": self.expected_head,
            "pin_matches_catalogue": self.pin_matches_catalogue,
            "db_target_path": self.db_target_path,
            "expected_target_path": self.expected_target_path,
            "db_target_matches_authoritative": (
                self.db_target_matches_authoritative
            ),
            "db_readable": self.db_readable,
            "sidecars": list(self.sidecars),
            "integrity": self.integrity,
            "foreign_key_violations": self.foreign_key_violations,
            "applied_count": self.applied_count,
            "applied_head": self.applied_head,
            "applied_ledger": list(self.applied_ledger),
            "ledger_digest": self.ledger_digest,
            "ledger_matches_catalogue": self.ledger_matches_catalogue,
            "ledger_is_canonical_prefix": self.ledger_is_canonical_prefix,
            "migration_060_objects_ready": self.migration_060_objects_ready,
            "migration_061_objects_ready": self.migration_061_objects_ready,
            "migration_062_objects_ready": self.migration_062_objects_ready,
            "partial_application": self.partial_application,
            "admission_schema_ready": self.admission_schema_ready,
            "blocker_codes": list(self.blocker_codes),
            "object_issues": list(self.object_issues),
            "campaign_authorized": False,
            "application_marker_created": False,
            "cycle_3_unlocked": False,
        }


def _canonical_target() -> Path:
    return Path(CANONICAL_PERSISTENT_DB).resolve()


def _issues_name_hit(issues: Sequence[str], names: Iterable[str]) -> bool:
    labels = tuple(names)
    if not labels:
        return False
    return any(any(name in issue for name in labels) for issue in issues)


def evaluate_schema_admission_coherence(
    *,
    db_path: str | Path,
    migrations_dir: str | Path | None = None,
    expected_target: str | Path | None = None,
) -> SchemaAdmissionCoherenceResult:
    """Read-only comparison of pin, catalogue, ledger, objects, and target.

    ``expected_target is None`` means the canonical persistent corpus file.
    The target check is never skipped. Production callers must not pass a
    disposable path.
    """
    from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
        inspect_authoritative_database,
    )

    directory = Path(migrations_dir) if migrations_dir is not None else None
    blockers: list[str] = []
    catalogue_names: list[str] = []
    catalogue_valid = False
    catalogue_digest: str | None = None
    try:
        catalogue_names = list(canonical_migration_names(directory))
        catalogue_valid = True
        catalogue_digest = ordered_name_digest(catalogue_names)
    except RuntimeError:
        blockers.append("catalogue_invalid")

    catalogue_count = len(catalogue_names)
    catalogue_head = catalogue_names[-1] if catalogue_names else None
    pin_matches_catalogue = (
        catalogue_valid
        and REQUIRED_MIGRATION_COUNT == catalogue_count
        and REQUIRED_MIGRATION_HEAD == catalogue_head
    )
    if catalogue_valid and not pin_matches_catalogue:
        blockers.append(SCHEMA_EXPECTATION_MISMATCH)

    resolved_db = Path(db_path).resolve()
    resolved_expected = (
        Path(expected_target).resolve()
        if expected_target is not None
        else _canonical_target()
    )
    db_target_matches = resolved_db == resolved_expected
    if not db_target_matches:
        blockers.append("db_target_mismatch")

    identity = inspect_authoritative_database(resolved_db)
    sidecars = tuple(str(item) for item in (identity.get("sidecars") or ()))
    db_readable = identity.get("readable") is True
    if sidecars:
        blockers.append("authoritative_sidecars_present")
    if not db_readable:
        blockers.append("database_unavailable")

    integrity_rows = list(identity.get("integrity") or ())
    integrity: str | None
    if not db_readable:
        integrity = None
    elif integrity_rows == ["ok"]:
        integrity = "ok"
    else:
        integrity = ",".join(integrity_rows) if integrity_rows else "uninspectable"
        blockers.append("integrity_check_failed")

    foreign_key_violations: int | None
    if not db_readable:
        foreign_key_violations = None
    else:
        foreign_key_violations = int(identity.get("foreign_key_violations") or 0)
        if foreign_key_violations:
            blockers.append("foreign_key_violations")

    applied = tuple(str(item) for item in (identity.get("migration_ledger") or ()))
    applied_count = len(applied) if db_readable else None
    applied_head = applied[-1] if applied else None
    ledger_digest = (
        str(identity["ledger_digest"])
        if db_readable and identity.get("ledger_digest")
        else None
    )

    ledger_matches = False
    ledger_is_prefix = False
    if catalogue_valid and db_readable:
        report = validate_migration_ledger(applied, migrations_dir=directory)
        ledger_matches = report["matches"] is True
        ledger_is_prefix = list(applied) == catalogue_names[: len(applied)]
        if applied_count != catalogue_count:
            blockers.append("migration_count_mismatch")
        if applied_head != catalogue_head:
            blockers.append("migration_head_mismatch")
        missing = [name for name in catalogue_names if name not in set(applied)]
        unexpected = [name for name in applied if name not in set(catalogue_names)]
        if missing:
            blockers.append("migration_ledger_missing")
        if unexpected:
            blockers.append("migration_ledger_unexpected")
        if not ledger_is_prefix and applied:
            blockers.append("migration_ledger_out_of_order")

    object_issues: tuple[str, ...] = ()
    migration_060_ready = False
    migration_061_ready = False
    migration_062_ready = False
    if db_readable:
        import sqlite3

        try:
            connection = sqlite3.connect(
                f"file:{resolved_db.as_posix()}?mode=ro&immutable=1",
                uri=True,
                timeout=0.0,
            )
        except sqlite3.Error:
            blockers.append("schema_state_uninspectable")
            connection = None
        else:
            try:
                connection.execute("PRAGMA query_only=ON")
                object_issues = tuple(
                    str(item)
                    for item in inspect_required_schema_objects(connection)["issues"]
                )
            except sqlite3.Error:
                blockers.append("schema_state_uninspectable")
            finally:
                connection.close()
        if "schema_state_uninspectable" not in blockers:
            names_060 = (
                set(MIGRATION_060_REQUIRED_TABLES)
                | set(MIGRATION_060_REQUIRED_TRIGGERS)
                | set(MIGRATION_060_REQUIRED_INDEXES)
            )
            names_061 = (
                set(MIGRATION_061_REQUIRED_TABLES)
                | set(MIGRATION_061_REQUIRED_TRIGGERS)
                | set(MIGRATION_061_REQUIRED_INDEXES)
            )
            migration_060_ready = not _issues_name_hit(object_issues, names_060)
            migration_061_ready = not _issues_name_hit(object_issues, names_061)
            names_062 = (
                set(MIGRATION_062_REQUIRED_TABLES)
                | set(MIGRATION_062_REQUIRED_TRIGGERS)
                | set(MIGRATION_062_REQUIRED_INDEXES)
            )
            migration_062_ready = not _issues_name_hit(object_issues, names_062)
            if object_issues:
                blockers.append("required_schema_object_missing")

    mixed_objects = len(
        {migration_060_ready, migration_061_ready, migration_062_ready}
    ) > 1
    objects_complete = (
        migration_060_ready and migration_061_ready and migration_062_ready
    )
    partial_application = bool(
        (ledger_is_prefix and not ledger_matches)
        or mixed_objects
        or (objects_complete and not ledger_matches)
        or (ledger_matches and not objects_complete)
    )
    if partial_application:
        blockers.append("partial_migration_application")

    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered_blockers: list[str] = []
    for code in blockers:
        if code not in seen:
            seen.add(code)
            ordered_blockers.append(code)

    admission_schema_ready = (
        catalogue_valid
        and pin_matches_catalogue
        and db_target_matches
        and db_readable
        and not sidecars
        and integrity == "ok"
        and foreign_key_violations == 0
        and ledger_matches
        and ledger_is_prefix
        and objects_complete
        and not partial_application
        and not object_issues
        and applied_count == REQUIRED_MIGRATION_COUNT
        and applied_head == REQUIRED_MIGRATION_HEAD
        and not ordered_blockers
    )

    return SchemaAdmissionCoherenceResult(
        catalogue_valid=catalogue_valid,
        catalogue_count=catalogue_count,
        catalogue_head=catalogue_head,
        catalogue_digest=catalogue_digest,
        expected_count=REQUIRED_MIGRATION_COUNT,
        expected_head=REQUIRED_MIGRATION_HEAD,
        pin_matches_catalogue=pin_matches_catalogue,
        db_target_path=str(resolved_db),
        expected_target_path=str(resolved_expected),
        db_target_matches_authoritative=db_target_matches,
        db_readable=db_readable,
        sidecars=sidecars,
        integrity=integrity,
        foreign_key_violations=foreign_key_violations,
        applied_count=applied_count,
        applied_head=applied_head,
        applied_ledger=applied,
        ledger_digest=ledger_digest,
        ledger_matches_catalogue=ledger_matches,
        ledger_is_canonical_prefix=ledger_is_prefix,
        migration_060_objects_ready=migration_060_ready,
        migration_061_objects_ready=migration_061_ready,
        migration_062_objects_ready=migration_062_ready,
        partial_application=partial_application,
        admission_schema_ready=admission_schema_ready,
        blocker_codes=tuple(ordered_blockers),
        object_issues=object_issues,
    )


__all__ = [
    "REQUIRED_MIGRATION_COUNT",
    "REQUIRED_MIGRATION_HEAD",
    "SCHEMA_EXPECTATION_MISMATCH",
    "SchemaAdmissionCoherenceResult",
    "evaluate_schema_admission_coherence",
]
