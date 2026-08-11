# Printer V1 V2-9.8B — Third Standard Four-Hour Safety Cutoff / Provenance Repair-Scope Audit

## Verdict

`V2_9_8B_THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_SCOPE_AUDIT_PASS`

Primary Python-guide classification:

`COMMITTED_CODE_DEFECT`

Exact defect classification:

`COMMITTED_CODE_DEFECT_AT_FIXED_FIRST_HOUR_CUTOFF_VS_OBSERVED_CLOSE_SAFETY_EVIDENCE_BOUNDARY`

This audit is read-only/static plus review of already-created attempt evidence. It performs no Printer runtime, provider/source request, Central Scheduler execution, authoritative DB mutation, memory generation, authorization creation, rerun, resume, restart, successor, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or real-funds action.

## Authority and baseline

Use this audit inside the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

`docs/printer-v1-memory-growth-build-order-v2.md` remains the active memory-growth build order, not the sole source of truth. Later committed audit/design/implementation/proof/closeout evidence controls exact lane position.

Audit branch baseline: `cf5daf8294f6319a4bde99199eb41bd0010bfdf2`.

The frozen launch code is `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`. Comparison to `cf5daf...` shows only authorization-review documentation changes; production code is identical. The frozen launch branch is not modified by this audit.

## Third consumed attempt identity

Authorization:

- ID: `V2_9_8B_STANDARD_4H_AUTH_20260811T135326Z`
- SHA-256: `446e50cf376e576bf308ceee254d025e8fa3221683c9e91e1dcc1f0d2976db36`
- frozen launch branch: `agent/v2-9-8b-fresh-one-use-standard-4h-authorization-preparation`
- launch HEAD: `0be6b4f7f56a501a40b2ef02521689ccaffb0ce9`

Attempt:

- execution: `20260811T144050Z-28018eff9859`
- campaign: `20260811T144050Z-28018eff9859-campaign`
- campaign run: `20260811T144050Z-28018eff9859-campaign-run`
- authoritative factory run: `3d236624-c4d0-497f-8013-45aa7298955b`
- first terminal cause: `SAFE_STOP_4H_TERMINAL_INCOMPLETE`
- child exit: `0`
- marker consumed: true
- retry/rerun/resume/restart/successor: zero

The authorization is permanently consumed and non-reusable.

## Runtime reconstruction relevant to this audit

The attempt safely completed both owned `WINDOW_15M` lifecycles and both owned `WINDOW_1H` lifecycles. Both 1h campaign windows reached `CLEAN_PROMOTED`; both continuation-close run steps succeeded.

The standard-four-hour barrier waited until both 1h closes were terminal, then released with zero eligible slots and zero 4h jobs. Both tokens independently returned:

- `predecessor_evidence_stale`
- `governed_provenance_untraceable`
- `mandatory_safety_context_not_acceptable`

Direct B.2 inspection of the exact first-hour safety composites showed the same underlying failure on both tokens:

- slot 1 composite `13`: `safety_evidence_stale_or_post_cutoff`, `safety_source_trace_mismatch`
- slot 2 composite `14`: `safety_evidence_stale_or_post_cutoff`, `safety_source_trace_mismatch`
- both composites had two source traces
- both effective results: `SAFETY_CONTEXT_BLOCKED`

There were zero `WINDOW_4H` campaign windows and zero `LONG_CONTINUATION_%` run steps. Cleanup completed, the lease was released, DB integrity was `ok`, foreign-key violations were zero, no SQLite sidecars remained, and protected downstream financial/retrieval capabilities stayed locked.

## Root cause

The defect is a deterministic mismatch between three committed contracts.

### 1. Scheduler-owned first-hour close collects safety at the close boundary

`one_command_15m_factory._execute_continuation_close()` performs the approved sequence:

```text
collect fresh safety-only governed context
-> capture the final exact-pair snapshot
-> persist the safety evidence/composite against that snapshot
-> close WINDOW_1H
-> bind the exact fresh safety composite
-> audit/E2Z
-> later 4h barrier consumes B.2
```

The safety composite is persisted with `evaluated_at` equal to the actual final snapshot `captured_at`. Its contribution traces retain the actual source response/failure timestamps.

### 2. The physical WINDOW_1H uses a fixed lifecycle deadline as `window_end_at`

For predecessor-linked continuation, `lane_e2o_1h_window_close.py` computes the fixed deadline as the 15m close plus 2700 seconds. It correctly requires the actual closing snapshot not to precede that deadline, but then writes:

```text
window_start_at = exact 15m close
window_end_at   = exact 15m close + 2700 seconds
```

Therefore `WINDOW_1H.window_end_at` is the fixed lifecycle deadline, not the observed final-snapshot timestamp.

### 3. B.2 treats that fixed `window_end_at` as the safety evidence cutoff

`load_authoritative_window_safety()` is called with `memory_window_close_cutoff = physical WINDOW_1H.window_end_at`. It requires the composite and every contribution trace to be at or before that cutoff. Any negative age is rejected as post-cutoff and makes the source trace invalid.

The `CONTINUATION_CLOSE` job itself is due at the fixed deadline. It then performs the fresh safety transport work and captures the final snapshot. In a real run those observations naturally occur seconds after the deadline. The third attempt demonstrates this shape directly; for slot 2, the close was scheduled at `2026-08-11T15:41:15.481153+00:00` while the final snapshot was captured at `2026-08-11T15:41:21.460751+00:00`.

