# Printer V1 V2-9.8B Post-Rollover-2 `token_slot_id` Repair Independent Closeout

Date: 2026-08-03

Linear: `DTW-22`

Lane:
`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Independent Closeout`

Closeout branch:
`agent/v2-9-8b-post-rollover-2-token-slot-id-blocker-repair-independent-closeout`

Reviewed implementation branch:
`agent/v2-9-8b-post-rollover-2-token-slot-id-blocker-repair-implementation`

Reviewed implementation HEAD:
`089eb38651874d9b3ec4a4ce04600d45ea401b05`

Design baseline:
`dc7e7a855108fce2c60d8b84b347dd7f6c7de022`

Consumed authorization:
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

The consumed authorization remains permanently non-reusable.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_WINDOW_15M_TOKEN_SLOT_ID_BLOCKER_REPAIR_INDEPENDENT_CLOSEOUT_BLOCKED_PROOF_EVIDENCE_GAP`

The production repair is design-conformant and no source-code defect was found in the repaired projection. The remote diff adds the already-durable `s.token_slot_id` to `_read_activated_slots()` and leaves the strict accounting consumer unchanged.

The independent closeout is nevertheless BLOCKED because the implementation proof package does not fully satisfy the approved evidence and exact-composition requirements:

1. The bounded P5 proof in the new focused module runs the real origin driver and real one-command WINDOW_15M factory, but it does not execute the exact public coordinator -> authoritative owner -> real origin driver -> real one-command factory chain in one composition. The public accounting observer is exercised separately through a probe owner in P3. Those seams strongly support the repair but do not equal the exact integrated P5 composition frozen by the design.
2. The implementation report records pass totals and summary safety statements, but it does not preserve the design-required proof details: disposable DB identities, before/after DB hashes or canonical digests, exact callback slot-ID records, exact two `SELECTION_HANDOFF_VALIDATED` identities, Scheduler job/state/lock totals, active-residue totals, and explicit integrity/foreign-key outputs.
3. No durable raw test transcript or proof artifact containing those values is committed or linked. This closeout was read-only and could not reconstruct ephemeral test-database evidence after the fact.

This verdict does not reject or revert the one-column production repair. It blocks progression to fresh readiness or authorization until the existing approved proof contract is completed.

## 2. Independent review method

The closeout performed remote, read-only inspection of:

- the approved repair design;
- the implementation report;
- the exact design-baseline-to-implementation-HEAD comparison;
- the repaired `_read_activated_slots()` source;
- the complete new focused proof module;
- directly affected existing wiring and operational active-path tests;
- the final documentation-only typo-correction commit.

No local runtime, provider, RPC, WebSocket, PowerShell wrapper, operational command, authoritative database, authorization, memory factory campaign, retrieval, decision, position, trade, audit, PnL, or longer-window operation was executed by this closeout.

## 3. Git lineage and scope

Remote comparison from design baseline `dc7e7a855108fce2c60d8b84b347dd7f6c7de022` to reviewed HEAD `089eb38651874d9b3ec4a4ce04600d45ea401b05` reports:

- status: `ahead`;
- ahead by: `2` commits;
- behind by: `0`;
- merge base: exact design baseline;
- exactly three changed implementation files.

Changed implementation files:

1. `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
2. `tests/test_v2_9_8b_token_slot_id_projection_repair.py`
3. `docs/printer-v1-v2-9-8b-post-rollover-2-token-slot-id-blocker-repair-implementation.md`

The final reviewed commit `089eb38651874d9b3ec4a4ce04600d45ea401b05` changes only the implementation report spelling from `Indepent` to `Independent` in the next-lane name.

No schema, migration, provider contract, Source Governor owner, Central Scheduler owner, wrapper, authorization law, runtime command, memory rule, retrieval rule, decision rule, or financial capability appears in the remote implementation diff.

## 4. Source design conformance

### Approved source boundary

The design approved one projection-only change in:

`src/printer_v1/operator_cli/origin_lifecycle_campaign.py`

function:

`_read_activated_slots()`

The reviewed source now contains:

```sql
SELECT s.token_slot_id, s.slot_ordinal, s.token_row_id, s.pair_row_id,
       s.mint_identity, s.pair_identity, s.token_state,
       p.pair_address, t.token_status
```

and still returns:

```python
return [dict(row) for row in rows]
```

The repair therefore carries the already-persisted durable slot primary key through the existing SQLite-row-to-dictionary path.

### Prohibited alternatives absent

Static review found no:

- reconstructed slot ID;
- cycle/ordinal-derived fallback;
- mint/pair/token-row substitute identity;
- `.get("token_slot_id")` optional handling;
- silent skip;
- empty identity acceptance;
- consumer weakening;
- schema or migration change;
- ownership or lifecycle refactor.

