# Printer V1 V2-9.8B WINDOW_15M Fresh One-Use Authorization After Index Restoration Closeout

## Verdict

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_PASS`

This closeout authorizes exactly one manual ordinary `WINDOW_15M` campaign
attempt through the canonical one-shot wrapper on the restored Migration-050
evidence index state. It does **not** run, apply, or consume the authorization.
Codex did not execute the wrapper, launcher, operational Memory Factory command,
or any provider, discovery, Scheduler, campaign, or memory path.

## Baseline

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-migration-050-current-evidence-index-restoration` |
| Required full HEAD at start | `1706313de08717eff0434b9e956d67f54ad03db4` |
| Baseline commit subject | `Restore Migration-050 current evidence index state` |
| Authorization branch | `agent/v2-9-8b-window-15m-fresh-one-use-authorization-after-index-restoration` |
| Tracked tree and index at start | clean (only lawful Migration-050 untracked/ignored evidence) |
| Required retained-evidence repair ancestry | present (`c74fae4…`, `7ad3860…`) |
| Active Printer / campaign / discovery / Scheduler / factory / proof / DB-writer processes | none |
| Unresolved lock or application staging for this authorization | none at issuance |
| This closeout commit message | `Authorize one restored-head WINDOW_15M run` |

Exact-HEAD transaction:

1. This closeout document is committed alone.
2. The resulting full commit SHA becomes the authorized HEAD.
3. One new UTC authorization ID is generated after that commit.
4. Exactly one untracked package is written:

   `operator-runs/v2-9-8b-window-15m-final-authorization/<AUTHORIZATION_ID>/final_authorization.json`

5. The package binds that authorization commit, current DB identity, Migration-050
   evidence set, launch-chain identities, and one-use application law.
6. The commit is not amended or reset to absorb authorization bytes.

## Preauthorization gate

| # | Check | Result |
| --- | --- | --- |
| 1 | Prior `WINDOW_15M` authorizations reusable on this HEAD | **FAIL-closed / not reusable** — all prior IDs are consumed, incomplete, invalid, or bound to other HEADs/branches |
| 2 | Complete current evidence namespace reconcilable | **PASS** — Migration-050 package: 0 tracked, 10 visible untracked, 2 ignored; no unexpected visible/ignored evidence |
| 3 | Zero tracked files under current Migration-050 execution root | **PASS** |
| 4 | No unexpected visible or ignored evidence | **PASS** |
| 5 | All twelve Migration-050 retained files match expected size and SHA-256 | **PASS** (byte-identical to restoration closeout) |
| 6 | Authoritative DB readiness (integrity, FK, migrations, zero active residue) without mutation | **PASS** |
| 7 | Required environment variables present and structurally valid (values not printed) | **PASS** |
| 8 | Current launcher / wrapper / validator / operational command hashes recorded | **PASS** |
| 9 | No existing marker, application directory, or staging for the new authorization ID | **PASS** at issuance (ID generated after this commit) |
| 10 | Pre-authorization migration-ledger guard `prepare` | **PASS** |
| 11 | Providers contacted | **none** |

### Prior authorization disposition (not reusable)

| Authorization ID | Disposition |
| --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z` | consumed (application evidence present); other HEAD |
| `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` | other HEAD |
| `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260804T014448Z` | incomplete empty package directory |
| `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z` | other HEAD; external application directory exists |
| `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z` | other HEAD / other branch / other DB identity; external application directory exists |

None of the above bind baseline HEAD
`1706313de08717eff0434b9e956d67f54ad03db4` or this authorization branch tip.

## Migration-050 evidence reconciliation

Execution ID:

`V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Package root:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`

| Class | Count | Content |
| --- | ---: | --- |
| index-tracked under execution root | 0 | none |
| visible untracked under execution root | 10 | the ten non-SQLite evidence files |
| ignored under execution root | 2 | the two SQLite backups |

Listing digest (sorted repository-relative `shasum -a 256` lines):

`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`

All twelve files remain regular, non-symlink, mode `0644`, and byte-identical to
the Migration-050 current-evidence index restoration closeout:

| Path (relative to package root) | Size | SHA-256 |
| --- | ---: | --- |
| `application_started.json` | 50133 | `8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a` |
| `application_stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `application_stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `backup_restore_preflight.json` | 13836 | `569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083` |
| `closeout_inputs.json` | 2384 | `c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f` |
| `final_authorization.json` | 6589 | `eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835` |
| `post_migration_proof.json` | 103903 | `fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94` |
| `preauthorization_evidence.json` | 36274 | `4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c` |
| `preflight.json` | 18590 | `3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383` |
| `rollback_rehearsal.json` | 16244 | `997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149` |
| `disposable-restore/printer_v1-rehearsal.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |
| `verified-backup/printer_v1-pre050.sqlite3` | 65654784 | `e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2` |

