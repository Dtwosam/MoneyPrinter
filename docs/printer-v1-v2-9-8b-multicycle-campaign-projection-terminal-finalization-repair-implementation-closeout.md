# Printer V1 V2-9.8B Multi-Cycle Campaign Projection Terminal-Finalization Repair Implementation Closeout

Date: 2026-08-19

Lane: `V2-9.8B Multi-Cycle CampaignSixUnitProjection Terminal-Finalization Repair`

Status: `CLOSED_PASS`

Verdict:

`V2_9_8B_MULTICYCLE_CAMPAIGN_PROJECTION_TERMINAL_FINALIZATION_REPAIR_IMPLEMENTATION_PASS`

This is the implementation / bounded-proof closeout for PR #190. A PASS permits independent closeout/review only. It does not authorize a 4/2/2 run, create or reuse an authorization, merge the PR, or launch Printer.

## 1. Authority

Governing artifacts:

- `AGENTS.md` and the required Printer V1 source stack
- `docs/printer-v1-v2-9-8b-multicycle-campaign-six-unit-projection-terminal-finalization-repair-design.md` (`DESIGN_APPROVED_FOR_IMPLEMENTATION_BY_OPERATOR`)
- `docs/printer-v1-v2-9-8b-post-corrective-two-cycle-four-token-operational-4-2-2-authoritative-readiness.md` (readiness BLOCKED on this exact defect)

`CURRENT_HANDOFF.md` at branch start still described the readiness-blocked design-only next action. The committed design and operator instruction to finish this existing implementation are the lawful authority.

## 2. Branch and HEAD

| Item | Value |
|---|---|
| Branch | `agent/v2-9-8b-multicycle-campaign-projection-finalization-repair` |
| PR | `#190` (open, not merged) |
| PR base | `3c81b7b0cda9256e1d1e14eb5970cda2554d4692` |
| Executable defect baseline | `e8979e9c7e44e3165aa471827cecc407604895c0` |
| Starting HEAD at this finish-implementation handoff | `498e8a89e3952d82f5b046b8729c93c20014b805` |
| Closeout / handoff commit | this document's commit |

Verified at start: branch name and HEAD `498e8a8` matched the handoff.

## 3. Defect and repair

Observed live/readiness fault:

`FULL_RUN_FINALIZATION_FAULT:AttributeError:'CampaignSixUnitProjection' object has no attribute 'ingest_stage_evidence'`

`CampaignSixUnitProjection` is a read-only aggregate. Multi-cycle acceptance was passing that projection into `finalize_full_run_ownership_and_report()`, which still called `ingest_stage_evidence` when reconstructing missing `WINDOW_15M_SLOT_*` stages.

Committed production repair (already present at `498e8a8`, not reimplemented):

- `prepare_full_run_accounting_owner()` ingests only into a supplied mutable `CampaignSixUnitOwner`, then rebuilds the read-only projection.
- Missing stages on a projection without a lawful mutable owner fail closed as `MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED`.
- Missing rebuild factory after required ingest fails closed as `MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED` *before* mutating the cycle owner.
- `finalize_full_run_ownership_and_report()` collects durable slot-stage evidence first, then uses that helper.
- The operational coordinator keeps the mutable cycle owner as `accounting_stage_evidence_owner` and passes `cycle_accounting_registry.campaign_projection` as the rebuild factory.

`CampaignSixUnitProjection` still has no `ingest_stage_evidence`.

## 4. Files

Production (already committed before this closeout):

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`

Tests retained / supplemented in this closeout:

- `tests/test_v2_9_8b_multicycle_campaign_projection_finalization_repair.py`

Temporary scaffolding removed after committed-source proof:

- `tools/apply_v2_9_8b_multicycle_projection_finalization_repair.py`
- `.github/workflows/v2-9-8b-multicycle-projection-repair-proof.yml`

Design / readiness retained:

- `docs/printer-v1-v2-9-8b-multicycle-campaign-six-unit-projection-terminal-finalization-repair-design.md`
- `docs/printer-v1-v2-9-8b-post-corrective-two-cycle-four-token-operational-4-2-2-authoritative-readiness.md`

No migration. Head remains `058_direct_pump_migration_cursor.sql`.

## 5. Behavioral proof of the original defect

Disposable fixtures only.

1. A missing sealed stage is ingested into the supplied mutable cycle owner; a rebuilt projection contains it; the original projection object does not.
2. Preparing cycle-1 does not mutate cycle-2.
3. Re-preparing the same stage does not duplicate it.
4. `CampaignSixUnitProjection` has no `ingest_stage_evidence`.
5. A projection that needs a missing stage without a mutable owner raises `FullRunAccountingError:MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED`, not `AttributeError`.
6. A projection that needs a missing stage without a rebuild factory raises `MULTI_CYCLE_PROJECTION_REBUILD_REQUIRED` before the cycle owner is mutated or closed.
7. Ordinary single-cycle `CampaignSixUnitOwner` still ingests and closes exactly once.
8. Cross-cycle stage routing into the wrong mutable owner fails closed (`IDENTITY_MISMATCH`).
9. `_apply_full_run_campaign_acceptance(...)` with a read-only projection and no mutable owner returns `BLOCKED_UNSAFE` whose reason contains `MULTI_CYCLE_STAGE_EVIDENCE_OWNER_REQUIRED` and does **not** contain `AttributeError`.
10. The same acceptance seam with mutable owner + projection factory does not AttributeError; the other cycle owner stays empty.

## 6. Tests and checks

Interpreter: `.venv/bin/python` (3.12). `PYTHONPATH=src`.

Focused:

```text
python -m pytest -q tests/test_v2_9_8b_multicycle_campaign_projection_finalization_repair.py
```

**8 passed** after committed-source implementation and again after scaffolding removal.

Adjacent existing files enumerated from `tests/` (not guessed):

```text
python -m pytest -q \
  tests/test_v2_9_8b_multicycle_campaign_projection_finalization_repair.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_8b_e_per_cycle_six_unit_accounting.py \
  tests/test_v2_9_8b_four_token_gate_f_cycle_accounting.py \
  tests/test_v2_9_8b_four_token_gate_g_two_phase_terminal.py \
  tests/test_v2_9_8b_multi_cycle_lifecycle_identity_semantics.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py
```

**122 passed**, **7 failed**, 6 subtests passed.

The 7 failures are all `assert head.startswith("050")` against current head `058_direct_pump_migration_cursor.sql` in `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py`. They are pre-existing migration-head drift, not caused by this repair, and were not edited.

Compile/import of the two production modules: OK. `CampaignSixUnitProjection` has no `ingest_stage_evidence`. `git diff --check`: clean.

## 7. Locks / non-goals

No Source Governor or Central Scheduler change. No discovery/freeze/selection change. No E2Q/E2Z change. No wallet/flow change. No authorization. No Printer run. No provider contact. No authoritative DB mutation. No migration 059. Retrieval, BUY/SELL/HOLD, positions, trades, audits, PnL remain locked. 5m support-only. 12h/24h locked.

## 8. Exact next permitted action

`V2-9.8B Multi-Cycle Campaign Projection Terminal-Finalization Independent Closeout / Operator Review of PR #190`

Do **not** merge PR #190 from this closeout.
Do **not** create or reuse an authorization.
Do **not** run Printer.
Do **not** treat this PASS as 4/2/2 authorization readiness.
