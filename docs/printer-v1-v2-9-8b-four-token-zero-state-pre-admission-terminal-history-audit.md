# Printer V1 V2-9.8B Four-Token Zero-State Pre-Admission Terminal-History Audit

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_ZERO_STATE_PRE_ADMISSION_TERMINAL_HISTORY_AUDIT_BLOCKED_COMMITTED_CODE_DEFECT`

The post-repair rereadiness conclusion at `e149a5d95bc090cd711e7dc7abbe1f13fada7a53` is superseded for authorization readiness.

**NO FRESH FOUR-TOKEN AUTHORIZATION MAY BE CREATED YET.**

The canonical pre-consumption zero-state gate incorrectly counts every row in `printer_pre_admission_discovery_attempts`, including immutable retained terminal history. This contradicts the gate's own active-ownership semantics and makes a clean future four-token authorization fail after any retained pre-admission attempt.

## Baseline and boundary

- Repository: `Dtwosam/MoneyPrinter`
- Audit baseline: `e149a5d95bc090cd711e7dc7abbe1f13fada7a53`
- Source branch: `agent/v2-9-8b-four-token-post-repair-rereadiness-review`
- Repair branch: `agent/v2-9-8b-four-token-pre-admission-zero-state-repair`
- Classification: `COMMITTED_CODE_DEFECT`

This audit is static/read-only. It authorizes only a narrow design/implementation repair. It does not authorize Printer runtime, source fetching, discovery, database mutation, authorization creation/consumption, or proof execution.

## Evidence

### Canonical zero-state owner

`src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` uses active-state predicates for the other durable ownership domains but currently projects pre-admission ownership as:

```sql
SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts
```

The gate requires every projected domain count to equal zero. Therefore historical pre-admission evidence is treated as live ownership.

The same module already documents the correct general rule for supervision: zero-state means zero *active* ownership, not destruction of historical terminal evidence.

### Migration 055 state machine

`migrations/055_pre_admission_discovery_attempt_ownership.sql` constrains `attempt_state` to:

- `PLANNED`
- `RUNNING`
- `PAIR_READY`
- `NO_PAIR`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `CONSUMED`

Legal transitions are:

- `PLANNED -> RUNNING | CANCELLED | BLOCKED`
- `RUNNING -> PAIR_READY | NO_PAIR | BLOCKED | FAILED | CANCELLED`
- `PAIR_READY -> CONSUMED`

`FAILED`, `NO_PAIR`, `BLOCKED`, and `CANCELLED` have no transition back to active ownership. `CONSUMED` is terminal consumed evidence. `PAIR_READY` is terminalized discovery evidence but still carries an unconsumed exact pair and has the one remaining transition to `CONSUMED`; it must therefore remain blocking until consumed.

### Consumed-attempt forensic evidence

The retained real pre-admission row from the consumed proof is `FAILED`, has `first_terminal_cause = LATER_CYCLE_SUPPLY_FAILED`, and has `terminal_at` populated. Its linked Scheduler job 2010 is also `FAILED`, has `finished_at` populated, and has no lock owner or lock timestamp. The consumed-attempt cleanup evidence records zero active campaign/cycle/run/Scheduler ownership.

The retained row is therefore historical terminal evidence, not active Printer ownership.

## Causal chain

1. Cycle-2 pre-admission work legitimately created durable ownership evidence.
2. Later-cycle supply failed and the attempt terminalized to `FAILED`.
3. Its Scheduler job terminalized to `FAILED` and released its lock.
4. Active ownership returned to zero while historical evidence was intentionally retained.
5. The canonical zero-state gate raw-counts the retained row anyway.
6. A future authorization therefore fails before consumption despite no active pre-admission owner.

Deleting the row would destroy legitimate forensic history and conceal the defect. The owner query must be repaired instead.

## Required ownership semantics for design

The repair design must preserve this classification:

| Attempt state | Zero-state meaning |
|---|---|
| `PLANNED` | blocking ownership |
| `RUNNING` | blocking ownership |
| `PAIR_READY` | blocking unconsumed pair authority |
| `NO_PAIR` | retained terminal history; non-blocking |
| `BLOCKED` | retained terminal history; non-blocking |
| `FAILED` | retained terminal history; non-blocking |
| `CANCELLED` | retained terminal history; non-blocking |
| `CONSUMED` | retained consumed history; non-blocking |

Unexpected state values must fail closed rather than silently pass.

## Existing test gap

`tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` proves retained terminal campaign/proof supervision history does not block, but it has no equivalent pre-admission terminal-history coverage. That missing regression allowed the raw-count query to survive.

## Money-usefulness contribution

Repairing this blocker allows a future one-use four-token proof authorization to test actual concurrent Memory Factory capacity instead of being consumed or blocked by correctly retained historical bookkeeping. It preserves forensic evidence while reducing avoidable proof churn.

## What this audit improves

- Corrects the false authorization-ready conclusion from the prior rereadiness review.
- Binds the defect to the canonical zero-state owner rather than the database or Scheduler cleanup path.
- Defines the minimum state semantics the repair must preserve.

## What remains locked

This audit unlocks only the narrow repair design. It does not unlock a fresh four-token authorization or proof, six-token work, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, wallets, private keys, live execution, real funds, paid APIs, scoring/ranking/confidence logic, or embeddings/vectors.

## Proof required before repair closeout

Minimum sufficient repair proof:

- regression showing retained `FAILED` history no longer blocks and is not mutated;
- coverage for every migration-055 state;
- `PLANNED`, `RUNNING`, and `PAIR_READY` remain blocking;
- `NO_PAIR`, `BLOCKED`, `FAILED`, `CANCELLED`, and `CONSUMED` do not block;
- focused zero-state gate tests pass;
- nearest wrapper/pre-consumption contract remains intact;
- changed Python compiles and diff is clean.

No live/source-backed proof is authorized in this repair lane.

## Functionality Risks / Setbacks / Efficiency Blockers

- Misclassifying `PAIR_READY` as harmless history could permit a new proof while unconsumed pair authority still exists.
- A positive allowlist of blocking states could accidentally let an unexpected state pass; the implementation should remain fail closed.
- Expanding the repair into Scheduler, migration, discovery, or wrapper behavior would increase risk without addressing the proven defect.
- Historical rows must not be deleted, rewritten, or normalized as part of this repair.

## Next permitted phase

Design the narrow pre-admission zero-state semantics repair. Implementation is permitted only after that design is recorded. A fresh read-only rereadiness review is required after repair closeout before any new authorization is created.