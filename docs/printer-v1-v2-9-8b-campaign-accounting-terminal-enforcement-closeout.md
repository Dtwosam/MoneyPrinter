# Printer V1 V2-9.8B Campaign Accounting and Terminal Enforcement Closeout

Date: 2026-07-30

Lane: `V2-9.8B Campaign Accounting and Terminal Enforcement Completion`

Verdict:
`V2_9_8B_CAMPAIGN_ACCOUNTING_TERMINAL_ENFORCEMENT_BLOCKED`

## Sequence executed

```text
re-audit affected real path → final design → cohesive repair
→ frozen offline proof → corrected closeout
```

One full sequence was executed (not split into micro-repair lanes). The
accounting and terminal-enforcement core is repaired and proven; the
post-handoff zero-orphan proof (repair 11/12) is BLOCKED by a schema-enforced
invariant of the protected atomic two-slot handoff. Per the lane rule, every
remaining discrepancy is reported together and no further repair was started
automatically.

## Baseline

- Branch: `master`
- Start HEAD: `e864463472ad8c1db6f171847caac885940445fd`
- Authoritative DB SHA-256 (unchanged, never opened for write):
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head remains `049`
- No live provider/RPC/WebSocket, campaign, N2/N7, cursor, recovery, retrieval,
  or financial capability was authorized or run. All proof used frozen
  transports and disposable migration-049 databases only.

## Completed and proven (repairs 1–10, 13)

| # | Requirement | Resolution | Proof |
|---|---|---|---|
| 1 | Exact-pair DexScreener emits exactly one identity on success, HTTP error, rate limit, timeout, decode failure, malformed response, byte ceiling, row ceiling | `build_dexscreener_smoke_transport` now attaches one `TransportOperationIdentity` (`_pair_identity`) to **every** return path with a distinct `result` | `test_exact_pair_every_outcome_emits_exactly_one_identity` (9 outcome classes) |
| 2 | Preserve earlier identities on later-hop failure | Fresh-profiles multi-hop preserves step-1 identity when step-2 fails | `test_fresh_profiles_multi_hop_preserves_first_identity` |
| 3 | Propagate `ACCOUNTING_BLOCKED` as an immediate campaign safe stop; existing registry candidates must not continue | `run_direct_migration_discovery` withholds the entire candidate mix under `accounting_block_reason` (`campaign_safe_stop`, `registry_candidates_withheld`); registry rows are read-only, not handed forward | `test_accounting_blocked_withholds_registry_candidates` |
| 4/5 | Top-level `CampaignSixUnitOwner` threaded through/aggregating every active stage | `aggregate_campaign_six_unit_owner` + `CampaignSixUnitOwner.ingest_stage_evidence`; coordinator `_run_operational_campaign` builds the top-level owner and passes its evidence to the report | `test_top_level_owner_reconciles_every_stage` |
| 6 | Remove optional-dictionary accounting as an authority; owner aggregates | Coordinator no longer treats `reporting.get()/lifecycle.get()` as the six-unit authority; the owner aggregates stage evidence and is the sole source | coordinator wiring; `test_omitted_or_malformed_stage_accounting_fails_closed` |
| 7 | Missing/malformed/duplicate/partial/mismatched evidence fails closed before persistence | `build_campaign_terminal_report(require_six_unit_evidence=True)` + `write_campaign_terminal_report(require_six_unit_evidence=True)` raise `TerminalClosureError`; `_assert_report_six_unit_evidence` guards the write | `test_terminal_build_requires_present_evidence`, `test_write_blocks_on_evidence_mismatch` |
| 8 | No synthetic empty evidence for an attempted campaign | Synthetic `empty_six_unit_evidence()` is rejected under `require_six_unit_evidence` when evidence is absent | `test_terminal_build_requires_present_evidence` |
| 9 | Require `six_unit_evidence_match=True`; else accounting failure, no success report | Mismatch raises `TerminalClosureError` at both build and write | `test_terminal_build_rejects_mismatch`, `test_write_blocks_on_evidence_mismatch` |
| 10 | Replay reconstructs from durable evidence with zero source calls / Scheduler work / writes | `replay_campaign_terminal_report` opens `mode=ro`, contains no `urlopen`/`INSERT`/`UPDATE`/`DELETE`; independent reconstruction equals stored totals | `test_replay_is_read_only_and_reconstructs_from_evidence` |
| — | Normal success creates exactly two mint/pair slots and two `WINDOW_15M` jobs | preserved | `test_normal_success_two_slots_two_window_15m_jobs` + atomic-handoff `test_successful_initial_activation_commits_both` |
| 13 | Correct anchor / supersede prior PASS | anchor updated; prior verifiable-real-path PASS superseded (see below) | anchor doc |

