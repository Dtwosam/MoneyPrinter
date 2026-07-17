# Printer V1 V2-9.4.9 Integrated Readiness Proof Closeout

## Verdict

`V2_9_4_9_INTEGRATED_READINESS_PASS`

The V2-9.4.3 through V2-9.4.8.1 repairs compose correctly. A fully evidenced 15m
close now reaches `clean_memory_context_ready = True` with **zero blockers**
through the real shared-context resolver, with the exact-ledger intersection
active, the 15m zero-second lateness contract intact, flow honestly partial, and
every retrieval and financial delta at zero. No production defect was found. No
production code was changed by this lane.

Starting commit: `d2b328c`. Preflight passed — HEAD exactly `d2b328c`, tracked
tree clean, no proof runtime, no one-proof lock, persistent DB hash recorded,
161 unrelated untracked artifacts baselined and untouched.

## Method

Static inspection first, to avoid duplicating proven coverage. Each required
contract was mapped to the existing fixture that already proves it; only
existing focused tests were run. Exactly **one** small integration fixture was
added, for the single gap static inspection actually found.

## Composition map — what already proved what

| Required composition | Proven by | Status |
| --- | --- | --- |
| Launcher logging / supervision repair | `test_v2_9_4_3_launcher_log_reliability.py`, `test_v2_9_4_2_launcher_bootstrap.py`, `test_v2_9_4_1_heartbeat_close_boundary.py`, `test_v2_9_4_durable_supervision.py` | existing |
| 15m closing snapshot attached before context resolution | `test_v2_9_4_8_15m_close_ledger_ordering.py` (ordering spy, proven falsifiable) | existing |
| Valid 15m → 1h → 4h continuity | `test_v2_7_2_long_window_chained_continuity.py`, `test_v2_8_1_one_token_4h_runtime.py` | existing |
| Exact 4h opening and closing boundaries | `test_v2_9_4_6_exact_closing_boundary.py` | existing |
| 15m lateness remains 0 seconds | `test_v2_9_4_8` (`test_15m_allowance_stays_zero_without_tracking_lane`) | existing |
| 4h closing allowance remains 60 seconds | `test_v2_9_4_6` (`test_logical_deadline_preserved_and_cutoff_is_separate`) | existing |
| Fully evidenced negative outcomes can be CLEAN_MEMORY | `test_v2_9_4_5_outcome_evidence_separation.py`, `test_v2_9_4_7_trading_flow_memory_contract.py` | existing |
| Incomplete / mismatched evidence still fails closed | `test_v2_9_4_6`, `test_v2_9_4_8`, `test_v2_4_one_command_15m_factory.py` | existing |
| Flow PARTIAL/CAUTION does not automatically block clean memory | `test_v2_9_4_7_trading_flow_memory_contract.py` (unit level) | existing |
| Replay creates no duplicate snapshots, windows or memories | `test_v2_9_4_8` (`test_attachment_is_idempotent_and_creates_no_duplicates`) | existing |
| Retrieval and all financial deltas remain zero | `forbidden_deltas` in `test_v2_4_one_command_15m_factory.py`; explicit checks in `test_v2_9_4_6/7/8` | existing |
| Persistent DB remains unchanged | hash comparison, this lane | verified |

## The one real gap, and why it was real

V2-9.4.8 recorded as its risk 1 that the 15m ordering repair and the exact-range
resolver were each proven, but **their composition was not**, because the
harness compresses windows to fractions of a second and the resolver rejects
anything under its 900-second minimum span.

Static inspection showed that gap is narrower than V2-9.4.8 assumed. Three
existing V2-4 tests already patch `printer_v1.context_evidence.window_15m.
WINDOW_SECONDS` to `0`, which runs the **real** resolver end-to-end against the
compressed harness. The nearest of them,
`test_governed_close_context_reaches_exact_target_and_side_aware_flow`, already
asserts every section reaches `READY` — and since a false
`SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER` would propagate through `snapshot_blockers`
into the flow section, its passing already disproves the false-blocker case.

What no existing fixture asserted is the **integrated question itself**: that the
repairs compose into a window that can still be *clean*, rather than one that is
merely free of the specific blocker each lane removed. That fact was true but
unpinned. Measured on the composed path:

```
clean_memory_context_ready = True        blockers                = []
ledger_attachment.attached = True        non_ledger_snapshot_ids = []
closing_evidence_allowance = 0           cutoff == window_end_at = True
trading_flow_payload_quality_label = TRADING_FLOW_CONTEXT_PARTIAL
flow_memory_gate_label             = FLOW_CONTEXT_CAUTION
forbidden_deltas = all zero              running_jobs_after_stop = 0
```

This single line is the readiness result: **flow is honestly partial and the
window is still clean**, with ledger-exact identity active and 15m lateness still
zero. Four lanes' contracts hold simultaneously on one real path.

## The one added fixture

`tests/test_v2_9_4_9_integrated_readiness.py` — **1 test, 1 passed.**

`test_repairs_compose_into_a_clean_capable_15m_close` drives the real 15m factory
with clean context adapters and the established `WINDOW_SECONDS` patch, then
pins, on one path: V2-9.4.8 ledger attachment and exact `snapshot_end_id`;
V2-9.4.6 absence of both false boundary blockers; the 15m 0-second lateness
contract; V2-9.4.7 flow `PARTIAL`/`CAUTION` still supporting clean memory;
`clean_memory_context_ready` with zero blockers; and zero forbidden deltas,
zero downstream unlocks, no resolver writes, and a clean stop.

