# Printer V1 V2-9.8B Migration-061 Git Evidence Cutover Design

**Document status:** `DESIGN / REVIEW ONLY`

**Date:** 2026-08-23

**Branch:**
`agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`

**Required starting HEAD:**
`bb6260d7311af1355e5990714b214ed98d64a0a3`

**Parent design commit:**
`bb6260d7311af1355e5990714b214ed98d64a0a3`

**Verdict:**
`V2_9_8B_MIGRATION_061_GIT_EVIDENCE_CUTOVER_DESIGN_AMENDMENT_PASS_READY_FOR_NARROW_IMPLEMENTATION`

This lane is a documentation-only amendment of the accepted cutover topology.
It does not implement the cutover, edit production or tests, write
`data/printer_v1.sqlite3`, apply a migration, or create or consume
authorization.

The parent design's topology remains: 061 becomes singular current four-token
migration evidence; 059 becomes immutable historical evidence. This amendment
**replaces** the parent design's test-only 061 execution/digest facts with a
production-consumed `GitAuthorizationProfile` current-evidence identity
contract.

Passing this amendment means the later implementation is specified. It does
not mean git evidence has moved, a campaign is authorized, V2-9.8B is
complete, or V2-10 is ready.

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

### Proven blocker amended here

The parent design committed 061 execution ID, file count, and current-class
digest, then left prepare/validate on the previous root/kind +
caller-supplied execution-ID shape. Those facts would have been test/review
constants, not production-consumed evidence authority. That would still
permit:

1. a syntactically valid sibling execution ID under the 061 root to be
   selected; or
2. current-package bytes changed before manifest construction to be
   enumerated and then validated against the manifest generated from those
   same changed bytes.

This amendment binds the exact real 061 identity onto both four-token
profiles and requires `validate_git_provenance_manifest_pre_marker` to
enforce it before any review-PASS, marker, or usable authorization.

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

### Execution-ID binding (amended)

Today `GitAuthorizationProfile` has no execution-ID field. A later
authorization document and its git-provenance manifest both carry
`migration_execution_id`. The later cutover **adds** optional
`current_migration_execution_id` (and matching count/digest fields) so
four-token profiles can require the document/manifest ID to equal the
committed 061 identity. Ordinary profiles keep `None` and therefore keep
today's caller-supplied execution-ID shape.

Today `validate_git_provenance_manifest_pre_marker` already requires the
manifest and authorization-document execution IDs to match each other.
`_validate_files` then requires every current migration file to live under:

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
must be coherent. Tests must assert the two profiles share:

- `migration_package_kind`
- `migration_package_root`
- `current_migration_execution_id`
- `current_migration_expected_file_count`
- `current_migration_expected_inventory_sha256`
- `historical_migration_packages`

The later implementation should keep using the shared
`FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES` object so the two profiles cannot
drift on historical membership. The same three current-identity constants
must be passed into both profile constructors.

---

## 4. New 061 current-evidence contract

Do **not** reuse `HistoricalMigrationPackage` for current evidence. Its
docstring states that class never satisfies current-package identity.

### 4.1 Producer: optional profile identity fields

Extend `GitAuthorizationProfile` with three OPTIONAL fields whose names
follow existing `migration_package_*` and historical
`expected_file_count` / `expected_inventory_sha256` / `execution_id`
conventions:

```text
current_migration_execution_id: str | None = None
current_migration_expected_file_count: int | None = None
current_migration_expected_inventory_sha256: str | None = None
```

Defaults are `None`. Ordinary WINDOW_15M and two-token standard-four-hour
profiles omit them and keep today's root/kind + caller-supplied execution-ID
shape.

All-or-nothing: a profile may bind all three or none. One or two set is
malformed and must fail closed at profile construction or at the canonical
validator, before any PASS.

Module-level constants (same pattern as historical 058/059 identities) are
the values bound **into** both four-token profiles. They are not test-only:

| Name | Value |
| --- | --- |
| `MIGRATION_061_PACKAGE_KIND` | `MIGRATION_061_EVIDENCE` |
| `MIGRATION_061_PACKAGE_ROOT` | `operator-runs/v2-9-8b-migration-061-application` |
| `FOUR_TOKEN_CURRENT_MIGRATION_061_EXECUTION_ID` | `MIGRATION_061_20260823T200709Z` |
| `FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_FILE_COUNT` | `5` |
| `FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_INVENTORY_SHA256` | `a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6` |

Current evidence class remains `MIGRATION_061_EVIDENCE`, not
`HISTORICAL_MIGRATION_061_EVIDENCE`.

Both four-token profiles set:

```text
migration_package_root = MIGRATION_061_PACKAGE_ROOT
migration_package_kind = MIGRATION_061_PACKAGE_KIND
current_migration_execution_id = FOUR_TOKEN_CURRENT_MIGRATION_061_EXECUTION_ID
current_migration_expected_file_count = FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_FILE_COUNT
current_migration_expected_inventory_sha256 = FOUR_TOKEN_CURRENT_MIGRATION_061_EXPECTED_INVENTORY_SHA256
historical_migration_packages = FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES
```

`MIGRATION_061_20260823T200709Z` is a valid `require_safe_authorization_id`
value. Filesystem discovery of a sibling directory must never promote a
second current package.

### 4.2 Independently recomputed 061 inventory

Recomputed at amendment HEAD from the live untracked PR-3 package using
`compute_historical_migration_inventory_sha256` and evidence class
`MIGRATION_061_EVIDENCE`. Matches PR 4 and the parent design.

| path under the execution directory | size | sha256 |
| --- | --- | --- |
| `apply_migration_060_061.py` | 39030 | `362aa42b8b52f679f0583eedfbbe2c46f0af27c8d059ce843ccda4c20d922997` |
| `backup_restore_rehearsal.json` | 42034 | `9e4100eb2c4b59afae4f0f3df77719a3567fdd5d680b2a27dfb72a27ef380bc5` |
| `migration_060_061_application_receipt.json` | 28785 | `fecacf1649cf7e862aac1f4b7e9c057a92c4d4ddc6a351d247a4597b308170d1` |
| `post_application_snapshot.json` | 29299 | `590ec13b88cf75aba830808b73dd687135aa4573b2a31c7752006eeeb264ff2d` |
| `pre_application_snapshot.json` | 29600 | `906d3c302794c656dbea438b3758fae7ac0fcc46f0f171f39bfa7f6846ace0af` |

Current-class digest:

`a6eac8d12e30e9f134c137f79a8b72bbe4f9af9d62e65e159a025c5c87108bd6`

The digest under `HISTORICAL_MIGRATION_061_EVIDENCE` remains
`ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459`.
That class is **not** proposed.

During later implementation, recompute this current-class digest from the
live 061 package before committing the constant. If it differs, STOP.

### 4.3 Consumer: canonical pre-marker validator

**Producer:** committed four-token current-061 profile identity (the three
new fields plus KIND/ROOT).

**Consumer:** `validate_git_provenance_manifest_pre_marker`.

`validate_git_provenance_authorization` already calls that function first.
Four-token `apply_authorization_once` already calls it as
`pre_marker_validator` **before** writing `application-marker.json` and
before child launch. Manifest construction via `build_manifest_bytes` may
still enumerate live bytes, including a wrong sibling ID. That is acceptable
only because no review-PASS, marker, or usable authorization can occur until
pre-marker validation succeeds.

Do not add a parallel wrapper check unless implementation inspection proves
a four-token path that becomes review-PASS without
`validate_git_provenance_manifest_pre_marker`. Inspected source has no such
path.

When a profile binds current-migration identity, the canonical validator
must, in this order:

A. Require `manifest.migration_execution_id` equals
   `profile.current_migration_execution_id`. Also require the authorization
   document's `migration_execution_id` equals that same expected ID
   (`_validate_authorization_document` already requires document ID equals
   manifest ID; add the profile comparison there or immediately beside it).

