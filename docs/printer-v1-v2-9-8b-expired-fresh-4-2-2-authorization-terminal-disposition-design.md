# Printer V1 V2-9.8B Expired Fresh 4/2/2 Authorization Terminal Disposition Design

Date: 2026-08-24

Starting HEAD: `34e1e5ab242a90ece92b48ce43b17acb8d3909c4`

Verdict:

`V2_9_8B_EXPIRED_FRESH_4_2_2_AUTH_TERMINAL_DISPOSITION_PASS_HISTORICAL_ADOPTION_DESIGNED`

## Decision

The immutable authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a` is permanently
unusable as execution authority and must remain at its existing package path as
historical authorization evidence.

The minimum existing-authority disposition is
`EXISTING_HISTORICAL_AUTHORIZATION_ADOPTION_REQUIRED`. No new evidence class,
package root, reconciliation allowlist, or relocation is required.

## Terminal truth

The create-once package remains:

- path:
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260823T221645Z_6af1423a/final_authorization.json`;
- SHA-256:
  `c0d05a6c9de103e911f00d7f7e471e27d08fa983a57c6de33b6286a55388fb69`;
- size: `4218` bytes;
- mode: `0444`;
- bound HEAD: `34e1e5ab242a90ece92b48ce43b17acb8d3909c4`;
- expiry: `2026-08-24T10:20:29.759170+00:00`;
- terminal cause: `AUTHORIZATION_EXPIRED`;
- independently reviewed: no;
- consumed: no;
- durable manifest, marker, child, campaign, and runtime ownership: absent.

The package failed transient pre-marker reconciliation while unconsumed and
later expired. It cannot be refreshed, retried, resumed, restarted, succeeded,
rewritten, or reused. Historical adoption must not change any package byte or
reinterpret it as reviewed or consumed.

## Existing historical owner

`GitAuthorizationProfile.historical_authorization_package_roots` already
includes the package's current root for the four-token Standard-4H profile.
Historical trust is not created by directory discovery. It comes from the
future current authorization document's explicit, sorted
`prior_authorizations_non_reusable` list.

`extract_approved_historical_authorization_ids` and
`validate_prior_authorizations_non_reusable` validate that trust root.
`enumerate_historical_authorization_evidence` then inventories only approved
IDs under approved roots and emits exact per-file path, size, SHA-256, evidence
class, authorization ID, and diagnostic terminal disposition.

Expired-but-unconsumed and consumed packages use this same historical evidence
class. Consumption state does not create a second trust mechanism. The
diagnostic disposition is non-authoritative for reuse and is separate from the
per-file cryptographic binding.

## Future reconciliation proof

Read-only enumeration using a distinct audit-only future current ID proved:

- omitting `...6af1423a` from the future trust root fails closed with
  `unapproved historical authorization package contains untracked files not covered by the trust root`;
- including it produces exactly one historical record for the immutable file,
  with size `4218` and SHA-256
  `c0d05a6c9de103e911f00d7f7e471e27d08fa983a57c6de33b6286a55388fb69`;
- after conceptually removing only the nine separately classified top-level
  patch artifacts, reconciliation accounts for all `174` current
  `operator-runs` files as `T=78`, existing future-current Migration-061
  `M=5`, `Ha=34`, `Hm=45`, and `Hr=12`;
- no second undeclared path remains;
- the terminal package is historical `Ha`, not current `M`, and is not ignored.

The future authorization file does not exist in this audit. When a later
authorized preparation creates it, that one new file must join current `M`.

## Required narrow adoption

The current diagnostic result for `...6af1423a` is
`DISPOSITION_NOT_AVAILABLE`. Existing precedent assigns blocked, unconsumed,
marker-absent packages the already-approved diagnostic
`BLOCKED_UNCONSUMED_SUPERSEDED`.

A later narrow implementation must therefore:

1. add the exact authorization ID to the existing
   `_POLICY_TERMINAL_DISPOSITIONS` map with
   `BLOCKED_UNCONSUMED_SUPERSEDED`;
2. add focused proof that future historical enumeration, when the exact ID is
   present in the future document's trust root, emits the exact path, size,
   SHA-256, authorization ID, historical evidence class, and disposition;
3. prove omission from that trust root still fails closed;
4. prove it never appears in current `M`, never creates reuse authority, and
   remains distinct from consumed authorization `...512f2436`;
5. require every later fresh authorization preparation to include the exact ID
   in its complete sorted `prior_authorizations_non_reusable` list.

Expected production scope:

- `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

Expected focused test scope:

- `tests/test_v2_9_8b_four_token_historical_migration_provenance.py`, or one
  mechanically equivalent directly focused historical-authorization test.

No vocabulary, root, wrapper, runtime, schema, migration, Scheduler, Source
Governor, provider, or database change is justified.

The immutable package and this checkpoint preserve the more specific historical
truth: preparation blocked at reconciliation, independent review never passed,
expiry later made the exact identity terminal, and no consumption or runtime
occurred. `BLOCKED_UNCONSUMED_SUPERSEDED` remains diagnostic only.

## Distinct prior history

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436` remains a separate
historical authorization with a real consumption marker and permanent
non-reuse law. It must not be collapsed with the unconsumed expired package.

## Separate operator artifacts

The nine top-level patch/diff artifacts remain classified
`HISTORICAL_OPERATOR_ARTIFACT_NOT_RUNTIME_AUTHORITY`. Their later authorized
hash-preserving relocation outside the worktree is an operator-environment
action. It is not authorization historical adoption and does not move, adopt,
or dispose of the expired package.

## Remaining sequence

1. narrow historical-authorization adoption implementation and focused proof;
2. separately authorized hash-preserving relocation of the nine operator patch
   artifacts;
3. exact-HEAD and worktree rereadiness;
4. separately authorized completely new create-once four-token 4/2/2
   authorization preparation;
5. independent authorization review;
6. one separately operator-started campaign, if every later gate passes;
7. campaign closeout.

No automatic replacement, same-package review, manifest construction,
authorization application, campaign, provider call, SQLite write, Cycle 3,
V2-10, retrieval, or financial capability is authorized by this design.
