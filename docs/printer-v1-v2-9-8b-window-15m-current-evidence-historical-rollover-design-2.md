# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design 2

Date: 2026-08-02

Linear tracking issue: `DTW-9`

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design 2`

Authorization instance:
`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_DESIGN_2_PASS`

The minimum safe rollover is approved for a later local implementation.

The implementation must classify exactly one existing consumed authorization file as immutable tracked history at its current repository path. It must not regenerate, copy, move, rename, rewrite, chmod, delete, or otherwise transform the evidence file.

The implementation commit may contain exactly:

1. the existing `final_authorization.json`;
2. one implementation report.

The retained twelve-file Migration-050 package must remain current untracked evidence and must not enter the commit.

This design does not perform the rollover, authorize fresh readiness, create a fresh authorization, run the wrapper, or execute a campaign.

## 2. Controlling source stack

This design is governed by:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-python-builder-guide.md`;
- `docs/printer-v1-v2-9-8b-post-interpreter-repair-authoritative-window-15m-campaign-readiness-audit.md`;
- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-readiness-audit-2.md`;
- the committed one-shot failure, repair, proof, and closeout reports;
- the previously closed rollover mechanism, used as precedent only.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this source stack and is not the sole source of truth.

## 3. Exact baseline

| Item | Exact value |
| --- | --- |
| Design branch | `agent/v2-9-8b-window-15m-current-evidence-historical-rollover-design-2` |
| Starting HEAD | `0b15faf2fa7c7502d3bda54fee60459858333677` |
| Readiness verdict | `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_READINESS_AUDIT_2_PASS` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorization SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Authorization bytes | `8019` |
| Retained migration execution | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |

The implementation must start from this design commit and fail closed if branch, HEAD, status, evidence, DB, external application, or Git classification has drifted.

## 4. Exact evidence transition

### 4.1 Track in place

The only evidence file permitted to become tracked history is:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`

Required identity:

| Field | Value |
| --- | --- |
| Size | `8019` bytes |
| SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Entry type | regular file |
| Symlink | `false` |
| Current Git classification | untracked current evidence |
| Target Git classification | tracked immutable history |
| Physical destination | unchanged; same path |

The implementation must stage the exact existing file. It must not produce replacement JSON from a template, copy, shell redirection, Python serialization, or any other reconstruction.

### 4.2 Git mode truth

The audited worktree file is read-only at the incident boundary. Git records only the executable bit, so the expected stage-0 mode is `100644` even when the current worktree permission is `0444`.

The implementation must not claim that Git preserves the full POSIX `0444` mode across future checkouts. Historical integrity is established by:

- the exact committed blob bytes;
- the exact repository path;
- the authorization/application binding;
- the one-shot consumption evidence.

The implementation must not chmod the worktree file merely to match Git's normal `100644` index mode.

### 4.3 Retain as current evidence

The following package remains current and untracked:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Required identity:

- file count: `12`;
- symlink count: `0`;
- sorted identity-listing SHA-256: `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- two `.sqlite3` evidence files remain ignored;
- no Migration-050 file may be staged or committed;
- Migration 050 must not run again.

## 5. Implementation report and commit scope

The implementation may create exactly one report:

`docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2.md`

The implementation commit must contain exactly two paths:

1. `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`;
2. `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2.md`.

Commit message:

`Implement second current evidence historical rollover`

Forbidden commit content includes:

- any Migration-050 file;
- any external application artifact;
- production code or tests;
- any other documentation;
- database files or sidecars;
- caches, logs, or generated output.

## 6. Pre-mutation snapshot contract

Before creating the report or staging any path, implementation must capture and retain in memory/output:

### 6.1 Repository state

- exact branch;
- exact starting HEAD;
- clean tracked worktree;
- clean index;
- exact untracked roots;
- tracked, visible-current, ignored-current, and full `operator-runs/` inventories;
- proof that the authorization path is untracked and absent from `HEAD`.

### 6.2 Authorization package

- complete one-file tree snapshot;
- path, file type, size, mode, `mtime_ns`, and SHA-256;
- canonical JSON parse with duplicate-key rejection;
- authorization ID, authorized branch/HEAD, migration ID, command mode, invocation count, one-shot false flags, main window, and 1h lock;
- proof that the external marker and application make it consumed and non-reusable.

### 6.3 Migration package

- complete twelve-file tree snapshot;
- exact path inventory;
- sizes and SHA-256 values;
- no symlink or non-regular entry;
- sorted identity-listing digest.

### 6.4 Authoritative DB

Hash/stat only, with no SQLite connection:

| Field | Required baseline |
| --- | --- |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL/SHM/journal | absent |

### 6.5 External application

Snapshot:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications`

