# Printer V1 V2-9.8B Candidate-Acquisition Post-Foundation Integration Design

Date: 2026-07-29
Depends on: `printer-v1-v2-9-8b-candidate-acquisition-post-foundation-integration-audit.md`
Gate: 2 of 4 — complete integration design
Verdict: `V2_9_8B_CANDIDATE_ACQUISITION_POST_FOUNDATION_GATE_2_PASS`

## Invariants and modes

The only new public modes are:

- `acquisition-only-n2`, policy identity `ACQUISITION_ONLY_N2`;
- `acquisition-only-n7`, policy identity `ACQUISITION_ONLY_N7`.

Both require explicit operator authorization and stop before tracking,
snapshots, windows, memory, continuation, retrieval, decisions, or financial
owners. N=2 validates a read-only legacy projection but does not consume it.
N=7 never invokes the legacy adapter. Approved active Memory Factory capacity
remains exactly two.

## Canonical flow

```text
explicit operator authorization
-> public operational command and existing activation preflight
-> acquisition-scoped lease acquire
-> finite Central Scheduler DISCOVERY_REFRESH work
   -> Source Governor admit and persist exact request
   -> one bounded injected existing transport/decoder operation
   -> persist response/failure and underlying operation count
   -> terminalize Scheduler work with zero retry
-> source-specific candidate observations
-> atomic tracking/cooldown and cursor-head recheck
-> candidate-acquisition foundation
-> immutable certificates and capacity-neutral reserve
-> deterministic exact-N runtime-neutral manifest
-> N=2-only read-only legacy projection validation
-> no lifecycle start and no handoff writes
-> canonical integration report and read-only replay
-> immutable first terminal cause, lease release, safe stop
```

`operational_memory_factory_command.py` remains the only public runner. A
single internal `CandidateAcquisitionIntegrationOwner` composes the lease,
Scheduler, Governor, transport port, foundation, projection, report, and
cleanup. Transports remain dependency-injected and disabled until the command
has passed authorization/preflight. There is no loop hidden in an adapter and
no automatic successor.

## Exact ownership

| Contract | Owner |
| --- | --- |
| command / approval / preflight | public operational command; `build_activation_preflight` |
| Scheduler work kind | Central Scheduler, `DISCOVERY_REFRESH` |
| request admission and source request/response/failure | Source Governor governed execution boundary |
| transport per source | existing DexScreener, GeckoTerminal, one-shot Solana RPC, Pump origin kernel, strict Pump migration/PumpSwap decoders, holder and safety adapters |
| finite execution | `CandidateAcquisitionIntegrationOwner` |
| current cursor and immutable range | integration cursor table plus foundation transaction |
| DB transaction | foundation owner under `BEGIN IMMEDIATE`; integration owner for short lease/work/report transactions |
| lease and cancellation | acquisition integration lease owner |
| reserve/manifest | candidate-acquisition foundation only |
| projection | strict legacy two-token adapter only |
| canonical report/replay | integration report owner; foundation replay remains nested evidence |
| cleanup and first cause | integration owner `finally` path; first non-null terminal cause wins |

## Frozen policy and source plan

The Gate 1 ceiling matrix is the complete policy. Source ordering is:

1. DexScreener nomination;
2. GeckoTerminal nomination;
3. direct Pump create range;
4. direct Pump migration range;
5. exact Solana mint and pool batches;
6. DexScreener and GeckoTerminal present-market confirmation;
7. pair/token age evidence where adopted;
8. holder evidence;
9. optional GoPlus safety;
10. required route/tradeability evidence when the policy requires it.

Ordering controls budgets, not candidate preference. Observations are
canonicalized before deterministic selection. Per-mode exact ceilings are the
Gate 1 table and are persisted in policy JSON. Requests, underlying operations,
bytes, rows, duration, pages, and unique candidates fail before an excess is
executed or persisted as successful.

DexScreener and GeckoTerminal may nominate directly. At least one must complete
the nomination group. Solana RPC exact mint/token-program/pool relationship is
required. Pump lanes are first-class and required for Pump-specific claims;
unknown or non-Pump origin is not rewritten. A gap or unsupported Pump contract
is not a shortage. GoPlus and Birdeye are optional; absent optional evidence is
not converted into safety. DEXTools and PumpPortal have no operation in either
mode.

Each transport result carries exact `governed_requests_used`,
`transport_operations_used`, bytes, rows, duration, status, and optional cursor
range. Multi-call HTTP/RPC transports must report every underlying call. The
integration ledger stores each count even when the operation fails. Provider
faults are never retried.

## Cursor and bounded modes

`LIVE_TAIL` and `BACKFILL` are two values on the same operation plan and use the
same Scheduler/Governor/decoder owner. The cursor namespace is:

```text
network | indexed_address | official_contract_pin | decoder_version | direction
```

The current head is locked and checked under `BEGIN IMMEDIATE`. Range start must
match it when a head exists. Only a `CONTIGUOUS` range with an exact end boundary
and `cursor_advanced=true` updates the head. `GAPPED`, `UNKNOWN`, and
`BLOCKED_CONTRACT` persist immutable range evidence but cannot advance. The
range, accepted/rejected observations, certificates, reserve, manifest, and
cursor head commit or roll back together.

## Lease, cancellation, and first terminal cause

