# Printer V1 V2-9.7E Pilot Blocker Register

Cumulative register of blockers encountered on the road to a bounded two-token
full pilot. Created at V2-9.7E.39 (Full Pilot Attempt 1).

## Legend

- **Category** — one primary category per blocker.
- **Current status** — `OPEN` / `PARTIAL` / `MITIGATED` / `FIXED` / `RESEARCH`.
- **Repair status** — `FIXED_IN_THIS_SPRINT` / `PARTIALLY_FIXED` /
  `NOT_FIXED_REPAIR_IDENTIFIED` / `NOT_FIXED_REQUIRES_DESIGN` /
  `NOT_FIXED_REQUIRES_RESEARCH` / `OBSERVE_NOT_YET_STRUCTURAL`.

## Cumulative field table

| Blocker ID | First seen | Most recent attempt | Category | Root cause | Fixed behavior | Remaining limitation | Fix commit | Offline proof | Live proof after fix | Repeated after fix | Current status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BL-39-01 | E.39 | E.39 | MISSING_INTEGRATION | `FULL_PILOT` (`run_operational`) never integrated the E.36-38 900s maturity boundary or the E.26-E.33 strict two-bundle snapshot-readiness gate; both live only in `SNAPSHOT_READINESS` (`run_snapshot_readiness`) | None yet | Requires a frozen full-pilot maturity/readiness→lifecycle design before implementation | — | — | No | N/A | OPEN |
| BL-39-02 | E.35 | E.36-38 | DESIGN_GAP | No approved categorical snapshot-maturity boundary coordinated candidate age with the completed-exact-15m requirement (readiness mode) | 900s categorical maturity admission before holder/snapshot I/O in `SNAPSHOT_READINESS`; `BLOCKED_INSUFFICIENT_MATURE_POOL` for <2 mature | Applies to `SNAPSHOT_READINESS` only; does not cover `FULL_PILOT` (see BL-39-01); does not guarantee mature-candidate supply | `f7f5d73` | `tests/test_v2_9_7e_36_38_snapshot_maturity_boundary.py` (16 passed, 5 subtests) + regressions (44 passed) | No | N/A | FIXED (readiness mode only) |
| BL-39-03 | E.34/E.35 | E.35 | CANDIDATE_SUPPLY | Bounded newest-create Pump acquisition repeatedly returns pools ~170-243s old; selection has no mechanism to include older pools | None (admission gate only) | Mature-candidate supply productivity remains OPEN; a correctly gated run may still honestly block on supply | — | — | No | N/A | OPEN |

## Fixed blockers

- **BL-39-02** — Snapshot maturity boundary for the `SNAPSHOT_READINESS` path.
  Fixed and proved offline at `f7f5d73`. Applies to readiness mode only.
  Note: this is an admission gate, not a supply repair —
  `Maturity admission boundary: FIXED`;
  `Mature-candidate supply productivity: OPEN` (BL-39-03).

## Partially fixed blockers

- None.

## Open blockers

- **BL-39-01** (MISSING_INTEGRATION, requires design) — `FULL_PILOT` lacks the
  maturity boundary and the strict readiness gate before lifecycle/memory. This
  is the blocker that stopped E.39 at preflight.
- **BL-39-03** (CANDIDATE_SUPPLY) — young-candidate diet; no committed
  mature-candidate supply mechanism. Structural and repeatable.

## Repeated blockers

- **BL-39-03** repeats the E.34/E.35 observation of a repeatedly young candidate
  pool. Not yet resolved; not caused by the E.36-38 fix.

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

## Cross-attempt guidance

- Do not describe the maturity admission gate as a supply repair.
  `Maturity admission boundary: FIXED (readiness mode)`;
  `Mature-candidate supply productivity: OPEN`;
  `FULL_PILOT maturity/readiness integration: OPEN (requires design)`.
- Do not launch a live full pilot while BL-39-01 is OPEN.
