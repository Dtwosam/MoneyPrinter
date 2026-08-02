# Printer V1 V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization Independent Review

Date: 2026-08-02

Linear tracking issue: `DTW-16`

Lane:
`V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization Independent Review`

Lane type: read-only independent review of one fresh `WINDOW_15M` final
authorization. No authorization JSON was modified, recreated, staged, committed,
moved, consumed, or applied.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_FRESH_EXACT_HEAD_WINDOW_15M_FINAL_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

The independently reviewed authorization package is exact, canonical, correctly
lineage-bound to its own report commit, backed by byte-identical Migration-050
and authoritative-database evidence, bound to the exact current launch chain, and
entirely unconsumed. Every protected-capability counter remains zero. This PASS
authorizes no runtime by itself.

## 2. Exact baseline

| Item | Exact value | Result |
| --- | --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization-independent-review` | matched |
| Starting HEAD | `be6ead74a260d58c7ccca2042de2fe8f2b584242` | matched |
| Linear issue | `DTW-16` | matched |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` | matched |
| Tracked worktree | clean | matched |
| Index | clean | matched |
| Untracked roots | exactly two | matched |
| Untracked root 1 | `operator-runs/v2-9-8b-authoritative-mig050/` (Migration-050) | matched |
| Untracked root 2 | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z/` (new authorization package) | matched |
| Current authorization-package count | `1` | matched |
| Other current authorization | none | matched |

The only two untracked roots are the retained Migration-050 package and the new
authorization package. The two prior authorization directories
(`…205700Z`, `…112358Z`) are tracked history, not current packages.

## 3. Report-commit reconciliation

| Property | Required | Observed | Result |
| --- | --- | --- | --- |
| Report commit | `be6ead74…` | `be6ead74a260d58c7ccca2042de2fe8f2b584242` | matched |
| Parent | `d9714fa56ae0217dcca8a35ad66e27f223e0eba5` | `d9714fa5…` | matched |
| Files added | exactly one authorization report | `docs/printer-v1-v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization.md` (+264, 1 file) | matched |
| Amended or replaced | must be false | single clean commit, correct single parent, one added report | matched |

The report commit adds exactly one authorization report and has exactly the
readiness evidence-completion commit as its single parent. The untracked
`final_authorization.json` is not part of the commit, consistent with the
authorization's own binding statement.

## 4. Authorization schema and complete identity

Verified without rewriting or `chmod`. No component of the package path is a
symbolic link; all four components are regular directory/file entries.

| Property | Required | Observed | Result |
| --- | --- | --- | --- |
| Files in package | exactly one | `final_authorization.json` only | matched |
| Authorization ID equals directory | yes | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` | matched |
| Regular file | yes | yes (`nlink=1`, mode `100444`) | matched |
| Symlink in any path component | none | none | matched |
| Mode | `0444` | `0444` | matched |
| Size | `8129` | `8129` | matched |
| SHA-256 | `1191277816c97589ed05aa0aee8ec4a5af1feb777728c356a51eba40c1595626` | identical | matched |
| Tracking | untracked and unstaged | untracked, unstaged | matched |
| Canonical UTF-8 JSON | yes | round-trips byte-identically | matched |
| Sorted keys | yes | re-serialization equal | matched |
| Two-space indentation | yes | re-serialization equal | matched |
| Trailing newline | yes | present | matched |
| Duplicate-key rejection | must reject | strict `object_pairs_hook` found none; would raise | matched |
| NaN / unsupported value | none | strict `parse_constant` guard found none | matched |
| Schema | `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` | `schema_version = PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` | matched |

Canonical proof: `json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
+ "\n"` reproduced the exact on-disk bytes (size `8129`, SHA-256 `1191277816…`).
The tracked historical consumed authorization
`…112358Z/final_authorization.json` was read as schema precedent: it carries the
same `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` schema and an identical
top-level key set, confirming schema continuity.

## 5. Readiness and Git bindings

| Binding | Required | Observed | Result |
| --- | --- | --- | --- |
| Readiness audit commit | `9b1f88ac143db2db690dfd53bc9130017762179a` | present, message `Audit post-rollover-2 fresh authoritative 15m readiness` | matched |
| Readiness evidence-completion commit | `d9714fa56ae0217dcca8a35ad66e27f223e0eba5` | present, message `Complete post-rollover-2 fresh readiness evidence` | matched |
| Readiness verdict | `V2_9_8B_POST_ROLLOVER_2_FRESH_AUTHORITATIVE_WINDOW_15M_READINESS_EVIDENCE_COMPLETION_PASS` | `readiness.verdict` identical | matched |
| Authorized branch | `agent/v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization` | `authorized_git.branch` identical | matched |
| Authorized HEAD | `be6ead74a260d58c7ccca2042de2fe8f2b584242` | `authorized_git.head` identical | matched |
| Authorization report path | `docs/printer-v1-v2-9-8b-post-rollover-2-fresh-exact-head-window-15m-final-authorization.md` | identical | matched |
| Exact-HEAD requirement | true | `exact_head_required = true` | matched |
| Tracked worktree-clean requirement | true | `tracked_worktree_must_be_clean = true` | matched |

