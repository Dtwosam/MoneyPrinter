# V2-9.8B — Pre-Authorization Migration-Ledger Drift Guard Implementation and Bounded Proof Closeout

Verdict: `V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_DRIFT_GUARD_PASS`

This lane implements the highest-value follow-up identified by the migration-052
application closeout. It is an implementation and bounded-proof lane. No
authorization was created, no `WINDOW_15M` run was performed, the authoritative
database was not mutated, and nothing was pushed.

## Baseline

* Working tree: `/Users/Dtwo1/Developer/MoneyPrinter`
* Baseline branch: `agent/v2-9-8b-authoritative-migration-052-application`
* Baseline HEAD: `bb258733c01e67a05f0f8c334ace46e9379cdb9f`
* Authoritative DB SHA-256: `5cf5326c4a820538a2f648a274bf14797c23a988bfae0f25aa49f01205cfafdc`
* Migration state: `52 / 052_memory_observation_eligibility_layers.sql`
* Implementation branch: `agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard`

## Problem this closes

Authorization `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` was permanently consumed
for zero campaign output. Its child exited before campaign identity creation with:

```
operational preflight blocked: gate=migration_ledger: missing canonical migrations: ['052_memory_observation_eligibility_layers.sql']
```

The operational preflight behaved correctly. The defect was purely one of
*ordering*: the preflight runs inside the child, and the authorization is
consumed the moment the wrapper begins. A structural question answerable in
milliseconds from two read-only sources was therefore first asked at the one
moment when answering it costs an entire non-reusable authorization.

This lane asks the same question earlier, where it is free, without weakening the
existing final defence.

## Implemented exactly

### 1. Strengthened canonical migration catalogue — `src/printer_v1/db/migrate.py`

* `MIGRATION_FILENAME_PATTERN` — exact filename contract: three-digit zero-padded
  ordinal, `_`, lowercase `[a-z0-9]` words joined by single underscores, `.sql`.
  Uppercase, doubled underscores, leading/trailing underscores, dash separators,
  short ordinals, and non-`.sql` suffixes are all rejected.
* `parse_migration_ordinal(name)` — ordinal extraction that raises on any
  violation of the contract.
* `describe_canonical_catalogue_issues(names)` — strict structural validation:
  malformed filenames, duplicate names, duplicate ordinals, non-lexicographic
  ordering, and any sequence that is not a contiguous gap-free `001..NNN` run.
* `ordered_name_digest(names)` — order-sensitive SHA-256 over a domain-tagged
  newline-joined sequence (`PRINTER_V1_CANONICAL_MIGRATION_ORDER_V1`). A
  reordering changes the digest even when the name *set* is identical.
* `canonical_migration_digest(migrations_dir=None)` — the catalogue's ordered-name
  digest.
* `canonical_migration_names()` now *enforces* the contract instead of assuming
  it, failing closed before any caller can judge a live ledger against an
  untrustworthy catalogue.

### 2. New guard — `src/printer_v1/operator_cli/pre_authorization_migration_ledger_guard.py`

* **Sidecar-safe immutable read-only inspection.** `-wal`, `-shm`, and `-journal`
  sidecars are detected and rejected *before* any connection opens; only then is
  the database opened `file:...?mode=ro&immutable=1` with `PRAGMA query_only=ON`.
  The ordering is the safety property: refusing sidecars first is what makes the
  immutable open sound, and the immutable open is what guarantees SQLite creates
  no sidecar of its own and takes no lock on a file the guard must not disturb.
* **Structured PASS/BLOCKED result.** `GuardResult` carries `status`, `verdict`,
  coded `blockers`, full repository catalogue facts, full database identity
  (path, SHA-256, size, inode, mtime_ns, ledger, digest, integrity, FK count),
  optional package-binding report, and explicit zero counters for
  `authorization_created`, `package_bytes_written`, `database_writes`,
  `source_calls`, and `scheduler_runtime_calls`.
* **`prepare` and `review` CLI modes**, exit `0` on PASS and `3` on BLOCKED.

### 3. `prepare` blocks before any package directory or byte is written

The guard is a pure inspector: it opens nothing for writing, creates no
directory, and emits its report to stdout/stderr only. Proven by
`test_prepare_writes_no_package_directory_or_byte`, which runs the blocking CLI
with the process working directory inside an empty workspace and asserts the
workspace and the whole temporary tree are byte-for-byte unchanged, with no
sidecar created.

