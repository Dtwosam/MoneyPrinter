# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Source-Visibility Repair Re-proof Authorization

Date: 2026-08-07

Readiness HEAD: `7191c1fe0f6616d3809452b779f7786ebffae69e`

## Operator authorization

The operator explicitly authorized exactly one new Checkpoint 8 re-proof attempt after the source-visibility fixture accounting repair.

Exact operator statement:

> I explicitly authorize one new Checkpoint 8 re-proof attempt after the source-visibility fixture accounting repair.

## Authorized scope

- exactly one ordinary `WINDOW_15M` Checkpoint 8 controlling re-proof;
- exact authorized Git HEAD is this authorization commit;
- deterministic offline fixture composition only;
- real Source Governor and Central Scheduler ownership;
- fresh disposable SQLite DB, artifact root, proof identity, and one-shot sentinel namespace;
- zero external-network/provider fallback;
- upload frozen evidence regardless of campaign outcome;
- invoke independent success inspection only if frozen summary proves `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`.

## Single-use law

This authorization is consumed when the one-shot proof runner starts. It does not permit retry, rerun, resume, restart, or successor execution. Any blocked or failed result must be preserved and audited before any later proof is considered.

## Locked capabilities

This authorization does not unlock `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet use, private keys, real funds, live execution, paid APIs, scoring/ranking/confidence/weights, or embeddings/vectors.

## Stop condition

After this authorization commit, perform the minimum pre-execution integrity check and exactly one controlling re-proof attempt. If it passes, perform independent read-only inspection and Checkpoint 8 closeout. If it blocks or fails, preserve evidence and stop without another proof attempt.