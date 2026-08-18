# CURRENT HANDOFF

Date: 2026-08-18

## Current lane

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Design`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_POST_REPAIR_TWO_CYCLE_FOUR_TOKEN_OPERATIONAL_AUTHORIZATION_ALIGNMENT_DESIGN_PASS`

Implementation disposition: `IMPLEMENTATION_REQUIRED`

## Current code baseline

Repaired operational product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Design branch:

`agent/v2-9-8b-post-repair-two-cycle-four-token-operational-authorization-alignment-design`

Design commit before this handoff update:

`d24853d8b6c2545a1d4031ecdf776e0de5ed0f8e`

Parent audit handoff:

`282066b2711b35e9a83117571fe278edf5e91dc5`

The design lane changes documentation only. Master remains untouched.

## Latest completed work

The design establishes a distinct operational 4/2/2 authority while preserving both existing authorities:

- `standard-four-hour-run` remains the exact two-token Standard-4H operational authority;
- `four-token-bounded-capacity-proof-run` remains proof-only;
- new designed operational child mode: `four-token-standard-four-hour-run`;
- one exact bounded invocation, four through-4h token slots, two cycles, two fresh distinct token/pair slots per cycle;
- Cycle 2 is governed later-cycle fresh acquisition inside the same campaign/run and may overlap Cycle 1 only through existing multi-cycle admission/capacity gates;
- no second Memory Factory runner, Scheduler, Source Governor, provider loop, schema owner or selection algorithm;
- capacity remains derived from `scaled_standard_four_hour_capacity_contract(4)` rather than copied;
- cycle-local 15m -> 1h -> eligible 4h continuation remains unchanged; 5m is support-only and 12h/24h remain locked;
- one fresh operational authorization covers the exact whole 4/2/2 child; no per-cycle authorization, retry, rerun, resume, restart or successor.

The design also requires post-repair provenance alignment:

- Migration 058 is current schema-transition evidence for both the repaired four-token proof profile and the new operational four-token profile;
- Migration 057 becomes distinct preserved historical migration evidence alongside 050, 055 and 056;
- exact Migration-057 historical execution/inventory values must come from preserved real evidence and must not be guessed;
- exact Migration-058 current evidence must be reconciled with real repair evidence; inability to establish it is a readiness block, not permission to fabricate evidence;
- ordinary and two-token Standard-4H profile semantics remain outside this repair scope.

The preceding repository preparation lane created no fresh Standard-4H authorization. If additional authorization evidence exists only on the actual host, later preparation must enumerate and classify it by exact identity; it cannot be repurposed as 4/2/2 authority.

## Designed implementation boundary

Likely implementation changes are limited to:

- public-command registration/policy for the new exact operational mode;
- a distinct `four_token_standard_four_hour_one_shot_wrapper.py` authority;
- a distinct Git authorization profile for that operational mode;
- Migration-058 current / Migration-057 historical repair for four-token provenance;
- reuse/generalization of the existing read-only four-token zero-state gate without duplicating its ownership SQL;
- only the smallest neutral facade/helper needed to enter the already-repaired multi-cycle composition.

No migration file, provider contract, broad runtime repair or future capability activation is designed.

## Verification sequence after implementation

Implementation must use focused cross-cutting tests for wrapper one-use behavior, exact 4/2/2 derivation, command separation, Cycle-2 distinct identities/fresh supply, Source Governor/Scheduler ownership, 058-current/057-historical provenance, zero-state migration 58/058, locked long windows and existing standard/proof regressions.

After implementation, a separate bounded offline/disposable proof must run with fake/frozen transports and deterministic time. No live provider/RPC/WebSocket campaign is authorized by implementation alone.

Only after implementation -> bounded proof/test -> closeout PASS may host-local operational 4/2/2 authorization preparation begin.

## Exact next permitted action

`V2-9.8B Post-Repair Two-Cycle Four-Token Operational Authorization Alignment Implementation`

Implementation only.

If exact preserved Migration-057 evidence needed for the immutable historical inventory cannot be established, stop as `BLOCKED_READINESS` before weakening provenance law.

Do not create or consume the final operational authorization and do not run a live campaign in the implementation lane.

## Locks

5m remains support-only. Migration head remains 058; no 059 is permitted. 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live wallet/private-key/signing execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic and embeddings/vectors remain locked.

The active authority stack wins any conflict with this handoff.
