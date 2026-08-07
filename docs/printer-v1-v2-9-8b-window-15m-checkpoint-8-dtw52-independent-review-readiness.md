# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-52 Independent Review and Readiness

Date: 2026-08-07

Linear: `DTW-52`

Audit HEAD: `24e6e6e1e842c2fa4cfc4dfce66a2bf838302805`

Design HEAD: `f09a51283e8798541466190e0398d8e23bbd419c`

Implementation commit: `a5145dc5b62230d2289335f8244c217937b77c04`

Closeout commit: `4b3d2ac603710e5df88f9103fa6dd4cfb4f44fe2`

Independent verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW52_REPAIR_CLOSEOUT_INDEPENDENT_REVIEW_PASS`

Readiness verdict:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW52_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

## Independent inspection

The DTW-52 implementation over the approved design changes exactly two files:

1. `src/printer_v1/operator_cli/operational_memory_factory_command.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_terminal_campaign_run_identity.py`

The production repair is limited to projecting the already-authoritative campaign run identity `command.run_id` onto public terminal packaging surfaces that already emit `command.campaign_id` (success, terminal-failure, and pre-lifecycle packaging returns).

It does not change extractor conflict/cardinality law, does not use factory UUID as campaign run identity, does not alter runtime source/budget/holder law, and does not reopen DTW-50/51.

The closeout is exactly one documentation file over the implementation tip.

## Offline proof reviewed

- deterministic RED for missing campaign run identity packaging;
- changed-file `py_compile`: PASS;
- dedicated DTW-52 regression: `7 passed`;
- C8 real-consumer compatibility: `9 passed`;
- complete focused C8 suite: `117 passed`;
- exact two-file implementation manifest: PASS;
- `git diff --check`: PASS;
- provider/network execution: NONE;
- controlling C8 proof: NONE.

## Readiness decision

The known post-DTW51 packaging blocker addressed by DTW-52 is repaired and independently reviewed.

No remaining **known** packaging blocker from the consumed post-DTW50 identity-missing stop is established by the current reviewed evidence.

This does not guarantee that a future Checkpoint 8 attempt will pass. Any newly exposed blocker must be preserved as a new honest frozen result and handled through its own narrow audit/design/repair lane.

Checkpoint 8 / `DTW-34` remains open.

A future controlling C8 re-proof requires a new explicit operator authorization and a fresh documentation-only authorization commit over the reviewed lineage produced by this independent review.

## Locks preserved

No authorization is granted here for another C8 proof attempt, operational `WINDOW_15M` memory growth, provider/network access, authoritative DB use, `WINDOW_1H+`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, or live funds/execution.

`WINDOW_5M_MICRO_EVENT` remains support-only.
