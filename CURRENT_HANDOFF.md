# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION-PREPARATION BOUNDARY DESIGN / SPECIFICATION — NO AUTHORIZATION CREATION`

Independent post-repair readiness review result:

`PASS`

Readiness verdict:

`V2_9_8B_POST_REPAIR_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`

This reviewed readiness-closeout state becomes active when this six-doc package
is committed. Until that commit exists, do not begin the authorization-boundary
design lane. Do not invent the future readiness-closeout commit SHA. The later
design must inspect/bind the actual HEAD produced by this readiness-closeout
commit.

## Current repository state

Implementation repair:

`27964ebc050bfd263a2db275f092f3ebca7dbe46`

Aug-30 repair closeout commit:

`e79c80d872e6694fce564dbd683567e0c02622f2`

Audited repository baseline for readiness:

`e79c80d872e6694fce564dbd683567e0c02622f2`

Implementation commit message:

`Repair token-local Standard-4H lifecycle isolation`

Closeout commit message:

`Close Aug-30 lifecycle isolation repair`

The repair implementation and readiness audit are independently reviewed PASS.

## Authoritative database

Path: `data/printer_v1.sqlite3`

Exact SHA-256 audited during post-repair readiness:

`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

Read-only health facts reconfirmed during readiness:

- `PRAGMA integrity_check`: `ok`
- `PRAGMA foreign_key_check`: `0` violations
- migration count: `62`
- migration tip: `062_pre_admission_attempt_evidence.sql`
- active Scheduler jobs: `0`
- active factory runs: `0`
- active campaign-owned work (`PENDING`/`RUNNING`/`COOLDOWN`): `0`
- non-terminal campaigns: `0`
- active/stopping campaign supervision: `0`
- unreleased campaign leases: `0`
- active pre-admission attempts (`PLANNED`/`RUNNING`): `0`
- SQLite WAL/SHM/journal sidecars: absent
- Printer/Governor/Central Scheduler matching processes: none observed

Do not reuse any older pre-readiness DB SHA as current authority.

## Latest completed work

`V2_9_8B_POST_REPAIR_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`

Independent readiness operator review: `PASS`

Also:

- implementation repair commit `27964ebc050bfd263a2db275f092f3ebca7dbe46`
- Aug-30 closeout commit `e79c80d872e6694fce564dbd683567e0c02622f2`
- readiness audit:
  `docs/printer-v1-v2-9-8b-post-repair-next-bounded-campaign-readiness-audit.md`
- Aug-30 authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260830T113652Z_a89ed6bc`
  remains permanently consumed and non-reusable
- earlier consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`
  remains permanently consumed and non-reusable
  (`CONSUMED_CHILD_EXITED_NONZERO`)

No authorization currently exists for the next campaign.

Governing readiness audit:

`docs/printer-v1-v2-9-8b-post-repair-next-bounded-campaign-readiness-audit.md`

Governing repair closeout:

`docs/printer-v1-v2-9-8b-aug30-token-local-standard-4h-lifecycle-isolation-repair-closeout.md`

## Exact next permitted action

`Design/specify the fresh exact-HEAD / exact-DB one-shot Standard-4H authorization-preparation boundary for the next bounded campaign.`

This is DESIGN / SPECIFICATION ONLY.

It may define exact future authorization binding requirements, repository HEAD
identity semantics, authoritative DB SHA binding semantics, the already-approved
V2-9.8B authorization schema/profile, historical authorization non-reuse trust
root, one-shot invocation constraints, Source Governor / Central Scheduler
ownership requirements, the Standard-4H 2-concurrent / <=4 campaign-wide /
two-cycle envelope, `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated
`WINDOW_4H` → stop, no retry/rerun/resume/restart/successor, required
independent authorization-package review before any application, and later
explicit operator approval before any execution.

It does **not** authorize:

- authorization package creation
- authorization ID minting
- `final_authorization.json` writing
- authorization hashing/signing/finalization
- application-marker creation
- authorization application/consumption
- Printer execution
- another campaign
- provider/RPC/WebSocket calls
- Central Scheduler runtime
- authoritative DB mutation
- retry/rerun/resume/restart/successor
- retrieval
- BUY/SELL/HOLD
- positions/trades/audits/PnL
- `WINDOW_12H` / `WINDOW_24H`

Authorization preparation/creation remains blocked during this design lane.
Preserve the builder sequence:

```text
readiness -> authorization-boundary design/specification -> authorization preparation/implementation only if separately approved -> independent package review -> later explicit execution approval -> bounded execution/proof -> closeout
```

Do not collapse design/specification into package creation.

## Cycle-2 SELECTED residue governance

Cycle-2 slot rows from the Aug-30 failed campaign remain historical `SELECTED`
rows with null slot-level terminal timestamps. This is NOT active ownership
because canonical campaign/run/supervision/lease/Scheduler/progression truth is
terminal/drained. Do not repair or mutate those rows.

For the next authorization-boundary design, require:

```text
Raw historical slot state alone must not establish active execution authority.
Canonical campaign/run/supervision/lease/Scheduler/progression ownership truth governs active-work readiness.
```

A future design may specify a fail-closed preflight check around this rule. Do
not implement such a check in this documentation transition.

## Provider classification

Providers were not contacted. Readiness PASS is structural/governance only.
Current provider availability remains execution-time operational evidence. The
historical DexScreener transport failure is not a current committed-code
blocker. Source Governor honest safe-stop behavior remains authoritative. Do
not convert readiness PASS into provider-readiness claims.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live
wallet/private keys/signing/real funds/live execution. No paid API dependency.
No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors
unless explicitly approved. No Source Governor or Central Scheduler bypass. No
dirty-memory retrieval/decisions. Retrieval and all financial capability remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. No automatic retry/rerun/resume/restart. Remote/VPS
work remains paused at `agent/remote-host-linux-portability-implementation`,
HEAD `f61419f2db37fc5eb220c20fafeaf15501218033`.
