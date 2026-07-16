# Printer V1 V2-9.4.4 Evidence-Boundary and Memory-Quality Semantics Design

## Verdict

`V2_9_4_4_EVIDENCE_MEMORY_DESIGN_READY`

Lane: `V2-9.4.4 - Evidence-boundary and memory-quality semantics design`

Static audit/design only. No test, source, runtime, or DB command was run. No
implementation started. Preflight passed: HEAD exactly `f197a49`, tracked tree
clean, no proof runtime, no one-proof lock.

The governing spec already states the rule the code violates. The Memory Factory
guide is explicit: **"Clean memory is evidence quality plus outcome clarity, not
price performance"**, "A window must not become clean just because the token
pumped", and the anti-bias rule **"No winner-only memory"** requires storing
"winners, losers, traps, dead tokens, wrong avoids, and wrong waits". Attempt 6
produced the inverse failure: a fully evidenced loser was discarded as dirty.
This design corrects the code to the spec; it does not loosen the spec.

## 1. Current defect map

### Defect A — market outcome is encoded as evidence quality (Q1)

`src/printer_v1/chart_volatility/classifier.py`:

- `chart_context_blocks_clean_memory` (lines 190-197) returns `True` when
  `classify_volatility(...) == VOLATILITY_EXTREME` **or**
  `classify_candle_path(...) == PATH_ROUND_TRIP`. Both are *price-path facts*,
  not evidence-integrity facts.
- `classify_chart_memory_gate` (lines 200-217) computes payload `quality`
  first, then at lines 213-214 returns `CHART_CONTEXT_DO_NOT_TRAIN` for those
  outcomes — **the same label** it returns at lines 205-206 for a genuinely
  failed/dirty source. A payload whose quality is `CHART_CONTEXT_CLEAN` can
  therefore exit as `DO_NOT_TRAIN`.

The conflation then propagates:

- `src/printer_v1/memory/quality.py` line 45-46 maps
  `chart_memory_gate_label == "CHART_CONTEXT_DO_NOT_TRAIN"` to
  `REJECT_DIRTY_CHART_CONTEXT` — a reason that asserts the chart context was
  *dirty* when it was clean and merely negative;
- `classify_memory_quality` lines 92-98: any such reason (not stale/conflicting)
  → `DIRTY_MEMORY`;
- `src/printer_v1/context_evidence/window_15m.py` line 505 excludes
  `CHART_CONTEXT_DO_NOT_TRAIN` from `chart_clean`, emitting the generic
  `CHART_OR_VOLATILITY_NOT_CLEAN` blocker (line 510);
- `src/printer_v1/chart_volatility/lookup.py` lines 51-53 independently treat
  `PATH_ROUND_TRIP` as memory-blocking.

Attempt 6 is the proof: 61/61 snapshots, zero misses, clean cadence, exact
continuity, successful forced close, budgets within scope — and
`DIRTY_MEMORY` / `do_not_train=1` **solely because the price round-tripped**.
The audit's own read-only recomputation confirmed the corrected 1053-1113 set
still yields `PATH_ROUND_TRIP`, i.e. the outcome was real and the evidence was
sound. That is precisely the "winner-only memory" bias the spec forbids.

`VOLATILITY_EXTREME` is the same class of defect: extreme volatility is a market
fact, not a data fault.

### Defect B — boundary resolution ignores the current-run ledger (Q4 target)

`src/printer_v1/context_evidence/window_15m.py` lines 288-302:

```
SELECT * FROM printer_token_snapshots
WHERE token_id = ? AND pair_id = ?
  AND datetime(captured_at) >= datetime(window_start)
  AND datetime(captured_at) <= datetime(window_end)
```

- Selection is a **wall-clock scan scoped to token+pair**, not the run ledger.
- `snapshot_start_id` / `snapshot_end_id` *are* passed in but are used only
  post-hoc at line 302 (`exact_bounds`) to raise `SNAPSHOT_BOUNDARY_MISMATCH`
  (line 314) — never to select rows.
- Inclusive `>=` admitted predecessor snapshot 1052 captured exactly at
  `window_start`; strict `<=` excluded closing snapshot 1113 captured 3.660 s
  after the logical deadline. The count coincidentally stayed 61, so a
  count-only check passed while the **set** was wrong (1052-1112, not
  1053-1113). Count checks are structurally insufficient here.

