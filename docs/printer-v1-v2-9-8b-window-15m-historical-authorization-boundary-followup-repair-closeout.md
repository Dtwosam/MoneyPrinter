# Printer V1 V2-9.8B WINDOW_15M Historical Authorization Boundary Follow-up Repair Closeout

| Field | Value |
| --- | --- |
| Document title | Historical Authorization Boundary Follow-up Repair Closeout |
| Date | 2026-08-06 |
| Verdict | `V2_9_8B_WINDOW_15M_HISTORICAL_AUTHORIZATION_BOUNDARY_FOLLOWUP_REPAIR_PASS` |
| Required baseline branch | `agent/v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation` |
| Follow-up repair baseline HEAD | `92881743d0b34c0afcd1224480782f3f7f82ea87` |
| Atomic implementation commit | `6a5be245ac6c30f6ebf49505adc5afc98a33356a` |
| Repair branch | `agent/v2-9-8b-window-15m-historical-authorization-boundary-followup-repair` |

Readiness must resolve and bind the **live branch tip** after this repair. This closeout does not hard-code a self-referential final branch SHA.

## 1. Verdict

`V2_9_8B_WINDOW_15M_HISTORICAL_AUTHORIZATION_BOUNDARY_FOLLOWUP_REPAIR_PASS`

Preparation temporary-directory placement is fail-closed against the repository and `APPLICATION_ROOT`. Pre-marker cleanup failures preserve the original exception identity and report secondary cleanup blockers separately. Invocation-created empty canonical directories are removed with `rmdir` only when promotion fails before publication. Implementation identity wording distinguishes the atomic implementation commit from the follow-up repair baseline.

## 2. Issues repaired

### A. Preparation temporary-directory boundary

`prepare_git_provenance_authorization_parity` now:

1. Resolves the canonical repository root.
2. Resolves the canonical application root (`application_root` override or production `APPLICATION_ROOT`).
3. Resolves and validates the proposed temporary parent **before** creation.
4. Blocks if the parent is the repository or inside it, `APPLICATION_ROOT` or inside it, a symlink, or unavailable.
5. Creates the temporary directory only under the validated parent (`tempfile.mkdtemp(dir=...)`).
6. Revalidates the created directory’s canonical containment before writing.
7. Retains exact-path cleanup in `finally`.
8. Creates no marker, canonical application directory, or child.

Optional injectable `application_root` and `temporary_parent` support disposable tests; production defaults remain canonical.

### B. Primary blocker preservation

On pre-marker cleanup failure the wrapper:

- re-raises the **original** exception type and message as the controlling blocker;
- attaches cleanup failure on `secondary_staging_cleanup_blocker` (and notes when available);
- never replaces the original with a new `OneShotWrapperError`;
- never implies consumption.

Wrapper CLI blocked JSON retains original `error_type` / `error_message` and conditionally includes:

- `secondary_staging_cleanup_blocker`
- `secondary_canonical_cleanup_blocker`

### C. Canonical-directory residue before publication

The wrapper tracks `canonical_created_by_invocation`.

On failure before successful publication:

- cleans the exact staging directory under existing known-entry rules;
- removes the exact newly created canonical directory only when this invocation created it, no marker exists, it is a real non-symlink directory, and it is completely empty;
- uses only `rmdir` (no recursive delete);
- reports cleanup failure as secondary;
- never touches pre-existing or non-empty canonical directories.

### D. Implementation identity wording

Updated implementation documents:

- `Atomic implementation commit`: `6a5be245ac6c30f6ebf49505adc5afc98a33356a`
- `Follow-up repair baseline`: `92881743d0b34c0afcd1224480782f3f7f82ea87`

Removed the misleading label `Final full HEAD = 6a5be245…`.

## 3. Files changed

Production:

- `src/printer_v1/operator_cli/window_15m_authorization_preparation.py`
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`

Tests:

- `tests/test_v2_9_8b_window_15m_historical_authorization_boundary_followup_repair.py` (new)
- `tests/test_v2_9_8b_window_15m_historical_authorization_evidence_contract.py` (blocker-preservation expectation update)

Documentation:

- `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation.md`
- `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation-closeout.md`
- `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-boundary-followup-repair-closeout.md` (this file)

## 4. Focused proof commands and results

Interpreter: repository `.venv/bin/python`.

```text
.venv/bin/python -m unittest \
  tests.test_v2_9_8b_window_15m_historical_authorization_boundary_followup_repair \
  tests.test_v2_9_8b_window_15m_historical_authorization_evidence_contract -v
→ Ran 51 tests … OK

.venv/bin/python -m unittest \
  tests.test_v2_9_8b_window_15m_git_provenance_authorization_manifest \
  tests.test_v2_9_8b_window_15m_one_shot_wrapper \
  tests.test_v2_9_8b_window_15m_ignored_evidence_visibility
→ Ran 135 tests … OK

.venv/bin/python -m compileall -q \
  src/printer_v1/operator_cli/window_15m_authorization_preparation.py \
  src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py
→ exit 0

git diff --check
→ exit 0

grep -R SELECTED_MINT_NOT_IN_REGISTRY src tests
→ ABSENT
```

Proved:

1. Temp parent inside repository blocks before creation.
2. Temp parent equal to / inside `APPLICATION_ROOT` blocks before creation.
3. Symlink temporary parent blocks.
4. Valid external temp parent passes and is removed afterward.
5. Preparation creates no marker, canonical application directory, or child.
6. Pre-marker failure with successful cleanup preserves the original exception.
7. Cleanup failure preserves original type/message and reports a separate secondary blocker.
8. Wrapper CLI JSON exposes the original `error_type`.
9. Manifest-promotion failure removes the invocation-created empty canonical directory.
10. Pre-existing or non-empty canonical directories are never deleted.
11. Marker creation remains the consumption boundary.
12. Existing Manifest V2 / trust-root / T/M/H / preparation-parity / ignored-evidence suites remain green.
13. `SELECTED_MINT_NOT_IN_REGISTRY` remains absent.
14. No DB, provider, discovery, Scheduler, campaign, or memory work occurred.

## 5. Authoritative database identity

Read-only before and after:

| Field | Value |
| --- | --- |
| path | `data/printer_v1.sqlite3` |
| size | `68366336` |
| SHA-256 | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` |
| inode | `1230526` |
| integrity | `ok` |
| foreign-key violations | `0` |
| WAL/SHM/journal | absent |
| migration count | `52` |
| migration head | `052_memory_observation_eligibility_layers.sql` |

Identity unchanged.

## 6. Restrictions honored

Did **not**:

- run the real one-shot wrapper against the repository;
- reuse either historical authorization;
- create an authorization or application marker on the live application root;
- clean real staging residue;
- edit historical authorization packages;
- mutate the authoritative DB;
- contact providers;
- run discovery, Scheduler, campaign, or memory;
- change admission, orientation, or financial capability logic.

## 7. Exact next step

Independent inspection of this follow-up repair, then a **separate readiness lane** that resolves and binds the **live repaired branch tip**, followed by **one fresh authorization**.

Do **not** create that authorization in this lane.

## 8. Commit message

```text
Repair authorization preparation and blocker boundaries
```
