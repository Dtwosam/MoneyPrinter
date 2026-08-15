# Printer V1 V2-9.8B Pre-Lifecycle Schema / Gate Coherence Implementation

Date: 2026-08-15

## Verdict

`V2_9_8B_PRE_LIFECYCLE_SCHEMA_GATE_COHERENCE_IMPLEMENTATION_PASS_READY_FOR_BOUNDED_DISPOSABLE_MIGRATION_PROOF`

## Boundary

Design baseline `6eb8a6714d229fac09cfa00347f87fb376ec31b3`. Implementation only:
no authoritative DB mutation, migration 056 was **not** applied to the
authoritative database, no Printer/Scheduler/runtime, no source fetch, no memory
generation, no campaign, no retrieval/decisions/trading. Every migration
exercised in tests ran against disposable `tmp_path` databases. The user's
working repository (HEAD `8fbfb088…`) was untouched; work was done in a separate
worktree.

## Changed files

Production (2):

- `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` —
  `REQUIRED_MIGRATION_COUNT` 55 → **56**, `REQUIRED_MIGRATION_HEAD` 055 → **056**,
  with a comment recording that these are deliberately explicit literals and that
  a future head requires its own gate review.
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` — new
  `MIGRATION_056_PACKAGE_KIND` / `MIGRATION_056_PACKAGE_ROOT`; new
  `HISTORICAL_MIGRATION_055_EVIDENCE_CLASS` /
  `FOUR_TOKEN_HISTORICAL_MIGRATION_055_EXECUTION_ID`; the four-token profile's
  current migration package advanced to 056.

Tests (4):

- `tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py` — **new**, 12 tests
- `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` — expected count/head
  56/056; test renamed `…post_055…` → `…post_056…`
- `tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py` — harness now
  builds under the profile's *current* migration root; current-identity
  assertions moved to 056; explicit 055-vs-056 distinctness assertions added
- `tests/test_v2_9_8b_four_token_historical_migration_provenance.py` — the
  "050 never becomes current" test now compares against the 056 current kind/root

Unchanged, as required: migration 056 SQL, pre-lifecycle terminalization logic,
the historical reconciliation's intentional 55/055 pins, tracking-queue
semantics, source/Scheduler/runtime/memory behaviour, and operational mutation
allowlists.

## RED evidence

New test file run **before** any production edit:

```
8 failed, 3 passed
```

Failing: gate admits 056 · gate rejects the superseded 055 pin · pins are literal
constants · disposable schema-56 satisfies the pins · disposable schema-55 does
not · profile current evidence is 056 · profile historical-package shape · 055
constants preserved and distinct.

Already passing (correctly, pre-change): the canonical ledger drift guard is
still wired into the gate; migration-056 provenance objects exist on a disposable
schema; the historical reconciliation contract is pinned to 55/055.

## GREEN evidence

New test file after implementation: **12 passed**.

Full directly-affected set:

```
tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py
tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py
tests/test_v2_9_8b_four_token_proof_zero_state_gate.py
tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py
tests/test_v2_9_8b_four_token_historical_migration_provenance.py
tests/test_v2_9_8b_four_token_proof_authorization_profile.py
tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py
tests/test_v2_9_8b_four_token_factory_terminal_integration.py
tests/test_v2_9_8b_pre_admission_discovery_attempt_schema.py

