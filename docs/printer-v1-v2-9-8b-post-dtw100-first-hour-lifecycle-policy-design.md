# Printer V1 V2-9.8B Post-DTW100 First-Hour Lifecycle Policy Design

## Verdict

```text
V2_9_8B_POST_DTW100_FIRST_HOUR_LIFECYCLE_POLICY_DESIGN_PASS
```

This design replaces outcome/learning-need-gated `WINDOW_15M -> WINDOW_1H` continuation with a standard first-hour lifecycle for every token that has been validly activated into the bounded main tracking campaign.

`WINDOW_15M` remains a required first main-memory checkpoint. It no longer decides whether a token deserves the remaining first-hour observation. `WINDOW_1H` becomes the normal first-hour horizon. Selective continuation begins only after 1h for later approved windows such as 4h.

This design does not authorize a live 1h run, fresh authorization, source fetching, Scheduler runtime, authoritative-DB mutation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors.

## 1. Baseline and reason for change

Baseline:

- repository: `Dtwosam/MoneyPrinter`
- audit baseline: `b976538d3e7a9c7c2173b8751e19eef3295c0d04`
- preceding verdict: `V2_9_8B_POST_DTW100_15M_TRAJECTORY_CLASSIFICATION_AUDIT_BLOCKED_PATH_AWARE_LEARNING_POLICY_DESIGN_REQUIRED`

The audit proved that Printer already preserves richer intra-window evidence than the single 15m outcome label exposes. A 15m outcome label is therefore not a reliable reason to terminate observation at minute 15. Stopping `NO_PUMP` or `CONSOLIDATION` tokens at 15m also biases the corpus away from delayed pumps, delayed dumps, breakouts, breakdowns, recoveries, revivals, and genuinely quiet full-hour behavior.

## 2. Adopted product rule

For every token validly activated into the bounded main lifecycle:

```text
activation
-> track from t=0
-> close/evaluate WINDOW_15M at ~t=15m
-> continue observing the same exact token/pair
-> close/evaluate WINDOW_1H at ~t=60m
-> stop at 1h unless a later separately approved selective-long-window policy continues it
```

The first-hour observation commitment is made by campaign policy at lifecycle activation. It is not earned by a 15m price/outcome label.

Therefore none of the following may decide 15m->1h observation continuation:

- `NO_PUMP`
- `CONSOLIDATION`
- pump/dump/dead/revival labels
- final 15m price direction
- a score, rank, confidence, probability, or weighted rule
- a 5m support-only event
- profitability or BUY readiness

## 3. What may still stop first-hour observation

There is no token-behavior qualification gate, but fail-closed operational stops remain mandatory. First-hour observation may stop only when the campaign can no longer continue the exact lifecycle safely or validly, including:

- campaign cancellation or terminal state;
- exact token/mint/pair/lifecycle identity mismatch;
- broken predecessor-window lineage;
- predecessor 15m window did not reach a terminal close boundary;
- broken token/pair tracking continuity;
- shared DB, lease, or integrity failure;
- Source Governor or Central Scheduler ownership/integrity failure;
- campaign or token source/Scheduler budget exhaustion;
- an explicit operator interruption/safe-stop;
- inability to create the exact bounded successor work without violating the one-shot campaign contract.

A bad market outcome is not an operational failure.

## 4. Memory-quality separation

Observation continuation and clean-memory promotion are separate concerns.

- `WINDOW_15M` is audited and stored honestly as clean/dirty/blocked according to its evidence.
- The token remains in the first-hour observation lifecycle unless an operational stop above occurs.
- `WINDOW_1H` is independently audited from its exact full first-hour evidence and may be clean/dirty/blocked.
- Dirty or blocked memory remains unavailable to retrieval/decisions.
- A dirty 15m label must never be relabelled clean merely to permit 1h tracking.
- A later 1h result must not rewrite the historical 15m result.

The implementation must not use 15m outcome direction, clean-promotion success, or token-risk semantics as a behavioral qualification test for first-hour observation. Evidence-integrity failures remain visible and may still make the resulting 1h memory dirty/blocked.

## 5. 5m support-only law

`WINDOW_5M_MICRO_EVENT` remains support-only.

It may explain intra-window events but cannot independently start, stop, or authorize the first-hour lifecycle; replace 15m or 1h; become a main outcome memory; unlock retrieval; or unlock any paper/financial capability.

## 6. Later-window selectivity remains

