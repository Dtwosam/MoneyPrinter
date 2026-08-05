# V2-9.8B — Post-Drift-Guard Fresh One-Use WINDOW_15M Authorization Closeout

Lane:
`V2-9.8B — Post-Drift-Guard Fresh One-Use WINDOW_15M Authorization`

Lane type: authorization packaging and independent review only.

No PowerShell launcher, application marker, child process, provider contact,
discovery run, Scheduler runtime, campaign, or memory generation was executed by
this lane. The authoritative database was not mutated.

## Verdicts

| Phase | Verdict |
| --- | --- |
| Creation | `V2_9_8B_POST_DRIFT_GUARD_WINDOW_15M_AUTHORIZATION_PASS` |
| Independent review | `V2_9_8B_POST_DRIFT_GUARD_WINDOW_15M_AUTHORIZATION_REVIEW_PASS` |

This package remains **unused**. It is ready for one future manual operator
invocation only after the operator re-validates live HEAD, clean tracked tree,
database identity, and unexpired status at application time.

## Exact baseline

| Item | Required / observed |
| --- | --- |
| Working tree | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Authorization branch | `agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard` |
| Authorization HEAD | `7a4152bb90b14317513bb10879ee3861410270c7` |
| HEAD subject | `Enforce package database binding before consumption` |
| Tracked / staged trees | Clean at package creation and at review |
| Relevant Printer processes | None (macOS PrintKit system processes ignored) |
| Active / locked Scheduler jobs | Zero (`SUCCEEDED` 1316 / `CANCELLED` 45 / `FAILED` 14) |
| Push | Not performed |

### Authoritative database (seven-field binding)

| Field | Value |
| --- | --- |
| path | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` |
| SHA-256 | `5cf5326c4a820538a2f648a274bf14797c23a988bfae0f25aa49f01205cfafdc` |
| size | `68009984` |
| inode | `1230526` |
| mtime_ns | `1785921369859239685` |
| migration_count | `52` |
| migration_head | `052_memory_observation_eligibility_layers.sql` |

Additional health facts bound in the package:

| Field | Value |
| --- | --- |
| integrity | `ok` |
| foreign_key_violations | `0` |
| journal / wal / shm | absent / absent / absent |
| opened_mode | `read_only_immutable` |
| mutated_by_authorization_lane | `false` |

Post-052 database state is proven by the Migration-052 closeout and backup
evidence, the seven-field binding above, and the `prepare` / `review` / wrapper /
child preflight guard chain. Migration-050 evidence is retained only for the
existing git-provenance manifest compatibility contract and does **not**
independently prove the post-052 database state.

## Package identity

| Field | Value |
| --- | --- |
| Authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z` |
| Package root | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z/` |
| Schema | `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2` |
| Authorization type | `V2_9_8B_POST_DRIFT_GUARD_WINDOW_15M_ONE_USE_AUTHORIZATION` |
| Package verdict | `V2_9_8B_POST_DRIFT_GUARD_WINDOW_15M_AUTHORIZATION_PASS` |
| `final_authorization.json` SHA-256 | `500b634619fe1ba59fca1db0dd805c03cab9a2d5a08ba469ff74ea239475256c` |
| Package bytes | `7944` |
| Nonce | `d1fd4876eb4b6f610d2bfcc6e017ab97` |
| Authorized at | `2026-08-05T10:12:48.555929Z` |
| Expires at | `2026-08-06T10:12:48.555929Z` |
| Validity | `86400` seconds |
| Expiry enforcement | `OPERATOR_ENFORCED_ONLY` |

Package files (not committed):

| File | Role |
| --- | --- |
| `final_authorization.json` | Canonical authorization document (mode `0444`) |
| `final_authorization.sha256` | Exact SHA-256 of the JSON bytes |
| `binding_inventory.json` | Bound identities inventory |
| `authorization_report.md` | Package-local authorization summary |
| `exact_manual_command.md` | Exact manual PowerShell command with path and hash |
| `consumed_on_start_rule.md` | Permanent consumed-on-start law |
| `stop_conditions.md` | Stop / fail-closed conditions |

External application directory at issuance and after review: **absent**

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z`

## Authorized Git

| Field | Value |
| --- | --- |
| Branch | `agent/v2-9-8b-pre-authorization-migration-ledger-drift-guard` |
| HEAD | `7a4152bb90b14317513bb10879ee3861410270c7` |
| Exact HEAD required | `true` |
| Tracked worktree must be clean | `true` |

