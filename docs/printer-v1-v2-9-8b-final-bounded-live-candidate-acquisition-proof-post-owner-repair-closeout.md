# Printer V1 V2-9.8B Final Bounded Live Candidate-Acquisition Proof — Post Transport-Owner Repair Closeout

Date: 2026-07-29

Starting HEAD: `34100c97f7cc21488591fe7567ba5a3211b62ebf`

Lane: `V2-9.8B Final Bounded Live Candidate-Acquisition Proof — Post Transport-Owner Repair`

## Final verdict

`V2_9_8B_FINAL_BOUNDED_LIVE_CANDIDATE_ACQUISITION_PROOF_BLOCKED`

Stage A (`ACQUISITION_ONLY_N2`) was invoked exactly once through the canonical
public operational command after the transport-owner repair. It reached a
canonical terminal state of `BLOCKED` with exact cause `CANDIDATE_LIMIT` after
governed live transport completed and before foundation admission, certificate
issue, or manifest creation.

Stage A therefore failed the required success gates (exact two admitted
certificates, exact two-item manifest, legacy projection count two, and
canonical `COMPLETED` status).

Stage B (`ACQUISITION_ONLY_N7`) is `NOT_RUN`.

No retry, restart, successor, code change, configuration change, budget
increase, provider substitution, operational campaign, tracking, lifecycle,
snapshot, window, memory, retrieval, or financial work was performed.

The earlier blocked pre-repair proof closeout remains preserved history:

- `docs/printer-v1-v2-9-8b-final-bounded-live-candidate-acquisition-proof-closeout.md`
  (`V2_9_8B_FINAL_BOUNDED_LIVE_CANDIDATE_ACQUISITION_PROOF_BLOCKED` for
  `APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED`)

## Baseline and worktree

| Check | Result |
| --- | --- |
| required HEAD | exact match: `34100c97f7cc21488591fe7567ba5a3211b62ebf` |
| branch | `master` |
| tracked worktree/index | clean before Stage A |
| untracked inventory | none before Stage A |
| authoritative DB | `data/printer_v1.sqlite3` |
| latest migration | exact `049_candidate_acquisition_integration.sql` (49 rows) |
| pre-Stage-A DB size | 16,826,368 bytes |
| pre-Stage-A DB SHA-256 | `e6748de305800fc65ce287ef00e72be0ba7910ae7766f8331280f35da4aa07df` |
| integrity / FK before | `ok` / zero violations |
| active Printer/campaign/acquisition process | none |
| active acquisition lease | zero |
| active Scheduler work | zero (`PENDING`/`RUNNING`/`COOLDOWN`/locked = 0) |
| SQLite sidecars | none |
| `PRINTER_SOLANA_RPC_URL` | present, HTTPS-only, hostname present; full URL never printed or persisted |

## DB backup

