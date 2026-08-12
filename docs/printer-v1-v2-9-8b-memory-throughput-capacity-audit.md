# Printer V1 V2-9.8B Memory Throughput Capacity Audit

## Verdict

`V2_9_8B_MEMORY_THROUGHPUT_CAPACITY_AUDIT_PASS_MINIMAL_CHANGE_MULTI_CYCLE_SCALING_RECOMMENDED`

This audit finds a roadmap-aligned way to materially increase Printer's daily Solana memecoin learning throughput **without replacing the operational Memory Factory architecture**.

The recommended scaling primitive is **not** a larger monolithic token-slot set and **not** multiple independent Printer processes. It is:

> keep the existing exact two-token campaign cycle as the atomic admission/fairness unit, allow one bounded campaign/run to own several finite two-token cycles, admit those cycles gradually under the existing Central Scheduler and Source Governor, and place a separate bounded ceiling on the number of tokens still inside the 15m/1h/4h observation path.

The audit recommends an initial design target of **three concurrently active two-token cycles = six through-4h tokens**, reached through a focused `2 -> 4 -> 6` proof ladder. Six is a design/proof candidate, not an authorization. The current public operational capacity remains exactly two until a later design, implementation, bounded proof, and closeout pass.

A later `8` or `10` through-4h token proof may be considered only after the six-token boundary is measured cleanly and the extra throughput is justified. No immediate jump to the Memory Factory Guide's stable-later `20-30` total active planning range is recommended.

No source rate ceiling is raised. No retry is added. No paid API is introduced. No 12h/24h runtime is activated. No retrieval or paper capability is unlocked.

## Scope and authority

Baseline branch/commit:

- `agent/v2-9-8b-post-seventh-standard-4h-operational-rereadiness`
- `f35309b8eab291bfd6372a960b641686723328f9`

Active source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of the source stack, not its sole authority.

This lane is audit-only. It performs static repository inspection, prior-artifact review, source-contract review, arithmetic, and official external documentation review. It does not run Printer sources, mutate the authoritative database, generate memory, start Scheduler runtime, or change production capacity.

## Roadmap reconciliation

An older V2-9 bounded-4h closeout recorded a BLOCKED state after earlier transport-fragile attempts. That document is historical. The later durable final V2-9 closeout at commit `51bcfdb8a97f2457464bce4f5ec015ebb8235172` supersedes it and records:

`V2_9_FINAL_CLOSEOUT_PASS`

The final proof produced one exact clean promoted `WINDOW_4H` episode after a real 15m -> 1h -> 4h lifecycle. Therefore the build-order prerequisite that 4h proof exist before long-window readiness has been satisfied historically.

Separately, the latest two-token **operational** standard-four-hour attempt remains a safe-stop rather than a clean two-token 4h close. That operational fact is not rewritten by the historical V2-9 PASS.

V2-9.8B remains the current operational memory-growth area. This throughput audit is intentionally placed there before any implementation or long-window activation.

## User objective translated into Printer terms

The required outcome is:

- learn from materially more tokens per day;
- allow older token lifecycles to continue while later token cohorts start;
- keep the same Source Governor, Central Scheduler, ownership graph, evidence rules, exact token/pair identity, clean/dirty rules, and bounded-campaign model;
- stay inside free/public source contracts;
- avoid API/RPC rate-limit pressure;
- avoid SQLite/lease contention;
- preserve room for future retrieval, paper decisions, open paper-position monitoring, trade auditing, and other later-approved work;
- never improve row count by weakening memory quality.

The audit explicitly rejects a redesign into independent HOT/WARM/LONG engines, multiple competing campaign processes, source-specific loops, or a new trading/runtime architecture.

## Current operational boundary

The current standard-four-hour path is deliberately fixed at:

- active token capacity: `2`
- lifecycle request outer ceiling: `236`
- lifecycle requests per token after shared discovery: `117`
- lifecycle Scheduler outer ceiling: `210`
- automatic retries: `0`
- endpoint rotation: disabled
- `WINDOW_12H` / `WINDOW_24H`: locked

