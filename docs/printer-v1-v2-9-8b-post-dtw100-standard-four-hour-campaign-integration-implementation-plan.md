# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Campaign-Integration Implementation Plan

## Baseline

`0a8068a4e4bd26f9f36d1a2d4c5863ac514478f1`

## Approved implementation slices

### Slice A — policy and capacity foundation

TDD first:

- `WINDOW_1H -> WINDOW_4H` continues after hard gates with `learning_need=None`;
- no outcome/learning-need special authority;
- token/shared hard gates remain fail-closed;
- derive two-token FAST/FAST, FAST/NORMAL, NORMAL/NORMAL full-first-four-hour request/Scheduler ceilings from committed policies.

Owners:

- `src/printer_v1/scheduler/token_local_continuation.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` or a narrower existing budget owner if code inspection proves better.

### Slice B — atomic campaign 1h->4h handoff and Scheduler ownership

TDD first:

- exact two-slot `WINDOW_1H_CLOSED` predecessor set;
- exact campaign `WINDOW_4H` successors;
- token slots -> `WINDOW_4H_CONTINUING`;
- no duplicate/partial handoff;
- policy-derived mixed-lane counts;
- every long Scheduler job projected into `WINDOW_LIFECYCLE` campaign Scheduler ownership;
- both tokens can be planned; no one-continuer compressed-proof assumption.

Reuse campaign ownership and long-window planner primitives; do not create a second collector.

### Slice C — two-token collection ownership/fairness and 4h terminal reconciliation

TDD first:

- claim/success/failure campaign-work synchronization;
- lifecycle reservation accounting;
- token-local failure isolation;
- shared stop cleanup;
- exact 4h physical close through existing continuity/cadence/E2Q/Lane Q/E2Z;
- campaign 4h terminal state + token `WINDOW_4H_CLOSED`/failure mapping;
- zero active 4h work after terminal close;
- zero `WINDOW_12H` work.

## Hard boundaries

- `WINDOW_4H.enabled_for_real_collection` stays false.
- No source fetching or operational runtime.
- No fresh authorization/wrapper.
- No authoritative DB mutation.
- No 12h/24h.
- No retrieval/decisions/BUY/positions/trades/audits/PnL.
- No wallet/private keys/signing/real funds/live execution.
- No scoring/ranking/confidence/weighted logic/embeddings/vectors.

## Verification policy

Use focused slice tests plus directly affected regressions. Run the broader first-hour + long-window focused composition set only at the implementation/proof closeout or when a cross-cutting slice requires it.
