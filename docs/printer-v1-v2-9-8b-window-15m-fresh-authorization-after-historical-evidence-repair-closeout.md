# Printer V1 V2-9.8B WINDOW_15M Fresh One-Use Authorization After Historical Evidence Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_HISTORICAL_EVIDENCE_REPAIR_PASS`

This closeout authorizes exactly one manual ordinary `WINDOW_15M` campaign
attempt through the canonical one-shot wrapper after the historical
authorization evidence contract (Manifest V2 + approved-ID trust root) and the
boundary follow-up repair. It does **not** run, apply, or consume the
authorization. Codex did not execute the wrapper, launcher, operational Memory
Factory command, or any provider, discovery, Scheduler, campaign, or memory
path.

This lane combines the minimum mandatory non-consuming readiness checks with
authorization preparation. It is not a separate readiness-only lane.

## Baseline

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-historical-authorization-boundary-followup-repair` |
| Required full HEAD at start | `244511b7d0e028bacd0aa75a741c38a11cede13c` |
| Baseline commit subject | `Repair authorization preparation and blocker boundaries` |
| Authorization branch | `agent/v2-9-8b-window-15m-fresh-authorization-after-historical-evidence-repair` |
| Tracked tree and index at start | clean (only lawful untracked Migration-050 and two prior authorization packages) |
| Required repair ancestry | historical evidence contract implementation + boundary follow-up repair at `244511b7…` |
| Active Printer / campaign / discovery / Scheduler / factory / proof / DB-writer processes | none (macOS PrintKit system processes only; not MoneyPrinter) |
| Unresolved lock or application staging for **this** new authorization | none at issuance |
| This closeout commit message | `Authorize one WINDOW_15M run after historical evidence repair` |

Exact-HEAD transaction:

1. This closeout document is committed alone.
2. The resulting full commit SHA becomes the authorized HEAD.
3. One new UTC authorization ID is generated after that commit.
4. Exactly one untracked package is written:

   `operator-runs/v2-9-8b-window-15m-final-authorization/<AUTHORIZATION_ID>/final_authorization.json`

5. The package binds that authorization commit, current DB identity, Migration-050
   evidence set, Manifest V2 / Marker V1 law, historical trust-root IDs,
   launch-chain identities, and one-use marker-based consumption law.
6. The commit is not amended or reset to absorb authorization bytes.
7. Production non-consuming `prepare_git_provenance_authorization_parity` must
   PASS after packaging (reported with package identity in the operator
   response). Preparation PASS is not campaign success or memory readiness.

## Permanently non-reusable prior authorizations

These packages must not be edited, deleted, moved, renamed, regenerated, or
reused:

| Authorization ID | Disposition |
| --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` | `PERMANENTLY_CONSUMED_PRESERVED` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` | `BLOCKED_UNCONSUMED_SUPERSEDED` |

### Exact trust-root field required on the new package

```json
"prior_authorizations_non_reusable": [
  "V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z",
  "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z"
]
```

Only these two IDs contribute untracked historical evidence (`H`). Older
authorization directories under the package root are **tracked** historical
paths (`T`) and do not require trust-root entries. The empty directory
`V2_9_8B_WINDOW_15M_AUTH_20260804T014448Z` has no regular files and does not
require a trust-root entry. No unknown non-empty untracked authorization
directory was discovered.

Historical package file identities (unchanged; not edited):

| Authorization ID | `final_authorization.json` SHA-256 |
| --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` | `c928f9588f5c82b350f71d0df40c4cb3a7e2a92fd366541f109488edbc17dcea` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` | `d58e354a2d01acc0c893ff20941055cd4cf5fb86e2b4daf889b0e8312db90e59` |

## Minimum non-consuming gates

| # | Check | Result |
| --- | --- | --- |
| 1 | Live branch exact at start | **PASS** — baseline branch tip |
| 2 | Live HEAD exactly `244511b7d0e028bacd0aa75a741c38a11cede13c` at start | **PASS** |
| 3 | Tracked tree and index clean; tip matches `origin` | **PASS** |
| 4 | No unexpected submodule or tracked-file drift | **PASS** |
| 5 | Manifest V2 active (`PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2`) | **PASS** |
| 6 | Marker V1 remains active (`PRINTER_V1_APPLICATION_MARKER_V1`) | **PASS** |
| 7 | `prior_authorizations_non_reusable` required and validated | **PASS** (production owner) |
| 8 | `enumerate_historical_authorization_evidence` uses approved IDs only | **PASS** |
| 9 | Unlisted non-empty authorization packages block | **PASS** (law active) |
| 10 | Reconciliation `F = T ∪ M ∪ H`; current package equality `C = M`; allowlist `M ∪ H` | **PASS** |
| 11 | Marker creation remains the consumption boundary; pre-marker cleanup preserves original blocker | **PASS** |
| 12 | Authoritative DB integrity `ok`, FK `0`, no sidecars, active residue zero | **PASS** |
| 13 | Required env vars present and structurally valid (values not printed) | **PASS** |
| 14 | Source configuration validates | **PASS** |
| 15 | Repository `.venv` interpreter valid | **PASS** |
| 16 | Migration-ledger prepare + review PASS against measured DB identity | **PASS** |
| 17 | Concrete `WINDOW_15M` composition preflight (zero provider I/O) | **PASS** — status `READY`, `external_requests=0`, `database_writes=0` |
| 18 | Source Governor and Central Scheduler ownership intact | **PASS** |
| 19 | Retrieval / financial capabilities remain locked | **PASS** |
| 20 | Staging residue for superseded auth inspected read-only; no canonical marker | **PASS** (see below) |
| 21 | No wrapper execution; no application marker creation; no provider contact in this lane | **PASS** |

## Authoritative database identity

Remeasured read-only (not blindly reused). Absolute path:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

| Field | Value |
| --- | --- |
| size | `68366336` |
| SHA-256 | `5612556ce62074327524533ee8932203be129f19843afe4052da7dbb2f756e64` |
| inode | `1230526` |
| mtime_ns | `1785970388921155893` |
| migration_count | `52` |
| migration_head | `052_memory_observation_eligibility_layers.sql` |
| integrity | `ok` |
| foreign_key_violations | `0` |
| WAL / SHM / journal | absent / absent / absent |
| non-terminal campaigns | `0` |
| non-terminal campaign runs | `0` |
| non-terminal supervision | `0` |
| non-terminal scheduler jobs | `0` |
| locked scheduler jobs | `0` |
| non-terminal campaign scheduler work | `0` |
| non-terminal discovery work | `0` |
| active unreleased leases | `0` |
| non-terminal factory runs | `0` |
| identity vs last-known repair closeout | **unchanged** (size/SHA/inode/migrations match) |
| mutated by this lane | `false` |

Package binding uses exactly `PACKAGE_BINDING_FIELDS`:

`path`, `sha256`, `size`, `inode`, `mtime_ns`, `migration_count`, `migration_head`.

## Migration-050 evidence

Execution ID:

`V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

