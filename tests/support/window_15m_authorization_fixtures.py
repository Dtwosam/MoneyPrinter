"""Offline validated-authorization fixtures for ordinary WINDOW_15M tests."""

import hashlib
from pathlib import Path

from printer_v1.db.migrate import canonical_migration_names
from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    ValidatedGitProvenanceAuthorization,
)


def validated_window_15m_authorization(
    *, database_sha256: str | None = None
) -> ValidatedGitProvenanceAuthorization:
    from printer_v1.operator_cli import operational_memory_factory_command as command

    database = Path(command.AUTHORITATIVE_DB).resolve()
    observed_sha256 = (
        hashlib.sha256(database.read_bytes()).hexdigest()
        if database_sha256 is None
        else database_sha256
    )
    migrations = canonical_migration_names()
    return ValidatedGitProvenanceAuthorization(
        allowed_untracked_paths=(),
        authorization_id="offline-window-15m-authorization",
        manifest_sha256="b" * 64,
        marker_sha256="c" * 64,
        allowed_file_set_sha256="d" * 64,
        file_count=0,
        authorization_consumed_once=True,
        invocation_count=1,
        allowed_invocation_count=1,
        automatic_retry_allowed=False,
        manual_rerun_allowed=False,
        resume_allowed=False,
        restart_allowed=False,
        successor_allowed=False,
        authoritative_database={
            "path": str(database),
            "sha256": observed_sha256,
            "size": database.stat().st_size,
            "inode": database.stat().st_ino,
            "mtime_ns": database.stat().st_mtime_ns,
            "migration_count": len(migrations),
            "migration_head": migrations[-1],
        },
    )
