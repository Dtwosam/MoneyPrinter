# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-52 Terminal Campaign Run Identity Repair Design

Date: 2026-08-07

Linear: `DTW-52`

Audit commit: 24e6e6e1e842c2fa4cfc4dfce66a2bf838302805

Baseline HEAD: `479dfee0c06fb634caab0e510036b363e6641584`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Design decision

Project the already-authoritative campaign run identity `command.run_id` onto the
public terminal packaging surface assembled by
`operational_memory_factory_command.py`.

This is the minimum exact invariant: the same identity already used for campaign
graph ownership, cleanup, reconciliation, and durable report body identity.

## Why this owner

- The C8 extractor requires top-level or packaging-report `run_id`.
- `command.run_id` is the sole durable campaign-run authority for the public path.
- Factory UUID must never be used as a substitute.
- Reading nested durable report JSON from disk is unnecessary when the owner
  already holds the exact identity at terminal assembly.

## Required projection

Every public terminal packaging dict that already emits `campaign_id` from
`command.campaign_id` must also emit:

```text
"run_id": command.run_id
```

Covered surfaces in `operational_memory_factory_command.py`:

1. successful `OPERATIONAL_CAMPAIGN_TERMINAL` return;
2. terminal-failure packaging returns that already include `campaign_id`;
3. pre-lifecycle terminal packaging return that already includes `campaign_id`.

Optional complementary (only if needed for extractor parity and already in the
same packaging owner): include `run_id` on the `write_campaign_terminal_report`
return packaging surface. Prefer terminal top-level projection as primary.

## Explicit non-goals

- Do not change extractor conflict/cardinality fail-closed law.
- Do not accept factory `run_id` / UUID as campaign run identity.
- Do not invent run IDs from `execution_id` alone.
- Do not alter campaign runtime, source law, budgets, or DTW-50/51 repairs.
- Do not run a controlling C8 proof.

## Approved implementation surface

Production:

1. `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Optional tiny packaging helper only if it remains inside that file.

Proof:

2. `tests/test_v2_9_8b_window_15m_checkpoint8_terminal_campaign_run_identity.py`

No other production file may change unless audit proves the extractor itself
must read an already-projected packaging field without weakening law (default:
extractor unchanged).

## Deterministic RED

At design baseline, focused offline regression must prove:

1. a representative public terminal packaging shape with campaign_id but without
   campaign run_id causes
   `extract_checkpoint8_terminal_identity()` →
   `CHECKPOINT8_TERMINAL_IDENTITY_MISSING`;
2. factory UUID alone cannot satisfy campaign run identity;
3. report-only cannot lawfully start without the resolved campaign run ID.

Classification:

`DTW52_TERMINAL_CAMPAIGN_RUN_IDENTITY_MISSING_RED_CONFIRMED`

## GREEN acceptance

1. Success terminal packaging includes exact `campaign_id` + campaign `run_id`
   from command authority.
2. Extractor returns those exact identities.
3. Conflicting multi-valued campaign/run identities still fail closed.
4. Factory UUID does not substitute for campaign run ID.
5. Offline fixture path can invoke `report_only` from resolved identities and
   remains zero-work (or proves the identity handoff without network).
6. Offline fixture/unit path can complete frozen-summary packaging without a
   controlling C8 proof (or proves extractor+summary identity inputs).
7. `py_compile`, dedicated DTW-52, C8 real-consumer compatibility, full focused
   `checkpoint8_*.py`, exact manifest, `git diff --check`, zero network.

## Money-usefulness contribution

A true C8 runtime result must survive terminal identity extraction, zero-work
report replay, and frozen-summary creation so it can be independently accepted.

## What remains locked

No controlling C8 proof is authorized. Operational WINDOW_15M memory growth,
WINDOW_1H+, retrieval, decisions, trades, and PnL remain locked.

## Implementation readiness

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW52_READY_FOR_OFFLINE_IMPLEMENTATION`
