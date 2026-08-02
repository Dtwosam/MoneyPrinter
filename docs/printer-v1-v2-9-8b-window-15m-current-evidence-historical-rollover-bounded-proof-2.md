# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Bounded Proof 2

Date: 2026-08-02

Linear tracking issue: `DTW-11`

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Bounded Proof 2`

Lane type: bounded read-only proof and documentation only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_BOUNDED_PROOF_2_PASS`

The second current-evidence historical rollover is proven for its exact approved scope.

The consumed authorization file
`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`
was added to Git at its existing repository path without a rename or replacement. The implementation commit contains exactly that authorization file and one implementation report. Remote Git inspection independently confirms the exact ancestry, exact two-path scope, same-path addition, and committed blob identity.

The committed implementation report preserves and reconciles the Mac-local pre-stage, staged, committed, and worktree identities; Migration-050 current evidence; authoritative database identity and sidecar absence; external application identity; namespace arithmetic; and zero protected-capability activity.

This proof does not claim that a second Mac-local mutation or runtime command was executed. It proves the committed rollover from remote Git truth plus the implementation's committed local reconciliation record. No wrapper, provider, Scheduler, campaign, SQLite, memory, retrieval, decision, trade, audit, or PnL path ran in this proof lane.

## 2. Controlling source stack

This proof is governed by:

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
- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2.md`;
- the committed one-shot failure, interpreter-repair, proof, and closeout reports.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside the controlling source stack and is not the sole source of truth.

## 3. Exact baseline and method

| Item | Exact value |
| --- | --- |
| Proof branch | `agent/v2-9-8b-window-15m-current-evidence-historical-rollover-bounded-proof-2` |
| Starting HEAD | `0ee0ccc7258f462e528c175ac330da35cdaa00fd` |
| Implementation parent | `5b74ee218c9863ff5279b72a1f71c545e2907123` |
| Implementation message | `Implement second current evidence historical rollover` |
| Implementation verdict | `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_IMPLEMENTATION_2_PASS` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Proof runtime commands | `0` |
| Production/test code changes | `0` |

Proof method:

1. remote Git commit and compare inspection;
2. remote committed authorization blob inspection;
3. remote committed implementation-report reconciliation;
4. exact design-contract review;
5. lock and roadmap-boundary review;
6. one proof report only.

No broad or focused test suite was required because the implementation changed no production or test code.

## 4. Exact ancestry and implementation scope

Remote comparison proves:

- implementation commit `0ee0ccc7258f462e528c175ac330da35cdaa00fd` is exactly one commit after design commit `5b74ee218c9863ff5279b72a1f71c545e2907123`;
- `ahead_by = 1`;
- `behind_by = 0`;
- merge base is the exact design commit;
- implementation changed exactly two paths, both additions:
  1. `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation-2.md`;
  2. `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`.

No Migration-050 file, production source, test, database, sidecar, external application artifact, or unrelated document entered the implementation commit.

The authorization change is an addition at the exact audited path. It is not a rename, move, replacement, or copied destination.

## 5. Committed authorization blob proof

Remote Git identifies the committed authorization blob as:

`36f11811b76c9a1f7121f08592642ff984384036`

The implementation record establishes the following exact identity across all stages:

| Stage | Git object ID | Size | SHA-256 |
| --- | --- | ---: | --- |
| Raw worktree, no filters | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Staged | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Committed | `36f11811b76c9a1f7121f08592642ff984384036` | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |
| Worktree after commit | same bytes | `8019` | `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60` |

Remote blob retrieval independently confirms that object `36f11811b76c9a1f7121f08592642ff984384036` decodes to the expected final-authorization JSON and preserves the exact authorization identity and policy described below.

Git stage mode `100644` is correct. The implementation intentionally preserved the worktree file's non-executable read-only incident mode and did not chmod the evidence. Git does not encode the full POSIX `0444` permission; historical integrity is based on exact path, exact blob bytes, application binding, and one-shot consumption truth.

## 6. Authorization schema and one-shot truth

The committed authorization JSON preserves:

| Field | Value |
| --- | --- |
| Schema | `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Authorized branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| Authorized HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |
| Migration execution | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Mode | `run` |
| Operator approved | `true` |
| Invocation count | `1` |
| Main window | `WINDOW_15M` |
| Token capacity | `2` |
| Total duration | `1200` seconds |
| Automatic retries | `0` |
| Selective 1h continuation | `false` |
| Provider rotation | `false` |
| Source owner | `SOURCE_GOVERNOR` |
| Scheduler owner | `CENTRAL_SCHEDULER` |
| Support-only window | `WINDOW_5M_MICRO_EVENT` |

The following remain false:

- automatic retry;
- manual rerun;
- resume;
- restart;
- successor.

The external create-once marker recorded consumption at
`2026-08-02T11:34:17.389120+00:00` and binds the same authorization SHA-256. The canonical external application directory exists. Historical classification therefore cannot restore or reuse the authorization.

The authorization remains permanently consumed and non-reusable.

## 7. Namespace proof

The implementation's committed pre/post inventory is:

| Set | Before | After | Required after |
| --- | ---: | ---: | ---: |
| Tracked historical `T` | `18` | `19` | `19` |
| Visible current | `11` | `10` | `10` |
| Ignored current | `2` | `2` | `2` |
| Current evidence `M` | `13` | `12` | `12` |
| Complete inventory `F` | `31` | `31` | `31` |

The required relationships hold:

```text
F == T union M
T intersect M == empty
M == visible-current union ignored-current
```

The authorization moved only by Git classification:

```text
same path + same bytes
untracked current evidence -> tracked immutable historical evidence
```

The final untracked root is the retained Migration-050 package only.

## 8. Migration-050 preservation

The implementation record confirms after commit:

- file count: `12`;
- symlink count: `0`;
- non-regular entries: `0`;
- sorted identity-listing SHA-256:
  `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`;
- tracked Migration-050 files: `0`;
- two `.sqlite3` evidence files remain ignored;
- no Migration-050 file entered the implementation commit;
- Migration 050 was not invoked again.

The migration package remains the exact bounded current evidence set needed by later fresh readiness and authorization review.

## 9. Authoritative database preservation

The implementation used stat/hash only and did not open SQLite.

Before and after identity:

| Field | Value |
| --- | --- |
| Path | `data/printer_v1.sqlite3` |
| Size | `65671168` bytes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL | absent |
| SHM | absent |
| Journal | absent |

The implementation report records exact before/after equality. The proof lane did not open or mutate the database.

## 10. External application preservation

The consumed external application remains at:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Its preserved inventory is:

- `application-marker.json`;
- `child-stderr.txt`;
- `child-stdout.txt`;
- `git-provenance-manifest.json`;
- `wrapper-terminal.json`;
- one historical empty staging directory under the application parent.

Complete application-parent sorted file-hash-listing SHA-256:

`f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`

The implementation report records exact before/after equality. No external application or staging artifact was moved, rewritten, deleted, or added to Git.

## 11. Protected capability counters

For both implementation and this bounded proof:

| Capability | Count |
| --- | ---: |
| Wrapper application | `0` |
| Operational command | `0` |
| Manifest creation | `0` |
| Marker creation | `0` |
| Authorization creation | `0` |
| Provider/source access | `0` |
| Source Governor runtime | `0` |
| Central Scheduler runtime | `0` |
| Discovery/campaign | `0` |
| SQLite opens or mutations | `0` |
| Memory generation | `0` |
| Retrieval/decisions | `0` |
| BUY/SELL/HOLD | `0` |
| Positions/trades/audits/PnL | `0` |
| Migration-050 reruns | `0` |
| Production/test edits | `0` |
| Broad suites | `0` |

This proof is evidence classification verification only.

## 12. Proof sufficiency and limitation

The proof is sufficient for the exact rollover claim because:

- remote Git independently confirms exact ancestry and exact two-path scope;
- remote Git independently confirms the same-path authorization addition and exact committed blob object;
- remote blob inspection confirms the committed JSON identity and safety policy;
- the committed implementation report records the local raw/staged/committed/worktree byte equality and all required pre/post filesystem identities;
- the user's immediate post-commit and push output confirms exact branch/HEAD and only the Migration-050 root remains untracked;
- no later step modified evidence or runtime state.

This proof does not claim a fresh independent Mac filesystem rerun after push. The local preservation evidence is the implementation's committed reconciliation record plus the user's final status output. That is sufficient for this documentation-only bounded proof because the remote push did not itself change repository worktree evidence, the authoritative DB, or the external application.

Independent closeout remains required before fresh authoritative readiness.

## 13. Money-usefulness contribution

The rollover removes a namespace blocker that would otherwise risk wasting another scarce one-shot authorization before useful market collection begins.

It preserves the failed authorization as immutable history while retaining Migration-050 as the only current evidence package. It creates no market evidence, memory, decision, trade, or profit claim.

## 14. What this proof improves

- proves the exact consumed package is now immutable tracked history;
- proves the transition used the same path and same blob bytes;
- proves the current namespace returned to one bounded Migration-050 package;
- protects the external application and database evidence;
- preserves one-shot non-reuse truth;
- provides a clean handoff to independent closeout.

## 15. What remains locked

This proof does not unlock:

- fresh authoritative readiness;
- a fresh authorization;
- manifest or marker creation;
- wrapper application;
- provider/source access;
- Source Governor or Central Scheduler runtime;
- discovery or campaign execution;
- authoritative SQLite mutation;
- memory generation or retrieval;
- paper decisions or BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- wallets, private keys, real funds, live execution, or paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana-memecoin-only, and paper-only.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Proof disposition |
| --- | --- |
| Authorization bytes transformed by Git | Closed: raw/staged/committed object identity is exact |
| Authorization path moved or renamed | Closed: remote diff shows same-path addition |
| Migration-050 accidentally tracked | Closed: exact commit scope excludes it; implementation inventory records zero tracked Migration files |
| Historical classification mistaken for reuse | Closed: consumption marker and canonical application remain binding and non-reusable |
| DB or external application changed | No drift recorded by implementation; proof did not touch them |
| Remote proof mistaken for a second Mac execution | Explicitly bounded; no second local mutation/runtime is claimed |
| Fresh readiness assumed automatically | Prevented; independent closeout and a new readiness audit remain required |
| Windows symlink-test portability | Separate interpreter-test risk; unrelated to this evidence rollover and not broadened here |

## 17. Roadmap decision

- implementation commit accepted: `true`;
- bounded proof passed: `true`;
- evidence rollover section closed: `false`;
- independent closeout required: `true`;
- fresh readiness authorized: `false`;
- fresh authorization authorized: `false`;
- wrapper application or campaign authorized: `false`.

## 18. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Independent Closeout 2`

Stop after this proof report. Do not begin fresh readiness, authorization, wrapper application, or runtime in this lane.
