# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Readiness Audit 2

Date: 2026-08-02

Linear tracking issue: `DTW-8`

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Readiness Audit`

Instance:
`2 — V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Lane type: audit/readiness only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_READINESS_AUDIT_2_PASS`

The exact consumed authorization package is ready for a separate evidence-specific historical-rollover design lane.

The package:

- is complete and immutable at the audited boundary;
- is permanently consumed and non-reusable;
- remains current untracked evidence at its original repository path;
- is bound to one preserved external application record;
- can be transitioned into immutable tracked history at the same path without moving or rewriting bytes;
- has no tracked-path collision at the current baseline;
- must remain distinct from the retained Migration-050 current package.

This PASS does not stage, commit, move, rename, rewrite, chmod, delete, or otherwise mutate evidence. It does not authorize fresh readiness, a fresh authorization, a wrapper application, or a campaign.

## 2. Controlling source stack

This audit is governed by:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-python-builder-guide.md`;
- `docs/printer-v1-v2-9-8b-post-interpreter-repair-authoritative-window-15m-campaign-readiness-audit.md`;
- the interpreter failure-audit, repair, proof, and closeout reports;
- the previously closed current-evidence historical-rollover pattern, used only as precedent.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this source stack and is not the sole source of truth.

## 3. Exact baseline and scope

| Item | Exact value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-current-evidence-historical-rollover-readiness-audit-2` |
| Starting HEAD | `6cd4bd38ce65e5a160ed2198391cfa279998b0e2` |
| Blocking readiness verdict | `V2_9_8B_POST_INTERPRETER_REPAIR_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_READINESS_AUDIT_BLOCKED_CURRENT_EVIDENCE_ROLLOVER_REQUIRED` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorization path | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json` |
| Authorization SHA-256 | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Retained migration execution | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |

Allowed work performed:

- committed report and Git-history review;
- exact package identity and consumption-state review;
- read-only current-vs-historical classification;
- tracked-destination collision review;
- external application binding review;
- rollover safety and stop-condition definition.

Not performed:

- evidence staging or commit;
- file move, rename, rewrite, deletion, chmod, or timestamp touch;
- manifest, marker, or authorization creation;
- wrapper or operational command execution;
- provider/source access;
- Source Governor or Central Scheduler runtime;
- campaign, discovery, lifecycle, SQLite, memory, retrieval, decision, trade, audit, or PnL activity;
- production or test code changes;
- test execution.

## 4. Exact authorization package

Repository root:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Package inventory:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `final_authorization.json` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |

Audited package properties:

- file count: `1`;
- symlink count: `0`;
- non-regular entry count: `0`;
- duplicate-path count: `0`;
- path is normalized and authorization-ID specific;
- the package remains at its original repository path;
- the user's latest local Git status classifies it as untracked current evidence;
- the current committed tree does not already track this authorization-specific file.

The tracked historical destination is therefore the exact same repository path. No physical relocation is required or permitted.

## 5. Authorization identity and non-reuse

| Field | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorized branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| Authorized HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Authorized mode | ordinary `run` |
| Explicit operator approval | `true` |
| Allowed invocation count | `1` |
| Main window | `WINDOW_15M` |
| Selective 1h continuation | `false` |
| Automatic retry | `false` |
| Manual rerun | `false` |
| Resume | `false` |
| Restart | `false` |
| Successor | `false` |
| Consumed | `true` |
| Reusable | `false` |

The authorization was consumed when its create-once marker was written. The external application directory exists, and the wrapper also rejects reuse when the canonical application directory already exists.

Historical rollover changes evidence classification only. It cannot restore, amend, reissue, resume, or make the authorization reusable.

## 6. External application binding

External application directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Immutable application inventory:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `application-marker.json` | `881` | `c32d25577010e391ad103ec0f709955d3a13bd12b877ef7dddbee375d20e54ef` |
| `child-stderr.txt` | `204` | `1eb9c38e1513b3dd8e7861f5674cf09cbed2d340b0059f54c56edb6eca651dc1` |
| `child-stdout.txt` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git-provenance-manifest.json` | `4769` | `8c8ff8916f260349de0d5ee2b3d8440bbfbf7c1dd1ad82ead0f94fe6df6e7ddb` |
| `wrapper-terminal.json` | `1774` | `ff3370d2890b3b95ac640f4e3b543009893de4dd8ddc6569d2b34ceac82f7a17` |

The application parent also retains one authorization-specific historical empty staging directory.

Complete application-parent sorted file-hash-listing SHA-256:

`f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`

The authorization JSON, manifest, marker, and wrapper terminal form one exact binding chain. Rollover must not modify any external application or staging artifact.

## 7. Historical destination and collision review

The approved destination is not a new directory. It is the current package's exact repository path:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`

