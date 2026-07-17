# Printer V1 V2-9.4.8 15m Close Ordering and Exact-Ledger Attachment Closeout

## Executive verdict

`V2_9_4_8_15M_CLOSE_ORDERING_PASS`

The 15m close now attaches the exact closing snapshot to the current-run ledger
and verifies its identity **before** shared context resolves. The last known
ordering barrier to ledger-exact identity on the 15m path is removed, closing the
gap left open by V2-9.4.6. The 4h path is unchanged, the 15m zero-second
closing-lateness contract is preserved, and no schema, adapter, budget, cadence,
supervision or migration was touched.

## Starting commit

`3bddcfd` — preflight verified: HEAD exactly `3bddcfd`, tracked tree clean, no
proof runtime, no one-proof lock (`runs/v2-9-one-proof.lock.json` absent), 161
unrelated untracked historical artifacts baselined and untouched.

The prior V2-9.4.8 attempts failed inside the Codex desktop `apply_patch` helper
under the Windows split-writable-roots sandbox. That was an environment failure.
This lane restarted from the beginning using normal repository-editing tools and
added no `apply_patch` availability gate.

## Defect confirmed

`_execute_close` persisted the closing snapshot, then resolved shared context,
and only afterwards did the snapshot_id reach the ledger — either at
`one_command_15m_factory.py:2720` (guarded by `continuous_first_hour`) or via the
generic `_update_step` finalizer. **Both attachment sites are after
`_execute_close` returns**, so the defect held on every 15m path.

Proven, not assumed. With the closing snapshot absent from the ledger — exactly
the pre-repair state — the V2-9.4.6 resolver reports:

```
blockers                : [... 'SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER',
                              'SNAPSHOT_BOUNDARY_MISMATCH']
non_ledger_snapshot_ids : [6]
snapshot_ids            : [2, 3, 4, 5]      # closing snapshot 6 dropped
```

Both blockers are false: the snapshot is real, governed, clean, and belongs to
the run. This is why V2-9.4.6 deliberately left the 15m caller unwired.

The repair is proven falsifiable: with the pre-resolution attachment disabled,
`test_closing_snapshot_is_in_the_ledger_before_context_resolution` fails with
`closing_in_ledger_at_resolve_time = False`. With the repair, it passes.

## Implementation summary

| File | Change |
| --- | --- |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | New `_attach_closing_snapshot_to_ledger` helper, called from `_execute_close` immediately after the closing snapshot is persisted and before any context resolution. `_attach_context_and_gate_window` now passes `run_id` to `build_window_15m_context_evidence`. |
| `tests/test_v2_9_4_8_15m_close_ledger_ordering.py` | New fixture matrix (below). |

The helper mirrors the proven 4h pattern at `one_command_15m_factory.py:1500`:

- reads the snapshot's own `token_id`/`pair_id` and rejects a foreign target;
- updates the close step's ledger row scoped by `id`, `run_id`, `token_id`,
  `pair_id` and `step_status='RUNNING'`;
- commits, then **confirms by reading the ledger back** rather than trusting the
  UPDATE's rowcount;
- returns an honest report; `_execute_close` fails closed with the precise reason
  and does not proceed.

Precise, non-generic failure reasons: `CLOSING_SNAPSHOT_NOT_PERSISTED`,
`CLOSING_SNAPSHOT_TARGET_MISMATCH`, `CLOSING_SNAPSHOT_LEDGER_ATTACHMENT_FAILED`.

`tracking_lane` is deliberately **not** passed to the 15m resolver. Passing it
would resolve a `closing_clean_late_seconds` policy and silently widen 15m
closing lateness from 0s to the 4h 60s allowance. A fixture pins this:
`closing_evidence_allowance_seconds == 0` and
`closing_evidence_cutoff_at == window_end_at`. The V2-9.4.6 design made
`run_id` and `tracking_lane` independent optional parameters precisely so the
15m path could take ledger identity without taking the 4h allowance.

## Exact ordering, before and after

**Before**

1. collect pre-close context
2. persist closing snapshot (`_execute_snapshot`)
3. persist pre-close context
4. find opening snapshot, check duration
5. close memory window
6. **resolve shared context** ← ledger has no closing snapshot yet
7. E2Q audit, Lane K/E2Z pipeline
8. return → *caller* finally writes `snapshot_id` to the ledger

**After**

