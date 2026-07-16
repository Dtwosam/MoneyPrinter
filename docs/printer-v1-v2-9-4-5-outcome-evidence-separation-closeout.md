# Printer V1 V2-9.4.5 Outcome / Evidence-Quality Separation Closeout

## Verdict

`V2_9_4_5_OUTCOME_EVIDENCE_SEPARATION_PASS`

Lane: `V2-9.4.5 - Separate market outcome from memory evidence quality`

Design steps 1-2 of `printer-v1-v2-9-4-4-evidence-boundary-memory-semantics-design.md`
are implemented. Market outcome can no longer degrade evidence quality: no price
direction, path, magnitude, or volatility label can produce `DIRTY_MEMORY`. The
labels remain truthful. Every genuine dirty and audit-only gate is preserved and
proven still firing. No 4h boundary change, no migration, no historic rewrite.

Preflight passed: HEAD exactly `b193739`, tracked tree clean, no proof runtime,
no one-proof lock.

## What was wrong

`chart_volatility/classifier.py` routed two *market-outcome* facts into the
*evidence* gate:

```
chart_context_blocks_clean_memory(...) ->
    classify_volatility(...) == VOLATILITY_EXTREME
    or classify_candle_path(...) == PATH_ROUND_TRIP
```

`classify_chart_memory_gate` returned `CHART_CONTEXT_DO_NOT_TRAIN` for those —
**the same label it returns for a failed or dirty source**. A payload whose own
quality was `CHART_CONTEXT_CLEAN` therefore exited as `DO_NOT_TRAIN`, flowed
into `memory/quality.py` as `REJECT_DIRTY_CHART_CONTEXT`, and became
`DIRTY_MEMORY`. `chart_volatility/lookup.py` independently repeated the same two
outcome clauses.

This is what marked Attempt 6 dirty: 61/61 snapshots, zero misses, clean
cadence, exact continuity, successful forced close — discarded solely because
the price round-tripped. The Memory Factory guide already forbids this
("Clean memory is evidence quality plus outcome clarity, not price performance";
anti-bias rule "No winner-only memory"). This lane corrects code to spec; it
does not loosen the spec.

## Implementation (smallest change)

| File | Change |
| --- | --- |
| `src/printer_v1/chart_volatility/classifier.py` | Deleted `chart_context_blocks_clean_memory` and the gate branch that consumed it. `classify_chart_memory_gate` is now a pure function of payload quality, with a comment recording why. `classify_volatility` / `classify_candle_path` are untouched and still emit `VOLATILITY_EXTREME` / `PATH_ROUND_TRIP` as truthful outcome labels. |
| `src/printer_v1/chart_volatility/lookup.py` | `chart_volatility_snapshot_blocks_clean_memory` now blocks only on `CHART_CONTEXT_DO_NOT_TRAIN` (an evidence fault). The `VOLATILITY_EXTREME` / `PATH_ROUND_TRIP` clauses are removed; the two now-unused imports are dropped. |
| `src/printer_v1/chart_volatility/__init__.py` | Removed the deleted symbol from the import and `__all__`. |
| `tests/test_phase12_chart_volatility_engine.py` | `test_extreme_or_round_trip_blocks_memory_without_paper_decisions` asserted the *defect* (that outcome blocks memory). Rewritten as `test_extreme_or_round_trip_is_outcome_not_evidence_fault`: the labels are still asserted truthful, but the blocking is gone. |
| `tests/test_v2_9_4_5_outcome_evidence_separation.py` | New fixture matrix (below). |

`src/printer_v1/memory/quality.py` required **no change**. Its
`chart_memory_gate_label == "CHART_CONTEXT_DO_NOT_TRAIN"` check became correct
automatically once the classifier stopped emitting that label for outcomes — the
rejection reason `REJECT_DIRTY_CHART_CONTEXT` now only fires on genuine chart
evidence faults, which the fixtures prove.

