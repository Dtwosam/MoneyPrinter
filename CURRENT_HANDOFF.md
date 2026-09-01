# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — AUTHORITATIVE-HOST PREPARATION-ENTRY REBIND BLOCKED PENDING HOST-LOCAL EVIDENCE`

The V2-9.8B freeze-ready candidate-supply reliability repair is closed PASS.
The repository-side preparation-entry attempt after that closeout failed closed
because the authoritative host-local DB/runtime evidence is unavailable from a
GitHub runner.

This handoff does not approve a new authorization package and does not authorize
application or execution.

## Latest completed work

Candidate-supply closeout verdict:

`V2_9_8B_FREEZE_READY_CANDIDATE_SUPPLY_RELIABILITY_CLOSEOUT_PASS`

Closeout:

`docs/printer-v1-v2-9-8b-freeze-ready-candidate-supply-reliability-closeout.md`

Preparation-entry report:

`docs/printer-v1-v2-9-8b-post-candidate-supply-preparation-entry-rebind.md`

Preparation-entry verdict:

`V2_9_8B_POST_CANDIDATE_SUPPLY_PREPARATION_ENTRY_REBIND_BLOCKED`

Code-defect verdict for that rebind:

`NO_CODE_DEFECT_PROVEN_BY_THIS_REBIND`

Package state:

`NOT_CREATED / NOT_PREPARED / UNCONSUMED / UNAPPLIED`

Candidate-supply branch:

`assistant/freeze-ready-candidate-supply`

Last exact target HEAD evaluated by the remote rebind:

`2e398087c279375d527cc7172eaa8a84fac5affb`

The remote verifier proved that exact checked-out HEAD and a clean committed
tracked checkout. It then failed at the first authoritative DB gate with:

`BLOCKER: authoritative DB missing`

`data/printer_v1.sqlite3` is not in the GitHub checkout. Therefore GitHub cannot
prove the authoritative host's DB filesystem identity/health/zero-state or its
live Printer/process quiescence.

The report/handoff commit changes HEAD after the evaluated `2e398...` state.
Every future preparation attempt must resolve and bind the actual live HEAD at
that time; do not reuse `2e398...` as a remembered authorization binding.

## Candidate-supply repair evidence

Reviewed/squashed repair commit before closeout:

`3ac80cbb2ffa424667dd98d3c35c89bd00d883da`

Final focused verification on the repaired production tree reported:

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

Required authoritative DB path:

`data/printer_v1.sqlite3`

Last historically approved DB SHA-256 carried by the stale-authorization
handoff:

`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

That hash is historical evidence only. It must not be reused as current truth.
The candidate-supply lane did not mutate the authoritative DB, but a future
package requires a fresh host-local read-only rebind of path/hash/size/inode/
mtime, migration count/head, integrity/FKs, sidecars, durable zero-state, and
ownership/runtime quiescence.

## Stale frozen authorization

Authorization ID:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

Frozen SHA-256:

`5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`

Frozen repository HEAD binding:

`abdd210d2d1e0788d241d8a26f09b9a60a105912`

Package path:

`operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46/final_authorization.json`

Final pre-application verdict:

`V2_9_8B_FROZEN_STD4H_PREAPPLICATION_APPROVAL_BLOCKED`

Blocker:

`AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`

Final state:

`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

No application or consumption occurred. Do not alter, rebind, renew, delete,
rename, move, or apply it. `...b6d7ab46` remains required in the complete prior
non-reuse trust root for every future Standard-4H package.

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

No new CLI, replacement owner, or bypass is justified by the missing host-local
evidence.

## Exact next permitted action

Run the existing canonical **read-only preparation-entry rebind on the
authoritative operator host** against:

1. the actual live Git HEAD containing this report/handoff; and
2. the actual host-local `data/printer_v1.sqlite3`.

Freshly establish, without authoritative DB mutation:

- exact live Git HEAD and branch;
- live tracked-clean state;
- exact authoritative DB path/hash/size/inode/mtime;
- migration count/head;
- integrity/FKs and absence of SQLite WAL/SHM/journal sidecars;
- zero non-terminal campaign/run/cycle ownership;
- zero active/stopping supervision;
- zero unreleased leases;
- zero active Scheduler jobs;
- zero active factory runs/steps/campaign work;
- zero active pre-admission attempts outside terminal dispositions;
- live Printer/process quiescence;
- canonical Standard-4H schema/profile/policy/command mode;
- exact 4/2/2 envelope and lifecycle locks;
- complete permanent prior-authorization non-reuse trust root, including
  `...b6d7ab46`;
- no retrieval/financial/12h/24h unlock;
- no Source Governor or Central Scheduler bypass.

If any gate is missing, unprovable, or failing, stop without package creation
and record the exact blocker.

If and only if every preparation-entry gate passes and the exact current
HEAD/DB are independently accepted for preparation, exactly one fresh
Standard-4H authorization package may be prepared using the existing canonical
owners. It must stop:

`PREPARED / UNCONSUMED / UNAPPLIED`

for independent package review.

That is not application approval and not execution approval.

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
