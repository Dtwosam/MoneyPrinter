"""V2-9.7E.6 Phase 3 — one bounded read-only live Pump create classification capture.

Answers the question V2-9.7E.5A could not: which branch actually fires on live
create-index traffic. Records transaction-envelope classification separately
from Pump discriminator classification, so no outcome is conflated.

Read-only. No production mutation. Free public Solana RPC only.
One signature request. Zero retries. Zero endpoint rotation.
Stores discriminators (public protocol constants) and counts — never raw payloads.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from printer_v1.sources.pumpfun_direct import (
    CREATE_DISCRIMINATOR,
    CREATE_EVENT_DISCRIMINATOR,
    CREATE_V2_DISCRIMINATOR,
    EVENT_CPI_WRAPPER,
    MINT_AUTHORITY_ID,
    PUMP_PROGRAM_ID,
    PumpContractError,
    SignatureReference,
    _b58decode,
    decode_finalized_create,
)
from printer_v1.sources.pumpfun_origin import (
    CREATE_INDEX_DECODE_CEILING,
    CREATE_INDEX_PAGE_SIZE,
    PUMP_CREATE_INDEX_ADDRESS,
)

PROVEN_HEAD = "c2ecff6cb7c1b8c80dd520a907710cd50f76ed00"
RPC_URL = "https://api.mainnet-beta.solana.com"
USER_AGENT = "PrinterV1/0.1 (+paper-only V2-9.7E.6 create classification capture)"
ROOT = Path(__file__).resolve().parents[2]
OPS = Path(__file__).resolve().parent

MAX_UNDERLYING = 15
MAX_DURATION_SECONDS = 300
CAPTURE_TIMEOUT = 120
TRANSACTION_TIMEOUT = 45

RESULT_PATH = OPS / "V2_9_7E_6_CLASSIFICATION_RESULT.json"

KNOWN_DISCRIMINATORS = {
    CREATE_DISCRIMINATOR.hex(): "create",
    CREATE_V2_DISCRIMINATOR.hex(): "create_v2",
    CREATE_EVENT_DISCRIMINATOR.hex(): "CreateEvent",
    (EVENT_CPI_WRAPPER + CREATE_EVENT_DISCRIMINATOR).hex()[:16]: "event_cpi_wrapper",
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


class Budget:
    def __init__(self) -> None:
        self.underlying = 0
        self.by_method: Counter[str] = Counter()
        self.retries = 0
        self.endpoint_rotations = 0
        self.started = time.monotonic()

    def allow(self, n: int = 1) -> bool:
        return (
            self.underlying + n <= MAX_UNDERLYING
            and (time.monotonic() - self.started) < MAX_DURATION_SECONDS
        )

    def elapsed(self) -> int:
        return int(time.monotonic() - self.started)


def rpc_once(budget: Budget, method: str, params: list[Any], *, timeout: int) -> dict[str, Any]:
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
        with url_request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(response.status)
    except url_error.HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        status = int(exc.code)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "transport_error": type(exc).__name__, "body": None}
    body: Any = None
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError:
        body = None
    rpc_error = body.get("error") if isinstance(body, dict) else None
    return {
        "ok": status == 200 and isinstance(body, dict) and rpc_error is None,
        "transport_error": None,
        "status": status,
        "rpc_error": str(rpc_error)[:200] if rpc_error else None,
        "body": body,
    }


def classify_envelope(body: Any) -> tuple[str, object]:
    """Transaction-envelope classification, independent of Pump content."""
    if not isinstance(body, dict):
        return "UNAVAILABLE", None
    version = body.get("version", "<absent>")
    if version in ("legacy", 0) and not isinstance(version, bool):
        return "ACCEPTED", version
    return "UNSUPPORTED_TRANSACTION_VERSION", version


def pump_discriminators(body: Any) -> list[dict[str, Any]]:
    """Discriminators of Pump-program instructions, with mint-authority marker."""
    found: list[dict[str, Any]] = []
    try:
        message = body["transaction"]["message"]
        keys = list(message["accountKeys"])
        loaded = body["meta"].get("loadedAddresses") or {}
        keys += list(loaded.get("writable", [])) + list(loaded.get("readonly", []))
        keys = [k if isinstance(k, str) else k.get("pubkey") for k in keys]
        groups = body["meta"].get("innerInstructions") or []
        instructions = list(message["instructions"])
        for group in groups:
            instructions.extend(group.get("instructions", []))
    except (KeyError, TypeError, AttributeError):
        return found
    for instruction in instructions:
        if not isinstance(instruction, dict) or not isinstance(instruction.get("data"), str):
            continue
        index = instruction.get("programIdIndex")
        if type(index) is not int or not (0 <= index < len(keys)):
            continue
        if keys[index] != PUMP_PROGRAM_ID:
            continue
        try:
            data = _b58decode(instruction["data"])
        except PumpContractError:
            continue
        head = data[:8].hex()
        accounts = instruction.get("accounts")
        touches_authority = isinstance(accounts, list) and any(
            type(i) is int and 0 <= i < len(keys) and keys[i] == MINT_AUTHORITY_ID
            for i in accounts
        )
        found.append(
            {
                "discriminator_hex": head,
                "known_as": KNOWN_DISCRIMINATORS.get(head, "UNKNOWN"),
                "account_count": len(accounts) if isinstance(accounts, list) else None,
                "touches_mint_authority": touches_authority,
            }
        )
    return found


def main() -> int:
    started_utc = utc_now()
    budget = Budget()

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, cwd=ROOT
    ).stdout.strip()
    if head != PROVEN_HEAD:
        print("V2_9_7E_6_BLOCKED_HEAD_MISMATCH")
        return 4

    health = rpc_once(budget, "getHealth", [], timeout=30)
    budget.underlying -= 1  # health is not proof evidence
    budget.by_method["getHealth"] -= 1
    if not (health["ok"] and health["body"].get("result") == "ok"):
        print("V2_9_7E_6_BLOCKED_CLASSIFICATION_PROOF (health)")
        return 3

    capture = rpc_once(
        budget,
        "getSignaturesForAddress",
        [PUMP_CREATE_INDEX_ADDRESS, {"limit": CREATE_INDEX_PAGE_SIZE, "commitment": "finalized"}],
        timeout=CAPTURE_TIMEOUT,
    )
    rows = []
    if capture["ok"] and isinstance(capture["body"].get("result"), list):
        rows = [r for r in capture["body"]["result"] if isinstance(r, dict)]

    finalized_rows = [
        r
        for r in rows
        if (r.get("confirmationStatus") or "finalized") == "finalized" and r.get("err") is None
    ]
    finalized_rows.sort(key=lambda r: (r.get("slot", 0), r.get("signature", "")))

    inspected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    envelope_counts: Counter[str] = Counter()
    discriminator_counts: Counter[str] = Counter()

    for ordinal, row in enumerate(finalized_rows, start=1):
        if not budget.allow(1) or len(inspected) >= CREATE_INDEX_DECODE_CEILING:
            break
        transaction = rpc_once(
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
            timeout=TRANSACTION_TIMEOUT,
        )
        body = transaction["body"].get("result") if transaction["ok"] else None
        envelope, version = classify_envelope(body)
        envelope_counts[envelope] += 1
        discriminators = pump_discriminators(body) if envelope == "ACCEPTED" else []
        for entry in discriminators:
            discriminator_counts[f"{entry['known_as']}:{entry['discriminator_hex']}"] += 1
        reference = SignatureReference(
            row["signature"],
            int(row["slot"]),
            row.get("confirmationStatus") or "finalized",
            row.get("err"),
        )
        try:
            decode_finalized_create(body, reference=reference, cutoff_slot=int(row["slot"]))
        except PumpContractError as exc:
            outcome = exc.code
        except Exception as exc:  # noqa: BLE001
            outcome = type(exc).__name__
        else:
            outcome = "CREATE_CONFIRMED"
        counts[outcome] += 1
        inspected.append(
            {
                "ordinal": ordinal,
                "signature_prefix": row["signature"][:8],
                "slot": row["slot"],
                "body_returned": body is not None,
                "envelope": envelope,
                "version": version,
                "pump_instructions": discriminators,
                "decode_outcome": outcome,
            }
        )

    create_v2_observed = any(
        entry["known_as"] == "create_v2"
        for item in inspected
        for entry in item["pump_instructions"]
    )
    unknown_layout_observed = any(
        entry["known_as"] == "UNKNOWN" and entry["touches_mint_authority"]
        for item in inspected
        for entry in item["pump_instructions"]
    )

    payload = {
        "lane": "V2-9.7E.6 Phase 3 classification capture",
        "proven_head": PROVEN_HEAD,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "rpc_url": RPC_URL,
        "index_address": PUMP_CREATE_INDEX_ADDRESS,
        "health_check": {"ok": True, "is_proof_evidence": False},
        "capture": {
            "attempts": 1,
            "ok": bool(capture["ok"]),
            "status": capture.get("status"),
            "transport_error": capture.get("transport_error"),
            "rows_returned": len(rows),
            "finalized_rows": len(finalized_rows),
        },
        "counts": {
            "transactions_inspected": len(inspected),
            "bodies_returned": sum(1 for i in inspected if i["body_returned"]),
            "bodies_unavailable": sum(1 for i in inspected if not i["body_returned"]),
            "envelope_classification": dict(envelope_counts),
            "pump_discriminators": dict(discriminator_counts),
            "decode_outcomes": dict(counts),
        },
        "gate_signals": {
            "create_v2_observed": create_v2_observed,
            "unknown_create_layout_observed": unknown_layout_observed,
            "legacy_create_observed": counts.get("CREATE_CONFIRMED", 0) > 0,
            "envelope_rejected_count": envelope_counts.get(
                "UNSUPPORTED_TRANSACTION_VERSION", 0
            ),
        },
        "per_transaction": inspected,
        "accounting": {
            "underlying_total": budget.underlying,
            "by_method": {k: v for k, v in budget.by_method.items() if v > 0},
            "ceiling": MAX_UNDERLYING,
            "retries": budget.retries,
            "endpoint_rotations": budget.endpoint_rotations,
            "duration_seconds": budget.elapsed(),
        },
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
    print(json.dumps(payload["gate_signals"], indent=2))
    print(json.dumps(payload["accounting"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
