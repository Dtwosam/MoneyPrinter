# Printer V1 V2-9.8B Post Cursor-Repair Bounded Live N2 Proof Closeout

Date: 2026-07-29

Starting HEAD: `2b6e82076806a3c84ed1212d597d1c899f84a71c`

Lane: `V2-9.8B Post Cursor-Repair Bounded Live N2 Proof`

## Verdict

`V2_9_8B_POST_CURSOR_REPAIR_LIVE_N2_PROOF_BLOCKED`

Exactly one canonical public `ACQUISITION_ONLY_N2` execution ran. The durable
cursor repair passed its live boundary: both declared live namespaces performed
explicit `FORWARD` bootstrap, proposed and committed unique namespace advances
reconciled `2 / 2`, each new head was version 1, and both historical `BACKWARD`
rows remained byte-identical.

The execution then reached foundation admission and blocked honestly with the
earliest terminal cause `IDENTITY_MERGE_FAILURE` and foundation reason
`IDENTITY_NOT_MERGED`. All four cohort identities had a present pool observation
but no exact quote-mint identity. Foundation therefore issued four rejected
certificates, admitted zero, and created no manifest or projection.

There was no retry, restart, successor, N7 run, code/configuration change,
cursor reset, ceiling change, provider substitution, campaign, tracking,
lifecycle, snapshot, window, memory, retrieval, decision, position, trade,
audit, or PnL work.

## Preflight

| Check | Result |
| --- | --- |
| exact HEAD | `2b6e82076806a3c84ed1212d597d1c899f84a71c` |
| worktree/index/untracked inventory | clean |
| authoritative starting DB SHA-256 | `d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2` |
| migration ledger | 49 canonical rows; latest `049_candidate_acquisition_integration.sql` |
| integrity / foreign keys | `ok` / zero violations |
| journal mode | `delete` |
| active Printer process | none |
| active acquisition lease/integration | zero / zero |
| active or locked Scheduler work | zero |
| active campaign Scheduler work | zero |
| SQLite open handle / sidecars | zero / zero |
| HTTPS RPC configuration | present and structurally valid; value not printed or persisted |
| canonical public preflight | `V2_9_8_OPERATIONAL_PREFLIGHT_READY`; zero source calls/writes |
| active runtime capacity | exactly two |
| automatic retries | zero |

## Fresh Backup

Host-only backup directory:

`/private/tmp/printer-v1-post-cursor-repair-live-n2.6GZH7L`

Backup file:

`printer_v1.pre-n2.backup.sqlite3`

| Evidence | Result |
| --- | --- |
| source SHA-256 | `d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2` |
| backup SHA-256 | `d062a108fa178527e64c5ceb061c30a6889832dab8d072ff486b6a70797008f2` |
| source / backup size | 17,100,800 / 17,100,800 bytes |
| byte-hash equality | PASS |
| migration / integrity / FK | 049 / `ok` / zero violations |

The backup, authoritative database, RPC configuration, and raw source payloads
remain outside the commit.

## Protected Baseline and Final Deltas

| Protected surface | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Memory Factory campaigns / runs / cycles / slots / windows | 17 / 17 / 17 / 14 / 2 | unchanged | 0 |
| Memory Factory runs / steps | 6 / 54 | unchanged | 0 |
| tracking queue | 29 | 29 | 0 |
| token snapshots | 1,054 | 1,054 | 0 |
| memory windows | 160 | 160 | 0 |
| episodes / outcomes / episode snapshots | 57 / 23 / 107 | unchanged | 0 |
| memory fingerprints / audit reports | 23 / 5 | unchanged | 0 |
| retrieval queries / matches | 10 / 0 | unchanged | 0 |
| paper decisions | 2 | 2 | 0 |
| paper positions | 0 | 0 | 0 |
| paper trade events / audits | 0 / 0 | 0 / 0 | 0 |
| paper audit reports | 1 | 1 | 0 |

