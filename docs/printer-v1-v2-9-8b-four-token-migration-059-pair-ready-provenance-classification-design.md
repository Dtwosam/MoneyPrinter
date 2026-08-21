# Printer V1 V2-9.8B Four-Token Migration-059 / PAIR_READY Provenance Classification Design

Date: 2026-08-21

## Verdict

`V2_9_8B_FOUR_TOKEN_MIGRATION_059_PAIR_READY_PROVENANCE_CLASSIFICATION_DESIGN_PASS`

This is an approved narrow provenance-classification design. It authorizes a
focused TDD implementation and directly affected verification only. It does
not authorize an application marker, manifest, authorization application,
Printer launch, provider/RPC/WebSocket contact, Source Governor or Central
Scheduler runtime, campaign, authoritative database mutation, or any retrieval
or financial capability.

## Classification and root cause

Primary blocker classification: `CONTRACT_DRIFT` with an approved repair
boundary.

The authoritative database and preserved operator evidence lawfully advanced
through Migration 059 and the PAIR_READY residual reconciliation. The committed
four-token provenance profiles still classify Migration 058 as current and do
not classify the exact PAIR_READY reconciliation package. Consequently the
strict complete-inventory reconciliation correctly rejects legitimate current
repository evidence as unexplained. The repair belongs in the canonical Git
provenance authorization-manifest owner; `_reconcile_evidence_sets()` must not
be weakened.

## Evidence classification

`CURRENT` migration:

- `059`

`HISTORICAL` migrations, in exact order:

- `050`
- `055`
- `056`
- `057`
- `058`

`HISTORICAL` reconciliation:

- all existing profile-bound historical reconciliation packages;
- the exact PAIR_READY residual reconciliation package.

Migration 059 remains current evidence whose execution identity and exact
files are preparation-time bound by the authorization/manifest contract. The
production profile should declare only its current package root and evidence
kind. Migration 058 moves to an exact immutable `HistoricalMigrationPackage`.
The PAIR_READY residual reconciliation becomes an exact immutable
`HistoricalReconciliationPackage`.

## Set law

Let:

- `C` be the enumerated current package inventory;
- `M` be the manifest-bound current evidence inventory;
- `T` be tracked operator-run history;
- `Ha` be approved historical authorization evidence;
- `Hm` be exact historical migration evidence;
- `Hr` be exact historical reconciliation evidence;
- `F` be the complete operator-runs filesystem inventory considered by the
  production preparation boundary.

Current-package equality remains exactly:

```text
C == M
```

Complete inventory remains exactly:

```text
F = T ∪ M ∪ Ha ∪ Hm ∪ Hr
```

All evidence sets remain disjoint under the existing trust model. Historical
migration or reconciliation paths can never satisfy current-package equality.

## Exact trust boundary

No wildcard trust, prefix-only trust, or directory-discovery trust is allowed.
Every historical package must bind:

- one exact package root;
- one exact execution ID;
- one distinct evidence class;
- the exact expected file count;
- the exact canonical inventory SHA-256;
- every exact repository-relative regular-file path, byte size, and SHA-256
  where the historical reconciliation contract requires member declarations.

Missing, mutated, added, symlinked, non-regular, aliased, overlapping, or
unexplained sibling evidence fails closed. Existing production enumeration and
digest primitives must derive all identities; implementation must not guess
hashes.

## Profile scope

Rotate current migration authority from Migration 058 to Migration 059 for the
two four-token profiles that currently share Migration 058:

- `FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE`;
- `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`.

Do not change ordinary `WINDOW_15M` or two-token Standard-4H profile semantics.

Attach the exact PAIR_READY historical reconciliation package to the smallest
profile scope proven necessary by complete-inventory preparation. The minimum
expected scope is `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`; include
the four-token proof profile only if its real preparation namespace otherwise
rejects the same exact five legitimate files.

## Blocked authorization disposition

Authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d` remains immutable,
unconsumed, marker-absent, manifest-absent, and ineligible for the repaired HEAD.

Only if the existing production diagnostic-disposition map is the canonical
owner, record:

```text
V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T124505Z_8cf7ee5d
-> BLOCKED_UNCONSUMED_SUPERSEDED
```

This is diagnostic only. It must not alter authorization bytes, mark the
authorization consumed, create a marker, or create reuse authority.

## Required TDD and proof

RED must reproduce the current strict production failure for the legitimate
Migration-059 plus PAIR_READY inventory:

```text
GitProvenanceAuthorizationError:
unexpected untracked repository file not covered by manifest
```

GREEN must prove:

1. Migration 059 is current evidence and obtains its execution identity from
   the authorization/preparation contract, not historical directory discovery.
2. Migration 058 is exact historical migration evidence only and cannot satisfy
   current Migration-059 equality.
3. PAIR_READY is exact historical reconciliation evidence only.
4. Missing, mutated, extra, wrong-execution, sibling, symlink, non-regular,
   arbitrary-unrelated, overlap, and current-inventory mismatch cases block.
5. Exact-HEAD validation, create-once marker law, single child-launch ownership,
   one-attempt/no-retry/no-rerun/no-resume/no-restart/no-successor rules, and
   direct-command fail-closed behavior remain unchanged.
6. The blocked authorization SHA remains
   `644a7b16c7055334e59ab5aa4e820f712b055f8fa4e902d3b9810389fe2724b7`,
   with no marker, no consumption, and no repaired-HEAD authority.
7. The authoritative DB remains byte-identical at
   `87dac0d15ee32940f7dda30d0704dc252ff540c9d6f1ff6a3857e8f598c9f2fa`
   with migration `59 / 059_pair_ready_parent_terminal_cancellation_transition.sql`
   and no sidecars.

## Hard locks

- no authorization application or replacement authorization;
- no manifest or application marker;
- no Printer launch or child process;
- no provider/RPC/WebSocket contact;
- no Source Governor or Central Scheduler runtime;
- no authoritative database mutation or campaign;
- no editing, deleting, moving, renaming, staging, or committing operator-run
  evidence;
- no weakening exact-HEAD, complete-inventory, disjointness, or current-package
  equality;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper
  audits, PnL, wallet/signing/live execution, paid APIs, scoring/ranking/
  confidence/weighted logic, embeddings/vectors, or 12h/24h capability.

## Money-usefulness contribution

The repair lets the one-shot preparation boundary classify the exact legitimate
schema-transition and reconciliation history without deleting evidence or
broadening trust. This protects the next bounded paper-only collection attempt
from consuming scarce authorization on a provenance-classification defect.

## Functionality Risks / Setbacks / Efficiency Blockers

- Risk: Migration 058 remains current by accident. Mitigation: rotate both
  proven four-token profiles to 059 and assert `C == M` against 059 only.
- Risk: PAIR_READY gains broad directory trust. Mitigation: exact five-file
  member declarations plus canonical reconciliation digest and sibling checks.
- Risk: reconciliation is misclassified as migration evidence. Mitigation:
  retain distinct closed evidence vocabularies and set membership.
- Risk: the blocked authorization is mistaken for reusable authority.
  Mitigation: diagnostic `BLOCKED_UNCONSUMED_SUPERSEDED` only, with immutable
  bytes and no consumption marker.
- Setback: any local evidence identity that cannot be reproduced with existing
  primitives blocks implementation; no guessed hash or weakened negative test
  is allowed.

## Next permitted lane

`V2-9.8B Four-Token Migration-059 / PAIR_READY Provenance Classification TDD Implementation`

After an implementation PASS, the exact next lane is the separately bounded
proof. No replacement authorization may be constructed in this implementation
lane.
