# V2-9.7E.8 Origin-to-Lifecycle Operational Campaign Integration Design

**Status:** FROZEN
**Lane:** V2-9.7E.8 — Origin-to-Lifecycle Operational Campaign Integration
**Boundary:** internal composition only; no live pilot; no public CLI; no origin/decoder/cutoff/pagination/`create_v2` change
**Date:** 2026-07-21
**Baseline HEAD:** `4ab0f85a50d5e5ba656c5841fa6108755832f790`

## 1. Phase 1 — whole-path audit

### 1.1 The path

```
prospective Pump origin acquisition  (pumpfun_origin.run_acquisition_cycle)
→ durable origin registry            (printer_pumpfun_finalized_origin_registry, migration 036)
→ secondary enrichment               (secondary_discovery)
→ fixed gates                        (CombinedPumpfunCampaignExecutor._apply_gates, GATE_ORDER)
→ deterministic selection            (_select, uniform Fisher-Yates on cycle seed)
→ atomic campaign_token_slots        (_persist_selection_and_handoff → two-or-none)
→ lifecycle tracking targets         (** GAP **)
→ 15m → selective 1h → conditional 4h → support-only 5m → promotion → report → replay
                                     (one_command_15m_factory)
```

### 1.2 Findings

**F1 — Why `CombinedPumpfunCampaignExecutor` stops after activation.**
`execute()` runs one `_run_cycle`: discovery → merge → origin (registry-first) →
PumpSwap → fixed gates → uniform selection → `_persist_selection_and_handoff`,
which atomically creates `printer_tokens`, `printer_pairs`,
`printer_tracking_queue` rows, `TRACK_NORMAL_FIRST_15M` scheduler jobs, and
`printer_memory_factory_campaign_token_slots` (two-or-none). It then returns
`COMPLETED`. It has **no window loop, no snapshot, no promotion, no report** —
and no `src/` caller. It is a discovery-and-activation owner, by construction.

**F2 — Why `one_command_15m_factory` performs separate legacy discovery.**
`run_one_command_15m_factory` predates the combined origin architecture. Its
`_build_discovery_args` hard-codes `source_name="geckoterminal"`, `query="pump"`,
and its default discovery (`build_discover_candidates_once_payload`) neither
consults the origin registry nor enforces `PUMPFUN_ORIGIN_CONFIRMED`. But it
**already exposes a `discovery_runner` injection seam**: when supplied, the
factory calls it instead of geckoterminal discovery, reads
`selection_handoff_report.batch_id`, loads targets via `_selected_targets`, and
runs the **entire** proven lifecycle (15m → 1h → 4h → 5m → promotion → report →
replay → cleanup) on those targets.

**F3 — Data-model difference.**
The executor's activation output is
`printer_memory_factory_campaign_token_slots`
(`token_row_id`, `mint_identity`, `pair_row_id`, `pair_identity`,
`tracking_queue_id`, `token_state='SELECTED'`, `slot_ordinal ∈ {1,2}`) plus the
`printer_tokens`/`printer_pairs`/`printer_tracking_queue` rows it created.
The factory's lifecycle input is `printer_selection_batch_items`
(`item_status='SELECTED'`, `token_id`, `pair_id`, `token_mint`, `pair_address`,
`tracking_lane`) joined to the same `printer_tokens`/`printer_pairs`. The two
tables describe the **same two activated identities** in different shapes; the
`printer_tokens`/`printer_pairs` rows are shared.

**F4 — Which owner performs the authoritative handoff.**
Neither existing owner. The handoff belongs to a **new internal driver** that
composes the executor and the factory and performs an
**identity-preserving materialization** of the two activated slots into the
factory's `selection_batch_items` shape. This is a translation of an existing,
already-atomic activation — not a second discovery or selection.

**F5 — Can existing lifecycle owners accept exact preselected identities?**
Yes. `_selected_targets` reads whatever `SELECTED` items exist for the batch;
the factory does not itself discover or re-rank once a `discovery_runner` is
supplied. Feeding it the two activated identities is sufficient and requires no
change to the lifecycle loop.

**F6 — Would any path rediscover, reselect, or replace origin authority?**
No, under the chosen model. The injected `discovery_runner` runs the executor
**once** (the sole discovery+origin+gates+selection+activation) and then only
**mirrors** its atomic result. The factory never runs geckoterminal discovery
when a runner is supplied, and never re-ranks. Origin authority stays with the
executor's registry-backed gates; the factory receives already-confirmed
identities and cannot alter them.

**F7 — Is a schema change required?**
No. Every identity needed by the factory (`token_id`, `pair_id`, `token_mint`,
`pair_address`, `tracking_lane`) is already present in
`printer_tokens`/`printer_pairs` (created by the executor) and
`campaign_token_slots`. The materialization writes only existing
`printer_selection_batches`/`printer_selection_batch_items` rows. **No
migration.**