The exact two-token value is a proven authorization boundary, not evidence that two is the maximum capacity of the underlying architecture.

## Existing architecture that should be reused

### 1. Two-token cycle ownership is already first-class

Migration `032_campaign_ownership_schema.sql` defines:

- campaign;
- run;
- cycle;
- token slots;
- window ownership;
- Scheduler work ownership.

Each **cycle** intentionally has slot ordinals exactly `{1,2}`. The schema does not model one global campaign-wide pair of slots; token slots are keyed through `cycle_id`, `run_id`, and `campaign_id`.

`campaign_ownership.create_cycle_with_two_slots(...)` already accepts a `cycle_ordinal` and creates another exact two-slot cycle under an existing campaign/run.

This is the strongest minimal-change scaling seam found by the audit.

### 2. Campaign configuration already models a finite cycle count

`AbstractCampaignCommand` carries `CampaignCeilings.cycle_count`. Its preflight allows multiple cycle rows up to that finite ceiling while requiring every cycle to contain exactly two slots.

The current public operational mode configures `cycles=1`; that is an operational policy choice, not a schema law that the campaign may contain only one cycle.

### 3. Existing two-slot handoff should stay atomic

The current discovery handoff deliberately activates the initial two slots as two-or-none under a SAVEPOINT. A failure in the second handoff cannot leave a one-token partial activation.

That safety property should be preserved per cycle. Scaling should create another exact two-slot cycle rather than widening one atomic handoff to 5, 10, or 20 token slots.

### 4. Existing token-local lifecycle/rotation remains useful

Lifecycle reconciliation already makes terminal/cooldown/archive handling token-local and avoids damaging a healthy peer slot. Replacement eligibility is read-only after cleanup.

The scaling design should not replace those contracts. New cycles and replacements must continue to use the same exact token/mint/pair/lifecycle ownership rules.

### 5. Central Scheduler remains the only scheduling authority

The existing Scheduler is SQLite-backed and orders due work by priority/due time. The campaign fairness layer separately gives mandatory main-window closes and evidence-gap/safe-stop work precedence before ordinary token work.

Future paper monitoring is already represented at the top of Scheduler priority:

1. `OPEN_PAPER_TRADE_MONITOR`
2. `ACTIVE_EXIT_RISK_TOKEN`

Memory scaling must preserve those priorities. No memory-specific parallel scheduler is required or recommended.

### 6. Source Governor remains the only source authority

The existing Source Governor and rolling budget accounting count provider attempts globally and fail closed when the configured source ceiling is reached.

No engine-specific source budget is recommended. Multiple cycles must consume the same central source budget ledger.

### 7. SQLite source-I/O lock risk has already been repaired

V2-9.8B.20 repaired the previous lease-heartbeat lock failure by recording the governed source request, releasing the write transaction, executing network I/O without holding the SQLite writer, then recording response/failure in another short transaction.

Disposable concurrency proof passed, including repeated heartbeat renewal under concurrent writers and a genuine-lock fail-closed test.

That makes modest multi-cycle scaling materially safer than it would have been before B.20, but it does not remove the need for a bounded multi-cycle proof.

## Historical scaling evidence

### Three-token 15m proof

The historical V2-5 conservative proof safely exercised three simultaneous token lifecycles with:

- deterministic service;
- token-local isolation;
- 35 governed non-discovery requests observed;
- 25 Scheduler rows observed;
- zero active jobs after natural close;
- no persistent DB mutation because the proof was isolated.

It did not prove clean yield or current 1h/4h behavior, but it proves that core token-local source/Scheduler mechanics were not inherently limited to two tokens.

### Five-token historical runner

The historical five-token runner implemented deterministic A/B/C/D/E service and source-budget stopping. It is 15m-only and predates the current operational lifecycle, so it must **not** be reactivated as production code.

It remains useful architectural evidence that fairness and per-token isolation can scale beyond two without a new engine.