B. Inventory the COMPLETE directory
   `{migration_package_root}/{current_migration_execution_id}` with the
   existing `_inventory_bound_package_files` owner (same complete-directory
   law as historical packages). Do not inventory a caller-selected sibling.

C. Require file count equals
   `current_migration_expected_file_count`.

D. Compute SHA-256 with existing
   `compute_historical_migration_inventory_sha256`, using
   `evidence_class = profile.migration_package_kind`
   (`MIGRATION_061_EVIDENCE` on the four-token profiles). No new hash
   convention.

E. Require that digest equals
   `current_migration_expected_inventory_sha256`.

F. Then preserve existing `_validate_files` per-member path/size/SHA
   validation against the manifest.

A manifest that is internally consistent with **tampered live bytes** must
still FAIL at E, because E compares to the committed profile digest, not to
the manifest's own file hashes.

When all three identity fields are `None`, skip A–E. Ordinary profiles keep
today's behavior.

Add `MIGRATION_061_PACKAGE_KIND` to `_NON_RECONCILIATION_EVIDENCE_CLASSES`
and export the new public names in `__all__`. Do not copy the package into
a tracked directory.

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

Independently recomputed at amendment HEAD from the live 059 package with
that historical class. Matches PR 4 and the parent design.

During later implementation, recompute this historical digest from the live
immutable 059 package before committing. If it differs, STOP rather than
silently replacing this value.

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
| extra file in real 061 dir | **not** against a committed current digest today | pre-marker identity check: count/digest FAIL |
| unexpected current execution ID / sibling ID | only fails if that directory is missing today | pre-marker requires profile `current_migration_execution_id` |
| bytes changed before manifest construction | today the new manifest would self-validate | pre-marker digest vs committed expected digest FAIL |
| 059 historical missing/tampered/extra | yes, `enumerate_historical_migration_evidence` | declare 059 historical; existing validator covers it |
| current root also historical | yes, tests + path overlap checks | rebind the exclusivity test to 061 |

Do not duplicate package files into a tracked tree. The current-identity
fields on `GitAuthorizationProfile` are the single current-evidence
completeness owner for constrained profiles. Do not add a second hash
helper or a parallel wrapper validator.

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

| Role | Owner |
| --- | --- |
| Producer | `GitAuthorizationProfile` current-061 identity fields on both four-token profiles |
| Canonical consumer | `validate_git_provenance_manifest_pre_marker` (also the first step of `validate_git_provenance_authorization`) |
| Runtime gate | four-token `apply_authorization_once` already calls that pre-marker validator before marker write and child launch |
| Historical consumer | `enumerate_historical_migration_evidence` over the shared tuple, including 059 |
| Wrapper construction | `build_manifest_bytes` still enumerates live bytes; it is **not** the identity authority |

`operational_memory_factory_command` already passes the four-token profile
objects into git-provenance validation. After the profile fields exist, that
command consumes them without a source edit.

Do not edit wrappers unless inspection proves a four-token path that can
become review-PASS without `validate_git_provenance_manifest_pre_marker`.
Inspected source has no such path. Wrapper docstrings saying migration
055/058 remain pre-existing comment lag.

WINDOW_15M / two-token standard-four-hour wrappers stay unconstrained
(`current_migration_* is None`) on migration-050.

`pre_authorization_migration_ledger_guard` binds DB path/count/head, not
git package identity. Leave it alone.

A later proof that only asserts constants, without calling
`validate_git_provenance_manifest_pre_marker` against real or disposable
061 bytes **and** `enumerate_historical_migration_evidence` for 059, is
insufficient. The expected execution/count/digest values must not be
test-only constants.

---

## 11. Test design

Minimum sufficient later proof. Tests must change underlying package
bytes/identity and call `validate_git_provenance_manifest_pre_marker` (and
historical enumerate where applicable). Do not inject a finished PASS flag.

A. Exact real 061 execution ID plus exact live bytes → current-evidence
   validation PASS through the canonical pre-marker validator.

