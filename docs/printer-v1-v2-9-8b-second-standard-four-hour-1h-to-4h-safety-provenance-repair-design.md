# Printer V1 V2-9.8B — Second Standard Four-Hour 1h→4h Safety/Provenance Repair Design

## Design verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_DESIGN_PASS`

This design implements the repair-scope audit without weakening safety, freshness, provenance, Source Governor, Central Scheduler, or any downstream V1 lock.

## Design baseline

- parent audit commit: `303227dd76b96b144dab75c11bf1cb827563babc`
- repair branch: `agent/v2-9-8b-second-standard-4h-safety-provenance-repair`
- frozen consumed launch HEAD remains `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`

## Required behavior

For every Scheduler-owned `CONTINUATION_CLOSE` that attempts to produce a `WINDOW_1H` memory:

```text
Scheduler claims exact CONTINUATION_CLOSE
  -> reserve exact-pair close observation + bounded first-hour safety context
  -> collect fresh safety through existing Source-Governed context collector
  -> collect/persist exact-pair closing snapshot
  -> persist safety evidence/composite against that exact closing snapshot
  -> resolve exact current-run 15m predecessor
  -> close exact WINDOW_1H
  -> bind exact fresh safety composite ID into the 1h memory
  -> derive full-first-hour outcome
  -> audit / E2Z
  -> campaign binds exact 1h memory
  -> standard 4h barrier reads the exact bound safety through existing B.2
```

No step may substitute a prior 15m safety composite for the fresh first-hour composite.

## 1. Source-governed collection

Extend `one_command_15m_factory._execute_continuation_close()` to accept the already existing `context_adapter_factories` dependency from `run_one_command_15m_factory()`.

Before the final exact-pair snapshot, call the existing collector with only:

```python
include=frozenset({"safety"})
```

The existing collector remains the sole provider-call owner and retains:

- GoPlus safety request;
- conditional Solana RPC holder primary;
- exactly one approved backup holder RPC after eligible transient primary failure;
- Source Governor persistence/accounting;
- zero automatic retries;
- no unapproved endpoint rotation.

The caller must thread `cancellation_probe` unchanged.

## 2. Exact closing-snapshot persistence

After the final exact-pair snapshot succeeds, persist the fresh safety bundle with the existing `_persist_preclose_context()` using:

- exact `CONTINUATION_CLOSE` step identity;
- exact newly persisted closing `snapshot_id`;
- the fresh safety-only context bundle.

The result report must expose:

- `governed_context_collection`;
- `governed_context_persistence`.

This makes the safety composite's `evaluated_at` and snapshot linkage correspond to the actual first-hour close boundary.

## 3. Exact first-hour safety binding

Add a narrow orchestration helper:

`_attach_first_hour_safety_overlay(...)`

Inputs:

- DB connection;
- exact close step;
- produced `WINDOW_1H` memory ID;
- exact closing snapshot ID;
- persisted context result.

The helper must fail closed unless all are true:

1. the target memory exists;
2. target `window_kind == WINDOW_1H`;
3. memory token/pair equals step token/pair;
4. memory `snapshot_end_id` equals the exact closing snapshot;
5. persisted context contains `safety_composite.composite_id`;
6. the referenced composite exists;
7. composite token/pair equals the exact step target;
8. composite `snapshot_id` equals the exact closing snapshot.

On success, preserve all existing `supporting_context_json` fields and set only:

```json
{
  "memory_build_evidence_overlays": {
    "...existing keys preserved...": "...",
    "safety_composite_id": <exact fresh composite id>
  }
}
```

The helper must not mark the memory clean by itself, alter outcome, change `do_not_train`, or perform source calls.

## 4. Ordering

The exact first-hour close order becomes:

1. collect fresh safety-only governed context;
2. execute final exact-pair snapshot;
3. persist safety against the exact closing snapshot;
4. resolve exact current-run 15m predecessor;
5. close 1h memory;
6. attach exact fresh first-hour safety overlay;
7. derive first-hour outcome;
8. run existing audit/E2Z.

A failure at steps 1-6 blocks the first-hour close path. It must not yield a clean 1h object with missing safety authority.

## 5. Transport reservations

Add a named shared hard-reservation constant for first-hour safety:

```python
FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3
```

Update `LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND`:

```text
SNAPSHOT            = 1
WINDOW_CLOSE        = 1 + existing 15m preclose context
CONTINUATION_CLOSE  = 1 + FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT
```

