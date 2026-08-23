# Printer V1 V2-9.8B Migration-061 Git Evidence Cutover Design

**Document status:** `DESIGN / REVIEW ONLY`

**Date:** 2026-08-23

**Branch:**
`agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`

**Required starting HEAD:**
`81714134783cfd5cd6cea72af6d71b3cb7579494`

**Verdict:**
`V2_9_8B_MIGRATION_061_GIT_EVIDENCE_CUTOVER_DESIGN_REVIEW_PASS_READY_FOR_NARROW_IMPLEMENTATION`

This lane is documentation and read-only source review. It does not edit
production or tests, does not edit
`git_provenance_authorization_manifest.py`, does not write
`data/printer_v1.sqlite3`, does not apply a migration, does not create or
consume authorization, and does not implement the cutover.

Passing this review means the later implementation is specified. It does not
mean git evidence has moved, a campaign is authorized, V2-9.8B is complete,
or V2-10 is ready.

---

## Overview

Catalogue, reviewed admission pin, and the authoritative database are 61 /
`061_standard_4h_progression_fault_preservation.sql`. A real Migration-061
application package exists at
`operator-runs/v2-9-8b-migration-061-application/MIGRATION_061_20260823T200709Z/`.
Both four-token authorization profiles still bind current schema-transition
evidence as `MIGRATION_059_EVIDENCE`.

That is the remaining git-evidence mismatch. This design specifies the
minimum fail-closed cutover that makes Migration 061 the single current
schema-transition evidence owner for both four-token profiles and demotes
Migration 059 to one immutable historical package. It does not authorize a
campaign.

---

## 1. Current manifest topology

Inspected at HEAD `81714134783cfd5cd6cea72af6d71b3cb7579494` in
`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`.

### Current Migration-059 constants

| Name | Value |
| --- | --- |
| `MIGRATION_059_PACKAGE_KIND` | `MIGRATION_059_EVIDENCE` |
| `MIGRATION_059_PACKAGE_ROOT` | `operator-runs/v2-9-8b-migration-059-application` |

Source comment at those constants is the current-evidence law:

> Only the package root/kind are committed here. The exact execution
> identity remains authorization/preparation-time input and is hashed
> through the existing manifest mechanism; filesystem discovery never
> creates current authority.

There is **no** committed `MIGRATION_059` execution-ID or current-package
inventory digest on the profile. The real execution directory is the
untracked package `MIGRATION_059_20260821T095456Z`.

Former current kinds `MIGRATION_050_EVIDENCE` through `MIGRATION_058_EVIDENCE`
remain as distinct identity constants. Ordinary WINDOW_15M and two-token
standard-four-hour profiles still default to migration-050
(`MIGRATION_PACKAGE_KIND` / `MIGRATION_PACKAGE_ROOT`). They are out of
cutover scope.

There is no `MIGRATION_061_PACKAGE_*` symbol today.

### Execution-ID binding

`GitAuthorizationProfile` has no execution-ID field.

A later authorization document and its git-provenance manifest both carry
`migration_execution_id`. `validate_git_provenance_manifest_pre_marker`
requires those strings to match. `_validate_files` then requires every
current migration file to live under:

```text
{profile.migration_package_root}/{migration_execution_id}/
```

`require_safe_authorization_id` accepts `[A-Za-z0-9_.-]+` with no path
separators or glob characters. Both
`MIGRATION_059_20260821T095456Z` and `MIGRATION_061_20260823T200709Z`
satisfy that law.

### Required-file inventory (current vs historical)

Current packages have **no** named required-file list in the profile.

`window_15m_one_shot_wrapper._enumerate_package` walks all regular files
under the named current package directory. It fails closed if the directory
is missing, is a symlink, is empty, contains a symlink, or contains a
non-regular entry.

Four-token `build_manifest_bytes` uses that enumerator with
`profile.migration_package_kind`. `_validate_files` then re-reads each
manifest member by path, size, and SHA-256.

