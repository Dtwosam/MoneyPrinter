# Printer V1 V2-9.8B Post-Checkpoint-8 Authoritative WINDOW_15M Operational Re-Readiness Audit

Date: 2026-08-08

Linear: `DTW-70`

Lane type: audit/readiness only.

Starting reconciliation HEAD:
`6cbf22945d5429c993d1c9acf50f1d3cb70cf585`

## Interim verdict

`V2_9_8B_POST_C8_AUTHORITATIVE_WINDOW_15M_OPERATIONAL_REREADINESS_BLOCKED_FRESH_LOCAL_ATTESTATION_REQUIRED`

Remote/static readiness inspection is PASS for the current code contract. Full authoritative operational readiness cannot truthfully PASS until the current Mac repository/evidence/SQLite state is freshly remeasured read-only.

No authorization, wrapper application, provider/source request, Scheduler/runtime execution, authoritative DB write, memory generation, longer-window activation, retrieval, decision, position, trade, audit, or PnL action occurred.

## Static findings — PASS

### Canonical migration ownership

`src/printer_v1/db/migrate.py` derives migration names/counts from the ordered `migrations/*.sql` catalogue and fails closed on malformed, duplicate, reordered, missing, or extra migrations. It does not hard-code an authoritative migration count.

`migrations/052_memory_observation_eligibility_layers.sql` is present and preserves the separation between memory-observation eligibility and future action-specific eligibility.

Static repository inspection alone does not prove the current authoritative DB ledger still equals the repository catalogue.

### One-shot wrapper law

Current owner:
`src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`

Static PASS:

- explicit operator approval required;
- authorization file path/hash/schema/branch/HEAD exactness fail closed;
- authorized mode must be ordinary `run`;
- allowed invocation count must equal one;
- retry/rerun/resume/restart/successor flags must all be false;
- main window must equal `WINDOW_15M`;
- selective 1h continuation must be false;
- temporal validity checked before consumption;
- exact package-bound migration/DB ledger review checked before consumption;
- source configuration checked before consumption;
- zero-I/O concrete composition preflight checked before consumption;
- create-once application marker is the authorization-consumption boundary;
- child receives exact isolated manifest/marker bindings;
- exactly one repository-venv child command is launched;
- wrapper owns no provider, Scheduler, campaign, DB, memory, retrieval, or paper-trading behavior;
- wrapper terminal records retry/rerun/resume/restart/successor counters as zero.

Thin public launcher:
`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

It requires explicit operator approval and invokes only the repository `.venv` wrapper owner. It does not bypass into the operational command directly.

### Ordinary operational command law

Current owner:
`src/printer_v1/operator_cli/operational_memory_factory_command.py`

Static PASS:

- identifies itself as the only public V2-9.8 bounded persistent 15m Memory Factory command;
- authoritative DB target is fixed internally;
- Source Governor and Central Scheduler owners are preserved;
- `MAIN_WINDOW = WINDOW_15M` and `MAIN_WINDOW_SECONDS = 900`;
- normal campaign policy has `selective_1h_continuation=False`;
- `AUTOMATIC_RETRIES = 0`;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` are locked in normal operation;
- expected migration count is derived from the canonical repository catalogue;
- candidate-acquisition state remains deferred/experimental rather than operational authority.

### Source configuration law

Current owner:
`src/printer_v1/sources/operational_source_contracts.py`

Static PASS:

- explicit Solana RPC must be HTTPS and non-placeholder;
- missing explicit RPC resolves to the documented official public Solana fallback;
- ordinary active source contracts are free-public compatible;
- optional Helius holder backup is limited to optional free API-key use;
- wallet/private-key/signing/funding/transaction-submission/execution-endpoint/paid-dependency fields are fail-closed prohibited for active ordinary profiles;
- validation is zero-network and does not mutate the parent environment.

Provider availability itself is deliberately not tested in this audit.

## Historical authoritative baseline — context only

Latest authoritative operational attempt substantiated by retained operator evidence:

- authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`;
- branch `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement`;
- HEAD `7defc2945c42053d9c770ebc66248d27c63ff4a3`;
- execution `20260806T131312Z-829382105482`;
- first terminal cause `HolderBudgetError:PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES:campaign_identity_count=5,manifest_transport_count=9`;
- cleanup complete and lease released;
- zero active/locked Scheduler residue;
- post-attempt DB SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- size `69328896`, inode `1230526`;
- historical migration `52 / 052_memory_observation_eligibility_layers.sql`;
- historical integrity/FK `ok / 0`.

This evidence is not a fresh 2026-08-08 attestation and cannot authorize a new run.

Earlier `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` was `BLOCKED_UNCONSUMED_SUPERSEDED`; filename/package presence must never be treated as reusable authority.

## Fresh local evidence required

PASS requires one fresh read-only capture from the actual Mac repository. The capture must establish:

1. current branch/full HEAD and tracked/index/untracked state;
2. current canonical migration catalogue and exact applied DB ledger;
3. DB SHA-256, size/inode/mtime, WAL/SHM/journal state, integrity and FK;
4. current active/non-terminal operational residue;
5. current authorization-package and external application-marker inventory;
6. current source configuration shape without exposing secret values;
7. zero-I/O concrete-composition readiness.

### Approved read-only capture command

Run from the Mac repository exactly as follows. It does not create or consume authorization, call providers, start Scheduler/runtime, or write SQLite.

```bash
cd "$HOME/Developer/MoneyPrinter"

PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python - <<'PY'
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from printer_v1.db.migrate import canonical_migration_names, validate_migration_ledger
from printer_v1.sources.operational_source_contracts import (
    HELIUS_API_KEY_ENVIRONMENT_NAME,
    resolve_solana_rpc_configuration,
)

ROOT = Path.cwd().resolve()
DB = (ROOT / "data/printer_v1.sqlite3").resolve()
AUTH_ROOT = ROOT / "operator-runs/v2-9-8b-window-15m-final-authorization"
APP_ROOT = Path.home() / "PrinterOperations/v2-9-8/window-15m-one-shot-applications"