The command's `forbidden_table_deltas` map and the independent recount agree
that every protected delta is zero.

## Execution Identity

Exactly one invocation used the required command:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Field | Result |
| --- | --- |
| execution ID | `20260729T165903Z-acq-790357d6567a` |
| integration ID | `cain-4b53b5ec211f4940a6fc4ea4fa6510aa` |
| mode | `ACQUISITION_ONLY_N2` |
| command exit / wall clock | 0 / 18.915 seconds |
| canonical status | `BLOCKED` |
| earliest terminal cause | `IDENTITY_MERGE_FAILURE` |
| foundation failure family / reason | `IDENTITY_MERGE_FAILURE` / `IDENTITY_NOT_MERGED` |
| integration / foundation execution delta | +1 / +1 |
| retry / restart / successor | false / false / false |
| N7 executions created | 0 |

No private injector, proof launcher, direct adapter, legacy path, retry,
restart, successor, or N7 command was used.

## Complete Cursor Inventory

The values below are SHA-256 pseudonyms of raw namespace/identity/signature
material. The redacted evidence contains no raw indexed address or signature.

### Before

| Namespace SHA-256 | Direction | Slot | Version | Boundary signature SHA-256 | Row SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| `b7f2a32d079a308d453e9ac6a0a23c627f3ade0d8eabeea7feb9c41559a51a7a` | `BACKWARD` | 435970004 | 4 | `3ada16554015d024ed5cd69d8022c534906e02283bc7fb06004b1b0092b6d12d` | `df32996cb9707c80f66961d64f78bc8ba3de6d49f9120a7b7743932bf600b255` |
| `4d181551ff80368a6f3b019ec7d0bbf1fc248ff14f84feb5f77a20bc87c2aa15` | `BACKWARD` | 435969990 | 1 | `4e49ff9c91ebe685aa85d9a62887f270518cc83b3b81325db519cee01ba3dbdc` | `454c8e9b644e8f7f000dd7244284144672777f7eefe8d215699684b8fe21373c` |

There were zero `FORWARD` heads before execution.

### After

| Namespace SHA-256 | Direction | Slot | Version | Boundary signature SHA-256 | Row SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| `b7f2a32d079a308d453e9ac6a0a23c627f3ade0d8eabeea7feb9c41559a51a7a` | `BACKWARD` | 435970004 | 4 | `3ada16554015d024ed5cd69d8022c534906e02283bc7fb06004b1b0092b6d12d` | `df32996cb9707c80f66961d64f78bc8ba3de6d49f9120a7b7743932bf600b255` |
| `4d181551ff80368a6f3b019ec7d0bbf1fc248ff14f84feb5f77a20bc87c2aa15` | `BACKWARD` | 435969990 | 1 | `4e49ff9c91ebe685aa85d9a62887f270518cc83b3b81325db519cee01ba3dbdc` | `454c8e9b644e8f7f000dd7244284144672777f7eefe8d215699684b8fe21373c` |
| `d3ea1a5ce2fdec18943e638ebd812d72e70441f55d7aace9dc2e82a113623178` | `FORWARD` | 435985595 | 1 | `dbebabfecf14752efcc4849f48920798049c6be02726df8271181f0e277c9191` | `eabcbcc1955a4f201ed9321596cb4343e303a0dad0df5f65629e6dc0e568cc5a` |
| `c1c5966d311071a9318e822a44e0efac5885a6803419e8540dc90c9fedeb00ea` | `FORWARD` | 435985590 | 1 | `4f58da6d64d34694d232abd86055371587fea87d23f8e66355f63967a61caa79` | `563617c6b5b915b7fc8a8951266071a8beefd74c9b5c15b08fff3934348b1a45` |

Both historical `BACKWARD` row hashes are identical before and after. No
backward row was added, removed, rewritten, reset, or cross-used as a forward
head.

## Bootstrap, Hydration, and Range Reconciliation

