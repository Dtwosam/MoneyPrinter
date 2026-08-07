# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-49 Independent Review and Readiness

Date: 2026-08-07

Linear: `DTW-49`

Design V2 HEAD: `80e924c464e5c7304ee6124a097e166d4502edfd`

Implementation tip: `aed188ce14ca0584b3d09d315e1ee067475c5225`

Independent verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW49_REPAIR_CLOSEOUT_INDEPENDENT_REVIEW_PASS`

Readiness verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW49_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

## Independent inspection

The DTW-49 implementation range from the approved V2 design to the tested implementation tip changes exactly two files:

1. `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_holder_coverage_transport_identity.py`

The production repair is limited to holder coverage projection. It carries canonical per-request transport identity keys already present in the real normalized holder execution payload, keeps lawful zero-transport coverage explicit, and clears count/keys together when exact identity accounting fails.

It does not change request counts, transport counts, holder budgets, stage ceilings, provider transports, Source Governor, Central Scheduler, six-unit accounting, reconciliation law, clean-memory law, campaign acceptance, retrieval, decisions, positions, trades, audits, or PnL.

The pushed closeout is exactly one documentation file over the tested implementation tip.

## Offline proof reviewed

The committed closeout records:

- deterministic pre-repair RED on the missing holder transport-identity-key projection;
- changed-file `py_compile`: PASS;
- dedicated DTW-49 regression: `2 passed`;
- existing C8 real-consumer compatibility: `9 passed`;
- complete focused C8 suite: `102 passed`;
- exact two-file implementation manifest: PASS;
- `git diff --check`: PASS;
- provider/network execution: NONE;
- controlling C8 proof: NONE.

This is sufficient bounded offline evidence for DTW-49 repair closeout. No broad regression expansion is required for this narrow projection repair.

## Readiness decision

The known post-DTW48 reconciliation blocker addressed by DTW-49 is repaired and independently reviewed.

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
