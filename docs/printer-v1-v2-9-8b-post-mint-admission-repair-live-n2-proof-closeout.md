# Printer V1 V2-9.8B Post Mint-Admission-Repair Bounded Live N2 Proof Closeout

Date: 2026-07-29

Starting HEAD: `50e45a0c695995da3b74976137950cfb746b55cd`

Lane: `V2-9.8B Post Mint-Admission-Repair Bounded Live N2 Proof`

## Verdict

`V2_9_8B_POST_MINT_ADMISSION_REPAIR_LIVE_N2_PROOF_BLOCKED`

Exactly one canonical public `ACQUISITION_ONLY_N2` execution ran. It completed
all 20 governed source/Scheduler work items, formed the repaired `M=4` cohort,
and collected exact cohort-only enrichment, including four valid extended
Token-2022 mint-account observations. It then blocked before foundation
admission with the earliest terminal cause `CURSOR_START_MISMATCH`.

The current live transport proposed `null` start slot/signature values for
cursor namespaces that already had durable non-null heads. The first mismatch
was the Pump-create index namespace. The foundation transaction rolled back,
so no admission stage, certificate, manifest, cursor advance, projection, or
runtime handoff persisted.

There was no retry, restart, successor, N7 run, code/configuration change,
ceiling change, provider substitution, campaign, tracking/lifecycle start,
snapshot, window, memory, retrieval, decision, position, trade, audit, or PnL
work.

## Preflight

| Check | Result |
| --- | --- |
| exact HEAD | `50e45a0c695995da3b74976137950cfb746b55cd` |
| worktree/index/untracked inventory | clean |
| authoritative DB | `data/printer_v1.sqlite3` |
| authoritative starting SHA-256 | `08fb9d202bf60f258779041e85d79a5c65e789ea1bddb67745b218df588ba1db` |
| authoritative starting size | 17,018,880 bytes |
| migration ledger | 49 canonical rows; latest `049_candidate_acquisition_integration.sql` |
| integrity / foreign keys | `ok` / zero violations |
| journal mode | `delete` |
| active Printer process | none |
| active campaign/run/supervision/discovery/factory/proof work | all zero |
| active or locked Scheduler work | zero |
| active acquisition lease | zero |
| SQLite open handle / writer | none |
| SQLite WAL/SHM/journal sidecars | none |
| HTTPS RPC configuration | present and structurally valid; value not printed or persisted |
| canonical public preflight | `V2_9_8_OPERATIONAL_PREFLIGHT_READY`; zero source calls/writes |

The preflight also re-confirmed active runtime capacity exactly two, zero
automatic retries, Source Governor readiness, dependency readiness, and the
preserved historical locked-capability baseline.

## Fresh Backup

