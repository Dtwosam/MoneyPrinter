# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — PREPARATION-ENTRY REBIND REQUIRED AFTER CANDIDATE-SUPPLY REPAIR`

The V2-9.8B freeze-ready candidate-supply reliability repair is closed PASS.
This handoff does not itself approve a new authorization package and does not
authorize application or execution.

The existing reviewed authorization-preparation boundary remains governing, but
its mandatory preparation-time identity/readiness rebind must run against the
actual post-closeout HEAD and authoritative DB before any package bytes are
created or finalized.

## Latest completed work

Closeout verdict:

`V2_9_8B_FREEZE_READY_CANDIDATE_SUPPLY_RELIABILITY_CLOSEOUT_PASS`

Governing closeout:

`docs/printer-v1-v2-9-8b-freeze-ready-candidate-supply-reliability-closeout.md`

Candidate-supply branch:

`assistant/freeze-ready-candidate-supply`

Reviewed/squashed repair HEAD immediately before the closeout commit:

`3ac80cbb2ffa424667dd98d3c35c89bd00d883da`

That repair preserved the final verified tree while collapsing post-review
repair/proof churn.

Final focused verification on that repaired tree:

- 22 focused tests passed;
- changed Python compiled;
- explicit repaired-invariant checks passed;
- `git diff --check` passed;
- temporary verification workflow removed;
- temporary `proof-logs/` removed.

The repair closed:

- canonical valid-zero freeze-ready depth semantics;
- cumulative temporal-refresh coverage carry into canonical freeze readiness;
- later-cycle refresh carrier binding;
- obsolete campaign-level invented temporal runtime facts;
- current-run source-authority truthfulness already carried by the reviewed
  candidate-supply line.

No budget/ceiling, capacity, Source Governor, Central Scheduler, retrieval,
financial, or longer-window lock was widened.

## Authoritative DB identity

Authoritative DB path:

`data/printer_v1.sqlite3`

Last previously approved DB SHA-256 carried by the stale-authorization handoff:

`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

That hash is historical input only now. The candidate-supply lane did not mutate
the authoritative DB, but no future authorization package may reuse a remembered
DB identity. Preparation must recompute and independently accept the live DB
path/hash/size/inode/mtime, migration count/head, integrity/FKs, sidecars, and
ownership quiescence.

## Stale frozen authorization

Authorization ID:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

Frozen SHA-256 (byte-identical; do not alter):

`5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`

Frozen repository HEAD binding:

`abdd210d2d1e0788d241d8a26f09b9a60a105912`

Package path:

`operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46/final_authorization.json`

Final pre-application verdict:

`V2_9_8B_FROZEN_STD4H_PREAPPLICATION_APPROVAL_BLOCKED`

Blocker:

`AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`

Stale authorization final state:

`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

No application or consumption occurred. Do not describe this package as
consumed. Do not alter, rebind, renew, delete, rename, move, or apply it.

`...b6d7ab46` remains required in the complete prior non-reuse trust root for
every future Standard-4H package.

## Governing authorization design

Do not redo the completed authorization-boundary design:

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

Run the read-only preparation-entry rebind required by the governing design
against the actual HEAD containing this closeout/handoff and the authoritative
DB.

Freshly establish, without authoritative DB mutation:

- exact live Git HEAD and branch;
- tracked-clean state;
- exact authoritative DB path/hash/size/inode/mtime;
- migration count/head;
- integrity/FKs and absence of SQLite WAL/SHM/journal sidecars;
- zero non-terminal campaign/run/cycle ownership;
- zero active/stopping supervision;
- zero unreleased leases;
- zero active Scheduler jobs;
- zero active factory runs/steps/campaign work;
- zero active pre-admission attempts outside terminal dispositions;
- canonical Standard-4H schema/profile/policy/command mode;
- exact 4/2/2 envelope and lifecycle locks;
- complete permanent prior-authorization non-reuse trust root, including
  `...b6d7ab46`;
- no retrieval/financial/12h/24h unlock;
- no Source Governor or Central Scheduler bypass.

The prior preparation approval must not be treated as automatically approving a
package against the repaired production HEAD. If the current preparation-time
HEAD/DB identity is not independently accepted, or any required gate fails,
stop without creating/finalizing a package and record the exact blocker.

If and only if every preparation-entry gate passes and the exact current
HEAD/DB are accepted for preparation, exactly one fresh Standard-4H
authorization package may be prepared using the existing canonical owners. It
must stop:

`PREPARED / UNCONSUMED / UNAPPLIED`

for independent package review.

This is not application approval and not execution approval.

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
