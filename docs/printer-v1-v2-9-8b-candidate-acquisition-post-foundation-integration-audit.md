# Printer V1 V2-9.8B Candidate-Acquisition Post-Foundation Integration Audit

Date: 2026-07-29
Gate: 1 of 4 — integration and activation-readiness audit
Verdict: `V2_9_8B_CANDIDATE_ACQUISITION_POST_FOUNDATION_GATE_1_PASS`

## Scope and evidence

This audit starts from exact commit
`164dcd5e570d7de19a84bfa651e0320850f03348`. The tracked worktree and index
were clean, no untracked paths existed, and `data/printer_v1.sqlite3` had
SHA-256 `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`.
No provider, RPC, WebSocket, backfill, or operational command was invoked.

The active source stack, the four foundation records, migration 048, the
candidate foundation, public operational command, Scheduler, Source Governor,
combined discovery, eligible-supply, tracking/cooldown, campaign supervision,
report/replay, source adapters, and directly affected tests were inspected.

Python Builder Guide classification:

```text
BLOCKER CLASSIFICATION: MISSING_APPROVED_IMPLEMENTATION_BOUNDARY
EVIDENCE: migration 048 and the transport-free foundation are complete, but no
  canonical command path schedules source work, holds an acquisition lease,
  invokes the foundation, or projects an exact-two manifest.
OFFICIAL-SOURCE COMPARISON: no provider contract drift was found; the official
  Pump/PumpSwap pins adopted by the foundation remain the authority.
PRINTER-CONTRACT COMPARISON: the legacy discovery-only command explicitly makes
  zero Scheduler calls, defaults to PumpPortal, and bypasses certificate/reserve/
  manifest persistence, contrary to the adopted post-foundation boundary.
ROOT CAUSE: the previous lane intentionally stopped at a transport-free,
  runtime-neutral foundation.
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE: integrate acquisition-only modes into the one public
  command through one finite Scheduler/Source-Governed owner; do not create a
  second public runner or connect lifecycle.
UNTOUCHED SCOPE: operational campaign, tracking, snapshots, windows, memory,
  selective 1h, retrieval, decisions, and financial owners.
AUTHORIZATION STATUS: this combined lane explicitly authorizes implementation
  and disposable proof, but not live source execution or authoritative DB writes.
NEXT ROADMAP-COMPLIANT STEP: Gate 2 complete integration design.
```

## Canonical owner map

| Concern | Existing canonical owner | Integration conclusion |
| --- | --- | --- |
| Public command and explicit approval | `operator_cli/operational_memory_factory_command.py` | add bounded modes here; no second CLI |
| Operational preflight | `build_activation_preflight` plus source-contract, dependency, migration-ledger, integrity, capability-lock, and Git checks | reuse for a future authoritative run; offline proof injects a validated disposable preflight because a pre-commit worktree is intentionally dirty |
| Scheduler | `scheduler.scheduler` with `JobKind.DISCOVERY_REFRESH` and Resource Governor priority | one finite job per declared acquisition operation; claim and terminalize with `max_retries=0` |
| Source Governor and source ledger | `sources.governor`, `sources.contracts`, `sources.governed_execution`, source request/response/failure tables | every provider request must be admitted and persisted before transport; underlying operations also require exact durable counts |
| DexScreener | existing disabled-by-default adapter and fresh-profile/batch transports | reusable for nomination and present-market facts; may nominate directly |
| GeckoTerminal | existing disabled-by-default adapter and new-pool/exact-pool transports | reusable for nomination and present-market facts; may nominate directly |
| Solana RPC | existing one-shot RPC, Pump origin kernel, holder, mint-age, PumpSwap and strict foundation decoders | reusable read-only transport/decoder pieces; integration must wrap each operation in Scheduler/Governor accounting |
| Pump creation | `pumpfun_origin` shared finalized decode/cursor kernel plus foundation `pump_contracts` pins | one owner, bounded `LIVE_TAIL` or `BACKFILL`; no private loop |
| Pump migration | strict foundation migration decoder, program-wide finalized signature pages, finalized v0 transaction decode | no PumpPortal locator; bounded program-address pages only; budget end is coverage failure, not absence proof |
| Candidate composition | `discovery/candidate_acquisition.py` | sole certificate/reserve/manifest owner |
| Tracking and cooldown state | tracking queue exact-identity assessment and selection-rotation state | recheck under the same immediate transaction that issues certificates/manifests |
| Runtime projection | `legacy_two_token_runtime_projection` | N=2 validation only; read-only; no slot/queue/job creation; never called for N=7 |
| Campaign supervision | campaign-only DB/file lease owner requires campaign/config/run rows | cannot be reused without falsely creating an operational campaign; an acquisition-scoped lease using the same finite acquire/renew/cancel/release/first-cause law is required |
| Report/replay | foundation canonical report/replay plus public report-only conventions | persist one integration terminal report; replay is read-only and zero-source |
| Migration | canonical forward-only migration runner | 048 and the integration migration apply only to a disposable copy in this lane; future authoritative adoption requires explicit backup/authorization |

## Confirmed integration defects

1. `discovery-only` uses `run_persistent_eligible_token_supply`, not immutable
   candidate certificates, the capacity-neutral reserve, or exact-N manifests.
2. Its docstring and report assert zero Central Scheduler runtime calls. It
   therefore cannot be renamed into a Scheduler-owned acquisition proof.
3. Its default migration locator is PumpPortal, whose current foundation use is
   prohibited.
