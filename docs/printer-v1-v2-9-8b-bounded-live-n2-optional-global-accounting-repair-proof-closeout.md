# Printer V1 V2-9.8B Bounded Live N2 Optional-Global Accounting Repair Proof Closeout

Date: 2026-07-29

Starting and launch HEAD:
`f5e23d59c22df3cd40c2eb8bd10b31c0fb661f47`

Required authoritative DB starting SHA-256:
`688aa243efe82d1d034bac2f46181ab929a0874400ed9be3709ac29fd7555275`

Lane:
`V2-9.8B Bounded Live N2 Optional-Global Accounting Repair Proof`

## Verdict

`V2_9_8B_BOUNDED_LIVE_N2_OPTIONAL_GLOBAL_ACCOUNTING_REPAIR_PROOF_BLOCKED`

The exact canonical `ACQUISITION_ONLY_N2` command ran once and terminalized
`BLOCKED` on `OBSERVATION_ROW_CEILING`.

The repaired optional-global accounting boundary live-proved correctly before
that terminal stop. One optional-global `pumpfun_migration_transaction`
performed exactly one real `getTransaction`, normalized exactly one operation
detail, persisted exactly one durable transport-operation row, and failed
categorically as `UNSUPPORTED_PUMP_CONTRACT`. Local decoding, validation, and
contract checks created no second transport operation. The optional result
remained diagnostic with `required=false`, `admission_authority=NONE`, and
`universal_failure_contribution=false`.

The integration continued through unrelated work. It then consumed 65
normalized observation rows against the unchanged ceiling of 64 and failed
closed. This is an honest bounded budget exhaustion, not an operation-accounting
defect, provider failure, candidate rejection, pruning result, or permission to
raise the ceiling.

No patch, retry, restart, recovery, cursor action, N7, campaign, or successor
ran.

## Source-grounded blocker classification

```text
BLOCKER CLASSIFICATION: EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE
PRIMARY TERMINAL CLASS: HONEST_BUDGET_EXHAUSTION
FIRST TERMINAL CAUSE: OBSERVATION_ROW_CEILING
COMMITTED ACCOUNTING DEFECT REPRODUCED: NO
CODE CHANGE JUSTIFIED: NO
AUTHORIZATION STATUS: the one live N2 authorization was consumed
MINIMUM SAFE RESPONSE: preserve terminal evidence and close BLOCKED
```

The committed row ceiling was 64. Durable work and the terminal report both
record 65 normalized rows. The ceiling was not altered before, during, or after
the run.

## Preflight and backup

Every hard preflight gate passed before the first source call.

| Gate | Result |
| --- | --- |
| exact clean HEAD / untracked files | required HEAD / zero |
| authoritative starting DB hash | exact required hash |
| migration ledger | 49 migrations; latest 049 |
| SQLite runtime | 3.53.4; threadsafety 3 |
| SQLite integrity / FK | `ok` / zero |
| journal / sidecars | `delete` / zero |
| Printer process / DB handle | zero / zero |
| active acquisition lease / integration | zero / zero |
| active Scheduler / campaign work | zero / zero |
| RPC configuration | present and valid HTTPS; value not printed |
| built-in preflight | `V2_9_8_OPERATIONAL_PREFLIGHT_READY` |
| active runtime capacity / cohort bound | 2 / `M=4` |

The fresh backup is:

`/private/tmp/printer-v1-optional-global-accounting-live-n2.t9SZ2f/printer_v1.pre-n2.backup.sqlite3`

Source and backup were each 64,692,224 bytes and byte-identical. Both had
SHA-256:

`688aa243efe82d1d034bac2f46181ab929a0874400ed9be3709ac29fd7555275`

The backup independently passed migration 049, journal `delete`, integrity
`ok`, zero foreign-key violations, and zero sidecars.

## Pinned contracts and unchanged bounds

