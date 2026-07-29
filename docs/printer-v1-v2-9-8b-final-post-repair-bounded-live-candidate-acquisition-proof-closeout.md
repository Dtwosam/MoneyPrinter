# Printer V1 V2-9.8B Final Post-Repair Bounded Live Candidate-Acquisition Proof Closeout

Date: 2026-07-29

Starting HEAD (full SHA): `a15648661d118a5d59fad7013a4527b2b0230b16`

Starting HEAD (short): `a156486`

Subject: `Repair candidate acquisition pipeline`

Lane: `V2-9.8B Final Post-Repair Bounded Live Candidate-Acquisition Proof`

## Final verdict

`V2_9_8B_FINAL_POST_REPAIR_BOUNDED_LIVE_CANDIDATE_ACQUISITION_PROOF_BLOCKED`

Stage A (`ACQUISITION_ONLY_N2`) was invoked exactly once through the canonical
public operational command after the comprehensive candidate-acquisition pipeline
repair. It reached a canonical terminal state of `BLOCKED` with exact cause
`IDENTITY_MERGE_FAILURE` after:

1. governed live multi-source nomination completed;
2. the repaired integration-owner cohort boundary thinned raw density
   (`39` unique nominations → cohort size `4` ≤ `M=4`);
3. cohort-only enrichment completed with zero out-of-cohort enrichment;
4. foundation admission issued four certificates and rejected all four with
   `MINT_STATUS_FAILED` at funnel stage `CHAIN_MINT_VALID`;
5. exact-N selection failed all-or-none (`selected_count=0`, no manifest).

Stage A therefore failed the required success gates (canonical `COMPLETED`,
exactly two admitted certificates, exact two-item manifest, and legacy
projection count two).

Stage B (`ACQUISITION_ONLY_N7`) is `NOT_RUN`.

No retry, restart, successor, code change, configuration change, budget
increase, provider substitution, operational campaign, tracking, lifecycle,
snapshot, window, memory, retrieval, or financial work was performed.

Preserved historical closeouts remain history:

- `docs/printer-v1-v2-9-8b-final-bounded-live-candidate-acquisition-proof-closeout.md`
  (pre transport-owner: `APPROVED_ACQUISITION_TRANSPORT_OWNER_REQUIRED`)
- `docs/printer-v1-v2-9-8b-final-bounded-live-candidate-acquisition-proof-post-owner-repair-closeout.md`
  (post transport-owner / pre pipeline repair: `CANDIDATE_LIMIT`)
- `docs/printer-v1-v2-9-8b-comprehensive-candidate-acquisition-pipeline-repair-closeout.md`
  (pipeline repair offline PASS; authorized this live re-proof)

## Baseline and worktree

| Check | Result |
| --- | --- |
| required HEAD short | exact match: `a156486` |
| required HEAD full | `a15648661d118a5d59fad7013a4527b2b0230b16` |
| subject | `Repair candidate acquisition pipeline` |
| branch | `master` |
| tracked worktree/index | clean before Stage A |
| untracked inventory | none before Stage A |
| authoritative DB | `data/printer_v1.sqlite3` |
| latest migration | exact `049_candidate_acquisition_integration.sql` (49 rows) |
| pre-Stage-A DB size | 16,867,328 bytes |
| pre-Stage-A DB SHA-256 | `516e2b000eb8f2bd10341a5464bb2bcfb19ecf7986f7a011864ce7390b124d1a` |
| integrity / FK before | `ok` / zero violations |
| active Printer/campaign/acquisition process | none |
| active acquisition lease | zero unreleased |
| active Scheduler work | zero (`PENDING`/`RUNNING`/`COOLDOWN`/locked = 0) |
| SQLite sidecars | none |
| `PRINTER_SOLANA_RPC_URL` | present, HTTPS-only, hostname present, no userinfo/fragment/non-default port; full URL never printed or persisted |

## DB backup

