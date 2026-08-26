# Printer V1 — V2-9.8B 15m→1h Campaign-Window Bind-Order Repair Closeout

Date: 2026-08-26

Verdict: `V2_9_8B_15M_TO_1H_BIND_ORDER_REPAIR_CLOSEOUT_PASS`

## Scope

This closeout covers only the proven `WINDOW_15M` → selective `WINDOW_1H` false-dirty bind-order defect discovered from the consumed Aug-26 four-token Standard-4H campaign.

It does not close the separate Cycle-2 frozen-lane failure, does not prove live 1h or 4h progression, and does not authorize another operational campaign.

Permanent Printer V1 locks remain unchanged.

## Proven incident

Consumed campaign:

- execution: `20260826T120605Z-89a8c95b155f`
- campaign: `20260826T120605Z-89a8c95b155f-campaign`
- run: `20260826T120605Z-89a8c95b155f-campaign-run`
- consumed authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T114542Z_d3bc361a`

The authorization is permanently non-reusable.

The Aug-26 readiness audit proved that both Cycle-1 physical `WINDOW_15M` rows initially classified `CLEAN_MEMORY / CLEAN_DATA / do_not_train=0`. The optional safety values `LIQUIDITY_LOCK_OR_BURN_UNKNOWN` and `KNOWN_RISK_FLAGS_UNKNOWN` were lawful 15m-acceptable UNKNOWNs and were not the blocker.

The actual defect was ordering:

```text
physical WINDOW_15M close/audit = CLEAN
→ E2Z / Lane Q consumed campaign cadence authority
→ campaign-window memory_window_row_id had not yet been bound
→ CAMPAIGN_WINDOW_BINDING_MISSING
→ Lane K downgraded the otherwise-clean physical memory
→ selective WINDOW_1H saw a dirty/ineligible predecessor
→ WINDOW_1H was not created
```

Classification: `COMMITTED_CODE_DEFECT`.

## Approved design

Design verdict: `V2_9_8B_15M_TO_1H_BIND_ORDER_DESIGN_PASS`.

Selected design: identity binding is separated from terminal/outcome registration.

Canonical order:

```text
physical WINDOW_15M close/audit
→ resolve exact campaign ownership
→ bind the pre-created campaign WINDOW_15M to the exact physical memory row
→ commit + durable readback
→ E2Z / Lane Q
→ Lane K only for a genuine blocker
→ existing terminal registration/reconciliation
→ existing selective WINDOW_1H evaluation
```

The repair must not weaken Lane Q, weaken Lane K, force continuation, reinterpret optional safety UNKNOWNs, add providers, change Scheduler/Source Governor behavior, or create a migration.

## Implementation

Parent:

`cc4324fc05c98d5a19808e4ad693c7c4e2a9e51e`

Implementation commit:

`9fd1378c7d5c42060b344cfc0d48de0a79c8cc5f`

Subject:

`Repair 15m campaign-window bind ordering`

Changed production files:

1. `src/printer_v1/operator_cli/one_command_15m_factory.py`
2. `src/printer_v1/operator_cli/operational_selective_1h.py`

Regression file:

3. `tests/test_v2_9_8b_15m_to_1h_campaign_window_bind_order.py`

No migration was added.

The implementation adds an identity-only early bind for campaign-owned 15m closes. It requires one exact pre-created campaign `WINDOW_15M`, validates campaign/run/cycle/slot/token/pair/window identity, uses the existing compare-and-set `bind_window_memory_row_id`, commits before E2Z, and verifies durable readback. It does not alter `window_state`, `first_terminal_cause`, `terminal_at`, physical memory quality, `do_not_train`, promotion, or continuation state.

Non-campaign 15m closes remain outside this bind path.

## Independent bounded proof

Proof verdict:

`V2_9_8B_15M_TO_1H_BIND_ORDER_BOUNDED_PROOF_PASS`

### Parent RED

A disposable worktree at exact parent `cc4324fc...` received only the new regression test.

Primary incident regression:

`BindOrderTests::test_production_close_binds_before_lane_q_and_does_not_false_dirty`

Meaningful parent failure:

`AssertionError: None != 1`

At the E2Z/Lane-Q boundary, `memory_window_row_id` was still `NULL` while the physical memory row was id `1`. This reproduced the old producer-before-consumer defect; it was not an import, fixture, schema, dependency, or harness error.

### Current GREEN

Against exact implementation commit `9fd1378...`:

- bind-order regression file: `6/6 PASS`
- neighboring focused suites: `36 PASS`

Covered behavior includes:

- exact bind exists before Lane Q;
- absent/mismatched identity still fails closed;
- conflicting rebind is rejected;
- exact rebind is idempotent;
- genuine Lane-Q blockers still dirty through Lane K;
- dirty predecessors do not force `WINDOW_1H`;
- later terminal registration reuses the exact early binding.

Two unrelated pre-existing baseline test failures were reproduced identically on parent `cc4324fc...` and were not introduced or repaired by this lane:

- `test_e2z_promotes_clean_1h_once`
- `test_selective_two_token_factory_ceilings_are_cadence_derived`

They remain separate evidence, not grounds to reopen this repair.

## Database and runtime invariants

Authoritative DB:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

SHA-256 before and after proof:

`7f3e725fb435c24c507f6e12fbee26789472017e6e0c63361404ab6589f7128c`

Verified:

- `PRAGMA integrity_check = ok`
- `PRAGMA foreign_key_check = 0 rows`
- no authoritative WAL/SHM/journal residue from proof
- provider calls = 0
- RPC calls = 0
- WebSocket calls = 0
- live Scheduler runtime launches = 0
- live Printer starts = 0
- new authorizations = 0
- consumed authorization reuse = 0

The proof used disposable/offline fixtures only.

## What is now closed

The following statement is proven:

> A legitimate clean campaign-owned `WINDOW_15M` is no longer falsely dirtied solely because its own exact campaign-window-to-memory-row binding was written after Lane Q consumed it.

The repair preserves fail-closed behavior for genuinely absent, ambiguous, mismatched, or conflicting bindings.

## What is not proven or unlocked

This closeout does not prove automatic `WINDOW_1H` continuation, live 1h/4h progression, four-token 4/2/2 success, or Cycle-2 admission success.

No financial/retrieval capability is unlocked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Remaining separate operational issue

The Aug-26 consumed run also failed to admit Cycle 2 with:

- terminal cause: `LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED`
- producer: `FROZEN_LANE_CLASSIFICATION`
- phase: `FROZEN_CARRIER`
- reason: `FROZEN_TRACKING_LANE_UNAVAILABLE`
- category: `APPLICATION_VALIDATION`

Cycle 2 never became a persisted campaign cycle. The exact selected classifier-input pair was not durably persisted as attempt items, so the evidence does not yet prove a committed classifier defect.

## Next permitted action

`V2-9.8B CYCLE-2 FROZEN-LANE CLASSIFIER-INPUT READINESS AUDIT ONLY`

No live run, new authorization, successor, retry, or Cycle-2 implementation is permitted before that audit and any required design/proof sequence.

## Closeout state

- audit/readiness: PASS
- design/specification: PASS
- implementation: PASS at `9fd1378c7d5c42060b344cfc0d48de0a79c8cc5f`
- independent bounded proof: PASS
- closeout: PASS
- migration: none
- authoritative DB mutation: none
- financial/retrieval unlocks: none

Final verdict:

`V2_9_8B_15M_TO_1H_BIND_ORDER_REPAIR_CLOSEOUT_PASS`
