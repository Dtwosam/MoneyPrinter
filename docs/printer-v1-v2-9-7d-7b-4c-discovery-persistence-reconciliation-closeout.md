# V2-9.7D.7B.4C Discovery Persistence Reconciliation Closeout

**Status:** PASS
**Lane:** V2-9.7D.7B.4C
**Boundary:** persistence ownership and exact links only
**Date:** 2026-07-21

PASS means the approved combined Pump.fun discovery ownership graph now has a
narrow SQLite migration and repository API for cycle-rooted discovery batch,
work, source provenance, observations, merged candidates, verification links,
selection handoff links, and provider-report reconstruction. It does not mean
combined execution, provider calls, tracking activation, or financial
capability exists.

## Todo / Checklist

- [x] Verify exact starting commit `7b4a872b276e0a47ed69f74a163083a976547f55`.
- [x] Read AGENTS.md, active source stack, 7B.2 design, and 7B.4A/4B closeouts.
- [x] Inventory campaign, Scheduler, selection, Source Governor, and migration head.
- [x] Add migration `034` with the minimum ownership graph.
- [x] Implement repository methods with immutability and idempotency.
- [x] Prove all required synthetic persistence cases on disposable DBs.
- [x] Write this closeout and commit only on PASS.

## Exact Files Changed

- `migrations/034_discovery_persistence_reconciliation.sql` (new)
- `src/printer_v1/discovery/persistence.py` (new)
- `tests/test_v2_9_7d_7b_4c_discovery_persistence.py` (new)
- `tests/test_phase1_database_schema.py` (migration-list expectation only)
- `docs/printer-v1-v2-9-7d-7b-4c-discovery-persistence-reconciliation-closeout.md` (new)

## Migration Number

`034_discovery_persistence_reconciliation.sql`

Derived from repository migration head `033_operational_campaign_supervision.sql`.

## Tables and Links Introduced

| Table | Role |
|---|---|
| `printer_discovery_batches` | One campaign/run/cycle-rooted discovery batch with cutoff, policy/contract versions, Git provenance identity, seed identity, cycle-seed hash, Pump cursor/continuity, batch state, and canonical hash |
| `printer_discovery_work` | Pre-selection cycle-rooted work linked to an existing Central Scheduler job and approved `work_type`; no token/window columns |
| `printer_discovery_work_source_links` | One-to-many immutable work-to-Source-Governor request/response/failure junctions |
| `printer_discovery_provider_observations` | Immutable normalized observations with mint/market/lifecycle identity, channel, times, raw payload hash, source provenance, factual payload, and observation hash |
| `printer_discovery_merged_candidates` | One merged candidate per exact batch/candidate identity with channel labels, conflicts, gaps, origin/PumpSwap states, and canonical hash |
| `printer_discovery_candidate_contributions` | Many provider observations contributing to one merged candidate without multiplying authority |
| `printer_discovery_origin_verifications` | Exact origin-verification admission/result links |
| `printer_discovery_pumpswap_confirmations` | Exact PumpSwap confirmation admission/result links |
| `printer_discovery_selection_links` | Discovery batch to existing selection batch |
| `printer_discovery_selected_item_links` | Selected item to merged candidate, optional token slot, and first WINDOW_15M Scheduler job link without activation |
| `printer_discovery_provider_report_links` | Factual provider-contribution report reconstruction objects |

## Existing Owners Reused

- Campaign root and configuration from migrations 031/032
- Campaign run/cycle/token-slot ownership from migration 032
- Central Scheduler jobs (`printer_scheduler_jobs`)
- Source Governor rows (`printer_source_requests` / `responses` / `failures`)
- Selection batch ownership from migration 025
- Launch Git provenance already stored on campaign configuration
- Existing token/pair rows only when optional post-selection slot links are present

No transport payloads were copied into discovery tables. No token/window
identities are fabricated for pre-selection work.

## Immutability and Idempotency Behavior

- Discovery batch identity fields and canonical hash are immutable after insert.
- Provider observations, contributions, origin/PumpSwap rows, selection links,
  and report links are append-only via update/delete abort triggers.
- Identical inserts are idempotent at the repository layer when identity and
  canonical content match.
- Conflicting repeats with the same identity and different content are rejected.
- One merged candidate per `(discovery_batch_id, candidate_identity_key)`.
- Duplicate provider contributions attach to one candidate and do not create
  additional candidates.

## Conflict and Cross-Owner Rejection

