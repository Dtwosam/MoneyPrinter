# V2-9.7E.8 Origin-to-Lifecycle Operational Campaign Integration Closeout

**Status:** PASS
**Lane:** V2-9.7E.8 — Origin-to-Lifecycle Operational Campaign Integration
**Date:** 2026-07-21
**Baseline HEAD:** `4ab0f85a50d5e5ba656c5841fa6108755832f790`
(Checkpoint 1 — `Derive canonical migration head in supervision test`)

## Final Verdict

`V2_9_7E_8_ORIGIN_TO_LIFECYCLE_INTEGRATION_PASS`

The gap identified in V2-9.7E.7 is closed. An internal, dependency-injected
driver now composes the proven V2-9.7E.6 origin architecture with the proven
memory lifecycle: atomic two-slot origin activation feeds the lifecycle its
exact activated identities through an identity-preserving handoff, with no
second discovery, no reselection, and no schema change.

## Checkpoint status

* **Checkpoint 1 — migration-test repair:** committed `4ab0f85`
  (`Derive canonical migration head in supervision test`), test-only, derived
  from the authoritative migration owner. This is the Checkpoint 2 baseline.
* **Checkpoint 2 — this lane.**

## 1. Confirmed root cause

V2-9.7E.7 established that no governed path carried a finalized-origin-confirmed
token into the full memory lifecycle. Phase 1 confirmed why:

* `CombinedPumpfunCampaignExecutor.execute()` runs discovery → registry-first
  finalized origin → fixed gates → uniform selection → atomic two-or-none
  activation into `printer_memory_factory_campaign_token_slots`, then **returns**.
  It has no window loop and, at lane start, no `src/` caller.
* `one_command_15m_factory.run_one_command_15m_factory` runs the entire
  `WINDOW_15M` → `WINDOW_1H` → `WINDOW_4H` → support-only 5m → promotion →
  report → replay → cleanup lifecycle, but its default discovery is
  geckoterminal and does not consult the origin registry.
* The two describe the **same two activated identities** in different shapes
  (`campaign_token_slots` vs `selection_batch_items`) over the same shared
  `printer_tokens`/`printer_pairs` rows.

The factory already exposes a `discovery_runner` injection seam. The missing
piece was an owner that runs the executor once and mirrors its atomic activation
into the factory's selection-batch shape. No schema change was required (F7).

## 2. Final ownership and handoff architecture

```
OriginToLifecycleCampaignDriver.run()
  → CombinedPumpfunCampaignExecutor.execute()      # ONE discovery→origin→gates→selection→atomic activation
  → read the two SELECTED campaign_token_slots
  → materialize_origin_activated_batch(...)         # identity-preserving mirror into selection_batch_items
       └ cancel the executor's superseded first-15m jobs (Scheduler-owned)
  → run_one_command_15m_factory(discovery_runner=<returns that batch>, ...)   # THE lifecycle owner
  → zero-slot / rolled-back / owner-unavailable activation → no lifecycle work
```

* **Authoritative handoff owner:** the new
  `printer_v1/operator_cli/origin_lifecycle_campaign.py` driver (internal,
  DI-only, no CLI, no live source path).
* **Lifecycle owner:** unchanged `run_one_command_15m_factory`.
* **Source ownership:** every source call remains inside the governed executor
  and the governed factory adapters. The driver adds no source surface.
* **Scheduler ownership:** the factory owns all window/tracking jobs; the
  executor's superseded first-15m jobs are cancelled via the canonical
  `cancel_job` owner so no stale scheduler work remains.

