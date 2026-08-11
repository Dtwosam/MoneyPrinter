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

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations control exact current lane position.

## Current durable state

V2-9.8B has consumed two separately authorized standard-four-hour attempts. Neither is a successful 4h proof and neither authorization may ever be reused.

Durable anchors include:

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
- post-safety-repair operational rereadiness audit closeout: `f153a6bc24efb3b708e6fb86c1e262f258613b67`.

DTW97 remains permanently consumed. DTW100 remains closed. No historical authorization may be reused.

## Second consumed standard-four-hour attempt

Fresh authorization:

- ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T010152Z`;
- SHA-256: `f58788685f836a3c0979bfb71ddd079beb84ffba568a5ad70823554fa2bb7612`;
- frozen launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`;
- exact launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7`.

Attempt identity:

- execution: `20260811T011906Z-2e278d795b54`;
- campaign: `20260811T011906Z-2e278d795b54-campaign`;
- campaign run: `20260811T011906Z-2e278d795b54-campaign-run`;
- authoritative factory run: `7a84b80b-4f51-4516-84e9-828132a45009`;
- first terminal cause: `SAFE_STOP_4H_TERMINAL_INCOMPLETE`;
- wrapper child exit: `0`;
- child terminal valid: true;
- retry / rerun / resume / restart / successor: none.

The authorization passed preparation and independent review, was consumed exactly once, and is permanently non-reusable.

## Second-attempt runtime truth

Read-only reconstruction closed PASS with root-cause classification:

`COMMITTED_CODE_DEFECT_AT_WINDOW_1H_TO_WINDOW_4H_SAFETY_PROVENANCE_INTEGRATION_BOUNDARY`

Both selected tokens completed valid physical and clean `WINDOW_15M` and `WINDOW_1H` memories. The standard-four-hour barrier later reached its two-token decision point but returned zero eligible slots and zero planned 4h jobs.

Both tokens received identical `BLOCK_CONTINUATION` reasons:

- `predecessor_evidence_stale`;
- `governed_provenance_untraceable`;
- `mandatory_safety_context_missing`.

Those three reasons derive from one systemic missing authority input, not three independent market failures.

The standard-4h consumer correctly requires the exact predecessor 1h memory to retain `supporting_context_json.memory_build_evidence_overlays.safety_composite_id`. The produced first-hour memories contained no such binding. The B.2 safety adapter therefore failed closed.

There were zero campaign/physical `WINDOW_4H` rows, zero 4h Scheduler jobs/work rows, no 4h collection, and no 4h memory. `SAFE_STOP_4H_TERMINAL_INCOMPLETE` is the downstream terminal symptom, not the root cause.

No attempt-linked retrieval, paper-decision, position, trade, audit, or PnL rows were created. All downstream financial capabilities remain locked.

## Repair audit result

The repair-scope audit closed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_SCOPE_AUDIT_PASS`

The audit proved the defect is broader than a missing copied ID. The committed safety composite freshness contract is 30 minutes, while the first-hour close is beyond the earlier 15m safety checkpoint. Therefore copying the old 15m safety-composite ID into the 1h memory is prohibited and would not constitute a valid repair.

The canonical repair is fresh first-hour safety authority:

1. during the already Scheduler-owned `CONTINUATION_CLOSE`, collect fresh safety through the existing Source-Governed context path;
2. persist that evidence/composite against the exact first-hour closing snapshot;
3. close the exact `WINDOW_1H` predecessor;
4. bind the exact fresh `safety_composite_id` into that first-hour memory before outcome/audit/E2Z;
5. leave the B.2 exact safety consumer and all freshness/provenance/safety hard gates unchanged.

The bounded worst-case first-hour safety bundle is three source transports, so `CONTINUATION_CLOSE` requires four reserved source operations total: one exact-pair close observation plus three first-hour safety reservations. No new Scheduler job is required.

Target standard request ceilings become:

- FAST + FAST: `236`;
- FAST + NORMAL: `188`;
- NORMAL + NORMAL: `140`.

Scheduler ceilings remain `210`, `162`, and `114` respectively.

## Repair design result