def run(*args: str) -> str:
    return subprocess.run(
        args, cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.rstrip("\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def grouped_state(conn: sqlite3.Connection, table: str):
    if not table_exists(conn, table):
        return {"exists": False}
    columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
    state_col = next(
        (c for c in (
            "status", "state", "run_state", "cycle_state", "supervision_state",
            "window_state", "work_state", "lease_state"
        ) if c in columns),
        None,
    )
    total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    result = {"exists": True, "total": int(total), "state_column": state_col}
    if state_col:
        result["states"] = {
            str(k): int(v)
            for k, v in conn.execute(
                f'SELECT "{state_col}", COUNT(*) FROM "{table}" GROUP BY "{state_col}"'
            ).fetchall()
        }
    return result


out: dict[str, object] = {}
out["git"] = {
    "branch": run("git", "branch", "--show-current"),
    "head": run("git", "rev-parse", "HEAD"),
    "status_short": run("git", "status", "--short", "--untracked-files=all").splitlines(),
    "tracked_status": run("git", "status", "--short", "--untracked-files=no").splitlines(),
}

if not DB.is_file():
    raise SystemExit("AUTHORITATIVE_DB_MISSING")
st = DB.stat()
out["database_file"] = {
    "path": str(DB),
    "size": st.st_size,
    "inode": st.st_ino,
    "mtime_ns": st.st_mtime_ns,
    "sha256": sha256_file(DB),
    "sidecars": {
        suffix: (Path(str(DB) + suffix).exists())
        for suffix in ("-wal", "-shm", "-journal")
    },
}

uri = f"file:{DB.as_posix()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)
try:
    conn.execute("PRAGMA query_only=ON")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    applied = [
        row[0]
        for row in conn.execute(
            "SELECT version FROM printer_schema_migrations ORDER BY rowid"
        ).fetchall()
    ]
    out["migration"] = {
        "canonical": list(canonical_migration_names()),
        "validation": validate_migration_ledger(applied),
    }
    out["database_checks"] = {
        "integrity": integrity,
        "foreign_key_violation_count": len(fk),
    }
    tables = (
        "printer_memory_factory_campaigns",
        "printer_memory_factory_campaign_runs",
        "printer_memory_factory_campaign_cycles",
        "printer_memory_factory_campaign_supervision",
        "printer_memory_factory_runs",
        "printer_memory_factory_campaign_windows",
        "printer_discovery_work",
        "printer_memory_factory_campaign_scheduler_work",
        "printer_scheduler_jobs",
    )
    out["operational_tables"] = {t: grouped_state(conn, t) for t in tables}
finally:
    conn.close()


def inventory(root: Path):
    if not root.exists():
        return {"exists": False, "entries": []}
    entries = []
    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if not p.is_dir():
            continue
        entries.append({
            "id": p.name,
            "final_authorization": (p / "final_authorization.json").is_file(),
            "application_marker": (p / "application-marker.json").is_file(),
            "wrapper_terminal": (p / "wrapper-terminal.json").is_file(),
        })
    return {"exists": True, "entries": entries}

out["authorization_packages"] = inventory(AUTH_ROOT)
out["external_applications"] = inventory(APP_ROOT)
staging = APP_ROOT / ".staging"
out["external_staging"] = {
    "exists": staging.exists(),
    "entries": sorted(p.name for p in staging.iterdir()) if staging.is_dir() else [],
}

rpc = resolve_solana_rpc_configuration(os.environ)
out["source_configuration"] = {
    "rpc_origin": rpc.origin,
    "rpc_identity_redacted": rpc.redacted_identity,
    "helius_key_present": bool(os.environ.get(HELIUS_API_KEY_ENVIRONMENT_NAME, "").strip()),
}

try:
    from printer_v1.operator_cli.window_15m_concrete_composition import (
        run_window_15m_concrete_composition_preflight,
    )
    run_window_15m_concrete_composition_preflight(
        repository_root=str(ROOT), timeout_seconds=5.0, environment=os.environ
    )
    out["zero_io_concrete_composition"] = {"pass": True}
except Exception as exc:
    out["zero_io_concrete_composition"] = {
        "pass": False,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }

print(json.dumps(out, indent=2, sort_keys=True))
PY
```

The command intentionally prints only a redacted RPC identity and a Helius presence boolean; it must not print secret values.

## Money-usefulness contribution

The audit confirms the post-C8 code boundary is structurally ready for a future operational readiness decision while preventing stale Git/DB/authorization evidence from being mistaken for current authority. That reduces the chance of burning another one-use authorization before useful paper-only collection begins.

## What this audit improves

- confirms the current one-shot and ordinary 15m code contracts remain fail-closed;
- confirms no redesign is currently justified by static inspection;
- isolates the exact missing evidence to current local state rather than another software patch;
- prevents default-branch or historical-DB assumptions from becoming execution authority.

## What remains locked

Everything beyond read-only readiness remains locked, including authorization creation/consumption, providers, runtime, memory generation, longer windows, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets/keys/signing/real funds/live execution, paid APIs, scoring/ranking/confidence/weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test needed before completion

Exactly the fresh local read-only capture above. Do not run a broad suite or any provider-backed test. If the capture passes all fail-closed checks, DTW-70 may close PASS and only then may a separate next-step/authorization decision be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- GitHub cannot attest the current local DB bytes or external application-marker namespace.
- Historical `7380f9...` DB evidence must not be silently promoted to current truth.
- A clean tracked tree can coexist with expected untracked operator evidence; classification, not blanket deletion, is required.
- An old authorization directory can be consumed, superseded, or expired; existence alone never implies reusability.
- Zero-I/O composition PASS cannot prove live provider availability or eligible supply.
- Do not convert this audit blocker into another code repair unless the fresh local capture identifies a real current defect.

## Stop condition

Stop at `BLOCKED_FRESH_LOCAL_ATTESTATION_REQUIRED` until the approved read-only capture is supplied. No authorization request or runtime step is permitted before this audit closes PASS.