| Contract | Exact pin |
| --- | --- |
| Pump Program ID | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` |
| PumpSwap Program ID | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |
| Pump IDL SHA-256 | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| PumpSwap IDL SHA-256 | `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56` |
| official repository commit | `9c82f61cb711b044a17f770ab8ce9f9bdf78f333` |
| SPL Token Program ID | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` |
| Token-2022 Program ID | `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` |
| cursor decoder | `canonical-live-acquisition-v1` |

N2 remained selection capacity 2, candidate limit 4, duration 180 seconds,
governed-request ceiling 24, transport-operation ceiling 32, byte ceiling
16,777,216, row ceiling 64, and Scheduler-job ceiling 24. The active runtime
capacity remained exactly two. The committed candidate-specific migration
verification capacity remained one slot. No request-kind budget changed.

## Exactly one live invocation

The required public command ran exactly once:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Field | Result |
| --- | --- |
| exit / wall time | 0 / 22.0112 seconds |
| durable duration | 21,319 milliseconds |
| execution ID | `20260729T210445Z-acq-0cc4c41f8e82` |
| integration ID | `cain-70684bc766301f6a5e4ddaffc2a03c72` |
| status | `BLOCKED` |
| first cause / detail | `OBSERVATION_ROW_CEILING` / same |
| retry / restart / successor | false / false / false |
| recovery / N7 / campaign | not run / not run / not run |
| lifecycle / runtime handoff | false / 0 |

## Mandatory repaired-boundary live proof

Optional-global work ordinal 9 was
`pumpfun_migration_transaction`.

```text
ordered predeclared identity:
  solana_rpc / pumpfun_migration_transaction / work 9 /
  transport 1 / getTransaction

actual low-level attempts:       1
normalized operation details:    1
durable transport-operation rows: 1
terminal report contribution:    1
zero-source replay contribution: 1
```

Exact durable result:

| Field | Result |
| --- | --- |
| required source | false |
| Scheduler state | `FAILED` |
| Source Governor request | persisted |
| Source Governor failure | persisted |
| source failure | `UNSUPPORTED_PUMP_CONTRACT` |
| acquisition work state | `FAILED` |
| operation kind / state | `getTransaction` / `COMPLETE` |
| redacted endpoint role | `PUMP_MIGRATION_TRANSACTION_1` |
| operation rows | 1 |
| bytes | 15,302 |
| normalized rows | 0 |
| duplicate operation identities | 0 |
| local checks counted as transport | 0 |

There was no fabricated failed `ATTEMPTED_TRANSPORT` detail. Local Pump decoding
rejected the already-returned response without creating another operation.

The observer result remained:

```text
observer_status=GLOBAL_PUMP_OBSERVER_BLOCKED_CONTRACT
required=false
admission_authority=NONE
universal_failure_contribution=false
```

The integration continued through mint, pool, holder, and safety work. This
proves that an exactly accounted optional contract failure cannot block
unrelated branches. The later universal stop came only from the genuine
65-over-64 row-ceiling breach.

## Scheduler, Governor, work, transport, report, and replay reconciliation

| Evidence layer | Exact total |
| --- | ---: |
| Scheduler jobs | 22 |
| Scheduler succeeded / failed | 20 / 2 |
| Source Governor requests | 22 |
| governed responses / failures | 21 / 1 |
| acquisition work rows | 22 |
| work succeeded / failed | 20 / 2 |
| transport operations | 23 |
| transport bytes | 176,086 |
| normalized rows | 65 |

Every total above equals the corresponding integration row, durable work sum,
durable transport-operation count/sum, terminal report, and zero-source replay.
All 22 executed work items reconciled their ordered operation identities.
Identity mismatches and frozen synthesized live details were both zero.

Work ordinal 22 persisted its Source Governor response, work row, exact
transport operation, 918 bytes, one row, failed Scheduler state, and first
terminal cause `OBSERVATION_ROW_CEILING`. Planned work ordinal 23 was not
scheduled after the universal stop.

The repair's fail-closed guard was not weakened. A genuine identity mismatch or
operation/row/byte/request ceiling breach remains universal; this run exercised
the row-ceiling path.

## Observer and cursor preservation

