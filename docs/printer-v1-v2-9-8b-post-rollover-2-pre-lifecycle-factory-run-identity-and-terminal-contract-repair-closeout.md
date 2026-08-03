# Printer V1 V2-9.8B Post-Rollover-2 Pre-Lifecycle Factory-Run Identity and Terminal Contract Repair Closeout

Date: 2026-08-03

Baseline:

```text
6dc8969444a86199cdefb17c050d7a8f1f10490b
Record authoritative 15m child blocker
```

Lane:

```text
V2-9.8B Post-Rollover-2 Pre-Lifecycle Factory-Run Identity and Terminal Contract Repair
```

## Verdict

```text
V2_9_8B_POST_ROLLOVER_2_PRE_LIFECYCLE_FACTORY_RUN_IDENTITY_AND_TERMINAL_CONTRACT_REPAIR_PASS
```

## Exact files changed

| Path | Role |
| --- | --- |
| `docs/printer-v1-v2-9-8b-post-rollover-2-pre-lifecycle-factory-run-identity-and-terminal-contract-repair-design.md` | design/readiness |
| `docs/printer-v1-v2-9-8b-post-rollover-2-pre-lifecycle-factory-run-identity-and-terminal-contract-repair-closeout.md` | this closeout |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | coordinator identity retain order, factory extraction, retained-only failure terminalization, honest exception mutation envelope |
| `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` | pre-lifecycle shortage/block returns expose `campaign_run_id` only |
| `tests/test_v2_9_8b_post_rollover_2_pre_lifecycle_factory_run_identity_and_terminal_contract_repair.py` | focused deterministic proofs |

No schema, migration, Source Governor, Central Scheduler, wrapper, authorization-law,
provider-contract, eligibility-floor, retry, or accounting-architecture files were
changed.

## Before / after control flow

### Before (defective)

```text
result = owner.run_operational(...)
lifecycle = dict(result.lifecycle)
returned = lifecycle.get("run_id")          # campaign-run on shortage path
if returned:
    retain_factory_run_id(returned)         # raises identity-changed
# heartbeat handling...
if not result.lifecycle_started:            # never reached on shortage path
    return pre_lifecycle_finalize(...)
```

Concurrent honest shortage became:

```text
OperationalMemoryFactoryError: initialized factory-run identity changed
```

Exception envelope hard-coded `database_writes: 0` even after campaign rows and
source requests were written. Failure terminalization passed the pre-generated
factory UUID and reported `lifecycle_started=true` without durable factory entry.

### After (repaired)

```text
result = owner.run_operational(...)
lifecycle = dict(result.lifecycle)
if result.lifecycle_started:
    returned = extract_factory_run_id(lifecycle)  # never campaign-run shaped
    if returned:
        retain_factory_run_id(returned)           # fail-closed equality retained
# heartbeat handling...
if not result.lifecycle_started:
    return pre_lifecycle_finalize(...)            # no factory retain on this branch
```

Owner pre-lifecycle shortage/block returns:

| Field | Before | After |
| --- | --- | --- |
| `run_id` | `command.run_id` (campaign-run) | omitted |
| `campaign_run_id` | absent | `command.run_id` |
| factory identity | ambiguous via `run_id` | none |
| `lifecycle_started` | `False` | `False` |

Failure terminalization passes `factory_run_id` only when
`factory_identity_retained` is true (genuine lifecycle insert/retain). Exception
envelope:

| State | Mutation reporting |
| --- | --- |
| `action_run_id` set | `database_writes=null`, `database_mutation_known=false`, `database_mutation_status=UNKNOWN_ON_EXCEPTION` |
| no action identity | `database_writes=0`, `database_mutation_known=true`, `PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY` |

## Focused test results

Command surface (offline, disposable DBs only):

```text
tests/test_v2_9_8b_post_rollover_2_pre_lifecycle_factory_run_identity_and_terminal_contract_repair.py
  8 passed

tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py
  + ActionLocalBlockedCountersTests
  + pre-lifecycle / lifecycle_started regressions from E.47
  26 passed, 37 deselected

tests/test_v2_9_8b_exact_offline_public_composition_lifecycle_entry_harness.py
  9 passed
```

### Proof coverage map

