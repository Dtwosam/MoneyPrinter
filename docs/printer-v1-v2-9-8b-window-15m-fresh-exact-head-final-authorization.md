# Printer V1 V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization`

## 1. Verdict

`V2_9_8B_WINDOW_15M_FRESH_EXACT_HEAD_FINAL_AUTHORIZATION_PASS`

One fresh authorization ID is approved for one future wrapper application:

`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

This report is committed first. The untracked `final_authorization.json` is then created and bound to the resulting report commit, preventing immediate exact-HEAD staleness.

This lane does not create a manifest or marker, does not apply the wrapper, and does not execute the real `WINDOW_15M` command.

## 2. Controlling source stack

- `AGENTS.md`: `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e`
- `docs/printer-v1-clean-master-spec.md`: `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657`
- `docs/printer-v1-post-rc-build-order.md`: `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2`
- `docs/printer-v1-memory-factory-guide.md`: `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d`
- `docs/printer-v1-current-state-memory-growth-audit.md`: `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81`
- `docs/printer-v1-memory-growth-build-order-v2.md`: `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1`

The active memory-growth build order remains part of the source stack and is not the sole source of truth.

## 3. Authorization baseline

| Item | Value |
| --- | --- |
| Readiness commit | `aee864888ade7a414940d21af6dfa83f349a69d1` |
| Readiness verdict | `V2_9_8B_WINDOW_15M_FRESH_AUTHORITATIVE_READINESS_AUDIT_PASS` |
| Authorization branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| New authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Old consumed ID | `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Current authorization files before creation | `0` |

The JSON package must bind the commit created by this report, not `aee864888ade7a414940d21af6dfa83f349a69d1`.

## 4. Retained migration package

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

All twelve files remain untracked and byte-identical. No new Migration-050 run is authorized.

## 5. Accepted launch-chain identities

| File | SHA-256 |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `77e35c14860e3aae02f570e18773a8c7edb2f76e71d3772adb0ec58ef57d37c6` |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `87a1b970ac6dac4bee8b43cc392b5c4e54feb1f06e606b1cc34c1ea29699780b` |

The future operator command must use:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

Direct invocation of the operational command is not authorized.

## 6. Authoritative DB binding

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | 65671168 |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | 1785617072867102156 |
| Sidecars | absent |

The DB was hashed as a regular file and never opened through SQLite.

## 7. Authorized command law

The new JSON package must authorize exactly:

- one ordinary `run`;
- explicit operator approval;
- `WINDOW_15M` as the main window;
- two-token capacity;
- 1,200-second total duration;
- zero automatic retries;
- no manual rerun, resume, restart, or successor;
- no selective 1h continuation;
- `WINDOW_5M_MICRO_EVENT` support-only;
- Source Governor and Central Scheduler ownership;
- no provider rotation.

The authorization may be consumed by a blocked or safe-stop attempt. It guarantees neither source availability, eligible supply, clean memory, favorable outcome, nor profit.

## 8. Money-usefulness contribution

The authorization creates a single exact, reviewable route toward a real 15-minute memory attempt while protecting the retained migration evidence and preventing stale-HEAD reuse.

It creates no market evidence, memory, decision, trade, or profit claim.

## 9. What this lane improves

- creates a distinct authorization identity;
- binds future application to the post-report exact HEAD;
- preserves the accepted wrapper-only route;
- preserves the migration package without rerun;
- keeps every later capability locked until independent review.

## 10. What remains locked

- manifest creation;
- application marker creation;
- wrapper application;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- SQLite access or mutation;
- memory generation and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

## 11. Proof/review required before application

Independent review must verify:

1. the report commit is the parent baseline of the current authorization;
2. exactly one new authorization file exists;
3. authorization ID is new and path-safe;
4. branch and HEAD equal the post-report commit;
5. migration execution ID and all twelve file identities match;
6. DB identity and absent sidecars match;
7. wrapper/validator/guard/launcher hashes match;
8. all retry/rerun/resume/restart/successor flags are false;
9. main window is `WINDOW_15M` and selective 1h is false;
10. no manifest, marker, wrapper application, provider call, campaign, or protected capability occurred.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Authorization disposition |
| --- | --- |
| Report commit changes HEAD | Package is created only after commit and binds that new HEAD |
| Package creation could fail after commit | Fail closed; preserve commit and do not auto-reset or amend |
| Evidence may drift before application | Independent review and wrapper validation must recheck it |
| Authorization can be consumed by a blocked preflight | One-attempt semantics are explicit |
| Real command still has natural source uncertainty | No outcome or profit guarantee |

## 13. Roadmap decision

- fresh authorization decision approved: `true`;
- untracked authorization package creation allowed after report commit: `true`;
- independent review required: `true`;
- manifest creation authorized: `false`;
- marker creation authorized: `false`;
- wrapper application authorized: `false`;
- campaign authorized: `false`.

## 14. Exact next lane

`V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization Independent Review`
