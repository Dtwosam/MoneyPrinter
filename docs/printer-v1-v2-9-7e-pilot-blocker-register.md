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
| BL-39-01 | E.39 | E.40 | MISSING_INTEGRATION | `FULL_PILOT` (`run_operational`) never integrated the E.36-38 900s maturity boundary; it composed newest-create activation straight into lifecycle | E.40: `run_operational` applies the frozen 900s categorical maturity boundary + fail-closed `BLOCKED_INSUFFICIENT_MATURE_POOL` before any holder/lifecycle/memory work; distinguishes historical admission evidence from the forward WINDOW_15M | Does not guarantee two mature candidates on a cold-start attempt (see BL-39-03) | `<pending E.40 repair commit>` | `tests/test_v2_9_7e_40_full_pilot_admission.py` (3 tests) + regressions (E.11 54, maturity/readiness/pilot 45+5, origin 71) | Pending Attempt 1 | No | FIXED |
| BL-39-02 | E.35 | E.36-38 | DESIGN_GAP | No approved categorical snapshot-maturity boundary coordinated candidate age with the completed-exact-15m requirement (readiness mode) | 900s categorical maturity admission before holder/snapshot I/O in `SNAPSHOT_READINESS`; `BLOCKED_INSUFFICIENT_MATURE_POOL` for <2 mature | Applies to `SNAPSHOT_READINESS` only; does not guarantee mature-candidate supply | `f7f5d73` | `tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py` (16 passed, 5 subtests) + regressions (44 passed) | No | N/A | FIXED |
| BL-39-03 | E.34/E.35 | E.40 | CANDIDATE_SUPPLY | Full-pilot candidate universe consisted solely of the newest Pump create transactions (~170-243s old); no mechanism admitted older/staged candidates | E.40: newest-too-young creates are categorically excluded from the active pool; every confirmed origin is staged into the durable prospective-origin registry; previously staged origins that are now due are reloaded (zero-source) and unioned into the universe; channel/age reporting added | Cross-run staged pool is inert on a fresh isolated DB, so a cold-start attempt still usually blocks on supply; guaranteed mature supply needs an adopted secondary discovery provider or a persistent cross-run pool (operator decisions) | `<pending E.40 repair commit>` | `tests/test_v2_9_7e_40_full_pilot_admission.py` (staging reload + partition) | Pending Attempt 1 | No | PARTIAL |

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

- **BL-39-03** — Candidate supply. E.40 made the structural repair: newest,
  too-young creates can no longer be the active selection pool (categorically
  excluded by maturity), every confirmed origin is staged into the durable
  prospective-origin registry, and previously staged origins that are now due
  are reloaded with zero source calls. Remaining limitation: on a fresh isolated
  DB the staged pool is empty, so a cold-start attempt still usually blocks on
  supply. Full mature-supply sufficiency needs an adopted secondary discovery
  provider or a persistent cross-run staged pool — both operator decisions.

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

## Cross-attempt guidance

- Do not describe the maturity admission gate as a supply repair.
  `Maturity admission boundary: FIXED (full pilot + readiness)`;
  `Mature-candidate supply productivity: PARTIAL (cold-start still blocks)`;
  `FULL_PILOT maturity integration: FIXED (E.40)`.
- A cold-start full pilot on a fresh DB is expected to close honestly with
  `BLOCKED_INSUFFICIENT_MATURE_POOL` unless live throughput happens to place two
  bounded creates past the 900s boundary. That is an honest supply outcome, not
  a code defect; do not retry, wait, widen acquisition, or add a source.