Host-only proof directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260729T154828Z-post-mint-admission-repair-live-n2`

Backup:

`printer_v1.pre-n2.backup.sqlite3`

| Evidence | Result |
| --- | --- |
| backup SHA-256 | `08fb9d202bf60f258779041e85d79a5c65e789ea1bddb67745b218df588ba1db` |
| backup size | 17,018,880 bytes |
| source/backup byte-hash equality | PASS |
| backup migration | 49 rows; latest migration 049 |
| backup integrity / FK | `ok` / zero violations |

The backup, database, secrets, raw source payloads, and complete RPC URL remain
outside the commit.

## Protected Baseline

| Protected surface | Before | After | Delta |
| --- | ---: | ---: | ---: |
| tracking queue | 29 | 29 | 0 |
| token snapshots | 1,054 | 1,054 | 0 |
| memory windows | 160 | 160 | 0 |
| episodes / outcomes / episode snapshots | 57 / 23 / 107 | 57 / 23 / 107 | 0 |
| memory fingerprints / audit reports | 23 / 5 | 23 / 5 | 0 |
| retrieval queries / matches | 10 / 0 | 10 / 0 | 0 |
| paper decisions | 2 | 2 | 0 |
| paper positions | 0 | 0 | 0 |
| paper trade events / audits | 0 / 0 | 0 / 0 | 0 |
| paper audit reports | 1 | 1 | 0 |
| Memory Factory campaigns / runs / cycles / slots / windows | 17 / 17 / 17 / 14 / 2 | unchanged | 0 |
| Memory Factory runs / steps | 6 / 54 | unchanged | 0 |

The command's own `forbidden_table_deltas` map and an independent read-only
recount agree that every protected delta is zero.

## Execution Identity

Exactly one invocation used the required command:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Field | Result |
| --- | --- |
| mode | `ACQUISITION_ONLY_N2` |
| execution ID | `20260729T154955Z-acq-adca0293ada0` |
| integration ID | `cain-31044a63424ef54219109918e738a943` |
| command exit code | `0` (terminal report emitted) |
| command wall clock | approximately 18.65 seconds |
| canonical status | `BLOCKED` |
| first terminal cause | `CURSOR_START_MISMATCH` |
| redacted failure-detail SHA-256 | `fe83b050a4a0157c22aafa74d277387b721dfcb04dbd1095a0eb4a16fe395922` |
| integration state | `TERMINAL` |
| foundation execution ID | `null` |
| retry / restart / successor | false / false / false |
| active capacity lock | 2 |

No private injector, proof launcher, direct adapter, legacy path, N7 command,
retry, restart, or successor was used.

## Raw Nomination and Cohort Boundary

| Funnel measure | Count |
| --- | ---: |
| raw observation rows | 58 |
| raw unique nominations | 36 |
| DexScreener nomination rows | 14 |
| GeckoTerminal nomination rows | 20 |
| direct Solana/Pump nomination rows | 2 |
| cohort bound `M` | 4 |
| exact cohort size | 4 |
| thinned beyond cohort | 32 |
| enriched identities | 4 |
| out-of-cohort enrichment | 0 |

The repaired raw nomination to `M=4` boundary passed. Candidate-specific mint,
pool, holder, and optional safety work targeted exactly the four cohort
identities.

## Mint Request/Slot and Decoder Evidence

The mint-account batch was inspected independently from every later identity,
pool, quote, holder, safety, liquidity, and admission category.

| Check | Result |
| --- | --- |
| exact requested targets | 4 |
| exact response slots | 4 (`0, 1, 2, 3`) |
| association mode | `POSITIONAL_RPC_CONTRACT` |
| request target equals candidate key | 4 / 4 |
| account presence | `PRESENT` 4 / 4 |
| adopted owner | PASS 4 / 4 |
| adopted layout | PASS 4 / 4 |
| SPL Token decoded | 0 |
| Token-2022 decoded | 4 |
| mint status | PASS 4 / 4 |
| token-program status | PASS 4 / 4 |
| categorical mint failures | none |

This live sample therefore confirms the post-mint-admission repair on its exact
target/slot/decoder boundary. It does not convert raw transport evidence into a
foundation-stage PASS because foundation admission did not run.

## Cohort Evidence by Separate Category

The committed JSON artifact uses full SHA-256 identity and pool pseudonyms.
The short prefixes below are display-only.

| Identity hash prefix | Present pool observations | Pool program category | Quote identity | Lineage claim | Holder | Safety | Market / age | Liquidity | Tradeability | Tracking / rotation conflict |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `e8fa55ebbf34d827` | 1 | Pump program, not PumpSwap | absent | `UNKNOWN_ORIGIN` | FAIL | PASS | PASS / PASS | FAIL | PASS | 0 / 0 |
| `bc2cfb1b8e3f6728` | 1 | PumpSwap program | absent | `UNKNOWN_ORIGIN` | PASS | PASS | PASS / PASS | PASS | PASS | 0 / 0 |
| `12eddf5be21a039c` | 1 | Pump program, not PumpSwap | absent | `UNKNOWN_ORIGIN` | FAIL | PASS | PASS / PASS | FAIL | PASS | 0 / 0 |
| `d8da2c16ab85efd5` | 1 | Pump program, not PumpSwap | absent | `UNKNOWN_ORIGIN` | FAIL | PASS | PASS / PASS | FAIL | FAIL | 0 / 0 |

Important separations:

- A present pool address was observed for each candidate, but three pool-account
  observations carried the Pump program rather than the PumpSwap program.
- Exact quote-mint identity was absent for all four pool observations. This is
  not reported as a pool absence or mint failure.
- No cohort candidate claimed exact Pump origin or exact joined Pump
  migration/PumpSwap graduation; all remained categorical `UNKNOWN_ORIGIN`.
- Holder evidence was one PASS and three FAIL. Holder failure is not a mint,
  pool, quote, safety, liquidity, tradeability, or cursor failure.
- Raw safety facts were PASS for all four; all four optional GoPlus work items
  completed, but their normalized candidate observations added no separate
  categorical safety fact.
- Market and age facts were PASS for all four. At the exact adopted $3,000
  liquidity floor, liquidity was one PASS and three FAIL. Tradeability was
  three PASS and one FAIL.
- Current persistent-state inspection found zero active tracking rows and zero
  selection-rotation matches for the four cohort identities/pools. The atomic
  foundation recheck had no durable candidate-stage output because the cursor
  exception rolled the transaction back.

None of these later candidate facts is promoted to an admission verdict. The
cursor boundary terminated first.

## Exact Admission Funnel

Foundation admission did not persist or return a report. Every stage is kept
separate and marked honestly:

| Admission stage | Result | Available pre-foundation evidence |
| --- | --- | --- |
| `CHAIN_MINT_VALID` | `NOT_RUN` | four raw mint observations PASS |
| `TOKEN_PROGRAM_VALID` | `NOT_RUN` | four adopted Token-2022 observations PASS |
| `IDENTITY_AVAILABLE` | `NOT_RUN` | one present-pool observation per identity; owner/quote distinctions above |
| `POOL_QUOTE_VALID` | `NOT_RUN` | quote-mint identity absent on all four pool observations |
| `MARKET_FRESH` | `NOT_RUN` | four market observations PASS |
| `AGE_VALID` | `NOT_RUN` | four age observations PASS |
| `HOLDER_ACCEPTABLE` | `NOT_RUN` | one raw PASS, three raw FAIL |
| `SAFETY_ACCEPTABLE` | `NOT_RUN` | four raw safety PASS facts |
| `LIQUIDITY_TRADEABILITY_VALID` | `NOT_RUN` | one raw liquidity PASS, three raw FAIL |
| `ROUTE_TRADEABILITY_VALID` | `NOT_RUN` | three raw PASS, one raw FAIL |
| `LINEAGE_VALID` | `NOT_RUN` | four `UNKNOWN_ORIGIN`; no Pump graduation claim |

Resulting durable admission/selection totals:

| Surface | Result |
| --- | ---: |
| foundation execution delta | 0 |
| certificates issued / admitted / rejected | 0 / 0 / 0 |
| manifest count / items | 0 / 0 |
| selected count | 0 |
| projection count | 0 |
| runtime handoff count | 0 |
| lifecycle started | false |

The absence of certificates is caused by the pre-admission cursor terminal,
not by collapsing the raw holder, quote, pool-program, liquidity, tradeability,
or other evidence into `CURSOR_START_MISMATCH`.

## Cursor Reconciliation and Earliest Terminal Cause

Seven work observations proposed cursor ranges over two durable namespaces.
All proposed ranges were reported `CONTIGUOUS` and requested advancement, but
their start boundaries were unanchored:

| Namespace | Durable start | Proposed start | Proposed end | Result |
| --- | --- | --- | --- | --- |
| Pump-create index (failure-detail SHA-256 `fe83b050…`) | slot `435969990` plus non-null signature | slot `null`, signature `null` | slot `435975784` plus signature | `CURSOR_START_MISMATCH` first |
| Pump-migration index (redacted namespace) | slot `435970004` plus non-null signature | slot `null`, signature `null` | slot `435975793` plus signature | also mismatched, not terminal precedence |

Cursor accounting reconciles exactly:

- proposed range observations: 7;
- committed cursor heads for this execution: 0;
- durable cursor head rows before/after: 2 / 2;
- no durable cursor row has this execution as `last_execution_id`;
- the foundation transaction rolled back all cursor and admission writes;
- terminal report `cursor_advances_proposed=7` and
  `cursor_advances_committed=0` are truthful.

The earliest exact stop is therefore `CURSOR_START_MISMATCH`, not mint failure,
identity merge failure, pool failure, quote failure, holder failure, safety
failure, liquidity failure, tradeability failure, Source Governor failure,
Scheduler failure, provider failure, budget failure, or insufficient eligible
pool.

## Source, Scheduler, and Operation Accounting

| Counter | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Scheduler jobs | 1,157 | 1,177 | +20 |
| source requests | 1,492 | 1,512 | +20 |
| source responses | 1,379 | 1,399 | +20 |
| source failures | 113 | 113 | 0 |
| acquisition integrations | 2 | 3 | +1 |
| acquisition leases | 2 | 3 | +1 terminalized/released |
| acquisition work rows | 36 | 56 | +20 |
| acquisition transport operations | 36 | 57 | +21 |
| integration reports | 2 | 3 | +1 |
| foundation executions | 1 | 1 | 0 |
| certificates / manifests / items | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| cursor heads | 2 | 2 | 0 |

Execution-local reconciliation:

- 20 distinct work rows;
- 20 distinct Scheduler job IDs, all `SUCCEEDED`;
- 20 distinct Source Governor request IDs, all `COMPLETE`;
- 20 distinct source response IDs, all `COMPLETE`;
- zero source-failure links;
- 21 underlying transport operations, all `COMPLETE`;
- 126,030 bytes and 58 rows;
- Scheduler owner `Central Scheduler`;
- source owner `Source Governor`.

All immutable N2 ceilings remained unbreached:

| Ceiling | Used / allowed |
| --- | --- |
| governed requests | 20 / 24 |
| transport operations | 21 / 32 |
| bytes | 126,030 / 16,777,216 |
| rows | 58 / 64 |
| Scheduler jobs | 20 / 24 |
| selection capacity | 0 / 2 |

## Replay and Cleanup

The public DB-backed
`replay_candidate_acquisition_integration_report` path verified the stored
report hash and replay identity and returned the same terminal JSON without
source, Scheduler, transport, or DB mutation.

| Replay/cleanup check | Result |
| --- | --- |
| report hash / replay identity | verified / verified |
| deterministic terminal JSON | equal |
| new source requests / responses / failures | 0 / 0 / 0 |
| new Scheduler jobs | 0 |
| new transport operations / reports | 0 / 0 |
| active acquisition leases | 0 |
| active or locked Scheduler residue | 0 |
| active Printer process | 0 |
| SQLite open handles / sidecars | 0 / 0 |
| post-run integrity / FK | `ok` / zero violations |

Final authoritative DB:

| Field | Result |
| --- | --- |
| SHA-256 | `d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2` |
| size | 17,100,800 bytes |
| latest migration | `049_candidate_acquisition_integration.sql` |
| journal mode | `delete` |
| integrity / FK | `ok` / zero violations |

## Acceptance Result

| Required gate | Result |
| --- | --- |
| canonical `COMPLETED` | FAIL (`BLOCKED`) |
| exactly one execution | PASS |
| raw nomination to `M=4` cohort | PASS (`36 -> 4`) |
| exact cohort-only enrichment | PASS (4; out-of-cohort 0) |
| mint request targets / response slots reconcile | PASS (4; slots 0-3) |
| valid adopted Token-2022 evidence decoded | PASS (4 / 4) |
| precise mint failures | PASS (none observed) |
| at least two admitted certificates | FAIL (foundation not run; 0) |
| one exact two-item manifest | FAIL (0) |
| projection count two | FAIL (0) |
| runtime handoff zero | PASS |
| Scheduler / Source Governor / transport accounting | PASS |
| proposed / committed cursors reconcile | FAIL for successful proof; truthful `7 / 0` with exact mismatch |
| deterministic zero-source replay | PASS |
| leases and Scheduler residue zero | PASS |
| protected-table deltas zero | PASS |
| integrity `ok` / FK zero | PASS |

Overall: BLOCKED because the positive admission, manifest, projection, and
canonical completion gates were not reached.

## Blocker Classification

```text
BLOCKER CLASSIFICATION: CURSOR_START_MISMATCH (pre-admission continuity boundary)
EVIDENCE: exactly one public N2 run completed 20 Scheduler/Source-Governed work
  items and produced seven proposed cursor-range observations. Both live cursor
  namespaces already had durable non-null slot/signature heads. The new ranges
  supplied null start_slot/start_signature. The first Pump-create namespace
  comparison failed; foundation_execution_id stayed null; committed cursor
  advances, certificates, manifests, and projection all stayed zero.
