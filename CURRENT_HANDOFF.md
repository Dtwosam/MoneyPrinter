# CURRENT_HANDOFF — Printer V1

## Current lane

`SEPARATE OPERATOR APPROVAL GATE FOR ONE EXACT ONE-SHOT STANDARD-4H APPLICATION`

Fresh exact-HEAD/exact-DB Standard-4H authorization preparation and independent
review are complete PASS. This lane is an approval gate only. It does not itself
authorize authorization application/consumption, Printer execution,
providers/RPC/WebSocket, Central Scheduler runtime, another campaign, or
remote/VPS work.

Generic continuation language is not execution approval. A later approval must
be explicit and unmistakable for this exact authorization.

## Current repository state

Governance closeout branch:

`governance/v2-9-8b-fresh-std4h-authorization-review-closeout-final`

Authorized runtime branch/HEAD remain frozen separately as:

- branch: `governance/v2-9-8b-post-reconciliation-readiness-closeout`
- HEAD: `ba75c76b16cf1b5a2b44ec27822733e161b10abc`

The governance closeout commit is documentation-only and is **not** the
authorized runtime Git identity. Any later separately approved consumption must
return to the exact authorized branch/HEAD above.

## Authoritative database

Path: `data/printer_v1.sqlite3`

Exact SHA-256 bound by the fresh authorization:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Migration identity remains `62 / 062_pre_admission_attempt_evidence.sql`, with
current provenance package `MIGRATION_062_20260828T182504Z`.

## Fresh reviewed authorization

- ID: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41`
- file: `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41/final_authorization.json`
- SHA-256: `dde07b151b07a50e782830e0111eb860bb147f4ef51ebfcfd70bde1d46f3e6af`
- authorized at: `2026-08-29T12:58:11.442104+00:00`
- expires at: `2026-08-30T00:58:11.442104+00:00`
- validity: `43200` seconds
- prior non-reusable authorization count: `51`
- consumed Aug-28 authorization included: true
- allowed evidence file count: `110`
- allowed-file-set SHA-256: `f0146f5823291ceab9aff6fea92814025c41edee9d76551b1055385396a7bfa4`
- application state exists: false
- consumed: false
- runtime started: false
- independent zero-state ready: true

Preparation verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_PREPARATION_PASS`

Independent review verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

The separately rebuilt ephemeral manifest SHA values differed because each
in-memory build used its own `created_at`; the stable allowed-file-set SHA-256
matched exactly in both passes. No manifest or application marker was persisted.

## Historical non-reuse

Consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` remains permanently
non-reusable with historical disposition `CONSUMED_CHILD_EXITED_NONZERO`. The
fresh authorization explicitly carries it in `prior_authorizations_non_reusable`.

## Exact next permitted action

Wait for a **separate explicit operator approval** for one exact application of
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41`.

No application is approved by this handoff. If explicit approval is later given,
first return to the exact authorized runtime branch/HEAD and freshly prove,
before any marker or child launch:

- authorization file path and SHA-256 exact;
- authorization still temporally valid and unconsumed;
- exact Git branch/HEAD and tracked/index cleanliness;
- authoritative DB SHA-256 exact and migration ledger/coherence clean;
- migration-062/current and all historical provenance inventories exact;
- no application state exists;
- no Printer/Governor/Central Scheduler process;
- no SQLite WAL/SHM/journal sidecar;
- operational four-token Standard-4H zero-state PASS.

Any mismatch or expiry blocks consumption with no retry, rewrite, extension,
resume, restart, successor, provider call, Scheduler runtime, or DB mutation.

Only after those fresh gates pass may the canonical one-shot wrapper be called
exactly once under the separately explicit approval.

## Latest completed work

Fresh authorization preparation + independent review closed PASS without
consumption or runtime. Closeout:

`docs/printer-v1-v2-9-8b-fresh-exact-head-exact-db-standard-4h-authorization-preparation-independent-review-closeout.md`

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet/private
keys/signing/real funds/live execution. No paid API dependency. No
scoring/ranking/confidence/weighted decision logic. No embeddings/vectors unless
explicitly approved. No Source Governor or Central Scheduler bypass. No dirty
memory retrieval/decisions. Retrieval and all financial capability remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. Remote/VPS work remains paused at
`agent/remote-host-linux-portability-implementation`, HEAD
`f61419f2db37fc5eb220c20fafeaf15501218033`.
