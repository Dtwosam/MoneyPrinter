# Printer V1 V2-9.8B Bounded Live N2 Pump Migration Decoupling Proof Closeout

Date: 2026-07-29

Starting and launch HEAD:
`cf5622f09788715ae33e58a2dcaa7a548b83e569`

Required authoritative DB starting SHA-256:
`36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09`

Lane:
`V2-9.8B Bounded Live N2 Pump Migration Observation Decoupling Proof`

## Verdict

`V2_9_8B_BOUNDED_LIVE_N2_PUMP_MIGRATION_DECOUPLING_PROOF_BLOCKED`

The exact canonical `ACQUISITION_ONLY_N2` command ran once and terminated
`BLOCKED` on `OPERATION_ACCOUNTING_MISMATCH`.

The immediate source outcome was an honest optional-global
`UNSUPPORTED_PUMP_CONTRACT` failure. Its normalized evidence recorded two
underlying operations against the work item's declared ceiling of one. The
integration converted that mismatch into a universal terminal error before
optional-failure isolation. Consequently, the optional global observer blocked
the run before deterministic cohort construction.

This is a systemic implementation defect in the committed live accounting
boundary, not a candidate, market, provider-availability, pruning, or budget
outcome. No patch, retry, restart, recovery, N7, campaign, or successor ran.

## Preflight and backup

Every hard preflight gate passed before the source call.

| Gate | Result |
| --- | --- |
| exact clean HEAD / untracked files | required HEAD / zero |
| authoritative starting DB hash | exact required hash |
| migration ledger | 49 migrations; latest 049 |
| SQLite | 3.53.4; integrity `ok`; FK violations zero |
| journal / sidecars | `delete` / zero |
| Printer process / DB handle | zero / zero |
| active acquisition lease / integration | zero / zero |
| active Scheduler / campaign work | zero / zero |
| RPC configuration | present and valid HTTPS; value not printed |
| built-in preflight | `V2_9_8_OPERATIONAL_PREFLIGHT_READY` |
| active runtime capacity / cohort bound | 2 / `M=4` |

The fresh backup is:

`/private/tmp/printer-v1-pump-decoupling-live-n2.0TucbY/printer_v1.pre-n2.backup.sqlite3`

Source and backup were each 64,618,496 bytes and byte-identical. Both had
SHA-256:

`36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09`

The backup independently passed migration 049, journal `delete`, integrity
`ok`, and zero foreign-key violations.

## Pinned contracts and unchanged bounds

