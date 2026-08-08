# Printer V1 V2-9.8B — Post-DTW82 Fresh WINDOW_15M One-Use Authorization Closeout

Date: 2026-08-08

Linear: `DTW-83`

## Verdict

`V2_9_8B_POST_DTW82_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

The operator-approved DTW-83 authorization-preparation lane completed successfully without starting Printer runtime.

## Authorization identity

- authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z`
- authorization file: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z/final_authorization.json`
- authorization SHA-256: `9bf51d6d45d79f2532808f3280ae8afcbf3bbc252ecff55ba12599ba34ba5d7a`
- schema: `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`
- authorized at: `2026-08-08T17:18:29Z`
- expires at: `2026-08-09T17:18:29Z`
- validity: `86400` seconds

## Exact Git binding

The package is bound to the unchanged authorization-report branch and commit:

- branch: `agent/v2-9-8b-post-dtw82-window15m-authorization-preparation`
- head: `3da34d21d27ddfad1e62f901f4d87c01d90b62d5`
- report: `docs/printer-v1-v2-9-8b-post-dtw82-fresh-window-15m-one-use-authorization-report.md`
- exact HEAD required: true
- tracked worktree must be clean: true

This closeout is deliberately committed on a separate branch so it does not move or invalidate the authorized branch/HEAD.

## Authoritative DB binding

The reviewed package binds exactly the seven canonical fields:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `3a27598da678c20b96685722c664e14bca45a950e416c586ffdd1f74258109cf`
- size: `69705728`
- inode: `1230526`
- mtime_ns: `1786198066668444539`
- migration count: `52`
- migration head: `052_memory_observation_eligibility_layers.sql`

Post-creation review confirmed integrity `ok`, zero foreign-key violations, and no DB mutation.

## One-use and historical authority law

The package contains the reconciled 20 historical non-reusable authorization IDs and authorizes exactly one manually started invocation.

The reviewed command flags preserve:

- allowed invocation count = 1;
- automatic retry = false;
- manual rerun = false;
- resume = false;
- restart = false;
- successor = false;
- all existing automatic/scheduled/concurrent/second-execution locks remain preserved through the unchanged V2 template.

Once the wrapper creates the application marker, this authorization is permanently consumed regardless of child success or failure. No retry, rerun, resume, restart, successor, or second invocation is permitted.

## Independent review evidence

- exact V2 template transform pre-creation review: PASS;
- temporal validity: PASS;
- exact seven-key authoritative DB binding: PASS;
- exact Git branch/HEAD binding: PASS;
- 20-ID historical non-reuse review: PASS;
- repaired pre-marker Git-provenance validation: PASS;
- reviewed pre-marker manifest SHA-256: `ac4e1bde9638676839188ccf33f4971c567a28aba724ac2ef2d5e5f5db2fc5b7`;
- pre-marker allowed file count: `20`;
- no application marker created;
- no source fetching performed;
- no Printer/Scheduler runtime started;
- no DB mutation occurred.

## Money-usefulness contribution

This gives the repaired DTW-81 transport-accounting path exactly one tightly governed real `WINDOW_15M` opportunity while preserving one-use authority, exact DB/Git provenance, Source Governor/Central Scheduler ownership, and all downstream safety locks.

## What this still does not unlock

This closeout authorizes only one manual ordinary `WINDOW_15M` invocation using the exact package above.

Still locked:

- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallets, private keys, signing, real funds, or live execution;
- paid API dependencies;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- any tracked change on the authorized branch before invocation invalidates the Git binding;
- any authoritative DB identity change before invocation invalidates the package binding;
- package expiry blocks application and must not be extended or regenerated under this authorization;
- after marker creation the authorization is consumed permanently even if the child exits nonzero;
- therefore there must be no second wrapper invocation under this ID.

## Stop condition

DTW-83 stops here. The next action is the operator's single manual one-shot wrapper invocation using the exact reviewed authorization file and SHA. No runtime has been started by this closeout.