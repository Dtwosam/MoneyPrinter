# Printer V1 V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof`

Type: proof-only (disposable databases).

## Controlling verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`

This controlling PASS is bound only to the single immutable correction
execution below. Earlier PASS text in historical sections is **not**
controlling.

A PASS does **not** authorize applying migration `050` to the authoritative
database or resuming C1–C15.

Next permitted lane after independent review:

`V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout`

---

## C. Controlling correction — Canonical Evidence Correction

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof — Canonical Evidence Correction`

Baseline proof-branch HEAD before correction:
`13794719f0369df5f691407fc0b96500aa7e9b80`

### C.1 Evidence-overwrite defect

The first bounded suite was invoked twice under a harness that always:

1. copied the authoritative database;
2. applied migration `050` once to that disposable copy;
3. generated a new proof execution ID;
4. overwrote the shared tracked file
   `operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json`.

| Attempt | Proof execution ID | Role |
| --- | --- | --- |
| First suite invocation | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd` | Bound into the original report text |
| Combined regression re-run | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143555Z_4f9874ff` | Overwrote the shared JSON |

These are retained as superseded evidence attempts caused by the harness
overwrite defect. They are not deleted, and this correction does not pretend
they did not occur. Their PASS is not controlling.

### C.2 Harness correction

1. Canonical authoritative-copy proof requires explicit mode:

   ```text
   PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1
   ```

2. Default pytest / combined regression is non-canonical only:
   - no authoritative DB copy;
   - no authoritative-byte-copy migration application;
   - no new proof execution ID;
   - no write/overwrite of committed proof evidence.

3. Canonical evidence is written only to an execution-specific path:

   ```text
   operator-runs/v2-9-8b-mig050-bounded-proof/<EXECUTION_ID>/proof_summary.json
   ```

   The runner fails closed if that path already exists.

4. Controlling pointer:

   ```text
   operator-runs/v2-9-8b-mig050-bounded-proof/CONTROLLING_EXECUTION
   ```

5. The former shared `proof_summary.json` is marked
   `SUPERSEDED_HARNESS_OVERWRITE` and is not controlling.

### C.3 Single controlling correction execution

Canonical command (run **exactly once** for this correction):

```text
PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1 \
PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF_MAIN=1 \
.venv/bin/python tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py
```

| Field | Controlling value |
| --- | --- |
| Proof execution ID | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275` |
| Execution-specific evidence path | `operator-runs/v2-9-8b-mig050-bounded-proof/V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275/proof_summary.json` |
| Source SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Source size | `65654784` |
| Source mtime_ns | `1785510479935495533` |
| Disposable pre-migration SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| Disposable post-migration SHA-256 | `4000cbefaafb2a17c205a2129f2be14b30a01ec3bd7216397c0b66a09235f0cf` |
| Migration start | `2026-08-01T14:47:40.513480+00:00` |
| Migration finish | `2026-08-01T14:47:40.574741+00:00` |
| Ledger before tip | `049_candidate_acquisition_integration.sql` |
| Ledger before count | `49` |
| Ledger after tip | `050_campaign_scheduler_ownership_scope.sql` |
| Ledger after count | `50` |
| Ledger delta | `["050_campaign_scheduler_ownership_scope.sql"]` |
| Historical pre count | `0` |
| Historical post count | `0` |
| Historical pre hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Historical post hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Reconstruction hash | `1488cc12d4f4266daa81fac0025ce18e911ad444479b4eb49dea78156e78b46d` |
| Verdict | `V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS` |

These fields are identical in:

- this controlling report section;
- the execution-specific JSON (`cross_artifact_identity` and matching top-level fields);
- the canonical command return printed for the controlling run.

Cross-artifact equality is enforced by
`CanonicalEvidenceCrossArtifactEquality` in the proof harness.

### C.4 Non-canonical regression (after controlling execution)

After the one controlling canonical execution succeeded, canonical mode was
**not** re-run. Non-canonical regressions only:

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py -v
# (without PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF)
```

Expected: synthetic cases pass; canonical test skipped; cross-artifact equality
passes against the controlling package; evidence tree fingerprint unchanged.

Combined ownership/migration suite (non-canonical):

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
    tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py -q
```

### C.5 What this correction does not do

- does not change migration `050`;
- does not change production ownership or active-work code;
- does not open or mutate the authoritative database through SQLite;
- does not run providers/RPC/WebSockets/source fetching;
- does not resume C1–C15;
- does not unlock retrieval or financial capabilities;
- does not merge the branch.

