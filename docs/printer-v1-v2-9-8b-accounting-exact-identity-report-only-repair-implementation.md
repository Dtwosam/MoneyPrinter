# Printer V1 V2-9.8B Accounting and Exact-Identity Report-Only Repair Implementation

Date: 2026-07-31

Implementation baseline (prior closeout commit):
`fd35b414edac9ab2d2e533e690e05283db5feaea`

Branch:
`codex/v2-9-8b-accounting-report-only-repair`

Design source:
`docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-design.md`

Forensic source:
`docs/printer-v1-v2-9-8b-first-authoritative-15m-forensic-audit.md`

Implementation verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS`

This document was revised after the second operator-review gap repair. Earlier
language that accepted sealed-stage self-comparison for action-local identity
truth, a synthetic 30-operation report insert, or a label-only WINDOW_15M
string assertion is no longer retained as current truth.

## 1. Baseline and branch

| Check | Result |
| --- | --- |
| Prior closeout commit | `fd35b414edac9ab2d2e533e690e05283db5feaea` |
| Branch | `codex/v2-9-8b-accounting-report-only-repair` |
| Authoritative DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| Authoritative DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (unchanged) |

## 2. Exact files changed (second operator-review gap repair)

Source:

- `src/printer_v1/sources/measured_transport.py`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests:

- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py`

Documentation:

- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-implementation.md` (this file)

No schema migration. No authoritative DB mutation. No secrets, logs, or unrelated artifacts.

## 3. Operator-review blockers repaired

### 3.1 Independent action-local transport identity (no self-comparison)

Architecture finding: actual transport identities already exist at
`MeasuredTransportLedger.record_transport` time — before stage sealing. That
surface can be wired as a verification-only observer without:

- a migration;
- reconstructing evidence from SQLite request rows;
- creating a second campaign accounting authority;
- changing source budgets.

Implementation:

- `MeasuredTransportLedger.on_transport_recorded` fires after a transport is
  accepted into the stage measurement ledger
- the public coordinator supplies one observer that appends identity dicts to
  `action_local_transport_identities`
- the campaign evidence sink now only ingests sealed stages into
  `CampaignSixUnitOwner` — it no longer copies sealed transports into
  action-local
- pre-lifecycle reconciliation still requires exact identity/set equality both
  directions
- count-only governed-request surfaces still return
  `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`

If a started stage measures transports but never seals/emits evidence, action
local retains the measured identities while the owner does not — the completion
gate mismatches and blocks the report.

### 3.2 Exception-safe stage sealing (preserved)

Direct migration, locator, and each exact-liquidity round still seal and ingest
exactly once in a `try/except/finally` path before an unexpected exception
escapes. First-cause precedence is preserved.

### 3.3 Exact terminal-summary identity (preserved)

`_load_exact_terminal_summary` still requires `campaign_id`, `run_id`,
`configuration_id`, and `execution_id` exact non-empty matches.

### 3.4 Missing-summary primary block reasons (preserved)

| Condition | Primary `block_reason` |
| --- | --- |
| Exact report missing + valid exact summary | `EXACT_TERMINAL_REPORT_MISSING` |
| Exact report missing + summary absent/mismatched | `EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED` |

### 3.5 Genuine disposable coordinator 30-op shortage proof

Replaced the synthetic stage-construction + manual report-row insert with a
genuine disposable coordinator proof that invokes:

- real operational stage graph (`run_persistent_eligible_token_supply`)
- campaign evidence sink (owner ingest only)
- independent measurement observer (action-local)
- completion gate (`_finalize_operational_six_unit_accounting`)
- canonical report builder (`build_campaign_terminal_report`)
- canonical report writer (`write_campaign_terminal_report`)

Requires:

- 30 independently observed actual transport identities
- exact equality with the single campaign owner
- terminal `SOURCE_VISIBILITY_SHORTAGE`
- exactly one report row and one report artifact from production report code
- evidence reconstruction equals stored totals
- zero lifecycle/memory/retrieval/decision/position/trade/audit/PnL deltas
- no retry/restart/resume/successor

### 3.6 Genuine ordinary two-token WINDOW_15M regression

Replaced the label-only `window_label = "WINDOW_15M"` assertion with the nearest
genuine frozen, disposable, ordinary two-token operational coordinator path that
reaches and closes two `WINDOW_15M` windows (`fifteen_minute_only=True`, no
providers, no authoritative database).

## 4. Focused tests added/updated

- action-local observer independence from stage seal/owner ingest
- owner count greater than action-local blocks
- action-local greater than owner blocks
- equal counts with different identities block
- count-only action-local returns `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`
- unexpected direct-migration / locator / liquidity exception seal paths
- missing summary identity fields block
- mismatched summary identity primary block reason
- exact report missing with valid summary uses `EXACT_TERMINAL_REPORT_MISSING`
- genuine disposable 30-op coordinator shortage handoff + report write
- genuine ordinary two-token WINDOW_15M close regression

## 5. Tests and exact results

| Suite | Result |
| --- | --- |
| `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` | 31 passed |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | included |
| `tests/test_v2_9_8b_terminal_safety_accounting_finalization.py` | included |
| `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py` | included |
| Combined focused affected suites | 103 passed |
| Python compile of changed sources | pass |
| `git diff --check` | pass |

No full repository suite was run. No providers or authoritative campaign were run.

## 6. Authoritative DB hash before and after

```text
before: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
after:  f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
```

Identical. No authoritative mutation.

## 7. Money-usefulness contribution

Printer can preserve honest negative learning about source visibility only when
stage evidence is complete and reconcilable against an independent action-local
measurement surface. A stage that measures transports but never emits sealed
evidence is now detectable. Operators can no longer mistake sealed-stage
self-comparison for independent verification.

## 8. What improved versus the prior closeout commit

- removed sealed-stage self-comparison for action-local identities
- wired pre-seal `MeasuredTransportLedger.on_transport_recorded` observer
- genuine disposable 30-op shortage coordinator proof with production report write
- genuine ordinary two-token WINDOW_15M close regression
- preserved exception-safe sealing and exact terminal-summary repairs

## 9. What remains locked

- clean-memory creation / retrieval activation
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- live wallets, private keys, signing, real funds, live execution
- paid APIs, scoring, ranking, confidence, weighting, embeddings/vectors
- `WINDOW_1H` / longer production activation
- historical July 31 report backfill or reclassification
- campaign rerun of the permanent no-rerun marker attempt
- candidate-acquisition N2/N7, cursor recovery, provider campaigns

## 10. Functionality Risks / Setbacks / Efficiency Blockers

- Action-local independence depends on every measured stage ledger receiving
  the coordinator observer. Stages that create ledgers without the observer
  under-count action-local and fail closed at the completion gate.
- Fixture/offline transports that omit declared transport identities still fail
  closed when identity equality is required.
- Holder/lifecycle stages after lifecycle start are not forced into the
  pre-lifecycle action-local identity gate; later lanes may need explicit sealed
  stages for those owners if full-run identity equality is required.
- Exception-safe finally paths must continue to preserve first-cause precedence
  when sink ingestion fails after a source/market exception.
- Cross-cutting accounting and report-only changes used focused suites only;
  broader repository suite was intentionally not expanded.

## 11. Factual verdict

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS
```

All three remaining operator-review blockers listed in the repair prompt are
implemented and covered by focused disposable-DB tests.

## 12. Exact next permitted lane

```text
Operator review of the accounting / exact-identity report-only repair branch and closeout only.
```

No automatic campaign, recovery, cursor reset, N2/N7, provider/RPC work,
retrieval, or financial unlock is authorized.
