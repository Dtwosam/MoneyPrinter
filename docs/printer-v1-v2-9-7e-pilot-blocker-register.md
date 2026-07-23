# Printer V1 V2-9.7E Pilot Blocker Register

Cumulative register of blockers encountered on the road to a bounded two-token
full pilot. Created at V2-9.7E.39 (Full Pilot Attempt 1); updated at V2-9.7E.40
(Continuous Full-Pilot Repair/Restart Session).

## Legend

- **Category** — one primary category per blocker.
- **Current status** — `OPEN` / `PARTIAL` / `MITIGATED` / `FIXED` / `RESEARCH`.
- **Repair status** — `FIXED_IN_THIS_SPRINT` / `PARTIALLY_FIXED` /
  `NOT_FIXED_REPAIR_IDENTIFIED` / `NOT_FIXED_REQUIRES_DESIGN` /
  `NOT_FIXED_REQUIRES_RESEARCH` / `OBSERVE_NOT_YET_STRUCTURAL`.

## Cumulative field table

| Blocker ID | First seen | Most recent attempt | Category | Root cause | Fixed behavior | Remaining limitation | Fix commit | Offline proof | Live proof after fix | Repeated after fix | Current status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BL-39-01 | E.39 | E.40 | MISSING_INTEGRATION | `FULL_PILOT` (`run_operational`) never integrated the E.36-38 900s maturity boundary; it composed newest-create activation straight into lifecycle | E.40: `run_operational` applies the frozen 900s categorical maturity boundary + fail-closed `BLOCKED_INSUFFICIENT_MATURE_POOL` before any holder/lifecycle/memory work; distinguishes historical admission evidence from the forward WINDOW_15M | Does not guarantee two mature candidates on a cold-start attempt (see BL-39-03) | `68274a9` | `tests/test_v2_9_7e_40_full_pilot_admission.py` + regressions (E.11 54, maturity/readiness/pilot 45+5, origin 71) | Yes (Attempt 2 clean) | No | FIXED |
| BL-39-02 | E.35 | E.36-38 | DESIGN_GAP | No approved categorical snapshot-maturity boundary coordinated candidate age with the completed-exact-15m requirement (readiness mode) | 900s categorical maturity admission before holder/snapshot I/O in `SNAPSHOT_READINESS`; `BLOCKED_INSUFFICIENT_MATURE_POOL` for <2 mature | Applies to `SNAPSHOT_READINESS` only; does not guarantee mature-candidate supply | `f7f5d73` | `tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py` (16 passed, 5 subtests) + regressions (44 passed) | No | N/A | FIXED |
| BL-39-03 | E.34/E.35 | E.40 | CANDIDATE_SUPPLY | Full-pilot candidate universe consisted solely of the newest Pump create transactions (~170-243s old); no mechanism admitted older/staged candidates | E.40 admission (`68274a9`): newest-too-young creates categorically excluded, staged to registry, due reloaded zero-source. E.40 persistent pool: discovery-only durable pool retains confirmed origins across cycles, matures them categorically outside FULL_PILOT, and copies a bounded immutable DUE export into a fresh attempt for mixed-age mature supply | Discovery-channel diversity limited to direct LATEST_PUMPFUN; secondary trending/top/active coverage NOT proved (future operator decision); a live PASS needs ~15+ min maturation before 2 DUE | `68274a9` + `7dc0f62` + `3ab4bc2` | `test_v2_9_7e_40_full_pilot_admission.py` + `test_v2_9_7e_40b_persistent_candidate_pool.py` | Partial (mature admitted at Attempt 3) | No | PARTIAL |
| BL-40-01 | E.40 Attempt 1 | E.40 Attempt 1 | CODE_DEFECT | The E.40 fail-closed admission terminal returns a campaign `run_id` with no `printer_memory_factory_runs` row; the live pilot runner unconditionally called `_sup.attach_run`, which failed the supervision `run_id` foreign key | E.40 repair: `run_two_token_operational_pilot` skips `attach_run` and factory replay when `lifecycle_started` is False, finalizing supervision directly from the honest terminal (a pre-lifecycle block has no factory run to attach) | None known; a lifecycle that does start still attaches + replays as before | `47e76e8` | `tests/test_v2_9_7e_40_full_pilot_admission.py::BlockedFullPilotThroughRunnerTests` + E.14 (13 passed) | Yes (Attempt 2 clean) | No | FIXED |

