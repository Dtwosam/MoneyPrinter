# Printer V1 — V2-9.8B `WINDOW_15M` Final Integrated Readiness Repair Closeout

**Date:** 2026-08-05  
**Lane:** `V2-9.8B — WINDOW_15M Final Integrated Readiness Repair`  
**Branch:** `agent/v2-9-8b-window-15m-final-integrated-readiness-repair`  
**Baseline HEAD:** `e32cf740d465518474587295973eb0ae607cbba6`  
**Baseline branch:** `agent/v2-9-8b-window-15m-a-to-z-deterministic-readiness-repair`

## Final verdict

`V2_9_8B_WINDOW_15M_FINAL_INTEGRATED_READINESS_REPAIR_BLOCKED`

PASS requires one continuous wrapper-to-memory proof with four observation-eligible
candidates, two selected plus two alternates, two 900-second windows, two clean
episodes, and two exact fingerprints. That continuous success path did not complete.

## What was implemented (partial)

### A — Shared production composition owner

- Registry and production runtime constructor identities are equal
  (`ordinary_window_15m_builder_identities` == `production_runtime_constructor_identities`).
- Production defaults for pump, secondary, and migration transports now resolve
  through `construct_ordinary_window_15m_dependency` /
  `production_runtime_default_constructors` (same owner as preflight).
- Request-kind validation: when `expected_request_kind` is supplied, missing
  canonical `allowed_request_kinds` contract fails
  (`REQUIRED_ADAPTER_REQUEST_KIND_CONTRACT_MISSING`).

### B — Action-local mutation identity recorder

- New `action_local_mutation_recorder.py` with insert/update/unknown emission.
- Installed for ordinary campaign runs in `_ACTION_RUN_CONTEXT`.
- Campaign create owners emit inserted campaign/config/run identities.
- Campaign run bind emits updated run identity.
- Public exception path passes frozen owner-emitted identities into
  `build_action_local_terminal_truth` (observed in continuous attempt: 3
  authoritative writes, first terminal cause preserved).

### C — Lane K fingerprint integration

- `_attach_fingerprint_for_episode` now fetches episode/window/token/pair IDs,
  source outcome, tracking lane, age/discovery when present, and canonical
  supporting-context labels.
- Focused tests require exact identity and real outcome when present; `UNKNOWN`
  only when the source fact is absent.

### D — Continuous wrapper-to-memory proof (incomplete)

Implemented continuous structure:

1. Disposable Git worktree with historical evidence + fresh fixture authorization.
2. Disposable Migration-052 DB under `repo/data/printer_v1.sqlite3` (so
   `AUTHORITATIVE_DB.parent.parent` is the disposable repo).
3. Actual one-shot wrapper launch of the actual operational child module
   (`printer_v1.operator_cli.operational_memory_factory_command run`).
4. Activation preflight not patched out.
5. Zero external network (urlopen guarded).
6. Shared composition registry used by production defaults.
7. No direct `_run_operational_campaign()` call from the test.
8. No custom owner replacing eligible supply.
9. Authorization consumed exactly once (second application blocked).

**Blocking failure on continuous success path:**

```text
CampaignSixUnitError:SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE
```

Campaign identity is created; five governed source requests/responses are
recorded; graduated market floor state inserts four rows; then stage sealing
fails for an empty-started stage under frozen migration/market transport
injection. Token slots, 900-second windows, clean episodes, and fingerprints
are not reached.

Supporting preflight fixes made for disposable continuous structure:

- `build_activation_preflight` resolves `AUTHORITATIVE_DB` at call time (not
  import-time default freeze).
- Package-under-repo check applies only to full source checkouts containing
  `src/printer_v1` (evidence-only disposable worktrees allowed).

## Confirmed remaining blockers (post-lane)

1. Continuous ordinary graduated-supply path under frozen transports still fails
   stage-evidence sealing (`EMPTY_STARTED_STAGE_EVIDENCE`) before freeze/selection.
2. Four fresh observation-eligible candidates with two selected + two alternates
   not proven on the continuous wrapper→child path.
3. Two real logical 900-second windows, clean episodes, and fingerprints not
   proven continuously.
4. Production runtime still needs deeper ordinary-path transport freezes that
   keep MeasuredTransportLedger/stage seals non-empty without inventing a second
   discovery graph.

## Focused tests

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_final_integrated_readiness_repair.py \
  tests/test_v2_9_8b_window_15m_a_to_z_deterministic_readiness_repair.py \
  -q
```

**Result: 37 passed** (A/B/C and prior deterministic readiness suite).

Continuous proof test:

```bash
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py \
  -q
```

**Result: failed** on two-slot handoff (child exit 1, stage evidence malformed).

## Authoritative DB

Unchanged throughout (never mutated):

| Fact | Value |
|---|---|
| Path | `data/printer_v1.sqlite3` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| Size / inode | `68067328` / `1230526` |

## Explicit confirmations

- No real authorization created.
- No live provider contact.
- No live `WINDOW_15M` campaign against the authoritative database.
- No merge to `master`; no tag.

## Exact next permitted step

Design and implement a continuous ordinary-path graduated-supply freeze that:

1. records non-empty MeasuredTransport stage evidence for every started stage;
2. produces four memory-observation-eligible candidates and two+two selection;
3. completes two controlled 900-second windows with clean episodes and exact
   Lane K fingerprints;

then re-run the single continuous wrapper-to-memory proof until PASS.

Do not create a real authorization until that continuous proof passes and an
independent read-only readiness review follows.