Host-only artifact directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260729T150838Z-final-post-repair-proof`

Verified pre-Stage-A backup:

`.../printer_v1.pre-stage-a-n2.backup.sqlite3`

| Evidence | Result |
| --- | --- |
| backup size | 16,867,328 bytes |
| backup SHA-256 | `516e2b000eb8f2bd10341a5464bb2bcfb19ecf7986f7a011864ce7390b124d1a` |
| size/hash equality vs source | PASS |
| backup integrity / FK (read-only open) | `ok` / zero violations |
| backup latest migration | `049_candidate_acquisition_integration.sql` |
| restore after Stage A | not performed; DB integrity, migration state, and capability locks remained clean after expected acquisition writes |

## Protected-table counts (pre-Stage-A)

| Protected surface | Count |
| --- | ---: |
| tracking queue | 29 |
| token snapshots | 1,054 |
| memory windows | 160 |
| episodes / outcomes / episode snapshots | 57 / 23 / 107 |
| memory fingerprints / audit reports | 23 / 5 |
| retrieval queries / matches | 10 / 0 |
| paper decisions | 2 |
| paper positions | 0 |
| paper trade events / audits | 0 / 0 |
| paper audit reports | 1 |
| Memory Factory campaigns / runs / cycles / slots / windows / runs / steps | 17 / 17 / 17 / 14 / 2 / 6 / 54 |

## Canonical command path

Exactly one Stage A invocation:

```bash
.venv/bin/python -m printer_v1.operator_cli.operational_memory_factory_command acquisition-only-n2 --operator-approved
```

| Timing | Value |
| --- | --- |
| start (UTC) | 2026-07-29T15:08:49Z |
| end (UTC) | 2026-07-29T15:09:08Z |
| wall clock | ~19 s |
| process exit code | `0` (terminal report emitted; status `BLOCKED`) |

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
| first_terminal_cause | `IDENTITY_MERGE_FAILURE` |
| failure_detail | `null` |
| execution_id | `20260729T150849Z-acq-9de864deec62` |
| integration_id | `cain-d81d0334325e70b062ad08b5f22ba5b2` |
| foundation_execution_id | `20260729T150849Z-acq-9de864deec62` |
| mode | `ACQUISITION_ONLY_N2` |
| selected_count | `0` |
| certificates issued / admitted / rejected | `4` / `0` / `4` |
| admission_reason (all four) | `MINT_STATUS_FAILED` |
| exclusion funnel stage | `CHAIN_MINT_VALID: 4` |
| manifests / items | `0` / `0` |
| projection_count | `0` |
| runtime_handoff_count | `0` |
| lifecycle_started | `false` |
| automatic_retry / restart / successor | `false` / `false` / `false` |
| active_lease_count | `0` |
| scheduler_residue_terminalized | `0` |
| reliability_claim_status | `UNPROVEN_NO_INDEPENDENT_SAMPLE` |
| scheduler_owner | Central Scheduler |
| source_governor_owner | Source Governor |

### Candidate funnel (repaired cohort boundary)

| Funnel stage | Count |
| --- | ---: |
| raw observation rows | 61 |
| raw unique nominations | 39 |
| candidate cohort bound M | 4 |
| candidate cohort size | 4 |
| thinned beyond cohort | 35 |
| enrichment identities | 4 |
| out-of-cohort enrichment | 0 |
| nomination rows Dex / Gecko / Solana | 17 / 20 / 2 |
| certificates admitted | 0 |
| manifest items | 0 |
| legacy projection | 0 |
| runtime handoff | 0 |

The prior live blocker (`CANDIDATE_LIMIT` on raw unique mints > M) did **not**
recur. The repaired integration-owner cohort boundary thinned `39 → 4` and
allowed foundation entry. Stage A then failed inside foundation admission /
identity merge, not at the pre-foundation raw-density ceiling.

### Foundation result

| Field | Result |
| --- | --- |
| verdict | `EXACT_N_MANIFEST_NOT_CREATED` |
| failure_family | `IDENTITY_MERGE_FAILURE` |
| failure_reason | `IDENTITY_NOT_MERGED` |
| exact_n_selection_result | `ALL_OR_NONE_FAILURE` |
| certificates_issued | 4 |
| certificates_admitted | 0 |
| certificates_rejected | 4 |
| reserve_size | 0 |
| selected_count | 0 |
| source_failures | `[]` |
| stale_or_expired_evidence_count | 0 |
| cursor_continuity | `CONTIGUOUS: 8` |

### Source / Scheduler / operation accounting

| Counter | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Scheduler jobs total | 1,137 | 1,157 | +20 |
| active Scheduler jobs | 0 | 0 | 0 |
| Source requests | 1,472 | 1,492 | +20 |
| Source responses | 1,359 | 1,379 | +20 |
| Source failures | 113 | 113 | 0 |
| acquisition integrations | 1 | 2 | +1 |
| acquisition leases (unreleased) | 1 (0) | 2 (0) | +1 terminalized/released |
| acquisition work rows | 16 | 36 | +20 |
| transport-operation rows | 15 | 36 | +21 |
| foundation executions | 0 | 1 | +1 |
| certificates / manifests / items | 0 / 0 / 0 | 4 / 0 / 0 | +4 / 0 / 0 |
| cursor heads / ranges | 0 / 0 | 2 / 5 | +2 / +5 |
| integration reports | 1 | 2 | +1 |

Stdout and durable integration report:

- `scheduler_jobs_created` = 20
- `governed_requests_used` = 20
- `transport_operations_used` = 21
- `bytes_used` = 132,615
- `rows_used` = 61
- `cursor_advances_proposed` = 7
- `cursor_advances_committed` = 2

Reconciliation:

- 20 work rows, each with exactly one Scheduler job and one governed source
  request (20 distinct job IDs, 20 request IDs, 20 response IDs);
- all 20 work rows `SUCCEEDED`;
- zero source-failure rows for this execution;
- 21 durable underlying transport operations, all `COMPLETE`;
- composites (Dex profiles/market materialization and holder
  largest-accounts/supply) account for transport ops (21) exceeding governed
  requests (20) in the exact operation-plan sense already proven offline; every
  external work item still has one job and one governed request;
- Scheduler owner and Source Governor owner are recorded on the terminal report;
- budgets unbreached relative to immutable ceilings:
  - governed requests 20 ≤ 24
  - transport operations 21 ≤ 32
  - bytes 132,615 ≤ 16,777,216
  - rows 61 ≤ 64
  - scheduler jobs 20 ≤ 24
  - selected 0 ≤ capacity 2

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
| 11 | solana_rpc / candidate_mint_account_batch | yes | 1 | cohort mint accounts |
| 12 | solana_rpc / pumpswap_pool_account_batch | yes | 1 | |
| 13–16 | solana_rpc / holder_concentration_reference | yes | 2 each | largest-accounts + supply composite (cohort M=4) |
| 17–20 | goplus / safety_reference | no | 1 each | optional; completed |

Cursor facts:

- terminal report: proposed advances `7`, committed advances `2`;
- durable heads written: `2` (Pump create + migration indexed addresses);
- durable ranges written: `5`, all `CONTIGUOUS` with `cursor_advanced=1`;
- no gapped/unknown/blocked-contract cursor advance was recorded.

### Acceptance gates

| Gate | Result |
| --- | --- |
| successful canonical terminal state (`COMPLETED`) | FAIL (`BLOCKED`) |
| exactly one N2 execution; no retry/restart/successor | PASS |
| raw nomination density handled through repaired cohort boundary | PASS (`39 → 4`, thinned 35) |
| cohort size no greater than four | PASS (`4`) |
| exactly two distinct admitted certificates | FAIL (`0` admitted; `4` issued, all rejected) |
| one exact two-item immutable manifest | FAIL (`0`) |
| manifest and certificate hashes verify | FAIL (no admitted/manifest) |
| legacy projection count exactly two | FAIL (`0`) |
| runtime handoff count zero | PASS |
| no tracking or lifecycle work | PASS |
| every external op has one Scheduler job and one governed request | PASS |
| truthful required/optional source outcomes | PASS |
| budgets/ceilings unbreached | PASS |
| cursor proposed/committed facts reconcile | PASS (proposed 7 / committed 2; durable heads 2) |
| zero active acquisition lease | PASS |
| zero active Scheduler work | PASS |
| deterministic zero-source replay | PASS (full JSON equal; +0 source/sched/ops) |
| integrity `ok` and zero FK violations | PASS |
| all protected-table deltas zero | PASS |

Stage A overall: **FAIL** (success gates not met).

### Report / replay

One integration report row exists for execution
`20260729T150849Z-acq-9de864deec62`. Public zero-source replay via
`replay_candidate_acquisition_integration_report` returned the identical
terminal JSON and performed zero new source requests, Scheduler jobs, or
transport operations.

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
| DB SHA-256 | `08fb9d202bf60f258779041e85d79a5c65e789ea1bddb67745b218df588ba1db` |
| DB size | 17,018,880 bytes |
| latest migration | still `049_candidate_acquisition_integration.sql` |
| integrity | `ok` |
| foreign-key violations | 0 |
| active acquisition lease | 0 (lease released; terminal cause `IDENTITY_MERGE_FAILURE`) |
| active Scheduler residue | 0 |
| sidecars | none |
| secrets / full RPC URL in stdout, stderr, report, or committed artifact | none |

## Stage B — `ACQUISITION_ONLY_N7`

`NOT_RUN`

Stage B was not authorized because Stage A did not pass every acceptance gate.
No N7 execution identity, lease, manifest, projection, legacy-adapter rejection
check, source request, or Scheduler job exists for N7.

The committed Governor constraint (N7 enrichment limited to ten cohort
candidates) was therefore never exercised live. No limit was increased.

## Blocker classification

```text
BLOCKER CLASSIFICATION: IDENTITY_MERGE_FAILURE (foundation admission)
EVIDENCE: exactly one public N2 run completed all 20 planned work items through
  Central Scheduler and Source Governor. The repaired cohort boundary thinned
  raw unique nominations 39 → cohort 4 (M=4) with zero out-of-cohort enrichment.
  Foundation entered, issued 4 certificates, rejected all 4 with
  MINT_STATUS_FAILED at CHAIN_MINT_VALID, then failed exact-N all-or-none
  selection (selected_count=0, no manifest). Terminal cause
  IDENTITY_MERGE_FAILURE / IDENTITY_NOT_MERGED / EXACT_N_MANIFEST_NOT_CREATED.
