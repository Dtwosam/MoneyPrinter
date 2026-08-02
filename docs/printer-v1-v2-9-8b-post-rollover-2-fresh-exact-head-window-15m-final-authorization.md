# Printer V1 V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization

Date: 2026-08-02

Linear tracking issue: `DTW-15`

Lane:
`V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization`

Lane type: single fresh final authorization for one future wrapper application.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_FRESH_EXACT_HEAD_WINDOW_15M_FINAL_AUTHORIZATION_PASS`

This lane issues exactly one fresh `WINDOW_15M` final authorization for one
future one-shot wrapper application. It creates the authorization report first
and, only afterward, one untracked `final_authorization.json` bound to the
commit created by this report — not to the starting baseline. It does not run
or apply the authorization, create any manifest or marker, create any external
application directory, or contact any provider.

## 2. Exact starting baseline

| Item | Exact value |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization` |
| Required and inspected starting HEAD | `d9714fa56ae0217dcca8a35ad66e27f223e0eba5` |
| Starting commit message | `Complete post-rollover-2 fresh readiness evidence` |
| Linear issue | `DTW-15` |
| Tracked worktree | clean |
| Index | clean |
| Only untracked root | `operator-runs/v2-9-8b-authoritative-mig050/` |
| Current `WINDOW_15M` authorization packages | `0` |
| Retained migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Production/test changes | `0` |

The exact branch and HEAD matched before authorization work began. The tracked
worktree and index were clean. The sole untracked root held the ten visible and
two ignored Migration-050 evidence files. No current `WINDOW_15M`
final-authorization package existed.

## 3. New authorization ID

`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

Generated exactly once as a UTC identifier. It is path-safe, distinct from every
historical authorization ID (notably distinct from the consumed
`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` and from
`V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`), and neither its destination package
directory nor its external one-shot application directory existed at issuance.

## 4. Bound readiness lineage

| Binding | Commit / verdict |
| --- | --- |
| Readiness audit commit | `9b1f88ac143db2db690dfd53bc9130017762179a` |
| Readiness evidence-completion commit | `d9714fa56ae0217dcca8a35ad66e27f223e0eba5` |
| Bound readiness verdict | `V2_9_8B_POST_ROLLOVER_2_FRESH_AUTHORITATIVE_WINDOW_15M_READINESS_EVIDENCE_COMPLETION_PASS` |

The authorization binds the readiness evidence-completion commit
`d9714fa56ae0217dcca8a35ad66e27f223e0eba5` as its readiness anchor.

## 5. Fresh preauthorization evidence

### 5.1 Migration-050 package

Execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`.

Exactly twelve regular, non-symlink files were enumerated and freshly hashed as
ordinary files. Neither retained SQLite evidence file was opened through SQLite.
The exact sorted, repository-relative identity listing reproduced SHA-256
`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`.

| Repository-relative path | Bytes | Fresh SHA-256 |
| --- | ---: | --- |
| `.../application_started.json` | `50133` | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `.../application_stderr.txt` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.../application_stdout.txt` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.../backup_restore_preflight.json` | `13836` | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `.../closeout_inputs.json` | `2384` | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `.../disposable-restore/printer_v1-rehearsal.sqlite3` | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `.../final_authorization.json` | `6589` | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `.../post_migration_proof.json` | `103903` | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `.../preauthorization_evidence.json` | `36274` | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `.../preflight.json` | `18590` | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `.../rollback_rehearsal.json` | `16244` | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `.../verified-backup/printer_v1-pre050.sqlite3` | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

All paths are under
`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`.
These are the exact individual identities recorded in the readiness
evidence-completion report. `migration_050_must_not_be_invoked_again` remains
true.

### 5.2 Authoritative database

Hash/stat only; SQLite was never opened.

