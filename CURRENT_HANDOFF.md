# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — POST-SCOPE-PROPAGATION-REPAIR READINESS PASS; PACKAGE PREPARATION PERMITTED AGAINST THIS COMMIT HEAD`

The V2-9.8B campaign-source-request-scope propagation repair remains closed
PASS. The post-repair fresh exact-HEAD / exact-DB readiness/governance audit is
closed PASS.

This handoff does **not** authorize application or execution.

## Latest completed work

Repair closeout:

`V2_9_8B_CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_PASS`

Readiness verdict:

`V2_9_8B_POST_SCOPE_PROPAGATION_REPAIR_FRESH_READINESS_PASS`

Readiness report:

`docs/printer-v1-v2-9-8b-post-scope-propagation-repair-fresh-readiness.md`

Repair-closeout HEAD evaluated during this readiness audit:

`952960452999379abaaf99fb579f58ae00b3ab9a`

The commit that lands this handoff and readiness report becomes the exact live
HEAD that any immediately following package preparation must bind. Do not reuse
`95296045...` or any remembered SHA as the package binding after this commit
exists.

Consumed authorization remains:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Do not retry or reuse it.

## Fresh host-local DB identity at readiness

Required authoritative DB path:

`data/printer_v1.sqlite3`

Fresh identity:

- SHA-256: `ca4c678b6164ad2aad36ed6140a06d96dc409d1cd3b64c40b17bce78a42b01dc`
- size: `146505728`
- inode: `1230526`
- mtime_ns: `1788290102639046545`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- integrity: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars: none

Preparation must re-read these facts at package-creation time and fail closed
on drift.

## Durable zero-state / quiescence at readiness

All canonical ownership domains were zero. Campaign and candidate-acquisition
leases were released/terminal. `active_printer_runtime_processes` was empty.
Historical terminal rows, including the consumed Sep-1 campaign, remain
historical residue and must not be mutated.

## Governing authorization design

Do not redesign the completed preparation boundary:

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-preparation-boundary-design.md`

Canonical owners remain authoritative:

- document validator:
  `validate_four_token_standard_four_hour_authorization_document`;
- application/consumption owner: `apply_authorization_once`;
- operational policy: `exact_operational_policy()`;
- profile: `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`;
- zero-state: `assert_four_token_standard_four_hour_zero_state`;
- prior non-reuse: `validate_prior_authorizations_non_reusable`.

## Exact next permitted action

`Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, binding the actual HEAD of this readiness commit and the freshly re-read authoritative DB identity, including the complete prior non-reuse trust root with V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe, and stop unconsumed for independent package review.`

After that package is published:

- final package state must be exactly `PREPARED / UNCONSUMED / UNAPPLIED`;
- do not create an application marker;
- do not call `apply_authorization_once`;
- do not add a later tracked commit that would recreate exact-HEAD binding drift;
- record package ID/path/SHA-256 in the operator response / package bytes only.

Independent package review is the next lane after preparation. Review PASS still
does not authorize application or execution.

## Application / execution remain blocked

This handoff does **not** authorize:

- `apply_authorization_once`;
- application-marker creation;
- Printer execution or child launch;
- campaign creation;
- provider / RPC / WebSocket calls;
- Central Scheduler runtime;
- authoritative DB mutation;
- retry / rerun / resume / restart / successor;
- retrieval / BUY / SELL / HOLD / positions / trades / audits / PnL;
- `WINDOW_12H` / `WINDOW_24H`.

## Standard-4H envelope

Preserve exactly:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- two cycles;
- exactly 2 concurrently active token slots;
- up to 4 distinct identities campaign-wide;
- Cycle 2 fresh/disjoint from prior admitted campaign identities;
- `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop`;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_12H` / `WINDOW_24H` locked;
- no automatic retry/rerun/resume/restart/successor.

## Builder sequence

```text
readiness -> design/specification -> preparation -> independent package review -> explicit application/execution approval -> one-shot bounded execution/proof -> closeout
```

Do not collapse preparation, review, application approval, and execution into
one action. The authorization-boundary design is already complete; do not redo
it.

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
