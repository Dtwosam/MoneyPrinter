# Printer V1 V2-9.8B Source-Failure Lineage-Boundary Audit

## Verdict

`V2_9_8B_SOURCE_FAILURE_LINEAGE_BOUNDARY_AUDIT_PASS_READY_FOR_SCOPED_CURRENT_WINDOW_REPAIR_DESIGN`

The Step D stop was correct. The operational database contains manifest-provider failure rows without `source_request_id`, and Step C correctly refuses to invent `printer_source_requests.requested_at` for them.

The blocker does **not** justify historical DB backfill yet. Static root-cause inspection shows the current Step C ambiguity guard is broader than the 60-second provider-capacity authority it protects: it scans the provider's entire failure/response history before applying the current-window cutoff. A historical unlinked row can therefore block provider capacity forever even when it cannot affect the present 60-second window.

The smallest next repair should be a **read-only current-window/evidence-frontier repair**, not historical mutation.

## Authority and baseline

Branch:

`agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`

Baseline/final code HEAD for this audit:

`a3e0573470c9443931c8bf1cf75877ae179d9939`

Relevant active sources include the active Printer V1 source stack plus:

- `docs/printer-v1-v2-9-8b-source-free-discovery-capacity-authority-design.md`
- `src/printer_v1/sources/budget_accounting.py`
- `src/printer_v1/sources/recording.py`
- `src/printer_v1/sources/governed_execution.py`
- `migrations/001_database_foundation.sql`
- `migrations/037_holder_reliability_budget_control.sql`

No source fetching, Scheduler/runtime work, DB mutation, callback, cycle-2 admission, capacity implementation, authorization, proof, retrieval, or financial action is authorized by this audit.

## Operational evidence boundary

The immediately preceding mandatory Step D compatibility gate inspected `data/printer_v1.sqlite3` read-only and reported:

- 45 manifest-provider `printer_source_failures` rows with `source_request_id IS NULL`;
- DexScreener: 41 rows — 39 `pair_market_snapshot`, 2 `token_discovery`;
- Solana RPC: 4 `holder_concentration_reference` rows, failure IDs 9–12;
- no mismatched non-null linkage;
- GeckoTerminal, GoPlus and Helius Free passed current linkage projection;
- DB SHA-256 unchanged before/after the inspection.

Those live-DB facts are accepted as the input evidence from the preceding read-only gate. This ChatGPT environment does not mount the operator SQLite file, so this audit independently verifies the repository/code/provenance law and does not claim to have re-queried the 45 rows.

## Finding 1 — Step C is globally fail-closed, not window-scoped

`recent_consumed_provider_attempts(...)` defines the provider-capacity window from `current_time - DEFAULT_WINDOW_SECONDS`, with `DEFAULT_WINDOW_SECONDS == 60`.

However `_select_consumed_provider_attempts(...)` first calls `_require_unambiguous_attempt_linkage(conn, source_name)`, and that guard searches **all** response/failure rows involving the provider. It has no cutoff predicate.

Only after the global ambiguity guard passes are request rows selected and filtered by canonical `printer_source_requests.requested_at`.

Therefore an unlinked failure from a closed historical era can permanently produce `CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS` even when it cannot contribute to the current 60-second provider count.

`STEP_C_AMBIGUITY_SCOPE_OVER_BROAD = TRUE`

Fail-closed behavior is required for evidence that can affect the current window; it does not require every historical schema-era row to remain a permanent blocker.

## Finding 2 — migration 037 created a lineage-era boundary

Migration 037 added:

`printer_source_failures.source_request_id INTEGER REFERENCES printer_source_requests(id)`

and an index over that column.

The repository repair introducing this lineage support was committed on 2026-07-22. The operational database's exact migration `applied_at` remains the authoritative local boundary and must be read from `printer_schema_migrations` during implementation/readiness proof rather than copied from the Git commit timestamp.

This boundary may be used only as **negative historical provenance**. It must not substitute for provider-attempt `requested_at`.

## Finding 3 — canonical governed failures are currently linked

The current canonical governed execution sequence is:

1. build Governor decision;
2. persist `printer_source_requests` through `record_source_request(...)`;
3. receive a `SourceRequestRecord` containing the persisted request ID;
4. release the request write transaction before adapter work;
5. on Governor rejection or provider/adapter failure, call `record_source_failure(...)` with that `SourceRequestRecord`.

`record_source_failure(...)` derives `source_request_id = int(source_request.id)` when passed a `SourceRequestRecord`.

Thus the current canonical governed execution path persists exact failure-to-request linkage.

The lower-level helper still accepts a bare `SourceRequest`, in which case it writes `source_request_id = NULL`. Static repository search found the production governed execution owner as the operational callsite; other matches are the helper itself, tests, and documentation. No evidence was found that the current canonical provider path intentionally creates new unlinked provider-reaching failures.

Any new current-window unlinked failure must nevertheless remain fail-closed.

## Finding 4 — historical DB mutation is not the smallest repair

The provider-capacity question is only: which provider-reaching attempts consume capacity in the canonical current 60-second window?

Rewriting historical failure rows is higher risk because exact request IDs may not be reconstructible, nearest-time matching is not authoritative, `failed_at` is not the canonical attempt timestamp, and durable evidence would be mutated solely to satisfy a read-side projection.

`HISTORICAL_BACKFILL_REQUIRED = FALSE`

unless a later independent historical-audit requirement proves otherwise.

## Finding 5 — lawful current-window evidence frontier

The repair must keep `printer_source_requests.requested_at` as the **only positive provider-attempt timestamp** used for counting and package-ready calculations.

For unlinked/ambiguous evidence, another persisted timestamp may be used only to prove that a row **cannot possibly belong to the current accounting window**.

