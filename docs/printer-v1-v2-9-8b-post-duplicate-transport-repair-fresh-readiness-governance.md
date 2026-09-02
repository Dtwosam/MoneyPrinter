# Printer V1 V2-9.8B Post-Duplicate-Transport-Repair Fresh Readiness / Governance

Date: 2026-09-02

Verdict:

`V2_9_8B_POST_DUPLICATE_TRANSPORT_REPAIR_FRESH_EXACT_HEAD_EXACT_DB_READINESS_PASS`

## 1. Purpose

This is the currently permitted lane at audit start:

`POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE ONLY`

It is read-only readiness/governance after the later-cycle cooperative
mint-market-batch duplicate-transport authoritative repair. It does not prepare
or apply an authorization, run Printer, start a campaign, contact
providers/RPC/WebSocket, run Central Scheduler operationally, mutate the
authoritative DB, or unlock any capability.

The authorization-boundary design remains already complete:

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-preparation-boundary-design.md`

Classification of that design remains `EXISTING_OWNER_ALREADY_SUFFICIENT`.
Do not redo it.

## 2. Authority

Active source stack:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Current-lane files at audit start:

- `CURRENT_HANDOFF.md`
- `docs/printer-v1-v2-9-8b-later-cycle-duplicate-transport-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-auth-12a7ea61-campaign-closeout.md`

Those sources all named this readiness/governance lane as the exact next
permitted action. Older historical pointers were not used. No authority
conflict was found.

## 3. Git readiness

| Item | Value |
| --- | --- |
| Branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Live starting HEAD audited | `b2497d8a434de3adad79432117f05ec097fa11b6` |
| Parent / integrated repair | `041e2550ec2ec090e45eec2d8de45f6a0c1e84f0` |
| Repair-closeout parent / campaign closeout | `903046d7dc6b215b80eeed5633072eb1cd39dfe2` |
| Historical execution HEAD remaining ancestral | `91c757c542d8098ecf7b244769061f333dcfc21f` |
| Tracked working tree at audit start | clean |
| Staged | empty |
| Merge / rebase / cherry-pick in progress | none |
| Untracked | previously known `operator-runs/...` evidence directories only |

Ancestry was established from live `git log` / `git rev-parse`, not from a
remembered HEAD. Repair commit `041e2550` is the parent of the audited HEAD.
Historical execution HEAD `91c757c5` remains in ancestry.

No unexplained tracked drift exists on this HEAD.

## 4. Authoritative DB identity

Canonical `inspect_authoritative_database` over
`/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`:

- exists / readable: true
- opened mode: `read_only_immutable`
- SHA-256: `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c`
- size: `154796032`
- inode: `1230526`
- mtime_ns: `1788310792540112946`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- `PRAGMA integrity_check`: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars (`-wal` / `-shm` / `-journal`): none

This freshly calculated SHA matches the post-campaign / repair-closeout
identity. The DB was not restored and was not mutated.

Canonical `evaluate_schema_admission_coherence`:
`admission_schema_ready=True`, empty blocker codes. Summary:
`schema admission coherence: schema-ready (not campaign GO)`.

Required pin remains `REQUIRED_MIGRATION_COUNT=62` /
`REQUIRED_MIGRATION_HEAD=062_pre_admission_attempt_evidence.sql`.

## 5. Durable zero-state

Canonical `project_four_token_proof_zero_state` is zero across every required
domain:

| Domain | Count |
| --- | ---: |
| active_campaigns | 0 |
| active_campaign_runs | 0 |
| active_campaign_cycles | 0 |
| active_campaign_scheduler_work | 0 |
| campaign_supervision (`ACTIVE`/`STOPPING`) | 0 |
| proof_supervision | 0 |
| active_discovery_work | 0 |
| active_factory_runs | 0 |
| active_factory_steps | 0 |
| pre_admission_discovery_attempts outside terminal dispositions | 0 |
| active_pre_lifecycle_discovery_refresh_work | 0 |
| active_scheduler_jobs | 0 |

Additional read-only corroboration:

- campaign supervision unreleased leases (`lease_released_at IS NULL`): `0`
- all 75 campaign-supervision rows: `TERMINAL`
- candidate-acquisition leases: 19 historical `TERMINAL`; unreleased `0`
- source requests pending/running: `0` (4531 historical `COMPLETE`)
- latest campaign `20260901T205859Z-89a1f9b9b2bd-campaign`: `TERMINAL_COMPLETED`,
  supervision `TERMINAL`, lease released
  `2026-09-02T00:59:50.736115+00:00`
- 12a7ea61 Cycle 2 pre-admission attempt
  `...89a1f9b9b2bd-cycle-2` is historical `FAILED` /
  `LATER_CYCLE_SUPPLY_EXCEPTION_CAMPAIGNSIXUNITERROR`, not active work
- 12a7ea61 Cycle 1 slots are historical `MANUAL_REVIEW`

Four historical `SELECTED` token-slot rows remain. They are **not** active
ownership:

| Slot | Campaign / cycle state |
| --- | --- |
| `slot-20260727T001520Z-d513e21260b5-cycle-1` | `TERMINAL_FAILED` / `TERMINAL_FAILED` |
| `slot-20260727T001520Z-d513e21260b5-cycle-2` | `TERMINAL_FAILED` / `TERMINAL_FAILED` |
| `slot-20260830T120215Z-7fb82f2d6a65-cycle-2-1` | `TERMINAL_FAILED` / `TERMINAL_FAILED` |
| `slot-20260830T120215Z-7fb82f2d6a65-cycle-2-2` | `TERMINAL_FAILED` / `TERMINAL_FAILED` |

Raw historical slot state alone does not establish active execution authority.
Canonical campaign/run/supervision/lease/Scheduler/factory/progression/
pre-admission ownership truth governs active-work readiness. The Aug-30 Cycle-2
`SELECTED` rows remain untouched historical residue.

## 6. Runtime quiescence

- canonical `active_printer_runtime_processes(...)`: empty
- no matching Printer / Memory Factory / four-token operational process
- no `lsof` holders on the authoritative DB
- live campaign lease lock file absent
- no competing operational writer

## 7. Consumed authorization trust

### 12a7ea61

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`

