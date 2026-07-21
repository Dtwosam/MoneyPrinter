"""Focused synthetic proof for V2-9.7D.7B.4B secondary discovery adapters."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from printer_v1.sources.governor import can_request_source
from printer_v1.sources.registry import SOURCE_REGISTRY
from printer_v1.sources.secondary_discovery import (
    DISCARDED_NON_AUTHORITATIVE_FIELDS,
    GECKO_ACTIVE_REQUEST,
    GECKO_SOURCE_NAME,
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
    GECKO_WORK_TYPE,
    PUMPFUN_ORIGIN_STATUS,
    SCHEDULER_JOB_KIND,
    SecondaryDiscoveryError,
    SolanaTrackerAuthConfig,
    TRACKER_SOURCE_NAME,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    TRACKER_WORK_TYPE,
    fixture_operation,
    normalize_gecko_active,
    normalize_gecko_trending,
    normalize_tracker_list,
    run_combined_secondary_fixture,
    run_geckoterminal_fixture_lane,
    run_solana_tracker_fixture_lane,
)


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "secondary_discovery_adapters.json"
)


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def tracker_auth(fixture: dict | None = None) -> SolanaTrackerAuthConfig:
    data = (fixture or load_fixture())["solana_tracker"]
    return SolanaTrackerAuthConfig(
        api_key_secret_ref=data["api_key_secret_ref"],
        free_requests_remaining_month=data["free_requests_remaining_month"],
        free_requests_per_second=data["free_requests_per_second"],
        free_requests_per_month=data["free_requests_per_month"],
    )


def gecko_ops(fixture: dict, *, include_active: bool = True):
    gecko = fixture["geckoterminal"]
    ops = [
        fixture_operation(
            request_id="gecko-trending-1",
            request_kind=GECKO_TRENDING_REQUEST,
            receipt_time=gecko["trending"]["receipt_time"],
            response={
                "body": gecko["trending"]["body"],
                "params": gecko["trending"]["params"],
                "receipt_time": gecko["trending"]["receipt_time"],
                "status_code": 200,
            },
        )
    ]
    if include_active:
        ops.append(
            fixture_operation(
                request_id="gecko-active-1",
                request_kind=GECKO_ACTIVE_REQUEST,
                receipt_time=gecko["active"]["receipt_time"],
                response={
                    "body": gecko["active"]["body"],
                    "receipt_time": gecko["active"]["receipt_time"],
                    "status_code": 200,
                },
            )
        )
    return ops


def tracker_ops(fixture: dict):
    tracker = fixture["solana_tracker"]
    return [
        fixture_operation(
            request_id="tracker-trending-1",
            request_kind=TRACKER_TRENDING_REQUEST,
            receipt_time=tracker["trending"]["receipt_time"],
            response={
                "body": tracker["trending"]["body"],
                "receipt_time": tracker["trending"]["receipt_time"],
                "status_code": 200,
            },
        ),
        fixture_operation(
            request_id="tracker-top-1",
            request_kind=TRACKER_TOP_REQUEST,
            receipt_time=tracker["top"]["receipt_time"],
            response={
                "body": tracker["top"]["body"],
                "receipt_time": tracker["top"]["receipt_time"],
                "status_code": 200,
            },
        ),
    ]


class RegistryAndOwnershipTests(unittest.TestCase):
    def test_governor_admits_adopted_secondary_request_kinds(self) -> None:
        gecko = SOURCE_REGISTRY["geckoterminal"]
        self.assertIn(GECKO_TRENDING_REQUEST, gecko.allowed_request_kinds)
        self.assertIn(GECKO_ACTIVE_REQUEST, gecko.allowed_request_kinds)
        tracker = SOURCE_REGISTRY["solana_tracker"]
        self.assertEqual(
            tracker.allowed_request_kinds,
            (TRACKER_TRENDING_REQUEST, TRACKER_TOP_REQUEST),
        )
        self.assertFalse(tracker.requires_paid_plan)
        self.assertEqual(tracker.stale_after_seconds, 180)
        self.assertEqual(tracker.max_retries, 0)
        for kind in (
            GECKO_TRENDING_REQUEST,
            GECKO_ACTIVE_REQUEST,
            TRACKER_TRENDING_REQUEST,
            TRACKER_TOP_REQUEST,
        ):
            source = (
                GECKO_SOURCE_NAME
                if kind.startswith("geckoterminal")
                else TRACKER_SOURCE_NAME
            )
            decision = can_request_source(source, kind, 0)
            self.assertTrue(decision.allowed, kind)

    def test_source_governor_bypass_rejected(self) -> None:
        fixture = load_fixture()
        bad = fixture_operation(
            request_id="bypass",
            request_kind=GECKO_TRENDING_REQUEST,
            response={"body": {"data": []}, "status_code": 200},
            receipt_time=fixture["geckoterminal"]["trending"]["receipt_time"],
            source_name="dexscreener",
        )
        result = run_geckoterminal_fixture_lane(
            [bad],
            evaluated_at=fixture["evaluated_at"],
        )
        self.assertEqual(result.status, "FAILED")
        self.assertTrue(
            any(failure.code == "SOURCE_GOVERNOR_BYPASS" for failure in result.failures)
        )
        self.assertEqual(result.accounting.transport_operations, 0)
        unknown = can_request_source("solana_tracker", "not_a_real_kind", 0)
        self.assertFalse(unknown.allowed)

    def test_central_scheduler_bypass_rejected(self) -> None:
        fixture = load_fixture()
        bad = fixture_operation(
            request_id="sched-bypass",
            request_kind=TRACKER_TRENDING_REQUEST,
            response={"body": [], "status_code": 200},
            receipt_time=fixture["solana_tracker"]["trending"]["receipt_time"],
            scheduler_work_type="NOT_A_REAL_WORK_TYPE",
        )
        result = run_solana_tracker_fixture_lane(
            [bad],
            evaluated_at=fixture["evaluated_at"],
            auth=tracker_auth(fixture),
        )
        self.assertEqual(result.status, "FAILED")
        self.assertTrue(
            any(failure.code == "CENTRAL_SCHEDULER_BYPASS" for failure in result.failures)
        )
        self.assertEqual(result.accounting.transport_operations, 0)


class GeckoTerminalAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.evaluated = self.fixture["evaluated_at"]
        self.gecko = self.fixture["geckoterminal"]

    def test_valid_trending_and_active_identity_normalization(self) -> None:
        trending = normalize_gecko_trending(
            self.gecko["trending"]["body"],
            receipt_time=self.gecko["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
            params=self.gecko["trending"]["params"],
        )
        mints = [row.mint for row in trending]
        self.assertEqual(
            mints,
            [
                "MintA1111111111111111111111111111111111111",
                "MintB1111111111111111111111111111111111111",
            ],
        )
        # Duplicate exact pool collapses; provenance retained without authority multiply.
        self.assertEqual(len(trending), 2)
        by_mint = {row.mint: row for row in trending}
        self.assertEqual(by_mint["MintB1111111111111111111111111111111111111"].provenance_count, 2)
        for row in trending:
            self.assertEqual(row.network, "solana")
            self.assertEqual(row.channel, "TRENDING_PUMPFUN")
            self.assertEqual(row.pumpfun_origin_status, PUMPFUN_ORIGIN_STATUS)
            self.assertEqual(
                row.quote_mint, "So11111111111111111111111111111111111111112"
            )
            self.assertEqual(row.venue, "pump-fun")
            self.assertNotIn("rank", row.identity_dict())
            self.assertNotIn("gt_score", row.identity_dict())

        active = normalize_gecko_active(
            self.gecko["active"]["body"],
            receipt_time=self.gecko["active"]["receipt_time"],
            evaluated_at=self.evaluated,
            requested_pool=self.gecko["active"]["requested_pool"],
        )
        self.assertEqual(active.mint, "MintA1111111111111111111111111111111111111")
        self.assertEqual(active.activity_interval, "m5")
        self.assertEqual(active.activity_count, 3)
        self.assertEqual(active.channel, "ACTIVE_PUMPFUN")
        self.assertEqual(active.pumpfun_origin_status, PUMPFUN_ORIGIN_STATUS)
        self.assertNotIn("price_change_percentage", active.identity_dict())

    def test_rank_score_order_stripping_invariance(self) -> None:
        body = deepcopy(self.gecko["trending"]["body"])
        baseline = normalize_gecko_trending(
            body,
            receipt_time=self.gecko["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
            params=dict(GECKO_TRENDING_PARAMS),
        )
        body["data"].reverse()
        for item in body["data"]:
            item["attributes"]["gt_score"] = -1
            item["attributes"]["rank"] = 999999
        mutated = normalize_gecko_trending(
            body,
            receipt_time=self.gecko["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
            params=dict(GECKO_TRENDING_PARAMS),
        )
        self.assertEqual(
            [row.identity_dict() for row in mutated],
            [row.identity_dict() for row in baseline],
        )

    def test_malformed_stale_ambiguous_zero_active_and_ceilings(self) -> None:
        with self.assertRaises(SecondaryDiscoveryError) as zero:
            normalize_gecko_active(
                {
                    "data": {
                        **self.gecko["active"]["body"]["data"],
                        "attributes": {
                            **self.gecko["active"]["body"]["data"]["attributes"],
                            "transactions": {"m5": {"buys": 0, "sells": 0}},
                        },
                    }
                },
                receipt_time=self.gecko["active"]["receipt_time"],
                evaluated_at=self.evaluated,
                requested_pool=self.gecko["active"]["requested_pool"],
            )
        self.assertEqual(zero.exception.code, "NOT_ACTIVE")

        with self.assertRaises(SecondaryDiscoveryError) as stale:
            normalize_gecko_trending(
                self.gecko["trending"]["body"],
                receipt_time="2026-07-19T11:50:00Z",
                evaluated_at=self.evaluated,
                params=dict(GECKO_TRENDING_PARAMS),
            )
        self.assertEqual(stale.exception.code, "STALE_OR_UNKNOWN")

        ambiguous = deepcopy(self.gecko["active"]["body"])
        ambiguous["data"]["id"] = "solana_WrongPool"
        with self.assertRaises(SecondaryDiscoveryError) as amb:
            normalize_gecko_active(
                ambiguous,
                receipt_time=self.gecko["active"]["receipt_time"],
                evaluated_at=self.evaluated,
                requested_pool=self.gecko["active"]["requested_pool"],
            )
        self.assertEqual(amb.exception.code, "AMBIGUOUS_IDENTITY")

        over = deepcopy(self.gecko["trending"]["body"])
        over["data"] = over["data"][:1] * 21
        with self.assertRaises(SecondaryDiscoveryError) as ceiling:
            normalize_gecko_trending(
                over,
                receipt_time=self.gecko["trending"]["receipt_time"],
                evaluated_at=self.evaluated,
                params=dict(GECKO_TRENDING_PARAMS),
            )
        self.assertEqual(ceiling.exception.code, "SCHEMA_OR_LIMIT_DRIFT")

        malformed = {"not": "data"}
        with self.assertRaises(SecondaryDiscoveryError) as mal:
            normalize_gecko_trending(
                malformed,
                receipt_time=self.gecko["trending"]["receipt_time"],
                evaluated_at=self.evaluated,
                params=dict(GECKO_TRENDING_PARAMS),
            )
        self.assertEqual(mal.exception.code, "MALFORMED_RESPONSE")

    def test_rate_limit_handling_and_lane_success(self) -> None:
        ops = [
            fixture_operation(
                request_id="gecko-rl",
                request_kind=GECKO_TRENDING_REQUEST,
                receipt_time=self.gecko["trending"]["receipt_time"],
                response={
                    "fixture_status": "rate_limited",
                    "status_code": 429,
                    "failure_type": "rate_limited",
                },
            )
        ]
        result = run_geckoterminal_fixture_lane(ops, evaluated_at=self.evaluated)
        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.failures[0].code, "BLOCKED_QUOTA")
        self.assertEqual(result.work_type, GECKO_WORK_TYPE)
        self.assertEqual(result.accounting.governed_requests[GECKO_TRENDING_REQUEST], 1)

        success = run_geckoterminal_fixture_lane(
            gecko_ops(self.fixture),
            evaluated_at=self.evaluated,
            requested_active_pool=self.gecko["active"]["requested_pool"],
        )
        self.assertEqual(success.status, "SUCCEEDED")
        self.assertEqual(len(success.observations), 3)  # 2 unique trending + 1 active
        self.assertEqual(
            success.accounting.governed_requests,
            {GECKO_TRENDING_REQUEST: 1, GECKO_ACTIVE_REQUEST: 1},
        )
        self.assertEqual(success.accounting.transport_operations, 2)


class SolanaTrackerAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.evaluated = self.fixture["evaluated_at"]
        self.tracker = self.fixture["solana_tracker"]
        self.auth = tracker_auth(self.fixture)

    def test_valid_trending_top_and_auth_quota(self) -> None:
        trending = normalize_tracker_list(
            self.tracker["trending"]["body"],
            channel="TRENDING_PUMPFUN",
            receipt_time=self.tracker["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
        )
        top = normalize_tracker_list(
            self.tracker["top"]["body"],
            channel="TOP_PUMPFUN",
            receipt_time=self.tracker["top"]["receipt_time"],
            evaluated_at=self.evaluated,
        )
        self.assertEqual(len(trending), 1)
        self.assertEqual(trending[0].mint, "MintB1111111111111111111111111111111111111")
        self.assertEqual(trending[0].pool, "PoolB1111111111111111111111111111111111111")
        self.assertEqual(trending[0].venue, "pumpfun")
        self.assertEqual(trending[0].provenance_count, 2)
        self.assertEqual(trending[0].pumpfun_origin_status, PUMPFUN_ORIGIN_STATUS)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].mint, "MintA1111111111111111111111111111111111111")
        self.assertEqual(top[0].channel, "TOP_PUMPFUN")
        # raydium and mint/pool mismatch rows contribute nothing.
        self.assertTrue(all(row.venue == "pumpfun" for row in (*trending, *top)))
        self.auth.validate()
        blocked = SolanaTrackerAuthConfig(
            api_key_secret_ref="",
            free_requests_remaining_month=100,
        )
        with self.assertRaises(SecondaryDiscoveryError) as auth_err:
            blocked.validate()
        self.assertEqual(auth_err.exception.code, "BLOCKED_AUTH")
        quota = SolanaTrackerAuthConfig(
            api_key_secret_ref="SOLANA_TRACKER_API_KEY_REF",
            free_requests_remaining_month=1,
        )
        with self.assertRaises(SecondaryDiscoveryError) as quota_err:
            quota.validate()
        self.assertEqual(quota_err.exception.code, "BLOCKED_QUOTA")

    def test_rank_score_risk_promoted_order_stripping(self) -> None:
        body = deepcopy(self.tracker["trending"]["body"])
        baseline = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=self.tracker["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
        )
        body.reverse()
        for item in body:
            item["rank"] = 999999
            item["score"] = -999999
            item["promoted"] = False
            item["risk"] = {"score": 100, "rugged": True, "insiders": {"count": 999}}
            item["holders"] = 0
            if item.get("pools"):
                item["pools"][0]["score"] = -1
        mutated = normalize_tracker_list(
            body,
            channel="TRENDING_PUMPFUN",
            receipt_time=self.tracker["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
        )
        self.assertEqual(
            [row.identity_dict() for row in mutated],
            [row.identity_dict() for row in baseline],
        )
        for row in mutated:
            identity = row.identity_dict()
            for field in ("rank", "score", "risk", "promoted", "holders"):
                self.assertNotIn(field, identity)

    def test_malformed_stale_ambiguous_rate_limit_and_ceilings(self) -> None:
        # V2-9.7D.7B.4B.1: single-pool stale is row-level skip; the duplicate
        # fresh pumpfun row in the fixture still contributes.
        stale_body = deepcopy(self.tracker["trending"]["body"])
        stale_body[0]["pools"][0]["lastUpdated"] -= 181_000
        stale_rows = normalize_tracker_list(
            stale_body,
            channel="TRENDING_PUMPFUN",
            receipt_time=self.tracker["trending"]["receipt_time"],
            evaluated_at=self.evaluated,
        )
        self.assertEqual(len(stale_rows), 1)
        self.assertEqual(
            stale_rows[0].mint, "MintB1111111111111111111111111111111111111"
        )
        self.assertEqual(stale_rows[0].provenance_count, 1)

        all_stale = deepcopy(self.tracker["trending"]["body"])
        for item in all_stale:
            for pool in item.get("pools") or []:
                if isinstance(pool, dict) and pool.get("market") == "pumpfun":
                    pool["lastUpdated"] -= 181_000
        self.assertEqual(
            normalize_tracker_list(
                all_stale,
                channel="TRENDING_PUMPFUN",
                receipt_time=self.tracker["trending"]["receipt_time"],
                evaluated_at=self.evaluated,
            ),
            (),
        )

        malformed = deepcopy(self.tracker["top"]["body"])
        malformed[0]["pools"][0].pop("quoteToken")
        with self.assertRaises(SecondaryDiscoveryError) as mal:
            normalize_tracker_list(
                malformed,
                channel="TOP_PUMPFUN",
                receipt_time=self.tracker["top"]["receipt_time"],
                evaluated_at=self.evaluated,
            )
        self.assertEqual(mal.exception.code, "AMBIGUOUS_IDENTITY")

        drift = deepcopy(self.tracker["trending"]["body"])
        drift = drift * 51
        with self.assertRaises(SecondaryDiscoveryError) as ceiling:
            normalize_tracker_list(
                drift,
                channel="TRENDING_PUMPFUN",
                receipt_time=self.tracker["trending"]["receipt_time"],
                evaluated_at=self.evaluated,
            )
        self.assertEqual(ceiling.exception.code, "SCHEMA_OR_LIMIT_DRIFT")

        not_array = {"tokens": []}
        with self.assertRaises(SecondaryDiscoveryError) as shape:
            normalize_tracker_list(
                not_array,
                channel="TRENDING_PUMPFUN",
                receipt_time=self.tracker["trending"]["receipt_time"],
                evaluated_at=self.evaluated,
            )
        self.assertEqual(shape.exception.code, "MALFORMED_RESPONSE")

        ops = [
            fixture_operation(
                request_id="tracker-rl",
                request_kind=TRACKER_TRENDING_REQUEST,
                receipt_time=self.tracker["trending"]["receipt_time"],
                response={
                    "fixture_status": "rate_limited",
                    "status_code": 429,
                    "failure_type": "rate_limited",
                },
            ),
            fixture_operation(
                request_id="tracker-top-ok",
                request_kind=TRACKER_TOP_REQUEST,
                receipt_time=self.tracker["top"]["receipt_time"],
                response={
                    "body": self.tracker["top"]["body"],
                    "receipt_time": self.tracker["top"]["receipt_time"],
                    "status_code": 200,
                },
            ),
        ]
        partial = run_solana_tracker_fixture_lane(
            ops, evaluated_at=self.evaluated, auth=self.auth
        )
        self.assertEqual(partial.status, "PARTIAL")
        self.assertTrue(any(f.code == "BLOCKED_QUOTA" for f in partial.failures))
        self.assertEqual(len(partial.observations), 1)
        self.assertEqual(partial.observations[0].channel, "TOP_PUMPFUN")


class IsolationReplayAndBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture()
        self.evaluated = self.fixture["evaluated_at"]
        self.auth = tracker_auth(self.fixture)

    def test_independent_provider_failure_isolation(self) -> None:
        gecko_fail = [
            fixture_operation(
                request_id="gecko-fail",
                request_kind=GECKO_TRENDING_REQUEST,
                receipt_time=self.fixture["geckoterminal"]["trending"]["receipt_time"],
                response={
                    "fixture_status": "error",
                    "status_code": 500,
                    "failure_type": "provider_error",
                },
            )
        ]
        combined = run_combined_secondary_fixture(
            gecko_operations=gecko_fail,
            tracker_operations=tracker_ops(self.fixture),
            evaluated_at=self.evaluated,
            auth=self.auth,
            requested_active_pool=None,
        )
        self.assertEqual(combined.geckoterminal.status, "FAILED")
        self.assertEqual(combined.solana_tracker.status, "SUCCEEDED")
        self.assertGreater(len(combined.solana_tracker.observations), 0)
        self.assertEqual(len(combined.geckoterminal.observations), 0)
        self.assertTrue(
            all(
                obs.pumpfun_origin_status == PUMPFUN_ORIGIN_STATUS
                for obs in combined.solana_tracker.observations
            )
        )

    def test_deterministic_replay(self) -> None:
        first = run_combined_secondary_fixture(
            gecko_operations=gecko_ops(self.fixture),
            tracker_operations=tracker_ops(self.fixture),
            evaluated_at=self.evaluated,
            auth=self.auth,
            requested_active_pool=self.fixture["geckoterminal"]["active"]["requested_pool"],
        )
        second = run_combined_secondary_fixture(
            gecko_operations=gecko_ops(self.fixture),
            tracker_operations=tracker_ops(self.fixture),
            evaluated_at=self.evaluated,
            auth=self.auth,
            requested_active_pool=self.fixture["geckoterminal"]["active"]["requested_pool"],
        )
        self.assertEqual(first.canonical(), second.canonical())
        # Duplicate observations never multiply unique authority keys.
        self.assertEqual(
            len(first.geckoterminal.unique_authority_keys),
            len({obs.authority_key() for obs in first.geckoterminal.observations}),
        )
        self.assertEqual(
            len(first.solana_tracker.unique_authority_keys),
            len({obs.authority_key() for obs in first.solana_tracker.observations}),
        )
        self.assertIn("rank", DISCARDED_NON_AUTHORITATIVE_FIELDS)
        self.assertIn("promoted", DISCARDED_NON_AUTHORITATIVE_FIELDS)
        self.assertEqual(SCHEDULER_JOB_KIND, "DISCOVERY_REFRESH")
        self.assertEqual(GECKO_WORK_TYPE, "DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE")
        self.assertEqual(TRACKER_WORK_TYPE, "DISCOVERY_SOLANA_TRACKER_TRENDING_TOP")

    def test_no_network_or_secret_material_in_module_surface(self) -> None:
        import printer_v1.sources.secondary_discovery as module

        source = Path(module.__file__).read_text(encoding="utf-8")
        for banned in (
            "urlopen",
            "import requests",
            "from urllib",
            "http.client",
            "websocket",
            "socket.create_connection",
            "private_key",
            "api_key=",
        ):
            self.assertNotIn(banned, source)
        # Fixture auth uses a secret reference only.
        self.assertEqual(
            self.fixture["solana_tracker"]["api_key_secret_ref"],
            "SOLANA_TRACKER_API_KEY_REF",
        )
        self.assertNotIn("sk-", json.dumps(self.fixture))


if __name__ == "__main__":
    unittest.main()
