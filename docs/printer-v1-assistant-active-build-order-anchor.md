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

Inside that source stack, `docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order. It is not the sole source of truth. Current lane position must also follow later committed audits, designs, implementations, proofs, closeouts, and explicit build-order reconciliations.

Current reconciliation:

`docs/printer-v1-v2-9-8b-post-checkpoint-8-active-roadmap-current-state-reconciliation.md`

Verdict:

`V2_9_8B_POST_CHECKPOINT_8_ACTIVE_ROADMAP_CURRENT_STATE_RECONCILIATION_PASS`

## Current state

V2-9.8B rolling ordinary `WINDOW_15M` blocker-readiness hardening is complete through Checkpoint 8.

Checkpoint 8 controlling proof:

- approved immutable proof HEAD `7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575`;
- proof ID `C8_REPROOF_AFTER_DTW67_20260808`;
- Actions run `31239317931`, job `93057459320`;
- controlling campaign `CAMPAIGN_PASS`;
- mandatory independent inspection `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`;
- artifact ID `9016671724`;
- zero network attempts;
- zero protected-capability deltas;
- zero `WINDOW_1H/WINDOW_4H/WINDOW_12H/WINDOW_24H`;
- exactly one authorization-consuming attempt and no retry/rerun/resume/restart/successor.

Checkpoint 8 closeout commit:

`8629f8da9392b958f6716c9155afdc567a797f16`

The rolling readiness-hardening tracker and Checkpoint 8 are closed PASS. The older post-migration C1-C15 and candidate-acquisition “next task” pointers are historical and must not be revived as current execution instructions.

## Exact next permitted lane

```text
V2-9.8B Post-Checkpoint-8 Authoritative WINDOW_15M Operational Re-Readiness Audit
```

Lane type: audit/readiness only.

The lane must freshly establish the authoritative local operational state before any new authorization can be considered.

Required fresh read-only facts include:

1. exact local controlling branch and full HEAD;
2. tracked/index cleanliness and explicit untracked evidence classification;
3. repository migration catalogue versus authoritative DB migration ledger;
4. authoritative DB SHA-256, size/inode, sidecars, integrity and FK state;
5. zero non-terminal campaign/run/supervision/factory/window/discovery/Scheduler work and zero active locks;
6. exact current/historical classification of every one-shot authorization and application marker;
7. no ambiguous partial application or reusable stale authority;
8. current wrapper/manifest/marker/source-configuration launch path is statically valid;
9. main window remains `WINDOW_15M`, selective 1h false, no retry/restart/resume/successor;
10. all longer-window, retrieval, decision, position, trade, audit and PnL locks remain inactive.

Historical evidence is not a substitute for the fresh local snapshot.

## Latest substantiated historical authoritative baseline

The latest authoritative operational attempt currently substantiated by retained operator evidence is:

- authorization `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`;
- branch `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement`;
- HEAD `7defc2945c42053d9c770ebc66248d27c63ff4a3`;
- execution `20260806T131312Z-829382105482`;
- first terminal cause `HolderBudgetError:PRE_HOLDER_TRANSPORT_COUNT_WITHOUT_IDENTITIES:campaign_identity_count=5,manifest_transport_count=9`;
- cleanup complete, lease released, zero active/locked Scheduler residue;
- post-attempt DB SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- DB size `69328896`, inode `1230526`;
- historical migration count/head `52 / 052_memory_observation_eligibility_layers.sql`;
- historical integrity/FK `ok / 0`.

These are historical facts only. They must be remeasured read-only before operational readiness can PASS.

Earlier package `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` was explicitly classified `BLOCKED_UNCONSUMED_SUPERSEDED`; it is not reusable. Consumed authorizations remain permanently non-reusable.

## Repository lineage rule

Do not assume the default `master` branch is the controlling operational lineage.

At the post-C8 reconciliation, `master` and the Checkpoint closeout lineage were diverged. A future authorization may bind only the exact branch/HEAD proven by the fresh operational re-readiness audit. No merge/rebase is implied by this anchor.

## Lane boundaries

Allowed in the next audit:

- static inspection;
- read-only Git/evidence/database inspection;
- existing artifact review;
- zero-I/O focused validation when needed;
- audit documentation.

Not allowed:

- authorization creation or consumption;
- wrapper application;
- providers, RPC, WebSockets or source fetching;
- Source Governor or Central Scheduler runtime;
- campaign execution;
- authoritative DB mutation;
- memory generation or promotion;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` activation;
- retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits or PnL;
- wallets, private keys, signing, real funds, live execution or paid APIs;
- scoring, ranking, confidence, weighting, embeddings or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only and never independently unlocks retrieval, decisions, BUY, positions or PnL.

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
- no BUY/SELL/HOLD unlock before its explicit approved lane;
- no paper positions, trade events, paper trade audits, or PnL before their explicit approved lanes.

## Assistant execution rule

For every major V2 section preserve:

1. audit/readiness review;
2. design/specification;
3. implementation, if approved;
4. bounded proof/test;
5. closeout.

Use minimum sufficient risk-based verification. Do not run broad suites after every prompt. Reserve broad/full suites for major lane closeout, pre-live-proof validation, releases/checkpoints, and broad architectural changes. Document unrelated pre-existing failures rather than widening scope automatically.

Assistants must never move from Checkpoint 8 PASS directly into authorization or runtime. The current next step is the fresh read-only authoritative operational re-readiness audit above.