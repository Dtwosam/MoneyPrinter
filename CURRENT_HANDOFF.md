# CURRENT_HANDOFF — Printer V1

## Current lane

`POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE ONLY`

The consumed Sep-1 Standard-4H failure is closed as a committed-code defect and
narrow scope-propagation repair. This handoff does **not** authorize application
or execution.

## Latest completed work

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

Authorization state:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Authorized HEAD for that one-shot:

`eefd909fe40b14a6459154c71ba56ace8be08b4f`

Execution:

`20260901T191450Z-520d6a348621`

Terminal cause:

`ValueError:CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

Classification:

`COMMITTED_CODE_DEFECT` / `CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS`

Repair closeout:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-closeout.md`

Forensic audit:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-forensic-audit.md`

Design:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-design.md`

Repair branch:

`assistant/v2-9-8b-campaign-source-request-scope-propagation-repair`

The commit that lands this handoff and closeout becomes the exact live HEAD that
any later readiness package must bind. Do not reuse `eefd909f...` as a future
package binding after this commit exists.

## Consumed-run zero-state

The failed run cleaned up. Do not mutate its historical rows.

- campaign/run/cycle: `TERMINAL_FAILED`
- supervision: `TERMINAL`; lease released; cleanup completed
- no active Printer process
- no active/stopping campaign ownership
- no unreleased campaign or candidate-acquisition lease
- no scheduler/factory work attributable to this run
- DB integrity `ok`; foreign-key violations `0`; no unexpected SQLite sidecars

Post-run authoritative DB identity at investigation time:

- path: `data/printer_v1.sqlite3`
- SHA-256: `ca4c678b6164ad2aad36ed6140a06d96dc409d1cd3b64c40b17bce78a42b01dc`

Any later readiness/preparation must re-read live DB identity and fail closed on
drift. Do not reuse a remembered hash.

## Exact next permitted action

`Perform a fresh exact-HEAD / exact-DB read-only readiness / governance audit against the live repair-closeout HEAD and the freshly re-read authoritative DB. Stop. Do not prepare an authorization in the same lane as this repair.`

After that readiness PASS, a later separate lane may prepare exactly one fresh
exact-HEAD / exact-DB one-shot Standard-4H authorization, including this consumed
ID in the complete prior non-reuse trust root, and must stop unconsumed for
independent package review.

## Application / execution remain blocked

This handoff does **not** authorize:

- `apply_authorization_once`
- application-marker creation
- Printer execution or child launch
- campaign creation
- provider / RPC / WebSocket calls
- Central Scheduler runtime
- authoritative DB mutation
- retry / rerun / resume / restart / successor
- retrieval / BUY / SELL / HOLD / positions / trades / audits / PnL
- `WINDOW_12H` / `WINDOW_24H`

Do not reuse `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`.

## Standard-4H envelope

Preserve exactly:

- Solana-only
- Solana memecoin-only
- paper-only
- two cycles
- exactly 2 concurrently active token slots
- up to 4 distinct identities campaign-wide
- Cycle 2 fresh/disjoint from prior admitted campaign identities
- `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop`
- `WINDOW_5M_MICRO_EVENT` support-only
- `WINDOW_12H` / `WINDOW_24H` locked
- no automatic retry/rerun/resume/restart/successor

## Builder sequence

```text
readiness -> design/specification -> preparation -> independent package review -> explicit application/execution approval -> one-shot bounded execution/proof -> closeout
```

Do not collapse readiness, preparation, review, application approval, and
execution into one action.

## Active-work governance

```text
Raw historical slot state alone must not establish active execution authority.
Canonical campaign/run/supervision/lease/Scheduler/factory/progression/pre-admission ownership truth governs active-work readiness.
```

Do not mutate historical Aug-30 Cycle-2 `SELECTED` rows.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live
wallet/private keys/signing/real funds/live execution. No paid API dependency.
No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors
unless explicitly approved. No Source Governor or Central Scheduler bypass. No
dirty-memory retrieval/decisions. Retrieval and all financial capability remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. No automatic retry/rerun/resume/restart.

Remote/VPS work remains paused at
`agent/remote-host-linux-portability-implementation`, HEAD
`f61419f2db37fc5eb220c20fafeaf15501218033`.
