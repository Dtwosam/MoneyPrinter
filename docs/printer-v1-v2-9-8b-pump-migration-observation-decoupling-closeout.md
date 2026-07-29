# Printer V1 V2-9.8B Pump Migration Observation Decoupling Closeout

Date: 2026-07-29

Starting HEAD: `90f80d85d99c994a762a47b98fcbb41c5beef63c`

Authoritative DB SHA-256:
`36cf157b74a28fe93695f7c29ffee143a3d7ed6453bdcec5ad74ea666284fa09`

Lane: `V2-9.8B Pump Migration Observation Decoupling Audit and Design`

## Verdict

`V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_DESIGN_PASS`

The source-grounded audit classified the current coupling as `DESIGN_GAP`.
The design closes that gap without changing code, configuration, schemas,
migrations, cursors, recovery bounds, source budgets, or the database.

The global Pump-program migration observer remains optional coverage and
diagnostic/audit evidence, but it is retired from active universal candidate
gating. Exact Pump graduation moves to a candidate-specific finalized
transaction plus canonical PumpSwap Pool join. Exact generic/non-Pump and
unknown-origin current-pool branches can proceed without global migration
continuity.

## Confirmed findings

1. The current program-wide Pump migration namespace is marked required and can
   stop unrelated candidate branches before foundation.
2. The namespace is not migrate-exclusive. The bounded recovery inspected
   11,000 signatures across 44 pages, moved only 40 slots from its frozen tip,
   and still did not encounter the prior boundary.
3. The resulting historical gap is valid coverage evidence but not a universal
   candidate-lineage prerequisite.
4. The pinned `migrate` layout exposes exact address-indexable candidate mint,
   bonding curve, and Pool accounts at positions 2, 3, and 9.
5. A known signature, pool, curve, or mint can therefore locate a bounded
   candidate-specific transaction set. Only finalized exact transaction decode
   is proof.
6. Exact Pump `migrate` and exact PumpSwap Pool state must join on the same
   candidate mint and Pool and pass canonical creator/index/quote/PDA/LP/vault
   relationships.
7. PumpSwap Pool presence alone never proves graduation.
8. Non-Pump and unknown-origin exact-present-pool admission does not depend on
   global Pump migration continuity.
9. No current pinned narrower global HTTP locator is established.
10. A future bounded logs channel can be locator-only and must be followed by
    finalized HTTP verification.
11. Compact page summaries and hashes can prevent another program-wide raw-
    signature growth event without turning negative bounded searches into
    absence claims.

## Rejected findings

- cursor reset, rewind, advancement, or silent checkpoint adoption;
- adoption of the recovery continuation as an authoritative head;
- arbitrary recovery/page/source-budget increase;
- global continuity as a prerequisite for all nominations or pools;
- PumpSwap presence, venue label, program presence, log text, or provider label
  as migration proof;
- failure of a Pump claim followed by generic/unknown fallback;
- candidate-specific proof as a substitute for global discovery/completeness;
- retirement of all optional global observation;
- PumpSwap-program or guessed fixed-account history as a new global index;
- logs as finalized or complete evidence;
- another full raw-signature ledger; and
- any score, rank, confidence, weighting, quota, or source preference.

## Final authority model

```text
multi-source nomination
-> deterministic M=2N cohort
-> exact categorical branch

Pump graduation claim
-> candidate-specific signature/pool/curve/mint locator
-> finalized exact Pump migrate decode
-> exact canonical PumpSwap Pool state
-> exact joined proof
-> PUMP_GRADUATION_CONFIRMED

active Pump curve, complete=false
-> exact origin + curve proof
-> PUMP_ORIGIN_CONFIRMED

no Pump graduation claim
-> exact current-pool orientation + owner/program proof
-> UNKNOWN_ORIGIN or NON_PUMP_POOL_CONFIRMED

optional global observer
-> discovery and bounded coverage only
-> exact hits re-enter candidate-specific verification
-> no universal gating authority
```

The candidate-acquisition integration owner remains the sole finite
orchestrator, Central Scheduler owns every work item, Source Governor owns every
request/response/failure, and the foundation remains the sole
certificate/reserve/manifest owner.

## Exact branch-specific evidence contracts

| Branch | Required evidence | Explicit non-requirement |
| --- | --- | --- |
| Pump graduation | exact Pump origin; exact finalized `migrate`; exact candidate mint/curve/pool accounts; exact canonical PumpSwap Pool owner/layout/base/WSOL quote/creator/index/PDA/LP/vault join | global continuity |
| active Pump bonding curve | exact Pump creation; derived curve PDA; Pump owner; pinned curve layout/quote; `complete=false` | migration proof and global continuity |
| unknown-origin PumpSwap-present pool | exact Pool state/current relationship with no Pump graduation assertion | Pump graduation; global continuity |
| non-Pump current pool | exact provider orientation; candidate base; allowed quote; exact pool owner; executable owner program | Pump evidence and global continuity |
| unknown-origin generic pool | same exact current-pool evidence, origin retained unknown | Pump evidence and global continuity |
| explicit/conflicting Pump claim | all exact Pump branch evidence or categorical failure | downgrade to generic/unknown |

Every candidate-specific signature remains locator evidence until finalized
`getTransaction` plus the Pool join passes. Empty, bounded, null, or pruned
history remains incomplete/unknown and never means `not migrated`.

## Existing global cursor and historical gap

The existing authoritative migration head at slot `435985595`, frozen recovery
tip at `435999023`, last committed continuation at `435998983`, 11,000 inspected
signatures, 44 pages, immutable work evidence, and
`CURSOR_RECOVERY_LANE_BOUND_EXHAUSTED` result remain untouched.