1. collect pre-close context
2. persist closing snapshot (`_execute_snapshot`)
3. **attach exact closing snapshot_id to the current-run ledger + verify run/token/pair identity**
4. persist pre-close context
5. find opening snapshot, check duration
6. close memory window
7. **resolve shared context using the exact ledger range** (`run_id` passed)
8. E2Q audit, Lane Q, Lane K/E2Z pipeline
9. finalize close step and memory window

The caller's later ledger writes are preserved and now re-assert the same value.

## Replay and idempotency behaviour

- **Attachment is idempotent.** Confirmation reads the ledger rather than the
  UPDATE rowcount, so re-running an already-attached close is a no-op and
  succeeds even when the step is no longer `RUNNING`. Fixture-proven: calling the
  helper twice more after a completed close leaves step, snapshot, window and
  ledger counts identical.
- **No duplicates.** `record_token_snapshot` dedupes on
  `(token_id, pair_id, captured_at)`; window close is idempotent on the existing
  window; `_capture_same_stream_5m_support` guards on an existing step key.
  Fixture-proven: zero duplicate snapshot, close step, window or memory rows.
- **A failure after attachment leaves an honest recoverable state.** The ledger
  row truthfully records the snapshot that was captured. Replay re-attaches the
  same `snapshot_id` and proceeds; it does not fail and does not fork identity.
- **Exact first failure attribution is kept.** Attachment failure returns the
  specific reason and `_execute_close` stops there, so a later generic blocker
  cannot mask it.

## Fixture and regression results

`tests/test_v2_9_4_8_15m_close_ledger_ordering.py` — **12 passed**.

| # | Fixture | Result |
| --- | --- | --- |
| 1 | Closing snapshot attached to the ledger before shared context resolution | proven by reading the ledger through the resolver's own connection at call time; falsifiable (fails without the repair) |
| 2 | Exact 15m ledger range includes the closing snapshot | `snapshot_end_id` == close snapshot, present in ledger |
| 3 | Predecessor captured exactly at `window_start_at` excluded | excluded |
| 4 | Future, unrelated-run, wrong-token, wrong-pair excluded | excluded |
| 5 | Valid close produces no false `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER` | no ledger blocker, `non_ledger_snapshot_ids == []`, no boundary mismatch |
| 6 | Wrong run/token/pair identity fails closed with a precise reason | `CLOSING_SNAPSHOT_TARGET_MISMATCH`, `CLOSING_SNAPSHOT_NOT_PERSISTED`, another run → `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER` |
| 7 | Replay-safe after post-attachment failure | idempotent; zero duplicate snapshot/close/window/memory |
| 8 | 15m deadline and zero-second closing lateness unchanged | allowance `0`, cutoff == `window_end_at` |
| 9 | 4h exact-boundary fixtures still pass | 15 passed |
| 10 | E2Q, Lane Q, Lane K/E2Z deltas | zero retrieval, paper-decision, BUY/SELL/HOLD, position, trade-event, paper-trade-audit and PnL rows |
| 11 | Fully evidenced negative outcome stays clean-eligible | V2-9.4.5 contract untouched; resolver writes nothing |
| 12 | Missing/stale/mismatched evidence still fails closed | fails closed, no downstream unlocks |

Regressions:

| Suite | Result |
| --- | --- |
| New V2-9.4.8 fixtures | 12 passed |
| V2-4 one-command 15m factory, V2-4.1 shared context, V2-9.4.6 4h exact boundary | 38 passed, **1 pre-existing failure (below)** |
| E2Q, Lane Q, Lane K/E2Z, E2Z clean memory, cadence/continuity, continuous runtime | 408 passed |
| Python compilation | `COMPILE_OK` |
| `git diff --check` | clean |
| Migration added | none — zero files under `migrations/` |
| Unrelated untracked artifacts | 161 baselined, unchanged |

### Pre-existing failure, confirmed against baseline and deferred

`test_v2_4_one_command_15m_factory.py::test_mismatched_safety_and_quotes_fail_closed_without_exact_evidence`
expects `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE` but receives
`CLOSING_EVIDENCE_TARGET_MISMATCH`.

**This is not caused by this lane.** Verified by stashing this lane's only
production change and re-running against clean `3bddcfd`: the failure is
byte-identical. It is stale-assertion drift from the V2-9.4.6 blocker rename —
that lane specifically replaced generic boundary blockers with precise ones and
did not run this test file. Production is more precise and correct; the
assertion is stale.

Per the risk-based verification policy (`AGENTS.md`, `ddbfdc7`): confirmed
against baseline, documented, and **deferred** rather than expanding this lane's
scope. It needs a one-line assertion update in a separate, explicitly-scoped
lane.