## Fixed blockers

- **BL-39-01** — Full-pilot maturity integration. E.40 wired the frozen 900s
  categorical maturity boundary + fail-closed `BLOCKED_INSUFFICIENT_MATURE_POOL`
  into `run_operational` before any holder/lifecycle/memory work, and
  distinguished historical admission evidence from the forward `WINDOW_15M`.
  Proved offline; awaiting live confirmation at Attempt 1.
- **BL-39-02** — Snapshot maturity boundary for the `SNAPSHOT_READINESS` path.
  Fixed and proved offline at `f7f5d73`. Applies to readiness mode only.
  Note: an admission gate, not a supply repair —
  `Maturity admission boundary: FIXED`;
  `Mature-candidate supply productivity: PARTIAL` (BL-39-03).

## Partially fixed blockers

- **BL-39-03** — Candidate supply (structural, not observation-only). Two-stage
  repair:
  - E.40 admission (commit `68274a9`): newest, too-young creates can no longer be
    the active selection pool (categorically excluded by maturity); confirmed
    origins are staged into the durable registry; due staged origins reload
    zero-source. Proved live at Attempt 2.
  - E.40 persistent pool (operator-approved Option 1): a discovery-only
    persistent pool (existing `printer_pumpfun_finalized_origin_registry`,
    reused — no new table) retains confirmed origins across bounded acquisition
    cycles; they mature categorically through real wall clock / Scheduler-owned
    states outside `FULL_PILOT`; a bounded immutable DUE export is copied into a
    fresh isolated attempt DB, and the existing E.40 admission + combined
    selection produce two mature candidates. This supplies the mixed-age mature
    candidates a cold start could not.
  - **What is fixed:** the full-pilot candidate universe is no longer solely the
    newest creates, and a persistent mixed-age Pump-origin supply now exists.
  - **Remaining limitation (explicit):** discovery-channel diversity is still
    limited to the direct `LATEST_PUMPFUN` origin channel; trending/top/active
    secondary-channel candidate coverage is NOT proved by this repair and remains
    a separate future operator decision. A live Attempt 3 also requires ~15+
    minutes of real maturation time before two candidates are DUE.

## Open blockers

- None at the code level. The residual candidate-supply *sufficiency* for a
  cold-start PASS (BL-39-03 remaining limitation) is an operator policy decision,
  not an open code defect.

## Repeated blockers

- **BL-39-03** repeats the E.34/E.35 young-candidate observation. E.40 repaired
  the mechanism; the cold-start supply limitation persists structurally.

## Newly discovered blockers

- **BL-39-01** — first discovered at E.39 preflight, when the full pilot was
  first prepared against the maturity-boundary commit.

## Detailed entries

### BL-39-01 — FULL_PILOT missing maturity + readiness integration

- **First seen:** E.39. **Most recent attempt:** E.39.
- **Stage:** Phase 1 preflight (before any provider call).
- **Starting commit:** `f7f5d73f260cba58b2953fdf0efbc1b3b4d062d5`.
- **Campaign/run/cycle identity:** none created.
- **First terminal cause:** preflight requirement "FULL_PILOT uses the
  900-second maturity boundary and strict snapshot-readiness gate before
  lifecycle or memory" is not met by the committed `run_operational` path.
- **Exact status/error:** no error raised; the block is a static-verification
  refusal to launch. No provider call, authorization, or run identity created.
- **Evidence:** `run(mode=FULL_PILOT)` → `run_operational`
  (`authoritative_live_operational_campaign.py:1129-1241`) contains no
  `evaluate_snapshot_maturity` call, no `mature_candidates` filter, and no
  two-complete-bundle gate; `OriginToLifecycleCampaignDriver.run`
  (`origin_lifecycle_campaign.py:207-313`) begins the lifecycle immediately after
  activating two structural origin slots. The 900s boundary and the two-bundle
  gate exist only in `run_snapshot_readiness`
  (`authoritative_live_operational_campaign.py:1625-1806`). HEAD commit `f7f5d73`
  added the wiring to `run_snapshot_readiness` only (+74 runner lines).
