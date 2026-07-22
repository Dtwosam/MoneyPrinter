# V2-9.7E.11 Authoritative Live Operational Campaign Closeout

**Status:** IMPLEMENTATION AND OFFLINE PROOF COMPLETE — LIVE READINESS BLOCKED

**Baseline:** `75b22c51791d619dfb2f1746932743db082d544f`

## Verdict

`V2_9_7E_11_BLOCKED_LIVE_READINESS`

Implementation and the complete offline natural-evidence proof pass. Live
readiness authorization was already consumed by an earlier interrupted attempt
and must not be rerun, so the live-readiness cycle remains unproved and the
final V2-9.7E pilot must not run.

---

# Fail-closed repair attempt — 2026-07-22 (implementation + offline proof PASS)

## Todo / Checklist

- [x] Continue from the uncommitted E.11 working tree at `75b22c5`; preserve all
  completed results (lazy-decode Pump refactor, live campaign owner, natural
  disposition path, readiness harness, prior passing tests).
- [x] Defect 1 — explicit Source Governor approval + Central Scheduler ownership
  before every secondary transport; zero HTTP on denial/unavailability.
- [x] Defect 2 — reject dirty / `DO_NOT_TRAIN` / ineligible memory quality even
  when the mapped outcome is meaningful.
- [x] Defect 3 — readiness fails closed (starts non-ready; `READY` only on the
  full fixed-gate success).
- [x] Defect 4 — two-terminal-15m-close barrier before operational disposition.
- [x] Focused tests across the required surfaces; complete offline proof.
- [x] Live readiness treated as consumed — not rerun.

## The four repaired defects

1. **Governor approval before secondary transport.**
   `LiveSecondaryDiscoveryAdapter._get` now calls `_admit_source_request(...)`
   immediately before any transport. It re-validates canonical Source Governor
   availability and Central Scheduler ownership per request and, when the
   injected Governor exposes an `admit(source_name, request_kind)` decision hook,
   consults it and fails closed (`SECONDARY_REQUEST_DENIED`) on a falsy decision.
   A denied or unavailable owner makes **zero** HTTP calls. Request and
   underlying-operation accounting, and the zero-retry / zero-rotation /
   zero-reconnect / zero-successor / zero-restart guarantees, are unchanged.

2. **Reject dirty and `DO_NOT_TRAIN` evidence.**
   `NaturalEvidenceDispositionOwner.derive_from_labels` checks memory quality
   **before** the outcome. Only `CLEAN_MEMORY` / `PARTIAL_MEMORY` are eligible;
   any other quality — dirty, `DO_NOT_TRAIN`(`_MEMORY`), audit-only, stale,
   incomplete, mismatched, empty or unknown — returns
   `INELIGIBLE_15M_MEMORY_QUALITY` with no continuation, no support-only 5m
   capture, no trigger family and no promotion authority, regardless of a
   meaningful outcome such as `SHORT_TERM_PUMP`. No score, weight, rank,
   confidence or new threshold was added.

3. **Readiness fails closed.**
   `run_readiness_only` starts `NOT_READY` and only becomes `READY` after every
   fixed gate holds: finalized Pump origin accepted, activation gates complete
   (`terminal_status == COMPLETED`), exactly two atomic activated slots, all
   slots `SELECTED`, activated identities ⊆ finalized origin identities (exactly
   two distinct), disposable handoff succeeded (each activated slot's first-15m
   job cancelled), zero lifecycle windows scheduled after cleanup, and an
   identical zero-source replay. Zero, one, failed, partial, mismatched or
   non-atomic activation stays non-ready with the exact failing gate names in
   `summary["blocked_reasons"]`.

4. **Two-terminal-15m-close barrier.**
   In `one_command_15m_factory.py`, operational-natural disposition now waits
   until every activated token has terminal 15m close evidence. The first
   terminal close records itself and defers
   (`DEFERRED_PENDING_PEER_15M_CLOSE`) — it schedules no continuation and no
   support-only 5m. Once all activated tokens have closed, each is evaluated
   from its **own** governed 15m window via `_natural_disposition_schedule`,
   only the permitted continuation is enqueued, token identity and token-local
   results are preserved, and the earlier deferred close's persisted result is
   rewritten. Because every decision is token-local, the outcome is identical
   regardless of close-arrival order. No polling, retries, predeclared
   continuation token or fixture disposition was introduced. The E.9 compressed
   proof path is untouched (preserved in the `else` branch).