The snapshot must include the five authorization-specific application files and the preserved historical empty staging directory.

Required complete-parent sorted file-hash-listing SHA-256:

`f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`

## 7. Byte-preserving index procedure

Broad staging commands are forbidden:

- `git add .`;
- `git add -A`;
- `git add operator-runs/`;
- staging the authorization parent directory.

The implementation must use the exact authorization path and report path.

For the authorization file:

1. verify the pre-mutation identity;
2. inspect `git check-attr --all -- <path>`;
3. compute the raw worktree blob object ID with `git hash-object --no-filters -- <path>`;
4. stage the exact path only;
5. inspect the stage-0 entry with `git ls-files --stage -- <path>`;
6. require index mode `100644`;
7. read staged bytes with `git cat-file blob <object-id>`;
8. require staged size `8019` and SHA-256 `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60`;
9. require the staged blob object ID to equal the no-filter raw-byte object ID;
10. require the file to be an addition, not a replacement or rename.

If attributes or filters would transform bytes, implementation must unstage and stop. It must not work around the result by rewriting evidence.

For the report:

- create it only after all pre-mutation checks pass;
- stage it by exact path;
- verify the staged set is exactly the two approved paths.

## 8. Pre-commit rollback contract

Any failure before a successful commit must:

1. unstage only the exact authorization and report paths;
2. delete only the newly created untracked implementation report;
3. never restore, checkout, reset, clean, remove, chmod, rewrite, or touch the authorization file;
4. never touch Migration-050 evidence;
5. revalidate authorization, migration, DB, external application, and repository snapshots;
6. require return to the original two untracked evidence roots and clean tracked/index state.

A broad `git reset --hard`, `git clean`, or worktree restore of evidence is forbidden.

## 9. Commit and post-commit contract

After all staged checks pass, create one commit with the exact message.

Immediately verify:

- parent equals the design commit;
- message is exact;
- commit scope is exactly the two approved files;
- the committed authorization blob equals the audited pre-mutation bytes;
- the committed path is unchanged;
- the worktree authorization file remains byte-identical;
- Migration-050 remains byte-identical and untracked;
- DB identity and sidecars remain unchanged;
- external application identity remains unchanged;
- tracked tree and index are clean;
- final untracked status contains only the retained Migration-050 root.

Expected namespace after implementation:

| Set | Expected count |
| --- | ---: |
| Tracked historical `T` | `19` |
| Visible current | `10` |
| Ignored current | `2` |
| Current evidence `M` | `12` |
| Complete inventory `F` | `31` |

Required relationships:

```text
F == T union M
T intersect M == empty
M == visible-current union ignored-current
```

## 10. Post-commit failure law

After a successful commit, automatic reset, amend, force-move, revert, or deletion is forbidden.

If any post-commit check fails:

- preserve the commit and all evidence;
- return a precise BLOCKED verdict;
- report the exact mismatch;
- do not conceal the result;
- require a new independent audit before any repair action.

Evidence honesty takes priority over producing a PASS.

## 11. Minimum implementation verification

No broad test suite is required because no production code changes.

Minimum sufficient verification:

- exact branch/HEAD/status;
- exact one-file authorization allowlist;
- exact twelve-file migration allowlist;
- canonical authorization JSON and one-shot state;
- raw worktree/staged/committed blob equality;
- exact two-file staged and commit scope;
- namespace arithmetic before and after;
- DB hash/stat and absent sidecars before and after;
- external application snapshot equality;
- no protected capability execution;
- `git diff --check` for the report;
- final clean tracked/index state.

