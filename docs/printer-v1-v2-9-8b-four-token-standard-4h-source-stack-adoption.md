# Printer V1 V2-9.8B Four-Token Standard-4H Source-Stack Adoption

Date: 2026-08-26

Status: `ADOPTED` into the active authoritative source stack by this
documentation-only governance synchronization.

Design verdict referenced by the implementation lane:

`V2_9_8B_SOURCE_STACK_GOVERNANCE_SYNCHRONIZATION_DESIGN_PASS`

Prior reconciliation:

`V2_9_8B_OPERATIONAL_AUTHORITY_CONTRACT_RECONCILIATION_BLOCKED`

Classification resolved by this adoption:

`CONTRACT_DRIFT`

## 1. Reconciliation finding

The later V2-9.8B four-token / two-cycle / standard-four-hour operational
authority was designed, implemented, exercised, repaired, and re-readied while
the active authoritative source stack still retained stale next-lane pointers
(notably the 2026-08-01 `WINDOW_15M` external one-shot wrapper design pointer)
and lacked an explicit four-token capacity envelope.

Candidate-acquisition N2/N7 remained deferred by restoration language, but that
deferral had never been paired with a formal source-stack adoption of the
later 4/2/2 operational envelope.

This adoption synchronizes the active source stack with that later operational
authority. It does **not** treat any consumed authorization or prior run as
execution authority.

## 2. Authority being adopted

Adopt the already-designed operational Memory Factory envelope:

- policy family: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- public mode family: `four-token-standard-four-hour-run`
- lane: `V2-9.8B — Active Bounded Memory Growth Operations`

Supporting later evidence (historical / non-authorizing by itself):

- post-DTW100 standard four-hour lifecycle source-stack adoption
- two-cycle / four-token operational authorization-alignment design and
  implementation/independent closeouts
- Aug-26 bind-order, timestamp/provenance, and cycle-disjointness repair
  closeouts
- post-repair next-bounded-campaign readiness audit
- operational authority contract-drift reconciliation

## 3. Exact capacity semantics

The current bounded operational campaign envelope may use:

- two cycles;
- exactly two concurrently active token slots;
- up to four **distinct** token identities across the full two-cycle campaign.

"Four-token" does **not** mean concurrent capacity four.

Concurrent capacity remains exactly:

```text
2
```

No capacity increase to 3 or 4 concurrent tokens is authorized by this adoption.

## 4. Cycle disjointness

Cycle-2 fresh-slot identity must be campaign-history disjoint from all earlier
admitted cycles.

Historical identities may appear in discovery / market-observation diagnostics,
but they cannot consume later-cycle fresh slots. Admission-time historical
validation remains defense-in-depth.

## 5. Standard four-hour lifecycle boundary

Standard observation lifecycle for otherwise-valid activated tokens:

```text
WINDOW_15M
-> hard-gated WINDOW_1H
-> hard-gated WINDOW_4H
-> stop
```

This adopts only the already-approved standard four-hour lifecycle authority.

`WINDOW_12H` and `WINDOW_24H` remain locked until later explicit source-stack
lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create
main outcome memory, continuation, retrieval, decisions, positions, or PnL.

## 6. Candidate-acquisition deferred status

Candidate-acquisition foundation, N2, N7, and global Pump cursor/recovery work
remain preserved but **DEFERRED**.

They are not an operational prerequisite for the active factory unless a later
explicit source-stack lane reactivates them. Historical documentation is
retained.

## 7. Implemented ≠ exercised ≠ authorized now

This adoption establishes the bounded capability envelope only.

| Layer | Effect of this adoption |
| --- | --- |
| Implemented capability | acknowledged as existing |
| Previously exercised capability | acknowledged as historical evidence only |
| Authorization to run now | **not** granted |

Formal source-stack adoption does **not** issue authorization.

## 8. Future campaign still requires separate authority

A future operational campaign still requires all of:

- separate fresh exact-HEAD authorization;
- explicit operator approval;
- exact DB binding;
- Source Governor;
- Central Scheduler;
- one-shot semantics;
- consumed authorization non-reuse;
- no automatic retry / resume / restart / successor.

Source scarcity, rate limits, insufficient fresh candidates, insufficient
evidence, or other honest market blockers remain valid terminal outcomes. The
profile does not promise 4/2/2 success.

## 9. Permanent locks preserved

Printer V1 remains:

- Solana-only
- Solana memecoin-only
- paper-trading only
- no wallet / private keys / signing
- no real funds / live execution
- no paid API dependency
- no scoring / ranking / confidence / weights
- no Source Governor bypass
- no Central Scheduler bypass
- no dirty-memory retrieval / decisions
- no retrieval / financial lane
- no BUY / SELL / HOLD
- no positions
- no trade events
- no paper audits
- no PnL
- no 12h / 24h activation

## 10. Current source-stack files amended by the synchronization

- `AGENTS.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`

`docs/printer-v1-clean-master-spec.md` and
`docs/printer-v1-post-rc-build-order.md` require no change for this adoption.
`CURRENT_HANDOFF.md` is intentionally left for the later closeout lane.

## 11. Next permitted governance lane

After this synchronization is itself proved and closed, the exact next
permitted lane is:

```text
POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION
READINESS / GOVERNANCE ONLY
```

This synchronization:

- creates no authorization;
- automatically authorizes no campaign;
- unlocks no live runtime;
- leaves fresh authorization as a separate later lane.

Do not jump directly to execution.

## 12. Non-mutation statement

This documentation adoption does not:

- edit product code or tests;
- add or apply migrations;
- write the authoritative database;
- contact providers / RPC / WebSocket;
- start Central Scheduler runtime;
- create or consume an authorization;
- start a campaign;
- unlock retrieval or any financial capability.