B. Another syntactically valid sibling execution ID under the same 061
   root, even with a complete package, → FAIL (profile expected execution
   ID mismatch). Do not mutate the real package; use a disposable tree.

C. Mutate a 061 file **before** manifest construction → FAIL against the
   committed expected inventory digest, even if the manifest is built from
   the mutated bytes.

D. Add an extra file **before** manifest construction → FAIL exact file
   count/digest.

E. Remove a member **before** manifest construction → FAIL.

F. Mutate a member **after** manifest construction → existing `_validate_files`
   SHA/size check still FAIL.

G. Both live four-token profiles have identical KIND, ROOT, execution ID,
   file count, digest, and historical tuple.

H. Ordinary profiles with all three identity fields `None` preserve
   existing root/kind + caller-supplied execution-ID behavior.

I. Historical 059 missing/extra/mutated remains fail closed via
   `enumerate_historical_migration_evidence`.

J. Current 061 root cannot appear in the historical tuple.

K. Old consumed `…512f2436` remains unusable (one-shot flags false; still
   bound to 59/059). Do not load it as capability.

L. Cutover tests create no authorization; `authorization_created is False`.

M. No SQLite writes; no `apply_migrations`.

N. Cycle 3 / V2-10 / retrieval / financial locks unchanged.

Completeness fixtures that currently write TESTONLY current files under
`MIGRATION_059_PACKAGE_ROOT` must move off that root. After 059 is
historical, an untracked TESTONLY sibling there fails unapproved-historical
package law. Synthetic completeness profiles that need a passing
TESTONLY current package must **not** copy production
`current_migration_*` fields; leave them `None` or bind them to the
synthetic inventory. Production four-token profiles must keep the real
061 identity.

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
| `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py` | add optional `current_migration_*` fields on `GitAuthorizationProfile`; add 061 KIND/ROOT and identity constants; bind both four-token profiles to the exact 061 identity; consume that identity in `validate_git_provenance_manifest_pre_marker` (and document-ID equality); add 059 historical class/execution/count/digest; append 059 to `FOUR_TOKEN_HISTORICAL_MIGRATION_PACKAGES`; update `_NON_RECONCILIATION_EVIDENCE_CLASSES` and `__all__`; update “current authority is 059” comments |
| Directly affected focused tests listed in §11–§12 | rebind current identity, historical membership, completeness fixtures, real-byte fail-closed matrix A–N |

Do **not** include, unless a later inspection proves the canonical validator
cannot enforce identity without them:

- `schema_admission_coherence.py`
- `proof_db_schema_readiness.py`
- `four_token_proof_one_shot_wrapper.py`
- `four_token_standard_four_hour_one_shot_wrapper.py`
- `operational_memory_factory_command.py`
- `migrate.py` / migration SQL
- Scheduler / Source Governor / campaign runtime

If implementation discovers a production file that still literals
`MIGRATION_059_PACKAGE_KIND` as **current** evidence, stop and extend this
design before editing it. Wrapper comments are not that signal.

---

## 16. Remaining sequence

Do not combine stages.

```text
this design amendment PASS
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

This DESIGN/AMENDMENT lane does not implement the cutover.

After this amended design closes PASS, the next permitted lane **is**:

```text
V2-9.8B MIGRATION-061 GIT EVIDENCE CUTOVER
NARROW IMPLEMENTATION ONLY
```

Do not authorize anything beyond that lane. Do not skip to a fresh 4/2/2
package.

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

None that block this amendment. The parent design's test-only identity
binding is withdrawn.

Non-blocking notes:

- Ordinary profiles remain unconstrained (`current_migration_* is None`).
- Wrapper comment lag and leftover ledger-guard fixture assertions stay
  out of scope.
- Completeness fixtures that need synthetic current packages must not copy
  production `current_migration_*` values.

---

## 19. What this review does not do

- implement the cutover
- edit `git_provenance_authorization_manifest.py`
- create or consume authorization
- write the authoritative database
- begin the narrow implementation in the same run
- skip to a fresh 4/2/2 package