This amendment is only for `WINDOW_15M -> WINDOW_1H`.

`WINDOW_1H -> WINDOW_4H` remains selective and must continue to require the approved categorical continuation policy, evidence quality, exact continuity, budget, and later-lane authorization. `WINDOW_12H` and `WINDOW_24H` remain locked.

This is not an all-token/all-timeframe policy.

## 7. Implementation boundary

Minimum implementation should stay inside the existing campaign/factory architecture and must not create a parallel runner.

Primary policy owner:

- `src/printer_v1/scheduler/token_local_continuation.py`

Required behavior:

1. For exact `WINDOW_15M -> WINDOW_1H`, after common operational/identity/continuity/budget fail-closed checks pass, return `CONTINUE_TO_WINDOW_1H` without requiring `learning_need`.
2. Outcome label and 15m learning-need mapping may remain diagnostic metadata only; it has no authority to stop first-hour observation.
3. For exact `WINDOW_1H -> WINDOW_4H`, preserve the existing selective learning-need and clean-evidence gates unchanged.
4. Preserve two-token fairness, Source Governor ownership, Central Scheduler ownership, no retries/restarts/successors, and downstream locks.

The existing `operational_selective_1h.py` filename/API may remain for compatibility in this scoped repair. Historical selective-1h artifacts remain historical. Future cleanup/rename is not required for this implementation.

## 8. Focused proof

Minimum sufficient offline proof must demonstrate:

- two healthy 15m tokens both continue to 1h even when `learning_need=None`;
- a 15m token with `NO_PUMP`-equivalent no-learning-need metadata does not stop merely for that reason;
- a 15m token with consolidation-equivalent no-learning-need metadata does not stop merely for that reason;
- token-local budget exhaustion still blocks only that token;
- campaign budget, DB, lease, or integrity failure still blocks both;
- identity mismatch, cancellation/terminal state, or broken continuity still fail closed;
- `WINDOW_1H -> WINDOW_4H` with no learning need still stops at 1h;
- 5m support has no continuation authority;
- no retrieval/paper/financial rows are created.

Use focused offline/temp-DB or pure-policy tests only. No live source call, Scheduler runtime, authoritative DB write, or operational proof is allowed in this lane.

## 9. Money-usefulness contribution

This removes a learning bias at minute 15. Printer can learn the difference between early quiet behavior and later movement, early consolidation and later breakout/breakdown, early pump and later collapse, early dump and later recovery, and genuinely inactive full-hour behavior.

It also makes 15m->1h comparison structurally available for every bounded activated token instead of only the subset whose 15m label passed a heuristic continuation gate.

## 10. What this improves

- full first-hour coverage for every valid activated token;
- less outcome-label bias in the corpus;
- cleaner separation between observation policy and memory interpretation;
- simpler 15m->1h lifecycle semantics;
- continued boundedness at the current two-token campaign capacity.

## 11. What this still does not unlock

- live first-hour execution;
- a fresh one-use authorization;
- 4h automatic continuation;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper trade audits, or PnL;
- wallets, private keys, real funds, live execution;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

The separate post-DTW100 one-shot selective-1h authorization/wrapper integration blocker remains and must still be repaired before any operational first-hour proof.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Required control | Proof |
|---|---|---|
| First-hour policy accidentally becomes all-timeframe tracking | Keep 1h->4h and later transitions selective/locked | 1h->4h no-learning-need STOP test |
| More first-hour source/Scheduler spend | Re-derive exact current two-token budgets before later authorization | later authorization/readiness lane |
| Dirty 15m is silently upgraded | Keep memory quality independent from observation continuation | dirty/blocked quality assertions |
| Broken identity/continuity keeps collecting | Preserve fail-closed identity/continuity checks | focused mismatch/gap tests |
| 5m gains authority | Keep 5m support-only/non-authoritative | exclusion test |
| Old outcome labels still appear in reports | Treat them as diagnostic only for 15m->1h | focused no-learning-need continuation test |
| Historical selective docs become confusing | Add explicit active-stack superseding amendment; do not rewrite historical closeouts | static doc scan |

## 13. Closeout boundary

After design/source-stack adoption passes, implementation may modify only the minimum policy/test surfaces needed for the behavior above, run focused offline proof, and write an implementation/proof closeout.

Stop after implementation/proof closeout. Do not create authorization and do not run `WINDOW_15M` or `WINDOW_1H` operationally.
