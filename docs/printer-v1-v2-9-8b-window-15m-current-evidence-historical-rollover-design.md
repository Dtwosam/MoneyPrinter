# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design`

Lane type: design/specification only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_DESIGN_PASS`

The historical rollover is approved for a narrow implementation that tracks exactly seven consumed authorization files in place while preserving all evidence bytes and retaining the twelve-file Migration-050 package as current untracked evidence.

This design does not itself authorize staging, tracking, fresh readiness, fresh authorization, or a campaign.

## 2. Controlling source stack

- `AGENTS.md`: `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e`
- `docs/printer-v1-clean-master-spec.md`: `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657`
- `docs/printer-v1-post-rc-build-order.md`: `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2`
- `docs/printer-v1-memory-factory-guide.md`: `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d`
- `docs/printer-v1-current-state-memory-growth-audit.md`: `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81`
- `docs/printer-v1-memory-growth-build-order-v2.md`: `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this source stack and is not the sole source of truth.

## 3. Audit baseline

- readiness audit commit: `b07bd1715d052df2d4faf5b051b5c54484d3ad64`;
- readiness verdict: `V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_READINESS_AUDIT_PASS`;
- consumed authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`;
- retained migration execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`;
- pre-rollover namespace: `T=11`, visible current `=17`, ignored current `=2`, `M=19`, `F=30`;
- target pre-fresh-authorization namespace: `T=18`, visible current `=10`, ignored current `=2`, `M=12`, `F=30`.

The implementation must start from this design commit and must fail closed if any evidence path, size, SHA-256, Git classification, DB identity, branch, or HEAD has drifted.

## 4. Exact implementation scope

### 4.1 Track in place

The implementation may add exactly these seven paths to Git:

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json` | 1062 | `8a41c49c5779915df95c03944cd7cb01f95d86ae9d54f7bed5eea036648d9fb3` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json` | 714 | `c39d6db10b33c982424db10831671441c85e71ea0604bd6e9ea0506f051c8290` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt` | 408 | `2147f56be47b8347d347dec71af075a4d2573ba322d709cfbdf2428493c88508` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` | 6772 | `b90dec9584a258314ed2a20a5a2b14c21608c0f90eb22da57f5b26db4adeba47` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json` | 80508 | `7d9bca953be6976221796d1d441f3edf61704cc6fc036eeef020fdbf7ec6e17f` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json` | 79775 | `38d0958ea0d7212f07bf630e9c0e71c3c3b945e5ae04a5bc98eca2092c94d23a` |

No path may be moved, renamed, deleted, rewritten, chmod-expanded, or replaced by a symlink.

### 4.2 Retain as current untracked evidence

The following twelve files must remain byte-identical and untracked:

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json` | 50133 | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json` | 13836 | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json` | 2384 | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json` | 6589 | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json` | 103903 | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json` | 36274 | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json` | 18590 | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json` | 16244 | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

The two `.sqlite3` files remain ignored evidence. They must never be opened through SQLite in this section.

### 4.3 Implementation report

The implementation commit may additionally add only:

`docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation.md`

Therefore, the implementation commit scope is exactly eight files: seven historical evidence files plus one implementation report.

## 5. Byte-preserving index design

The implementation must not use a broad command such as:

- `git add operator-runs/`;
- `git add -A`;
- `git add .`.

It must use the exact seven-path allowlist.

For every authorization path, immediately before staging:

1. verify regular-file identity and reject symlinks;
2. verify audited path, size, and SHA-256;
3. compute the expected Git blob object ID from raw worktree bytes using `git hash-object --no-filters`;
4. inspect Git attributes and record any `filter`, `text`, `eol`, or `working-tree-encoding` behavior;
5. stage only the exact path;
6. read the stage-0 index entry with `git ls-files --stage`;
7. read the staged blob using `git cat-file blob`;
8. prove staged blob size and SHA-256 equal the audited worktree bytes;
9. prove the index mode is `100644`;
10. prove all seven entries are additions and no unrelated path entered the index.

A normal exact-path `git add -- <seven paths>` is allowed only if every staged blob passes the raw-byte identity checks. If any attribute or filter changes bytes, the helper must unstage all seven paths and stop. It must not silently normalize or replace evidence.

Current read-only attribute observations:

| Path | Attributes |
| --- | --- |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json` | `<none>` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json` | `<none>` |

These observations are informational only. The implementation must repeat them at its own exact HEAD.

## 6. Pre-commit transaction and rollback

Before staging, the implementation must capture:

- branch and exact HEAD;
- tracked worktree/index cleanliness;
- full authorization and migration filesystem snapshots;
- authoritative DB and sidecar identities;
- visible, ignored, tracked, and full `operator-runs/` inventories;
- exact seven- and twelve-file hashes.

Before commit, any failure must trigger:

1. `git restore --staged -- <exact seven authorization paths> <implementation report>`;
2. removal of the untracked implementation report only;
3. verification that both evidence packages and DB snapshot still equal the baseline;
4. verification that repository status returned to the original two untracked evidence directories.

Rollback must never remove, rewrite, reset, checkout, clean, or restore an evidence worktree file.

After a successful commit, automatic reset, amend, or rollback is forbidden. A post-commit verification failure must return a blocked verdict and preserve the commit for independent inspection.

## 7. Exact commit contract

Commit message:

`Implement current evidence historical rollover`

The commit must include exactly:

- seven audited authorization evidence files;
- one implementation report.

The commit must not include:

- any Migration-050 file;
- any source code;
- any other documentation;
- database files or sidecars;
- generated caches or logs.

Expected post-commit status:

```text
?? operator-runs/v2-9-8b-authoritative-mig050/
```

Expected post-commit namespace:

- tracked historical `T=18`;
- visible current `=10`;
- ignored current `=2`;
- current manifest candidate `M=12`;
- complete inventory `F=30`;
- `F == T union M`;
- `T intersect M == empty`;
- `M == visible union ignored`.

## 8. Implementation-time checks

Minimum sufficient checks:

- exact baseline branch and HEAD;
- exact seven-path authorization allowlist;
- exact twelve-path migration allowlist;
- file sizes and SHA-256 values;
- no symlinks or non-regular entries;
- tracked tree and index clean before staging;
- raw worktree bytes equal staged blobs;
- exact stage-0 modes and object IDs;
- exact eight-file commit scope;
- committed blobs equal audited bytes;
- Migration-050 remains untracked and byte-identical;
- authoritative DB and sidecars unchanged;
- no provider, Scheduler, campaign, memory, retrieval, or trading call.

No broad regression suite is required because this is a Git/evidence transition with no production-code change.

## 9. Bounded proof design

The next proof must be read-only with respect to evidence and DB.

It must independently verify:

1. implementation commit descends from this design commit;
2. the implementation commit contains exactly seven evidence files and one report;
3. each committed evidence blob has the audited size and SHA-256;
4. each worktree evidence file matches its committed blob;
5. all seven paths remain in place;
6. all twelve Migration-050 files remain untracked and byte-identical;
7. post-rollover namespace is `T=18`, visible `=10`, ignored `=2`, `M=12`, `F=30`;
8. authoritative DB bytes, size, `mtime_ns`, and sidecar state match the implementation baseline;
9. zero protected capabilities executed.

The proof may create and commit one proof report only.

## 10. Independent closeout design

Independent closeout must review:

- audit, design, implementation, and proof ancestry;
- exact commit scopes;
- file/blob identities;
- transaction rollback contract;
- current namespace arithmetic;
- Migration-050 retention conditions;
- DB preservation;
- zero protected-capability execution.

Only after closeout passes may fresh authoritative readiness begin.

## 11. Fresh-readiness boundary

The rollover does not authorize the real 15-minute command.

After rollover closeout, fresh readiness must prove:

- the retained migration execution ID is exactly `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`;
- all twelve migration paths and hashes remain unchanged;
- a new authorization ID will be used;
- the fresh authorization binds the then-current exact HEAD;
- no tracked file exists inside the retained migration root;
- the future current package inventory reconciles exactly;
- no evidence or DB drift occurs before one-shot application.

## 12. Money-usefulness contribution

This design defines the shortest safe transition toward the real `WINDOW_15M` command without repeating Migration-050 unnecessarily.

It protects scarce one-shot authorization value by preserving historical evidence and preventing accidental staging of the retained current migration package.

It creates no memory, market signal, paper decision, trade, or profit claim.

## 13. What this design improves

- exact seven-file mutation boundary;
- byte-preserving index and commit verification;
- deterministic pre-commit rollback;
- no broad `git add` exposure;
- explicit proof and closeout contracts;
- preservation of reusable Migration-050 evidence;
- a direct route to fresh readiness.

## 14. What remains locked

- evidence tracking until the implementation lane;
- fresh readiness and fresh authorization;
- manifest and marker creation;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- authoritative SQLite access or mutation;
- memory and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Design control |
| --- | --- |
| Broad staging captures Migration-050 | Exact seven-path allowlist; broad add commands forbidden |
| Git filters normalize evidence | Compare raw worktree bytes to stage-0 blob bytes |
| Pre-commit failure leaves index dirty | Exact-path unstage and report removal only |
| Rollback accidentally touches evidence | Worktree restore/reset/clean of evidence forbidden |
| Commit changes HEAD | Fresh readiness and authorization must bind the new HEAD |
| Migration evidence drifts later | Exact twelve-file revalidation at every later gate |
| Post-commit check fails | Preserve commit; block and inspect independently |
| Proof becomes another mutation | Proof is read-only except its single report |

## 16. Roadmap decision

The design passes implementation readiness only.

It does not authorize fresh readiness, fresh authorization, or a campaign.

## 17. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Implementation`
