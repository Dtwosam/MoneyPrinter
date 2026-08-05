# Printer V1 V2-9.8B WINDOW_15M Migration-050 Current-Evidence Index Restoration Closeout

## Verdict

`V2_9_8B_WINDOW_15M_MIGRATION_050_CURRENT_EVIDENCE_INDEX_RESTORATION_PASS`

This closeout restores the Migration-050 **current** evidence package to lawful
Git classification only. No authorization was created or consumed. No wrapper,
launcher, operational command, provider, discovery, Scheduler, campaign, or
memory action ran. The authoritative database was not opened with SQLite and was
not mutated. No evidence working-tree byte was modified, moved, or deleted.

## Baseline

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-retained-evidence-exactness-repair` |
| Required full HEAD | `7ad3860ceb7dafa0c9ccee242b70b6f1faea5240` |
| Tracked tree and index at start | clean |
| Restoration branch | `agent/v2-9-8b-window-15m-migration-050-current-evidence-index-restoration` |
| Active Printer / DB writer processes | none |
| Implementation | index-only `git rm --cached --` on ten exact paths |

## Root cause

Commit `aaac921` (*Repair WINDOW_15M A-to-Z deterministic readiness*) tracked ten
non-SQLite files inside the still-current Migration-050 evidence package:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`

The canonical Git-provenance validator
(`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`,
`_reconcile_evidence_sets`) correctly fails closed when any tracked file exists
inside a current evidence package root, with:

`current manifest file is tracked instead of untracked`

That classification made every fresh exact-HEAD WINDOW_15M authorization package
on descendant HEADs non-applicable at pre-marker validation, even when package
bytes and database identity were otherwise ready.

The two SQLite backup files under the same package were already ignored via
`*.sqlite3` and were never part of the defect.

## Exact ten-path scope

Index removals only (working-tree bytes and paths preserved):

1. `application_started.json`
2. `application_stderr.txt`
3. `application_stdout.txt`
4. `backup_restore_preflight.json`
5. `closeout_inputs.json`
6. `final_authorization.json`
7. `post_migration_proof.json`
8. `preauthorization_evidence.json`
9. `preflight.json`
10. `rollback_rehearsal.json`

Under package root:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`

Unchanged and still ignored:

* `disposable-restore/printer_v1-rehearsal.sqlite3`
* `verified-backup/printer_v1-pre050.sqlite3`

Not changed: `.gitignore`, `.gitattributes`, validator, wrapper, launcher,
operational command, production code, tests, schemas, migrations, source-stack
or build-order documents, authoritative DB, or any other `operator-runs/` path.

## Pre / post file identity

All twelve package files remained regular, non-symlink files at the same paths.
Sizes and SHA-256 digests are byte-identical before and after the index-only
operation.

| Path (relative to package root) | Size | SHA-256 | Bytes equal |
| --- | ---: | --- | --- |
| `application_started.json` | 50133 | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` | yes |
| `application_stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | yes |
| `application_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | yes |
| `backup_restore_preflight.json` | 13836 | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` | yes |
| `closeout_inputs.json` | 2384 | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` | yes |
| `final_authorization.json` | 6589 | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` | yes |
| `post_migration_proof.json` | 103903 | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` | yes |
| `preauthorization_evidence.json` | 36274 | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` | yes |
| `preflight.json` | 18590 | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` | yes |
| `rollback_rehearsal.json` | 16244 | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` | yes |
| `disposable-restore/printer_v1-rehearsal.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | yes |
| `verified-backup/printer_v1-pre050.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` | yes |

Modes remained `0644` for all twelve files.

## Pre / post Git classification

| Path (relative to package root) | Pre | Post |
| --- | --- | --- |
| ten named non-SQLite files | tracked | visible untracked |
| `disposable-restore/printer_v1-rehearsal.sqlite3` | ignored | ignored |
| `verified-backup/printer_v1-pre050.sqlite3` | ignored | ignored |

After index-only removal and before commit:

* exactly ten staged index deletions (those paths only);
* no working-tree diff for those paths;
* zero paths remaining in the index under the current Migration-050 execution root;
* the ten files present on disk as visible untracked.

## Evidence-set reconciliation

Post-restoration live Git classifications for the current Migration-050 package:

| Class | Count | Content |
| --- | ---: | --- |
| index-tracked under execution root | 0 | none |
| visible untracked under execution root | 10 | the ten restored non-SQLite files |
| ignored under execution root | 2 | the two SQLite backups |

Repository-wide visible untracked after restoration (pre-closeout only): exactly
those ten Migration-050 files. No other `operator-runs/` path was staged or
reclassified.

Historical tracked WINDOW_15M authorization packages under
`operator-runs/v2-9-8b-window-15m-final-authorization/` remain tracked history
outside the current Migration-050 package root and were not modified.

