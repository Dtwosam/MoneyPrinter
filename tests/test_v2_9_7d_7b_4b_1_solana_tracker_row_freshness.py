"""V2-9.7D.7B.4B.1 — Solana Tracker row-level freshness repair proof.

Synthetic fixtures only. No network. No live 7B.6 re-proof.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from printer_v1.sources.governor import can_request_source
from printer_v1.sources.secondary_discovery import (
    DISCARDED_NON_AUTHORITATIVE_FIELDS,
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
    SCHEDULER_JOB_KIND,
    SecondaryDiscoveryError,
    SolanaTrackerAuthConfig,
    TRACKER_SOURCE_NAME,
    TRACKER_STALE_AFTER_SECONDS,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    TRACKER_WORK_TYPE,
    fixture_operation,
    normalize_gecko_trending,
    normalize_tracker_list,
    run_solana_tracker_fixture_lane,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "secondary_discovery_adapters.json"
QUOTE = "So11111111111111111111111111111111111111112"
RECEIPT = "2026-07-19T12:00:00Z"
EVALUATED = "2026-07-19T12:01:00Z"
# Fresh relative to EVALUATED (within 180s): evaluated epoch - 60s, as ms.
FRESH_MS = 1_784_462_340_000  # 2026-07-19T12:00:00Z approx in fixture epoch
# Align to fixture evaluated epoch for deterministic ages.
# evaluated = 2026-07-19T12:01:00Z → compute from that.
from datetime import datetime, timezone  # noqa: E402


def _epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


EVAL_EPOCH = _epoch(EVALUATED)
FRESH_MS = int((EVAL_EPOCH - 60) * 1000)
STALE_MS = int((EVAL_EPOCH - (TRACKER_STALE_AFTER_SECONDS + 1)) * 1000)
FUTURE_MS = int((EVAL_EPOCH + 30) * 1000)  # >5s future → reject row


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def token_item(
    mint: str,
    pool: str,
    *,
    last_updated_ms: int,
    market: str = "pumpfun",
    rank: int | None = None,
    score: int | None = None,
    promoted: bool | None = None,
    risk: dict | None = None,
) -> dict:
    item: dict = {
        "token": {"mint": mint, "name": mint[:6]},
        "pools": [
            {
                "poolId": pool,
                "tokenAddress": mint,
                "quoteToken": QUOTE,
                "market": market,
                "lastUpdated": last_updated_ms,
            }
        ],
    }
    if rank is not None:
        item["rank"] = rank
    if score is not None:
        item["score"] = score
        item["pools"][0]["score"] = score
    if promoted is not None:
        item["promoted"] = promoted
    if risk is not None:
        item["risk"] = risk
    return item


class TestV297D7B4B1TrackerRowFreshness(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.evaluated = self.fixture["evaluated_at"]
        self.receipt = self.fixture["solana_tracker"]["trending"]["receipt_time"]
        self.auth = SolanaTrackerAuthConfig(
            api_key_secret_ref=self.fixture["solana_tracker"]["api_key_secret_ref"],
            free_requests_remaining_month=self.fixture["solana_tracker"][
                "free_requests_remaining_month"
            ],
            free_requests_per_second=self.fixture["solana_tracker"][
                "free_requests_per_second"
            ],
            free_requests_per_month=self.fixture["solana_tracker"][
                "free_requests_per_month"
            ],
        )

    def test_01_valid_row_normalizes(self) -> None:
        body = [
            token_item(
                "MintValid1111111111111111111111111111111111",
                "PoolValid1111111111111111111111111111111111",
                last_updated_ms=FRESH_MS,
            )
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].mint, "MintValid1111111111111111111111111111111111")
        self.assertEqual(rows[0].pool, "PoolValid1111111111111111111111111111111111")
        self.assertEqual(rows[0].venue, "pumpfun")
        self.assertEqual(rows[0].pumpfun_origin_status, "PROVIDER_LABEL_UNVERIFIED")

    def test_02_stale_row_no_contribution(self) -> None:
        body = [
            token_item(
                "MintStale1111111111111111111111111111111111",
                "PoolStale1111111111111111111111111111111111",
                last_updated_ms=STALE_MS,
            )
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(rows, ())

    def test_03_future_row_no_contribution(self) -> None:
        body = [
            token_item(
                "MintFuture111111111111111111111111111111111",
                "PoolFuture111111111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            )
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(rows, ())

    def test_04_mixed_preserves_only_valid(self) -> None:
        body = [
            token_item(
                "MintStaleMixed11111111111111111111111111111",
                "PoolStaleMixed11111111111111111111111111111",
                last_updated_ms=STALE_MS,
            ),
            token_item(
                "MintValidMixed11111111111111111111111111111",
                "PoolValidMixed11111111111111111111111111111",
                last_updated_ms=FRESH_MS,
            ),
            token_item(
                "MintFutureMixed111111111111111111111111111",
                "PoolFutureMixed111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            ),
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].mint, "MintValidMixed11111111111111111111111111111")

    def test_05_stale_future_before_valid_do_not_abort(self) -> None:
        body = [
            token_item(
                "MintStaleFirst1111111111111111111111111111",
                "PoolStaleFirst1111111111111111111111111111",
                last_updated_ms=STALE_MS,
            ),
            token_item(
                "MintFutureFirst111111111111111111111111111",
                "PoolFutureFirst111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            ),
            token_item(
                "MintValidLater1111111111111111111111111111",
                "PoolValidLater1111111111111111111111111111",
                last_updated_ms=FRESH_MS,
            ),
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(
            [row.mint for row in rows],
            ["MintValidLater1111111111111111111111111111"],
        )

    def test_06_stale_future_after_valid_do_not_remove_valid(self) -> None:
        body = [
            token_item(
                "MintValidEarly1111111111111111111111111111",
                "PoolValidEarly1111111111111111111111111111",
                last_updated_ms=FRESH_MS,
            ),
            token_item(
                "MintStaleAfter1111111111111111111111111111",
                "PoolStaleAfter1111111111111111111111111111",
                last_updated_ms=STALE_MS,
            ),
            token_item(
                "MintFutureAfter111111111111111111111111111",
                "PoolFutureAfter111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            ),
        ]
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(
            [row.mint for row in rows],
            ["MintValidEarly1111111111111111111111111111"],
        )

    def test_07_all_stale_future_returns_empty_not_exception(self) -> None:
        body = [
            token_item(
                "MintAllStale11111111111111111111111111111",
                "PoolAllStale11111111111111111111111111111",
                last_updated_ms=STALE_MS,
            ),
            token_item(
                "MintAllFuture1111111111111111111111111111",
                "PoolAllFuture1111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            ),
        ]
        rows = normalize_tracker_list(
            body,
            channel="TOP_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(rows, ())

    def test_08_invalid_top_level_schema_response_level(self) -> None:
        with self.assertRaises(SecondaryDiscoveryError) as exc:
            normalize_tracker_list(
                {"tokens": []},
                channel="TRENDING_PUMPFUN",
                receipt_time=RECEIPT,
                evaluated_at=EVALUATED,
            )
        self.assertEqual(exc.exception.code, "MALFORMED_RESPONSE")

        with self.assertRaises(SecondaryDiscoveryError) as ceiling:
            normalize_tracker_list(
                [
                    token_item(
                        f"MintCeil{i:03d}11111111111111111111111111111",
                        f"PoolCeil{i:03d}11111111111111111111111111111",
                        last_updated_ms=FRESH_MS,
                    )
                    for i in range(101)
                ],
                channel="TRENDING_PUMPFUN",
                receipt_time=RECEIPT,
                evaluated_at=EVALUATED,
            )
        self.assertEqual(ceiling.exception.code, "SCHEMA_OR_LIMIT_DRIFT")

        # Receipt-level staleness remains response-level.
        with self.assertRaises(SecondaryDiscoveryError) as receipt:
            normalize_tracker_list(
                [
                    token_item(
                        "MintReceipt11111111111111111111111111111",
                        "PoolReceipt11111111111111111111111111111",
                        last_updated_ms=FRESH_MS,
                    )
                ],
                channel="TRENDING_PUMPFUN",
                receipt_time="2026-07-19T11:50:00Z",
                evaluated_at=EVALUATED,
            )
        self.assertEqual(receipt.exception.code, "STALE_OR_UNKNOWN")
        self.assertEqual(receipt.exception.detail, "stale_receipt")

    def test_09_auth_and_transport_remain_response_level(self) -> None:
        bad_auth = SolanaTrackerAuthConfig(
            api_key_secret_ref="",
            free_requests_remaining_month=1000,
        )
        result = run_solana_tracker_fixture_lane(
            [],
            evaluated_at=EVALUATED,
            auth=bad_auth,
        )
        self.assertEqual(result.status, "FAILED")
        self.assertTrue(any(f.code == "BLOCKED_AUTH" for f in result.failures))
        self.assertEqual(result.observations, ())

        ops = [
            fixture_operation(
                request_id="tracker-rl-4b1",
                request_kind=TRACKER_TRENDING_REQUEST,
                receipt_time=RECEIPT,
                response={
                    "fixture_status": "rate_limited",
                    "status_code": 429,
                    "failure_type": "rate_limited",
                },
            ),
            fixture_operation(
                request_id="tracker-top-empty-4b1",
                request_kind=TRACKER_TOP_REQUEST,
                receipt_time=RECEIPT,
                response={"body": [], "status_code": 200, "receipt_time": RECEIPT},
            ),
        ]
        limited = run_solana_tracker_fixture_lane(
            ops,
            evaluated_at=EVALUATED,
            auth=self.auth,
        )
        self.assertTrue(any(f.code == "BLOCKED_QUOTA" for f in limited.failures))
        self.assertEqual(limited.observations, ())

    def test_10_malformed_identity_unchanged(self) -> None:
        missing_quote = [
            {
                "token": {"mint": "MintBad11111111111111111111111111111111111"},
                "pools": [
                    {
                        "poolId": "PoolBad11111111111111111111111111111111111",
                        "tokenAddress": "MintBad11111111111111111111111111111111111",
                        "market": "pumpfun",
                        "lastUpdated": FRESH_MS,
                    }
                ],
            }
        ]
        with self.assertRaises(SecondaryDiscoveryError) as missing:
            normalize_tracker_list(
                missing_quote,
                channel="TRENDING_PUMPFUN",
                receipt_time=RECEIPT,
                evaluated_at=EVALUATED,
            )
        self.assertEqual(missing.exception.code, "AMBIGUOUS_IDENTITY")

        missing_mint = [{"token": {}, "pools": []}]
        with self.assertRaises(SecondaryDiscoveryError) as mint_exc:
            normalize_tracker_list(
                missing_mint,
                channel="TRENDING_PUMPFUN",
                receipt_time=RECEIPT,
                evaluated_at=EVALUATED,
            )
        self.assertEqual(mint_exc.exception.code, "AMBIGUOUS_IDENTITY")

    def test_11_rank_score_risk_promoted_order_stripped(self) -> None:
        body = [
            token_item(
                "MintStripB111111111111111111111111111111111",
                "PoolStripB111111111111111111111111111111111",
                last_updated_ms=FRESH_MS,
                rank=2,
                score=50,
                promoted=False,
                risk={"score": 1},
            ),
            token_item(
                "MintStripA111111111111111111111111111111111",
                "PoolStripA111111111111111111111111111111111",
                last_updated_ms=FRESH_MS,
                rank=1,
                score=999,
                promoted=True,
                risk={"score": 0, "rugged": True},
            ),
        ]
        # Provider order B then A; deterministic output must sort by mint/pool.
        rows = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(
            [row.mint for row in rows],
            [
                "MintStripA111111111111111111111111111111111",
                "MintStripB111111111111111111111111111111111",
            ],
        )
        for row in rows:
            identity = row.identity_dict()
            for field in ("rank", "score", "risk", "promoted", "holders", "response_order"):
                self.assertNotIn(field, identity)
        self.assertIn("rank", DISCARDED_NON_AUTHORITATIVE_FIELDS)
        self.assertIn("score", DISCARDED_NON_AUTHORITATIVE_FIELDS)

    def test_12_deterministic_identical_fixtures(self) -> None:
        body = [
            token_item(
                "MintDetB11111111111111111111111111111111111",
                "PoolDetB11111111111111111111111111111111111",
                last_updated_ms=STALE_MS,
            ),
            token_item(
                "MintDetA11111111111111111111111111111111111",
                "PoolDetA11111111111111111111111111111111111",
                last_updated_ms=FRESH_MS,
                rank=99,
            ),
            token_item(
                "MintDetC11111111111111111111111111111111111",
                "PoolDetC11111111111111111111111111111111111",
                last_updated_ms=FUTURE_MS,
            ),
        ]
        first = normalize_tracker_list(
            deepcopy(body),
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        second = normalize_tracker_list(
            deepcopy(body),
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(
            [row.identity_dict() for row in first],
            [row.identity_dict() for row in second],
        )
        self.assertEqual(len(first), 1)

    def test_13_pagination_and_observation_ceilings(self) -> None:
        self.assertEqual(TRACKER_STALE_AFTER_SECONDS, 180)
        over = [
            token_item(
                f"MintPage{i:03d}11111111111111111111111111111",
                f"PoolPage{i:03d}11111111111111111111111111111",
                last_updated_ms=FRESH_MS,
            )
            for i in range(101)
        ]
        with self.assertRaises(SecondaryDiscoveryError) as exc:
            normalize_tracker_list(
                over,
                channel="TRENDING_PUMPFUN",
                receipt_time=RECEIPT,
                evaluated_at=EVALUATED,
            )
        self.assertEqual(exc.exception.code, "SCHEMA_OR_LIMIT_DRIFT")

        # 100-row ceiling is still admitted; mixed stale does not inflate count.
        body_100 = [
            token_item(
                f"MintOk{i:03d}1111111111111111111111111111111",
                f"PoolOk{i:03d}1111111111111111111111111111111",
                last_updated_ms=FRESH_MS if i % 2 == 0 else STALE_MS,
            )
            for i in range(100)
        ]
        rows = normalize_tracker_list(
            body_100,
            channel="TRENDING_PUMPFUN",
            receipt_time=RECEIPT,
            evaluated_at=EVALUATED,
        )
        self.assertEqual(len(rows), 50)

    def test_14_geckoterminal_behavior_unchanged(self) -> None:
        gecko = self.fixture["geckoterminal"]
        rows = normalize_gecko_trending(
            gecko["trending"]["body"],
            receipt_time=gecko["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
            params=dict(GECKO_TRENDING_PARAMS),
        )
        self.assertGreaterEqual(len(rows), 1)
        # Gecko still fails whole-body on stale receipt (unchanged).
        with self.assertRaises(SecondaryDiscoveryError) as stale:
            normalize_gecko_trending(
                gecko["trending"]["body"],
                receipt_time="2026-07-19T11:50:00Z",
                evaluated_at=self.evaluated,
                params=dict(GECKO_TRENDING_PARAMS),
            )
        self.assertEqual(stale.exception.code, "STALE_OR_UNKNOWN")

    def test_15_source_governor_and_scheduler_ownership(self) -> None:
        for kind in (TRACKER_TRENDING_REQUEST, TRACKER_TOP_REQUEST):
            decision = can_request_source(TRACKER_SOURCE_NAME, kind, 0)
            self.assertTrue(decision.allowed, msg=f"{kind}: {decision.reason}")
        self.assertEqual(TRACKER_WORK_TYPE, "DISCOVERY_SOLANA_TRACKER_TRENDING_TOP")
        self.assertEqual(SCHEDULER_JOB_KIND, "DISCOVERY_REFRESH")
        # Fixture lane still uses one work type and no retries/rotation.
        ops = [
            fixture_operation(
                request_id="own-trend",
                request_kind=TRACKER_TRENDING_REQUEST,
                receipt_time=RECEIPT,
                response={
                    "body": [
                        token_item(
                            "MintOwn11111111111111111111111111111111111",
                            "PoolOwn11111111111111111111111111111111111",
                            last_updated_ms=FRESH_MS,
                        ),
                        token_item(
                            "MintOwnStale11111111111111111111111111111",
                            "PoolOwnStale11111111111111111111111111111",
                            last_updated_ms=STALE_MS,
                        ),
                    ],
                    "status_code": 200,
                    "receipt_time": RECEIPT,
                },
            ),
            fixture_operation(
                request_id="own-top",
                request_kind=TRACKER_TOP_REQUEST,
                receipt_time=RECEIPT,
                response={
                    "body": [
                        token_item(
                            "MintOwnTop1111111111111111111111111111111",
                            "PoolOwnTop1111111111111111111111111111111",
                            last_updated_ms=FUTURE_MS,
                        )
                    ],
                    "status_code": 200,
                    "receipt_time": RECEIPT,
                },
            ),
        ]
        result = run_solana_tracker_fixture_lane(
            ops, evaluated_at=EVALUATED, auth=self.auth
        )
        self.assertEqual(result.provider, TRACKER_SOURCE_NAME)
        self.assertEqual(result.work_type, TRACKER_WORK_TYPE)
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(
            result.observations[0].mint, "MintOwn11111111111111111111111111111111111"
        )
        self.assertEqual(result.failures, ())
        # Stale/future alone do not create response-level failures.
        self.assertEqual(result.status, "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
