# Printer V1 V2-9.8B 4/2/2 Orchestration Correctness Implementation Closeout

Date: 2026-08-28

## 1. Verdict

`V2_9_8B_4_2_2_ORCHESTRATION_CORRECTNESS_IMPLEMENTATION_PASS`

All four defects proven by the consumed 4/2/2 campaign forensic audit now have
focused production repairs and bounded offline GREEN proof. No authorization
was created, no live campaign ran, no live provider/RPC/WebSocket was contacted,
and the authoritative database was not migrated or mutated.

This is an implementation closeout only. It is not operational readiness for a
new campaign because additive migration 062 has not been applied to the
authoritative database.

## 2. Implemented repairs

### Defect 1 — 1h campaign-window binding order

The selective-1h close path now resolves the exact owned `WINDOW_1H` campaign
row, validates campaign/run/cycle/slot/token/pair/window/memory identity, binds
the physical memory row idempotently, commits and reads it back, and only then
runs E2Z/Lane Q. Missing, ambiguous, or conflicting ownership still fails
closed. Lane Q, Lane K, terminal cause, memory quality, and progression rules
were not weakened.

### Defect 2 — Cycle-2 cooperative acquisition cadence

The existing attempt, Central Scheduler, temporal refresh, Source Governor,
deterministic request, and StageBudget owners remain authoritative. Direct
migration now performs at most one missing Source-Governed request per
cooperative claim. PumpSwap verification remains one governed request with its
full multi-transport bound. Terminal request replay is limited to cooperative
resume, emits no duplicate action-local transport, and ordinary independent
discovery invocations preserve their fresh-versus-persisted semantics.

Temporal opportunities are anchored to the explicit acquisition-start identity
at +600, +1200, and +1800 seconds. Incomplete refresh work yields and reclaims
the same wait/work/Scheduler owner. A request starts only when its full governed
request bound plus checkpoint reserve fits before both the next lifecycle
deadline and the acquisition horizon.

### Defect 3 — durable Cycle-2 terminal evidence

Migration `062_pre_admission_attempt_evidence.sql` adds only an append-only,
attempt-owned evidence ledger with immutable-row triggers and exact ownership/
event identities. The attempt callback records opportunities, cooperative
claims, source results/failures, candidate observations/re-observations,
rejections, duplicates, exact-pair/PumpSwap/liquidity/safety outcomes, and final
disposition. The terminal exhaustion certificate is rebuilt by a deterministic
reducer from durable attempt evidence rather than final-call locals.

No score, rank, confidence, generic acquisition-quantum table, second scheduler,
or second discovery owner was added.

### Defect 4 — full-run accounting aggregation

Later-cycle holder evaluation now receives the independent action-local
transport observer. Cooperative pre-close claims cumulatively preserve every
exact reservation record; exact replay is idempotent and ordinal/ownership
conflicts fail closed. Full-run sealing reconstructs pre-close reservation
identities from durable cumulative records while ordinary lifecycle steps retain
their static reservation contract. Strict owner/action-local equality remains
unchanged.

## 3. Commits

- `64e3ab3` — governance sync and Cycle-2 design amendment
- `57d4804` — implementation plan
- `f4486bd` — 1h pre-E2Z campaign-window binding
- `5d67716` — cooperative governed-request acquisition quanta
- `9f27096` — durable pre-admission attempt evidence and migration 062
- `87d40c0` — full-run transport/reservation accounting reconciliation
- `1c74c4d` — cooperative replay scope, temporal anchor, and migration-head regression correction

## 4. Bounded GREEN proof

Final acceptance groups, all using disposable/offline fixtures:

- binding, clean 1h-to-4h evaluation, migration-061/062 coexistence, and
  progression: **71 passed**;
- direct migration, one-request cooperative acquisition, cadence isolation,
  persistent refresh ownership, later-cycle acquisition, and eligible supply:
  **123 passed, 2 deselected**;
- attempt evidence, exhaustion reconstruction, migration ordering, schema
  coherence, and provenance alignment: **74 passed, 8 subtests passed**;
- full-run accounting, terminal evidence, cumulative pre-close work, later-cycle
  failure domain, holder transport identity, and campaign accounting terminal
  enforcement: **120 passed, 6 subtests passed**.

Final total: **388 passed, 14 subtests passed, 2 deselected, 0 failed**.

The two deselected eligible-supply tests are unchanged historical tests already
failing at baseline on later tracking-queue behavior outside this repair lane.
Additional diagnostic runs confirmed other historical fixture failures at the
baseline, including two selective-1h expectations that omit the already-required
campaign-window binding and use the obsolete three-request safety count. They
were not weakened or rewritten to manufacture a pass.

Static proof includes changed-module compilation/import, canonical migration
ordering/schema tests, and `git diff --check`.

## 5. Migration status and safety

Migration 062 was applied only to disposable test databases. It is additive and
contains no generic quantum table. The authoritative database remains the
post-campaign database with migration 061 as its applied head. Runtime readiness
therefore remains fail-closed until a separately approved controlled migration
lane applies and verifies 062.

The authoritative database SHA-256 remained
`f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`.
Final read-only database checks reported `integrity_check=ok`,
`foreign_key_check=0`, and no WAL/SHM/journal sidecars.

## 6. Preserved invariants and non-goals

One Central Scheduler and one Source Governor remain authoritative. Lifecycle
deadlines retain priority. Provider timeouts, exact Pump migration/PumpSwap,
exact-pair, liquidity, safety, holder, provenance, historical-disjointness,
accounting, and fail-closed rules remain intact. The fixed 2400-second horizon
and fixed temporal opportunities remain intact.

This lane does not unlock `WINDOW_12H`, `WINDOW_24H`, retrieval, BUY/SELL/HOLD,
positions, trades, paper audits, PnL, wallets, signing, real funds, paid APIs,
scores, ranks, confidence, embeddings, or vectors. `WINDOW_5M_MICRO_EVENT`
remains support-only.

## 7. Remaining blocker and next permitted action

The only implementation-readiness blocker created by this lane is the unapplied
authoritative migration 062. A new campaign is not permitted yet.

Exact next permitted lane:

`IMPLEMENTATION PASS -> MIGRATION 062 CONTROLLED APPLICATION READINESS / AUTHORITY GATE`

That gate may inspect and prepare the controlled migration procedure. It does
not itself authorize migration application, a new authorization, or live
Printer execution.
