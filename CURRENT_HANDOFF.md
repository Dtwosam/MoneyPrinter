# CURRENT_HANDOFF — Printer V1

## Current lane

`V2-9.8B POST-MIGRATION FRESH NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE ONLY`

The explicitly approved controlled application of migration 062 is closed:

`V2_9_8B_MIGRATION_062_CONTROLLED_APPLICATION_PASS`

Application closeout:

`operator-runs/v2-9-8b-migration-062-application/MIGRATION_062_20260828T182504Z/migration_062_controlled_application_closeout.md`

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

Current authoritative DB SHA-256:

`dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836`

The authoritative DB now has canonical migration count 62 and tip
`062_pre_admission_attempt_evidence.sql`. Controlled application preserved all
pre-existing critical row counts, passed integrity and foreign-key checks,
created the exact additive table/index/four-trigger object set, and left the new
attempt-evidence table at zero rows. The verified pre-application backup remains
preserved in the application evidence directory.

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`

It remains permanently consumed and non-reusable.

## Latest completed work

Migration 062 was applied exactly once through the canonical migration runner
after exact operator approval. The fresh byte-identical backup, disposable
restore rehearsal, pre/post identities, row-count reconciliation, schema-object
proof, process/sidecar checks, and focused offline tests are recorded in the
application evidence directory. No Printer, provider, Source Governor, Central
Scheduler, campaign, authorization, retrieval, financial, or remote-host work
ran as part of the application.

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

Perform the **read-only post-migration fresh next-bounded-campaign readiness /
governance phase**. It may establish the exact final Git identity, new
authoritative DB identity and health, migration-062 continuity, runtime
quiescence, historical evidence continuity, consumed-authorization non-reuse,
and permanent-lock continuity.

This handoff does **not** authorize preparing, creating, or applying a new
authorization; running Printer; contacting providers/RPC/WebSocket; running
Central Scheduler; mutating the authoritative DB; resuming remote-host work; or
unlocking retrieval, financial capability, or longer windows. Any later
authorization preparation/review remains a separate lane after readiness PASS,
and execution would still require separate explicit operator approval.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No wallet/private
keys/signing/real funds/live execution. No paid API dependency. No
scoring/ranking/confidence/weighted decision logic. No Source Governor or
Central Scheduler bypass. No dirty-memory retrieval/decisions. Retrieval and
all financial capability remain locked. `WINDOW_5M_MICRO_EVENT` remains
support-only. `WINDOW_12H` and `WINDOW_24H` remain locked.

The active authority stack wins any conflict with this handoff.
