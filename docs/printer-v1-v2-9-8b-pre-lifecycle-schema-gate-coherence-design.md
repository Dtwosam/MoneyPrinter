# Printer V1 V2-9.8B Pre-Lifecycle Schema / Gate Coherence Design

Date: 2026-08-15

## Verdict

`V2_9_8B_PRE_LIFECYCLE_SCHEMA_GATE_COHERENCE_DESIGN_PASS_READY_FOR_IMPLEMENTATION`

## Boundary

Design only. No DB mutation, no migration-056 execution, no production code
change, no Printer/Scheduler start, no source fetch, no memory generation, no
campaign. Baseline: the post-clearance recurrence/gate audit at
`858bded8ad6ecf60bc71e7e0c74c8bf776e171eb`. The authoritative DB was read
read-only at sha `9d0addd9…`, migrations `55`, head `055`.

## Selected design

**Option A — advance the authoritative schema and readiness contract to migration
056.** Option B (retain schema 55 with an equivalent alternative provenance
mechanism) is rejected, and the evidence makes that rejection non-discretionary.

### The decisive evidence: schema 55 is already non-viable

The audit framed this as "gate wants 55, repair wants 56, pick one." Direct
measurement shows schema 55 is not actually an available option.

`four_token_proof_zero_state_gate.py:313` calls
`assert_migration_ledger_ready(mode="review", …)` and records any failure as a
`migration_ledger_drift` blocker. Run against the authoritative database with the
committed migrations directory, that guard **already fails**:

```
pre-authorization migration-ledger guard blocked:
  migration_ledger_missing: missing canonical migrations:
    ['056_four_token_pre_lifecycle_terminal_provenance.sql']
  migration_count_mismatch: applied count 55 != canonical count 56
  migration_head_mismatch: applied head '055_…' != canonical head '056_…'
```

`canonical_migration_count()` is derived from the migrations directory, never
hard-coded (`db/migrate.py:138`), and returns **56** because
`migrations/056_four_token_pre_lifecycle_terminal_provenance.sql` is committed.

So the current authoritative database cannot pass the four-token zero-state gate
**at all** — not because of the `REQUIRED_MIGRATION_COUNT = 55` pin, but because
the canonical ledger already demands 056. The two hard-coded constants at
`four_token_proof_zero_state_gate.py:41–42` are now the *stale* artifacts, not the
schema. Migration 056 is not an optional enhancement; it is already the canonical
schema, and the database is behind it.

### Why Option B is rejected

Retaining schema 55 would require deleting or reverting
`migrations/056_…sql` from the canonical set. That would:

- destroy a committed, DB-enforced provenance mechanism whose guarantees are
  stronger than anything reachable in application code (see below), and
- leave the `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` shape with no provenance at
  all, restoring the original stranding defect.

No application-level substitute can match migration 056's guarantees, because
they are enforced by SQLite itself rather than by a caller that can be bypassed:

- `CHECK` constraints pin `cycle_ordinal = 1`, `proposed_cycle_ordinal = 2`,
  `terminal_phase = 'CAMPAIGN_PRE_LIFECYCLE'`, and non-empty
  `first_terminal_cause` / `recorded_at`;
- a composite primary key makes the record singular per
  campaign/run/factory-run/proposed-ordinal;
- four foreign keys bind it to the exact campaign, run, factory run, and cycle;
- a `BEFORE INSERT` trigger independently re-proves owner identity
  (`run_state = 'RUNNING'`, `authoritative_run_id` match), exactly one cycle,
  live Cycle 1, exactly two Cycle-1 slots, no Cycle 2, no Cycle-2 attempt
  evidence, and no lifecycle windows;
- `BEFORE UPDATE` and `BEFORE DELETE` triggers make the row **immutable**;
- a reciprocal trigger on `printer_pre_admission_discovery_attempts` forbids
  inserting a Cycle-2 attempt that would contradict existing provenance, and a
  further trigger makes attempts non-deletable.

Option B would have to reproduce all of that in Python, where it is bypassable
and where forensic truth would depend on the writer rather than the store. That
is strictly weaker provenance, weaker fail-closed behaviour, and weaker forensic
truth — the three properties the task requires B to preserve. B therefore fails
its own admission test.

## Exact contract changes required

Precisely two production edits. Both are constant re-pins, not logic changes.

1. `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py:41–42`

   ```python
   REQUIRED_MIGRATION_COUNT = 56
   REQUIRED_MIGRATION_HEAD = "056_four_token_pre_lifecycle_terminal_provenance.sql"
   ```

   Preferably derived from `canonical_migration_count()` /
   `canonical_migration_names()[-1]` so this constant can never drift from the
   migrations directory again. If derivation is judged too broad a change for this
   lane, re-pin the literals and add a test asserting they equal the canonical
   values.

2. A new migration-056 evidence root for the four-token authorization profile in
   `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py:61–62`
   and `:145–146`:

   ```python
   MIGRATION_056_PACKAGE_KIND = "MIGRATION_056_EVIDENCE"
   MIGRATION_056_PACKAGE_ROOT = "operator-runs/v2-9-8b-migration-056-application"
   ```

   with `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.migration_package_root` /
   `migration_package_kind` advanced to them. The existing
   `operator-runs/v2-9-8b-migration-055-application` root must be preserved as
   historical migration evidence, exactly as migration-050 evidence was preserved
   when 055 became current.

