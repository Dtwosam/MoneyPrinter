#!/usr/bin/env python3
"""Checkpoint 8 controlling-proof safety shell.

This file intentionally owns only the proof-only safety envelope at this stage:
the process-local network tripwire and the atomic one-shot attempt claim.

It does not construct fixtures, start Printer runtime work, or execute the
controlling proof. Those entry responsibilities remain fail-closed until the
subsequent Checkpoint 8 harness-wiring slice is proven.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
from typing import Any


_ATTEMPT_SENTINEL_NAME = "checkpoint8-controlling-attempt.json"


class Checkpoint8ControllingProofError(RuntimeError):
    """Fail-closed controlling-proof harness fault."""


class Checkpoint8NetworkTripwireError(Checkpoint8ControllingProofError):
    """Raised when the proof process attempts an external network operation."""


class Checkpoint8NetworkAttempt:
    """Minimal import-safe record for one blocked network attempt."""

    __slots__ = ("operation", "target")

    def __init__(self, *, operation: str, target: str) -> None:
        self.operation = operation
        self.target = target


def _redacted_target(value: Any) -> str:
    if isinstance(value, tuple) and value:
        host = str(value[0])
        port = value[1] if len(value) > 1 else None
        family = "IPV6" if ":" in host else "IP"
        return f"{family}:{port if port is not None else 'UNKNOWN'}"
    return type(value).__name__


class Checkpoint8NetworkTripwire:
    """Process-local socket tripwire used only by the C8 controlling harness."""

    def __init__(self) -> None:
        self.attempts: list[Checkpoint8NetworkAttempt] = []
        self._installed = False
        self._original_create_connection = None
        self._original_connect = None
        self._original_connect_ex = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def _record_and_fail(self, operation: str, target: Any) -> None:
        self.attempts.append(
            Checkpoint8NetworkAttempt(
                operation=operation,
                target=_redacted_target(target),
            )
        )
        raise Checkpoint8NetworkTripwireError(
            "CHECKPOINT8_EXTERNAL_NETWORK_ATTEMPT_FORBIDDEN"
        )

    def __enter__(self) -> "Checkpoint8NetworkTripwire":
        if self._installed:
            raise Checkpoint8NetworkTripwireError(
                "CHECKPOINT8_NETWORK_TRIPWIRE_ALREADY_INSTALLED"
            )

        self._original_create_connection = socket.create_connection
        self._original_connect = socket.socket.connect
        self._original_connect_ex = socket.socket.connect_ex
        tripwire = self

        def blocked_create_connection(address, *args, **kwargs):
            del args, kwargs
            tripwire._record_and_fail("socket.create_connection", address)

        def blocked_connect(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect", address)

        def blocked_connect_ex(sock, address):
            del sock
            tripwire._record_and_fail("socket.socket.connect_ex", address)

        socket.create_connection = blocked_create_connection
        socket.socket.connect = blocked_connect
        socket.socket.connect_ex = blocked_connect_ex
        self._installed = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._installed:
            socket.create_connection = self._original_create_connection
            socket.socket.connect = self._original_connect
            socket.socket.connect_ex = self._original_connect_ex
            self._installed = False
        return False


def claim_controlling_attempt_sentinel(
    proof_root: str | Path,
    *,
    proof_id: str,
    git_head: str,
) -> Path:
    """Atomically consume the single C8 controlling-attempt entitlement."""
    root = Path(proof_root).expanduser().resolve()
    if not root.is_dir():
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_PROOF_ROOT_MISSING"
        )

    proof = str(proof_id or "").strip()
    head = str(git_head or "").strip()
    if not proof:
        raise Checkpoint8ControllingProofError("CONTROLLING_PROOF_ID_MISSING")
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head.lower()):
        raise Checkpoint8ControllingProofError("CONTROLLING_GIT_HEAD_INVALID")

    sentinel = root / _ATTEMPT_SENTINEL_NAME
    payload = {
        "attempt_ordinal": 1,
        "git_head": head,
        "proof_id": proof,
        "sentinel_schema": "CHECKPOINT8_CONTROLLING_ATTEMPT_V1",
    }
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(sentinel, flags, 0o600)
    except FileExistsError as exc:
        raise Checkpoint8ControllingProofError(
            "CONTROLLING_ATTEMPT_ALREADY_CONSUMED"
        ) from exc

    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            sentinel.unlink()
        except FileNotFoundError:
            pass
        raise

    return sentinel


def main(argv: list[str] | None = None) -> int:
    del argv
    raise Checkpoint8ControllingProofError(
        "CHECKPOINT8_CONTROLLING_PROOF_ENTRY_NOT_YET_WIRED"
    )


if __name__ == "__main__":
    raise SystemExit(main())