---

## 0. Boundary

This lane proves migration
`migrations/050_campaign_scheduler_ownership_scope.sql` and its scope-aware
ownership primitives on disposable databases only.

It does **not**:

- open the authoritative database through SQLite;
- mutate the authoritative database;
- repair production implementation (no production defect in migration/owner code);
- change migration `050`;
- add a migration;
- run providers, RPC, WebSockets, or source fetching;
- run discovery or an operational campaign;
- wire migration primitives into runtime;
- resume C1–C15;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits,
  or PnL;
- merge the proof branch.

## 1. Baseline

| Item | Value |
| --- | --- |
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Required clean `master` HEAD (original lane) | `19bcd23da1608e406e25f675532df193b65d038a` |
| Proof branch | `codex/v2-9-8b-scheduler-ownership-schema-migration-proof` |
| Implementation branch | `codex/v2-9-8b-scheduler-ownership-schema-migration` (not modified) |
| Migration under proof | `050_campaign_scheduler_ownership_scope.sql` |
| **Controlling proof execution ID** | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275` |

Controlling sources:

- `docs/printer-v1-v2-9-8b-full-run-accounting-final-conformance-map.md`
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-design-amendment.md`
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-implementation.md`
- `migrations/050_campaign_scheduler_ownership_scope.sql`

## 2. Disposable-copy method (canonical mode only)

1. Record filesystem identity of `data/printer_v1.sqlite3` (SHA-256, size,
   mtime) without opening that path through SQLite.
2. Create a temporary proof directory.
3. `shutil.copy2` produces a byte-identical filesystem copy.
4. Recompute the copy hash and require equality with the source hash.
5. Perform every SQLite open/query/migration only on disposable paths.
6. Write evidence only under the execution-specific directory.
7. After the proof, recompute the authoritative identity and require an exact
   match to the pre-proof identity.

Non-canonical regressions never perform steps 1–6 against the authoritative
path.

## 3. Source and copy hashes (controlling)

| Artifact | SHA-256 | Size | mtime_ns |
| --- | --- | --- | --- |
| Authoritative before/after | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | 65654784 | 1785510479935495533 |
| Disposable pre-migration | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | 65654784 | 1785510479935495533 |
| Disposable post-migration | `4000cbefaafb2a17c205a2129f2be14b30a01ec3bd7216397c0b66a09235f0cf` | — | — |

Authoritative unchanged through the controlling execution: **true**.

## 4. Readiness results (controlling disposable copy, pre-050)

| Check | Result |
| --- | --- |
| Migration ledger tip | `049_candidate_acquisition_integration.sql` |
| Migration ledger count | 49 |
| Migration `050` present | no |
| Scheduler ownership row count | 0 |
| Duplicate non-null `scheduler_job_id` | 0 |
| `PRAGMA integrity_check` | `ok` |
| Foreign-key violations | 0 |
| Historical pre hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

## 5. One canonical migration application (controlling)

| Field | Value |
| --- | --- |
| Proof execution ID | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275` |
| Migration start | `2026-08-01T14:47:40.513480+00:00` |
| Migration finish | `2026-08-01T14:47:40.574741+00:00` |
| Ledger before tip | `049_candidate_acquisition_integration.sql` |
| Ledger after tip | `050_campaign_scheduler_ownership_scope.sql` |
| Ledger delta | `["050_campaign_scheduler_ownership_scope.sql"]` |
| Integrity after | `ok` |
| FK violations after | 0 |

## 6. Historical preservation (controlling)

| Direction | Result |
| --- | --- |
| Pre preserved-field set == post | yes |
| Pre count / post count | 0 / 0 |
| Pre hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |
| Post hash | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Empty bidirectional equality on the authoritative copy. Non-empty preservation
remains covered by the focused migration suite.

## 7. V2 scope matrix and reconstruction (controlling package)

All four scopes projected on a separate post-migration synthetic fixture inside
the controlling run (not the authoritative copy):

- `DISCOVERY_SELECTION`
- `FIRST_15M_HANDOFF`
- `WINDOW_LIFECYCLE`
- `TERMINAL_CLEANUP`

Reconstruction hash (read-only URI, double-hash match):

`1488cc12d4f4266daa81fac0025ce18e911ad444479b4eb49dea78156e78b46d`

## 8. Negative proofs

Synthetic non-canonical regressions re-prove:

- duplicate historical job ownership blocks migration;
- injected rebuild failure rolls back fully;
- field mismatch blocks;
- foreign-key failure blocks;
- invalid scope/nullability blocks;
- duplicate V2 job ownership and identity conflicts block;
- V1 evidence cannot satisfy V2;
- foreign-cycle capture excluded;
- partial failure leaves no ledger entry or replacement table.

## 9. Tests and exact outputs

### 9.1 Canonical command (once)

```text
$ PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF=1 \
  PRINTER_V2_9_8B_MIG050_CANONICAL_PROOF_MAIN=1 \
  .venv/bin/python tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py
...
proof_execution_id: V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275
VERDICT V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS
EVIDENCE operator-runs/v2-9-8b-mig050-bounded-proof/V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275/proof_summary.json
```

Canonical mode was not re-run after this controlling success.

### 9.2 Non-canonical regressions

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py -v
======================== 15 passed, 1 skipped in 3.07s =========================
# skipped: CanonicalAuthoritativeMigrationProof (env not set)
# passed: synthetic cases + cross-artifact equality against controlling package

$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
    tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py -q
............s.............................................               [100%]
57 passed, 1 skipped in 16.25s
```

Evidence immutability after those non-canonical runs:

| Artifact | SHA-256 (unchanged) |
| --- | --- |
| Controlling JSON | `a6598c06ae85d4388df4d7e809e67475adcb386cd094639a78e9f358d70cafec` |
| Superseded generic summary | `948e4ad646a200158d48fd8295b2b3998aaff38bfe854b6f0a54c220e5406d92` |
| Controlling pointer | `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275` |

## 10. Schema verdict

Migration `050` remains proven safe on a disposable byte-identical copy of the
current authoritative pre-050 database. Controlling evidence is immutable and
execution-specific.

## 11. Money-usefulness contribution

Unchanged: capital-protection and accounting-honesty gate only. No profit
feature, no positions, no decisions unlocked.

## 12. What remains locked

- Applying migration `050` to the authoritative database
- Resuming C1–C15
- Wiring ownership projection into the operational campaign path
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- Live execution, wallets, private keys, signing, real funds
- Paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status | Notes |
| --- | --- | --- |
| Setback: shared JSON overwrite across two suite invocations | Corrected | Env-gated canonical mode + execution-specific immutable path |
| Historical ownership rows empty on authoritative copy | Observed | Empty equality still valid; non-empty covered by focused suite |
| Production migration/owner defect | None found | Correction is harness/evidence only |

## 14. Files changed by the correction

| File | Change |
| --- | --- |
| `tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py` | Split canonical vs synthetic modes; immutable execution-specific evidence; cross-artifact equality. |
| `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-bounded-proof.md` | Controlling correction section; earlier PASS no longer controlling alone. |
| `operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json` | Marked `SUPERSEDED_HARNESS_OVERWRITE`. |
| `operator-runs/v2-9-8b-mig050-bounded-proof/CONTROLLING_EXECUTION` | Pointer to controlling execution ID. |
| `operator-runs/v2-9-8b-mig050-bounded-proof/V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275/proof_summary.json` | Immutable controlling evidence package. |

Not touched:

- `migrations/050_campaign_scheduler_ownership_scope.sql`
- production ownership / active-work code
- authoritative `data/printer_v1.sqlite3`
- implementation branch
- operational campaign commands

## 15. Historical evidence (superseded; not controlling)

The original report body bound
`V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143546Z_f98b72fd` while the tracked
shared JSON later held
`V2_9_8B_MIG050_BOUNDED_PROOF_20260801T143555Z_4f9874ff`.

Those attempts remain documented above as superseded harness-overwrite
evidence. Do not use them as the controlling package.

## 16. Final controlling verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS`

Confirmation:

- Authoritative DB path was never opened through SQLite by this lane.
- Authoritative SHA-256 / size / mtime
  (`e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` /
  `65654784` / `1785510479935495533`) match before and after the controlling
  execution.
- One controlling canonical execution only:
  `V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275`.
- Report / JSON / return share the same cross-artifact identity fields.
- Non-canonical regressions do not rewrite controlling evidence.
- No operational campaign, provider, RPC, WebSocket, or source-fetch path ran.
- No retrieval or financial capability was unlocked.

Next permitted lane after independent review:

`V2-9.8B Campaign Scheduler Ownership Schema Migration Closeout`
