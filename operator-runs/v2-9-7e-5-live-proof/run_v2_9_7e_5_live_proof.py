"""V2-9.7E.5 — exactly one bounded read-only live proof of the reset architecture.

Tests the NEW prospective primary path:

- signature-anchored finalized polling on the create-exclusive Pump
  mint-authority index address;
- no getSlot, no cutoff, no subscription;
- finalized transaction confirmation via the pinned create decoder;
- durable registry persistence in a disposable target;
- zero-source deterministic replay.

The seven aged pilot mints are deliberately NOT a PASS dependency.

Proof-only. No production mutation. Free public Solana RPC only.
Zero retries, zero endpoint rotation, zero reconnect.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from printer_v1.db.migrate import apply_migrations
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import PumpContractError, decode_finalized_create
from printer_v1.sources.pumpfun_origin import (
    ACQUISITION_MODE_PROSPECTIVE,
    CREATE_INDEX_DECODE_CEILING,
    CREATE_INDEX_PAGE_CEILING,
    CREATE_INDEX_PAGE_SIZE,
    PUMP_CREATE_INDEX_ADDRESS,
    SCHEDULER_JOB_KIND,
    SCHEDULER_WORK_TYPE,
    SIGNATURE_PAGE_REQUEST,
    TRANSACTION_REQUEST,
    ContinuityState,
    FixtureOperation,
    load_origin_cursor,
    lookup_confirmed_origin,
    record_confirmed_origin,
    run_acquisition_cycle,
    save_origin_cursor,
)
from printer_v1.sources.pumpfun_direct import SignatureReference

PROVEN_HEAD = "3396dfc6833c15f96e2dd45aa0a405858e1cb290"
RPC_URL = "https://api.mainnet-beta.solana.com"
USER_AGENT = "PrinterV1/0.1 (+paper-only V2-9.7E.5 origin architecture proof)"
OPS = Path(__file__).resolve().parent

# Predeclared ceilings for this single session.
MAX_UNDERLYING = CREATE_INDEX_PAGE_CEILING + CREATE_INDEX_DECODE_CEILING  # 15
MAX_DURATION_SECONDS = 300
MAX_FAILURES = 5
# Matches INTAKE_STORAGE_BYTES in combined_executor. The empty migrated schema
# is already ~2.1 MB, so this bounds evidence growth, not schema baseline.
MAX_STORAGE_BYTES = 8 * 1024 * 1024
REQUIRED_CREATES = 2

PROOF_DB = OPS / "v2_9_7e_5_proof.sqlite3"
RESULT_PATH = OPS / "V2_9_7E_5_LIVE_PROOF_RESULT.json"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Budget:
    def __init__(self) -> None:
        self.underlying = 0
        self.by_method: Counter[str] = Counter()
        self.retries = 0
        self.endpoint_rotations = 0
        self.reconnects = 0
        self.failures = 0
        self.started = time.monotonic()

    def allow(self, n: int = 1) -> bool:
        return (
            self.underlying + n <= MAX_UNDERLYING
            and self.failures <= MAX_FAILURES
            and (time.monotonic() - self.started) < MAX_DURATION_SECONDS
        )

    def elapsed(self) -> int:
        return int(time.monotonic() - self.started)


def rpc_call(budget: Budget, method: str, params: list[Any]) -> dict[str, Any]:
    """One JSON-RPC call. Never retried, never rotated."""
    if not budget.allow(1):
        return {"ok": False, "error": "CEILING_REACHED", "body": None}
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": budget.underlying + 1, "method": method, "params": params}
    ).encode("utf-8")
    request = url_request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    budget.underlying += 1
    budget.by_method[method] += 1
    try:
        with url_request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = int(response.status)
    except url_error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        status = int(exc.code)
    except Exception as exc:  # noqa: BLE001
        budget.failures += 1
        return {"ok": False, "error": type(exc).__name__, "body": None}

    body: Any = None
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError:
        body = None
    ok = status == 200 and isinstance(body, dict) and body.get("error") is None
    if not ok:
        budget.failures += 1
    return {"ok": ok, "status": status, "body": body, "raw_sha256": sha256_bytes(raw)}


def op(request_id: str, request_kind: str, rpc_operation: str, response: Any) -> FixtureOperation:
    return FixtureOperation(
        request_id=request_id,
        request_kind=request_kind,
        rpc_operation=rpc_operation,
        response=response,
        source_name="solana_rpc",
        scheduler_job_kind=SCHEDULER_JOB_KIND,
        scheduler_work_type=SCHEDULER_WORK_TYPE,
    )


def normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    signature = row.get("signature")
    slot = row.get("slot")
    if not isinstance(signature, str) or type(slot) is not int:
        return None
    return {
        "signature": signature,
        "slot": slot,
        "confirmationStatus": row.get("confirmationStatus") or "finalized",
        "err": row.get("err"),
    }


def main() -> int:
    started_utc = utc_now()
    budget = Budget()
    notes: list[str] = []

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    if head != PROVEN_HEAD:
        print("V2_9_7E_5_BLOCKED_HEAD_MISMATCH")
        return 2

    governor = {
        kind: dict(
            allowed=can_request_source("solana_rpc", kind, 0).allowed,
            reason=can_request_source("solana_rpc", kind, 0).reason,
        )
        for kind in (SIGNATURE_PAGE_REQUEST, TRANSACTION_REQUEST)
    }
    if not all(entry["allowed"] for entry in governor.values()):
        print("V2_9_7E_5_BLOCKED_GOVERNOR_REJECTED_KIND")
        return 3

    # --- Live capture: one signature page on the create index address ------
    page_response = rpc_call(
        budget,
        "getSignaturesForAddress",
        [
            PUMP_CREATE_INDEX_ADDRESS,
            {"limit": CREATE_INDEX_PAGE_SIZE, "commitment": "finalized"},
        ],
    )
    raw_rows: list[dict[str, Any]] = []
    if page_response["ok"]:
        result = page_response["body"].get("result")
        if isinstance(result, list):
            raw_rows = [
                normalized
                for normalized in (
                    normalize_row(item) for item in result if isinstance(item, dict)
                )
                if normalized is not None
            ]
    else:
        notes.append(f"signature page failed: {page_response.get('error')}")

    # Owner admission order: finalized, successful, deduplicated, ascending
    # (slot, signature). This must match the owner's decode order exactly so
    # the planned transactions line up with the rows it will decode.
    deduplicated: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        if row["confirmationStatus"] != "finalized" or row["err"] is not None:
            continue
        previous = deduplicated.get(row["signature"])
        if previous is not None:
            if previous != row:
                deduplicated.pop(row["signature"])
                notes.append("conflicting duplicate signature observed")
            continue
        deduplicated[row["signature"]] = row
    admitted = sorted(
        deduplicated.values(), key=lambda item: (item["slot"], item["signature"])
    )

    # --- Bounded finalized confirmation, stopping at two creates -----------
    transaction_ops: list[FixtureOperation] = []
    confirmed_preview = 0
    decode_outcomes: list[dict[str, Any]] = []
    for index, row in enumerate(admitted, start=1):
        if confirmed_preview >= REQUIRED_CREATES:
            notes.append("stopped after two confirmed creates")
            break
        if not budget.allow(1) or len(transaction_ops) >= CREATE_INDEX_DECODE_CEILING:
            notes.append("stopped at predeclared ceiling")
            break
        transaction_response = rpc_call(
            budget,
            "getTransaction",
            [
                row["signature"],
                {
                    "encoding": "json",
                    "commitment": "finalized",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        body = (
            transaction_response["body"].get("result")
            if transaction_response["ok"]
            else None
        )
        transaction_ops.append(op(f"tx-{index}", TRANSACTION_REQUEST, "getTransaction", body))
        reference = SignatureReference(
            row["signature"], row["slot"], row["confirmationStatus"], row["err"]
        )
        try:
            decode_finalized_create(body, reference=reference, cutoff_slot=row["slot"])
        except PumpContractError as exc:
            decode_outcomes.append({"ordinal": index, "code": exc.code})
        except Exception as exc:  # noqa: BLE001
            decode_outcomes.append({"ordinal": index, "code": type(exc).__name__})
        else:
            confirmed_preview += 1
            decode_outcomes.append({"ordinal": index, "code": "CREATE_CONFIRMED"})

    # --- Authoritative owner run over the captured session -----------------
    operations = (
        op("page-1", SIGNATURE_PAGE_REQUEST, "getSignaturesForAddress", {"rows": raw_rows}),
        *transaction_ops,
    )
    owner_error: str | None = None
    try:
        cycle = run_acquisition_cycle(operations)
    except PumpContractError as exc:
        owner_error = exc.code
        cycle = None
    except Exception as exc:  # noqa: BLE001
        owner_error = type(exc).__name__
        cycle = None

    observations = list(cycle.observations) if cycle is not None else []
    distinct_mints = sorted({observation.mint for observation in observations})

    # --- Durable persistence in a disposable target ------------------------
    if PROOF_DB.exists():
        PROOF_DB.unlink()
    apply_migrations(PROOF_DB)
    connection = sqlite3.connect(PROOF_DB)
    connection.row_factory = sqlite3.Row
    persisted = 0
    persistence_error: str | None = None
    try:
        for observation in observations:
            if record_confirmed_origin(
                connection,
                observation,
                now=started_utc,
                acquisition_mode=ACQUISITION_MODE_PROSPECTIVE,
            ):
                persisted += 1
        if cycle is not None:
            save_origin_cursor(connection, cycle.cursor, now=started_utc)
        connection.commit()
    except Exception as exc:  # noqa: BLE001
        connection.rollback()
        persistence_error = type(exc).__name__
    finally:
        connection.close()

    # --- Zero-source deterministic replay ----------------------------------
    replay_rpc_before = budget.underlying
    replay = sqlite3.connect(f"file:{PROOF_DB.as_posix()}?mode=ro", uri=True)
    replay.row_factory = sqlite3.Row
    replay_lookups = {
        mint[:8]: lookup_confirmed_origin(replay, mint) is not None
        for mint in distinct_mints
    }
    replay_cursor = load_origin_cursor(replay)
    replay.close()
    replay_used_zero_rpc = budget.underlying == replay_rpc_before

    canonical_stable = False
    if cycle is not None:
        try:
            canonical_stable = (
                run_acquisition_cycle(operations).canonical() == cycle.canonical()
            )
        except Exception:  # noqa: BLE001
            canonical_stable = False

    storage_bytes = PROOF_DB.stat().st_size if PROOF_DB.exists() else 0

    # --- Verdict ------------------------------------------------------------
    passed = (
        owner_error is None
        and persistence_error is None
        and len(distinct_mints) >= REQUIRED_CREATES
        and persisted >= REQUIRED_CREATES
        and all(replay_lookups.values())
        and replay_used_zero_rpc
        and canonical_stable
        and budget.underlying <= MAX_UNDERLYING
        and budget.retries == 0
        and budget.endpoint_rotations == 0
        and budget.reconnects == 0
        and budget.failures <= MAX_FAILURES
        and storage_bytes <= MAX_STORAGE_BYTES
        and budget.elapsed() <= MAX_DURATION_SECONDS
    )

    payload = {
        "lane": "V2-9.7E.5",
        "proven_head": PROVEN_HEAD,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "rpc_url": RPC_URL,
        "index_address": PUMP_CREATE_INDEX_ADDRESS,
        "architecture": "SIGNATURE_ANCHORED_PROSPECTIVE",
        "governor": governor,
        "capture": {
            "signature_rows": len(raw_rows),
            "admitted_rows": len(admitted),
            "decode_attempts": len(transaction_ops),
            "decode_outcomes": decode_outcomes,
            "create_density": (
                round(confirmed_preview / len(transaction_ops), 3)
                if transaction_ops
                else None
            ),
        },
        "owner": {
            "error": owner_error,
            "observations": len(observations),
            "distinct_mints": len(distinct_mints),
            "mint_prefixes": [mint[:8] for mint in distinct_mints],
            "signature_prefixes": [
                observation.signature[:8] for observation in observations
            ],
            "slots": [observation.slot for observation in observations],
            "program_ids": sorted(
                {observation.program_id for observation in observations}
            ),
            "continuity": str(cycle.cursor.continuity) if cycle else None,
            "pages_used": cycle.pages_used if cycle else 0,
            "non_create_count": cycle.non_create_count if cycle else 0,
            "create_v2_count": cycle.create_v2_count if cycle else 0,
            "underlying_rpc_operations": (
                cycle.accounting.underlying_rpc_operations if cycle else 0
            ),
        },
        "persistence": {
            "error": persistence_error,
            "rows_written": persisted,
            "storage_bytes": storage_bytes,
            "disposable_target": str(PROOF_DB.name),
        },
        "replay": {
            "zero_source": replay_used_zero_rpc,
            "exact_mint_lookups_ok": replay_lookups,
            "cursor_continuity": str(replay_cursor.continuity),
            "canonical_stable": canonical_stable,
        },
        "accounting": {
            "underlying_total": budget.underlying,
            "by_method": dict(budget.by_method),
            "ceiling": MAX_UNDERLYING,
            "retries": budget.retries,
            "endpoint_rotations": budget.endpoint_rotations,
            "reconnects": budget.reconnects,
            "failures": budget.failures,
            "duration_seconds": budget.elapsed(),
        },
        "provider_label_origin": False,
        "notes": notes,
        "verdict": "PASS" if passed else "BLOCKED",
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
