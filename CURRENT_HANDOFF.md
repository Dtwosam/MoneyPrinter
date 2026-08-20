# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Fresh 4/2/2 Authorization Design`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_FRESH_4_2_2_AUTHORIZATION_DESIGN_PASS`

`AUTHORIZATION_CREATED: NO`

`PRINTER_EXECUTED: NO`

## Exact design / launch identities

Design branch:

`agent/v2-9-8b-fresh-4-2-2-authorization-design`

Design commit:

`564f3765697fb81ec61f20f959a6444d4c2282c9`

The design branch is **not** the launch checkout.

Authorized-source binding for any future authorization:

- launch source branch: `agent/v2-9-8b-pre-admission-terminal-cleanup-repair`
- exact launch HEAD: `9cfa8a152c3a02c0c5ef599cf0cffe6e269ab885`
- authoritative DB SHA-256: `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`
- migrations: 58; head `058_direct_pump_migration_cursor.sql`
- re-readiness prerequisite: `V2_9_8B_POST_ALL_SIX_REPAIRS_OPERATIONAL_REREADINESS_PASS`

Design artifact:

`docs/printer-v1-v2-9-8b-fresh-4-2-2-authorization-design.md`

## Frozen authorization shape

Use only the existing operational authority:

- command: `four-token-standard-four-hour-run`
- schema: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`
- policy: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- exactly 4 through-4h tokens / 2 cycles / 2 tokens per cycle
- Cycle 2 fresh/disjoint from Cycle 1
- minimum cycle spacing 300s
- `WINDOW_15M` root; lawful token-local `15m -> 1h -> 4h`
- pre-lifecycle acquisition 2,400s; post-supply lifecycle 18,000s
- governed/lifecycle request outer ceiling 476
- governed/lifecycle requests per token 118
- shared discovery requests 4
- Scheduler outer ceiling 420
- campaign storage-growth ceiling 67,108,864 bytes (64 MiB)
- automatic retries 0; endpoint rotation false
- 12h/24h locked
- one-shot only; no rerun/resume/restart/successor

The future authorization must use a new authorization ID and a fresh one-shot application/execution identity. Historical authorization/application identities are non-reusable.

## Mandatory pre-consumption posture

Before any future authorization is consumed, fail closed unless exact Git/DB/package/migration identity still matches, the launch tree is clean, integrity/FK are clean, there is zero active campaign/Scheduler/pre-admission/discovery/factory/refresh/lease residue, runtime dependencies pass, Source Governor/Central Scheduler remain the only owners, and all retrieval/financial locks remain intact.

Any drift blocks before consumption.

## Exact next permitted action

`V2-9.8B Fresh 4/2/2 Authorization Creation / Independent Application Preparation`

That action may prepare and independently validate exactly one new authorization/application package against the frozen launch HEAD and DB identity. It does **not** itself authorize a Printer campaign execution unless its own preparation/review passes and the operator proceeds to the separately gated one-shot execution.

Do **not** run Printer from this handoff.
Do **not** contact providers/RPC/WebSockets from this handoff.
Do **not** reuse any historical or consumed authorization/application artifact.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The active authority stack wins any conflict with this handoff.
