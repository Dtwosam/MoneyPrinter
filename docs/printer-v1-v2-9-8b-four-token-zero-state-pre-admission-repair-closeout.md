# Printer V1 V2-9.8B Four-Token Pre-Admission Zero-State Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_ZERO_STATE_PRE_ADMISSION_REPAIR_CLOSEOUT_PASS_READY_FOR_FRESH_READ_ONLY_REREADINESS_REVIEW`

The committed-code defect in the canonical pre-consumption zero-state projection is repaired narrowly. This closeout does **not** authorize creation or consumption of a fresh four-token authorization and does not authorize proof execution.

## Commit sequence

- Starting reviewed HEAD: `e149a5d95bc090cd711e7dc7abbe1f13fada7a53`
- Corrective audit: `0212f9c2913e159559aa96a3f002c96144b3d7da`
- Repair design: `f4dfc75745f66152e8b89db6c31e2612f655598f`
- RED regression contract: `a7eadc1c2ccf284ed510a19d00c61202705251bb`
- Production repair: `b67d0aeca73882b309fbf3e292a2068b15085e61`

Branch: `agent/v2-9-8b-four-token-pre-admission-zero-state-repair`

## Implemented change

Only the pre-admission entry in `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` changed.

Before:

```sql
SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts
```

After:

```sql
SELECT COUNT(*)
FROM printer_pre_admission_discovery_attempts
WHERE attempt_state NOT IN (
    'NO_PAIR','BLOCKED','FAILED','CANCELLED','CONSUMED'
)
```

This preserves migration-055 ownership semantics:

- blocking: `PLANNED`, `RUNNING`, `PAIR_READY`;
- retained non-blocking history: `NO_PAIR`, `BLOCKED`, `FAILED`, `CANCELLED`, `CONSUMED`;
- unexpected non-null state: blocking/fail closed.

No historical row is deleted or rewritten.

## TDD evidence

A new focused offline regression was committed before production code:

`tests/test_v2_9_8b_four_token_pre_admission_zero_state_semantics.py`

### RED

Against the original raw-count query:

- `PLANNED` / `RUNNING` / `PAIR_READY`: blocking checks passed;
- unexpected state: fail-closed check passed;
- each retained terminal state (`NO_PAIR`, `BLOCKED`, `FAILED`, `CANCELLED`, `CONSUMED`) failed because the old query projected `1` instead of `0`.

Observed result: `FAILED (failures=5)` across the retained-history subtests. This is the intended defect-specific RED.

### GREEN

Against the repaired exact `_ZERO_STATE_QUERIES` projection:

- retained terminal history test: PASS;
- active/unconsumed pair authority test: PASS;
- unexpected-state fail-closed test: PASS.

Observed result: `Ran 3 tests ... OK`.

The same focused files also passed Python compilation in the isolated verification harness.

## GitHub diff verification

The production implementation commit relative to the RED commit is one commit ahead and changes only:

- `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py`

GitHub reports `4 additions`, `2 deletions` for that implementation commit.

The complete repair branch relative to `e149a5d...` contains only:

- corrective audit document;
- repair design document;
- focused regression test;
- the canonical zero-state query change;
- this closeout document.

No migration, wrapper, Scheduler, discovery, Source Governor, campaign, factory, runtime, or trading code changed.

## Verification boundary

There is no repository GitHub Actions workflow on this branch, and this environment does not have a network-accessible/local MoneyPrinter checkout. Therefore this closeout does not claim a fresh full repository `pytest` run or a live wrapper execution.

That does not justify widening the lane: the defect is a single SQL projection, the regression extracts the canonical production query directly, RED/GREEN was demonstrated on that exact query contract, and the GitHub implementation diff proves no unrelated production behavior changed.

The next fresh read-only rereadiness review should still run the repository's normal minimum pre-authorization static/offline checks from the operator checkout before any authorization is created.

## Money-usefulness contribution

The repair prevents valid retained forensic history from falsely exhausting future proof opportunities. The eventual one-use four-token proof can now be gated on actual active ownership rather than an old terminal attempt, while the evidence needed to diagnose prior failures remains intact.

## What the repair improves

- fixes the proven false-positive pre-admission zero-state blocker;
- preserves migration-055 terminal history;
- keeps `PAIR_READY` fail closed until consumed;
- keeps unexpected states fail closed;
- leaves independent Scheduler/process/sidecar/migration/source-configuration defences unchanged.

## What remains locked

Still locked until later explicit lanes/reviews:

- fresh four-token authorization creation or consumption;
- four-token proof execution;
- six-token proof;
- 12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions, trade events, audits, and PnL;
- wallets, private keys, signing, live execution, and real funds;
- paid APIs, scoring/ranking/confidence systems, and embeddings/vectors.

## Proof required before the next proof attempt

The next permitted phase is a fresh independent/read-only rereadiness review from this repair closeout HEAD. It must confirm, at minimum:

- exact branch/HEAD and clean intended tracked state;
- canonical zero-state query semantics at the repaired HEAD;
- real authoritative DB/process zero active ownership without deleting terminal history;
- migration 055 identity/integrity/foreign-key readiness;
- no authoritative sidecars;
- exact four-token 4/2/2 policy and locked 12h/24h windows;
- existing pre-consumption wrapper still delegates to the canonical zero-state gate;
- minimum focused repository checks available from the operator checkout.

Only after that rereadiness closes PASS may a new authorization lane be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- `PAIR_READY` remains intentionally blocking; any later change to its consumption semantics requires a new audit/design rather than weakening this predicate casually.
- The retained-history allowlist is pinned to migration 055. A future migration that adds a state will fail closed until its ownership semantics are explicitly reviewed.
- Full repository pytest was not available in this connector-only environment; this is recorded rather than expanding scope or inventing CI.
- The old `e149a5d...` authorization-ready rereadiness conclusion remains superseded and must not be reused.

## Next permitted phase

**Fresh read-only four-token rereadiness review at the exact repair closeout HEAD.**

Do not create a fresh authorization before that review passes.