## Focused test results

All run with the repository interpreter; only minimum-sufficient focused suites.

- **E.11 suite** `test_v2_9_7e_11_authoritative_live_operational_campaign.py`:
  **40 passed** (25 preserved + 15 new). New proofs cover: Governor denial →
  zero secondary HTTP; missing Scheduler ownership → zero HTTP; unavailable
  Governor → zero HTTP; per-request individual admission; dirty +
  `SHORT_TERM_PUMP` blocked; `DO_NOT_TRAIN` + mapped outcome blocked; other
  ineligible quality blocked; clean/partial pump may continue; readiness
  non-ready for zero / one / transport-fault activation; readiness `READY` only
  on full two-slot atomic handoff + cleanup; first close alone schedules no
  continuation (spy proves scheduling runs only when both closes exist);
  per-window disposition close-order independence; barrier release leaves no
  deferred markers; the complete offline natural-evidence lifecycle proof
  (retrieval/financial deltas zero, one clean promotion, one support-only 5m).
- **Related suites (no regression):**
  - `test_v2_4_one_command_15m_factory.py`,
    `test_v2_9_7d_4a_token_local_selective_continuation.py`,
    `test_v2_9_7d_4b_conditional_support_only_5m_capture.py` — 42 passed.
  - `test_v2_9_7e_5_pump_origin_acquisition_architecture.py`,
    `test_v2_9_7d_7b_4d_combined_discovery_executor.py`,
    `test_v2_9_7d_6b_3_promotion_safety_integration.py`,
    `test_v2_9_7d_6b_6_final_campaign_report.py`,
    `test_v2_9_7d_6b_7_zero_source_read_only_replay.py`,
    `test_phase2_source_registry_governor.py` — 78 passed.
  - `test_v2_6_2_continuous_lifecycle.py`,
    `test_v2_9_7d_6b_4_lifecycle_rotation_integration.py`,
    `test_secondary_discovery_contract_fixtures.py`,
    `test_v2_9_7d_7b_4b_secondary_discovery_adapters.py` — 55 passed.
  - `test_v2_9_7e_8_origin_to_lifecycle_integration.py`,
    `test_v2_9_7e_9_two_token_continuous_lifecycle.py` — 20 passed (E.9
    compressed proof behaviour unchanged).

`git diff --check` clean; production/harness/scripts compile and import.

## Final offline proof

`NaturalOperationalLifecycleProofTests` runs the full two-token operational
campaign end to end through migration 036 on a disposable SQLite with a
deterministic clock over the real 15m/1h/4h/5m deadlines: two finalized origins
→ two atomic activations → both 15m closes → exactly one natural continuation to
terminal 1h and 4h, one naturally eligible support-only 5m capture, exactly one
authoritative clean promotion, zero dirty promotions, complete cleanup, and zero
retrieval/financial deltas, with a deterministic report and a zero-source replay.

## Readiness was consumed and not rerun

The interrupted readiness attempt is fail-closed as consumed. This continuation
therefore made no provider request, ran no reachability check, did not execute
the readiness harness, and does not claim a live-readiness PASS.

## Why live readiness remains unproved

The single authorized bounded readiness cycle is consumed and must not be rerun,
so no live end-to-end admission → transport → decode → merge/gates → atomic
disposable handoff has been demonstrated in this continuation. The offline proof
exercises every seam with transport-shaped fakes but cannot substitute for the
one consumed live cycle.

## Money-usefulness contribution

The lane hardens the only pathway that turns free-public live Pump/secondary
observations into governed, clean, promotable 15m memory: no ungoverned network
call can occur, only clean-eligible evidence can drive learning continuations,
readiness cannot silently pass, and both tokens' terminal evidence must exist
before any continuation commits Scheduler work — raising the quality and
trustworthiness of the memory the eventual paper-decision engine will consume,
while adding zero financial or retrieval surface.

## What remains locked

All Printer V1 Solana-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, and financial/retrieval locks remain
unchanged. No retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits or
PnL surface was added or activated.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk:** live readiness is unproved (authorization consumed); the final
  pilot must not run until a fresh authorized readiness cycle succeeds.
