# Printer V1 V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M `token_slot_id` Blocker Repair Design

Date: 2026-08-03

Linear: `DTW-19`

Lane:
`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Design`

Lane type: design/specification only.

Starting branch:
`agent/v2-9-8b-post-rollover-2-token-slot-id-blocker-repair-design`

Starting HEAD:
`6c9b572c5df0f61b51d8e3c101c32dcefa364701`

Parent audit:
`docs/printer-v1-v2-9-8b-post-rollover-2-token-slot-id-blocker-audit.md`

Parent audit verdict:
`V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_ROOT_CAUSE_CONFIRMED`

Consumed authorization:
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

The consumed authorization is permanently non-reusable. This design does not
authorize implementation, proof execution, provider contact, authoritative DB
mutation, wrapper use, operational execution, memory generation, or a fresh
authorization.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_REPAIR_DESIGN_PASS`

The approved repair is one identity-preserving projection change:

```sql
SELECT s.token_slot_id, s.slot_ordinal, s.token_row_id, s.pair_row_id,
       s.mint_identity, s.pair_identity, s.token_state,
       p.pair_address, t.token_status
```

in:

`src/printer_v1/operator_cli/origin_lifecycle_campaign.py`

function:

`_read_activated_slots()`

The repair must carry the already-persisted `s.token_slot_id` unchanged into
the existing `sqlite3.Row -> dict -> record["slots"] -> accounting observer`
path. The consumer remains strict:

```python
subject_identity=str(slot["token_slot_id"])
```

and the validation remains:

```text
SELECTION_HANDOFF_VALIDATED
```

against the exact durable campaign token-slot primary key.

No schema, ID construction, fallback, optional lookup, consumer weakening,
selection change, Scheduler change, Source Governor change, accounting-law
change, wrapper change, authorization change, or lifecycle refactor is approved.

## 2. Source-stack and evidence alignment

This design follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The governing pattern remains:

```text
audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout
```

The parent audit completed the audit step and proved:

- the durable producer creates and persists `token_slot_id`;
- the selected-item handoff link preserves the same identity;
- `_read_activated_slots()` omits the column;
- the subsequent dict copy does not remove any present field;
- the accounting consumer correctly requires the durable ID;
- the first public ordinary WINDOW_15M attempt failed before lifecycle factory
  execution because the projection contract was stale;
- the failed attempt created terminal pre-lifecycle history but no factory run,
  memory window, snapshot, fingerprint, retrieval, paper decision, position,
  trade, audit, or PnL delta;
- cleanup reached zero active residue.

This design does not reopen any settled audit finding.

## 3. Problem contract

### 3.1 Durable producer contract

`CombinedPumpfunCampaignExecutor._handoff_one_slot()` creates:

```text
slot-{cycle_id}-{ordinal}
```

and persists it as:

- `printer_memory_factory_campaign_token_slots.token_slot_id`;
- `printer_discovery_selected_item_links.token_slot_id`.

The ID is therefore a durable owned identity, not a value that a consumer may
derive independently.

### 3.2 Incomplete intermediate contract

Current `_read_activated_slots()` returns:

```text
slot_ordinal
token_row_id
pair_row_id
mint_identity
pair_identity
token_state
pair_address
token_status
```

It does not return `token_slot_id`.

The driver copies those rows directly into:

```python
"slots": [dict(row) for row in slots]
```

The missing field is not introduced or removed anywhere else in this path.

### 3.3 Correct consumer contract

The public coordinator creates one `LocalValidationIdentity` per selected slot:

```python
LocalValidationIdentity(
    stage_id=stage_id,
    subject_identity=str(slot["token_slot_id"]),
    validation_kind="SELECTION_HANDOFF_VALIDATED",
    validation_ordinal=index,
)
```

The exact durable token-slot primary key is the correct validation subject.
Mint, pair, token row, ordinal, lifecycle label, or selected-item ID is not an
equivalent substitute.

## 4. Alternatives considered

### 4.1 Approved: extend the existing projection

Add `s.token_slot_id` to `_read_activated_slots()`.

Advantages:

- repairs the exact loss boundary;
- carries existing durable truth rather than inventing identity;
- requires no schema or ownership change;
- keeps the consumer fail-closed;
- affects both current reader call sites consistently;
- minimizes implementation and regression risk.

This is the selected design.

### 4.2 Rejected: reconstruct from cycle and ordinal

Example rejected form:

```python
f"slot-{cycle_id}-{slot['slot_ordinal']}"
```

Reason: a consumer-generated lookalike is not proof of the persisted primary
key. It could conceal corruption, format changes, mismatched ownership, or an
incorrect row.

### 4.3 Rejected: use another identity

Rejected substitutes include:

- `mint_identity`;
- `pair_identity`;
- `token_row_id`;
- `pair_row_id`;
- `token_identity`;
- `lifecycle_identity`;
- `selection_item_id`;
- `merged_candidate_id`;
- `tracking_queue_id`.

Reason: none represents the exact campaign token-slot subject validated at the
selection handoff boundary.

### 4.4 Rejected: weaken the consumer

Rejected forms include:

```python
slot.get("token_slot_id")
```

```python
if slot.get("token_slot_id"):
    ...
