# Printer V1 V2-9.8B WINDOW_15M Fresh One-Use Authorization After Source-Request Scope Enforcement Closeout

## Verdict

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_SOURCE_REQUEST_SCOPE_ENFORCEMENT_PASS`

This closeout authorizes exactly one manual ordinary `WINDOW_15M` campaign
attempt through the canonical one-shot wrapper after the source-request scope
ownership repair, the enforcement follow-up, and independent inspection. It does
**not** run, apply, or consume the authorization. Codex did not execute the
wrapper, launcher, operational Memory Factory command, or any provider,
discovery, Scheduler, campaign, or memory path.

This lane combines the minimum mandatory non-consuming readiness checks with
authorization preparation. It is not a separate readiness-only lane.

## Baseline

| Item | Value |
| --- | --- |
| Required baseline branch | `agent/v2-9-8b-window-15m-source-request-scope-enforcement-independent-inspection` |
| Required full HEAD at start | `327ad27d2c8df6a4818af13752fb7bb419116d07` |
| Baseline commit subject | `Inspect source request scope enforcement follow-up` |
| Authorization branch | `agent/v2-9-8b-window-15m-fresh-authorization-after-source-request-scope-enforcement` |
| Tracked tree and index at start | clean (only lawful untracked Migration-050 and four prior authorization packages) |
| Local tip equals remote inspection tip | **yes** (`327ad27d…`) |
| Active Printer / campaign / discovery / Scheduler / factory / proof / DB-writer processes | none |
| Unresolved lock or application staging for **this** new authorization | none at issuance |
| This closeout commit message | `Authorize one WINDOW_15M run after source request scope enforcement` |

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

The final branch tip and authorization package identity are reported externally
after this commit. This document does not embed a self-referential final commit
SHA or a not-yet-created authorization package ID.

## Permanently non-reusable prior authorizations

These packages must not be edited, deleted, moved, renamed, regenerated, or
reused:

| Authorization ID | Disposition |
| --- | --- |
| `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z` | `PERMANENTLY_CONSUMED_PRESERVED` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z` | `BLOCKED_UNCONSUMED_SUPERSEDED` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z` | `CONSUMED_CHILD_EXITED_NONZERO` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` | `CONSUMED_CHILD_EXITED_NONZERO` |

### Exact trust-root field required on the new package

```json
"prior_authorizations_non_reusable": [
  "V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z",
  "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z",
  "V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z",
  "V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z"
]
```

Only these four IDs contribute untracked historical evidence (`H`). Older
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
| `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z` | `5cfa2c67bef94b16427cdf2cf426a38bf0543aaa328a2d095c2d85fa5e10a74c` |
| `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z` | `2648cb962cd87ef15a02a9247294ae3df0ce17996054a74ce16c73cffe0e545f` |

## Source-request scope enforcement findings (static)

Confirmed on baseline HEAD `327ad27d…` (includes prior repair ancestry through
independent inspection):

| Check | Result |
| --- | --- |
| Public permanent path constructs `CampaignSourceRequestScope` | **PASS** |
| Canonical root `v2-9-8b-window15m-<execution_id>` | **PASS** |
| Discovery and front-door prefixes forced to the same root | **PASS** |
| Collision inspection before provider work | **PASS** |
| Scoped reconciliation requires valid typed scope | **PASS** (fail-closed; no silent `scope_obj = None`) |
| Scoped prefix lookup uses exactly the canonical root | **PASS** (`prefixes = [root]`) |
| Known-ID and prefix-derived rows both root-filtered | **PASS** |
| Foreign durable stage requests remain `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE` | **PASS** |
| Source-specific temporal validation remains present | **PASS** (`_require_positive_graduation_epoch`, `type(...) is int`) |

Independent inspection verdict:

`V2_9_8B_WINDOW_15M_SOURCE_REQUEST_SCOPE_ENFORCEMENT_INDEPENDENT_INSPECTION_PASS`

## Minimum non-consuming gates

| # | Check | Result |
| --- | --- | --- |
| 1 | Live branch exact at start | **PASS** — inspection branch tip |
| 2 | Live HEAD exactly `327ad27d2c8df6a4818af13752fb7bb419116d07` at start | **PASS** |
| 3 | Tracked tree and index clean; tip matches `origin` | **PASS** |
| 4 | No unexpected submodule or tracked-file drift | **PASS** |
| 5 | Manifest V2 active (`PRINTER_V1_GIT_PROVENANCE_MANIFEST_V2`) | **PASS** |
| 6 | Marker V1 remains active (`PRINTER_V1_APPLICATION_MARKER_V1`) | **PASS** |
| 7 | Marker creation remains the consumption boundary | **PASS** |
| 8 | Pre-marker failures remain non-consuming | **PASS** |
| 9 | No automatic retry / rerun / resume / restart / successor | **PASS** |
| 10 | `prior_authorizations_non_reusable` exact four-ID trust root | **PASS** (required on package) |
| 11 | Unlisted non-empty authorization packages would block | **PASS** (law active) |
| 12 | Authoritative DB integrity `ok`, FK `0`, no sidecars, active residue zero | **PASS** |
| 13 | Required env vars present and structurally valid (values not printed) | **PASS** |
| 14 | Repository `.venv` interpreter valid | **PASS** |
| 15 | Migration-ledger prepare PASS against measured DB identity | **PASS** — `V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_PASS` |
| 16 | Concrete `WINDOW_15M` composition preflight (zero provider I/O) | **PASS** — status `READY`, `external_requests=0`, `database_writes=0`, `builder_count=20` |
| 17 | Source Governor and Central Scheduler ownership intact | **PASS** |
| 18 | Retrieval / financial capabilities remain locked | **PASS** |
| 19 | Staging residue and prior application evidence inspected read-only | **PASS** |
| 20 | No wrapper execution; no application marker creation; no provider contact in this lane | **PASS** |