### 4. `review` independently re-derives every fact

`review` never ratifies what a package asserts. It re-derives the canonical
catalogue from the live repository and the ledger from the live database, then
checks the package's claimed `migration_count`, `migration_head`, `sha256`,
`size`, and `path` against independently observed values, and additionally
rejects a package binding a head the repository does not actually ship. Missing
claims are rejected as `package_binding_incomplete` rather than silently skipped.

### 5. Wrapper integration — `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`

The guard runs inside `apply_authorization_once` **after** authorization/package
resolution and child-interpreter selection, and **before** the staging directory,
manifest bytes, canonical application directory, marker, and child creation. At
that point the authorization is resolved but untouched, so a block costs nothing.
The call is injectable (`migration_ledger_guard`) and defaults to the real
`assert_migration_ledger_ready`; a guard fault is re-raised as
`OneShotWrapperError` prefixed `authorization blocked before consumption:`.

### 6. Existing operational preflight unchanged

`operational_memory_factory_command.py` is untouched — verified by
`OperationalPreflightUnchangedTests`, which asserts its `migration_ledger` gate
and `validate_migration_ledger` call remain in place and that it carries no
reference to the new guard. The new guard is an additional earlier gate, never a
replacement. `git diff` confirms zero changes to that module.

### 7. Authorization schema unchanged

Exact local inspection of the live package
`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z/final_authorization.json`
(schema `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`) shows it already carries a
complete `authoritative_database` binding: `path`, `sha256`, `size`, `inode`,
`mtime_ns`, `migration_count`, `migration_head`, `integrity`,
`foreign_key_violations`, and the three sidecar flags. The existing binding fully
supports the approved design, so **no authorization schema change was made**.
`review` reads exactly what the package already recorded.

## Files

| File | Change |
| --- | --- |
| `src/printer_v1/db/migrate.py` | strict filename/sequence validation, ordered-name digest |
| `src/printer_v1/operator_cli/pre_authorization_migration_ledger_guard.py` | new guard module and CLI |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | guard invocation before staging |
| `tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py` | new bounded proof (43 tests) |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | one required test correction (below) |
| `docs/printer-v1-v2-9-8b-pre-authorization-migration-ledger-drift-guard-closeout.md` | this closeout |

## Integration points

1. `window_15m_one_shot_wrapper.apply_authorization_once` — after package
   resolution and interpreter selection, before staging/manifest/directory/
   marker/child. The only consumption-path integration.
2. `pre_authorization_migration_ledger_guard prepare` CLI — for any authorization
   preparation flow, before a package directory or byte exists.
3. `pre_authorization_migration_ledger_guard review --authorization-file` CLI —
   for independent review of a prepared package's migration honesty.
4. `operational_memory_factory_command` preflight — unchanged final defence
   inside the child.

## Blocker cases

| Code | Condition |
| --- | --- |
| `canonical_catalogue_invalid` | malformed filename or non-contiguous/duplicate ordinal run |
| `migration_ledger_absent` | `printer_schema_migrations` table missing |
| `migration_ledger_empty` | ledger table present but empty |
| `migration_ledger_missing` | canonical migration not applied |
| `migration_ledger_unexpected` | applied migration not in the repository |
| `migration_ledger_duplicate` | same migration recorded twice |
| `migration_ledger_out_of_order` | ledger is not a strict ordered prefix of the catalogue |
| `migration_count_mismatch` | applied count != canonical count |
| `migration_head_mismatch` | applied head != canonical head |
| `migration_ledger_digest_mismatch` | ordered-name digest disagreement |
| `database_integrity` | `PRAGMA integrity_check` not `ok` |
| `foreign_key_violations` | `PRAGMA foreign_key_check` returned rows |
| `database_unavailable` | file missing, unreadable, or sidecars present |
| `package_binding_dishonest` | package claim contradicts independently observed truth |
| `package_binding_incomplete` | package omits a required migration fact |
| `guard_input_invalid` | malformed CLI input or package file |

The exact historical failure reproduces as `migration_ledger_missing` +
`migration_head_mismatch`, now raised before consumption instead of after.

## Live behaviour on the current corpus