It reuses the V2-4 harness by reference rather than subclassing, so the V2-4
tests are not re-collected. It is one test in one file. No new framework, no
production change.

**Proven falsifiable.** With the V2-9.4.8 pre-resolution ledger attachment
temporarily disabled, the fixture fails exactly where it should:
`non_ledger_snapshot_ids` becomes `[16]` — the closing snapshot — instead of `[]`.
The repair was restored immediately and the tracked tree returned to clean.

## Results

| Suite | Result |
| --- | --- |
| Launcher log reliability, bootstrap, heartbeat close boundary, durable supervision, outcome/evidence separation, flow memory contract | 61 passed, 31 subtests |
| Chained continuity, 4h runtime, exact 4h closing boundary, 15m close ledger ordering, shared context evidence, one-command 15m factory | 65 passed, 64 subtests |
| New integrated readiness fixture | 1 passed |
| Python compilation | `COMPILE_OK` |
| `git diff --check` | clean |
| Production files changed | **none** — 0 tracked dirty |
| Migration added | none — zero files under `migrations/` |
| Unrelated untracked artifacts | 161, unchanged |

**127 existing tests and 95 subtests pass across every contract this lane was
asked to compose**, with no full-suite run, no live sources and no discovery.

## Persistent DB verification

```
before: 97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
after : 97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB
```

Unchanged. All fixtures used temporary isolated databases only.

## Money-usefulness contribution

Four consecutive repair lanes each removed a blocker in isolation. That is
exactly the pattern that produces a system where every lane is green and the
machine still cannot build memory — because the lanes compose into a window that
is blocker-free but never clean. This lane asked the only question that matters
before spending another four hours of real market time: *can these repairs, run
together on one real path, still produce clean memory?* They can, and that fact
is now pinned by a falsifiable test rather than inferred from six closeouts.

It also retires V2-9.4.8's risk 1 at low cost, without the large integration
framework that risk implied was necessary.

## What this lane improves

- The integrated outcome — clean memory is reachable — is now asserted, not assumed.
- V2-9.4.6, V2-9.4.7 and V2-9.4.8's contracts are pinned *simultaneously on one path*, so a future change cannot satisfy each in isolation while breaking their composition.
- V2-9.4.8 risk 1 is closed, and the belief that it required a full-duration harness is corrected: the `WINDOW_SECONDS` technique already existed in this suite.

## What remains locked

Retrieval activation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper trade audits, PnL, live execution, wallets, private keys, paid APIs,
scoring, ranking, confidence, weighted logic, embeddings, vectors, `WINDOW_12H`
and `WINDOW_24H` remain locked. `WINDOW_5M_MICRO_EVENT` stays support-only.
V2-10 and operational memory growth were not begun.

## Proof still required

This is a readiness proof, not a live proof. Everything here runs on deterministic
fixture adapters against temporary databases, with compressed windows and a
patched minimum span. It establishes that the repairs compose; it does not
establish that they survive real sources, real cadence, real latency or four real
hours. **Only Attempt 7 can prove that, and it requires separate explicit
operator approval.**

## Functionality Risks / Setbacks / Efficiency Blockers

1. **`WINDOW_SECONDS = 0` is not the same as a real 15-minute window.** The
   patch disables the minimum-span check so the real resolver will accept a
   sub-second window. Everything downstream of that check is genuinely exercised,
   but duration-dependent behaviour — cadence drift, staleness, real freshness
   windows — is not. A full-duration composition proof still does not exist.
2. **The composed proof is 15m only.** The 4h path's boundary and allowance
   contracts are proven by their own fixtures, but no test composes a real
   15m → 1h → 4h chain through the real resolver end to end. The 4h leg's
   composition remains inferred from its parts.
3. **Clean here means clean *context*, not a promoted clean memory row.** The
   fixture asserts `clean_memory_context_ready`; it does not assert that E2Z
   created a `CLEAN_MEMORY` episode. Promotion has further gates that this lane
   deliberately did not exercise.
4. **The proof depends on fixture adapters being representative.** The clean
   context factories supply ideal goplus/jupiter/coingecko payloads. Real sources
   fail, conflict and arrive late; V2-9 Attempt 4 was blocked by exactly that.
   Green here does not predict source availability.
5. **Wash detection remains blind** (V2-9.4.7 risk 1). This lane's headline
   result — partial flow still yields clean memory — is correct per the
   specification and is precisely why clean memory is reachable. It also means
   the composed clean path has had no wallet-level authenticity check available
   to it. That trade-off is now load-bearing for Attempt 7.
6. **No known blocker remains for a 4h window.** As recorded in V2-9.4.7, that
   means the next failure will be discovered empirically in an attempt rather
   than predicted here.

## Attempt 7

**Explicit statement:** Attempt 7 was **not** launched and is **not** authorised
by this lane. No live source or discovery was run, no launcher or supervision code
was touched, no proof runtime was started, and the one-proof lock was never taken.
This closeout is a readiness input for an operator decision, not that decision.

## Files changed

- `tests/test_v2_9_4_9_integrated_readiness.py` (new)
- `docs/printer-v1-v2-9-4-9-integrated-readiness-proof-closeout.md` (this file)

No production file was modified.

## Next recommended phase

An operator decision on Attempt 7, informed by risks 4 and 5: source
availability is the historical failure mode (Attempt 4), and the composed clean
path currently has no wallet-level authenticity check. Alternatively, close risk 5
first via the wallet-authenticity lane carried over from V2-9.4.7. Both require
separate operator approval, as do V2-10, memory growth, retrieval and any
financial unlock. **Not started here.**
