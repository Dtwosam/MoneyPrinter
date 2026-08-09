# Printer V1 V2-9.8B Post-DTW100 First-Hour Lifecycle Policy Design Closeout

## Verdict

```text
V2_9_8B_POST_DTW100_FIRST_HOUR_LIFECYCLE_POLICY_DESIGN_AND_SOURCE_STACK_ADOPTION_PASS
```

## Baseline and commits

- Audit baseline: `b976538d3e7a9c7c2173b8751e19eef3295c0d04`
- Design branch: `agent/v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design`
- Design commit: `04668c7204e0d56f1df7b56dfcd1eaa8d50be921`
- Assistant/source-stack anchor adoption commit: `d034b8b9cdaf34b103af7533e05d420bbdf372f4`

## Adopted rule

Every token validly activated into the bounded main tracking lifecycle is committed to observation through the first hour. `WINDOW_15M` remains the first main-memory checkpoint, but its outcome/learning-need label no longer qualifies or disqualifies the token for the remaining first-hour observation.

`NO_PUMP`, `CONSOLIDATION`, pump/dump/dead/revival labels, final 15m direction, profitability, scoring/ranking/confidence/weighting, and `WINDOW_5M_MICRO_EVENT` have no 15m->1h continuation authority.

Fail-closed operational validity remains mandatory: exact identity/pair/lifecycle lineage, closed 15m boundary, continuity, campaign state, cancellation/terminal state, Source Governor/Central Scheduler ownership, DB/lease/integrity health, bounded resources, and one-shot execution authority.

Memory quality remains separate from observation. Continuing collection cannot turn dirty/blocked 15m evidence into clean memory. `WINDOW_1H` is independently audited.

Selectivity begins after 1h. `WINDOW_1H -> WINDOW_4H` remains selective; 12h/24h remain locked.

## Source-stack handling

The current GitHub `AGENTS.md` and active repository documentation had advanced beyond the uploaded copies available in this chat. To avoid overwriting newer repository guidance with stale uploads, this lane did not replace those larger files from the uploads.

Instead, the current repository assistant alignment anchor—already referenced by `AGENTS.md` and explicitly subordinate to the full source stack—was updated to record the new post-DTW100 policy and controlling design. Its own authority statement remains unchanged: the V2 document is the active memory-growth build order, not the sole source of truth, and later committed audits/designs/closeouts control current lane position.

Historical selective-1h documents remain historical evidence and are not rewritten.

## Money-usefulness contribution

The new policy removes minute-15 outcome bias so Printer can learn delayed pumps, delayed dumps, consolidation breaks, recoveries, revivals, and genuinely quiet full-hour behavior from every valid activated token.

## What this improves

- standard first-hour coverage after activation;
- separation of observation from outcome classification;
- reduced winner/early-mover learning bias;
- preserved bounded two-token architecture;
- preserved later-window selectivity.

## What this does not unlock

No live source work, Scheduler runtime, authoritative DB mutation, operational 15m/1h run, fresh authorization, 4h+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, real funds, paid APIs, scoring/ranking/confidence/weighting, embeddings, or vectors were unlocked.

The separate post-DTW100 one-use first-hour authorization/wrapper integration blocker remains.

## Proof required next

Implementation must be test-first and minimal. Focused offline proof must show 15m->1h no longer requires a learning need, while common fail-closed operational controls and 1h->4h selectivity remain intact.

## Functionality Risks / Setbacks / Efficiency Blockers

- First-hour source/Scheduler spend increases to the bounded two-token worst case; exact post-DTW100 ceilings must be re-derived before later authorization.
- Historical names such as `selective_1h` may remain in compatibility surfaces; they must not restore outcome-gated 15m->1h semantics.
- Memory quality must not be weakened to achieve full-hour observation.
- No live proof may occur until the separate one-use authorization/wrapper integration sequence passes.

## Next lane

```text
V2-9.8B Post-DTW100 Standard First-Hour Lifecycle Policy Implementation + Focused Offline Proof
```

Stop before any authorization or operational run.