The JSON binds its readiness anchor to the evidence-completion commit
`d9714fa5…` and its authorized HEAD to the report commit `be6ead74…`, exactly as
the authorization report states.

## 6. Migration-050 proof

All twelve files were freshly hashed as ordinary files. Neither retained SQLite
evidence file was opened through SQLite.

| Property | Required | Observed | Result |
| --- | --- | --- | --- |
| Execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` | identical | matched |
| Regular non-symlink files | 12 | 12 (0 symlinks, 0 non-regular) | matched |
| Individual sizes and hashes | per readiness-evidence-completion and authorization reports | all 12 reproduced identically | matched |
| Each retained SQLite size | `65654784` | `65654784` (both) | matched |
| Each retained SQLite SHA-256 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | identical (both) | matched |
| Listing digest | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` | reproduced identically | matched |
| Migration-050 rerun | none | none | matched |

The sorted (`LC_ALL=C` bytewise path) twelve-line identity listing —
`<sha><two spaces><path><LF>` — was independently reconstructed and its own
SHA-256 reproduced `08e6f40b…`, matching both source reports.

## 7. DB proof

Hash/stat only; SQLite never opened. Checked before and after the review with
exact equality.

| Field | Required | Before | After | Result |
| --- | --- | --- | --- | --- |
| Size | `65671168` | `65671168` | `65671168` | matched |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` | identical | identical | matched |
| `mtime_ns` | `1785617072867102156` | `1785617072867102156` | `1785617072867102156` | matched |
| WAL / SHM / journal | absent | absent | absent | matched |

## 8. Launch-chain proof

Current Git blob, size, and SHA-256 were freshly computed for all five files.

| File | Git blob | Bytes | SHA-256 | Result |
| --- | --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `a7fd77e6…` | 878 | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` | matched |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `64b8a305…` | 42875 | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` | matched |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `70b87bef…` | 169566 | `16c8bb80569a870c21a13cc9f3a7ba724042dbb5fbab86f8ca080293b4c6587b` | matched |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `73d5ac30…` | 30802 | `cb3eb498593bec2bd4460d30ddf67e864b195f9bb89b82ecd707dc31304cc047` | matched |
| `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py` | `e4f1eb04…` | 34700 | `b41678d3b1ff08ae9dccca9639b7f412e104356805683bfcab178f4a72ff47fe` | matched |

All five SHA-256 values match both the authorization JSON `accepted_launch_chain`
and the authorization report. Static wrapper confirmation:

- exactly one production `subprocess.Popen` (single launch site, line 392);
- `shell=False` (line 398);
- lexical `<repository>/.venv` child-interpreter preservation, with venv-ancestor,
  `pyvenv.cfg`, and entrypoint validation and symlink rejection;
- wrapper-only application; direct operational-command invocation is
  unauthorized (`direct_operational_command_authorized = false`,
  `wrapper_required = true`);
- no retry, rerun, resume, restart, or successor path — all flags hard `false`.

The wrapper and operational command were not run.

## 9. Command and campaign law

| Field | Required | Observed | Result |
| --- | --- | --- | --- |
| Mode | `run` | `run` | matched |
| Operator approved | true | true | matched |
| Allowed invocation count | `1` | `1` | matched |
| Automatic retry | false | false | matched |
| Manual rerun | false | false | matched |
| Resume | false | false | matched |
| Restart | false | false | matched |
| Successor | false | false | matched |
| Main window | `WINDOW_15M` | `WINDOW_15M` | matched |
| Main-window duration | `900` | `900` | matched |
| Total duration | `1200` | `1200` | matched |
| Token capacity | `2` | `2` | matched |
| Support-only window | `WINDOW_5M_MICRO_EVENT` | `WINDOW_5M_MICRO_EVENT` | matched |
| Selective 1h continuation | false | false | matched |
| Provider rotation | false | false | matched |
| Source owner | Source Governor | `SOURCE_GOVERNOR` | matched |
| Scheduler owner | Central Scheduler | `CENTRAL_SCHEDULER` | matched |
| Locked windows | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` | all four locked | matched |

## 10. Unconsumed-state proof

No artifact exists for the new authorization ID under
`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/`.

| Artifact for `…210122Z` | Required | Observed |
| --- | --- | --- |
| External application directory | absent | absent |
| Application marker | absent | absent |
| Git-provenance manifest | absent | absent |
| Staging directory | absent | absent (`.staging` holds only a `…112358Z-…` entry) |
| Child stdout / stderr | absent | absent |
| Terminal evidence | absent | absent |
| Authorization consumption | unconsumed | unconsumed |

A recursive search of the operations tree for `20260802T210122Z` returned
nothing. No such artifact was created by this review.

## 11. Namespace reconciliation

