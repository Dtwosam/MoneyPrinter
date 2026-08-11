# Printer V1 Assistant Active Build Order Anchor

## Purpose and authority

This document aligns ChatGPT, Codex, Claude, and future assistants before Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations control exact current lane position.

## Current durable state

V2-9.8B has progressed through the first consumed standard-four-hour attempt, the two-boundary preflight-composition repair chain, fresh post-repair operational rereadiness, and fresh one-use authorization preparation plus independent review.

Durable anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- first-hour Checkpoint 1-6 offline-composition closeout: `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- first standard-four-hour rereadiness closeout: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- consumed standard-four-hour runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- repair-scope audit: `30bbeca17f723e5c7cfe6da25f7ef73cc6191256`;
- repair design: `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`;
- repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
- post-repair rereadiness closeout: `8fd74f5d13225b72ebb56890dfd17224600189c5`;
- fresh authorization-review closeout: `e5708a9b132f3a268571eaae01455e5fd63d4704`.

DTW97 is permanently consumed and must not be rerun. DTW100 is closed. No historical authorization may be reused.

## Consumed standard-four-hour attempt

The prior authorization `V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z` was consumed exactly once and is permanently non-reusable.

Attempt identity:

- launch HEAD: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- execution: `20260810T221625Z-20e56a0c7f56`;
- campaign: `20260810T221625Z-20e56a0c7f56-campaign`;
- run: `20260810T221625Z-20e56a0c7f56-campaign-run`;
- first terminal cause: `SAFE_STOP_PREFLIGHT_FAILED`;
- retry/rerun/resume/restart/successor: none.

Independent forensics found a committed two-boundary preflight-composition defect. The repair is closed: standard-four-hour no longer inherits historical operational-natural disposition, and factory continuous-first-hour preflight recognizes the standard persistent two-token shape before historical proof shapes. No holder/source/Governor/Scheduler/budget/memory-quality law was weakened.

`HOLDER_CONTEXT_BUDGET_EXHAUSTED` from the consumed attempt remains bounded holder-context truth, not the root blocker. Holder budgets were not increased.

## Fresh post-repair rereadiness

Fresh read-only rereadiness closed PASS at `8fd74f5d13225b72ebb56890dfd17224600189c5` with verdict:

`V2_9_8B_POST_STANDARD_4H_OPERATIONAL_REREADINESS_AFTER_PREFLIGHT_COMPOSITION_REPAIR_CLOSEOUT_PASS`

Rereadiness bound the authoritative DB:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`;
- SHA-256: `92c58ba196284b9ffb54b7d7b63fbe01771333eb0261d894a22ce4901a3c778c`;
- size: `77049856`;
- inode: `1230526`;
- mtime_ns: `1786400211363093334`;
- migration count/head: `54` / `054_pre_lifecycle_discovery_refresh_wait.sql`;
- integrity: `ok`;
- foreign-key violations: `0`;
- sidecars: none.

Host/process/lease/staging state was quiescent and all active operational counts were zero. Rereadiness made zero source calls, zero Scheduler runtime calls, zero authoritative DB writes, created no authorization, and started no runtime.

Historical evidence remains audit-only, not a runtime allowlist. The application marker for the prior consumed standard-four-hour authorization is preserved as permanent non-reuse evidence.

## Fresh reviewed authorization

Fresh authorization preparation passed and created exactly one new, unconsumed standard-four-hour authorization:

- authorization ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T010152Z`;
- authorization file: `operator-runs/v2-9-8b-standard-four-hour-final-authorization/V2_9_8B_STANDARD_4H_AUTH_20260811T010152Z/final_authorization.json`;
- SHA-256: `f58788685f836a3c0979bfb71ddd079beb84ffba568a5ad70823554fa2bb7612`;
- size: `2611`;
- authorized at: `2026-08-11T01:01:52.093893+00:00`;
- expires at: `2026-08-11T13:01:52.093893+00:00`;
- launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`;
- exact launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`.

Independent authorization review passed and was closed at `e5708a9b132f3a268571eaae01455e5fd63d4704` with verdict:

`V2_9_8B_FRESH_ONE_USE_STANDARD_FOUR_HOUR_AUTHORIZATION_REVIEW_CLOSEOUT_PASS`

Review established:

- frozen launch branch remained exactly at `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`;
- exact authorization file/hash/schema/time/Git binding passed;
- exact DB binding remained unchanged;
- migration-ledger review passed;
- source/composition prelaunch passed with zero provider I/O;
- pre-marker Git-provenance validation passed;
- manifest SHA-256: `7a9a8629a193b10e8fdca035ebccaf3c12c1649d2bfbd22d9b457a92995ab957`;
- allowed-file-set SHA-256: `bad1f2558182e9901ed213d75053ea171ca032f67496fe3831f95ef0bdb11bbf`;
- allowed untracked file count: `30`;
- `17` historical authorization IDs are explicitly non-reusable;
- no application marker was created;
- authorization remains unapplied and unconsumed;
- no Printer runtime started;
- source calls, Scheduler runtime calls, and authoritative DB writes were all `0`.

The fresh authorization is not blanket permission. It may be consumed only once through the canonical standard-four-hour one-shot wrapper while still temporally valid and only if all launch-time fail-closed checks continue to pass.

## Active first-four-hour policy

Valid activation commits the exact same token/pair to bounded first-four-hour observation:

```text
activation
-> same exact token/pair from t=0
-> WINDOW_15M checkpoint
-> hard-gated continuation through full first hour
-> WINDOW_1H checkpoint
-> hard-gated continuation through full first four hours
-> WINDOW_4H checkpoint
-> automatic continuation stops
```

15m or 1h outcome, direction, profitability, trajectory class, manipulation label, `learning_need`, scoring, ranking, confidence, weighting, and `WINDOW_5M_MICRO_EVENT` do not behavior-qualify continuation.

Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, DB/lease integrity, bounded resources, and one-shot authority remain fail-closed. Dirty memory remains barred from retrieval or decisions.

Standard-four-hour policy:

- `V2-9.8-STANDARD-4H-OPERATIONAL-V1`;
- post-supply duration `14700s`;
- pre-lifecycle acquisition `900s`;
- governed request ceiling `230`;
- governed requests per token `114`;
- Scheduler-row ceiling `210`;
- exactly two activation slots;
- automatic retries/restarts/successors: none;
- `WINDOW_12H` / `WINDOW_24H`: locked.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a main outcome, start/stop the standard first-four-hour lifecycle, unlock retrieval, authorize paper decisions, or create positions/trades/PnL.

## Current lane sequence

Completed:

1. repair-scope audit — **PASS**;
2. repair design — **PASS**;
3. narrow implementation — **PASS**;
4. focused offline production-shaped proof — **PASS**;
5. repair closeout — **PASS**;
6. fresh post-repair operational rereadiness — **PASS**;
7. fresh one-use standard-four-hour authorization preparation — **PASS**;
8. independent authorization review and closeout — **PASS**.

Current next step:

9. **at most one separately operator-started bounded standard 15m -> 1h -> 4h attempt using only the exact reviewed authorization while it remains valid and every canonical launch-time check passes**;
10. independent runtime closeout before any further capability lane.

No step authorizes a successor automatically.

## Current lane boundary

The immediate next lane is:

`SEPARATELY_OPERATOR_STARTED_STANDARD_FOUR_HOUR_BOUNDED_ATTEMPT`

Allowed now:

- verify the exact frozen launch branch/HEAD and current authorization temporal validity;
- verify exact authorization file/hash and authoritative DB binding;
- run the canonical one-shot standard-four-hour wrapper once with explicit operator approval;
- let Source Governor and Central Scheduler perform only the already-approved bounded standard-four-hour work if pre-consumption checks pass;
- preserve all runtime evidence and safe-stop truth;
- perform independent runtime closeout after terminalization.

Not allowed:

- reusing any historical authorization;
- running the fresh authorization more than once;
- retry/rerun/resume/restart/successor after consumption;
- bypassing the canonical wrapper, Source Governor, or Central Scheduler;
- raising request, Scheduler, holder, duration, or token-capacity ceilings;
- `WINDOW_12H` / `WINDOW_24H` activation;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, paper-trade audits, or PnL;
- live trading, wallets, private keys, signing, or real funds.

If any pre-consumption binding has drifted or the authorization has expired, stop. Do not issue a replacement authorization automatically; return to the appropriate rereadiness/authorization lane.

Once the canonical application marker is created, the authorization is permanently consumed regardless of child outcome. No rerun is permitted. Independent runtime closeout is mandatory.

## Permanent restrictions

Printer V1 remains Solana-only, Solana memecoin-only, paper-trading only, with no live wallet/private keys/signing/real funds/live execution, no paid API dependency, no scoring/ranking/confidence/weighted logic, no embeddings/vectors unless explicitly approved, no Source Governor or Central Scheduler bypass, no dirty-memory retrieval/decisions, and no retrieval/paper decisions/BUY/SELL/HOLD/positions/trade events/paper-trade audits/PnL before their explicit approved lanes.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.