### Defect C — the logical deadline is used as the evidence cutoff

The same module passes `target_time=window_end` (lines 330, 349, 369, 377, 435)
into `_broad_context` (line 158: `WHERE captured_at <= ?`) and the exact-target
safety/quote lookups (lines 199, 233). Closing GoPlus safety
(`18:14:04.817838Z`) and Jupiter exit quote (`18:14:05.307071Z`) were captured
*during governed close work*, after the deadline, and were filtered out — even
though both rows exist on the exact closing snapshot 1113 and are fresh,
`TARGET_MATCH`, `COMPLETE`, `CLEAN_DATA`, with clean governed traces. This
produced `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE` (line 409) and
`NO_VALID_EXACT_TARGET_EXIT_QUOTE_EVIDENCE` (line 445) as **false negatives**.

Root cause: one value (`window_end`) is serving two distinct concepts — the
immutable *logical window deadline* and the *approved closing-evidence cutoff*.
The approved allowance already exists and is unused here:
`SnapshotCadencePolicy.closing_clean_late_seconds = 60`
(`src/printer_v1/snapshots/cadence_policy.py` line 104). Attempt 6's 3.660 s
lateness was inside it.

### Defect D — generic blockers mask their real cause

`CHART_OR_VOLATILITY_NOT_CLEAN` and `FLOW_DIRECTION_OR_PRESSURE_NOT_CLEAN` were
emitted when direction/pressure were in fact known and the true failure was the
boundary set. Generic reasons increase forensic cost and hide defects.

### Rules that are correct today (Q2)

These already mark evidence dirty for the right reason and must be preserved:

- `memory/quality.py`: `evaluate_snapshot_coverage_gate` (too few snapshots;
  missing `price_usd`/`liquidity_usd`); `evaluate_source_quality_gate`
  (`STALE`/`CONFLICTING`/`DIRTY_DATA`/`MISSING_CRITICAL_DATA`/`DO_NOT_TRAIN`);
  `evaluate_realism_gate` (profit claimed without realistic entry *and* exit;
  `UNREALISTIC_PROFIT`); `classify_memory_quality` incomplete-coverage and
  `REJECT_5M_ONLY_WINDOW` rules.
- `evaluate_context_quality_gate` for genuine unsafety/staleness/conflict:
  `SAFETY_UNSAFE`, `SAFETY_DO_NOT_USE_FOR_MEMORY`, `SAFETY_CONTEXT_STALE`,
  `SAFETY_CONTEXT_CONFLICTING`, `REALISM_CONTEXT_BLOCKED`, market/chain-heat
  stale/conflicting.
- `classify_chart_payload_quality` lines 158-187 (source status/quality,
  staleness, required fields) — a correct quality axis.
- `safety/composite.py`: GoPlus mandatory
  (`GOPLUS_MANDATORY_SAFETY_SOURCE_NOT_USABLE`), holder
  `HOLDER_CONCENTRATION_SOURCE_CONFLICT`, exact-pair-only LP-lock danger,
  provenance-incomplete blocking.
- Lane Q cadence/gap blocking; E2Q dirty on `DIRTY_DATA`/failed sources;
  `SNAPSHOT_BOUNDARY_MISMATCH` *as a concept* (its detection is right; its
  input set is wrong).
- `trading_flow/classifier.py` `TRADING_FLOW_CONTEXT_PARTIAL` for missing
  `buy_volume_5m` / `sell_volume_5m` / `unique_wallets_5m` — an honest provider
  limitation that must stay honest.
- `classify_flow_memory_gate` line 233: `FLOW_WASH_LIKE` → `DO_NOT_TRAIN`
  **stays**. Wash-like trading attacks *evidence authenticity* (reported volume
  does not reflect real participation), not price performance. It is an
  integrity signal, not an outcome signal.

## 2. Approved evidence-quality / outcome / relevance contract (Q3)

Three axes, independently computed, never collapsed:

| Axis | Question | Vocabulary | Status |
| --- | --- | --- | --- |
| **Evidence quality** | Can this record be trusted? | `CLEAN_MEMORY`, `PARTIAL_MEMORY`, `DIRTY_MEMORY`, `AUDIT_ONLY_MEMORY`, `DO_NOT_TRAIN_MEMORY` | active |
| **Market outcome** | What actually happened? | `EpisodeOutcomeLabel` (existing): `NO_PUMP`, `FAKE_PUMP`, `SHORT_TERM_PUMP`, `SUSTAINED_PUMP`, `EXTENDED_PUMP`, `CONSOLIDATION`, `DUMP`, `PUMP_AND_DUMP`, `ROUND_TRIP`, `REVIVAL`, `DEAD_TOKEN`, `REALISTIC_PAPER_PROFIT`, `REALISTIC_CAPITAL_PROTECTION`, `UNREALISTIC_PROFIT`, `MISSED_UPSIDE`, `OUTCOME_UNKNOWN` | active |
| **Future relevance** | What should a future setup like this do? | `BUY`, `SELL`, `HOLD`, `WAIT`, `AVOID`, `NO_ACTION` | **LOCKED — design only, not implemented** |

Binding rules:

1. **Evidence quality is a function of evidence only.** Inputs: coverage, gaps,
   required fields, source status/quality, staleness, conflict, provenance,
   target/identity match, safety availability, realism-when-profit-claimed,
   authenticity (wash-like). Price path, direction, magnitude, and volatility
   are **never** inputs.
2. **Market outcome is a function of price/liquidity/flow facts only.** It never
   changes evidence quality. `ROUND_TRIP`, `DUMP`, `PUMP_AND_DUMP`,
   `DEAD_TOKEN` are outcomes to be recorded truthfully and kept.
3. **A fully evidenced negative outcome is `CLEAN_MEMORY`.** A dump, reversal,
   round trip, rug, failed breakout, or no-exit outcome with complete, fresh,
   provenance-clean, exactly-bounded evidence is clean and retrieval-eligible
   (when retrieval is later unlocked).
4. **`DIRTY_MEMORY` is reserved for unreliable or incomplete evidence.**
   Never for disliked outcomes.
5. **Outcome clarity is still required.** `OUTCOME_UNKNOWN` remains
   `AUDIT_ONLY_MEMORY` (existing line 88-89): unclear ≠ negative.
6. **Realism gate unchanged.** Profit claims still require realistic entry and
   exit; `UNREALISTIC_PROFIT` stays `AUDIT_ONLY_MEMORY`.
7. **No missing-data gate is weakened to manufacture clean memory.** Partial
   flow stays partial.

### Vocabulary gaps and one governance conflict

- `EpisodeOutcomeLabel` lacks `RUG`, `FAILED_BREAKOUT`, `SURVIVAL`, `NO_EXIT`,
  `REVERSAL`. These are **additive string values** in an unconstrained TEXT
  column (see §5) and may be added when their derivation rules are specified.
  They must not be inferred loosely; `RUG` in particular requires an explicit
  liquidity/authority evidence rule, not a price threshold.
- **Conflict flagged, not resolved:** the task's relevance axis includes
  `DO_NOT_CHASE`, but `AGENTS.md` fixes the decision vocabulary at `BUY`,
  `SELL`, `HOLD`, `WAIT`, `AVOID`, `NO_ACTION` (lines 79-89). Adding
  `DO_NOT_CHASE` would change a locked V1 rule. This design therefore maps the
  intent onto the approved vocabulary (`AVOID` / `WAIT`) and does **not**
  introduce a new decision label. Changing the decision vocabulary requires an
  explicit operator-approved AGENTS.md lane.

## 3. Exact 4h boundary contract (Q4)

The resolver must satisfy all seven clauses:

1. **Ledger-exact selection.** Select snapshots by
   `id BETWEEN snapshot_start_id AND snapshot_end_id` for the exact
   `token_id`/`pair_id`, sourced from the current run's ledger step rows —
   never a wall-clock scan. `captured_at` becomes an ordering/reporting field,
   not a selector.
2. **Predecessor exclusion.** The 1h predecessor snapshot (id <
   `snapshot_start_id`, e.g. 1052) is outside the set by construction, even when
   its `captured_at` equals `window_start_at`.
3. **Future/unrelated exclusion.** Any snapshot with id >
   `snapshot_end_id`, or belonging to another run/token/pair, is excluded by
   construction.