One partial unique index permits one `ACTIVE` or `STOPPING` acquisition lease.
Acquire and renew use bounded `BEGIN IMMEDIATE` transactions. An unexpired
foreign owner blocks. An expired lease is recovered once to terminal state
before a new execution acquires. Renewal requires the exact integration,
execution, owner, mode, and unexpired lease. Cancellation sets `STOPPING` with
an immutable reason; the owner checks before every operation and before the
foundation transaction.

Every exit runs cleanup. The first terminal cause is written once to the
integration execution and lease; later cleanup errors are diagnostics only.
No terminal state creates a retry, reconnect, successor, or endpoint rotation.

## Persistence and migration

Forward migration 049 adds:

1. `printer_candidate_acquisition_integrations` — authorization/preflight,
   mode, exact N, terminal state/cause, manifest/projection and accounting;
2. `printer_candidate_acquisition_leases` — acquisition-only ownership,
   heartbeat, cancellation, recovery, and release;
3. `printer_candidate_acquisition_work` — exact Scheduler/source request and
   response/failure linkage, operation accounting and immutable cursor-range
   evidence even when a required gap stops before foundation invocation;
4. `printer_candidate_acquisition_transport_operations` — immutable one-row
   accounting for every declared underlying HTTP/RPC transport operation;
5. `printer_candidate_acquisition_cursors` — durable current cursor heads;
6. `printer_candidate_acquisition_integration_reports` — immutable terminal
   report/replay identity.

Identity columns and terminal causes are immutable. Mode CHECKs allow only N2
and N7 with exact capacity. Runtime handoff count is always zero. Projection
count is zero or two and only N2 may record two. Work requires one Scheduler job
and one source request; response and failure are mutually exclusive.

Migration 048 and 049 are proved on a fresh DB and a byte copy of the
authoritative DB. The authoritative DB is not opened for migration in this
lane. Future live adoption requires explicit authorization, verified backup and
restore rehearsal, application of both pending migrations, canonical ledger,
integrity/FK proof, and hash reporting. Rollback means restoring the verified
pre-migration bytes, never reversing applied SQL.

## Atomic tracking and cooldown recheck

Before candidate hashes are finalized, the foundation holds `BEGIN IMMEDIATE`
and re-reads the exact mint/pair tracking state for both active lanes. Pending,
running, unexpired cooldown, terminal-reopen-required, or unsupported states set
the categorical tracking gate to fail. It also evaluates token and pair
selection-rotation cooldown using the next legacy batch sequence without
writing rotation state. This recheck becomes part of the canonical input hash.
No token, pair, tracking, Scheduler, slot, or lifecycle row is created.

## Manifest and legacy projection

Exact-N is all-or-none. N=2 invokes the legacy adapter only after the immutable
manifest exists, verifies its hash and two distinct identities, records
`projection_count=2`, and discards the returned read-only value after including
its hash in the report. N=7 records `projection_count=0`; a test directly proves
the adapter rejects the manifest. Projection never means runtime handoff and
`runtime_handoff_count` remains zero.

## Failure and optional-source semantics

Terminal precedence remains:

```text
UNSUPPORTED_CONTRACT
-> SOURCE_PROVIDER_FAILURE
-> BUDGET_EXHAUSTION
-> COVERAGE_FAILURE / cursor gap
-> STALE_OR_INCOMPLETE_EVIDENCE
-> IDENTITY_MERGE_FAILURE
-> ADMISSION_FAILURE
-> INSUFFICIENT_ELIGIBLE_POOL
```

The nomination group tolerates one optional member outage if the other is
complete. A required Solana/Pump contract fault stops. Optional GoPlus/Birdeye
failure is reported and candidates lacking required evidence fail admission;
the provider outage cannot become a safe result or market shortage.
Cancellation and lease renewal failure have higher operational precedence than
candidate outcome. First cause remains immutable.

## Report and replay

The canonical report contains preflight identity, policy/ceilings, lease
history, Scheduler jobs, governed requests, underlying operation totals,
source-group disposition, foundation report/hash, cursor continuity, manifest,
projection count/hash, forbidden table deltas, integrity/FK results, cleanup,
terminal cause, no-retry/successor assertions, active capacity two, and
`UNPROVEN_NO_INDEPENDENT_SAMPLE`.

Integration replay opens SQLite read-only, verifies report hash, foundation
report replay, execution/mode/manifest identities, and returns the stored JSON.
It makes zero source or Scheduler calls and zero writes.

## Offline proof contract

The canonical public dispatch is called with a dependency-injected frozen
transport owner and disposable migrated DB:

- N=2: complete preflight, exact operation ownership/accounting, exact manifest,
  two-item projection, no runtime work, deterministic replay, released lease;
- N=7: separate identity, exact neutral manifest, no adapter call, direct adapter
  rejection proof, no runtime work, deterministic replay, released lease;
- edge cases: N-1, required/optional provider failure, budget exhaustion,
  gapped cursor, unsupported Pump contract, identity conflict, stale evidence,
  true insufficient pool, cancellation, lease renewal failure, repeated
  invocation, and zero forbidden deltas.

Focused tests cover authorization/preflight, Scheduler/Source Governor linkage,
multi-call accounting, cursor atomicity, leases, exact manifests/projection,
tracking/cooldown races, replay, migration 048+049, integrity/FKs, and capability
locks. Broad affected suites run once at closeout. No live reliability claim is
made.

## Gate result

Gate 2 passes. An implementer has exact owners, modes, ceilings, source groups,
transactions, cursor/lease law, schema, failure semantics, proof cases, and
stopping boundaries without inventing an external contract.