`printer_source_failures.created_at` is the strongest existing candidate because the current recorder does not supply it; SQLite assigns it when the failure row is inserted. It must never be treated as `requested_at` or enter provider-expiry arithmetic.

A lawful scoped guard should distinguish:

1. linked evidence — use linked request `requested_at`;
2. unlinked evidence provably inserted before the current cutoff — historical-only for this 60-second question; do not count it and do not let it permanently block the present window;
3. unlinked evidence whose insertion time is within the current window, missing, malformed, timezone-ambiguous, or otherwise unable to prove historical exclusion — fail closed with no healthy capacity and no synthetic recheck;
4. mismatched linked evidence associated with a request whose canonical `requested_at` is in the current window — fail closed;
5. historical mismatch whose linked request is canonically outside the window — must not contaminate current provider capacity.

The operational migration-037 `applied_at` may strengthen classification of pre-lineage-era rows, but it must not replace the cutoff or linked request timestamp.

`failed_at`, `retry_after_at`, Source Governor `retry_after_seconds`, and pacer state remain forbidden as package-ready timing authority.

## Operational row classification

From the supplied compatibility gate, exact known counts are:

- `UNLINKED_EXISTING`: 45
- DexScreener: 41
- Solana RPC: 4
- non-null linkage mismatch: 0

The exact row-by-row split among `EXACT_LINK_PROVABLE`, `HISTORICAL_OUTSIDE_CURRENT_CAPACITY_BOUNDARY`, and `AMBIGUOUS` must be produced by the scoped repair/readiness proof using the live DB's `created_at`, canonical current cutoff, migration-037 `applied_at`, and exact linked lineage already present. This audit does **not** manufacture that split from failure IDs or nearest timestamps.

For Step D, the required outcome is not that all 45 historical rows obtain links. The required outcome is that no ambiguous evidence capable of affecting the **current** 60-second window is silently ignored.

## Recommended smallest repair

Choose option **A: scoped current-window/evidence-frontier repair with no DB mutation**.

Requirements:

- preserve `recent_consumed_provider_attempts(...)` as read-only;
- preserve canonical 60-second accounting;
- preserve `printer_source_requests.requested_at` as positive attempt timestamp authority;
- scope ambiguity validation to evidence capable of affecting the current window;
- make current-window or temporally-unclassifiable unlinked evidence fail closed;
- allow provably historical rows to remain immutable without permanently blocking current capacity;
- read migration-037 `applied_at` from the DB if used; never copy a date constant;
- do not backfill source request IDs;
- do not use nearest timestamps;
- do not use `failed_at` as attempt timing;
- preserve exact count/detail parity;
- preserve zero-write behavior.

## Rejected alternatives

### B — historical exact-link backfill

Rejected as the next step. It mutates durable evidence and is unnecessary if current-window authority can be made exact without rewriting history.

### C — current failure-persistence repair first

Not required by current evidence. Canonical governed execution already persists request first and passes the persisted `SourceRequestRecord` into failure recording. The low-level bare-`SourceRequest` capability remains, but any misuse in the current window remains detectable and fail-closed.

### D — `failed_at` or retry metadata fallback

Rejected. These are not canonical request-window timestamps and cannot drive package-ready/recheck authority.

## Minimum proof before repair closeout

Focused TDD must prove:

1. a historical unlinked failure provably outside the current 60-second window does not permanently block current provider detail;
2. a current-window unlinked failure fails closed;
3. malformed/missing historical-boundary evidence fails closed;
4. a current-window source/request mismatch fails closed;
5. historical mismatch outside the current request window does not contaminate current capacity;
6. response-backed and attributable linked failures retain existing Step C behavior;
7. `count_recent_source_requests(...) == len(recent_consumed_provider_attempts(...))` remains exact;
8. no `failed_at`, `retry_after_at`, `retry_after_seconds`, or pacer timing becomes provider-window authority;
9. current canonical governed failure execution produces a linked failure row;
10. live DB read-only rereadiness shows no ambiguity capable of intersecting the current 60-second window;
11. zero DB writes/source requests/Scheduler/runtime/callback/admission activity.

Only after this repair passes may Step D package capacity and exact `recheck_at` resume.

## Money-usefulness contribution

This repair prevents old failure-history artifacts from permanently disabling safe discovery growth while still refusing to admit a new pair when current provider capacity is genuinely ambiguous. That preserves the ability to grow the clean four-token corpus without weakening source-budget protection.

## What this lane still does not unlock

It does not unlock provider package-capacity implementation, `recheck_at`, `MultiCycleAdmissionHealth`, later-cycle discovery, cycle-2 admission/persistence, factory wake integration, source fetching, memory generation, authorization/proof, 12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- Treating an old row as historical without authoritative negative-boundary evidence could hide real current capacity consumption.
- Continuing to scan all history keeps Step D permanently blocked despite a clean current provider window.
- Mutating the 45 rows now expands scope and creates provenance risk without improving the current-window calculation.
- The low-level `record_source_failure(SourceRequest, ...)` surface remains capable of creating an unlinked row; current-window ambiguity must remain fail-closed.
- The live operational DB must be reread read-only after implementation before Step D resumes.

## Closeout

`V2_9_8B_SOURCE_FAILURE_LINEAGE_BOUNDARY_AUDIT_PASS_READY_FOR_SCOPED_CURRENT_WINDOW_REPAIR_DESIGN`

Correct next lane: **design, then TDD-implement, the scoped current-window/evidence-frontier repair.**

Do not backfill the 45 historical failures as part of this prerequisite. Do not resume Step D until the scoped repair passes focused tests and the live DB rereadiness check.
