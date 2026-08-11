# Printer V1 V2-9.8B — Third Standard Four-Hour Safety Cutoff / Provenance Repair Implementation Plan

**Goal:** Make B.2 distinguish the fixed WINDOW_1H lifecycle deadline from the exact observed closing-snapshot evidence cutoff without weakening freshness, provenance, identity, or safety gates.

**Architecture:** Keep `window_end_at` unchanged as the 15m-close + 2700s lifecycle boundary. In the memory-window B.2 adapter only, validate the caller against that lifecycle boundary, load the exact `snapshot_end_id`, and use that snapshot's `captured_at` as the evidence cutoff. Checkpoint B.2 behavior and all producer/Scheduler/budget owners remain unchanged.

## Global constraints

- Solana-only, paper-only V1 restrictions remain unchanged.
- No Source Governor or Central Scheduler bypass.
- No request/Scheduler budget changes.
- No grace period or latest-row fallback.
- No authorization, provider call, runtime, authoritative DB mutation, or live proof in this implementation lane.

## Task 1 — Focused RED proof

Create `tests/test_v2_9_8b_third_standard_four_hour_safety_cutoff_provenance_repair.py` with a minimal SQLite fixture that exercises the real `load_authoritative_window_safety()` behavior.

Required cases:

1. fixed lifecycle deadline `T`, exact closing snapshot `T+5s`, safety composite/trace at `T+4s` => B.2 accepts when all other safety facts are acceptable;
2. caller cutoff different from `window_end_at` => `CampaignAuthorityAdapterError`;
3. safety evidence/trace after exact closing snapshot => fail closed;
4. stale >1800s evidence => fail closed;
5. wrong closing-snapshot token/pair identity => fail closed;
6. source request/response mismatch => fail closed.

Run the focused test before production edits and record the expected failure of case 1 under the current fixed-cutoff implementation.

## Task 2 — Minimal production repair

Modify only `src/printer_v1/operator_cli/campaign_authority_adapters.py`:

- when `memory_window_close_cutoff` is supplied, keep exact equality validation against `window_end_at`;
- load `printer_token_snapshots.id == snapshot_end_id`;
- validate token/pair identity and parse `captured_at`;
- fail closed if observed close precedes lifecycle deadline;
- use observed close `captured_at` as `cutoff_value` for composite and trace age checks;
- report both `lifecycle_deadline` and `evidence_cutoff`, with `evidence_cutoff_source = EXACT_CLOSING_SNAPSHOT`;
- leave checkpoint safety logic unchanged.

## Task 3 — Focused GREEN proof and closeout

Run the new focused test plus the directly adjacent first-hour safety/provenance repair test. Do not widen to a broad suite unless these focused checks expose coupling.

If GREEN, write the implementation closeout documenting exact HEAD, tests, preserved locks, money-usefulness, what remains locked, and the next lane: fresh operational rereadiness audit. No new authorization or live attempt.