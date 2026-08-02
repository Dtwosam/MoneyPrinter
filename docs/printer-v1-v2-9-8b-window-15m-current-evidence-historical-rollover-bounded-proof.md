# Printer V1 V2-9.8B WINDOW_15M Current Evidence Historical Rollover Bounded Proof

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Bounded Proof`

Lane type: bounded, read-only evidence/DB proof plus one proof report.

## 1. Verdict

`V2_9_8B_WINDOW_15M_CURRENT_EVIDENCE_HISTORICAL_ROLLOVER_BOUNDED_PROOF_PASS`

The historical rollover implementation is independently proven at the bounded proof layer.

Exactly seven consumed authorization files are committed as historical evidence. Exactly twelve Migration-050 files remain current untracked evidence. Their paths and bytes are unchanged.

No provider, Source Governor runtime, Central Scheduler runtime, campaign, SQLite connection, manifest, marker, authorization, memory, retrieval, decision, position, trade, audit, or PnL capability ran.

## 2. Exact chain

| Stage | Commit |
| --- | --- |
| Design | `f87fb0f1122e5a3476c49402427f99891dc0d68b` |
| Implementation | `da8e50835bf483a3fe5b5498b74aee3122034c36` |
| Bounded proof | current commit |

The implementation commit has the correct parent, message, and exact eight-file scope.

## 3. Implementation commit scope

- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-implementation.md`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json`
- `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json`

The commit contains exactly seven historical evidence files and one implementation report. It contains no Migration-050 file, source file, database, sidecar, or unrelated documentation.

## 4. Committed historical evidence proof

| Path | Bytes | SHA-256 | Blob OID | Mode |
| --- | ---: | --- | --- | --- |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/application_started.json` | 1062 | `8a41c49c5779915df95c03944cd7cb01f95d86ae9d54f7bed5eea036648d9fb3` | `c98edacb95c39899e4b643c3e4f4cbaa756f7596` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_exit.json` | 714 | `c39d6db10b33c982424db10831671441c85e71ea0604bd6e9ea0506f051c8290` | `6e239993531fff756e74768db3eff8405ae92c7d` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stderr.txt` | 408 | `2147f56be47b8347d347dec71af075a4d2573ba322d709cfbdf2428493c88508` | `264b14c6f21586fc1e94913967082d050e4b572b` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/campaign_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/final_authorization.json` | 6772 | `b90dec9584a258314ed2a20a5a2b14c21608c0f90eb22da57f5b26db4adeba47` | `428bf69465673b9dea5b93c6164c8b83db76a3dd` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/pre_run_evidence.json` | 80508 | `7d9bca953be6976221796d1d441f3edf61704cc6fc036eeef020fdbf7ec6e17f` | `b2f56ddf1d7e061b1505b3cc3672c11107e19061` | `100644` |
| `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z/terminal_evidence.json` | 79775 | `38d0958ea0d7212f07bf630e9c0e71c3c3b945e5ae04a5bc98eca2092c94d23a` | `bc21b84e16e766a62169ed2b4a92fc067a61865e` | `100644` |

For all seven paths:

- committed mode is `100644`;
- committed blob OID equals the implementation record;
- committed blob bytes match audited size and SHA-256;
- worktree bytes equal committed blob bytes;
- path and authorization ID remain unchanged.

## 5. Retained Migration-050 proof

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

All twelve files remain untracked and byte-identical. The two `.sqlite3` evidence files remain ignored and were hashed as regular files without opening SQLite.

## 6. Namespace proof

| Set | Count |
| --- | ---: |
| Tracked historical | 18 |
| Visible current | 10 |
| Ignored current | 2 |
| Current evidence | 12 |
| Complete inventory | 30 |

- `F == T union M`: `true`;
- `T intersect M == empty`: `true`;
- `M == visible union ignored`: `true`.

## 7. Authoritative DB proof

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | 65671168 |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | 1785617072867102156 |
| WAL | absent |
| SHM | absent |
| Journal sidecar | absent |

The DB identity exactly matches the terminal evidence preserved in the consumed authorization package. The proof never opened SQLite.

## 8. Before/after noninterference

The proof captured complete authorization, migration, and DB filesystem snapshots before inspection and again before committing this report.

The snapshots were equal. No evidence path, content, mode, timestamp, DB byte, or sidecar state changed.

## 9. Money-usefulness contribution

This proof establishes that the consumed authorization package is safely historical and no longer competes with fresh current authorization evidence.

It preserves the valid Migration-050 package for the next exact revalidation gate, reducing unnecessary reruns and shortening the safe route to the real `WINDOW_15M` command.

It creates no memory, market signal, decision, trade, or profit claim.

## 10. What this proof improves

- independently validates implementation ancestry and scope;
- proves committed evidence blob identity;
- proves retained migration identity;
- proves namespace arithmetic after rollover;
- proves authoritative DB noninterference;
- proves zero protected-capability execution.

## 11. What remains locked

- fresh authoritative readiness;
- fresh manifest, marker, and authorization;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- authoritative SQLite access or mutation;
- memory generation and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 12. Proof/test required before rollover completion

This bounded proof satisfies the design's minimum proof:

- exact ancestry;
- exact eight-file implementation scope;
- exact committed blob identity;
- exact retained migration identity;
- `18/10/2/12/30` namespace;
- authoritative DB and sidecar preservation;
- zero protected-capability execution.

No broad regression suite was required because no production source changed.

Independent closeout remains required before fresh readiness.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Proof disposition |
| --- | --- |
| Future commit changes exact HEAD | Fresh readiness and authorization must bind the post-closeout HEAD |
| Migration evidence may drift after proof | Fresh readiness must recheck all twelve identities |
| Historical files contain failed prior command output | Preserved honestly and intentionally |
| DB was not opened for integrity queries | Correct for this read-only filesystem proof; prior authoritative evidence covers integrity |
| Fresh authorization does not exist | Remains locked until closeout and fresh readiness |

## 14. Roadmap decision

Rollover is ready for independent closeout only.

Fresh readiness, authorization, and campaign remain unauthorized.

## 15. Exact next lane

`V2-9.8B WINDOW_15M Current Evidence Historical Rollover Independent Closeout`