Source design conformance: `PASS`.

## 5. Focused proof review

The new module contains five focused tests corresponding to P1-P5.

### P1 - activated-slot projection

Test:
`test_reader_projects_exact_durable_token_slot_ids`

Verified coverage:

- uses real atomic slot persistence;
- reads exact token-slot-table IDs;
- reads selected-item-link IDs;
- asserts exact equality and distinctness;
- asserts deterministic slot order 1,2;
- compares DB bytes before and after the read.

Result: `PASS_BY_RECORDED_EXECUTION_AND_STATIC_TEST_REVIEW`.

### P2 - executor-to-driver callback

Test:
`test_real_driver_callback_carries_exact_slot_ids`

Verified coverage:

- real executor/driver fixture path;
- one `DISCOVERY_SELECTION_TERMINAL` callback record;
- callback slot IDs equal durable token-slot and selected-item-link IDs;
- two distinct activation slots.

Result: `PASS_BY_RECORDED_EXECUTION_AND_STATIC_TEST_REVIEW`.

### P3 - public accounting observer

Test:
`test_public_accounting_observer_uses_two_exact_slot_validations`

Verified coverage:

- invokes the real public coordinator observer;
- captures `CampaignActionLocalLedger.observe_local_validation`;
- asserts two `SELECTION_HANDOFF_VALIDATED` identities;
- asserts exact subject identity order and ordinals 1,2.

Limitation:

- a probe owner invokes the observer with a record captured from a separate real-driver run; the full public coordinator/authoritative-owner/driver/factory composition is not executed in one call.

Result: `PASS_FOR_OBSERVER_BOUNDARY_WITH_COMPOSITION_LIMITATION`.

### P4 - malformed-slot fail closed

Test:
`test_public_observer_missing_slot_id_fails_before_stage_validation`

Verified coverage:

- removes one `token_slot_id`;
- expects `KeyError` from the strict direct lookup;
- asserts terminalization is invoked;
- asserts no local validation was accepted before failure.

Result: `PASS_BY_RECORDED_EXECUTION_AND_STATIC_TEST_REVIEW`.

### P5 - bounded offline ordinary WINDOW_15M path

Test:
`test_bounded_offline_two_token_window_15m_path_closes_cleanly`

Verified coverage:

- real origin driver;
- real one-command factory lifecycle;
- two distinct callback slot IDs;
- exactly two terminal `WINDOW_CLOSE` steps;
- no continuation or longer-window close;
- zero pending/running steps and jobs;
- zero forbidden deltas;
- deterministic zero-source, zero-evidence-write report-only replay;
- unchanged DB bytes across replay.

Blocking limitation:

- the test starts from the driver helper rather than the exact public coordinator -> authoritative owner -> real origin driver -> real one-command factory chain required by the approved P5 fixture.
- Existing affected suites prove factory/finalization and restored operational-driver paths, but they do not close that exact one-call public composition with the repaired real slot record.

Result: `BLOCKED_EXACT_PUBLIC_COMPOSITION_NOT_PROVEN`.

## 6. Recorded verification evidence

The implementation report records:

- compile exit `0`;
- focused proof exit `0`;
- affected regression exit `0`;
- diff-check exit `0`;
- migration-head check exit `0`;
- focused result: `5 passed in 8.62s`;
- affected result: `122 passed, 2 skipped, 6 subtests passed in 79.55s`;
- migration count `50`;
- migration head `050_campaign_scheduler_ownership_scope.sql`.

The test code statically supports the claimed test purposes, and no contradiction was found in the remote source or test files.

However, the closeout cannot independently certify the complete proof contract from the implementation report alone because the design-required concrete DB, Scheduler, identity, integrity, and residue outputs were not preserved.

Recorded test-result review: `PASS_RECORDED_NOT_FULLY_EVIDENCED`.

## 7. Acceptance-criteria matrix