| Check | Result |
| --- | --- |
| declared live namespaces | 2 |
| established `FORWARD` heads loaded | 0 |
| explicit `FORWARD` bootstrap namespaces | 2 |
| proposed unique namespace advances | 2 |
| committed head advances | 2 |
| persisted immutable range-evidence rows | 5 across 2 namespaces |
| distinct normalized ranges per namespace | exactly 1 |
| committed head versions | both version 1 |
| range continuity | all `CONTIGUOUS` |
| bootstrap starts | null, as required for first forward bootstrap |
| real range ends | present for both namespaces |
| synthetic boundary / rewind / skip | none |
| intermediate-page conflict | none; every work reference for a namespace carried the same normalized range |
| prior-boundary unavailable/unreachable | not applicable; there was no prior `FORWARD` boundary |

Five immutable range-evidence rows retained shared final-range evidence from
five foundation observations. They collapse to two exact normalized namespace
ranges and two head commits. No namespace head advanced or versioned more than
once.

## Pump Event and Boundary Classification

Both first-forward-bootstrap signature pages returned one live-tip row. The
bounded transaction work completed, but no decoded Pump-create or Pump-migration
candidate event with a mint identity entered the cohort. This is not a prior
boundary availability failure: no established forward boundary existed to
verify, and neither namespace reported `CURSOR_PRIOR_BOUNDARY_UNREACHABLE`.

Under the adopted multi-source contract, this did not block direct
DexScreener/GeckoTerminal nomination. The aggregator nomination universe
remained eligible, while all four selected candidates correctly retained
`UNKNOWN_ORIGIN`; Printer made no unsupported Pump origin, graduation, or
canonical PumpSwap lineage claim.

## Nomination, Cohort, and Enrichment

| Funnel measure | Count |
| --- | ---: |
| raw normalized rows | 63 |
| raw unique nominations | 41 |
| DexScreener nomination rows | 21 |
| GeckoTerminal nomination rows | 18 |
| Solana cursor/nomination rows | 2 |
| cohort bound `M` | 4 |
| exact cohort size | 4 |
| thinned beyond cohort | 37 |
| enriched identities | 4 |
| out-of-cohort enrichment | 0 |

The repaired raw nomination to `M=4` boundary passed, and candidate-specific
mint, pool, holder, safety, market, liquidity, and tradeability work remained
cohort-only.

## Mint Target, Slot, and Decoder Evidence

| Check | Result |
| --- | --- |
| requested targets / response slots | 4 / 4 |
| exact response slots | `0, 1, 2, 3` |
| association | `POSITIONAL_RPC_CONTRACT` |
| target-to-candidate merge guards | PASS 4 / 4 |
| account presence / owner / layout | PASS 4 / 4 each |
| SPL Token decoded | 1 |
| Token-2022 decoded | 3 |
| mint / token-program status | PASS 4 / 4 each |
| categorical mint failures | none |

## Pool, Quote, Holder, Liquidity, Tradeability, Lineage, and Conflicts

Full SHA-256 pseudonyms are retained in the redacted JSON artifact. Prefixes
below are display-only.

| Identity | Pool | Pool program | Quote | Holder | Liquidity | Tradeability | Lineage | Tracking/cooldown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `d3d40a855d840f69` | `be7d5a77ff5af5e4` present | Pump program | absent | FAIL | FAIL | PASS | `UNKNOWN_ORIGIN` | PASS / no conflict |
| `86043f62cc0bc3e5` | `afacc3c523bbb793` present | Pump program | absent | FAIL | FAIL | PASS | `UNKNOWN_ORIGIN` | PASS / no conflict |
| `38d4d7ad56d37e2d` | `667cff0366b09d0c` present | PumpSwap AMM program | absent | PASS | PASS | PASS | `UNKNOWN_ORIGIN` | PASS / no conflict |
| `477d367988e31a55` | `672546316229af78` present | Pump program | absent | FAIL | FAIL | PASS | `UNKNOWN_ORIGIN` | PASS / no conflict |