Deleting the function (rather than leaving it always-returning-`False`) was
chosen because a predicate named "blocks clean memory" that never blocks is dead
and misleading API. Its only consumers were the gate, the package export, and
the stale test — all updated.

## Preserved gates (proven still firing)

Unchanged and fixture-verified: snapshot coverage; missing `price_usd` /
`liquidity_usd`; stale / conflicting / failed sources; failed chart source →
`DO_NOT_TRAIN`; stale chart evidence → `AUDIT_ONLY`; mandatory safety failure
(`SAFETY_UNSAFE`, `SAFETY_DO_NOT_USE_FOR_MEMORY`); dirty safety context;
`OUTCOME_UNKNOWN` → `AUDIT_ONLY`; unrealistic profit and profit-claimed-without-
realistic-entry-and-exit → `AUDIT_ONLY`; `FLOW_WASH_LIKE` → `DO_NOT_TRAIN`;
incomplete-coverage flag → `DIRTY_MEMORY`.

`FLOW_WASH_LIKE` deliberately stays blocking: wash-like trading attacks
**evidence authenticity** (reported volume does not reflect real participation),
not price performance. It is an integrity signal, not an outcome signal.

## Fixture matrix

`tests/test_v2_9_4_5_outcome_evidence_separation.py` — **18 passed, 15 subtests**.

| Fixture | Result |
| --- | --- |
| Fully evidenced round trip (`PATH_ROUND_TRIP`, complete evidence) | `CLEAN_MEMORY`, outcome preserved, zero rejection reasons |
| Fully evidenced dump / pump-and-dump | `CLEAN_MEMORY`, truthful negative outcome |
| Extreme volatility, trustworthy evidence | not dirty; `chart_context_can_support_clean_memory` true |
| Every price path (round trip / dump / pump-and-dump / extreme / calm) | no rejection reason produced from any outcome label |
| Stored-snapshot lookup with outcome labels | no longer blocks; still blocks on `CHART_CONTEXT_DO_NOT_TRAIN` |
| Missing `price_usd` or `liquidity_usd` | `DIRTY_MEMORY` |
| Insufficient coverage | `DIRTY_MEMORY` |
| Stale / conflicting source | `AUDIT_ONLY_MEMORY` |
| Stale chart evidence | `CHART_CONTEXT_AUDIT_ONLY` |
| Failed chart source | `CHART_CONTEXT_DO_NOT_TRAIN` → `DIRTY_MEMORY` |
| Mandatory safety failure | `DIRTY_MEMORY`, `REJECT_UNSAFE_TOKEN` |
| Dirty safety context | `DIRTY_MEMORY` |
| `OUTCOME_UNKNOWN` | `AUDIT_ONLY_MEMORY` |
| Unrealistic profit | `AUDIT_ONLY_MEMORY` |
| Profit claim without realistic entry+exit | `AUDIT_ONLY_MEMORY` |
| `FLOW_WASH_LIKE` | `DIRTY_MEMORY` (authenticity) |
| Partial trading flow (no split volume / unique wallets) | honestly partial: neither `ACCEPTABLE` nor `DO_NOT_TRAIN` |
| Incomplete-coverage flag | `DIRTY_MEMORY` |

## Verification performed

| Check | Result |
| --- | --- |
| Changed tests (`test_phase12_chart_volatility_engine.py`) | 15 passed |
| New lane fixtures | 18 passed, 15 subtests |
| Nearest contracts: chart, episode/memory quality, real memory-quality audit, E2Q, 1h audit gate, Lane Q, Lane K/E2Z, E2Z clean-memory creation | all green |
| Python compilation | `COMPILE_OK` |
| Persistent DB hash unchanged | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| `git diff --check` | clean (exit 0) |
| Migration added | none — zero files under `migrations/` |
| Temporary fixture DBs only; no live sources; no full repository suite | confirmed |

## Scope honoured

