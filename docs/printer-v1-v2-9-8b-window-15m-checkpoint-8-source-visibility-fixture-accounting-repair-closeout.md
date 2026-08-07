# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Source-Visibility Fixture Accounting Repair Closeout

Date: 2026-08-07

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_SOURCE_VISIBILITY_FIXTURE_ACCOUNTING_REPAIR_PASS`

Implementation commit: `496847f` — `Repair Checkpoint 8 PumpSwap fixture accounting`

## What changed

Only two non-production files changed in implementation:

- `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
- `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

The C8 PumpSwap fixture now uses the canonical measured-transport helpers to emit the production-shaped two-operation signature-resolution identity set (`getTransaction` + `getMultipleAccounts`). The synthetic migration epoch is now a fixed valid-past value rather than January 2027. A direct-migration regression now proves the exact canonical persistence/accounting boundary.

No production discovery, Source Governor, Central Scheduler, selection, lifecycle, memory, retrieval, decision, position, trade, audit, or PnL file changed.

## Verification

Actions run `31192161828` passed the approved offline gate before committing:

- `py_compile` — PASS
- real-consumer compatibility file — `4 passed`
- full focused Checkpoint 8 wildcard suite — `95 passed`
- `git diff --check` — PASS

The new regression proved, under the C8 network tripwire:

- zero network attempts;
- canonical direct-migration status `COMPLETE`;
- two confirmed candidates;
- five governed source requests;
- seven measured source transport operations;
- operation accounting reconciled;
- exactly two rows persisted to `printer_pumpswap_graduated_candidate_registry`;
- fixture migration timestamps satisfy the production future-time tolerance.

The first disposable repair runner attempt (`31191985920`) stopped before tests/commit only because its generated test file had one extra blank line at EOF. It produced no code commit and no Printer runtime/proof work. The corrected runner passed.

## Consumed controlling proof remains historical evidence

The earlier one-shot re-proof from run `31190804691` remains consumed and honestly blocked at `SOURCE_VISIBILITY_SHORTAGE`. It must not be reinterpreted as a pass or rerun under the same authorization.

Its independent-inspector `CURRENT_RUN_IDENTITY_MISSING` error remains a secondary runner-gating symptom: a future one-shot runner must invoke the independent success inspector only after the frozen summary itself proves `campaign_pass == true` and `campaign_acceptance_verdict == CAMPAIGN_PASS`.

## Money-usefulness contribution

The C8 proof fixture can now hand source-clean, exactly accounted graduated candidates into the same durable candidate registry used by the ordinary path. This removes a false zero-candidate condition that prevented the readiness proof from reaching the money-useful observation/memory path.

## What remains locked

This repair does not authorize another Checkpoint 8 proof. It does not unlock `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Proof required before Checkpoint 8 completion

One new explicitly authorized ordinary `WINDOW_15M` Checkpoint 8 controlling proof must still demonstrate the complete successful public-composition path and independent closeout. The next runner must gate the independent inspector on the frozen campaign PASS fields before invoking it.

## Functionality Risks / Setbacks / Efficiency Blockers

- Offline regression proves the repaired discovery-accounting seam, not complete Checkpoint 8 success.
- The next controlling attempt remains a one-shot proof and requires a new explicit operator authorization.
- Any newly exposed blocker must be audited rather than hidden behind reruns or fixture shortcuts.