Separate categorical facts:

- exact pool identity was present for all four;
- exact quote-mint identity was absent for all four;
- holder evidence was one PASS and three FAIL;
- market, age, safety, and tradeability evidence was PASS for all four;
- liquidity evidence was one PASS and three FAIL;
- lineage remained `UNKNOWN_ORIGIN` for all four;
- the atomic tracking/cooldown recheck passed all four with no reason codes;
- current persistent state contained zero active tracking rows and zero
  selection-rotation matches for the cohort.

These later holder/liquidity facts were preserved separately. They did not
replace or outrank the first admission failure at exact identity availability.

## Exact Admission Funnel

| Admission stage | Result |
| --- | --- |
| `CHAIN_MINT_VALID` | PASS 4 / 4 |
| `TOKEN_PROGRAM_VALID` | PASS 4 / 4 |
| `IDENTITY_AVAILABLE` | FAIL 4 / 4 — `IDENTITY_INCOMPLETE` |
| `POOL_QUOTE_VALID` | NOT_REACHED 4 / 4 |
| `MARKET_FRESH` | NOT_REACHED 4 / 4 |
| `AGE_VALID` | NOT_REACHED 4 / 4 |
| `HOLDER_ACCEPTABLE` | NOT_REACHED 4 / 4 |
| `SAFETY_ACCEPTABLE` | NOT_REACHED 4 / 4 |
| `LIQUIDITY_TRADEABILITY_VALID` | NOT_REACHED 4 / 4 |
| `ROUTE_TRADEABILITY_VALID` | NOT_REACHED 4 / 4 |
| `LINEAGE_VALID` | NOT_REACHED 4 / 4 |

| Durable result | Count |
| --- | ---: |
| certificates issued | 4 |
| certificates admitted / rejected | 0 / 4 |
| manifest count / item count | 0 / 0 |
| selected count | 0 |
| projection count | 0 |
| runtime handoff count | 0 |

The PASS requirement for at least two admitted certificates, one exact-two
manifest, and projection count two was not met.

## Source, Scheduler, and Underlying Operations

| Counter | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Scheduler jobs | 1,177 | 1,197 | +20 |
| source requests | 1,512 | 1,532 | +20 |
| source responses | 1,399 | 1,419 | +20 |
| source failures | 113 | 113 | 0 |
| acquisition integrations / leases | 3 / 3 | 4 / 4 | +1 / +1 |
| acquisition work rows | 56 | 76 | +20 |
| transport operations | 57 | 78 | +21 |
| integration reports | 3 | 4 | +1 |
| foundation executions | 1 | 2 | +1 |
| observations / certificates | 26 / 4 | 52 / 8 | +26 / +4 |
| manifests / manifest items | 0 / 0 | 0 / 0 | 0 / 0 |
| cursor heads | 2 | 4 | +2 `FORWARD` |

Execution-local reconciliation:

- 20 distinct work rows and Scheduler job IDs, all `SUCCEEDED`;
- 20 distinct Source Governor request and response links, all `COMPLETE`;
- zero source-failure links;
- 21 underlying transport operations, all `COMPLETE`;
- 143,576 bytes and 63 normalized rows;
- Scheduler owner `Central Scheduler`;
- source owner `Source Governor`;
- immutable ceilings remained unbreached: requests `20 / 24`, operations
  `21 / 32`, bytes `143,576 / 16,777,216`, rows `63 / 64`, Scheduler jobs
  `20 / 24`, selected capacity `0 / 2`.

## Replay, Cleanup, and Final Database

The public DB-backed `replay_candidate_acquisition_integration_report` path
verified the stored report hash, replay identity, and foundation replay and
returned the same terminal semantic payload without source, Scheduler,
transport, or DB mutation.