| # | Closeout criterion | Result | Basis |
|---|---|---|---|
| 1 | Source diff adds only durable `s.token_slot_id` to projection | PASS | Exact remote source and compare inspection |
| 2 | No consumer/schema/ownership/Scheduler/Governor/wrapper/authorization/lifecycle semantic change | PASS | Three-file remote diff and source inspection |
| 3 | New module covers P1-P5 at specified real-composition boundaries | BLOCKED | P5 does not run the exact one-call public coordinator/owner/driver/factory composition |
| 4 | Malformed slot remains fail closed | PASS | Direct `KeyError`, no validation accepted |
| 5 | Focused regression set passes or unrelated failures documented | PARTIAL | Pass totals recorded; required detailed proof transcript absent |
| 6 | No provider or authoritative DB touched | PARTIAL | Test design/report state zero contact; no durable detailed transcript |
| 7 | No runtime authorization or one-shot application created | PASS | Remote diff contains none; consumed ID only referenced historically |
| 8 | Protected capabilities remain locked and zero-delta | PASS_STATIC / PARTIAL_PROOF | No capability changes; tests assert zero deltas, but concrete outputs not preserved |
| 9 | Consumed authorization never copied, modified, or reused | PASS | No authorization file or runtime change in diff |
| 10 | Git contains only approved source, test, implementation and closeout documentation | PASS | Implementation diff is exact three-file scope; this lane adds one closeout report |

Because criterion 3 is BLOCKED and criteria 5/6 lack the complete evidence package required by design, closeout PASS is not permitted.

## 8. Money-usefulness contribution

This closeout protects operator time, source budget, and future single-use authorization capacity by refusing to treat a likely-correct one-line repair as fully proven before its exact operational composition and evidence package are closed.

It preserves the useful part of the work:

- the deterministic `token_slot_id` projection defect is repaired;
- strict identity validation remains intact;
- focused tests cover the reader, driver callback, public observer, fail-closed behavior, and offline 15-minute lifecycle seams.

It creates no memory, decision, position, trade, PnL, or profit claim.

## 9. What this closeout improves

- Separates source correctness from proof completeness.
- Prevents a fresh authorization from relying on an under-documented proof package.
- Identifies the minimum remaining composition proof instead of reopening the repair broadly.
- Preserves risk-based verification: no full repository suite is required unless the missing exact composition exposes a wider defect.

## 10. What remains locked

The following remain locked:

- fresh readiness PASS;
- final authorization;
- PowerShell wrapper execution;
- operational command execution;
- source/provider/RPC/WebSocket contact;
- authoritative DB mutation;
- authoritative memory generation;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY, SELL, HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet, private key, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

### Functionality risks

- Separate seam tests can pass while a real one-call composition fails due to wiring, ownership, or callback installation differences.
- Summary-only test reporting can conceal missing Scheduler residue, identity drift, or DB integrity evidence.
- Treating the implementation PASS as equivalent to independent closeout PASS would repeat the exact class of coverage error that consumed the prior authorization.

### Setbacks

- The production repair cannot advance directly to readiness despite appearing correct.
- The prior authorization remains consumed and no memory was produced from that attempt.
- A small additional offline proof/evidence-completion step is required.

### Efficiency blockers

- No durable raw proof transcript or structured artifact was preserved.
- Ephemeral disposable-DB paths and values cannot be reconstructed from Git history.
- The closeout environment has read-only GitHub access and cannot execute the repository test suite.

## 12. Minimum completion required

The next lane must remain bounded to proof/evidence completion on exact reviewed HEAD `089eb38651874d9b3ec4a4ce04600d45ea401b05` or a descendant containing only the missing proof/report work.

Minimum required work:

1. Add or adapt one focused offline test that executes the exact public coordinator -> authoritative owner -> real origin driver -> real one-command WINDOW_15M factory composition with frozen transports and a disposable Migration-050 DB.
2. Prove two exact durable slot IDs reach two `SELECTION_HANDOFF_VALIDATED` identities and the factory produces two terminal WINDOW_15M closes.
3. Preserve a structured proof artifact or complete report containing:
   - exact command and exit code;
   - exact test totals;
   - disposable DB identity;
   - DB before/after hash or canonical digest where required;
   - exact durable/link/callback/validation identity equality;
   - Scheduler job/state/lock totals;
   - active-residue totals;
   - integrity and foreign-key results;
   - provider and authoritative-DB contact counts of zero;
   - protected-capability deltas of zero;
   - no longer-window, retry, rerun, resume, restart, successor, wrapper, or authorization activity.
4. Run only the focused test and directly affected regression set unless a shared-owner failure requires justified expansion.
5. Re-enter a separate independent closeout after the evidence-completion PASS.

## 13. Exact next lane

`V2-9.8B Post-Rollover-2 Authoritative WINDOW_15M token_slot_id Blocker Repair Proof-Evidence Completion`

This next lane may add only the missing focused proof and proof-evidence report on disposable/frozen offline paths.

It must not run the PowerShell wrapper or operational command, contact providers, mutate the authoritative DB, create or apply an authorization, generate authoritative memory, activate retrieval or decisions, unlock financial capabilities, or start any longer window.

Final status:

`SOURCE_REPAIR_ACCEPTED_PROOF_CLOSEOUT_BLOCKED_RUNTIME_LOCKED`