## Command chain

Exact authorized chain:

1. `scripts/Start-PrinterV1-Window15M-OneShot.ps1`
2. `printer_v1.operator_cli.window_15m_one_shot_wrapper`
3. one child `printer_v1.operator_cli.operational_memory_factory_command` with
   `run --operator-approved`

### Launch-chain file hashes at packaging

| File | SHA-256 |
| --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | `e899ecc14b62b3b46e6344ee2e3358ec5a09b6c523bdcbc821a8d3a70d9854c1` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | `58b65975bf16f745250e7ec3491815d3f878dc984b693eec9d6cec20d9e73df1` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | `0b7de72a545f4baffb6ae5e9f09ab1aed0811ea0e3e63acf79392f65f2146cf4` |

Direct operational-command invocation and alternate launchers are forbidden.

## Campaign and capability law

| Field | Value |
| --- | --- |
| Main window | `WINDOW_15M` (`900` s) |
| Support-only window | `WINDOW_5M_MICRO_EVENT` |
| Total duration | `1200` s |
| Token capacity | `2` |
| Campaign / cycle count | `1` / `1` |
| Selective 1h continuation | `false` |
| Locked longer windows | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| Solana-only / memecoin-only / paper-only | `true` / `true` / `true` |
| Automatic retries | `0` |
| Retry / rerun / resume / restart / successor | all `false` |
| Allowed invocation count | `1` |

Capabilities remaining locked include retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, live wallets / private keys / real funds / live
execution, paid API dependency, embeddings/vectors/scoring/ranking/confidence,
concurrent or second execution, discovery-only substitutes, Source Governor
bypass, and Central Scheduler bypass.

Secret names only are recorded (`PRINTER_SOLANA_RPC_URL`,
`PRINTER_HELIUS_API_KEY`). No secret values, fragments, lengths, or digests are
recorded.

## One-use and expiry rules

* Authorization is permanently consumed when wrapper execution begins and the
  external application marker is created.
* Consumption is permanent regardless of PASS, block, safe-stop, interruption,
  or failure.
* No reuse, retry, rerun, resume, restart, recovery, automatic successor,
  concurrent execution, or second execution is authorized under this ID.
* Validity is 24 hours operator-enforced. The production wrapper does not read
  `expires_at`; the operator must refuse expired packages.

## Prior consumed authorization

`V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` remains permanently consumed.

| Evidence | Value |
| --- | --- |
| External application directory | present |
| Marker path | `~/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z/application-marker.json` |
| Consumed at | `2026-08-04T22:05:43.422196+00:00` |
| Package reuse | forbidden |

That authorization was archived out of the repository untracked set only so
pre-marker validation can see an exact current file set. Archival does not
restore or reauthorize it. The external application marker remains the permanent
consumption record.

## Migration-050 compatibility package

| Field | Value |
| --- | --- |
| Root | `operator-runs/v2-9-8b-authoritative-mig050` |
| Execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| File count | `12` |
| Listing digest | `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a` |
| Rerun authorized | `false` |

Used only for the existing manifest compatibility contract.

## Externally archived evidence

Unrelated untracked packages would have blocked exact pre-marker validation.
They were moved intact (never deleted or overwritten) to:

`/Users/Dtwo1/PrinterOperations/v2-9-8/pre-marker-evidence-archive-20260805T101200Z/`

Archive inventory manifest:

`/Users/Dtwo1/PrinterOperations/v2-9-8/pre-marker-evidence-archive-20260805T101200Z/ARCHIVE_MANIFEST.json`

### 1. Migration-052 operator package

| Field | Value |
| --- | --- |
| Source | `operator-runs/v2-9-8b-authoritative-mig052` |
| Archive path | `.../pre-marker-evidence-archive-20260805T101200Z/operator-runs/v2-9-8b-authoritative-mig052` |
| File count | `8` |
| Post-move hash verification | PASS (all 8 files) |

Notable archived hashes:

| Size | SHA-256 | File |
| ---: | --- | --- |
| 261 | `6af7b4a9b96a855c641e9b078278f510fa9068779ef83e864aa0701b48857f7f` | `.../application_stdout.txt` |
| 9514 | `1546f16f5961a866fbc88c91396f7ae1230e5f2b0dce66e0456fdba8b75bcda6` | `.../backup_restore_preflight.json` |
| 68009984 | `0ed2580429735109751e01ff174da192d0efdedfd2c7963d0cc87e61042be42c` | `.../disposable-restore/printer_v1-rehearsal.sqlite3` |
| 322 | `41f443d405fbd98eea5dd8ab57c19309ca3d7c946e459b6ee00bb7dba7c180d6` | `.../disposable_layer_proof.json` |
| 1334 | `0b5dbe4d46fc2c067a34ef0bad0fcd93565a3b32df60a09ee2fe03579a1b310f` | `.../post_migration_proof_part1.json` |
| 1740 | `afadf6bb310ffa5d4c54bfd16d0c2b1bf1244f6048ae8a5c936c94d07edbe761` | `.../post_migration_proof_part2.json` |
| 440672 | `a53ff4ab733186cec2ed4349b9681fd162aded8451ce16439abfcbe8f5f5d9cb` | `.../pre_migration_snapshot.json` |
| 67862528 | `a9c1472016dd1909df06897cc7e7257347f8af6d3f6927dc5cbc19dba21f6233` | `.../verified-backup/printer_v1-pre052.sqlite3` |

### 2. Consumed WINDOW_15M authorization package

| Field | Value |
| --- | --- |
| Source | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` |
| Archive path | `.../pre-marker-evidence-archive-20260805T101200Z/operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z` |
| File count | `7` |
| Post-move hash verification | PASS (all 7 files) |
| `final_authorization.json` SHA-256 | `0b3bd62dd912c7292c9dbb159def963f768e3c0e6e30b624ff90cfd3d420316e` |

After archival, the only untracked evidence packages visible for manifest
validation were the retained Migration-050 package and the new authorization
package.

## Pre-creation gates

| Gate | Result |
| --- | --- |
| Exact branch and HEAD | PASS |
| Tracked tree clean | PASS |
| No active Printer / operational work | PASS |
| Production guard `prepare` | PASS — `V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_PASS` at exact `52 / 052` |
| DB SHA-256 / size / inode / mtime_ns unchanged after prepare | PASS |
| Prior auth `…214901Z` permanently consumed | PASS |
| No application directory for new authorization ID | PASS |

## Independent review

Review was a separate operation after package creation. It did not call
`build_marker_bytes`, `apply_authorization_once`, the PowerShell launcher, or
the operational child.

| Check | Result |
| --- | --- |
| Production guard `review` against exact package | PASS — all seven binding fields honest |
| Recompute Git branch and HEAD | PASS |
| Recompute package bytes and SHA-256 | PASS (`500b634619fe1ba59fca1db0dd805c03cab9a2d5a08ba469ff74ea239475256c`) |
| Production `_resolve_authorization` | PASS |
| Launch-chain file hashes and command ownership | PASS |
| One-use, expiry, capability locks | PASS |
| Absence of secret values | PASS |
| No external application directory or marker | PASS |
| Database identity unchanged | PASS |
| Package remains unused | PASS |

### Pre-marker compatibility (missed by prior authorization review)

| Item | Result |
| --- | --- |
| `build_manifest_bytes` (no apply) | PASS |
| Temporary external manifest only | `/Users/Dtwo1/PrinterOperations/v2-9-8/post-drift-guard-window-15m-authorization-review-20260805T101248Z/git-provenance-manifest.pre-marker-review-only.json` |
| Temporary manifest SHA-256 | `5e74243ae6f6270c4f86fae0eee689533e8724d078f3a4c8d805464a5e21e52b` |
| `validate_git_provenance_manifest_pre_marker` | PASS |
| Prepared authorization ID | `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z` |
| Allowed-file-set digest | `4958dd88fa572553ca57e9400b0c363d2b545968eb82e70cda05dce03aea6c27` |
| Manifest file count | `19` |
| Application directory / canonical manifest / marker / terminal / child | none created |

Independent review artifacts (outside repository):

`/Users/Dtwo1/PrinterOperations/v2-9-8/post-drift-guard-window-15m-authorization-review-20260805T101248Z/`

## Proof the package remains unused

* No external application directory for `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z`
* No package-local `application-marker.json`, `git-provenance-manifest.json`,
  `wrapper-terminal.json`, or `application_started.json`
* Package field `authorization_consumed_by_this_lane` is `false`
* Review temporary manifest was written only outside the repository
* No child process, PowerShell launcher, or `apply_authorization_once` invocation

## Minimum proof executed

| Suite / check | Result |
| --- | --- |
| Focused migration-ledger guard suite | `57` tests — OK |
| Focused one-shot wrapper suite | `44` tests — OK |
| Production `prepare` | PASS |
| Production `review` | PASS |
| Production resolver | PASS |
| Production pre-marker manifest validation | PASS |
| `git diff --check` | clean |
| Broad suite / providers / runtime | not run |

## Exact future operator command (do not execute in this lane)

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z/final_authorization.json `
  -AuthorizationSha256 500b634619fe1ba59fca1db0dd805c03cab9a2d5a08ba469ff74ea239475256c `
  -OperatorApproved
```

