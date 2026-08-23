# Printer V1 V2-9.8B Post-Lane-4 Schema / Gate Coherence Implementation Inspection

**Document status:** `INSPECTION / CLOSEOUT ONLY`

**Date:** 2026-08-23

**Branch:**
`agent/v2-9-8b-consumed-4-2-2-full-operational-run-forensic-audit`

**Required starting HEAD:**
`610ea565bb73ef43b98019c1aaba68df31c0ddee`
(`Enforce canonical DB target in schema admission`)

**Verdict:**
`V2_9_8B_POST_LANE4_SCHEMA_GATE_COHERENCE_IMPLEMENTATION_INSPECTION_PASS`

This lane is read-only inspection plus documentation. It does not modify
production code or tests, apply a migration, mutate
`data/printer_v1.sqlite3`, construct or reuse an authorization, run a
campaign, call providers, create a 061 evidence package, activate Cycle 3,
or begin V2-10.

This inspection is **not** authorization to apply Migration 060 or 061.

---

## 1. Inspected chain

| Stage | Commit | Verdict / subject |
| --- | --- | --- |
| Post-Lane-4 authoritative readiness audit | `7c32a2330f90ef47cacb2a0f9474f7fe35bc3efd` | `PRINTER_V1_POST_LANE4_AUTHORITATIVE_READINESS_AUDIT_PASS_NEXT_ACTION_IDENTIFIED` |
| Schema / gate coherence design | `4835e7872c2250335b25899b433e33ec2a641d47` | `V2_9_8B_POST_LANE4_SCHEMA_GATE_COHERENCE_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION` |
| Narrow implementation (PR 1) | `dca4f858a76cbde45a7c8e8f39ddd65663dad55a` | Implement V2-9.8B schema gate coherence |
| Canonical-target repair | `610ea565bb73ef43b98019c1aaba68df31c0ddee` | Enforce canonical DB target in schema admission |
| This inspection (PR 2) | repository HEAD containing this document | see verdict above |

Authority read: `AGENTS.md`, active Printer V1 source stack, `CURRENT_HANDOFF.md`
at start (still named the design-stage next action), the post-Lane-4
readiness audit, the accepted design, implementation commit `dca4f85`, and
repair commit `610ea56`.

---

## 2. Intended current identity

Current HEAD intentionally represents:

| Authority | Identity |
| --- | --- |
| Repository catalogue | 61 / `061_standard_4h_progression_fault_preservation.sql` |
| Reviewed admission pin | 61 / `061_standard_4h_progression_fault_preservation.sql` |
| Authoritative DB ledger | 59 / `059_pair_ready_parent_terminal_cancellation_transition.sql` |
| Physical 060/061 objects on the authoritative DB | absent |

Therefore `admission_schema_ready = false` for the authoritative database,
and all fresh admission remains fail-closed. This is the designed blocked
maintenance state, not a campaign GO and not a claim that the database is
migration-ready by assertion.

Live helper evaluation against `data/printer_v1.sqlite3` with
`expected_target=None` returned:

- `admission_schema_ready`: false
- `applied_count` / `applied_head`: 59 /
  `059_pair_ready_parent_terminal_cancellation_transition.sql`
- `migration_060_objects_ready`: false
- `migration_061_objects_ready`: false
- blockers: `migration_count_mismatch`, `migration_head_mismatch`,
  `migration_ledger_missing`, `required_schema_object_missing`,
  `partial_migration_application`
- `campaign_authorized`: false

---

## 3. Expected-schema owner / pin

`src/printer_v1/operator_cli/schema_admission_coherence.py` owns the
reviewed pin as explicit `ast.Constant` literals:

```python
REQUIRED_MIGRATION_COUNT = 61
REQUIRED_MIGRATION_HEAD = (
    "061_standard_4h_progression_fault_preservation.sql"
)
```

They are not derived from `canonical_migration_count()` /
`canonical_migration_names()`. The zero-state gate re-exports those names
in `__all__` only: no local Assign, and no `canonical_migration_*` names in
that file.

Live catalogue comparison equals the pin (61 files, head `061_…sql`). A
fixture catalogue containing an extra well-formed `062_*.sql` yields
`schema_expectation_mismatch` and keeps `admission_schema_ready` false
without patching the production pin. No `migrations/062*` exists.

---

## 4. Canonical-target binding

