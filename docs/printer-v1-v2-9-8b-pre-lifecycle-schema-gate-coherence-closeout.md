# Printer V1 V2-9.8B Pre-Lifecycle Schema / Gate Coherence Closeout

Date: 2026-08-15

## Verdict

`V2_9_8B_PRE_LIFECYCLE_SCHEMA_GATE_COHERENCE_CLOSEOUT_PASS_READY_FOR_AUTHORITATIVE_MIGRATION_056_READINESS_REVIEW`

## Lane chain

| stage | commit | verdict |
| --- | --- | --- |
| Audit (recurrence / gate completeness) | `858bded8ad6ecf60bc71e7e0c74c8bf776e171eb` | `…AUDIT_BLOCKED:pre_lifecycle_zero_attempt_provenance_requires_migration_056_absent_from_authoritative_db` |
| Design | `6eb8a6714d229fac09cfa00347f87fb376ec31b3` | `…DESIGN_PASS_READY_FOR_IMPLEMENTATION` |
| Implementation | `6b99e32bef38661f093e29837f2a1c3d45661347` | `…IMPLEMENTATION_PASS_READY_FOR_BOUNDED_DISPOSABLE_MIGRATION_PROOF` |
| Bounded disposable proof | `8c58e9241d21a8e44f4ebeaee95af59093ae80f4` | `…BOUNDED_DISPOSABLE_MIGRATION_PROOF_PASS_READY_FOR_CLOSEOUT` |
| Closeout (this document) | this commit | see verdict above |

No authoritative database mutation occurred at any stage of this chain.

## What the chain established

### The contradiction and its resolution

The audit found that bounded four-token admission was unsatisfiable at any
schema: the zero-state gate pinned migration 55 / head 055, while
`ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` required the migration-056 provenance
table. The design measured a sharper fact — `canonical_migration_count()` already
derives 56 from the committed migrations directory, so
`evaluate_migration_ledger_drift(mode="review")` already rejected the
authoritative database outright. Schema 55 was not an available option; the
55/055 constants were the stale artefacts.

### Gate moved from 55/055 to explicit 56/056

`four_token_proof_zero_state_gate.py` now pins:

```python
REQUIRED_MIGRATION_COUNT = 56
REQUIRED_MIGRATION_HEAD = "056_four_token_pre_lifecycle_terminal_provenance.sql"
```

These are deliberately **explicit literals**, never derived from the migrations
directory, so a future migration cannot silently re-authorize bounded-proof
admission. An AST test asserts both are `ast.Constant` and that
`canonical_migration_count` / `canonical_migration_names` do not appear in the
module. The canonical migration-ledger drift guard was left fully intact and
still runs independently.

### Migration-056 provenance is required for the early shape

`_validate_pre_lifecycle_zero_attempt_provenance_shape()` fails closed with
`pre-lifecycle zero-attempt provenance table is missing` when the table is
absent, and it runs early inside `reconcile_four_token_cycle_terminal()` —
before any terminalization write. The factory supplies
`terminal_phase="CAMPAIGN_PRE_LIFECYCLE"` exactly on the early-Cycle-1 path. So
without migration 056 the repair is not merely inert; it actively aborts before
terminalizing.

### 55 control rejected, 56 copy admitted

Two byte-identical copies of the authoritative database were taken at
`9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39`; one was
migrated through the canonical runner, one held as an untouched control.

| | migrated-56 | control-55 |
| --- | --- | --- |
| ledger / head | 56 / 056 | 55 / 055 |
| gate migration pins satisfied | **True** | **False** |
| canonical drift guard passed | **True** | **False** |
| eleven zero-state domains all zero | True | True |
| integrity / FK / sidecars | ok / 0 / none | ok / 0 / none |

The control is rejected by both independent checks; the migrated copy passes
both.

### Measured migration delta and preservation

- ledger `55` → `56`, head `055` → `056`
- sha `9d0addd9…` → `dfdced4a5fa476c682ec3df631af50f89984f9950053376370a1600657743c95`
- exactly **one** table added: `printer_four_token_pre_lifecycle_terminal_provenance`
  (0 rows), zero removed
- all five triggers present; DDL `CHECK`s, composite `PRIMARY KEY`, and `FOREIGN KEY`s verified
- of 114 pre-existing tables, **113 byte-identical**; the only change is the one
  expected `printer_schema_migrations` row
- post-migration `integrity_check = ok`, foreign-key violations `0`

### Normal TWO_CYCLE_COMPLETION still passes

`tests/test_v2_9_8b_four_token_factory_terminal_integration.py` passes unchanged
on migration 056, so the new triggers on
`printer_pre_admission_discovery_attempts` do not regress the legitimate
two-cycle admission path.

### Early Cycle-1 terminal leaves zero stranded ownership

The existing zero-attempt suite proved terminalization and admitted shape but
never asserted absence of stranding. The proof lane added
`tests/test_v2_9_8b_pre_lifecycle_zero_attempt_no_stranding.py`, which proves
that after the early Cycle-1 terminal:

- campaign, run, and cycle are all `TERMINAL_*`
- the factory run is no longer `RUNNING`
- zero supervision rows remain `ACTIVE`/`STOPPING`
- zero tracking-queue rows remain in a claimed state
- the full eleven-domain projection returns **all zero**

### Counterfactual without 056 reproduces stranding