4. **Logical deadline preserved.** `window_end_at` remains the immutable
   `1h close + 10,800 s` deadline for window identity, duration, drift, and
   cadence evaluation. It is **not** reused as an evidence cutoff.
5. **Separate approved closing cutoff.** Introduce
   `closing_evidence_cutoff_at = window_end_at + policy.closing_clean_late_seconds`
   (existing field, FAST/NORMAL 4h = 60 s). Closing evidence is accepted only
   when `window_end_at <= captured_at <= closing_evidence_cutoff_at`, and only
   when bound to the exact closing snapshot id. Evidence later than the cutoff
   is rejected as stale. The cutoff never extends the window, the cadence
   evaluation, or the deadline-drift calculation.
6. **Exact closing evidence attachment.** Safety composite and entry/exit quote
   evidence must bind to `snapshot_end_id` exactly, be `TARGET_MATCH`,
   `COMPLETE`/`CLEAN_DATA`, and carry a clean governed source trace. Evidence
   attached to any other snapshot is rejected.
7. **Fail closed with a specific reason.** Stale, unrelated, mismatched, or
   absent evidence blocks. Blockers must name the true cause
   (`CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF`,
   `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER`,
   `CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT`), replacing the generic
   `CHART_OR_VOLATILITY_NOT_CLEAN` / `FLOW_DIRECTION_OR_PRESSURE_NOT_CLEAN`
   masks. `SNAPSHOT_BOUNDARY_MISMATCH` remains, but as a genuine assertion over
   a ledger-selected set.

Under this contract Attempt 6's three misleading blockers disappear as false
negatives, the corrected 1053-1113 set is used, and the outcome remains a
truthful `ROUND_TRIP` — now `CLEAN_MEMORY` rather than `DIRTY_MEMORY`.

## 4. Affected modules (Q5)

| Module | Change |
| --- | --- |
| `src/printer_v1/chart_volatility/classifier.py` | Remove outcome facts from the memory gate: delete `chart_context_blocks_clean_memory`'s `VOLATILITY_EXTREME`/`PATH_ROUND_TRIP` clauses (lines 190-197) and the gate branch at 213-214. Gate becomes a pure function of payload quality. |
| `src/printer_v1/chart_volatility/lookup.py` | Drop `PATH_ROUND_TRIP` as a memory-blocking condition (lines 51-53). |
| `src/printer_v1/memory/quality.py` | `REJECT_DIRTY_CHART_CONTEXT` fires only on genuine chart-evidence faults. Confirm no outcome label maps to a rejection reason. |
| `src/printer_v1/context_evidence/window_15m.py` | Ledger-exact snapshot selection; separate `closing_evidence_cutoff_at` from `window_end_at`; exact closing safety/quote attachment; specific blockers; `chart_clean` (line 505) no longer excludes outcome-driven `DO_NOT_TRAIN`. |
| `src/printer_v1/snapshots/cadence_policy.py` | Read-only consumer of `closing_clean_late_seconds`; no policy value changes. |
| `src/printer_v1/operator_cli/e2q_memory_window_audit.py` | Verify only: dirty must derive from evidence faults, never outcome. |
| `src/printer_v1/operator_cli/lane_q_15m_window_integrity_guard.py` | Verify only: cadence/gap blocking unchanged. |
| `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py` | Verify only: promotion follows the corrected quality axis; no new unlock. |
| `src/printer_v1/trading_flow/classifier.py` | **No change.** Partial stays partial; `FLOW_WASH_LIKE` stays `DO_NOT_TRAIN` (authenticity). |
| `src/printer_v1/memory/contracts.py` | Optional, later: additive outcome values once their derivation rules are approved. |

## 5. Migration assessment

**No migration is required.**

- `outcome_label`, `memory_quality_label`, `rejection_reasons_json` were added
  as **plain `TEXT` with no `CHECK`** (`migrations/014_episode_memory_engine.sql`
  lines 2-4), so additive outcome values need no schema change.
- `memory_status` has a fixed `CHECK (... IN ('CLEAN_MEMORY','PARTIAL_MEMORY',
  'DIRTY_MEMORY','DO_NOT_TRAIN','AUDIT_ONLY'))`
  (`migrations/001_database_foundation.sql` line 173). The repair only moves a
  window between **existing** allowed values (`DIRTY_MEMORY` → `CLEAN_MEMORY`);
  no new status is introduced.
