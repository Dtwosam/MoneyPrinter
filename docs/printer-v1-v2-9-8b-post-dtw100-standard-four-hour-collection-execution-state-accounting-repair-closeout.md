# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Collection Execution / State / Accounting Repair Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_COLLECTION_EXECUTION_STATE_ACCOUNTING_REPAIR_PASS`

The approved offline repair is complete and independently re-proven on the exact durable implementation commit.

This PASS establishes campaign-owned `WINDOW_4H` collection-state truth, long-window lifecycle reservation accounting, token-local/shared collection failure cleanup, and categorical two-token 4h service fairness around the existing governed collector.

It does **not** authorize real `WINDOW_4H` collection and does not complete successful 4h physical close, memory construction, quality classification, or campaign terminal reconciliation.

## Durable anchors

Corrected RED baseline:

`403169301eb2cd6f026457e7852d527806b2bac8` — `Correct four-hour fairness fixture scope`

Production implementation:

`dc525000dd574c6b4f288a7962c8543bdb5272db` — `Repair standard four-hour collection state accounting`

Production diff from corrected RED baseline:

- exactly one commit ahead;
- exactly one production file changed;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- 418 additions / 27 deletions;
- no schema or migration change;
- no source-adapter/provider-contract change;
- no cadence/budget activation change.

## RED evidence

Corrected RED workflow:

- run: `31383976886`;
- job: `93440167263`;
- exact head: `403169301eb2cd6f026457e7852d527806b2bac8`;
- compile: PASS;
- 60 tests executed;
- existing B2, first-hour Checkpoint-3, handoff, and Scheduler-ownership regressions remained green;
- exactly nine new checkpoint cases failed for the intentionally missing 4h production behavior.

The failures reduced to:

- missing exact 4h collecting/close-pending state owners;
- zero long-window reservation observations where existing projected request counts required them;
- 1h-only shared lifecycle cleanup;
- missing categorical exact-`WINDOW_4H` fairness selector.

The fairness fixtures were corrected before RED acceptance so unrelated earlier pending non-4h work retained its existing priority. Production fairness was not weakened to satisfy a bad fixture.

## Implementation completed

### Exact lifecycle ownership

The canonical factory now has one stage-exact lifecycle resolver reused by explicit 1h and 4h wrappers. `WINDOW_4H` work must resolve one exact V2 stage-scoped Scheduler owner and exact campaign window/slot identity or fail closed.

### 4h collection-state truth

- claimed `LONG_CONTINUATION_SNAPSHOT` can move only its exact owned 4h window `PLANNED -> COLLECTING`;
- claimed `LONG_CONTINUATION_CLOSE` can move only its exact owned 4h window `COLLECTING -> CLOSE_PENDING`;
- exact replay is idempotent;
- conflicting state/identity fails closed.

### Long-window reservation accounting

The canonical lifecycle reservation builder now emits long-window verification observations from the already-existing projected request count:

- `LONG_CONTINUATION_OPENING_OBSERVATION`;
- `LONG_CONTINUATION_SNAPSHOT_OBSERVATION`;
- `LONG_CONTINUATION_CLOSE_OBSERVATION`.

This adds accounting visibility only. It creates no new request, retry, transport budget, source path, or provider behavior.

### Token-local and shared 4h cleanup

Collection-stage terminal reconciliation now supports:

- `BLOCKED -> token slot FAILED`;
- `CANCELLED -> token slot MANUAL_REVIEW`.

It preserves exact token/pair/window/slot ownership, immutable first terminal cause, idempotent exact replay, and atomic read-back checks.

A failed token can cancel/block only its own remaining long lifecycle while its peer stays serviceable. Shared cleanup now covers both proven `WINDOW_1H` and exact campaign-owned `WINDOW_4H` nonterminal lifecycles.

Successful 4h clean/dirty/no-promotion terminal reconciliation is intentionally not implemented here.

### Categorical two-token fairness

The canonical pending-step selector now adds special fairness only when exact campaign-owned due `WINDOW_4H` work is the active scope.

It preserves unrelated/non-4h behavior and future scheduling. Within eligible due 4h work it enforces:

1. due long close before ordinary long snapshots;
2. less actual service in the exact 4h window first;
3. older canonical Scheduler job identity;
4. stable slot ordinal only as final tie-breaker.