## Current per-token 4h workload arithmetic

The canonical current standard-4h budget is componentized by lane.

### TRACK_FAST

Per token through the full 4h checkpoint:

- 15m snapshots: `16`
- 1h continuation snapshots: `24`
- 4h snapshots: `61`
- total primary snapshot observations: `101`
- non-snapshot/context allowance: `16`
- total governed requests per token: `117`
- total Scheduler work per token: `105`

### TRACK_NORMAL

Per token through the full 4h checkpoint:

- 15m snapshots: `9`
- 1h continuation snapshots: `13`
- 4h snapshots: `31`
- total primary snapshot observations: `53`
- non-snapshot/context allowance: `16`
- total governed requests per token: `69`
- total Scheduler work per token: `57`

The standard campaign currently budgets two shared discovery requests for one two-token activation.

### Multi-cycle worst-case FAST projections

For conservative scaling arithmetic, assume every admitted token is FAST and reaches 4h.

| Active cycles | Active tokens | Approx lifecycle governed-request envelope | Scheduler-work envelope | Primary snapshots over ~4h |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 2 | 236 | 210 | 202 |
| 2 | 4 | 472 | 420 | 404 |
| 3 | 6 | 708 | 630 | 606 |
| 5 | 10 | 1,180 | 1,050 | 1,010 |

For rows above two tokens, the request projection applies the current per-token `117` plus two discovery requests per two-token cycle. It is audit arithmetic, not an implemented campaign ceiling.

At six all-FAST active tokens, the average primary-snapshot demand over four hours is about `2.53` requests/minute. Total governed demand averaged over the same period is about `2.95` requests/minute. Those averages are far below the current Printer source ceilings; the harder problem is **burst timing, fallback reserve, Scheduler service time, and close deadlines**, not aggregate average API volume.

## Current Printer source ceilings versus upstream documentation

The capacity design should obey Printer's internal ceilings unless a separate future source-policy lane explicitly changes them. The external numbers below are verification context only.

| Source | Current Printer ceiling | Official/public information reviewed | Audit implication |
| --- | ---: | --- | --- |
| DexScreener | 60/min | pair/token endpoints documented at 300/min | Printer's 60/min remains the operative ceiling; do not raise it for scaling |
| GeckoTerminal | 10/min | Public API documented at 30/min | Printer deliberately keeps a 3x stricter ceiling; this is the tightest important market fallback |
| CoinGecko | 20/min | keyless public tier uses dynamic IP throttling, no stable fixed public limit | keep low-volume/context use and the internal conservative ceiling; never design to an assumed external maximum |
| GoPlus | 20/min | Security API documented at 30/min | current internal ceiling has reserve; do not raise |
| Solana RPC | 30/min | Solana public mainnet docs currently list 100 requests/10s/IP, 40/10s for one method, 40 concurrent connections; limits may change and public endpoints are not production guarantees | current Printer ceiling is vastly more conservative and should remain so |
| Helius Free | 30/min | Free plan currently 10 RPC req/s, 1M monthly credits; standard RPC normally costs one credit | immediate rate is not the current bottleneck; monthly credit use still belongs in reporting |
| Jupiter Quote | 30/min | keyless access currently 0.5 RPS = 30/min | Printer already sits at the documented keyless maximum; leave explicit headroom by admission policy, not by raising the limit |

Official documentation checked during this audit:

- DexScreener API Reference: `https://docs.dexscreener.com/api/reference`
- GeckoTerminal FAQ: `https://apiguide.geckoterminal.com/faq`
- GoPlus Support / Rate Limits: `https://docs.gopluslabs.io/reference/support`
- Jupiter Plans: `https://developers.jup.ag/docs/portal/plans`
- Solana Clusters/Public RPC: `https://solana.com/docs/references/clusters`
- Helius Plans/Rate Limits/Credits: `https://www.helius.dev/docs/billing/plans`, `.../rate-limits`, `.../credits`
- CoinGecko Keyless Public API: `https://docs.coingecko.com/docs/keyless-public-api`

