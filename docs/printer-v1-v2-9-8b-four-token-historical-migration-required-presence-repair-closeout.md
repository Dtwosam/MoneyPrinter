# Printer V1 V2-9.8B Four-Token Historical Migration Required-Presence Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_HISTORICAL_MIGRATION_REQUIRED_PRESENCE_REPAIR_PASS_READY_FOR_FINAL_REREVIEW`

This lane is authorization-preparation safety work only. It created no
authorization, no application marker, no Printer runtime, no live source or RPC
call, no Scheduler work, no memory, no migration and no authoritative database
mutation. The migration-055 database state is untouched.

## Commits

- baseline: `a4376c2bf9725d290ba3b3c5114586b7cd217b1c`
- RED: `addc740c4ab26de5ad4c9b557166d14e93b7737d`
- GREEN: `b768ab1b6b0d724b5fb3fbdf1bcd5fb94ca26bf9`
- final HEAD: see the closeout commit at the end of this branch
- branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`

Local was at `78e1549`, remote at the stated baseline `a4376c2`; the branch was
safe-fast-forwarded only. No reset, clean, stash, delete, move or modification
touched any `operator-runs/` artifact.

## Defect repaired

`enumerate_historical_migration_evidence()` treated a missing declared package
root as optional (`if not package_root_path.exists(): continue`), and the focused
suite locked that with `test_missing_historical_migration_root_is_not_required`.

For a profile-declared `HistoricalMigrationPackage` that is wrong. If the exact
preserved migration-050 package were removed before authorization preparation,
manifest construction would emit an empty `historical_migration_evidence` array
and complete inventory reconciliation would still pass, because the removed
bytes are no longer present as unexplained evidence.

## Repair

For every package declared in `profile.historical_migration_packages`:

- the declared package root must exist;
- it must be a real, non-symlinked, readable directory;
- the exact execution directory must exist;
- it must be a real, non-symlinked, readable directory;
- the exact execution package must yield at least one bound untracked regular
  file;
- any absence fails closed.

The empty default is untouched. A profile with `historical_migration_packages=()`
returns immediately and performs no filesystem work, so ordinary `WINDOW_15M`
and standard-four-hour behavior is unchanged. The manifest schema was not
reopened.

## Model unchanged

`T` tracked history, `M` current migration-055 plus current four-token
authorization, `Ha` historical authorization evidence, `Hm` exact historical
migration-050 evidence. `U = M ∪ Ha ∪ Hm`, `F = T ∪ M ∪ Ha ∪ Hm`, and
current-package equality remains `C == M` only.

All previously accepted protections are retained and still locked: exact root
plus exact execution ID only; migration 050 stays historical and never current;
migration 055 stays the sole current schema transition; path/size/SHA-256
binding; mutation, deletion, extra file, extra package, symlink/alias and
non-regular entries all fail closed; arbitrary `operator-runs/` evidence is still
rejected; `Hm` still enters the allowed-file-set digest.

## Correct consequence for disposable fixtures

Required presence means a four-token proof repository must actually carry the
declared package. The shared disposable fixture `FourTokenProofFixture` now
creates the exact migration-050 package, and its expected allowlist count moves
from 2 to 3. The current package set it asserts is unchanged: the added file
appears only in `historical_migration_evidence`, never in `files`, which is a
direct re-proof that `C == M` still holds.

A read-only check against the live repository confirms the real preserved package
still enumerates as 12 bound records, and that both the ordinary and
standard-four-hour profiles return an empty tuple. No authorization was prepared
to obtain this.

## Files changed

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- `tests/test_v2_9_8b_four_token_historical_migration_provenance.py`
- `tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py`
- `docs/printer-v1-v2-9-8b-four-token-historical-migration-required-presence-repair-closeout.md` (new)

## Tests and results

RED (`addc740`): `3 failed, 20 passed, 2 subtests passed` in the focused suite.
The three required-presence tests failed because the declared package was treated
as optional.

GREEN focused historical migration provenance suite —
`tests/test_v2_9_8b_four_token_historical_migration_provenance.py`:
`23 passed, 2 subtests passed`.

Required-presence proofs:

1. missing declared package root fails —
   `test_missing_declared_package_root_fails_closed`;
2. root present but exact execution directory missing fails —
   `test_missing_exact_execution_directory_fails_closed`;
3. exact execution directory present but empty fails —
   `test_empty_exact_execution_directory_fails_closed`.

Two hardening locks were added alongside them:
`test_declared_package_root_must_be_a_real_directory` and
`test_symlinked_exact_execution_directory_fails_closed`.

Directly affected four-token provenance/wrapper locks (8 files):
`12 failed, 57 passed, 12 subtests passed`. The failing set is byte-identical to
the same run at baseline `a4376c2` (`diff` clean). Those 6 failures plus 6
subtest failures are pre-existing wall-clock `AUTHORIZATION_EXPIRED` /
zero-state-gate fixture drift in
`test_v2_9_8b_four_token_proof_zero_state_gate.py` and
`test_v2_9_8b_four_token_proof_authorization_profile.py`, unrelated to historical
migration evidence. They were measured in place by temporarily restoring only the
baseline production module and fixture. During development this repair
transiently broke 6 further tests in three fixture-sharing files; updating the
shared disposable fixture to carry the now-required package closed all 6, and the
final failing set matches baseline exactly.

Ordinary `WINDOW_15M` profile regression (5 files): `68 failed, 120 passed`,
failing-test-ID set byte-identical to the 68 documented pre-existing failures
recorded in the previous closeout (`diff` clean). Scope was not expanded to them.

Standard-four-hour profile regression (5 files): `51 passed, 3 subtests passed`.

Static checks: `py_compile` clean on the touched production module and both
touched test modules; `git diff --check` clean.

## Note on one RED assertion

The RED tests initially asserted that manifest construction would raise
`FourTokenProofOneShotWrapperError`. That was wrong.
`GitProvenanceAuthorizationError` is the provenance authority's own type and
already propagates through every four-token validation path, so the assertion was
corrected to expect it rather than adding a wrapping layer. The fail-closed
requirement itself was unchanged.

## What was not touched

No authorization preparation or creation, no application marker, no Printer
runtime, no live source or RPC call, no authoritative DB mutation, no migration,
no 12h/24h, no retrieval, no paper decisions, no BUY/SELL/HOLD, no positions,
trades, audits or PnL. Source Governor and Central Scheduler ownership is
unchanged. The manifest schema version is unchanged at
`PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_PROOF_V2`.

## Functionality Risks / Setbacks / Efficiency Blockers

- Risk: required presence makes any future four-token disposable fixture fail
  unless it carries the declared package. Mitigation: the shared fixture now
  creates it, and the failure message names the exact missing package prefix.
- Risk: a future profile declares a package that is not preserved, hard-blocking
  preparation. Mitigation: declaration is explicit, per profile, and empty by
  default; nothing is declared implicitly.
- Risk: an at-least-one-file rule could be satisfied by a token placeholder.
  Mitigation: every accepted file is still path/size/SHA-256 bound and enters the
  allowed-file-set digest, and the manifest must match the enumerated inventory
  exactly.
- Setback: the pre-existing zero-state-gate temporal-expiry failures and the 68
  `WINDOW_15M` failures remain open. Both predate this lane and were deliberately
  left out of scope.

## What this still does not unlock

It does not create or approve a four-token authorization and does not permit
runtime. One final focused independent rereview is required. Only a rereview PASS
may return to fresh four-token authorization preparation against the new exact
HEAD.

## Next permitted lane

`FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_FINAL_INDEPENDENT_REREVIEW`

Do not prepare another authorization before that rereview closes PASS.
