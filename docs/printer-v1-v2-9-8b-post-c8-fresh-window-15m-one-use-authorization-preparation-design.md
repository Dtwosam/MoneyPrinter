# Printer V1 V2-9.8B Post-C8 Fresh WINDOW_15M One-Use Authorization Preparation — Design

Date: 2026-08-08

Linear: `DTW-72`

## Design verdict

`V2_9_8B_POST_C8_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_DESIGN_PASS`

This design defines the smallest safe authorization path after post-C8 operational re-readiness PASS. It does not create or consume an authorization and does not permit runtime.

## Proven readiness input

Exact proven Mac operational baseline:

- branch `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit`;
- HEAD `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`;
- authoritative DB SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- migrations `52/52`, integrity `ok`, FK `0`, no SQLite sidecars;
- terminal-only operational state;
- zero-I/O concrete-composition preflight PASS;
- all historical staging classified and no historical authorization reusable.

DTW-71 closeout verdict:

`V2_9_8B_POST_C8_LOCAL_OPERATIONAL_LINEAGE_STAGING_RECONCILIATION_PASS`

## Required approval gate

Before any new `final_authorization.json` is created, require explicit operator approval for exactly one new real operational ordinary `WINDOW_15M` cycle.

No inference from readiness PASS, prior authorizations, Checkpoint proof approval, or earlier operator messages may satisfy this gate.

## Fresh package contract

After explicit approval, create exactly one new authorization ID and one package:

`operator-runs/v2-9-8b-window-15m-final-authorization/<NEW_AUTH_ID>/final_authorization.json`

The package must be created once, must not reuse any historical authorization ID, and must bind the exact authorization-report commit produced by that lane.

Required authorization properties:

- verdict ends in `_PASS`;
- exact authorized branch and 40-char HEAD;
- `authorized_command.mode = run`;
- `authorized_command.operator_approved = true`;
- `allowed_invocation_count = 1`;
- automatic retry, manual rerun, resume, restart, successor all `false`;
- main window exactly `WINDOW_15M`;
- selective 1h continuation `false`;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` locked;
- Source Governor owner preserved;
- Central Scheduler owner preserved;
- paper-only, Solana-only, Solana-memecoin-only;
- no wallet/private-key/signing/real-fund/live-execution authority;
- no paid API dependency;
- no retrieval/decision/BUY/SELL/HOLD/position/trade/audit/PnL authority.

## Temporal validity

The current wrapper uses `authorization_temporal_validity.py` before staging or marker creation.

The new package must therefore include:

- timezone-aware `authorized_at`;
- timezone-aware `expires_at` or valid `validity_seconds`;
- validity no greater than `86400` seconds;
- issue age within the same maximum at application time.

Use a 24-hour validity ceiling only; do not create an open-ended package.

## Historical authorization law

The new package must explicitly list only approved historical authorization IDs under the current non-reuse field expected by the manifest owner. Directory discovery must not invent historical trust.

Every historical package remains consumed, expired, superseded, or otherwise non-current. No historical package may be revived.

## Exact-head law

Authorization creation must not silently bind the old local code HEAD if tracked authorization/report docs have advanced the branch.

Required sequence after explicit operator approval:

1. create authorization report on the dedicated DTW-72 branch;
2. bind the resulting exact report commit as `authorized_git.head`;
3. create the untracked authorization JSON only after that commit exists;
4. independently verify JSON hash and exact report/branch/HEAD binding;
5. before wrapper application, align the Mac to that exact authorized commit and recheck tracked/index cleanliness plus authoritative DB identity.

No force reset/clean/stash or evidence deletion is allowed.

## Independent review requirements

Before any wrapper application, independently prove:

- authorization ID fresh and unique;
- package contains the exact expected file only;
- exact JSON SHA-256 recorded;
- exact authorized branch/HEAD exists;
- tracked/index clean on the Mac at application boundary;
- authoritative DB SHA remains the reviewed value unless a separately approved intervening lane legitimately changes it;
- migration ledger exact and no sidecars;
- temporal validity PASS;
- no existing marker/application for the new ID;
- no current competing authorization authority;
- launch-chain identities match current reviewed wrapper/launcher/operational command;
- current source configuration passes zero-I/O validation;
- wrapper policy remains one invocation, no retry/rerun/resume/restart/successor;
- `WINDOW_15M` only and selective 1h false.

## Runtime boundary

Independent authorization review PASS still does not auto-start Printer. Runtime must be a manual one-shot wrapper invocation using the exact new authorization file and SHA.

No direct operational-command bypass is allowed.

## Money-usefulness contribution

A fresh exact-head one-use authorization converts the completed post-C8 safety/readiness work into one tightly bounded opportunity to collect new clean `WINDOW_15M` memory while preventing stale authority, obsolete code, or ambiguous evidence from consuming the scarce run.

## What this improves

- fresh exact-head authority instead of reusing historical packages;
- bounded temporal validity;
- independent package/application review before runtime;
- preservation of the proven authoritative DB and one-shot safety model.

## What this does not unlock

No provider/source call, runtime, DB mutation, memory generation, longer window, retrieval, paper decision, BUY/SELL/HOLD, position, trade, paper-trade audit, or PnL is unlocked by this design.

## Functionality Risks / Setbacks / Efficiency Blockers

- any tracked change after authorization creation invalidates exact-head readiness until reviewed;
- DB drift between authorization and application must fail closed;
- historical staging must remain evidence-only and never be treated as authority;
- a package that ages beyond the temporal limit must expire rather than be extended in place;
- no broad regression suite is required for package design; use focused exact-head/package/source-config checks.

## Stop condition

Stop here until the operator explicitly authorizes exactly one new real operational ordinary `WINDOW_15M` cycle. Do not create the authorization package, marker, manifest, or run Printer before that approval.