`expected_target is None` means
`proof_db_schema_readiness.CANONICAL_PERSISTENT_DB`
(`data/printer_v1.sqlite3`). The target check is never skipped.

Production callers all pass `expected_target=None`:

- four-token zero-state gate
- `build_activation_preflight`
- pre-authorization `prepare` / `review` (`evaluate_migration_ledger_drift`)
- WINDOW_15M inherited ledger guard (default
  `assert_migration_ledger_ready`)
- standard-4h inherited ledger guard (same default)

Static production scan found no `expected_target=db_path`,
`expected_target=path`, `expected_target=target`, or
`expected_target=None if db_path is None else target`. Disposable
`expected_target=disposable_path` remains test-only.

A coherent 61 disposable database with production default target is
blocked (`db_target_mismatch`). The same bytes pass the schema
prerequisite only when the test target is the disposable file, and that
result still sets `campaign_authorized=false`.

Four-token one-shot wrappers default `migration_ledger_guard=None` and
rely on the zero-state gate, which itself calls the helper with
`expected_target=None` before marker creation.

---

## 5. Physical object inventory

`proof_db_schema_readiness.py` remains the single inventory owner.
`inspect_required_schema_objects()` never raises because an object is
absent; it returns `{"issues": list[str]}`. Sister-dict reads use
`.get(table, set())`. The 060 table has lawful empty sister keys.

Migration 060 inventory:

- seven frozen-lane columns on
  `printer_pre_admission_discovery_attempt_items`
- trigger `printer_pre_admission_item_frozen_lane_complete`
- `REQUIRED_NOT_NULL_COLUMNS[…] == set()`
- `REQUIRED_UNIQUE_KEYS[…] == set()`

Migration 061 inventory:

- both progression tables
- required columns on both tables
- three indexes, including `idx_standard_4h_progression_successor`
- exact five-column attempt composite unique
  `(progression_attempt_id, campaign_id, campaign_run_id, cycle_id, factory_run_id)`
- all eight immutability triggers

A disposable 059 schema produces inspector issues rather than `KeyError`.
`validate_runtime_schema_connection` still calls the inspector.

---

## 6. False-ready protection

Focused proof injects the underlying absence, not a pre-baked flag. Each
of the following leaves `admission_schema_ready` false:

- missing 060 column (`frozen_tracking_lane`)
- missing 060 trigger
- missing 061 table
- missing 061 successor index
- missing 061 immutability trigger
- missing 061 five-column composite unique

---

## 7. State matrix

| Condition | Result |
| --- | --- |
| catalogue61 / pin61 / DB59 | BLOCKED |
| catalogue61 / pin61 / DB60 | BLOCKED (`partial_application`) |
| ledger61 + missing object | BLOCKED |
| objects61 + wrong/incomplete ledger | BLOCKED |
| catalogue62 / pin61 | BLOCKED (`schema_expectation_mismatch`) |
| coherent61 wrong canonical target | BLOCKED (`db_target_mismatch`) |
| exact coherent61 matching **test** target | schema prerequisite READY, not campaign GO |

The last row is disposable/test-only. It does not grant campaign
permission, authorization, marker creation, or Cycle 3.

---

## 8. Admission chain

The coherence gate executes before authorization consumption, application
marker, child creation, and campaign start on the covered production
paths:

- WINDOW_15M and standard-4h wrappers call
  `assert_migration_ledger_ready(mode="review")` after temporal validity
  and before staging, marker, or child.
- Four-token wrappers run the zero-state gate, which calls the helper,
  before staging/marker.
- `build_activation_preflight` calls the helper immediately after sidecar
  quiescence and before git provenance, composition, campaign identity, or
  child work.
- Pre-authorization `prepare` / `review` call the helper inside
  `evaluate_migration_ledger_drift`.

No catalogue-only admission bypass remains on those paths. Helper
`admission_schema_ready` is a schema prerequisite only.

---

## 9. Authoritative database (read-only)

`data/printer_v1.sqlite3` was opened read-only / immutable. It was not
written.

| Fact | Observed |
| --- | --- |
| sha256 | `17ac6ba70cbfff699b5b32d8930736e561cbe02eff0d56e698da91ed1820db13` |
| size | 117846016 |
| sidecars | none |
| integrity | `ok` |
| foreign-key violations | 0 |
| applied count / head | 59 / `059_pair_ready_parent_terminal_cancellation_transition.sql` |
| ledger 060 / 061 rows | absent |
| frozen-lane columns | absent |
| 061 progression tables | absent |