OFFICIAL/PRINTER CONTRACT COMPARISON: Printer requires each proposed cursor
  range to begin exactly at its durable namespace head before foundation can
  advance any cursor. A range may be transport-complete and CONTIGUOUS yet still
  fail this exact persisted-start identity contract.
ROOT CAUSE AT THIS LANE DEPTH: proposed live cursor starts did not carry the two
  existing durable heads into the foundation input. This proof does not decide
  whether the missing propagation is transport construction, integration
  wiring, configuration/state handoff, or another canonical-owner defect.
CODE CHANGE JUSTIFIED: NOT DETERMINED AND NOT AUTHORIZED IN THIS PROOF LANE.
MINIMUM SAFE RESPONSE: retain the terminal report; do not retry N2; do not run
  N7; do not patch code or configuration; do not reset or overwrite cursors.
FOCUSED NEXT INVESTIGATION: source-ground the exact durable-head -> live
  operation -> normalized cursor_range -> foundation handoff chain, preserving
  both namespace identities and the no-skip/no-rewind continuity contract.
UNTOUCHED SCOPE: ceilings, source/provider contracts, runtime capacity,
  campaign, tracking/lifecycle, snapshots/windows/memory, retrieval, decisions,
  and every financial capability.
AUTHORIZATION STATUS: investigation/repair, retry, N7, cursor mutation, and
  campaign are not authorized by this closeout.
