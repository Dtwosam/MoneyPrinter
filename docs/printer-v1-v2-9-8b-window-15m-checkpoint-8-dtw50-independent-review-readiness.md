# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-50 Independent Review and Readiness

Date: 2026-08-07

Linear: `DTW-50`

Audit HEAD: `6120370d8346337e7408695a4ec20e243b99c7ac`

Design HEAD: `1feff619726b496867306d3be52a46c8962d9e68`

Implementation commit: `6015e2c3084cf6b4ebbdf4097a71a369813f2087`

Closeout commit: `07b63fea587cab475817ebe9f0f7553eddcb85dc`

Independent verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW50_HOLDER_REQUEST_SCOPE_PROPAGATION_REPAIR_INDEPENDENT_REVIEW_PASS`

Readiness verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW50_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

## Independent inspection

The DTW-50 implementation commit over the approved design changes exactly four files:

1. `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
2. `src/printer_v1/operator_cli/one_command_15m_factory.py`
3. `src/printer_v1/operator_cli/safety_context_source_redundancy.py`
4. `tests/test_v2_9_8b_window_15m_checkpoint8_holder_request_scope.py`

The production repair is limited to request-key scope propagation for permanent holder evidence:

- `run_operational()` passes only the already-validated supply diagnostics `request_key_root` into the holder funnel;
- permanent holder mode fails closed if that root is missing;
- each permanent candidate uses deterministic `<root>-holder-<ordinal>-context`;
- `_collect_preclose_context()` accepts an optional explicit prefix and otherwise preserves the legacy `run_id:step_key:context` contract;
- the sole holder backup reuses the same explicit prefix as `<prefix>:holder_backup`, otherwise keeps the legacy backup key.

It does not change request counts, transport counts, holder budgets, stage ceilings, provider transports, Source Governor, Central Scheduler, six-unit accounting, reconciliation law, clean-memory law, campaign acceptance, retrieval, decisions, positions, trades, audits, or PnL.

The closeout is exactly one documentation file over the implementation tip. No second campaign scope is reconstructed and reconciliation is not widened.

## Offline proof reviewed

The committed closeout records:

- deterministic pre-repair RED: holder requests remained under legacy `run_id:holder_eligibility_N:context:*` outside the campaign root (`DTW50_HOLDER_REQUEST_OUTSIDE_CAMPAIGN_SCOPE_RED_CONFIRMED`);
- changed-file `py_compile`: PASS;
- dedicated DTW-50 regression: `3 passed`;
- existing C8 real-consumer compatibility: `9 passed`;
- complete focused C8 suite: `105 passed`;
- exact four-file implementation manifest: PASS;
- `git diff --check`: PASS;
- provider/network execution: NONE;
- controlling C8 proof: NONE.

Independent replay of the dedicated regression against the immutable implementation tree also passed (`3 passed`).

This is sufficient bounded offline evidence for DTW-50 repair closeout. No broad regression expansion is required for this narrow scope-propagation repair.

## Readiness decision

The known post-DTW49 reconciliation blocker addressed by DTW-50 is repaired and independently reviewed.

No remaining **known** blocker from that consumed attempt is established by the current reviewed evidence.

This does not guarantee that a future Checkpoint 8 attempt will pass. Any newly exposed blocker must be preserved as a new honest frozen result and handled through its own narrow audit/design/repair lane.

Checkpoint 8 / `DTW-34` remains open.

A future controlling C8 re-proof requires a new explicit operator authorization and a fresh documentation-only authorization commit over the reviewed lineage produced by this independent review.

## Locks preserved

No authorization is granted here for:

- another C8 proof attempt;
- operational `WINDOW_15M` memory growth;
- provider/network access;
- authoritative DB use;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet, private keys, real funds, or live execution.

`WINDOW_5M_MICRO_EVENT` remains support-only.