- **Setback:** the reversed-close-order end-to-end lifecycle proof is limited by
  order-sensitive context fixtures tuned to a single pump target; order
  independence is instead proven at the per-token evaluator the barrier uses at
  release (`derive_natural_disposition`), plus the spy proof that no scheduling
  occurs before both closes exist.
- **Efficiency blocker:** the barrier defers the first close's continuation
  until the peer closes, so both tokens' terminal 15m evidence must land before
  any 1h/4h/5m work is enqueued (correct fail-closed behaviour, not a defect).

## Explicit non-readiness for the final V2-9.7E pilot

**NOT READY for the final V2-9.7E pilot.** Implementation and offline proof are
complete, but live readiness is consumed and unproved. The multi-hour pilot,
V2-9.7F, V2-9.8, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits
and PnL remain out of scope and were not started.

---

# Continuation attempt — 2026-07-22

## Todo / Checklist

- [x] Verify exact baseline `75b22c5` and clean tracked tree/index.
- [x] Confirm the tooling can read tracked source and write the workspace.
- [x] Confirm live free-public network reachability (readiness prerequisite).
- [x] Re-audit the fixture/live boundary against the live source stack.
- [x] Map every composition seam the frozen design requires.
- [x] Identify the precise remaining implementation decision.
- [ ] Implement the frozen design completely — not completed this session.
- [ ] Prove natural dispositions offline — not reached (no production to prove).
- [ ] Run one bounded readiness-only live cycle — not reached.
- [x] Commit nothing incomplete; preserve prior evidence as dated history.

## What this attempt changes versus the prior blocked attempt

Two blockers that stopped the prior E.11 and the E.10 preflight are **no longer
present** in this environment:

1. **Tooling.** The prior attempt reported a Windows split-writable-root sandbox
   initialization error and `Access is denied` when patching tracked files
   through its patch service. In this session the standard file tools read
   tracked source normally and write the workspace (scratchpad files and this
   untracked closeout were written without error). Tracked-source *editing* was
   not exercised because no production edit was completed this attempt; the
   read + write evidence contradicts the prior hard tooling failure, but a
   clean tracked-source edit is not yet independently proven here.
2. **Network.** The one authorized readiness cycle needs bounded free-public
   live access. Reachability was confirmed read-only at preflight: Solana
   mainnet RPC and GeckoTerminal both answered `200`. No campaign, RPC decode,
   secondary enrichment, Scheduler work, activation, or lifecycle window was
   started; this was a single reachability check, not the readiness cycle.

The remaining obstacle is therefore **implementation completeness within one
session**, not capability, authorization, tooling, or network.

## Seam-level implementation map (verified against the live stack)

The frozen design composes existing owners; the audit confirmed each seam:

- **Live→existing envelope conversion.** `FixtureOperation`
  (`sources/pumpfun_origin.py`) and `FixtureSourceFact`
  (`discovery/combined_executor.py`) are governed *operation carriers*, not
  synthetic-only values. A live adapter converts raw transport responses into
  them and feeds `CombinedDiscoveryFixtures.direct_operations` /
  `gecko_ops` / `tracker_ops` / `dexscreener_ops`. Offline tests can inject
  transport-shaped raw responses through the same adapter — no disposition is
  injected.
- **Direct lane.** `CombinedPumpfunCampaignExecutor._run_direct_lane` already
  runs `run_acquisition_cycle(fixtures.direct_operations, prior_cursor=...)`,
  records confirmed origins, and preserves the cursor. The live Pump adapter
  supplies `direct_operations`; all decode/cursor/registry semantics stay in
  the existing owner.
- **Secondary lanes.** `_run_secondary_lane` + `_normalize_op` consume
  `FixtureSourceFact` bodies via the existing `normalize_gecko_trending`,
  `normalize_gecko_active`, `normalize_tracker_list`, and DexScreener
  normalizers. Request kinds/source names/base URLs are already defined in
  `sources/secondary_discovery.py` and `sources/dexscreener.py`.
- **Handoff.** `OriginToLifecycleCampaignDriver.run` (`origin_lifecycle_campaign.py`)
  mirrors exactly the two activated slots into the lifecycle batch and runs the
  factory once — identity-preserving, no reselection.