```

## Money-Usefulness Contribution

Positive:

- the repaired mint decoder passed four real extended Token-2022 accounts with
  exact target/slot evidence;
- cohort thinning, source governance, accounting, cleanup, replay, and protected
  isolation remained reliable under one live sample;
- the cursor contract prevented an unanchored backfill range from advancing or
  creating admission evidence.

Incomplete:

- no candidate reached durable foundation admission;
- no certificate, exact-two manifest, projection, or usable candidate handoff
  was created;
- no memory corpus growth or financial usefulness was unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Live cursor start propagation is unproven.** Both existing durable heads
   were omitted from the new proposed start boundary; another proof would
   predictably risk the same safe block until source-grounded.
2. **No successful live admission sample exists after the mint repair.** Raw
   mint evidence passed, but cursor continuity stopped the foundation first.
3. **Later cohort evidence contains independent blockers.** Quote identity was
   absent for all four; three pool observations were owned by the Pump program,
   holder evidence failed for three, liquidity failed for three, and
   tradeability failed for one. These remain separate and were not evaluated as
   admission outcomes.
4. **The sample cannot establish general reliability.** One blocked N2 is an
   honest bounded incident, not a reliability percentage.
5. **Cursor mutation would be unsafe.** Resetting, overwriting, skipping, or
   synthesizing cursor starts to force a rerun would destroy continuity
   evidence and is not authorized.

## Exact Next Permitted Task

Operator decision on a separate source-grounded investigation lane for the
canonical durable cursor-head to live proposed-start propagation boundary that
produced `CURSOR_START_MISMATCH`. Only after that investigation classifies the
issue may an explicitly authorized design/repair lane be considered.

No N2 retry, N7 run, cursor reset, configuration change, code patch, provider
substitution, ceiling increase, operational Memory Factory campaign, tracking,
lifecycle, snapshot, window, memory, retrieval, decision, position, trade,
audit, or PnL task is authorized next.

## Files Changed

- this closeout document;
- `docs/printer-v1-v2-9-8b-post-mint-admission-repair-live-n2-proof-redacted.json`;
- minimal active-pointer updates in `AGENTS.md`,
  `docs/printer-v1-assistant-active-build-order-anchor.md`, and
  `docs/printer-v1-memory-growth-build-order-v2.md`.

## What Was Built

- one bounded live N2 proof closeout;
- one redacted proof artifact;
- exact evidence for the mint repair, cohort, accounting, cursor terminal,
  replay, cleanup, protected deltas, and remaining locks.

## What Was Not Touched

- Python code, tests, configuration, migrations, source/provider contracts,
  budgets, ceilings, and capacity;
- N7, retry, restart, successor, campaign, tracking/lifecycle, snapshots,
  windows, memory, retrieval, decisions, positions, trades, audits, and PnL;
- wallets, private keys, signing, transactions, real funds, paid sources,
  scores, ranks, confidence, weighting, embeddings, and vectors.

## Tests / Checks Run

- exact clean Git/HEAD and authoritative DB hash preflight;
- canonical public `preflight-only` (zero source/write) readiness check;
- migration-049 ledger, integrity, FK, journal-mode, active-state, process,
  SQLite handle/sidecar, and HTTPS RPC configuration checks;
- fresh backup hash/size/integrity/FK/migration verification;
- exactly one canonical live N2 command;
- independent work/source/Scheduler/transport/cursor/admission/protected-table
  reconciliation;
- public DB-backed deterministic zero-source replay;
- final process/lease/Scheduler/handle/sidecar/integrity/FK checks;
- redaction, JSON, Markdown, diff, and repository-scope checks before commit.

## Pass / Fail Status

BLOCKED:
`V2_9_8B_POST_MINT_ADMISSION_REPAIR_LIVE_N2_PROOF_BLOCKED`.

## Risks or Concerns

The exact cursor-start propagation blocker and the independent later-stage raw
cohort weaknesses above remain unresolved. No repair or rerun is authorized.

## Next Recommended Phase

Stop after this closeout. The next permitted task is only the separate
operator-authorized source-grounded cursor-start-boundary investigation
described above.

## Redacted Proof Artifact

`docs/printer-v1-v2-9-8b-post-mint-admission-repair-live-n2-proof-redacted.json`

It contains no complete RPC URL, secret, raw provider payload, mint address,
pool address, or cursor signature.