The same module's second test drops the 056 objects and repeats the identical
call. It raises `provenance table is missing`; campaign, run, and cycle stay
non-terminal; the factory run stays `RUNNING`; the projection is non-zero. This
reproduces exactly the stranding the residue programme spent multiple lanes
clearing, and demonstrates that migration 056 removes it.

Focused verification across the affected set: **61 passed, 10 subtests passed**.
`py_compile` and `git diff --check` pass.

## Boundaries deliberately preserved

### Historical reconciliation remains its closed historical 55/055 contract

`operational_campaign_recovery` still pins `len(migrations) != 55` and the 055
head, and contains neither `!= 56` nor `056_four_token`. A test locks this.
Empirically, `_historical_preflight` rejects both disposable copies with
`historical authoritative DB SHA mismatch`: its pinned pre-reconciliation sha
`5e830af4…` no longer matches the post-reconciliation database, so that operation
is permanently closed and cannot be re-entered at any schema. Advancing its pins
would falsify its own provenance, so they were not touched.

### Migration-055 historical-package promotion remains deferred

Declaring 055 as a second `HistoricalMigrationPackage` was attempted during
implementation and reverted. Every declared package is mandatory for every
manifest build, so promoting 055 would newly require its untracked operator
evidence to exist forever and would fail closed the first time it were pruned; it
also broke 11 provenance-fixture tests. 055 keeps its own constants, evidence
class, and execution identity for a deliberate later lane, and
`test_055_is_not_newly_promoted_to_a_required_historical_package` prevents
accidental adoption.

**Classification:** `DEFERRED_CONTRACT_DECISION`.

### Tracking-queue vocabulary gap remains non-blocking and separate

`project_four_token_proof_zero_state()` does not cover `printer_tracking_queue`,
and `bounded_readiness_report`'s filter
(`PENDING`/`ACTIVE`/`TRACK_FAST`/`TRACK_NORMAL`) omits `QUEUED` and is not invoked
by any four-token gate. The 17 `QUEUED` rows on the authoritative database are
historical (ids 1–17, created 2026-06-21 to 2026-07-27), hold no Scheduler job
and no campaign ownership, and were classified `NON_BLOCKING_KNOWN_LIMITATION`.
The proposed future rule — block on *ownership binding plus Scheduler claim*, not
bare `QUEUED` state — is recorded for its own lane. Existing historical queue rows
must not be cleaned or rewritten.

## Authoritative database — still untouched

Rechecked at closeout:

- sha256 `9d0addd9e2b4859a33d07810cee26ec0893ada3ae884bde740719a4ec20e3b39`
- ledger `55`, head `055_pre_admission_discovery_attempt_ownership.sql`
- migration-056 table **absent**
- no `-wal` / `-shm` / `-journal`
- `integrity_check = ok`, foreign-key violations `0`

The real `operator-runs/v2-9-8b-migration-056-application` evidence package was
deliberately **not** created; all proof artefacts lived in a disposable proof root
outside the repository.

## Money-usefulness contribution

Turns a blocking contradiction into a proven, bounded, single-step prerequisite
without spending an authoritative schema change or a one-use authorization. The
counterfactual test means the repair's value is measured rather than argued: the
early-Cycle-1 path provably strands ownership without migration 056 and provably
does not with it.

## What this lane improves

- Bounded four-token admission is coherent for the first time since migration 056
  landed in the repository.
- The gate's authorized schema is explicit and change-reviewed, enforced by test
  rather than convention.
- The pre-lifecycle repair is reachable instead of aborting before terminalization.
- Non-stranding is now an asserted property with a counterfactual.
- Historical provenance boundaries (reconciliation 55/055, migration-050
  historical evidence) are preserved rather than reinterpreted.

## What remains locked

Authoritative migration-056 application, four-token proof execution, fresh
authorization creation, reuse of any consumed authorization, six-token proof and
capacity widening, 12h/24h activation, source fetching and discovery, memory
generation, Scheduler work creation, campaign start, retrieval, paper decisions,
BUY/SELL/HOLD, positions, trade events, paper audits, PnL, wallets, private keys,
signing, live execution, real funds, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The authoritative database is still at 55/055 and is therefore now rejected by
  the gate. Nothing is unblocked operationally until a separate lane applies
  migration 056. The block moved from an unreachable contradiction to an explicit
  prerequisite.
- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE.migration_package_root` points at
  `operator-runs/v2-9-8b-migration-056-application`, which does not yet exist, so
  manifest builds and authorization preparation fail closed until the migration
  lane produces it. Correct by design; not a regression.
- Migration 056 makes `printer_pre_admission_discovery_attempts` rows permanently
  undeletable and aborts attempt inserts contradicting provenance. Irreversible
  without a further migration; it warrants explicit operator acknowledgement.
- The new triggers were exercised through the integration suite on a full copy for
  schema, not across every legacy attempt-write path. The migration lane should
  re-verify trigger coexistence against real attempt history.
- Applying 056 will change the authoritative sha, invalidating artefacts pinning
  `9d0addd9…`.
- The recurring wall-clock `AUTHORIZATION_EXPIRED` fixture defect remains unfixed
  and out of scope.
- Test scope was focused per the risk-based verification policy; a broader sweep
  belongs to the migration lane's closeout.

## Next permitted lane

Authoritative migration-056 readiness review. Migration 056 must not be applied
before that review closes PASS.
