# Printer V1 V2-9.8B Post-DTW100 15m Trajectory Classification Audit

## Verdict

```text
V2_9_8B_POST_DTW100_15M_TRAJECTORY_CLASSIFICATION_AUDIT_BLOCKED_PATH_AWARE_LEARNING_POLICY_DESIGN_REQUIRED
```

Printer already captures materially more intra-window evidence than the final `outcome_label` exposes. The current 15m memory path preserves ordered snapshots and derives open/high/low/close, net change, maximum run-up, and maximum drawdown. However, the current outcome classifier and selective 15m→1h learning-need bridge do not consistently use that full path.

The result is a real learning-policy distortion: two radically different observed trajectories can become the same `NO_PUMP` label, and `NO_PUMP` / `CONSOLIDATION` are then categorically stopped at 15m. A clean token that materially collapses and recovers can therefore be denied 1h continuation even though Printer retained the evidence proving that the path was not ordinary.

This is an audit only. It does not change production code, migrations, tests, runtime, source work, Scheduler state, the authoritative DB, memory, authorization, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

---

## 1. Baseline

- Repository: `Dtwosam/MoneyPrinter`
- Starting commit: `13aa70b3bc91def711a64d8f46ed6fa0b98dc488`
- Starting closeout: `Close post-DTW100 selective 1h rereadiness audit`
- Audit branch: `agent/v2-9-8b-post-dtw100-15m-trajectory-classification-audit`
- Branch created exactly from the starting commit.

The preceding rereadiness verdict remains factually valid: selective 1h still also needs the post-DTW100 one-use authorization/wrapper integration design before any operational proof.

---

## 2. Roadmap and product-law check

The active V2 roadmap targets reliable paper-only learning efficiency and requires audit → design → implementation → bounded proof/test → closeout for major capability changes.

The active learning diet explicitly includes winners, losers, traps, dead tokens, fake pumps, revivals, liquidity/volume/transaction transitions, and **consolidation**. The adopted trajectory product law also says a main memory must not be reduced to opening price versus closing price; ordered intra-window behavior is first-class memory where evidence supports it.

Therefore this audit is roadmap-aligned. Quiet/negative/consolidating behavior is learning evidence, not disposable evidence. At the same time, V2-9.7C deliberately made longer-window tracking selective, so the correct repair is **not** automatically “continue every token to 1h.” The required design must preserve selectivity while making the learning need path-aware.

---

## 3. What Printer already captures correctly

### 3.1 Main-window snapshot path

The episode assembler loads every persisted snapshot for the exact token + pair inside the memory-window timestamps and orders them by `captured_at` and id.

The authoritative cadence contract currently requires:

- `WINDOW_15M / TRACK_FAST`: nominal 60s spacing, minimum 16 snapshots;
- `WINDOW_15M / TRACK_NORMAL`: nominal 120s spacing, minimum 9 snapshots;
- missed/excessive gaps become DIRTY/BLOCKED rather than silently interpolated.

So Printer is designed to observe the path during 15m, subject to the finite cadence. It cannot know a price move that occurs entirely between observed snapshots, but it does preserve the governed observations it actually captures.

### 3.2 Episode persistence

For the observed snapshots, the memory engine derives and persists:

- `price_start`
- `price_high`
- `price_low`
- `price_end`
- `price_change_percent`
- `max_runup_percent`
- `max_drawdown_percent`

It also persists the ordered episode-to-snapshot links. Therefore a captured `100 → 20 → 100` path is not lost from the episode evidence merely because start and end are equal.

Classification: `CAPTURE_AND_BASE_PATH_PERSISTENCE_PRESENT`.

---

## 4. Where full-trajectory implementation remains incomplete

Printer has approved trajectory/checkpoint objects with categorical phases such as expansion, pullback, consolidation, breakdown, reclaim, collapse, survival, and revival. Those objects also model ordered observations, peaks, reversals, and visible evidence gaps.

