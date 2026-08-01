# Printer V1 V2-9.8B WINDOW_15M Repeated Post-Repair Authoritative Readiness Audit

Date: 2026-08-01

Lane:
`V2-9.8B WINDOW_15M Repeated Post-Repair Authoritative Readiness Audit`

Lane type: audit-only, read-only, documentation-only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_REPEATED_POST_REPAIR_AUTHORITATIVE_READINESS_AUDIT_BLOCKED`

The ignored-evidence visibility repair remains valid at the approved implementation, bounded-proof, and independent-closeout levels. However, the real authoritative repository is not ready for wrapper construction or a fresh one-shot authorization.

The repaired production validator correctly reconciles the intended current evidence as 17 Git-visible untracked files plus 2 Git-ignored untracked SQLite files. It then blocks because its complete filesystem inventory covers every file beneath `operator-runs/`, including 11 preserved historical files that are committed repository artifacts and are not part of the new 19-file authorization manifest.

The authoritative state is therefore:

- current manifest-shaped evidence: 19 files;
- current Git-visible untracked evidence: 17 files;
- current Git-ignored untracked evidence: 2 files;
- complete `operator-runs/` filesystem inventory: 30 files;
- additional committed historical files: 11 files;
- production reconciliation: BLOCKED.

No file was deleted, moved, renamed, ignored, rewritten, or added to the current evidence manifest. No wrapper or marker was built, no authorization was issued, no provider or source was contacted, no Source Governor or Central Scheduler runtime ran, no campaign executed, and the authoritative database was not opened through SQLite or mutated.

## 2. Controlling source stack

This audit follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of the source stack and is not treated as the sole source of truth.

The required V2 pattern remains:

`audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout report`

## 3. Starting baseline

| Item | Value |
| --- | --- |
| Audit branch | `agent/v2-9-8b-window-15m-repeated-post-repair-authoritative-readiness-audit` |
| Starting HEAD | `83b8333cbd49994a3cc9dcbb3755a229825d60d5` |
| Repair implementation commit | `32ec6467d08165637015d5775d5ba6e2180a74af` |
| Bounded-proof closeout commit | `21ea24d5e2ae53b7d689c2acd97a94688f58d9c0` |
| Independent closeout commit | `83b8333cbd49994a3cc9dcbb3755a229825d60d5` |
| Independent closeout verdict | `V2_9_8B_WINDOW_15M_AUTHORITATIVE_IGNORED_EVIDENCE_VISIBILITY_REPAIR_INDEPENDENT_CLOSEOUT_PASS` |

The implementation, proof, and independent-closeout commits were all confirmed as ancestors of the audit HEAD.

## 4. External audit record identity

The operator supplied the immutable read-only audit record:

`V2_9_8B_WINDOW_15M_REPEATED_AUTHORITATIVE_READINESS_20260801T233327Z`

Recorded local path:

`/Users/Dtwo1/PrinterOperations/v2-9-8/repeated-post-repair-authoritative-readiness-audit/V2_9_8B_WINDOW_15M_REPEATED_AUTHORITATIVE_READINESS_20260801T233327Z/authoritative_readiness_audit_record.json`

Independent file identity:

- SHA-256: `cb30508343924a28a8f8f1015fc91b66f3cd596c3853b466d069aa8d0e574bd6`
- size: `28116` bytes
- schema: `PRINTER_V1_V2_9_8B_REPEATED_AUTHORITATIVE_READINESS_AUDIT_V1`
- record verdict: `V2_9_8B_WINDOW_15M_REPEATED_POST_REPAIR_AUTHORITATIVE_READINESS_AUDIT_BLOCKED`

The prior bounded disposable-proof record also remained present and unchanged:

- SHA-256: `33d2e42b640fd8cbef77af215491efc653bbf0c0ef6d6daf885770da8cf36705`
- size: `172156` bytes.

## 5. Exact authoritative reconciliation result

The repaired validator reported:

| Set | Count | Result |
| --- | ---: | --- |
| Manifest set | 19 | expected |
| Git-visible untracked set | 17 | exactly expected |
| Scoped Git-ignored untracked set | 2 | exactly expected |
| Complete `operator-runs/` inventory | 30 | 11 more than manifest |

The 17 visible plus 2 ignored paths are exactly the intended 19-file current evidence package.

The two ignored paths remain:

1. `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3`
2. `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3`

The intended 19 files match the earlier bounded-proof baseline exactly by path, size, SHA-256, and `mtime_ns`. They did not drift.

The audit record's broad field `content_hash_size_matches_proof: false` is caused by comparing the complete 30-file inventory with the earlier 19-file baseline. It must not be interpreted as modification of the intended 19 files.

## 6. The 11 additional historical files

The complete inventory includes these 11 files outside the current authorization packages:

1. `operator-runs/v2-9-7e-5-live-proof/V2_9_7E_5_LIVE_PROOF_RESULT.json`
2. `operator-runs/v2-9-7e-5-live-proof/run_v2_9_7e_5_live_proof.py`
3. `operator-runs/v2-9-7e-5a-decisive-reproof/V2_9_7E_5A_DECISIVE_REPROOF_RESULT.json`
4. `operator-runs/v2-9-7e-5a-decisive-reproof/run_v2_9_7e_5a_decisive_reproof.py`
5. `operator-runs/v2-9-7e-6-classification/V2_9_7E_6_CLASSIFICATION_RESULT.json`
6. `operator-runs/v2-9-7e-6-classification/run_v2_9_7e_6_classification_capture.py`
7. `operator-runs/v2-9-7e-6-final-proof/V2_9_7E_6_FINAL_PROOF_RESULT.json`
8. `operator-runs/v2-9-7e-6-final-proof/run_v2_9_7e_6_final_proof.py`
9. `operator-runs/v2-9-8b-mig050-bounded-proof/CONTROLLING_EXECUTION`
10. `operator-runs/v2-9-8b-mig050-bounded-proof/V2_9_8B_MIG050_BOUNDED_PROOF_20260801T144740Z_5df7a275/proof_summary.json`
11. `operator-runs/v2-9-8b-mig050-bounded-proof/proof_summary.json`

These are not additional current untracked evidence. The Git-visible and Git-ignored untracked sets already account for all 19 current files. The remaining 11 are preserved committed historical artifacts under `operator-runs/`; representative files from every historical root are present in the current Git tree.

They must not be deleted, relocated, ignored, or inserted into the current authorization manifest merely to satisfy readiness.

## 7. Root cause

The approved repair introduced the following central invariant:

`F == M`

Where:

- `F` is every regular file beneath repository `operator-runs/`;
- `M` is every file in the current authorization manifest.

That invariant correctly detects extra untracked or ignored evidence. It is too broad for the real repository because `operator-runs/` is also a committed historical artifact namespace.

The current production validator does not distinguish:

1. committed historical `operator-runs/` baseline files;
2. current manifest-bound visible untracked evidence;
3. current manifest-bound ignored untracked evidence;
4. unexpected new untracked or ignored files.

As a result, preserved historical files block through:

`unexpected operator-runs filesystem file not covered by manifest`

This is a real authoritative-environment compatibility blocker. It does not invalidate the repair's focused tests or bounded proof; those proofs did not reproduce a repository containing committed historical files beneath `operator-runs/`.

## 8. Rejected shortcuts

The following remain prohibited:

- deleting or moving the 11 historical files;
- deleting or moving the intended 19 files;
- adding the historical files to the current authorization manifest;
- changing `.gitignore`, `.git/info/exclude`, or global Git configuration;
- broadly exempting `operator-runs/`;
- accepting directories or globs;
- bypassing the production validator;
- creating a marker before complete validation;
- issuing another authorization to test the blocked state;
- running a campaign before readiness passes.

## 9. Required next design problem

The next lane must design a narrow, fail-closed historical-baseline reconciliation contract.

The design must explicitly distinguish committed historical files from current untracked authorization evidence without weakening detection of unexpected files.

The design must preserve at least:

- exact current manifest paths only;
- direct package, path, size, SHA-256, regular-file, and non-symlink validation;
- exact 17-visible plus 2-ignored current evidence classification;
- detection of any additional visible or ignored untracked file anywhere relevant;
- detection of tracked-file mutation or tracked-tree dirtiness;
- no directory or glob exemption;
- no ignore-rule mutation;
- no historical evidence deletion or relocation;
- unchanged manifest and marker binding unless a later design proves a schema change is necessary;
- unchanged six-field Git-provenance payload;
- one-attempt/no-retry law;
- ordinary `WINDOW_15M` only;
- Source Governor and Central Scheduler ownership;
- all memory, retrieval, paper-decision, position, trade, audit, and PnL locks.

One possible design direction is to reconcile a separately proven tracked historical baseline with the current untracked manifest rather than requiring the current manifest to equal every tracked and untracked file beneath `operator-runs/`. This is a design question only and is not yet approved implementation.

## 10. Authoritative database invariance

The authoritative database remained exactly unchanged:

- SHA-256: `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5`
- size: `65671168` bytes
- `mtime_ns`: `1785617072867102156`
- regular file: true
- symlink: false
- `-wal`: absent
- `-shm`: absent
- `-journal`: absent
- opened through SQLite: false.

## 11. Repository and capability invariance

The tracked tree was clean before and after the audit.

All inspected implementation, test, proof, and closeout working blobs matched their committed blobs.

Every protected capability counter remained zero:

- network calls;
- provider calls;
- Source Governor calls;
- Scheduler calls;
- wrapper builds;
- marker creation;
- authorization issuance;
- campaign calls;
- database connections and writes;
- memory calls;
- retrieval calls;
- decision calls;
- position calls;
- trade calls;
- paper-trade audit calls;
- PnL calls.

## 12. Money-usefulness contribution

This audit prevents another scarce one-shot authorization from being consumed by a deterministic pre-marker failure.

It also preserves both kinds of valuable evidence:

- the intended current 19-file authorization evidence;
- the committed historical proof record under `operator-runs/`.

That improves future paper-only collection reliability without creating market signal, memory, retrieval, decisions, positions, trades, or profit claims.

## 13. What this lane improves

- proves the ignored `.sqlite3` visibility problem itself is repaired;
- confirms the intended 19 files remain exact and unchanged;
- identifies the remaining conflict as tracked historical baseline handling;
- separates current untracked authorization evidence from committed historical artifacts;
- prevents destructive cleanup or manifest inflation;
- preserves the authoritative database and all capability locks.

## 14. What remains locked

This audit does not unlock:

- historical-baseline reconciliation implementation;
- production wrapper construction;
- application marker creation;
- a fresh final authorization;
- providers, RPC, WebSockets, or source fetching;
- Source Governor or Central Scheduler runtime;
- a `WINDOW_15M` campaign;
- memory generation or promotion;
- retrieval;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL;
- wallets, private keys, signing, real funds, live execution, or paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer V1 remains Solana-only, Solana memecoin-only, and paper-only.

## 15. Proof required after a later repair

Before readiness can pass, a later approved repair sequence must include:

1. historical-baseline reconciliation design;
2. narrow implementation, if approved;
3. focused tests containing committed historical files beneath `operator-runs/`;
4. positive proof with 11 committed historical files plus the 19 current manifest files;
5. negative proof for an additional visible untracked file;
6. negative proof for an additional ignored untracked file;
7. negative proof for tracked-tree mutation;
8. proof that historical tracked files cannot become current authorized evidence automatically;
9. bounded disposable proof;
10. independent closeout;
11. repeated authoritative readiness audit;
12. only after readiness PASS, a separate fresh final authorization lane.

No campaign may run before all required steps pass.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current disposition |
| --- | --- |
| Current `F == M` treats committed history as current evidence | Confirmed authoritative blocker |
| Deleting historical files would damage audit continuity | Prohibited |
| Adding historical files to current manifest would inflate authorization scope | Prohibited |
| Broad `operator-runs/` exemption would hide unexpected evidence | Prohibited |
| Narrowing inventory to current roots could miss unexpected ignored files elsewhere | Must be solved by design |
| Tracked historical baseline could drift between authorization and launch | Must remain bound to clean Git HEAD and tracked-tree checks |
| Intended 19 files appear changed because total inventory grew | Corrected interpretation: intended 19 match exactly; 11 historical files are additional |
| Another authorization is consumed before repair | Prohibited |
| Disposable fixtures omit committed historical files | Must be corrected in later focused tests and proof |
| Scope expands into runtime or campaign work | Explicitly prohibited |

## 17. Exact next lane

`V2-9.8B WINDOW_15M Historical operator-runs Baseline Reconciliation Design`

Type: design/specification only.

The next lane may inspect the production validator, Git classifications, committed historical `operator-runs/` files, current evidence packages, and prior proof records to define a narrow fail-closed reconciliation contract.

It may not implement code, modify ignore rules, delete or move evidence, build the wrapper, create a marker, issue authorization, contact providers, run Source Governor or Central Scheduler, execute a campaign, mutate the database, generate memory, activate retrieval, or unlock paper trading.