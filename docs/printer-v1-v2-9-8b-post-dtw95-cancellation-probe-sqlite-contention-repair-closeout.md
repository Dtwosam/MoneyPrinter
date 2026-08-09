# Printer V1 V2-9.8B Post-DTW95 Cancellation-Probe SQLite Contention Repair Closeout

Date: 2026-08-09

Lane:
`V2-9.8B Post-DTW95 Cancellation-Probe SQLite Contention Repair`

## 1. Verdict

`V2_9_8B_POST_DTW95_CANCELLATION_PROBE_SQLITE_CONTENTION_REPAIR_CLOSEOUT_PASS`

The DTW95 operational `WINDOW_15M` attempt is permanently consumed and remains a blocked campaign, not a clean-memory proof.

The post-attempt audit established that the campaign entered the real two-token `WINDOW_15M` lifecycle and completed all scheduled snapshot steps through `snapshot_07` for both activated tokens. Both `WINDOW_CLOSE` steps were still pending and not yet due when the factory stopped.

The authoritative factory report preserved the hidden root cause:

`OperationalError: database is locked`

The timeline then established the exact contention boundary:

- the last snapshot completed before the first `WINDOW_CLOSE` due time;
- the first close was not due until after the terminal event;
- campaign heartbeat renewal succeeded at the terminal boundary and extended the lease;
- no heartbeat-failure row existed;
- the factory idle-wait path called the cancellation probe once per second;
- that probe used a read-only SQLite connection with `timeout=0.0`;
- a legitimate short heartbeat write therefore could make the probe raise immediately;
- the factory outer exception handler generalized that runtime SQLite lock into `SAFE_STOP_PREFLIGHT_FAILED`.

The approved repair is implemented and focused-proofed. No new authorization or operational campaign was run.

## 2. Controlling source stack

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order remains part of this source stack and is not the sole source of truth.

## 3. Exact lane chain

| Stage | Commit / evidence |
| --- | --- |
| DTW95 consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z` |
| Consumed-attempt closeout | `921fa3db10698f2d067e62744f508ff8bc811c7a` |
| Static/root-cause audit | `27e38a3e03e173a46dd07aac51762972b110308c` |
| Repair design | `5fe76ad91a04dc6a680988d5598ab1d07a9ca7f8` |
| RED test-only commit | `395bff66248f6b127775503fc43ff5f0b5a116b9` |
| Implementation | `d6d1de2b4e3708144cdfb7f0ab7eaf09d198df7d` |

Temporary PR #75 was used only as a disposable TDD review surface and was closed without merge.

## 4. Root cause

The defect was not lease expiry, holder admission, discovery, source failure, memory quality, or the `WINDOW_CLOSE` implementation itself.

`_sleep_with_cancellation()` checks the cancellation probe repeatedly during the intentional wait between lifecycle steps. The public command's cancellation probe opened the authoritative database read-only with a zero-second SQLite timeout. A legitimate concurrent heartbeat writer could therefore cause an immediate `OperationalError: database is locked` instead of waiting for the short operational writer to finish.

That uncaught exception escaped the lifecycle wait boundary and was generalized by the factory as `SAFE_STOP_PREFLIGHT_FAILED`.

## 5. Implemented repair

The implementation is deliberately narrow:

1. the generic `_read_only()` helper keeps its historical default `timeout_seconds=0.0`;
2. one dedicated supervision-cancellation reader now accepts a bounded timeout;
3. that reader uses the existing operational SQLite contention budget through `DEFAULT_OPERATIONAL_BUSY_TIMEOUT_MS`;
4. the cancellation probe uses a 2.0-second bounded wait for this supervision-state read only;
5. short legitimate writer contention is tolerated;
6. persistent `busy` / `locked` contention becomes the explicit cooperative terminal cause `CANCELLATION_PROBE_SQLITE_LOCKED`;
7. non-lock SQLite operational errors still propagate rather than being hidden.

No lease duration, heartbeat cadence, source behavior, Scheduler ownership, selection behavior, holder semantics, memory quality law, or downstream capability was weakened.

## 6. Focused proof

Local TDD proof returned:

- RED head: `395bff66248f6b127775503fc43ff5f0b5a116b9`;
- RED verdict: `EXPECTED_RED_MISSING_CANCELLATION_PROBE_HELPER`;
- focused GREEN: PASS;
- Python compile: PASS;
- Git diff check: PASS;
- production implementation commit changes exactly `src/printer_v1/operator_cli/operational_memory_factory_command.py`;
- design-to-implementation range contains only that production file plus `tests/test_post_dtw95_cancellation_probe_sqlite_contention.py`;
- bounded busy wait: 2.0 seconds;
- persistent contention cause: `CANCELLATION_PROBE_SQLITE_LOCKED`;
- authoritative database accessed: false;
- Printer source calls: 0;
- Scheduler runtime calls: 0;
- authorization created: false;
- `WINDOW_15M` started: false.

Verdict from the focused proof:

`V2_9_8B_POST_DTW95_CANCELLATION_PROBE_SQLITE_REPAIR_FOCUSED_PROOF_PASS`

## 7. Money-usefulness contribution

This repair prevents a healthy paper-only collection campaign from being discarded solely because a read-only cancellation check happened to collide with Printer's own legitimate short heartbeat write.

That improves the chance that an authorized 15-minute observation reaches its actual window-close and memory-quality boundary, while retaining fail-closed behavior for persistent database contention.

It creates no market signal, trading decision, position, trade, or profit claim.

## 8. What improved

- transient heartbeat/read-probe contention is no longer an immediate false campaign-wide preflight failure;
- cancellation-state reads now share Printer's existing bounded operational SQLite tolerance;
- prolonged contention has an exact terminal cause instead of generic `SAFE_STOP_PREFLIGHT_FAILED`;
- the existing heartbeat and lease safety model remains unchanged;
- the DTW95 root cause is independently distinguishable from memory-quality and lifecycle-close failures.

## 9. What remains locked

This closeout does **not** authorize another live attempt.

Still locked:

- fresh authoritative rereadiness must pass first;
- fresh one-use authorization preparation and independent review must occur separately;
- the consumed `V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z` may never be reused;
- no `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- no retrieval;
- no paper BUY/SELL/HOLD decisions;
- no paper positions, trade events, paper trade audits, or PnL;
- no wallet, private key, real funds, or live execution;
- no paid API dependency, scoring/ranking/confidence/weighted decision system, embeddings, or vectors.

