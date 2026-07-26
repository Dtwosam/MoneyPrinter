# Printer V1 V2-9.7E Pilot Blocker Register

Cumulative register of blockers encountered on the road to a bounded two-token
full pilot. Created at V2-9.7E.39 (Full Pilot Attempt 1); updated at V2-9.7E.40
(Continuous Full-Pilot Repair/Restart Session), V2-9.7E.41 (Graduation-Only
Selection and Mixed-Channel Discovery Repair), and V2-9.7E.42 (Direct Pump
Migration Discovery and Graduated-Candidate Supply Repair — BL-41-04 direct channel
now operational; BL-42-01 added and fixed), V2-9.7E.43 ($3K Graduated
Discovery and Selection Front-Door Repair — exact-pool liquidity floor added;
BL-43-01 live discovery-window supply tuning recorded), V2-9.7E.45 (canonical
graduated supply + graduation-native activation), V2-9.7E.46 (canonical
two-token full-pilot execution; BL-46-01 holder-source environment blocker),
V2-9.7E.47 (lifecycle + clean-memory repair), and the post-E.47 bounded full-pilot
proof (`V2_9_7E_POST_E47_FULL_PILOT_PASS`).

> **V2-9.7E.41 supersession note.** The E.40 900-second maturity-based
> full-pilot admission policy (BL-39-01, BL-39-03) is preserved as historically
> implemented but is **superseded** by the E.41 graduation-only tracking law. Age
> is context, not eligibility. Old live-attempt facts are not rewritten; the
> maturity gate remains intact only in `SNAPSHOT_READINESS`.

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
| BL-41-01 | E.41 | E.41 | INCORRECT_ELIGIBILITY | `FULL_PILOT` used the categorical 900-second Pump-origin maturity boundary as the selection gate; the direct `LATEST_PUMPFUN` channel yields only pre-graduation bonding-curve creates, so the gate admitted **aged ungraduated (bonding-curve) tokens** — a violation of the graduation-only tracking law | E.41: `run_operational` replaces `_mature_admission` (900s) with `_graduated_admission` (exact PumpSwap graduation); the honest terminal is `BLOCKED_INSUFFICIENT_GRADUATED_POOL`; the 900s gate is removed from FULL_PILOT and retained only in `SNAPSHOT_READINESS` | No graduated-discovery channel is operationally wired for fresh live discovery, so cold-start FULL_PILOT honestly blocks `BLOCKED_INSUFFICIENT_GRADUATED_POOL` | `<repair commit>` | `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py` + updated E.40 admission suite | No (offline lane) | No | FIXED |
| BL-41-02 | E.41 | E.41 | INCORRECT_ELIGIBILITY | Discovery-only lifecycle states (`PUMP_CREATED_UNPAIRED`, `PUMP_BONDING_CURVE_ACTIVE`, `PUMP_MIGRATION_OBSERVED` without confirmation, `PUMP_LIFECYCLE_UNKNOWN`, `DISCOVERED_UNPAIRED`) could reach pilot supply and selection: the executor `LIFECYCLE_MARKET` gate rejected only a candidate *claiming* GRADUATED without confirmation, and the E.40 persistent pool exported aged ungraduated origins as "candidates" | E.41: the executor `LIFECYCLE_MARKET` gate fails closed any candidate that is not `PUMPSWAP_GRADUATED_CONFIRMED` + `pumpswap_state==CONFIRMED` + a valid PumpSwap market identity; `_select` re-drops non-graduated; the persistent pool separates pending-discovery origins from a graduation-gated `export_graduated_pilot_candidates` (empty for bare origins); PumpSwap confirmation rebinds the tracking market identity to the confirmed pool | Graduated candidates must be supplied with confirmed PumpSwap evidence; no operational fresh-discovery graduated channel yet | `<repair commit>` | `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py`; `test_v2_9_7e_40b_persistent_candidate_pool.py`; combined-discovery suites | No (offline lane) | No | FIXED |
| BL-41-03 | E.41 | E.41 | DISCOVERY_CONCENTRATION | Selection could concentrate on latest-only candidates; the old `_select` lifecycle-rank had no categorical distribution and could pick two latest candidates | E.41: `_categorical_two_slot` enforces that when at least one latest-only and one non-latest eligible graduated candidate exist, the two slots are not both latest-only (one latest + one non-latest by durable seeded categorical round-robin); deterministic seeded uniform within each category; multi-channel duplicates are one candidate with no boost | Applies only when both partitions have eligible **graduated** candidates; with a single available category it degrades honestly | `<repair commit>` | `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py::CategoricalDistributionTests` | No (offline lane) | No | FIXED |
| BL-41-04 | E.41 | E.41 | BLOCKED_CONTRACT | Trending/top/active graduated-discovery channels (GeckoTerminal, Solana Tracker, PumpPortal migration feed) are not adopted/operationally permitted, so no operational channel supplies already-graduated Pump tokens for fresh live discovery | E.41: the channels remain explicitly `SKIPPED_BLOCKED_CONTRACT` and visible in the admission report; none is silently activated; no paid dependency added; DexScreener active-market enrichment and PumpSwap confirmation remain operational per contract | Fresh-discovery graduated supply remains unavailable until a graduated-discovery contract is adopted or a migration-signature locator is supplied — a future operator decision | `<repair commit>` | `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py::FullPilotNoMaturityGateTests::test_blocked_channels_remain_visible` | No (offline lane) | N/A | OPEN (contract) |

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

## V2-9.7E.41 repair updates (graduation-only selection and mixed discovery)

E.41 froze the **Printer V1 Graduation-Only Tracking Law**: a Pump.fun token is
selection-eligible only after exact governed evidence confirms graduation and
binds its exact mint to one valid post-graduation PumpSwap market identity. Age
is context, not eligibility. This supersedes the E.40 900-second maturity-based
full-pilot admission policy, which is preserved as historically implemented.

### BL-41-01 — incorrect 900-second FULL_PILOT age gate

- **Category:** `INCORRECT_ELIGIBILITY`. **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `run_operational` used the categorical 900-second Pump-origin
  maturity boundary as the selection gate. The direct `LATEST_PUMPFUN` channel
  yields only pre-graduation bonding-curve creates, so the gate admitted aged,
  ungraduated (bonding-curve) tokens — a graduation-only-law violation.
