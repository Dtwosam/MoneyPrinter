# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Implementation 2

Date: 2026-08-02

Linear tracking issue: `DTW-10`

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Implementation 2`

Authorization instance:
`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Lane type: same-path, same-byte Git classification change only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_IMPLEMENTATION_2_PASS`

The exact consumed authorization file was transitioned from untracked current
evidence into immutable tracked history at its original repository path without
moving, copying, renaming, rewriting, chmod-ing, or otherwise transforming its
bytes. The commit contains exactly the authorization file and this implementation
report. The retained twelve-file Migration-050 package remains current untracked
evidence. The authoritative database, external application evidence, and all
protected-capability locks are unchanged.

This PASS performs only the approved Git classification change. It does not
regenerate evidence, restore or reuse the consumed authorization, authorize fresh
readiness, create a fresh authorization, run the wrapper, open SQLite, generate
memory, activate retrieval, or execute a campaign.

## 2. Controlling source stack

Governed by the active Printer V1 source stack:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-python-builder-guide.md`;
- `docs/printer-v1-v2-9-8b-post-interpreter-repair-authoritative-window-15m-campaign-readiness-audit.md`;
- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-readiness-audit-2.md`;
- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-design-2.md`;
- `docs/printer-v1-v2-9-8b-window-15m-one-shot-application-failure-audit.md`;
- `docs/printer-v1-v2-9-8b-window-15m-one-shot-child-interpreter-preservation-repair-independent-closeout.md`;
- the committed active Printer V1 wrapper stack, whose one-shot wrapper identity
  (`src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`,
  SHA-256 `77e35c14860e3aae02f570e18773a8c7edb2f76e71d3772adb0ec58ef57d37c6`)
  remains the immutable failure/repair reference and was not touched.

This lane follows
`docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-design-2.md`
exactly.

## 3. Exact baseline

| Item | Exact value |
| --- | --- |
| Implementation branch | `agent/v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2` |
| Starting HEAD | `5b74ee218c9863ff5279b72a1f71c545e2907123` |
| Design commit / parent | `5b74ee218c9863ff5279b72a1f71c545e2907123` |
| Design verdict | `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_DESIGN_2_PASS` |
| Readiness verdict | `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_READINESS_AUDIT_2_PASS` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Retained migration execution | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Starting tracked worktree | clean |
| Starting index | clean |

Untracked roots at baseline (exactly two):

```text
operator-runs/v2-9-8b-authoritative-mig050/
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/
```

## 4. Pre-mutation identities

### 4.1 Repository state

- exact branch and HEAD confirmed above;
- tracked worktree and index clean before staging;
- authorization path untracked (`git ls-files` empty) and absent from `HEAD`
  (`git cat-file -e HEAD:<path>` → `128`, "exists on disk, but not in 'HEAD'").

### 4.2 Authorization file (the only file rolled over)

Path:
`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`

| Field | Value |
| --- | --- |
| Entry type | regular file |
| Symlink | `false` |
| Size | `8019` bytes |
| SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Worktree mode | `0444` |
| Current Git classification | untracked current evidence |
| Absent from starting `HEAD` | `true` |

Package inventory: `1` regular file, `0` symlinks, `0` non-regular entries.

Canonical JSON parse with duplicate-key rejection: PASS (no duplicate keys).
Parsed-bytes SHA-256 equals the file SHA-256.

Authorization fields:

| Field | Value |
| --- | --- |
| `authorization_id` | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorized branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| Authorized HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |
| `migration_execution_id` | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Command mode | `run` (operator-approved) |
| `allowed_invocation_count` | `1` |
| Main window | `WINDOW_15M` |
| `selective_1h_continuation` | `false` |
| `automatic_retry_allowed` | `false` |
| `manual_rerun_allowed` | `false` |
| `resume_allowed` | `false` |
| `restart_allowed` | `false` |
| `successor_allowed` | `false` |

### 4.3 Migration-050 package (retained current evidence)