### Explicitly NOT changed

`operational_campaign_recovery.py:1152–1154` pins 55/055 for the **historical**
four-token reconciliation. That operation is complete, its idempotent path
returns `ALREADY_RECONCILED` with zero writes, and its contract describes a
past state. It must stay pinned to 55/055 as a historical record and must not be
advanced. Advancing it would falsify the reconciliation's own provenance.

No change to `finalize_four_token_shared_terminal()`,
`_validate_pre_lifecycle_zero_attempt_provenance_shape()`, the factory
`terminal_phase` trigger, the ten-identity allowlist, or the eleven zero-state
domains. The repair logic is already correct; only the schema and its pins move.

## Migration / readiness sequencing

1. **Bounded disposable rehearsal.** Apply 056 to a byte-identical disposable
   copy of the authoritative DB. Prove: ledger 56 / head 056; the provenance
   table, its three immutability triggers, and both pre-admission triggers exist;
   `integrity_check = ok`; FK `0`; every pre-existing table hash unchanged;
   locked retrieval/financial hashes unchanged; the eleven zero-state domains
   still all `0`; the historical reconciled rows still terminal with their
   original cause.
2. **Authoritative migration-056 application**, in its own lane, with an
   independent operator backup and an evidence root mirroring the 055 pattern
   (`pre_application_snapshot.json`, `authoritative-pre-056.sqlite3`,
   `migration_056_application_result.json`, `disposable_rehearsal.json`,
   `disposable/migration-056-rehearsal.sqlite3`).
3. **Production re-pin** of the two contract points above, with tests.
4. **Post-migration zero-state / readiness revalidation** (below).
5. Only then a fresh authorization-preparation lane.

Steps 1–2 and 3 may be ordered either way, but the gate re-pin must land before
any authorization is prepared, and the migration must land before any proof runs.

## Failure and rollback boundaries

- The rehearsal is disposable: failure means discard the copy and stop. No
  authoritative effect is possible.
- Authoritative application is a schema mutation and changes the DB sha. Rollback
  = restore byte-for-byte from the independent pre-056 backup, then re-verify sha
  `9d0addd9…`, `integrity_check = ok`, FK `0`, ledger 55/055, no sidecars, and
  that the historical reconciled rows remain terminal with their preserved cause.
- Stop-on-drift before applying: DB sha ≠ `9d0addd9…`; any sidecar; integrity or
  FK failure; ledger ≠ 55/055; the 056 table already present; any of the eleven
  zero-state domains non-zero; any live Printer process or DB holder; the
  intended evidence root already existing.
- Migration 056 wraps itself in `BEGIN IMMEDIATE … COMMIT`, so a mid-statement
  failure leaves no partial schema. It must be applied with no other writer
  present.
- One-shot caution: after 056 the DB sha changes permanently. Any artifact
  pinning `9d0addd9…` becomes stale by design, and a retry after a rolled-back
  failure must restore to `9d0addd9…` first.

## Implementation files and tests that would change

Production:

- `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` (two
  constants, ideally canonical-derived)
- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
  (migration-056 package kind/root; 055 retained as historical)

Tests:

- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py` — already
  applies 056 (`MIGRATION_056` at line 25) and covers the exact shape, the
  no-phase case, the fail-closed no-provenance case, immutability, and migration
  presence. Expected to pass unchanged; it becomes the primary regression.
- `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` — update expected
  migration count/head; add an assertion that the pins equal the canonical
  values.
- `tests/test_v2_9_8b_four_token_proof_authorization_profile.py` and
  `tests/test_v2_9_8b_four_token_historical_migration_provenance.py` — extend for
  the 056 current-evidence root while asserting 050 and 055 remain preserved
  historical evidence.
- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py` and
  `tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py` — confirm
  the early-Cycle-1 path now terminalizes instead of raising.

## Minimum sufficient bounded proof before authoritative migration

Focused tests only, no broad suite: the five pre-lifecycle zero-attempt tests,
the zero-state gate tests, the authorization-profile and historical-migration
provenance tests, plus `python -m py_compile` on the two changed modules and a
`git diff --check`. Then the disposable migration rehearsal from sequencing
step 1. No proof run, no authorization, no campaign.

## Required post-migration revalidation

- DB sha recorded as the new authoritative POST identity; no sidecars
- `integrity_check = ok`; FK `0`
- ledger `56` / head `056`; provenance table and all five triggers present
- `evaluate_migration_ledger_drift(mode="review")` now **passes**
- all eleven zero-state domains still exactly `0`, queried directly
- historical execution `20260814T172224Z-490856f405bf` rows still terminal with
  the exact preserved cause `FourTokenFactoryAdapterError: cycle terminal
  reconciliation requires a fresh transaction`
- locked retrieval/financial table hashes unchanged; no source/memory row created
- both historical evidence roots unchanged; 055 evidence root preserved
- no Printer/Scheduler process started

