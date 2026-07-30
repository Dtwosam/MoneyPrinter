# Printer V1 V2-9.8B Discovery and Selection Verifiable Real-Path Design

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Verifiable Real-Path Completion`

Status: `FINAL_DESIGN_FOR_IMPLEMENTATION`

## Contracts

### Measured identity (every attempt)

Every successful or failed HTTP/RPC attempt appends one
`TransportOperationIdentity` before return. Multi-call governed requests keep
prior identities when a later hop fails.

### Fail closed before persistence

Direct migration discovery:

1. run live-tail + verifications and record identities;
2. reconcile claimed transport totals vs identity count;
3. **only then** call `record_graduated_candidate`;
4. on mismatch: `ACCOUNTING_BLOCKED`, zero new registry rows.

### Campaign six-unit owner

`printer_v1.sources.campaign_six_unit_accounting.CampaignSixUnitOwner`:

- owns one ledger for the attempt;
- emits durable `six_unit_evidence` (identities + non-transport counters +
  started_at/ended_at/elapsed_seconds);
- `reconstruct_six_unit_totals_from_evidence` rebuilds totals from evidence only;
- `compare_report_totals_to_evidence` compares stored report totals to that rebuild
  with `self_comparison=False`.

### Terminal report / replay

- Report stores both `six_unit_totals` and `six_unit_evidence`.
- Replay reads durable report JSON, reconstructs from evidence, compares to
  stored totals, creates zero transports/writes.
- `elapsed_seconds` is wall-clock duration for the discovery attempt and is
  surfaced on the terminal report when available.

### Activation / lifecycle proof

Use the existing disposable-DB atomic handoff harness inject points:

- BEFORE_FIRST
- DURING_SECOND
- SECOND_SCHEDULER_JOB
- DUPLICATE_ACTIVE
- CONFLICTING_SLOT

Each must leave zero active tracking / first-15m jobs.

## Preserved locks

Direct one-page Pump path, complete 25-role validation, canonical two-token
selector, migration 049, exactly two tokens, WINDOW_15M only, Source Governor,
Central Scheduler, all financial/retrieval locks.

## Implementation modules

| Module | Role |
|---|---|
| `sources/campaign_six_unit_accounting.py` | campaign owner + reconstruct + compare |
| `sources/dexscreener.py` | fail/rate-limit/timeout identities + multi-call preserve |
| `discovery/direct_migration_discovery.py` | pre-persist reconcile + evidence + elapsed |
| `operator_cli/unified_terminal_closure.py` | evidence in report; independent replay compare |
| `operator_cli/operational_memory_factory_command.py` | pass evidence/elapsed into report |
| tests + docs | real-path frozen proofs; supersede prior PASS |