The implementation concept is classification by Git tracking:

```text
same path + same bytes
untracked current evidence -> tracked immutable historical evidence
```

Readiness findings:

- the exact path is currently untracked according to the user's fresh status;
- the baseline commit contains no tracked file at that authorization-specific path;
- no destination rename is required;
- no destination overwrite is permitted;
- the authorization ID is unique from the earlier historical authorization ID;
- the package path cannot collide with the retained Migration-050 package;
- the implementation must stage the exact existing file, not recreate it from copied JSON.

## 8. Retained Migration-050 boundary

The migration package remains current evidence and must not be tracked by this rollover:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Accepted identity:

- file count: `12`;
- symlink count: `0`;
- sorted identity-listing SHA-256: `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- two retained SQLite evidence files remain ignored current evidence and must never be opened or staged by the rollover;
- Migration 050 must not run again.

After successful rollover, expected current evidence is the retained twelve-file migration package only.

## 9. Authoritative DB boundary

Last independently reconciled identity:

| Field | Value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL | absent |
| SHM | absent |
| Journal | absent |

The rollover design and implementation must hash/stat the DB before and after without opening SQLite. Any identity or sidecar drift blocks and rolls back the Git staging/commit attempt where possible.

## 10. Required design contract

The next design must specify:

1. exact starting branch and HEAD;
2. the one-file authorization package allowlist;
3. pre-mutation package, migration, DB, and external-application snapshots;
4. exact proof that the authorization is consumed and non-reusable;
5. exact proof that the path is untracked and collision-free;
6. staging of the existing file only, with no content generation;
7. a commit containing exactly:
   - the authorization file;
   - one implementation report;
8. no staging of Migration-050 evidence;
9. no file move, rename, rewrite, chmod, or deletion;
10. post-commit proof that the tracked blob bytes equal the pre-mutation file bytes;
11. post-commit repository inventory reconciliation;
12. rollback handling for any failure before commit;
13. fail-closed handling if a commit succeeds but post-commit proof fails;
14. bounded proof and independent closeout after implementation;
15. a new fresh authoritative readiness audit only after rollover closeout.

## 11. Acceptance and stop conditions

The later implementation may proceed only if the design preserves all conditions above.

Immediate stop conditions include:

- authorization path or SHA mismatch;
- package contains an extra file, symlink, or non-regular entry;
- authorization is not provably consumed;
- tracked destination already exists or differs;
- migration identity drift;
- DB identity or sidecar drift;
- external application identity drift;
- staged scope contains anything beyond the authorization file and approved implementation report;
- evidence bytes change;
- any runtime or provider path is entered.

## 12. Money-usefulness contribution

This readiness audit protects the next one-shot authorization from being rejected by stale current evidence.

It preserves failed-attempt evidence while restoring a clean bounded current namespace for later memory collection.

It creates no memory, market signal, paper decision, trade, or profit claim.

## 13. What this audit improves

- proves the exact consumed package is eligible for historical classification;
- identifies a collision-free same-path transition;
- preserves the external application binding;
- protects Migration-050 as current evidence;
- defines a minimum, auditable mutation scope;
- prevents a generic prior script from being reused without new identity checks.

## 14. What remains locked

This PASS does not unlock:

- evidence staging or commit;
- fresh authoritative readiness;
- fresh authorization;
- manifest or marker creation;
- wrapper application;
- provider/source access;
- Source Governor or Central Scheduler runtime;
- campaign execution;
- SQLite access or mutation;
- memory generation or retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- longer windows, live funds, wallets, keys, paid APIs, scoring, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana-memecoin-only, and paper-only.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Readiness disposition |
| --- | --- |
| Accidentally staging Migration-050 files | Design must use an exact one-file authorization allowlist |
| Recreating JSON instead of tracking existing bytes | Forbidden; stage the exact existing file |
| Git changes file mode unexpectedly | Verify tracked blob and mode against pre-mutation identity |
| Commit succeeds but later proof fails | Fail closed; do not amend, reset, or hide the result without a new audit |
| External application is outside Git | Preserve and hash independently before/after |
| Generic prior rollover script targets old IDs | New design must bind the current ID and exact evidence identities |
| DB is opened during rollover | Forbidden; hash/stat only |
| Historical classification mistaken for authorization reuse | Explicitly impossible; consumption remains permanent |

## 16. Roadmap decision

- rollover readiness passed: `true`;
- rollover design lane authorized: `true`;
- rollover implementation authorized: `false`;
- fresh readiness authorized: `false`;
- fresh authorization authorized: `false`;
- wrapper application or campaign authorized: `false`.

## 17. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design 2`
