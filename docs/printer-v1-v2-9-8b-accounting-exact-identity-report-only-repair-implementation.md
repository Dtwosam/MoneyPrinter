# Printer V1 V2-9.8B Accounting and Exact-Identity Report-Only Repair Implementation

Date: 2026-07-31

Implementation baseline:
`e71e543d197154eba427b41e2e01574a59f527f5`

Branch:
`codex/v2-9-8b-accounting-report-only-repair`

Design source:
`docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-design.md`

Forensic source:
`docs/printer-v1-v2-9-8b-first-authoritative-15m-forensic-audit.md`

Implementation verdict:
`V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS`

## 1. Baseline and branch

| Check | Result |
| --- | --- |
| Required base | `e71e543d197154eba427b41e2e01574a59f527f5` |
| `origin/master` | matches required base |
| Branch | `codex/v2-9-8b-accounting-report-only-repair` |
| HEAD before edit | required base |
| Worktree before edit | clean |
| Authoritative DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| Authoritative DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (unchanged) |

## 2. Exact files changed

Source:

- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests:

- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` (new)

Documentation:

- `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-implementation.md` (this file)

No schema migration. No authoritative DB mutation. No secrets, logs, or unrelated artifacts.

## 3. Coding approach

One campaign owner remains the only campaign-wide accounting authority. Child stages may own a local `MeasuredTransportLedger`, seal one immutable evidence block, and call the same one-way sink. Stages never write an alternate final campaign report and never manufacture missing evidence from SQLite request rows.

Public `report-only` resolves exact campaign/run identity first (explicit pair or latest supervision), then queries the terminal report for that pair only. Global latest-report and discovery-only fallbacks are removed from the campaign report-only path.

## 4. Accounting ownership before and after

### Before

1. Public coordinator created `CampaignSixUnitOwner` and passed `ingest_stage_evidence` as sink.
2. Live operational composition ingested only post-return `supply.discovery_report.six_unit_evidence`.
3. Bounded `SOURCE_VISIBILITY_SHORTAGE` returned after full governed work, so locator and exact-liquidity stage evidence never reached the owner.
4. Terminalization saw incomplete evidence and blocked with `SIX_UNIT_EVIDENCE_MISSING` even though action-local source truth recorded 30 operations.

### After

1. `CampaignSixUnitOwner` still owns campaign totals.
2. Sealed-stage metadata is required for repaired operational stages:
   - `stage_id`, `stage_kind`, `stage_sequence`, `stage_terminal_status`,
     `stage_first_terminal_cause`, `sealed_at`, `campaign_id`, `run_id`, `cycle_id`.
3. `seal_campaign_stage_evidence(...)` copies source evidence, validates, and returns deterministic JSON-serializable sealed blocks.
4. `ingest_stage_evidence(...)` rejects duplicate stage IDs, duplicate transport identities across stages, identity mismatch, invalid status/sequence, negative counters; remains atomic; preserves the first accounting block reason; exposes sealed/ingested diagnostics.
5. Direct migration, locator (when attempted), and each exact-liquidity round seal once before return/raise and call the campaign sink.
6. `run_persistent_eligible_token_supply` / `build_graduated_supply` pass the sink unchanged; no second aggregate owner.
7. Authoritative campaign no longer re-ingests discovery evidence after return.
8. Completion gate reconciles owner transport completeness against pre-lifecycle action-local source calls. Mismatch sets `SIX_UNIT_ACCOUNTING_BLOCKED` / `CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH` and writes no canonical report. A fully accounted shortage may write an honest blocked report.

## 5. Report-only identity behavior before and after

### Before

- Selected the globally newest `REPORT_TERMINAL` row.
- Preferred newer discovery-only artifacts over the intended campaign.
- Could replay an older unrelated campaign when the current attempt wrote no report.

### After

- `--campaign-id` and `--run-id` accepted only on `report-only`; both required together.
- Incomplete pair returns `REPORT_ONLY_EXACT_IDENTITY_INCOMPLETE`.
- Explicit pair resolves only that campaign/run/configuration.
- No-argument mode resolves latest supervision first, then that exact pair.
- Exact report query requires `REPORT_TERMINAL`, matching campaign, matching configuration, matching run identity, and matching report JSON identity fields.
- Missing exact report returns `REPLAY_BLOCKED` / `EXACT_TERMINAL_REPORT_MISSING` with optional exact terminal-summary projection when identities match.
- Discovery-only is never a campaign report-only fallback.
- Successful and blocked replay remain zero-source, zero-Scheduler, zero-write.

## 6. Tests and exact results

Focused suite run (venv pytest):

| Suite | Result |
| --- | --- |
| `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` | 16 passed |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | included |
| `tests/test_v2_9_8b_terminal_safety_accounting_finalization.py` | included |
| Combined accounting + terminal safety + new repair file | 62 passed earlier; later combined core run 118 passed with discovery regressions |
| `tests/test_v2_9_7e_42_direct_migration_discovery.py` | passed in combined run |
| `tests/test_v2_9_7e_43_graduated_liquidity_front_door.py` | passed in combined run |
| `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py` | 26 passed |
| `test_status_and_report_only_are_zero_source_zero_write` | passed after zero-work stamp fix |
| Python compile of changed sources | pass |
| `git diff --check` | pass |

Covered behaviors:

- sealed evidence ingestion, duplicate stage ID, duplicate transport, identity mismatch, invalid status/sequence, negative counters, atomic rollback, stable first block reason
- direct migration seals once; locator seals once when attempted; no locator stage when not requested; distinct liquidity round stage IDs; failed/malformed liquidity still measures transports; sink exception path
- July 31-shaped 30-operation shortage handoff with independent reconstruction
- exact report-only identity, incomplete pair, latest-supervision-first, no global/discovery fallback, zero-work replay

No full repository suite was run. No providers or authoritative campaign were run.

## 7. Authoritative DB hash before and after

```text
before: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
after:  f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
```

Identical. No authoritative mutation.

## 8. Money-usefulness contribution

Printer can now preserve honest negative learning about source visibility and market eligibility with a complete accounting chain. Operators can no longer mistake an unrelated historical report for the current attempt. Incomplete evidence still cannot become clean memory or a paper decision.

## 9. What improved

- ingest-before-shortage / ingest-before-return stage handoff
- single accounting authority preserved
- sealed-stage uniqueness and diagnostics
- action-local completeness gate for pre-lifecycle terminals
- exact-identity report-only
- deterministic blocked replay for missing exact reports

## 10. What remains locked

- clean-memory creation / retrieval activation
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL
- live wallets, private keys, signing, real funds, live execution
- paid APIs, scoring, ranking, confidence, weighting, embeddings/vectors
- `WINDOW_1H` / longer production activation
- historical July 31 report backfill or reclassification
- campaign rerun of the permanent no-rerun marker attempt
- candidate-acquisition N2/N7, cursor recovery, provider campaigns

## 11. Proof still required

- Operator review of this branch and closeout
- Optional later disposable end-to-end coordinator proof using frozen transports and a full operational owner (not authorized automatically by this lane)
- No live provider campaign is authorized by this PASS

## 12. Functionality Risks / Setbacks / Efficiency Blockers

- Multi-hop locator transports can exceed governed request counts; the completeness gate therefore treats action-local **greater than** owner transport total as mismatch (missing evidence), not owner greater than action-local (multi-hop).
- Fixture/offline transports that omit declared transport identities still fail closed when a stage sink is required; they must declare measured identities.
- Holder/lifecycle stages after lifecycle start are not forced into the pre-lifecycle action-local equality check; later lanes may need explicit sealed stages for those owners if full-run identity equality is required.
- Existing historical report shapes remain readable only when exact identity fields agree; compatibility does not restore global fallback.
- Cross-cutting accounting and report-only changes required nearest regressions; broader suite was intentionally not expanded.

## 13. Factual verdict

```text
V2_9_8B_FIRST_AUTHORITATIVE_15M_ACCOUNTING_EXACT_IDENTITY_REPORT_ONLY_REPAIR_IMPLEMENTATION_PASS
```

## 14. Exact next permitted lane

```text
Operator review of the accounting / exact-identity report-only repair branch and closeout only.
```

No automatic campaign, recovery, cursor reset, N2/N7, provider/RPC work, retrieval, or financial unlock is authorized.