- **Appeared before:** No. Newly discovered at E.39.
- **Category:** `MISSING_INTEGRATION` (with a `DESIGN_GAP` component: full-pilot
  maturity/readiness sequencing is undesigned).
- **Root cause — what Printer did:** would activate two ~3-4 minute-old origin
  candidates and begin a 15m/1h/4h lifecycle with no maturity or readiness gate.
- **Root cause — what Printer should have done:** apply the 900s categorical
  maturity boundary before holder/snapshot I/O, block if fewer than two mature
  candidates, and require the strict snapshot-readiness policy before lifecycle
  or memory work.
- **Why the difference:** the maturity boundary (E.36-38) and readiness gate
  (E.26-E.33) were built and proved only in `SNAPSHOT_READINESS`; the older
  `run_operational` full-pilot path was never integrated with them. Prior
  closeouts explicitly deferred full-pilot integration to a separate operator
  decision.
- **Isolated or repeatable:** structurally repeatable on every FULL_PILOT
  invocation of the committed runner.
- **Owner:** `run_operational` + `OriginToLifecycleCampaignDriver`.
- **Design already defines correct behavior:** No — E.36 design is scoped to
  `SNAPSHOT_READINESS` only.
- **Repair status:** `NOT_FIXED_REQUIRES_DESIGN`.
  - What was fixed: nothing.
  - Files changed: none.
  - Behavior changed: none.
  - Offline proof performed: none (no code change).
  - What was not fixed: full-pilot maturity + readiness gating.
  - Why it remains open: the correct fix depends on undecided full-pilot
    semantics (whether pre-lifecycle completed-15m bundles are required at all,
    how the 900s admission interacts with the lifecycle's own 15m window, and how
    a mature-pool shortage terminates a full pilot). Implementing without that
    design would invent policy.
  - Can it block the next attempt: Yes — it blocks any full pilot until the
    design is frozen and proved offline.

### BL-39-02 — Snapshot maturity boundary (readiness mode)

- **First seen:** E.35 (audit). **Most recent attempt:** E.36-38 (fix + proof).
- **Category:** `DESIGN_GAP` → resolved for readiness mode.
- **Root cause:** readiness mode admitted candidates by structure only; no
  categorical age boundary coordinated with the completed-exact-15m requirement.
- **Fixed behavior:** `evaluate_snapshot_maturity` enforces `block_time + 900s`;
  fewer than two mature candidates make zero holder/snapshot calls and yield
  `BLOCKED_INSUFFICIENT_MATURE_POOL`; two mature candidates traverse the exact
  readiness path.
- **Fix commit:** `f7f5d73`.
- **Offline proof:** `tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py`
  (16 passed, 5 subtests) plus directly affected regressions (44 passed), per the
  E.36-38 closeout.
- **Live proof after fix:** No. **Repeated after fix:** N/A.
- **Remaining limitation:** admission gate only; readiness mode only; does not
  guarantee mature-candidate supply (BL-39-03) and is not integrated into
  FULL_PILOT (BL-39-01).
- **Current status:** `FIXED` (readiness mode).

### BL-39-03 — Young-candidate supply

- **First seen:** E.34/E.35. **Most recent attempt:** E.35 (audit).
- **Category:** `CANDIDATE_SUPPLY`.
- **Root cause:** bounded newest-create Pump acquisition returns pools ~170-243s
  old across six live observations; selection cannot deliberately include older
  pools and the prior cursor favors newer creates.
- **Fixed behavior:** none. The maturity boundary makes the shortage explicit
  and honest but does not supply mature candidates.
- **Remaining limitation:** even a correctly gated full pilot may honestly block
  with fewer than two mature candidates.
- **Repair status:** `OBSERVE_NOT_YET_STRUCTURAL` — do not widen acquisition,
  add a source, wait, or retry. Requires a separately designed and offline-proved
  mature-candidate supply mechanism if the operator wants a non-blocking pilot.
- **Live proof after fix:** No. **Repeated after fix:** N/A.
- **Current status:** `OPEN`.