## 2. Phase 2 — frozen design

### 2.1 Selected composition

```
OriginToLifecycleCampaignDriver.run(...)
  → CombinedPumpfunCampaignExecutor.execute()      # ONE discovery→origin→gates→selection→atomic activation
  → if exactly two SELECTED campaign_token_slots:
        reconcile_activation_for_lifecycle(...)     # cancel the executor's own first-15m jobs (superseded)
        materialize origin-activated selection batch # identity-preserving, from campaign_token_slots
        run_one_command_15m_factory(                 # THE lifecycle owner, unchanged
            discovery_runner = <returns the materialized batch>,
            proof_mode / continuous_first_hour / continuous_four_hour, ...
        )
  → else (zero or rolled-back activation):
        no batch, no lifecycle work
```

### 2.2 Authoritative internal owner

A new internal module `printer_v1/operator_cli/origin_lifecycle_campaign.py`
exposing `OriginToLifecycleCampaignDriver` (dependency-injected: it receives the
executor factory and the lifecycle callable). It is **not** a public CLI and has
no argparse surface.

The `discovery_runner` seam is the **identity-preserving lifecycle handoff**.
The runner:

1. runs the executor exactly once and inspects `campaign_token_slots`;
2. on `slot_ordinal` 1 and 2 both `SELECTED` with distinct
   `token_row_id`/`pair_row_id`: cancels the executor's `TRACK_NORMAL_FIRST_15M`
   jobs (reconciliation — the factory owns lifecycle scheduling), then inserts
   one `printer_selection_batches` row and two `SELECTED`
   `printer_selection_batch_items` mirroring the exact slot identities;
3. returns `{"selection_handoff_report": {"batch_id", "selection_seed",
   "eligible_pool_size": 2}, "discovery_results": []}`;
4. on fewer than two activated slots: returns `batch_id=None`,
   `eligible_pool_size=0`, no rows → factory `STOP_EMPTY`, no lifecycle work.

### 2.3 Requirements satisfied

| Requirement | How |
|---|---|
| Exact identity linkage (campaign/run/cycle/slot/mint/pair/lifecycle) | batch items materialized directly from `campaign_token_slots`; token/pair rows shared |
| No second discovery or reselection after activation | executor runs once; runner only mirrors its atomic result; factory discovery replaced |
| No manual copying of loosely related rows | materialization keyed on `token_row_id`/`pair_row_id` from the two slots only |
| Lifecycle from the two activated slots | factory `_selected_targets` reads exactly those two |
| Source-Governor ownership for source work | all source work is inside the executor (governed) and factory snapshot/context adapters (governed); no new source path |
| Central-Scheduler ownership for tracking/window work | factory `enqueue_job` for every step; executor's superseded jobs cancelled |
| Token-local failure isolation | unchanged factory per-token step handling |
| Continuation / cutoff / promotion / safety / reporting / replay | unchanged factory lifecycle |
| No public operational command | driver is internal, DI-only |
| No competing primary path | ONE lifecycle owner (the factory); the legacy geckoterminal front-end remains **non-authoritative / historical-compatibility only** (see §2.5) |

### 2.4 Zero-slot and rollback

If the executor activates zero slots (`INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`) or
rolls back an initial activation (`HANDOFF_*`, `CONFLICTING_SLOT`, …), no
`campaign_token_slots` reach the two-`SELECTED` state, the runner returns an
empty batch, and the factory starts **no** lifecycle work. The driver reports
the executor's terminal cause honestly.

### 2.5 Authority status of the legacy path

`run_one_command_15m_factory` with the **default** `discovery_runner=None` keeps
its geckoterminal discovery for historical V2-4/V2-5/V2-7/V2-8 compatibility and
their existing tests. It is **not** the V2-9.7E operational path and does **not**
enforce finalized Pump origin. The V2-9.7E operational path is **only** the new
driver, which always supplies the origin-based `discovery_runner`. The factory
lifecycle body is shared and unchanged; there is exactly one lifecycle
implementation, so no competing primary path exists.

### 2.6 No migration

Justified by F7. All identities pre-exist; only existing selection-batch tables
are written.

## 3. Internal review

| Question | Finding |
|---|---|
| Does the factory re-rank the materialized items? | No — `_selected_targets` returns all SELECTED items; both are activated targets. |
| Can the factory mutate the activated identities? | No — it reads token/pair ids and runs snapshots; it never re-selects or re-discovers. |
| Stale executor jobs after handoff? | Reconciled: the executor's first-15m jobs are cancelled before the factory plans its own; cleanup terminalizes both ledgers. |
| Governor/Scheduler bypass? | Impossible to add — the driver introduces no new source or scheduler surface; both remain owned by the executor and factory. |
| Any financial/retrieval surface? | None added. |

**Verdict:** approved for implementation.