* `prepare` against the live repository and live database: **PASS**, count `52`,
  head `052_memory_observation_eligibility_layers.sql`, ledger digest
  `0c31f75ea2e204be2a9857542895a5dfc8f1f88120eb0c60ae83cd47f5d22fbe`,
  integrity `ok`, FK violations `0`, no sidecars.
* `review` against the consumed `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z`
  package: **BLOCKED** with four `package_binding_dishonest` findings — the
  package binds the pre-052 database (`51` / `051…` /
  `a9c1472…f6233` / `67862528`) which no longer matches the live post-052
  database (`52` / `052…` / `5cf5326…cfafdc` / `68009984`). Correct: that package
  is stale and must never be treated as current.

## Tests

Focused disposable tests only. Every database used for blocking proof is a
disposable temporary file; the authoritative database is only ever observed.

| Suite | Result |
| --- | --- |
| `test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py` (new) | 43 passed, 10 subtests |
| `test_v2_9_8b_window_15m_one_shot_wrapper.py` | 44 passed |
| `test_v2_9_8b_graduated_discovery_liquidity_memory_eligibility.py` | passed |
| `test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py` | passed |
| `test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py` | passed (1 env-gated skip) |
| `test_v2_9_7d_6b_2_operational_backup_restore_preflight.py` | passed |
| `test_v2_9_1_proof_db_schema_readiness.py` | passed |
| **Combined focused run** | **174 passed, 1 skipped, 10 subtests** |

Compilation (`compileall`) clean on all changed modules and tests.
`git diff --check` clean.

Required proof coverage:

* canonical 052 PASS — `test_canonical_052_ledger_passes`,
  `test_real_migrated_database_passes` (real `apply_migrations` run to a
  disposable file, ledger digest equals `canonical_migration_digest()`)
* missing / unexpected / duplicate / reordered / non-prefix / head mismatch BLOCK
  — six dedicated tests, each against a real disposable database
* malformed filename and invalid canonical sequence BLOCK — catalogue tests plus
  two on-disk disposable catalogue tests
* integrity and FK failures BLOCK — real corrupted file, real FK violation
* dishonest package facts rejected by review — head, count, hash, size, path,
  non-canonical head, and incomplete binding
* wrapper blocks before consumption — `test_drift_blocks_before_any_consumption_artifact`
* authoritative DB hash/size/inode/mtime unchanged — enforced by the
  `AuthoritativeDatabaseUntouched` base class at every class teardown
* no package, marker, campaign, provider, Scheduler, memory or financial activity
  — asserted directly in the wrapper block test and by construction elsewhere

### Required test correction

`test_v2_9_8b_window_15m_one_shot_wrapper.py::test_23` previously asserted the
wrapper opens **no** SQLite connection at all. This lane deliberately changes that
invariant: reading the ledger is the guard's entire purpose. The test was
narrowed honestly rather than deleted — the network prohibition remains absolute,
and the SQLite assertion is now stronger in the dimension that matters: exactly
one open, via URI, containing both `mode=ro` and `immutable=1`, against the
authoritative database path, with the file's SHA-256 verified unchanged across
the call. This is the only test correction made.

### Pre-existing failures outside this lane

`tests/test_v2_9_8b_19_production_readiness_consolidation.py` has 6 failures from
stale hard-coded migration expectations (`047`, `049`) left by earlier lanes.
These were confirmed pre-existing by running that suite against the unmodified
baseline before any change in this lane, and are unrelated to this work. They are
out of this lane's scope and were deliberately not modified; they remain open.

## Authoritative database before/after identity

| | Before | After |
| --- | --- | --- |
| SHA-256 | `5cf5326c4a820538a2f648a274bf14797c23a988bfae0f25aa49f01205cfafdc` | identical |
| Size | `68009984` | identical |
| Inode | `1230526` | identical |
| mtime (epoch s) | `1785921369` | identical |
| Migration count / head | `52` / `052_memory_observation_eligibility_layers.sql` | identical |
| Sidecars | none | none |

The database was neither migrated nor written. Migration count and head are
unchanged at `52 / 052`.

## Zero-effect confirmation

* authorizations created: `0`
* `WINDOW_15M` runs: `0`
* package or marker artifacts written: `0`
* campaign identities: `0`
* source calls: `0`
* Scheduler runtime calls: `0`
* memory, retrieval, decision, position, trade, audit, or PnL activity: none
* authoritative database writes: `0`
* pushes: none