Host-only artifact directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260729T124351Z-05896a69446d`

Verified pre-Stage-A backup:

`.../printer_v1.pre-stage-a-n2.backup.sqlite3`

| Evidence | Result |
| --- | --- |
| backup size | 16,826,368 bytes |
| backup SHA-256 | `e6748de305800fc65ce287ef00e72be0ba7910ae7766f8331280f35da4aa07df` |
| size/hash equality vs source | PASS |
| backup integrity / FK (read-only open) | `ok` / zero violations |
| backup latest migration | `049_candidate_acquisition_integration.sql` |
| restore after Stage A | not performed; DB integrity, migration state, and capability locks remained clean after expected acquisition writes |

## Canonical command path

Exactly one Stage A invocation:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

The public dispatch constructed `LiveCandidateAcquisitionTransportOwner` through
the normal approved path. No private injector, direct adapter, proof launcher,
`python -c`, or legacy discovery path was used.

Immutable N2 policy ceilings remained unchanged:

| Ceiling | Value |
| --- | ---: |
| selection_capacity | 2 |
| candidate_limit | 4 |
| duration_seconds | 180 |
| governed_request_ceiling | 24 |
| transport_operation_ceiling | 32 |
| byte_ceiling | 16,777,216 |
| row_ceiling | 64 |
| scheduler_job_ceiling | 24 |

## Stage A — `ACQUISITION_ONLY_N2`

| Field | Result |
| --- | --- |
| exit code | `0` (terminal report emitted; status `BLOCKED`) |
| status | `BLOCKED` |
| first_terminal_cause / failure_detail | `CANDIDATE_LIMIT` |
| execution_id | `20260729T124405Z-acq-2f658ff333d7` |
| integration_id | `cain-fdc50b90b7e8c3bbdbf32022bdea7c03` |
| mode | `ACQUISITION_ONLY_N2` |
| selected_count | `0` |
| certificates | `0` |
| manifests / items | `0` / `0` |
| projection_count | `0` |
| runtime_handoff_count | `0` |
| lifecycle_started | `false` |
| foundation_execution_id | `null` (foundation not entered) |
| automatic_retry / restart / successor | `false` / `false` / `false` |
| active_lease_count | `0` |
| scheduler_residue_terminalized | `0` |
| reliability_claim_status | `UNPROVEN_NO_INDEPENDENT_SAMPLE` |

### Source / Scheduler / operation accounting

| Counter | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Scheduler jobs total | 1,121 | 1,137 | +16 |
| active Scheduler jobs | 0 | 0 | 0 |
| Source requests | 1,456 | 1,472 | +16 |
| Source responses | 1,343 | 1,359 | +16 |
| Source failures | 113 | 113 | 0 |
| acquisition integrations | 0 | 1 | +1 |
| acquisition leases (active) | 0 (0) | 1 (0) | +1 terminalized/released |
| acquisition work rows | 0 | 16 | +16 |
| transport-operation rows | 0 | 15 | +15 |
| foundation executions | 0 | 0 | 0 |
| certificates / manifests / items | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| cursor heads / ranges | 0 / 0 | 0 / 0 | 0 |
| integration reports | 0 | 1 | +1 |

Stdout and durable integration report:

- `scheduler_jobs_created` = 16
- `governed_requests_used` = 16
- `transport_operations_used` = 15
- `bytes_used` = 105,805
- `rows_used` = 25

Reconciliation:

- 16 work rows, each with exactly one Scheduler job and one governed source request;
- 16 distinct Scheduler job IDs and 16 distinct source request IDs;
- all 16 work rows `SUCCEEDED` / `SOURCE_OPERATION_COMPLETE`;
- all 16 source requests `COMPLETE`; all 16 responses present; zero source failures;
- 15 durable underlying transport operations, all `COMPLETE`;
- declared zero-transport materialization / empty-slot work accounts for
  `transport_operations_used` (15) being one below governed requests (16) in the
  exact operation plan sense already proven offline; every external operation
  still has one job and one governed request.

Work plan outcomes (redacted roles only):

| Ord | Source / kind | Required | Ops | Notes |
| ---: | --- | --- | ---: | --- |
| 1 | dexscreener / candidate_nomination | no | 2 | Dex profiles + market composite |
| 2 | geckoterminal / candidate_nomination | no | 1 | new pools |
| 3 | dexscreener / candidate_market_batch | no | 0 | zero-transport materialization |
| 4 | geckoterminal / candidate_market_batch | no | 0 | zero-transport materialization |
| 5 | solana_rpc / pumpfun_create_index_signature_page | yes | 1 | |
| 6–7 | solana_rpc / pumpfun_create_index_transaction | yes | 1 each | |
| 8 | solana_rpc / pumpfun_migration_signature_page | yes | 1 | |
| 9–10 | solana_rpc / pumpfun_migration_transaction | yes | 0 each | empty/no-fetch slots after page |
| 11 | solana_rpc / candidate_mint_account_batch | yes | 1 | |
| 12 | solana_rpc / pumpswap_pool_account_batch | yes | 1 | |
| 13–14 | solana_rpc / holder_concentration_reference | yes | 2 each | largest-accounts + supply composite |
| 15–16 | goplus / safety_reference | no | 1 each | optional; completed |

Budgets unbreached relative to immutable ceilings:

- governed requests 16 ≤ 24
- transport operations 15 ≤ 32
- bytes 105,805 ≤ 16,777,216
- rows 25 ≤ 64
- scheduler jobs 16 ≤ 24
- selected 0 ≤ capacity 2

Cursor advancement: none. No cursor head or range rows were written, so no
gapped/unknown advance occurred.

### Candidate funnel

| Funnel stage | Count |
| --- | ---: |
| observation rows accounted (`rows_used`) | 25 |
| approx. unique mint-like identities across response payloads | 6 |
| immutable N2 `candidate_limit` | 4 |
| foundation executions | 0 |
| identities / reserve | 0 / 0 |
| certificates admitted | 0 |
| manifest items | 0 |
| legacy projection | 0 |
| runtime handoff | 0 |

Exact terminal mechanism (code path already committed; not modified):

```text
unique_mints = {observation.mint for observation rows with mint}
if len(unique_mints) > policy.candidate_limit:  # 4 for N2
    raise CandidateAcquisitionIntegrationError("CANDIDATE_LIMIT")