But the V2-9.7D.5A closeout explicitly states those objects are **in-memory representations only** and that persistence/operational integration remained outside that lane. Static source usage remains consistent with that boundary: the trajectory builders are used by representation/manipulation/opportunity object layers and tests, not by the current `memory.assembler` operational episode-build path.

The current episode assembler therefore does not presently produce the adopted full ordered phase/reversal representation as part of each operational main memory.

Classification: `PRODUCT_LAW_PARTIALLY_IMPLEMENTED`.

This is broader than the immediate 1h blocker, so a minimum repair should not expand into a full trajectory-engine rewrite unless a design proves that breadth is necessary.

---

## 5. Current outcome classifier is not sufficiently path-aware

`memory/outcomes.py` calculates high/low/run-up/drawdown, but its outcome rule order still lets end-state thresholds dominate important negative excursions.

Deterministic examples from the current rule order:

| Observed prices | Current summary outcome | Audit assessment |
|---|---|---|
| `100 → 100 → 100` | `NO_PUMP` | reasonable quiet case |
| `100 → 250 → 100` | `ROUND_TRIP` | material positive excursion preserved |
| `100 → 20 → 100` | `NO_PUMP` | material -80% collapse/recovery hidden by label |
| `100 → 20 → 105` | `NO_PUMP` | material collapse/recovery hidden by label |
| `100 → 20 → 110` | `REVIVAL` | revival recognized |
| `100 → 20 → 114` | `REVIVAL` | revival recognized |
| `100 → 20 → 120` | `SHORT_TERM_PUMP` | recovery path collapses into end gain |
| `100 → 20 → 150` | `SUSTAINED_PUMP` | recovery path collapses into end gain |

The asymmetry is structural:

- positive excursion followed by return can become `ROUND_TRIP`;
- negative excursion followed by return to roughly the opening price can become `NO_PUMP`;
- the `REVIVAL` check occurs after the near-flat and pump checks, leaving it a narrow classification band rather than a general collapse→recovery path description.

Therefore `NO_PUMP` currently cannot safely be interpreted as “nothing meaningful happened.”

Classification: `PATH_CLASSIFICATION_DEFECT`.

---

## 6. Consolidation is also too coarse for continuation

The main outcome classifier can emit `CONSOLIDATION` when the near-flat ending state is accompanied by `MICRO_PUMP_TO_CONSOLIDATION` support evidence.

That means `CONSOLIDATION` can represent a path that had an earlier expansion and then settled. It is not necessarily the same thing as a genuinely quiet sideways token.

Yet the selective 1h policy currently places both:

```text
CONSOLIDATION
NO_PUMP
```

in `_STOP_OUTCOMES`, giving them no unresolved 15m→1h learning need.

This loses the distinction between at least:

1. genuinely quiet/no-material-move behavior; and
2. material movement followed by consolidation/recovery back near the opening level.

The active learning roadmap explicitly includes consolidation, so a blanket “all consolidation is ordinary and finished at 15m” rule is not sufficiently justified by the current evidence semantics.

Classification: `CONTINUATION_LEARNING_NEED_COARSENING`.

---

## 7. Rich evidence does not currently rescue the 1h decision

The selective 1h bridge derives its learning need from the stored **single `outcome_label`**.

Current behavior:

- `CONSOLIDATION` / `NO_PUMP` → no learning need → STOP;
- named transition outcomes → `TRANSITION`;
- other accepted mappings may receive a categorical coverage path depending on owner;
- dirty/missing/ineligible evidence blocks.

It does not use the predecessor episode's persisted:

- max drawdown;
- max run-up;
- ordered snapshot path;
- chart recovery/path labels;
- ordered phase/reversal objects;
- complete set of micro-events

to decide whether a nominal `NO_PUMP` or `CONSOLIDATION` actually contains a material unresolved transition.

Therefore the fact that Printer captured `100 → 20 → 100` does not currently prevent the `NO_PUMP` stop rule from ending observation at 15m.