This mismatch is now the intended blocked maintenance state.

---

## 10. Migration-application authority

PR 1 added no migration-application authority. The helper, zero-state
gate, preflight, ledger guard, and one-shot wrappers do not invoke
authoritative:

- `apply_migrations`
- `initialize_operator_db`
- `apply_all_migrations_to_operator_db`
- heartbeat terminal recovery
- or an equivalent corpus writer

Existing production applier remains
`printer_v1.db.migrate.apply_migrations`. The separately authorized PR 3
application, if later approved, will use the accepted one-shot 059-pattern
evidence driver. This inspection did not build or run it.

---

## 11. Migrations / git evidence

Compared with design parent `4835e7872c2250335b25899b433e33ec2a641d47`:

- `migrations/060_pre_admission_frozen_tracking_lane_provenance.sql` unchanged
- `migrations/061_standard_4h_progression_fault_preservation.sql` unchanged
- no migration 062
- `src/printer_v1/db/migrate.py` unchanged

Four-token current git evidence remains `MIGRATION_059_EVIDENCE` /
`operator-runs/v2-9-8b-migration-059-application` on both four-token
profiles. `MIGRATION_061_PACKAGE_KIND` and `MIGRATION_061_PACKAGE_ROOT`
were not invented.

---

## 12. Consumed authorization

Consumed one-shot
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260821T153458Z_512f2436` remains
permanently non-reusable (`successor_allowed=false`,
`automatic_retry_allowed=false`, `resume_allowed=false`). Schema
coherence does not revive it. No replacement authorization exists. Helper
result dictionaries keep `campaign_authorized=false`,
`application_marker_created=false`, and `cycle_3_unlocked=false`.

---

## 13. Permanent locks

Unchanged by implementation, repair, and this inspection:

- Source Governor
- Central Scheduler
- cadence
- Lane-1 frozen-lane semantics
- Lane-3 progression
- Lane-4 accounting/reporting
- Cycle 3
- 12h / 24h
- retrieval
- financial / paper-trading decision capabilities
- live execution
- scoring / embeddings

`WINDOW_5M_MICRO_EVENT` remains support-only. Slot-ordinal CHECK remains
`(1, 2)`.

---

## 14. Verification

Minimum sufficient read-only verification. No broad suite. No DB writes.

| Check | Result |
| --- | --- |
| `py_compile` of touched production modules | pass |
| live helper import + authoritative evaluate | blocked as designed |
| static production `expected_target` scan | only `expected_target=None` |
| static migration-writer scan on this change | no corpus writer added |
| `git diff --check` | pass |
| tracked tree vs HEAD before this documentation commit | clean |
| focused PR-1 / canonical-target tests | pass |
| nearest pre-lifecycle, GuardBlocker, Review, schema-readiness, 057, ZeroStateGate, Lane-3 061 lock tests | pass |

Focused command: **103 passed, 7 subtests passed**.

The full historical
`tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py`
file still contains leftover assertions that PR 1 did not rewrite
(`CanonicalCatalogueTests` still ends at 052; CLI
`test_prepare_cli_returns_zero_on_pass` still expects a ledger-only
disposable PASS; wrapper `test_honest_live_binding_passes_the_real_guard`
still expects live-59 consumption; incomplete-binding tests still require
the exact string `package_binding_incomplete`). Those leftovers do not
contradict production fail-closed behavior. Several of them now fail
*because* the helper and canonical-target repair work. This inspection
does not edit tests. They are deferred test-file lag, not a production
defect and not campaign permission.

---

## 15. What this inspection does not do

- apply Migration 060 or 061
- create or consume a campaign authorization
- cut git current evidence from 059
- invent a `MIGRATION_061` package
- declare the authoritative DB migration-ready by assertion
- authorize PR 3

---

## 16. Next permitted action

The design requires PR 3 to have **both** this inspection PASS **and** a
separate explicit operator authorization for authoritative migration
application. That second authorization does not exist.

```text
V2-9.8B Post-Lane-4 Schema / Gate Coherence
AUTHORITATIVE MIGRATION 060/061 APPLICATION — AWAITING SEPARATE OPERATOR AUTHORIZATION
```

Do not treat this document as that authorization.
