from pathlib import Path

root = Path.cwd()
agents = root / "AGENTS.md"
handoff = root / "CURRENT_HANDOFF.md"
closeout = root / "docs/printer-v1-v2-9-8b-fresh-exact-head-exact-db-standard-4h-authorization-preparation-independent-review-closeout.md"

old = '''### Current V2-9.8B post-reconciliation governance state — 2026-08-29

The interrupted consumed four-token execution has completed production repair,
exact-residue recovery, separately approved authoritative reconciliation, and
post-reconciliation readiness review.

Authoritative DB identity remains:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Fresh local read-only evidence reports `RECOVERED`, integrity/FKs `ok / 0`,
migration `62 / 062_pre_admission_attempt_evidence.sql`, zero active Scheduler
jobs, zero active pre-admission attempts, zero active factory runs, no campaign
lease, no Printer/Governor/Central Scheduler process, and no SQLite sidecars.
A final post-implementation local re-hash returned the same authoritative DB
SHA above.

The consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`
remains permanently consumed and non-reusable. Its exact diagnostic historical
disposition is now `CONSUMED_CHILD_EXITED_NONZERO`; this records the original
wrapper/child result and does not grant reuse authority. Any future authorization
must explicitly carry this exact ID in its approved
`prior_authorizations_non_reusable` trust root.

Post-reconciliation readiness verdict:

`V2_9_8B_POST_RECONCILIATION_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`

The exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION + INDEPENDENT REVIEW`

That lane may prepare and independently review one brand-new authorization
package only. The package must bind the then-current reviewed Git HEAD and exact
authoritative DB SHA, preserve migration-062 provenance and all historical
non-reuse trust, and remain unusable until its own independent review and later
separate operator execution approval. This lane does **not** authorize applying
or consuming an authorization, Printer execution, provider/RPC/WebSocket calls,
Central Scheduler runtime, another campaign, retry/resume/restart of the
consumed campaign, remote/VPS work, retrieval, paper decisions, positions,
trades, audits, PnL, or longer-window activation.

Governing readiness closeout:

`docs/printer-v1-v2-9-8b-post-reconciliation-next-bounded-campaign-readiness-closeout.md`
'''

new = '''### Current V2-9.8B fresh Standard-4H authorization state — 2026-08-29

The interrupted consumed four-token execution has completed production repair,
exact-residue recovery, separately approved authoritative reconciliation,
post-reconciliation readiness review, latest-consumed-authorization historical
disposition repair, fresh next-campaign readiness, and fresh exact-HEAD/exact-DB
Standard-4H authorization preparation plus independent review.

Authoritative DB identity remains:

`a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`

Fresh authorization preparation and independent review both PASS for:

- authorization ID: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41`
- authorization SHA-256: `dde07b151b07a50e782830e0111eb860bb147f4ef51ebfcfd70bde1d46f3e6af`
- exact authorized branch: `governance/v2-9-8b-post-reconciliation-readiness-closeout`
- exact authorized HEAD: `ba75c76b16cf1b5a2b44ec27822733e161b10abc`
- authoritative DB SHA-256: `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`
- current migration evidence: `MIGRATION_062_20260828T182504Z`
- prior non-reusable authorization count: `51`
- consumed Aug-28 authorization included explicitly: true
- allowed evidence file count: `110`
- allowed-file-set SHA-256: `f0146f5823291ceab9aff6fea92814025c41edee9d76551b1055385396a7bfa4`
- authorized at: `2026-08-29T12:58:11.442104+00:00`
- expires at: `2026-08-30T00:58:11.442104+00:00`
- application state exists: false
- authorization consumed: false
- runtime started: false
- independent zero-state ready: true

The consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`
remains permanently consumed and non-reusable with diagnostic historical
disposition `CONSUMED_CHILD_EXITED_NONZERO`. It is explicitly present in the
new authorization's `prior_authorizations_non_reusable` trust root.

Preparation verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_PREPARATION_PASS`

Independent review verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

The exact current permitted lane is:

`SEPARATE OPERATOR APPROVAL GATE FOR ONE EXACT ONE-SHOT STANDARD-4H APPLICATION`

This gate does not itself authorize consumption or execution. Approval must be
explicit and unmistakable; generic continuation language does not authorize the
one-shot application. If separately approved before expiry, the application
must return to the exact authorized branch/HEAD above and freshly revalidate the
exact authorization bytes/hash, temporal validity, authoritative DB identity,
migration/provenance inventory, absence of application state, host/process and
SQLite-sidecar quiescence, and operational zero-state before the canonical
one-shot wrapper may consume the authorization exactly once.

If the authorization expires, any bound identity drifts, or any fresh preflight
fails, stop without consumption. Do not extend, rewrite, retry, resume, restart,
or create application state for the expired/drifted package.

Governing preparation/review closeout:

`docs/printer-v1-v2-9-8b-fresh-exact-head-exact-db-standard-4h-authorization-preparation-independent-review-closeout.md`
'''

text = agents.read_text()
if text.count(old) != 1:
    raise SystemExit(f"AGENTS active-section replacement count={text.count(old)}")
agents.write_text(text.replace(old, new, 1))

handoff.write_text('''# CURRENT_HANDOFF — Printer V1

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

`governance/v2-9-8b-fresh-std4h-authorization-review-closeout`

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
''')

