# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Readiness Audit

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Readiness Audit`

Lane type: audit-only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_READINESS_AUDIT_PASS`

The current evidence namespace is ready for a narrowly designed historical rollover.

The safest minimal transition is to preserve the consumed authorization package **in place** as tracked historical evidence while retaining the unchanged Migration-050 package as current untracked evidence only under an exact future revalidation contract.

No evidence was staged, tracked, moved, renamed, deleted, or rewritten during this audit.

## 2. Exact baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-window-15m-current-evidence-historical-rollover-readiness-audit` |
| HEAD | `69bf8e1153cef39a1ddc5b6d95febda1d184461d` |
| Migration package | `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Consumed authorization package | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Final authorization document | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Authorization branch | `agent/v2-9-8b-post-migration-window-15m-final-authorization` |
| Authorization HEAD | `ffb7e4581833ee4ee77763a2bfcff0c98f8087a1` |
| Authorization verdict | `V2_9_8B_POST_MIGRATION_AUTHORITATIVE_WINDOW_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS` |

The authorization HEAD differs from the current repository HEAD. The consumed authorization is therefore not exact-HEAD reusable even apart from its already-consumed status.

## 3. Current namespace reconstruction

| Set | Count |
| --- | ---: |
| Tracked historical `T` | 11 |
| Visible current untracked | 17 |
| Ignored current untracked | 2 |
| Current evidence `M` | 19 |
| Complete `operator-runs/` inventory `F` | 30 |
| Migration package files | 12 |
| Authorization package files | 7 |

Reconciliation:

- `F == T union M`: `true`;
- `T intersect M == empty`: `true`;
- `M == visible union ignored`: `true`;
- visible and ignored classifications are disjoint;
- all evidence entries are regular files with no symlink components;
- extension profile: `.json`=13, `.sqlite3`=2, `.txt`=4.

## 4. Exact current evidence inventory

| Path | Class | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json` | `CURRENT_VISIBLE_MIGRATION` | 50133 | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt` | `CURRENT_VISIBLE_MIGRATION` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt` | `CURRENT_VISIBLE_MIGRATION` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json` | `CURRENT_VISIBLE_MIGRATION` | 13836 | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json` | `CURRENT_VISIBLE_MIGRATION` | 2384 | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3` | `CURRENT_IGNORED_MIGRATION` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json` | `CURRENT_VISIBLE_MIGRATION` | 6589 | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json` | `CURRENT_VISIBLE_MIGRATION` | 103903 | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json` | `CURRENT_VISIBLE_MIGRATION` | 36274 | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json` | `CURRENT_VISIBLE_MIGRATION` | 18590 | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json` | `CURRENT_VISIBLE_MIGRATION` | 16244 | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3` | `CURRENT_IGNORED_MIGRATION` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 1062 | `8a41c49c5779915df95c03944cd7cb01f95d86ae9d54f7bed5eea036648d9fb3` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 714 | `c39d6db10b33c982424db10831671441c85e71ea0604bd6e9ea0506f051c8290` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 408 | `2147f56be47b8347d347dec71af075a4d2573ba322d709cfbdf2428493c88508` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 6772 | `b90dec9584a258314ed2a20a5a2b14c21608c0f90eb22da57f5b26db4adeba47` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 80508 | `7d9bca953be6976221796d1d441f3edf61704cc6fc036eeef020fdbf7ec6e17f` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json` | `CONSUMED_AUTHORIZATION_HISTORICAL_ONLY` | 79775 | `38d0958ea0d7212f07bf630e9c0e71c3c3b945e5ae04a5bc98eca2092c94d23a` |

## 5. Package classification

### 5.1 Consumed authorization package

Classification: `HISTORICAL_ONLY_REQUIRES_TRACKED_IN_PLACE_ROLLOVER`.

Reasons:

- the wrapper closeout explicitly records the package as consumed current evidence;
- the authorization permits exactly one invocation;
- retry, rerun, resume, restart, and successor are all false;
- its authorized HEAD is historical and does not equal current HEAD;
- reusing the same authorization ID for a fresh application is forbidden;
- deleting, rewriting, renaming, or silently relocating it would weaken the evidence chain.

The future rollover implementation should add exactly these 7 existing files to Git at their current paths. It should not modify their bytes or directory names.

