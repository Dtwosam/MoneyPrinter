# Printer V1 V2-9.8B.4A — Blocked-Supply and Source-Activity Reporting Design

## Verdict

`V2_9_8B_4A_REPORTING_DESIGN_PASS`

This design authorizes a **reporting-only** repair. It does **not** change source
ceilings, token capacity, eligibility rules, or durable schemas beyond the
minimum report-JSON surface already owned by terminal report persistence. It
does **not** unlock retrieval, paper decisions, BUY/SELL/HOLD, positions,
trades, audits, PnL, live execution, or another production run.

## Problem statement

Execution `20260726T172119Z-941d6d86aa56` closed correctly as:

```text
BLOCKED_INSUFFICIENT_GRADUATED_POOL
```

Durable campaign-attributable evidence proves:

```text
campaign_source_calls = 4
campaign_scheduler_calls = 0
candidates_observed = 2
eligible_candidates = 1
required_token_capacity = 2
```

The terminal report write surface incorrectly records:

```text
source_calls: 0
scheduler_calls: 0
```

and omits per-candidate pass/fail detail. Report-only replay correctly reports
zero **new** work, but that zero is easily mistaken for the original campaign
total.

Classification carried from the outcome audit:

```text
MIXED_BLOCKER
primary: HONEST_MARKET_SUPPLY_BLOCK
secondary: REPORTING_VISIBILITY_DEFECT
```

## Design goal

One authoritative terminal-reporting path that:

1. Exposes original campaign source/scheduler totals from durable
   campaign-attributable evidence.
2. Keeps report-only / replay **new** work totals separate and zero when no new
   work is performed.
3. Makes blocked-supply capacity and per-candidate eligibility explicit.
4. Remains deterministic, replayable, and idempotent.
5. Does not create a second source-accounting owner.

## Authoritative owners (no second accounting owner)

| Concern | Existing owner | Use in this repair |
|---|---|---|
| Governed request execution | Source Governor | unchanged; no bypass |
| Campaign operation totals | `printer_holder_campaign_operation_ledgers` via holder budget ledger | **read** for `campaign_source_calls` |
| Stage-local source request identities | discovery / front-door stage ledgers already feeding the holder ledger | unchanged accounting; reporting only |
| Candidate market eligibility | graduated liquidity front door (`$3,000` floor) | **read** candidate outcomes at report assembly |
| Terminal report row + artifact | `write_campaign_terminal_report` / `persist_terminal_report` | enrich payload; keep one row / one artifact |
| Report-only replay | `replay_campaign_terminal_report` | surface stored campaign totals + `replay_new_* = 0` |
| Public operational modes | `operational_memory_factory_command` | wire assembly on terminal write and report-only |

Do **not** invent a parallel source counter, whole-table request re-count, or
second ledger writer.

## Exact source-total semantics

### Campaign totals (original work)

```text
campaign_source_calls
  = durable holder ledger.governed_requests for the campaign run/cycle
  = invocation-local governed source operations charged into the ledger

campaign_scheduler_calls
  = campaign-attributable Scheduler work created by the campaign
  = 0 for pre-lifecycle blocked-supply closes that create no scheduler work
```

Rules:

- Campaign totals come only from durable campaign-attributable evidence.
- Prefer the holder operation ledger already persisted before terminal close.
- Never recompute campaign totals from whole-table `COUNT(*)` over historical
  `printer_source_requests` on a persistent operational DB.
- Never treat report-write or report-only mode as campaign source activity.

### Replay / report-only totals (new work during the reporting action)

```text
replay_new_source_calls = 0 when report-only/replay performs no Source Governor work
replay_new_scheduler_calls = 0 when report-only/replay performs no Scheduler work
```

Rules:

- Report-only must remain zero-source and zero-scheduler.
- Replay must not create a second report row or second artifact.
- Replay must not mutate campaign evidence.

### Compatibility aliases

Historical surfaces used overloaded `source_calls`:

| Surface | Required meaning after repair |
|---|---|
| Terminal report payload `campaign_source_calls` | Original campaign total |
| Terminal report write return `campaign_source_calls` | Same as payload |
| Terminal report write return `source_calls` | **Same as campaign total for original write**, so terminal-summary is no longer silently zero when the campaign did real governed work |
| Report-only `replay_new_source_calls` / `new_source_calls` | New work during replay only (usually 0) |
| Status / cooperative-stop / preflight `source_calls: 0` | Still means “this read/status action performed no source work” and is not a campaign total |

## Blocked-supply reporting contract

The terminal report payload gains one canonical section assembled at original
report write time:

```text
blocked_supply:
  required_token_capacity
  candidates_observed
  candidates_validated
  eligible_candidates
  blocked_supply_reason
  candidates: [ candidate_report, ... ]
```

and campaign activity:

```text
campaign_activity:
  campaign_source_calls
  campaign_scheduler_calls
```

### Top-level required fields (authoritative path)

| Field | Meaning for the audited class of close |
|---|---|
| `campaign_source_calls` | Durable governed source ops for the campaign |
| `campaign_scheduler_calls` | Campaign Scheduler work created (0 when none) |
| `replay_new_source_calls` | Present on replay surfaces only; 0 when no new work |
| `replay_new_scheduler_calls` | Present on replay surfaces only; 0 when no new work |
| `candidates_observed` | Distinct candidates evaluated for the supply decision |
| `candidates_validated` | Candidates that reached market/graduation validation evidence |
| `eligible_candidates` | Candidates that passed the exact market/graduation eligibility gate used for the two-token requirement |
| `required_token_capacity` | Configured token capacity (remains 2) |
| `blocked_supply_reason` | Terminal/blocked reason, e.g. `BLOCKED_INSUFFICIENT_GRADUATED_POOL` |

For a non-blocked successful terminal, blocked-supply fields may be omitted or
recorded as non-blocking zeros/empty with no false insufficient-pool reason.
This repair’s focused proof targets the blocked-supply path.

### Per-candidate report

Each candidate report includes:

| Field | Source of truth |
|---|---|
| `mint` | Front-door / graduated candidate identity |
| `source_path` | Honest stage path labels already known to discovery/front-door (e.g. migration → PumpSwap → DexScreener pair snapshot, or registry re-enrichment) |
| `stage_reached` | Highest stage actually reached |
| `migration_evidence` | Migration signature / provenance when present |
| `pool_confirmation` | PumpSwap pool + confirmed/failed state |
| `liquidity` | Exact-pool `liquidity_usd` when proven or below-floor measured |
| `market_cap` | Exact-pool market cap when present on the same governed snapshot payload; otherwise `null` (no extra source call) |
| `eligibility_result` | `eligible` or `rejected` |
| `rejection_or_exclusion_reason` | Exact reason such as `LIQUIDITY_BELOW_SELECTION_FLOOR`, or `null` when eligible |

No scoring, ranking, confidence percentage, or weighted fitness is introduced.
Liquidity magnitude above the floor is never used as a rank.

## Assembly path (one write, one payload)

### Original campaign terminal write

In the public operational campaign terminal path:

1. Lifecycle / supply already produce front-door candidate outcomes and persist
   the holder ledger before terminal close for insufficient-pool blocks.
2. Terminal assembly reads:

   - holder ledger for the campaign run/cycle → `campaign_source_calls`
   - campaign configuration / fixed capacity → `required_token_capacity`
   - lifecycle/front-door candidate outcomes available at write time → candidate reports
   - terminal cause → `blocked_supply_reason` when blocked for insufficient supply

3. `build_campaign_terminal_report(...)` accepts the assembled
   `campaign_activity` and `blocked_supply` maps and embeds them in the
   canonical terminal report JSON.
4. `write_campaign_terminal_report(...)` persists the same payload once and
   returns campaign totals from that payload.
5. `terminal-summary.json` inherits the honest campaign totals through the
   existing report return surface.

### Lifecycle data attachment for blocked insufficient pool