## 3. Files and schema changes

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` | new — driver, `materialize_origin_activated_batch`, activation-job reconciliation, identity guard |
| `tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py` | new — 14 integrated proofs |
| `docs/printer-v1-v2-9-7e-8-origin-to-lifecycle-integration-design.md` | new — audit + frozen design |
| `docs/printer-v1-v2-9-7e-8-origin-to-lifecycle-integration-closeout.md` | new — this closeout |

**No migration.** All identities (`token_id`, `pair_id`, `token_mint`,
`pair_address`, `tracking_lane`) pre-exist in `printer_tokens`/`printer_pairs`
(created by the executor) and `campaign_token_slots`. The driver writes only
existing `printer_selection_batches`/`printer_selection_batch_items` rows.

## 4. Retired / non-authoritative paths

* The legacy geckoterminal-discovering `run_one_command_15m_factory` front-end
  (default `discovery_runner=None`) is retained **only** for historical
  V2-4/V2-5/V2-7/V2-8 compatibility and their tests. It is **not** the V2-9.7E
  operational path and does not enforce finalized Pump origin.
* The V2-9.7E operational path is **only** the new driver, which always supplies
  the origin-based `discovery_runner`. There is exactly one lifecycle
  implementation (the factory body), so no competing primary path exists.

## 5. Integrated proof results

`tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py` — **14 passed**.

**Activation → lifecycle (driver):**

| Proof | Result |
|---|---|
| Two finalized origins → two atomic slots → lifecycle starts on those slots | PASS |
| Lifecycle targets are exactly the two activated identities (no foreign token) | PASS |
| Exactly two SELECTED batch items mirroring the slots — no reselection | PASS |
| Executor's first-15m jobs cancelled — no stale activation jobs | PASS |
| No running jobs / pending run-steps after terminalization | PASS |
| Lifecycle never invoked legacy geckoterminal discovery | PASS |
| Financial / retrieval locks stay zero-delta | PASS |
| Deterministic zero-source replay (stable report) | PASS |
| Two activated slots carry two distinct token identities | PASS |

**Continuation depth through the handoff:**

| Proof | Result |
|---|---|
| An origin-activated identity drives the continuous 15m→1h lifecycle path (enabled, token present, 15m snapshots on the exact mint, 1h/4h continuation structure present), no legacy discovery, locks zero, clean terminalization | PASS |

**Negative and bypass:**

| Proof | Result |
|---|---|
| Single origin → `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` → zero activation, zero lifecycle work, zero run-steps, zero batch items | PASS |
| No origins → no activation → no lifecycle | PASS |
| Duplicate-token slot set → materialization fails closed `IDENTITY_MISMATCH` | PASS |
| Source Governor unavailable → fail closed, no lifecycle | PASS |
| Central Scheduler unavailable → fail closed, no lifecycle | PASS |

**Regressions (all green):** isolated combined discovery proof, combined
discovery executor, one-command 15m factory (V2-4), durable supervision
(43 + 7 subtests); multi-token conservative, atomic two-slot handoff, origin
acquisition, `create_v2` classification (83 passed).

Risk-based verification: no broad repository suite run — no broad shared owner
changed. The factory lifecycle body is unmodified.

## 6. Identity and Scheduler evidence

* **Identity linkage:** batch items are materialized directly from the two
  `campaign_token_slots` (`token_row_id`, `pair_row_id`, `mint_identity`,
  `pair_address`); lifecycle run-steps reference only those activated token ids
  (proven a strict subset). The two slots always carry distinct token rows
  (schema `UNIQUE (cycle_id, token_row_id)` plus collapse-by-mint selection).
* **Scheduler ownership / no stale work:** the executor's superseded first-15m
  jobs are cancelled through the canonical Scheduler owner; the factory owns all
  subsequent window jobs; no `window15m:*` job remains active after handoff, and
  no running jobs or pending run-steps remain after terminalization.

## 7. Money-usefulness contribution

* Closes the last structural gap between working finalized-origin acquisition
  (V2-9.7E.6) and memory growth: origin-confirmed tokens now actually enter the
  15m/1h/4h memory lifecycle.
* Reuses the entire proven lifecycle unchanged, so no lifecycle behaviour,
  promotion rule, or safety gate is re-litigated or put at risk.
* Preserves finalized-origin authority end to end — the lifecycle receives only
  already-confirmed identities and can never re-discover or re-rank them.
* Adds no source surface and no schema, so the integration cost is a thin,
  auditable handoff.

## 8. What the lane improves

One authoritative internal operational campaign composition
(origin → activation → identity-preserving handoff → lifecycle), with the legacy
geckoterminal front-end explicitly demoted to historical compatibility.

## 9. What remains locked

Live pilot; full V2-9.7E pilot; V2-9.7F; V2-9.8; retrieval; paper decisions;
BUY/SELL/HOLD; positions; trades; audits; PnL; wallet, keys, signing, real
funds, live execution; paid APIs; scoring/ranking/confidence/weighted logic;
embeddings/vectors; Source Governor and Scheduler bypass; finalized exact-mint
origin requirement; two-or-none activation; freshness/liquidity/activity/cooldown
and selection rules; `WINDOW_5M_MICRO_EVENT` support-only; automatic successor or
restart after terminal failure.

## 10. Functionality Risks / Setbacks / Efficiency Blockers

1. **Proof-harness limitation (not an integration defect):** the factory's
   compressed-time continuous proof mode is single-token by contract
   (`_CONTINUOUS_MAX_SELECTED_TOKENS == 1`), while atomic activation is
   two-or-none. The integrated proof therefore demonstrates the full 15m→1h→4h
   continuation depth for **one** activated identity, and the two-token 15m
   lifecycle for **both**. A two-token continuous compressed proof is not
   expressible in the current factory harness. In real (wall-clock) operation
   each activated token runs its own windows independently; this is a proof
   compression limit, not an operational one. A later live pilot exercises the
   true two-token continuation over real time.
2. **Risk:** the driver reconciles (cancels) the executor's own first-15m jobs
   so the factory owns scheduling. This is deliberate and tested (no stale
   jobs), but it means the executor's activation-time tracking handoff and the
   factory's lifecycle scheduling are two ledgers bridged at handoff; a future
   simplification could have the executor activate slots without queuing its own
   first-15m jobs.
3. **Risk:** the exact 1h/4h close outcomes are the factory's proven contract
   (V2-4/V2-7/V2-8); this lane proves the pathway is reached via origin
   activation, not the factory internals, which its own suites lock.
4. No defect was found that would justify weakening any gate, the
   finalized-origin requirement, two-or-none activation, or any ceiling.

## 11. Readiness for one later V2-9.7E pilot rerun

**READY.**

The origin subsystem (V2-9.7E.6) and the memory lifecycle are now integrated
through a single internal governed driver, proven end to end offline: origin
activation feeds the lifecycle its exact activated identities, lifecycle starts
only on two-slot activation, identity is isolated and Scheduler-owned, no legacy
discovery runs, and all financial/retrieval locks hold. A later single live
pilot may now run the true two-token operational campaign over real time. The
live pilot itself was **not** run in this lane and is not claimed to have passed.

## 12. Stop boundary

V2-9.7E.8 ends PASS. No tag. No live pilot. V2-9.7F, V2-9.8, retrieval,
decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL were not begun.

## Dated correction — 2026-07-21 (V2-9.7E.9)

The E.8 implementation and its original focused tests passed, and that
historical result is preserved. Its integrated-proof verdict was nevertheless
incomplete: E.8 projected only one of the two activated identities into the
continuous harness, did not enable terminal 4h proof mode, and asserted that
1h/4h report structures existed instead of proving succeeded terminal 1h and
4h closes. Therefore E.8's original statement that the integrated two-token
campaign was ready for a live pilot was premature.

V2-9.7E.9 closes that proof gap with one exact two-slot campaign: both tokens
reach terminal 15m, one stops, one reaches terminal 1h and 4h, one authoritative
clean main-memory promotion is present, 5m remains support-only, cleanup and
zero-source replay are deterministic, and all locks remain intact. This
correction does not erase or reinterpret E.8's valid origin-to-lifecycle bridge;
it narrows the historical claim to what E.8 actually proved.