## Checks and exact results

| # | Check | Result |
| --- | --- | --- |
| 1 | Focused existing manifest / one-shot wrapper tests | `92 passed` in 8.38s (`tests/test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`, `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`) |
| 2 | Non-consuming pre-marker validation with disposable auth/application artifacts | **PASS** — disposable auth ID `V2_9_8B_WINDOW_15M_AUTH_DISPOSABLE_INDEX_RESTORATION_CHECK`; manifest allowed file count `13`; external staging manifest only; disposable package fully removed after check |
| 3 | Prior tracked-current-root failure gone for actual retained package | **PASS** — `git ls-tree HEAD` under current Migration-050 execution root returns empty; pre-marker no longer raises tracked-current-root for the retained package |
| 4 | Disposable tracked-current-root negative case still fails | **PASS** — re-adding one current-package path to the index fails closed (`launch Git tree has staged changes` / tracked-current-root family); index restored with `git rm --cached` only; existing focused suite also keeps pure tracked-inside-current-package negatives green |
| 5 | Missing / modified / extra / ignored-extra / symlink / non-regular fail-closed | covered by nearest existing focused suite; 92 passed; no production code change |
| 6 | Zero tracked files beneath current Migration-050 execution root | **PASS** |
| 7 | Ten files visible untracked | **PASS** |
| 8 | Two SQLite files ignored | **PASS** |
| 9 | Complete evidence-set reconciliation | **PASS** — disposable pre-marker prepared successfully against the restored branch tip after this commit |
| 10 | `git diff --check` | **PASS** on staged restoration set |
| 11 | Authoritative DB identity unchanged | **PASS** |

No full test suite ran. SQLite was not opened. No authorization was created or
applied. No wrapper, launcher, operational command, provider, discovery,
Scheduler, campaign, or memory ran. The disposable pre-marker auth/application
artifacts were removed after validation.

## Authoritative database identity

Recorded without SQLite open / without mutation:

| Field | Value |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| size | `68067328` |
| mtime_ns | `1785925095953652677` |
| inode | `1230526` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| WAL / SHM / journal | absent / absent / absent |

Identity is unchanged from the retained-evidence exactness repair closeout.

## Confirmation: no evidence byte changed

* `git rm --cached --` only; no working-tree delete or rewrite.
* All twelve package file sizes and SHA-256 digests match the pre-snapshot.
* The two ignored SQLite backups were not staged, untracked, opened, moved, or
  deleted.
* No other `operator-runs/` path was touched.

## Money-usefulness contribution

Restoring lawful untracked/ignored classification for the current Migration-050
package re-enables exact-set Git-provenance pre-marker validation for a future
one-use WINDOW_15M authorization. Without that classification, the operator
cannot lawfully bind and apply a fresh exact-HEAD authorization even when the
memory-activation repairs are complete. This is an evidence-index integrity fix,
not a trading or decision unlock.

## What remains locked

* No WINDOW_15M authorization, application, or campaign.
* No provider contact, discovery runtime, Scheduler runtime, or memory generation.
* Retrieval; paper decisions; BUY/SELL/HOLD; paper positions; trade events;
  paper-trade audits; PnL; wallets; private keys; signing; real funds; live
  execution; paid APIs; scoring; ranking; confidence; weighted logic;
  embeddings; vectors.
* Longer windows as production (`WINDOW_1H` / `4H` / `12H` / `24H`).
* Source Governor and Central Scheduler ownership unchanged.
* Automatic retry / rerun / resume / restart / successor remain forbidden for
  one-use WINDOW_15M law.

## Functionality Risks / Setbacks / Efficiency Blockers

* After this commit the ten files are untracked operational evidence. Future
  commits must not re-add them to the index while Migration-050 remains a
  current evidence package.
* Pre-marker validation still uses live HEAD + live untracked/ignored sets. Any
  later unrelated untracked file under `operator-runs/` outside the two current
  package roots will again block exact-set validation until archived or
  reconciled by an authorized lane.
* Historical tracked WINDOW_15M authorization packages remain on the branch as
  history; they are not current packages and must not be reused.
* This lane does not re-prove database migration content; it only restores index
  classification for the retained Migration-050 evidence package.

## Exact next step

A fresh one-use `WINDOW_15M` authorization on this restored HEAD that:

1. binds exact branch and full HEAD;
2. binds the current authoritative database identity;
3. creates exactly one untracked `final_authorization.json`;
4. validates the package with non-consuming canonical validators;
5. returns one ready-to-paste manual terminal command for the operator.

Do not create that authorization in this lane.

## Commit scope

Final staged set:

* ten index removals (the named Migration-050 non-SQLite files);
* this closeout document.

Commit message:

`Restore Migration-050 current evidence index state`