- **Natural disposition target.** The continuation/support-only-5m decision
  lives in `one_command_15m_factory.py` at the `WINDOW_CLOSE` seam
  (≈ lines 3309–3373). Today it is unconditional (ordinary one-token path) or
  predeclared (E.9 `CompressedTwoTokenProofPlan`). The support domain owner
  `scheduler/support_only_5m_capture.evaluate_support_only_5m_capture` already
  consumes `ordinary_movement`, `meaningful_transition_proven`, and
  `trigger_family` as inputs.
- **Existing classifier vocabulary.** `commands._derive_15m_window_context_from_snapshots`
  emits `held_to_15m_result_label`, `outcome_label`, and `micro_event_*`
  labels with all quantitative thresholds inside the `classify_*` functions.
  A `NaturalEvidenceDispositionOwner` is a **pure categorical map** from those
  existing labels to `{learning_need (continue/stop), trigger_family,
  ordinary_movement, meaningful_transition}`. No new score, weight, rank,
  confidence, or threshold is required — consistent with the design.
- **Proof harness.** `tests/test_v2_9_7e_8_*` (`_IntegrationBase`) and
  `tests/test_v2_9_7e_9_*` already stand up a migration-036 disposable DB and
  drive the full two-token 15m→1h→4h→promotion→report→replay→cleanup lifecycle.
  The E.9 comment confirms its support trigger is *natural evidence in the
  snapshots* (an observed 50% liquidity increase) that the plan merely relabels
  — so the natural path can derive it from the same snapshot evidence.

## Precise remaining implementation decision (new finding)

The frozen design says the live Pump adapter "creates the existing operation
envelope and delegates all admission, decoding, cursor, and continuity
semantics to `run_acquisition_cycle`." Implementing that against the current
owner exposes one under-specified tension:

`run_acquisition_cycle` wraps its operations in an **eager**
`FixtureOperationPort` (`self._operations = tuple(operations)`), and it pairs
each `getTransaction` response **positionally** with the `(slot, signature)`-
sorted `decode_queue` reference. Consequences:

- The adapter cannot fetch transactions lazily (the tuple is materialised up
  front), and it must supply `getTransaction` responses in exactly the sorted
  admitted order or the decoder will validate a transaction against the wrong
  reference.
- `assert_consumed()` forbids leftover operations, and `EARLY_CREATE_STOP`
  (8 observations) makes the *number* of consumed transactions depend on decode
  outcomes the adapter cannot know in advance.

To honour both "delegate all admission to `run_acquisition_cycle`" **and** "do
not duplicate existing origin logic," the correct resolution is a
behavior-preserving extraction inside `pumpfun_origin.py` of the admission/
ordering step into a pure helper (e.g. `plan_finalized_decode_queue`) used by
both `run_acquisition_cycle` and the live adapter, so the adapter knows exactly
which finalized signatures to decode and in what order without re-implementing
admission. This is *resolvable* — hence **not** a design contradiction — but it
edits the otherwise-locked Pump-origin module and must be re-verified against
that module's full existing test surface. That verification, plus the rest of
the build, exceeds what one session can complete and honestly prove.

## Why nothing was implemented or committed

The full deliverable is a new internal owner + two live transport adapters + a
natural-evidence disposition owner + a narrow factory change (operational-
natural mode, `WINDOW_CLOSE` derivation, budget branch, preflight mutual
exclusion with the E.9 plan) + real one-shot transports + a complete offline
natural-evidence proof (both terminal 15m outcomes, a naturally derived
continuation split, terminal 1h/4h, one clean promotion, zero dirty, positive
and negative 5m, deterministic report, zero-source replay, cleanup, and the
full failure matrix) + one bounded readiness cycle.

Producing that partially — without a genuinely passing offline proof — would
either mislabel unproven work as passing or leave the locked Pump-origin core
edited and unverified. Both violate this lane's discipline. Per the commit
policy, an incomplete implementation/offline-proof blocker is **not committed**;
no partial production, test, harness, migration, schema, database, payload,
secret, backup, or log was created. Only documentation was touched.

## Live adapters / composition / natural disposition / offline proof / readiness

Not implemented and not proven this session. No authoritative callable live
origin-to-lifecycle owner, no natural-evidence disposition owner, no offline
natural proof, and no readiness cycle are claimed. Current-lane operational use
is exactly zero: 0 campaigns, 0 source requests, 0 RPC/HTTP decode operations
beyond the single reachability check, 0 Scheduler rows, 0 activations, 0
lifecycle windows, 0 promotions, 0 retries, rotations, reconnects, successors,
or restarts, and 0 retrieval/financial deltas.