- **What was fixed:** `run_operational` replaces `_mature_admission` (900s) with
  `_graduated_admission` (exact PumpSwap graduation). The honest terminal is
  `BLOCKED_INSUFFICIENT_GRADUATED_POOL`. The 900s gate is removed from FULL_PILOT
  and remains intact only in `SNAPSHOT_READINESS`. Confirmed origins are still
  staged as pending discovery evidence.
- **What remains unfixed:** no operational graduated-discovery channel supplies
  fresh graduated candidates (BL-41-04), so cold-start FULL_PILOT honestly blocks.
- **Tests:** `tests/test_v2_9_7e_41_graduation_only_mixed_discovery.py`
  (`FullPilotNoMaturityGateTests`, `GraduationClassifierTests`); updated E.40
  admission suite.
- **Can block next pilot:** Yes — until a graduated-discovery supply exists,
  cold-start FULL_PILOT blocks honestly. This is a correct outcome, not a defect.
- **Operational channel coverage after repair:** PumpSwap on-chain confirmation
  operational (confirmation-only); direct channel is pending-discovery only.

### BL-41-02 — unpaired/bonding-curve candidates reaching pilot supply

- **Category:** `INCORRECT_ELIGIBILITY`. **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** the executor `LIFECYCLE_MARKET` gate rejected only a candidate
  claiming `GRADUATED` without confirmation, so discovery-only states
  (`PUMP_CREATED_UNPAIRED`, `PUMP_BONDING_CURVE_ACTIVE`,
  `PUMP_MIGRATION_OBSERVED` without confirmation, `PUMP_LIFECYCLE_UNKNOWN`,
  `DISCOVERED_UNPAIRED`) passed selection; the E.40 persistent pool exported aged
  ungraduated origins as "candidates".
- **What was fixed:** the `LIFECYCLE_MARKET` gate fails closed any candidate that
  is not `PUMPSWAP_GRADUATED_CONFIRMED` + `pumpswap_state==CONFIRMED` + a valid
  PumpSwap market identity; `_select` re-drops non-graduated; PumpSwap
  confirmation is now per-mint and rebinds the tracking market identity to the
  confirmed pool; the persistent pool separates pending-discovery origins from a
  graduation-gated `export_graduated_pilot_candidates` (empty for bare origins).
- **What remains unfixed:** graduated candidates must be supplied with confirmed
  PumpSwap evidence; there is no persisted graduated-candidate store yet.
- **Tests:** `test_v2_9_7e_41_...::SelectGraduationOnlyTests`,
  `GraduationClassifierTests`; `test_v2_9_7e_40b_persistent_candidate_pool.py`;
  combined-discovery suites (7B.4d/4d.1/5) now run on graduated candidates.
- **Can block next pilot:** No — it removes an unlawful path; it cannot itself
  block a lawful graduated candidate.
- **Operational channel coverage after repair:** unchanged; the gate is enforcement.

### BL-41-03 — latest-only discovery concentration

- **Category:** `DISCOVERY_CONCENTRATION`. **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** the old `_select` lifecycle-rank had no categorical distribution
  and could select two latest-only candidates.
- **What was fixed:** `_categorical_two_slot` enforces that when at least one
  latest-only and one non-latest eligible graduated candidate exist, the two
  slots are not both latest-only (one latest + one non-latest via durable seeded
  categorical round-robin); deterministic seeded uniform within each category;
  multi-channel duplicates are one candidate with no probability boost; provider
  order/rank/score/popularity cannot affect selection.
- **What remains unfixed:** applies only when both partitions have eligible
  graduated candidates; a single available category degrades honestly.
- **Tests:** `test_v2_9_7e_41_...::CategoricalDistributionTests`.
- **Can block next pilot:** No.
- **Operational channel coverage after repair:** the categorical rule is active;
  its non-latest categories depend on graduated-discovery channels (BL-41-04).

### BL-41-04 — still-blocked trending/top channel contracts

- **Category:** `BLOCKED_CONTRACT`. **Repair status:**
  `NOT_FIXED_REQUIRES_RESEARCH` (contract adoption is a separate operator lane).
- **Root cause:** GeckoTerminal (fixture-only contract), Solana Tracker (free-REST
  contract), and PumpPortal (wallet/funds requirement) remain unadopted, so no
  operational channel supplies already-graduated Pump tokens for fresh live
  discovery.
- **What was fixed:** the channels remain explicitly `SKIPPED_BLOCKED_CONTRACT`
  and visible in the admission report; none is silently activated; no paid
  dependency added. DexScreener active-market enrichment and PumpSwap confirmation
  remain operational per their contracts.
- **What remains unfixed:** fresh graduated-candidate supply is unavailable until
  a graduated-discovery contract is adopted or a migration-signature locator is
  supplied. This is a future operator decision, not a code defect.
- **Tests:** `test_v2_9_7e_41_...::FullPilotNoMaturityGateTests::test_blocked_channels_remain_visible`.
- **Can block next pilot:** Yes — cold-start FULL_PILOT blocks honestly with no
  graduated supply.
- **Operational channel coverage after repair:** graduation confirmation
  (PumpSwap on-chain) operational; graduated-discovery channels blocked.

## V2-9.7E.42 repair updates (direct Pump migration discovery)

E.42 made BL-41-04 operational for the **direct migration channel**: real
already-graduated Pump.fun candidate supply from PumpPortal `subscribeMigration`
events, with no manual migration signature. Two blockers are recorded.

### BL-41-04 — trending/top channel contracts (E.42 partial resolution)

- **Category:** `BLOCKED_CONTRACT`. **Repair status:** `PARTIALLY_FIXED` — the
  direct migration channel is now operational; the trending/top channels remain
  blocked.
- **What became operational (E.42):** the keyless PumpPortal `subscribeMigration`
  free stream + governed on-chain verification now supply confirmed
  `PUMPSWAP_GRADUATED_CONFIRMED` candidates for fresh live discovery with **no
  operator-supplied migration-signature locator**. The evidence chain is: migration
  event (locator) → governed `getTransaction` → exact Pump migration proof (adopted
  program presence + exact mint + success + finalized block time) → unique PumpSwap
  pool resolution (owner + `base_mint@43 == mint`) → pool confirmation → persist to
  the new durable `printer_pumpswap_graduated_candidate_registry` (migration 040).
  `export_graduated_pilot_candidates` now reads that registry.
