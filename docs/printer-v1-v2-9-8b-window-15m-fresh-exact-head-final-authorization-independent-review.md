# Printer V1 V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization Independent Review

Date: 2026-08-02

Lane:
`V2-9.8B WINDOW_15M Fresh Exact-HEAD Final Authorization Independent Review`

Lane type: independent, read-only review plus one report.

## 1. Verdict

`V2_9_8B_WINDOW_15M_FRESH_EXACT_HEAD_FINAL_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

The fresh authorization package is independently accepted for one future wrapper application only.

Authorization ID:

`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`

Authorization file:

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z/final_authorization.json`

Authorization SHA-256:

`af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60`

No manifest, marker, application directory, wrapper child, provider request, Scheduler runtime, campaign, SQLite connection, memory, retrieval, decision, position, trade, audit, or PnL capability ran.

## 2. Critical exact-HEAD boundary

The authorization binds:

| Field | Value |
| --- | --- |
| Authorized branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` |
| Authorized HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |
| Review branch | `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization-independent-review` |
| Review starting HEAD | `00f827c8c6c179534ab4e26e710c359e6d0ada22` |

This review report is committed on a separate branch.

The future application **must not run from the review branch or review commit**. It must return to `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization` at exact HEAD `00f827c8c6c179534ab4e26e710c359e6d0ada22` with a clean tracked tree and index.

## 3. Authorization identity and schema

| Field | Result |
| --- | --- |
| File size | `8019` |
| File mode | read-only `0444` |
| Canonical JSON | PASS |
| Duplicate keys | none |
| Schema exact | `true` |
| New authorization ID | PASS |
| Exact branch/HEAD | PASS |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Allowed invocation count | `1` |
| Retry/rerun/resume/restart/successor | all `false` |
| Main window | `WINDOW_15M` |
| Selective 1h | `false` |
| Wrapper required | `true` |

The authorization remains untracked current evidence and has not been consumed.

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

All twelve files remain untracked, exact, and unchanged. Migration 050 must not run again.

## 5. Launch-chain identities

| File | SHA-256 |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `77e35c14860e3aae02f570e18773a8c7edb2f76e71d3772adb0ec58ef57d37c6` |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `87a1b970ac6dac4bee8b43cc392b5c4e54feb1f06e606b1cc34c1ea29699780b` |

Direct invocation of the operational command remains unauthorized.

The only authorized entrypoint is:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

## 6. Current namespace

| Set | Count |
| --- | ---: |
| Tracked historical | 18 |
| Visible current | 11 |
| Ignored current | 2 |
| Current evidence | 13 |
| Complete inventory | 31 |
| Current authorization files | 1 |

- `F == T union M`: `true`;
- `T intersect M == empty`: `true`;
- `M == visible union ignored`: `true`.

## 7. Authoritative DB identity

| Field | Value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Size | 65671168 |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | 1785617072867102156 |
| WAL/SHM/journal | absent |

The DB was hashed as a regular file and never opened through SQLite.

## 8. Application-state proof

| Field | Value |
| --- | --- |
| Canonical application directory | `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` |
| Canonical application exists | `false` |
| Authorization-specific staging residue | `0` |
| Manifest exists | `false` |
| Marker exists | `false` |
| Terminal exists | `false` |

The authorization is therefore unconsumed at review time.

## 9. Money-usefulness contribution

This review reduces the chance that a one-shot authorization is lost to malformed JSON, stale Git identity, migration drift, DB drift, wrapper bypass, or an already-existing application marker.

It creates no memory, market signal, decision, trade, or profit claim.

## 10. What this review improves

- independently accepts the exact authorization bytes and schema;
- confirms one distinct current authorization package;
- confirms exact authorized branch and HEAD;
- confirms retained migration and DB identities;
- confirms accepted wrapper-only launch chain;
- confirms no prior application exists for this authorization.

## 11. What remains locked

Until the operator runs the exact approved one-shot command:

- manifest and marker creation;
- provider/source access;
- Source Governor and Central Scheduler runtime;
- campaign execution;
- SQLite access or mutation;
- memory generation and retrieval;
- BUY/SELL/HOLD, positions, trade events, audits, and PnL;
- longer windows;
- wallets, private keys, real funds, live execution, paid APIs;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 12. Required application procedure

After this review commit is pushed and remotely verified:

1. switch back to `agent/v2-9-8b-window-15m-fresh-exact-head-final-authorization`;
2. verify HEAD is exactly `00f827c8c6c179534ab4e26e710c359e6d0ada22`;
3. verify tracked tree and index are clean;
4. verify status contains only the retained migration root and this authorization root;
5. invoke `scripts/Start-PrinterV1-Window15M-OneShot.ps1` exactly once with:
   - the exact authorization file;
   - authorization SHA-256 `af63b05423c4baa7f577cc18b252ab96a2c4cd0200d534375164887727d55c60`;
   - explicit operator approval;
6. capture and preserve all wrapper output immediately;
7. do not retry, rerun, resume, restart, or create a successor.

The wrapper will create the manifest and create-once marker and may consume the authorization even if the operational command blocks before provider access.

## 13. Proof/test required after application

Immediate terminal evidence must prove:

- exact application directory and artifact identities;
- manifest/marker binding to this authorization, branch, and HEAD;
- exactly one child invocation;
- actual exit code and terminal status;
- source, Scheduler, and DB activity truthfully reported;
- no retry, rerun, resume, restart, or successor;
- protected capability deltas remain zero unless explicitly authorized;
- independent post-application closeout remains required.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Review disposition |
| --- | --- |
| Review commit changes HEAD on review branch | Application must return to the separate authorized branch/HEAD |
| Authorization may be consumed by blocked preflight | Explicit one-attempt law; no retry |
| Evidence or DB may drift after review | Wrapper must revalidate before marker creation |
| Natural source availability may fail | No source, clean-memory, outcome, or profit guarantee |
| Application creates irreversible marker | Exact operator command and immediate capture required |

## 15. Roadmap decision

- independent authorization review passed: `true`;
- one-shot wrapper application lane authorized: `true`;
- application authorized only on exact authorized branch/HEAD: `true`;
- direct operational command authorized: `false`;
- automatic retry or rerun authorized: `false`;
- longer windows authorized: `false`;
- retrieval or trading capabilities authorized: `false`.

## 16. Exact next lane

`V2-9.8B WINDOW_15M Fresh One-Shot Wrapper Application and Immediate Terminal Evidence Capture`