- canonical package present under
  `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization/`
- exactly one canonical application marker;
  `authorization_consumed_at=2026-09-01T20:58:56.789413+00:00`
- wrapper terminal: `CHILD_EXITED_ZERO`; `child_exit_code=0`;
  automatic retries / manual reruns / resumes / restarts / successors all `0`
- authorized execution HEAD `91c757c542d8098ecf7b244769061f333dcfc21f`
- permanent disposition remains
  `CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`

Canonical `extract_approved_historical_authorization_ids` accepts that
package's declared prior root (57 IDs).

### ab6c68fe

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

- remains inside the 12a7ea61 prior root
- marker consumed at `2026-09-01T19:14:47.648742+00:00`
- wrapper `child_exit_code=1`
- permanent disposition remains
  `CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

### Stale unapplied

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

- remains inside the 12a7ea61 prior root
- no application marker exists
- remains
  `STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

### Complete future prior-non-reuse trust root

Derived from the most recent consumed operational package plus that package's
own ID, then checked against governance-required IDs:

- 12a7ea61 prior root: 57 IDs
- plus `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`
- complete future root: 58 unique lexicographically sorted IDs
- required IDs present: `12a7ea61`, `ab6c68fe`, stale `b6d7ab46`,
  `a89ed6bc`, `5fcb1bf5`, `804f9a32`, `7e03d673`

No currently prepared fresh authorization exists. The newest canonical package
is consumed `12a7ea61`. Every application-marker directory under the one-shot
namespace has `authorization_consumed_at` set. No previous package can inherit
authority. Markers and authorization files were not modified.

Any future Standard-4H package must include this complete 58-ID root and must
not reuse, rebind, renew, or revive any member.

## 8. Repair-specific readiness

Inspected current production owner on this HEAD, no further code change:

`load_completed_cooperative_mint_market_batch_mints` in
`src/printer_v1/discovery/eligible_token_supply.py`

Present behavior on the exact HEAD:

- completed current-cycle/current-scope DexScreener `MINT_MARKET_BATCH` round
  transport (`COMPLETE` + `CLEAN_DATA` + exact canonical due-mint identity) is
  rehydrated across cooperative resume;
- successful transport is not treated as fresh MOE completion;
- failed / rate-limited / partial / dirty / malformed / foreign / distinct
  transport remain unsuppressed;
- missing `campaign_source_request_scope` still fails closed through
  `validate_campaign_source_request_scope` /
  `validate_cooperative_resume_source_request_scope`;
- `CampaignSixUnitOwner` is unchanged;
- `DUPLICATE_TRANSPORT_IDENTITY` remains fail-closed.

The repair closeout already proved the focused GREEN suite. This readiness did
not rerun that suite. Presence of the owner on the ancestral repair commit is
sufficient.

Unchanged:

- Source Governor remains sole source authority
  (`SOURCE_GOVERNOR_UNCHANGED_NO_BYPASS`);
- Central Scheduler remains sole scheduling authority
  (`CENTRAL_SCHEDULER_UNCHANGED_NO_BYPASS`);
