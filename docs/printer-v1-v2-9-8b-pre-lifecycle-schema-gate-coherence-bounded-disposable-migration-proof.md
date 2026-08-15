# Printer V1 V2-9.8B Pre-Lifecycle Schema / Gate Coherence — Bounded Disposable Migration-056 Proof

Date: 2026-08-15

## Verdict

`V2_9_8B_PRE_LIFECYCLE_SCHEMA_GATE_COHERENCE_BOUNDED_DISPOSABLE_MIGRATION_PROOF_PASS_READY_FOR_CLOSEOUT`

## Boundary

Proof only. Migration 056 was **not** applied authoritatively. No providers,
discovery, Source Governor runtime, Scheduler runtime, campaign, memory
generation, retrieval, paper decisions, positions, trades, audits, or PnL. Every
migration ran against disposable copies. All proof evidence lives in a disposable
proof root outside the repository; the real
`operator-runs/v2-9-8b-migration-056-application` package was **not** created.

## Lane identity

- Baseline / starting HEAD: `6b99e32bef38661f093e29837f2a1c3d45661347`
- Final code HEAD: `6b99e32bef38661f093e29837f2a1c3d45661347` — unchanged. This
  lane adds one commit carrying this report plus one focused proof test.
- Disposable proof root: `…/scratchpad/mig056-proof-154917Z/`
- The user's working repository (HEAD `8fbfb088…`) and untracked operator
  evidence were untouched.

## 1. Pre-copy source identity

| check | value |
| --- | --- |
| sha256 | `9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39` |
| `-wal` / `-shm` / `-journal` | all absent |
| `integrity_check` | `ok` |
| foreign-key violations | `0` |
| ledger / head | `55` / `055_pre_admission_discovery_attempt_ownership.sql` |
| migration-056 table | absent |

## 2. Disposable copies begin at exact 55/055

Two byte-identical copies were taken:

- `disposable-56.sqlite3` — the migration target
- `disposable-55-control.sqlite3` — the untouched control

Both opened at sha `9d0addd9…` (identical to source), ledger `55`, head `055`,
migration-056 table absent.

## 3. Exact migration delta

Applied through the normal chain
(`printer_v1.db.migrate.apply_migrations`), resolving `MIGRATIONS_DIR` from the
proof worktree with canonical head
`056_four_token_pre_lifecycle_terminal_provenance.sql`.

Result on `disposable-56.sqlite3`:

- ledger `55` → **`56`**, head → **`056_four_token_pre_lifecycle_terminal_provenance.sql`**
- sha `9d0addd9…` → `dfdced4a5fa476c682ec3df631af50f89984f9950053376370a1600657743c95`
- table count `114` → `115`

Ledger delta is exactly one row added
(`056_four_token_pre_lifecycle_terminal_provenance.sql`), zero removed.

## 4. Schema and preservation evidence

**Added, exactly one table:** `printer_four_token_pre_lifecycle_terminal_provenance`
(0 rows on creation). **Removed: none.**

All five triggers present:

- `printer_four_token_pre_lifecycle_provenance_exact_shape`
- `printer_four_token_pre_lifecycle_provenance_immutable_update`
- `printer_four_token_pre_lifecycle_provenance_immutable_delete`
- `printer_pre_admission_attempt_forbids_pre_lifecycle_provenance`
- `printer_pre_admission_attempt_immutable_delete`

DDL constraints verified present: `cycle_ordinal = 1`,
`proposed_cycle_ordinal = 2`, `terminal_phase = 'CAMPAIGN_PRE_LIFECYCLE'`,
composite `PRIMARY KEY`, and `FOREIGN KEY` bindings.

**Preservation:** of the 114 pre-existing tables, **113 are byte-identical** by
content hash. The single changed table is `printer_schema_migrations`, whose
change is exactly the one expected ledger row. No pre-existing row in any other
table was added, altered, or removed.

Post-migration `integrity_check = ok`, foreign-key violations `0`.

## 5. Gate admission evidence

Re-pinned gate constants: `REQUIRED_MIGRATION_COUNT = 56`,
`REQUIRED_MIGRATION_HEAD = 056_four_token_pre_lifecycle_terminal_provenance.sql`.

| | migrated-56 | control-55 |
| --- | --- | --- |
| ledger / head | 56 / 056 | 55 / 055 |
| gate migration pins satisfied | **True** | **False** |
| canonical drift guard passed | **True** | **False** |
| eleven zero-state domains all zero | True | True |
| integrity / FK / sidecars | ok / 0 / none | ok / 0 / none |

The control is rejected by *both* independent checks — the explicit gate pin and
the canonical ledger drift guard (`migration_ledger_missing: ['056_…']`). The
migrated copy passes both. This is the coherence the repair was for: before it,
no schema satisfied gate and repair together.

## 6–7. Behavioural proofs

**Normal two-cycle admission compatibility.** `TWO_CYCLE_COMPLETION` remains
proven on migration 056 —
`tests/test_v2_9_8b_four_token_factory_terminal_integration.py` passes unchanged,
so the new triggers on `printer_pre_admission_discovery_attempts` do not regress
the legitimate admission path.

**`ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` terminalization with provenance.**
`tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py` passes:
Phase A returns `pre_lifecycle_zero_attempt_provenance_recorded = True` with
exactly one provenance marker, zero cycle-2 attempts, zero windows; Phase B
returns `admitted_shape = "ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT"` and
`shared_terminalized = True`.

**Non-stranding (requirement 7).** The existing suite proved terminalization and
admitted shape but did **not** assert absence of stranding, so this proof adds
`tests/test_v2_9_8b_pre_lifecycle_zero_attempt_no_stranding.py` (2 tests, both
pass), using the same canonical helpers:

- `test_early_cycle1_terminal_leaves_no_stranded_ownership` — after the early
  Cycle-1 terminal, campaign, run, and cycle are all `TERMINAL_*`, the factory
  run is no longer `RUNNING`, zero supervision rows remain `ACTIVE`/`STOPPING`,
  zero tracking-queue rows remain in a claimed state, and the full eleven-domain
  projection returns **all zero**.
- `test_without_migration_056_the_same_path_strands_ownership` — the migration-55
  counterfactual. With the 056 objects dropped, the identical call raises
  `provenance table is missing`, campaign/run/cycle stay non-terminal, the factory
  run stays `RUNNING`, and the projection is non-zero.

That counterfactual is the decisive evidence: it reproduces the exact stranding
this programme spent multiple lanes clearing, and shows migration 056 removes it.

## 8. Evidence identity scope

- `operator-runs/v2-9-8b-migration-056-application` does **not** exist in the
  repository or the proof worktree — deliberately not created.
- The profile's current migration root resolves to that path and is reported
  absent, so authorization preparation remains fail-closed until a separate
  migration lane produces real evidence.
- All proof artefacts (`disposable-56.sqlite3`,
  `disposable-55-control.sqlite3`, pre/post snapshots) live only under the
  disposable proof root.

## 9. Historical reconciliation remains pinned to 55/055

Static: `operational_campaign_recovery` still contains `len(migrations) != 55`
and the `055_pre_admission_discovery_attempt_ownership.sql` head, and contains
neither `!= 56` nor `056_four_token` — no silent reinterpretation.
`test_historical_reconciliation_contract_remains_pinned_to_55` locks this.

Empirical: `_historical_preflight` was invoked against both disposable copies and
rejected both with `historical authoritative DB SHA mismatch`. Its pinned
pre-reconciliation sha `5e830af4…` no longer matches the post-reconciliation
database, so that operation is permanently closed and cannot be re-entered at any
schema. The sha guard fires ahead of the migration assertion, which is why the
static evidence is the primary proof of the 55 pin.

## 10. Authoritative database unchanged

Rechecked after all proof work:

- sha256 `9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39` — unchanged
- no `-wal` / `-shm` / `-journal`
- ledger `55`, head `055_pre_admission_discovery_attempt_ownership.sql`
- migration-056 table **absent**
- `integrity_check = ok`, foreign-key violations `0`

## Test summary

Focused set, minimum sufficient:

```
tests/test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py
tests/test_v2_9_8b_pre_lifecycle_zero_attempt_no_stranding.py     (new)
tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py
tests/test_v2_9_8b_four_token_factory_terminal_integration.py
tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py
tests/test_v2_9_8b_four_token_proof_zero_state_gate.py
tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py
tests/test_v2_9_8b_four_token_historical_migration_provenance.py

-> 61 passed, 10 subtests passed
```

`py_compile` on the new test: PASS. `git diff --check`: PASS. The known
`AUTHORIZATION_EXPIRED` fixture failure is out of scope and did not appear in
this set.

## Money-usefulness contribution

Converts the migration-056 admission repair from an argued design into measured
evidence, before spending any authoritative schema change. The counterfactual
test in particular means the repair's value is demonstrated rather than assumed:
without 056 the early-Cycle-1 path provably strands ownership; with it, the
eleven-domain projection returns to all zero. That is the difference between
authorizing a migration on reasoning and authorizing it on proof.

## What improved

- Migration 056's delta is now measured: exactly one new table, exactly one new
  ledger row, 113 of 114 pre-existing tables byte-identical.
- Gate admission is demonstrated on real migrated data rather than synthetic
  fixtures, with a control copy proving rejection.
- Non-stranding is now an asserted property with a counterfactual, closing the
  gap the existing suite left.
- Normal two-cycle admission is shown compatible with the new triggers.
- Evidence-identity scope and the historical 55/055 pin are both verified.

## What remains locked

Authoritative migration-056 application, four-token proof execution, fresh
authorization creation, reuse of any consumed authorization, six-token proof and
capacity widening, 12h/24h activation, source fetching and discovery, memory
generation, Scheduler work creation, campaign start, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets, private keys,
signing, live execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative DB remains at 55/055 and is therefore still rejected by the
  gate. Nothing is unblocked operationally until a separate lane applies
  migration 056 authoritatively.
- The proof exercised the new pre-admission triggers only through the existing
  two-cycle integration test. Real historical campaigns on the authoritative
  database contain far more attempt history; the authoritative migration lane
  should re-verify FK and trigger coexistence against the real data, which this
  proof did on a full copy but only for schema, not for every legacy write path.
- The attempt-immutability trigger remains irreversible without a further
  migration. This proof confirms it installs cleanly; it does not make it undoable.
- `_historical_preflight` could not isolate its migration-55 assertion because the
  sha guard fires first. The 55 pin is proven statically and by test, not by that
  runtime path.
- Applying 056 authoritatively will change the authoritative sha, invalidating
  every artefact pinning `9d0addd9…`.
- The tracking-queue readiness blind spot remains open in its own deferred lane;
  the non-stranding test asserts only the claimed-state queue domains.
- Test scope was deliberately focused per the risk-based verification policy. A
  broader regression sweep belongs to the migration lane's closeout.

## Next permitted lane

Closeout of this bounded disposable proof, then a readiness review for
authoritative migration-056 application. Migration 056 must not be applied to the
authoritative database before that review closes PASS.
