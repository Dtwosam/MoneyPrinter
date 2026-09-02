# CURRENT_HANDOFF — Printer V1

## Current lane

`POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE`

The later-cycle cooperative mint-market-batch duplicate transport identity
repair is closed PASS on the authoritative host-local lineage.

This handoff does **not** authorize another campaign, another authorization,
application, or execution. Do not enter the readiness lane automatically.

## Latest completed work

Later-cycle duplicate-transport authoritative repair:

`V2_9_8B_LATER_CYCLE_DUPLICATE_TRANSPORT_AUTHORITATIVE_REPAIR_PASS`

Integrated repair commit:

`041e2550ec2ec090e45eec2d8de45f6a0c1e84f0`

Governing closeout:

`docs/printer-v1-v2-9-8b-later-cycle-duplicate-transport-repair-closeout.md`

Prior campaign closeout remains historically correct:

`V2_9_8B_AUTH_12A7EA61_CAMPAIGN_CLOSEOUT_PASS`

Scope-propagation repair live proof remains:

`CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_REPAIR_LIVE_PROOF_PASS`

## Consumed authorization

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61`

`CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`

Authorization SHA-256:

`b8112ab756e46c60bac82d486a0de113113cb3b266690f2850f2d6c7698a96f3`

Authorized execution HEAD:

`91c757c542d8098ecf7b244769061f333dcfc21f`

Do not retry, rerun, resume, restart, reuse, or create a successor from this
authorization. It must remain in every future prior-authorization non-reuse
trust root, together with consumed
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe` and every already
required prior ID.

## Campaign result

Historical. Cycle 1 admitted two tokens and completed
`WINDOW_15M -> WINDOW_1H -> WINDOW_4H`. Cycle 2 was attempted and not admitted
because cooperative `MARKET_DISCOVERY` replayed the same DexScreener due-mint
transport identity. That producer defect is now repaired in host-local code.
The consumed authorization remains dead.

## Post-campaign DB identity

Required authoritative DB path:

`data/printer_v1.sqlite3`

- SHA-256: `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c`
- size: `154796032`
- inode: `1230526`
- mtime_ns: `1788310792540112946`
- migration count/head: `62` / `062_pre_admission_attempt_evidence.sql`
- integrity: `ok`
- foreign-key violations: `0`
- journal mode: `delete`
- sidecars: none

This repair lane did not mutate the authoritative DB. Do not restore the
pre-run DB. Campaign writes were authorized.

## Durable zero-state / quiescence

All canonical ownership domains remain zero. No operational Printer processes.
Historical terminal rows remain historical residue and must not be mutated.

## Exact next permitted action

`Establish fresh exact-HEAD / exact-DB readiness / governance after the later-cycle duplicate-transport repair closeout commit exists. Do not prepare or apply an authorization in this handoff. Do not run Printer.`

The completed authorization-boundary design remains authoritative and must not
be redone. The scope-propagation repair remains closed PASS and live-proven.
The later-cycle duplicate-transport repair remains closed PASS.

## Application / execution remain blocked

This handoff does **not** authorize:

- `apply_authorization_once`;
- application-marker creation;
- Printer execution or child launch;
- campaign creation;
- provider / RPC / WebSocket calls;
- Central Scheduler runtime;
- authoritative DB mutation;
- retry / rerun / resume / restart / successor;
- retrieval / BUY / SELL / HOLD / positions / trades / audits / PnL;
- `WINDOW_12H` / `WINDOW_24H`.

## Standard-4H envelope

Preserve exactly:

- Solana-only;
- Solana memecoin-only;
- paper-only;
- two cycles;
- exactly 2 concurrently active token slots;
- up to 4 distinct identities campaign-wide;
- Cycle 2 fresh/disjoint from prior admitted campaign identities;
- `WINDOW_15M -> hard-gated WINDOW_1H -> hard-gated WINDOW_4H -> stop`;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_12H` / `WINDOW_24H` locked;
- no automatic retry/rerun/resume/restart/successor.

## Builder sequence

```text
audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout
```

Do not collapse readiness, authorization preparation, and execution into one
action.

## Permanent locks

Solana-only; Solana memecoin-only; paper-trading only. No live
wallet/private keys/signing/real funds/live execution. No paid API dependency.
No scoring/ranking/confidence/weighted decision logic. No embeddings/vectors
unless explicitly approved. No Source Governor or Central Scheduler bypass. No
dirty-memory retrieval/decisions. Retrieval and all financial capability remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. No automatic retry/rerun/resume/restart.

Remote/VPS work remains paused at
`agent/remote-host-linux-portability-implementation`, HEAD
`f61419f2db37fc5eb220c20fafeaf15501218033`.