| Set | Required | Observed | Result |
| --- | ---: | ---: | --- |
| Tracked historical `T` | `19` | `19` | matched |
| Visible current | `11` | `11` | matched |
| Ignored current | `2` | `2` | matched |
| Current evidence `M` | `13` | `13` | matched |
| Complete inventory `F` | `32` | `32` | matched |
| `F == T ∪ M` | true | `19 ∪ 13 = 32`, disjoint | matched |
| `T ∩ M == ∅` | true | tracked paths disjoint from current | matched |
| `M == visible-current ∪ ignored-current` | true | `11 ∪ 2 = 13` | matched |

Visible current = ten Migration-050 non-SQLite files + one new
`final_authorization.json`. Ignored current = the two retained SQLite evidence
files. Tracked `T` = 19 committed files under `operator-runs/`. The sets are
disjoint and their union is the complete 32-file inventory.

## 12. Zero protected-capability activity

Checked before and after; all unchanged.

| Protected item | Before | After |
| --- | ---: | ---: |
| Authorization bytes | `1191277816…` | `1191277816…` (unchanged) |
| Migration-050 package | 12 identities + `08e6f40b…` listing | unchanged |
| Authoritative DB | `56ca1218…`, `65671168`, `mtime_ns 1785617072867102156` | unchanged |
| Old consumed application digest | `f1a12143425ab418b14bbd0e60dfacd5268b99a13e6c637590160dbfe034f96f` | reproduced identically |
| New authorization / manifest / marker / application | 0 | 0 |
| Provider requests / Scheduler work / campaigns | 0 | 0 |
| Memory / retrieval / decisions / positions / trades / audits / PnL | 0 | 0 |

Every protected-capability counter remains zero. The old consumed application
(`…112358Z`, five `0444` immutable files) reproduced its exact parent digest
`f1a12143…` and was neither reused, removed, repaired, nor altered.

## 13. Money-usefulness contribution

This independent review converts a self-attested fresh authorization into an
independently verified permission. It confirms — from raw bytes, Git objects, and
filesystem state rather than from the authoring lane's own claims — that exactly
one scarce `WINDOW_15M` one-shot attempt is backed by byte-identical migration
and database evidence and by the exact current launch chain, and that nothing has
been prematurely consumed. That protects the single remaining bounded
clean-memory attempt from resting on unverified assertion. It creates no market
observation, memory, decision, trade, or profit.

## 14. What this review establishes

- the authorization package is an exact, canonical, single-file `0444` artifact
  bound to its own report commit `be6ead74…`;
- readiness lineage, launch chain, Migration-050, and authoritative DB are all
  byte-identical to the bound evidence;
- the authorization is unconsumed with no external application, manifest, marker,
  or staging for its ID;
- the complete 32-file namespace reconciles exactly (`T=19`, `M=13`, disjoint);
- all command and campaign law fields hold; retry/rerun/resume/restart/successor
  are all `false`;
- zero protected-capability activity occurred during the review.

## 15. What remains locked

This PASS authorizes no runtime by itself. Still locked: manifest and marker
creation; wrapper application and operational-command execution; provider/source
contact and paid APIs; Source Governor and Central Scheduler runtime; discovery
and campaign execution; authoritative SQLite mutation or migration; memory
generation, retrieval activation, and decisions; BUY/SELL/HOLD, positions,
trades, audits, and PnL; selective `WINDOW_1H` continuation and any longer
window; wallets, private keys, real funds, live execution; scoring, ranking,
confidence, weighting, embeddings, and vectors. `WINDOW_5M_MICRO_EVENT` remains
support-only. Printer remains Solana-only, Solana-memecoin-only, paper-only,
Source-Governed, and Central-Scheduler-led.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Disposition |
| --- | --- |
| Authorization bytes altered during review | Prevented; read-only hashing/stat only, before/after byte-identical |
| Accidental SQLite open on DB or evidence | Prevented; ordinary-file hashing only, no SQLite access |
| Package binds baseline instead of report commit | Verified false; `authorized_git.head = be6ead74…` (report commit) |
| Premature consumption (manifest/marker/application) | Verified absent for the new ID; nothing created |
| Namespace collision or miscount | Verified; `F=32`, `T∩M=∅`, exactly one current authorization |
| Old consumed application tampering | Verified intact; digest `f1a12143…` reproduced, untouched |
| Launch-chain drift (esp. stale wrapper) | Verified; current wrapper `cb3eb498…` bound, not consumed `77e35c14…` |
| Natural source availability / clean-memory yield | Still unproven; belongs to the later separately authorized runtime lane |

## 17. Final verdict

`V2_9_8B_POST_ROLLOVER_2_FRESH_EXACT_HEAD_WINDOW_15M_FINAL_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

A PASS authorizes no runtime by itself. It confirms the authorization package is
eligible for exactly one future wrapper application under separate work.

## 18. Exact next lane

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M One-Shot Wrapper Application`

This lane stops after committing this review report. It does not apply the
wrapper.