Not touched, exactly as instructed: the 4h snapshot-boundary and
closing-evidence resolution (`context_evidence/window_15m.py`) is **unchanged** —
that is design steps 3-5 and a separate lane. The stored Attempt 6 result was
**not** forced to `CLEAN_MEMORY` and no historic memory was rewritten. Whether
partial trading flow is optional or mandatory for overall clean promotion is
**not decided here**; the existing requirement stands until an explicit contract
resolves it. `trading_flow/classifier.py` is unchanged.

## Money-usefulness contribution

This is the difference between a corpus that learns from losses and one that
only remembers winners. A perfect 10,800-second record of a token that
round-tripped to zero was being thrown away as "dirty" — the single most
capital-protective lesson available, discarded because the price ended badly.
After this change, a fully evidenced dump, round trip, or failed breakout is a
retained, trustworthy lesson. No clean memory is created by this lane itself;
it removes the rule that was destroying it.

## What improves

- `DIRTY_MEMORY` regains one honest meaning: untrustworthy evidence.
- Fully evidenced negative outcomes can reach `CLEAN_MEMORY`, satisfying the
  spec's "No winner-only memory" anti-bias rule.
- The chart gate answers one question ("can this evidence be trusted?") instead
  of silently answering two.
- A misleading always-blocking predicate and its duplicate in `lookup.py` are
  gone, so the outcome/evidence boundary cannot drift back.

## What remains locked

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`,
`WINDOW_24H`, and active memory growth all remain locked. `WINDOW_5M_MICRO_EVENT`
stays support-only. No Attempt 7, no V2-10. Safety, liquidity, provenance,
realism, and missing-data gates are unchanged — none was weakened to create
clean memory.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **This does not make Attempt 6's token good.** It makes a truthful
   `ROUND_TRIP` record *trustworthy*. Any future decision layer must still treat
   that outcome as a loss lesson; clean means reliable, not favourable.
2. **The stored Attempt 6 window is still `DIRTY_MEMORY`.** This lane changes
   forward classification only. Re-deriving or re-running that window is an
   explicit operator decision for a later lane.
3. **The 4h boundary defect remains open.** Until design steps 3-5 land, 4h
   context resolution can still exchange a valid closing snapshot for a
   predecessor and reject valid closing safety/quote evidence, so a 4h window
   may still be blocked for boundary reasons unrelated to this repair.
4. **Partial trading flow still gates clean promotion** under the existing
   requirement, unresolved by design. DexScreener cannot supply the split
   volume / unique-wallet fields, so 4h windows may remain non-clean for that
   reason until a separate operator-approved provider-contract lane resolves it.
5. **`chart_context_blocks_clean_memory` was a public export.** It is removed.
   Only the gate, the package export, and one stale test referenced it (all
   verified by grep across `src/` and `tests/`), so no caller is stranded.
6. **A now-clean round trip becomes retrieval-eligible when retrieval is later
   unlocked.** That is the intended behaviour, but it means the retrieval lane
   must be reviewed knowing negative outcomes are now first-class clean memory.

## Files changed

- `src/printer_v1/chart_volatility/classifier.py`
- `src/printer_v1/chart_volatility/lookup.py`
- `src/printer_v1/chart_volatility/__init__.py`
- `tests/test_phase12_chart_volatility_engine.py`
- `tests/test_v2_9_4_5_outcome_evidence_separation.py` (new)
- `docs/printer-v1-v2-9-4-5-outcome-evidence-separation-closeout.md` (this file)

## Next recommended phase

Design steps 3-5 — the 4h boundary contract (ledger-exact snapshot selection,
predecessor/future exclusion, preserved logical deadline, a separate approved
closing-evidence cutoff, exact closing safety/quote attachment, fail-closed
specific blockers) with fixtures 11-20 of the V2-9.4.4 design. **Not started
here.** It requires a new explicit operator-approved lane, as does any Attempt 7,
V2-10, memory growth, retrieval, or financial unlock.