The global Pump observer remained optional and non-authoritative. Its preserved
historical gap is:

```text
authoritative head slot: 435985595
frozen tip slot: 435999023
last recovery continuation slot: 435998983
pages inspected: 44
signatures inspected: 11000
exact prior boundary reached: false
terminal reason: CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED
cursor mutation performed: false
```

The four durable cursor rows had identical pre/post canonical snapshot hash:

`2d701dad15a80f26fcd54252d990afc384b582e3dc77def1076200a2e46731c3`

All preserved recovery rows were byte-identical:

| Recovery surface | Rows | Canonical snapshot SHA-256 |
| --- | ---: | --- |
| integrations | 12 | `ddc59c68a5be6cf0230b1924629f7b81ee14ac79e2e82de71855fb69daf9e0a6` |
| leases | 12 | `a287b26bd5bd59ed7669c0ada1dc20235cb213fb8484a953c96d27cab5c1ca67` |
| work | 89 | `7f8ed2251fd7fae9dd6d29cd5d2fb7221ab58470e8323a965b05c54ecd500317` |
| reports | 12 | `4a0bc2e2ba65b7b600067dd0f47a12903c4d0a0c6265458f2436613f7f79cd2f` |

There was no recovery continuation, cursor reset, overwrite, rewind,
checkpoint adoption, proposed advance, or committed advance.

Only Pump create and optional-global Pump migration work carried cursor-range
JSON. Candidate mint, pool, migration verification, holder, safety, market,
liquidity, and tradeability work carried none. No candidate observation,
observation link, source round, evidence row, or cursor range was created, so
global ranges did not attach to unrelated candidate evidence.

## Nomination, cohort, and enrichment boundary

The live union produced:

| Funnel field | Result |
| --- | ---: |
| overall normalized/work rows | 65 |
| normalized nomination rows | 42 |
| raw unique nominations | 42 |
| DexScreener nomination rows | 23 |
| GeckoTerminal nomination rows | 17 |
| direct Solana nomination rows | 2 |
| cross-source overlap | 0 |
| deterministic cohort bound | 4 |
| finalized cohort constructed | 0 |
| tentative enrichment identities | 4 |
| terminal report out-of-cohort enrichment | 4 |
| thinned beyond cohort | 0 |

The terminal stop occurred before formal cohort construction and foundation
classification. The live transport had targeted the first four deterministic
nomination identities for enrichment, but because the row ceiling fired before
the cohort was finalized, the terminal report correctly does not claim those
identities as a constructed cohort and records all four as out-of-cohort.
Therefore the zero-out-of-cohort PASS requirement was not met.

No source preference, quota, score, rank, confidence, or weighting selected
those identities. No candidate-specific migration locator ran because there was
no finalized Pump graduation candidate. The committed one-slot verification
budget remained unchanged and unused. No fallback locator was attempted.

## Branch distribution

There was no legitimate finalized branch classification:

```text
PUMP_GRADUATION_CLAIMED: 0 (not reached)
PUMP_ACTIVE_BONDING_CURVE: 0 (not reached)
NO_PUMP_GRADUATION_CLAIM: 0 (not reached)
lineage conflict: 0 (not reached)
```

These zeros do not assert absence. They mean classification was not reached.
No active Pump curve was forced through migration lookup, no generic or unknown
candidate was made dependent on global migration continuity, PumpSwap presence
did not establish graduation, and no failed Pump claim downgraded.

## Mint, pool, holder, safety, and later gates

Tentative cohort-targeted enrichment returned:

| Check | Result |
| --- | --- |
| mint observations | 4 |
| exact target association | 4 |
| mint/layout/owner/program validation pass | 4 |
| SPL Token | 1 |
| Token-2022 | 3 |
| pool observations | 4 |
| exact positional association | 4 |
| base-mint and WSOL quote match | 4 |
| pool pass | 0 |
| pool fail | 4, all `POOL_PROGRAM_NOT_EXECUTABLE` |
| holder outcomes | 2 pass / 2 fail |
| safety observations before stop | 3 |
| explicit safety failures | 0 |
| safety unknown/no adopted risk fact | 3 |

