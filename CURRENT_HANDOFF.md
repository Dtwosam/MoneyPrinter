# CURRENT_HANDOFF — Printer V1

## Current lane

`ONE EXACT FRESH STANDARD-4H ONE-SHOT APPLICATION — EXPLICITLY APPROVED`

Fresh exact-HEAD/exact-DB Standard-4H authorization preparation and independent review are complete PASS. The operator has separately and explicitly approved exactly one application/consumption of this exact reviewed authorization with:

`FRESH_STANDARD_4H_ONE_SHOT_APPLICATION = EXPLICITLY_APPROVED`

This approval permits only the canonical one-shot application described below. It does not permit a second application, retry, rerun, resume, restart, successor authorization, manual Scheduler intervention, Source Governor bypass, Central Scheduler bypass, remote/VPS work, retrieval activation, financial capability, or longer-window activation.

## Frozen runtime launch identity

The authorization remains bound to the existing local runtime branch and HEAD:

- branch: `governance/v2-9-8b-post-reconciliation-readiness-closeout`
- HEAD: `ba75c76b16cf1b5a2b44ec27822733e161b10abc`

The docs-only governance closeout branch is not runtime authority. Do not switch the Mac to the governance closeout branch before application.

## Authoritative database

Path: `data/printer_v1.sqlite3`

Exact bound SHA-256:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Migration identity remains `62 / 062_pre_admission_attempt_evidence.sql`, with current provenance package `MIGRATION_062_20260828T182504Z`.

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

Preparation verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_PREPARATION_PASS`

Independent review verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

Preparation/review closeout:

`docs/printer-v1-v2-9-8b-fresh-exact-head-exact-db-standard-4h-authorization-preparation-independent-review-closeout.md`

## Exact next permitted action

Apply this reviewed authorization exactly once through `four_token_standard_four_hour_one_shot_wrapper.apply_authorization_once` with explicit operator approval.

Immediately before consumption, fail closed unless all of the following still hold:

- local branch exactly `governance/v2-9-8b-post-reconciliation-readiness-closeout`;
- local HEAD exactly `ba75c76b16cf1b5a2b44ec27822733e161b10abc`;
- tracked/index tree clean;
- authorization file path and SHA-256 exact;
- authorization temporally valid and unconsumed;
- authoritative DB SHA exactly `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`;
- migration ledger/coherence and migration-062 provenance exact;
- all historical authorization/migration/reconciliation evidence exact;
- no application directory or marker already exists for this authorization;
- no Printer/Governor/Central Scheduler process;
- no SQLite WAL/SHM/journal sidecar;
- operational four-token Standard-4H zero-state PASS.

Any mismatch or expiry blocks before marker creation. Do not rewrite, extend, replace, retry, resume, restart, or create successor authority.

If all fresh gates pass, invoke the canonical one-shot wrapper exactly once. Once an application marker exists, the authorization is permanently consumed regardless of the child outcome.

After the one application returns, stop. Record exact wrapper status, marker/application identity, child result, terminal campaign evidence, post-DB identity, and any honest blocker. Do not automatically rerun or prepare a successor.

## Permanent consumed history

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` remains permanently consumed/non-reusable with historical disposition `CONSUMED_CHILD_EXITED_NONZERO` and must never be reused, resumed, restarted, or converted into successor authority.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors unless explicitly approved. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decisions. Retrieval and all financial capability remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and `WINDOW_24H` remain locked. Remote/VPS work remains paused at `agent/remote-host-linux-portability-implementation`, HEAD `f61419f2db37fc5eb220c20fafeaf15501218033`.
