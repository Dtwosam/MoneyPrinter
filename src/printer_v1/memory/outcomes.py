"""Episode outcome labeling from completed local snapshot windows."""

from typing import Any, Mapping, Sequence

from printer_v1.memory.contracts import ActionLessonLabel, EpisodeOutcomeLabel


def numeric(value: Any) -> float | None:
    return float(value) if value is not None else None


def percent_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return ((end - start) / start) * 100.0


def calculate_window_price_path(snapshots: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = sorted([dict(row) for row in snapshots], key=lambda row: str(row.get("captured_at") or ""))
    prices = [numeric(row.get("price_usd")) for row in rows]
    prices = [price for price in prices if price is not None]
    if not prices:
        return {
            "price_start": None,
            "price_high": None,
            "price_low": None,
            "price_end": None,
            "price_change_percent": None,
            "max_runup_percent": None,
            "max_drawdown_percent": None,
        }
    start = prices[0]
    high = max(prices)
    low = min(prices)
    end = prices[-1]
    return {
        "price_start": start,
        "price_high": high,
        "price_low": low,
        "price_end": end,
        "price_change_percent": percent_change(start, end),
        "max_runup_percent": percent_change(start, high),
        "max_drawdown_percent": percent_change(start, low),
    }


def classify_episode_outcome(
    window_kind: str,
    snapshots: Sequence[Mapping[str, Any]],
    liquidity_exit_context: Mapping[str, Any] | None = None,
    micro_event_context: Mapping[str, Any] | None = None,
) -> EpisodeOutcomeLabel:
    path = calculate_window_price_path(snapshots)
    change = path["price_change_percent"]
    runup = path["max_runup_percent"]
    drawdown = path["max_drawdown_percent"]
    liquidity = dict(liquidity_exit_context or {})
    micro = dict(micro_event_context or {})
    if window_kind == "WINDOW_5M":
        return EpisodeOutcomeLabel.OUTCOME_UNKNOWN
    if change is None or runup is None or drawdown is None:
        return EpisodeOutcomeLabel.OUTCOME_UNKNOWN
    if liquidity.get("realism_gate_label") in {"REALISM_CONTEXT_BLOCKED", "REALISM_CONTEXT_DO_NOT_TRAIN"}:
        return EpisodeOutcomeLabel.UNREALISTIC_PROFIT if runup >= 20 else EpisodeOutcomeLabel.OUTCOME_UNKNOWN
    if liquidity.get("entry_realism_label") == "ENTRY_REALISTIC" and liquidity.get("exit_realism_label") == "EXIT_REALISTIC" and change >= 25:
        return EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT
    if runup >= 39.9 and change <= 8:
        return EpisodeOutcomeLabel.ROUND_TRIP
    if runup >= 25 and change <= -10:
        return EpisodeOutcomeLabel.PUMP_AND_DUMP
    if runup >= 20 and change < 12:
        return EpisodeOutcomeLabel.FAKE_PUMP
    if change >= 100:
        return EpisodeOutcomeLabel.EXTENDED_PUMP
    if change >= 35:
        return EpisodeOutcomeLabel.SUSTAINED_PUMP
    if change >= 15:
        return EpisodeOutcomeLabel.SHORT_TERM_PUMP
    if change <= -40:
        return EpisodeOutcomeLabel.DEAD_TOKEN
    if change <= -15:
        return EpisodeOutcomeLabel.DUMP
    if -8 <= change <= 8:
        if micro.get("micro_event_state_label") == "MICRO_PUMP_TO_CONSOLIDATION":
            return EpisodeOutcomeLabel.CONSOLIDATION
        return EpisodeOutcomeLabel.NO_PUMP
    if drawdown <= -25 and change >= 10:
        return EpisodeOutcomeLabel.REVIVAL
    return EpisodeOutcomeLabel.OUTCOME_UNKNOWN


def classify_action_lesson(
    outcome_label: str | EpisodeOutcomeLabel,
    realistic_profit_possible: bool | None = None,
    capital_protection_possible: bool | None = None,
) -> ActionLessonLabel:
    outcome = EpisodeOutcomeLabel(outcome_label)
    if realistic_profit_possible and outcome == EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT:
        return ActionLessonLabel.ACTION_BUY_WORKED
    if outcome in {EpisodeOutcomeLabel.UNREALISTIC_PROFIT, EpisodeOutcomeLabel.PUMP_AND_DUMP, EpisodeOutcomeLabel.ROUND_TRIP}:
        return ActionLessonLabel.ACTION_HOLD_FAILED
    if capital_protection_possible or outcome in {EpisodeOutcomeLabel.DUMP, EpisodeOutcomeLabel.DEAD_TOKEN, EpisodeOutcomeLabel.FAKE_PUMP}:
        return ActionLessonLabel.ACTION_AVOID_WORKED
    if outcome in {EpisodeOutcomeLabel.NO_PUMP, EpisodeOutcomeLabel.CONSOLIDATION}:
        return ActionLessonLabel.ACTION_WAIT_WORKED
    if outcome in {EpisodeOutcomeLabel.SHORT_TERM_PUMP, EpisodeOutcomeLabel.SUSTAINED_PUMP, EpisodeOutcomeLabel.EXTENDED_PUMP}:
        return ActionLessonLabel.ACTION_WAIT_FAILED
    return ActionLessonLabel.ACTION_LESSON_UNKNOWN


def outcome_requires_audit(outcome_label: str | EpisodeOutcomeLabel) -> bool:
    return EpisodeOutcomeLabel(outcome_label) in {
        EpisodeOutcomeLabel.UNREALISTIC_PROFIT,
        EpisodeOutcomeLabel.ROUND_TRIP,
        EpisodeOutcomeLabel.PUMP_AND_DUMP,
        EpisodeOutcomeLabel.OUTCOME_UNKNOWN,
    }


def outcome_can_support_clean_memory(outcome_label: str | EpisodeOutcomeLabel, realism_context: Mapping[str, Any]) -> bool:
    outcome = EpisodeOutcomeLabel(outcome_label)
    if outcome in {EpisodeOutcomeLabel.OUTCOME_UNKNOWN, EpisodeOutcomeLabel.UNREALISTIC_PROFIT}:
        return False
    if outcome == EpisodeOutcomeLabel.REALISTIC_PAPER_PROFIT:
        return realism_context.get("entry_realism_label") == "ENTRY_REALISTIC" and realism_context.get("exit_realism_label") == "EXIT_REALISTIC"
    return True
