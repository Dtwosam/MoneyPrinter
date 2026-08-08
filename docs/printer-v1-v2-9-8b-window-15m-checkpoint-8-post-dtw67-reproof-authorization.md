# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW67 One-Shot Re-proof Authorization

Date: 2026-08-08

Linear: `DTW-68`

Final readiness commit:

`7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575`

Approved immutable proof HEAD:

`7584b846fbe0fa79e8c9ce6fe35dfacbf7e07575`

Proof ID:

`C8_REPROOF_AFTER_DTW67_20260808`

## Operator authorization

The operator explicitly authorized:

> I authorize exactly one new bounded Checkpoint 8 controlling proof.

This authorization permits exactly one fresh controlling harness invocation against the immutable approved proof HEAD above.

The first actual controlling attempt consumes the authorization regardless of PASS or FAIL.

## Required proof envelope

- disposable proof DB only;
- fixture-backed transport only;
- process-local network tripwire enabled;
- zero external network attempts required;
- one controlling campaign only;
- REPORT_ONLY replay only after the controlling campaign sequence;
- repaired independent inspection only after a frozen campaign PASS;
- frozen artifact upload even on failure;
- no retry, rerun, resume, restart, successor, or second proof identity under this authorization.

Checkpoint 8 PASS requires both:

1. `campaign_pass=true` with `campaign_acceptance_verdict=CAMPAIGN_PASS`; and
2. independent inspection `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`.

## Preserved locks

No authoritative DB mutation, provider/network fallback, WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper trade audits, PnL, wallet/private-key/real-fund/live execution, paid API dependency, scoring/ranking/confidence/weighted logic, embeddings, or vectors are authorized.

## Stop condition

After the single controlling attempt and mandatory independent inspection/closeout, stop. A failure does not authorize a retry. A PASS does not by itself unlock downstream capability lanes.