`CONTINUATION_CLOSE` therefore reserves `4` source transport operations.

Reservation observation families:

- ordinal 0: `CONTINUATION_CLOSE_OBSERVATION`
- ordinals 1-3: `FIRST_HOUR_SAFETY_CONTEXT`

This is conservative capacity. It does not force all three safety-context requests to occur.

## 6. Lifecycle request budgets

The first-hour safety reserve must be represented explicitly in policy-derived lifecycle request components.

For `one_token_4h_runtime.cumulative_lifecycle_budget()` add:

```text
window_1h_safety_context = 3
```

For `standard_campaign_lifecycle_budget()` add per token:

```text
token_N_window_1h_safety_context = 3
```

The resulting both-eligible standard campaign request ceilings are:

| lanes | request ceiling | Scheduler ceiling |
|---|---:|---:|
| FAST + FAST | 236 | 210 |
| FAST + NORMAL | 188 | 162 |
| NORMAL + NORMAL | 140 | 114 |

Scheduler ceilings do not change because no new Scheduler job is introduced.

The maximum standard-four-hour outer request ceiling changes from `230` to `236`.

Historical single/continuous/selective first-hour hard request ceilings in `one_command_15m_factory` must also include the first-hour safety reserve wherever a real `CONTINUATION_CLOSE` can occur, so budget enforcement cannot reject the newly approved governed calls as an overrun.

## 7. B.2 / 4h consumer

Do not change the semantic contract of `load_authoritative_window_safety()`.

Do not introduce fallback-to-latest behavior.

Do not relax:

- freshness;
- exact token/pair identity;
- exact memory-window linkage;
- source-trace requirements;
- safety acceptance.

The repair is successful only when the unchanged B.2 contract can consume the newly produced first-hour output.

## 8. 1h close module boundary

`lane_e2o_1h_window_close.py` remains source-free.

Its responsibility remains physical first-hour window construction and continuity. Provider/source work stays in the Scheduler-owned factory orchestration around it.

## 9. Focused offline verification

Minimum tests:

1. `CONTINUATION_CLOSE` request projection/reservation is exactly `4`;
2. reservation families are one close observation plus three first-hour safety reservations;
3. one-token/standard campaign lifecycle budgets contain the explicit first-hour safety component and exact new ceilings;
4. helper binds an exact matching fresh composite while preserving existing supporting context;
5. helper rejects missing composite, wrong token/pair, wrong snapshot, and non-1h target;
6. `_execute_continuation_close` uses safety-only governed context and threads the configured context adapter factories;
7. consumer-facing first-hour memory shape contains `memory_build_evidence_overlays.safety_composite_id` before audit/E2Z/4h barrier consumption;
8. no test uses live providers, Scheduler runtime, authoritative corpus DB, retrieval, decisions, positions, trades, or PnL.

Use only the minimum additional existing tests needed for directly touched budget/safety/first-hour behavior. Do not broaden to unrelated regression suites unless focused failures indicate a direct dependency.

## Money-usefulness contribution

Fresh first-hour safety makes a clean 1h memory more useful and trustworthy for later observation: Printer can continue learning through 4h when safety remains acceptable, while still stopping when rug/holder/provenance conditions genuinely become stale, missing, or unsafe.

## What this design improves

- restores the producer/consumer contract at 1h→4h;
- preserves changing safety information instead of reusing stale 15m evidence;
- makes resource accounting truthful before source work begins;
- keeps the exact B.2 safety gate fail-closed.

## What this design still does not unlock

- no runtime or source fetching;
- no new authorization;
- no another 4h attempt;
- no 12h/24h;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trade events, paper trade audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Fresh-safety failure is expected fail-closed behavior:** provider failure at first-hour close may block a memory/continuation; the repair must not hide it.
- **Over-reservation vs actual calls:** three safety-context operations are a hard worst-case allowance; normal runs may consume fewer.
- **Duplicate context mutation:** overlay insertion must preserve existing first-hour supporting context rather than replace it.
- **Ordering risk:** audit/E2Z must not run before the exact safety overlay is bound.
- **Budget drift:** every hard-ceiling representation used by the affected lifecycle must move together; focused tests must detect divergence.

## Implementation authorization boundary

The user explicitly authorized implementation after audit and design. Implementation may now proceed only to code plus bounded offline proof. It does not authorize provider contact, Scheduler runtime, corpus mutation, a new authorization, or another standard-four-hour attempt.