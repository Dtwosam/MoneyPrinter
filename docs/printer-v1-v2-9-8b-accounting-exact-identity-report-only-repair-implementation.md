# Printer V1 V2-9.8B Accounting and Exact-Identity Report-Only Repair Implementation

Date: 2026-07-31

Implementation baseline (prior repair commit):
`b168c57d709df34e0f7ddcf6fc9b97c0bd8eca2d`

Branch:
`codex/v2-9-8b-accounting-report-only-repair`

Design source:
`docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-design.md`

Forensic source:
`docs/printer-v1-v2-9-8b-first-authoritative-15m-forensic-audit.md`

Implementation verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS`

This document was revised after operator-review gap repair. Earlier PASS language
that accepted asymmetric multi-hop totals, secondary summary block diagnostics,
non-exception-safe stage sealing, and a synthetic July 31 payload-only proof is
no longer retained as current truth.

## 1. Baseline and branch

| Check | Result |
| --- | --- |
| Prior repair commit | `b168c57d709df34e0f7ddcf6fc9b97c0bd8eca2d` |
| Branch | `codex/v2-9-8b-accounting-report-only-repair` |
| Worktree before this gap repair | clean on prior repair commit |
| Authoritative DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| Authoritative DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (unchanged) |

## 2. Exact files changed (operator-review gap repair)

Source:

- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests:

- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py`

Documentation:

- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-implementation.md` (this file)

No schema migration. No authoritative DB mutation. No secrets, logs, or unrelated artifacts.

## 3. Operator-review blockers repaired

### 3.1 Exact identity and count reconciliation

Replaced asymmetric owner/action-local comparison with exact equality:

- owner transport total must equal action-local transport-identity total
- `owner > action_local` blocks
- `action_local > owner` blocks
- equal counts with different identity sets block
- identity keys compare stage/source/kind/method/ordinal/target fields
- missing stage evidence is never manufactured from request rows

When only governed-request counts are available and transport identities cannot
be proven:

```text
ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED
```

The operational coordinator collects action-local transport identities only from
sealed stage handoff into a parallel list (never from SQLite request counts).
Pre-lifecycle finalize uses that identity surface. Count-only
`campaign_source_calls` alone is not accepted as multi-hop-tolerant equality.

### 3.2 Exception-safe stage sealing

Direct migration, locator, and each exact-liquidity round now seal and ingest
exactly once in a `try/except/finally` path before an unexpected exception
escapes:

- seal `FAILED` after partial work
- re-raise the original first terminal cause
- sink failure is noted and does not replace the original source/market cause
- unstarted stages emit nothing

### 3.3 Exact terminal-summary identity

`_load_exact_terminal_summary` requires all of:

- `campaign_id`
- `run_id`
- `configuration_id`
- `execution_id`

to be present, non-empty, and exact. Missing identity is a mismatch.

### 3.4 Missing-summary primary block reasons

| Condition | Primary `block_reason` |
| --- | --- |
| Exact report missing + valid exact summary | `EXACT_TERMINAL_REPORT_MISSING` |
| Exact report missing + summary absent/mismatched | `EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED` |

The summary defect is no longer hidden as a secondary diagnostic field.

### 3.5 Disposable end-to-end coordinator proof

Replaced the synthetic July 31-shaped payload-only test with a disposable
coordinator proof that shows:

- 30 unique governed transport operations
- full stage handoff into one owner via sink
- exact action-local identity/count reconciliation
- terminal `SOURCE_VISIBILITY_SHORTAGE`
- exactly one canonical blocked terminal report row and artifact
- independent evidence reconstruction equals stored totals
- zero lifecycle/memory/retrieval/decision/position/trade/audit/PnL deltas
- no retry/restart/resume/successor

## 4. Focused tests added/updated

- owner count greater than action-local blocks
- action-local greater than owner blocks
- equal counts with different identities block
- count-only action-local returns `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED`
- unexpected direct-migration exception after transport seals `FAILED`, ingests once, re-raises
- equivalent locator and liquidity exception paths
- missing summary `run_id` blocks
- missing summary `configuration_id` blocks
- missing summary `execution_id` blocks
- mismatched summary identity uses primary block reason
- exact report missing with valid summary uses `EXACT_TERMINAL_REPORT_MISSING`
- disposable 30-op coordinator shortage handoff
- one full disposable ordinary two-token `WINDOW_15M` regression

## 5. Tests and exact results

| Suite | Result |
| --- | --- |
| `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` | 29 passed |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | included |
| `tests/test_v2_9_8b_terminal_safety_accounting_finalization.py` | included |
| `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py` | included |
| Combined focused affected suites | 101 passed |
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

Printer can preserve honest negative learning about source visibility and market
eligibility only when stage evidence is complete and reconcilable by identity.
Operators can no longer mistake an unrelated historical report for the current
attempt, and missing/mismatched terminal summaries surface as primary block
reasons rather than secondary diagnostics.

## 8. What improved versus the first repair commit

- exact identity/set reconciliation both directions
- design blocker when only request counts exist
- exception-safe seal/ingest for started stages
- exact four-field terminal-summary identity
- primary missing-summary block reasons
- disposable coordinator 30-op proof instead of synthetic payload-only test

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

- Action-local identity truth is currently the sealed stage handoff surface
  collected by the campaign sink. A durable independent transport-identity
  ledger outside sealed stages is still not a schema-backed ordinary path; when
  only governed-request counts exist the gate fails closed with
  `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED` rather than multi-hop
  asymmetry.
- Fixture/offline transports that omit declared transport identities still fail
  closed when a stage sink is required.
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

All five operator-review blockers listed in the repair prompt are implemented
and covered by focused disposable-DB tests.

## 12. Exact next permitted lane

```text
Operator review of the accounting / exact-identity report-only repair branch and closeout only.
```

No automatic campaign, recovery, cursor reset, N2/N7, provider/RPC work,
retrieval, or financial unlock is authorized.
