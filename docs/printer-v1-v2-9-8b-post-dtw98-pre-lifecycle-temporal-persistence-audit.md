# Printer V1 — V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Audit

## Verdict

`V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_AUDIT_PASS_DESIGN_REQUIRED`

Primary blocker classification: `DESIGN_GAP`.

DTW98's durable runtime facts remain unchanged: it was a truthful pre-lifecycle `HONEST_BLOCKED` attempt under the committed behavior. This audit supersedes only the narrower conclusion that no software/design work is warranted after that honest block.

## Baseline and scope

- baseline commit: `f8c609884a44e5aeb5f7fa4623b842a4a28a0a09`
- baseline closeout: `V2_9_8B_POST_DTW98_CONSUMED_HONEST_PRE_LIFECYCLE_COVERAGE_CLOSEOUT_PASS`
- audit type: static/read-only architecture review
- no provider/source call
- no Source Governor runtime
- no Central Scheduler runtime
- no authoritative DB read or mutation by this audit
- no authorization creation
- no Printer runtime
- no memory generation

The active Printer V1 source stack and its restrictions remain binding. The Memory Factory architecture requires Source Governor ownership of source requests and Central Scheduler ownership of scheduled work; no independent polling/retry loop is permitted.

## Trigger evidence

DTW98 reached:

- unique tokens observed: `51`
- eligible reserve count: `3`
- required eligible capacity: `4`
- source operations used: `14`
- source operations remaining: `16`
- provider failures: `0`
- unavailable channels: none
- unexplored work prevented by hard ceiling: `false`
- terminal reachability reason: `ALL_REACHABLE_CANDIDATES_EVALUATED`
- first terminal cause: `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT`

The same broad shortage pattern has occurred in earlier operational work. Repetition makes it necessary to distinguish a truthful single-snapshot exhaustion result from a complete temporally persistent acquisition design.

## Finding 1 — Current persistence is inventory-persistent, not time-persistent

`run_persistent_eligible_token_supply()` loops while eligible capacity is unmet, but it exits immediately when:

- the computed maximum current-inventory round count is reached;
- no permanent inventory rows remain unevaluated;
- `_unexplored()` becomes empty; or
- no additional unique candidates are currently reachable.

Those paths set `ALL_REACHABLE_CANDIDATES_EVALUATED` or `NO_ADDITIONAL_UNIQUE_CANDIDATES_REACHABLE` and terminate the same campaign's supply acquisition.

There is no nonterminal `WAITING_FOR_ELIGIBLE_SUPPLY`/equivalent state and no scheduled future discovery refresh that lets the reachable universe change before terminal shortage classification.

## Finding 2 — A deadline contract exists but ordinary runtime does not bind it

The canonical eligible-supply function accepts `deadline_at`. Its duration check is wall-clock based and can classify `CAMPAIGN_DURATION_EXHAUSTED` / `DURATION_EXHAUSTION` when a deadline is supplied.

`build_graduated_supply()` also accepts and forwards `deadline_at` to the eligible-supply service.

However, `AuthoritativeLiveOperationalCampaignOwner.run_operational()` currently calls `build_graduated_supply(...)` before it computes the ordinary campaign `deadline`. No `deadline_at` is added to `supply_kwargs` at that supply boundary.

Only after supply returns does current code calculate:

`deadline = evaluated + timedelta(seconds=command.ceilings.duration_seconds)`

This explains why DTW98's exhaustion certificate had no usable duration horizon. The eligible-supply loop was not bound to the ordinary campaign deadline.

This omitted wiring is an integration symptom, but simply passing the later lifecycle deadline backward is not an adequate repair because the existing `1,200s` campaign/lifecycle envelope contains a `900s` main WINDOW_15M and was historically started after supply acquisition. A temporal-acquisition horizon must be specified explicitly rather than stealing required lifecycle time or silently doubling a campaign ceiling.

## Finding 3 — Original V2-9.8B.21 design does not define temporal waiting

The adopted eligible-supply design requires persistent discovery inside the same campaign while all of these remain true:

- reserve below capacity;
- lawful source operations remain;
- duration remains when a deadline is provided;
- approved channels remain usable;
- **new unique supply remains reachable**.

It therefore solved the former one-batch false-shortage defect but intentionally still stops when the currently reachable unique universe is exhausted.

The design does not specify:

- a waitable nonterminal supply state;
- a Scheduler-owned delayed refresh;
- a bounded temporal acquisition horizon after current-universe exhaustion;
- reserve revalidation after such a wait;
- terminal classification when the universe changes zero or more times during the wait horizon.

The requested behavior cannot be implemented safely from the existing specification alone. That is why `DESIGN_GAP` is the controlling classification rather than an ad-hoc code patch.

## Finding 4 — Central Scheduler already has the correct job category and delayed-job primitive

The canonical Scheduler already defines `JobKind.DISCOVERY_REFRESH`.

`enqueue_job()` accepts a future `scheduled_for`, persists a PENDING Scheduler job, and `claim_due_job()` refuses to claim before due time.

The resource governor assigns `DISCOVERY_REFRESH` its existing low-priority place after token/window work and exposes a normal next-check interval of `600s`.

`CombinedDiscoveryExecutor` already proves the claim-at-work-start pattern for discovery work:

`enqueue -> exact claim_due_job -> identity/equality checks -> discovery work RUNNING -> governed work -> terminalization`.

