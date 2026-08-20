# Printer V1 V2-9.8B Cooperative Later-Cycle Repair Design

Date: 2026-08-20

Lane: `V2-9.8B Cooperative Later-Cycle Scheduling / 4-Token 2-Cycle Repair`

Baseline: `91535856be9e335ede15308c3b422b5e8a4e8bec`

## 1. Scope

Repair the proven 4/2/2 coordination defects without changing capacity, provider cadence, safety gates, or capability locks.

In scope:

- D4 `CYCLE2_PREMATURE_CAMPAIGN_SHUTDOWN`;
- D5 later-cycle acquisition under-service caused by stale lifecycle scheduling after a cooperative acquisition quantum;
- bounded offline proof of the repaired coordination law.

Out of scope:

- Cycle 3 / six-token activation;
- retrieval activation;
- BUY/SELL/HOLD, paper positions, trade events, paper audits or PnL;
- provider/source redundancy repairs such as GoPlus/Solana-native safety work;
- wallet/trading-flow completeness;
- capacity, cadence, retry, endpoint-rotation or rate-limit increases;
- authoritative/live provider campaign execution.

## 2. Proven root cause

The canonical factory selects `pending` lifecycle work before invoking the four-token admission boundary. A later-cycle callback may then run exactly one bounded acquisition quantum and return durable `RUNNING`.

The current callsite only re-enters the factory loop after admission or REARM. A nonterminal `RUNNING` attempt falls through and reuses the lifecycle selection made before the acquisition quantum.

Consequences:

1. if the old lifecycle selection is `None`, the factory can leave the active loop while later-cycle acquisition is still RUNNING (D4);
2. if the old lifecycle selection is a future snapshot, the factory sleeps toward that stale selection instead of immediately checking whether another bounded acquisition quantum still fits (D5).

The existing terminal validator is correct to reject one-cycle terminalization while a later-cycle attempt remains RUNNING. It must not be weakened.

## 3. Required coordination law

After every bounded later-cycle acquisition boundary, scheduling state must be re-evaluated before the factory may use an earlier lifecycle selection.

Two nonterminal RUNNING cases are lawful:

### A. Productive cooperative quantum completed

If the attempt remains RUNNING and there is no active temporal-refresh wait for that cycle, the just-completed bounded quantum yielded control. Re-enter the canonical loop immediately.

The next loop iteration recomputes lifecycle deadlines and invokes another acquisition quantum only if the existing deadline-conflict guard still permits it.

### B. Temporal refresh genuinely pending

If the attempt remains RUNNING and exactly one active temporal-refresh wait exists, do not busy-spin. Wake at the earliest of:

- the pending temporal-refresh `scheduled_for`;
- the freshly recomputed next lifecycle due time;
- the proof/campaign deadline.

Then re-enter the canonical loop and recompute authority/state.

Multiple/ambiguous active refresh waits remain fail-closed.

## 4. Architecture invariants

The repair must preserve all existing V1 laws:

- one Central Scheduler;
- one Source Governor;
- lifecycle-deadline work retains priority over ordinary discovery/acquisition;
- `_later_cycle_acquisition_deadline_conflict()` remains the admission-quantum protection gate;
- no background polling loop or new worker/thread is introduced;
- no SQLite write transaction is held across waits or provider I/O;
- no capacity increase beyond current 4 tokens / 2 cycles / 2 tokens per cycle;
- 300-second minimum cycle spacing remains unchanged;
- exact-pool `$3,000` liquidity floor remains unchanged;
- retries remain 0 and endpoint rotation remains false;
- 12h/24h remain locked and `WINDOW_5M_MICRO_EVENT` remains support-only;
- retrieval and financial capabilities remain locked.

The implementation should use generic `later-cycle` naming where practical so this coordination law can be reused when a future approved Cycle-3 lane generalizes ordinal reachability. This lane does not generalize or activate Cycle 3.

## 5. Minimal implementation

Modify only the canonical factory coordination surface unless proof demonstrates another necessary change.

1. Add a read-only helper that resolves an active later-cycle temporal-refresh wake from the existing persisted wait ownership rows.
2. Extend the internal `FourTokenAdmissionBoundaryResult` with an optional wake timestamp for a RUNNING attempt.
3. When the later-cycle callback returns RUNNING, resolve whether a temporal refresh is pending:
   - no active wait -> immediate coordinator re-evaluation;
   - one WAITING refresh -> expose its due timestamp;
   - ambiguous/claimed ownership -> fail closed.
4. In the main factory loop, handle RUNNING before any stale `pending is None` terminal path or stale lifecycle sleep:
   - immediate re-loop for a productive quantum;
   - bounded sleep to the earliest lawful wake for a genuine temporal wait, then re-loop.
5. Do not modify the terminal validator, lifecycle deadline guard, provider pacing, source budgets, or capacity policy.

## 6. Bounded proof requirements

Focused tests must prove:

1. RUNNING + no active refresh wait requires immediate re-evaluation.
2. RUNNING + active temporal refresh does not busy-spin and cannot cause premature terminalization.
3. A nearer lifecycle deadline wakes before the temporal refresh.
4. The proof deadline caps every wait.
5. Terminal/no-pair/blocked states do not re-enter the active acquisition loop.
6. The RUNNING re-evaluation occurs before the existing `pending is None` terminal branch.
7. Existing lifecycle deadline-conflict tests remain green.
8. Existing four-token admission/terminal semantics remain green.
9. No forbidden capability/configuration deltas are introduced.

No provider contact, authoritative DB mutation, authorization creation, or live Printer execution is permitted for this proof.

## 7. Closeout gate

Close GREEN only if the focused regression suite and directly affected existing tests pass and inspection confirms all locks above remain unchanged.

A GREEN closeout for this lane repairs D4/D5 only. GoPlus safety redundancy remains a separate blocker before another authoritative 4/2/2 campaign unless separately repaired and closed.