Printer remains Solana-only, Solana memecoin-only, and paper-only.

## 10. Proof required before completion of the next readiness step

The next lane is a **read-only post-repair rereadiness audit** against the authoritative repository and database state after DTW95.

Minimum sufficient checks:

- exact repaired Git HEAD;
- migration ledger count/head/digest unchanged and valid;
- `PRAGMA integrity_check` clean;
- zero FK violations;
- no SQLite sidecars;
- zero active campaign / supervision / Scheduler / discovery / factory-step residue;
- source contract READY with zero external requests;
- concrete composition READY;
- dependency status READY;
- holder budget READY;
- historical paper-audit row preservation;
- zero database writes, source calls, Scheduler runtime calls, authorization creation, or `WINDOW_15M` runtime during the audit.

Only a PASS may advance to a separate fresh authorization lane.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Control |
| --- | --- |
| Bounded read wait hides a real prolonged DB fault | Persistent contention returns explicit `CANCELLATION_PROBE_SQLITE_LOCKED` and remains fail-closed |
| Global read semantics accidentally change | `_read_only()` default remains zero timeout; only the cancellation-state path opts into 2 seconds |
| Lease safety is weakened | Lease duration and heartbeat cadence are unchanged |
| Runtime retries are introduced | No source, Scheduler, lifecycle, campaign, or authorization retry was added |
| A future lock is incorrectly attributed to heartbeat | Terminal evidence must retain exact runtime cause; no assumption that all SQLite locks share this mechanism |
| Another scarce authorization is consumed before readiness | Fresh authorization remains blocked until post-repair rereadiness PASS |
| Previous failed attempt is reused | DTW95 authorization is permanently historical/non-reusable |

## 12. Next lane

`V2-9.8B Post-DTW95 Cancellation-Probe SQLite Repair — Authoritative Rereadiness Audit`

Type: read-only audit/readiness only.

No new authorization or runtime is permitted in that lane.