New proof suite: `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py`
— **25 passed**. Broad affected operational suite (14 files) — **202 passed, 15
subtests passed**, with 3 failures that are **pre-existing at the clean baseline
`e864463`** (see "Pre-existing baseline failures"), identical with and without
this lane's changes. This lane introduces **zero regressions**.

## BLOCKED discrepancies (repairs 11–12)

### D-1 (primary): literal "zero slots / jobs / links" is unreachable after a committed initial handoff

Repair 12 requires each post-handoff failure to leave **zero** newly active or
orphan slots, queue rows, jobs, leases, batches, links, and lifecycle objects.
The affected real path makes this **schema-impossible** for the committed atomic
two-slot handoff:

- `printer_discovery_selected_item_links` is **append-only immutable** — both
  `BEFORE UPDATE` and `BEFORE DELETE` triggers `RAISE(ABORT,
  'discovery selected item link is immutable')` (migration 034).
- The atomic initial handoff commits these links with
  `tracking_handoff_state='HANDOFF_RECORDED'` (`combined_executor.py`).
- That immutable link **FK-pins** the token slots
  (`token_slot_id, campaign_id → printer_memory_factory_campaign_token_slots`)
  and the first-15m job (`first_window_15m_scheduler_job_id →
  printer_scheduler_jobs`), both `NO ACTION`.

Therefore, once the handoff has committed, the audit links cannot be deleted,
and the slots and first-15m jobs cannot be deleted while the links reference
them. A post-handoff compensation can only remove the state the **subsequent
lifecycle stages** materialized (the origin-activated selection batch, run
steps, lifecycle-event objects). The committed handoff (slots, tracking,
first-15m jobs, immutable audit links) **survives by design**.

The implemented compensation (`_compensate_post_handoff_teardown`) reflects this
exactly: it drives the deletable lifecycle-materialization residual to zero and
**reports** the surviving schema-pinned handoff residual. The proof
(`test_post_handoff_fault_compensation_and_pinned_handoff_residual`, all five
stages) asserts `pinned_slots >= 1`, `pinned_first_15m_jobs >= 1`,
`pinned_immutable_links >= 1` — the direct evidence that literal zero is not met.

Reaching literal zero would require the atomic two-slot handoff to **defer**
immutable audit-link creation until past the post-handoff lifecycle, changing a
design the preserve-list protects (canonical deterministic two-token selector;
atomic exact two-token handoff) and breaking its existing proof
(`test_successful_initial_activation_commits_both` asserts `selected_links == 2`
at handoff commit). That redesign is outside an accounting/terminal-enforcement
lane and was not undertaken.

### D-2 (secondary): object-materialization / post-activation injections are driver-level simulations

Injection stages 1–3 (selection-batch creation, executor-job cancellation, job
replanning) fire inside the real materialization/handoff path. Stages 4–5
(lifecycle object materialization, post-activation state transition) are applied
as a **representative** lifecycle object / batch-state transition at the driver
boundary and then faulted, rather than faulting **inside** the real
`run_one_command_15m_factory` runner mid-materialization. The compensation is
proven against that representative state, not against runner-created lifecycle
objects. A complete proof would fault within the real runner's materialization.

## Pre-existing baseline failures (not caused by this lane)

`tests/test_v2_9_8b_selective_1h_liquidity_evidence_repair.py` fails 3 tests
(`test_24_identical_transport_failures_are_source_unavailability_with_ownership`,
`test_budget_exhaustion_and_true_supply_exhaustion_remain_distinct`,
`test_blocked_supply_and_terminal_artifact_are_truthful_and_keep_locks`) at
`e864463` **with this lane's changes stashed** — identical `assert 2 == 1`
(`provider_failures`) at line 525. They are pre-existing and unrelated to this
lane. They are reported here for completeness and are a separate blocker for any
subsequent operator review.

## What remains locked

Live probe, campaign, N2/N7/cursor/recovery/backfill, PumpPortal ordinary
authority, capacity >2, longer-window production, retrieval, decisions,
BUY/SELL/HOLD, positions, trades, audits, PnL, wallets/keys/signing, paid APIs,
scoring/ranking/confidence/weighting/embeddings, automatic
retry/restart/successor. No ceiling was raised. No authoritative DB mutation.

## Anchor

The prior verifiable-real-path PASS
(`V2_9_8B_DISCOVERY_SELECTION_VERIFIABLE_REAL_PATH_PASS`) is superseded and its
operator-review-blocked status is confirmed: this lane closed repairs 1–10 and
13 but is BLOCKED on repairs 11–12 (D-1, D-2) plus the pre-existing baseline
failures. The active anchor is updated to this lane and this verdict.

## Exact next permitted task

Independent operator review of the blocker evidence only (D-1, D-2, and the
pre-existing baseline failures). There is no automatic repair, retry, or
successor. No commit was made (commit is authorized only on PASS). No tag, no
push.
