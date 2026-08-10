from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


policy_path = Path("src/printer_v1/scheduler/token_local_continuation.py")
budget_path = Path("src/printer_v1/operator_cli/one_token_4h_runtime.py")
legacy_test_path = Path("tests/test_v2_9_7d_4a_token_local_selective_continuation.py")
composition_test_path = Path("tests/test_post_dtw100_first_hour_lifecycle_policy.py")

policy = policy_path.read_text(encoding="utf-8")
budget = budget_path.read_text(encoding="utf-8")
legacy = legacy_test_path.read_text(encoding="utf-8")
composition = composition_test_path.read_text(encoding="utf-8")

policy = replace_once(
    policy,
'''Post-DTW100 policy amendment: WINDOW_15M -> WINDOW_1H is the standard bounded
first-hour lifecycle for every otherwise-valid activated token. Outcome or
learning-need labels do not qualify that transition. WINDOW_1H -> WINDOW_4H
remains selective and learning-need-gated.
''',
'''Post-DTW100 policy amendments: WINDOW_15M -> WINDOW_1H and
WINDOW_1H -> WINDOW_4H are the standard bounded first-four-hour lifecycle for
every otherwise-valid activated token. Outcome or learning-need labels do not
qualify either transition. Automatic continuation stops at WINDOW_4H.
''',
    "policy module description",
)
policy = replace_once(
    policy,
'''_FIRST_HOUR_TRANSITION = (
    MemoryWindowKind.WINDOW_15M,
    MemoryWindowKind.WINDOW_1H,
)

_ALLOWED_TRANSITIONS = {
''',
'''_FIRST_HOUR_TRANSITION = (
    MemoryWindowKind.WINDOW_15M,
    MemoryWindowKind.WINDOW_1H,
)
_FIRST_FOUR_HOUR_TRANSITION = (
    MemoryWindowKind.WINDOW_1H,
    MemoryWindowKind.WINDOW_4H,
)
_STANDARD_OBSERVATION_TRANSITIONS = frozenset(
    {_FIRST_HOUR_TRANSITION, _FIRST_FOUR_HOUR_TRANSITION}
)

_ALLOWED_TRANSITIONS = {
''',
    "policy standard transition constants",
)
policy = replace_once(
    policy,
'''    # Post-DTW100 first-hour lifecycle amendment: once a token has passed every
    # hard operational/evidence/identity/safety/continuity gate above, the only
    # remaining first-hour resource gate is the bounded token budget. A 15m
    # outcome or learning-need label has no authority to stop observation.
    if transition_key == _FIRST_HOUR_TRANSITION:
        if not token.token_budget_available:
            return _result(
                token,
                ContinuationVerdict.BLOCK_CONTINUATION,
                ("token_budget_exhausted",),
            )
        return _result(
            token,
            ContinuationVerdict.CONTINUE_TO_WINDOW_1H,
            ("standard_first_hour_lifecycle",),
        )

    # Later windows remain selective. Preserve the established 1h -> 4h
    # decision order exactly: no learning need is a normal stop; an applicable
    # need then still requires available token budget.
''',
'''    # Post-DTW100 standard observation amendments: once a token has passed every
    # hard operational/evidence/identity/safety/continuity gate above, 15m->1h
    # and 1h->4h are governed only by the remaining bounded token-resource gate.
    # Outcome and learning-need labels have no authority to stop or promote
    # observation within the first four hours.
    if transition_key in _STANDARD_OBSERVATION_TRANSITIONS:
        if not token.token_budget_available:
            return _result(
                token,
                ContinuationVerdict.BLOCK_CONTINUATION,
                ("token_budget_exhausted",),
            )
        if transition_key == _FIRST_HOUR_TRANSITION:
            return _result(
                token,
                ContinuationVerdict.CONTINUE_TO_WINDOW_1H,
                ("standard_first_hour_lifecycle",),
            )
        return _result(
            token,
            ContinuationVerdict.CONTINUE_TO_WINDOW_4H,
            ("standard_first_four_hour_lifecycle",),
        )

    # Any later approved transition remains selective. The learning-need
    # vocabulary is intentionally retained for those future lanes.
''',
    "policy standard evaluation",
)

