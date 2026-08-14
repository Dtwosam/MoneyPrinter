# Printer V1 V2-9.8B Four-Token Historical Migration Required-Presence Final Rereview

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_HISTORICAL_MIGRATION_REQUIRED_PRESENCE_FINAL_REREVIEW_PASS_READY_FOR_FRESH_AUTHORIZATION_PREPARATION`

This is a focused independent rereview of the single required-presence blocker identified in the prior historical-migration provenance review. It does not create an authorization, application marker, Printer runtime, source request, Scheduler work, memory, migration, or authoritative DB mutation.

## Reviewed baseline and candidate

- prior blocked-review baseline: `a4376c2bf9725d290ba3b3c5114586b7cd217b1c`
- RED: `addc740c4ab26de5ad4c9b557166d14e93b7737d`
- GREEN: `b768ab1b6b0d724b5fb3fbdf1bcd5fb94ca26bf9`
- implementation closeout: `cc56e6168f622c23b661dd994e7b570458aaf371`
- branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`

GitHub compare shows the candidate is exactly three commits ahead of the blocked-review baseline with no divergence.

## Independent findings

The blocker is repaired correctly.

For every profile-declared `HistoricalMigrationPackage`, `enumerate_historical_migration_evidence()` now fails closed unless:

- the declared package root exists;
- the package root is a real directory and is readable/searchable;
- the exact declared execution directory exists;
- the exact execution directory is a real, non-symlink directory and is readable/searchable;
- the exact execution package yields at least one bound untracked regular file.

The former optional behavior (`if not package_root_path.exists(): continue`) is removed.

The RED correctly replaced the optional-absence lock with three required-presence failures:

1. missing declared root;
2. root present but exact execution directory absent;
3. exact execution directory present but empty.

It also adds hardening locks for a non-directory root and an aliased execution directory.

The GREEN is narrowly scoped to required presence. The accepted provenance model remains unchanged:

- `T` = tracked operator-run history
- `M` = current migration-055 evidence plus current four-token authorization
- `Ha` = explicitly approved historical authorization evidence
- `Hm` = exact profile-bound historical migration-050 evidence
- `U = M ∪ Ha ∪ Hm`
- `F = T ∪ M ∪ Ha ∪ Hm`
- current-package equality remains `C == M` only

Migration 055 remains the sole current schema-transition evidence. Migration 050 remains historical evidence only. The manifest schema is not reopened.

The empty-default behavior is preserved: profiles with `historical_migration_packages=()` return before historical-migration filesystem inspection, so ordinary WINDOW_15M and standard-four-hour profile semantics remain isolated.

The fixture adjustment is appropriate: disposable four-token fixtures now carry the profile-required migration-050 evidence. Their allowlist count increases only because `Hm` exists; their current-package set remains unchanged, which preserves `C == M`.

## Verification evidence

Reported local GREEN evidence:

- focused historical migration provenance: `23 passed, 2 subtests passed`
- standard-four-hour profile regression: `51 passed, 3 subtests passed`
- ordinary WINDOW_15M regression retained the same documented `68 failed, 120 passed` baseline failure set
- directly affected four-token locks retained the same documented 12 baseline wall-clock/fixture failures and otherwise passed
- `py_compile`: clean
- `git diff --check`: clean

This independent rereview statically inspected the GitHub RED/GREEN diffs and ancestry. It did not independently re-execute the local pytest suites; the executor-reported results are therefore treated as reported local evidence, while the acceptance decision is based on the inspected fail-closed implementation and focused tests.

## Accepted protections retained

- exact historical migration root + exact execution ID only
- no broad `operator-runs/` trust
- no use of `prior_authorizations_non_reusable` for migration evidence
- no sidecar classification shortcut
- path / size / SHA-256 binding
- mutation, deletion, extra file/package, symlink/alias/non-regular evidence fail closed
- arbitrary untracked/ignored operator-run evidence remains rejected
- `Hm` remains included in the allowed-file-set digest
- `C == M` remains current-only
- ordinary WINDOW_15M and standard-four-hour profiles remain unchanged through the empty default

## Money-usefulness contribution

This closes the last known pre-authorization provenance hole: the proof can no longer become easier to authorize merely because preserved migration-050 evidence disappeared. The future four-token run will therefore remain attributable to one exact code, DB, migration, authorization, and preserved-history state.

## What this improves

- historical migration evidence is now required when the active profile declares it;
- deletion of the whole preserved package cannot silently produce an empty historical-migration manifest;
- the exact execution directory itself is independently required and non-aliased;
- the accepted current-vs-historical evidence boundary remains unchanged.

## What this still does not unlock

This rereview does not itself authorize or start the four-token proof. The next permitted lane is fresh authorization preparation against the new exact branch HEAD and the then-current authoritative DB identity. After a fresh authorization is prepared, it still requires an independent authorization review before one-shot consumption/runtime.

No 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet, private keys, real funds, paid APIs, scoring/ranking/confidence, or embeddings/vectors are unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical migration package drift after manifest construction remains fail-closed through path/size/hash validation and final inventory reconciliation.
- Existing unrelated WINDOW_15M baseline failures remain outside this lane and must not be conflated with this repair.
- The launch branch must be frozen after this rereview commit so the next authorization binds a stable exact HEAD.

## Next permitted lane

`FOUR_TOKEN_FRESH_AUTHORIZATION_PREPARATION`

Prepare exactly one fresh, unconsumed authorization against the new exact HEAD. Do not start Printer. Perform a separate independent authorization review before any application marker or child launch.
