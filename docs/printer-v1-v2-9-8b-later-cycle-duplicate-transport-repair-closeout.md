# Printer V1 V2-9.8B Later-Cycle Duplicate-Transport Authoritative Repair Closeout

Date: 2026-09-02

Verdict:

`V2_9_8B_LATER_CYCLE_DUPLICATE_TRANSPORT_AUTHORITATIVE_REPAIR_PASS`

This closeout records authoritative host-local integration, bounded proof, and
governance closeout of the proven later-cycle cooperative mint-market-batch
duplicate transport identity defect. It does not run Printer, prepare or apply
an authorization, reuse a consumed authorization, or start another Standard-4H
campaign.

## 1. Authority

Active source stack unchanged:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

Campaign closeout that proved the defect:

`docs/printer-v1-v2-9-8b-auth-12a7ea61-campaign-closeout.md`

Scope-propagation repair closeout (must not be regressed):

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-closeout.md`

The operator authorized this lane as:

```text
AUTHORITATIVE REPAIR INTEGRATION -> BOUNDED PROOF -> CLOSEOUT
```

for the independently verified portable replay repair. This closeout does not
reopen the 12a7ea61 campaign and does not rewrite historical campaign truth.

## 2. Authoritative starting lineage

| Item | Value |
| --- | --- |
| Starting branch | `assistant/v2-9-8b-auth-12a7ea61-campaign-closeout` |
| Starting HEAD | `903046d7dc6b215b80eeed5633072eb1cd39dfe2` |
| Historical campaign closeout | that same HEAD |
| Authoritative repaired execution HEAD | `91c757c542d8098ecf7b244769061f333dcfc21f` |
| Ancestry | `91c757c5` is an ancestor of the starting HEAD and of the integrated repair |
| Tracked tree at start | clean (untracked `operator-runs/` residue only) |
| Active Printer process | none |
| Pending cherry-pick / rebase / merge | none |
| Authoritative DB SHA-256 | `a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c` |

The production ancestry includes the already-proven CampaignSourceRequestScope
propagation repair. That repair was not redone and was not duplicated.

## 3. Integration branch and repair commit

| Item | Value |
| --- | --- |
| Integration branch | `assistant/v2-9-8b-later-cycle-mint-market-replay-repair` |
| Branch parent | `903046d7dc6b215b80eeed5633072eb1cd39dfe2` |
| Integrated repair commit | `041e2550ec2ec090e45eec2d8de45f6a0c1e84f0` |
| Verified portable replay-only commit | `173cb1bd7c16104dc5e4266b8f1886d0275dc168` |
| Replay commit message | `fix: preserve cooperative mint-market completion state` |
| Remote candidate branch | `assistant/v2-9-8b-replay-only-integration-candidate` |

Cherry-pick of `173cb1bd` onto the host-local closeout HEAD was **not clean**.
The replay commit parent used simulated `campaign_source_scope_obj` wiring
(`6786b9e0 sim: normalize scope wiring to verified placement`). Host-local
authoritative code already forwards the authentic
`campaign_source_request_scope` parameter from the scope-propagation repair.

The conflict was inspected and not blindly resolved. The helper function from
`173cb1bd` was applied byte-identically. The MARKET_DISCOVERY resume call site
was mapped onto host-local `campaign_source_request_scope` and the existing
invocation identities (`execution_id`, `campaign_id`, `run_id`, `cycle_id`).
Diagnostics fields were inserted beside `cooperative_phase` without replacing
the host-local scope diagnostic block.

A GitHub branch named `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`
already existed on origin, but it does **not** contain execution HEAD
`91c757c5`. It was not used as the integration base.

## 4. Exact files changed

Repair commit `041e2550`:

- `src/printer_v1/discovery/eligible_token_supply.py`
- `tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py`

The focused regression test file is byte-identical to `173cb1bd`.
`load_completed_cooperative_mint_market_batch_mints` is byte-identical to
`173cb1bd`.

No other production file changed. `CampaignSixUnitOwner` is unchanged.

## 5. Replay defect

Proven producer:

Cooperative Cycle-2 `MARKET_DISCOVERY` resume rehydrated evaluated mints from
fresh MOE inventory only. A mint whose current-cycle DexScreener
`MINT_MARKET_BATCH` round transport had already completed `COMPLETE` +
`CLEAN_DATA` with the exact canonical due-mint identity was forgotten and
re-issued as `due_mints`. Canonical transport identity keys exclude stage
sequence, so mint-batch `r1` and `r2` collided in the Cycle 2 six-unit owner.

Classification remains:

`COMMITTED_CODE_DEFECT` /
`LATER_CYCLE_COOPERATIVE_MINT_MARKET_BATCH_DUPLICATE_TRANSPORT_IDENTITY`

## 6. Source-of-truth behavior

A mint with:

`COMPLETE + CLEAN_DATA + exact canonical current-cycle MINT_MARKET_BATCH transport`

must not be put back into `due_mints` merely because fresh MOE has not yet been
created.

The repair does **not** mark the mint MOE-complete. It only prevents replay of
an already-completed identical transport by rehydrating those mints into
`evaluated_mints` before the MARKET_DISCOVERY due-set is built.

Must remain retryable / unsuppressed:

- failed transport;
- rate-limited transport;
- partial response;
- dirty / stale response;
- malformed transport identity;
- foreign campaign evidence;
- foreign cycle evidence;
- historical unrelated evidence;
- genuinely distinct canonical transport, including protocol-resume batches.

`CampaignSixUnitOwner` remains unchanged and fail-closed.
`DUPLICATE_TRANSPORT_IDENTITY` is not weakened.

Missing `campaign_source_request_scope` on this cooperative MARKET_DISCOVERY
resume path still raises `CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`.

## 7. RED / GREEN provenance

RED: the 12a7ea61 campaign sealed Cycle 2 mint-batch `r1` for
`AQi9C9ak1TKTse3kSFKANybEhZmaVpTab1ukhsEhpump` and then re-issued the same
canonical due-mint identity as `r2`, raising
`SIX_UNIT_STAGE_EVIDENCE_DUPLICATE_TRANSPORT:DUPLICATE_TRANSPORT_IDENTITY`.

GREEN: focused replay tests now prove that a complete current-cycle round
batch is rehydrated, that failed / partial / malformed / foreign / non-round
evidence is not suppressed, and that MARKET_DISCOVERY resume uses the
rehydrated set before issuing another due-mint batch.

## 8. Authoritative focused test results

| Proof | Result |
| --- | --- |
| `tests/test_v2_9_8b_later_cycle_mint_market_replay_repair.py` | `6 passed` |
| `tests/test_v2_9_8b_terminal_safety_accounting_finalization.py::test_accounting_rejects_absence_malformed_duplicate_mismatch_and_accepts_explicit_no_work` | `1 passed` |
| `tests/test_v2_9_8b_freeze_ready_wiring_completion.py` | `5 passed` |
| `tests/test_v2_9_8b_campaign_source_request_scope_propagation_repair.py` | `8 passed` |
| `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py::EligibleTokenSupplyArchitectureTests::test_two_eligible_outside_first_six_discovered_and_selected` | `1 passed` |
| `python -m py_compile` of changed Python files | PASS |
| `git diff --check` | PASS |

`tests/test_v2_9_8b_window_15m_source_request_scope_repair.py` was run as
required. Result on the repaired tree: `19 passed, 7 failed`. The same 7
tests fail on parent `903046d7` with the same assertions. They are
pre-existing baseline residue in that older window-15m file, not a regression
from this repair. They were not expanded into a repair in this lane.

The current host-local scope-propagation repair file remains `8 passed`.

## 9. Cycle-1 non-regression

`test_two_eligible_outside_first_six_discovered_and_selected` passed. The
Cycle-2 cooperative MARKET_DISCOVERY resume path does not disturb normal
first-cycle acquisition.

## 10. Six-unit duplicate fail-closed proof

`test_accounting_rejects_absence_malformed_duplicate_mismatch_and_accepts_explicit_no_work`
passed. Genuine duplicate transport identity remains rejected. This repair
does not catch, rename, or bypass `DUPLICATE_TRANSPORT_IDENTITY`.

## 11. Source Governor verdict

`SOURCE_GOVERNOR_UNCHANGED_NO_BYPASS`

The repair only reads durable `printer_source_requests` /
`printer_source_responses` already owned by Source Governor. It issues no
provider call, creates no request, and does not rotate endpoints or increase
budgets. Resume validation still uses
`validate_campaign_source_request_scope` and
`validate_cooperative_resume_source_request_scope`.

## 12. Central Scheduler verdict

`CENTRAL_SCHEDULER_UNCHANGED_NO_BYPASS`

No scheduler owner, cadence, lease, or quantum contract changed. Cooperative
resume remains Scheduler-led. This lane did not run Central Scheduler.

## 13. DB mutation verdict

`AUTHORITATIVE_DB_UNTOUCHED`

Authoritative DB path `data/printer_v1.sqlite3` SHA-256 remained
`a3172e04f99ef410ba66eb4e2928b5b4edbdd7dfad4d713fcd1605fa3b702a8c` before and
after this lane. No migration was added or applied. Focused tests used
disposable SQLite only.

## 14. Permanent lock verdict

Unchanged:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet / private keys / signing / real funds;
- no paid APIs;
- no scoring / ranking / confidence / weighted logic;
- no embeddings / vectors;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty-memory retrieval;
- retrieval locked;
- BUY / SELL / HOLD locked;
- positions / trades / audits / PnL locked;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_12H` and `WINDOW_24H` locked;
- no automatic retry / rerun / resume / restart / successor;
- candidate capacity unchanged (exactly 2 concurrent; 4/2/2 envelope unchanged);
- freeze-ready depth unchanged;
- request budget unchanged.

## 15. Consumed authorization non-reuse

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T203521Z_12a7ea61` remains:

`CONSUMED / CHILD_EXITED_ZERO / PERMANENTLY NON-REUSABLE`

Consumed `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe` remains:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Neither was retried, rerun, resumed, restarted, reused, or used as successor
authority. Both must remain in every future Standard-4H prior non-reuse trust
root, together with every already-required prior ID, including stale
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`.

The application marker was not modified.

## 16. Explicit non-changes

- no six-unit accounting weakening;
- no Source Governor bypass;
- no Scheduler bypass;
- no candidate-capacity change;
- no 4/2/2 change;
- no freeze-ready depth change;
- no request-budget increase;
- no endpoint rotation;
- no retries / reruns;
- no retrieval / financial changes;
- no migrations;
- no Printer execution;
- no authorization preparation or application.

## 17. Exact next permitted lane

```text
POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE
```

Do not enter that lane automatically. This closeout does not prepare or apply
an authorization and does not run Printer.