- **Live proof:** Attempt 2 (`5dc63f5`) confirmed **three** real graduated Pump.fun
  candidates end-to-end (mints `AVuU5FZ…`, `Hj3Kg6St…pump`, `2KpU8qUz…pump`; pools
  `6MNGrmRL…`, `E3EmqM1H…`, `5SKDccVf…`); forbidden deltas 0; integrity/FK ok.
- **What remains blocked:** GeckoTerminal (fixture-only contract) and Solana Tracker
  (free-REST contract) trending/top graduated-discovery channels are still
  `SKIPPED_BLOCKED_CONTRACT` — a separate operator lane. The direct migration
  channel does not require them.
- **Tests:** `tests/test_v2_9_7e_42_direct_migration_discovery.py` (29).
- **Can block next pilot:** No for graduated supply — the direct channel supplies
  candidates. Trending/top diversity remains optional.
- **Current status:** `PARTIAL` (direct channel operational; trending/top blocked).

### BL-42-01 — migration-verification transaction freshness

- **First seen:** E.42 Attempt 1 (`f29c8b9`). **Category:** `CODE_DEFECT`
  (live-discovery robustness). **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** a PumpPortal migration **notification** arrives before its
  finalized transaction is queryable on the public multi-backend Solana RPC, so an
  immediate governed `getTransaction` fails with a transient RPC/not-found reason
  (`pumpswap_rpc_transport_error`) and verification correctly falls closed. The
  pipeline was proven correct by re-verifying the exact Attempt-1 event minutes
  later (confirmed end-to-end).
- **What was fixed (`5dc63f5`):** the direct-migration orchestrator gained bounded,
  governed, recorded robustness — `collection_rounds` (accumulate deduplicated
  locator pairs across N bounded governed migration requests), `settle_seconds`
  (one bounded wait before verification so fresh migrations finalize), and
  `reverify_on_transient` (exactly one additional governed verification per
  candidate whose first attempt failed **transiently** — never on a genuine
  graduation failure). Fixture defaults unchanged (single round, no wait, no retry).
- **Offline proof:** `tests/test_v2_9_7e_42_direct_migration_discovery.py`
  (`TestBL4201Robustness`: transient re-verify confirms; non-transient never
  retries; multi-round dedup).
- **Live proof after fix:** Attempt 2 confirmed three candidates, all
  `verify_attempts=1` after the settle window.
- **Can recur:** No — the transient path is bounded and unit-tested; non-transient
  failures are never retried.
- **Current status:** `FIXED`.

### E.41 supersession of E.40 maturity policy

- **BL-39-01 / BL-39-03** (E.40 900s maturity + persistent maturity pool): marked
  **historically implemented but superseded** by the graduation-only law. The
  maturity boundary is not removed from `SNAPSHOT_READINESS`; it is removed only
  from FULL_PILOT, where it was the wrong (age-based) eligibility gate. Old
  live-attempt facts (Attempts 1–3) are not rewritten.

## V2-9.7E.43 repair updates ($3K graduated selection front door)

E.43 added the market-performance front door on top of the E.41 graduation-only law
and the E.42 direct-migration supply: a confirmed graduated candidate may enter
active selection only once a governed, fresh, **exact-pool** DexScreener observation
proves `liquidity_usd >= 3000` for the exact Solana mint and exact confirmed
PumpSwap pool. `$3,000` is the only numeric market-performance threshold. Verdict
`V2_9_7E_43_3K_GRADUATED_FRONT_DOOR_PASS` (live Attempt 3).

### BL-43-01 — live migration-supply timing (proof orchestration)

- **First seen:** E.43 Attempt 1 (`d7ed63a`). **Category:** `CANDIDATE_SUPPLY`
  (live-stream timing). **Repair status:** `MITIGATED` (proof-driver tuning; no
  production code change).
- **Root cause:** PumpPortal `subscribeMigration` graduations are sparse and bursty
  — a single short bounded window may catch zero events. Attempt 1 used 25 s windows
  (0 graduations both cycles); Attempt 2 used 120 s windows but cycle 1 fell in a
  quiet burst gap (0), while cycle 2 caught 5.
- **What was fixed:** the bounded **proof driver** (scratchpad, not production) was
  tuned — discovery windows widened to the approved 120 s ceiling and cycle 1 made
  to persist (loop) until it confirms ≥ 2 graduated candidates before separating the
  cycles. The front-door production code was unchanged across all three attempts.
- **Live proof:** Attempt 3 (`d7ed63a`) confirmed 2 persisted (cycle 1) + 2 latest
  (cycle 2) real graduated candidates, all four with fresh live exact-pool liquidity
  ≥ $3,000, one LATEST + one PERSISTED selected, deterministic replay, atomic-handoff
  ready, forbidden deltas 0.
- **Can block next pilot:** Partially — a productive session must persist discovery
  until an eligible cohort exists; this is honest live-supply behaviour, not a code
  defect.
- **Current status:** `MITIGATED`.

### E.43 — exact-pool liquidity floor (front door)

- **Category:** `INCORRECT_ELIGIBILITY` (missing market-performance gate).
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** graduation-only selection admitted *any* confirmed graduated token
  regardless of tradeable liquidity; a token with a near-zero pool (live: `$8.70`,
  Attempt 2) could consume a scarce tracking slot.
- **What was fixed:** new `discovery/graduated_liquidity_front_door.py` enriches
  every graduated candidate (LATEST and PERSISTED) with one governed DexScreener
  `pair_market_snapshot` against the exact confirmed pool and applies the `$3,000`
  floor before selection. Below-floor → `LIQUIDITY_BELOW_SELECTION_FLOOR` (retained,
  not selectable); missing/stale/conflicting/token-level/wrong-pool/non-exact →
  `LIQUIDITY_UNPROVEN` (never zero). Truthful `LATEST_GRADUATED` /
  `PERSISTED_GRADUATED` provenance replaces the misleading `PERSISTED_ACTIVE`. The
  frozen mixed two-slot law and the tracking boundary are preserved.
- **Live proof:** Attempt 3 selected LATEST
  `4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump`
  (pool `BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p`, `$9,723.71`) + PERSISTED
  `4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump`
  (pool `9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo`, `$15,350.10`). The `$8.70`
  pool (Attempt 2) was correctly excluded live.
- **Tests:** `tests/test_v2_9_7e_43_graduated_liquidity_front_door.py` (26).
- **Can block next pilot:** No — it removes an untradeable-pool path; it cannot
  block a lawful `$3K+` graduated candidate.
- **Current status:** `FIXED`.

### E.43 live attempt log

