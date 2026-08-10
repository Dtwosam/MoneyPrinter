"""Pure production standard-four-hour campaign eligibility boundary.

No source fetch, Scheduler mutation, database mutation, or successor creation is
performed here. The canonical token-local continuation policy remains the sole
hard-gate evaluator; this module only enforces the post-DTW100 1h->4h verdict
vocabulary and returns the exact eligible slot subset.
"""

from __future__ import annotations

from typing import Iterable

from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ContinuationVerdict,
    TokenContinuationInput,
    evaluate_token_local_continuations,
)


STANDARD_FOUR_HOUR_ALLOWED_VERDICTS = frozenset(
    {
        ContinuationVerdict.CONTINUE_TO_WINDOW_4H.value,
        ContinuationVerdict.BLOCK_CONTINUATION.value,
    }
)


class StandardFourHourOperationalError(RuntimeError):
    """Fail-closed standard-four-hour campaign-barrier error."""


def evaluate_standard_four_hour_eligibility(
    *,
    campaign: CampaignContinuationContext,
    tokens: Iterable[TokenContinuationInput],
) -> dict[str, object]:
    token_inputs = tuple(tokens)
    if len(token_inputs) != 2:
        raise StandardFourHourOperationalError(
            "standard four-hour campaign barrier requires exactly two token slots"
        )
    try:
        results = evaluate_token_local_continuations(
            campaign=campaign,
            tokens=token_inputs,
        )
    except Exception as exc:
        raise StandardFourHourOperationalError(str(exc)) from exc

    verdicts: dict[str, str] = {}
    reasons: dict[str, tuple[str, ...]] = {}
    eligible: list[str] = []
    for result in results:
        verdict = str(result.verdict)
        if verdict not in STANDARD_FOUR_HOUR_ALLOWED_VERDICTS:
            raise StandardFourHourOperationalError(
                f"unexpected standard 1h->4h verdict: {verdict}"
            )
        slot_id = str(result.token_slot_id)
        verdicts[slot_id] = verdict
        reasons[slot_id] = tuple(result.reasons)
        if verdict == ContinuationVerdict.CONTINUE_TO_WINDOW_4H.value:
            eligible.append(slot_id)
    return {
        "eligible_token_slot_ids": tuple(eligible),
        "continuation_count": len(eligible),
        "verdicts": verdicts,
        "reasons": reasons,
    }