Therefore the temporal repair must reuse Central Scheduler ownership. The eligible-supply service must not add `sleep` polling, a private retry loop, a background thread, or another scheduler.

The exact orchestration owner and linkage for a pre-lifecycle delayed refresh must be specified in design before implementation.

## Finding 5 — Reserve revalidation support already exists

The eligible-supply service already persists reserve candidates across campaigns and enforces mandatory freshness:

- prior `ELIGIBLE_FRESH` / `ELIGIBLE_STALE` rows are loaded;
- they are marked stale before reuse;
- prior reserve mints receive revalidation focus;
- stale/rejected candidates do not count toward capacity;
- failed revalidation removes a prior eligible candidate from current capacity.

This is the correct basis for waiting: a 3-of-4 reserve may be retained as durable evidence, but no candidate may remain counted merely because it was eligible before the wait. On every later refresh opportunity, the reserve required for freeze must be revalidated under the same exact-pool, liquidity, tracking, evidence-freshness, and current-policy rules.

## Required design decisions

The next lane must specify all of the following before code changes:

1. a bounded pre-lifecycle temporal acquisition horizon distinct from the main WINDOW_15M lifecycle timing;
2. exact canonical owner of the waiting state and `DISCOVERY_REFRESH` Scheduler job;
3. exact scheduling/claim/terminalization linkage and cleanup identities;
4. refresh cadence, using existing Scheduler policy rather than an independent sleep loop;
5. zero provider operations while merely waiting;
6. normal Source-Governed accounting for each due refresh attempt;
7. mandatory reserve revalidation after each wait;
8. persistence of the same authorization, campaign, run, and cycle identities across waits;
9. no retry/restart/resume/successor semantics and no second operator authorization inside the wait loop;
10. explicit terminals for capacity met, acquisition-duration exhausted, source budget exhausted, provider/source failure, operator/safe stop, and unsafe Scheduler/DB state;
11. exhaustion-certificate fields that distinguish `CURRENT_UNIVERSE_EXHAUSTED_WAITING` from true terminal exhaustion;
12. exact interaction with campaign supervision/lease heartbeat while pre-lifecycle waiting;
13. fail-closed cleanup for pending/running discovery-refresh Scheduler rows;
14. no weakening of four-deep freeze, tracking exclusions, exact-pair requirements, liquidity floor, holder-context separation, Source Governor, or any capability lock.

## Roadmap alignment

A direct implementation now would skip the required specification step and violate Printer's audit -> design -> implementation -> bounded proof -> closeout pattern.

The compliant path is:

1. this audit;
2. temporal-persistence design/specification;
3. narrow implementation if design passes;
4. focused offline/disposable proof;
5. repair closeout;
6. fresh authoritative rereadiness;
7. only later, a new one-use authorization and independent review before any live WINDOW_15M attempt.

The already-created post-DTW98 rereadiness branch remains unused. Rereadiness is deferred until this deterministic boundary gap is resolved and closed.

## Money-usefulness contribution

This repair path addresses a repeated source of wasted one-use authorizations: Printer can already preserve candidate quality and detect a 3-of-4 shortage, but it cannot currently exploit bounded time for new supply to appear. A Scheduler-owned temporal acquisition state can improve the probability of reaching a valid four-deep memory-observation freeze without lowering evidence quality or repeatedly restarting campaigns.

## What this audit improves

- distinguishes snapshot exhaustion from temporal exhaustion;
- identifies the omitted operational deadline binding;
- identifies the existing Scheduler primitive that must own future refresh work;
- confirms reserve revalidation can be reused rather than rebuilt;
- prevents another live authorization from being spent on the same deterministic stop behavior.

## What this audit still does not unlock

It does not authorize implementation, source fetching, Scheduler runtime, authoritative DB mutation, memory generation, a new authorization, or WINDOW_15M runtime. It does not unlock WINDOW_1H/4H/12H/24H, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, private keys, real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof/test required before completion of the repair program

The later focused proof must show at minimum:

- 3-of-4 + currently exhausted universe becomes a nonterminal waiting state when lawful horizon/budget remain;
- waiting performs zero provider calls;
- one due `DISCOVERY_REFRESH` is Central-Scheduler enqueued, claimed, linked, and terminalized exactly;
- refresh source work remains Source-Governed and accounted;
- prior reserve is revalidated before it can count again;
- a newly eligible fourth identity reaches exact 2-selected + 2-alternate freeze;
- duration exhaustion terminals honestly if no fourth token appears;
- source/budget/provider failures retain their existing classifications;
- no hidden retry/restart/resume/successor/new authorization occurs;
- safe stop leaves zero active/locked Scheduler and campaign residue;
- no forbidden capability-table deltas occur.

## Functionality Risks / Setbacks / Efficiency Blockers

- A poorly chosen acquisition horizon can make one-shot commands unnecessarily long.
- Reusing the 1,200-second lifecycle duration without specification can either steal time from WINDOW_15M or silently expand the total envelope.
- A private `sleep`/poll loop would violate the Central Scheduler architecture.
- Revalidating all reserve evidence too aggressively can waste source budget; revalidation must remain domain/freshness aware.
- Leaving delayed refresh jobs after stop would create Scheduler residue and future cross-campaign interference.
- Treating waiting as retry/restart would break one-use authorization semantics.
- Raising source ceilings or weakening the four-deep/market/tracking gates to force success remains prohibited.

## Next lane

`V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Design`

Design/documentation only. No runtime, source fetching, DB mutation, authorization, or WINDOW_15M execution.