Classification: `PATH_EVIDENCE_NOT_CONSUMED_BY_CONTINUATION_POLICY`.

---

## 8. Micro-event narrowing

The episode evidence collector retains all micro-event rows within the main window in chronological order.

However, the current outcome classifier is invoked with only the **first** micro-event object when one or more are present. The complete list remains in supporting context, but later micro-events cannot directly affect this outcome-classification call.

This can further compress a multi-event 15m trajectory into one end label.

`WINDOW_5M_MICRO_EVENT` must remain support-only and must not independently unlock continuation. A future design may consume exact-linked support events as evidence for a main-window categorical learning need, but authority must remain with the clean 15m main window.

Classification: `MULTI_EVENT_CLASSIFICATION_COVERAGE_GAP`.

---

## 9. Outcome vocabulary drift requiring design review

The static Phase-14 `EpisodeOutcomeLabel` vocabulary includes `DEAD_TOKEN` and does not include `SLOW_BLEED`, while current operational continuation mappings contain `DEAD` and `SLOW_BLEED`.

Historical operational fixtures/closeouts do contain those operational labels, so this audit does not declare either vocabulary invalid. It does establish that the next design must identify the **authoritative operational 15m outcome layer** and prevent accidental cross-layer aliases from silently changing continuation behavior.

Classification: `CATEGORICAL_VOCABULARY_ALIGNMENT_GAP`.

---

## 10. Root cause

The root problem is **not missing observation**.

The root problem is the handoff:

```text
ordered governed snapshots
        ↓
rich path evidence retained
        ↓
coarse single outcome label
        ↓
outcome-label-only learning need
        ↓
15m STOP / 1h CONTINUE
```

The current system preserves useful facts and then throws too much of their meaning away at the classification/continuation boundary.

---

## 11. Safest next design requirement

Before another selective 1h proof, add a scoped design lane for **path-aware 15m outcome / continuation learning-need semantics**.

The design should:

1. preserve the existing governed snapshot cadence and quality gates;
2. distinguish genuinely quiet `NO_PUMP` from material excursion/recovery that happens to close near the opening price;
3. distinguish quiet consolidation from material expansion→consolidation where later transition remains useful to learn;
4. use ordered clean main-window evidence, not profitability prediction;
5. reuse existing categorical trajectory/outcome vocabulary where adequate and introduce no score/rank/confidence/weighting;
6. decide whether the minimal safe implementation belongs in outcome classification, learning-need derivation, or both;
7. keep `WINDOW_5M_MICRO_EVENT` support-only and non-authoritative;
8. define how multiple exact-linked micro-events may support the main-window interpretation without independently causing continuation;
9. reconcile/explicitly separate `DEAD` vs `DEAD_TOKEN`, `SLOW_BLEED`, and related outcome vocabularies;
10. preserve selective resource use rather than converting every token into a mandatory 1h continuation;
11. keep 4h/12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL locked.

A good design outcome is likely a categorical question closer to:

```text
Does this clean 15m path contain an unresolved behavior transition worth
observing through 1h?
```

rather than:

```text
Is the final outcome label in a short allow/stop list?
```

The design must choose the exact implementation contract; this audit does not.

---

## 12. Minimum sufficient proof required later

A later implementation should be proven with focused offline fixtures at minimum for:

- quiet flat path: `100 → 100 → 100`;
- bounded ordinary noise near opening;
- pump→return: `100 → 250 → 100`;
- collapse→return: `100 → 20 → 100`;
- collapse→partial recovery;
- collapse→strong recovery;
- expansion→consolidation;
- genuinely quiet consolidation;
- multiple exact-linked micro-events inside one 15m window;
- dirty/gapped/stale path blocks rather than infers;
- 5m support cannot create continuation authority by itself;
- continuation remains categorical, token-local, bounded, Scheduler-owned and Source-Governed;
- locked downstream tables remain unchanged.