External provider contracts can change. They must be rechecked immediately before any implementation/proof that depends on them.

## Why six through-4h tokens is the correct first design target

Six is not claimed to be Printer's final maximum. It is the best **next capacity boundary to prove** for four reasons.

### 1. It reaches the guide's stable daily learning scale without a large jump

The current standard wall envelope is approximately 260 minutes when the pre-lifecycle acquisition allowance is included.

If every valid token occupied a through-4h observation slot for that full conservative envelope:

- 2 active tokens -> about `11` full-envelope token lifecycles/day;
- 4 active tokens -> about `22`/day;
- 6 active tokens -> about `33`/day;
- 10 active tokens -> about `55`/day.

These are capacity projections, not clean-memory guarantees.

The Memory Factory Guide's stable-later planning target is `20-40` accepted tracking tokens/day and `20-30` total active at once after staged windows are approved. Six through-4h tokens already puts full-envelope daily intake near the middle of that accepted-tracking range without immediately adopting the much larger active-token planning ceiling.

### 2. It leaves meaningful primary-source headroom

Six all-FAST tokens require only about `2.53` average primary snapshots/minute over the 4h path against Printer's DexScreener `60/min` ceiling.

### 3. It leaves a bounded GeckoTerminal fallback margin even under a bad minute

If six exact-pair DexScreener close requests all suffered a transport-class failure in one minute, at most six governed GeckoTerminal market fallbacks would be attributable to those six tokens under the current fallback shape. That remains below Printer's `10/min` Gecko ceiling.

If a two-request discovery action were also allowed in that same minute, the rough combined pressure would be `8/10`. Therefore new-cycle admission/discovery must pause around close/fallback pressure rather than treating the remaining two requests as guaranteed capacity.

At eight or ten simultaneously aligned fallback closes, the current `10/min` Gecko ceiling becomes much easier to saturate. That is why 8/10 should be later evidence-driven steps, not the first production target.

### 4. Scheduler timeout pressure remains bounded

The current DexScreener network timeout is 5 seconds. Six simultaneously due primary snapshot attempts that all consumed the full timeout would represent roughly 30 seconds of sequential network wait before considering other work. This is still a serious degraded condition, but materially safer than a ten-token 50-second timeout burst against FAST cadence and close-freshness boundaries.

This is not a promise that six cannot miss deadlines. It is why six is a reasonable boundary to prove while ten is not yet justified.

## Recommended scaling shape

### Preserve exact two-token cycles

Do not widen migration 032's slot ordinal constraint from `(1,2)` merely to increase throughput.

Do not replace the atomic two-slot activation path.

Do not create a new N-token discovery engine.

Instead, keep:

`one cycle = exactly two token slots`

and increase campaign throughput by allowing several finite cycles to remain active under one campaign/run.

### One campaign, one supervisor, one Scheduler, one Source Governor

Overlapping cycles must still have:

- one bounded campaign authorization;
- one campaign supervision/lease owner;
- one Central Scheduler;
- one Source Governor/global request accounting path;
- one authoritative DB;
- exact cycle/token/pair/window identities.

Starting independent two-token campaign processes every five minutes is rejected. It would create competing supervision, DB, source-budget, and terminal-accounting domains.

### Stagger cycle admission, not independent runtimes

The user's 12:00 / 12:05 / 12:10 concept is directionally useful. The safer contract is:

- each newly admitted cycle contains exactly two tokens;
- a cycle is admitted **no more frequently than once per five minutes in the initial scaling design**;
- five minutes is a minimum spacing, not a guarantee that another cycle will start;
- existing cycles continue unaffected when a later cycle is admitted;
- admission is skipped/deferred whenever capacity, close reserve, provider budget, Scheduler health, DB health, source cooldown, or future critical-work reserve is not clean.

The exact five-minute minimum must be revalidated in the design/proof. It is not activated by this audit.

### Admission must be backpressure-controlled

