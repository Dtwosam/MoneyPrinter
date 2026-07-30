# Printer V1 V2-9.8B Discovery and Selection Final Consolidation Design

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Full-System Re-Audit and Consolidation`

Status: `FINAL_DESIGN_FOR_IMPLEMENTATION`

## Work gate

- Supersedes the unaccepted prior consolidation closeout blocked by operator
  review at HEAD `d21d7c82dbd98fc1e86637f871fdb190176fdec8`.
- Migration head remains `049` (no schema migration required; six units persist
  inside durable terminal report JSON).
- Frozen transports + disposable migration-049 databases only.

## Final architecture

### Candidate state machine

```text
NOMINATED (direct Pump live tail)
  -> VERIFICATION (25-role migrate + PumpSwap join)
  -> REGISTRY_GRADUATED
  -> MARKET_ENRICHED (exact-pair liquidity)
  -> ELIGIBLE | REJECTED
  -> SELECTED_TWO | NONE (canonical selector)
  -> ACTIVATED_TWO | COMPENSATED_NONE
  -> WINDOW_15M lifecycle
```

### Final active call graph

```text
public operational run
  -> resolve Solana RPC once (immutable configuration)
  -> zero-I/O preflight (same endpoint + typed prohibitions)
  -> direct Pump live-tail (measured identities per RPC)
  -> exact 25-role migrate + PumpSwap join
       (1 getTransaction + 1..3 getMultipleAccounts; identities + bytes + rows)
  -> graduated registry
  -> DexScreener (2 HTTP for fresh profiles; exact-pair snapshots)
       with declared row/byte ceilings at every multi-row call site
  -> holder/safety (same Solana endpoint)
  -> selection_authority.select_two_candidates only
  -> atomic two-or-none activation + first 15m jobs (savepoint compensate)
  -> terminal report with six_unit_totals
  -> zero-source replay reconstructs six units from durable report JSON
  -> safe stop
```

### Six independent units

1. `SOURCE_TRANSPORT_OPERATION`
2. `LOCAL_VALIDATION_STEP`
3. `SCHEDULER_WORK_ITEM`
4. `SOURCE_RESPONSE_BYTES`
5. `NORMALIZED_SOURCE_ROWS`
6. `LIFECYCLE_RESERVED_TRANSPORT_OPERATION`

Every actual HTTP/RPC creates one `TransportOperationIdentity`. Missing,
duplicate, or over-ceiling identities fail closed. Parsing never counts as a
transport.

### Complete 25-role contract

All fixed programs/sysvars, PDA/ATA relationships, and the pinned mainnet
`withdraw_authority` (`PUMP_WITHDRAW_AUTHORITY_ID`) fail closed with distinct
reasons. Valid-but-wrong substitutions must not pass.

### Canonical selector

One owner: `printer_v1.discovery.selection_authority`.

Product:

```text
TwoCandidateSelection {
  candidate_a, candidate_b,
  composition_label,  # diagnostic only
  provenance_summary  # diagnostic only
}
```

Removed as ordinary product fields:

- `selected_latest` / `selected_persisted` readiness columns
- compulsory latest+persisted quota
- lexicographic mint preference as selection criterion

`select_holder_eligible_pair` remains offline-only historical helper text; not
ordinary authority.

### Terminal report / replay

- `build_campaign_terminal_report` embeds `six_unit_totals`.
- Durable storage is the terminal report JSON + artifact (migration 049, no new table).
- `replay_campaign_terminal_report` reconstructs six units from stored report only.
- `reconcile_six_unit_totals` equality is required for report vs replay.
- Replay creates zero source transports.

### Atomic handoff

`CombinedPumpfunCampaignExecutor._atomic_initial_two_slot_handoff` savepoint:

- `BEFORE_FIRST`, `DURING_SECOND`, `SECOND_SCHEDULER_JOB`, `DUPLICATE_ACTIVE`
- rollback leaves no partial slots / queue / first 15m jobs

## Preserved locks

All V1 and V2-9.8B locks remain: Solana memecoin-only, paper-only, no PumpPortal
ordinary authority, no N2/N7/cursor/recovery/backfill, exactly two tokens,
WINDOW_15M only, 5m support-only, Source Governor + Central Scheduler, no
retrieval/decisions/positions/trades/audits/PnL, no wallets/keys/signing/paid
APIs/scoring/ranking/confidence/weighting/embeddings/live execution.

Do not raise ceilings to force PASS.

## Implementation modules

| Module | Change |
|---|---|
| `sources/measured_transport.py` | identity helpers, payload record/reconcile |
| `sources/pump_contracts.py` | pin withdraw_authority; full relation fail-closed |
| `sources/direct_pump_migration.py` | measure bytes + identities on every RPC normalize |
| `sources/pumpswap.py` | measure RPC bytes; preserve identities |
| `sources/pump_migration.py` | full identities per getTx/account batch |
| `sources/dexscreener.py` | row/byte ceilings + identities at call sites |
| `discovery/direct_migration_discovery.py` | full six-unit ledger reconcile |
| `discovery/graduated_liquidity_front_door.py` | neutral product; offline helper labeled |
| `operator_cli/graduated_supply_front_door.py` | candidate_a/b product only |
| `operator_cli/unified_terminal_closure.py` | six-unit report + replay |
| `operator_cli/operational_memory_factory_command.py` | pass six units into report |
| tests + authority docs | proof + anchor supersession |

## Proof plan

Frozen offline proof covering public composition, identities, batches, roles,
ceilings, endpoint, provenance, deadline, cooldown, activation inject surface,
six-unit report/replay equality, zero CA/financial deltas, migration 049.