- freeze-ready depth `MINIMUM_FREEZE_DEPTH == 4`;
- 4 freeze-ready -> 2 selected + 2 report-only alternates;
- concurrent capacity exactly 2;
- up to 4 campaign-wide identities;
- Cycle 2 fresh/disjoint identity rule unchanged;
- no request-budget increase;
- no endpoint rotation;
- no automatic retry/rerun/resume/restart/successor.

## 9. Seven WINDOW_15M scope-test failures

Required classification of
`tests/test_v2_9_8b_window_15m_source_request_scope_repair.py` on this HEAD:

`19 passed / 7 failed`

The same seven tests fail on parent `903046d7` and on the repaired tree. They
are not a regression from the duplicate-transport repair. They were not
expanded into a production or test change in this lane.

Canonical current contract for request-key membership:

`request_key_belongs_to_root(key, root)` is `key == root or key.startswith(root + "-")`

Production Standard-4H request keys use the hyphenated suffix
(`{root}-locator`, `{root}-migration-page-live-tail`, `{root}-mint-batch-rN`).
The older file still inserts `{root}|...` pipe-delimited fixture keys.

Canonical superseding owner/tests:

- production assemble path:
  `assemble_and_reconcile_campaign_source_requests` with typed
  `campaign_source_request_scope`
- freeze-ready forwarding:
  `tests/test_v2_9_8b_campaign_source_request_scope_propagation_repair.py`
  (`8 passed` at repair closeout; not rerun here)
- live 12a7ea61 campaign completed Cycle 1
  `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` under this owner; it did not fail
  source-request reconciliation

None of the seven failures is an active Standard-4H production defect or a
readiness blocker.

### Failure 1

- test:
  `TestScopedDurableReconciliation.test_pass_has_each_current_request_exactly_once_in_d_s_m`
- exact assertion:
  `assert recon["status"] == "OK"`; observed `BLOCKED`
- observed recon:
  `CAMPAIGN_SOURCE_REQUEST_RECONCILIATION_MISMATCH` /
  `CURRENT_STAGE_REQUEST_OUTSIDE_CAMPAIGN_SCOPE` +
  `MANIFEST_REQUEST_NOT_DURABLE`; durable set empty; transport identity `OK`
- claimed owner: scoped D/S/M assemble equality
- Standard-4H use: yes, via freeze-ready assemble with hyphenated production
  keys
- supersession: typed-scope assemble + hyphen membership; newer freeze-ready
  forwarding tests
- could recur in another authorized campaign: only if production emitted
  `{root}|...` keys; it does not
- classification: stale fixture delimiter (`|` instead of `-`)
- readiness impact: non-blocking

### Failure 2

- test:
  `TestScopedDurableReconciliation.test_prefix_lookup_detects_durable_omitted_from_stage_reporting`
- exact assertion:
  `assert recon["status"] == "BLOCKED"`; observed `OK`
- observed recon: durable/prefix-lookup empty because `{root}|orphan` is
  foreign under hyphen membership, so empty D/S/M is an honest OK
- claimed owner: prefix lookup of omitted durable IDs
- Standard-4H use: hyphenated current-scope rows only
- supersession: `request_key_belongs_to_root`; passing same-file tests that
  insert `{root}-locator`
- could recur: no, for production hyphenated keys omitted durable rows still
  block
- classification: stale fixture delimiter
- readiness impact: non-blocking

### Failure 3

- test:
  `TestScopedDurableReconciliation.test_durable_omitted_from_coverage_categorized`
- exact assertion:
  `assert rid in recon["missing_from_manifest"]`; observed `[]`
- same `{root}|nomanifest` fixture exclusion from D
- claimed owner: durable-not-manifested category
- supersession: same hyphen membership contract
- could recur: no for production keys
- classification: stale fixture delimiter
- readiness impact: non-blocking

### Failure 4

- test:
  `TestScopedDurableReconciliation.test_ordinary_provider_failure_reconciles_when_coverage_complete`
- exact assertion:
  `assert recon["status"] == "OK"`; observed `BLOCKED`
- fixture key `{root}|blocked` is foreign; stage/coverage IDs therefore sit
  outside D
- claimed owner: ordinary provider `BLOCKED` coverage still reconciles when
  transport/coverage is complete
- Standard-4H use: production coverage uses in-scope hyphenated keys
- supersession: hyphen membership; transport-identity exactness remains OK on
  this fixture
- could recur: no for production keys
- classification: stale fixture delimiter
- readiness impact: non-blocking

### Failure 5

- test:
  `TestScopedDurableReconciliation.test_terminal_detail_contains_category_count_and_bounded_ids`
- exact assertion:
  `assert detail is not None`; observed `None` because status is OK
- fixture keys `{root}|o{i}` are excluded from D, so no defect is reported
- claimed owner: terminal-detail formatting of omitted durable IDs
- supersession: same as Failure 2
- could recur: no for production keys
- classification: stale fixture delimiter
- readiness impact: non-blocking

