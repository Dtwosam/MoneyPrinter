# Printer V1 V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof`

Type: proof-only (disposable databases).

## Verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`

A PASS does **not** authorize applying migration `050` to the authoritative
database or resuming C1–C15.

Next permitted lane after independent review:

`V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout`

## 0. Boundary

This lane proves migration
`migrations/050_campaign_scheduler_ownership_scope.sql` and its scope-aware
ownership primitives on disposable databases only.

It does **not**:

- open the authoritative database through SQLite;
- mutate the authoritative database;
- repair production implementation (no production defect was found);
- change migration `050`;
- add a migration;
- run providers, RPC, WebSockets, or source fetching;
- run discovery or an operational campaign;
- wire migration primitives into runtime;
- resume C1–C15;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL;
- merge the proof branch.

## 1. Baseline and proof execution ID

| Item | Value |
| --- | --- |
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Required clean `master` HEAD | `19bcd23da1608e406e25f675532df193b65d038a` |
| Proof branch | `codex/v2-9-8b-scheduler-ownership-schema-migration-proof` |
| Implementation branch | `codex/v2-9-8b-scheduler-ownership-schema-migration` (not modified) |
| Migration under proof | `050_campaign_scheduler_ownership_scope.sql` |
| Proof execution ID | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd` |

Controlling sources:

- `docs/printer-v1-v2-9-8b-full-run-accounting-final-conformance-map.md`
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-design-amendment.md`
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-implementation.md`
- `migrations/050_campaign_scheduler_ownership_scope.sql`

## 2. Disposable-copy method

1. Record filesystem identity of `data/printer_v1.sqlite3` (SHA-256, size,
   mtime) without opening that path through SQLite.
2. Create a temporary proof directory.
3. `shutil.copy2` produces a byte-identical filesystem copy.
4. Recompute the copy hash and require equality with the source hash.
5. Perform every SQLite open/query/migration only on disposable paths.
6. After the proof, recompute the authoritative identity and require an exact
   match to the pre-proof identity.

## 3. Source and copy hashes

| Artifact | SHA-256 | Size | mtime_ns |
| --- | --- | --- | --- |
| Authoritative before | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | 65,654,784 | 1785510479935495533 |
| Disposable copy | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | 65,654,784 | 1785510479935495533 |
| Authoritative after | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | 65,654,784 | 1785510479935495533 |

Authoritative unchanged: **true**.

Canonical disposable copy after one migration application:

| Stage | File SHA-256 |
| --- | --- |
| Pre-migration disposable | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Post-migration disposable | `91ac9a57226d2df960731e86eeee98db63c80565556624806daf2caebf5987a0` |

## 4. Readiness results (disposable copy, pre-050)

| Check | Result |
| --- | --- |
| Migration ledger tip | `049_candidate_acquisition_integration.sql` |
| Migration ledger count | 49 |
| Migration `050` present | no |
| Scheduler ownership row count | 0 |
| Duplicate non-null `scheduler_job_id` | 0 |
| `PRAGMA integrity_check` | `ok` |
| Foreign-key violations | 0 |
| Pre-050 columns include `ownership_contract_version` | no |
| Canonical hash of preserved ownership rows | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Pre-migration schema identity (ownership table):

- Columns: the 17 pre-050 fields only
  (`scheduler_work_id` … `updated_at`; no V2 identity columns).
- Indexes: `idx_campaign_work_owner` plus SQLite autoindexes.
- Triggers: `printer_campaign_work_provenance_insert`,
  `printer_campaign_work_identity_immutable`.

Readiness gate: **PASS**. Migration application was allowed to proceed.

## 5. One canonical migration proof

Exactly one canonical application of migration `050` was run on the
authoritative byte-identical disposable copy. No retry and no successor
canonical proof.

| Field | Value |
| --- | --- |
| Proof execution ID | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd` |
| Migration start | `2026-08-01T14:35:46.390303+00:00` |
| Migration finish | `2026-08-01T14:35:46.453225+00:00` |
| Ledger delta | `["050_campaign_scheduler_ownership_scope.sql"]` |
| Ownership row count after | 0 |
| Integrity | `ok` |
| Foreign-key violations | 0 |

### Migration ledger before / after

| Side | Tip | Count |
| --- | --- | --- |
| Before | `049_candidate_acquisition_integration.sql` | 49 |
| After | `050_campaign_scheduler_ownership_scope.sql` | 50 |

Delta is exactly one version: `050_campaign_scheduler_ownership_scope.sql`.

### Post-migration schema / index / trigger identity

Added columns:

- `ownership_contract_version`
- `stage_id`
- `work_scope`
- `target_category`
- `target_identity`
- `factory_run_id`

Indexes present:

- `idx_campaign_work_owner`
- `idx_campaign_work_scheduler_job_unique` (new partial unique on
  non-null `scheduler_job_id`)
- `idx_campaign_work_scope_stage` (new reporting index)
- SQLite autoindexes for PK / composite UNIQUE

Triggers recreated:

- `printer_campaign_work_provenance_insert`
- `printer_campaign_work_identity_immutable` (amended to cover V2 identity
  fields while preserving 047 once-bound semantics)

## 6. Historical preservation comparison

The authoritative disposable copy had **zero** historical Scheduler ownership
rows. Preservation is therefore exact empty equality in both directions:

| Direction | Result |
| --- | --- |
| Pre preserved-field set == post preserved-field set | yes |
| Post preserved-field set == pre preserved-field set | yes |
| Pre count | 0 |
| Post count | 0 |
| Pre canonical hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Post canonical hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Additionally, the focused migration suite proves non-empty historical
preservation on synthetic pre-050 fixtures
(`test_01_historical_rows_migrate_without_drift`): every preserved field is
byte-identical, every migrated row is tagged `V1_WINDOW_BOUND`, and all V2-only
identity fields are null.

V1 rows remain readable and identity-immutable; they cannot satisfy repaired V2
exact capture, cleanup evidence, slot linkage, equality, or reconstruction
(covered by negative proofs and the focused suite).

Historical preservation: **PASS**.

## 7. V2 scope matrix

On a **separate** post-migration disposable fixture (full `apply_migrations`,
not the authoritative copy), lawful projection was proven for all four scopes
through `project_campaign_scheduler_work` / the lifecycle wrapper. No
operational campaign path was connected.

| Scope | Job | Lineage / target | Linkage | State | Idempotency / sync |
| --- | --- | --- | --- | --- | --- |
| `DISCOVERY_SELECTION` | 1 | `printer_discovery_work` / `dwork-1` | no slot/window/factory | PENDING → SUCCEEDED (lawful sync) | exact-repeat `created=False` |
| `FIRST_15M_HANDOFF` | 3 | selected-item link / `cand-1` | optional `slot-1`; window/factory null | PENDING | created |
| `WINDOW_LIFECYCLE` | 4 | factory run-step + window + bind / `window-15m-a` | slot+window+factory required | PENDING | created via wrapper |
| `TERMINAL_CLEANUP` | 5 | exact pre-cancel capture / job `5` | no window/factory | CANCELLED / `CLEANUP_CANCELLED` | first terminal cause immutable |

Additional invariants proven on that fixture:

- one Scheduler job → one ownership row (no duplicate non-null job ownership);
- all four scopes coexist as `V2_STAGE_SCOPED`;
- terminal-cause immutability after cleanup projection.

V2 scope matrix: **PASS**.

## 8. Read-only reconstruction

Proof-local read-only reconstruction of all `V2_STAGE_SCOPED` rows from the
separate post-migration fixture (SQLite URI `mode=ro`):

| Field | Value |
| --- | --- |
| Row count | 4 |
| Canonical reconstruction hash | `1488cc12d4f4266daa81fac0025ce18e911ad444479b4eb49dea78156e78b46d` |
| Hash repeated twice | identical |
| Zero writes | yes (read-only connection) |
| V1 rows included | no |
| Source request | none |
| Scheduler mutation | none |
| Operational report-only path | not invoked |

No production report or replay owner was added.

Reconstruction: **PASS**.

## 9. Negative proofs

Each negative case began from a fresh disposable state.

| Case | Result |
| --- | --- |
| Duplicate historical Scheduler-job ownership blocks migration | PASS |
| Injected failure during rebuild rolls back fully | PASS |
| Row/field mismatch blocks (corrupted preserved field during copy) | PASS |
| Foreign-key failure blocks (orphan `scheduler_job_id`) | PASS |
| Invalid scope/nullability combinations block | PASS |
| Duplicate V2 job ownership blocks | PASS |
| Scope/stage/target/linkage conflict blocks | PASS |
| V1 evidence cannot satisfy V2 proof | PASS |
| Foreign-run or foreign-cycle capture is excluded | PASS |
| Partial/failed migration leaves no migration-ledger entry or replacement table | PASS |

On every failed migration body: no `ownership_contract_version` column, no
`__v2_9_8b_050` leftover table, and no `050_...` ledger entry.

## 10. Tests and exact outputs

Proof file:

`tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py`

Evidence artifact (generated by the suite):

`operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json`

