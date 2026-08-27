# Printer V1 Assistant Active Build Order Anchor

## Purpose and authority

This document aligns ChatGPT, Codex, Claude, and future assistants before Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations may explain history, but material current operational authority must be adopted into the active source stack before assistants treat it as current law.

## Current durable state (2026-08-26)

Active memory-growth lane:

- `V2-9.8B — Active Bounded Memory Growth Operations`

Canonical current operational envelope adoption:

- `docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`
- policy family: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- public mode family: `four-token-standard-four-hour-run`

Exact capacity semantics:

- two cycles;
- exactly two concurrently active token slots;
- up to four distinct token identities across the full two-cycle campaign;
- "four-token" does **not** mean concurrent capacity four;
- concurrent capacity remains exactly `2`;
- no increase to 3 or 4 concurrent tokens is authorized.

Standard observation lifecycle:

```text
WINDOW_15M
-> hard-gated WINDOW_1H
-> hard-gated WINDOW_4H
-> stop
```

`WINDOW_12H` and `WINDOW_24H` remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

Cycle-2 fresh-slot identity must be campaign-history disjoint from earlier admitted cycles. Historical identities may appear in discovery diagnostics but cannot consume later-cycle fresh slots.

Candidate-acquisition foundation / N2 / N7 / global Pump cursor/recovery remain preserved but deferred and are not an operational prerequisite.

Capability layers:

- implemented capability exists;
- previously exercised capability is historical evidence only;
- this adoption does **not** authorize a run now.

No historical authorization may be reused. Consumed authorizations remain permanently dead.

## Exact next permitted lane

The exact current next permitted lane is:

```text
POST-REPAIR FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION
READINESS / GOVERNANCE ONLY
```

Historical at the time of the 2026-08-26 source-stack synchronization:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. That pointer is superseded by the later Cycle-1
historical-disjointness repair closeout and `CURRENT_HANDOFF.md`.

This lane is readiness/governance only:

- creates no authorization;
- automatically authorizes no campaign;
- unlocks no live runtime;
- leaves fresh exact-HEAD authorization as a separate later lane after a new
  readiness PASS at the then-current HEAD.

A future operational campaign still requires separate fresh exact-HEAD authorization, explicit operator approval, exact DB binding, Source Governor, Central Scheduler, one-shot semantics, consumed-authorization non-reuse, and no automatic retry/resume/restart/successor. Source scarcity and honest evidence blockers remain valid terminals. The profile does not promise 4/2/2 success.

## Historical durable anchors (preserved; not current next-lane authority)

