# Printer V1 V2-9.8B Four-Token Historical Migration Provenance Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_REPAIR_PASS_READY_FOR_INDEPENDENT_REVIEW`

This lane is authorization-preparation safety work only. It created no
authorization, no application marker, no Printer runtime, no source or RPC call,
no Scheduler work, no memory, no migration and no authoritative database
mutation. The migration-055 database state is untouched.

## Commits

- baseline: `025992207bf636b4be7bb626d43e989d38635949`
- RED: `2517f215019394e7a46936d2c93c76b99707eaef`
- GREEN: `1fa8b83260f0157fa13e4c0079ae8d206b7ddf28`
- final HEAD: `1fa8b83260f0157fa13e4c0079ae8d206b7ddf28`
- branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`

The branch was safe-fast-forwarded from local `5eff4cb` to the exact baseline
`0259922`. No reset, clean, stash, delete, move, rewrite or commit touched any
`operator-runs/` artifact. The two preserved untracked roots
(`v2-9-8b-migration-055-application`, `v2-9-8b-standard-four-hour-final-authorization`)
and the ignored `v2-9-8b-authoritative-mig050` package remain exactly as found.

## Real blocker reproduced (RED)

The first four-token authorization preparation reached pre-marker Git-provenance
reconciliation and correctly failed. The preserved historical migration package

- root: `operator-runs/v2-9-8b-authoritative-mig050`
- execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`

is untracked/ignored and had no semantic class in the generic reconciliation
model, so it was rejected as unexplained ignored evidence.

RED reproduces exactly that shape offline — migration-055 current evidence plus
the exact four-token authorization fixture plus the preserved ignored
migration-050 package — and fails with the real production message:

```text
unexpected ignored operator-runs file not covered by manifest:
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/...
```

RED result: `13 failed, 8 passed` in the new focused suite.

## Evidence model implemented

Four disjoint sets:

- `T`  tracked operator-run history
- `M`  current manifest evidence — migration 055 plus the current four-token
  authorization only
- `Ha` explicitly approved historical authorization evidence
- `Hm` explicitly profile-bound historical migration evidence

Untracked allowlist `U = M ∪ Ha ∪ Hm`. Complete inventory `F = T ∪ M ∪ Ha ∪ Hm`.

Current-package equality remains `C == M` only. `Hm` is checked against the
current package roots and rejected if it ever lies inside one, so historical
migration evidence can never satisfy current-package identity. Migration 055
remains the sole current schema-transition evidence and the authorization still
binds migration count 55 / head 055 / current DB identity.

## Exact binding

`FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` — and only that profile — declares one
`HistoricalMigrationPackage`:

- package root: `operator-runs/v2-9-8b-authoritative-mig050`
- execution ID: `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f`
- evidence class: `HISTORICAL_MIGRATION_050_EVIDENCE`

Directory presence creates no trust. Every regular file in that exact package is
bound by normalized repository-relative path, size and SHA-256, and those records
enter the allowed-file-set digest before any marker can exist.

Read-only enumeration against the live repository binds the real preserved
package as 12 records, including nested `disposable-restore/` and
`verified-backup/` database artifacts. No authorization was prepared to obtain
this; it is a pure read of already-present bytes.

## Design constraints honored

- minimal additive `GitAuthorizationProfile` extension
  (`historical_migration_packages`, default `()`);
- ordinary `WINDOW_15M` and standard-four-hour profiles keep byte-for-byte
  behavior, exact manifest key sets and unchanged schema versions through that
  default;
- `Hm` is represented separately from `historical_authorization_evidence` and
  deliberately carries no authorization id and no terminal disposition;
- `prior_authorizations_non_reusable` is not used for migration evidence;
- `sidecar_untracked_paths` is not used;
- neither `operator-runs/` nor the whole migration-050 root is broadly trusted —
  exact root plus exact execution ID only;
- any second or unapproved package beneath the migration-050 root that still
  holds untracked files fails closed;
- missing, mutated, extra, symlinked, aliased and non-regular entries fail
  closed;
- arbitrary ignored/untracked `operator-runs/` files remain rejected.

## Manifest schema revision

The four-token manifest gains one profile-scoped field,
`historical_migration_evidence`, and its schema version moves to
`PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V2`. No four-token
authorization has ever been created or consumed, so no live contract migrates.
`expected_manifest_keys()` returns the original exact key set for every profile
that declares no historical migration package, so previously consumed ordinary
and standard manifest semantics are unchanged. A manifest that declares
`historical_migration_evidence` under a profile without the binding is rejected.

## Files changed

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `src/printer_v1/operator_cli/four_token_proof_one_shot_wrapper.py`
- `tests/test_v2_9_8b_four_token_historical_migration_provenance.py` (new)
- `tests/test_v2_9_8b_four_token_proof_authorization_profile.py` (schema version)
- `tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py` (schema version)
- `docs/printer-v1-v2-9-8b-four-token-historical-migration-provenance-repair-closeout.md` (new)

## Tests and results

Focused RED/GREEN provenance suite —
`tests/test_v2_9_8b_four_token_historical_migration_provenance.py`:
`19 passed, 2 subtests passed`.

GREEN proofs:

1. exact historical migration-050 package passes for the four-token profile —
   `test_exact_historical_migration050_package_passes`,
   `test_preserved_migration050_package_does_not_block_preparation`,
   `test_historical_migration_binding_is_exact_and_profile_scoped`;