| Field | Exact value |
| --- | --- |
| Path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| Regular file / symlink | yes / no |
| Size | `65671168` |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` |
| `mtime_ns` | `1785617072867102156` |
| WAL / SHM / journal | absent / absent / absent |

### 5.3 Consumed historical application

The external consumed application at
`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`
was inspected read-only. Its complete application-parent digest reproduced
exactly `f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f`
(sorted `shasum -a 256` over the five `0444` immutable files by absolute path,
then hashed). The consumed authorization
`V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` remains permanently consumed and
non-reusable; no attempt was made to reuse, remove, repair, or alter it.

### 5.4 Current launch chain

Git blobs, sizes, and SHA-256 values were freshly computed.

| File | Bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `878` | `a7fd77e680fa48dff911982d1491462185b5699a` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `42875` | `64b8a305765bb0967ae1f57301d8bcee70db22a3` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `169566` | `70b87bef1add0f203c5d497213ad2c6d8ef52470` | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `30802` | `73d5ac306eee0241dcb3d1b97bd353fa950bd470` | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `34700` | `e4f1eb046d8ce9c4def2840d9ffb80edd679589a` | `b41678d3b1ff08ae9dccca9639b7f412e104356805683bfcab178f4a72ff47fe` |

The current repaired wrapper SHA-256 is
`cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047`. The old
consumed wrapper hash beginning `77e35c14` is not reused.

Static confirmation of the wrapper:

- exactly one production `subprocess.Popen` (single launch site);
- `shell=False`;
- lexical `<repository>/.venv` child interpreter preservation, with venv
  ancestor, `pyvenv.cfg`, and entrypoint validation;
- no direct operational-command authorization — the operational command is
  launched only through the validated Git-provenance authorization and a
  create-once marker;
- no retry, rerun, resume, restart, or successor path — all such flags are hard
  `false` and all such counters are `0`.

### 5.5 Environment shape

`PRINTER_HELIUS_API_KEY`, `SOLANA_TRACKER_API_KEY`, and `PRINTER_SOLANA_RPC_URL`
are present, non-empty, non-placeholder, and structurally valid. No value was
printed or hashed and no endpoint was contacted.

## 6. Authorized command law

| Field | Value |
| --- | --- |
| Mode | `run` |
| Operator approved | `true` |
| Allowed invocation count | `1` |
| Automatic retry allowed | `false` |
| Manual rerun allowed | `false` |
| Resume allowed | `false` |
| Restart allowed | `false` |
| Successor allowed | `false` |

Exactly one wrapper application of exactly one operational-command child is
authorized. Direct operational-command invocation remains unauthorized; the
wrapper is required.

## 7. Campaign policy

Main window `WINDOW_15M` (`900` seconds); total duration `1200` seconds; token
capacity `2`; support-only window `WINDOW_5M_MICRO_EVENT`; selective `WINDOW_1H`
continuation `false`; provider rotation `false`. Source Governor owns
external-source access; Central Scheduler owns runtime. `WINDOW_1H`,
`WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain locked.

## 8. Money-usefulness contribution

This authorization converts a proven-ready, evidence-complete state into a
single scarce permission to attempt exactly one bounded `WINDOW_15M` clean-memory
collection window. It preserves the exact retained migration package, the
authoritative database identity, and the consumed prior application, so the one
future attempt rests on fresh proof rather than assumption. It creates no market
observation, memory, decision, trade, or profit; its only value is enabling one
carefully bounded future attempt to gather clean memory that a later lane could
use.

## 9. What this authorization improves

- binds the exact post-report commit and branch rather than the starting
  baseline;
- binds fresh Migration-050, authoritative-DB, launch-chain, and consumed-
  application evidence;
- binds the current repaired wrapper (`cb3eb498…`), not the consumed
  `77e35c14…` wrapper;
- reasserts the single-invocation, no-retry command law for one wrapper
  application.

## 10. What remains locked

- manifest and marker creation until independent review;
- wrapper application and operational-command execution;
- provider/source contact and paid APIs;
- Source Governor and Central Scheduler runtime;
- discovery and campaign execution;
- authoritative SQLite mutation or migration;
- memory generation, retrieval activation, and decisions;
- BUY/SELL/HOLD, positions, trades, audits, and PnL;
- selective `WINDOW_1H` continuation and any longer window;
- wallets, private keys, real funds, live execution;
- scoring, ranking, confidence, weighting, embeddings, and vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, paper-only, Source-Governed, and Central-Scheduler-led.

## 11. Independent-review requirements

Before any wrapper application, an independent review must confirm:

- independent authorization review PASS;
- exact branch and HEAD, with tracked worktree and index clean;
- retained Migration-050 package byte-identical (twelve identities and listing
  digest);
- this authorization package exact and unconsumed;
- authoritative DB identity exact and no SQLite sidecars;
- accepted launch-chain identities exact, including the current wrapper hash;
- no pre-existing manifest, marker, or external application for the new ID.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition |
| --- | --- |
| JSON might bind the starting baseline instead of the report commit | Prevented; JSON binds the commit created by this report |
| Stale evidence reuse | Prevented; all Git, wrapper, DB, migration, and timestamp values freshly computed |
| Old consumed wrapper hash reuse | Prevented; current wrapper `cb3eb498…` bound, `77e35c14…` rejected |
| Authorization-ID collision | Prevented; fresh path-safe ID, destination and external app dirs absent |
| Accidental SQLite open | Prevented; hash/stat only on both DB and evidence files |
| Application before review | Locked; manifest/marker/application remain forbidden until independent review |
| Natural source availability or clean-memory yield | Still unproven; belongs to a later separately authorized runtime lane |
| Package creation or verification failure | Fail closed; preserve report commit, return BLOCKED, issue no replacement ID |

## 13. JSON binding statement

The untracked `final_authorization.json` created after this report binds the
commit created by this report — not the starting baseline
`d9714fa56ae0217dcca8a35ad66e27f223e0eba5`. The readiness anchor bound inside the
JSON remains the readiness evidence-completion commit
`d9714fa56ae0217dcca8a35ad66e27f223e0eba5`; the authorized Git HEAD is the report
commit.

## 14. Honest terminal law

This authorization guarantees none of: provider success, eligible two-token
supply, clean memory, favorable outcome, or profit. It may be permanently
consumed by a blocked or safe-stop attempt.

## 15. Exact next lane

`V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization Independent Review`

This lane stops after creating and verifying the authorization package. It does
not begin independent review or apply the wrapper.