Historical packages use a different completeness law. Each
`HistoricalMigrationPackage` commits `package_root`, `execution_id`,
`evidence_class`, `expected_file_count`, and `expected_inventory_sha256`.
`enumerate_historical_migration_evidence` inventories **every** regular file
under `{package_root}/{execution_id}`, requires the file count to match, requires
every member to be untracked, and requires
`package.inventory_sha256(files) == expected_inventory_sha256`.

There is no whitelist of historical filenames. Completeness is the complete
directory inventory.

### Inventory-digest computation

One helper owns both historical completeness and any test-side digest of a
current package:

`compute_historical_migration_inventory_sha256`

Domain: `PRINTER_V1_HISTORICAL_MIGRATION_INVENTORY_DOMAIN` =
`PRINTER_V1_HISTORICAL_MIGRATION_PACKAGE_INVENTORY_V1`

Canonical payload, sorted by path:

```text
{
  domain,
  package_root,
  execution_id,
  evidence_class,
  file_count,
  files: [{path, sha256, size}, ...]
}
```

`evidence_class` is inside the digest. Hashing the same bytes as
`MIGRATION_061_EVIDENCE` versus `HISTORICAL_MIGRATION_061_EVIDENCE` produces
different digests. That fact must be preserved.

Do not introduce a second hashing convention.

### `_validate_files`

Valid `package_kind` values are only:

- `profile.migration_package_kind`
- `profile.authorization_package_kind`

A current migration member whose kind is the profile's migration kind must
resolve under the current migration prefix. A historical class is rejected
here as a current file kind. Missing file, size mismatch, or SHA-256
mismatch fail closed.

### Four-token profiles

Both currently bind the same migration evidence:

```text
migration_package_root = MIGRATION_059_PACKAGE_ROOT
migration_package_kind = MIGRATION_059_PACKAGE_KIND
historical_migration_packages = FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES
```

`FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES` is the shared tuple, in order:

| # | root | execution ID | evidence_class | files | digest prefix |
| --- | --- | --- | --- | --- | --- |
| 1 | `operator-runs/v2-9-8b-authoritative-mig050` | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` | `HISTORICAL_MIGRATION_050_EVIDENCE` | 12 | `2bcbfdd3…` |
| 2 | `…/v2-9-8b-migration-055-application` | `MIGRATION_055_20260813T220109Z` | `HISTORICAL_MIGRATION_055_EVIDENCE` | 5 | `c0044373…` |
| 3 | `…/v2-9-8b-migration-056-application` | `MIGRATION_056_20260815T164802Z` | `HISTORICAL_MIGRATION_056_EVIDENCE` | 6 | `4918774b…` |
| 4 | `…/v2-9-8b-migration-057-application` | `MIGRATION_057_20260816T191558Z` | `HISTORICAL_MIGRATION_057_EVIDENCE` | 6 | `9272f596…` |
| 5 | `…/v2-9-8b-migration-058-application` | `MIGRATION_058_20260818T082552Z` | `HISTORICAL_MIGRATION_058_EVIDENCE` | 11 | `d6dc1431…` |

059 is **not** in that tuple. Source comment currently says current authority
is migration 059 alone.

`test_current_migration_059_is_never_a_historical_package` encodes the
current-vs-historical exclusivity invariant: the current root must not appear
in `historical_migration_packages`.

Duplicate current/historical paths also fail in `_reconcile_evidence_sets`
and `_validate_historical_migration_evidence` (historical execution ID must
not equal the manifest's current `migration_execution_id`; historical paths
must not lie inside a current package prefix).

`_NON_RECONCILIATION_EVIDENCE_CLASSES` already includes
`MIGRATION_059_PACKAGE_KIND` and the historical 050/055/056/057/058 classes.
It does not include a 061 kind or `HISTORICAL_MIGRATION_059_EVIDENCE`.

---

## 2. Exact target state

Confirmed from source, not corrected.

A. Migration 061 becomes the **only** current schema-transition evidence for
   **both** four-token profiles.

B. Migration 059 becomes one immutable historical migration package, appended
   to `FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES`.

C. Current evidence refers to the real Migration-061 package bytes under
   `operator-runs/v2-9-8b-migration-061-application/`.

D. Historical 059 continues to refer to the real immutable 059 package under
   `operator-runs/v2-9-8b-migration-059-application/MIGRATION_059_20260821T095456Z/`.

E. No package bytes are copied, rewritten, regenerated, or synthesized. The
   packages remain untracked operator evidence.

F. No authorization is created by this cutover.

There must not be two competing current schema-evidence owners.

Ordinary WINDOW_15M and two-token standard-four-hour profiles remain on
migration-050.

---

## 3. Atomic profile cutover

The committed repository state after the later implementation must have
**both** `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` and
`FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE` bound to 061 current
evidence and to the same historical tuple that now includes 059.

No accepted HEAD may exist in which:

- one four-token profile uses 061 and the other 059;
- one profile points at a nonexistent package root;
- one profile uses a historical evidence class as `migration_package_kind`.

Python assignment order inside the module is irrelevant. The committed file
must be coherent. Tests must assert the two profiles'
`migration_package_kind` and `migration_package_root` are equal to each
other and equal to the 061 constants.

The later implementation should keep using the shared
`FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES` object so the two profiles cannot
drift on historical membership.

---

## 4. New 061 current-evidence contract

Derive names from the 055–059 constant pattern already in source.

### Required profile/current constants

| Name | Value |
| --- | --- |
| `MIGRATION_061_PACKAGE_KIND` | `MIGRATION_061_EVIDENCE` |
| `MIGRATION_061_PACKAGE_ROOT` | `operator-runs/v2-9-8b-migration-061-application` |

Current evidence class is `MIGRATION_061_EVIDENCE`, not
`HISTORICAL_MIGRATION_061_EVIDENCE`.

Both four-token profiles set:

```text
migration_package_root = MIGRATION_061_PACKAGE_ROOT
migration_package_kind = MIGRATION_061_PACKAGE_KIND
```

### Execution ID source

Keep the established current-evidence law: execution ID is **not** a
`GitAuthorizationProfile` field. The next separately authorized 4/2/2
package must supply `migration_execution_id` as authorization-time input.

The only real 061 package that exists is:

`MIGRATION_061_20260823T200709Z`

That string is a valid `require_safe_authorization_id` value. Filesystem
discovery of a sibling directory must never promote a second current
package.

### Real current package inventory

Complete directory inventory (5 regular files, no extras):

| path under the execution directory | size | sha256 |
| --- | --- | --- |
| `apply_migration_060_061.py` | 39030 | `362aa42b8b52f679f0583eedfbbe2c46f0af27c8d059ce843ccda4c20d922997` |
| `backup_restore_rehearsal.json` | 42034 | `9e4100eb2c4b59afae4f0f3df77719a3567fdd5d680b2a27dfb72a27ef380bc5` |
| `migration_060_061_application_receipt.json` | 28785 | `fecacf1649cf7e862aac1f4b7e9c057a92c4d4ddc6a351d247a4597b308170d1` |
| `post_application_snapshot.json` | 29299 | `590ec13b88cf75aba830808b73dd687135aa4573b2a31c7752006eeeb264ff2d` |
| `pre_application_snapshot.json` | 29600 | `906d3c302794c656dbea438b3758fae7ac0fcc46f0f171f39bfa7f6846ace0af` |

Independently recomputed with `compute_historical_migration_inventory_sha256`
and evidence class `MIGRATION_061_EVIDENCE`:

`a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6`

This matches PR 4. It is the **proposed current-class digest**.

The digest under `HISTORICAL_MIGRATION_061_EVIDENCE` is
`ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459`.
That class is **not** proposed. 061 is not being demoted.

### Validator ownership for current 061

Existing owners, after the profile rebind, already reach the 061 root:

| Owner | Behavior |
| --- | --- |
| `_enumerate_package` | missing / empty / symlink / non-regular → fail |
| four-token `build_manifest_bytes` | enumerates `{root}/{migration_execution_id}` |
| `_validate_files` | member path/size/sha256 vs live bytes |
| `validate_git_provenance_manifest_pre_marker` | current prefix + historical tuple |

Narrow extension: commit the real 061 execution identity and current-class
inventory digest as **module-level identity constants**, not as new
`GitAuthorizationProfile` fields. Purpose:

- focused tests recompute the real-package digest against a committed expected
  value;
- later authorization review can require the document's
  `migration_execution_id` to equal that identity;
- production prepare/validate APIs stay the 059 current-evidence shape.

Suggested names, following the historical `FOUR_TOKEN_HISTORICAL_MIGRATION_*`
pattern without pretending they are historical:

- `FOUR_TOKEN_CURRENT_MIGRATION_061_EXECUTION_ID`
- `FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_FILE_COUNT` = 5
- `FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_INVENTORY_SHA256` =
  `a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6`

Do not add a second inventory helper. Do not copy the package into a tracked
directory.

Also add `MIGRATION_061_PACKAGE_KIND` to
`_NON_RECONCILIATION_EVIDENCE_CLASSES` and export the new public names in
`__all__`.

---

## 5. 059 historical transition

Mirror the 058 demotion.

Keep `MIGRATION_059_PACKAGE_KIND` / `MIGRATION_059_PACKAGE_ROOT` as the
former current identity constants. Do not reuse `MIGRATION_059_EVIDENCE` as
the historical `evidence_class`. 058 still has both a KIND constant and a
separate `HISTORICAL_MIGRATION_058_EVIDENCE` class.

### Historical 059 declaration

| Field | Value |
| --- | --- |
| `package_root` | `MIGRATION_059_PACKAGE_ROOT` |
| `execution_id` | `MIGRATION_059_20260821T095456Z` |
| `evidence_class` | `HISTORICAL_MIGRATION_059_EVIDENCE` |
| `expected_file_count` | 5 |
| `expected_inventory_sha256` | `d23c4f4bbf2b4683c69038bb6fc372f85c52e280b24662cb46c133690b1479c6` |

Independently recomputed from the live 059 package with that historical
class. Matches PR 4.

Live 059 members:

| path | size | sha256 |
| --- | --- | --- |
| `apply_migration_059.py` | 27890 | `4a66f4f72e1f763d92d74b496ffc98c74df4fc61ac11e90eb8850a165cdb5565` |
| `backup_restore_rehearsal.json` | 343461 | `fd51c11215ddb27a587b5c4bb5843f40e8974eed0d5bd6a6e48a2671da9d4d0e` |
| `migration_059_application_receipt.json` | 18204 | `eb3fd20c2656952bba25597d21ac02e232cdb82232a8a2cc2fb20c1f6059cd06` |
| `post_application_snapshot.json` | 326195 | `77fafcef86bb704f7076201843cf6b6db6d71dc7882e1dec09c0a77c90829bf5` |
| `pre_application_snapshot.json` | 326067 | `9ec304205868bb51d7ebc895f12ea567b4437821780e998842c57ac44702f9cb` |

Hashing those same bytes as `MIGRATION_059_EVIDENCE` yields
`e4a985be8dd90a55bd8f8c6c7301dda50b053353b46672d90ba6b092a7aa16e5`.
That is **not** the historical digest. Historical declaration must use
`HISTORICAL_MIGRATION_059_EVIDENCE`.

### Ordering, duplicates, exclusivity

Append 059 as the sixth member of `FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES`,
after 058. Do not reorder 050–058. Do not delete the 059 package.

Current 061 root must not appear in the historical tuple.
Historical 059 root must not remain `migration_package_root`.
`test_current_migration_059_is_never_a_historical_package` becomes the 061
form of the same invariant, plus an assertion that 059 **is** historical.

`enumerate_historical_migration_evidence` already fails closed on a missing
059 execution directory, wrong file count, tracked member, digest mismatch,
or unapproved sibling untracked package under the 059 root.

Add `HISTORICAL_MIGRATION_059_EVIDENCE_CLASS` to
`_NON_RECONCILIATION_EVIDENCE_CLASSES`.

Historical file-count total today is 40 (12+5+6+6+11). After append it is
45. `test_production_total_declared_hm_count_is_40` must move with that
identity, not be deleted.

---

## 6. Inventory / hash authority

`compute_historical_migration_inventory_sha256` is the single owner.

Later implementation tests must call that helper on actual package bytes and
compare to the committed expected digest. Do not paste a digest into tests
without a production recomputation.

Current-class and historical-class `evidence_class` values remain different
on purpose.

---

## 7. Create-once / real-bytes law

| Failure | Already enforced? | Cutover action |
| --- | --- | --- |
| 061 current directory missing | yes, `_enumerate_package` | keep; test against real root |
| 061 current directory empty | yes, `_enumerate_package` | keep |
| current member missing vs prepared manifest | yes, `_validate_files` | keep |
| current member byte mismatch vs prepared manifest | yes, `_validate_files` | keep |
| extra file in real 061 dir | next prepare would include it; no committed current completeness field today | focused real-byte digest test fails if count/digest change |
| unexpected current execution ID | only fails if that directory is missing | document that next 4/2/2 must name `MIGRATION_061_20260823T200709Z`; do not add a profile execution-ID field |
| 059 historical missing/tampered/extra | yes, `enumerate_historical_migration_evidence` | declare 059 historical; existing validator covers it |
| current root also historical | yes, tests + path overlap checks | rebind the exclusivity test to 061 |

Do not duplicate package files into a tracked tree. Do not invent a second
current-package completeness subsystem inside `GitAuthorizationProfile`.

---

## 8. Authorization separation

This cutover is git-evidence reconciliation only.

It must not create, review, consume, clone, or refresh a 4/2/2 package. It
must not revive `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436`.
That package remains bound to migration count 59 / 059 head, one-shot flags
all false, `allowed_invocation_count=1`. After cutover it still fails package
binding and one-shot policy. Schema readiness is not campaign GO.

A **new** exact-HEAD authorization is still separately required after
cutover implementation, inspection, and schema-gate closeout.

---

## 9. Database separation

The later implementation must not write SQLite, call `apply_migrations`,
initialize or repair the operator DB, rewrite the ledger, or add migration
062.

PR 4 already proved the authoritative file. Git-evidence cutover may read
package bytes and, if a focused test needs it, read-only schema facts. It
must not mutate `data/printer_v1.sqlite3`.

`schema_admission_coherence.py`, `proof_db_schema_readiness.py`,
`migrate.py`, and migration SQL are out of scope unless a later inspection
proves a consumer still hard-codes 059 package KIND/ROOT. Current source
does not: those modules own pin/catalogue/objects, not git evidence.

---

## 10. Production consumer trace

Cutover of the two profile fields reaches every real four-token consumer
without editing those files:

| Consumer | Use |
| --- | --- |
| `git_provenance_authorization_manifest._validate_files` | current prefix `{root}/{execution_id}` |
| `validate_git_provenance_manifest_pre_marker` / `validate_git_provenance_authorization` | full current + historical boundary |
| `enumerate_historical_migration_evidence` | historical tuple, including new 059 |
| `four_token_proof_one_shot_wrapper.build_manifest_bytes` | `profile = FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE` then enumerate |
| `four_token_standard_four_hour_one_shot_wrapper.build_manifest_bytes` | same for the operational four-token profile |
| `operational_memory_factory_command` | passes the same profile objects into git-provenance validation |

Wrapper docstrings still say “migration 055” / “migration 058”. That is
pre-existing comment lag. Do not expand this cutover to rewrite those
comments unless a later implementation inspection finds a **code** path that
still hard-codes 059 KIND/ROOT. Inspected code uses `profile.migration_*`.

WINDOW_15M / two-token standard-four-hour wrappers stay on migration-050.

`pre_authorization_migration_ledger_guard` binds DB path/count/head, not
git package KIND. Leave it alone.

A later proof that only asserts constants, without
`enumerate_historical_migration_evidence` and a four-token
`build_manifest_bytes` / pre-marker validate on real or disposable package
bytes, is insufficient.

---

## 11. Test design

Minimum sufficient later proof. Tests must hash real or disposable package
bytes and call production validators. Do not inject a finished PASS flag.

A. Both four-token profiles bind `MIGRATION_061_PACKAGE_KIND` /
   `MIGRATION_061_PACKAGE_ROOT`, and those two profiles are equal to each
   other.

B. 059 is in `FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES` with the historical
   class, execution ID, count 5, and digest below. 059 is no longer
   `migration_package_root`.

C. Real 061 package inventory recomputes to
   `a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6`
   with evidence class `MIGRATION_061_EVIDENCE`.

D. Real 059 package inventory recomputes to
   `d23c4f4bbf2b4683c69038bb6fc372f85c52e280b24662cb46c133690b1479c6`
   with evidence class `HISTORICAL_MIGRATION_059_EVIDENCE`.
   `enumerate_historical_migration_evidence` accepts that declaration.

E. Disposable copy of the 061 current package with a missing or mutated
   member fails `_enumerate_package` and/or `_validate_files` / digest
   comparison. Do not mutate the real package.

F. Disposable copy of historical 059 with a missing, extra, or mutated
   member fails `enumerate_historical_migration_evidence`.

G. Current 061 root is absent from the historical tuple. Historical 059
   execution ID must not equal a current manifest `migration_execution_id`.

H. A constructed profile pair that splits 059 vs 061 is not an accepted
   production state; the production objects must not diverge. Assert
   equality of the two live four-token profiles.

I. `_enumerate_package` / `build_manifest_bytes` fail if the 061 current
   prefix directory does not exist.

J. Consumed `…512f2436` remains non-reusable (one-shot flags false; still
   bound to 59/059). Do not load it as capability.

K. Cutover tests create no authorization package and assert
   `authorization_created is False` on any helper they call.

L. No authoritative DB write; no `apply_migrations`.

M. Cycle 3 / 12h / 24h / retrieval / financial locks unchanged.

Completeness fixtures that currently write TESTONLY current files under
`MIGRATION_059_PACKAGE_ROOT` must move to the 061 current root. After 059
is historical, an untracked TESTONLY sibling under the 059 root fails
“unapproved historical migration package contains untracked files”.

---

## 12. Stale test / fixture classification

| Test / assertion | Classification |
| --- | --- |
| `test_v2_9_8b_four_token_operational_provenance_alignment.py` current-059 identity and `test_both_four_token_profiles_are_current_at_059` | **must change** to 061 current; keep “ordinary/std4h remain 050” |
| `test_current_migration_059_is_never_a_historical_package` | **generalizable invariant**; rebind to 061 current / 059 historical |
| `test_production_total_declared_hm_count_is_40` | **must change** to 45 |
| Completeness fixture current files under 059 root | **must change** to 061 current root |
| `test_v2_9_8b_four_token_proof_migration_055_evidence.py` assertions that production current is 059 | **must change** current identity; keep 055 historical identity |
| `test_profile_current_migration_evidence_is_059` and historical-root set in `test_v2_9_8b_pre_lifecycle_schema_gate_coherence.py` | **must change** git-evidence parts; leave pin/helper 61 tests |
| `test_four_token_current_migration_evidence_is_exactly_059` and historical-count 5 in `test_v2_9_8b_four_token_proof_migration_057_readiness.py` | **must change** git-evidence parts; pin-61 assertions stay |
| `test_l_four_token_current_git_evidence_remains_059` and “no MIGRATION_061_PACKAGE_* in source” | **must change**; that was the PR 1 blocked-window assertion |
| `ProfileScopeProofTests.test_only_four_token_profiles_receive_059_058_and_pair_ready` | **must change** current identity to 061; keep pair-ready reconciliation and “ordinary profiles untouched” |
| Fixture `migration_id = "MIGRATION_059_COMPLETENESS_TESTONLY"` | **must change** naming to 061 TESTONLY under the 061 root |
| `test_k_consumed_authorization_binding_unusable_against_61` | **unrelated** schema-binding lock; keep |
| `test_v2_9_8b_four_token_proof_existing_wrapper_regression_locks.py` 050 on ordinary/std4h | **unrelated**; do not touch |
| WINDOW_15M one-shot wrapper tests | **unrelated** |
| PR 2 leftover ledger-guard 052/59 disposable assertions | **unrelated stale debt**; this lane is not permission to repair them |
| Wrapper docstrings saying migration 055/058 | **unrelated comment lag**; do not broaden unless code still hard-codes 059 |

Do not opportunistically rewrite schema-helper tests that apply 001–059 only
as disposable 059 databases.

---

## 13. Failure / rollback semantics

This later implementation is a tracked git change, not a DB migration.

If real 061 current inventory or historical 059 inventory does not recompute
to the committed digest, do not commit the cutover.

Do not leave a HEAD that claims schema-61 readiness in git evidence while
profiles still name 059.

Do not invent a fallback to 059.

Do not create authorization.

Do not mutate the database.

No runtime rollback mechanism is required. `git revert` of the cutover
commit is the recovery if a later inspection finds the commit incoherent.

---

## 14. Source-of-truth question

Resolved:

- Migration 061 is the **singular** current migration-transition evidence for
  both four-token profiles (`MIGRATION_061_EVIDENCE`).
- Migration 059 is **one** immutable historical migration package
  (`HISTORICAL_MIGRATION_059_EVIDENCE`).
- There is no second current owner.

---

## 15. Later implementation file list

Minimum expected set:

| File | Change |
| --- | --- |
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | add 061 current KIND/ROOT; add 059 historical class/execution/count/digest; rebind both four-token profiles; append 059 to `FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES`; update `_NON_RECONCILIATION_EVIDENCE_CLASSES` and `__all__`; update the “current authority is 059” comments |
| Directly affected focused tests listed in §11–§12 | rebind current identity, historical membership, completeness fixtures, real-byte digest proofs |

Do **not** include, unless a later inspection proves a hard-coded 059
KIND/ROOT in code:

- `schema_admission_coherence.py`
- `proof_db_schema_readiness.py`
- `four_token_proof_one_shot_wrapper.py` (reads profile fields)
- `four_token_standard_four_hour_one_shot_wrapper.py` (reads profile fields)
- `operational_memory_factory_command.py` (passes profile objects)
- `migrate.py` / migration SQL
- Scheduler / Source Governor / campaign runtime

If implementation discovers a production file that still literals
`MIGRATION_059_PACKAGE_KIND` as **current** evidence, stop and extend this
design before editing it. Wrapper comments are not that signal.

---

## 16. Remaining sequence

Do not combine stages.

```text
this cutover design/review PASS
→ narrow git-evidence cutover implementation
→ independent implementation inspection / bounded proof
→ schema-gate coherence closeout
→ fresh exact-HEAD 4/2/2 authorization
→ independent authorization review
→ one separately operator-started post-repair 4/2/2 attempt
→ campaign closeout
```

V2-9.8B remains the active memory-growth program until that campaign
closeout. V2-10 remains blocked. Cycle 3 remains locked.

The next permitted action after this document is **only**:

```text
V2-9.8B MIGRATION-061 GIT EVIDENCE CUTOVER
NARROW IMPLEMENTATION ONLY
```

---

## 17. Permanent locks

Unchanged by this design and by the later cutover:

- Solana-only; Solana memecoin-only; paper-trading only
- no wallet / private-key / signing / live funds / live execution
- no paid API dependency
- no scoring / ranking / confidence / weighted logic
- no embeddings / vectors
- Source Governor and Central Scheduler authority unchanged
- dirty memory not used for retrieval or decisions
- `WINDOW_5M_MICRO_EVENT` support-only
- Cycle 3 locked; 12h / 24h locked
- retrieval, BUY/SELL/HOLD, positions, trades, audits, PnL locked

---

## 18. Blockers / open questions

None that block this design.

Non-blocking notes:

- Current-package execution ID remains authorization-time input. The real
  061 package identity is specified here for tests and for the later
  authorization lane; it is not a new `GitAuthorizationProfile` field.
- Empty or extra-file behavior of current packages is the existing 059
  current-evidence law. This cutover does not invent a second completeness
  engine for current packages.
- Pre-existing wrapper comment lag and leftover ledger-guard fixture
  assertions are out of scope.

---

## 19. What this review does not do

- implement the cutover
- edit `git_provenance_authorization_manifest.py`
- create or consume authorization
- write the authoritative database
- begin the narrow implementation in the same run
- skip to a fresh 4/2/2 package