```

Foundation `run_candidate_acquisition` was never called. This is a unique-mint
ceiling stop after live multi-source observation accumulation, not a market
shortage label and not `INSUFFICIENT_ELIGIBLE_POOL`.

### Acceptance gates

| Gate | Result |
| --- | --- |
| successful canonical terminal state (`COMPLETED`) | FAIL (`BLOCKED`) |
| exactly one N2 execution; no retry/restart/successor | PASS |
| exactly two distinct admitted certificates | FAIL (0) |
| one exact two-item immutable manifest | FAIL (0) |
| manifest and certificate hashes verify | FAIL (none issued) |
| legacy projection count exactly two | FAIL (0) |
| runtime handoff count zero | PASS |
| no tracking or lifecycle work | PASS |
| every external op has one Scheduler job and one governed request | PASS |
| truthful required/optional source outcomes | PASS |
| budgets/ceilings unbreached | PASS |
| cursor advancement only for contiguous evidence | PASS (no advance) |
| zero active acquisition lease | PASS |
| zero active Scheduler work | PASS |
| deterministic zero-source replay | PASS (replay equals terminal report; +0 source/sched/ops) |
| integrity `ok` and zero FK violations | PASS |
| all protected-table deltas zero | PASS |

Stage A overall: **FAIL** (success gates not met).

### Report / replay

One integration report row exists for execution
`20260729T124405Z-acq-2f658ff333d7`. Public zero-source replay returned the
identical terminal JSON and performed zero new source requests, Scheduler jobs,
or transport operations.

### Protected-table deltas

All protected surfaces remained unchanged:

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
| Memory Factory campaigns / runs / cycles / slots / windows / runs / steps | unchanged | unchanged | 0 |

Stdout `forbidden_table_deltas` all zero; independent recount agrees.

### Integrity and residue

| Check | After Stage A |
| --- | --- |
| DB SHA-256 | `516e2b000eb8f2bd10341a5464bb2bcfb19ecf7986f7a011864ce7390b124d1a` |
| latest migration | still `049_candidate_acquisition_integration.sql` |
| integrity | `ok` |
| foreign-key violations | 0 |
| active acquisition lease | 0 (lease released; terminal cause `CANDIDATE_LIMIT`) |
| active Scheduler residue | 0 |
| sidecars | none |
| secrets / full RPC URL in stdout, stderr, report, or committed artifact | none |

## Stage B — `ACQUISITION_ONLY_N7`

`NOT_RUN`

Stage B was not authorized because Stage A did not pass every acceptance gate.
No N7 execution identity, lease, manifest, projection, legacy-adapter rejection
check, source request, or Scheduler job exists for N7.

## Blocker classification

```text
BLOCKER CLASSIFICATION: CANDIDATE_LIMIT (unique-mint ceiling after live observation)
EVIDENCE: exactly one public N2 run completed all 16 planned work items through
  Central Scheduler and Source Governor, then stopped with CANDIDATE_LIMIT because
  unique observation mints exceeded the immutable N2 candidate_limit of 4 before
  foundation admission. Foundation execution, certificates, and manifest were not
  created. Approx. unique mint-like identities in response payloads: 6 > 4.
OFFICIAL-SOURCE COMPARISON: live DexScreener, GeckoTerminal, Solana RPC, Pump
  create/migration reads, PumpSwap pool reads, and optional GoPlus completed
  without source-failure rows. The stop is policy-ceiling enforcement on the
  accumulated observation set, not a provider HTTP/RPC outage and not an
  unsupported Pump/PumpSwap contract failure.
PRINTER-CONTRACT COMPARISON: immutable N2 ceilings were not modified. The
  integration correctly fails closed when unique mints exceed candidate_limit.
  This is distinct from INSUFFICIENT_ELIGIBLE_POOL, admission failure, cursor
  GAPPED/UNKNOWN/BLOCKED_CONTRACT, rate limit, timeout, and authentication.
ROOT CAUSE: live multi-source observation accumulation produced more unique
  mint identities than the frozen N2 candidate_limit before foundation could
  select exact N=2. Offline frozen fixtures did not exercise this live density
  interaction.
CODE CHANGE JUSTIFIED: not authorized by this proof prompt. Any repair requires
  a separate source-grounded investigation under the Python builder guide and a
  later explicit repair lane. Do not raise ceilings to force success.