```

and silent skipping or empty-string coercion.

Reason: they would allow incomplete stage evidence to seal or make accounting
appear complete without validating both selected handoffs.

### 4.5 Rejected: schema change or typed-slot refactor

The schema already stores the required identity. A new column, table, migration,
DTO hierarchy, or broad slot-reader refactor adds risk without repairing a
missing SQL column more safely.

A later separately approved cleanup may introduce a typed activated-slot
contract, but it is not part of this blocker repair.

## 5. Approved implementation boundary

### 5.1 Production source file

Only this production file may change:

`src/printer_v1/operator_cli/origin_lifecycle_campaign.py`

Approved source edit:

- add `s.token_slot_id` to the select list in `_read_activated_slots()`;
- return it through the existing `dict(row)` conversion;
- preserve existing filtering, joins, ordering, transaction behavior, and all
  other selected fields.

Preferred column order:

```text
token_slot_id
slot_ordinal
token_row_id
pair_row_id
mint_identity
pair_identity
token_state
pair_address
token_status
```

The order is for stable human inspection only. Consumers must use named keys.

No other production source file is approved unless implementation discovers a
contradiction with this design. Any contradiction must stop the lane and return
to design review rather than widening scope.

### 5.2 Focused test file

Add one focused module:

`tests/test_v2_9_8b_token_slot_id_projection_repair.py`

This module owns the new blocker-specific proofs. It may reuse existing
disposable fixtures and frozen transports, but it must not mutate historical
tests merely to make them pass.

A minimal import-only adjustment to an existing test helper is not approved by
default. Prefer importing existing helpers as they are. If a helper must be
made reusable, stop and justify the extra test-file change before proceeding.

### 5.3 Documentation

The implementation lane may create its required implementation/proof report
only after the approved tests pass. The design lane itself changes no code or
tests.

## 6. Implementation sequence

1. Confirm exact implementation branch and parent design commit.
2. Confirm the consumed authorization remains untouched and no runtime is
   authorized.
3. Add one SQL projection column in `_read_activated_slots()`.
4. Add the focused blocker-repair test module.
5. Run syntax compilation only for the changed production file and new test
   module.
6. Run the five blocker-specific proof groups below.
7. Run the minimum affected regression set.
8. Record exact commands, results, file hashes, disposable DB identities, and
   zero-contact/zero-protected-delta evidence.
9. Commit only the approved source, focused test module, and implementation
   report.
10. Stop for an independent implementation/proof closeout. Do not create a new
    authorization.

## 7. Focused proof matrix

All tests use disposable databases migrated through canonical Migration 050,
frozen or injected evidence, no real provider/RPC/WebSocket contact, no wrapper,
no authorization, and no authoritative database.

### P1. Activated-slot projection regression

Purpose:

Prove the reader returns the exact durable slot IDs that already exist in the
token-slot table.

Fixture:

- disposable Migration-050 DB;
- one campaign/run/cycle;
- two valid durable SELECTED token slots;
- matching token, pair, tracking, and selected-item-link rows.

Assertions:

- exactly two rows ordered by `slot_ordinal` 1 then 2;
- each row contains a nonempty `token_slot_id`;
- returned values exactly equal the two persisted token-slot primary keys;
- returned values exactly equal selected-item-link `token_slot_id` values;
- IDs are distinct;
- token row, pair row, mint, pair, state, pair address, and token status are
  unchanged;
- no derived or reconstructed identity is used.

DB/Scheduler assertions:

- test read does not create or modify rows;
- database bytes or canonical content digest remain unchanged across the read;
- no Scheduler job is enqueued, claimed, completed, cancelled, or locked;
- integrity check is `ok`;
- foreign-key check is empty;
- no sidecar remains after close.

### P2. Real executor-to-driver callback integration

Purpose:

Close the exact composition gap that existing origin-to-lifecycle tests missed.

Fixture:

- real `CombinedPumpfunCampaignExecutor`;
- real `OriginToLifecycleCampaignDriver`;
- frozen Pump origin and PumpSwap evidence;
- real atomic two-slot handoff on a disposable Migration-050 DB;
- injected `full_run_stage_observer`;
- lifecycle runner replaced with a bounded fixture seam only after the callback
  has been observed, so no wall-clock lifecycle is required for this test.

Assertions:

- the executor persists two exact durable slot IDs;
- the driver callback boundary is
  `DISCOVERY_SELECTION_TERMINAL`;
- `record["slots"]` contains exactly two dictionaries;
- both dictionaries include `token_slot_id`;
- callback IDs equal the token-slot table IDs;
- callback IDs equal selected-item-link IDs;
- callback mint/pair identities remain exact and distinct;
- no legacy discovery or reselection occurs;
- the callback is invoked once for the terminal discovery-selection stage.

DB/Scheduler assertions:

- atomic two-or-none activation remains intact;
- first-15m handoff Scheduler identities remain linked to the same slots;
- no active or locked Scheduler residue remains after fixture cleanup;
- protected capabilities have zero deltas.

### P3. Public accounting-boundary integration

Purpose:

Exercise the real public coordinator observer that previously raised the
`KeyError`.

Fixture:

- disposable Migration-050 DB;
- real public coordinator/owner/driver composition;
- frozen transports and injected dependencies;
- no PowerShell wrapper and no external authorization;
- capture the action-local ledger and sealed discovery-selection stage.

Assertions:

- no `KeyError` occurs;
- exactly two `LocalValidationIdentity` objects are observed;
- both use `validation_kind="SELECTION_HANDOFF_VALIDATED"`;
- their subject identities exactly equal the two durable slot IDs;
- validation ordinals are deterministic 1 and 2;
- the discovery-selection stage seals exactly once;
- owner and action-local identity sets agree for these validations;
- the stage cannot report completion with zero or one slot validation.

DB/Scheduler assertions:

- campaign/run/cycle/factory identities remain exact;
- no duplicate Scheduler-work projection appears;
- no active/locked residue remains;
- integrity and foreign-key checks pass;
- protected-capability deltas remain zero.

### P4. Malformed-slot negative fail-closed proof

Purpose:

Prove strictness is preserved and missing durable identity can never be treated
as successful accounting.

Fixture:

- invoke the real public stage observer through the approved test seam;
- provide an otherwise valid two-slot stage record with one slot's
  `token_slot_id` deliberately removed.

Assertions:

- the boundary fails before lifecycle work or successful stage sealing;
- no `SELECTION_HANDOFF_VALIDATED` identity is recorded for the malformed slot;
- the stage is not accepted as complete;
- failure is explicit and deterministic;
- no `.get()`, fallback, substitute identity, empty identity, or silent skip is
  accepted;
- terminal cleanup remains bounded and idempotent where campaign state was
  initialized.

DB/Scheduler assertions:

- no memory window, snapshot, fingerprint, retrieval, decision, position, trade,
  audit, or PnL row is created;
- zero active/locked Scheduler residue;
- integrity and foreign-key checks pass.

### P5. Bounded offline ordinary WINDOW_15M public-path proof

Purpose:

Prove the repaired ordinary public composition progresses beyond the failed
handoff boundary and completes a bounded two-token WINDOW_15M lifecycle offline.

Fixture:

- exact public coordinator -> authoritative owner -> real origin driver -> real
  one-command factory wiring;
- disposable Migration-050 DB;
- frozen Pump/PumpSwap and snapshot/context transports;
- compressed test timing only;
- capacity exactly two;
- `WINDOW_15M` only;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- all longer windows locked;
- no wrapper and no authorization.

Assertions:

- two distinct durable slot IDs reach the public observer;
- two handoff validations use those exact IDs;
- lifecycle factory starts;
- exactly two terminal WINDOW_15M lifecycle outcomes are produced;
- campaign-window and memory-window ownership binds to the correct slot/token/
  pair identities;
- owner/action-local reconciliation is non-vacuous and exact;
- terminal reporting and deterministic zero-side-effect replay complete;
- clean, partial, dirty, or blocked memory quality remains evidence-driven and
  is not forced to CLEAN;
- runtime terminal status, campaign acceptance, and memory quality remain
  separate axes;
- no automatic retry, restart, resume, or successor is created.

DB/Scheduler assertions:

- zero active campaigns, runs, supervision, discovery work, factory steps,
  Scheduler jobs, and locks after closeout;
- integrity check `ok`;
- foreign-key check empty;
- replay adds zero source calls, Scheduler actions, or writes;
- retrieval and every financial/protected surface have zero delta;
- no 1h, 4h, 12h, or 24h row or work is created.

## 8. Minimum affected regression set

Run blocker-specific tests first:

```bash
.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_token_slot_id_projection_repair.py
```

Then run only the directly affected composition and safety suites:

```bash
.venv/bin/python -m pytest -q \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py \
  tests/test_v2_9_8b_operational_factory_active_path_restoration.py \
  tests/test_v2_9_8b_post_handoff_terminal_compensation.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_8a_public_operational_command.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py
