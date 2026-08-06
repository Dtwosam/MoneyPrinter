# Printer V1 V2-9.8B WINDOW_15M Historical Authorization Evidence Contract Implementation Closeout

| Field | Value |
| --- | --- |
| Document title | Historical Authorization Evidence Contract Implementation Closeout |
| Date | 2026-08-06 |
| Verdict | `V2_9_8B_WINDOW_15M_HISTORICAL_AUTHORIZATION_EVIDENCE_CONTRACT_IMPLEMENTATION_PASS` |
| Baseline branch | `agent/v2-9-8b-window-15m-historical-authorization-trust-root-design-revision` |
| Baseline full HEAD | `a80673db2187bc394872acd1941385307fe7e155` |
| Implementation branch | `agent/v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation` |
| Atomic implementation commit | `6a5be245ac6c30f6ebf49505adc5afc98a33356a` |
| Follow-up repair baseline | `92881743d0b34c0afcd1224480782f3f7f82ea87` |
| Controlling design | R2 historical authorization trust root design |

Readiness lanes must resolve and bind the **live branch tip** after any follow-up repair. Do not treat the atomic implementation commit as the final branch tip if later identity/closeout commits exist on the branch.

## 1. Verdict

`V2_9_8B_WINDOW_15M_HISTORICAL_AUTHORIZATION_EVIDENCE_CONTRACT_IMPLEMENTATION_PASS`

Atomic Manifest V2 builder+validator, approved-ID trust root, historical evidence owner, split reconciliation, preparation parity, marker consumption wording, and pre-marker staging cleanup landed with focused disposable proof. No real authorization, wrapper run against the live repository, provider, discovery, Scheduler, campaign, memory, or DB mutation occurred.

## 2. Exact files changed

Production:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- `src/printer_v1/operator_cli/window_15m_authorization_preparation.py` (new)

Tests:

- `tests/test_v2_9_8b_window_15m_historical_authorization_evidence_contract.py` (new)
- `tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`
- `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`
- `tests/test_v2_9_8b_window_15m_ignored_evidence_visibility.py`

Documentation:

- `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation.md`
- `docs/printer-v1-v2-9-8b-window-15m-historical-authorization-evidence-contract-implementation-closeout.md`

## 3. Root cause (confirmed)

`COMMITTED_CODE_DEFECT`: two-class inventory `F == T ∪ M` could not bind preserved untracked historical authorization packages. R2 repair introduces explicit set `H` bound only through `prior_authorizations_non_reusable` on the current final authorization document.

## 4. Trust-root / Manifest V2 / historical owner / reconciliation

See implementation document sections 3–6. Summary:

- Trust root = validated `prior_authorizations_non_reusable` (declaration, not discovery).
- Schema = `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2` with required `historical_authorization_evidence`.
- Marker remains `PRINTER_V1_APPLICATION_MARKER_V1`.
- Owner = `enumerate_historical_authorization_evidence`.
- Reconciliation uses separate `current_manifest_paths` and `historical_paths` with `F = T ∪ M ∪ H` and `C = M`.

## 5. Preparation parity

`prepare_git_provenance_authorization_parity` uses production `build_manifest_bytes` + `validate_git_provenance_manifest_pre_marker`, writes outside repository/application root, creates no marker/child/DB/Git side effects, and states:

```text
inventory_pre_marker_parity_PASS ≠ full_apply_readiness_PASS
```

## 6. Marker consumption and staging cleanup

- Consumption = successful create-once `application-marker.json` write only.
- Pre-marker block = `UNCONSUMED_PRE_MARKER_BLOCKED`.
- Staging cleanup = exact path, known regular files only, no `shutil.rmtree`, original exception controlling, secondary cleanup blocker when unexpected entries exist.

## 7. Focused test commands and exact results

Interpreter: repository `.venv/bin/python` (Python 3.12.13).

```text
.venv/bin/python -m unittest tests.test_v2_9_8b_window_15m_historical_authorization_evidence_contract -v
→ Ran 37 tests … OK

.venv/bin/python -m unittest \
  tests.test_v2_9_8b_window_15m_git_provenance_authorization_manifest \
  tests.test_v2_9_8b_window_15m_one_shot_wrapper \
  tests.test_v2_9_8b_window_15m_ignored_evidence_visibility
→ Ran 135 tests in ~12.8s … OK
```

Additional verification:

```text
.venv/bin/python -m compileall -q \
  src/printer_v1/operator_cli/git_provenance_authorization_manifest.py \
  src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py \
  src/printer_v1/operator_cli/window_15m_authorization_preparation.py
→ exit 0

git diff --check
→ exit 0

grep -R SELECTED_MINT_NOT_IN_REGISTRY src tests
→ ABSENT

search for wildcard/directory-wide authorization allowance in production owners
→ none added
```

Covered proofs include approved multi-file historical packages, unlisted/safe-looking package rejection, trust-root malformation, T/H split, complete inventory equality, allowlist/digest determinism, preparation parity, pre-marker non-consumption, staging cleanup, marker consumption boundary, Manifest V1 rejection, Marker V1 acceptance, ignored SQLite reconciliation, and current-vs-historical trust-boundary regressions.

## 8. Authoritative database identity

Read-only remeasurement before and after implementation:

| Field | Value |
| --- | --- |
| path | `data/printer_v1.sqlite3` |
| size | `68366336` |
| SHA-256 | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` |
| inode | `1230526` |
| mtime_ns (stat seconds field observed) | `1785970388` |
| integrity | `ok` |
| foreign-key violations | `0` |
| WAL/SHM/journal | absent |
| migration count | `52` |
| migration head | `052_memory_observation_eligibility_layers.sql` |

Identity unchanged before and after this lane.

## 9. Historical packages untouched

Untracked historical packages remain on disk and were not modified, moved, deleted, or reissued:

| Authorization ID | Disposition | final_authorization.json SHA-256 (post-lane) |
| --- | --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` | `PERMANENTLY_CONSUMED_PRESERVED` | `c928f9588f5c82b350f71d0df40c4cb3a7e2a92fd366541f109488edbc17dcea` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` | `BLOCKED_UNCONSUMED_SUPERSEDED` | `d58e354a2d01acc0c893ff20941055cd4cf5fb86e2b4daf889b0e8312db90e59` |

Neither package was reused, edited, deleted, moved, or reissued.

## 10. No authorization or runtime path ran

Confirmed absent in this lane:

- public PowerShell one-shot wrapper execution;
- real-repository `apply_authorization_once`;
- application marker creation under live `APPLICATION_ROOT`;
- provider contact;
- discovery;
- Central Scheduler / campaign / factory run;
- memory generation;
- DB write/migration;
- retrieval / paper-trading unlock.

Disposable tests may call `apply_authorization_once` only against temporary repositories and temporary application roots.

## 11. Money-usefulness contribution

Restores a lawful pre-marker inventory path so a correctly prepared exact-HEAD authorization can pass while preserved historical packages remain non-reusable and exact-file-bound. Creates no market signal, decision, position, trade, or PnL claim.

## 12. What this repair improves

- preserved prior authorization evidence can remain untracked without blocking every later authorization;
- unknown package directories cannot self-authorize by location;
- every accepted historical file is bound by exact path/size/SHA-256 and approved ID membership;
- preparation becomes an honest predictor of production pre-marker inventory validation;
- consumption wording matches marker creation;
- pre-marker staging residue is bounded and safely cleaned.

## 13. What remains locked

- retrieval or dirty-memory use;
- paper decisions or BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, keys, signing, real funds, live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, vectors;
- retry/rerun/resume/restart/successor;
- reuse of `…005252Z` or `…224959Z`;
- Source Governor or Central Scheduler bypass;
- `WINDOW_1H` / `4H` / `12H` / `24H` activation;
- any guarantee of provider success, eligible two-token supply, or clean memory.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Severity | Status / mitigation |
| --- | --- | --- |
| Authorization creator blindly copies all directory IDs into trust list | High | preparation must supply explicit known history; owner never discovers IDs |
| Growing historical ID/file counts | Medium | optional later rollover into `T`; enumeration remains bounded to auth root |
| Builder/validator schema mismatch | High | atomic V2 merge in one commit tip |
| Incorrect `M ∪ H` in current-package equality | High | split reconciliation signature and tests |
| Disposition metadata unavailable | Low | `DISPOSITION_NOT_AVAILABLE`; never trust/reuse authority |
| Staging cleanup deletes unrelated evidence | High | exact-path known-entry-only cleanup |
| Operator mistakes unconsumed for reusable | High | superseded disposition + exact HEAD law |
| Preparation parity marketed as full readiness | Medium | explicit non-equality in return payload and docs |

## 15. Exact next step

Independent inspection of this implementation closeout, then a **separate readiness lane**, followed by **one fresh authorization on the repaired HEAD**.

Do **not** create that authorization in this lane.

## 16. Commit message

```text
Implement historical authorization evidence contract
```