closeout.write_text('''# Printer V1 V2-9.8B Fresh Exact-HEAD / Exact-DB Standard-4H Authorization Preparation + Independent Review Closeout

Date: 2026-08-29

## Verdict

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_PREPARATION_INDEPENDENT_REVIEW_CLOSEOUT_PASS`

Fresh authorization preparation and its separate independent review both
completed PASS without consuming the authorization, creating application state,
or starting Printer/runtime work.

## Authority and lane

This closeout follows the active Printer V1 source stack and the readiness
handoff at `ba75c76b16cf1b5a2b44ec27822733e161b10abc`.

The completed lane was preparation/review only. It did not authorize execution.

## Operator-local evidence basis

The authoritative Mac host executed the bounded preparation/review script whose
reported SHA-256 was:

`ca004531c2fc4f5fb521191168ee75cd77784393ef8c9f36acbcf1dd5cbc70cc`

The following results are operator-produced local evidence supplied for this
closeout; GitHub-hosted review does not claim independent access to the Mac DB or
local untracked `operator-runs` bytes.

## Fresh authorization identity

- authorization ID: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41`
- authorization path: `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260829T125811Z_98d1df41/final_authorization.json`
- authorization SHA-256: `dde07b151b07a50e782830e0111eb860bb147f4ef51ebfcfd70bde1d46f3e6af`
- authorized branch: `governance/v2-9-8b-post-reconciliation-readiness-closeout`
- authorized HEAD: `ba75c76b16cf1b5a2b44ec27822733e161b10abc`
- authorized at: `2026-08-29T12:58:11.442104+00:00`
- expires at: `2026-08-30T00:58:11.442104+00:00`
- validity seconds: `43200`

## Exact DB and provenance binding

- authoritative DB SHA-256: `a7ad83d5f368192da7a4e7522870e3956e6f42f70b51748ff642f2c2c53683f8`
- migration execution ID: `MIGRATION_062_20260828T182504Z`
- prior non-reusable authorization count: `51`
- consumed Aug-28 authorization included in explicit trust root: true
- allowed evidence file count: `110`
- stable allowed-file-set SHA-256: `f0146f5823291ceab9aff6fea92814025c41edee9d76551b1055385396a7bfa4`

Consumed predecessor:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`

remains permanently non-reusable with exact historical disposition
`CONSUMED_CHILD_EXITED_NONZERO`.

## Preparation proof

Reported preparation verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_PREPARATION_PASS`

Preparation reported:

- exact branch/HEAD binding PASS;
- exact authoritative DB SHA binding PASS;
- migration-062 binding PASS;
- explicit historical non-reuse chain includes the consumed Aug-28 ID;
- application state absent;
- authorization unconsumed;
- runtime not started;
- allowed evidence inventory bound to the stable digest above.

## Independent review proof

Reported independent review verdict:

`V2_9_8B_FRESH_EXACT_HEAD_EXACT_DB_STANDARD_4H_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

Independent review re-derived the same authorization ID/SHA, branch/HEAD, DB SHA,
migration identity, historical non-reuse count, evidence file count, and stable
allowed-file-set digest, and reported:

- `zero_state_ready=true`;
- `application_state_exists=false`;
- `authorization_consumed=false`;
- `runtime_started=false`;
- `execution_authorized_by_this_review=false`.

The final script line was:

`NO_AUTHORIZATION_CONSUMPTION_OR_RUNTIME_PERFORMED=TRUE`

## Ephemeral manifest note

Preparation ephemeral manifest SHA-256:

`5b60975a14391e2e176adb7dace7b15df6b0f26ea6fa36c2e6260a4306c10204`

Independent-review ephemeral manifest SHA-256:

`ee8d0715b744adab4ebeb568db3dba7519d1e4bdbb2d9e0564a68e8b60e430db`

These differ because each in-memory manifest build carries its own fresh
`created_at`. The stable allowed-file-set digest matched exactly between both
passes. Neither ephemeral manifest was persisted and no application marker was
created.

## Money-usefulness contribution

This lane protects a scarce bounded campaign attempt from stale Git/DB identity,
provenance erosion, historical authorization reuse, pre-existing application
state, or known zero-state blockers before consumption. It makes no profitability
claim and unlocks no financial capability.

## What remains locked

This PASS does not itself authorize:

- authorization application or consumption;
- Printer/runtime execution;
- provider/RPC/WebSocket calls;
- Central Scheduler runtime;
- a new campaign;
- retry/rerun/resume/restart/successor behavior;
- remote/VPS work;
- `WINDOW_12H` or `WINDOW_24H`;
- retrieval or dirty-memory use;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallet/private-key/signing/real-funds/live execution;
- paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Next permitted lane

`SEPARATE OPERATOR APPROVAL GATE FOR ONE EXACT ONE-SHOT STANDARD-4H APPLICATION`

The authorization is bound to the original runtime branch/HEAD
`governance/v2-9-8b-post-reconciliation-readiness-closeout` /
`ba75c76b16cf1b5a2b44ec27822733e161b10abc`. This docs-only closeout branch is
not execution authority.

Generic continuation is not sufficient approval. A later explicit approval must
name or unmistakably authorize consumption/application of this fresh exact
authorization.

If explicit approval is later supplied before expiry, first perform fresh
pre-consumption validation of exact authorization bytes/SHA, temporal validity,
Git identity, DB identity/migration coherence, current/historical provenance,
application-state absence, host/process and SQLite-sidecar quiescence, and
operational zero-state. Any drift or expiry blocks without consumption.

If all fresh gates pass, the canonical one-shot wrapper may be invoked exactly
once. There is no retry, rerun, resume, restart, successor, extension, or rewrite
of this authorization.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authorization expires at `2026-08-30T00:58:11.442104+00:00`; expiry is a
  hard block, not a reason to extend the package.
- Any Git/DB/package/provenance/application-state drift invalidates consumption.
- Provider/network/source availability remains an honest runtime uncertainty and
  is not proven by this zero-I/O preparation/review lane.
- A later bounded attempt may still terminate on an honest operational blocker;
  that outcome must be audited rather than retried automatically.
''')