Package root:

`operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/`

| Class | Count |
| --- | ---: |
| index-tracked under execution root | 0 |
| visible untracked under execution root | 10 |
| ignored under execution root (SQLite backups) | 2 |
| total regular files | 12 |

Listing digest (sorted repository-relative `shasum -a 256` lines):

`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`

Migration-050 must not be re-invoked.

## Staging-residue inspection (read-only)

Root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/`

Directories associated with `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z`:

### 1. `…/V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9`

| Entry | Regular file | Size | SHA-256 |
| --- | --- | ---: | --- |
| `git-provenance-manifest.json` | yes | 4777 | `d010dc1b2e7f8d220cb81aefd2f8474d7b35de1cc4618f8daa2675ee8ff1d9a1` |

### 2. `…/V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba`

| Entry | Regular file | Size | SHA-256 |
| --- | --- | ---: | --- |
| `git-provenance-manifest.json` | yes | 4777 | `47d76219c47e4dbe77d2901f089b3fc4604c6cd3835841188cfb479ca82ead04` |

| Check | Result |
| --- | --- |
| Canonical application directory for `…005252Z` | **absent** |
| Application marker outside staging for `…005252Z` | **absent** |
| Residue establishes consumption | **no** (pre-marker block residue only) |
| Residue modified by this lane | **no** (read-only inspection) |

Canonical marker for the **consumed** prior auth
`V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` remains present under the external
application root and is consistent with `PERMANENTLY_CONSUMED_PRESERVED`.

A canonical marker for the superseded unconsumed auth `…005252Z` would be a
blocker; none exists.

## Launch-chain identities (current HEAD `244511b7…` tree; re-hash after packaging still required against live files)

| File | Bytes | Git blob | SHA-256 |
| --- | ---: | --- | --- |
| `scripts/Start-PrinterV1-Window15M-OneShot.ps1` | 878 | `a7fd77e680fa48dff911982d1491462185b5699a` | `524c6332d0952b3959a8136140bc9e1a98acd54f486d88d70910dd537a496d4f` |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | 67349 | `1440083f92f7d24e6de84e25141913126882c1b7` | `9057d9cc67f478ec988348aaa00fae2b95c63b44fba5ad12c89fa6ed98cd6110` |
| `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py` | 43082 | `ef482a12f2e6203d1c097854e4f0ebbdf0d0439c` | `27ae0ddd67a3795acf59d476a22c627d3211e189474d57832f6eafccc9649e0f` |
| `src/printer_v1/operator_cli/window_15m_authorization_preparation.py` | 11352 | `4fca03acedf902a2c335412026acb4a1e6cbc4a1` | `aa0997bac41987617ff1c1b9db0ab534b0b9f57d65f89a49676d385d8b952632` |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | 201722 | `1d7177567f6b35f524e24b1ff1a7f90a9ff523f6` | `b1c60a11943d59cb841c389be9fbeb05ad1457a0506fbfbdc8f33c8cb1d7183b` |

Accepted entry only:

`scripts/Start-PrinterV1-Window15M-OneShot.ps1`

→ `printer_v1.operator_cli.window_15m_one_shot_wrapper`

→ one child `printer_v1.operator_cli.operational_memory_factory_command` with
`run --operator-approved`.

Direct operational-command invocation is forbidden. Alternate launchers are
forbidden. Manifest schema `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2` and marker
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
| Source configuration validation | **PASS** |
| Composition preflight external_requests | `0` |
| Composition preflight database_writes | `0` |

## Authorized scope

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
| concurrent_execution_allowed | `false` |
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

## Consumption law

```text
consumed_when = create_once_application_marker_successfully_written
pre_marker_block_consumes_authorization = false
wrapper_process_start_consumes_authorization = false
permanently_non_reusable_after_marker = true
```

- Marker creation is the consumption boundary.
- Any failure **after** marker creation permanently consumes the authorization.
- A pre-marker block leaves the authorization technically unconsumed; do **not**
  automatically retry. Stop for inspection.
- No reuse, retry, rerun, resume, restart, successor, concurrent, or second
  execution under the same ID after marker creation.
- Wrapper creates external Manifest V2 and application marker; this lane must not.

## Capabilities that remain locked

Keep disabled:

* retrieval;
* dirty-memory use;
* paper decisions;
* BUY / SELL / HOLD;
* paper positions;
* trade events;
* paper-trade audits;
* PnL;
* wallets, private keys, signing, real funds, and live execution;
* paid APIs;
* scoring, ranking, confidence, weighting, embeddings, and vectors;
* automatic retry, rerun, resume, restart, or successor;
* concurrent or second execution;
* discovery-only substitutes;
* `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H`;
* Source Governor bypass;
* Central Scheduler bypass.

## Package creation after this commit

After this closeout commit is created:

1. Resolve the full authorized HEAD (this commit).
2. Generate one new UTC authorization ID:

   `V2_9_8B_WINDOW_15M_AUTH_<YYYYMMDDTHHMMSSZ>`

3. Write exactly one untracked:

   `operator-runs/v2-9-8b-window-15m-final-authorization/<AUTHORIZATION_ID>/final_authorization.json`

4. Bind JSON to:

   * authorization branch and full authorized HEAD;
   * freshly measured authoritative DB identity;
   * Migration-050 evidence;
   * Manifest V2 / Marker V1;
   * exact historical trust-root IDs above;
   * current launcher, wrapper, validator, preparation, and operational-command hashes;
   * one-use marker-based consumption law;
   * explicit expiry/TTL (max 86400s).

5. Run production `prepare_git_provenance_authorization_parity` and require:

   ```text
   inventory_pre_marker_parity_PASS = true
   full_apply_readiness_PASS = false
   marker_created = false
   canonical_application_directory_created = false
   child_launched = false
   ```

6. Confirm use count remains zero; no marker; no canonical application directory
   for the new ID; no provider/discovery/Scheduler/campaign/memory path; DB and
   historical packages and staging residue unchanged.
7. Confirm Codex neither ran nor consumed the authorization.

Schema:

`PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`

Authorization type:

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_HISTORICAL_EVIDENCE_REPAIR`

