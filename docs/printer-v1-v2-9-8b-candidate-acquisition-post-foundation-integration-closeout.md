# Printer V1 V2-9.8B Candidate-Acquisition Post-Foundation Integration Closeout

Date: 2026-07-29

Starting HEAD: `164dcd5e570d7de19a84bfa651e0320850f03348`

## Final verdict

`V2_9_8B_CANDIDATE_ACQUISITION_POST_FOUNDATION_INTEGRATION_PASS`

All four internal gates pass. The existing public operational command now owns
two explicit acquisition-only modes through one finite integration owner. The
path is Scheduler-led, Source-Governed, lease-bound, cursor-safe,
capacity-neutral, deterministically reported and replayable, and terminal before
tracking or any runtime lifecycle. No live source or operational campaign ran.

## Phase gates

| Gate | Result | Evidence |
| --- | --- | --- |
| Gate 1 — readiness audit | PASS | canonical owners, defects, concurrency, ceilings, DB adoption and reliability boundary are complete in the integration audit |
| Gate 2 — complete design | PASS | exact modes, flow, ownership, policies, schema, terminal semantics and proof contract are complete in the integration design |
| Gate 3 — implementation | PASS | canonical command integration, migration 049, cursor/lease/work/report ledgers, adapter reuse, atomic tracking/cooldown recheck and focused verification pass |
| Gate 4 — offline proof | PASS | canonical N=2/N=7 command dispatch and every required failure/cancellation/idempotency case pass with frozen transports and disposable DBs |

## Authority model and documentation repair

Candidate discovery is multi-source. DexScreener and GeckoTerminal may nominate
directly and prove only their supported current market facts. Direct Pump and
PumpSwap evidence remains mandatory and authoritative for exact Pump origin,
migration, graduation and canonical PumpSwap-pool claims; it is not mandatory
lineage for non-Pump or honest unknown-origin candidates. Exact Solana
mint/token-program/pool relationships remain required. Birdeye is optional and
not in the minimum plan. DEXTools is deferred. PumpPortal is excluded from the
foundation under its current API-key/wallet contract. GoPlus is optional and
absence is never safety.

The active anchors, Clean Master Spec, Memory Factory Guide and V2 build order
now supersede the stale Direct Pump/PumpSwap-audit pointer, the enrichment-only
aggregator wording, and the statement that foundation implementation is still
pending. The historical roadmap-adoption document is preserved as history with
an explicit current-status superseding notice.

## Integrated architecture and owners

```text
explicit authorization and existing activation preflight
-> acquisition-scoped lease
-> finite Central Scheduler DISCOVERY_REFRESH jobs
-> Source Governor request/response/failure persistence
-> injected existing bounded source adapters and strict decoders
-> normalized observations and exact underlying-operation ledger
-> atomic tracking/cooldown and current-cursor recheck
-> candidate-acquisition certificates, reserve and exact-N manifest
-> N=2-only read-only legacy projection; never N=7
-> zero runtime handoff
-> immutable canonical report/replay
-> Scheduler residue terminalization, lease release and safe stop
```

`operational_memory_factory_command.py` remains the sole public command owner.
`candidate_acquisition_integration.py` owns the finite integration, lease,
Scheduler/Governor composition, source plan, cleanup and first terminal cause.
Existing DexScreener and GeckoTerminal adapters are reused; GeckoTerminal's
local allowed-kind boundary now matches the adopted registry nomination kinds.
The foundation remains the sole certificate/reserve/manifest owner. The legacy
adapter remains the sole two-item projection owner and creates no runtime work.

## Modes and frozen ceilings

| Ceiling | `ACQUISITION_ONLY_N2` | `ACQUISITION_ONLY_N7` |
| --- | ---: | ---: |
| selection / candidate limit | 2 / 4 | 7 / 14 |
| duration | 180 s | 360 s |
| governed requests | 24 | 64 |
| underlying operations | 32 | 96 |
| bytes | 16 MiB | 32 MiB |
| observation rows | 64 | 192 |
| Scheduler jobs | 24 | 64 |

Per-source request ceilings are persisted in the immutable policy JSON. The
minimum source group is DexScreener/GeckoTerminal nomination plus required
approved Solana RPC exact verification and first-class Pump creation/migration
attempts. There is no retry, reconnect, endpoint rotation or successor.

## Schema and migration

Migration `049_candidate_acquisition_integration.sql` adds:

- acquisition integration executions and immutable terminal identity;
- acquisition-scoped leases and one-active-owner constraint;
- Scheduler/source-linked work rows;
- one immutable row per underlying transport operation;
- durable current cursor heads joined to immutable migration-048 ranges; and
- immutable integration reports and replay identity.

A fresh disposable DB applied all 49 migrations, latest 049, with
`integrity_check=ok` and zero foreign-key violations. A byte copy of the
authoritative 47-migration DB advanced through migrations 048 and 049, latest
049, with `integrity_check=ok` and zero foreign-key violations. Existing rows
were preserved by the forward-only canonical migration runner. Recovery remains
restore of the verified pre-migration byte backup; the authoritative DB was not
migrated in this task.

## Offline capacity and integration matrix