## 12. Bounded proof design

The later bounded proof is read-only except for one proof report.

It must independently verify:

1. implementation commit descends exactly from this design commit;
2. implementation commit contains exactly the authorization file and implementation report;
3. committed authorization blob has the audited size and SHA-256;
4. worktree authorization file matches the committed blob;
5. path remained unchanged;
6. authorization is still consumed and non-reusable;
7. all twelve Migration-050 files remain untracked and byte-identical;
8. namespace is `T=19`, visible `=10`, ignored `=2`, `M=12`, `F=31`;
9. DB and sidecars match the implementation baseline;
10. external application remains unchanged;
11. zero runtime/provider/Scheduler/campaign/SQLite/memory/retrieval/financial capabilities executed.

Proof commit may add exactly one proof report.

## 13. Independent closeout design

Independent closeout must reconcile:

- readiness audit → design → implementation → bounded proof ancestry;
- exact commit scopes;
- pre-stage, staged, committed, and worktree byte identities;
- authorization consumption/non-reuse truth;
- migration retention;
- DB and external application preservation;
- namespace arithmetic;
- rollback and post-commit failure laws;
- zero protected-capability execution.

Only a closeout PASS may authorize another fresh authoritative readiness audit.

## 14. Fresh-readiness boundary

Rollover completion does not authorize a new authorization or campaign.

After closeout, fresh readiness must independently recheck:

- exact branch/HEAD and clean state;
- Migration-050 package and namespace;
- current authorization package count equals zero;
- DB identity, integrity/readiness requirements, sidecars, and active residue as required by that lane;
- lexical repository venv/bootstrap readiness;
- required environment-variable shape without exposing values;
- all one-shot, Source Governor, Scheduler, memory, retrieval, and financial locks.

## 15. Money-usefulness contribution

This design removes a known namespace blocker using the smallest possible evidence transition.

It preserves the failed attempt as immutable history while protecting the retained migration package for a later fresh one-shot attempt.

It creates no memory, market signal, decision, trade, or profit claim.

## 16. What this design improves

- one-file evidence mutation boundary;
- same-path, same-byte historical classification;
- no broad staging exposure;
- explicit Git filter/blob verification;
- deterministic pre-commit rollback;
- honest post-commit fail-closed behavior;
- exact proof and closeout contracts;
- clear route back to fresh readiness.

## 17. What remains locked

This design does not unlock:

- evidence tracking before the implementation lane;
- fresh authoritative readiness;
- fresh authorization;
- manifest, marker, or wrapper application;
- providers, Source Governor, Scheduler, or campaign runtime;
- SQLite access or mutation;
- memory generation or retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- longer windows, wallets, keys, real funds, live execution, paid APIs, scoring, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana-memecoin-only, and paper-only.

## 18. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design control |
| --- | --- |
| Broad staging captures Migration-050 | Exact file allowlist; parent/broad adds forbidden |
| JSON is regenerated or normalized | Stage the existing file; compare raw/staged/committed bytes |
| Git attributes transform evidence | `check-attr`, no-filter object ID, and staged blob equality |
| Full POSIX read-only mode is not represented by Git | Record expected `100644`; preserve bytes and current worktree mode without false claims |
| Pre-commit failure leaves index dirty | Exact-path unstage and report-only deletion |
| Rollback touches evidence | Reset/clean/restore/chmod of evidence forbidden |
| Commit succeeds but proof fails | Preserve commit and return BLOCKED; no amend/reset |
| Migration evidence enters history | Exact staged/commit scope and post-status checks |
| External application drifts | Snapshot complete parent before/after |
| Historical classification is mistaken for reuse | Consumption and application directory remain permanent |

## 19. Roadmap decision

- design passed: `true`;
- exact implementation lane authorized: `true`;
- rollover already performed: `false`;
- fresh readiness authorized: `false`;
- fresh authorization or campaign authorized: `false`.

## 20. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Implementation 2`