budget = replace_once(
    budget,
'''def require_projected_capacity(
''',
'''def standard_two_token_lifecycle_budget(
    tracking_lanes: tuple[str, str],
) -> dict[str, Any]:
    """Derive the bounded two-token 15m+1h+4h campaign ceilings from policy."""
    lanes = tuple(str(lane) for lane in tracking_lanes)
    if len(lanes) != 2:
        raise ValueError("standard four-hour campaign requires exactly two tracking lanes")
    request_components: dict[str, int] = {"discovery": 2}
    scheduler_components: dict[str, int] = {}
    for index, lane in enumerate(lanes, start=1):
        lifecycle = cumulative_lifecycle_budget(lane)
        if lane not in REQUEST_CEILINGS:
            raise ValueError("TRACK_FAST or TRACK_NORMAL cadence policy required")
        for name, value in lifecycle["request_components"].items():
            if name == "discovery":
                continue
            request_components[f"token_{index}_{name}"] = int(value)
        for name, value in lifecycle["scheduler_components"].items():
            scheduler_components[f"token_{index}_{name}"] = int(value)
    return {
        "tracking_lanes": lanes,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "real_collection_enabled": all(
            bool(runtime_budget(lane)["enabled_for_real_collection"]) for lane in lanes
        ),
    }


def require_projected_capacity(
''',
    "two-token budget owner",
)

legacy = replace_once(
    legacy,
'''    def test_only_token_b_continues_1h_to_4h(self) -> None:
        a = replace(_token("A", stage="1h_to_4h"), learning_need=None)
        b = _token("B", stage="1h_to_4h")
        result = self._evaluate(a=a, b=b)
        self.assertEqual(result[0].verdict, ContinuationVerdict.STOP_AFTER_WINDOW_1H)
        self.assertEqual(result[1].verdict, ContinuationVerdict.CONTINUE_TO_WINDOW_4H)
''',
'''    def test_both_tokens_continue_1h_to_4h_without_learning_need_gate(self) -> None:
        a = replace(_token("A", stage="1h_to_4h"), learning_need=None)
        b = _token("B", stage="1h_to_4h")
        result = self._evaluate(a=a, b=b)
        self.assertEqual(
            [item.verdict for item in result],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_4H] * 2,
        )
        self.assertTrue(
            all(item.reasons == ("standard_first_four_hour_lifecycle",) for item in result)
        )
''',
    "legacy 1h-to-4h expectation",
)

composition = replace_once(
    composition,
'''    def test_5m_support_cannot_authorize_first_hour_and_1h_to_4h_remains_selective(self) -> None:
''',
'''    def test_5m_support_cannot_authorize_main_lifecycle_and_1h_to_4h_is_standard(self) -> None:
''',
    "composition test name",
)
composition = replace_once(
    composition,
'''        self.assertEqual(
            [item.verdict for item in later],
            [ContinuationVerdict.STOP_AFTER_WINDOW_1H] * 2,
        )
        self.assertTrue(
            all(item.reasons == ("no_unresolved_learning_need",) for item in later)
        )
''',
'''        self.assertEqual(
            [item.verdict for item in later],
            [ContinuationVerdict.CONTINUE_TO_WINDOW_4H] * 2,
        )
        self.assertTrue(
            all(
                item.reasons == ("standard_first_four_hour_lifecycle",)
                for item in later
            )
        )
''',
    "composition 4h expectation",
)

policy_path.write_text(policy, encoding="utf-8")
budget_path.write_text(budget, encoding="utf-8")
legacy_test_path.write_text(legacy, encoding="utf-8")
composition_test_path.write_text(composition, encoding="utf-8")
