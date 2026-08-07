# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Pre-Existing Regression Classification

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_PRE_EXISTING_REGRESSIONS_CLASSIFIED_OUT_OF_SCOPE`

Classification baseline:

`6956013ac0d4eb68b0955882a1c40e5bf5f3ae15` — `Add Checkpoint 8 pre-proof acceptance replay REDs`

## Classification result

The broad affected-regression selector used during the first C8 acceptance/replay implementation attempt surfaced six failures. The exact same six failures were then reproduced on the untouched classification baseline above, before the C8 acceptance/replay source patch was applied.

Therefore these failures are pre-existing and are not regressions caused by the C8 acceptance/replay repair.

### Five legacy authoritative-owner failures

All five fail in the historical non-permanent `graduated_supply is None` path when `pre_lifecycle_admission["ordered_selected_slots"]` dereferences `supply.holder_reserve_candidates`:

- `NaturalOperationalLifecycleProofTests::test_governed_secondary_enrichment_flows_through_existing_normalizers`
- `NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof`
- `NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer`
- `TwoTerminalCloseBarrierTests::test_both_terminal_closes_resolve_with_no_deferred_markers`
- `TwoTerminalCloseBarrierTests::test_first_close_alone_schedules_no_continuation`

Source test file:

`tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py`

Observed pre-existing failure owner:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

### One historical 15m DB-binding failure

- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py::test_ordinary_disposable_two_token_window_15m_regression`

It fails under the existing 15m database-target binding law with `OPERATIONAL_DB_BINDING_MISSING`.

## Lane decision

Do not repair these failures inside Checkpoint 8 pre-proof acceptance/replay work. They do not originate in the two files modified by that repair and expanding scope would violate risk-based verification.

Checkpoint 8 verification therefore uses the minimum directly affected accounting/report/replay regression set while retaining these six failures as documented pre-existing debt.

No production/provider run, memory proof, retrieval, decision, position, trade, audit or PnL capability is authorized by this classification.