Because the row ceiling stopped the integration before formal cohort and
foundation assembly, there were no authoritative age, liquidity, market,
tradeability, tracking, or cooldown gate outcomes. The fourth planned safety
work item did not run.

## Admission funnel

| Field | Result / delta |
| --- | ---: |
| foundation executions | 0 |
| certificates issued | 0 |
| certificates admitted | 0 |
| reserve rows | 0 |
| manifests | 0 |
| manifest items | 0 |
| selected | 0 |
| projection | 0 |
| runtime handoff | 0 |

The PASS requirements for two admitted certificates, one exact two-item
manifest, projection two, and terminal integration `COMPLETED` were not met.

## Compact storage and zero-source replay

- the two global signature-page rows stored compact summaries and page hashes;
- both retained `positive_matching_signatures=[]`;
- no full unrelated program-wide signature array appeared in a governed
  response/failure, work row, or report;
- terminal report hash:
  `c60acb214f984ae746ad6817b338a7d238aed87fafb34c76b760b055ef492ec2`;
- replay identity:
  `1f80ec583e0bc80599556e58811ba3a0ff6f3d275fe15061e38f193496e51f16`;
- zero-source replay returned the exact status, first cause, observer result,
  operation accounting, Scheduler/Governor/transport totals, bytes, rows,
  projection, and handoff;
- the authoritative DB hash remained
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
  across replay.

## Postflight, cleanup, and deltas

Authoritative post-live DB:

```text
SHA-256: e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6
bytes: 64,827,392
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

Authorized evidence deltas:

- N2 integrations / leases / reports: +1 / +1 / +1;
- acquisition work / transport rows: +22 / +23;
- Scheduler jobs: +22;
- Source Governor requests / responses / failures: +22 / +21 / +1.

Foundation and protected deltas:

- N7 integrations: 0;
- foundation executions: 0;
- certificates: 0;
- manifests and items: 0;
- reserve, identities, evidence, observation links, source observations,
  source rounds, and cursor ranges: 0;
- every protected tracking, snapshot, window, memory, retrieval, decision,
  position, trade, audit, and PnL delta: 0; and
- all 22 protected table snapshots were byte-identical to the backup.

The complete protected baseline and pre/post hashes are in the redacted
evidence artifact.

## Redacted evidence

The redacted evidence artifact is:

`docs/printer-v1-v2-9-8b-bounded-live-n2-optional-global-accounting-repair-proof-redacted.json`

It contains no candidate address, raw address, raw signature, raw provider
payload, secret, program ID, or complete endpoint URL.

## What was not touched

No Python, configuration, migration, schema, provider selection, source plan,
ceiling, candidate-verification capacity, cursor policy, cursor row, recovery
row, tracking handoff, lifecycle, snapshot, window, memory, retrieval, decision,
BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, transaction
submission, funds, paid source, score, rank, confidence, weighting, quota,
embedding, or vector capability changed.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The fixed 64-row ceiling was honestly exhausted by 65 normalized rows before
   formal cohort construction. This proof does not establish live admission,
   certificates, exact-two manifest formation, or projection.
2. Four tentative enrichment identities were processed before the terminal
   cohort was formalized. The report therefore records four out-of-cohort
   enrichment identities and cannot satisfy the zero-out-of-cohort PASS gate.
3. All four tentative pool checks failed because the observed pool-owner
   programs were not proven executable in the returned evidence. No candidate
   reached formal admission.
4. The optional global historical gap remains real. Exact accounting makes its
   contract failure diagnostic; it does not make the coverage complete.
5. Current provider yield can vary. No source or row ceiling may be raised, and
   no retry is authorized merely to obtain a smaller nomination set.

## Exact next permitted task

Operator review of this terminal BLOCKED closeout and redacted evidence.

No automatic run, retry, recovery, cursor action, N7, campaign, successor,
source/budget change, or later runtime lane is authorized.
