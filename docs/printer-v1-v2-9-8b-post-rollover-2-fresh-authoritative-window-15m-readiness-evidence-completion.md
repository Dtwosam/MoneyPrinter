# Printer V1 V2-9.8B Post-Rollover-2 Fresh Authoritative WINDOW_15M Readiness Evidence Completion

Date: 2026-08-02

Linear tracking issue: `DTW-14`

Lane:
`V2-9.8B Post-Rollover-2 Fresh Authoritative WINDOW_15M Campaign Readiness Evidence Completion`

Lane type: documentation-only readiness evidence completion.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_FRESH_AUTHORITATIVE_WINDOW_15M_READINESS_EVIDENCE_COMPLETION_PASS`

The single proof gap in the pushed post-rollover-2 fresh authoritative
`WINDOW_15M` campaign-readiness audit is closed. Both retained Migration-050
SQLite evidence files were freshly inspected and hashed by reading their raw
bytes as ordinary files. Each is a regular non-symlink file of exactly
`65654784` bytes and each freshly reproduced SHA-256
`e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2`.

All twelve Migration-050 files were then freshly hashed. Their exact sorted,
repository-relative identity listing reproduced SHA-256
`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`.

No SQLite connection, query, or PRAGMA was issued against either retained
Migration-050 SQLite evidence file. No evidence was copied, moved, chmod-ed,
rewritten, touched, or otherwise altered.

This PASS completes readiness evidence only. It creates no authorization and
authorizes no wrapper application or campaign.

## 2. Exact baseline

| Item | Exact value |
| --- | --- |
| Branch | `agent/v2-9-8b-post-rollover-2-fresh-authoritative-window-15m-readiness-evidence-completion` |
| Required and inspected starting HEAD | `9b1f88ac143db2db690dfd53bc9130017762179a` |
| Starting commit message | `Audit post-rollover-2 fresh authoritative 15m readiness` |
| Linear issue | `DTW-14` |
| Tracked worktree | clean |
| Index | clean |
| Only untracked root | `operator-runs/v2-9-8b-authoritative-mig050/` |
| Current `WINDOW_15M` authorization packages | `0` |
| Retained migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| Report files created by this lane | exactly this report |
| Production/test changes | `0` |

The exact branch and HEAD matched before evidence work began. Tracked worktree
and index checks passed. The visible untracked set contained the ten
non-SQLite Migration-050 files, while the two retained SQLite evidence files
remained ignored and untracked under the same sole untracked root. No current
`WINDOW_15M` final-authorization package existed.

## 3. Controlling source-stack review

The active Printer V1 source stack and all three task-required audit/closeout
documents were read before hashing. The active-stack identities at the starting
HEAD were:

| File | SHA-256 |
| --- | --- |
| `AGENTS.md` | `d71bdf56518543c9c66bb419c917cf5dc421d61380bb3da8b756c06166af743e` |
| `docs/printer-v1-clean-master-spec.md` | `83d026c2a3ce6d35bd3b4cb67b72ff404a283ded86561597485109204c4cc657` |
| `docs/printer-v1-post-rc-build-order.md` | `c40c1533d1be579c3b07559cbcd58396205da73e674b0b6600beb1bf3cff67e2` |
| `docs/printer-v1-memory-factory-guide.md` | `1325d9bd126e526738e397ec2aee453de77705a15dbc469de048c49cbd4b740d` |
| `docs/printer-v1-current-state-memory-growth-audit.md` | `130d245008d75210f2610e158757b235b33f4737a929b9750e38beaba87edb81` |
| `docs/printer-v1-memory-growth-build-order-v2.md` | `c12f5dcbd8700ec50e0926d3dd14430839575a707c13cf836fc0373e3bc722c1` |
| `docs/printer-v1-python-builder-guide.md` | `1b1487040710d35e7e453254feaaeaca15adf346f9d356fe379c8899efaabe0f` |

The task-required procedural and historical sources were:

- `docs/printer-v1-v2-9-8b-window-15m-fresh-authoritative-readiness-audit.md`;
- `docs/printer-v1-v2-9-8b-post-rollover-2-fresh-authoritative-window-15m-campaign-readiness-audit.md`;
- `docs/printer-v1-v2-9-8b-window-15m-current-evidence-historical-rollover-independent-closeout-2.md`.

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active
memory-growth build order inside this source stack and is not the sole source
of truth. All Source Governor, Central Scheduler, one-shot, retrieval,
decision, and financial locks remain binding.

## 4. Why the prior PASS was held for review

The pushed readiness audit correctly freshly re-hashed the ten non-SQLite
Migration-050 files, but it did not freshly read the raw bytes of the two
retained SQLite evidence files. It instead reused their accepted prior hashes
when reconstructing the twelve-file identity listing.

That method supported an unchanged-package conclusion but did not prove that
the two SQLite evidence hashes themselves had been freshly calculated in the
post-rollover-2 readiness lane. The PASS was therefore held for review on this
single evidence-completeness gap. No broader readiness mismatch, database
identity mismatch, namespace collision, authorization collision, or capability
lock failure was identified.

## 5. Raw-file hashing method

The two retained SQLite evidence paths were handled only as ordinary filesystem
files:

1. filesystem inspection confirmed each path was a regular file and was not a
   symbolic link;
2. filesystem stat confirmed each exact byte size;
3. `shasum -a 256 <repository-relative-path>` read the raw file bytes and
   calculated each SHA-256;
4. no SQLite library, CLI, connection, query, or PRAGMA was used on either
   evidence file;
5. no copy, move, chmod, rewrite, touch, sidecar, or helper artifact was used.

For the complete package, all twelve regular files beneath the exact retained
execution root were enumerated, sorted bytewise by repository-relative path
under `LC_ALL=C`, and freshly passed to `shasum -a 256`. The reconstructed
listing used exactly:

```text
<64 lowercase hexadecimal SHA-256><two ASCII spaces><repository-relative path><LF>
```

The listing contains twelve lines and includes the final trailing newline. Its
raw bytes were themselves hashed with SHA-256. No listing file was created.

## 6. Fresh SQLite evidence-file proof

| Repository-relative path | Regular file | Symlink | Bytes | Fresh SHA-256 |
| --- | --- | --- | ---: | --- |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3` | yes | no | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3` | yes | no | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

Both exact expected identities were reproduced from fresh raw-byte reads.

## 7. All twelve freshly calculated file identities

| Repository-relative path | Bytes | Fresh SHA-256 |
| --- | ---: | --- |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json` | `50133` | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt` | `0` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json` | `13836` | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json` | `2384` | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3` | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json` | `6589` | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json` | `103903` | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json` | `36274` | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json` | `18590` | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json` | `16244` | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3` | `65654784` | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

