# Printer V1 V2-9.8B.2 — Holder Budget and Supervision Lock Repair Closeout

## Verdict

`V2_9_8B_2_HOLDER_BUDGET_SUPERVISION_REPAIR_PASS`

V2-9.8B.2 is closed PASS. This does **not** mark V2-9.8B complete and does
**not** authorize another production campaign, restart, successor, retry, tag,
or push.

## Scope and identities

- Baseline repository HEAD:
  `ccf5bb924f80819223bd596d8f8ccb0f6aeecad1`
- Failed execution:
  `20260726T141321Z-e762ecf7b374`
- Repair checkpoint:
  `fb276e4942e92db11b8429ede1fc1cc8547ff9ac`
  (`Repair V2-9.8B holder budget and supervision contention`)
- Closeout commit: this document

Failed execution confirmed result:

```text
terminal cause: OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError
lifecycle started: false
source calls: 0 (report surface; durable stage rows existed)
Scheduler runtime calls: 0
active work: 0
supervision: TERMINAL / FAILED
cleanup and lease release: complete
restart/successor: false/false
```

Heartbeat thread also observed:

```text
sqlite3.OperationalError: database is locked
```

## Root cause

### 1. HolderBudgetError path (budget accounting defect)

Exact raise path:

```text
run_operational_campaign
  -> AuthoritativeLiveOperationalCampaignOwner.run_operational
    -> build_graduated_supply (discovery + front door)
    -> build_ledger(
         pump_operations=...,
         additional_governed_operations=
           enrichment.requested + supply_source_operations
       )
    -> HolderBudgetError("CAMPAIGN_BASE_WORK_EXCEEDS_RESERVED_BUDGET")
```

`supply_source_operations` was sourced from:

```text
discovery_report.source_operation_ledger.source_requests
+ front_door_report.source_operation_ledger.liquidity_requests
```

Front door was already stage-local (E.46B.2). Discovery still used whole-table:

```text
SELECT COUNT(*) FROM printer_source_requests
```

On the operational persistent DB this returned the entire historical ledger
(~1121 rows), not the current invocation's migration/verify requests.

With only three new durable requests in the failed window:

| time (UTC) | source | request_kind |
|---|---|---|
| 14:13:21 | pumpportal | pumpfun_migration_stream |
| ~14:15:26 | pumpswap | pumpswap_signature_pool_resolution |
| 14:15:26 | dexscreener | pair_market_snapshot |

the campaign charged ~1121 base ops into an admission ceiling of 45.

No holder operation ledger row was persisted because `build_ledger` raised before
`persist_ledger`.

Classification: `COMMITTED_CODE_DEFECT` (stage-local accounting incomplete on
persistent operational DB). Not a correct policy block, not an approved-ceiling
shortfall, and not a holder-evidence rule issue.

### 2. Heartbeat / supervision lock contention

`renew_campaign_lease` used SQLite `timeout=0.0` and, on any renewal fault
(including `database is locked`), immediately called
`cleanup_campaign_supervision` from the heartbeat path.

Effects:

- Heartbeat competed with the main SQLite writer under zero busy timeout.
- Heartbeat could attempt terminal cleanup independently of the main coordinator.
- Original terminal cause could be replaced by `LEASE_RENEWAL_UNCONFIRMED` if
  heartbeat cleaned up first.
- In the failed run, heartbeat renewal never advanced `heartbeat_at` past create
  time; cleanup ultimately completed on the main failure path with
  `OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError`.

Classification: `COMMITTED_CODE_DEFECT` (supervision ownership and lock handling).

## Exact budget contract

Authoritative admission/holder ledger constants (unchanged ceilings):

