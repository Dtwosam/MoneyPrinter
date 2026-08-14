# Printer V1 V2-9.8B Four-Token Historical Migration Provenance Independent Review

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_HISTORICAL_MIGRATION_PROVENANCE_INDEPENDENT_REVIEW_BLOCKED_REQUIRED_PACKAGE_ABSENCE`

Independent review baseline: `78e1549b93af4b89d45d138e23dffd5bb0f8d66d`.

The repair is accepted except for one fail-closed gap. The four-token profile explicitly declares the preserved migration-050 package as historical migration evidence, but `enumerate_historical_migration_evidence()` treats a missing declared package root as optional (`continue`), and the focused suite locks that behavior with `test_missing_historical_migration_root_is_not_required`.

That contradicts the repair design and implementation acceptance requirement that missing historical migration evidence fail closed. If the exact preserved migration-050 package is removed before authorization preparation, manifest construction can emit an empty `historical_migration_evidence` array and complete inventory reconciliation can pass because the removed bytes are no longer present as unexplained evidence.

## Accepted seams

- `T / M / Ha / Hm` is the correct evidence model.
- `U = M ∪ Ha ∪ Hm` and `F = T ∪ M ∪ Ha ∪ Hm` are correct.
- Current-package equality remains `C == M` only.
- Migration 055 remains the sole current migration evidence.
- Historical migration-050 evidence is separate from historical authorization evidence.
- Trust is scoped to exact package root plus exact execution ID for the four-token profile only.
- Historical migration records bind normalized path, size and SHA-256 and enter the allowed-file-set digest.
- Mutation, deletion after manifest creation, extra files/packages, symlinks, aliases, non-regular files and arbitrary operator-runs evidence are rejected.
- Ordinary WINDOW_15M and standard-four-hour profile schemas/defaults remain unchanged by this lane.

## Required repair

For a profile-declared `HistoricalMigrationPackage`, the exact declared package root and exact execution directory must exist and be a readable real directory. Absence must fail closed before manifest creation/validation succeeds.

Replace the optional-absence test with a fail-closed test proving the exact four-token migration-050 package cannot disappear. Preserve empty `historical_migration_packages=()` behavior for ordinary and standard-four-hour profiles.

No authorization preparation, marker, Printer runtime, source call, migration, DB mutation, 12h/24h, retrieval or paper-trading capability is permitted during this repair.

## Next permitted lane

`FOUR_TOKEN_HISTORICAL_MIGRATION_REQUIRED_PRESENCE_REPAIR`

After focused RED/GREEN repair and closeout, perform one final focused independent rereview. Only a PASS may return to fresh four-token authorization preparation against the new exact HEAD.
