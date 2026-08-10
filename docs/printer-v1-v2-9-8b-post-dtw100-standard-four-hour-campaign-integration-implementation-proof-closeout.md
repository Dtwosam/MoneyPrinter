# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Campaign Integration Implementation / Proof Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CAMPAIGN_INTEGRATION_IMPLEMENTATION_PROOF_PASS`

The adopted Standard Four-Hour Lifecycle Policy and Campaign-Integration Design is now implemented through the required first-four-hour standard campaign boundary and has passed one exact-HEAD, bounded, offline integration proof.

This PASS closes the **implementation/proof** checkpoint only. It does not activate real `WINDOW_4H` collection and does not authorize source fetching, runtime execution, a fresh operational authorization, `WINDOW_12H` / `WINDOW_24H`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, live execution, or real funds.

## Controlling design and implementation anchors

Adopted design:

- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`

Key durable implementation/proof anchors:

- B1 exact clean 1h -> campaign-owned 4h handoff production: `ba58873...`; B1 closeout: `ad9da64...`;
- B2 exact two-token 4h planning + stage-scoped Scheduler ownership production: `2492e480...`; B2 closeout: `7c73aad...`;
- 4h collection execution/state/accounting/fairness production: `dc525000dd574c6b4f288a7962c8543bdb5272db`; closeout: `27d331579c3329fd7bedf8e5d7f36fe9f2c9990f`;
- 4h close/memory/terminal reconciliation production: `51a9cf3649420577503bcc7678e94f666733eb25`; closeout: `786950e9b98677e97f55996507ae1f2145c8eb5e`;
- overall integration reconciliation audit: `a67ffc7fca5ce4bd503b74675804ab405459f81b`.

The overall integration proof ran on exact reconciliation HEAD `a67ffc7fca5ce4bd503b74675804ab405459f81b`; no production edit was made by the proof.

## Overall exact-HEAD proof

Disposable proof PR:

- PR #151;
- closed unmerged;
- read-only proof runner only;
- no patcher or production mutation path.

Workflow evidence:

- run `31390840985`;
- job `93461946225`;
- exact checkout: `a67ffc7fca5ce4bd503b74675804ab405459f81b`;
- compile: PASS;
- integration suite: **110/110 tests PASS** in 85.051 seconds;
- derived-ceiling / no-later-window / capability-lock checks: PASS;
- `git diff --check`: PASS.

The proof used no provider call, no source transport, no operational Scheduler/runtime execution, no authoritative DB mutation, and no real memory-generation run.

## Integrated contract proven

### Standard observation policy

The proof preserved the standard bounded observation law:

- otherwise-valid `WINDOW_15M -> WINDOW_1H` continuation is not selected by price outcome or a `learning_need` preference;
- otherwise-valid `WINDOW_1H -> WINDOW_4H` continuation is likewise standard through the first-four-hour horizon;
- hard identity, evidence, safety, continuity, campaign and resource gates remain authoritative;
- token budget remains a hard gate;
- `WINDOW_5M_MICRO_EVENT` remains support-only and cannot authorize a main continuation.

### Exact two-token capacity

The proof independently asserted the policy-derived campaign ceilings:

| Tracking lanes | Request ceiling | Scheduler-row ceiling |
|---|---:|---:|
| FAST + FAST | 230 | 210 |
| FAST + NORMAL | 182 | 162 |
| NORMAL + NORMAL | 134 | 114 |

For all three shapes:

- automatic retries remain `0`;
- endpoint rotation remains disabled;
- real collection remains disabled.

### Campaign-owned handoff and planning

The integrated proof covered:

- exact campaign/run/cycle/token-slot/token/pair 1h -> 4h handoff;
- exact predecessor/root lifecycle linkage;
- atomic/idempotent handoff and conflict rollback;
- policy-derived FAST/NORMAL 4h cadence planning;
- exact V2 stage-scoped Scheduler ownership;
- B2 atomic rollback on ownership/projection failure;
- mixed FAST/NORMAL standard planning of 61 + 31 long work rows.

### Collection execution state, accounting and fairness

The proof covered:

- `PLANNED -> COLLECTING -> CLOSE_PENDING` truth from real Scheduler-claim semantics in fixtures;
- exact long-window lifecycle reservation observations;
- close priority;
- categorical two-token fairness;
- token-local failure isolation;
- shared safe-stop reconciliation;
- canonical Scheduler/campaign-work state synchronization;
- no scoring, ranking, confidence, weighted priority, or private scheduling loop.

### Physical 4h memory and terminal reconciliation

The proof covered:

- exact full current-run 4h outcome path;
- exclusion of foreign/historical snapshots;
- known outcome persisted before E2Q/Lane Q/E2Z;
- first clean 4h creation and exact replay idempotency;
- clean, dirty and no-promotion campaign outcomes;
- exact physical memory/campaign identity checks;
- successful caller-owned transaction reconciliation;
- mixed FAST/NORMAL two-window terminal validation;
- zero active owned 4h work and zero nonterminal owned 4h windows at standard closeout;
- historical one-token 4h compatibility;
- directly affected first-hour close and full-path outcome/memory contracts.

## No automatic 12h / 24h successor

The overall proof created a fresh standard mixed FAST/NORMAL 4h plan and explicitly queried campaign windows afterward.

Result:

- `WINDOW_12H` campaign-window count: `0`;
- `WINDOW_24H` campaign-window count: `0`.

No standard 4h success path creates a later-window successor.

Real collection capability also remained disabled for:

- `WINDOW_4H` FAST;
- `WINDOW_4H` NORMAL;
- `WINDOW_12H` FAST/NORMAL;
- `WINDOW_24H` FAST/NORMAL.

## Money-usefulness contribution

Printer can now represent the first four hours of an otherwise-valid two-token campaign without selecting longer observation based on an early winner/loser outcome, while preserving exact identity, bounded resources, source accounting, fairness, failure isolation, truthful full-path outcomes, and clean/dirty/no-promotion separation.

That materially reduces behavior-conditioned sampling bias and improves the future corpus for delayed pumps, collapses, survival, revival, distribution, round trips, consolidation and liquidity deterioration.

A clean memory still requires complete clean evidence and a known promotable outcome. This PASS proves no profitability and grants no paper-trading authority.

## What this checkpoint improves

- completes the adopted standard first-four-hour implementation as one composed campaign contract;
- proves the previously isolated sub-slices remain compatible on one exact HEAD;
- derives rather than guesses the worst-case two-token resource ceilings;
- preserves one Source Governor and one Central Scheduler ownership model;
- preserves categorical fairness with no score/rank system;
- proves mixed FAST/NORMAL two-token closeout;
- preserves historical one-token and first-hour behavior;
- proves no automatic 12h/24h extension.

## What remains locked

Still locked after this PASS:

- real `WINDOW_4H` collection;
- operational standard-four-hour activation;
- any cadence-policy enablement for real 4h work;
- fresh one-use 4h authorization;
- `WINDOW_12H` / `WINDOW_24H` activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallets, private keys, signing, live execution, real funds;
- paid APIs;
- scoring, ranking, confidence percentages, weighted logic;
- embeddings or vectors.

No previous 15m authorization or historical 4h proof authorization becomes reusable because this closeout passed.

## Proof/test required before operational 4h use

The next checkpoint is **operational standard-four-hour rereadiness**, read-only only.

It must verify the current authoritative operational boundary against the now-complete implementation, including at minimum:

- exact current repository / implementation HEAD and active source stack;
- authoritative DB schema/migration compatibility for current campaign/Scheduler ownership;
- zero conflicting active work / stale authorization / stale lease assumptions;
- Source Governor and Central Scheduler operational ownership;
- worst-case two-token ceilings (`230` requests / `210` Scheduler rows) relative to current operational limits;
- current safe-stop, lease and cancellation behavior;
- current authorization contract and whether it can represent bounded standard 4h scope without silently reusing a 15m authorization;
- real 4h cadence remains locked during audit;
- no 12h/24h path;
- what activation repair/proof is required before any real source call.

A fresh operational 4h authorization must not be created during rereadiness.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two simultaneous full 4h lifecycles are materially more expensive than the historical one-continuer proof; operational ceilings must be checked against the worst-case standard campaign shape rather than a mixed or one-token example.
- The physical memory-quality path commits before later campaign reconciliation; a later campaign binding fault cannot erase physical evidence and must remain honestly reportable.
- `OUTCOME_UNKNOWN` remains intentionally non-promotable and can reduce clean-memory yield.
- Partial or ambiguous B2 ownership must continue to fail closed rather than falling back to historical one-token validation.
- A completed implementation does not prove that the current authoritative operational DB, leases, authorization artifact shape, or source budgets are ready for real 4h work.
- GitHub Actions emitted Node-runtime deprecation warnings from third-party action internals; these did not affect Printer behavior or proof results and are not a product blocker.

## Next permitted step

Begin a separate **read-only Operational Standard Four-Hour Rereadiness Audit**.

Do not enable real 4h cadence, run sources, execute Scheduler work, mutate the authoritative DB, create a fresh authorization, or begin 12h/24h work in that audit.
