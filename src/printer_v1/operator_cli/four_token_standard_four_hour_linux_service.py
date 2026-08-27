"""Native Linux/systemd entrypoint for one authorized Printer V1 4/2/2 run.

This module is infrastructure glue around the existing one-shot wrapper. It owns
no discovery, source, Scheduler, campaign, window, retrieval, or financial
policy and never launches the operational child directly outside the wrapper's
single process-launcher boundary.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
from typing import Any, Callable, Mapping

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    StopSignalState,
    assert_local_ext4_paths,
    assert_remote_disk_space,
    assert_system_time_synchronized,
    launch_child_foreground,
    linux_verified_host_process_inventory,
)


def build_filesystem_preflight_paths(
    *,
    authoritative_db_path: str | Path,
    application_root: str | Path,
    artifact_root: str | Path,
) -> dict[str, Path]:
    database = Path(authoritative_db_path).expanduser().resolve()
    return {
        "authoritative_db": database,
        "authoritative_db_parent": database.parent,
        "application_root": Path(application_root).expanduser().resolve(),
        "operational_artifact_root": Path(artifact_root).expanduser().resolve(),
    }


def _default_repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def run_linux_service(
    *,
    authorization_file: str | Path,
    authorization_sha256: str,
    operator_approved: bool,
    repository_root: str | Path | None = None,
    application_root: str | Path | None = None,
    authoritative_db_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    filesystem_preflight: Callable[..., Mapping[str, Any]] = assert_local_ext4_paths,
    disk_space_preflight: Callable[..., Mapping[str, Any]] = assert_remote_disk_space,
    time_sync_preflight: Callable[..., Mapping[str, Any]] = assert_system_time_synchronized,
    storage_growth_ceiling_bytes: int | None = None,
    apply_authorization: Callable[..., Mapping[str, Any]] | None = None,
    stop_state: StopSignalState | None = None,
) -> dict[str, Any]:
    """Preflight Linux host readiness, then enter the one-shot wrapper once."""
    if not sys.platform.startswith("linux"):
        raise LinuxPortabilityError("native remote-host service requires Linux")
    if operator_approved is not True:
        raise LinuxPortabilityError("explicit operator approval is required")

    root = Path(repository_root or _default_repository_root()).resolve()
    if application_root is None or apply_authorization is None:
        from printer_v1.operator_cli import (
            four_token_standard_four_hour_one_shot_wrapper as wrapper,
        )

        if application_root is None:
            application_root = wrapper.APPLICATION_ROOT
        if apply_authorization is None:
            apply_authorization = wrapper.apply_authorization_once
    if (
        authoritative_db_path is None
        or artifact_root is None
        or storage_growth_ceiling_bytes is None
    ):
        from printer_v1.operator_cli import operational_memory_factory_command as command

        if authoritative_db_path is None:
            authoritative_db_path = command.AUTHORITATIVE_DB
        if artifact_root is None:
            artifact_root = command.ARTIFACT_ROOT
        if storage_growth_ceiling_bytes is None:
            storage_growth_ceiling_bytes = command.STORAGE_BYTE_CEILING

    database = Path(authoritative_db_path).resolve()
    app_root = Path(application_root).expanduser().resolve()
    artifacts = Path(artifact_root).expanduser().resolve()
    state = stop_state or StopSignalState()
    previous_handlers: dict[int, Any] = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, state.handle_signal)

    preflight_paths = build_filesystem_preflight_paths(
        authoritative_db_path=database,
        application_root=app_root,
        artifact_root=artifacts,
    )

    def process_launcher(**kwargs: Any) -> Mapping[str, Any]:
        return launch_child_foreground(
            **kwargs,
            authoritative_db_path=database,
            stop_state=state,
        )

    try:
        filesystem_evidence = dict(filesystem_preflight(preflight_paths))
        if state.requested:
            raise LinuxPortabilityError(
                "stop requested before authorization consumption"
            )
        disk_space_evidence = dict(
            disk_space_preflight(
                authoritative_db_path=database,
                write_paths={
                    "authoritative_db_parent": database.parent,
                    "application_root": app_root,
                    "operational_artifact_root": artifacts,
                },
                storage_growth_ceiling_bytes=int(storage_growth_ceiling_bytes),
            )
        )
        if state.requested:
            raise LinuxPortabilityError(
                "stop requested before authorization consumption"
            )
        time_sync_evidence = dict(time_sync_preflight())
        if state.requested:
            raise LinuxPortabilityError(
                "stop requested before authorization consumption"
            )
        result = dict(
            apply_authorization(
                authorization_file=authorization_file,
                authorization_sha256=authorization_sha256,
                operator_approved=True,
                repository_root=root,
                application_root=app_root,
                process_launcher=process_launcher,
                authoritative_db_path=database,
                printer_host_process_inventory=linux_verified_host_process_inventory,
            )
        )
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    result["filesystem_preflight"] = filesystem_evidence
    result["host_readiness"] = {
        "disk_space": disk_space_evidence,
        "time_sync": time_sync_evidence,
    }
    result["linux_service"] = {
        "wrapper_owned": True,
        "direct_child_launch": False,
        "automatic_restart": False,
        "signal_count": state.signal_count,
        "cooperative_cancellation_attempted": state.cancellation_attempted,
    }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printer-v1-four-token-standard-four-hour-linux-service"
    )
    parser.add_argument("--authorization-file", required=True)
    parser.add_argument("--authorization-sha256", required=True)
    parser.add_argument("--operator-approved", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_linux_service(
        authorization_file=args.authorization_file,
        authorization_sha256=args.authorization_sha256,
        operator_approved=bool(args.operator_approved),
    )
    classification = str(result.get("terminal_classification") or "")
    return 0 if classification == "CHILD_EXITED_ZERO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
