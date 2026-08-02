# Printer V1 V2-9.8B WINDOW_15M Fresh Authoritative Readiness Audit

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Fresh Authoritative Readiness Audit`

Lane type: audit/readiness only.

## 1. Verdict

`V2_9_8B_WINDOW_15M_FRESH_AUTHORITATIVE_READINESS_AUDIT_PASS`

The post-rollover repository and retained Migration-050 package are ready for a separate fresh exact-HEAD final-authorization lane.

This audit does not create an authorization package, manifest, marker, or application record. It does not authorize the wrapper application or the real `WINDOW_15M` command.

No SQLite connection, provider/source request, Source Governor runtime, Central Scheduler runtime, campaign, child process, memory, retrieval, decision, position, trade, audit, or PnL capability ran.

## 2. Controlling source stack

- `AGENTS.md`: `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e`
- `docs/printer-v1-clean-master-spec.md`: `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657`
- `docs/printer-v1-post-rc-build-order.md`: `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2`
- `docs/printer-v1-memory-factory-guide.md`: `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d`
- `docs/printer-v1-current-state-memory-growth-audit.md`: `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81`
- `docs/printer-v1-memory-growth-build-order-v2.md`: `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order inside this stack and is not the sole source of truth.

## 3. Exact baseline

| Item | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-window-15m-fresh-authoritative-readiness-audit` |
| Inspected HEAD | `0025f33eefe25ca561b978c0b613320c74925940` |
| Rollover closeout | `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-independent-closeout.md` |
| Retained migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Consumed historical authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Consumed authorization HEAD | `ffb7e4581833ee4ee77763a2bfcff0c98f8087a1` |
| Current authorization package files | `0` |

The fresh authorization must bind the readiness-audit commit created by this lane, not the older inspected baseline or the consumed authorization HEAD.

## 4. Retained Migration-050 readiness

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

All twelve files:

- remain at their exact audited paths;
- remain untracked current evidence;
- have unchanged sizes and SHA-256 values;
- contain no symlink or non-regular entry;
- include two ignored `.sqlite3` evidence files that were hashed as regular files and never opened through SQLite.

A future final authorization must bind exactly:

`V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

No new Migration-050 run is authorized or required by this PASS.

## 5. Namespace readiness

| Set | Count |
| --- | ---: |
| Tracked historical | 18 |
| Visible current | 10 |
| Ignored current | 2 |
| Current evidence | 12 |
| Complete inventory | 30 |
| Current authorization files | 0 |

- `F == T union M`: `true`;
- `T intersect M == empty`: `true`;
- `M == visible union ignored`: `true`;
- no tracked file exists inside the current migration package;
- no untracked current authorization package exists.

The namespace is therefore clear for one distinct future authorization package.

## 6. Historical authorization non-reuse proof

| Field | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Authorized HEAD | `ffb7e4581833ee4ee77763a2bfcff0c98f8087a1` |
| Consumed | `true` |
| Allowed invocation count | `1` |
| Reusable | `false` |
| New authorization ID required | `true` |

Historical files:

| Path | Bytes | SHA-256 |
| --- | ---: | --- |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json` | 1062 | `8a41c49c5779915df95c03944cd7cb01f95d86ae9d54f7bed5eea036648d9fb3` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json` | 714 | `c39d6db10b33c982424db10831671441c85e71ea0604bd6e9ea0506f051c8290` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt` | 408 | `2147f56be47b8347d347dec71af075a4d2573ba322d709cfbdf2428493c88508` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` | 6772 | `b90dec9584a258314ed2a20a5a2b14c21608c0f90eb22da57f5b26db4adeba47` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json` | 80508 | `7d9bca953be6976221796d1d441f3edf61704cc6fc036eeef020fdbf7ec6e17f` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json` | 79775 | `38d0958ea0d7212f07bf630e9c0e71c3c3b945e5ae04a5bc98eca2092c94d23a` |

The old authorization remains tracked history. It cannot be reused, resumed, restarted, rerun, or issued again.

## 7. Accepted wrapper and guard identities