## Money-usefulness contribution

Each `WINDOW_15M` authorization is single-use and non-reusable. Before this lane,
a one-migration ledger drift converted an authorization into a permanent loss:
consumed, zero data, no rerun. The drift was detectable from two read-only
sources in milliseconds, but only asked after the point of no return. This guard
makes that class of loss cost nothing — the same question now blocks before the
package exists and again before the wrapper stages anything, so authorizations
are spent on observation rather than on discovering schema drift.

## What this improves

* Migration-ledger drift is now caught at authorization preparation, at
  independent review, and at wrapper start — all before consumption.
* The canonical catalogue is validated rather than assumed: a malformed filename
  or a gap in the ordinal run can no longer silently become the standard a live
  ledger is judged against.
* Ledger comparison is order-sensitive. A ledger with the right names in the
  wrong order is now drift, not a match.
* Package migration claims are checked for honesty against independently
  observed truth instead of being trusted.
* Database inspection is provably non-disturbing: sidecar-refusing, immutable,
  read-only, lock-free, and asserted byte-identical after every test class.

## What remains locked

* Printer V1 remains Solana-only and paper-trading only. No live trading, wallet
  connection, private keys, real fund movement, or paid API dependency.
* No score, rank, confidence, or weight surface was added.
* No retrieval, decision, position, trade, audit, PnL, signing, or live-execution
  surface was created or touched.
* The authorization schema is unchanged.
* The operational preflight remains the final defence, unchanged.
* No authorization exists; a fresh one is still required before any campaign work.

## Proof completed

* Strict catalogue validation and ordered-name digest: complete
* Guard module with sidecar-safe immutable inspection: complete
* Structured PASS/BLOCKED result and both CLI modes: complete
* `prepare` writes-nothing proof: complete
* `review` independent re-derivation and dishonesty rejection: complete
* Wrapper integration before consumption: complete
* Operational preflight unchanged: complete and asserted
* Focused bounded tests, compilation, and `git diff --check`: complete
* Authoritative database identity unchanged: complete

## Functionality Risks / Setbacks / Efficiency Blockers

### Functionality Risks

* The wrapper's guard call defaults to the *machine-level* authoritative database
  and repository catalogue, not to the `repository_root` argument. This is
  deliberate — the authoritative database is a fixed resource, not a function of
  a caller-supplied root — but it means a caller passing a synthetic
  `repository_root` still has the real database inspected. Tests inject a stub
  guard rather than relying on that coupling.
* `review` proves a package's migration facts are honest *at review time*. It
  cannot prevent the database changing between review and consumption. The
  wrapper-start guard and the in-child operational preflight are what close that
  window; `review` alone must not be treated as a consumption-time guarantee.
* Enforcing the filename contract inside `canonical_migration_names` means any
  future migration violating it fails closed everywhere at once, including in
  unrelated callers. This is intended, but it makes the naming contract a hard
  dependency: a future migration must match `NNN_lowercase_words.sql` exactly.
* The guard reads the ledger with `ORDER BY rowid` (insertion order) while the
  operational preflight reads `ORDER BY version` (lexicographic). The guard's
  choice is what makes genuine reordering detectable; the two orderings agree on
  a healthy ledger but would report a corrupted one differently. That divergence
  is intentional and both gates still fail closed, but it is a real asymmetry to
  keep in mind when reading the two reports side by side.

### Setbacks

* Six pre-existing failures in
  `tests/test_v2_9_8b_19_production_readiness_consolidation.py` remain open. They
  are stale hard-coded migration expectations from earlier lanes, confirmed
  present at baseline, and outside this lane's scope — but they mean that file
  does not currently provide a trustworthy signal.
* This lane does not retroactively recover the authorization already consumed by
  the migration-052 drift. That loss stands.

### Efficiency Blockers

* The guard hashes the full 68 MB database on every invocation to record identity.
  At current size this is a fraction of a second, but it scales linearly with the
  memory corpus and will eventually want an incremental or page-level identity.
* Campaign work remains blocked pending a fresh authorization. This lane adds a
  protective gate only and deliberately creates no authorization.
* No automated scheduled drift check exists. The guard must still be invoked —
  by the wrapper, or manually via `prepare`/`review`. Periodic invocation would
  surface drift before an operator even begins preparing a package.
