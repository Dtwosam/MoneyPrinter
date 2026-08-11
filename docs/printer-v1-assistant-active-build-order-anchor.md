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

V2-9.8B has progressed through the first standard-four-hour consumed attempt, its repair chain, and fresh post-repair rereadiness.

Durable anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- post-DTW100 E2Q audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`;
- first-hour Checkpoint 1-6 offline-composition chain closeout: `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- pre-attempt standard-four-hour rereadiness closeout: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- consumed standard-four-hour runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- repair-scope audit: `30bbeca17f723e5c7cfe6da25f7ef73cc6191256`;
- repair design: `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`;
- repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
- post-repair standard-four-hour rereadiness closeout: `8fd74f5d13225b72ebb56890dfd17224600189c5`.

DTW97 is permanently consumed and must not be rerun. DTW100 is closed. No historical authorization may be reused.

## Consumed standard-four-hour attempt

Authorization `V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z` was consumed exactly once and is permanently non-reusable.

Attempt identity:

- launch HEAD: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- execution: `20260810T221625Z-20e56a0c7f56`;
- campaign: `20260810T221625Z-20e56a0c7f56-campaign`;
- run: `20260810T221625Z-20e56a0c7f56-campaign-run`;
- first terminal cause: `SAFE_STOP_PREFLIGHT_FAILED`;
- retry / rerun / resume / restart / successor: none.

Independent forensics classified the blocker as a committed two-boundary preflight-composition defect. The repair is now implemented and closed:

1. standard-four-hour no longer inherits historical `operational_natural_disposition=True` from the live owner;
2. factory continuous-first-hour preflight explicitly recognizes standard-four-hour before historical compressed/natural/one-token shapes;
3. ordinary operational-natural behavior and historical one-token proof semantics remain preserved;
4. focused offline proof reaches a real factory run and both opening `WINDOW_15M` stage plans under the exact persistent two-token standard shape;
5. no holder/source/Scheduler/memory-quality/capability law was weakened.

`HOLDER_CONTEXT_BUDGET_EXHAUSTED` from the consumed attempt remains bounded holder-context truth, not the root blocker. Holder budgets were not increased and memory-observation holder-decoupling remains intact.

The consumed attempt and authorization must never be rerun, resumed, restarted, reused, or treated as successor authority.

## Fresh post-repair rereadiness

Fresh read-only rereadiness is now closed PASS at `8fd74f5d13225b72ebb56890dfd17224600189c5` with verdict:

`V2_9_8B_POST_STANDARD_4H_OPERATIONAL_REREADINESS_AFTER_PREFLIGHT_COMPOSITION_REPAIR_CLOSEOUT_PASS`

Exact rereadiness branch/HEAD before closeout documentation:

- branch: `agent/v2-9-8b-post-standard-4h-operational-rereadiness-after-preflight-composition-repair`;
- HEAD: `333e25d81af38c934048bd7924629f8ea4520665`;
- repaired implementation ancestor: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- tracked tree: clean.

Authoritative DB state observed by rereadiness:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`;
- SHA-256: `92c58ba196284b9ffb54b7d7b63fbe01771333eb0261d894a22ce4901a3c778c`;
- size: `77049856`;
- migration count/head: `54` / `054_pre_lifecycle_discovery_refresh_wait.sql`;
- integrity: `ok`;
- foreign-key violations: `0`;
- sidecars: none;
- DB unchanged during rereadiness: true.

Host/process/lease/staging state was quiescent before and after, all active operational counts were zero, and rereadiness performed:

- source calls: `0`;
- Scheduler runtime calls: `0`;
- authoritative DB writes: `0`;
- filesystem mutations: `0`;
- authorization creation: false;
- Printer/runtime start: false.

Retained evidence remains exact and audit-only:

- visible untracked evidence: `27` exact files;
- digest: `e8e20503c391384fb1f2363d34b88d189c4c501afbfb38b3fa3950067f36f53f`;
- migration package: exact `12/12`;
- migration digest: `74e690d793da5d6631160fc00bda25c05056ece197d3e8c826cf4ad2ea2b3d7c`;
- authority: `AUDIT_ONLY_NOT_RUNTIME_ALLOWLIST`;
- Git-provenance authorization fabricated during rereadiness: false.

The one standard-four-hour application marker is the expected historical marker for the consumed authorization. It remains preserved as non-reuse evidence and is not reusable authority.

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

Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, DB/lease integrity, bounded resources and one-shot authority remain fail-closed.

Memory quality remains separate. Dirty memory must never be relabeled clean or used for retrieval or decisions.

Standard-four-hour production policy remains:

- policy version: `V2-9.8-STANDARD-4H-OPERATIONAL-V1`;
- post-supply duration: `14700s`;
- pre-lifecycle acquisition: `900s`;
- governed request ceiling: `230`;
- governed requests per token: `114`;
- Scheduler-row ceiling: `210`;
- exactly two activation slots;
- automatic retries/restarts/successors: none;
- `WINDOW_12H` / `WINDOW_24H`: locked.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a main outcome, start/stop the first-four-hour lifecycle, unlock retrieval, authorize paper decisions, or create positions/trades/PnL.

## Current lane sequence

Completed:

1. repair-scope audit — **PASS**;
2. repair design — **PASS**;
3. narrow implementation — **PASS**;
4. focused offline production-shaped proof — **PASS**;
5. repair closeout — **PASS**;
6. fresh post-repair operational rereadiness — **PASS**.

Next sequence:

7. **fresh one-use standard-four-hour authorization preparation**;
8. independent authorization review and closeout;
9. only after authorization review PASS, consider at most one separately operator-started bounded standard 15m→1h→4h operational attempt;
10. independent runtime closeout before any further capability lane.

No step authorizes the next automatically. Historical authorizations remain non-reusable.

## Current lane boundary

The immediate next lane is:

`FRESH_ONE_USE_STANDARD_FOUR_HOUR_AUTHORIZATION_PREPARATION`

Allowed now:

- exact current Git/branch/HEAD verification;
- fresh read-only DB/host/provenance binding needed to prepare an authorization;
- exact historical-authorization non-reuse inventory;
- preparation of one fresh standard-profile authorization package bound to the exact then-current Git/DB/host state;
- authorization-preparation documentation.

Not allowed in preparation:

- applying/consuming the new authorization;
- starting the standard-four-hour wrapper/runtime;
- discovery/source fetching or provider calls;
- Scheduler runtime execution;
- authoritative DB mutation;
- memory generation;
- rerun/resume/restart/successor of the consumed attempt;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL;
- `WINDOW_12H` / `WINDOW_24H` activation.

After preparation, the fresh authorization must be independently reviewed and closed PASS before any new standard-four-hour runtime can be considered.

## Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no paper decisions before their explicit approved lane;
- no BUY/SELL/HOLD before its explicit approved lane;
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.

During fresh authorization preparation, do not apply or consume the authorization, start a live wrapper, contact providers, mutate the authoritative DB, generate operational memory, or unlock downstream financial capabilities. Authorization preparation must receive a separate independent review and closeout before any bounded runtime attempt.