-> 1 failed, 75 passed, 10 subtests passed
```

Each required verification, met:

| requirement | evidence |
| --- | --- |
| schema-55 / old pin rejected | `test_disposable_schema_55_does_not_satisfy_the_gate_migration_pins`, `test_zero_state_gate_rejects_the_superseded_055_pin` |
| schema-56 / head056 satisfies the gate's migration portion | `test_disposable_schema_56_satisfies_the_gate_migration_pins`, `test_quiescent_post_056_database_passes_read_only` |
| `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` still proven on 056 | `test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py` — all pass unchanged |
| normal two-cycle admission still compatible with 056 | `test_v2_9_8b_four_token_factory_terminal_integration.py` (`TWO_CYCLE_COMPLETION`) passes |
| historical reconciliation still pinned 55/055 | `test_historical_reconciliation_contract_remains_pinned_to_55` |
| 056 provenance immutability / contradictory-attempt protection intact | `test_migration_056_provenance_objects_exist_on_disposable_schema` (all 5 triggers) plus the existing immutability tests |
| canonical drift guard intact | `test_canonical_ledger_drift_guard_is_still_wired_into_the_gate` |
| pins are not dynamically derived | `test_gate_migration_pins_are_explicit_literals_not_derived` (AST assertion + absence of `canonical_migration_*` in the module) |

`py_compile` on both changed production modules: PASS. Import check confirms
pins `56` / `056…`, current root `operator-runs/v2-9-8b-migration-056-application`,
kind `MIGRATION_056_EVIDENCE`. `git diff --check`: PASS. Net diff: 5 files,
+57 / −15.

### The one remaining failure is pre-existing

`test_v2_9_8b_four_token_proof_authorization_profile.py::test_exact_four_token_fixture_document_validates`
fails with `AUTHORIZATION_EXPIRED`. Confirmed against baseline by stashing all
`src/` and `tests/` changes and re-running the single test: it fails identically
with no changes applied. This is the recurring wall-clock-dependent authorization
fixture-expiry defect, unrelated to schema or gate pins. Documented and deferred,
not fixed here.

The baseline run also showed two further `AUTHORIZATION_EXPIRED` failures
(`test_long_windows_remain_locked`, `test_historical_terminal_supervision_does_not_block`)
that pass in later runs — confirming that failure class is time-sensitive and
flaky rather than deterministic.

## Scope decision: a broader contract change was found and NOT adopted

The design said to preserve 050/055 historical evidence semantics. Implementing
that literally — declaring 055 as a second `HistoricalMigrationPackage` — was
attempted and then **reverted**, because it is a broader contract change than the
approved repair.

`_bind_historical_migration_packages()` documents that "Every declared package is
required, not optional." Declaring 055 would therefore make its operator evidence
mandatory for **every** four-token manifest build, forever. In the real
repository that evidence is untracked operator output which could legitimately be
pruned; the first prune would fail manifest builds closed on evidence that was
never previously required. It also broke 11 existing provenance tests whose
fixtures build only a 050 evidence root.

Resolution, per the instruction to classify rather than widen: 056 becomes
current; 050 remains the single declared required historical package; 055 keeps
its own constants, evidence class, and execution identity so a later lane can
promote it deliberately. `test_055_is_not_newly_promoted_to_a_required_historical_package`
locks that decision in place so it cannot be adopted by accident.

**Classification:** `DEFERRED_CONTRACT_DECISION` — promoting migration 055 to a
required historical package is a separate lane with its own evidence-retention
implications.

## Money-usefulness contribution

Makes bounded four-token admission coherent for the first time since migration
056 landed in the repository. Before this change no schema could both enter the
gate and safely terminalize an early Cycle-1 failure, so any authorization
prepared against the current contract would have been spent on a state that
could re-strand campaign ownership. This is a two-constant change that removes
that trap without touching terminalization logic.

## What this improves

- The zero-state gate now admits exactly the schema whose provenance table the
  pre-lifecycle repair requires.
- The pins stay explicit, so a future migration cannot silently re-authorize
  bounded-proof admission — enforced by an AST test, not convention.
- The canonical migration-ledger drift guard is untouched and still runs.
- Migration 056 becomes the current evidence identity while 050 keeps its
  historical role and 055 keeps its identity without gaining new obligations.
- The historical reconciliation contract remains truthfully pinned to the state
  it describes.

## What remains locked

Migration-056 application to the authoritative database, four-token proof
execution, fresh authorization creation, reuse of any consumed authorization,
six-token proof and capacity widening, 12h/24h activation, source fetching and
discovery, memory generation, Scheduler work creation, campaign start, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL,
wallets, private keys, signing, live execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative DB is still at 55/055, so the gate now rejects it. That is
  intended and fail-closed, but it means **no bounded four-token operation can
  proceed until migration 056 is applied**. The block simply moved from an
  unreachable contradiction to an explicit, satisfiable prerequisite.
- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.migration_package_root` now points at
  `operator-runs/v2-9-8b-migration-056-application`, which does not yet exist.
  Manifest builds and authorization preparation will fail closed until the
  migration lane creates that evidence root. Correct by design, but it must not
  be misread as a regression.
- Migration 056 adds a trigger making `printer_pre_admission_discovery_attempts`
  rows permanently undeletable, and another that aborts attempt inserts
  contradicting provenance. Irreversible without a further migration; the
  disposable migration proof must exercise a normal two-cycle admission on a copy
  of real data, not only synthetic fixtures.
- The `AUTHORIZATION_EXPIRED` fixture-expiry defect is unfixed and recurring. It
  currently masks assertions in at least one gate test; those assertions were
  corrected here but cannot be observed passing until that defect is repaired.
- Test-suite scope was limited to directly affected modules per the
  risk-based verification policy. A broader regression sweep belongs to the
  migration lane's closeout.
- The tracking-queue readiness blind spot is untouched and still open.

## Exact next proof requirement

A **bounded disposable migration-056 proof**, before any authoritative
application:

1. Copy the authoritative DB byte-identically; verify the copy's sha equals the
   current authoritative sha `9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39`.
2. Apply migration 056 to the copy only.
3. Prove on the copy: ledger 56 / head 056; the provenance table and all five
   triggers present; `integrity_check = ok`; foreign-key violations 0; every
   pre-existing table hash unchanged; locked retrieval/financial hashes
   unchanged; all eleven zero-state domains still exactly 0; the reconciled
   historical execution rows still terminal with the exact preserved cause
   `FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`.
4. Prove `evaluate_migration_ledger_drift(mode="review")` passes on the migrated
   copy and still fails on an unmigrated copy.
5. Exercise one normal two-cycle admission and one early-Cycle-1 pre-lifecycle
   terminal against the migrated copy, proving the latter now terminalizes
   instead of raising.
6. Confirm the authoritative DB sha is unchanged throughout.

Only after that proof closes may a readiness review authorize authoritative
migration-056 application.
