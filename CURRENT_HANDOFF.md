# CURRENT_HANDOFF — Printer V1

## Current lane

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION`

Independent authorization-boundary design review result:

`PASS`

Design classification:

`EXISTING_OWNER_ALREADY_SUFFICIENT`

This reviewed design and preparation-lane state becomes active only when this
six-doc package is committed. Until that commit exists, do not begin
authorization preparation. Do not invent the future design-closeout commit SHA.
The later preparation task must inspect the actual HEAD produced by this
commit.

## Current repository state

Implementation repair:

`27964ebc050bfd263a2db275f092f3ebca7dbe46`

Aug-30 repair closeout commit:

`e79c80d872e6694fce564dbd683567e0c02622f2`

Readiness closeout / design baseline commit:

`7d5c3a631091af7e07f941fe56647d6ffc596d46`

Design:

`NEXT STANDARD-4H AUTHORIZATION-PREPARATION BOUNDARY DESIGN`

Governing design document:

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-preparation-boundary-design.md`

No code change is required. Existing canonical wrapper/profile/policy/
non-reuse/zero-state owners remain authoritative. The design baseline HEAD
`7d5c3a631091af7e07f941fe56647d6ffc596d46` is NOT the future package binding
after this docs package is committed.

## Authoritative database

Path: `data/printer_v1.sqlite3`

Design-time / last verified authoritative DB SHA-256:

`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

Preparation must recompute the live DB SHA and full identity fields at
preparation time. Do not treat a remembered design-time SHA as a substitute for
live measurement.

## Latest completed work

- readiness verdict:
  `V2_9_8B_POST_REPAIR_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`
- readiness independent review: `PASS`
- authorization-boundary design independent review: `PASS`
- design classification: `EXISTING_OWNER_ALREADY_SUFFICIENT`
- Aug-30 authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260830T113652Z_a89ed6bc`
  remains permanently consumed and non-reusable
- earlier consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`
  remains permanently consumed and non-reusable
  (`CONSUMED_CHILD_EXITED_NONZERO`)

No authorization currently exists for the next campaign.

## Exact next permitted action

`Prepare one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, freeze/hash the exact package bytes, and stop unconsumed for independent package review.`

This lane permits PACKAGE CREATION ONLY.

It does **not** authorize:

- application/consumption
- `apply_authorization_once`
- application-marker creation
- Printer execution
- child launch
- campaign creation
- provider/RPC/WebSocket calls
- Central Scheduler runtime
- authoritative DB mutation
- retry/rerun/resume/restart/successor
- retrieval
- BUY/SELL/HOLD
- paper positions/trades/audits/PnL
- `WINDOW_12H` / `WINDOW_24H`

Application/consumption/execution remain blocked after this package is
committed. Independent package review remains mandatory. A further explicit
operator approval remains mandatory before `apply_authorization_once`.

## Preparation-time rebinding rule

The future preparation task MUST re-read the actual HEAD produced by this
source-stack/design commit. Do not bind a package to
`7d5c3a631091af7e07f941fe56647d6ffc596d46` merely because that was the design
baseline.

After commit, preparation must freshly establish:

- actual Git HEAD;
- actual branch;
- tracked-clean tree;
- authoritative DB path;
- DB SHA-256;
- DB size/inode/mtime_ns;
- migration count/head;
- integrity/FKs/sidecars;
- canonical campaign/run/supervision/lease/Scheduler/factory/progression/
  pre-admission quiescence.

The future package binds those preparation-time identities. Any mismatch from
the independently approved preparation baseline must fail closed.

## Canonical owners

Preserve these exact existing owners:

- document validator:
  `validate_four_token_standard_four_hour_authorization_document`
  in `src/printer_v1/operator_cli/four_token_standard_four_hour_one_shot_wrapper.py`
- application/consumption owner:
  `apply_authorization_once` in the same module
- operational policy: `exact_operational_policy()`
- authorization profile: `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`
- zero-state owner: `assert_four_token_standard_four_hour_zero_state`
- prior non-reuse validation: `validate_prior_authorizations_non_reusable`

No parallel authorization schema/runner/application path is permitted.

## Authorization profile

- schema: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`
- wrapper: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_ONE_SHOT_WRAPPER_V1`
- Git manifest: `PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1`
- policy: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- mode: `four-token-standard-four-hour-run`
- current migration evidence: migration 062
- prior migrations remain historical evidence

## Non-reuse trust

Future preparation derives the complete prior non-reuse root from authoritative
durable/committed evidence. Minimum required IDs include
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260830T113652Z_a89ed6bc` and
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5`, but those are not
assumed to be the complete set. Directory discovery never creates authorization
trust. Every consumed authorization remains permanently non-reusable.

## Active-work governance

```text
Raw historical slot state alone must not establish active execution authority.
```

Canonical campaign/run/supervision/lease/Scheduler/factory/progression/
pre-admission ownership truth governs active-work readiness. Do not mutate the
historical Aug-30 Cycle-2 `SELECTED` rows.

## Standard-4H envelope

Preserve exactly: Solana-only; Solana memecoin-only; paper-only; two cycles;
exactly 2 concurrent active token slots; up to 4 distinct identities
campaign-wide; Cycle 2 fresh/disjoint; `WINDOW_15M`; hard-gated `WINDOW_1H`;
hard-gated `WINDOW_4H`; stop at 4h; `WINDOW_5M` support-only; `WINDOW_12H` /
`WINDOW_24H` locked; no automatic retry/rerun/resume/restart/successor.

## Builder sequence

```text
readiness -> authorization-boundary design/specification -> authorization preparation -> independent package review -> later explicit application/execution approval -> bounded execution/proof -> closeout
```

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