## Persistent DB hash verification

`data/printer_v1.sqlite3` SHA256 unchanged across the lane:

```
before: 97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
after : 97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
```

All fixtures used temporary isolated databases only.

## Money-usefulness contribution

The 15m window is the only memory Printer actually builds today. Until now it was
the one path that could not use ledger-exact identity: it selected evidence by id
range and wall clock with no authoritative check that the rows belonged to the
run that produced them. A predecessor, a neighbouring run's snapshot, or a
foreign row inside the id range could have entered a 15m window's evidence
silently — and a silently wrong memory is worse than a rejected one, because it
trains on a lie.

That hole is now closed on the path that produces real memory. No clean memory is
created by this lane; it makes the memory that is created provably the run's own.

## What the lane improves

- The 15m close can now use the exact current-run ledger without producing a
  false `SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER`.
- Snapshot identity on the 15m path comes from the authoritative ledger rather
  than an id range plus wall clock.
- Wrong-token, wrong-pair, wrong-run, predecessor and future snapshots are
  excluded from 15m windows, and each rejection has a precise reason.
- 15m and 4h now use the same identity discipline while keeping their distinct
  and correct lateness contracts.
- An attachment failure is attributed exactly, instead of surfacing later as a
  generic boundary blocker.

## What it still does not unlock

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`
and `WINDOW_24H` all remain locked. `WINDOW_5M_MICRO_EVENT` stays support-only.
Wash detection is untouched and remains blind for the reason recorded in the
V2-9.4.7 closeout: no adapter supplies wallet participation.

## Proof still required

Nothing here is proven against live data. The fixtures prove the ordering,
identity and replay contracts under controlled conditions with deterministic
adapters and compressed windows. A real bounded run is the only way to prove the
full path end to end, and it requires separate operator approval.

One honest limitation: the integration harness compresses the window to fractions
of a second, so the real resolver rejects it on the 900-second minimum span
before the ledger intersection is reached. The ordering proof therefore inspects
the ledger through the resolver's own connection at call time, and the
exact-range blocker proof runs at resolver level against a genuine 15-minute
window. Neither is a full-duration integration proof.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **No end-to-end 15m proof at real duration.** No fixture exercises the real
   resolver through a real 15-minute close, because the harness cannot span 900
   seconds. Ordering and exact-range are each proven, but their composition at
   real duration is not. This is the most likely place for a surprise.
2. **The ledger intersection trusts the ledger.** If any step fails to record its
   `snapshot_id`, its snapshot is excluded and the window fails closed. That is
   the correct direction, but it shifts a failure class onto ledger-write
   reliability. A missed intermediate snapshot now blocks a window that would
   previously have passed.
3. **A pre-existing V2-9.4.6 stale assertion is left red** (documented above). The
   nearest 15m close suite is not fully green, and I am deliberately not fixing it
   in this lane.
4. **V2-9.4.6 risk 1 is now resolved, but its cause remains instructive**: the 15m
   path was left unwired for three lanes because the ordering was wrong. Any
   future caller of the exact-ledger resolver must verify its own attachment
   ordering; nothing structurally enforces it.
5. **`continuous_first_hour` still re-writes the ledger after close.** That write
   is now redundant for `snapshot_id` but is preserved to avoid touching the
   continuation contract. Two writers of one field is a drift risk if either
   changes.
6. **The 4h blocker remains unidentified.** As recorded in V2-9.4.7, there is no
   known remaining reason a boundary-correct window would fail. The next failure
   will be found empirically, in an attempt.

## Attempt 7 was not launched

**Explicit statement:** Attempt 7 was **not** launched, authorised or unblocked
by this lane. No live source was called, no launcher or supervision code was
touched, no proof runtime was started, and the one-proof lock was never taken.

## V2-10 and operational memory growth remain blocked

**Explicit statement:** V2-10 and operational memory growth remain **blocked**
and were not begun. Retrieval, paper decisions and every financial capability
remain locked. Any of these requires separate, explicit operator approval.

## Files changed

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_9_4_8_15m_close_ledger_ordering.py` (new)
- `docs/printer-v1-v2-9-4-8-15m-close-ordering-closeout.md` (this file)

## Next recommended phase

Either the deferred one-line V2-9.4.6 stale-assertion cleanup (risk 3), or the
wallet-authenticity decision carried over from V2-9.4.7. Both need separate
operator approval, as do Attempt 7, V2-10, memory growth, retrieval and any
financial unlock. **Not started here.**