## Secondary task — `printer_tracking_queue` in mandatory readiness semantics

**Deferred to a separate lane.** It does not belong in this repair.

Reasoning and the precise proposed semantics, recorded so the deferral is not a
loss of analysis:

The queue's live-ownership question is genuinely separate from the schema
contradiction, and folding it in would expand a two-constant re-pin into a
semantics change affecting every campaign path that touches the queue. The audit
already classified it `NON_BLOCKING_KNOWN_LIMITATION` on measured evidence: the
17 non-terminal `QUEUED` rows are ids 1–17 created 2026-06-21 to 2026-07-27, none
on or after 2026-08-14, holding no Scheduler job (0 active or locked globally),
no campaign/run/cycle/supervision claim, and no lease.

The observed vocabulary on the authoritative DB is `SKIPPED` (27), `QUEUED` (17),
`COOLDOWN` (15). `bounded_readiness_report.py:84` filters
`PENDING`/`ACTIVE`/`TRACK_FAST`/`TRACK_NORMAL` — none of which occur — so it
matches `0` rows and provides no coverage; it is also not invoked by any
four-token gate.

Proposed future semantics, for the deferred lane to prove rather than assume:

- **Live ownership that must block** — a queue row that is *bound to the
  campaign/run/cycle under test* and in an actively-claimed state
  (`PENDING`/`ACTIVE`/`TRACK_FAST`/`TRACK_NORMAL`), or any queue row referenced by
  a `PENDING`/`RUNNING`/`COOLDOWN` or locked Scheduler job.
- **Not blocking** — `QUEUED` backlog rows with no Scheduler job and no
  campaign-scoped binding; `COOLDOWN`; `SKIPPED`. A bare `QUEUED` row is a
  discovery backlog entry, not ownership, and must not become a blocker.

The correct scoping test is *ownership binding plus Scheduler claim*, not queue
state alone. The existing historical queue rows must not be cleaned or rewritten
in either lane.

## Money-usefulness contribution

Restores the ability to enter a bounded four-token operation at all — currently
impossible, since the ledger drift guard rejects the authoritative DB outright —
while ensuring the early-Cycle-1 failure shape terminalizes instead of stranding
ownership. It prevents a third cycle of consuming scarce one-use authority to
rediscover a known state defect, and it chooses the mechanism whose guarantees
the database enforces rather than one the caller could bypass.

## What this improves

- Removes a contradiction that made the four-token gate unsatisfiable at any
  schema.
- Retires two stale hard-coded constants and, if derived, prevents that class of
  drift recurring.
- Makes the already-implemented pre-lifecycle repair actually reachable.
- Keeps historical reconciliation provenance pinned to the state it describes.
- Preserves 050 and 055 migration evidence while adding 056 as current.
- Records exact tracking-queue semantics without widening this repair.

## What remains locked

Four-token proof execution, fresh authorization creation, reuse of any consumed
authorization, six-token proof and capacity widening, 12h/24h activation, source
fetching and discovery, memory generation, Scheduler work creation, campaign
start, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper
audits, PnL, wallets, private keys, signing, live execution, real funds, paid
APIs, scoring/ranking/confidence/weighted logic, embeddings, and vectors.

Migration 056 application is itself locked until its own bounded lane.

## Minimum implementation / proof sequence

1. Implement the two contract re-pins; update the named tests.
2. Run the focused test set plus compile and diff checks.
3. Disposable migration-056 rehearsal on a byte-identical copy; prove schema,
   integrity/FK, unchanged table hashes, and all-zero zero state.
4. Independent readiness review of the migration plan.
5. Bounded authoritative migration-056 application with independent backup and a
   055-pattern evidence root.
6. Post-migration revalidation as specified above.
7. Separate lane: tracking-queue readiness semantics.
8. Only then: fresh four-token authorization preparation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Migration 056 adds five triggers, two of which fire on
  `printer_pre_admission_discovery_attempts` inserts and deletes. Any existing
  code path that deletes an attempt row will now abort. The rehearsal must
  exercise a normal two-cycle admission to prove no legitimate path regresses.
- The attempt-immutability trigger makes attempt rows permanently undeletable.
  This is intended forensic hardening but is irreversible without a further
  migration; it should be an explicit operator acknowledgement, not a side effect.
- Applying 056 changes the authoritative DB sha, invalidating every artifact
  pinning `9d0addd9…`.
- Re-pinning `REQUIRED_MIGRATION_COUNT` by literal repeats the drift that caused
  this contradiction. Canonical derivation is the durable fix and is preferred.
- The provenance FKs reference campaign/run/factory-run/cycle rows. Because
  migration 056 is applied after the historical reconciliation, the reconciled
  execution's rows are already terminal; the rehearsal must confirm the new FKs
  and triggers coexist with that terminal history without error.
- This design ran no tests and applied no migration. Every claim about test
  outcomes is a prediction to be verified in implementation.
- The tracking-queue blind spot remains open until its own lane; a future residue
  in that table would still be invisible to the eleven-domain gate.