| Case | Result | Terminal evidence |
| --- | --- | --- |
| N=2 | PASS | exactly 2 selected; two-item neutral manifest; legacy projection count 2; runtime handoff 0; lease released; deterministic replay |
| N=7 | PASS | exactly 7 selected; runtime-neutral manifest; projection count 0; direct legacy-adapter rejection; runtime handoff 0; lease released; deterministic replay |
| N-1 | PASS | no partial manifest; `INSUFFICIENT_ELIGIBLE_POOL` |
| required source outage | PASS | `REQUIRED_SOURCE_FAILURE`, not shortage |
| optional source outage | PASS | honest degradation; success only from sufficient remaining evidence |
| source budget exhaustion | PASS | `SOURCE_REQUEST_BUDGET_EXHAUSTED` before excess execution |
| gapped cursor | PASS | `CURSOR_CONTINUITY_GAPPED`; no cursor advance |
| unsupported Pump contract | PASS | `UNSUPPORTED_CONTRACT`; no manifest |
| identity conflict | PASS | `IDENTITY_MERGE_FAILURE` |
| stale evidence | PASS | expired/stale evidence excluded from certificates |
| cancellation | PASS | immutable `ACQUISITION_CANCELLED`; lease released |
| renewal failure | PASS | immutable `LEASE_RENEWAL_UNCONFIRMED`; lease released |
| active/expired competing lease | PASS | active owner blocks cleanly; expired owner recovers once before new acquisition |
| repeated execution/report replay | PASS | identical report; zero new source, Scheduler or report writes |
| tracking/cooldown race | PASS | atomic exact-identity recheck prevents manifest admission |

Every successful operation has one Scheduler job, one governed request and its
exact declared underlying-operation rows. Happy-path Scheduler residue is zero;
unexpected active jobs are failed with zero retries during safe stop. Protected
tracking, snapshot, window, memory, retrieval, decision, position, trade, audit
and PnL table deltas are all zero.

This is an integration-mechanics proof using committed frozen fixtures. It is
not an independently frozen real-observation window and does not establish a
99% or other live acquisition reliability claim. Reliability remains
`UNPROVEN_NO_INDEPENDENT_SAMPLE`.

## Verification totals

- focused foundation/integration suite: 37 passed;
- broad directly affected closeout suite: 313 passed plus 4 subtests;
- Python compilation: pass;
- `git diff --check`: pass;
- fresh disposable migration: 49/49, integrity ok, zero FK violations;
- authoritative-copy forward migration: 047 -> 049, integrity ok, zero FK violations;
- no live HTTP, RPC, WebSocket, discovery, backfill or provider execution.

## Authoritative DB hashes

- before: `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`
- after: `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`
- byte-identical: yes
- disposable authoritative copy after migrations 048+049:
  `b53d82aa4d131fe86afe0413319ab99d759c333d4a9919b8fa51a1ce4dadb676`

## Files changed

- `AGENTS.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md`
- `docs/printer-v1-v2-9-8b-candidate-acquisition-post-foundation-integration-audit.md`
- `docs/printer-v1-v2-9-8b-candidate-acquisition-post-foundation-integration-design.md`
- `docs/printer-v1-v2-9-8b-candidate-acquisition-post-foundation-integration-closeout.md`
- `migrations/049_candidate_acquisition_integration.sql`
- `src/printer_v1/discovery/candidate_acquisition.py`
- `src/printer_v1/operator_cli/candidate_acquisition_integration.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/sources/geckoterminal.py`
- `tests/test_v2_9_8b_candidate_acquisition_foundation.py`
- `tests/test_v2_9_8b_candidate_acquisition_post_foundation_integration.py`
- `tests/test_v2_9_8b_10_post_selection_lifecycle_integrity.py`
- `tests/test_v2_9_8b_19_production_readiness_consolidation.py`

## Money-usefulness contribution

Printer can now fill a durable candidate reserve and produce an exact neutral
intake manifest without conflating provider, budget, coverage, identity,
admission and genuine market-supply failures. Atomic tracking/cooldown and
cursor checks prevent duplicated or discontinuous candidates from contaminating
future bounded memory collection. This improves the honesty and efficiency of
future intake without making a decision, position or profit claim.

## What improved

- the old discovery-only supply slice is no longer the candidate-foundation
  integration boundary;
- exact N=2 and neutral N=7 use the same canonical owner and failure law;
- every external unit is Scheduler-owned, Governor-recorded and operation-ledgered;
- cursor advancement, certificate/reserve/manifest writes and tracking/cooldown
  rechecks are atomic;
- competing owners, cancellations and terminal residue fail closed;
- report replay is deterministic and zero-source; and
- active documentation names one unambiguous next lane.

## What remains locked

Active Memory Factory capacity remains exactly two. N=7 never reaches runtime.
Tracking, snapshots, 5m/15m/1h windows, memory creation, continuation,
retrieval, decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL,
wallets, signing, real funds, paid APIs and live execution remain locked. No
selective-1h proof or operational campaign is authorized.

## Functionality Risks / Setbacks / Efficiency Blockers

- real provider availability, cross-source yield and real-market eligibility
  have not been measured by an independently frozen live window;
- the future live proof must construct the approved bounded transport owner
  explicitly; no default live transport is silently enabled;
- the authoritative DB remains at migration 047 and may receive 048+049 only
  after explicit authorization, quiescent backup, hash verification and restore
  rehearsal;
- public RPC pruning or Pump cursor gaps can honestly block acquisition; budgets
  must not be increased merely to force N; and
- optional safety evidence may reduce eligible yield but may never be treated as
  implicit safety.

## Commit and exact next permitted task

Commit subject: `Integrate candidate acquisition foundation`

The exact next permitted task is:

```text
V2-9.8B Final Bounded Live Candidate-Acquisition Proof
Stage A: one no-retry ACQUISITION_ONLY_N2 execution and terminal inspection
Stage B: only after Stage A PASS, one separate no-retry ACQUISITION_ONLY_N7 execution
```

That task requires separate explicit operator authorization, verified DB backup
and disposable restore/migration rehearsal. It must stop acquisition-only with
zero lifecycle work. It does not authorize the operational Memory Factory
campaign or any retrieval or financial capability.