- `do_not_train` stays `INTEGER 0/1`.
- The boundary repair changes a `SELECT` predicate and adds an in-memory cutoff
  parameter — no stored column.
- The **future-relevance axis is deliberately not persisted** in this lane. A
  new persisted relevance column *would* require a migration; because relevance
  is decision-domain and locked, it stays design-only, keeping the repair
  migration-free.

If implementation discovers a genuine need for a new persisted column, the lane
must stop `BLOCKED` rather than add a migration silently.

## 6. Focused fixture matrix

Temporary isolated DBs and fixtures only; no live sources.

| # | Fixture | Expected |
| --- | --- | --- |
| 1 | Fully evidenced 100% round trip, complete ledger set | `CLEAN_MEMORY`, `outcome=ROUND_TRIP`, `do_not_train=0` |
| 2 | Fully evidenced dump / pump-and-dump | `CLEAN_MEMORY`, truthful negative outcome |
| 3 | Extreme volatility, evidence clean | `CLEAN_MEMORY`, volatility label preserved |
| 4 | Missing `price_usd`/`liquidity_usd` in one snapshot | `DIRTY_MEMORY` (unchanged) |
| 5 | Stale / conflicting source | `AUDIT_ONLY_MEMORY` (unchanged) |
| 6 | Failed mandatory GoPlus | blocked; never relabeled safe (unchanged) |
| 7 | `OUTCOME_UNKNOWN` | `AUDIT_ONLY_MEMORY` (unchanged) |
| 8 | Profit claimed without realistic entry+exit | `AUDIT_ONLY_MEMORY` (unchanged) |
| 9 | `FLOW_WASH_LIKE` | `DO_NOT_TRAIN` (unchanged, authenticity) |
| 10 | Partial flow (missing 5m split volume/wallets) | honestly partial; never silently cleaned |
| 11 | Predecessor snapshot at exactly `window_start_at` | excluded; set = ledger ids only |
| 12 | Closing snapshot 3.66 s late (inside 60 s allowance) | included; boundary intact |
| 13 | Closing snapshot 61 s late (outside allowance) | rejected; `CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF` |
| 14 | Future/unrelated snapshot after `snapshot_end_id` | excluded |
| 15 | Wrong-count-but-right-count decoy (1052-1112 vs 1053-1113) | ledger set wins; count-only check insufficient |
| 16 | Closing safety/quote on exact snapshot, captured post-deadline within allowance | attached |
| 17 | Safety/quote attached to a different snapshot | rejected, specific blocker |
| 18 | Deadline/drift/cadence values | unchanged by the cutoff |
| 19 | Zero retrieval / decision / position / trade / audit / PnL deltas | all zero |
| 20 | Attempt 6 replay of ids 1053-1113 | `CLEAN_MEMORY`, `ROUND_TRIP`, three false blockers gone |

## 7. Smallest implementation sequence

1. **Split the chart gate.** Make `classify_chart_memory_gate` a pure
   evidence-quality function; delete the outcome clauses; keep
   `classify_candle_path` / `classify_volatility` as outcome labels. Fixtures
   1-3, 9-10.
2. **Purge outcome from the memory-quality gate.** Ensure no `EpisodeOutcomeLabel`
   or path/volatility label reaches a `MemoryRejectionReasonLabel`. Fixtures 4-8.
3. **Ledger-exact selection.** Select by `snapshot_start_id..snapshot_end_id`;
   keep `SNAPSHOT_BOUNDARY_MISMATCH` as a genuine assertion. Fixtures 11, 14, 15.
4. **Separate the closing cutoff.** Add `closing_evidence_cutoff_at` from
   `closing_clean_late_seconds`; keep `window_end_at` for identity/duration/drift.
   Fixtures 12, 13, 18.
5. **Exact closing evidence attachment + specific blockers.** Fixtures 16, 17, 20.
6. **Verify E2Q / Lane Q / Lane K** consume the corrected axes without new
   unlocks. Fixture 19.

Steps 1-2 and 3-5 are independently landable; each is a separate reviewable
change with its own fixtures.

## 8. Money-usefulness contribution