| Contract | Exact pin |
| --- | --- |
| Pump Program ID | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` |
| PumpSwap Program ID | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |
| Pump IDL SHA-256 | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| PumpSwap IDL SHA-256 | `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56` |
| official repository commit | `9c82f61cb711b044a17f770ab8ce9f9bdf78f333` |
| cursor decoder | `canonical-live-acquisition-v1` |

The N2 policy remained selection capacity 2, candidate limit 4, duration 180
seconds, governed-request ceiling 24, transport-operation ceiling 32, byte
ceiling 16,777,216, row ceiling 64, and Scheduler-job ceiling 24. All
request-kind budgets remained the committed values. The one candidate
migration-verification slot was not increased.

SPL Token and Token-2022 program/layout support remained pinned and unchanged.
The terminal run did not reach mint enrichment, so it produced no new live
support result for either program.

## Exactly one live invocation

The required public command ran exactly once:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Field | Result |
| --- | --- |
| exit / wall time | 0 / 8.9756 seconds |
| execution ID | `20260729T200835Z-acq-2849418f5f07` |
| integration ID | `cain-754abcd6eaa47248a63820d8e8f812c2` |
| status | `BLOCKED` |
| first cause / detail | `OPERATION_ACCOUNTING_MISMATCH` / same |
| retry / restart / successor | false / false / false |
| recovery / N7 / campaign | not run / not run / not run |
| lifecycle / runtime handoff | false / 0 |

## Exact systemic blocker

The first eight work items completed. Work item nine was optional-global
`pumpfun_migration_transaction` with `required=false`.

The source failure was:

```text
failure type: UNSUPPORTED_PUMP_CONTRACT
declared operation ceiling: 1
normalized underlying operation count: 2
normalized operation detail count: 2
normalized failure bytes: 8463
```

The operation-accounting guard ran before the optional observer could be
classified as non-authoritative failure. It therefore raised
`OPERATION_ACCOUNTING_MISMATCH`, failed Scheduler job nine, omitted a durable
work row for that operation, and stopped the integration.

The committed requirement that optional global observer failures never
universally block candidate admission is not live-proved. In this exact case it
is disproved by the accounting path. No repair was made after terminal
evidence.

## Global observer and cursor state

The terminal report still states:

- observer state `GLOBAL_PUMP_OBSERVER_GAPPED`;
- `required=false`;
- `admission_authority=NONE`;
- `universal_failure_contribution=false`;
- two established cursor heads loaded;
- no bootstrap;
- zero proposed and zero committed advances.

The preserved historical gap remains:

```text
authoritative migration head slot: 435985595
frozen tip slot: 435999023
last recovery continuation slot: 435998983
pages inspected: 44
signatures inspected: 11000
exact prior boundary reached: false
terminal reason: CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED
```

All four durable cursor rows are byte-identical before and after. The twelve
recovery integrations, 89 recovery work rows, and twelve recovery reports are
also byte-identical. No recovery continuation, cursor reset, overwrite, rewind,
or checkpoint adoption occurred.

No global cursor range attached to a candidate mint, pool, holder, liquidity,
or tradeability observation because the run stopped before enrichment.

## Nomination, cohort, and branch boundary

The live source union produced:

| Funnel field | Result |
| --- | ---: |
| normalized rows | 44 |
| raw unique nominations | 40 |
| DexScreener nomination rows | 19 |
| GeckoTerminal nomination rows | 19 |
| direct Solana nomination rows | 2 |
| deterministic cohort bound | 4 |
| cohort constructed | 0 |
| enrichment identities | 0 |
| out-of-cohort enrichment | 0 |

The accounting failure occurred before deterministic `M=4` thinning. Therefore
there were no cohort candidates and no legitimate branch distribution:

```text
PUMP_GRADUATION_CLAIMED: 0
PUMP_ACTIVE_BONDING_CURVE: 0
NO_PUMP_GRADUATION_CLAIM: 0
lineage conflict: 0
```

These zeros mean `not reached`; they do not assert that no nominated candidate
belonged to a branch. No branch, migration, absence, or graduation fact was
manufactured.

Candidate-specific signature lookup, candidate transaction verification, and
candidate PumpSwap verification each ran zero times. There was no fallback
locator, hidden retry, Pump graduation claim, or PumpSwap-presence-only claim.

## Admission result

The terminal run did not reach:

- deterministic cohort-only enrichment;
- exact mint target/response association;
- SPL Token or Token-2022 live validation;
- exact pool/base/quote validation;
- holder, safety, market, age, liquidity, or tradeability gates;
- tracking/cooldown recheck;
- branch classification;
- foundation certificates, reserve, or selection.

Final admission counts:

| Field | Result |
| --- | ---: |
| foundation executions | 0 |
| certificates issued | 0 |
| certificates admitted | 0 |
| manifests | 0 |
| manifest items | 0 |
| selected | 0 |
| projection | 0 |
| runtime handoff | 0 |

The PASS requirements were not met.

## Accounting reconciliation

The terminal report contains:

```text
Scheduler jobs: 9
governed requests used: 8
transport operations used: 9
bytes used: 136135
normalized rows: 44
```

Durable source evidence contains:

```text
Scheduler jobs: 9 = 8 SUCCEEDED + 1 FAILED
source requests: 9
source responses: 8
source failures: 1
persisted work rows: 8, all SUCCEEDED
persisted successful transport operations: 9
terminal failed-request underlying operations: 2
reconstructed transport operations: 11
persisted successful bytes: 136135
terminal failure bytes: 8463
reconstructed bytes: 144598
```

Request-kind counts:

| Request kind | Count |
| --- | ---: |
| `candidate_nomination` | 2 |
| `candidate_market_batch` | 2 |
| `pumpfun_create_index_signature_page` | 1 |
| `pumpfun_create_index_transaction` | 2 |
| `pumpfun_migration_signature_page` | 1 |
| `pumpfun_migration_transaction` | 1 |

Scheduler, Source Governor, work, operation, and report totals do not reconcile
because the terminal optional-global failure was rejected before work
persistence and cumulative report accounting. This is part of the systemic
defect, not an acceptable terminal accounting result.

## Compact storage and replay

The successful global signature-page rows stored compact page summaries,
hashes, cursor facts, and empty exact-positive-match lists. No full unrelated
program-wide signature array appears in source-response normalized payloads,
work JSON, or report JSON.

The public zero-source replay reproduced the exact terminal report with:

- report hash
  `2562fd8d6458fcde9d36a3d0b3211697b5529022832a5de35e6dd60228b5ae43`;
- replay identity
  `19f37f3d0fd8e409ce14a29e0e5b10b6bace22347eeb26b659f686d17dd9eb36`;
- zero new provider or transport calls.

## Postflight and protected deltas

Authoritative post-live DB:

```text
SHA-256: 688aa243efe82d1d034bac2f46181ab929a0874400ed9be3709ac29fd7555275
bytes: 64692224
journal mode: delete
integrity: ok
foreign-key violations: 0
```

Cleanup:

- active Printer processes: 0;
- open DB handles: 0;
- SQLite sidecars: 0;
- active acquisition leases: 0;
- active acquisition integrations: 0;
- active Scheduler jobs: 0;
- active campaign work: 0; and
- Scheduler residue: 0.

Database deltas:

- N2 integrations: +1;
- N7 integrations: 0;
- foundation executions: 0;
- certificates: 0;
- manifests: 0;
- every protected tracking, snapshot, window, memory, retrieval, decision,
  position, trade, audit, and PnL delta: 0; and
- every protected row set is byte-identical to the backup.

## Redacted evidence

The redacted evidence artifact is:

`docs/printer-v1-v2-9-8b-bounded-live-n2-pump-migration-decoupling-proof-redacted.json`

It contains no candidate mint, raw address, raw signature, raw provider
payload, secret, program ID, or complete endpoint URL.

## What was not touched

No Python, configuration, migration, schema, source plan, provider selection,
ceiling, candidate-verification capacity, cursor policy, cursor row, recovery
row, tracking handoff, lifecycle, snapshot, window, memory, retrieval, decision,
BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, transaction
submission, funds, paid source, score, rank, confidence, weighting, quota,
embedding, or vector capability changed.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Optional-global failure is not fully decoupled from universal accounting.
   An unsupported global migration transaction can still stop unrelated
   candidate branches before cohort construction.
2. The failed optional operation is absent from durable work and cumulative
   report totals, so Scheduler/Source Governor/transport accounting is
   incomplete even though the source failure itself is preserved.
3. The source failure recorded two operations against a declared ceiling of
   one. The live proof does not establish whether the intended accounting fix
   is deduplication, a different declared bound, or a different local-parse
   representation; that requires a source-grounded design, not an ad hoc patch.
4. Candidate-specific Pump migration verification, branch independence, mint
   and pool enrichment, categorical admission, and exact-two formation were not
   reached live.
5. The historical global migration gap remains unresolved and non-authoritative.
6. Live source yield and later admission gates remain unproved beyond the 40
   nomination identities observed before the stop.

## Exact next permitted task

Operator review of this terminal BLOCKED closeout and redacted artifact.

Only if separately and explicitly authorized, the next technical task is:

```text
V2-9.8B documentation-only audit and design of optional-global
pumpfun_migration_transaction operation accounting
```

That future task must determine why one returned unsupported transaction
produced two operation details, define exact failed-operation persistence and
report reconciliation, and preserve optional observer non-authority. This
closeout does not authorize a repair, retry, recovery, N7, campaign, source or
budget change, cursor mutation, or later runtime lane.