Application-time prerequisites (operator responsibility):

1. Live branch and HEAD still equal the authorized binding.
2. Tracked trees remain clean.
3. Package unexpired under operator-enforced 24-hour validity.
4. Seven-field authoritative database identity unchanged.
5. Migration-050 retained package and this authorization package remain the only
   current untracked evidence packages for manifest validation.
6. No external application directory or marker already exists for this ID.
7. No active/locked Scheduler residue and no relevant Printer process.

## Money-usefulness contribution

This lane restores a usable one-shot path to a single paper-only two-token
`WINDOW_15M` clean-memory attempt **after** the migration-ledger drift guard is
in place. The previous authorization was permanently consumed for zero campaign
output because ledger drift was first discovered inside the child. This package:

* binds exact post-052 database identity (content + inode + mtime);
* requires `prepare`/`review` honesty before any future consumption;
* passes pre-marker provenance validation against the exact current file set;
* preserves one-use scarcity and all V1 capability locks.

It does not itself produce memory or trading signal. Its money value is
conserving the scarce authorization so a later operator-approved run can reach
useful collection instead of dying on a free structural question.

## What this improves

* Closes the post-drift-guard gap: a fresh authorization now exists on the exact
  guard implementation HEAD with a complete seven-field post-052 binding.
* Adds the pre-marker compatibility check that the previous authorization review
  missed, proving the package can clear git-provenance reconciliation without
  consuming itself.
* Archives unrelated untracked evidence intact so validation is exact without
  destroying history.

## What remains locked

* Actual wrapper application and child launch until the operator runs the command
* Provider/source contact and paid APIs until authorized child runtime
* Memory retrieval, paper decisions, BUY/SELL/HOLD
* Positions, trades, audits, and PnL
* Longer windows and continuous 4h
* Wallets, private keys, real funds, live execution
* Scoring, ranking, confidence, weighting, embeddings, and vectors
* Any retry/rerun/resume/restart/successor under this authorization ID
* Reuse of any prior consumed authorization

## Branch and commit policy

* Do **not** commit the authorization package on the authorized branch (that
  would move HEAD and invalidate the package).
* Closeout-only sibling branch:
  `agent/v2-9-8b-post-drift-guard-window-15m-authorization`
* Commit message: `Authorize post-drift-guard WINDOW_15M attempt`
* Not committed: authorization package files, database files, backups,
  application artifacts, archived operator evidence.
* Do not push unless explicitly instructed.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Operator-enforced expiry only.** The wrapper does not enforce `expires_at`.
   An expired package can still be applied if the operator ignores the 24-hour
   window.
2. **HEAD immobility.** Any commit on the authorized branch invalidates this
   package. Future product work must use sibling branches or a new authorization.
3. **Untracked evidence discipline.** Any extra untracked `operator-runs/` path
   will fail pre-marker validation and consume the authorization if the wrapper
   has already started staging after resolution. Keep only Migration-050 and this
   package visible at application time.
4. **Eligible supply and provider success are not guaranteed.** The package
   authorizes one attempt; clean memory is not promised.
5. **Migration-050 is compatibility evidence only.** It does not prove post-052
   DB state. Application still depends on the seven-field binding and live
   `review`-mode guard.
6. **Archived packages are outside the repository.** Operators must not treat the
   external archive as live reusable authorization or as a substitute for the
   retained Migration-050 package in-repo.
7. **Application still requires live re-checks.** Packaging PASS is not
   application PASS. Drift after packaging still blocks correctly, but only if
   the operator applies while bindings still match.

## Stop

Stop after the closeout commit. Do not launch the authorized attempt from this
lane.
