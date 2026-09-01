# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — HOST-LOCAL PREPARATION-ENTRY REBIND PASS; PACKAGE PREPARATION PERMITTED AGAINST THIS COMMIT HEAD`

The V2-9.8B freeze-ready candidate-supply reliability repair remains closed
PASS. The previously blocked GitHub-runner preparation-entry attempt is
superseded by a completed authoritative-host read-only rebind PASS.

This handoff does **not** authorize application or execution.

## Latest completed work

Candidate-supply closeout verdict:

`V2_9_8B_FREEZE_READY_CANDIDATE_SUPPLY_RELIABILITY_CLOSEOUT_PASS`

Closeout:

`docs/printer-v1-v2-9-8b-freeze-ready-candidate-supply-reliability-closeout.md`

Preparation-entry report:

`docs/printer-v1-v2-9-8b-post-candidate-supply-preparation-entry-rebind.md`

Preparation-entry verdict:

`V2_9_8B_POST_CANDIDATE_SUPPLY_PREPARATION_ENTRY_REBIND_PASS`

Code-defect verdict for that rebind:

`NO_CODE_DEFECT_PROVEN_BY_THIS_REBIND`

Branch:

`assistant/freeze-ready-candidate-supply`

Pre-commit HEAD evaluated during the host-local rebind:

`93d9fa2f5b16af1326a419abbbfba744a8e1c424`

The commit that lands this handoff and the updated rebind report becomes the
exact live HEAD that any immediately following package preparation must bind.
Do not reuse `93d9fa2f...` or any remembered SHA as the package binding after
this commit exists.

## Fresh host-local DB identity at rebind

Required authoritative DB path:

`data/printer_v1.sqlite3`

Fresh identity:

- SHA-256: `f5ea648a3f77a3cdb72aed2c9d6520018a02308303ee8150ba78aa94c165888b`
- size: `146202624`
- inode: `1230526`
- mtime_ns: `1788262599935401784`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- integrity: `ok`
- foreign-key violations: `0`
- sidecars: none

Preparation must re-read these facts at package-creation time and fail closed
on drift.

## Durable zero-state / quiescence at rebind

All canonical ownership domains were zero. Campaign and candidate-acquisition
leases were released/terminal. `active_printer_runtime_processes` was empty.
Historical Aug-30 Cycle-2 `SELECTED` rows remain historical residue under
terminal campaigns and must not be mutated.

## Stale frozen authorization

Authorization ID:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

Frozen SHA-256:

`5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`

Final state:

`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

No application or consumption occurred. Do not alter, rebind, renew, delete,
rename, move, or apply it. It remains required in the complete prior non-reuse
trust root for every future Standard-4H package.

Later consumed packages `...804f9a32` and `...7e03d673` also remain permanently
non-reusable and must stay in that trust root.

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

`Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, binding the actual HEAD of this handoff/rebind commit and the freshly re-read authoritative DB identity, including the complete prior non-reuse trust root with V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46, and stop unconsumed for independent package review.`

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
one action.

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
