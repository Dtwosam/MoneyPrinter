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
- partial implementation status checkpoint: `81ca0385ac258c496df54e5034b94b4529de0a66`.

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

## Current implementation status

Current repair branch:

`agent/v2-9-8b-second-standard-4h-safety-provenance-repair`

Durable status verdict:

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_PARTIAL_BLOCKED_TOOLING`

Implementation is **not complete**, bounded offline proof has **not passed**, and the branch is **not runnable or merge-ready**.

Completed implementation surfaces:

- `src/printer_v1/operator_cli/first_hour_safety_binding.py` — exact source-free fail-closed first-hour safety-composite binding helper;
- `src/printer_v1/sources/measured_transport.py` — `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT = 3` and `CONTINUATION_CLOSE = 4` reservation capacity;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — explicit first-hour safety request components in one-token and standard campaign lifecycle budgets;
- `tests/test_v2_9_8b_first_hour_safety_provenance_repair.py` — focused offline proof staged but not successfully executed.

Required canonical integration still unapplied:

1. `src/printer_v1/operator_cli/one_command_15m_factory.py` must collect/persist fresh safety during `CONTINUATION_CLOSE`, bind the exact fresh composite to the produced 1h memory, thread the existing context adapter factories, update local continuous/selective request ceilings, and identify the three first-hour safety reservations;
2. `src/printer_v1/operator_cli/operational_standard_4h.py` must change only `LIFECYCLE_REQUEST_OUTER_CEILING` from `230` to `236`; the Scheduler outer ceiling remains `210`.

No implementation closeout may be written until those edits land on one exact HEAD and the focused bounded offline proof passes.

## Tooling blocker truth

The GitHub connector available in this lane supports whole-file replacement but not a surgical line patch. `one_command_15m_factory.py` is a large canonical orchestration file, and connector reads of the whole file are truncated, so wholesale replacement from incomplete content was rejected as an unacceptable corruption/drift risk.

Temporary GitHub Actions edit/proof harnesses were attempted only as offline tooling. Runs `31480678969` and `31481278895` failed before any runner step executed and exposed no usable execution logs. These are CI-startup/tooling failures, not repair-test failures and not evidence that the implementation passed or failed its tests.

Temporary workflow/patch/trigger artifacts were removed. Temporary PR `#180` was closed unmerged. Its temporary CI-base branch was reset to the unchanged classification baseline. No temporary CI artifact remains in the repair branch diff.

## Safety status during repair work

This repair work has performed no Printer provider/source run, no Central Scheduler runtime, no authoritative Printer DB mutation, no memory generation, no new authorization, no reuse of either consumed authorization, and no standard-four-hour rerun/resume/restart/successor.

No 12h/24h, retrieval, paper decision, BUY/SELL/HOLD, position, trade event, paper-trade audit, or PnL capability has been unlocked or exercised.

The frozen consumed launch branch remains immutable.

## Current lane boundary

Remain inside:

`SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION`

Allowed next work is only completion of the two exact remaining canonical source edits plus minimum sufficient bounded offline proof and, if that proof passes, implementation closeout.

Not allowed while the implementation verdict remains partial/blocked:

- provider/source fetching;
- Central Scheduler runtime;
- authoritative DB mutation;
- operational rereadiness;
- new authorization creation/review;
- rerun/resume/restart/successor of either consumed attempt;
- another standard-four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL.

After implementation and bounded offline proof eventually close PASS, preserve the required sequence:

`implementation closeout -> fresh operational rereadiness -> only later fresh one-use authorization review`

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

Do not run another standard-four-hour attempt or create another authorization until the current repair implementation, bounded offline proof, implementation closeout, and fresh operational rereadiness all pass in order.