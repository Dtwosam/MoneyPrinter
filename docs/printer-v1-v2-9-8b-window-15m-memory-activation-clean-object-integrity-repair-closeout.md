# Printer V1 V2-9.8B WINDOW_15M Memory Activation and Clean-Object Integrity Repair Closeout

## Verdict

`V2_9_8B_WINDOW_15M_MEMORY_ACTIVATION_CLEAN_OBJECT_INTEGRITY_REPAIR_PASS`

This is an implementation and isolated-test closeout only. No proof ran, no
authorization was created or consumed, no provider was contacted, no discovery
or Scheduler runtime ran, and the authoritative database was not opened or used
by tests.

## Baseline and branch

- Required tracked baseline / starting HEAD:
  `3f4a7ad4ea653fec7ece4e6a469643898260cd87`
- Baseline ancestry: verified with `git merge-base --is-ancestor`.
- Repair branch:
  `agent/v2-9-8b-window-15m-memory-activation-clean-object-integrity-repair`
- Starting tracked worktree: clean.
- Intentional operator-supplied untracked inputs at start:
  - `docs/printer-v1-v2-9-8b-window-15m-full-memory-path-readiness-audit.md`
  - `docs/printer-v1-v2-9-8b-window-15m-memory-activation-clean-object-integrity-design.md`
- Supplied audit SHA-256:
  `02db8ff1f1184a6797a20fbb63bebe961162c115d524589b7d22ee92ee5c8cba`
- Supplied design SHA-256:
  `ca493612d3eff7c333b1e7bab5d0410e883452430dcbc841c2f5710ac7c48f15`
- Python environment: repository `.venv`, Python 3.12.13.
- No active Printer/database process or authoritative-database handle was found
  before implementation.

## Files changed

Implementation:

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/pilot_input_readiness.py`
- `src/printer_v1/memory/clean_object_promotion.py`
- `src/printer_v1/operator_cli/e2z_clean_memory_creation.py`
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`

Tests:

- `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`
- `tests/test_v2_9_8b_campaign_manifest_evidence_repair.py`
- `tests/test_v2_9_8b_remaining_runtime_blocker_repair.py`

Documents:

- the two supplied audit/design documents listed above
- `docs/superpowers/plans/2026-08-05-window-15m-memory-activation-clean-object-integrity.md`
- this closeout

No migration was added.

## Confirmed defects and repairs

### 1. Holder context incorrectly blocked memory activation

`MEMORY_OBSERVATION` now separates holder condition from tracking and evidence
quality. Holder pass, fail, source-unavailable and budget-bound unknown remain
truthful context without creating `HOLDER_EVIDENCE_INELIGIBLE` or blocking the
memory path. `fully_eligible` is true only for a measured healthy/pass holder;
future-action eligibility stays blocked or unknown otherwise. The legacy
non-memory holder gate is unchanged.

### 2. A second selector could replace the freeze authority

The exact pair is constructed directly from
`freeze_eligible_reserve().selected`. The immutable contract carries slot
ordinals 1 and 2 in order. In memory mode the combined executor validates and
uses that pair directly; it does not invoke `_select()` or category-composition
logic. Alternates are typed report-only evidence and are never substituted.

### 3. Activation manufactured new source evidence

The new retained-evidence contract validates exact request/response rows,
response ownership, clean/complete status, response hash, mint, pool,
observation time, manifest membership and measured transport identities. The
combined executor creates only Scheduler-owned discovery projection/link rows
with `RETAINED_GOVERNED_EVIDENCE_REFERENCE`; it does not call
`_governed_request()` or `_store_response()`.

### 4. Tracking was not a freeze input

The campaign now performs an exact identity-based tracking assessment
independently of holder safety before `MEMORY_OBSERVATION_ELIGIBLE` admission.
Ineligible or requalification-required candidates receive categorical EXCLUDED
reserve evidence and cannot enter the four-candidate freeze. The executor
revalidates the frozen identities during the atomic two-slot handoff; any
changed state rolls back both slots with no alternate substitution.

### 5. Episode and fingerprint committed separately

`promote_clean_object()` owns one SQLite savepoint/transaction for the eligible
window, clean episode, canonical fingerprint, exact identity validation and
commit. A fingerprint failure rolls back the episode. An exact complete pair is
idempotent; an incomplete or mismatched existing object blocks without repair
or mutation. Lane K no longer opens a second fingerprint connection.

## Readiness and terminal reporting

- Readiness now reports `ordered_selected_candidates` with exact slot ordinal,
  mint, pool, market identity, true provenance, holder/future-action context,
  tracking feasibility and retained request/response IDs.
- Migration-041 `latest` and `persisted` fields remain positional compatibility
  fields only and are explicitly labelled
  `POSITIONAL_COMPATIBILITY_ONLY`.
- `liquidity_observed_at` comes from the candidate's exact retained market
  evidence, never report generation time.
- Lane K reports episode ID, fingerprint ID, atomic status, idempotency and exact
  integrity blocker.
- A legitimate dirty/partial/no-promotion close remains honest. A clean-object
  integrity failure makes the close fail with the exact categorical cause.
- Current-run terminal acceptance counts clean success only when the run's clean
  episode has one exact canonical fingerprint with matching episode/window/token/
  pair/window-kind identity.

## Source request and transport reconciliation

Focused activation tests demonstrate:

- original request and response IDs are reused in projection links;
- activation source-request delta is zero;
- activation source-response delta is zero;
- every activation request is present in the immutable manifest;
- each required transport identity is present in the measured identity set;
- manifest, transport, mint, pool, response-hash or observation-time mismatch
  blocks before handoff;
- no table-count-only inference is used by the retained-reference validator;
- report-only replay remains zero-source and zero-write.

Legacy readiness fixtures that supplied request coverage but deliberately had no
retained market response now assert the categorical
`RETAINED_EVIDENCE_REFERENCE_INCOMPLETE` blocker. The repair does not invent the
missing rows to preserve their former readiness result.

## Atomic clean-object evidence

Isolated SQLite tests prove:

- clean episode and fingerprint are created together;
- exact episode/window/token/pair/window-kind identity is present and never
  `UNKNOWN`;
- injected fingerprint failure leaves zero new episode and fingerprint rows;
- replay of an exact complete pair is idempotent;
- an existing episode without a fingerprint blocks without mutation;
- a mismatched fingerprint blocks without rewrite;
- factory close accounting blocks exact atomic-integrity failure while an
  honest no-promotion result remains lawful;
- current-run terminal acceptance rejects clean window labels without complete
  clean objects.

## Focused tests and commands

Passing commands/results:

- Final activation/authorization/holder/combined verification:
  `127 passed in 23.04s`.
- Final E2Z/Lane K/report-only replay verification:
  `204 passed, 5 subtests passed in 53.56s`.
- Repair, freeze, holder-budget, holder-manifest/accounting and campaign
  reconciliation:
  `102 passed in 65.34s`.
- Lane E2Z, Lane K and promotion alignment:
  `198 passed in 51.44s`.
- Repair plus terminal clean-memory validation:
  `69 passed, 32 subtests passed`; one unrelated stale provenance fixture failed
  as documented below.
- Authorization/retention, combined executor/handoff and terminal accounting:
  `108 passed`; seven unrelated stale migration-head assertions failed as
  documented below.
- Report-only replay, exact accounting identity, holder safe-stop/accounting and
  combined handoff:
  `105 passed, 5 subtests passed`; one unrelated missing DB-binding fixture
  failed as documented below.
- Python compilation of directly changed modules: PASS.
- `git diff --check` over all implementation, test, plan and closeout files:
  PASS. The unmodified operator-supplied audit/design inputs are excluded from
  that whitespace-only check because they contain intentional Markdown
  two-space hard breaks; their required SHA-256 values remain exact.

All tests used disposable temporary databases created by the test harness.

## Unrelated pre-existing/stale focused-test failures

These failures were not expanded into this lane because their failing
preconditions are outside the changed path:

1. Seven cases in
   `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` assert that
   the migration head starts with `050`; the repository baseline migration head
   is already `052_memory_observation_eligibility_layers.sql`.
2. One case in `tests/test_v2_9_2_terminal_budget_repair.py` calls final reporting
   without the now-required exact Git provenance fixture and fails in
   `validate_launch_provenance()` before this repair's terminal validation.
3. One ordinary disposable regression in
   `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` invokes
   the ordinary 15m path without the now-required operational database target
   binding and fails before discovery or this repair path.

## Authoritative database identity

Recorded without connecting to the database:

- Path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- Before size: `68067328` bytes
- Before mtime: `2026-08-05T11:18:15+0100`
- Before SHA-256:
  `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb`
- After size: `68067328` bytes
- After mtime: `2026-08-05T11:18:15+0100`
- After SHA-256:
  `ecf0557cf213b44b51f840983e5472a53777f609dee650580d1844e7b01ac2bb`

Identity is unchanged.

## Locks preserved

The repair remains Solana-only, memecoin-only and paper-only. It does not enable
1h/4h/12h/24h production, retrieval, BUY/SELL/HOLD, paper decisions, positions,
trades, audits, PnL, live execution, wallet/private-key/signing/funding logic,
paid APIs, scoring, ranking, confidence, weighting, embeddings or vectors. It
does not bypass Source Governor or Central Scheduler and adds no retry, resume,
restart, successor or alternate substitution.

## Money-usefulness contribution

The repaired path preserves otherwise useful but holder-uncertain observations
as honest 15m memory context, while preventing untrackable candidates, false
source evidence and half-created clean objects from contaminating the corpus.
That improves the realism and auditability of future clean-memory comparison
without creating a decision or financial capability.

## Functionality Risks / Setbacks / Efficiency Blockers

- Exact retained-evidence activation intentionally blocks older/disposable
  carriers that do not include source response and measured transport identity;
  no compatibility fabrication is allowed.
- Transport identity association is categorical and fail-closed. Ambiguous
  repeated same-source/same-kind manifests require exact target identity and
  will block rather than infer ownership.
- Existing historical incomplete clean episodes are not backfilled by this
  repair; they remain categorical review blockers.
- A full unscoped `git diff --check` reports only the intentional Markdown
  hard-break spaces already present in the two hash-pinned operator inputs.
- The unrelated stale test fixtures listed above remain for a separate narrow
  maintenance lane.

## What remains locked and next step

No WINDOW_15M run is authorized. No proof or authorization ran. The only next
step is an independent read-only review of this branch, commit and closeout.
PASS does not authorize a campaign, provider contact, proof, authorization,
retrieval activation or any financial action.
