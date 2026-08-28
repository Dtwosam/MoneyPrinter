# CURRENT_HANDOFF — Printer V1

## Current lane

`V2-9.8B MIGRATION 062 — CONTROLLED APPLICATION READINESS / AUTHORITY GATE`

The four-defect 4/2/2 orchestration repair and its independent follow-up code
review/corrective proof are closed with verdicts:

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_IMPLEMENTATION_PASS`

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_FOLLOWUP_REPAIR_PASS`

Governing closeout:

`docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-implementation-closeout.md`

Governing Cycle-2 amendment:

`docs/printer-v1-v2-9-8b-cycle-2-cooperative-acquisition-design-amendment.md`

## Current repository state

Active reviewed branch:

`repair/v2-9-8b-422-followup`

Reviewed product-code repair commit:

`91ec3131318f5bff4d3c6dfed12b09c5b6747827`

Its parent implementation baseline is:

`ea8d8d633994245a597bd4aae64fb5e303cbcd97`

The current branch HEAD is a documentation-only governance successor of that
reviewed product-code commit. The follow-up closeout addendum was recorded by
documentation commit `02b9da8c000c3c44a846efda8053159939cda5a4`;
this handoff update follows it. No source, test, migration, or database change is
authorized by those documentation-only successors.

Authoritative DB:

`data/printer_v1.sqlite3`

Previously recorded authoritative DB SHA-256:

`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`

The authoritative DB remains the post-campaign DB with migration 061 applied.
Migration 062 exists in the repository and has been exercised only on
disposable test databases. It has not been applied to the authoritative DB.
The hosted follow-up proof did not contain the authoritative DB, so it did not
re-hash that file; instead it verified that the follow-up repair commit contains
no `data/printer_v1.sqlite3` diff.

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

It remains permanently consumed and non-reusable.

## Latest completed work

The original four repair areas remain implemented:

- exact owned 1h campaign-window binding before E2Z/Lane Q;
- existing-owner, one-Source-Governed-request cooperative Cycle-2 acquisition
  with deterministic terminal replay and fixed +600/+1200/+1800 opportunities;
- append-only attempt-owned terminal evidence and deterministic certificate
  reconstruction through additive migration 062; and
- independent transport observation plus cumulative pre-close reservation
  reconstruction under strict owner/action equality.

Independent review of the actual implementation then found and corrected five
follow-up gaps inside that approved scope:

- the real delayed-refresh composition now stops after at most one newly
  executed Source-Governed request per cooperative claim;
- attempt evidence preserves exact `(mint,pair)` re-observations and outcome
  facts rather than collapsing them to weaker token-local truth;
- the durable attempt reducer is the terminal certificate count authority, with
  exact-identity compare-and-swap compatibility for an already-existing
  expected certificate and fail-closed conflict handling;
- the cumulative PRE_CLOSE reservation checkpoint is durable before provider
  execution, while replay does not duplicate action-local observation; and
- full-run PRE_CLOSE accounting requires and verifies the immutable exact
  source-unit manifest.

Independent bounded follow-up proof:

- **5 passed** follow-up regressions;
- **22 passed** retained original orchestration tests;
- **167 passed, 1 deselected, 8 subtests passed** in nearby affected acceptance
  families;
- changed-module compilation and `git diff --check` passed.

The single deselected nearby test is the authoritative-DB identity check because
the hosted checkout intentionally lacked `data/printer_v1.sqlite3`. It was not
weakened or replaced. The final workflow's non-success conclusion came only
from a stale `git push --force-with-lease` after all substantive proof gates had
passed and after the branch had already advanced to the clean product-code
repair commit.

Remote-host / VPS work remains paused and preserved separately at branch
`agent/remote-host-linux-portability-implementation`, HEAD
`f61419f2db37fc5eb220c20fafeaf15501218033`.

## Exact next permitted action

Perform the **read-only readiness/authority-gate phase** for controlled
application of migration 062 to the authoritative DB.

That gate must verify, without applying the migration:

- exact reviewed repository/product-code identity and authoritative DB identity;
- migration 062 SQL identity, digest/order, additive-only scope, and schema-head
  expectations;
- backup creation procedure and disposable restore rehearsal readiness;
- exclusive authoritative DB writer/process state and absence of unsafe
  WAL/SHM/journal/process conditions;
- exact pre/post integrity, foreign-key, schema/version, critical row-count, and
  semantic-identity checks required for a future controlled application; and
- rollback evidence and explicit governance/application approval boundary.

This handoff does **not** authorize applying migration 062, creating or applying
an authorization, running Printer, contacting providers/RPC/WebSocket, or
running Central Scheduler against the authoritative DB. A fresh campaign
readiness and authorization decision remains later and separate.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No wallet/private
keys/signing/real funds/live execution. No paid API dependency. No
scoring/ranking/confidence/weighted decision logic. No Source Governor or
Central Scheduler bypass. No dirty-memory retrieval/decisions. Retrieval and
all financial capability remain locked. `WINDOW_5M_MICRO_EVENT` remains
support-only. `WINDOW_12H` and `WINDOW_24H` remain locked.

The active authority stack wins any conflict with this handoff.