### 5.2 Migration-050 package

Classification: `CONDITIONALLY_RETAINABLE_AS_CURRENT`.

The package may remain current untracked evidence only if all of the following are later proven again:

1. a fresh final authorization binds the exact migration execution ID `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`;
2. every retained migration file has the same path, size, and SHA-256 recorded here;
3. the fresh readiness audit proves no tracked file exists inside the retained current migration root;
4. the complete future inventory still satisfies `F == T union M`;
5. no new Migration-050 run is executed;
6. no database or evidence mutation occurs between readiness and one-shot application.

If any condition fails, the migration package must also become historical and a separately approved fresh migration package must be produced. This audit does not authorize either mutation path.

## 6. Minimal transition model

Recommended design target:

- track the consumed authorization package in place;
- keep the Migration-050 package untracked and unchanged;
- require a new authorization ID;
- bind the exact existing migration execution ID;
- rerun fresh authoritative readiness after the rollover commit;
- issue a fresh exact-HEAD authorization only after readiness passes.

Predicted post-rollover/pre-fresh-authorization shape:

| Set | Predicted count |
| --- | ---: |
| Tracked historical | 18 |
| Retained current migration evidence | 12 |
| Fresh authorization evidence | 0 until separately created |

A future fresh authorization package will add a new current authorization root. Its ID must differ from `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`.

## 7. Why tracking in place is preferred

Tracking the consumed package at its existing path preserves:

- exact filenames and directory identity;
- existing content hashes;
- chronological evidence context;
- compatibility with the validator's tracked-history inventory;
- a clean distinction between the old authorization ID and a future new current authorization ID.

Moving or renaming the package would create unnecessary identity drift. Deleting it would break historical completeness. Leaving it untracked blocks a fresh current authorization package.

## 8. Money-usefulness contribution

This audit identifies the shortest safe route to the real 15-minute operator command.

It avoids rebuilding valid Migration-050 evidence unnecessarily while ensuring the consumed authorization cannot contaminate or block the next exact-HEAD authorization.

It creates no memory, market signal, decision, trade, or profit claim.

## 9. What this audit improves

- exact current-vs-historical package classification;
- a minimal rollover target;
- explicit conditions for Migration-050 retention;
- exact file-level hashes for future proof;
- a no-move/no-delete/no-rewrite historical preservation rule;
- a clear route back to fresh readiness.

## 10. What remains locked

- staging or committing the authorization package;
- any evidence mutation;
- fresh readiness;
- fresh manifest or marker;
- fresh authorization;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- authoritative SQLite access or mutation;
- memory generation and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, live execution, and paid APIs.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 11. Proof/test required before rollover completion

The later rollover section must preserve the standard sequence:

1. design/specification;
2. narrow implementation;
3. bounded proof;
4. independent closeout;
5. fresh authoritative readiness.

Minimum proof must establish:

- only the exact consumed authorization package files became tracked;
- their paths, sizes, and hashes are unchanged;
- Migration-050 remains untracked and byte-identical if retained;
- no extra visible or ignored evidence exists;
- no authoritative DB byte, size, `mtime_ns`, or sidecar change;
- no provider, Scheduler, campaign, memory, retrieval, or trading action;
- future namespace arithmetic remains compatible with `F == T union M`.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Audit disposition |
| --- | --- |
| Future Git tracking changes HEAD | Expected; fresh readiness and authorization must bind the new HEAD |
| Migration retention could hide later mutation | Exact file hashes and fresh readiness are mandatory |
| New authorization accidentally reuses consumed ID | Design must require a distinct authorization ID |
| Tracking broader `operator-runs/` scope captures current migration | Implementation must stage an exact authorization-package allowlist only |
| Git attributes or filters could transform evidence bytes | Design/proof must compare worktree bytes, index blobs, and committed blobs |
| Evidence changes between rollover and readiness | Any drift blocks and requires re-audit |
| Fresh authorization package may have a different file count | Allowed only if its own readiness manifest exactly accounts for it |

## 13. Roadmap decision

The audit passes readiness for design only.

It does not authorize evidence tracking. It does not authorize fresh readiness, authorization, or a campaign.

## 14. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Design`

The design must specify exact paths, index/blob preservation checks, commit scope, rollback behavior before commit, and the proof needed before the rollover can close.