Actual service is derived from Scheduler start evidence. The relation is categorical; no score, rank, confidence, weighted priority, or market-performance preference was introduced.

## GREEN and independent proof

Apply workflow:

- run: `31385232516`;
- job: `93444062960`;
- exact corrected RED parent verified;
- one-file production patch scope verified;
- compile PASS;
- `60/60` focused tests PASS;
- capability locks PASS;
- production-only commit/push PASS.

Independent exact-head proof:

- PR #141, closed unmerged;
- run: `31385380336`;
- job: `93444513699`;
- checkout explicitly bound to `dc525000dd574c6b4f288a7962c8543bdb5272db`;
- compile PASS;
- `60/60` tests PASS in 56.128 seconds;
- `git diff --check` PASS;
- real `WINDOW_4H` collection remained disabled for FAST and NORMAL;
- `WINDOW_12H` and `WINDOW_24H` remained disabled.

The focused suite covered the nine new collection/state/accounting/fairness cases plus directly affected B2 campaign planning/handoff, first-hour Checkpoint-3, and Scheduler-ownership contracts.

No broad suite was required for this narrow repair.

## Money-usefulness contribution

Printer can now distinguish a genuinely serviced two-token 4h collection path from one that is unfair, unaccounted, state-stale, or orphaned after failure.

That makes later four-hour memories more trustworthy for learning continuation, collapse, revival, distribution, and liquidity deterioration because service, source-capacity accounting, and failure isolation have exact campaign ownership.

This PASS proves no profitability and creates no trading authority.

## What this checkpoint improves

- campaign `WINDOW_4H` state follows actual Scheduler-claimed service;
- long source demand has matching lifecycle reservation observations;
- token-local long failures do not silently poison the peer lifecycle;
- shared safe stop reconciles nonterminal owned 4h campaign state;
- the adopted categorical two-token fairness law is executable and proven;
- the existing Source Governor/Scheduler/collector owners remain canonical.

## What remains locked / incomplete

Still locked or incomplete:

- real `WINDOW_4H` collection;
- successful campaign-level 4h physical close composition;
- 4h memory construction/binding at campaign level;
- 4h clean/dirty/no-promotion terminal reconciliation;
- operational 4h rereadiness or authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, audits, PnL;
- wallets, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

The known unrelated historical one-token E2Z replay assertion remains outside this checkpoint unless the next close/memory audit proves it affects the required standard campaign path.

## Proof/test required before later 4h completion

The next checkpoint must first audit the existing physical 4h close, memory construction, E2Q/Lane-Q/E2Z quality path, and campaign terminal owners.

Before that later checkpoint can PASS, proof must establish at minimum:

- exact campaign 4h close binds to the correct physical memory-window identity;
- forced closing snapshot and governed closing context remain intact;
- memory quality/classification is derived from the physical 4h result without fabricating clean status;
- successful clean/dirty/no-promotion outcomes reconcile the exact campaign window and token slot atomically;
- terminal Scheduler work and campaign ownership agree with the physical close result;
- exact replay is idempotent and conflicting replay fails closed;
- no active long work or orphaned campaign state remains after terminal reconciliation;
- peer-token independence is preserved;
- real 4h/12h/24h collection remains locked during offline proof unless a later explicit activation lane says otherwise.

## Functionality Risks / Setbacks / Efficiency Blockers

- The large canonical factory remains a concentration point; future work should stay narrow rather than refactor it opportunistically.
- Fairness uses Scheduler `started_at` as service-attempt evidence. A later Scheduler contract change must preserve or explicitly redesign that fact.
- Shared cleanup now covers both 1h and 4h; later closeout must keep proving first-hour behavior did not regress.
- Successful 4h terminal reconciliation is deliberately absent; treating this PASS as full 4h campaign completion would be unsafe.
- Reservation observations follow existing projected request counts; changing those projections later requires matching accounting proof.
- GitHub Actions emitted Node runtime deprecation warnings for action internals; they did not affect Printer tests or product behavior and are not a Printer production blocker.

## Next permitted checkpoint

Begin a **read-only standard four-hour close / memory / terminal-reconciliation audit**.

That audit may inspect code, tests, schema, and existing artifacts only. It must determine exactly what can be reused from the one-token 4h path and first-hour Checkpoints 4–6 before any new implementation is designed.

No real source call, runtime, DB operational mutation, memory generation, authorization, or activation is permitted by this closeout.