## E.40 repair updates

### BL-39-01 — repaired (E.40)

- **Stage:** full-pilot admission, before holder/lifecycle.
- **Category:** `MISSING_INTEGRATION`.
- **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **What was fixed:** `run_operational` now stages confirmed origins, reloads due
  staged origins, classifies the candidate universe with the frozen 900s
  `evaluate_snapshot_maturity`, keeps only `DUE` candidates as the active pool,
  and returns a clean `BLOCKED_INSUFFICIENT_MATURE_POOL` terminal
  (`run_status=NOT_STARTED`, `lifecycle_started=False`, zero forbidden deltas)
  when fewer than two mature candidates exist — before any holder, snapshot,
  lifecycle or memory work. Holder eligibility runs on the `DUE` set only.
- **Files changed:**
  `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
  `src/printer_v1/sources/pumpfun_origin.py` (`load_due_staged_origins`).
- **Design distinction:** the `SNAPSHOT_READINESS` completed-historical-15m gate
  is intentionally NOT copied — it would conflict with the lifecycle's own
  forward WINDOW_15M. Full-pilot pre-lifecycle readiness = mature + holder-eligible.
- **Offline proof:** `tests/test_v2_9_7e_40_full_pilot_admission.py` plus
  directly affected regressions (E.11 operational 54, maturity/readiness/pilot
  45+5 subtests, origin/registry 71, integration/E.8).
- **Can recur:** No — the gate is unconditional on the full-pilot path.
- **Live proof after fix:** pending Attempt 1.

### BL-39-03 — partially repaired (E.40)

- **Category:** `CANDIDATE_SUPPLY`.
- **Repair status:** `PARTIALLY_FIXED` (was the contradictory
  `OBSERVE_NOT_YET_STRUCTURAL`; the weakness is structural and now addressed at
  the mechanism level).
- **What was fixed:** the active selection pool can no longer consist solely of
  the newest creates — maturity categorically excludes the newest, too-young
  creates; confirmed origins are staged into the durable prospective-origin
  registry; previously staged origins now due are reloaded zero-source and
  unioned into the universe; channel/age composition is reported.
- **What was not fixed:** on a fresh isolated DB the staged pool is empty, so a
  cold-start attempt still usually has fewer than two due candidates. Guaranteed
  mature supply requires an adopted secondary discovery provider (with live
  origin verification) or a persistent cross-run staged pool.
- **Why it remains partial:** both remaining options are operator decisions (new
  provider/contract; a materially different persistence policy), out of scope for
  a same-session narrow repair.
- **Offline proof:** staging-reload and partition assertions in
  `tests/test_v2_9_7e_40_full_pilot_admission.py`.
- **Can recur:** the cold-start supply limitation recurs by construction until an
  operator decision resolves supply sufficiency.

### BL-40-03 — pool-seeded origin re-record layout conflict (E.40 Attempt 3)

- **Attempt/stage:** Attempt 3, combined executor origin re-record, before any
  observation/selection.
- **Starting commit:** `61fe119`. **Execution id:** `e40-attempt3-20260723T174343Z`.
- **First terminal cause:** `CombinedDiscoveryError(ORIGIN_REGISTRY_CONFLICT)`
  from the executor, surfaced by the driver as `ACTIVATION_FAILED`.
- **Evidence:** the 8 pool origins were `PUMP_CREATE_V2`; the executor
  reconstructs `PumpCreateObservation` from the reduced `FixtureOriginProof`,
  which dropped `create_layout` and defaulted to `PUMP_CREATE_V1`. Re-derived
  `evidence_hash` differed from the verbatim-seeded rows for all 8, so
  `record_confirmed_origin` raised `ORIGIN_REGISTRY_CONFLICT`. Reproduced offline
  (8/8 hash mismatch).
- **Category:** `CODE_DEFECT`.
- **Root cause:** `FixtureOriginProof` (and `load_due_staged_origins`) did not
  carry `create_layout`, so any round-trip through the reduced proof shape lost
  the layout and conflicted with the verbatim confirmed-origin registry rows.
- **Repair status:** `FIXED_IN_THIS_SPRINT`. `create_layout` is now carried by
  `FixtureOriginProof`, returned by `load_due_staged_origins`, propagated by
  live acquisition and the `run_operational` reload, and used in the executor's
  reconstruction. The re-record is now idempotent for a matching origin.
- **Files changed:** `combined_executor.py`,
  `authoritative_live_operational_campaign.py`, `pumpfun_origin.py`.
- **Offline proof:**
  `tests/test_v2_9_7e_40b_persistent_candidate_pool.py::test_reloaded_v2_origin_rerecord_is_idempotent`
  plus combined-executor / origin regressions.
- **Can recur:** No for this cause. **Live proof after fix:** NOT yet — the
  three-attempt ceiling is reached; a 4th attempt requires operator authorization.

### BL-40-04 — pilot runner no-atomic-activation robustness (E.40 Attempt 3)

- **Attempt/stage:** Attempt 3, post-`run_operational`, at the run-identity check.
- **First terminal cause:** `PilotRunnerError("pilot campaign returned no run
  identity")` — the driver's `ACTIVATION_FAILED`/`NO_ATOMIC_ACTIVATION` terminal
  returns no `run_id`, and the runner unconditionally required one.
- **Category:** `CODE_DEFECT` (framework robustness).
- **Root cause:** the pilot runner assumed any non-pre-lifecycle terminal has a
  factory run id; a legitimate activation-failed terminal has none.
- **Repair status:** `FIXED_IN_THIS_SPRINT`. The runner now requires `run_id`
  only when `lifecycle_started` is True; otherwise it finalizes supervision from
  the honest terminal report (governed safe stop), like a pre-lifecycle block.
- **Files changed:** `two_token_operational_pilot_runner.py`.
- **Offline proof:**
  `tests/test_v2_9_7e_40_full_pilot_admission.py::BlockedFullPilotThroughRunnerTests::test_activation_failed_terminates_cleanly`.
- **Can recur:** No — the pre-run-identity path is explicit and tested.
- **Live proof after fix:** NOT yet (ceiling reached).

### BL-40-02 — maturity-before-cap ordering (E.40 pool integration, static)

- **Found by:** static inspection while wiring the persistent pool into Attempt 3
  (before spending the attempt).
- **Category:** `CODE_DEFECT`.
- **Root cause:** the E.40 admission applied the candidate cap (3) to the
  identity-sorted union of live young creates + reloaded due origins *before*
  classifying maturity. With more young creates than the cap, the young mints
  (by base58 identity order) could displace the categorically due candidates, so
  a pool with two due candidates could still block.
- **Repair status:** `FIXED_IN_THIS_SPRINT`. Extracted `_mature_admission`,
  which deduplicates, classifies 900s maturity over the whole universe, and then
  admits up to the candidate cap from the DUE subset only — immature candidates
  never consume a cap slot.
- **Files changed:** `authoritative_live_operational_campaign.py`.
- **Offline proof:**
  `tests/test_v2_9_7e_40_full_pilot_admission.py::MaturityBeforeCapTests`
  (five young + two due survive a cap of 3; >cap due is bounded) plus E.11
  operational regression (43 with the pool suite).
- **Can recur:** No — maturity precedes the cap and is unit-tested.
- **Live proof after fix:** pending Attempt 3.

### BL-40-01 — pilot runner pre-lifecycle block defect (E.40 Attempt 1)

- **Attempt/stage:** Attempt 1, post-`run_operational`, at `attach_run`.
- **Starting commit:** `68274a9`. **Execution id:** `e40-attempt1-20260723T170534Z`.
- **First terminal cause:** `sqlite3.IntegrityError: FOREIGN KEY constraint
  failed` at `proof_supervision.attach_run`. Attempt 1 did NOT terminate cleanly.
- **Evidence:** Attempt 1 reached live acquisition and the new admission gate,
  which returned a fail-closed `BLOCKED_INSUFFICIENT_MATURE_POOL` terminal with
  `run_id="pilot-run"`. The live pilot runner then called `attach_run`, whose
  supervision `run_id` FK references `printer_memory_factory_runs`; no factory
  run exists for a pre-lifecycle block, so the FK failed and the process raised.
- **Category:** `CODE_DEFECT` (integration of the new admission terminal with the
  committed supervision/pilot-runner contract).
- **Root cause:** the pilot runner assumed `run_operational` always starts a
  factory lifecycle run; the E.40 admission gate legitimately blocks before any
  factory run.
- **Repair status:** `FIXED_IN_THIS_SPRINT`.
  - **Fixed:** `run_two_token_operational_pilot` now skips `attach_run` and the
    factory replay when `lifecycle_started` is False, finalizing supervision
    directly from the honest terminal report; it surfaces `full_pilot_admission`.
  - **Files changed:** `two_token_operational_pilot_runner.py`.
  - **Offline proof:** new
    `tests/test_v2_9_7e_40_full_pilot_admission.py::BlockedFullPilotThroughRunnerTests`
    drives the runner with a pre-lifecycle fail-closed owner and asserts a clean
    governed-safe-stop terminal, released lock, deterministic zero-source replay,
    and no attach/FK error; E.14 pilot-runner suite (13) still passes.
  - **Can recur:** No — the pre-lifecycle branch is now explicit and tested.
- **Live proof after fix:** pending Attempt 2.

## E.40 live attempt log

| Attempt | Commit | Execution id | Terminal | First cause | Notes |
|---|---|---|---|---|---|
| 1 | `68274a9` | `e40-attempt1-20260723T170534Z` | not clean (exception) | `attach_run` FK failure (BL-40-01) | Reached live acquisition + admission; blocked, but pilot runner raised on the pre-lifecycle terminal. Repaired at `47e76e8`. |
| 2 | `47e76e8` | `e40-attempt2-20260723T171456Z` | `GOVERNED_SAFE_STOP` (clean) | `BLOCKED_INSUFFICIENT_MATURE_POOL` (CANDIDATE_SUPPLY) | 8 confirmed origins staged; universe 3, all IMMATURE (ages 118-121s; block_times ~2026-07-23T17:12Z). mature=0. Channels: LATEST_PUMPFUN 8, GECKO_TRENDING 2, DEXSCREENER 1, STAGED_DUE 0. integrity ok, FK 0, all forbidden-capability counts 0, replay deterministic zero-source, lock released. |
| 3 | `61fe119` | `e40-attempt3-20260723T174343Z` | blocked, not clean (defects) | `ACTIVATION_FAILED` / `ORIGIN_REGISTRY_CONFLICT` (BL-40-03); pilot runner raised on no run_id (BL-40-04) | Pool populated (8 origins), matured through Scheduler-owned states OUTSIDE FULL_PILOT (~15 min), 8 DUE. Fresh attempt seeded with the bounded DUE export (8 copied). **Maturity/supply repair worked: mature candidates were admitted past the 900s gate.** But the executor's reduced-shape re-record of the seeded `PUMP_CREATE_V2` origins used a default `PUMP_CREATE_V1` layout → evidence-hash conflict → `ACTIVATION_FAILED`; no tokens/pairs/slots. All forbidden-capability counts 0. |

**Attempt 2 interpretation:** live proof that the E.40 repair works end-to-end —
the full pilot applies the 900s maturity boundary, stages confirmed origins, and
fails closed honestly with zero holder/lifecycle/memory/financial work when no
candidate is mature. The block is the BL-39-03 structural cold-start supply
limitation: real Pump creates are ~2 minutes old and a fresh isolated DB has an
empty staged pool. No narrow code repair can supply two mature candidates on a
cold start; resolution is an operator decision (persistent cross-run staged pool
or an adopted secondary discovery provider with live origin verification).

## Cross-attempt guidance

- Do not describe the maturity admission gate as a supply repair.
  `Maturity admission boundary: FIXED (full pilot + readiness)`;
  `Mature-candidate supply productivity: PARTIAL (cold-start still blocks)`;
  `FULL_PILOT maturity integration: FIXED (E.40)`.
- A cold-start full pilot on a fresh DB is expected to close honestly with
  `BLOCKED_INSUFFICIENT_MATURE_POOL` unless live throughput happens to place two
  bounded creates past the 900s boundary. That is an honest supply outcome, not
  a code defect; do not retry, wait, widen acquisition, or add a source.