MINIMUM SAFE RESPONSE: preserve the terminal report and accounting; do not
  retry N2; do not run N7; do not change code or configuration in this lane.
FOCUSED PROOF: future re-proof only after an operator-authorized repair or
  policy investigation and a new explicit proof prompt.
UNTOUCHED SCOPE: operational campaign, tracking, lifecycle, snapshots, windows,
  memory, selective 1h, retrieval, decisions, and all financial surfaces.
AUTHORIZATION STATUS: repair, retry, N7, and campaign remain unauthorized.
NEXT ROADMAP-COMPLIANT STEP: operator decision on a separate source-grounded
  investigation/repair lane for live unique-observation density versus the
  frozen N2 candidate_limit, before any new bounded live acquisition proof.
```

## Live reliability status

`UNPROVEN_SINGLE_BLOCKED_SAMPLE`

This lane produced exactly one independent live N2 sample. That sample proved:

- public construction of `LiveCandidateAcquisitionTransportOwner` works live;
- Scheduler/Governor ownership, accounting, lease release, protected-table
  isolation, integrity, and zero-source replay hold under live load;
- the run did **not** prove successful exact-N admission or manifest readiness.

Do not claim general real-market reliability, and do not claim 99% reliability,
from this single blocked execution.

## Money-usefulness contribution

Positive:

- confirmed the post-repair public live path no longer dies on missing transport
  owner before any source work;
- confirmed acquisition-only surfaces can write while all memory/financial
  protected tables remain zero-delta;
- produced truthful terminal evidence of a live ceiling interaction that offline
  fixtures did not surface.

Negative / incomplete:

- no admitted certificates and no immutable two-item manifest;
- no clean acquisition corpus growth usable by later retrieval or paper memory;
- Stage B capacity-neutral N=7 proof remains unexecuted.

## Remaining locks

Unchanged and still locked:

- Solana-only / Solana memecoin-only
- paper-only; no wallet, private keys, signing, transaction submission, real funds
- no paid sources; DEXTools, PumpPortal, Birdeye, Helius remain excluded
- no scoring, ranking, confidence, weighting, embeddings, or vectors
- no Scheduler or Source Governor bypass
- active Memory Factory capacity exactly two
- no operational campaign
- no tracking/lifecycle start; no snapshots or memory windows
- no selective-1h proof
- no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL
- GoPlus remains optional

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Live unique-mint density vs frozen N2 `candidate_limit=4`** — the dominant
   blocker. Multi-source observation rows can exceed four unique mints even when
   selection capacity is two. Offline proofs used controlled fixture counts and
   did not reveal this live stop.
2. **No automatic thinning path is authorized** — raising ceilings, preferring
   sources, or scoring candidates would violate V1 locks and frozen proof policy.
3. **Foundation never entered** — so admission quality, certificate hashing,
   legacy N2 projection, and real cursor continuity under success remain unproven
   live.
4. **Holder evidence authenticity** remains partial (`getTokenLargestAccounts`
   wallet-level limits). GoPlus absence would be optional degradation; here GoPlus
   completed and was not the stop cause.
5. **Single blocked sample** cannot establish live reliability. A future PASS
   still would be only two stage samples, not general market reliability.
6. **Public free-source pruning/latency** can still block later attempts even
   after a density repair.

## Exact next roadmap step

```text
Operator decision required:
  separate source-grounded investigation / optional repair lane for
  live unique-observation accumulation versus immutable N2 candidate_limit,
  without raising ceilings to force success, without operational campaign,
  and without N2 retry or N7 until a new explicit proof prompt authorizes it.
```

Do not treat this closeout as authorization to repair, retry, run N7, start a
campaign, or unlock any financial capability.

## Redacted proof artifact

Committed redacted Stage A summary (no secrets, no full RPC URL, no raw provider
payloads):

`docs/printer-v1-v2-9-8b-final-bounded-live-candidate-acquisition-proof-post-owner-repair-stage-a-redacted.json`

Host-only full inspection and backup remain outside the repository under
`/Users/Dtwo1/PrinterOperations/v2-9-8/20260729T124351Z-05896a69446d`.

## Files changed by this closeout lane

- this closeout document
- redacted Stage A proof artifact
- minimal active-pointer updates in `AGENTS.md`,
  `docs/printer-v1-assistant-active-build-order-anchor.md`, and
  `docs/printer-v1-memory-growth-build-order-v2.md`

No Python code, configuration, policy ceilings, migrations, or databases were
committed.