OFFICIAL-SOURCE COMPARISON: live DexScreener, GeckoTerminal, Solana RPC, Pump
  create/migration reads, PumpSwap pool reads, holder references, and optional
  GoPlus completed without source-failure rows for this execution. The stop is
  foundation identity/admission failure on the cohort, not a provider outage
  and not a recurrence of raw CANDIDATE_LIMIT.
PRINTER-CONTRACT COMPARISON: immutable N2 ceilings were not modified. Prior
  raw-density CANDIDATE_LIMIT did not fire. Cohort size stayed ≤ M. Exact-N
  all-or-none correctly refused a partial selection when zero certificates
  admitted. This is distinct from CANDIDATE_LIMIT, INSUFFICIENT_ELIGIBLE_POOL
  as a pure shortage label, cursor GAPPED/UNKNOWN/BLOCKED_CONTRACT, rate limit,
  timeout, and authentication.
ROOT CAUSE (observed facts only): the entire four-identity cohort failed mint-
  status / chain-mint validation (`MINT_STATUS_FAILED` × 4), so identity merge
  and exact-N admission produced zero admitted certificates. Deeper mint-status
  evidence decoding is reserved for a separate source-grounded investigation;
  this proof lane does not authorize code diagnosis or repair.
CODE CHANGE JUSTIFIED: not authorized by this proof prompt. Any repair requires
  a separate source-grounded investigation under the Python builder guide and a
  later explicit repair lane. Do not raise ceilings, prefer sources, score, or
  force partial selection.