Package verdict field:

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_HISTORICAL_EVIDENCE_REPAIR_PASS`

## Exact manual operator command

After packaging, the operator must run the following form with the actual path
and SHA-256 from the finished package (no placeholders):

```bash
cd "$HOME/Developer/MoneyPrinter"

pwsh -NoProfile \
  -File scripts/Start-PrinterV1-Window15M-OneShot.ps1 \
  -AuthorizationFile '<ACTUAL_AUTHORIZATION_PATH>' \
  -AuthorizationSha256 '<ACTUAL_SHA256>' \
  -OperatorApproved
```

The operator must run that command manually. Codex must not execute it.

At application time:

* live branch and full HEAD must match the package binding;
* tracked worktree and index must be clean;
* Migration-050 and this authorization package must remain the only current
  evidence package roots required by Git-provenance reconciliation;
* approved historical packages must remain byte-identical and listed in
  `prior_authorizations_non_reusable`;
* external application directory and marker for this ID must still be absent
  before the wrapper creates them.

## What this authorization permits

* one manual ordinary `WINDOW_15M` campaign attempt;
* two token slots;
* `WINDOW_5M_MICRO_EVENT` support-only (cannot unlock decisions, memory
  outcomes, PnL, positions, or retrieval);
* Source Governor ownership of sources;
* Central Scheduler ownership of scheduling;
* paper-only memory-growth campaign under the existing locked capability set.

## What this authorization does not unlock

* retrieval, dirty memory, paper decisions, BUY/SELL/HOLD, positions, trades,
  audits, or PnL;
* wallets, private keys, signing, real funds, or live execution;
* paid APIs, scoring, ranking, confidence, weighting, embeddings, or vectors;
* automatic retry, manual rerun, resume, restart, or successor;
* provider rotation after failure;
* longer main windows (`WINDOW_1H` / `4H` / `12H` / `WINDOW_24H`);
* Source Governor or Central Scheduler bypass;
* reuse of any prior authorization ID;
* campaign success or clean-memory guarantee from preparation-parity PASS.

## Money-usefulness contribution

A lawful exact-HEAD one-use `WINDOW_15M` authorization is the operator gate
between the repaired historical-evidence boundary and one governed memory-growth
campaign attempt under Source Governor and Central Scheduler ownership. Without
this package, the operator cannot lawfully start the canonical one-shot wrapper
on the post-repair HEAD while preserving untracked prior authorization evidence.

## Functionality Risks / Setbacks / Efficiency Blockers

* Marker-based one-use law: any post-marker failure permanently consumes the package.
* Pre-marker block does not consume, but automatic retry is forbidden; inspect first.
* Exact HEAD binding: any later commit invalidates this package.
* Exact DB binding: any DB rewrite, even same-byte replace with new
  inode/mtime, invalidates the package.
* Exact evidence binding: altering Migration-050 or historical trust-root package
  bytes, or adding unlisted non-empty authorization packages, blocks pre-marker
  validation.
* Staging residue for `…005252Z` is preserved; it must not be mistaken for
  consumption of that superseded ID.
* Temporal validity is enforced before consumption (`authorized_at` /
  `expires_at` / max 86400s); expired packages must not be applied.
* Preparation-parity PASS is mandatory and is **not** campaign success or memory
  readiness (`full_apply_readiness_PASS` remains false until real application).
* This authorization does not guarantee clean memory, eligible two-token supply,
  provider success, or memory PASS. Exit code zero is not automatically a memory
  PASS.

## What this lane did not do

* wrapper or launcher execution against the live repository for consumption;
* `apply_authorization_once` for a real campaign;
* operational Memory Factory command execution;
* authorization consumption;
* application marker or canonical application directory for the new ID;
* provider, API, RPC, or WebSocket contact for campaign work;
* discovery, Scheduler runtime, campaign, lifecycle, or memory generation;
* production code, test, schema, migration, validator, wrapper, or command changes;
* DB mutation;
* mutation, deletion, rename, or reuse of prior authorization packages;
* mutation of old staging residue;
* retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Exact next step

1. Commit this closeout.
2. Package one untracked authorization bound to the post-closeout HEAD.
3. Run production preparation-parity (non-consuming).
4. Operator-only manual application via the command form above with actual path
   and SHA-256. No second authorization, no automatic retry, and no Codex
   execution of the wrapper.