When returning `BLOCKED_INSUFFICIENT_GRADUATED_POOL`, lifecycle must retain
enough in-memory candidate outcome evidence for the terminal writer:

- front-door candidate list (or equivalent serializable candidate reports)
- supply diagnostics already present
- no new network I/O during reporting

This is report packaging only. It does not change admission, ceilings, or
activation.

### Report-only / replay

`replay_campaign_terminal_report` remains read-only:

- returns stored report payload unchanged
- `replay_new_source_calls = 0`
- `replay_new_scheduler_calls = 0`
- `duplicate_reports_created = 0`
- no database writes
- no second artifact

Public `report-only` mode surfaces:

```text
mode: REPORT_ONLY
campaign_source_calls: <from stored report>
campaign_scheduler_calls: <from stored report>
replay_new_source_calls: 0
replay_new_scheduler_calls: 0
blocked_supply: <from stored report when present>
```

## Non-goals / hard stops

Stop and report a blocker if implementation appears to require:

- changing admission source ceiling (45)
- changing token capacity (2)
- changing the `$3,000` exact-pool floor or eligibility rules
- durable schema migration not strictly required for report JSON
- second source-accounting owner or whole-table request recount
- rewriting historical terminal report rows for past executions
- retrieval, paper decision, position, trade, audit, or PnL activation
- live source calls during proof
- production `-Mode run`

## Prior report rows

Do **not** retroactively rewrite
`20260726T172119Z-941d6d86aa56-report` unless an existing canonical rewrite
owner already supports it (none is authorized here). Prove the repair with
disposable fixtures. The audited execution remains historical evidence with a
known reporting defect.

## Implementation plan (after design PASS)

1. Extend terminal report builders/writers in
   `unified_terminal_closure.py` to carry campaign activity and blocked-supply
   candidate surfaces.
2. Attach serializable candidate outcomes on the insufficient graduated-pool
   lifecycle return path.
3. Wire `operational_memory_factory_command` terminal write and report-only
   surfaces to the new fields.
4. Keep recovery/other terminals compatible: missing blocked-supply data must
   not break writes; campaign totals default honestly from ledger when present,
   else zero.
5. Add focused disposable tests only.
6. Run preflight-only / status / report-only against the existing terminal
   campaign without `-Mode run`.

## Focused proof requirements

Disposable DB fixtures must prove:

1. Campaign with four durable source operations reports
   `campaign_source_calls: 4`.
2. Report-only replay reports `replay_new_source_calls: 0`.
3. Candidate evidence reports one eligible and one rejected candidate with the
   exact liquidity-based rejection reason.
4. Required capacity `2` versus eligible count `1` is explicit.
5. Terminal report replay is deterministic and idempotent.
6. No duplicate report is created.
7. No retrieval or financial row delta.
8. Zero active work and lease release remain correct after terminal closure
   where that path is exercised by existing terminal-closure fixtures.

## Locks preserved

- two-token requirement
- existing graduated-pool market boundary (`$3,000` exact-pool floor)
- approved ceilings
- Source Governor
- Central Scheduler
- no scoring / ranking / confidence / weighted logic
- all retrieval and financial locks
- no production retry authorization from this design alone

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Effect | Design control |
|---|---|---|
| Overloaded `source_calls` alias confuses status vs campaign totals | Operator misread | Explicit `campaign_*` and `replay_new_*`; document status zeros as action-local |
| Reconstructing candidates after process death without stored payload | Report-only of old rows stays incomplete | New writes embed candidate surface; no historical rewrite |
| Whole-table request recount on persistent DB | False huge totals | Forbidden; use holder ledger only |
| Expanding into eligibility/ceiling changes | Policy drift / forced trades risk | Hard stop; reporting only |
| Extra source call for market cap | Budget waste | Market cap optional from existing snapshot only |
| Broad suite expansion | Unrelated baseline noise | Focused tests only |

## Design decision

Proceed to implementation under this design. No ceiling, capacity, eligibility,
schema-migration, or unlock change is required.
