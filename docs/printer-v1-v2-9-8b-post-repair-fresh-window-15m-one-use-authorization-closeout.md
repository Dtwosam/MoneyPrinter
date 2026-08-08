# Printer V1 V2-9.8B Post-Repair Fresh WINDOW_15M One-Use Authorization — Closeout

Date: 2026-08-08

Linear: `DTW-77`

## Verdict

`V2_9_8B_POST_REPAIR_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

Exactly one fresh post-repair ordinary `WINDOW_15M` one-use authorization was prepared after the required Mac alignment/readiness gate passed. Package-level independent review and the final Mac application-boundary pre-marker review both passed. No application manifest, application marker, provider/runtime call, Scheduler/Printer execution, authoritative DB mutation, or memory generation occurred in this lane.

## Exact authorization

- Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z`
- Authorization SHA-256: `4e6f4ae2845ed8bb09241d49868e18d6f2c80a9adbf464e35c9ebd26dd941253`
- Authorized branch: `agent/v2-9-8b-post-c8-window15m-postrepair-authorization-preparation`
- Authorized exact HEAD: `1667d3a1391ef4e93766fcdc0d5824d3da2f2127`
- Authorized at: `2026-08-08T13:31:00Z`
- Expires at: `2026-08-09T13:31:00Z`
- Validity: 86400 seconds
- Allowed invocation count: 1
- Retry/rerun/resume/restart/successor: forbidden

## Authoritative database binding

The authorization binds exactly the canonical seven fields and no extras:

- path `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`
- size `69328896`
- inode `1230526`
- mtime_ns `1786022001929258221`
- migration count `52`
- migration head `052_memory_observation_eligibility_layers.sql`

The repaired pre-authorization migration-ledger review returned `V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_PASS`.

## Final Mac application-boundary evidence

The operator-provided final pre-marker output established:

- current branch `agent/v2-9-8b-post-c8-window15m-postrepair-authorization-preparation`;
- current HEAD `1667d3a1391ef4e93766fcdc0d5824d3da2f2127`;
- exact authorization SHA matched;
- temporal status `TEMPORALLY_VALID`;
- authoritative database exact key count `7`;
- DB SHA unchanged at `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- integrity `ok`;
- foreign-key violations `0`;
- no unexpected nonterminal operational state;
- canonical application absent;
- current authorization staging matches `[]`;
- zero-I/O concrete composition PASS;
- provenance manifest built in memory only, current file count `13`;
- malformed prior authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` explicitly non-reusable;
- prior non-reusable authorization count `15`;
- manifest not written;
- marker not written;
- runtime not started.

Final markers:

- `DTW77_POST_REPAIR_APPLICATION_BOUNDARY_PREMARKER_REVIEW_PASS`
- `DTW77_EXACT_POST_REPAIR_AUTHORIZATION_INSTALLED_AND_REVIEWED`
- `NO_MANIFEST_MARKER_OR_RUNTIME_CREATED`

## Money-usefulness contribution

This gate protects the scarce real `WINDOW_15M` proof opportunity from another structurally invalid package and ensures the real run starts only from a repaired, exact, independently reviewed authorization boundary.

## What this improves

- exact package DB-binding shape is verified before application;
- Mac tracked lineage is bound to the exact authorization HEAD;
- the authoritative DB identity and health are unchanged;
- competing current application/staging residue is absent;
- the wrapper's full provenance manifest can be constructed successfully before consumption.

## What this still does not unlock

This closeout permits only the one already operator-authorized ordinary `WINDOW_15M` wrapper invocation. It does not unlock `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live funds, paid APIs, scoring/ranking/confidence/weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The next wrapper invocation is single-use by operator policy. Once attempted, no retry/rerun/resume/restart/successor is permitted under this authorization, regardless of outcome.
- The authorization must remain temporally valid and Git/DB-bound at application time.
- Any tracked HEAD change or authoritative DB identity change before invocation invalidates readiness and must block.
- The historical malformed authorization remains evidence only and non-reusable.

## Next gate

Perform exactly one manual invocation through `scripts/Start-PrinterV1-Window15M-OneShot.ps1` with the exact authorization path/SHA and `-OperatorApproved`, then stop immediately after terminalization for evidence closeout. No second Printer command is permitted under this authorization.