Migration-050 must not be re-invoked.

## Authoritative database identity

Recorded with approved read-only readiness inspection only (no mutation):

| Field | Value |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| size | `68067328` |
| SHA-256 | `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb` |
| inode | `1230526` |
| mtime_ns | `1785925095953652677` |
| integrity | `ok` |
| foreign_key_violations | `0` |
| migration_count | `52` |
| migration_head | `052_memory_observation_eligibility_layers.sql` |
| WAL / SHM / journal | absent / absent / absent |
| non-terminal campaigns / runs / supervision | `0` / `0` / `0` |
| non-terminal scheduler jobs | `0` |
| locked scheduler jobs | `0` |
| non-terminal campaign scheduler work | `0` |
| mutated by authorization lane | `false` |

Identity matches the Migration-050 current-evidence index restoration closeout
and the retained-evidence exactness repair closeout.

The package `authoritative_database` binding uses exactly the canonical
`PACKAGE_BINDING_FIELDS` set required by the Git-provenance validator and
migration-ledger review gate:

`path`, `sha256`, `size`, `inode`, `mtime_ns`, `migration_count`, `migration_head`.

## Launch-chain identities

| File | Bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | 878 | `a7fd77e680fa48dff911982d1491462185b5699a` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | 45779 | `fc6a3682b3a0644743c9db5759aaff12ef1dcf3d` | `137a4fd695c5c519febb6dea9044378301793d33c4ceba4295fa848c5c7e452c` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | 36328 | `793f1e8105094825bdcaebb7465b976e2cbc118b` | `f4d7e7e46e5a65126a7a73470cf392ab8e7c98302fd695ba1deae944903722f2` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | 201722 | `1d7177567f6b35f524e24b1ff1a7f90a9ff523f6` | `b1c60a11943d59cb841c389be9fbeb05ad1457a0506fbfbdc8f33c8cb1d7183b` |

Accepted entry only:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

→ `printer_v1.operator_cli.window_15m_one_shot_wrapper`

→ one child `printer_v1.operator_cli.operational_memory_factory_command` with
`run --operator-approved`.

Direct operational-command invocation is forbidden. Alternate launchers are
forbidden. Manifest schema `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1` and marker
schema `PRINTER_V1_APPLICATION_MARKER_V1` are created only by the wrapper at
application time. This lane must not create them.

## Environment shape (values not recorded)

| Item | Result |
| --- | --- |
| `/Users/Dtwo1/.config/printer-v1/secrets.env` permissions | `0600` |
| `PRINTER_SOLANA_RPC_URL` | present, non-empty, structural URL shape |
| `PRINTER_HELIUS_API_KEY` | present, non-empty |
| Secret values / digests printed | **no** |
| Provider contacted during authorization | **no** |

## Authorization limits

Exactly one manual invocation is authorized with:

| Field | Value |
| --- | --- |
| mode | `run` |
| operator_approved | `true` |
| allowed_invocation_count | `1` |
| automatic_retry_allowed | `false` |
| manual_rerun_allowed | `false` |
| resume_allowed | `false` |
| restart_allowed | `false` |
| successor_allowed | `false` |
| main_window | `WINDOW_15M` only |
| support_only_window | `WINDOW_5M_MICRO_EVENT` |
| token_capacity | `2` |
| campaign_count / cycle_count | `1` / `1` |
| selective_1h_continuation | `false` |
| provider_rotation_allowed | `false` |
| locked windows | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| source_owner | `SOURCE_GOVERNOR` |
| scheduler_owner | `CENTRAL_SCHEDULER` |
| automatic_retries | `0` |

Keep disabled:

* retrieval;
* paper decisions;
* BUY / SELL / HOLD;
* paper positions;
* trade events;
* paper-trade audits;
* PnL;
* wallets, private keys, signing, real funds, and live execution;
* paid APIs;
* scoring, ranking, confidence, weighting, embeddings, and vectors.

## Consumption law

Authorization is permanently consumed when wrapper execution begins, regardless
of PASS, block, safe-stop, interruption, or failure.

* No reuse after start.
* No retry, rerun, resume, restart, or successor under the same ID.
* No concurrent or second execution.
* No discovery-only substitute.
* Wrapper creates external manifest and application marker; this lane must not.

## Package creation after this commit

After this closeout commit is created:

1. Resolve the full authorized HEAD (this commit).
2. Generate one new UTC authorization ID:

   `V2_9_8B_WINDOW_15M_AUTH_<YYYYMMDDTHHMMSSZ>`

3. Write exactly one untracked:

   `operator-runs/v2-9-8b-window-15m-final-authorization/<AUTHORIZATION_ID>/final_authorization.json`

4. Bind JSON to:

   * this branch and full authorized HEAD;
   * current DB identity (exact package binding fields);
   * Migration-050 execution and exact evidence set;
   * current launch-chain identities;
   * one-use application law above.

5. Validate the package without applying it (non-consuming).
6. Confirm no marker / staging remains for the new authorization ID.
7. Confirm DB and evidence identities are unchanged after packaging.
8. Confirm Codex neither ran nor consumed the authorization.

Schema:

`PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`

Authorization type:

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_INDEX_RESTORATION`

Package verdict field ends with `_PASS` and matches the closeout verdict family:

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_PASS`

## Exact manual command (operator only)

After packaging, the operator must run the following form with the actual path
and SHA-256 from the finished package (no placeholders):

```bash
cd "$HOME/Developer/MoneyPrinter"

pwsh -NoProfile \
  -File scripts/Start-PrinterV1-Window15M-OneShot.ps1 \
  -AuthorizationFile '<ACTUAL_AUTHORIZATION_FILE>' \
  -AuthorizationSha256 '<ACTUAL_64_CHARACTER_SHA256>' \
  -OperatorApproved
```

The operator must run that command manually. Codex must not execute it.

At application time:

* live branch and full HEAD must match the package binding;
* tracked worktree and index must be clean;
* Migration-050 and this authorization package must remain the only current
  evidence package roots required by Git-provenance reconciliation;
* external application directory and marker for this ID must still be absent
  before the wrapper creates them.

## What this lane did not do

* wrapper or launcher execution;
* `apply_authorization_once`;
* operational Memory Factory command execution;
* authorization consumption;
* application marker or external application staging retained for the new ID;
* provider, API, RPC, or WebSocket contact;
* discovery, Scheduler runtime, campaign, lifecycle, or memory generation;
* code, test, schema, migration, validator, wrapper, or command changes;
* repair, review, bounded proof, or another design lane;
* DB mutation;
* retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Remaining locks and risks

* One-use law: a blocked or failed wrapper start still consumes the package.
* Exact HEAD binding: any later commit invalidates this package.
* Exact DB binding: any DB rewrite, even same-byte replace with new
  inode/mtime, invalidates the package.
* Exact evidence binding: re-tracking Migration-050 files, adding unexpected
  untracked `operator-runs/` files, or altering retained evidence bytes blocks
  pre-marker validation.
* Launch-chain drift after packaging invalidates the accepted chain binding.
* Temporal validity is enforced before consumption (`authorized_at` /
  `expires_at` / max 86400s); expired packages must not be applied.
* Historical tracked authorization packages remain repository history and must
  not be reused.
* This authorization does not guarantee clean memory, eligible two-token supply,
  provider success, or memory PASS. Exit code zero is not automatically a memory
  PASS.

## Money-usefulness contribution

A lawful exact-HEAD one-use `WINDOW_15M` authorization is the only remaining
operator gate between restored Migration-050 evidence integrity and one governed
memory-growth campaign attempt under Source Governor and Central Scheduler
ownership. Without this package, the operator cannot lawfully start the
canonical one-shot wrapper on the restored evidence state.

## Exact next step

Operator-only manual application of the finished package via the command above.
No second authorization, no automatic retry, and no Codex execution.
