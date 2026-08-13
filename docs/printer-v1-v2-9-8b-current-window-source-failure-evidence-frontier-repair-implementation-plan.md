# Printer V1 V2-9.8B Current-Window Source-Failure Evidence-Frontier Repair Implementation Plan

> **For agentic workers:** execute this plan with strict TDD and stop after the operational rereadiness gate. Do not continue into provider package capacity or `recheck_at`.

**Goal:** Make provider-attempt ambiguity fail closed only when evidence can intersect the canonical current 60-second provider window, without rewriting historical source-failure rows.

**Architecture:** Keep `recent_consumed_provider_attempts(...)` as the single read-only accounting authority. Linked evidence continues to use only `printer_source_requests.requested_at` as positive attempt time; unlinked failures may use canonical SQLite `created_at` only to prove strict historical exclusion from the current window.

**Tech Stack:** Python, SQLite, pytest.

## Global Constraints

- Baseline: `50d9dcf75f5f12ce575a88032ce27470f7d2348c`.
- Design: `docs/printer-v1-v2-9-8b-current-window-source-failure-evidence-frontier-repair-design.md`.
- `DEFAULT_WINDOW_SECONDS` remains `60`.
- Window law remains inclusive: `requested_at >= cutoff` counts.
- No historical DB backfill, migration, deletion, quarantine, nearest-time inference, `failed_at` timing, retry timing, pacer timing, source call, Scheduler work, callback, admission, runtime, authorization, package-capacity, or `recheck_at` implementation.
- `TOKEN_CAPACITY` remains `2`.

---

### Task 1: RED current-window evidence-frontier contract

**Files:**
- Create: `tests/test_v2_9_8b_current_window_source_failure_evidence_frontier.py`
- Read: `tests/test_v2_9_8b_provider_reaching_attempt_detail.py`
- Read: `src/printer_v1/sources/budget_accounting.py`

**Contract to prove:**

1. Unlinked failure with canonical SQLite `created_at < cutoff` does not block current provider detail.
2. Unlinked failure with `created_at == cutoff` fails with `CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS`.
3. Unlinked failure with `created_at > cutoff` fails closed.
4. Blank, malformed, offset-bearing, or otherwise non-canonical unlinked `created_at` fails closed.
5. Linked current-window source or request-kind mismatch fails closed.
6. Linked historical mismatch with canonical request `requested_at < cutoff` does not contaminate the current window.
7. Existing linked response-backed and attributable-failure attempts remain unchanged.
8. `count_recent_source_requests(...) == len(recent_consumed_provider_attempts(...))` remains exact.
9. Projection performs zero DML/source/Scheduler/runtime activity.

Use a fixed timezone-aware `now`. For canonical negative evidence, set `printer_source_failures.created_at` explicitly to `YYYY-MM-DD HH:MM:SS` in fixtures; do not derive authority from `failed_at`.

Run only the new focused test file and verify at least the historical-unlinked case fails under the current global ambiguity guard.

Commit RED separately.

---

### Task 2: Minimum GREEN in `budget_accounting.py`

**Files:**
- Modify: `src/printer_v1/sources/budget_accounting.py`
- Test: `tests/test_v2_9_8b_current_window_source_failure_evidence_frontier.py`

**Required implementation:**

1. Extend `_require_current_attempt_schema(...)` so `printer_source_failures.created_at` is required.
2. Add a private parser, named `_canonical_sqlite_created_at_utc(raw, *, failure_id) -> datetime`, that:
   - accepts only exact `YYYY-MM-DD HH:MM:SS`;
   - interprets it as UTC;
   - rejects blank, malformed, fractional, `T`-separated, `Z`, or offset-bearing values with `CONSUMED_ATTEMPT_LINKAGE_AMBIGUOUS`.
3. Replace global-history `_require_unambiguous_attempt_linkage(...)` with a cutoff-aware evidence-frontier validation used by `_select_consumed_provider_attempts(...)`.
4. For an unlinked provider failure:
   - parse only `created_at` for negative exclusion;
   - `created_at < cutoff` => historical-only, ignore for current capacity;
   - `created_at >= cutoff` or unparsable => fail closed;
   - never emit `created_at` as `ConsumedProviderAttempt.requested_at`.
5. For linked response/failure evidence:
   - resolve linked request first;
   - parse linked `requested_at` with existing `_canonical_utc_timestamp(...)`;
   - if `requested_at < cutoff`, historical structural/source/request mismatch does not block current capacity;
   - if `requested_at >= cutoff`, source/request mismatch or malformed evidence fails closed.
6. Orphan/non-resolvable non-null linkage has no canonical request timestamp. It may be excluded only if the failure's canonical `created_at < cutoff`; otherwise fail closed. Responses have no fallback and remain fail closed if linkage cannot resolve.
7. Preserve the existing attributable-failure exclusion set and deterministic `(requested_at, source_request_id)` ordering.
8. Preserve `count_recent_source_requests(...)` as `len(recent_consumed_provider_attempts(...))`.

Do not add another accounting API or migration.

Run:
- new evidence-frontier tests;
- `tests/test_v2_9_8b_provider_reaching_attempt_detail.py`;
- existing focused E2C-B source-budget-accounting tests affected by the refactor;
- one focused governed-execution test proving a new canonical governed failure has non-null `source_request_id`;
- `python -m py_compile src/printer_v1/sources/budget_accounting.py`;
- `git diff --check`.

Commit GREEN separately.

---

### Task 3: Mandatory operational DB rereadiness gate

**No production changes. No DB mutation.**

Open `data/printer_v1.sqlite3` using SQLite URI `mode=ro` and `PRAGMA query_only=ON`.

Record SHA-256 before and after.

Read and report:
- migration `037` `applied_at` from `printer_schema_migrations` as provenance context only;
- all manifest-provider unlinked failures;
- their source, request kind, `created_at`, and new frontier classification;
- any current-window or unclassifiable ambiguity.

Then invoke `recent_consumed_provider_attempts(...)` against every provider required by the current source-free manifest.

PASS requires:
- all 45 known historical unlinked rows may remain untouched;
- no unlinked/mismatched evidence capable of intersecting the inspection-time 60-second window remains ambiguous;
- detail projection succeeds for every manifest provider;
- DB SHA-256 unchanged.

If any current-window/unclassifiable ambiguity remains, stop with `BLOCKED`. Do not mutate data and do not resume Step D.

If PASS, push RED/GREEN commits and stop. The next lane is Step D provider package capacity + exact `recheck_at`.

## Closeout report

Report:
- starting HEAD;
- RED SHA and exact failing assertion;
- GREEN SHA;
- files changed;
- exact positive timestamp authority;
- exact negative historical-exclusion authority;
- focused test results;
- live DB migration-037 `applied_at`;
- row classification counts;
- per-manifest-provider rereadiness result;
- pre/post DB SHA-256;
- zero-write/source/Scheduler/runtime confirmation;
- Functionality Risks / Setbacks / Efficiency Blockers;
- final HEAD;
- verdict: `PASS_READY_TO_RESUME_STEP_D` or `BLOCKED`.