2. migration 050 remains historical, never current —
   `test_migration050_remains_historical_never_current`;
3. current equality remains migration-055 plus current authorization only —
   `test_current_equality_remains_migration055_plus_current_authorization`;
4. all `Hm` files are path/size/SHA bound —
   `test_every_historical_migration_file_is_path_size_sha_bound`;
5. mutation fails — `test_mutated_historical_migration_file_fails_closed`;
6. deletion fails — `test_deleted_historical_migration_file_fails_closed`;
7. extra file fails — `test_extra_historical_migration_file_fails_closed`;
8. extra migration-050 package fails —
   `test_second_migration050_package_fails_closed`;
9. symlink/alias and non-regular entries fail —
   `test_symlinked_historical_migration_entry_fails_closed`,
   `test_non_regular_historical_migration_entry_fails_closed`;
10. arbitrary operator-runs evidence still fails —
    `test_arbitrary_ignored_operator_runs_evidence_still_fails`;
11. allowed-file-set digest covers `Hm` —
    `test_allowed_file_set_digest_covers_historical_migration_evidence`;
12. `WINDOW_15M` behavior unchanged —
    `test_window_15m_profile_declares_no_historical_migration`,
    `test_only_four_token_profile_accepts_the_historical_migration_field`;
13. standard-four-hour behavior unchanged —
    `test_standard_four_hour_profile_declares_no_historical_migration`.

Disjointness and the empty-`Hm` default are additionally locked by
`test_historical_migration_is_disjoint_from_other_evidence_sets` and
`test_missing_historical_migration_root_is_not_required`.

Directly affected four-token wrapper/provenance locks —
`test_v2_9_8b_four_token_historical_migration_provenance.py`,
`test_v2_9_8b_four_token_proof_migration_055_evidence.py`,
`test_v2_9_8b_four_token_proof_authorization_profile.py`,
`test_v2_9_8b_four_token_proof_one_shot_wrapper.py`,
`test_v2_9_8b_four_token_proof_integrated_disposable_wrapper.py`,
`test_v2_9_8b_four_token_proof_existing_wrapper_regression_locks.py`,
`test_v2_9_8b_four_token_proof_integration.py`,
`test_v2_9_8b_four_token_proof_cli_mode.py`,
`test_v2_9_8b_four_token_proof_zero_state_gate.py`:
`82 passed, 20 subtests passed`.

Standard-four-hour provenance regression —
`test_v2_9_8b_post_dtw100_standard_four_hour_activation_authorization.py`,
`test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py`,
`test_v2_9_8b_second_standard_four_hour_public_budget_authority_repair.py`,
`test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py`,
`test_v2_9_8b_fourth_standard_four_hour_manifest_budget_repair.py`:
`51 passed, 3 subtests passed`.

Ordinary `WINDOW_15M` provenance regression —
`test_v2_9_8b_window_15m_git_provenance_authorization_manifest.py`,
`test_v2_9_8b_window_15m_ignored_evidence_visibility.py`,
`test_v2_9_8b_window_15m_historical_authorization_evidence_contract.py`,
`test_v2_9_8b_window_15m_historical_authorization_boundary_followup_repair.py`,
`test_v2_9_8b_window_15m_one_shot_wrapper.py`:
`68 failed, 120 passed`.

Those 68 failures are pre-existing documented baseline failures, not regressions.
They were measured in place at the exact baseline `0259922` by temporarily
restoring only the two production modules, and the failing-test-ID sets before
and after this repair are byte-identical (`diff` clean, 68 lines each). The
representative baseline cause is
`final authorization migration_execution_id mismatch` in those suites' fixtures,
which is unrelated to the historical migration evidence class. Scope was not
expanded to them.

Static checks: `py_compile` clean on both touched production modules and the new
test module; `git diff --check` clean.

## What was not touched

No authorization preparation or creation, no application marker, no Printer
runtime, no source/RPC fetching, no authoritative DB read for mutation, no
migration, no 12h/24h, no retrieval, no paper decisions, no BUY/SELL/HOLD, no
positions, trades, audits or PnL. Source Governor and Central Scheduler ownership
is unchanged. No broad regression suite was run; the change is narrow and its
architectural scope is the Git-provenance evidence model only.

## Functionality Risks / Setbacks / Efficiency Blockers

- Risk: a future profile copies the four-token binding and widens trust.
  Mitigation: `historical_migration_packages` defaults to empty, each package is
  an exact root plus exact execution ID, and unapproved sibling packages with
  untracked files fail closed.
- Risk: historical migration evidence is mistaken for current migration
  authority. Mitigation: separate class with no authorization id or terminal
  disposition, `C == M` equality untouched, and an explicit rejection when an
  `Hm` record claims the current migration execution id.
- Risk: the preserved package drifts between manifest creation and validation.
  Mitigation: every file is size- and SHA-256-bound and enters the
  allowed-file-set digest, so mutation, deletion or addition fails closed.
- Setback: the pre-existing 68 `WINDOW_15M` suite failures remain open. They
  predate this lane and were deliberately not repaired here.

## What this still does not unlock

It does not create or approve a four-token authorization and does not permit
runtime. One focused independent review of this closeout is required. Only a
review PASS may return to fresh authorization preparation against the new exact
HEAD.

## Next permitted lane

`FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_REPAIR_INDEPENDENT_REVIEW`

Do not prepare another authorization before that review closes PASS.