Root:
`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

- file count: `12`; symlink count: `0`; non-regular: `0`;
- every file's SHA-256 matches the closeout/bounded-proof record;
- sorted `shasum` identity-listing SHA-256 (repo-relative paths):
  `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- two `.sqlite3` files remain ignored current evidence (not opened, not staged);
- Migration 050 was not run again.

### 4.4 Authoritative database (stat/hash only, no SQLite)

| Field | Value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Type | regular file |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL / SHM / journal | absent |

No SQLite connection was opened. Identity established by `os.lstat` and file
hashing only.

### 4.5 External application (consumption + non-reuse)

Application directory:
`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Five immutable application files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `application-marker.json` | 881 | `c32d25577010e391ad103ec0f709955d3a13bd12b877ef7dddbee375d20e54ef` |
| `child-stderr.txt` | 204 | `1eb9c38e1513b3dd8e7861f5674cf09cbed2d340b0059f54c56edb6eca651dc1` |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-provenance-manifest.json` | 4769 | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| `wrapper-terminal.json` | 1774 | `ff3370d2890b3b95ac640f4e3b543009893de4dd8ddc6569d2b34ceac82f7a17` |

Plus one preserved historical empty staging directory under the application
parent `.staging/`.

Complete application-parent sorted file-hash-listing SHA-256 (absolute paths):
`f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`

## 5. Authorization consumption and non-reuse proof

The external application marker
(`application-marker.json`, `PRINTER_V1_APPLICATION_MARKER_V1`) records:

- `authorization_consumed_at`: `2026-08-02T11:34:17.389120+00:00`;
- `authorization_sha256`: `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60`;
- `manifest_sha256`: `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb`;
- `allowed_invocation_count`: `1`;
- `automatic_retry_allowed` / `manual_rerun_allowed` / `resume_allowed` /
  `restart_allowed` / `successor_allowed`: all `false`.

The create-once marker and the canonical application directory prove the
authorization is permanently consumed and non-reusable. Historical Git
classification changes evidence status only; it cannot restore, amend, reissue,
resume, or make the authorization reusable.

## 6. Raw / staged / committed / worktree blob identities

The exact byte-preserving index procedure was followed on the exact path only.

| Stage | Object ID | Size | SHA-256 |
| --- | --- | ---: | --- |
| Raw worktree (`git hash-object --no-filters`) | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Staged (`git ls-files --stage` / `git cat-file blob`) | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Committed blob (`HEAD:<path>` after commit) | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Worktree after commit | n/a (regular file) | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |

- `git check-attr --all -- <path>`: no attributes (no filter/text/eol transform);
- staged index mode: `100644`;
- staged blob object ID equals the raw no-filter object ID;
- diff status: `A` (addition at the same path — not a replacement or rename);
- worktree mode remained `0444` and was not chmod-ed to match Git's `100644`.

Git records only the executable bit, so the stage-0 mode `100644` is expected even
though the worktree permission is `0444`. Historical integrity rests on the exact
committed blob bytes, the exact repository path, the authorization/application
binding, and the one-shot consumption evidence — not on Git preserving the full
POSIX `0444` mode.

## 7. Exact staged and committed scope

Staged set before commit (exactly two paths):

1. `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json` (`A`);
2. `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2.md` (`A`).

Committed scope: exactly the same two paths. No Migration-050 file, external
application artifact, production code, test, other documentation, database file,
sidecar, cache, log, or generated output entered the commit.

Broad staging (`git add .`, `git add -A`, `git add operator-runs/`, staging the
authorization parent directory) was not used. Only the two exact paths were
staged.

## 8. Migration-050 preservation

Post-commit, the Migration-050 package is byte-identical and remains untracked:

- file count `12`, symlink count `0`;
- sorted identity-listing SHA-256 unchanged:
  `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- both `.sqlite3` files remain ignored and were never opened or staged;
- no Migration-050 path appears in the commit.

## 9. DB and external application before/after reconciliation

| Item | Before | After |
| --- | --- | --- |
| DB size | `65671168` | `65671168` |
| DB SHA-256 | `56ca1218…d4c8eed5` | `56ca1218…d4c8eed5` |
| DB `mtime_ns` | `1785617072867102156` | `1785617072867102156` |
| DB WAL/SHM/journal | absent | absent |
| External application-parent digest | `f1a12143…f96f` | `f1a12143…f96f` |

No SQLite connection was opened before, during, or after the classification
change. The external application evidence and its historical empty staging
directory were not modified.

## 10. Namespace before / after

| Set | Before | After |
| --- | ---: | ---: |
| Tracked historical `T` | `18` | `19` |
| Visible current | `11` | `10` |
| Ignored current | `2` | `2` |
| Current evidence `M` | `13` | `12` |
| Complete inventory `F` | `31` | `31` |

Required relationships (after):

```text
F == T union M            -> 31 == 19 + 12
T intersect M == empty    -> disjoint
M == visible-current union ignored-current -> 12 == 10 + 2
```

Exactly one file (the consumed authorization) moved from visible current evidence
into tracked history. Final untracked status contains only:

```text
operator-runs/v2-9-8b-authoritative-mig050/
```

## 11. Protected capability zero counters

| Capability | Executions |
| --- | ---: |
| Wrapper / operational command | 0 |
| Manifest / marker / authorization creation | 0 |
| Provider / source contact | 0 |
| Source Governor runtime | 0 |
| Central Scheduler runtime | 0 |
| Discovery / campaign | 0 |
| SQLite open / mutation | 0 |
| Memory generation | 0 |
| Retrieval / decisions | 0 |
| Positions / trades / audits / PnL | 0 |
| Migration 050 re-run | 0 |
| Production code / test modification | 0 |
| Broad test-suite runs | 0 |
| Commit push | 0 |

## 12. Money-usefulness contribution

This implementation removes the known current-evidence namespace blocker using the
smallest possible evidence transition. It preserves the failed one-shot attempt as
immutable, same-byte tracked history while protecting the retained Migration-050
package as current evidence for a later fresh one-shot attempt. It creates no
memory, market signal, decision, trade, or profit claim.

## 13. What improved

- the consumed authorization is now immutable tracked history at its exact path;
- the current namespace returns to one bounded migration package with no current
  authorization package;
- explicit raw/staged/committed/worktree blob equality is on record;
- Git filter/attribute neutrality is proven for the evidence bytes;
- the fresh-readiness roadmap order is restored.

## 14. What remains locked

This implementation does not unlock:

- fresh authoritative readiness;
- fresh authorization;
- manifest, marker, or wrapper application;
- providers, Source Governor, Central Scheduler, or campaign runtime;
- SQLite access or mutation;
- memory generation or retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- longer windows, wallets, keys, real funds, live execution, paid APIs, scoring,
  or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, and paper-only.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Implementation disposition |
| --- | --- |
| Broad staging captures Migration-050 | Avoided; only the two exact paths were staged |
| JSON regenerated or normalized | Avoided; raw == staged == committed == worktree bytes (`8019` / `af63b05…`) |
| Git attributes transform evidence | `check-attr` empty; no-filter OID equals staged OID |
| Full POSIX `0444` not represented by Git | Recorded expected `100644`; worktree mode left `0444`, no false claim |
| Commit succeeds but a post-commit check fails | Post-commit checks passed; otherwise preserve commit and return BLOCKED |
| Migration evidence enters history | Prevented; exact scope and post-status checks confirm untracked |
| External application drifts | Parent digest reconciled before/after (`f1a12143…f96f`) |
| Historical classification mistaken for reuse | Consumption/non-reuse remain permanent; marker and application directory persist |

## 16. Roadmap decision

- implementation performed: `true`;
- rollover complete (authorization now tracked history): `true`;
- Migration-050 retained as current evidence: `true`;
- fresh readiness authorized: `false`;
- fresh authorization or campaign authorized: `false`.

## 17. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Bounded Proof 2`