| Check | Result |
| --- | --- |
| report hash / replay identity | verified / verified |
| deterministic terminal replay | equal |
| replay new source / Scheduler / transport work | 0 / 0 / 0 |
| active acquisition leases / integrations | 0 / 0 |
| active or locked Scheduler residue | 0 |
| active Printer process | 0 |
| SQLite handles / sidecars | 0 / 0 |
| final integrity / FK | `ok` / zero violations |
| final authoritative DB SHA-256 | `898d9b0fa9e99417a3429c21f5dd02817d80d3b78402c4e35d2c261e9e62f1c9` |
| final authoritative DB size | 17,305,600 bytes |

## Acceptance Result

| Required gate | Result |
| --- | --- |
| canonical `COMPLETED` | FAIL — `BLOCKED` |
| exactly one execution; no retry/restart/successor | PASS |
| explicit forward bootstrap or exact hydration | PASS — bootstrap 2 / hydration 0 |
| historical `BACKWARD` isolation | PASS |
| proposed / committed cursor reconciliation | PASS — 2 / 2 |
| no skip, rewind, synthetic boundary, or range conflict | PASS |
| raw nomination to `M=4` cohort | PASS — 41 to 4 |
| cohort-only enrichment | PASS — 4; out-of-cohort 0 |
| mint targets / slots / SPL and Token-2022 decode | PASS |
| categorical foundation stages | PASS as fail-closed behavior |
| at least two admitted certificates | FAIL — 0 |
| one exact two-item manifest | FAIL — 0 |
| projection count two | FAIL — 0 |
| runtime handoff zero | PASS |
| Scheduler / Governor / operation accounting | PASS |
| deterministic zero-source replay | PASS |
| cleanup and protected deltas | PASS |
| integrity / FK | PASS |

Overall: BLOCKED because exact quote identity was absent for every cohort item,
so foundation stopped at `IDENTITY_AVAILABLE` and no candidate was admitted.

## Blocker Classification

```text
BLOCKER CLASSIFICATION: EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE
EVIDENCE: Exactly one live N2 reached foundation after successful forward
  bootstrap and categorical mint validation. All four identities had a present
  pool and absent exact quote mint; foundation recorded IDENTITY_INCOMPLETE,
  rejected four certificates, and created no manifest or projection.
OFFICIAL-SOURCE COMPARISON: No new official/provider contract mismatch was
  established by this bounded sample. Live observations supplied insufficient
  exact pool/quote identity evidence for admission.
PRINTER-CONTRACT COMPARISON: The adopted multi-source foundation allows
  aggregator nomination but requires exact current pool/base/quote identity
  before admission. Unknown origin may remain categorical; missing exact quote
  identity must fail closed and cannot be synthesized.
ROOT CAUSE: The live cohort's present-pool observations did not carry exact
  quote-mint identity, leaving all four foundation identities incomplete.
CODE CHANGE JUSTIFIED: NO.
MINIMUM SAFE RESPONSE: Preserve this terminal evidence and stop without patch,
  configuration change, cursor reset, provider substitution, retry, N7, or
  successor.
FOCUSED PROOF: This closeout's single execution, durable report/replay,
  categorical certificate stages, cursor reconciliation, and zero-protected-
  delta checks.
UNTOUCHED SCOPE: Provider contracts, code, configuration, ceilings, capacity,
  campaign, tracking/lifecycle, snapshots/windows/memory, retrieval, decisions,
  and every financial capability.
AUTHORIZATION STATUS: No repair, retry, N7, campaign, or later runtime work is
  authorized by this blocker closeout.
NEXT ROADMAP-COMPLIANT STEP: Operator review of this blocked closeout and a
  decision whether to authorize a separate read-only, source-grounded exact
  pool/quote-identity evidence investigation. No successor exists automatically.
```

## Money-Usefulness Contribution

Positive:

- the first live `FORWARD` bootstrap proved the durable cursor repair without
  altering historical backfill heads;
- source-neutral nomination, `M=4` thinning, cohort-only enrichment, mint
  decoding, accounting, replay, cleanup, and protected isolation held under a
  real bounded sample;
