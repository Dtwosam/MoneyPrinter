# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Fresh Re-proof Authorization

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_FRESH_REPROOF_EXPLICITLY_AUTHORIZED_ONE_ATTEMPT`

The operator explicitly authorized one fresh Checkpoint 8 re-proof attempt after the completed offline repair on 2026-08-07.

Exact operator statement:

`I explicitly authorize one fresh Checkpoint 8 re-proof attempt after the offline repair.`

## Approved lineage

- readiness decision: `476c5de47fd32bb664a1cbb1b9486d86f7a54ca7`
- readiness verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_REPROOF_PROPOSAL_READY_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`
- repair closeout: `4fe933751f4af24fb7c3ca31e3c87b5053969a67`
- final GREEN repaired code state: `9feee2b102b31bb2ae095d3092956fee322036b4`
- historical consumed attempt: `C8_CONTROLLING_E263F5F3_20260807`
- historical result remains: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_CONTROLLING_PROOF_BLOCKED_NO_RERUN`

This authorization commit is the only approved execution HEAD for the fresh proof. Its full SHA must be resolved after commit creation and supplied exactly to the proof harness. The proof checkout must contain no later runtime or source-owner change.

## Fresh proof identity

`C8_REPROOF_AFTER_OFFLINE_REPAIR_20260807`

The fresh attempt must use:

- a fresh canonically migrated disposable SQLite DB;
- a fresh disposable artifact root;
- a fresh one-shot sentinel namespace tied only to this proof ID;
- the exact canonical 20-label deterministic fixture composition;
- the process-local external-network tripwire;
- zero provider fallback and zero external-network/provider attempts.

## Exactly-one-attempt law

This authorization permits exactly one ordinary `WINDOW_15M` proof attempt. It does not authorize a retry, rerun, resume, restart, successor, or reinterpretation of either the historical attempt or this fresh attempt.

The attempt must use exactly one public `run_operational_campaign()` call and exactly one `report_only()` replay. If the harness or independent inspection fails, the result is evidence and this authorization is consumed.

## Acceptance boundary

PASS still requires the existing Checkpoint 8 law, including:

- real Source Governor ownership;
- real Central Scheduler ownership;
- exactly two distinct current-run terminal `WINDOW_15M` windows;
- both terminal memories `CLEAN_MEMORY` with fingerprints;
- `CAMPAIGN_PASS`;
- cleanup complete, lease released, and zero active/orphan Scheduler/discovery residue;
- report-only replay with zero source calls, Scheduler runtime calls, and DB writes;
- frozen-summary/hash identity parity;
- independent read-only inspection PASS;
- zero protected downstream capability deltas;
- zero `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Still locked

This authorization does not unlock retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper-trade audits, PnL, wallets, private keys, real funds, live execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Stop condition

Run only the single authorized fresh proof. If the proof succeeds, run the independent read-only inspector once and then close Checkpoint 8 from frozen evidence. If either step fails, stop with the factual blocker and do not rerun.