| Quantity | Value | Role |
|---|---:|---|
| Campaign / admission source ceiling (`source_calls` / `OPERATION_CEILING`) | 45 | Hard admission operation ceiling |
| Admission ceiling configured by public command | 45 | Must equal authoritative ceiling |
| Holder worst-case transport ops / candidate | 5 | Candidate-cap divisor |
| Combined zero-transport validation charge | 9 | Fixed charged reservation |
| Dex snapshot reservation | 2 | Reserved for snapshot path |
| Snapshot completion reservation | 4 | Reserved for completion path |
| Readiness snapshot reservation | 6 | Readiness-only contract |
| Discovery request ceiling (outer 15m policy) | 2 | Outer campaign ceiling |
| Governed 15m request ceiling (outer) | 65 | Outer 15m policy ceiling |
| Governed requests per token (outer) | 21 | Outer per-token ceiling |
| Scheduler row ceiling | 51 | Outer scheduler ceiling |
| Total duration | 1200s | Campaign wall clock |
| Main window | WINDOW_15M / 900s | Main memory window |

Static feasibility:

```text
fixed_charge_before_base_work = 9 + 2 + 4 = 15
available_for_base_work       = 45 - 15 = 30
candidate_cap                 = available_before_reservation // 5
```

Runtime base work must be **invocation-local only**:

```text
base_operations =
  pump_underlying_rpc_operations
  + enrichment.requested
  + locator.source_requests            # 0 or 1
  + discovery.source_requests          # stage-local migration/verify ids
  + front_door.liquidity_requests      # stage-local pair snapshot ids

charged_operations = base_operations + 9
charged_plus_reserved = charged_operations + 2 + 4
require charged_plus_reserved <= 45
```

Whole-table historical `printer_source_requests` counts are forbidden for campaign
charging.

Approved ceilings and holder-evidence rules were **not** raised or weakened.

## Repair implemented

### Budget ledger

1. Discovery `_ledger_counts` now charges only the exact request identities created
   by the current discovery invocation.
2. Locator reports `request_id` / `source_requests`.
3. Graduated supply diagnostics expose stage-local sums:
   `locator + discovery + front_door`.
4. `run_operational` prefers that stage-local sum when building the holder ledger.
5. `build_ledger` / `HolderBudgetError` report exact expected, reserved, charged,
   available, and base-work values.
6. `build_operational_budget_preflight` is the static authoritative budget gate used
   by activation preflight before campaign rows are created.
7. Impossible static admission mismatch blocks preflight with zero source calls.

### Supervision lock

1. `renew_campaign_lease` never performs terminal cleanup.
2. Renewal failures return a signal payload:
   `signal_main_coordinator=true`,
   `terminal_cleanup_performed=false`,
   `suggested_terminal_cause=LEASE_RENEWAL_UNCONFIRMED`.
3. Bounded SQLite busy handling:
   `SQLITE_BUSY_TIMEOUT_SECONDS=2.0`,
   `SQLITE_BUSY_MAX_ATTEMPTS=5`,
   `SQLITE_BUSY_RETRY_SECONDS=0.05`,
   shared `_begin_immediate` helper.
4. Heartbeat thread records failure to the main coordinator and never calls
   cleanup.
5. Main terminal coordinator remains the only cleanup / lease-release / report
   owner and preserves the original first terminal cause.

## Focused test results

Command:

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_2_holder_budget_supervision_repair.py \
  tests/test_v2_9_7e_22_holder_reliability_budget_repair.py \
  tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py \
  tests/test_v2_9_7e_46b_2_source_accounting.py \
  tests/test_v2_9_8b_1_first_operation_blocker_repair.py \
  tests/test_v2_9_7e_26_snapshot_readiness_contract_repair.py \
  tests/test_v2_9_7e_24_holder_source_reporting_repair.py \
  -q