Consequently, evidence produced exactly by the approved first-hour close path is structurally liable to be rejected by B.2 as future/post-cutoff evidence.

## Why this is a code defect, not an expected market blocker

The two tokens had different market behavior but failed the exact same timestamp/provenance checks at the same boundary. Their 1h collection and continuity were otherwise valid. The rejection is explained by deterministic orchestration timing and cutoff semantics, not by token-specific safety facts.

The prior first-hour safety repair correctly added fresh governed collection, exact snapshot linkage, exact composite binding, and fail-closed B.2 consumption. Its focused offline proof did not reproduce the real case where fresh provider responses and the actual closing snapshot arrive slightly after the fixed lifecycle deadline while B.2 still uses that deadline as its evidence cutoff.

B.2 itself correctly fails closed under its current contract. This audit does not authorize weakening freshness, provenance, target, identity, or safety checks.

## Repair scope

The next lane is design/specification only:

`THIRD_STANDARD_FOUR_HOUR_SAFETY_CUTOFF_PROVENANCE_REPAIR_DESIGN`

The design must align lifecycle deadline semantics with observed close-evidence semantics without introducing future-data leakage or weakening evidence authority.

It must explicitly resolve the ownership of two distinct concepts:

1. **fixed lifecycle deadline** — the scheduled end of the 45-minute continuation phase;
2. **observed close-evidence cutoff** — the latest timestamp legitimately produced by the Scheduler-owned close operation for the exact closing snapshot and its governed safety evidence.

The design may evaluate narrowly scoped approaches such as:

- keeping fixed `WINDOW_1H` duration semantics while giving B.2 an exact observed-close evidence cutoff bound to the same final snapshot; or
- moving the fresh safety collection into a specifically approved pre-deadline Scheduler-owned phase if that can preserve exact snapshot/trace identity and bounded budgets.

The audit does **not** choose or implement either approach.

Forbidden repair shortcuts:

- arbitrary grace/tolerance widening;
- accepting evidence merely because it is the latest row;
- reusing the old 15m safety composite as 1h authority;
- dropping the source-trace requirement;
- allowing post-observed-close evidence;
- weakening target/pair/mint/snapshot identity checks;
- Source Governor bypass;
- Central Scheduler bypass;
- hidden request-budget or Scheduler-budget expansion;
- parallel/disposable runner or harness as production authority.

## Minimum later proof required

Before implementation closeout, focused offline tests must prove at minimum:

1. a real-shaped `CONTINUATION_CLOSE` where safety responses and the final snapshot occur a few seconds after the fixed lifecycle deadline is handled according to the approved design;
2. exact token/pair/mint/final-snapshot/composite/source-request/source-response correspondence remains mandatory;
3. truly post-observed-close evidence still fails closed;
4. evidence older than the existing 1800-second freshness maximum still fails closed;
5. mismatched source traces, wrong target, missing composite, and wrong snapshot remain blocked;
6. fixed 45-minute lifecycle/cadence semantics remain auditable and are not silently replaced by an unbounded window;
7. request and Scheduler ceilings remain exact, or any approved change is derived from the canonical budget owner and proven cross-owner before rereadiness.

No live standard-four-hour rerun is part of this repair proof.

## Money-usefulness contribution

This repair scope targets a deterministic false safety block that can consume a scarce one-use standard-four-hour authorization after an otherwise valid first hour. Correctly separating lifecycle timing from exact observed close evidence should let Printer grow valid 1h→4h learning evidence when the safety data is genuinely acceptable, without making unsafe tokens easier to pass.

## What this audit improves

- identifies one concrete architectural cause instead of treating three barrier reasons as independent failures;
- preserves the fail-closed B.2 safety authority;
- prevents another authorization from being consumed on the same known defect;
- defines the exact design boundary that must be solved before implementation.

## What remains locked

This audit does not unlock:

- another standard-four-hour attempt;
- any new authorization;
- `WINDOW_12H` or `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallet/private keys/signing/real funds/live execution;
- paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Consequence | Required control |
|---|---|---|
| Simply move the cutoff later | May admit genuine future data | Cutoff must be bound to exact Scheduler-owned observed close evidence, never wall-clock grace |
| Change `window_end_at` to arbitrary actual completion time | Can blur fixed 45m lifecycle/cadence semantics | Keep lifecycle deadline and evidence-observation semantics explicit and independently auditable |
| Move safety collection earlier without ownership design | Can create new Scheduler/budget/timing drift | Design exact owner, timing, reservation and failure behavior before implementation |
| Keep one timestamp serving two incompatible meanings | Repeats the defect | Separate fixed lifecycle deadline from evidence cutoff contractually |
| Weaken B.2 trace checks to make proof pass | Unsafe provenance acceptance | Negative trace/target/snapshot tests remain mandatory |
| Broad regression work after a narrow defect | Wastes time and increases drift | Use focused risk-based tests; document unrelated pre-existing failures separately |

## Closeout and next lane

This audit supersedes the earlier authorization-review statement that the third authorization is unconsumed. The third authorization has since been consumed exactly once and is permanently non-reusable.

Required sequence from here:

```text
third-attempt repair-scope audit        <- CLOSED PASS here
-> safety cutoff/provenance repair design
-> implementation, if design passes
-> focused bounded offline proof
-> implementation closeout
-> fresh operational rereadiness
-> only then, if rereadiness passes, fresh one-use authorization preparation
-> independent authorization review
-> separately operator-started bounded attempt
```

No step authorizes the next automatically.