This repair is the difference between a corpus that learns from losses and one
that only remembers winners. Today a perfect 10,800-second record of a token
that round-tripped to zero is thrown away as "dirty" — the single most
capital-protective lesson available, discarded because the price ended badly.
Fixing this converts Attempt 6's already-paid four hours of collection into a
usable clean record, and makes every future dump, rug, and failed breakout a
retained lesson rather than wasted work. The boundary repair additionally stops
the resolver from silently trading a valid closing snapshot for a predecessor —
a defect that a count-only check cannot see and that would quietly corrupt
future evidence sets.

No clean memory is created by this document.

## 9. What improves

- Fully evidenced negative outcomes become clean, retrieval-eligible records
  (when retrieval is later unlocked), satisfying "No winner-only memory".
- `DIRTY_MEMORY` regains a single, honest meaning: untrustworthy evidence.
- 4h context resolution becomes identity-exact rather than time-approximate.
- The logical deadline and the approved closing allowance stop fighting.
- Blockers name their real cause, cutting forensic cost.
- Attempt 6's accepted runtime evidence becomes reusable under a corrected
  resolver.

## 10. What remains locked

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`,
`WINDOW_24H`, and active memory growth all remain locked. The future-relevance
axis is specified but **not implemented**. `WINDOW_5M_MICRO_EVENT` stays
support-only. Safety, liquidity, provenance, realism, and missing-data gates are
unchanged or strengthened, never weakened. No Attempt 7 and no V2-10.

## 11. Proof required

Implementation lanes must show, on temporary isolated DBs with fixtures only:

- fixtures 1-20 above passing;
- a fully evidenced round trip reaching `CLEAN_MEMORY` with `ROUND_TRIP`
  preserved and `do_not_train=0`;
- every unchanged dirty rule still firing (4-9);
- ledger-exact sets, predecessor/future exclusion, and the count-decoy case;
- cadence, continuity, duration, and deadline-drift values unchanged;
- zero retrieval/decision/position/trade/audit/PnL deltas;
- persistent DB hash unchanged; `git diff --check`; Python compilation;
- no migration added.

A live proof is **not** required to validate this design and is not authorized
here. Whether Attempt 6's stored report can be re-derived or must be re-run is
an operator decision for a later lane.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

1. **Correctness risk (highest).** Removing outcome clauses from a *memory gate*
   must not accidentally remove a genuine evidence check. `VOLATILITY_EXTREME`
   and `PATH_ROUND_TRIP` are outcomes; `FLOW_WASH_LIKE` is authenticity and must
   stay. Steps 1-2 must be reviewed against fixtures 4-9 specifically.
2. **This does not make Attempt 6's token good.** It makes a truthful `ROUND_TRIP`
   record clean. Any future decision layer must still treat that outcome as a
   loss lesson; clean means trustworthy, not favourable.
3. **`DO_NOT_CHASE` conflicts with the locked AGENTS.md decision vocabulary.**
   Not adopted here. Requires an explicit operator-approved lane.
4. **`RUG` / `FAILED_BREAKOUT` / `NO_EXIT` / `SURVIVAL` / `REVERSAL` need
   derivation rules before use.** Adding labels without evidence rules would
   invent facts; `RUG` especially must not become a price threshold.
5. **DexScreener still cannot satisfy the full flow-field contract.** Partial
   flow will persist until a separate operator-approved provider-contract lane
   resolves it. This design explicitly refuses to derive the missing fields.
6. **Historic dirty rows are not rewritten.** Windows already marked dirty by the
   outcome defect stay as they are unless a separate, explicitly approved
   re-derivation lane is authorized. No backfill is proposed.
7. **Count-only boundary checks proved insufficient.** Any future check must
   compare id sets, not lengths.
8. **Three provider modules named in the Attempt 6 audit remain unauthored**
   (marked planned in the Solana Builder README), so upstream contract claims
   remain `UNKNOWN_REQUIRES_RESEARCH` and cannot back stronger conclusions.

## 13. Next phase

Implementation is **not** started. The recommended next lane is steps 1-2
(evidence/outcome separation) as one bounded change with fixtures 1-10, followed
by steps 3-5 (boundary contract) with fixtures 11-20. Each requires a new
explicit operator-approved lane. No Attempt 7, V2-10, memory growth, retrieval,
or financial unlock is authorized by this document.
