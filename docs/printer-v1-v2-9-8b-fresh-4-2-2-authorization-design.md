# Printer V1 V2-9.8B Fresh 4/2/2 Authorization Design

Date: 2026-08-20

Status: `DESIGN_PASS`

Verdict: `V2_9_8B_FRESH_4_2_2_AUTHORIZATION_DESIGN_PASS`

`AUTHORIZATION_CREATED: NO`

`PRINTER_EXECUTED: NO`

This document specifies the next fresh one-use operational 4/2/2 authorization. It creates no authorization, application marker, campaign, Scheduler work, source request, database mutation, retrieval capability, or financial capability.

## 1. Authority and immutable launch baseline

The future authorization MUST target the repaired launch source checkout, not this design branch.

- launch source branch: `agent/v2-9-8b-pre-admission-terminal-cleanup-repair`
- exact launch Git HEAD: `9cfa8a152c3a02c0c5ef599cf0cffe6e269ab885`
- authoritative DB path: `data/printer_v1.sqlite3`
- required DB SHA-256: `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`
- canonical migration count: `58`
- canonical migration head: `058_direct_pump_migration_cursor.sql`
- readiness prerequisite: `V2_9_8B_POST_ALL_SIX_REPAIRS_OPERATIONAL_REREADINESS_PASS`

The design branch and any later authorization-evidence branch are evidence/control-plane work only. Their commits MUST NOT replace the launch Git identity above. Any future authorization document MUST bind its `repository.head` to the exact launch HEAD above.

At authorization preparation time the DB binding MUST be freshly remeasured read-only and contain the wrapper-required exact fields: `path`, `sha256`, `size`, `inode`, `mtime_ns`, `migration_count`, and `migration_head`. The measured SHA MUST still equal the required SHA above. No size/inode/mtime value is invented or frozen by this design.

## 2. Existing operational authorization authority

Use the committed operational authority only:

- command mode: `four-token-standard-four-hour-run`
- authorization schema: `PRINTER_V1_FOUR_TOKEN_STANDARD_4H_FINAL_AUTHORIZATION_V1`
- policy version: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- authorization profile package root: `operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization`
- current migration evidence authority remains Migration 058; this design does not create Migration 059.

Do not reinterpret ordinary, two-token standard-4h, or four-token proof authorization evidence as operational 4/2/2 authority.

## 3. Fresh identities and non-reuse

Authorization creation MUST generate a new `authorization_id` that has never appeared in historical authorization evidence.

The one-shot wrapper/application stage MUST create a fresh application/execution identity in the dedicated four-token standard-four-hour application namespace. No historical application marker, campaign identity, execution identity, run identity, or authorization may be reused.

The authorization MUST enumerate prior authorization IDs as non-reusable under the existing validator. The current authorization ID must not appear in that historical set.

The Migration-058 execution/evidence identity is current schema evidence, not a campaign execution identity and not a license to reuse a prior campaign.

## 4. Exact 4/2/2 operational policy

The authorization MUST equal `four_token_operational_composition.exact_operational_policy()` exactly. No independently maintained numeric copy becomes authority.

Current derived values at the bound launch HEAD are:

| Contract | Exact value |
| --- | ---: |
| through-4h token ceiling | 4 |
| active cycle ceiling | 2 |
| total cycle admission ceiling | 2 |
| tokens per cycle | 2 |
| minimum cycle admission spacing | 300 seconds |
| root main window | `WINDOW_15M` |
| pre-lifecycle acquisition clock | 2,400 seconds |
| post-supply lifecycle clock | 18,000 seconds |
| maximum one-shot wall envelope | 20,400 seconds |
| shared discovery requests | 4 |
| lifecycle/governed request outer ceiling | 476 |
| lifecycle requests per token | 118 |
| lifecycle Scheduler outer ceiling | 420 |
| automatic retries | 0 |
| endpoint rotation | false |
| long windows activated | false |
| locked windows | `WINDOW_12H`, `WINDOW_24H` |

The request/Scheduler numbers are derived by `scaled_standard_four_hour_capacity_contract(4)` from the canonical two-token FAST/FAST standard-4h envelope. A future code change that changes the derived policy makes this design binding stale; do not widen the authorization to match drift.

Additional campaign ceilings remain fixed by the existing operational command:

- exactly 1 campaign;
- campaign storage-growth ceiling: `64 * 1024 * 1024 = 67,108,864` bytes;
- failure ceiling: 20;
- existing admission-operation ceiling remains owned by the operational command and is not replaced by the 476 governed-request envelope.

The 64 MiB boundary is campaign-attributable storage usage/growth, not total historical SQLite file size.

## 5. Selection and lifecycle law

The future one-shot campaign may admit exactly two cycles of exactly two token/pair slots each.

Cycle 2 MUST be fresh/disjoint from Cycle 1 under the existing four-token activation/selection law. The authorization does not permit a third cycle, a single-token cycle, reuse of a Cycle-1 token/pair, or widening beyond four through-4h slots.

Existing admission/evidence law remains unchanged, including:

- Solana memecoin-only scope;
- freeze/minimum-depth requirement of 4;
- exact-pool liquidity floor of `$3,000`;
- exact mint + pair/pool/protocol identity and provenance;
- Source-Governed evidence only;
- honest UNKNOWN where optional evidence is unavailable;
- `WINDOW_5M_MICRO_EVENT` support-only;
- token-local `WINDOW_15M -> WINDOW_1H -> WINDOW_4H` only.