The derived future report status is `OPTIONAL_OBSERVER_GAPPED` with
`admission_authority=NONE`. This is an interpretation boundary only. It is not a
database update, cursor reset, checkpoint adoption, compacting operation, or
permission to continue recovery.

## Minimum implementation scope

A later explicit implementation is limited to:

1. make global migration observation optional and detach its cursor from
   unrelated observations;
2. classify cohort candidates into exact lineage branches;
3. add bounded candidate signature/pool/curve/mint lookup;
4. reuse the strict pinned `migrate` and PumpSwap verifier;
5. add exact governed request kinds and operation accounting;
6. persist compact page summaries/hashes and positive decoded facts, not full
   program-wide signature arrays;
7. preserve all existing cursor/recovery rows byte-for-byte; and
8. prove the change offline with focused and directly affected tests.

If migrations 048/049 cannot represent the compact evidence safely, the later
lane must stop `BLOCKED`. This design does not authorize a schema or migration.

## Offline proof required before live work

The mandatory disposable/frozen proof must cover:

- generic and non-Pump admission while the optional global observer is gapped,
  unknown, unavailable, blocked-contract, or not run;
- active Pump bonding curve without migration work;
- Pump graduation from exact signature, pool, curve, and mint locators;
- one-field-at-a-time migrate/Pool join failures;
- PumpSwap-presence-only rejection and no Pump-claim fallback;
- bounded no-match, pruned/null history, provider failure, malformed page,
  unsupported contract, ambiguity, and budget categories;
- optional global positive hits passing through the candidate verifier;
- optional global failures excluded from universal required failures;
- crash/replay/continuation integrity with zero automatic restart;
- compact storage with no raw program-wide signature arrays;
- exact Scheduler/Governor/transport/lease/report reconciliation;
- live-shaped N2 exact-two mechanics and N7 runtime-neutral preservation;
- current budgets/capacity/cursors unchanged and zero protected deltas; and
- no-wallet/no-paid/no-scoring/no-retrieval/no-financial scans.

No live proof may follow automatically.

## Money-usefulness contribution

The design removes an unrelated high-volume coverage bottleneck from exact
present-pool candidates while keeping Pump graduation evidence strict. That
improves the chance of forming a truthful two-candidate cohort without admitting
fake Pump lineage, guessed quote identity, or PumpSwap-presence-only graduation.
It also prevents raw signature bookkeeping from crowding out durable,
money-useful market memory.

No memory, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, PnL, or
profit capability is created.

## What remains locked

- Python, configuration, schema, migration, cursor, recovery-bound, source-
  budget, and authoritative DB changes;
- provider, RPC, WebSocket, recovery, N2, N7, and campaign execution;
- active runtime capacity above two;
- tracking handoff, lifecycle, snapshots, windows, and memory production;
- retrieval and dirty/partial evidence use;
- paper decisions, BUY, SELL, HOLD, positions, trades, audits, and PnL;
- wallets, private keys, signing, transactions, real funds, and live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, quotas, embeddings, and vectors; and
- Source Governor or Central Scheduler bypass.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Candidate-specific histories may still be long, pruned, or unavailable; a
   required Pump branch must block honestly.
2. Candidate-specific verification complements but does not replace global
   discovery. Optional global coverage remains gapped until separately resolved.
3. No currently pinned narrower global HTTP index exists.
4. A future logs locator is lossy and cannot be required for correctness.
5. Existing 11,000-signature recovery evidence and its roughly 47 MB growth are
   immutable; this lane prevents repetition but does not reclaim space.
6. Fixed Solana capacity may be insufficient for dynamic cohort-specific work;
   later budget arithmetic must fail before excess without increasing ceilings.
7. The current migration pin excludes unsupported Token-2022/alternate-quote
   migration layouts.
8. Existing tables may prove insufficient for compact replay; that would require
   a new separately authorized design, not improvisation.

## Files changed

- `docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-audit.md`
- `docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-design.md`
- `docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-closeout.md`

## What was built

- a source-grounded decoupling audit;
- a complete four-channel authority and ownership architecture;
- exact branch, locator, migration/Pool join, failure, restart, storage, and
  offline-proof contracts; and
- this documentation-only closeout.

## What was not touched

No Python, tests, configuration, schema, migration, cursor, recovery bound,
source budget, database, provider, RPC, WebSocket, N2, N7, campaign, runtime,
memory, retrieval, or financial path was changed or run.

## Tests / checks run

- exact clean starting HEAD/worktree and authoritative DB hash preflight: PASS;
- active source-stack, closest audits/designs/closeouts, pinned Pump/PumpSwap,
  Solana RPC/parsing, Python Builder Guide, and Source Governor review: PASS;
- current owner/cursor/gating/storage call-path inspection: PASS;
- required-section and exact-verdict scan: PASS;
- balanced Markdown fence scan: PASS;
- ASCII/non-secret documentation scan: PASS;
- untracked/file-scope check: PASS - exactly the three lane documents;
- per-file no-index whitespace check and `git diff --check`: PASS; and
- final authoritative DB SHA-256 recheck: PASS and unchanged.

No runtime, provider, RPC, recovery, N2, N7, campaign, Python, migration, or
database test was run or permitted.

## Pass / fail status

PASS: `V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_DESIGN_PASS`.

## Exact next permitted task

Only a separately explicit operator-authorized
`V2-9.8B Pump Migration Observation Decoupling Implementation and Offline Proof`
lane from this committed design.

That task may implement only the minimum scope above using frozen transports and
disposable databases. It may not call a provider or RPC, mutate the authoritative
database, reset/advance/continue a cursor, change a recovery bound or source
budget, run N2 or N7, start a campaign, or unlock memory, retrieval, or any
financial capability.