```

Run syntax compilation:

```bash
.venv/bin/python -m py_compile \
  src/printer_v1/operator_cli/origin_lifecycle_campaign.py \
  tests/test_v2_9_8b_token_slot_id_projection_repair.py
```

Run:

```bash
git diff --check
```

Do not run the full repository suite unless the focused matrix exposes a broad
shared-owner regression or the independent closeout classifies the one-line
change as broader than designed. Unrelated pre-existing failures must be
recorded, not absorbed into this repair lane.

## 9. Evidence required from implementation/proof

The implementation report must record:

- starting and ending commit identities;
- exact changed-file list;
- source and test SHA-256 identities;
- exact source diff showing the projection-only change;
- exact test commands and complete pass/fail totals;
- canonical migration count and Migration-050 head;
- disposable DB path identities without committing DB files;
- DB before/after hashes or canonical content digests for read-only tests;
- callback slot records with secrets absent;
- durable token-slot and selected-item-link ID equality;
- two exact `SELECTION_HANDOFF_VALIDATED` identities;
- Scheduler job/state/lock totals;
- active-residue totals;
- integrity and foreign-key results;
- source/provider contact count of zero;
- authoritative DB access/mutation count of zero;
- wrapper invocation count of zero;
- authorization creation/application count of zero;
- protected-capability deltas of zero;
- no longer-window work;
- no retry, rerun, resume, restart, or successor.

No secret value, API key, RPC URL, raw environment value, or sensitive artifact
may enter the report or Git.

## 10. Independent closeout acceptance criteria

A separate read-only closeout must verify all of the following before any fresh
readiness review:

1. The source diff adds only `s.token_slot_id` to the existing projection.
2. No consumer, schema, ownership, Scheduler, Source Governor, wrapper,
   authorization, or lifecycle semantics changed.
3. The new test module covers P1-P5 with real composition at the specified
   boundaries.
4. The malformed-slot proof remains fail-closed.
5. The focused regression set passes or any unrelated pre-existing failure is
   documented with evidence and no scope expansion.
6. No provider or authoritative DB was touched.
7. No runtime authorization or one-shot application was created.
8. All protected capabilities remain locked and zero-delta.
9. The consumed authorization is referenced only as historical evidence and is
   never copied, modified, or reused.
10. Git contains only approved source, test, and implementation/closeout
    documentation changes.

Closeout PASS may authorize only a new read-only exact-HEAD readiness review. It
must not directly authorize a live run.

## 11. Rollback and stop conditions

Stop implementation immediately if:

- `token_slot_id` is not present on the durable token-slot row;
- selected-item-link and token-slot IDs disagree;
- the repair requires identity derivation or fallback;
- a schema or ownership change appears necessary;
- the public observer cannot be exercised offline;
- tests require provider contact or the authoritative DB;
- the source diff expands beyond the approved projection;
- Scheduler or Source Governor ownership would change;
- protected-capability deltas are nonzero;
- active or locked residue remains;
- a test tries to reuse the consumed authorization;
- a longer window is activated;
- a failure would require broad refactoring.

Rollback is deletion of the uncommitted projection/test changes on the
implementation branch. The failed live action and its historical rows must
never be rolled back, edited, reused, or erased.

## 12. Money-usefulness contribution

This design creates no memory, decision, position, trade, or PnL.

Its contribution is reliability and budget protection:

- prevents another one-shot authorization and governed source budget from being
  consumed by a deterministic shape mismatch;
- preserves exact per-token campaign-slot attribution required for trustworthy
  memory ownership and later quality comparison;
- blocks false accounting success from skipped or substituted validations;
- restores the path toward bounded 15-minute memory growth without weakening
  evidence quality or financial locks.

This is enabling usefulness, not a profit claim.

## 13. What the repair improves

After implementation and proof, the ordinary public WINDOW_15M composition can
carry the exact durable selected-slot identities into discovery-selection
accounting.

The repair improves:

- producer-to-consumer shape completeness;
- exact handoff attribution;
- action-local accounting truth;
- offline composition coverage;
- operator confidence that a later authorization will not fail at this known
  deterministic boundary.

## 14. What remains locked

This design does not unlock:

- wrapper or operational-command execution;
- provider, RPC, WebSocket, or source contact;
- authoritative DB mutation;
- discovery or campaign runtime;
- new authorization;
- memory generation on the authoritative corpus;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- trade audits;
- PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- live wallet, private keys, real funds, signing, or live execution;
- paid APIs;
- scoring, ranking, confidence, or weighted logic;
- embeddings or vectors;
- Source Governor or Central Scheduler bypass.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot unlock any main outcome
or financial capability.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- A one-line source repair can still be under-proven if tests exercise only
  manually seeded identity-rich fixtures.
- A test that calls the driver without the real public observer would repeat the
  original coverage gap.
- A consumer fallback would conceal future contract regressions.
- A broader slot-reader refactor could alter compensation, batch materialization,
  or lifecycle behavior unrelated to this blocker.
- Fixed outward command counters may not describe pre-lifecycle persistence;
  future closeouts must reconcile DB rows and hashes rather than trust one
  envelope field.

### Setbacks

- The prior authorization was consumed without a factory run or memory.
- Six governed source calls and terminal pre-lifecycle persistence were spent.
- Two valid selected slots were terminalized to `MANUAL_REVIEW`.
- The next live attempt cannot be considered until design, implementation,
  bounded proof, independent closeout, readiness, and fresh authorization each
  pass separately.

### Efficiency blockers

- Existing origin tests do not install the public stage observer.
- Existing accounting tests manually seed slot IDs, bypassing the real reader.
- Existing active-path proof calls the owner directly, not the exact public
  observer composition that failed.
- Multiple `_read_activated_slots()` call sites share one stale projection;
  fixing the single reader is efficient, but the callback contract must now be
  locked by a real-composition regression test.
- Broad regression execution would waste time unless the focused matrix finds a
  shared-owner issue.

## 16. Exact next lane

After this design PASS, the exact next lane is:

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Implementation`

That lane may implement only the approved source boundary, focused tests, and
bounded offline proof.

It may not run the wrapper or operational command, contact providers, mutate
the authoritative DB, create or apply an authorization, generate authoritative
memory, activate retrieval or decisions, unlock financial capabilities, or
start any longer window.

Final status:

`DESIGN_COMPLETE_IMPLEMENTATION_SEPARATELY_REQUIRED_RUNTIME_LOCKED`