| # | Requirement | Result |
| --- | ---: | --- |
| 1 | Pre-lifecycle `SOURCE_VISIBILITY_SHORTAGE` terminates without identity exception | PASS |
| 2 | Campaign-run ID never retained as factory-run ID | PASS |
| 3 | `lifecycle_started=False` honored before factory retain | PASS |
| 4 | No factory run / slot / step / campaign window / memory window fabricated | PASS |
| 5 | Shortage remains first terminal cause | PASS |
| 6 | Lifecycle reporting stays false | PASS |
| 7 | Cleanup / lease release remain clean | PASS |
| 8 | Genuine lifecycle entry retains initialized factory UUID | PASS |
| 9 | Real factory UUID mismatch still fails closed | PASS |
| 10 | Exact offline public-composition success intact | PASS (9/9) |
| 11 | Exception envelope no longer falsely claims zero DB mutation with action identity | PASS |
| 12 | Retrieval / decisions / positions / trades / audits / PnL remain locked | PASS (locked-table zero checks + no capability unlock) |

## Preserved shortage terminal behavior

- First terminal cause remains the owner-returned shortage/block cause
  (`SOURCE_VISIBILITY_SHORTAGE` in the focused shortage fixture).
- Pre-lifecycle finalizer still uses `factory_run_id=None` and
  `lifecycle_started=False`.
- No automatic retry, restart, resume, or successor is created.
- Eligibility floors, discovery budgets, and shortage classification logic were
  not modified.

## Lifecycle / factory identity proof

| Case | Behavior |
| --- | --- |
| Pre-lifecycle with legacy `run_id=campaign-run` | no retain; clean shortage terminal |
| Pre-lifecycle with repaired `campaign_run_id` only | no factory identity exposed |
| Lifecycle entry with initialized UUID | retain succeeds via `factory_run_initialized` and post-return extract |
| Lifecycle entry with wrong UUID | `initialized factory-run identity changed` fail-closed |
| Failure without retain | terminalization does not inflate `lifecycle_started` from pre-generated UUID alone |

## Exception-envelope result

| Scenario | `database_writes` | `database_mutation_known` | Status field |
| --- | --- | --- | --- |
| `run` exception after action identity | `null` | `false` | `UNKNOWN_ON_EXCEPTION` |
| `preflight-only` exception (no action identity) | `0` | `true` | `PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY` |

## Money-usefulness contribution

This repair restores honest operator signal on thin-market pre-lifecycle stops.
A real `SOURCE_VISIBILITY_SHORTAGE` can terminalize without being masked as a
factory-identity fault. That:

1. prevents false repair work on identity when the market is empty;
2. preserves one-use authorization economics (no wasteful “identity crash”
   misdiagnosis consuming the next readiness cycle for the wrong reason);
3. keeps lifecycle reporting truthful so later readiness and corpus reporting do
   not claim collection that never started.

It does **not** create clean memory, retrieval value, paper decisions, or PnL.

## What improved

- Coordinator separates `campaign_run_id` from `factory_run_id` at retain time.
- Pre-lifecycle shortage/block paths no longer hard-fail on identity retain.
- Lifecycle reporting no longer inflates from a mere pre-generated UUID.
- CLI exception envelopes stop claiming zero DB writes after campaign creation.
- Fail-closed factory UUID equality remains for genuine lifecycle entry.

## What remains locked

- retrieval activation
- paper decisions / BUY / SELL / HOLD
- paper positions, trade events, paper audits, PnL
- live wallet / private keys / real funds / live execution
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- 1h / 4h / 12h / 24h production continuation under the consumed authorization
- automatic retry / resume / restart / successor under that authorization
- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`
- any new authorization until the next readiness audit PASSes

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Market supply remains thin.** After this repair, a later authorized attempt
   may still terminalize cleanly on `SOURCE_VISIBILITY_SHORTAGE` without 15m
   collection. That is expected operational honesty, not a residual identity bug.
2. **Historical lifecycle reports still place factory UUID in `run_id`.**
   Extraction keeps that working after lifecycle entry while rejecting
   campaign-run shapes. Future cleanup may make `factory_run_id` exclusive.
3. **Exception envelopes still cannot always compute exact write totals** without
   a heavier delta scan; unknown is preferred over a false zero.
4. **Authorization economics:** the prior authorization is permanently consumed.
   Progress requires this PASS closeout → fresh readiness audit → **new**
   exact-HEAD one-use authorization only if readiness PASSes.
5. **No wrapper/live campaign was re-run** in this lane (by design). Live proof
   of the repaired path waits for readiness + new authorization.

## Exact next lane

```text
V2-9.8B Post-Rollover-2 Repaired Authoritative WINDOW_15M Current-HEAD Readiness Audit
```

No authorization may be created until that fresh readiness audit PASSes.

## Stop condition

This lane stops after the repair closeout commit. No wrapper execution, provider
contact, authorization creation, or live 15m/1h/4h memory window is authorized.