Package inspection before and after hashing found exactly twelve files, zero
symlinks, and zero non-regular entries.

## 8. Exact reconstructed identity listing and digest

The freshly reconstructed, path-sorted listing was exactly:

```text
8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt
569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json
c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json
e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/disposable-restore/printer_v1-rehearsal.sqlite3
eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json
fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json
4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json
3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json
997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json
e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2  operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/verified-backup/printer_v1-pre050.sqlite3
```

| Listing property | Exact value |
| --- | --- |
| Line count | `12` |
| Sort | repository-relative path, bytewise `LC_ALL=C` |
| Separator | two ASCII spaces |
| Final newline | present |
| Fresh identity-listing SHA-256 | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` |
| Required identity-listing SHA-256 | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` |
| Match | yes |

## 9. Authoritative DB before/after reconciliation

The authoritative database identity was checked immediately before and after
the Migration-050 raw-file hashes. Its SHA-256 was calculated from ordinary raw
file bytes. The protected counters were checked separately through a minimal
strict read-only connection to the authoritative database only, using SQLite
URI `mode=ro&immutable=1` plus `PRAGMA query_only = ON`. Only the five exact
`COUNT(*)` reads shown below were performed; the broader readiness audit was not
rerun.

| Field | Before | After | Equal |
| --- | --- | --- | --- |
| Regular file | yes | yes | yes |
| Symlink | no | no | yes |
| Size | `65671168` | `65671168` | yes |
| SHA-256 | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` | `56ca1218442db1a571ba715794ba91b70c3bfeba242f21855275c026d4c8eed5` | yes |
| `mtime_ns` | `1785617072867102156` | `1785617072867102156` | yes |
| WAL | absent | absent | yes |
| SHM | absent | absent | yes |
| Journal | absent | absent | yes |

No authoritative database identity mismatch was found, so no broader database
readiness audit was run.

## 10. Namespace and evidence before/after reconciliation

| Field | Before | After | Equal |
| --- | ---: | ---: | --- |
| Tracked worktree changes | `0` | `0` | yes |
| Index changes | `0` | `0` | yes |
| Untracked roots | `1` | `1` | yes |
| Only untracked root | `operator-runs/v2-9-8b-authoritative-mig050/` | `operator-runs/v2-9-8b-authoritative-mig050/` | yes |
| Visible current Migration-050 files | `10` | `10` | yes |
| Ignored current Migration-050 files | `2` | `2` | yes |
| Total current Migration-050 files | `12` | `12` | yes |
| Migration-050 symlinks | `0` | `0` | yes |
| Migration-050 non-regular entries | `0` | `0` | yes |
| Current visible `WINDOW_15M` authorization files | `0` | `0` | yes |
| Current ignored `WINDOW_15M` authorization files | `0` | `0` | yes |
| Current `WINDOW_15M` authorization packages | `0` | `0` | yes |

All twelve evidence-file sizes, `mtime_ns` values, and `ctime_ns` values matched
before and after hashing. The freshly calculated content hashes matched the
accepted package identities. No evidence file changed.

The hashing and reconciliation created no new evidence file, SQLite sidecar,
identity-list file, manifest, marker, authorization, or application. No
Migration-050 rerun occurred. The only repository file created by the lane is
this required evidence-completion report.

## 11. Zero protected-capability activity

| Protected counter | Before | After | Activity |
| --- | ---: | ---: | ---: |
| `printer_paper_positions` | `0` | `0` | `0` |
| `printer_paper_trade_events` | `0` | `0` | `0` |
| `printer_paper_decision_audits` | `0` | `0` | `0` |
| `printer_paper_trade_audits` | `0` | `0` | `0` |
| `printer_memory_retrieval_matches` | `0` | `0` | `0` |

Additional protected activity remained zero:

- authorizations created or applied: `0`;
- wrapper or operational commands run: `0`;
- provider/source contacts: `0`;
- Source Governor starts: `0`;
- Central Scheduler starts: `0`;
- discovery or campaigns started: `0`;
- Migration-050 SQLite evidence connections/queries/PRAGMAs: `0`;
- authoritative SQLite read/write connections: `0`;
- authoritative SQLite mutations: `0`;
- memory records generated: `0`;
- retrieval or decision activations: `0`;
- BUY/SELL/HOLD decisions created: `0`;
- positions, trades, audits, or PnL created: `0`.

The only authoritative SQLite connections were the two minimal immutable
read-only protected-counter inspections described above.

## 12. Money-usefulness contribution

This proof prevents a scarce future one-shot authorization from resting on an
assumed evidence identity. It replaces the two inherited SQLite hash assertions
with fresh raw-byte proof while preserving the exact retained package, database,
and namespace.

That closes a reviewable provenance gap before the next authorization lane and
reduces the risk that stale or substituted migration evidence could invalidate a
future bounded collection attempt. It creates no market observation, clean
memory, decision, trade, or profit claim.

## 13. What this proof completes

- closes the single evidence gap in the pushed post-rollover-2 fresh
  authoritative readiness audit;
- freshly proves the size, regular-file/non-symlink status, and complete SHA-256
  of both retained Migration-050 SQLite evidence files;
- freshly proves all twelve Migration-050 content identities;
- reproduces the exact sorted identity listing and its accepted digest;
- proves DB, sidecar, namespace, evidence-metadata, authorization-count, and
  protected-counter stability before and after hashing;
- preserves the prior readiness audit's remaining accepted findings;
- makes the exact next final-authorization lane eligible for separate work.

## 14. What remains locked

This PASS does not create or apply a final authorization. It does not authorize:

- manifest or application-marker creation;
- wrapper application or operational-command execution;
- provider/source contact;
- Source Governor or Central Scheduler runtime;
- discovery or campaign execution;
- authoritative SQLite mutation;
- memory generation, retrieval activation, or decisions;
- BUY, SELL, HOLD, positions, trades, audits, or PnL;
- selective `WINDOW_1H` continuation or any longer window;
- wallets, private keys, real funds, live execution, or paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only. Printer remains Solana-only,
Solana-memecoin-only, paper-only, Source-Governed, and Central-Scheduler-led.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Completion disposition |
| --- | --- |
| Prior PASS reused two accepted SQLite hashes | Closed by fresh raw-byte hashing of both exact retained files |
| Raw-byte hashing might accidentally open SQLite | Prevented; ordinary file hashing only, with zero SQLite access to either evidence file |
| Hashing might alter evidence metadata or content | No change; all sizes, hashes, `mtime_ns`, and `ctime_ns` reconciled before/after |
| Identity-listing serialization drift | Closed; exact path sort, two-space separator, trailing newline, and digest reproduced |
| Authoritative DB drift | None; exact size, hash, `mtime_ns`, and absent sidecars matched before/after |
| Current authorization collision | None; current authorization count remained zero |
| Broader DB audit consumes effort or creates unintended scope | Avoided; no identity mismatch, so only minimal protected-counter reads were used |
| Natural source availability or clean-memory yield | Still unproven; belongs to a later separately authorized runtime lane |
| This report commit changes HEAD | Expected; the next authorization must bind the exact post-completion commit and branch |

## 16. Final decision

PASS criteria are satisfied:

- exact required baseline matched;
- both retained SQLite evidence files were freshly read as raw ordinary files;
- both exact size and SHA-256 requirements matched;
- all twelve Migration-050 identities were freshly calculated;
- the exact twelve-line listing digest matched;
- authoritative DB and sidecars were unchanged;
- evidence and namespace were unchanged;
- current `WINDOW_15M` authorization count remained zero;
- all protected counters and activities remained zero;
- no boundary was weakened and no broader readiness audit was rerun.

Final verdict:

`V2_9_8B_POST_ROLLOVER_2_FRESH_AUTHORITATIVE_WINDOW_15M_READINESS_EVIDENCE_COMPLETION_PASS`

## 17. Exact next lane

`V2-9.8B Post-Rollover-2 Fresh Exact-HEAD WINDOW_15M Final Authorization`

That next lane must bind the exact post-completion report commit and branch. It
remains separate work. This lane stops after committing this report and does not
create the authorization.