Durable historical anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- post-DTW100 E2Q audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`;
- first-hour Checkpoint 1-6 offline-composition chain closeout: `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- first consumed standard-four-hour runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- first-attempt repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- first-attempt repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
- post-repair standard-four-hour rereadiness closeout: `8fd74f5d13225b72ebb56890dfd17224600189c5`;
- second standard-four-hour launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`;
- second standard-four-hour runtime classification closeout: `623ea64657555341419fe92f000435e11ab52d5c`;
- second-attempt 1h→4h safety/provenance repair-scope audit: `303227dd76b96b144dab75c11bf1cb827563babc`;
- second-attempt 1h→4h safety/provenance repair design: `695fd3e53781b1faba13d21226f323d1e586cbb1`;
- partial implementation status checkpoint: `81ca0385ac258c496df54e5034b94b4529de0a66`;
- second-attempt 1h→4h safety/provenance repair implementation closeout: `0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`;
- post-safety-repair operational rereadiness audit closeout: `f153a6bc24efb3b708e6fb86c1e262f258613b67`;
- second standard-four-hour public budget-authority repair-scope audit: `146261d41cdd5ac9a13054bd3e8237d78d98db83`;
- second standard-four-hour public budget-authority repair design: `ba2843f0e26d67ad6175d27adce0ab63e30bb308`;
- second standard-four-hour public budget-authority repair implementation closeout: `61647122d33cbf45f0e321a989f4ea14ca00b1b1`;
- post-public-budget-authority-repair operational rereadiness closeout: **PASS** at `61647122d33cbf45f0e321a989f4ea14ca00b1b1`;
- fresh one-use standard-four-hour authorization preparation HEAD: `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`;
- independent fresh standard-four-hour authorization review closeout: historical PASS for a then-unconsumed authorization that is no longer the current next-lane authority;
- 2026-08-01 `WINDOW_15M` external one-shot wrapper-design next-lane pointer: historical only;
- Aug-26 bind-order / timestamp-provenance / cycle-disjointness repairs: closed PASS as product repairs; not themselves authorization;
- operational authority contract-drift reconciliation: `V2_9_8B_OPERATIONAL_AUTHORITY_CONTRACT_RECONCILIATION_BLOCKED`, resolved by this source-stack adoption.

DTW97 remains permanently consumed. DTW100 remains closed.

## Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no paper decisions before their explicit approved lane;
- no BUY/SELL/HOLD before its explicit approved lane;
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes;
- no 12h/24h activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Assistant execution rule

Preserve the V2 sequence and use minimum sufficient risk-based verification.

Do not create authorization, reuse a consumed authorization, start Printer, contact providers/RPC, or run Central Scheduler merely because this anchor or the source-stack adoption exists. The exact current next permitted lane is remote-host readiness / portability audit only; this is infrastructure support and does not advance capability order.

<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Retained-Evidence Repair Closeout — Historical Authority

This current-state synchronization block supersedes earlier current-looking
V2-9.8B repair/readiness/next-sub-lane pointers in this document for the
retained-evidence repair chain. Historical lane text remains evidence only.

- implementation / bounded-proof baseline: `851d92627c3f5b05b1366af0d0dfef2712a330d8`
- authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`
- bounded-proof verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_BOUNDED_PROOF_PASS`
- closeout verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_REPAIR_CLOSEOUT_PASS`
- consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable
- candidate-acquisition N2/N7 remains deferred and is not a prerequisite
- no Source Governor or Central Scheduler bypass
- successful freeze remains 4 candidates -> 2 selected + 2 report-only alternates
- standard memory path remains 15m -> 1h -> 4h -> stop
- 5m remains support-only; 12h/24h remain locked
- retrieval and all financial capability remain locked

At closeout time, the next permitted lane was:

`POST-CLOSEOUT FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS / GOVERNANCE ONLY`

This pointer is historical after the later authorization-readiness PASS below.

That lane is readiness/governance only. It does not itself authorize issuance,
execution, providers, RPC/WebSocket, Scheduler ticks, or authoritative DB writes.

This retained-evidence repair pointer is historical after later readiness and campaign closeout.
<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Closeout Authorization Readiness — Historical Authority

Readiness verdict:

`V2_9_8B_POST_CLOSEOUT_FRESH_NEXT_BOUNDED_CAMPAIGN_AUTHORIZATION_READINESS_GOVERNANCE_PASS`

Audited closeout HEAD: `941ddd727b0e8b6aabf7eacbf9513f47979adb46`
Authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`

The retained-evidence repair chain is closed. The historical authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable.

At readiness time, the next permitted lane was:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That lane may prepare and independently review a fresh exact-HEAD/exact-DB
one-shot authorization artifact. It does not authorize Printer execution.
Any fresh authorization must bind to the new readiness commit HEAD produced by
this synchronization and to the exact DB SHA above. Separate operator approval
is still required before execution.

All permanent V1 locks remain unchanged.

This readiness pointer is historical after the later authorized campaign closeout.
<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_END -->

<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Authorization 8e43eae7 Campaign Closeout — Current Authority

- campaign closeout: `V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_PASS`
- authoritative post-campaign DB: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- campaign classification: `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- Cycle 1: 2 tokens; 15m clean-promoted; 1h dirty; 4h ineligible/no successors
- Cycle 2: `NO_PAIR / DURATION_EXHAUSTION`
- no current-campaign active work
- retrieval/financial/12h/24h locks remain closed

The exact current next permitted lane is:

`REMOTE HOST READINESS / PORTABILITY AUDIT ONLY — INFRASTRUCTURE SUPPORT; NO CAPABILITY ADVANCEMENT`

This is infrastructure audit support only. It does not advance the active
memory-growth capability build order and does not authorize deployment,
migration, authorization issuance, provider/RPC/WebSocket calls, Scheduler
execution, another campaign, retrieval, financial capabilities, or longer
windows.
<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_END -->