## Files and schema changes

Documentation only, uncommitted:

- `docs/printer-v1-v2-9-7e-11-authoritative-live-operational-campaign-design.md`
  (frozen; unchanged this attempt)
- `docs/printer-v1-v2-9-7e-11-authoritative-live-operational-campaign-closeout.md`
  (this file)

The uncommitted E.10 preflight closeout and the earlier E.11 blocked section
below are preserved unchanged. No schema change exists.

## Money-usefulness contribution

The lane keeps the fixture-proof / live-operational distinction intact,
disproves the prior tooling and capability blockers, and leaves a verified,
seam-level implementation map plus the one concrete architectural decision that
must be made first. It creates no memory and makes no live-readiness or profit
claim.

## What remains locked

The final V2-9.7E pilot; V2-9.7F/V2-9.8; retrieval; decisions; BUY/SELL/HOLD;
positions; trades; audits; PnL; wallet, keys, signing, funds, live execution;
paid APIs; scoring/ranking/confidence/weighting; embeddings/vectors;
Governor/Scheduler bypass; non-finalized origin; gate weakening; non-atomic
activation; 5m authority; automatic successor or restart.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Session-scope setback:** the complete implementation + full offline
   natural-evidence proof + readiness cycle exceeds one session; per policy no
   partial production is committed, so this attempt leaves no code behind.
2. **Locked-core edit required:** the correct live-Pump-adapter design needs a
   behavior-preserving extraction inside `pumpfun_origin.py`, re-verified
   against its full test surface before it can be trusted.
3. **No acceptance proof:** terminal 15m/1h/4h, natural continuation split,
   positive/negative 5m, clean promotion, report, replay, cleanup, and zero
   deltas remain unproved operationally.
4. **No live readiness fact:** current provider yield and gate funnel remain
   unknown; the authorized cycle was not consumed (only reachability checked).
5. **Efficiency:** stopping before writing unverifiable code avoided a
   mislabeled partial pass and an unverified edit to the locked Pump-origin
   core.

## Pilot readiness

**NOT READY.** Design is complete and the build is fully scoped, but
implementation, offline proof, and the bounded readiness cycle are not done.
The full pilot must not run.

## Commit and stop boundary

Per the commit policy for an incomplete implementation/offline-proof blocker,
this closeout is not committed and no tag is created. No later lane was started.

---

# Historical section — prior blocked attempt (tooling)

**Status at the time:** BLOCKED DURING IMPLEMENTATION

`V2_9_7E_11_BLOCKED_IMPLEMENTATION_OR_OFFLINE_PROOF`

## Fixture / Live Boundary Findings

The audit separated the baseline into reusable domain owners (Pump
create/create_v2 decoding, finalized signature-anchored acquisition, cursor,
immutable registry, provider normalizers, combined merge/gates/uniform
selection, atomic activation, E.8 handoff, lifecycle collectors, promotion,
reporting, replay, cleanup, Source Governor, and Central Scheduler); a missing
live transport; missing composition joining live intake to E.8; a missing
natural-evidence runtime; and proof-only surfaces (E.9 compressed two-token
mode, historical Pump proof harnesses, and the legacy GeckoTerminal factory
front end) that must stay proof-only.

## Implementation blocker (prior)

After renewed operator approval, new untracked modules could be created through
the standard patch service, but that service consistently failed before reading
any existing tracked source file with a Windows split-writable-root sandbox
initialization error, and invoking the patch helper against a workspace-local
patch failed with OS-level `Access is denied`. The frozen design requires a
narrow edit to the existing lifecycle owner; without that tracked edit the only
alternatives (duplicate the lifecycle owner or feed the E.9 compressed plan into
operational mode) contradict the frozen design and locks, so implementation
stopped. All partial production modules and the temporary workspace patch were
removed; no incomplete production, test, harness, migration, schema, database,
payload, secret, backup, or log remained.

> Note (2026-07-22): the tooling failure above did **not** reproduce in the
> continuation environment; tracked reads and workspace writes both succeed.
> The current blocker is implementation completeness within one session, not
> tooling.