### Failure 6

- test:
  `TestScopedDurableReconciliation.test_multiple_defects_use_multiple_category_token`
- exact assertion:
  `assert durable_only in recon["durable_not_stage_reported"]`; observed `[]`
- fixture key `{root}|only` is excluded from D
- claimed owner: multiple-category terminal token
- supersession: same hyphen membership; same-file
  `test_stage_only_non_durable_categorized` still passes
- could recur: no for production keys
- classification: stale fixture delimiter
- readiness impact: non-blocking

### Failure 7

- test:
  `TestNoCapabilityExpansion.test_static_permanent_path_cannot_use_legacy_default`
- exact assertion: `graduated_supply_front_door.py` text contains
  `LEGACY_STATIC_REQUEST_SCOPE_BLOCKED_OPERATIONALLY` or
  `validate_permanent_operational_request_prefixes`
- that file is now a thin adapter over `_graduated_supply_front_door_base.py`;
  the strings live in the base module and
  `permanent_discovery_availability.py`
- claimed owner: static proof that permanent composition cannot use the
  legacy default
- Standard-4H use: yes; production still fail-closes missing/legacy/mismatch
  scope **before provider I/O**
- supersession:
  `tests/test_v2_9_8b_campaign_source_request_scope_propagation_repair.py::test_persistent_signature_and_freeze_ready_call_forward_scope`
  inspects the base module; same-file
  `TestPermanentOperationalScopeGates` (6 tests) all passed, including
  `test_legacy_static_prefix_blocks_before_provider_io`
- could recur: no; the operational gate remains live
- classification: stale file-location assumption
- readiness impact: non-blocking

**Active code/readiness blocker from these seven failures: none.**

## 10. Standard-4H envelope / permanent locks

Canonical `exact_operational_policy()` remains:

- policy `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- command mode `four-token-standard-four-hour-run`
- 2 cycles; 2 tokens/cycle; 4 through-4h identities
- `automatic_retries=0`; `endpoint_rotation=false`
- `long_windows_activated=false`; locked `WINDOW_12H`, `WINDOW_24H`
- root main window `WINDOW_15M`
- freeze-ready depth `MINIMUM_FREEZE_DEPTH == 4`
- concurrent selected capacity remains 2

Window law unchanged: `WINDOW_15M -> WINDOW_1H -> WINDOW_4H -> stop`;
`WINDOW_5M_MICRO_EVENT` support-only. Cycle-2 fresh/disjoint remains owned by
`validate_later_cycle_atomic_activation`. Source Governor and Central Scheduler
remain authoritative.

Permanent V1 locks unchanged: Solana-only; Solana memecoin-only; paper-only; no
live wallet/private keys/signing/real funds/live execution; no paid API
dependency; no scoring/ranking/confidence/weighted logic; no embeddings/vectors
unless explicitly approved; no dirty-memory retrieval/decisions; retrieval and
all financial capability locked.

## 11. Non-mutation proof

| Item | Before | After |
| --- | --- | --- |
| DB SHA-256 | `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c` | identical |
| size / inode / mtime_ns | `154796032` / `1230526` / `1788310792540112946` | identical |
| tracked repository | clean | clean |
| authorization packages | 25 historical; newest consumed `12a7ea61` | unchanged |
| canonical zero-state domains | all 0 | all 0 |

No provider/source calls. No Scheduler ticks. No Printer process launched.
Authoritative DB remained byte-identical.

## 12. Verification

- live Git identity / ancestry / tracked-clean / no in-progress rewrite
- canonical DB inspect, schema coherence, zero-state, runtime-process probe,
  and prior-non-reuse extraction
- extra read-only lease / slot / pre-admission / source-request corroboration
- application-marker consumed-at scan
- `tests/test_v2_9_8b_window_15m_source_request_scope_repair.py`:
  `19 passed, 7 failed`, with each failure classified from source
- disposable-fixture reproduction of the pipe-versus-hyphen membership cause

No broad suite. No provider/source calls.

## 13. Next permitted action

This documentation-only synchronization commit becomes the exact live HEAD that
a later separately approved preparation lane must bind. Do not reuse
`b2497d8a...` after this commit exists.

Exact next permitted lane after this commit:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION
```

Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H
authorization package using the existing canonical authorization owners, binding
the actual HEAD of this readiness commit and the freshly re-read authoritative
DB identity, including the complete 58-ID prior non-reuse trust root (12a7ea61
prior root plus
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`), and stop unconsumed
for independent package review.

Do not redo the completed authorization-boundary design. Do not create an
application marker. Do not call `apply_authorization_once`. Do not run Printer.
Do not enter that preparation lane automatically.
