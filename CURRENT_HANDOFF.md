# CURRENT HANDOFF

Date: 2026-08-20

## Current lane

`V2-9.8B Solana-Native Core Safety Redundancy Repair`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_SOLANA_NATIVE_CORE_SAFETY_REDUNDANCY_REPAIR_CLOSEOUT_GREEN`

The bounded GoPlus single-point-dependency repair is implemented and offline-proved. Core chain-provable safety facts now have an approved Source-Governed Solana RPC path while GoPlus remains complementary. Conflicts and missing required facts remain fail-closed.

This handoff does **not** authorize a new 4/2/2 campaign.

## Exact branch / evidence anchors

Branch:

`agent/v2-9-8b-safety-core-redundancy-repair`

Accepted D4/D5 base:

`3f982ce97f30d99fabc384bfbf790b02b2049bdf`

Clean committed-state proof anchor:

`3d9388fa7cb382450e026de0f2dc2d0d3140429f`

Post-proof cleanup anchor:

`7abca8cfa24638b6f9272818b2c2645bdbae2491`

Safety closeout commit:

`854f5c384fafe6197d3a29a0f03133b83e11ce1c`

Closeout document:

`docs/printer-v1-v2-9-8b-solana-native-core-safety-redundancy-repair-closeout.md`

## What landed

Product scope:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/safety/composite.py`
- `src/printer_v1/safety/goplus_normalizer.py`
- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/sources/solana_rpc_token_safety.py`

Key behavior:

- one additional Source-Governed Solana mint-account safety request inside the existing lifecycle safety collection;
- chain-provable mint authority, freeze authority, supply sanity, and Token / Token-2022 identity can remain usable when GoPlus is unavailable;
- usable source disagreement becomes explicit conflict + `UNKNOWN` and remains blocked;
- `METADATA_UNKNOWN` is optional 15m source coverage, while explicit mutable metadata remains blocking;
- holder unknown/conflict remains descriptive under the existing E.48 separation law;
- lifecycle request ceilings account for the one additional request per token; Scheduler ceilings are unchanged;
- no new Scheduler job, provider loop, cadence increase, migration, paid API, or capacity mechanism.

The final read-only committed-state proof passed the new safety contract, composite/holder regressions, first-hour/timeframe safety regressions, relevant lifecycle accounting regressions, D4/D5 coordinator regression, Python compilation, and `git diff --check`.

Temporary proof workflow/helpers were removed after proof.

## Known baseline debt kept separate

The safety repair did not change unrelated accepted-base fixture drift:

- an older V2-8.1 WINDOW_4H test still asserts real collection disabled although the accepted cadence policy already enables it only through standard-four-hour authority;
- selected legacy V2-9.2 / V2-9.3 final-report fixtures omit required launch Git provenance even though accepted-base `_final_report()` already validates it.

These items require their own evidence-based treatment if they remain relevant to later readiness; they are not classified as safety-repair regressions.

## Authorization posture

`NOT READY FOR NEW 4/2/2 AUTHORIZATION`

The previous GoPlus / Solana-native core-safety blocker is closed by this repair, but operational authorization remains blocked pending post-repair re-readiness, including fresh authoritative repository/database identity checks and any other current readiness blockers established there.

All prior authorizations remain non-reusable.

## Exact next permitted action

`V2-9.8B Post-Safety-Repair Operational Re-Readiness Audit`

This next action is read-only/offline first. It must reconcile the closed D4/D5 repair and closed core-safety redundancy repair against the current authoritative repository/database state before any fresh 4/2/2 authorization can be considered.

Do **not** create a new authorization from this handoff.
Do **not** run Printer from this handoff.
Do **not** reuse any consumed authorization or historical application artifact.

## Locks

Solana-only; Solana memecoin-only; paper-only. No live wallet/private keys/signing/real funds/live execution. No paid API dependency. No scoring/ranking/confidence/weighted logic. No embeddings/vectors. No Source Governor or Central Scheduler bypass. No dirty-memory retrieval/decision use. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. 12h/24h remain locked. No Migration 059.

The 4/2/2 contract remains: 4 total tokens; 2 cycles; 2 tokens per cycle; Cycle 2 fresh/disjoint from Cycle 1; freeze minimum depth 4; exact-pool liquidity floor `$3,000`; minimum spacing `300s`; `WINDOW_15M` root; lawful token-local `15m -> 1h -> 4h`; retries `0`; endpoint rotation `false`; one-shot only; no rerun/resume/restart/successor.

The active authority stack wins any conflict with this handoff.