A new two-token cycle is eligible only when all of the following are true:

1. configured active through-4h token ceiling has at least two free positions;
2. campaign cycle-count and total request/Scheduler/storage/failure ceilings have room for the full projected new cycle;
3. Source Governor rolling provider counts plus worst-case admission/close reserve stay within current internal ceilings;
4. no relevant provider is in cooldown/repeated-failure pressure;
5. no mandatory memory close is inside the configured close-reserve horizon;
6. Scheduler due-work lag is inside the approved bound;
7. no SQLite lock/lease/integrity issue exists;
8. when future paper monitoring becomes active, no critical paper-monitor/exit-risk capacity is being displaced;
9. all ordinary source, identity, evidence, and selection gates pass.

Failure of admission capacity must not stop healthy existing cycles. It simply produces no new cycle at that opportunity.

## Scheduler fairness change required

This is the main code generalization the audit expects.

`two_token_fairness.py` is intentionally pure and currently rejects any active slot set whose length is not exactly two. Its selection key already encodes useful safety behavior:

- main-window close first;
- evidence-gap/safe-stop next;
- ordinary work afterward;
- lower ordinary service count before higher;
- deterministic tie breaking.

The smallest safe implementation is to generalize that pure selection policy across the active slots of several two-token cycles while preserving the current two-token function as a compatibility wrapper or exact-two specialization.

Do **not** bypass this layer and rely on multiple independent schedulers.

The cross-cycle proof must establish that:

- a due close in one cycle can preempt ordinary work in another;
- token-local failure never stops a healthy peer cycle;
- ordinary work receives deterministic fair service across cycles;
- later cycle admission cannot starve earlier cycles;
- no duplicate active job or ownership identity is created.

## Campaign ownership change required

The current ordinary public operational graph creates cycle ordinal 1 and the current public preflight configures `cycle_count=1`.

The ownership module already contains `create_cycle_with_two_slots(...)`, so the preferred implementation is a narrow, authorized **additional-cycle admission owner** that:

- runs under the same existing campaign/run and supervision;
- checks the finite cycle ceiling;
- checks active through-4h capacity;
- performs the existing discovery/selection gates;
- atomically creates exactly one new two-slot cycle/handoff;
- uses the same Scheduler/Source Governor;
- never starts a child campaign or second supervisor.

This is an extension of existing ownership, not a replacement architecture.

## Source-budget changes required

Do not change registry rate ceilings for the first scaling implementation.

Instead add/derive campaign-level projected budgets from existing per-token/per-cycle contracts:

- shared discovery allowance per admitted cycle;
- FAST/NORMAL per-token lifecycle allowance;
- Scheduler rows per token;
- fallback operation ceiling;
- storage growth ceiling;
- failure ceiling;
- provider-specific rolling headroom used as an **admission gate**.

The current global rolling budget accounting should remain authoritative for consumed attempts.

## DB/storage conclusion

SQLite is not currently identified as the first scaling bottleneck for a six-token target because:

- governed network I/O no longer holds a write transaction;
- the concurrency repair proved repeated heartbeat renewal under concurrent writers;
- seventh-run post-close integrity was `ok`, foreign keys were clean, and no sidecars/handles remained.

However, the audit cannot derive an honest per-token byte-growth ceiling from static code alone. Multi-cycle proof reporting therefore must record:

- DB bytes before/after;
- rows added by table;
- write-lock/busy events;
- heartbeat renewal latency/failures;
- Scheduler queue lag;
- sidecar/terminal cleanup.

No claim that SQLite supports 20-30 active tokens should be made before that measured proof exists.

## Long-window implications

### Existing long-window identity foundation is reusable

The disabled 12h/24h foundation already preserves token-local predecessor identity and chained continuity. The capacity design should reuse that work when V2-10/V2-11/11.7 authorize it.

### Existing disabled cadence is expensive in rows and must be reviewed before activation

Current disabled cadence policy contains:

- FAST 12h continuation: 97 expected snapshots at 300s spacing;
- NORMAL 12h: 49 at 600s;
- FAST 24h continuation: 145 at 300s;
- NORMAL 24h: 73 at 600s.

Those numbers imply substantial source/Scheduler/DB row growth per long-window survivor even though the average per-minute API rate is modest.

V2-10C explicitly exists to define long-window budgets/stops. Therefore this audit recommends **not locking a 12h/24h active-token ceiling until V2-10 confirms the long-window cadence and close-context budget**.

The long-window capacity must be calculated from the approved cadence, not from today's disabled planning constants.

### Overlap remains the intended outcome

Once selective 12h/24h is later approved, a token in an older cycle may continue its own long-window Scheduler work while later two-token cycles are admitted. Starting a new cycle must not cancel, reset, or replace an older long-window lifecycle.

This achieves the user's desired overlap while staying inside one campaign/Scheduler/Governor architecture.

## Agreed long-window continuation gate carried forward

This audit does not activate or implement the gate, but capacity planning assumes selective rather than all-token long continuation.

4h -> 12h requires:

- predecessor `WINDOW_4H = CLEAN_MEMORY`;
- liquidity >= `$3,000`;
- current rolling 1h volume >= `$500`;
- current rolling 1h transactions >= `5`;
- current rolling 24h volume >= `$5,000`;
- exact pair remains valid;
- gate evidence is fresh and clean.

12h -> 24h applies the same market/activity/evidence conditions with predecessor `WINDOW_12H = CLEAN_MEMORY`.

All are AND conditions. Missing/stale/failed evidence fails continuation closed rather than becoming zero. Failing continuation preserves earlier memory and must not erase death/revival lessons.

## Future retrieval and paper-work reserve

An exact percentage reserve such as 70/30 is **not** justified today because retrieval, paper decisions, and paper-position monitoring remain locked and therefore have no measured live workload.

The correct current design is structural:

1. keep existing critical Scheduler priorities for open paper positions/exit risk;
2. make **new memory-cycle admission the first thing throttled** when future critical work requires capacity;
3. maintain provider-specific unallocated headroom instead of consuming rate ceilings merely because they exist;
4. recalculate the memory admission ceiling before retrieval/paper activation using the then-real source contracts and paper-monitor cadence;
5. allow that future review to reduce Memory Factory intake capacity if needed.

Memory throughput is subordinate to safe monitoring of an already-open paper position once that later capability is explicitly approved.

## Initial capacity recommendation

### Current authorized state

`2` active tokens / one two-token cycle.

No change in this audit.

### First bounded proof candidate

`4` active through-4h tokens / two two-token cycles.

Purpose:

- prove additional-cycle ownership;
- prove cross-cycle fairness;
- measure Scheduler lag and SQLite pressure;
- verify source accounting and staggered close behavior.

### Second bounded proof candidate

`6` active through-4h tokens / three two-token cycles.

This is the recommended **initial operational capacity target if and only if the 4-token and 6-token proofs pass**.

### Initial daily admission ceiling candidate

`30` newly activated tracking tokens per 24h.

Why 30:

- six full-envelope through-4h positions project to roughly 33 token lifecycles/day under the conservative ~260-minute wall envelope;
- 30 stays below that theoretical boundary;
- it sits inside the guide's stable-later `20-40 accepted tracking/day` planning range;
- it prevents capacity success from becoming an incentive to flood the corpus with low-value rows.

This is a design/proof candidate, not an active limit.

### Optional later proof

`8` and then at most `10` active through-4h tokens may be reviewed only after six-token evidence shows:

- substantial Scheduler deadline headroom;
- no scaling-induced provider rate limits;
- no fallback-reserve exhaustion;
- no DB/lease contention;
- clean-memory yield remains useful;
- future-capability reserve remains credible;
- additional daily throughput has actual corpus value.

Do not jump directly from 2 to 10.

## Why not simply set 20-30 active now

The Memory Factory Guide's `20-30 max active at once` is explicitly a **stable-later planning range**, alongside staged 12h/24h activation. It is not current proof evidence.

