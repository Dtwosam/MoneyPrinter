# Printer V1 V2-9.8B Current-Window Source-Failure Evidence-Frontier Repair Design

## Verdict

`V2_9_8B_CURRENT_WINDOW_SOURCE_FAILURE_EVIDENCE_FRONTIER_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This design resolves the Step D blocker without rewriting historical source-failure evidence.

The repair is read-only and narrow: provider-attempt ambiguity must remain fail-closed when it can affect the canonical current 60-second provider window, while failure rows that are authoritatively proven historical must not permanently block present capacity.

## Baseline

Parent audit:

`docs/printer-v1-v2-9-8b-source-failure-lineage-boundary-audit.md`

Current accounting owner:

`src/printer_v1/sources/budget_accounting.py`

Current canonical window:

`DEFAULT_WINDOW_SECONDS = 60`

Current positive attempt timestamp authority:

`printer_source_requests.requested_at`

No historical DB backfill is authorized.

## Problem

Step C currently calls `_require_unambiguous_attempt_linkage(conn, source_name)` before applying the 60-second cutoff.

That guard scans all historical response/failure evidence for the provider. Therefore one old unlinked failure can make `recent_consumed_provider_attempts(...)` fail forever even when the row cannot affect current provider capacity.

The repair must narrow ambiguity validation to evidence capable of intersecting the current accounting window without weakening current-window fail-closed behavior.

## Chosen architecture

Keep one canonical read-only provider-attempt projection in `budget_accounting.py`.

Do not add a second accounting subsystem and do not mutate source history.

The projection has two evidence roles:

1. **Positive attempt authority** — only a linked `printer_source_requests.requested_at` may establish that an attempt consumes current provider capacity.
2. **Negative historical exclusion authority** — persisted row insertion evidence may prove only that an unlinked failure was already historical before the current cutoff.

Negative exclusion evidence must never be converted into a synthetic request timestamp.

## Current-window evidence frontier

For a projection at `now`:

```text
cutoff = now - DEFAULT_WINDOW_SECONDS
```

The canonical request window remains inclusive:

```text
requested_at >= cutoff  => current-window attempt
requested_at < cutoff   => historical attempt
```

### A. Linked response or failure evidence

For exactly linked evidence:

- load the linked request;
- require exact source/request identity consistency;
- parse canonical `printer_source_requests.requested_at` as the attempt timestamp;
- if `requested_at >= cutoff`, structural ambiguity or mismatch fails closed;
- if `requested_at < cutoff`, the row cannot consume the current window and does not block present capacity.

A linked current-window response-backed or attributable-failure row continues to become a `ConsumedProviderAttempt` exactly as Step C defines.

### B. Unlinked failure evidence

An unlinked failure has no lawful positive attempt timestamp.

Use `printer_source_failures.created_at` only to answer the negative question:

> Was this failure row already persisted before the current provider-window cutoff?

The canonical recorder omits `created_at`; SQLite supplies it at insertion. For this purpose the repair may parse only the canonical SQLite UTC `datetime('now')` representation used by the schema.

Classification:

```text
created_at < cutoff
    => PROVABLY_HISTORICAL_OUTSIDE_CURRENT_WINDOW
    => do not count; do not block current capacity

created_at >= cutoff
    => CURRENT_WINDOW_COULD_BE_AFFECTED
    => fail closed

created_at missing / malformed / non-canonical / ambiguous
    => fail closed