No broad regression suite is required for the design lane. Focused classifier/assembler/continuation tests plus directly affected quality/cadence tests are the minimum sufficient implementation proof. Broader verification remains for the later major operational closeout/pre-live proof checkpoint.

---

## 13. Relationship to the existing authorization blocker

The post-DTW100 one-shot selective-1h authorization/wrapper blocker remains real and unresolved.

This audit adds a second pre-proof requirement: the policy deciding **which clean 15m tokens continue** must be corrected/proven before a fresh one-use selective-1h authorization is frozen and consumed.

Recommended order:

1. path-aware learning-policy design;
2. minimal implementation;
3. focused offline proof + closeout;
4. return to the already-identified selective-1h one-shot authorization/wrapper integration design;
5. authorization implementation/proof/readiness;
6. fresh exact-HEAD one-use authorization preparation/review;
7. exactly one selective-1h operational proof.

This avoids authorizing a live 1h proof around a continuation policy already known to distort some observed trajectories.

---

## 14. Money-usefulness contribution

This audit protects corpus quality from a subtle bias: Printer should not learn only obvious early movers while treating dramatic recovery/consolidation paths as ordinary simply because their 15m closing price is near the opening price.

Path-aware continuation can improve learning about collapses, recoveries, delayed breakouts, failed recoveries, consolidation breaks, and survival without requiring every token to consume a full hour of source budget.

---

## 15. What this improves / what it does not unlock

### Improves

- identifies the exact capture→classification→continuation information loss;
- preserves the distinction between evidence collection and evidence interpretation;
- prevents a premature “just continue every token” repair;
- gives the next design a bounded, testable target.

### Still does not unlock

- any production code change;
- source fetching or discovery;
- Scheduler/runtime execution;
- DB mutation or memory generation;
- 15m or 1h operational proof;
- 4h/12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions/trades/audits/PnL;
- wallets, keys, real funds, live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

---

## 16. Verification

Audit verification was static and read-only:

- current Git baseline inspected;
- active roadmap/product-law documents inspected;
- current snapshot cadence inspected;
- episode assembler/recorder inspected;
- outcome classifier inspected;
- trajectory-object implementation boundary inspected;
- selective 1h learning-need bridge inspected;
- operational selective tests inspected;
- deterministic edge-case truth table derived from the committed rule order;
- no DB opened or mutated;
- no runtime/source/Scheduler command executed;
- no tests were run because no implementation changed and static source was sufficient to establish the classification defect.

---

## 17. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Why it matters | Required control |
|---|---|---|
| Fix becomes “track everything for 1h” | defeats selective memory-growth efficiency | retain categorical unresolved-learning-need gate |
| Endpoint bias remains | rich path still collapses to close-only semantics | explicit path-sensitive fixtures |
| Full trajectory rewrite expands scope | delays the immediate 1h blocker unnecessarily | choose minimum implementation that restores correct learning need |
| New labels become hidden scoring | violates V1 policy | fixed categorical vocabulary only |
| 5m gains continuation authority | violates permanent support-only rule | main 15m remains the authority |
| Sparse cadence overclaims unseen moves | invents path between snapshots | preserve gap visibility; never interpolate missing evidence |
| Multi-event handling cherry-picks | hindsight bias | deterministic ordered-event policy |
| Vocabulary aliases drift | different owners disagree on same behavior | canonical mapping/explicit layer separation |
| Quiet tokens always continue | wastes source/Scheduler budget | allow genuine no-unresolved-learning-need STOP |
| Dramatic recovery stops as NO_PUMP | loses valuable memory | path-aware classification/learning-need proof |

---

## Closeout

```text
V2_9_8B_POST_DTW100_15M_TRAJECTORY_CLASSIFICATION_AUDIT_BLOCKED_PATH_AWARE_LEARNING_POLICY_DESIGN_REQUIRED
```

Stop here. Do not implement, authorize, or run selective 1h from this audit lane.