| File | SHA-256 |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `77e35c14860e3aae02f570e18773a8c7edb2f76e71d3772adb0ec58ef57d37c6` |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `87a1b970ac6dac4bee8b43cc392b5c4e54feb1f06e606b1cc34c1ea29699780b` |

Static inspection also confirms:

- one canonical Python one-shot wrapper;
- exactly one `subprocess.Popen` child-launch call site;
- `shell=False`;
- pre-marker and complete post-marker validation;
- complete four-value manifest/marker binding;
- manifest compatibility only for `preflight-only` and ordinary `run`;
- exact tracked-history/current-manifest inventory reconciliation;
- tracked files rejected inside current evidence packages;
- thin PowerShell launcher requires authorization file, SHA-256, and operator approval;
- PowerShell launcher invokes the wrapper and does not bypass it.

No source code or tests were executed or changed.

## 8. Authoritative DB readiness

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | 65671168 |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | 1785617072867102156 |
| WAL | absent |
| SHM | absent |
| Journal | absent |

The DB was hashed as a regular file and never opened through SQLite.

## 9. Fresh final-authorization contract

The next lane may create exactly one new current authorization package only if it:

1. uses a new authorization ID different from `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`;
2. binds the exact readiness-audit commit and branch;
3. binds migration execution ID `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`;
4. records the exact twelve retained migration file identities;
5. authorizes exactly one ordinary `run` invocation with explicit operator approval;
6. sets automatic retry, manual rerun, resume, restart, and successor to `false`;
7. sets main window to `WINDOW_15M`;
8. sets selective 1h continuation to `false`;
9. preserves `WINDOW_5M_MICRO_EVENT` as support-only;
10. creates no manifest, marker, wrapper application, provider call, Scheduler run, campaign, DB mutation, memory, retrieval, or trading action.

The authorization package must be independently reviewed before wrapper application.

## 10. Money-usefulness contribution

This readiness audit confirms that valid Migration-050 evidence can be reused safely and that the consumed authorization no longer occupies the current namespace.

It reduces the risk of losing another scarce one-shot authorization to stale Git identity, evidence drift, namespace collision, or wrapper bypass.

It creates no memory, market signal, decision, trade, or profit claim.

## 11. What this audit improves

- confirms post-rollover readiness at the exact closeout baseline;
- preserves the existing migration package without rerun;
- proves the old authorization is consumed and non-reusable;
- confirms no current authorization package exists;
- verifies accepted wrapper and direct-run guard identities;
- defines the exact fresh authorization boundary.

## 12. What remains locked

- wrapper application;
- manifest and marker creation;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- authoritative SQLite access or mutation;
- memory generation and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 13. Proof/test required before the real command

Before wrapper application:

- the fresh authorization package must receive an independent exact-scope review;
- its authorization ID must be new;
- its branch and HEAD must equal the post-readiness authorization baseline;
- the retained twelve-file migration package must be revalidated;
- repository namespace must reconcile with tracked history plus both current packages;
- the authorization SHA-256 must be recorded exactly;
- no manifest or marker may exist before the wrapper creates them;
- the wrapper command must be issued exactly once by the operator.

No broad regression suite is required because this audit changes no production source.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Readiness disposition |
| --- | --- |
| This audit commit changes HEAD | Final authorization must bind the post-audit exact HEAD |
| Migration evidence may drift after PASS | Any drift blocks authorization or application |
| Fresh authorization package does not yet exist | Correct; next lane creates and reviews it |
| Old authorization remains visible in Git history | Correct and required for honest evidence |
| Wrapper application could consume authorization on preflight failure | Final authorization and one-shot command must use the accepted wrapper contract |
| DB integrity was not queried | Correct; SQLite opening is forbidden in this readiness lane |

## 15. Roadmap decision

- rollover section closed: `true`;
- fresh readiness passed: `true`;
- fresh exact-HEAD final-authorization lane authorized: `true`;
- wrapper application authorized: `false`;
- campaign authorized: `false`;
- real `WINDOW_15M` command authorized: `false`.

## 16. Exact next lane

`V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization`
