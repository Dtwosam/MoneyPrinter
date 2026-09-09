# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-cycle1-cycle2-four-hour-admission-proof`.

Latest fully verified code/test HEAD before this handoff-only update:
`8c47c0833227f1181e5ff12045ea9dd02cf22cbc`.

GitHub Actions run `34384741151` is green on that HEAD:

- focused post-holder/reconciliation boundary: **29 passed**;
- shared discovery/admission/two-cycle Standard-4H boundary:
  **399 passed, 2 deselected, 32 subtests passed**;
- affected-module compile: passed;
- diff whitespace check: passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is
the sole governed source-request owner and Central Scheduler is the sole
Scheduler owner. Retrieval, decision, position, PnL, signing, wallet and live
trading capabilities remain locked. `WINDOW_5M_MICRO_EVENT` is support-only;
`WINDOW_12H` and `WINDOW_24H` remain locked.

The verified path now explicitly includes Cycle 1 and Cycle 2 together:

- Cycle-1 admission is owned by the real
  `CombinedPumpfunCampaignExecutor`, not by pre-seeded test slots;
- Cycle 1 requires exactly two candidates and atomically commits both token/pair
  identities, tracking-queue claims, selected slots and first-15m Scheduler
  handoffs;
- failure before slot 1, during slot 2, or during the second Scheduler handoff
  rolls the entire Cycle-1 admission back;
- the production origin->lifecycle bridge reads the two durable Cycle-1 slots,
  cancels the executor's superseded first-15m jobs, and materializes an
  identity-preserving factory selection batch with no reselection;
- the Standard-4H integration proof begins from an empty Cycle-1 shell, executes
  real Cycle-1 admission, then admits a fresh/disjoint Cycle 2 through the
  authoritative later-cycle `PAIR_READY -> CONSUMED` owner;
- Cycle-1 activation mint/pair identities are required to match the durable
  Cycle-1 slots, materialized selection rows, tracking lanes, factory run steps
  and Standard-4H progression rows;
- Cycle 2 remains campaign-history-disjoint from Cycle 1 and is admitted as an
  exact two-slot atomic pair;
- the resulting campaign has exactly four distinct token/pair targets across
  exactly two cycles;
- both cycles own exactly two `WINDOW_15M`, two `WINDOW_1H`, and two
  `WINDOW_4H` lifecycles, for four physical 4h memory windows total;
- every physical 4h window stays bound to its exact cycle, slot, token and pair;
- both cycles reach the shared Standard-4H terminal path together;
- clean-memory promotion remains quality-gated and preserves exact physical
  window identity in episodes/fingerprints;
- the integrated four-token run creates no retrieval, paper-decision, position,
  trade-event or trade-audit activity.

The earlier generic discovery/admission repairs remain covered by the same green
shared suite: exact-two supply, generic non-Pump present-pool verification and
protocol->market resume, exact source accounting, MOE recreation, Pump-only
legacy projections, and the lawful-work false-shortage guard.

## Latest meaningful result

The previous full four-token audit pre-created Cycle-1 slots, so it proved the
two-cycle 4h lifecycle but did not prove that the real Cycle-1 admission owner
could feed that lifecycle.

That shortcut is removed in the strengthened disposable proof. The test harness
can now start with only an empty Cycle-1 campaign shell. The real combined
executor creates Cycle-1 token/pair rows, tracking authority and two slots; the
production materialization bridge then feeds those exact identities into the
same factory that admits Cycle 2 and runs both cycles through Standard-4H.

The first strengthened CI run exposed only a test-harness API mistake: the
low-level executor returns `CampaignExecutionResult`, while `activated_slots`
belongs to the higher-level driver result. The proof was corrected to read the
durably committed Cycle-1 slots through the same `_read_activated_slots` owner
used by the production bridge. No production defect or runtime code change was
required.

## Proven blocker

None remains in the scoped Cycle-1 admission + Cycle-2 admission + joint
Standard-4H memory engineering lane.

This is **not** operational authorization and does not establish authoritative
database or live-run readiness. No operational Printer run, live provider/RPC
execution, Scheduler operation, or authoritative database mutation was
performed.

Default branch `master` remains historically divergent from this active
development lineage and is not a safe blind merge/rebase target.

## Exact next permitted action

Begin the next narrow read/test-only boundary from this green state, or resolve
the intended active integration lineage for this branch. A logical downstream
engineering boundary is clean-memory -> retrieval/paper-decision lockout.

Do not run Printer operationally or mutate the authoritative database without a
new explicit authorization boundary.
