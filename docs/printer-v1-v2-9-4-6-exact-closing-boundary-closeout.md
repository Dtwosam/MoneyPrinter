# Printer V1 V2-9.4.6 Exact Closing Boundary Closeout

## Verdict

`V2_9_4_6_EXACT_CLOSING_BOUNDARY_PASS`

Lane: `V2-9.4.6 - Implement exact 4h run-ledger and closing-evidence boundaries`

Design steps 3-5 of `printer-v1-v2-9-4-4-evidence-boundary-memory-semantics-design.md`
are implemented. 4h snapshot selection is now bound to the current run ledger by
exact id, the immutable logical deadline is separated from the closing-evidence
cutoff, and closing safety/exit-quote evidence attaches only when bound to the
exact `snapshot_end_id`. The three boundary blockers the Attempt 6 forensic audit
proved false are gone; every genuine fail-closed path is preserved and
fixture-proven. No migration, no historic rewrite, no schema change.

Preflight passed: HEAD exactly `4933bf8`, tracked tree clean, no proof runtime,
no one-proof lock.

## What was wrong

`context_evidence/window_15m.py` -- the shared resolver for WINDOW_15M and
WINDOW_4H -- carried the two remaining Attempt 6 defects (defect A, the
outcome/evidence conflation, was repaired in V2-9.4.5):

**B. Selection scanned by wall clock.** Snapshots were selected with a
`captured_at >= window_start_at` scan. The run ledger was consulted only
afterwards, for an `exact_bounds` check. A predecessor snapshot captured at
*exactly* `window_start_at` therefore entered the set, shifting the boundary and
raising `SNAPSHOT_BOUNDARY_MISMATCH` against a set the scan itself had corrupted.

**C. The logical deadline doubled as the evidence cutoff.** Closing safety and
quote lookups passed `target_time=window_end`. Attempt 6's closing snapshot
(id 1113) was captured 3.66s after the logical deadline -- well inside the
approved `closing_clean_late_seconds = 60` allowance the cadence policy already
defines -- so its safety composite and exit quote were rejected as
"no valid exact target evidence" when the evidence existed, was governed, was
clean, and was bound to the correct snapshot.

Net effect: a 61/61-snapshot, zero-miss, exact-continuity 4h window was blocked
for three reasons that were all artefacts of the resolver, not facts about the
token.

## Implementation (smallest change)

| File | Change |
| --- | --- |
| `src/printer_v1/context_evidence/window_15m.py` | Ledger-exact selection by `id BETWEEN snapshot_start_id AND snapshot_end_id` with exact `token_id`/`pair_id`, intersected against the current run's ledger snapshot ids. Logical deadline preserved; `closing_evidence_cutoff_at` derived from `closing_clean_late_seconds`. Safety/quote lookups bounded by the cutoff, with a `target_time=None` probe to distinguish *late* evidence from *absent* evidence. Specific blockers replace the generic ones. Report gains `closing_evidence_cutoff_at`, `closing_evidence_allowance_seconds`, `non_ledger_snapshot_ids`. |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | The 4h caller (`_execute_long_4h_step`) passes `tracking_lane` and `run_id`. The 15m caller is deliberately left unwired, with a comment recording why (see below). |
| `tests/test_v2_4_1_shared_context_evidence.py` | Two stale assertions updated to the new specific blocker names. Statically confirmed stale, not regressions: both fixtures still fail closed with identical statuses; only the blocker name became more precise. |
| `tests/test_v2_9_4_6_exact_closing_boundary.py` | New boundary fixture matrix (below). |

`tracking_lane` and `run_id` are optional keyword arguments defaulting to `None`.
With `run_id=None` the ledger intersection is skipped; with `tracking_lane=None`
the allowance collapses to `0`, reproducing today's exact behaviour. Every
existing caller is therefore unchanged by construction.

### The 15m caller is intentionally not wired