Current blockers to adopting it as an operational number today include:

- exact-two campaign fairness currently needs cross-cycle generalization;
- current public mode creates one cycle;
- multi-cycle Scheduler lag is unmeasured;
- long-window cadence/budget is still disabled and unproven;
- storage growth under overlapping 12/24h is unmeasured;
- future paper/retrieval source workload is unmeasured;
- free/public transport reliability has already caused real long-run safe stops.

## Why not batch sources yet

DexScreener officially supports up to 30 token addresses in one token endpoint request. That may eventually improve efficiency.

It is **not recommended as part of the first capacity scaling change** because Printer's current exact-pair source request, response, transport-identity, failure-attribution, and memory-provenance model is already proven one governed operation at a time.

Batching would require a separate proof that one upstream response can be split into exact token/pair evidence without weakening request identity, source accounting, failure attribution, or clean-memory provenance.

Capacity can reach the recommended 4/6-token boundary without batching, so adding it now would be unnecessary scope.

## Minimum implementation surface implied by the audit

If the following design is later approved, expected changes should stay narrow:

1. **campaign capacity configuration**
   - finite cycle ceiling >1;
   - active through-4h token ceiling;
   - daily admission ceiling;
   - minimum cycle-admission spacing;

2. **additional-cycle admission owner**
   - reuse existing campaign/run and `create_cycle_with_two_slots` ownership;
   - reuse discovery/selection/two-slot atomic handoff;
   - no second campaign process.

3. **cross-cycle campaign fairness**
   - generalize the current pure two-token selector across active cycles;
   - preserve an exact-two compatibility path;
   - keep close/evidence-gap precedence and deterministic ordinary fairness.

4. **capacity arithmetic/reporting**
   - derive request/Scheduler/storage/failure ceilings from number of admitted cycles and lane mix;
   - report per-source peaks, rate-limit events, fallback use, Scheduler lag, DB growth, cycle/token concentration.

5. **admission backpressure**
   - no admission during unsafe close/provider/Scheduler/DB conditions;
   - future critical paper work blocks new memory admission first.

No new scheduling engine, source engine, DB, daemon, wallet, trading engine, scoring layer, or paid service is required by this recommendation.

## Bounded proof plan recommended by the audit

### Audit/design proof before runtime

Focused fixture/disposable checks only:

- existing exact-two cycle behavior remains byte/semantically compatible;
- second/third cycle ownership can be created without cross-cycle identity collision;
- forced failure creating a later cycle leaves existing cycles untouched;
- main-window close in any cycle outranks ordinary work in every cycle;
- deterministic ordinary fairness across 4 then 6 tokens;
- token-local failure isolation across cycles;
- finite campaign ceiling and daily admission ceiling fail closed;
- provider-specific projected budget gate blocks unsafe admission;
- no retrieval/financial deltas.

### Four-token bounded proof

Minimum sufficient runtime evidence:

- two cycles, four active tokens;
- minimum configured stagger between cycle admissions;
- exact source/Scheduler accounting;
- no scaling-induced rate-limit event;
- no missed clean close caused by Scheduler starvation;
- no SQLite lock/lease failure;
- safe terminal cleanup;
- locks preserved.

### Six-token bounded proof

Only after four-token PASS:

- three cycles, six active tokens;
- same checks plus close-time/fallback reserve;
- record provider peak requests/minute, not only totals;
- record max due-job lateness by job kind/token/cycle;
- record DB byte/row growth and busy/lock events;
- record clean/dirty/failed outcome distribution honestly.

### Stop condition

Stop scaling at the first boundary that produces any of:

- source-rate pressure caused by concurrency;
- close/fallback reserve exhaustion;
- Scheduler starvation or unacceptable lateness;
- DB lock/lease instability;
- cross-cycle identity contamination;
- hidden dirty evidence;
- unsafe cleanup;
- unbounded retry/restart behavior;
- any retrieval/financial delta;
- materially worse clean-memory usefulness that defeats the throughput objective.