- categorical identity admission prevented incomplete pool/quote evidence from
  becoming a usable candidate.

Incomplete:

- no candidate was admitted;
- no exact-two manifest, projection, or usable candidate handoff was created;
- no memory corpus growth or financial usefulness was unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Exact quote identity remains unavailable for this cohort.** Present pools
   alone cannot satisfy the identity contract, and the missing quote must not be
   guessed or synthesized.
2. **Three candidates also had weak holder and liquidity evidence.** These
   independent categorical weaknesses did not become the first terminal cause
   because identity failed earlier.
3. **Forward bootstrap intentionally claims only the current live tip.** It does
   not backfill missed older history; historical `BACKWARD` heads remain separate
   and inactive.
4. **Range evidence is shared across multiple foundation observations.** Five
   immutable evidence rows collapse to two identical normalized namespace
   ranges and two head commits. Future reviews must continue distinguishing
   evidence references from actual head advancement.
5. **One blocked N2 is not a reliability statistic.** It proves this bounded
   execution and its safe stop only.

## Exact Next Permitted Task

Stop after this closeout. The next permitted task is operator review and, only
if separately explicitly authorized, a read-only source-grounded investigation
of the exact pool/quote-identity evidence boundary. No N2 retry, N7 run, cursor
reset, code/configuration change, provider substitution, ceiling increase,
operational campaign, tracking, lifecycle, snapshot, window, memory, retrieval,
decision, position, trade, audit, or PnL task is authorized.

## Files Changed

- this closeout document;
- `docs/printer-v1-v2-9-8b-post-cursor-repair-live-n2-proof-redacted.json`;
- minimal active-pointer updates in `AGENTS.md`,
  `docs/printer-v1-assistant-active-build-order-anchor.md`, and
  `docs/printer-v1-memory-growth-build-order-v2.md`.

## What Was Built

- one bounded live N2 blocker closeout;
- one redacted proof artifact;
- exact evidence for forward bootstrap, historical cursor isolation, cohort,
  admission, accounting, replay, cleanup, protected deltas, and remaining locks.

## What Was Not Touched

- Python code, tests, configuration, migrations, provider/source contracts,
  budgets, ceilings, capacity, and historical cursor rows;
- N7, retry, restart, successor, campaign, tracking/lifecycle, snapshots,
  windows, memory, retrieval, decisions, positions, trades, audits, and PnL;
- wallets, private keys, signing, transactions, real funds, paid sources,
  scores, ranks, confidence, weighting, embeddings, and vectors.

## Tests / Checks Run

- exact clean Git/HEAD and authoritative DB hash preflight;
- active source-stack and required repair/blocked-proof review;
- canonical zero-source `preflight-only` readiness check;
- migration-049, integrity, FK, journal-mode, process, lease, Scheduler,
  SQLite-handle/sidecar, and HTTPS-RPC-configuration checks;
- fresh byte-identical backup plus migration/integrity/FK checks;
- complete before/after cursor inventory and protected-table baseline;
- exactly one canonical live N2 execution;
- work/source/Scheduler/transport/cursor/foundation/certificate reconciliation;
- deterministic DB-backed zero-source replay;
- final cleanup, integrity, FK, DB hash, redaction, JSON, Markdown, diff, and
  repository-scope checks.

## Pass / Fail Status

BLOCKED: `V2_9_8B_POST_CURSOR_REPAIR_LIVE_N2_PROOF_BLOCKED`.

## Risks or Concerns

Exact quote identity was absent for all four candidates; three also had holder
and liquidity failures. No repair or rerun is authorized.

## Next Recommended Phase

Stop. Await operator review; the only possible next task is the separately
explicit read-only investigation described above.

## Redacted Proof Artifact

`docs/printer-v1-v2-9-8b-post-cursor-repair-live-n2-proof-redacted.json`

It contains no complete RPC URL, secret, raw provider payload, raw mint/pool or
indexed address, or raw cursor signature.
