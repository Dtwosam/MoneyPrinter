# Printer V1 V2-9.8B — Third Standard Four-Hour Safety Cutoff / Provenance Repair Implementation Closeout

## Verdict

`V2_9_8B_THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

The committed repair is complete and the required focused repository proof is GREEN.

## Authority and lineage

Use this closeout inside the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order, not the sole source of truth.

Lineage:

- repair-scope audit: `d1f57145ca719223502d6521cb4881532530e1b8`
- repair design: `19adeed4bf175331dd19bee31a1056bd396db80d`
- implementation plan: `214adee3afc34d6df15cbcf21bfbafa373d90b66`
- production repair: `0aef38c89320f9ca7a265bda5a8a5503a8c52484`
- test-harness placeholder correction: `8cc281a2d26aadaf4c3b31a0af4ba61e0b9281a3`

Implementation branch:

`agent/v2-9-8b-third-standard-4h-safety-cutoff-provenance-repair-implementation`

The third standard-four-hour authorization remains permanently consumed and non-reusable.

## Implemented repair

Production scope is limited to:

`src/printer_v1/operator_cli/campaign_authority_adapters.py`

The memory-window B.2 path now separates two exact concepts:

1. **Lifecycle deadline** — authoritative `WINDOW_1H.window_end_at`, still fixed at exact 15m close + 2700 seconds. The caller must still supply this exact value.
2. **Observed close-evidence cutoff** — `captured_at` of the exact `snapshot_end_id` already owned by that memory window.

The B.2 adapter therefore no longer classifies safety evidence created by the Scheduler-owned close operation a few seconds after the fixed lifecycle deadline as future evidence merely because the close itself required those seconds.

The repair does not introduce an arbitrary grace period and does not use a latest-row lookup. The cutoff is bound to the exact closing snapshot already owned by the exact memory window.

Fail-closed controls remain:

- exact caller lifecycle cutoff equality;
- exact token/pair/mint identity;
- exact closing-snapshot linkage;
- exact closing-snapshot token/pair identity;
- closing snapshot may not precede the fixed lifecycle deadline;
- exact safety-composite linkage;
- 1800-second freshness maximum;
- no evidence after the exact observed closing snapshot;
- source request/response correspondence;
- failure-source correspondence;
- source status/data quality/target status;
- existing composite safety acceptance policy.

No Scheduler, Source Governor, provider-call, request-budget, Scheduler-budget, schema, migration, authorization, 12h/24h, retrieval, decision, position, trade, audit, or PnL behavior was added or loosened.

## Focused proof

Operator executed the required repository proof locally at exact HEAD:

`8cc281a2d26aadaf4c3b31a0af4ba61e0b9281a3`

Commands:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_v2_9_8b_first_hour_safety_provenance_repair.py' -v
```

Results:

- new cutoff/provenance regression proof: `6 tests`, `OK`;
- prior first-hour safety/provenance proof: `5 tests`, `OK`;
- total focused proof: `11/11 GREEN`.

The six new tests prove:

- a real-shaped close with safety evidence after the fixed lifecycle deadline but before the exact observed closing snapshot is accepted;
- caller must still supply exact lifecycle deadline;
- evidence after exact closing snapshot is blocked;
- evidence older than 1800 seconds is blocked;
- wrong exact closing-snapshot identity is blocked;
- source-response/request mismatch is blocked.

The five prior tests confirm:

- exact fresh safety-composite binding;
- governed safety collection ordering before audit/4h barrier;
- fail-closed binding on identity mismatch;
- reservation-family/public ceiling invariants;
- first-hour safety request count and standard lifecycle budgets.

The initial six-test run failed before exercising production behavior because the new fixture defined 16 contribution columns but the SQL INSERT contained 15 placeholders. That was classified `TEST_HARNESS_DEFECT`; commit `8cc281a2...` changed only the placeholder count. The rerun then passed all six tests. Production code was not changed for that harness failure.

GitHub Actions remains independently unavailable because of an account billing lock, but that no longer blocks this closeout because the exact committed repository tests were executed successfully on the operator host at the exact implementation HEAD.

## Money-usefulness contribution

This repair removes a deterministic false 1h→4h safety block that could consume a scarce one-use standard-four-hour authorization after valid clean 15m and 1h learning. It improves the chance of collecting legitimate 4h learning evidence without making unsafe, stale, future, mismatched, or untraceable safety evidence easier to pass.

## What this repair improves

- separates lifecycle timing from observed close-evidence timing;
- preserves exact fixed 45-minute continuation semantics;
- preserves exact-snapshot provenance;
- preserves fail-closed B.2 safety authority;
- prevents recurrence of the third-attempt timestamp/provenance false block under the tested shape.

## What remains locked

This closeout does not unlock:

- another standard-four-hour attempt;
- a fresh authorization;
- 12h or 24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet/private keys/signing/real funds/live execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- A later operational attempt could still expose unrelated runtime blockers; this closeout proves only the repaired safety cutoff/provenance boundary.
- GitHub-hosted Actions remain unavailable due to the external billing lock; use operator-host focused verification where permitted and document that distinction.
- No authorization should be prepared until fresh operational rereadiness independently passes.
- No broad regression suite is required for this narrow repair closeout; the focused 11-test proof is the minimum sufficient risk-based verification.

## Next lane

The next permitted lane is:

`POST_THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_REPAIR_OPERATIONAL_REREADINESS_AUDIT`

Required sequence:

```text
repair-scope audit                         CLOSED PASS
-> design/specification                    CLOSED PASS
-> implementation                          COMPLETE
-> focused bounded offline proof           11/11 GREEN
-> implementation closeout                 CLOSED PASS here
-> fresh operational rereadiness           NEXT
-> fresh one-use authorization preparation only if rereadiness passes
-> independent authorization review
-> separately operator-started bounded standard-four-hour attempt
```

No step authorizes the next automatically.