- Campaign/configuration/run/cycle ownership is validated before batch insert.
- Cross-campaign configuration or run/cycle pairing fails closed.
- Work rows require an existing Scheduler job id.
- Source response links must match their request ids.
- Contributions must stay inside the same discovery batch.
- Selected-item token slots must belong to the exact campaign/run/cycle.
- Non-authoritative rank/score/risk/promoted/popularity/order fields are
  rejected from factual observation payloads and provider-report scoring keys.

## Money-Usefulness Contribution

This lane makes later combined discovery auditable and replayable. Exact
foreign links, immutable hashes, and explicit unknown/gap states prevent dirty
or cross-owner candidate history from becoming silent training or selection
input. The contribution is provenance integrity only; it predicts no return and
unlocks no paper or live action.

## What the Lane Improves

- Discovery can now be persisted before token-slot or tracking-window assignment
  without overloading token/window-rooted campaign scheduler work.
- One discovery work item can own multiple Source Governor facts.
- Provider observations and merged candidates are deterministic, immutable, and
  authority-safe against provider duplication.
- Selection and report reconstruction have exact foreign links ready for a
  later execution owner.

## What Remains Locked

- provider or internet calls;
- secrets/credential setup;
- adapter redesign;
- combined execution owner (`7B.4D`);
- live discovery, campaign runtime, Scheduler execution;
- tracking activation, memory generation, command publication;
- persistent operational-target activation;
- live-source proof, V2-9.7D closeout, pilot;
- retrieval, paper decisions, BUY/SELL/HOLD/WAIT/AVOID/NO_ACTION;
- positions, trades, audits, PnL;
- wallets, private keys, signing, real funds, live execution;
- paid APIs, scoring, ranking, confidence, weighting, embeddings, vectors;
- `WINDOW_5M_MICRO_EVENT` as anything other than support-only.

## Proof Results

Disposable isolated SQLite databases only.

| Check | Result |
|---|---|
| Clean migration from schema head 033 | PASS |
| Migration re-open and schema-version recognition | PASS |
| Campaign/run/cycle-rooted discovery-batch insert | PASS |
| Cross-campaign and cross-run link rejection | PASS |
| Pre-selection work without fabricated token/window identity | PASS |
| One work item linked to multiple Source Governor rows | PASS |
| Immutable provider-observation insert and readback | PASS |
| Identical-repeat idempotency | PASS |
| Conflicting-repeat rejection | PASS |
| Deterministic provider-observation ordering | PASS |
| One merged candidate with multiple contributions | PASS |
| Duplicate contributions do not create duplicate candidates | PASS |
| Explicit conflicts and gaps survive readback | PASS |
| Exact origin-verification links | PASS |
| Exact PumpSwap-confirmation links | PASS |
| Selection-batch and slot linkage without runtime activation | PASS |
| Provider-report reconstruction links | PASS |
| Foreign-key enforcement | PASS |
| Canonical-hash mismatch rejection | PASS |
| No retrieval/decision/position/trade/PnL rows written | PASS |
| Windows SQLite connections close cleanly | PASS |

Focused suite: `tests/test_v2_9_7d_7b_4c_discovery_persistence.py` — 7 passed.

Directly affected ownership/campaign/selection/schema checks were also run.

## Remaining Blockers

No blocker remains for this persistence reconciliation lane.

Combined execution ownership, real provider transport, durable operational
activation, and live-source proof remain intentionally unproved and belong to
later explicitly authorized lanes.

## Functionality Risks / Setbacks / Efficiency Blockers

- Cycle state remains independent of discovery-batch state. Existing migration
  032 still requires two token slots before a cycle leaves `PLANNED`. This lane
  therefore keeps discovery-batch state authoritative for pre-selection intake
  and does not force fabricated slots or alter that trigger.
- Selection-batch schema was extended only through junction tables; older
  selection rows without discovery links remain valid.
- Provider report payloads are free-form JSON constrained only against scoring
  keys; later report contracts may need tighter schemas.
- Origin confirmation still depends on later execution of direct Pump
  verification; provider `pumpfun` labels remain non-origin.
- SQLite expression indexes and JSON checks are portable for Printer's Windows
  SQLite path but remain SQLite-specific.
- Persistence proves link integrity, not measured storage cost under live
  provider volume.

## Stop Boundary

V2-9.7D.7B.4C stops at migration 034, repository methods, synthetic
persistence proof, and this closeout. `V2-9.7D.7B.4D`, live-source proof,
V2-9.7D closeout, and the pilot have not begun.

## Final Lane Result

`V2_9_7D_7B_4C_DISCOVERY_PERSISTENCE_RECONCILIATION_PASS`