```

Equality stays fail-closed because the canonical window is inclusive.

`created_at` must never appear as `ConsumedProviderAttempt.requested_at`, provider expiry time, or later `package_ready_at`.

### C. Unlinked response evidence

The current production schema requires `printer_source_responses.source_request_id NOT NULL`.

If an unlinked response is nevertheless observable under an unsupported or corrupted schema, fail closed. Do not add a historical fallback for response rows in this repair.

### D. Linked mismatch

A linked mismatch must be scoped by the linked request's canonical timestamp:

- linked request `requested_at >= cutoff` => fail closed;
- linked request `requested_at < cutoff` => historical inconsistency does not contaminate current provider capacity;
- missing/malformed linked request timestamp => fail closed.

No nearest-time inference is allowed.

## Migration 037 boundary

Migration 037 introduced `printer_source_failures.source_request_id`.

The operational database's `printer_schema_migrations.applied_at` may be inspected during read-only readiness proof and reported as provenance context.

It is **not required by the runtime projection** and must not become a substitute for either:

- canonical linked `requested_at`; or
- the current 60-second cutoff.

This keeps the production repair smaller and avoids coupling rate accounting to migration-history parsing.

## Canonical parser rule for negative historical evidence

Add one narrow private parser for failure `created_at` historical exclusion.

Requirements:

- accept only the canonical SQLite UTC timestamp format produced by `datetime('now')`;
- interpret it as UTC;
- reject missing, blank, malformed, offset-bearing, or otherwise non-canonical values;
- do not silently normalize arbitrary timestamp formats;
- do not reuse `_canonical_utc_timestamp`, because that function is for timezone-aware request timestamps and has a different authority meaning.

Second-level SQLite precision is acceptable for negative exclusion because only strict `< cutoff` qualifies as historical. Any equality/precision uncertainty fails closed.

## Refactor boundary

Replace the global `_require_unambiguous_attempt_linkage(...)` behavior with a current-window-aware validation/selection law.

Preferred implementation shape:

1. require current schema;
2. compute canonical UTC `cutoff` once;
3. inspect provider-linked and provider-named response/failure evidence;
4. classify structural ambiguity against the current-window frontier;
5. select linked response-backed / attributable-failure requests;
6. parse linked request `requested_at`;
7. keep only attempts with `requested_at >= cutoff`;
8. preserve deterministic ordering `(requested_at, source_request_id)`.

`count_recent_source_requests(...)` must continue to return:

```text
len(recent_consumed_provider_attempts(...))
```

There must remain one shared selection law.

## Current production failure persistence

The canonical governed execution path already:

1. records `printer_source_requests`;
2. receives a `SourceRequestRecord`;
3. passes that record to `record_source_failure(...)`.

The repair does not change this execution path.

Focused proof must still demonstrate that a current governed failure produces non-null exact `source_request_id` linkage.

The lower-level `record_source_failure(SourceRequest, ...)` compatibility surface is not removed in this lane. If a current operational caller creates an unlinked failure, the current-window frontier must fail closed rather than mask it.

## Explicitly forbidden alternatives

Do not:

- backfill the 45 historical failure rows;
- infer source-request IDs from nearest timestamps;
- use `failed_at` as request timing;
- use `created_at` as request timing;
- use `retry_after_at` or Source Governor `retry_after_seconds`;
- use `SequentialRequestPacer` timing;
- add a DB migration;
- delete or quarantine historical rows;
- weaken current-window ambiguity into zero consumption;
- implement provider package-fit or `recheck_at` in this repair.

## TDD implementation sequence

### RED

Add focused tests proving the current Step C behavior is wrong or incomplete for:

1. old unlinked failure with canonical `created_at < cutoff` currently blocks but must become historical-only;
2. unlinked failure with `created_at == cutoff` must fail closed;
3. unlinked failure with `created_at > cutoff` must fail closed;
4. missing/malformed/non-canonical `created_at` must fail closed;
5. linked current-window source/request mismatch must fail closed;
6. linked historical mismatch with canonical request `requested_at < cutoff` must not contaminate current capacity;
7. existing linked response/failure selection remains unchanged;
8. count/detail parity remains exact.

### GREEN

Implement only the minimum current-window evidence-frontier logic in `budget_accounting.py`.

Do not implement package capacity, `recheck_at`, admission health, or callback behavior.

## Minimum proof

Run only risk-based focused verification:

- new current-window evidence-frontier tests;
- existing `tests/test_v2_9_8b_provider_reaching_attempt_detail.py`;
- existing focused E2C-B budget-accounting tests affected by the refactor;
- focused governed-execution failure-linkage test proving canonical new failures are linked;
- `py_compile` for touched production modules;
- `git diff --check`.

Then run the mandatory operational DB rereadiness check in strict read-only mode:

- open `data/printer_v1.sqlite3` with `mode=ro` and `PRAGMA query_only=ON`;
- record SHA-256 before/after;
- report migration-037 `applied_at` as provenance context;
- classify manifest-provider unlinked failures by the new current-window frontier;
- prove no ambiguous evidence capable of intersecting the current 60-second window at the inspection instant;
- confirm Step C detail projection can execute for every manifest provider.

If current-window ambiguity remains, STOP. Do not resume Step D.

## Money-usefulness contribution

This repair prevents stale historical persistence artifacts from permanently disabling safe corpus growth while preserving strict provider-budget protection for evidence that can actually affect current discovery capacity.

It improves the chance that Printer can lawfully add the second exact two-token cycle without weakening Source Governor accounting or rewriting audit history.

## What this lane improves

- aligns ambiguity checking with the actual 60-second capacity question;
- preserves exact request-timestamp authority;
- keeps historical evidence immutable;
- keeps new/current unlinked failures fail-closed;
- restores a lawful path toward provider package-capacity projection.

## What this lane still does not unlock

This lane does not unlock:

- provider package-fit;
- provider `recheck_at`;
- `MultiCycleAdmissionHealth`;
- later-cycle discovery callback;
- cycle-2 admission/persistence;
- factory wake integration;
- source fetching;
- memory generation;
- proof authorization/runtime;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

`TOKEN_CAPACITY` remains 2.

## Functionality Risks / Setbacks / Efficiency Blockers

- A historical row must not be ignored unless its insertion evidence proves strict pre-cutoff exclusion.
- SQLite `created_at` has second precision, so boundary equality/uncertainty must remain blocked rather than rounded away.
- A malformed old row can still block current capacity if its historical exclusion cannot be proved; this is intentional fail-closed behavior.
- The low-level bare-`SourceRequest` failure-recording API remains capable of producing unlinked rows, so operational misuse can still cause a safe block.
- The live operational DB rereadiness check is mandatory before Step D resumes.

## Closeout condition

This repair is complete only when:

1. focused RED/GREEN proof passes;
2. count/detail parity remains exact;
3. current canonical governed failures remain linked;
4. zero DB/source/Scheduler/runtime mutation occurs in the projection;
5. live DB read-only rereadiness shows no current-window ambiguity for all manifest providers.

Then and only then resume:

**Step D — provider package capacity and exact `recheck_at`.**

## Design verdict

`V2_9_8B_CURRENT_WINDOW_SOURCE_FAILURE_EVIDENCE_FRONTIER_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`