| Attempt | Commit | Cycle 1 | Cycle 2 | Front door | Terminal |
|---|---|---|---|---|---|
| 1 | `d7ed63a` | 0 (25 s windows too short) | 0 | 0 candidates | NOT_PASS (BL-43-01) |
| 2 | `d7ed63a` | 0 (quiet burst gap) | 5 confirmed; 4 ≥ $3,000; `$8.70` excluded | 4 LATEST eligible, 0 PERSISTED | NOT_PASS (no persisted cohort) |
| 3 | `d7ed63a` | 2 confirmed | 2 confirmed | 2 LATEST + 2 PERSISTED eligible; 1+1 selected | **PASS** |

## V2-9.7E.44 repair updates (FULL_PILOT graduated candidate-supply integration)

### BL-44-01 — graduated discovery + $3K front door not wired into FULL_PILOT

- **First seen:** E.44 (operational continuation of BL-41-04).
- **Category:** `MISSING_INTEGRATION`.
- **Root cause:** the adopted E.42 direct-migration discovery and E.43 `$3,000`
  exact-pool front door were committed but had **no caller in `src/`**;
  `run_two_token_operational_pilot` invoked `run_operational` with **no
  `graduation_proofs`**, and `run_operational` never ran discovery or the front
  door. A live FULL_PILOT therefore cold-started straight to
  `BLOCKED_INSUFFICIENT_GRADUATED_POOL` and could never reach holder, activation or
  lifecycle.
- **Fixed behaviour:** new `graduated_supply_front_door.build_graduated_supply`
  composes the two owners verbatim (no new gate/score/selector/provider) and, for
  each front-door-*selected* mint, builds the confirmed-origin carrier (real derived
  Pump bonding-curve PDA + on-chain migration signature) and the exact PumpSwap
  graduation proof. `run_operational` gains
  `graduated_supply` / `migration_transport` / `graduated_supply_kwargs` /
  `stop_before_lifecycle`: the graduated candidates join the admission universe,
  holder eligibility runs, and the pre-lifecycle path returns atomic two-slot
  readiness without invoking the scheduler/lifecycle/memory driver.
- **Remaining limitation (deferred operator decision):** migration-discovered
  graduated candidates carry no original Pump **create** transaction (create
  signature/slot, associated bonding curve, creator address), which the executor
  activation path (`record_confirmed_origin`) requires. The narrow slice therefore
  wires the supply → `$3K` front door → holder → **atomic two-slot readiness**
  boundary and stops before create-centric activation. A create-origin backfill (or
  a graduation-native activation path) plus a continuously supervised real-wall-clock
  `15m → 1h → 4h` lifecycle session is the operator decision.
- **Fix commit:** `b273179`.
- **Offline proof:** `tests/test_v2_9_7e_44_full_pilot_supply_integration.py`
  (5 tests) + 137 directly affected regressions (142 total pass).
- **Live proof after fix:** bounded live pre-lifecycle supply proof — see the E.44
  live attempt log below.
- **Current status:** `PARTIAL` (supply integration committed + live-proven to
  atomic readiness; activation+lifecycle deferred).

### E.44 live attempt log (bounded supply proof — NOT a FULL_PILOT attempt)

One bounded live pre-lifecycle supply proof at HEAD `b273179`, fresh isolated proof
DB, explicit ceilings (2 discovery cycles, ≤4 migration events / 110 s per window,
≤4 verifications, 6 s settle, single transient reverify). Did **not** consume a
sustained FULL_PILOT attempt.

| Cycle | Live migrations | Confirmed graduated | Front-door result | Terminal |
|---|---|---|---|---|
| 1 | 0 (quiet window) | 0 | — | seeds nothing |
| 2 | 1 | 1 LATEST (on-chain verified, persisted) | fresh exact-pool liquidity **< $3,000** → 1 `LIQUIDITY_BELOW_SELECTION_FLOOR`; 0 eligible | `BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL` |