4. It is fixed at two and cannot produce a neutral N=7 manifest.
5. It creates neither an acquisition execution lease nor durable acquisition
   work identities and has no lease renewal/cancellation/recovery contract.
6. It slices an eligible list instead of consuming the deterministic exact-N
   manifest and does not project through the strict legacy adapter.
7. The foundation validates declared Governor kinds but does not itself persist
   transport request/response/failure rows; the integration owner must do so.
8. Foundation cursor ranges are immutable execution evidence, but migration 048
   has no durable current cursor head shared across executions.
9. Tracking and selection cooldown are represented in supplied facts, but the
   foundation did not atomically re-read authoritative queue/rotation state.
10. There is no acquisition-level canonical terminal report containing lease,
    Scheduler, underlying operation, projection, and cleanup evidence.
11. Active anchors contain stale historical pointers saying the next task is
    the Direct Pump/PumpSwap audit and one assistant section still calls
    DexScreener/GeckoTerminal enrichment-only.

None requires guessing a provider layout. They are missing integration owners
and stopping boundaries covered by this explicit lane.

## Concurrency, lease, cursor, and transaction findings

- A future acquisition must hold one global acquisition lease. It must not
  create `printer_memory_factory_campaign*` rows because acquisition-only is not
  an operational campaign.
- Lease acquire uses `BEGIN IMMEDIATE`; an unexpired active owner blocks. An
  expired owner is terminalized once as recovered before a new owner starts.
  Renew requires exact owner identity and unexpired state. Cancellation changes
  the lease to `STOPPING`. Cleanup writes the immutable first terminal cause and
  releases the lease in all exits.
- One integration execution owns all operation work. Each operation has one
  Scheduler job, one governed source request, at most one response or failure,
  and a declared underlying-operation count. No retry, cooldown successor,
  reconnect, endpoint rotation, or automatic successor is allowed.
- Cursor namespace is network, indexed address, official contract pin, decoder
  version, and direction. A range start must match the current durable head.
  Only `CONTIGUOUS` evidence with an exact terminal boundary may advance. Range
  evidence and cursor advancement must commit in the foundation transaction.
- Reserve and manifest writes already occur atomically in the foundation. The
  same `BEGIN IMMEDIATE` transaction must first recheck exact tracking state and
  legacy selection cooldown, preventing a concurrent handoff from admitting a
  stale candidate.
- A same execution/input replay returns the stored report. A changed input,
  cursor head, tracking state, or policy under the same identity is a conflict.

## Safe first-live-proof ceilings

These are ceilings, not reliability promises and not permission to run them.
They are derived from N, the foundation `M=2N` intake bound, existing provider
batch sizes/rate limits, Pump create decode ceilings, and zero retries.

| Ceiling | `ACQUISITION_ONLY_N2` | `ACQUISITION_ONLY_N7` |
| --- | ---: | ---: |
| N / maximum unique candidates M | 2 / 4 | 7 / 14 |
| total duration | 180 s | 360 s |
| total governed requests | 24 | 64 |
| total underlying operations | 32 | 96 |
| response bytes | 16 MiB | 32 MiB |
| observation rows | 64 | 192 |
| Scheduler jobs | 24 | 64 |
| DexScreener nomination / market requests | 1 / 1 | 1 / 1 |
| GeckoTerminal nomination / exact-pool requests | 1 / up to 4 | 1 / up to 10 |
| Pump create signature pages / transactions | 1 / 4 | 2 / 10 |
| Pump migration signature pages / transactions | 1 / 4 | 2 / 10 |
| mint/pool account batches | 1 / 1 | 1 / 1 |
| holder requests | up to 4 | up to 14 |
| optional GoPlus requests | up to 4 | up to 14 |

DexScreener and GeckoTerminal form a required nomination group: either may
degrade individually, but at least one must provide complete fresh nomination
coverage. Approved Solana RPC exact verification is required. Pump creation and
migration lanes are required first-class attempted lanes; a provider/RPC fault,
contract block, or gap is terminal and distinct from shortage. GoPlus is
optional; absence never becomes safety and candidates lacking adopted safety
evidence simply fail admission. Birdeye is optional and not required. DEXTools
and PumpPortal are excluded.

## Handoff and capability boundary

N=2 may call the strict legacy projection only after manifest hash and atomic
tracking/cooldown recheck pass. The projection is immutable input to a future
campaign handoff, but acquisition-only reports a projection count of two while
creating no token slot, tracking queue, Scheduler lifecycle job, snapshot,
window, memory, retrieval, decision, or financial row.

N=7 never calls the adapter. Any attempted call must fail
`LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO`. Every manifest remains
`runtime_neutral=1` and active capacity remains exactly two.

## DB adoption and reliability

The authoritative DB currently predates migration 048. This task may apply 048
and the integration migration only to fresh temporary DBs or byte copies. A
future live proof requires: quiescent SQLite, byte backup, source and backup
hashes, disposable restore rehearsal, explicit operator authorization, forward
migration ledger/integrity/FK proof, and post-proof source DB hash reporting.
Restore of the verified pre-migration backup is the rollback law.

No independently frozen qualifying real-market window exists for this
integrated source plan. The foundation mechanics and this lane's offline
integration can pass; acquisition reliability and any 99% claim remain
`UNPROVEN_NO_INDEPENDENT_SAMPLE`.

## Gate result

Gate 1 passes. Canonical owners, missing boundaries, concurrency law, cursor
law, source groups, exact ceilings, DB adoption prerequisites, failure
semantics, and reliability limits are known without inventing a provider or
protocol contract.