The repair design closed PASS:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_DESIGN_PASS`

Required exact order:

```text
Scheduler-owned CONTINUATION_CLOSE
-> collect fresh safety-only governed context
-> persist final exact-pair closing snapshot
-> persist fresh safety/composite against that exact snapshot
-> resolve exact current-run 15m predecessor
-> close exact WINDOW_1H
-> bind exact fresh safety composite ID
-> derive first-hour outcome
-> audit / E2Z
-> later standard 4h barrier consumes unchanged B.2 authority
```

`lane_e2o_1h_window_close.py` remains source-free. Source calls stay in `one_command_15m_factory.py`. B.2 must not fall back to an arbitrary latest safety composite. No freshness, provenance, safety, Source Governor, Scheduler, identity, or continuity gate may be weakened.

## Completed implementation status

Repair branch:

`agent/v2-9-8b-second-standard-4h-safety-provenance-repair`

Durable implementation verdict:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

Exact repaired implementation HEAD:

`0da9a5e1d5404e9ecfb9dba176028514e8de4e1f`

Implementation is complete and the focused bounded offline proof passed.

Completed implementation surfaces:

- `src/printer_v1/operator_cli/first_hour_safety_binding.py` — exact source-free fail-closed first-hour safety-composite binding helper;
- `src/printer_v1/sources/measured_transport.py` — `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3` and `CONTINUATION_CLOSE = 4` reservation capacity;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — explicit first-hour safety request components in one-token and standard campaign lifecycle budgets;
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — Scheduler-owned `CONTINUATION_CLOSE` collects safety-only governed context before the final exact-pair snapshot, persists it against that exact closing snapshot, binds the exact fresh composite into the produced `WINDOW_1H` before outcome/audit/E2Z, threads `context_adapter_factories`, raises factory-local request ceilings, and labels the three first-hour safety reservations;
- `src/printer_v1/operator_cli/operational_standard_4h.py` — `LIFECYCLE_REQUEST_OUTER_CEILING = 236`, Scheduler outer ceiling unchanged at `210`.

Confirmed repaired lifecycle budget truth:

| lanes | 4h eligible | requests | Scheduler |
|---|---|---:|---:|
| FAST + FAST | both | 236 | 210 |
| FAST + NORMAL | both | 188 | 162 |
| NORMAL + NORMAL | both | 140 | 114 |
| FAST + FAST | none | 98 | 82 |

`CONTINUATION_CLOSE` reserves exactly `4`: one exact-pair close observation plus three worst-case fresh 1h safety transports. No new Scheduler job was introduced. The unchanged B.2 consumer `load_authoritative_window_safety()` and source-free `lane_e2o_1h_window_close.py` were not modified.

Three unrelated pre-existing Git-provenance fixture failures remain separately documented; they are not a reason to reinterpret the safety repair as failed.

## Fresh operational rereadiness result

Fresh post-safety-repair operational rereadiness is **BLOCKED** with verdict:

`V2_9_8B_POST_SAFETY_PROVENANCE_REPAIR_OPERATIONAL_REREADINESS_BLOCKED_PUBLIC_BUDGET_AUTHORITY_DRIFT`

Audit closeout:

`docs/printer-v1-v2-9-8b-post-safety-provenance-repair-operational-rereadiness-audit.md`

Primary classification:

`PUBLIC_STANDARD_FOUR_HOUR_BUDGET_AUTHORITY_DRIFT_AFTER_FIRST_HOUR_SAFETY_REPAIR`

Static exact-HEAD inspection proved the repair's `236` worst-case request contract did not propagate through every live public/authorization owner:

- `one_token_4h_runtime` and `operational_standard_4h` carry the repaired lifecycle truth;
- `operational_memory_factory_command.py` still publishes and persists standard-four-hour `230` total / `114` per-token request capacity;
- `standard_four_hour_one_shot_wrapper.py` still generates and validates one-use authorization documents with request outer ceiling `230`;
- `tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` still explicitly pins those stale `230/114` public and wrapper contracts while other repaired tests pin `236`.

A fresh authorization prepared from the current committed wrapper would therefore bind a request-capacity contract that contradicts the repaired lifecycle planner/factory contract.

This is sufficient to block rereadiness before host-local execution. No fresh host/DB rereadiness PASS is claimed. The historical rereadiness helper is also not reusable unchanged because it encodes older branch/DB/application-marker state and the old `230` ceiling.

No Printer provider/source run, Central Scheduler runtime, authoritative DB mutation, memory generation, new authorization, authorization reuse, standard-four-hour rerun/resume/restart/successor, or downstream financial action occurred in this rereadiness audit.

## Current lane boundary

Current audit branch:

`agent/v2-9-8b-post-safety-repair-operational-rereadiness-audit`

The next roadmap-compliant lane is:

`SECOND_STANDARD_FOUR_HOUR_PUBLIC_BUDGET_AUTHORITY_REPAIR_SCOPE_AUDIT`

That next lane is **audit-only**.

It may inspect:

- the exact standard-four-hour capacity owners;
- public preflight and immutable campaign-configuration propagation;
- one-shot authorization generation/validation;
- directly affected policy/authorization tests;
- adjacent selective-1h `92/45` versus factory-local `98/48` representation only to determine whether the same canonical ownership/coupling is involved.

It may not implement a repair or widen into an unrelated capability change.

Still not allowed:

- host operational rereadiness PASS before the repair chain closes;
- provider/source fetching;
- Central Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- new authorization creation/review;
- reuse of either consumed authorization;
- rerun/resume/restart/successor of either consumed attempt;
- another standard-four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL.

Preserve the required sequence:

```text
repair-scope audit
-> design/specification
-> implementation if approved
-> bounded offline proof/test
-> closeout
-> fresh operational rereadiness
-> only later fresh one-use authorization preparation/review
-> only after independent authorization closeout may another bounded standard-four-hour attempt be considered
```

No step authorizes the next automatically.

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
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Assistant execution rule

Preserve the V2 sequence and use minimum sufficient risk-based verification.

Do not create another authorization or run another standard-four-hour attempt until the public budget-authority blocker is audited, designed, implemented if approved, proven, closed, and followed by a fresh operational rereadiness PASS.