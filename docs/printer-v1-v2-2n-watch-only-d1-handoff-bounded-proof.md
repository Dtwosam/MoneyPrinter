# Printer V1 V2-2N WATCH_ONLY / D1 Handoff Bounded Proof

Status: `BOUNDED PROOF`

Final verdict:

`V2-2N WATCH_ONLY / D1 Candidate-Pool Handoff Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

V2-2J and V2-3 remain paused. This proof exercised the repaired audit-only
handoff on an isolated database. It did not generate memory, run retrieval,
create paper decisions, or unlock any trading capability.

## 1. Source Stack and Anchors

The proof used these documents together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md`
- `docs/printer-v1-v2-2l-watch-only-d1-quota-handoff-design.md`

Implementation anchors:

- V2-2K audit: `2cd7940`
- V2-2L design: `da584d9`
- V2-2M implementation: `0fc06a0`
- V2-2M.2 eligibility repair: `e70c605`

## 2. Proof Setup

| Item | Result |
|---|---|
| Persistent DB | `data/printer_v1.sqlite3`, hash verification only |
| Proof DB | `data/printer_v1_v2_2n_audit_only_handoff_proof.sqlite3` |
| DB mode | Isolated copy of the persistent DB |
| Migration handling | Existing migration runner applied to proof DB only |
| Source | `geckoterminal` |
| Channels | New-pool discovery and trending-pool reference |
| Maximum candidates | 20 |
| Maximum source requests | 2 |
| Timeout | 5 seconds per request |
| Operator approval | Explicit |
| Chain | Solana only |
| Source Governor | Confirmed existing governed command path |
| Scheduler execution | Not run |
| Proof request interval | `2026-07-09T09:04:49.198407+00:00` to `2026-07-09T09:04:51.940872+00:00` |
| Command elapsed time | Approximately 5.57 seconds including command setup/reporting |

Command path:

```text
main_discover_candidates_once
--db-path data/printer_v1_v2_2n_audit_only_handoff_proof.sqlite3
--operator-approved
--chain solana
--source-name geckoterminal
--request-kind geckoterminal_new_pool_discovery
--max-candidates 20
--max-source-requests 2
--timeout-seconds 5
--request-key v2-2n-audit-only-handoff-proof-20260709
--format json
```

The persistent DB SHA-256 was
`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`
before and after the proof.

## 3. Source-Budget Metrics

| Metric | Result |
|---|---:|
| Source requests planned | 2 |
| Source requests attempted | 2 |
| Source responses received | 2 |
| Source failures | 0 |
| Source failure rate | 0.0% |
| Channels planned | 2 |
| Channels sampled | 2 |
| Channels not ready | 0 |
| Channels failed | 0 |
| Candidates seen, GeckoTerminal | 40 |
| Candidates seen, new pools | 20 |
| Candidates seen, trending | 20 |
| Candidates persisted, GeckoTerminal | 20 |
| Candidates persisted, new pools | 12 |
| Candidates persisted, trending | 8 |

Source request IDs were `1119` and `1120`. Source response IDs were `1072`
and `1073`. Both responses were HTTP 200, `COMPLETE`, and `CLEAN_DATA`.

## 4. Candidate-Stage Metrics

| Metric | Result |
|---|---:|
| Candidates seen | 40 |
| Candidates normalized | 40 |
| Active candidates persisted | 20 |
| Candidates rejected before persistence | 20 |
| Audit-only candidates captured | 7 |
| Audit-only WATCH_ONLY candidates | 7 |
| Audit-only D1 candidates | 0 |
| Audit-only candidates used for quota | 1 |

The audit-only candidates were a subset of the rejected pre-persistence
population. They were not moved into the active accepted list.

## 5. Audit-Only Handoff Metrics

| `audit_only_report` field | Result |
|---|---:|
| `raw_watch_only_count` | 7 |
| `audit_only_watch_only_count` | 7 |
| `persisted_watch_only_count` | 0 |
| `selected_watch_only_count` | 1 |
| `raw_d1_count` | 0 |
| `audit_only_d1_count` | 0 |
| `persisted_d1_count` | 0 |
| `selected_d1_count` | 0 |
| `audit_only_candidate_count` | 7 |
| `selected_audit_only_count` | 1 |
| `active_tracking_selected_count` | 20 |
| `quota_satisfied_by_audit_only_count` | 1 |
| `candidates_excluded_from_tracking_but_used_for_quota` | 1 |

The live sample therefore proved:

- eligible WATCH_ONLY candidates remain visible after their active-tracking
  rejection;
- all seven eligible WATCH_ONLY candidates entered the transient audit-only
  pool;
- one audit-only WATCH_ONLY candidate supplied only the missing WATCH_ONLY
  quota minimum;
- no WATCH_ONLY candidate was persisted as active tracking.

The live source sample contained no D1 candidate. D1 capture and quota
supplementation were therefore not proven from this live response. The targeted
V2-2M suite separately proved that an eligible D1 candidate enters the
audit-only pool and can satisfy both the WATCH_ONLY and D1 minimums.

## 6. Eligibility and Unsafe-Candidate Proof

Both live responses were `COMPLETE` and `CLEAN_DATA`, so the live pool contained
only source-eligible candidates. The repaired targeted test suite additionally
proved that these cases do not enter the audit-only pool:

- source status `FAILED`;
- source status `STALE`;
- dirty or stale data quality;
- missing critical data quality;
- unknown or missing data-quality labels;
- non-Solana candidates;
- instant-reject candidates;
- duplicate audit-only mints.

Unsafe candidates remain rejected and cannot satisfy quota.

## 7. Source-Trace Verification

All seven live audit-only candidates carried all required trace fields:

- `source_name = geckoterminal`;
- `source_channel = GECKOTERMINAL_NEW_POOL`;
- `source_response_id = 1072`;
- `source_channel_reason = geckoterminal_new_pool_discovery`.

Every item also retained
`pre_persistence_reject_reason = watch_only_not_eligible_for_15m_memory_proof_cycle`.
No trace field was null.

## 8. Selection and Quota Result

The command evaluated the active candidate view and then applied the bounded
audit-only quota supplement once.

Result:

- WATCH_ONLY requirement: resolved by one audit-only candidate;
- D1 requirement: unresolved because no D1 was present;
- overall quota: `FAIL`;
- quota was not forced.

Remaining quota violations:

- `WINNER_CAP_EXCEEDED_A1_MAX_2`;
- `GROUP_A_PRESENT_BUT_NO_TRAP_FAILURE_BUCKET`;
- `MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH`.

The proof DB retained zero `printer_selection_batches` and zero
`printer_selection_batch_items`. The repaired command-level handoff and quota
report were proven, but an actual persisted V2-2C batch containing an
`AUDIT_ONLY` item was not created. That remains a proof limitation rather than
an excuse to fabricate a D1 candidate.

## 9. Active Versus Audit-Only Isolation

The 20 accepted active candidates created the expected proof-only rows:

- 20 discovery candidates;
- 20 tracking queue rows;
- 20 bounded scheduler jobs.

Direct mint lookup for all seven audit-only candidates found:

- token rows: 0;
- tracking queue rows: 0;
- scheduler jobs attributable to those candidates: 0.

Thus the permitted tracking/scheduler deltas came from active candidates only.
Audit-only candidates consumed no active tracking or scheduler capacity.

## 10. Row-Delta Lock Proof

### Allowed proof-DB deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_source_requests` | 1118 | 1120 | +2 |
| `printer_source_responses` | 1071 | 1073 | +2 |
| `printer_source_failures` | 47 | 47 | 0 |
| `printer_discovery_candidates` | 15 | 35 | +20 |
| `printer_tracking_queue` | 15 | 35 | +20 active-only |
| `printer_scheduler_jobs` | 989 | 1009 | +20 active-only |
| `printer_selection_batches` | 0 | 0 | 0 |
| `printer_selection_batch_items` | 0 | 0 | 0 |

### Required locked deltas

| Table | Before | After | Delta |
|---|---:|---:|---:|
| `printer_memory_windows` | 156 | 156 | 0 |
| `printer_memory_retrieval_queries` | 10 | 10 | 0 |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| PnL table | Absent | Absent | 0 |

The persistent DB hash remained unchanged.

## 11. Comparison With V2-2K

| Area | V2-2K | V2-2N |
|---|---|---|
| Raw WATCH_ONLY visibility | 13 raw | 7 raw |
| WATCH_ONLY available to quota | 0 | 7 audit-only |
| WATCH_ONLY selected for quota | 0 | 1 |
| D1 available to quota | 0 despite raw D1 elsewhere | 0 because this live sample had no D1 |
| WATCH_ONLY violation | Present | Resolved |
| D1 violation | Present | Still present honestly |
| WATCH_ONLY active persistence | 0 | 0 |
| Audit-only source trace | Not available | All four fields present |
| Audit-only tracking/scheduler leakage | Not applicable | 0 / 0 |

V2-2K established a structural contradiction: WATCH_ONLY was required by quota
but removed before selection. V2-2N proves that the repaired handoff resolves
that contradiction when an eligible WATCH_ONLY candidate exists. It does not
claim that D1 is resolved when the governed source sample supplies none.

## 12. Tests and Checks

Required targeted suites:

- `tests/test_v2_2m_audit_only_handoff.py`: 95 passed.
- Remaining eight required suites combined: 418 passed and 219 subtests passed.
- Total: 513 tests passed and 219 subtests passed.

Pytest emitted a non-failing cache warning because `.pytest_cache` could not be
created. No live or persistent database was used by the tests.

## 13. Remaining Blockers

1. No live D1 candidate appeared, so live D1 capture and D1 quota satisfaction
   remain unproven.
2. Overall quota still failed because D1 and fast-event diversity were absent.
3. No persisted V2-2C selection batch represented the audit-only supplement;
   the proof is command-report-level.
4. Token age and native 15m fields remain missing from this source shape.
5. A3 remains blocked by token age, and A4 remains helper-only.
6. Productive cross-provider and launch/migration coverage remain separate
   V2-2 blockers.

## 14. Final Verdict

`V2-2N WATCH_ONLY / D1 Candidate-Pool Handoff Bounded Proof: PROOF_PASS_WITH_BLOCKERS`

The core repaired behavior passed:

- safe live WATCH_ONLY candidates entered the audit-only pool;
- one candidate repaired the WATCH_ONLY quota dimension;
- unsafe source/data states are blocked by tested eligibility guards;
- full source trace and rejection reasons remained visible;
- audit-only candidates created no active or downstream rows;
- quota failed honestly when D1 was absent;
- all downstream locks and the persistent DB were preserved.

The proof is not a full D1 end-to-end pass because the governed sample contained
no D1 candidate, and it did not create a persisted V2-2C batch carrying an
audit-only item.

## 15. Next Recommended Lane

Keep V2-2J and V2-3 paused.

The next safe step is a narrow V2-2N follow-up proof using a governed sample or
deterministic isolated fixture that contains an eligible D1 candidate and
demonstrates explicit active-versus-audit-only representation at the V2-2C
selection-batch boundary. It must retain zero tracking, scheduler, memory,
retrieval, paper, position, trade, audit, and PnL deltas for the audit-only
candidate.