The full integration executed **live end-to-end** — PumpPortal `subscribeMigration`
→ governed on-chain graduation verification → durable graduated registry → E.43
exact-pool DexScreener enrichment → `$3,000` floor — and the floor **fired live** on
a real below-floor freshly-migrated pool (positive evidence, mirroring E.43
Attempt 2's `$8.70` exclusion). Sparse/quiet live migration supply (BL-43-01) meant
no lawful `LATEST ≥ $3,000` and no `PERSISTED` cohort within the ceilings, so the
lane terminated honestly before holder/atomic work. `integrity_check == ok`,
`foreign_key_violations == 0`, discovery + front-door forbidden-delta totals `0`.
Per policy this sparse-supply/below-floor outcome is **not** a code defect and no
retry-until-success was performed.

**E.44 live-vs-offline distinction (added at E.45).** The E.44 live proof covered
discovery → on-chain graduation confirmation → durable registry → the `$3,000`
exact-pool front door **live** (the floor fired live). Holder eligibility, atomic
two-slot readiness and activation were proved **offline only** at E.44
(`stop_before_lifecycle` returned the pre-lifecycle readiness bundle without invoking
the driver). The migration-discovered candidate carried no create transaction, so the
E.44 supply carrier stuffed the migration signature into a `FixtureOriginProof`
consumed by the create-origin path and **stopped before activation** — that carrier
shape is superseded by the E.45 typed graduation-native route (BL-44-01 below).

## V2-9.7E.45 repair updates (canonical supply + graduation-native activation)

### BL-44-01 — graduation-native activation (RESOLVED at E.45)

- **Category:** `MISSING_INTEGRATION` / `DESIGN_GAP`. **Repair status:**
  `FIXED_IN_THIS_SPRINT` (offline) + live supply-ready.
- **Root cause (E.44 remaining limitation):** migration-discovered graduated
  candidates carry no Pump **create** transaction, and the executor activation path
  (`_run_direct_lane` → `record_confirmed_origin`) requires create-centric evidence.
  E.44 therefore fed the migration signature through a create-shaped
  `FixtureOriginProof` and stopped before activation — a fake-create anti-pattern.
- **What was fixed (E.45):** a typed `origin_route` (`PUMP_CREATE` |
  `GRADUATION_NATIVE`) on `FixtureOriginProof`/`_Observation`/`_Merged`. The
  executor's `_run_direct_lane` routes `GRADUATION_NATIVE` candidates through a new
  block that records the Pump **migration lineage** (migration signature + graduation
  slot/block time) as migration evidence, **never** writes or fabricates a Pump
  create-origin row, and produces token/pair/queue/scheduler/slot identities
  identical to the create route (verified: `_handoff_one_slot` reads only the merged
  candidate's mint + rebound PumpSwap market identity, never the create registry).
  Create-native activation (Route A) is unchanged; activation stays two-or-none.
- **Companion repairs:** canonical registry bootstrap + immutable isolated export
  (Repair 1); DexScreener fresh-profiles **locator-only** wiring (Repair 2C);
  holder-aware reserve selection with lawful replacement (Repair 4); immutable
  `PILOT_INPUT_READY` boundary, migration 041 (Repair 6).
- **Fix commits:** `e8fdeed` (Repair 5 + design), `81d2ba6` (Repair 1),
  `cf65b4a` (Repair 6), `57dcfdb` (Repair 4), `6544d44` (Repair 2C).
- **Offline proof:** 28 E.45 tests + 60 (E.42/E.43/E.44) + 47 (combined-executor /
  atomic-handoff / graduation-only / origin-to-lifecycle) regressions; full suite
  collects 8283 with no import breakage.
- **Live proof:** `lane-x-v2-9-7e-45-bounded-live-supply-readiness-output.txt` — a
  fresh isolated DB reached `GRADUATED_SUPPLY_READY` live over two cycles with one
  real LATEST (`aPij1aZg…pump`) + one real PERSISTED (`Z95okeyh…pump`) graduated
  candidate, both on exact confirmed PumpSwap pools `$3K+`; a decayed prior-cycle
  pool was correctly excluded below floor; integrity ok, FK 0, forbidden deltas 0.
- **Remaining limitation:** live holder chaining, live graduation-native activation,
  the live `PILOT_INPUT_READY` bundle write, and the sustained `15m → 1h → 4h`
  two-token `FULL_PILOT` (≥ 4 h continuous foreground supervision) were **not** run —
  a hard environment duration limit. Verdict `V2_9_7E_45_OPERATOR_DECISION_REQUIRED`;
  V2-9.7E stays active; V2-9.7F not started.
- **Current status:** `PARTIAL` — activation architecture resolved and offline-proven;
  supply proven live-ready; sustained pilot environment-blocked.

## V2-9.7E.46 live full-pilot update

### BL-46-01 — adopted holder evidence sources unavailable

- **First seen:** E.46 Attempt 2; independently repeated at Attempt 3.
- **Category:** `CONFIG_OR_ENVIRONMENT_BLOCKER__NO_PRODUCT_CODE`.
- **Root cause:** every selected token's fixed public Solana RPC primary
  `getTokenLargestAccounts(finalized)` returned HTTP 429, while the fixed Helius
  Free backup returned `helius_auth_missing` because `PRINTER_HELIUS_API_KEY` was
  not configured. GoPlus completed with clean exact-target safety context but does
  not establish wallet concentration, so the aggregate holder result correctly
  remained `HOLDER_CONCENTRATION_UNKNOWN`.
- **Observed scope:** Attempt 2 evaluated two exact-pool `$3K+` latest candidates;
  Attempt 3 evaluated the required mixed pair—LATEST `4yxNHzN7…pump` on
  `AeaiCGUs…5nSJ` at `$8,765.55`, and PERSISTED `9XuWt4W2…pump` on
  `PKztZQTM…DddE` at `$8,019.03`. Both fresh executions produced the same
  primary/backup failure for both tokens.
- **Fixed behavior:** no code change is justified. The existing holder owner
  failed closed before atomic activation or `PILOT_INPUT_READY`; no endpoint was
  added or rotated, no provider raced, no retry hidden, and no stale evidence
  reused.
- **Remaining limitation:** the live graduation-native activation and sustained
  `15m → 1h → 4h` lifecycle cannot begin until the adopted holder contract returns
  valid evidence. A lawful future retry requires fresh identities/evidence after
  the operator configures the already-approved Helius Free credential through the
  existing secret boundary, or after the fixed public endpoint supplies evidence.
- **Repair status:** `OBSERVE_NOT_YET_STRUCTURAL`; environment/configuration action,
  not product repair.
- **Fix commit:** N/A.
- **Offline proof:** existing E.22 holder fail-closed contract plus E.45 holder
  reserve tests; E.46 focused/regression suites remain PASS.
- **Live proof:** E.46 Attempts 2 and 3, fresh isolated DBs and identities.
- **Repeated after fix:** not applicable; no fix was claimed.
- **Current status:** `OPEN` (environment/configuration).

### E.46 execution and repair log

| Execution | HEAD | First terminal cause | Repair / disposition |
|---|---|---|---|
| Attempt 1b | `e86c6a2` | `BLOCKED_INSUFFICIENT_GRADUATED_POOL` | Exposed irrelevant create-acquisition budget use, non-durable locator accounting and latest-partition starvation; repaired at `18f9c6b`. |
| Attempt 2 | `18f9c6b` | `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` | Holder primary HTTP 429 + missing Helius Free auth for both eligible tokens; no code repair. Subsequent durable-registry merge exposed tuple-row idempotency defect, repaired at `08a1c9d`. |
| Attempt 3 | `08a1c9d` | `PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED` | Required LATEST + PERSISTED `$3K+` pair reached holder funnel; identical provider-wide holder evidence block reproduced. |

All executions stopped before lifecycle launch, ended `GOVERNED_SAFE_STOP`, released
the proof lock, left zero scheduler/run work, used zero-source deterministic replay,
created no successor/restart, passed integrity/FK checks, and produced zero
retrieval/decision/position/trade/audit/PnL deltas. No sustained attempt was consumed.

**E.46 verdict:** `V2_9_7E_46_BLOCKED_HOLDER_EVIDENCE`. V2-9.7E remains active;
V2-9.7F is not ready and was not started.

## V2-9.7E.46 authorized full-pilot retry (lifecycle evidence)

The separately authorized canonical `FULL_PILOT` at HEAD `26e0b22` completed two
real `WINDOW_15M` lifecycles and terminated `V2_9_7E_46_BLOCKED_LIFECYCLE_EVIDENCE`
(closeout `printer-v1-v2-9-7e-46-authorized-full-pilot-retry-closeout.md`). It
recorded four new blockers plus two evidence-semantics faults, all repaired at
V2-9.7E.47 below.

## V2-9.7E.47 repair updates (unified terminal closure + clean-memory contract)

All blockers below were confirmed against current code **and** against a
byte-identical disposable copy of the retained E.46 attempt database (SHA-256
`a29db0d9f3049b31a266ee6d28ed98708cfc896e6519954a57162cd80fa28ef3`, re-verified
unmutated). Verdict `V2_9_7E_47_LIFECYCLE_AND_CLEAN_MEMORY_REPAIR_PASS`.
Offline proof: `tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py`
(39 tests, 30 subtests) plus directly affected regressions.

### BL-47-01 — lifecycle-started terminal leaves the ownership graph RUNNING

- **First seen:** E.46 §10.1. **Category:** `CODE_DEFECT`.
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `_reconcile_pre_lifecycle_terminal_metadata` was gated on
  `not lifecycle_started` (`two_token_operational_pilot_runner.py:844`) on the
  stated assumption that "a started lifecycle owns its own terminal
  reconciliation". Nothing on the started path reconciled campaign/run/cycle.
- **Live evidence:** campaign `RUNNING`, run `RUNNING`, cycle `PLANNED`, all
  `first_terminal_cause = NULL`, while supervision was `TERMINAL` /
  `GOVERNED_SAFE_STOP` with zero active run steps.
- **Fixed behaviour:** one authoritative terminal path
  (`unified_terminal_closure.reconcile_campaign_terminal`) runs on **every**
  terminal and reconciles campaign, campaign run, cycle, factory run,
  supervision, every started campaign window, and all campaign-scoped work and
  Scheduler jobs, preserving the immutable first terminal cause.
- **Disposable-copy reconciliation:** `RUNNING/RUNNING/PLANNED` →
  `TERMINAL_STOPPED` ×3 with cause `SAFE_STOP_4H_TERMINAL_INCOMPLETE`.
- **Can recur:** No — the path is unconditional and unit-tested.
- **Live proof after fix:** NOT yet. **Current status:** `FIXED` (offline).

### BL-47-02 — discovery Scheduler jobs never transitioned out of PENDING

- **First seen:** E.46 §10.2. **Category:** `CODE_DEFECT` /
  `MISSING_INTEGRATION`. **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause (two independent faults):** (a)
  `combined_executor._terminalize_work` updated only `printer_discovery_work`
  and never transitioned the `DISCOVERY_REFRESH` job it had enqueued; (b)
  `_cancel_campaign_discovery_jobs` was invoked with the **handoff** batch id
  `origin-activated:<cycle>` while the executor writes work under
  `discovery-batch:<campaign>:<run>:<cycle>`, so the query matched zero rows —
  and blanket cancellation would in any case have been the wrong terminal for
  work that had SUCCEEDED.
- **Live evidence:** 8/8 work rows `SUCCEEDED` with explicit terminal causes;
  8/8 linked jobs `PENDING` with no `last_error`.
- **Fixed behaviour:** frozen parity mapping in
  `discovery/scheduler_parity.py` — successful work → `SUCCEEDED`, failed work →
  `FAILED`, abandoned/superseded/terminally-unnecessary work → `CANCELLED` —
  applied at the moment work becomes terminal and again at campaign terminal,
  always through the committed Central Scheduler owner. Cleanup is scoped by
  campaign/run/cycle identity; the handoff batch id is only a fallback.
- **Disposable-copy reconciliation:** 8 `PENDING` → 8 `SUCCEEDED`;
  terminal-work-with-active-job 8 → 0.
- **Can recur:** No. **Live proof after fix:** NOT yet. **Status:** `FIXED`.

### BL-47-03 — active-work accounting could not observe the defect

- **First seen:** E.46 §10.2. **Category:** `CODE_DEFECT` (observability).
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `running_jobs_after_stop` counted only jobs reachable through
  the run's factory run-steps whose status was `RUNNING` or which held a lock.
  `PENDING` and `COOLDOWN` were invisible and discovery jobs unreachable, so the
  reported `0` was accurate under that definition and still missed all eight.
- **Fixed behaviour:** `campaign_active_work.campaign_active_work_report` gives
  exact campaign-scoped accounting over `PENDING`/`RUNNING`/`COOLDOWN`/locked
  jobs across factory run-step jobs, discovery jobs and campaign scheduler work,
  plus active work rows. The narrow value is preserved as
  `running_or_locked_run_step_jobs`. A terminal campaign requires zero active
  jobs and zero active work rows.
- **Can recur:** No. **Status:** `FIXED`.

### BL-47-04 — false `SAFE_STOP_4H_TERMINAL_INCOMPLETE`

- **First seen:** E.46 §10 / §15 item 1. **Category:** `INCORRECT_ELIGIBILITY`
  (terminal semantics). **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `_four_hour_terminal_validation` required both closed 15m
  windows to be `CLEAN_MEMORY` before a natural no-continuation stop could be
  `complete`, conflating lifecycle completion with clean-memory success. A second
  contributing cause was found during confirmation: the same branch compared
  `window_status != "COMPLETE"`, a value no owner writes (`e2o_memory_window_close`
  writes `WINDOW_CLOSED`; the audit path writes `WINDOW_AUDIT_ONLY`), so even a
  fully clean natural stop could never be reported complete.
- **Fixed behaviour:** a lawful no-continuation close is a `COMPLETED` governed
  lifecycle. `SAFE_STOP_4H_TERMINAL_INCOMPLETE` is reserved for a continuation or
  required terminal phase that actually started or was required and did not
  complete. Memory quality is reported separately as `memory_acceptance`
  (`CLEAN_MEMORY_ACHIEVED` / `MEMORY_EVIDENCE_BLOCKED`) and blocks only the pilot
  acceptance verdict.
- **Superseded assertion:** `test_v2_9_7e_19_...::test_two_clean_natural_stops_complete_but_dirty_or_proof_mode_does_not`
  asserted the defect and was rewritten as
  `test_natural_stops_complete_regardless_of_memory_quality`.
- **Can recur:** No. **Status:** `FIXED`.

### BL-47-05 — no campaign report row or artifact on any terminal

- **First seen:** E.46 §13. **Category:** `MISSING_INTEGRATION`.
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** no campaign report owner had a caller on the pilot path;
  `handle_abstract_command` (which calls `persist_final_campaign_report`) is
  never invoked by `run_operational`, the driver or the pilot runner.
- **Live evidence:** `printer_memory_factory_campaign_reports` = 0 rows,
  `reports\` empty after a completed two-window lifecycle.
- **Fixed behaviour:** every terminal outcome writes exactly one immutable row
  through the committed `campaign_persistence` terminal-report owner plus exactly
  one durable canonical artifact in the configured report directory, with exact
  campaign/run/cycle/factory-run/report identity linkage and a deterministic
  zero-source `replay_campaign_terminal_report` that creates no duplicate.
- **Remaining limitation:** `final_campaign_report.persist_final_campaign_report`
  is still unused on this path because it requires the full 6B campaign-object
  graph (campaign objects of every kind, campaign windows, campaign scheduler
  work, campaign supervision rows) that the pilot path has never created. Wiring
  that graph is a separate lane.
- **Disposable-copy reconciliation:** 0 rows / 0 artifacts → 1 / 1; replay
  `new_source_calls = 0`, `new_scheduler_work = 0`, duplicates 0, DB writes 0.
- **Status:** `PARTIAL` (report and replay committed; 6B object graph deferred).

### BL-47-06 — declared dependency verified only after mutable state existed

- **First seen:** E.46 §2. **Category:** `CODE_DEFECT` (preflight ordering).
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** the PumpPortal migration transport was constructed **after**
  supervision, the campaign graph and the proof lock. `websockets>=12.0` is a
  declared `pyproject.toml` dependency but was absent from the selected
  interpreter, so an authorized launch burned its identity and left supervision
  `STARTING`, campaign `RUNNING/RUNNING/PLANNED` and a lock on disk.
- **Fixed behaviour:** `assert_runtime_dependency_preflight` resolves the exact
  interpreter, verifies every declared runtime dependency and minimum version,
  confirms the canonical package imports from this repository, constructs the
  required adapters without external calls, and validates invocation arguments
  and paths — all before any mutable attempt state or authorization. Zero
  external requests, zero database writes, so a failure creates zero campaign,
  run, cycle, supervision, lock or source rows. Anything that fails **after**
  state exists routes through `_emergency_terminal_closure`, which preserves the
  first failure, terminalises every ownership row, cancels active work, releases
  the lock, writes the terminal report, and creates no retry, restart or
  successor.
- **Can recur:** No for this cause. **Status:** `FIXED`.

### BL-47-07 — two disagreeing clean-memory evidence contracts

- **First seen:** E.46 §8. **Category:** `DESIGN_GAP` / `CODE_DEFECT`.
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** the shared exact-ledger resolver (`context_evidence/window_15m.py`)
  and the older `_classify_first_memory_review` disagreed. The classifier applied
  a blanket "any label whose value looks UNKNOWN is a blocker" rule that swept in
  **support-only 5m** descriptors, required a `micro_event` context row for a main
  window, and relabelled every non-clean result `MISSING_CRITICAL_DATA`.
- **Live evidence:** window 2 had `clean_memory_context_ready = true` and
  `evidence_blockers = []` from the shared resolver and was still refused.
- **Fixed behaviour:** one explicit required-evidence matrix for `WINDOW_15M`.
  Required: exact identity and current-run snapshot ledger; complete cadence and
  duration; price and liquidity fields; clean snapshot source status/quality;
  clean source provenance and traces; market regime; Solana chain heat; mandatory
  exact-target safety; entry/exit realism; trading-flow and chart evidence; clear
  outcome evidence. Optional/contextual: support-only 5m descriptors, whose
  absence stays an explicit `UNKNOWN` reported as `optional_unknown_context` and
  never converts to `MISSING_CRITICAL_DATA` on its own. Market regime and chain
  heat stay **mandatory** (Clean Master Spec 10.7 item 26 and 12.4); no
  contract conflict was found, so no `BLOCKED_CONTRACT_CONFLICT` was raised.
- **Status:** `FIXED`.

### BL-47-08 — measured `+5%..+25%` held-to-15m result became unknown

- **First seen:** E.46 §8 (window 2). **Category:** `CODE_DEFECT`
  (categorical gap). **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `classify_holding_to_15m_result` returned
  `HELD_TO_15M_UNKNOWN` for any `held_change > 5` below the `25` threshold.
- **Live evidence:** window 2 measured **+21.1217%** on **$324,448.66** exact-pool
  liquidity and was labelled unknown; that label was its **only** remaining
  blocker.
- **Fixed behaviour:** one added categorical label
  `HELD_TO_15M_MODERATE_CONTINUATION` (enum, classifier, outcome mapping to the
  existing approved `SHORT_TERM_PUMP`, persistence via migration `042`, reporting
  and tests). No score, rank, confidence or weighted logic. Surrounding bands
  unchanged; an absent measurement is still honestly `HELD_TO_15M_UNKNOWN`.
- **Disposable-copy reconciliation:** window 2 becomes
  `CLEAN_MEMORY` / `CLEAN_DATA` / `do_not_train = 0` with zero blockers — the
  program's first clean memory from real recorded evidence.
- **Status:** `FIXED`.

### BL-47-09 — known outcome erased by memory quality

- **First seen:** E.46 §8. **Category:** `CODE_DEFECT`.
  **Repair status:** `FIXED_IN_THIS_SPRINT`.
- **Root cause:** `_classify_first_memory_review` returned
  `"OUTCOME_UNKNOWN" if memory_quality != "CLEAN_MEMORY"`, discarding the
  truthful measured outcome.
- **Live evidence:** window 1, an unambiguous −99.986% collapse
  (`HELD_TO_15M_DEAD`), was stored as `OUTCOME_UNKNOWN`.
- **Fixed behaviour:** the truthful known outcome is persisted independently of
  memory quality (collapse/dead, dump, fade, consolidation, moderate
  continuation, strong continuation, round trip). Only a genuinely unresolved
  trajectory stays unknown. A window may truthfully be
  `outcome = DEAD_OR_COLLAPSE` with either `DIRTY_MEMORY` or `CLEAN_MEMORY`
  depending solely on evidence completeness. A fully evidenced ≈−99.99% collapse
  is eligible for `CLEAN_MEMORY` with `do_not_train = 0`; `CLEAN_MEMORY` never
  implies favourable, safe to buy or profitable.
- **Disposable-copy reconciliation:** window 1 keeps `HELD_TO_15M_DEAD` and is
  still refused as training material because its mandatory exact-target safety
  evidence is genuinely absent — no safety gate weakened.
- **Status:** `FIXED`.

### E.47 open items

- ~~Live confirmation of every BL-47-* repair (all proved offline and against
  recorded evidence; none observed on a live run).~~
  **Live confirmation completed** at post-E.47 full pilot (below).
- BL-47-05 6B campaign-object graph remains deferred.
- BL-46-01 (holder evidence) remains an `OPEN` environment/configuration
  condition, unchanged by this lane (public Solana RPC 429 still observed; Helius
  Free backup supplied exact-target holder evidence when primary RPC failed).
- BL-43-01 sparse live migration supply remains `MITIGATED`, unchanged
  (`pumpportal_no_valid_solana_events` ×1 this run; two graduated admits still
  obtained).

**E.47 verdict:** `V2_9_7E_47_LIFECYCLE_AND_CLEAN_MEMORY_REPAIR_PASS`. One fresh
full-pilot attempt may be considered under separate authorization. V2-9.7E
remains active; V2-9.7F was not started.

## V2-9.7E post-E.47 live full-pilot proof (2026-07-25)

**Verdict: `V2_9_7E_POST_E47_FULL_PILOT_PASS`.**

Closeout: `docs/printer-v1-v2-9-7e-post-e47-bounded-full-pilot-proof-closeout.md`.

| Field | Value |
|---|---|
| HEAD | `7df7ac0c1587e8b1d5a8af6464b5fbc4ad461fbe` |
| Execution id | `e47-full-20260725-7df7ac0` |
| Entry point | `scripts/v2_9_7e_14_two_token_operational_pilot.py` (macOS/zsh Python) |
| Wall clock | 1320.4 s |
| First terminal cause | `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` |
| Campaign / run / cycle | `TERMINAL_COMPLETED` ×3 |
| Discovery jobs after close | 8/8 `SUCCEEDED`, **0** `PENDING` |
| Campaign report + zero-source replay | 1 row / 1 artifact; `new_source_calls=0` |
| WINDOW_15M | 2 closed (~906 s / ~912 s); both `DIRTY_MEMORY` + truthful `DEAD` |
| Forbidden deltas | all 0 |
| Restart / successor | false / false |

Live status updates for E.47 blockers:

| Blocker | Live after post-E.47 pilot |
|---|---|
| BL-47-01 | **Live PASS** |
| BL-47-02 | **Live PASS** |
| BL-47-03 | **Live PASS** |
| BL-47-04 | **Live PASS** |
| BL-47-05 | **Live PASS** (report path; 6B graph still deferred) |
| BL-47-06 | **Live PASS** |
| BL-47-07 / BL-47-08 / BL-47-09 | **Live PASS** on adverse path (outcomes preserved; dirty only for real safety absence) |

**Readiness:** V2-9.7E pilot proof resolved for the post-E.47 bounded two-token
path. Live `CLEAN_MEMORY` and 1h/4h continuation remain open market/eligibility
items, not re-blocks of terminal closure. **V2-9.7F was not started.**

## V2-9.7E.48 holder-condition / memory-quality separation (2026-07-25)

**Verdict: `V2_9_7E_48_HOLDER_CONDITION_MEMORY_QUALITY_SEPARATION_PASS`.**

Closeout:
`docs/printer-v1-v2-9-7e-48-holder-condition-memory-quality-separation-closeout.md`.

### BL-48-01 — holder condition incorrectly controlled memory quality

- **Category:** `COMMITTED_CODE_DEFECT`. **Status:** `FIXED`.
- **Root cause:** concentrated, extreme, unknown, unavailable and conflicting
  holder evidence flowed through safety-policy/composite blockers into the 15m
  memory-quality gate. This conflated descriptive market-integrity risk with
  episode evidence trustworthiness.
- **Retained evidence:** both post-E.47 `DEAD` windows were dirty solely because
  `HOLDER_CONCENTRATION_EXTREME` was treated as a hard memory blocker.
- **Fixed behaviour:** all six holder states remain explicit descriptive
  evidence but never independently dirty memory. Wrong identity, contamination,
  invalid provenance, incomplete cadence/duration, missing snapshots/outcome,
  stale/broken core evidence and missing entry/exit realism still fail closed.
- **Disposable-copy reconciliation:** both windows retain `DEAD` and
  `HOLDER_CONCENTRATION_EXTREME`, become `CLEAN_MEMORY` / `CLEAN_DATA` /
  `do_not_train=0`, with zero forbidden capability deltas; integrity `ok`, FK 0.

### BL-48-02 — holder evidence provenance and measurement facts were lossy

- **Category:** `COMMITTED_CODE_DEFECT`. **Status:** `FIXED_FOR_NEW_EVIDENCE`.
- **Root cause:** top-ten percentage/basis/limitations were discarded and the
  Helius holder field was bound as `solana_rpc`.
- **Fixed behaviour:** new GoPlus/RPC/Helius composite contributions retain
  percentage, basis, reason and limitations and bind the field to the actual
  source. Thresholds remain 55%/80%. Token-account versus beneficial-owner,
  wallet-clustering and pool/vault/burn/program-account limitations are
  explicit.
- **Historical limitation:** retained composites are not rewritten; their
  original contribution rows and field-binding text remain historical.

**Readiness:** V2-9.7E.48 is closed. Retrieval and every financial capability
remain locked. Next: `V2-9.7F — Activation Readiness Review` (not started).

## V2-9.7F activation readiness (2026-07-25)

**Verdict: `V2_9_7F_ACTIVATION_READINESS_PASS`.**

Closeout: `docs/printer-v1-v2-9-7f-activation-readiness-closeout.md`.

Starting HEAD: `7326b9a4a23a859819a56f474e6746ec66df4401` (clean tracked tree).
Mode: static/read-only review only; no source calls, runtime, DB mutation,
pilot, code repair, or V2-9.8A start.

| Criterion | Result |
|---|---|
| Canonical command / supervision / safe stop / report / zero-source replay | PASS (committed + post-E.47 live-proven) |
| E.47 / E.48 blockers | PASS (fixed or non-activation residuals) |
| Memory quality vs outcome / safety / profitability / holder condition | PASS |
| Healthy / concentrated / extreme do not block collection or clean solely on condition | PASS |
| UNKNOWN / unavailable / conflicting pre-lifecycle admission | Standing resolved-holder collection gate; **not** a money-learning contract violation; wrong target / contamination / invalid provenance remain fail-closed |
| No governor/scheduler bypass, auto-restart, 5m authority, unsupported windows | PASS |
| Retrieval / paper / financial locks | PASS (remain locked) |
| V2-9.8A not started here | PASS |

No open code-level activation blocker remains. Next lane:

`V2-9.8A — Operator Activation Gate` (separate explicit operator gate; not started).
