# V2-9.8B.22 — Governed Discovery-Only Qualification Command Surface Audit

**Lane:** V2-9.8B.22 — Governed Discovery-Only Qualification Command Surface  
**Baseline HEAD:** `a13231a` — `Close V2-9.8B discovery and selection consolidation`  
**Audit type:** command-surface / operational ownership (read-only)  
**Live discovery / production campaign executed in this audit:** **No**

---

## 1. Purpose

Determine whether Printer already exposes a public, operator-approved **discovery-only**
qualification command that can exercise the V2-9.8B.21 Eligible Token Supply service
without opening a production Memory Factory campaign, and identify the exact gaps
this lane must close.

---

## 2. Baseline gates (authoritative corpus)

| Gate | Result |
|---|---|
| Exact HEAD `a13231a` | PASS |
| Clean worktree | PASS |
| SQLite integrity | PASS (`ok`) |
| Foreign key violations | PASS (`0`) |
| SQLite sidecars (`-wal`/`-shm`/`-journal`) | PASS (none) |
| Preflight active operational counts | PASS (all zero) |
| Migrations | PASS (46; latest `046_eligible_token_supply.sql`) |
| Preflight status | PASS `V2_9_8_OPERATIONAL_PREFLIGHT_READY` |

Historical residual rows exist (terminal campaigns, `QUEUED` tracking-queue
history, retrieval/paper-decision baseline rows). Preflight active surfaces are
zero; no campaign, supervision, discovery work, factory steps, proof, or
Scheduler lock is active.

---

## 3. Current public command surface

### 3.1 PowerShell wrapper

`scripts/Start-PrinterV1-MemoryFactory.ps1`

```text
ValidateSet: preflight-only | run | status | cooperative-stop | recover-orphan | report-only
```

Parameters:

* `-Mode` (default `preflight-only`)
* `-OperatorApproved` switch → forwarded as `--operator-approved`

The wrapper is a thin front door: repository interpreter `.venv/bin/python`,
module `printer_v1.operator_cli.operational_memory_factory_command`, single mode
argument. There is **no** `discovery-only` choice.

### 3.2 Python public command

`src/printer_v1/operator_cli/operational_memory_factory_command.py`

| Mode | Operator approval | Mutates production campaign | Source calls | Scheduler runtime |
|---|---|---|---|---|
| `preflight-only` | No | No | 0 | 0 |
| `run` | Required | Yes (full campaign) | Yes (governed) | Yes (lifecycle) |
| `status` | No | No | 0 | 0 |
| `cooperative-stop` | Required | Supervision only | 0 | 0 |
| `recover-orphan` | Required | Recovery only | 0 | 0 |
| `report-only` | No | No | 0 | 0 |

`run` always:

1. runs activation preflight;
2. creates execution identity + artifact tree;
3. runs backup/restore preflight;
4. creates campaign / run / cycle rows;
5. acquires production supervision lease + heartbeat;
6. invokes `AuthoritativeLiveOperationalCampaignOwner.run_operational`;
7. composes graduated supply (B.21 loop) **inside** production admission;
8. may proceed to tracking handoff, Scheduler work, factory lifecycle, 15m
   windows;
9. terminalizes campaign supervision and writes campaign terminal report.

There is **no** public path that stops after Eligible Token Supply qualification.

---

## 4. Preflight and authorization contracts

`build_activation_preflight` already enforces the gates discovery-only must share:

* authoritative DB path only (`data/printer_v1.sqlite3`);
* SQLite sidecar quiescence;
* clean Git provenance (tracked tree clean; no arbitrary untracked files);
* source-contract readiness (secrets / free-source contract);
* runtime dependency readiness;
* holder/admission budget readiness (ceiling 45, discovery headroom 30);
* migration ledger exact match (46 / `046_eligible_token_supply.sql`);
* integrity `ok`;
* zero FK violations;
* zero active campaign / run / supervision / discovery work / factory steps /
  proof / scheduler locks;
* locked-capability baseline exactness (historical retrieval/paper rows only).

Operator approval is enforced only on `run`, `cooperative-stop`, and
`recover-orphan`. A future discovery-only mode must require the same explicit
approval as production run.

---

## 5. Eligible Token Supply service ownership (V2-9.8B.21)

Canonical service: `src/printer_v1/discovery/eligible_token_supply.py`

| Capability | Status |
|---|---|
| Multi-round evaluation batches (`front_door_max_candidates=6`) | Implemented |
| Durable eligible reserve (migration 046) | Implemented |
| Exhaustion certificates + shortage classification | Implemented |
| Stop at required capacity 2 | Implemented |
| Deterministic non-ranked selection order | Implemented |
| Source Governor path for market checks | Implemented (front door) |
| Zero Scheduler / campaign / tracking creation | Implemented at service layer |