## Authoritative database identity

Remeasured read-only (not blindly reused). Absolute path:

`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`

| Field | Value |
| --- | --- |
| size | `69046272` |
| SHA-256 | `0b4b2b40c817bfd09a796686a898ef1c788d438b412ef6aa789ce6596c2c7b80` |
| inode | `1230526` |
| mtime_ns | `1786017804315875344` |
| migration_count | `52` |
| migration_head | `052_memory_observation_eligibility_layers.sql` |
| integrity | `ok` |
| foreign_key_violations | `0` |
| WAL / SHM / journal | absent / absent / absent |
| non-terminal campaigns | `0` (only `TERMINAL_COMPLETED` / `TERMINAL_FAILED`) |
| non-terminal campaign runs | `0` |
| non-terminal supervision | `0` (all `TERMINAL`) |
| non-terminal scheduler jobs | `0` (`SUCCEEDED` / `FAILED` / `CANCELLED` only) |
| locked scheduler jobs | `0` |
| active unreleased leases | `0` (all `TERMINAL`) |
| non-terminal discovery work | `0` (`SUCCEEDED` / `FAILED` only) |
| non-terminal factory runs | `0` (`COMPLETED` / `SAFE_STOPPED` only) |
| identity vs post-`…115911Z` failure closeout expectation | **exact match** |
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
| total regular files | 12 |

Listing digest (sorted repository-relative `shasum -a 256` lines):

`08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`

Migration-050 must not be re-invoked.

## Historical authorization and application evidence inventory

### Repository package root

`operator-runs/v2-9-8b-window-15m-final-authorization/`

Untracked non-empty authorization directories (exactly the trust root):

* `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z/`
* `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z/`
* `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z/`
* `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z/`

No unknown non-empty untracked authorization directory was found.

### External application root

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications`

| Authorization ID | Canonical application directory | Marker present | Notes |
| --- | --- | --- | --- |
| `…224959Z` | present | yes | preserved consumed |
| `…005252Z` | **absent** | no | pre-marker staging residue only |
| `…103951Z` | present | yes | `CONSUMED_CHILD_EXITED_NONZERO` |
| `…115911Z` | present | yes | `CONSUMED_CHILD_EXITED_NONZERO` (scope contamination incident) |

Consumed application evidence for `…115911Z` (present; not modified):

| File | SHA-256 |
| --- | --- |
| `application-marker.json` | `7c39f88e458135cde898fa7b380c0de3b7eb18cb629ef9b5086c6ca9b9c9b48d` |
| `git-provenance-manifest.json` | `bad5ff883e2ab5e604f2ed682dcf3abdb1d2b87c26fd831ae8a7eab7b3b1491e` |
| `wrapper-terminal.json` | `b272523950892466256c241d30bf97caec0bc893353ed825f76e09570e39f3e3` |
| `child-stderr.txt` | `60a6946b0f6b798d1d607a96baba5062d7892628339318cb725392e8fd163f00` |
| `child-stdout.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Failed-run DB evidence preserved (not restored/mutated): requests `1951–1968`,
responses `1738–1748`, failures `213–219`, and related campaign/supervision rows.

### Staging residue (read-only; not modified)

Root:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/.staging/`

Includes pre-marker residue for `…005252Z` and older IDs. Residue does not
establish consumption for unconsumed packages and was not modified by this lane.

## Launch-chain identities (remeasured on live tree before packaging)

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
   * exact four-ID historical trust-root IDs above;
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

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_SOURCE_REQUEST_SCOPE_ENFORCEMENT`

Package verdict field:

`V2_9_8B_WINDOW_15M_FRESH_ONE_USE_AUTHORIZATION_AFTER_SOURCE_REQUEST_SCOPE_ENFORCEMENT_PASS`

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
* Migration-050 and this authorization package must remain among the current
  evidence package roots required by Git-provenance reconciliation;
* approved historical packages must remain byte-identical and listed in
  `prior_authorizations_non_reusable`;
* external application directory and marker for this ID must still be absent
  before the wrapper creates them.

## Money-usefulness contribution

This authorization enables one ordinary bounded memory-growth attempt under the
repaired invocation-local source-request ownership boundary. Historical request
contamination under the legacy static root can no longer distort current durable
set accounting, so source budget truth and terminal diagnosis remain campaign-local
on the shared authoritative DB.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| Reusing a consumed authorization | Four-ID trust root + marker law; all four IDs non-reusable |
| Premature live proof before inspection | Independent inspection PASS required |
| Silent scope degradation | Scoped reconciliation fail-closed |
| Foreign prefix contamination of `D` | Canonical prefix set + row-level root filter |
| Accidental second execution | One-use marker consumption; no retry/resume/successor |
| DB mutation during authorization lane | Read-only inspection; identity remeasured before/after |

## Exact next step

Operator manually runs the one-shot wrapper with the actual package path and
SHA-256 after this closeout commit and package creation. No automatic retry.

Stop before wrapper execution in this lane.