```

Result:

```text
51 passed (+ subtests)
```

Covered proofs:

1. Correct budget arithmetic and reservation.
2. Impossible budget configuration blocks before campaign creation.
3. Valid configuration passes budget preflight with zero source calls.
4. Heartbeat/renew lock contention is reported to the main coordinator.
5. Heartbeat thread does not run terminal cleanup.
6. Final cleanup releases the lease and leaves zero active work.
7. Retrieval and financial create surfaces remain untouched by repair modules.
8. Discovery stage-local accounting ignores historical whole-table noise.
9. Existing E.22, E.46B.2, 6B.5, and 8B.1 directly affected tests remain green.

No broad regression suite was run. No production campaign was run.

## Post-repair operator modes (no `-Mode run`)

```text
preflight-only -> V2_9_8_OPERATIONAL_PREFLIGHT_READY
                 holder_budget_preflight.status=READY
                 source_calls=0
                 scheduler_runtime_calls=0
status         -> latest supervision TERMINAL/FAILED
                 first_terminal_cause=
                   OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError
                 cleanup_completed_at set
                 lease_released_at set
                 source_calls=0
report-only    -> artifact matches, zero new source/scheduler/DB writes
                 downstream unlocks all false
```

## Money-usefulness contribution

This repair restores truthful admission accounting on the persistent operational
database so bounded 15m memory-growth attempts can spend only real invocation
work against the approved 45-op ceiling. It also prevents heartbeat lock races
from destroying first-fault terminal truth. Both are required before any later
operator-authorized production retry can honestly grow clean 15m memory.

It does not create clean memory, does not activate retrieval, and does not make
paper profit.

## What remains locked

- V2-9.8B production campaign retry (not authorized by this closeout)
- retrieval activation
- paper decisions
- BUY / SELL / HOLD
- paper positions / trade events / paper audits / PnL
- live execution / wallets / private keys / real funds
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- dirty-memory decision support
- raising approved ceilings
- weakening holder-evidence rules
- restart / successor creation from this failure

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Residual awareness — live market supply**  
   Stage-local accounting may now correctly allow a campaign to reach holder /
   readiness work, then honestly block on insufficient graduated `$3K+` supply.
   That is market truth, not a repair defect.

2. **Residual awareness — heartbeat still advisory**  
   Heartbeat no longer terminalizes. If the main worker ignores the failure
   signal for a long time, lease expiry can become real. The public command now
   polls heartbeat failure in cancellation probe and success-path observation;
   deeper lifecycle paths must continue to honor cancellation probes.

3. **Residual awareness — outer vs admission ceilings**  
   Outer 15m ceilings (`governed_requests=65`, per-token `21`) remain larger than
   the admission operation ceiling (`45`). They are policy envelopes, not a second
   admission ledger. Future lanes must not reintroduce dual ledgers that double
   charge.

4. **Efficiency blocker removed**  
   Whole-table discovery charging on the persistent DB was an absolute blocker to
   any honest production 15m campaign after historical source rows accumulated.

5. **No design-decision ceiling raise required**  
   The conflict was implementation accounting, not approved policy insufficiency.
   No ceiling was raised.

## Files changed

### Repair commit (`fb276e4`)

- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py`
- `tests/test_v2_9_7e_46b_2_source_accounting.py`
- `tests/test_v2_9_8b_2_holder_budget_supervision_repair.py`

### Closeout commit

- `docs/printer-v1-v2-9-8b-holder-budget-supervision-repair-closeout.md`

## What was not touched

- Approved ceilings and holder-evidence policy values
- Source Governor / Central Scheduler ownership model
- Production campaign runner authorization
- Retrieval / paper / financial owners
- Broad regression suites
- Tags / pushes / production `-Mode run`

## Pass/fail status

`PASS` — `V2_9_8B_2_HOLDER_BUDGET_SUPERVISION_REPAIR_PASS`

## Next recommended action

Operator-only decision. Do **not** auto-start another production campaign from
this closeout. After operator review, a separately authorized V2-9.8B production
retry may be considered only if:

1. preflight-only remains READY,
2. status shows no active work,
3. this repair commit is the intended launch HEAD,
4. the operator explicitly approves `-Mode run`.
