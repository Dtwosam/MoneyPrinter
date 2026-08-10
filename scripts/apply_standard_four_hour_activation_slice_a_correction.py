from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected correction anchor missing in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# The pre-activation continuity helper intentionally rejected an enabled successor.
# Activation replaces that temporary cadence lock with an explicit caller authority;
# default callers still fail closed when the successor cadence is enabled.
replace_once(
    "src/printer_v1/snapshots/lifecycle_continuity.py",
    '''def build_long_window_continuation_plan(
    predecessor: Mapping[str, Any],
    successor_kind: str,
) -> dict[str, Any]:
''',
    '''def build_long_window_continuation_plan(
    predecessor: Mapping[str, Any],
    successor_kind: str,
    *,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
''',
)
replace_once(
    "src/printer_v1/snapshots/lifecycle_continuity.py",
    '''    if policy is not None and policy.enabled_for_real_collection:
        reasons.append("successor_not_disabled_for_real_collection")
''',
    '''    if (
        policy is not None
        and policy.enabled_for_real_collection
        and not allow_enabled_successor_planning
    ):
        reasons.append("successor_enabled_without_explicit_planning_authority")
''',
)
replace_once(
    "src/printer_v1/snapshots/lifecycle_continuity.py",
    '''    successor_kind: str,
    current_close_step_id: int | None = None,
) -> dict[str, Any]:
''',
    '''    successor_kind: str,
    current_close_step_id: int | None = None,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
''',
)
replace_once(
    "src/printer_v1/snapshots/lifecycle_continuity.py",
    '''    plan = build_long_window_continuation_plan(row, successor_kind)
''',
    '''    plan = build_long_window_continuation_plan(
        row,
        successor_kind,
        allow_enabled_successor_planning=allow_enabled_successor_planning,
    )
''',
)

# Thread the explicit authority through the 4h planner. The standard campaign
# composer requires STANDARD_CAMPAIGN; historical one-token proof remains PROOF.
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''    current_close_step_id: int | None = None,
    cumulative_scheduler_ceiling: int | None = None,
) -> dict[str, Any]:
''',
    '''    current_close_step_id: int | None = None,
    cumulative_scheduler_ceiling: int | None = None,
    allow_enabled_successor_planning: bool = False,
) -> dict[str, Any]:
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''        successor_kind=WINDOW_KIND,
        current_close_step_id=current_close_step_id,
    )
''',
    '''        successor_kind=WINDOW_KIND,
        current_close_step_id=current_close_step_id,
        allow_enabled_successor_planning=allow_enabled_successor_planning,
    )
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''        current_close_step_id=current_close_step_id,
        cumulative_scheduler_ceiling=(
            cumulative_scheduler_ceiling if compressed_two_token_proof else None
        ),
    )
''',
    '''        current_close_step_id=current_close_step_id,
        cumulative_scheduler_ceiling=(
            cumulative_scheduler_ceiling if compressed_two_token_proof else None
        ),
        allow_enabled_successor_planning=True,
    )
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''    eligible_token_slot_ids: Sequence[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose the exact eligible subset of the standard two-slot 4h campaign."""
''',
    '''    eligible_token_slot_ids: Sequence[str] | None = None,
    execution_authority: FourHourExecutionAuthority | str = FourHourExecutionAuthority.DISABLED,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose the exact eligible subset of the standard two-slot 4h campaign."""
    try:
        authority = FourHourExecutionAuthority(execution_authority)
    except ValueError as exc:
        raise ValueError("invalid standard four-hour execution authority") from exc
    if authority != FourHourExecutionAuthority.STANDARD_CAMPAIGN:
        raise ValueError(
            "standard four-hour campaign planning requires explicit STANDARD_CAMPAIGN authority"
        )
''',
)
replace_once(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    '''                tracking_lane=lane,
                cumulative_scheduler_ceiling=int(budget["scheduler_ceiling"]),
            )
''',
    '''                tracking_lane=lane,
                cumulative_scheduler_ceiling=int(budget["scheduler_ceiling"]),
                allow_enabled_successor_planning=True,
            )
''',
)

# Existing offline fixture suites exercise the production standard composer on
# isolated databases. Make that authority explicit and update activation-era
# cadence expectations; no source/runtime call is performed by these helpers.
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py",
    '''            candidates=candidates,
            now=_iso(T1H),
        )
''',
    '''            candidates=candidates,
            execution_authority=(
                one_token_4h_runtime.FourHourExecutionAuthority.STANDARD_CAMPAIGN
            ),
            now=_iso(T1H),
        )
''',
)
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py",
    '''            self.assertFalse(bool(budget["real_collection_enabled"]))
''',
    '''            self.assertTrue(bool(budget["real_collection_enabled"]))
''',
)
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py",
    '''                self.assertFalse(
                    bool(one_token_4h_runtime.runtime_budget(lane)["enabled_for_real_collection"])
                )
''',
    '''                self.assertTrue(
                    bool(one_token_4h_runtime.runtime_budget(lane)["enabled_for_real_collection"])
                )
''',
)
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset.py",
    '''            candidates=self.candidates,
            eligible_token_slot_ids=eligible_slots,
            now=_iso(T1H),
        )
''',
    '''            candidates=self.candidates,
            eligible_token_slot_ids=eligible_slots,
            execution_authority=(
                one_token_4h_runtime.FourHourExecutionAuthority.STANDARD_CAMPAIGN
            ),
            now=_iso(T1H),
        )
''',
)

# Explicitly preserve the fail-closed default in an existing production-planner
# fixture suite so cadence=true alone can never become planning authority.
insert_anchor = '''    def test_mixed_fast_normal_plans_exact_two_token_long_work_and_ownership(self) -> None:
'''
new_test = '''    def test_enabled_cadence_without_standard_authority_fails_closed(self) -> None:
        fx, candidates = self._prepared()
        try:
            planner = one_token_4h_runtime.plan_standard_campaign_4h_handoff
            with self.assertRaisesRegex(ValueError, "explicit STANDARD_CAMPAIGN authority"):
                planner(
                    fx.connection,
                    campaign_id="campaign-1h",
                    run_id="run-1h",
                    cycle_id="cycle-1h",
                    factory_run_id="factory-run-1",
                    candidates=candidates,
                    now=_iso(T1H),
                )
            self.assertEqual(
                int(fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows WHERE window_kind='WINDOW_4H'"
                ).fetchone()[0]),
                0,
            )
        finally:
            fx.close()

'''
replace_once(
    "tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py",
    insert_anchor,
    new_test + insert_anchor,
)
