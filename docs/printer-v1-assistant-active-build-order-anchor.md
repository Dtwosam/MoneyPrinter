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

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations control current lane position.

## Current state

Checkpoint 8 controlling proof and independent inspection passed on immutable proof HEAD `7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575` and closed at `8629f8da9392b958f6716c9155afdc567a797f16`.

Post-C8 roadmap/current-state reconciliation passed at `6cbf22945d5429c993d1c9acf50f1d3cb70cf585`.

The post-C8 authoritative `WINDOW_15M` operational re-readiness sequence is now complete:

- DTW-70 static/fresh audit identified local-lineage and staging-classification blockers;
- DTW-71 classified all historical staging, proved zero untracked-path collisions, and non-destructively aligned the Mac checkout;
- exact proven local operational baseline: `cd0a422d84a0076dd03ba34f1a764fc8795f6aaf`;
- local branch: `agent/v2-9-8b-post-c8-operational-window15m-rereadiness-audit`;
- authoritative DB SHA-256: `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- migrations `52/52`, integrity `ok`, FK violations `0`, no SQLite sidecars;
- all inspected campaign/factory/discovery/Scheduler state is terminal-only;
- zero-I/O concrete-composition preflight PASS;
- all seven staging entries classified, zero ambiguous, no historical authorization reusable.

Controlling closeout:

`docs/printer-v1-v2-9-8b-post-c8-local-operational-lineage-staging-reconciliation-closeout.md`

Verdict:

`V2_9_8B_POST_C8_LOCAL_OPERATIONAL_LINEAGE_STAGING_RECONCILIATION_PASS`

## Exact next permitted lane

```text
V2-9.8B Post-C8 Fresh WINDOW_15M One-Use Authorization Preparation and Independent Review
```

This is an authorization-preparation lane, not runtime permission.

Required order:

1. design/specify the fresh one-use authorization package against the exact current reviewed lineage;
2. create exactly one fresh authorization only after explicit operator approval;
3. independently review exact branch/HEAD, clean tracked/index state, authoritative DB identity, temporal validity, launch-chain identities, no-current-authority state, `WINDOW_15M`-only policy, selective-1h false, and no retry/rerun/resume/restart/successor;
4. close the authorization lane;
5. only after that may the operator separately invoke the one-shot wrapper exactly once.

No historical authorization package may be reused.

## Repository lineage rule

Do not assume default `master` is controlling. Future authorization may bind only an exact freshly reviewed branch/HEAD descended from the proven post-C8 lineage. Any tracked change after a readiness review requires exact-head re-review.

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
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes;
- no `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation before explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently unlock outcome memory, retrieval, decisions, positions, trades, or PnL.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.

Do not create or consume a fresh authorization, invoke the wrapper, contact providers, mutate the authoritative DB, generate memory, or unlock downstream financial capabilities without the explicit approved lane and operator authorization.