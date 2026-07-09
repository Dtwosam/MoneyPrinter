# Printer V1 V2-2Q Discovery Fair-Chance / Selection Rotation Audit

## 1. Status

**Lane:** V2-2Q - Discovery Fair-Chance / Selection Rotation Audit
**Task type:** Audit only
**Verdict:** `AUDIT_COMPLETE_WITH_BLOCKERS`

V2-2J and V2-3 remain paused.

This audit evaluates whether eligible Solana memecoin candidates receive a fair
chance to enter Printer's candidate universe and whether selection can rotate
across candidates without repeatedly choosing the same small token set.

The audit does not authorize implementation, source fetching, database
mutation, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, paper
positions, trades, paper audits, or PnL.

## 2. Source Stack Checked

The following documents were read together as the active source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`

The requested anchors were confirmed:

- V2-2K audit: `2cd7940`
- V2-2P.3 verification: `be70309`

## 3. Files Inspected

Static inspection covered the current discovery, selection, lifecycle, and
handoff paths, including:

- `src/printer_v1/operator_cli/commands.py`
- `src/printer_v1/discovery/selection_batch.py`
- `src/printer_v1/operator_cli/lane_x6_discovery_selection_repair.py`
- `src/printer_v1/operator_cli/lane_x3_post_cycle_lifecycle.py`
- `src/printer_v1/sources/geckoterminal.py`
- discovery, selection, lifecycle, STNP, source-attribution, and controlled
  discovery tests under `tests/`
- migrations defining discovery, tracking, lifecycle, and selection-batch
  storage

No source, scheduler, runtime, memory, retrieval, paper, or trading command was
executed.

## 4. Read-Only Database Inspection

Database inspected:

- `data/printer_v1.sqlite3`

The database was opened using SQLite URI read-only mode and
`PRAGMA query_only = ON`. Only schema inspection and `SELECT` statements were
used.

Tables inspected:

- `printer_discovery_candidates`
- `printer_tokens`
- `printer_pairs`
- `printer_tracking_queue`
- `sqlite_master`

The persistent database does not currently contain:

- `printer_selection_batches`
- `printer_selection_batch_items`

Those absent tables make historical selected-token and selected-pair repetition
unmeasurable in the current persistent database.

### 4.1 Discovery Population

| Measure | Result |
|---|---:|
| Discovery candidates | 15 |
| Distinct token IDs | 15 |
| Distinct pair IDs | 15 |
| Repeated persisted token IDs | 0 |
| Repeated persisted pair IDs | 0 |
| Tracking queue rows | 15 |
| Distinct queued token IDs | 15 |
| Distinct queued pair IDs | 15 |
| Repeated queued token IDs | 0 |
| Repeated queued pair IDs | 0 |
| Queue status `QUEUED` | 15 |

The discovery rows span five dates from 2026-06-21 through 2026-07-07. This
shows multiple collection dates, but not a persistent selection-rotation
history.

### 4.2 Source and Channel Concentration

| Source | Candidates | Share |
|---|---:|---:|
| DexScreener | 9 | 60.0% |
| GeckoTerminal | 6 | 40.0% |

| Source channel | Candidates | Share |
|---|---:|---:|
| Missing/null channel | 8 | 53.3% |
| `GECKOTERMINAL_NEW_POOL` | 3 | 20.0% |
| `GECKOTERMINAL_TRENDING_POOL` | 3 | 20.0% |
| `DEXSCREENER_SEARCH` | 1 | 6.7% |

Two GeckoTerminal responses each contributed three persisted candidates. Each
DexScreener source response contributed one persisted candidate. More than half
of the persistent discovery rows lack an explicit source channel, which limits
historical channel-diversity auditing.

### 4.3 Tracking-Lane Concentration

| Tracking action/lane | Rows |
|---|---:|
| `TRACK_NORMAL` | 8 |
| `TRACK_FAST` | 6 |
| `WATCH_ONLY` | 1 |

All 15 queue rows are still `QUEUED`. No persistent cooldown, archive, or
reopen population is available to prove lifecycle rotation in operation.

### 4.4 Same-Token / New-Pair Evidence

The pair table contains tokens associated with multiple pairs:

- one token with three pairs
- two tokens with two pairs each

This confirms that same-token/new-pair handling is a real requirement. It does
not prove that the normal discovery path currently distinguishes migration,
revival, distinct evidence, pair drift, and duplicate recycling correctly at
every handoff.

## 5. Current Pipeline Map

The audited path is:

1. A bounded, governed source request obtains candidates.
2. Source-specific data is normalized and assigned source/channel trace.
3. Within-response duplicate and STNP checks reject unsafe ambiguity.
4. Existing token and pair sets are loaded from persistent storage.
5. The normal discovery persistence gate rejects candidates whose mint or pair
   already exists.
6. New candidates are persisted and handed to the tracking queue.
7. Separate selection logic builds candidate metadata, validates category
   quotas, and can persist selection batches where the selection schema exists.
8. Lifecycle helpers can classify cooldown, archive, and explicit reopen
   eligibility.

The path has strong duplicate safety, but it does not yet form a complete
fair-chance rotation system across time.

## 6. Discovery Fairness Findings

### 6.1 What Is Safe

- Within-response duplicate pair and duplicate mint checks exist.
- Unresolved within-response STNP is rejected.
- Migration-class channels can retain explicitly classified same-token/new-pair
  evidence rather than treating every multi-pair case as safe.
- Persistent discovery currently contains no repeated token or pair IDs.
- Source name, source response, and newer source-channel attribution are
  available for audit.
- Candidate limits and source-request limits keep discovery bounded.

### 6.2 Fair-Chance Blockers

The normal discovery path rejects a candidate if either its mint or pair already
exists. This prevents duplicate persistence, but it is broader than a
fair-resurfacing policy:

- an existing mint with genuinely new evidence can be blocked permanently
- an existing mint on a valid new migration or revival pair can be blocked
  before lifecycle-aware selection
- a previously weak or archived candidate cannot re-enter merely because its
  evidence became fresh and meaningfully different
- duplicate safety and temporal resurfacing are not separated into distinct
  policies

This means Printer currently avoids repeated persisted candidates partly by
excluding them forever, not by giving eligible candidates a bounded cooldown
and evidence-aware second chance.

### 6.3 Source and Query Repetition Risk

The current READY paths have concentration risks:

- GeckoTerminal uses fixed page-one new-pool and trending-pool endpoints.
- DexScreener uses a stable default search query (`pump`) unless the operator
  supplies another query.
- no cursor, page rotation, or bounded query rotation policy was found
- PumpPortal and PumpSwap remain outside the proven READY set

These paths can repeatedly return the same top-page or query-matching tokens.
The persistent database's hard existing-mint rejection hides that repetition
after fetch rather than demonstrating broader candidate-universe coverage.

## 7. Selection Repetition Findings

### 7.1 Within-Batch Safety

Selection quota validation prevents duplicate token mints and duplicate pair
addresses inside one proposed batch. Category constraints also improve
within-batch memory-diet breadth:

- Group A is capped
- D1 and WATCH_ONLY representation is required for larger batches
- trap/failure representation is required when Group A is present
- broader B/D category representation is required

These are categorical gates, not scores, rankings, confidence values, or
weighted logic.

### 7.2 Cross-Batch Repetition Blocker

No current selection gate was found that queries recent selection-batch history
and blocks or cools down a token/pair selected in a recent batch.

Selection-batch records include `selected_at` and token/pair identity where the
schema is present, but the current batch builder does not use that history as a
cross-batch rotation gate. Therefore:

- the same token/pair can be eligible in successive batches
- recent selection does not create a proven exclusion period
- evidence freshness is not compared with the prior selected evidence before
  reselection
- source/channel concentration is reported but not capped across batches

The persistent database has no selection-batch tables, so actual historical
repeat counts cannot be measured there. The absence of measured repetition is
not evidence that cross-batch repetition is prevented.

## 8. Dedupe and STNP Findings

| Control | Finding |
|---|---|
| Duplicate mint within one response | Safely rejected |
| Duplicate pair within one response | Safely rejected |
| Duplicate mint/pair within one selection batch | Safely rejected |
| Existing mint or pair in normal discovery | Rejected broadly |
| Unresolved STNP | Rejected |
| Pair drift / duplicate recycle | Rejected by classification helper |
| Migration / revival / distinct evidence | Can be allowed by helper |
| Cross-batch repeated selection | Not prevented by a proven history gate |
| Evidence-aware resurfacing | Missing from normal discovery persistence |

The main design tension is that useful resurfacing is over-blocked during
discovery while recent reselection is under-controlled during batch assembly.

## 9. Cooldown, Archive, and Reopen Findings

Lifecycle helpers exist for:

- entering cooldown
- entering archive
- checking cooldown/archive eligibility
- explicit reopen with a reason

The Lane X6 repair path reads the latest tracking state and excludes candidates
whose latest state is cooldown or archived unless an allowed reopen state is
present.

However:

- the normal discovery persistence gate rejects existing mints before a
  complete evidence-aware reopen path can operate
- all 15 persistent tracking rows are `QUEUED`
- no persistent cooldown, archive, or reopen sample proves practical rotation
- lifecycle state is not a substitute for recent selection-batch cooldown
- no cross-batch selection-history gate was found

The controls are useful building blocks, but their integration is incomplete.

## 10. Rotation and Diversity Findings

### 10.1 Category Diversity

Quota logic can prevent a large batch from consisting only of winners or fast
pumps. The audit-only WATCH_ONLY/D1 handoff also allows negative-learning
examples to satisfy categorical representation without active tracking.

This is already safer than a winner-only candidate diet.

### 10.2 Temporal Rotation

The Lane X6 repair path:

1. orders recent candidates newest first
2. deduplicates by mint
3. deduplicates by pair
4. applies STNP and lifecycle gates
5. takes the first bounded candidates

This deterministic newest-first approach is bounded and auditable, but it is
not a temporal rotation policy. It does not consider:

- recently selected token/pair history
- time since last selection
- evidence identity change since last selection
- source/channel exposure in recent batches
- category exposure in recent batches
- fair aging of eligible candidates that repeatedly fall just below the cap

### 10.3 Negative-Learning Access

Low, dead, trap, failed-pump, and WATCH_ONLY candidates can be represented by
current categorical and audit-only mechanisms when such candidates reach the
pool. Their fair access is still limited by:

- narrow live source/channel coverage
- fixed page/query behavior
- broad existing-mint exclusion
- absent temporal selection rotation
- incomplete historical source-channel data

## 11. Is Same-Token Repetition Prevented?

**Discovery persistence:** Yes, but too broadly. Existing mints and pairs are
rejected, including potentially useful resurfacing.

**Within one selection batch:** Yes. Duplicate mints and pairs are rejected.

**Across selection batches:** No proven prevention. There is no recent-selection
history gate in the audited batch-building path.

**Same-token/new-pair:** Classification helpers are safe, but the normal
existing-mint discovery gate can block useful classified cases before they
receive a fair handoff.

The overall answer is therefore: **partially, with contradictory controls**.

## 12. What Is Already Safe

- Source Governor boundaries remain intact.
- Discovery is bounded by candidate and request limits.
- Direct ungoverned source loops were not found in the audited path.
- Duplicate and unresolved STNP cases are rejected conservatively.
- Selection quotas are categorical and audit-visible.
- WATCH_ONLY and D1 can remain audit-only instead of becoming active tracking.
- Pair-age context does not substitute for token age.
- The 5m window remains support-only.
- No audited control unlocks memory, retrieval, paper decisions, BUY/SELL/HOLD,
  positions, trades, paper audits, or PnL.

## 13. What Is Missing

1. A bounded evidence-aware resurfacing policy that distinguishes exact
   duplicate recycling from meaningful new evidence.
2. A recent-selection cooldown keyed by token and pair across batches.
3. A requirement that resurfacing carry fresh evidence identity or an explicit
   migration/revival/reopen reason.
4. A fair-aging rule for eligible candidates repeatedly omitted by a bounded
   newest-first cap.
5. Recent-batch source/channel exposure controls.
6. Recent-batch category exposure controls.
7. Persistent selection-batch schema readiness in the current database.
8. A measured proof using multiple batches over time.
9. Better historical source-channel completeness.
10. Broader READY source/channel coverage without paid dependencies.

## 14. Source Governor and Central Scheduler Boundaries

The audited discovery command builds bounded source request plans and routes
source work through governed paths. No direct engine API loop was identified.

Future rotation work must preserve:

- Source Governor approval and recording for every source request
- Central Scheduler control where scheduled execution is involved
- bounded candidate, request, and runtime limits
- token snapshots and protected monitoring priorities
- no page scraping or unbounded provider rotation
- no paid API requirement

Fair chance must be implemented as candidate eligibility and bounded rotation,
not as uncontrolled expansion of source calls.

## 15. Money-Usefulness Contribution

A correct rotation policy would improve the usefulness of Printer's memory diet
by:

- reducing repeated exposure to the same popular tokens
- allowing meaningfully changed tokens to re-enter after evidence-based
  cooldown
- retaining losers, traps, failed pumps, dead tokens, and revivals for
  negative-learning coverage
- reducing source and category concentration
- separating duplicate recycling from legitimate market evolution
- making later clean-memory comparisons less biased toward whichever provider
  or page happened to dominate recent discovery

This contribution is upstream evidence quality only. It is not a trading
signal, token ranking, confidence measure, or BUY probability.

## 16. What V2-2Q Improves

V2-2Q provides an explicit map of the current repetition controls and identifies
the central mismatch:

- discovery prevents recurrence by permanent identity exclusion
- selection prevents duplicates only within one batch
- neither side provides a complete evidence-aware, time-aware rotation policy

The audit also establishes persistent baseline counts for future proof:

- 15 unique discovery candidates
- 15 unique queued token/pair records
- no persistent selection-batch history
- 60% DexScreener and 40% GeckoTerminal source concentration
- 53.3% historical null source-channel attribution
- no exercised cooldown/archive/reopen population

## 17. What V2-2Q Does Not Unlock

This audit does not unlock or authorize:

- implementation
- source fetching
- scheduler or runtime execution
- database mutation
- snapshots or memory windows
- clean-memory creation
- retrieval
- paper decisions
- BUY, SELL, or HOLD
- paper positions
- trades
- paper trade audits
- PnL
- wallet, private-key, signing, or live-execution logic
- paid APIs
- scoring, ranking, confidence, or weighted logic
- embeddings or vectors

V2-2J and V2-3 remain paused.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Effect |
|---|---|
| Permanent existing-mint rejection | Blocks legitimate revival, migration, or distinct-evidence resurfacing |
| No cross-batch selection cooldown | Allows the same token/pair to be selected repeatedly |
| No evidence-change comparison | Cannot distinguish useful resurfacing from recycling at selection time |
| Fixed page-one/query discovery | Can repeatedly expose the same source-defined token set |
| Newest-first bounded cap | Can starve eligible candidates just below the cap |
| No recent source/channel rotation | One provider or channel can dominate successive batches |
| No recent category rotation | Quota-valid batches can still repeat the same categories over time |
| Selection tables absent in persistent DB | Selection repetition cannot be measured or enforced there |
| All tracking rows still queued | Cooldown/archive/reopen behavior is not operationally proven |
| Historical null source channels | Weakens provider/channel concentration analysis |
| Narrow READY source set | Limits fair access for dead, revival, migration, and negative-learning cases |

## 19. Audit Verdict

`AUDIT_COMPLETE_WITH_BLOCKERS`

Printer has conservative duplicate and STNP protection and useful within-batch
category quotas. Those controls protect integrity, but they do not yet guarantee
fair discovery access or time-aware selection rotation.

Current discovery can permanently suppress meaningful resurfacing, while
current selection can repeat candidates across batches because recent selection
history is not an eligibility gate. The persistent database also lacks the
selection-batch tables needed to measure or enforce cross-batch behavior.

The system is safe against obvious duplicate intake, but it is not yet close
enough to a fair-chance, rotation-aware discovery/selection standard.

## 20. Recommended Next Lane

**V2-2R - Discovery Fair-Chance / Selection Rotation Design**

This should be a design-only lane before implementation. It should define:

- exact duplicate versus distinct-evidence resurfacing semantics
- token-level and pair-level recent-selection cooldown
- explicit migration, revival, and reopen eligibility
- evidence freshness and evidence identity requirements
- bounded candidate fair-aging
- recent source/channel exposure limits
- recent category exposure limits
- selection-history schema/readiness requirements
- audit fields and proof metrics
- preservation of STNP, audit-only WATCH_ONLY/D1, Source Governor, Central
  Scheduler, and all downstream locks

V2-2R must not introduce token scores, ranks, confidence percentages, weighted
selection, live trading, or downstream activation.
