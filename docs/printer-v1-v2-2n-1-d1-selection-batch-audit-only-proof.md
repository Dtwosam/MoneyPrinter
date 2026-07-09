# Printer V1 V2-2N.1 D1 Selection-Batch Audit-Only Proof

Status: `BOUNDED DETERMINISTIC FIXTURE PROOF`

Final verdict:

`V2-2N.1 D1 / Selection-Batch Audit-Only Representation Follow-Up Proof: PROOF_PASS`

V2-2J and V2-3 remained paused during this proof. No live source was called.
No persistent database was changed.

## 1. Source Stack and Anchors

The proof used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2l-watch-only-d1-quota-handoff-design.md`
- `docs/printer-v1-v2-2n-watch-only-d1-handoff-bounded-proof.md`

Implementation and proof anchors:

- V2-2L design: `da584d9`
- V2-2M implementation: `0fc06a0`
- V2-2M.2 eligibility repair: `e70c605`
- V2-2N bounded proof: `04cb35f`

## 2. Proof Setup

| Item | Result |
|---|---|
| Proof mode | Deterministic fixture, not live evidence |
| Persistent DB | `data/printer_v1.sqlite3`, hash verification only |
| Proof DB | `data/printer_v1_v2_2n_1_d1_selection_batch_proof.sqlite3` |
| DB mode | Isolated copy |
| Migrations | Existing migration runner, proof DB only |
| Selection implementation | V2-2C `validate_batch_quota()`, `build_batch_item()`, and `persist_selection_batch()` |
| Batch ID | `V2-2N1-D1-AUDIT-ONLY-PROOF` |
| Window kind | `WINDOW_15M` |
| Live source fetching | Not run |
| Runtime/scheduler execution | Not run |

The persistent DB SHA-256 remained
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`
before and after the proof.

The fixture inserted one isolated, controlled source request and response into
the proof DB so selected items could retain valid foreign-key source trace:

- source request ID: `1119`;
- source response ID: `1072`;
- source name: `geckoterminal`;
- source status: `COMPLETE`;
- data quality: `CLEAN_DATA`.

These are deterministic fixture rows. They are not claimed as live source
evidence.

## 3. Candidate Pool Summary

| Candidate kind | Count | Tracking lane | Bucket role |
|---|---:|---|---|
| Active tracking | 6 | `TRACK_NORMAL` | `B5` consolidation |
| Audit-only WATCH_ONLY | 1 | `WATCH_ONLY` | `B5` |
| Audit-only D1 | 1 | `WATCH_ONLY` | `D1` dead token |
| Total | 8 | Mixed | Quota fixture |

All candidates were Solana fixture candidates. The two audit-only candidates
were `COMPLETE`, `CLEAN_DATA`, and eligible under the repaired
`_is_audit_only_eligible()` gate.

## 4. Quota Before and After

### Active candidates only

Result: `FAIL`

Violations:

- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`;
- `MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH`.

### Active candidates plus eligible WATCH_ONLY

Result: `FAIL`

Remaining violation:

- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`.

This proves the WATCH_ONLY candidate satisfies only the WATCH_ONLY minimum.

### Active candidates plus eligible WATCH_ONLY and D1

Result: `PASS`

Violations: none.

This proves the eligible D1 candidate satisfies the D1 minimum and changes the
otherwise valid fixture batch from quota failure to quota success.

### Active candidates plus unsafe audit-only inputs

The unsafe fixture candidates were:

- D1 with source status `FAILED`;
- WATCH_ONLY with data quality `DIRTY_DATA`.

Both returned `eligible = false`. The production selection gate produced an
empty audit-only pool, and quota remained `FAIL` with both D1 and WATCH_ONLY
violations. Unsafe candidates therefore could not create a fake quota pass.

## 5. D1 Proof Result

The D1 fixture candidate:

- was Solana;
- had source status `COMPLETE`;
- had data quality `CLEAN_DATA`;
- carried bucket `D1`;
- carried tracking lane `WATCH_ONLY`;
- carried `candidate_kind = AUDIT_ONLY`;
- carried `audit_only = true`;
- retained rejection reason
  `insufficient_activity_for_memory_growth`;
- retained full source trace.

Adding it after the eligible WATCH_ONLY candidate changed quota from
`MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH` to a clean pass.

Result: `D1_AUDIT_ONLY_QUOTA_PROOF_PASS`.

## 6. Selection-Batch Representation

The persisted proof batch contained:

- 8 selected items;
- 6 `ACTIVE_TRACKING` items;
- 2 `AUDIT_ONLY` items;
- 0 rejected items;
- 0 unclassified items.

The existing V2-2C schema has no dedicated `candidate_kind` column. The proof
used its existing `candidate_metadata_json` extension field, which is the
parallel JSON representation permitted by the V2-2L design.

For every active item, metadata contained:

- `candidate_kind = ACTIVE_TRACKING`;
- `audit_only = false`;
- source channel reason.

For both audit-only items, metadata contained:

- `candidate_kind = AUDIT_ONLY`;
- `audit_only = true`;
- source channel reason;
- pre-persistence rejection reason.

The ordinary item columns separately retained:

- `item_status = SELECTED`;
- `selection_reason = AUDIT_ONLY_QUOTA_SUPPLEMENT`;
- `rejection_reason`;
- `tracking_lane = WATCH_ONLY`;
- `source_name`;
- `source_channel`;
- `source_response_id`.

Active and audit-only counts were also stored in batch
`pool_summary_json` as:

- `active_tracking_selected_count = 6`;
- `selected_audit_only_count = 2`.

Result: `SELECTION_BATCH_REPRESENTATION_PASS`.

## 7. Source Trace and Rejection Reasons

### Audit-only WATCH_ONLY

- mint: `V22N1WatchOnlyMint`;
- source name: `geckoterminal`;
- source channel: `FIXTURE_WATCH_CHANNEL`;
- source response ID: `1072`;
- source channel reason: `deterministic_fixture_watch_only`;
- rejection reason:
  `watch_only_not_eligible_for_15m_memory_proof_cycle`.

### Audit-only D1

- mint: `V22N1DeadTokenMint`;
- source name: `geckoterminal`;
- source channel: `FIXTURE_D1_CHANNEL`;
- source response ID: `1072`;
- source channel reason: `deterministic_fixture_dead_token`;
- rejection reason: `insufficient_activity_for_memory_growth`.

All required trace and reason fields survived selection-batch persistence.

## 8. Row-Delta Lock Proof

### Expected proof-only deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1118 | 1119 | +1 fixture trace |
| `printer_source_responses` | 1071 | 1072 | +1 fixture trace |
| `printer_source_failures` | 47 | 47 | 0 |
| `printer_selection_batches` | 0 | 1 | +1 |
| `printer_selection_batch_items` | 0 | 8 | +8 |

### Active and downstream lock deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_discovery_candidates` | 15 | 15 | 0 |
| `printer_tracking_queue` | 15 | 15 | 0 |
| `printer_scheduler_jobs` | 989 | 989 | 0 |
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_queries` | 10 | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| PnL table | Absent | Absent | 0 |

Neither audit-only candidate was inserted into discovery, tracking, or
scheduler tables. No memory, retrieval, paper, position, trade, audit, or PnL
path was executed.

## 9. Comparison With V2-2N

| Gap | V2-2N | V2-2N.1 |
|---|---|---|
| Live WATCH_ONLY handoff | Passed | Preserved by regression tests |
| Eligible D1 observed | No | Deterministic fixture, passed |
| D1 changes quota to pass | Not measured live | Proven |
| Unsafe D1/WATCH_ONLY blocked | Targeted tests | Re-proven in fixture path |
| Active/audit-only batch distinction | Command report only | Persisted V2-2C batch representation |
| Full source trace/reason persisted | Command report | Selection-batch row plus metadata JSON |
| Audit-only tracking/scheduler rows | 0 | 0 |
| Downstream locked deltas | 0 | 0 |

V2-2N honestly stopped when its live source sample contained no D1 and did not
create a selection batch. V2-2N.1 closes both proof gaps without pretending the
fixture is live evidence.

## 10. Tests and Checks

Required suites:

- `tests/test_v2_2m_audit_only_handoff.py`: 95 passed.
- Remaining eight required suites combined: 418 passed and 219 subtests passed.
- Total: 513 tests passed and 219 subtests passed.

Pytest emitted a non-failing cache warning because `.pytest_cache` could not be
created. The tests did not mutate the persistent database.

## 11. Remaining Blockers

The two V2-2N follow-up proof gaps are closed.

Broader V2-2 blockers remain outside this proof:

- token creation age remains unavailable from current live discovery shapes;
- native 15m price/volume fields require staged governed evidence;
- A3 remains blocked by token age;
- A4 remains helper-only;
- productive cross-provider discovery remains limited;
- PumpPortal and PumpSwap discovery channels remain not ready;
- a live D1 sample remains desirable but is not required to validate the
  deterministic selection contract.

The existing selection schema represents candidate kind and source channel
reason inside `candidate_metadata_json`, not dedicated columns. This is
auditable and conforms to the V2-2L parallel-JSON option, but future reporting
must continue parsing that metadata rather than assuming first-class columns.

## 12. Final Verdict

`V2-2N.1 D1 / Selection-Batch Audit-Only Representation Follow-Up Proof: PROOF_PASS`

The proof demonstrates:

- eligible WATCH_ONLY and D1 candidates satisfy their exact quota minimums;
- quota passes only after both safe audit-only types are supplied;
- failed/dirty alternatives remain excluded and cannot satisfy quota;
- one persisted V2-2C batch clearly separates six active and two audit-only
  items;
- source trace and rejection reasons survive persistence;
- audit-only candidates create no discovery, tracking, scheduler, memory,
  retrieval, paper, position, trade, audit, or PnL rows;
- the persistent DB remains unchanged.

## 13. Next Recommended Lane

V2-3 remains paused.

After operator acceptance of this proof, V2-2J closeout may resume. V2-2J
should consolidate the V2-2K, V2-2N, and V2-2N.1 findings, explicitly preserve
the broader token-age, native-15m, A3/A4, and source-coverage blockers, and
decide whether those blockers remain inside V2-2 or are carried into later
approved lanes.