`_execute_close` calls the resolver at `one_command_15m_factory.py:1198`, but the
15m close step's own `snapshot_id` is not written to the run ledger until
`one_command_15m_factory.py:2712` -- *after* `_execute_close` returns. Passing
`run_id` there would make the intersection exclude the closing snapshot and raise
a false `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER` on every 15m close: precisely the
class of self-inflicted false blocker this lane exists to remove.

The 4h path has the opposite, correct ordering: `_execute_long_4h_step` writes
its ledger row at line 1500 and calls the resolver at line 1532, with an existing
comment recording that cadence and continuity may consume only ledger-attached
snapshots. This lane is scoped to the 4h boundary, so the 4h path is wired and
the 15m path is left byte-for-byte equivalent. Passing `tracking_lane` to the
15m path would additionally have widened its closing cutoff from 0s to 60s -- an
unrelated contract change this lane is not authorised to make.

Wiring the 15m path requires reordering that close's ledger write, which is a
separate, explicitly-scoped lane.

### Why the ledger intersection is not filtered by step status

The proven cadence precedent at line 1158 filters `step_kind='SNAPSHOT' AND
step_status='SUCCEEDED'`. The intersection here deliberately does **not**: the
closing step is still `RUNNING` when the resolver executes, so a `SUCCEEDED`
filter would drop the closing snapshot and re-create the exact false blocker
being repaired. Filtering on `run_id` with `snapshot_id IS NOT NULL` is the
correct authoritative identity set.

## Blockers

Specific blockers replacing misleading generic boundary blockers:

| Blocker | Fires when |
| --- | --- |
| `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER` | A selected snapshot is not attached to the current run's ledger |
| `CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF` | Evidence exists for the exact snapshot but past the approved allowance |
| `CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT` | No safety composite bound to the exact `snapshot_end_id` |
| `CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT` | No exit quote bound to the exact `snapshot_end_id` |
| `CLOSING_EVIDENCE_TARGET_MISMATCH` | Evidence exists but its target identity does not match |

`SNAPSHOT_BOUNDARY_MISMATCH` is retained as a genuine assertion over the exact
set: it now fires only when the exact ledger set does not reach the requested
boundary, never as a scan artefact. Truthful chart and flow labels are preserved;
the flow and chart sections were de-masked so a snapshot-set fault is reported as
itself rather than as a false `FLOW_...`/`CHART_...` fault.

## Fixture matrix

`tests/test_v2_9_4_6_exact_closing_boundary.py` -- **15 passed**. The window is
Attempt 6-shaped: predecessor at id 1052 captured at exactly `window_start_at`,
61 ledger snapshots at ids 1053-1113, closing snapshot 3.66s after the deadline.

| Fixture | Result |
| --- | --- |
| Predecessor at exactly `window_start_at` | excluded; exact ids 1053-1113 selected |
| Future snapshot beyond `snapshot_end_id` | excluded |
| Unrelated token/pair inside the id range | excluded |
| Snapshot from another run's ledger | `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER`, fails closed |
| Count-decoy set (correct count, wrong identity) | cannot pass |
| `SNAPSHOT_BOUNDARY_MISMATCH` | still a genuine assertion over the exact set |
| Logical deadline and duration | immutable; cutoff separate and strictly later |
| Cadence / duration / geometry with vs without lane | identical |
| Closing snapshot inside the freshness allowance | accepted |
| Closing evidence outside the allowance | `CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF` |
| Exact closing safety + exit quote | attached; `SAFETY_CLEAN`, `EXIT_REALISTIC` |
| Evidence attached to another snapshot | rejected, fails closed |
| Evidence for another pair | rejected, fails closed |
| Missing closing evidence | still fails closed |
| Attempt 6-shaped window | the three proven-false blockers are gone |
| Retrieval and every financial delta | zero; resolver writes nothing |

## Verification performed

Minimum sufficient verification for the change risk, per the risk-based
verification policy (`AGENTS.md`, commit `ddbfdc7`).