### Bounded-proof suite

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py -v
============================== 15 passed in 2.40s ==============================
```

Cases:

1. `test_01_authoritative_source_protection`
2. `test_02_readiness_gate`
3. `test_03_one_canonical_migration`
4. `test_04_historical_preservation`
5. `test_05_v2_scope_matrix`
6. `test_06_readonly_reconstruction`
7. `test_07_negative_duplicate_historical_job_blocks_migration`
8. `test_08_negative_injected_failure_rolls_back`
9. `test_09_negative_field_mismatch_blocks`
10. `test_10_negative_foreign_key_failure_blocks`
11. `test_11_negative_invalid_scope_nullability_blocks`
12. `test_12_negative_duplicate_v2_job_and_conflicts`
13. `test_13_negative_v1_cannot_satisfy_v2_and_foreign_cycle`
14. `test_14_negative_partial_failed_leaves_no_ledger_or_replacement`
15. `test_99_final_authoritative_unchanged_and_verdict`

### Existing migration / ownership suite

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py -q
....................................                                     [100%]
36 passed
```

Combined focused run (bounded proof + migration suite + campaign ownership
schema):

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
    tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py -q
.........................................................                [100%]
57 passed in 16.67s
```

No full repository suite was executed.

No production code, migration SQL, or implementation branch was modified.

## 11. Schema verdict

Migration `050` is proven safe on a disposable byte-identical copy of the
current authoritative pre-050 database:

- readiness fails closed on duplicates / integrity / FK problems;
- historical preserved fields migrate without drift (empty equality on the
  authoritative copy; non-empty equality in focused suite);
- post-schema carries the approved V2 columns, partial unique job index, and
  amended immutability trigger;
- V2 scope projection works for all four scopes with exact lineage, idempotency,
  state sync, and terminal immutability;
- read-only reconstruction is deterministic;
- every required negative path rolls back without ledger or replacement residue.

Schema verdict: **PASS** for disposable proof only.

## 12. Money-usefulness contribution

This proof is a capital-protection and accounting-honesty gate, not a profit
feature.

Without a proven scope-aware Scheduler ownership schema, full-run accounting
cannot honestly attribute discovery, selection, first-15m handoff, window
lifecycle, and terminal cleanup jobs. Forcing those jobs into window-only rows
would create fake ownership and fake equality. Leaving them unowned would create
silent accounting holes.

Proving the migration and primitives on disposable copies is the last required
evidence before closeout can consider operator-approved application of `050` on
a controlled path. It does not print money, open positions, or unlock decisions.

## 13. What the lane improves

- Proves migration `050` against a real pre-050 authoritative byte copy without
  touching production data.
- Records exact readiness, ledger delta, schema identity, and reconstruction
  hash for operator review.
- Re-proves all four ownership scopes and the full negative matrix in one
  ordered disposable suite.
- Keeps implementation and operational paths frozen.

## 14. What remains locked

- Applying migration `050` to the authoritative database
- Resuming C1–C15 full-run accounting implementation
- Wiring ownership projection into the operational campaign path
- Retrieval activation
- Paper decisions
- BUY / SELL / HOLD
- Paper positions, trade events, paper audits, PnL
- Live execution, wallets, private keys, signing, real funds
- Paid APIs
- Scoring / ranking / confidence / weighted logic
- Embeddings / vectors
- Source fetching outside governed approved commands

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status | Notes |
| --- | --- | --- |
| Functionality risk: authoritative DB already on 050 | Not observed | Tip was `049_...`; readiness passed. |
| Functionality risk: historical ownership rows empty on authoritative copy | Observed, not blocking | Empty bidirectional equality still satisfies preservation; non-empty path proven by focused suite. |
| Setback: selected-item handoff seed requires link-only insert pattern | Handled in proof harness | Matches focused migration suite; not a production repair. |
| Efficiency blocker: 65 MB authoritative copy | Acceptable | One canonical copy + small synthetic negatives; full suite ~2–3s after copy. |
| Production defect requiring implementation repair | None found | Proof harness only; migration and owner unchanged. |

## 16. Files changed

| File | Change |
| --- | --- |
| `tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py` | New focused bounded disposable proof suite (15 cases). |
| `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-bounded-proof.md` | This report. |
| `operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json` | Generated machine-readable evidence bag from the suite. |

Not touched:

- `migrations/050_campaign_scheduler_ownership_scope.sql`
- `src/printer_v1/operator_cli/campaign_ownership.py`
- authoritative `data/printer_v1.sqlite3`
- implementation branch
- operational campaign commands
- provider/RPC/WebSocket paths

## 17. Final verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`

Confirmation:

- Authoritative DB path was never opened through SQLite by this lane.
- Authoritative SHA-256 / size / mtime were identical before and after.
- All SQLite work used disposable copies or synthetic fixtures only.
- No operational campaign, provider, RPC, WebSocket, or source-fetch path ran.
- No retrieval or financial capability was unlocked.

Next permitted lane after independent review:

`V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout`
