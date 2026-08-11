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

V2-9.8B has now consumed two separately authorized standard-four-hour attempts. Neither is a successful 4h proof and neither authorization may ever be reused.

Durable anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- post-DTW100 E2Q audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`;
- first-hour Checkpoint 1-6 offline-composition chain closeout: `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- first consumed standard-four-hour runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- first-attempt repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- first-attempt repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
- post-repair standard-four-hour rereadiness closeout: `8fd74f5d13225b72ebb56890dfd17224600189c5`;
- second standard-four-hour launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`;
- second standard-four-hour runtime classification closeout: `623ea64657555341419fe92f000435e11ab52d5c`.

DTW97 remains permanently consumed. DTW100 remains closed. No historical authorization may be reused.

## First consumed standard-four-hour attempt

Authorization `V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z` was consumed exactly once at launch HEAD `3b558d2af77ac469dd0d6c2f04e3993515988b2e`.

It stopped at `SAFE_STOP_PREFLIGHT_FAILED`. Independent forensics proved a committed preflight-composition defect. That defect was audited, designed, repaired, focused-proofed, closed, and followed by fresh operational rereadiness PASS.

That authorization remains permanently non-reusable.

## Second consumed standard-four-hour attempt

Fresh authorization:

- ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T010152Z`;
- SHA-256: `f58788685f836a3c0979bfb71ddd079beb84ffba568a5ad70823554fa2bb7612`;
- frozen launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`;
- exact launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`.

Attempt identity:

- execution: `20260811T011906Z-2e278d795b54`;
- campaign: `20260811T011906Z-2e278d795b54-campaign`;
- campaign run: `20260811T011906Z-2e278d795b54-campaign-run`;
- authoritative factory run: `7a84b80b-4f51-4516-84e9-828132a45009`;
- first terminal cause: `SAFE_STOP_4H_TERMINAL_INCOMPLETE`;
- wrapper child exit: `0`;
- child terminal valid: true;
- retry / rerun / resume / restart / successor: none.

The authorization passed preparation and independent review, was consumed exactly once, and is permanently non-reusable.

## Second-attempt runtime truth

Read-only reconstruction closed PASS with root-cause classification:

`COMMITTED_CODE_DEFECT_AT_WINDOW_1H_TO_WINDOW_4H_SAFETY_PROVENANCE_INTEGRATION_BOUNDARY`

The runtime itself did not pass 4h proof.

### Proven successful before the blocker

Both selected tokens completed:

- physical `WINDOW_15M` rows `165` and `166`;
- clean 15m episodes `62` and `63`;
- all 16 scheduled 15m snapshots;
- both 15m closes;
- all 24 `WINDOW_1H` continuation snapshots;
- both 1h closes;
- physical `WINDOW_1H` rows `169` and `170`;
- clean 1h episodes `64` and `65`;
- campaign 1h ownership state `CLEAN_PROMOTED` for both tokens.

The current-run 15m and 1h clean memories remain valid memory evidence. They do not make the attempted campaign a successful 4h proof.

### Exact 1h -> 4h failure

The first 1h close reached `AWAITING_PEER_FIRST_HOUR_CLOSE` as designed.

After the second 1h close, the standard-four-hour barrier reached its two-token decision point but returned:

- barrier reached: true;
- successful first-hour closes: `2`;
- continuation count: `0`;
- eligible token slots: none;
- planned 4h jobs: `0`.

Both tokens received identical `BLOCK_CONTINUATION` reasons:

- `predecessor_evidence_stale`;
- `governed_provenance_untraceable`;
- `mandatory_safety_context_missing`.

Those three reasons derive from one systemic missing authority input, not three independent market failures.

The standard-4h consumer requires the exact predecessor 1h memory to retain `supporting_context_json.memory_build_evidence_overlays.safety_composite_id`. Current-run 1h rows `169` and `170` contain no `memory_build_evidence_overlays` key. The B.2 safety adapter therefore returns unknown/missing safety authority; the 4h continuation input maps that unknown safety state to freshness false, provenance untraceable, and mandatory safety missing.

The fail-closed safety rule is correct. The committed producer/consumer composition is defective because the first-hour output shape does not supply the exact safety/provenance binding required by the standard 4h handoff.

### What never happened

For this attempt:

- campaign `WINDOW_4H` rows: `0`;
- physical `WINDOW_4H` rows: `0`;
- 4h campaign Scheduler-work rows: `0`;
- 4h Scheduler jobs: `0`;
- 4h collection: not started;
- 4h memory: none.

`SAFE_STOP_4H_TERMINAL_INCOMPLETE` is a downstream terminal symptom of the absent 4h phase, not the primary root cause.

`HOLDER_CONTEXT_BUDGET_EXHAUSTED` observed in accounting is not the root cause.

### Post-run safety

Authoritative DB after the run:

- SHA-256: `1ec5bfe3bb3f554cae975720d9a9c7411bfc03c51628f75e76012138ca2d73d1`;
- integrity: `ok`;
- foreign-key violations: `0`;
- sidecars: none.

The read-only classification left that SHA unchanged and performed zero source calls, zero Scheduler runtime calls, and zero authoritative DB writes.

No attempt-linked rows were created in retrieval, paper decisions, paper decision audits, paper positions, trade events, paper trade audits, or paper audit reports. All downstream financial capabilities remain locked.

## Active first-four-hour policy remains unchanged

Valid activation still intends:

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

15m/1h outcome, direction, profitability, trajectory class, manipulation label, `learning_need`, scoring, ranking, confidence, weighting, and `WINDOW_5M_MICRO_EVENT` do not behavior-qualify continuation.

Hard identity, evidence quality, freshness, governed provenance, mandatory safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, DB/lease integrity, bounded resources, and one-shot authority remain fail-closed.

Do not weaken those gates to repair the integration defect.

## Current lane sequence

Completed:

1. second standard-four-hour authorization preparation — PASS;
2. independent authorization review — PASS;
3. one separately operator-started second standard-four-hour attempt — consumed once;
4. post-run forensic safety collection — PASS;
5. read-only second-attempt runtime classification — PASS;
6. runtime classification closeout — PASS with `COMMITTED_CODE_DEFECT`.

The runtime did **not** prove 4h memory.

## Current lane boundary

Immediate next lane:

`SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_SCOPE_AUDIT`

This lane is audit-only.

Allowed:

- exact Git/branch/HEAD verification;
- static inspection of the 1h producer, B.1/B.2 authority adapters, standard-4h consumer, Scheduler ownership, and relevant tests/designs;
- read-only inspection of the already-consumed attempt evidence and authoritative DB;
- exact canonical-owner and contract-mismatch classification;
- audit documentation.

Not allowed:

- repair implementation;
- weakening freshness/provenance/safety gates;
- source/provider fetching;
- Scheduler runtime;
- authoritative DB mutation;
- new memory generation;
- new authorization;
- rerun/resume/restart/successor of either consumed attempt;
- another 4h attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL.

After the audit, preserve the required sequence:

`audit/readiness -> design/specification -> implementation if approved -> bounded offline proof/test -> closeout -> fresh operational rereadiness -> only later fresh one-use authorization review`

No step authorizes the next automatically.

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

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Assistant execution rule

Preserve the V2 sequence and use minimum sufficient risk-based verification.

Do not run another standard-four-hour attempt or create another authorization until the new repair-scope audit, design, approved implementation, bounded offline proof, closeout, and fresh operational rereadiness all pass in order.
