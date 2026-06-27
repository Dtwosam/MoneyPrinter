# Printer V1 Lane E2D -- First Bounded Real Cycle Decision Package

## 1. Purpose

Lane E2D is a decision gate only.

E2D determines whether Printer V1 is ready for a later separately approved first
bounded real source-governed 15m Memory Factory cycle.

Lane E2D does NOT authorize real execution, real source fetching, scheduler runtime,
memory creation, snapshot collection, retrieval activation, paper decisions, or any
live wallet logic.

E2D wraps the E2C-F operator review payload and applies a final automated decision gate.

---

## 2. Anchor

- Lane E2C-F commit: `9dc0ed8`
- Lane E2C-F tag: `printer-v1-post-lane10-lane-e2c-f-final-closeout`
- E2C is closed.

Lane E2D is anchored to the E2C-F tag above.

---

## 3. E2D Decision Gate

Lane E2D delivers:

- `src/printer_v1/operator_cli/e2d_decision.py`
- CLI command `printer-decide-first-bounded-15m-cycle`
- Tests in `tests/test_post_rc_lane_e2d_first_bounded_cycle_decision.py`
- This decision document

E2D outputs `GO_TO_OPERATOR_APPROVAL` or `BLOCKED`.

`GO_TO_OPERATOR_APPROVAL` means all automated gates have passed and the package is
ready for a human operator approval review only. It does NOT start real execution.

### 3.1 Decision gates

All of the following must pass for `GO_TO_OPERATOR_APPROVAL`:

1. E2C-F operator review returns `READY_FOR_OPERATOR_DECISION`
2. Token list is valid and all entries are operator-approved
3. No placeholder mints
4. DB backup is confirmed
5. DB exists and is accessible
6. Zero RUNNING scheduler jobs
7. Zero active scheduler locks (locked_at or lock_owner)
8. Source Governor budget allows requests
9. E2C-C readiness returns `LIMITED_GO_FOR_OPERATOR_REVIEW`
10. E2C-E fixture rehearsal returns `FIXTURE_REHEARSAL_PASS`
11. All 11 hard-lock flags are False
12. Persistent DB row counts are unchanged (no mutation)

If any gate fails, the output is `BLOCKED` with reasons listed.

### 3.2 Payload structure

```json
{
  "command": "printer-decide-first-bounded-15m-cycle",
  "dry_run": true,
  "decision_only": true,
  "e2d_status": "E2D_READY_FOR_OPERATOR_APPROVAL_REVIEW | E2D_DECISION_BLOCKED",
  "e2c_f_review": { "...full E2C-F operator review payload..." },
  "db_mutation_proof": { "...mutation proof from fixture rehearsal..." },
  "final_decision": "GO_TO_OPERATOR_APPROVAL | BLOCKED",
  "final_decision_reasons": ["..."],
  "hard_locks": { "...all 11 flags, all false..." },
  "next_required_operator_action": "..."
}
```

---

## 4. What E2D Does NOT Authorize

`GO_TO_OPERATOR_APPROVAL` and the E2D decision output do NOT authorize any of the
following:

- Real source fetching (any adapter call to any source)
- Scheduler runtime execution
- Snapshot collection (any row in `printer_token_snapshots` or `printer_context_snapshots`)
- Memory window building
- Memory creation (any row in `printer_memories`)
- Retrieval activation
- Paper decisions (WAIT, AVOID, NO_ACTION, BUY, SELL, HOLD)
- Paper positions, trade events, paper trade audits
- PnL calculation or reporting
- Wallet logic, private keys, signing, live trading, real funds
- Paid APIs
- Scoring, ranking, confidence percentages, weighted logic
- Embeddings or vectors
- Token recommendations or financial advice

---

## 5. All V1 Restrictions Remain Active After E2D

After E2D, all Printer V1 restrictions from `AGENTS.md` and
`docs/printer-v1-clean-master-spec.md` remain fully active:

- Solana only. No multi-chain.
- Paper trading only. No real wallet. No private keys. No live execution.
- Free/public data only. No paid APIs.
- Memory comparison only. No scoring system.
- No BUY, SELL, or HOLD until separately unlocked under approved conditions.

---

## 6. Next Lane Boundary After E2D

The next lane after E2D must be separately named and explicitly approved by the
operator before any bounded real source-governed 15m Memory Factory cycle can begin.

`GO_TO_OPERATOR_APPROVAL` from E2D is not authorization to begin execution. Before
any real bounded cycle the operator must:

1. Review the E2D payload and confirm `GO_TO_OPERATOR_APPROVAL`.
2. Explicitly name and approve a next lane (e.g., "Lane E2E" or a separately named lane).
3. The next lane must explicitly unlock source fetching or scheduler runtime in its
   own approved scope -- E2D does not do this.
4. The operator must supply a real, non-placeholder token list with all fields
   correctly populated and `approved_by_operator: true`.
5. A DB backup must be confirmed before any real execution lane.

No execution lane is activated by this document or by E2D's `GO_TO_OPERATOR_APPROVAL`.

---

## 7. E2D Hard Lock Summary

All 11 hard-lock flags remain False in E2D and in all E2D CLI output:

| Flag                          | E2D Value |
|-------------------------------|-----------|
| source_fetching_enabled       | false     |
| scheduler_execution_enabled   | false     |
| snapshot_creation_enabled     | false     |
| memory_creation_enabled       | false     |
| retrieval_activation_enabled  | false     |
| paper_decisions_enabled       | false     |
| buy_enabled                   | false     |
| sell_enabled                  | false     |
| hold_enabled                  | false     |
| positions_enabled             | false     |
| pnl_enabled                   | false     |

These flags are enforced by `HARD_LOCKS` in
`src/printer_v1/operator_cli/e2c_readiness.py` and re-exported in every E2D payload.

---

*Document status: E2D decision gate -- static planning, no code execution.*
*Anchor: Lane E2D decision package anchored to E2C-F tag `printer-v1-post-lane10-lane-e2c-f-final-closeout`.*