Honest `DIRTY`, `NO_PROMOTION`, optional `UNKNOWN`, or other lawful non-clean outcomes do not invalidate a campaign merely because CLEAN memory was not produced. Parent `printer_memory_windows` rows may intentionally remain `PARTIAL_MEMORY`; promoted episode/fingerprint authority remains unchanged.

## 6. Mandatory pre-consumption fail-closed gate

Every item below MUST pass immediately before authorization consumption. Failure means no application marker and no campaign mutation.

### Git / authorization

- launch checkout branch resolves to the authorized source branch;
- launch HEAD equals `9cfa8a152c3a02c0c5ef599cf0cffe6e269ab885` exactly;
- tracked launch worktree is clean;
- authorization document validates under the dedicated operational four-token wrapper/profile;
- authorization is temporally valid under the central validity law;
- final authorization file/package/manifest hashes match;
- all historical authorization evidence is enumerated and non-reusable;
- no prior application marker is reused.

### Database / migrations

- target resolves to `data/printer_v1.sqlite3`;
- no hot SQLite sidecars;
- freshly measured SHA equals `f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341`;
- package DB binding equals the freshly measured `path/sha256/size/inode/mtime_ns/migration_count/migration_head`;
- `PRAGMA integrity_check = ok`;
- `PRAGMA foreign_key_check` returns zero rows;
- applied migration ledger exactly equals the canonical ordered catalogue;
- migration count remains 58 and head remains `058_direct_pump_migration_cursor.sql`.

### Zero active residue

Fresh read-only inspection MUST prove zero interfering active ownership:

- non-terminal campaign/run/supervision;
- PENDING/RUNNING/COOLDOWN or locked Central Scheduler jobs;
- PLANNED/RUNNING pre-admission discovery attempts;
- active discovery work;
- active factory/run-step work;
- active pre-lifecycle refresh waits/work;
- active candidate-acquisition leases or stale campaign/cycle ownership.

### Runtime / locks

- required interpreter/dependencies/adapters pass the existing runtime preflight;
- Source Governor and Central Scheduler owners are available;
- no paid source dependency is introduced;
- retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits and PnL remain locked;
- `WINDOW_12H` and `WINDOW_24H` remain locked.

Any drift is a pre-consumption BLOCK. Do not consume first and diagnose afterward.

## 7. One-shot consumption law

The authorization document MUST retain the existing one-shot policy exactly:

- allowed invocation count: 1;
- automatic retry: forbidden;
- manual rerun: forbidden;
- resume: forbidden;
- restart: forbidden;
- successor: forbidden.

The final application marker is the one-use consumption boundary. Once the future authorized invocation crosses that boundary, the authorization is spent regardless of later success, block, safe stop, or failure. A consumed authorization is never recycled.

Authorization temporal validity must remain within the central maximum of 86,400 seconds. The existing wrapper fixture default of 43,200 seconds is acceptable; creation should use the minimum sufficient validity window and must never exceed the central maximum.

## 8. Runtime proof obligations for the eventual campaign

The eventual one-shot run must report enough evidence to determine each of these without inference:

1. Cycle 1 admits exactly two lawful token/pair slots.
2. Cycle 2 receives lawful Central Scheduler slack and performs genuine later-cycle discovery/selection rather than reusing Cycle 1 supply.
3. Cycle 2 admits exactly two fresh/disjoint slots, or the run truthfully reports why the bounded campaign could not do so.
4. The campaign never declares terminal while Cycle 2 owns lawful active work.
5. Every admitted token has deadline-aware 15m collection; required snapshots/gaps are reported honestly.
6. Each token that satisfies continuation gates progresses independently through lawful 15m -> 1h -> 4h; a blocked token does not force fabricated continuation.
7. Central Scheduler priority preserves lifecycle deadlines while later-cycle discovery uses only safe slack; no starvation or bypass.
8. Governed request, Scheduler and storage-growth ceilings are never exceeded.
9. Solana-native core-safety redundancy remains functional without making one provider identity structurally mandatory.
10. Wallet/trading-flow aggregates remain evidence-honest; incomplete trade/address coverage remains UNKNOWN/None as specified.
11. Raw `tx_from_address` never reaches durable source-response, candidate, snapshot or report JSON.
12. Optional safety UNKNOWN reasons remain visible and nonblocking where V1 law says optional; explicit dangerous evidence remains blocking.
13. Terminal reports expose exact blockers and the existing parent-window / episode / fingerprint memory authority relationship.
14. Terminal reconciliation leaves zero active/runnable/locked/orphan Scheduler, pre-admission, discovery, factory, refresh or lease residue.
15. Retrieval/financial capability counts remain unchanged/locked.

The campaign is a proof of reliable bounded operation, not a requirement that all four tokens become CLEAN memory.

## 9. Verdict vocabulary

Authorization design:

- `V2_9_8B_FRESH_4_2_2_AUTHORIZATION_DESIGN_PASS`
- `V2_9_8B_FRESH_4_2_2_AUTHORIZATION_DESIGN_BLOCKED`

Future authorization creation/review must use the existing dedicated wrapper's PASS authorization verdict/schema and fail closed on any validation error. This design does not invent a parallel runtime terminal-state vocabulary; the existing campaign/child-terminal owners remain authoritative.

## 10. Next permitted action

If this design remains accepted against the unchanged source/DB baseline, the next permitted action is:

`V2-9.8B Fresh 4/2/2 Authorization Creation / Independent Application Preparation`

That action may create one new authorization package and independently validate it, but MUST NOT run Printer unless the resulting authorization/application preparation itself passes and the operator separately proceeds to the one authorized execution.

`AUTHORIZATION_CREATED: NO`

`PRINTER_EXECUTED: NO`