Composition entry: `build_graduated_supply` →
`run_persistent_eligible_token_supply`.

Production currently reaches this service only through `run` →
`run_operational` → graduated supply kwargs. That path is **not** discovery-only:
it continues into holder funnel, selection, handoff readiness, and lifecycle.

---

## 6. Mutation surfaces today

### 6.1 Production `run` may write (among others)

* campaign ownership / supervision / heartbeat / reports;
* factory runs / steps / slots / windows;
* tracking queue activation;
* Scheduler jobs;
* source request/response ledger;
* discovery inventory and market-floor evidence;
* eligible reserve + exhaustion certificates (via B.21);
* memory lifecycle evidence when lifecycle starts.

### 6.2 Discovery-owned evidence already used by B.21

Allowable discovery evidence tables (service + governors + migration path):

| Table / surface | Role |
|---|---|
| `printer_source_requests` / `printer_source_responses` / `printer_source_failures` | Governed ledger |
| `printer_source_health` / `printer_source_rate_limits` | Governor accounting |
| `printer_external_source_operations` | Operation accounting |
| `printer_pumpswap_graduated_candidate_registry` | Graduated inventory |
| `printer_discovery_*` persistence tables | Discovery batch/work evidence |
| `printer_graduated_market_floor_state` | Floor / cooldown evidence |
| `printer_eligible_token_reserve` | Durable eligible reserve (046) |
| `printer_discovery_exhaustion_certificates` | Honest exhaustion (046) |
| `printer_pumpfun_origin_cursor` / finalized origin registry | Migration/origin support |

### 6.3 Protected production surfaces (must stay zero-delta in discovery-only)

* all `printer_memory_factory_campaign*` ownership/supervision/slot/report tables
* `printer_memory_factory_runs` / `run_steps`
* `printer_scheduler_jobs`
* `printer_tracking_queue`
* `printer_memory_windows` / episodes / fingerprints
* retrieval and all paper financial tables
* token lifecycle / snapshot / memory factory window progression

---

## 7. Status / report-only inspection

| Mode | Current behavior |
|---|---|
| `status` | Inspects **latest campaign supervision** only |
| `report-only` | Replays **latest terminal campaign report** only |

Neither mode understands a discovery-only qualification identity or report path.
After a future discovery-only qualification, operators would have no public
zero-source inspection surface unless status/report-only are extended.

---

## 8. Gaps (normative for design)

| ID | Gap | Severity |
|---|---|---|
| G1 | No public `discovery-only` mode in PowerShell or Python CLI | Blocker |
| G2 | Only production `run` exercises live Eligible Token Supply | Blocker |
| G3 | Production `run` always creates campaign/supervision/lifecycle risk | Blocker |
| G4 | No qualification execution identity distinct from campaign IDs | High |
| G5 | No durable qualification terminal report contract | High |
| G6 | Status/report-only cannot inspect qualification residue-free | High |
| G7 | No public mutation allowlist / protected zero-delta proof for discovery-only | High |
| G8 | Terminal statuses do not distinguish capacity-ready vs honest exhaustion vs provider/budget/duration failures for a discovery-only mode | Medium |
| G9 | No disposable public-command proof that PowerShell accepts `discovery-only` on macOS | Medium |

---

## 9. What is already safe to reuse

* Activation preflight (`build_activation_preflight`)
* Git provenance capture
* Source-contract / dependency / holder-budget preflights
* `run_persistent_eligible_token_supply` completeness loop
* Migration 046 reserve + certificate schema
* Shortage classification (provider/budget/duration ≠ market shortage)
* Operational graduated-supply kwargs ownership of batch size 6 / capacity 2
* Live free transports already used by production (`build_pumpportal_migration_transport`, DexScreener pair transport, Solana RPC verify) — **must remain Source-Governed**
* Action-local blocked-command source accounting pattern

---

## 10. What must not be reused or improvised

* Production `run` as a substitute for discovery-only
* Direct calls that bypass the public PowerShell/Python command surface
* Campaign supervision lease / heartbeat for qualification
* Central Scheduler runtime admission
* Tracking-queue activation or token slots
* Automatic retry / restart / successor qualification
* Lowering the `$3,000` floor or token capacity
* Unlocking retrieval, decisions, positions, trades, audits, PnL

---

## 11. Audit conclusion

```text
V2_9_8B_22_DISCOVERY_ONLY_COMMAND_SURFACE_AUDIT_PASS
```

Printer has a complete Eligible Token Supply service and a production Memory
Factory command, but **no governed discovery-only public qualification command**.
Lane V2-9.8B.22 must add one explicit operator-approved mode that reuses preflight
+ B.21 supply, writes only discovery-owned evidence, emits a durable qualification
report, and leaves zero production campaign/Scheduler/tracking residue.

**Design next:** `docs/printer-v1-v2-9-8b-discovery-only-command-design.md`