| Check | Result |
| --- | --- |
| New boundary fixtures | 15 passed |
| Cadence, continuity, long-window foundation, chained continuity, 4h runtime, Lane U cadence policy | 153 passed, 70 subtests |
| E2Q, Lane Q, Lane K/E2Z, E2Z clean-memory creation, shared context evidence | 386 passed |
| Python compilation | `COMPILE_OK` |
| Persistent DB hash unchanged | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| `git diff --check` | clean |
| Migration added | none -- zero files under `migrations/` |
| Temporary isolated fixture DBs only; no live sources; no full repository suite | confirmed |

## Scope honoured

Outcome/evidence semantics from V2-9.4.5 are unchanged. Partial trading flow is
not made optional. No provider requirement was added or weakened. Attempt 6 and
all historic rows are untouched -- this lane changes forward resolution only.
Cadence thresholds, budgets, sources, retries and supervision are unchanged; the
launcher and its supervision are untouched. No migration.

## Money-usefulness contribution

Combined with V2-9.4.5, this is the difference between a 4h proof that can
succeed and one that cannot. Attempt 6 produced a flawless 61/61 evidence record
and was rejected for three reasons that were all resolver artefacts. A machine
that discards perfect evidence because its own boundary arithmetic disagrees with
its own ledger cannot build memory at any scale. No clean memory is created by
this lane; it removes the last boundary rule that was destroying it.

## What improves

- Snapshot identity comes from the run ledger, the authoritative source, instead
  of a wall-clock scan that could silently swap in a neighbour.
- "Too late" and "absent" are now distinguishable, so an operator reading a
  blocker learns what actually happened.
- The logical deadline is immutable and provably separate from the evidence
  cutoff, so allowing marginally-late closing evidence never extends the window.
- A snapshot-set fault is reported as itself rather than masquerading as a chart
  or flow fault.

## What remains locked

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`
and `WINDOW_24H` all remain locked. `WINDOW_5M_MICRO_EVENT` stays support-only.
No Attempt 7, no V2-10, no memory growth.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **The 15m close path has no ledger protection.** Its ledger write happens
   after context resolution, so it is intentionally unwired. 15m windows remain
   exactly as exposed to predecessor-swap as before this lane -- no worse, but no
   better. Fixing it needs a close-ordering lane.
2. **Partial trading flow still gates clean promotion.** Unresolved by design and
   out of scope here. DexScreener cannot supply split volume / unique-wallet
   fields, so a 4h window may still fail to reach clean for that reason even with
   perfect boundaries. This is now the most likely remaining blocker for an
   Attempt 7.
3. **The stored Attempt 6 window is still `DIRTY_MEMORY`.** Forward resolution
   only. Re-deriving it is an explicit operator decision.
4. **The 60s allowance is a policy value, not a proof.** It is the existing
   approved `closing_clean_late_seconds`; this lane consumes it rather than
   justifying it. If real closing latency regularly exceeded 60s, windows would
   still fail -- truthfully, but the threshold would deserve review.
5. **The ledger intersection trusts the ledger.** If a run step fails to record
   its `snapshot_id`, its snapshot is excluded and the window fails closed. That
   is the correct fail-closed direction, but it moves a class of failure from the
   resolver onto ledger-write reliability.
6. **This lane is not proven end-to-end.** Fixtures prove the boundary contract
   under controlled conditions. Only a real bounded 4h run can prove the full
   path, and that requires separate operator approval.

## Files changed

- `src/printer_v1/context_evidence/window_15m.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_4_1_shared_context_evidence.py`
- `tests/test_v2_9_4_6_exact_closing_boundary.py` (new)
- `docs/printer-v1-v2-9-4-6-exact-closing-boundary-closeout.md` (this file)

## Next recommended phase

Resolve whether partial trading flow is mandatory for clean promotion (risk 2) --
it is now the most probable blocker for a 4h window that satisfies every boundary
and evidence contract. That requires a separate operator-approved lane, as does
any Attempt 7, V2-10, memory growth, retrieval, or financial unlock. **Not
started here.**