MINIMUM SAFE RESPONSE: preserve the terminal report and accounting; do not
  retry N2; do not run N7; do not change code or configuration in this lane.
FOCUSED PROOF: future re-proof only after an operator-authorized repair or
  investigation and a new explicit proof prompt.
UNTOUCHED SCOPE: operational campaign, tracking, lifecycle, snapshots, windows,
  memory, selective 1h, retrieval, decisions, and all financial surfaces.
AUTHORIZATION STATUS: repair, retry, N7, and campaign remain unauthorized.
NEXT ROADMAP-COMPLIANT STEP: operator decision on a separate source-grounded
  investigation/repair lane for foundation IDENTITY_MERGE_FAILURE /
  MINT_STATUS_FAILED (CHAIN_MINT_VALID) on the repaired live cohort path,
  before any new bounded live acquisition proof.
```

## Live reliability status

`UNPROVEN_SINGLE_BLOCKED_SAMPLE`

This lane produced exactly one independent live N2 sample after the pipeline
repair. That sample proved:

- public construction of `LiveCandidateAcquisitionTransportOwner` still works live;
- the repaired cohort boundary handles raw nomination density above M without
  `CANDIDATE_LIMIT`;
- Scheduler/Governor ownership, accounting, lease release, protected-table
  isolation, integrity, cursor proposed/committed recording, and zero-source
  replay hold under live load;
- the run did **not** prove successful exact-N admission or manifest readiness.

Do not claim general real-market reliability, and do not claim 99% reliability,
from this single blocked execution. PASS would still have been only two stage
samples, not general market reliability.

## Money-usefulness contribution

Positive:

- confirmed the post-pipeline-repair public live path no longer dies on raw
  unique-mint density before foundation;
- confirmed acquisition-only surfaces can write while all memory/financial
  protected tables remain zero-delta;
- produced truthful terminal evidence of a live foundation identity/admission
  stop that offline high-density fixtures did not surface as this family.

Negative / incomplete:

- no admitted certificates and no immutable two-item manifest;
- no clean acquisition corpus growth usable by later retrieval or paper memory;
- Stage B capacity-neutral N=7 proof remains unexecuted;
- mint-status failure across the full cohort remains unexplained at proof depth.

## Remaining locks

Unchanged and still locked:

- Solana-only / Solana memecoin-only
- paper-only; no wallet, private keys, signing, transaction submission, real funds
- no paid sources; DEXTools, PumpPortal, Birdeye, Helius remain excluded as live
  acquisition dependencies in this path
- no scoring, ranking, confidence, weighting, embeddings, or vectors
- no Scheduler or Source Governor bypass
- active Memory Factory capacity exactly two
- no operational campaign
- no tracking/lifecycle start; no snapshots or memory windows
- no selective-1h proof
- no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL
- GoPlus remains optional

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Foundation `IDENTITY_MERGE_FAILURE` / `MINT_STATUS_FAILED`** — the dominant
   blocker on this sample. The full M=4 cohort failed chain-mint validation, so
   exact-N admission produced zero certificates and no manifest.
2. **Cohort quality under lexicographic thinning** — the repaired deterministic
   `sorted(universe)[:M]` cohort may select identities that later fail mint-
   status even when denser markets contain other eligible mints; scoring or
   preference is still forbidden.
3. **No automatic repair path is authorized** — raising ceilings, preferring
   sources, partial exact-N selection, or retry loops would violate V1 locks and
   frozen proof policy.
4. **N7 and legacy projection remain unproven live** after this pipeline repair.
5. **Holder evidence authenticity** remains partial (`getTokenLargestAccounts`
   wallet-level limits). GoPlus completed here and was not the stop cause.
6. **Single blocked sample** cannot establish live reliability.
7. **Public free-source pruning/latency** can still block later attempts even
   after an identity-admission repair.

## Exact next roadmap step

```text
Operator decision required:
  separate source-grounded investigation / optional repair lane for
  foundation IDENTITY_MERGE_FAILURE / MINT_STATUS_FAILED at CHAIN_MINT_VALID
  on the repaired live cohort path, without raising ceilings to force success,
  without operational campaign, and without N2 retry or N7 until a new
  explicit proof prompt authorizes it.
```

Do not treat this closeout as authorization to repair, retry, run N7, start a
campaign, or unlock any financial capability.

## Redacted proof artifact

Committed redacted Stage A summary (no secrets, no full RPC URL, no raw provider
payloads, no mint addresses):

`docs/printer-v1-v2-9-8b-final-post-repair-bounded-live-candidate-acquisition-proof-stage-a-redacted.json`

Host-only full inspection and backup remain outside the repository under
`/Users/Dtwo1/PrinterOperations/v2-9-8/20260729T150838Z-final-post-repair-proof`.

## Files changed by this closeout lane

- this closeout document
- redacted Stage A proof artifact
- minimal active-pointer updates in `AGENTS.md`,
  `docs/printer-v1-assistant-active-build-order-anchor.md`, and
  `docs/printer-v1-memory-growth-build-order-v2.md`

No Python code, configuration, policy ceilings, migrations, or databases were
committed.