Do not automatically proceed to the next capacity merely because a lower proof terminates successfully.

## Money-usefulness contribution

This capacity plan increases the number and diversity of real Solana memecoin trajectories Printer can learn from each day while preserving depth through the 4h checkpoint and selective later long-window learning.

It improves future money-usefulness by increasing exposure to distinct pumps, dumps, round trips, traps, deaths, liquidity decay, consolidations, and eventual revival candidates without weakening clean-memory standards or spending future paper-monitor capacity indiscriminately.

## What this audit improves

- identifies a minimal-change scaling seam already present in campaign ownership;
- separates per-cycle two-token safety from campaign-wide daily throughput;
- provides an evidence-based first capacity target rather than an arbitrary token count;
- accounts for provider limits, fallbacks, Scheduler service, SQLite behavior, daily throughput, and future paper/retrieval reserve;
- avoids premature batching, source-limit increases, retries, or parallel processes;
- flags long-window cadence as a V2-10 budget decision before active-count lock-in.

## What this audit still does not unlock

- token capacity above two;
- a second active cycle;
- any source/provider call;
- Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- another standard-four-hour authorization/attempt;
- 12h/24h runtime;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, trade audits, or PnL;
- live wallet/private keys/real funds/live execution;
- paid API dependency;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

### Multi-cycle executor does not yet exist on the public operational path

The schema/ownership seam exists, but current public runtime remains one cycle. Cross-cycle admission and fairness must be deliberately implemented and proved.

### Fairness is exact-two today

`two_token_fairness.py` intentionally rejects slot counts other than two. Generalization is required, but should preserve the existing exact-two path and selection semantics.

### Long-window capacity cannot be honestly fixed yet

Disabled 12h/24h cadence is source/Scheduler/storage heavy in row count and has not been operationally proved. V2-10C must settle its budget before a total long-window active ceiling is locked.

### Free/public network reliability remains a real external blocker

The sixth and seventh standard-four-hour operational attempts both safe-stopped on transport instability. Capacity must not be increased by adding retries or weakening freshness; degraded network health should reduce/stop new admissions instead.

### Future paper/retrieval workload is projected, not measured

The Scheduler already prioritizes open paper monitoring, but exact future provider consumption cannot be measured before those lanes exist. Capacity must be recalibrated before those capabilities activate.

### Daily row count is not success

The guide explicitly prefers a small number of well-audited clean memories over many dirty records. Daily token admission must remain subordinate to clean-memory yield and corpus diversity.

## Final recommendation

Lock the **design direction**, not the capacity in production:

1. keep exactly two token slots per cycle;
2. scale one bounded campaign by admitting multiple finite two-token cycles;
3. keep one supervisor, one Central Scheduler, one Source Governor, one DB;
4. initially prove 4 active tokens, then 6;
5. use six as the first operational capacity target only after both proofs pass;
6. use a candidate daily admission ceiling of 30 tracked tokens/day;
7. allow a new cycle no more frequently than once per five minutes initially, with admission always conditional on resource/close/provider health;
8. preserve all current source ceilings and zero-retry policy;
9. do not lock total 12h/24h active capacity until V2-10C approves cadence/budgets;
10. when retrieval/paper lanes later approach activation, re-audit shared provider/Scheduler headroom and reduce memory admissions if necessary;
11. consider 8/10 through-4h tokens only as later proof targets after six proves substantial real headroom;
12. do not redesign Printer into multiple memory engines or independent concurrent campaign processes.

## Closeout state

Audit result:

`PASS`

Implementation readiness:

`READY_FOR_SEPARATE_CAPACITY_SCALING_DESIGN__NOT_READY_FOR_RUNTIME`

The next roadmap-compliant step, if this recommendation is adopted, is a **design/specification lane** that turns the multi-cycle 4/6-token plan into exact contracts, affected-file scope, derived ceilings, admission guards, focused tests, bounded proof criteria, and rollback/stop conditions before any implementation.