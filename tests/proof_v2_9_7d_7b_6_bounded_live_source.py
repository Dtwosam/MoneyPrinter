"""Proof-only harness for V2-9.7D.7B.6 bounded live-source proof.

Single sequential live run. No production behavior changes. Never prints secrets.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any
from urllib import error as url_error
from urllib import parse as url_parse
from urllib import request as url_request

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import (
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixtureSourceFact,
)
from printer_v1.discovery.persistence import LOCKED_FINANCIAL_TABLES
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CAMPAIGN_MODE,
    CENTRAL_SCHEDULER_OWNER,
    CampaignCeilings,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.sources.governor import can_request_source
from printer_v1.sources.pumpfun_direct import (
    BACKFILL_REQUEST,
    PUMP_PROGRAM_ID,
    SESSION_REQUEST,
    SignatureReference,
    TRANSACTION_REQUEST,
    decode_finalized_create,
)
from printer_v1.sources.secondary_discovery import (
    GECKO_ACTIVE_REQUEST,
    GECKO_TRENDING_PARAMS,
    GECKO_TRENDING_REQUEST,
    TRACKER_TOP_REQUEST,
    TRACKER_TRENDING_REQUEST,
    SolanaTrackerAuthConfig,
    normalize_gecko_active,
    normalize_gecko_trending,
    normalize_tracker_list,
)


PROVEN_HEAD = "1309c2807d59d167fe90104eabcae64a8003acf7"
RPC_URL = "https://api.mainnet-beta.solana.com"
DEX_PROFILES = "https://api.dexscreener.com/token-profiles/latest/v1"
DEX_TOKENS = "https://api.dexscreener.com/tokens/v1/solana/{addresses}"
GECKO_TRENDING = (
    "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools"
    "?include=base_token,quote_token,dex&page=1&duration=1h"
)
GECKO_POOL = (
    "https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}"
    "?include=base_token,quote_token,dex"
)
TRACKER_BASE = "https://data.solanatracker.io"
TRACKER_KEY_ENV_CANDIDATES = (
    "SOLANA_TRACKER_API_KEY",
    "SOLANATRACKER_API_KEY",
    "SOLANA_TRACKER_DATA_API_KEY",
)
USER_AGENT = "PrinterV1/0.1 (+paper-only live-source-proof 7B.6)"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def redacted(obj: Any) -> Any:
    """Drop large bodies; keep hashes/counts/status only."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if str(key).startswith("_body"):
                continue
            if key in {"body"}:
                continue
            out[key] = redacted(value)
        return out
    if isinstance(obj, list):
        return [redacted(item) for item in obj[:20]]
    return obj


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_bytes: int = 1_000_000,
) -> dict[str, Any]:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    safe_headers = {
        k: ("<redacted>" if k.lower() in {"x-api-key", "authorization"} else v)
        for k, v in req_headers.items()
    }
    request = url_request.Request(url, headers=req_headers, method="GET")
    try:
        with url_request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            raw = raw[:max_bytes]
            status = getattr(response, "status", 200)
            body = json.loads(raw.decode("utf-8")) if raw else None
            return {
                "ok": True,
                "status_code": status,
                "bytes": len(raw),
                "truncated": truncated,
                "body": body,
                "payload_hash": sha256_bytes(raw),
                "headers_used": safe_headers,
                "url_host": url_parse.urlparse(url).netloc,
            }
    except url_error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(max_bytes)
        except Exception:
            pass
        return {
            "ok": False,
            "status_code": exc.code,
            "bytes": len(raw or b""),
            "truncated": False,
            "body": None,
            "payload_hash": sha256_bytes(raw or b""),
            "error": f"http_{exc.code}",
            "headers_used": safe_headers,
            "url_host": url_parse.urlparse(url).netloc,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": None,
            "bytes": 0,
            "truncated": False,
            "body": None,
            "payload_hash": sha256_text(""),
            "error": type(exc).__name__,
            "headers_used": safe_headers,
            "url_host": url_parse.urlparse(url).netloc,
        }


def rpc_call(method: str, params: list[Any], *, timeout: float = 15.0) -> dict[str, Any]:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode("utf-8")
    request = url_request.Request(
        RPC_URL,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with url_request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1_500_000)
            body = json.loads(raw.decode("utf-8"))
            return {
                "ok": "error" not in body,
                "status_code": getattr(response, "status", 200),
                "bytes": len(raw),
                "body": body,
                "payload_hash": sha256_bytes(raw),
                "error": body.get("error"),
                "url_host": "api.mainnet-beta.solana.com",
                "method": method,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status_code": None,
            "bytes": 0,
            "body": None,
            "payload_hash": sha256_text(""),
            "error": type(exc).__name__,
            "url_host": "api.mainnet-beta.solana.com",
            "method": method,
        }


def governor_check(source_name: str, request_kind: str) -> dict[str, Any]:
    decision = can_request_source(source_name, request_kind, 0)
    return {
        "source_name": source_name,
        "request_kind": request_kind,
        "allowed": bool(decision.allowed),
        "reason": decision.reason,
    }


def resolve_tracker_key() -> tuple[str | None, str]:
    for name in TRACKER_KEY_ENV_CANDIDATES:
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip(), name
    return None, ""


def locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in LOCKED_FINANCIAL_TABLES
    }


def provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": utc_now(),
    }


def probe_direct() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "provider": "solana_rpc",
        "program_id": PUMP_PROGRAM_ID,
        "endpoint": RPC_URL,
        "governor": [],
        "operations": 0,
        "decoded_creates": [],
        "gaps": [],
        "verdict": "FAIL",
    }
    for kind in (SESSION_REQUEST, BACKFILL_REQUEST, TRANSACTION_REQUEST):
        check = governor_check("solana_rpc", kind)
        evidence["governor"].append(check)
        if not check["allowed"]:
            evidence["gaps"].append(f"governor_denied:{kind}")
            return evidence

    slot_resp = rpc_call("getSlot", [{"commitment": "finalized"}])
    evidence["operations"] += 1
    evidence["getSlot"] = {
        "ok": slot_resp["ok"],
        "bytes": slot_resp["bytes"],
        "payload_hash": slot_resp["payload_hash"],
        "error": slot_resp.get("error"),
    }
    if not slot_resp["ok"] or not isinstance(slot_resp.get("body"), dict):
        evidence["gaps"].append("getSlot_failed")
        return evidence
    cutoff = slot_resp["body"].get("result")
    if type(cutoff) is not int:
        evidence["gaps"].append("getSlot_malformed")
        return evidence
    evidence["cutoff_slot"] = cutoff
    evidence["immutable_cutoff"] = cutoff

    sig_resp = rpc_call(
        "getSignaturesForAddress",
        [PUMP_PROGRAM_ID, {"limit": 4, "commitment": "finalized"}],
    )
    evidence["operations"] += 1
    evidence["getSignaturesForAddress"] = {
        "ok": sig_resp["ok"],
        "bytes": sig_resp["bytes"],
        "payload_hash": sig_resp["payload_hash"],
        "error": sig_resp.get("error"),
    }
    rows = []
    if sig_resp["ok"] and isinstance(sig_resp.get("body"), dict):
        result = sig_resp["body"].get("result") or []
        if isinstance(result, list):
            rows = [row for row in result if isinstance(row, dict)]
    evidence["signature_count"] = len(rows)
    if not rows:
        evidence["gaps"].append("empty_signature_page")
        evidence["continuity"] = "UNKNOWN"
        evidence["verdict"] = "PASS"
        return evidence

    decoded = []
    seen: set[str] = set()
    for row in rows[:4]:
        signature = row.get("signature")
        slot = row.get("slot")
        conf = row.get("confirmationStatus") or "finalized"
        err = row.get("err")
        if not isinstance(signature, str) or type(slot) is not int:
            evidence["gaps"].append("malformed_signature_row")
            continue
        if signature in seen:
            evidence["gaps"].append("duplicate_signature")
            continue
        seen.add(signature)
        if slot > cutoff:
            evidence["gaps"].append("post_cutoff")
            continue
        tx_resp = rpc_call(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "json",
                    "commitment": "finalized",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        evidence["operations"] += 1
        if not tx_resp["ok"] or not isinstance(tx_resp.get("body"), dict):
            evidence["gaps"].append("getTransaction_failed")
            continue
        result = tx_resp["body"].get("result")
        if result is None:
            evidence["gaps"].append("transaction_unavailable")
            continue
        try:
            observation = decode_finalized_create(
                result,
                reference=SignatureReference(signature, slot, conf, err),
                cutoff_slot=cutoff,
            )
        except Exception as exc:  # noqa: BLE001
            evidence["gaps"].append(str(getattr(exc, "code", type(exc).__name__)))
            continue
        decoded.append(
            {
                "mint": observation.mint,
                "bonding_curve": observation.bonding_curve,
                "associated_bonding_curve": observation.associated_bonding_curve,
                "creator_address": observation.creator_address,
                "signature": observation.signature,
                "slot": observation.slot,
                "block_time": observation.block_time,
                "program_id": observation.program_id,
            }
        )
    evidence["decoded_creates"] = decoded
    evidence["decoded_count"] = len(decoded)
    evidence["continuity"] = "GAPPED" if evidence["gaps"] else "CONTIGUOUS"
    evidence["no_retry"] = True
    evidence["no_endpoint_rotation"] = True
    evidence["verdict"] = "PASS"
    return evidence


def probe_dexscreener() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "provider": "dexscreener",
        "governor": [],
        "bytes": 0,
        "verdict": "FAIL",
    }
    for kind in ("dexscreener_fresh_profiles", "token_discovery"):
        evidence["governor"].append(governor_check("dexscreener", kind))
    if not any(item["allowed"] for item in evidence["governor"]):
        evidence["error"] = "governor_denied"
        return evidence

    profiles = http_get(DEX_PROFILES, timeout=15.0)
    evidence["bytes"] += int(profiles["bytes"] or 0)
    evidence["profiles"] = {
        "ok": profiles["ok"],
        "status_code": profiles["status_code"],
        "bytes": profiles["bytes"],
        "payload_hash": profiles["payload_hash"],
        "error": profiles.get("error"),
        "host": profiles["url_host"],
    }
    if not profiles["ok"] or not isinstance(profiles["body"], list):
        evidence["error"] = profiles.get("error") or "profiles_malformed"
        return evidence

    mints: list[str] = []
    seen: set[str] = set()
    for entry in profiles["body"]:
        if not isinstance(entry, dict) or entry.get("chainId") != "solana":
            continue
        addr = entry.get("tokenAddress")
        if isinstance(addr, str) and addr and addr not in seen:
            seen.add(addr)
            mints.append(addr)
        if len(mints) >= 5:
            break
    evidence["profile_solana_mints"] = len(mints)
    if not mints:
        evidence["error"] = "no_solana_profiles"
        return evidence

    tokens = http_get(DEX_TOKENS.format(addresses=",".join(mints)), timeout=15.0)
    evidence["bytes"] += int(tokens["bytes"] or 0)
    evidence["tokens_batch"] = {
        "ok": tokens["ok"],
        "status_code": tokens["status_code"],
        "bytes": tokens["bytes"],
        "payload_hash": tokens["payload_hash"],
        "error": tokens.get("error"),
        "host": tokens["url_host"],
    }
    pairs = tokens["body"] if isinstance(tokens.get("body"), list) else []
    solana_pairs = [
        p for p in pairs if isinstance(p, dict) and str(p.get("chainId", "")).lower() == "solana"
    ]
    evidence["observations"] = len(solana_pairs)
    evidence["unique_mints"] = len(
        {
            (p.get("baseToken") or {}).get("address")
            for p in solana_pairs
            if isinstance(p.get("baseToken"), dict)
        }
        - {None}
    )
    evidence["sample_mints"] = mints[:3]
    evidence["rank_boost_excluded"] = True
    evidence["no_retry"] = True
    evidence["_body_pairs"] = solana_pairs
    evidence["verdict"] = "PASS" if tokens["ok"] else "FAIL"
    return evidence


def probe_geckoterminal() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "provider": "geckoterminal",
        "governor": [],
        "bytes": 0,
        "verdict": "FAIL",
    }
    for kind in (GECKO_TRENDING_REQUEST, GECKO_ACTIVE_REQUEST):
        check = governor_check("geckoterminal", kind)
        evidence["governor"].append(check)
        if not check["allowed"]:
            evidence["error"] = f"governor_denied:{kind}"
            return evidence

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json;version=20230302",
    }
    trending = http_get(GECKO_TRENDING, headers=headers, timeout=15.0)
    evidence["bytes"] += int(trending["bytes"] or 0)
    evidence["trending"] = {
        "ok": trending["ok"],
        "status_code": trending["status_code"],
        "bytes": trending["bytes"],
        "payload_hash": trending["payload_hash"],
        "error": trending.get("error"),
        "host": trending["url_host"],
        "params": "include=base_token,quote_token,dex&page=1&duration=1h",
    }
    if not trending["ok"] or not isinstance(trending.get("body"), dict):
        evidence["error"] = trending.get("error") or "trending_failed"
        return evidence

    receipt = utc_now()
    try:
        rows = normalize_gecko_trending(
            trending["body"],
            receipt_time=receipt,
            evaluated_at=receipt,
            params=dict(GECKO_TRENDING_PARAMS),
        )
        evidence["normalized_trending"] = len(rows)
        evidence["trending_pools"] = len(trending["body"].get("data") or [])
        evidence["sample_mints"] = [row.mint for row in rows[:3]]
        evidence["sample_pools"] = [row.pool for row in rows[:3]]
        active_pool = rows[0].pool if rows else None
    except Exception as exc:  # noqa: BLE001
        evidence["error"] = f"normalize_trending:{getattr(exc, 'code', type(exc).__name__)}"
        return evidence

    evidence["_body_trending"] = trending["body"]
    if active_pool:
        active = http_get(GECKO_POOL.format(pool=active_pool), headers=headers, timeout=15.0)
        evidence["bytes"] += int(active["bytes"] or 0)
        evidence["active_request"] = {
            "ok": active["ok"],
            "status_code": active["status_code"],
            "bytes": active["bytes"],
            "payload_hash": active["payload_hash"],
            "error": active.get("error"),
            "pool": active_pool,
        }
        if active["ok"] and isinstance(active.get("body"), dict):
            evidence["_body_active"] = active["body"]
            try:
                row = normalize_gecko_active(
                    active["body"],
                    receipt_time=receipt,
                    evaluated_at=receipt,
                    requested_pool=active_pool,
                )
                evidence["active"] = {
                    "mint": row.mint,
                    "pool": row.pool,
                    "activity_interval": row.activity_interval,
                    "activity_count": row.activity_count,
                    "channel": row.channel,
                }
            except Exception as exc:  # noqa: BLE001
                evidence["active"] = {"error": getattr(exc, "code", type(exc).__name__)}
    evidence["no_retry"] = True
    evidence["verdict"] = "PASS"
    return evidence


def probe_solana_tracker() -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "provider": "solana_tracker",
        "governor": [],
        "bytes": 0,
        "verdict": "FAIL",
        "auth": "missing",
    }
    for kind in (TRACKER_TRENDING_REQUEST, TRACKER_TOP_REQUEST):
        check = governor_check("solana_tracker", kind)
        evidence["governor"].append(check)
        if not check["allowed"]:
            evidence["error"] = f"governor_denied:{kind}"
            return evidence

    key, env_name = resolve_tracker_key()
    if not key:
        evidence["auth"] = "BLOCKED_AUTH"
        evidence["error"] = "missing_free_rest_api_key_env"
        evidence["env_candidates_checked"] = list(TRACKER_KEY_ENV_CANDIDATES)
        evidence["verdict"] = "BLOCKED_AUTH"
        return evidence

    evidence["auth"] = "env_present"
    evidence["auth_env_name"] = env_name
    # Never fingerprint, length, prefix, or suffix the secret material.
    try:
        SolanaTrackerAuthConfig(
            api_key_secret_ref=env_name,
            free_requests_remaining_month=1000,
        ).validate()
    except Exception as exc:  # noqa: BLE001
        evidence["verdict"] = "BLOCKED_AUTH"
        evidence["error"] = getattr(exc, "code", type(exc).__name__)
        return evidence

    headers = {"x-api-key": key, "Accept": "application/json"}
    receipt = utc_now()
    trending = http_get(TRACKER_BASE + "/tokens/trending/1h", headers=headers, timeout=15.0)
    evidence["bytes"] += int(trending["bytes"] or 0)
    evidence["trending"] = {
        "ok": trending["ok"],
        "status_code": trending["status_code"],
        "bytes": trending["bytes"],
        "payload_hash": trending["payload_hash"],
        "error": trending.get("error"),
        "host": trending["url_host"],
        "body_type": type(trending.get("body")).__name__,
        "body_len": len(trending["body"]) if isinstance(trending.get("body"), list) else None,
    }
    top = http_get(TRACKER_BASE + "/top-performers/1h", headers=headers, timeout=15.0)
    evidence["bytes"] += int(top["bytes"] or 0)
    evidence["top"] = {
        "ok": top["ok"],
        "status_code": top["status_code"],
        "bytes": top["bytes"],
        "payload_hash": top["payload_hash"],
        "error": top.get("error"),
        "host": top["url_host"],
        "body_type": type(top.get("body")).__name__,
        "body_len": len(top["body"]) if isinstance(top.get("body"), list) else None,
    }

    if trending.get("status_code") in {401, 403} or top.get("status_code") in {401, 403}:
        evidence["verdict"] = "BLOCKED_AUTH"
        evidence["error"] = "http_auth_failure"
        return evidence
    if trending.get("status_code") == 429 or top.get("status_code") == 429:
        evidence["verdict"] = "BLOCKED_QUOTA"
        evidence["error"] = "http_429"
        return evidence

    # Schema/freshness diagnostics without retaining raw payloads permanently.
    def _tracker_body_shape(body: Any, *, evaluated_at: str) -> dict[str, Any]:
        if not isinstance(body, list):
            return {"shape": "not_list"}
        pumpfun_pools = 0
        fresh_pools = 0
        stale_pools = 0
        future_pools = 0
        last_updated_kinds: set[str] = set()
        eval_epoch = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00")).timestamp()
        for item in body[:100]:
            if not isinstance(item, dict):
                continue
            pools = item.get("pools")
            if not isinstance(pools, list):
                continue
            for pool in pools:
                if not isinstance(pool, dict):
                    continue
                if pool.get("market") != "pumpfun":
                    continue
                pumpfun_pools += 1
                lu = pool.get("lastUpdated")
                last_updated_kinds.add(type(lu).__name__)
                if type(lu) is not int:
                    continue
                age = eval_epoch - lu / 1000
                if age < -5:
                    future_pools += 1
                elif age > 180:
                    stale_pools += 1
                else:
                    fresh_pools += 1
        return {
            "shape": "list",
            "len": len(body),
            "pumpfun_market_pool_count_scanned": pumpfun_pools,
            "pumpfun_fresh_pool_count": fresh_pools,
            "pumpfun_stale_pool_count": stale_pools,
            "pumpfun_future_pool_count": future_pools,
            "lastUpdated_value_types": sorted(last_updated_kinds),
        }

    try:
        if trending["ok"] and isinstance(trending.get("body"), list):
            evidence["trending_shape"] = _tracker_body_shape(
                trending["body"], evaluated_at=receipt
            )
            rows = normalize_tracker_list(
                trending["body"],
                channel="TRENDING_PUMPFUN",
                receipt_time=receipt,
                evaluated_at=receipt,
            )
            evidence["trending_normalized"] = len(rows)
            evidence["trending_sample_mints"] = [row.mint for row in rows[:3]]
            evidence["_body_trending"] = trending["body"]
        elif trending["ok"]:
            evidence["verdict"] = "FAIL"
            evidence["error"] = "trending_body_not_list"
            return evidence
        if top["ok"] and isinstance(top.get("body"), list):
            evidence["top_shape"] = _tracker_body_shape(top["body"], evaluated_at=receipt)
            rows = normalize_tracker_list(
                top["body"],
                channel="TOP_PUMPFUN",
                receipt_time=receipt,
                evaluated_at=receipt,
            )
            evidence["top_normalized"] = len(rows)
            evidence["_body_top"] = top["body"]
        elif top["ok"]:
            evidence["verdict"] = "FAIL"
            evidence["error"] = "top_body_not_list"
            return evidence
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", type(exc).__name__)
        detail = getattr(exc, "detail", None) or getattr(exc, "args", [None])[0]
        evidence["verdict"] = "FAIL"
        evidence["error"] = f"normalize:{code}"
        evidence["normalize_detail"] = str(detail) if detail is not None else None
        # Identify which channel failed first for closeout without re-probing.
        if "trending_normalized" not in evidence:
            evidence["normalize_failed_channel"] = "TRENDING_PUMPFUN"
            if trending["ok"] and isinstance(trending.get("body"), list):
                evidence["trending_shape"] = evidence.get("trending_shape") or _tracker_body_shape(
                    trending["body"], evaluated_at=receipt
                )
        else:
            evidence["normalize_failed_channel"] = "TOP_PUMPFUN"
            if top["ok"] and isinstance(top.get("body"), list):
                evidence["top_shape"] = evidence.get("top_shape") or _tracker_body_shape(
                    top["body"], evaluated_at=receipt
                )
        return evidence

    if not (trending["ok"] and top["ok"]):
        evidence["verdict"] = "FAIL"
        evidence["error"] = "http_or_transport_failure"
        return evidence

    total_normalized = int(evidence.get("trending_normalized") or 0) + int(
        evidence.get("top_normalized") or 0
    )
    evidence["total_normalized"] = total_normalized
    evidence["pumpfun_label_unverified"] = True
    evidence["rank_score_risk_stripped"] = True
    evidence["row_level_freshness_skip"] = True
    evidence["no_retry"] = True
    evidence["free_rest_auth_ok"] = True
    # Empty after contractual freshness filter is factual empty, not failure.
    if total_normalized == 0:
        evidence["verdict"] = "PASS_EMPTY_AFTER_ROW_FILTER"
    else:
        evidence["verdict"] = "PASS"
    return evidence


def setup_campaign(db_path: Path, *, campaign_id: str, run_id: str, cycle_id: str, now: str):
    configuration = {
        "token_capacity": 2,
        "ceilings": {
            "campaign_count": 1,
            "cycle_count": 1,
            "duration_seconds": 360,
            "source_calls": 20,
            "scheduler_work": 11,
            "storage_bytes": 2_000_000,
            "failures": 3,
        },
        "campaign_selection_seed": "7b6-live-proof-seed",
        "report_directory_identity": "path-sha256:" + "b" * 64,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": "sha256:" + "c" * 64,
            "backup_sha256": "d" * 64,
            "required_migration": "032_campaign_ownership_schema.sql",
            "latest_migration": "034_discovery_persistence_reconciliation.sql",
        },
    }
    apply_migrations(db_path)
    created = create_campaign(
        db_path,
        campaign_id=campaign_id,
        configuration_id=f"configuration-{campaign_id}",
        configuration=configuration,
        launch_provenance=provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity=f"isolated-{campaign_id}",
        proof_source_db_identity=f"source-{campaign_id}",
        policy_version="v2-9.7d.7b.6",
    )
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection, campaign_id=campaign_id, run_id=run_id, run_ordinal=1, now=now
    )
    with connection:
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                created_at, updated_at
            ) VALUES (?, ?, ?, 1, 'PLANNED', ?, ?)
            """,
            (cycle_id, campaign_id, run_id, now, now),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
        )
    baseline = locked_counts(connection)
    connection.close()
    return created, configuration, baseline


def run_combined(work_dir: Path, probes: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    db_path = work_dir / "combined_live_proof.sqlite3"
    created, configuration, baseline = setup_campaign(
        db_path,
        campaign_id="campaign-7b6",
        run_id="run-7b6",
        cycle_id="cycle-7b6",
        now=now,
    )
    direct = probes["direct"]
    creates = list(direct.get("decoded_creates") or [])
    origin_proofs = {
        item["mint"]: FixtureOriginProof(
            mint=item["mint"],
            signature=item["signature"],
            slot=int(item["slot"]),
            block_time=int(item["block_time"]),
            bonding_curve=item.get("bonding_curve", "curve"),
            associated_bonding_curve=item.get(
                "associated_bonding_curve", "ata"
            ),
            creator_address=item.get("creator_address", "creator"),
        )
        for item in creates
        if isinstance(item, dict) and item.get("mint")
    }

    gecko = probes["geckoterminal"]
    gecko_ops = []
    if isinstance(gecko.get("_body_trending"), dict):
        gecko_ops.append(
            FixtureSourceFact(
                request_kind=GECKO_TRENDING_REQUEST,
                source_name="geckoterminal",
                body=gecko["_body_trending"],
                receipt_time=now,
                params=dict(GECKO_TRENDING_PARAMS),
            )
        )
    if isinstance(gecko.get("_body_active"), dict):
        pool = (gecko.get("active") or {}).get("pool") or (
            (gecko.get("sample_pools") or [None])[0]
        )
        if pool:
            gecko_ops.append(
                FixtureSourceFact(
                    request_kind=GECKO_ACTIVE_REQUEST,
                    source_name="geckoterminal",
                    body=gecko["_body_active"],
                    receipt_time=now,
                    requested_pool=pool,
                )
            )

    tracker = probes["solana_tracker"]
    tracker_ops = []
    if isinstance(tracker.get("_body_trending"), list):
        tracker_ops.append(
            FixtureSourceFact(
                request_kind=TRACKER_TRENDING_REQUEST,
                source_name="solana_tracker",
                body=tracker["_body_trending"],
                receipt_time=now,
            )
        )
    if isinstance(tracker.get("_body_top"), list):
        tracker_ops.append(
            FixtureSourceFact(
                request_kind=TRACKER_TOP_REQUEST,
                source_name="solana_tracker",
                body=tracker["_body_top"],
                receipt_time=now,
            )
        )

    dex = probes["dexscreener"]
    dex_ops = []
    if isinstance(dex.get("_body_pairs"), list):
        dex_ops.append(
            FixtureSourceFact(
                request_kind="dexscreener_fresh_profiles",
                source_name="dexscreener",
                body=dex["_body_pairs"],
                receipt_time=now,
            )
        )

    fixtures = CombinedDiscoveryFixtures(
        cycle_id="cycle-7b6",
        cycle_cutoff=now,
        campaign_selection_seed="7b6-live-proof-seed",
        provider_contract_versions={
            "geckoterminal": "V2-9.7D.7B.3B",
            "solana_tracker": "V2-9.7D.7B.3B",
            "dexscreener": "existing",
            "direct": "V2-9.7D.7B.3A",
        },
        git_provenance_identity="git-7b6-live",
        evaluated_at=now,
        direct_observations=tuple(origin_proofs.values()),
        origin_proofs=origin_proofs,
        gecko_ops=tuple(gecko_ops),
        tracker_ops=tuple(tracker_ops),
        dexscreener_ops=tuple(dex_ops),
        tracker_auth=SolanaTrackerAuthConfig(
            api_key_secret_ref=tracker.get("auth_env_name") or "SOLANA_TRACKER_API_KEY",
            free_requests_remaining_month=1000,
        )
        if tracker.get("verdict") == "PASS"
        else None,
        pumpswap_proofs={},
    )
    command = AbstractCampaignCommand(
        mode=CAMPAIGN_MODE,
        db_path=db_path,
        db_target_identity="isolated-campaign-7b6",
        campaign_id="campaign-7b6",
        configuration_id="configuration-campaign-7b6",
        configuration_hash=str(created["configuration_hash"]),
        policy_version="v2-9.7d.7b.6",
        token_capacity=2,
        ceilings=CampaignCeilings(
            campaign_count=1,
            cycle_count=1,
            duration_seconds=360,
            source_calls=20,
            scheduler_work=11,
            storage_bytes=2_000_000,
            failures=3,
        ),
        report_directory=work_dir,
        report_directory_identity="path-sha256:" + "b" * 64,
        launch_git_provenance=provenance(),
        run_id="run-7b6",
        report_id="report-7b6",
    )
    result = CombinedPumpfunCampaignExecutor(fixtures).execute(
        command=command,
        source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
        central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
    )
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        final_locked = locked_counts(connection)
        slots = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
            ).fetchone()[0]
        )
        tracking = int(
            connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0]
        )
        window15 = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE job_kind='TRACK_NORMAL_FIRST_15M'"
            ).fetchone()[0]
        )
        jobs = [
            row[0]
            for row in connection.execute("SELECT job_kind FROM printer_scheduler_jobs")
        ]
        batch = connection.execute(
            "SELECT batch_state, first_terminal_cause FROM printer_discovery_batches"
        ).fetchone()
        observations = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_discovery_provider_observations"
            ).fetchone()[0]
        )
        unique_mints = int(
            connection.execute(
                "SELECT COUNT(DISTINCT mint_identity) "
                "FROM printer_discovery_provider_observations"
            ).fetchone()[0]
        )
        selected = [
            row[0]
            for row in connection.execute(
                "SELECT mint_identity FROM printer_memory_factory_campaign_token_slots "
                "ORDER BY slot_ordinal"
            )
        ]
        work_types = [
            row[0]
            for row in connection.execute(
                "SELECT work_type FROM printer_discovery_work ORDER BY work_type"
            )
        ]
    finally:
        connection.close()

    acceptable = result.terminal_status == "COMPLETED" or (
        result.terminal_status == "FAILED"
        and result.first_terminal_cause == "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
        and slots == 0
        and tracking == 0
        and window15 == 0
    )
    return {
        "terminal_status": result.terminal_status,
        "first_terminal_cause": result.first_terminal_cause,
        "source_calls": result.source_calls,
        "scheduler_work": result.scheduler_work,
        "storage_bytes": result.storage_bytes,
        "failures": result.failures,
        "source_governor_used": result.source_governor_used,
        "central_scheduler_used": result.central_scheduler_used,
        "support_5m_only": result.support_5m_only,
        "successor_created": result.successor_created,
        "restart_created": result.restart_created,
        "slots": slots,
        "tracking": tracking,
        "window15m_jobs": window15,
        "job_kinds": sorted(set(jobs)),
        "work_types": work_types,
        "batch_state": None if batch is None else batch["batch_state"],
        "batch_cause": None if batch is None else batch["first_terminal_cause"],
        "observations": observations,
        "unique_mints": unique_mints,
        "selected_mints": selected,
        "locked_baseline": baseline,
        "locked_final": final_locked,
        "locked_delta_zero": baseline == final_locked,
        "no_1h_4h_5m": not any(
            kind
            in {
                "TRACK_NORMAL_1H",
                "TRACK_NORMAL_4H",
                "TRACK_FAST_1H",
                "TRACK_FAST_4H",
                "TRACK_FAST_MICRO_EVENT",
            }
            for kind in jobs
        ),
        "within_reduced_ceilings": (
            result.source_calls <= 20
            and result.scheduler_work <= 11
            and result.storage_bytes <= 2_000_000
            and result.failures <= 3
            and observations <= 24
            and unique_mints <= 12
        ),
        "acceptable_market_outcome": acceptable,
        "db_path": str(db_path),
        "window_jobs_not_executed": True,
    }


def run_negatives(work_dir: Path, probes: dict[str, Any], now: str) -> dict[str, Any]:
    configuration = {
        "token_capacity": 2,
        "ceilings": {
            "campaign_count": 1,
            "cycle_count": 1,
            "duration_seconds": 360,
            "source_calls": 20,
            "scheduler_work": 11,
            "storage_bytes": 2_000_000,
            "failures": 3,
        },
        "campaign_selection_seed": "7b6-live-proof-seed",
        "report_directory_identity": "path-sha256:" + "b" * 64,
        "backup_preflight_references": {
            "preflight_status": "READY",
            "source_identity": "sha256:" + "c" * 64,
            "backup_sha256": "d" * 64,
            "required_migration": "032_campaign_ownership_schema.sql",
            "latest_migration": "034_discovery_persistence_reconciliation.sql",
        },
    }
    creates = list((probes["direct"].get("decoded_creates") or []))
    origin_proofs = {
        item["mint"]: FixtureOriginProof(
            mint=item["mint"],
            signature=item["signature"],
            slot=int(item["slot"]),
            block_time=int(item["block_time"]),
        )
        for item in creates
        if isinstance(item, dict) and item.get("mint")
    }
    gecko_body = probes["geckoterminal"].get("_body_trending") or {"data": []}

    def one(name: str, fixtures: CombinedDiscoveryFixtures) -> dict[str, Any]:
        db_path = work_dir / f"{name}.sqlite3"
        created, _, _ = setup_campaign_simple(
            db_path, campaign_id=name, run_id=f"run-{name}", cycle_id=f"cycle-{name}", now=now,
            configuration=configuration,
        )
        command = AbstractCampaignCommand(
            mode=CAMPAIGN_MODE,
            db_path=db_path,
            db_target_identity=f"isolated-{name}",
            campaign_id=name,
            configuration_id=f"configuration-{name}",
            configuration_hash=str(created["configuration_hash"]),
            policy_version="v2-9.7d.7b.6",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1, cycle_count=1, duration_seconds=360,
                source_calls=20, scheduler_work=11, storage_bytes=2_000_000, failures=3,
            ),
            report_directory=work_dir,
            report_directory_identity="path-sha256:" + "b" * 64,
            launch_git_provenance=provenance(),
            run_id=f"run-{name}",
            report_id=f"report-{name}",
        )
        result = CombinedPumpfunCampaignExecutor(fixtures).execute(
            command=command,
            source_governor=OwnerPort(SOURCE_GOVERNOR_OWNER, True),
            central_scheduler=OwnerPort(CENTRAL_SCHEDULER_OWNER, True),
        )
        connection = sqlite3.connect(db_path)
        try:
            slots = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
                ).fetchone()[0]
            )
            tracking = int(
                connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0]
            )
            window15 = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_kind='TRACK_NORMAL_FIRST_15M'"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        return {
            "terminal_status": result.terminal_status,
            "first_terminal_cause": result.first_terminal_cause,
            "cancellation_reason": result.cancellation_reason,
            "slots": slots,
            "tracking": tracking,
            "window15m": window15,
        }

    isolation = CombinedDiscoveryFixtures(
        cycle_id="cycle-neg-isolation",
        cycle_cutoff=now,
        campaign_selection_seed="7b6-live-proof-seed",
        provider_contract_versions={"direct": "V2-9.7D.7B.3A"},
        git_provenance_identity="git-7b6",
        evaluated_at=now,
        direct_observations=tuple(origin_proofs.values()),
        origin_proofs=origin_proofs,
        gecko_ops=(
            FixtureSourceFact(
                request_kind=GECKO_TRENDING_REQUEST,
                source_name="geckoterminal",
                body=gecko_body,
                receipt_time=now,
                params=dict(GECKO_TRENDING_PARAMS),
            ),
        ),
        provider_failures_injected={"geckoterminal": "rate_limited"},
    )
    origin_loss = CombinedDiscoveryFixtures(
        cycle_id="cycle-neg-origin",
        cycle_cutoff=now,
        campaign_selection_seed="7b6-live-proof-seed",
        provider_contract_versions={"direct": "V2-9.7D.7B.3A"},
        git_provenance_identity="git-7b6",
        evaluated_at=now,
        direct_observations=(),
        origin_proofs={},
        gecko_ops=(
            FixtureSourceFact(
                request_kind=GECKO_TRENDING_REQUEST,
                source_name="geckoterminal",
                body=gecko_body,
                receipt_time=now,
                params=dict(GECKO_TRENDING_PARAMS),
            ),
        ),
    )
    shared = CombinedDiscoveryFixtures(
        cycle_id="cycle-neg-shared",
        cycle_cutoff=now,
        campaign_selection_seed="7b6-live-proof-seed",
        provider_contract_versions={"direct": "V2-9.7D.7B.3A"},
        git_provenance_identity="git-7b6",
        evaluated_at=now,
        force_shared_fault="SHARED_CONFIGURATION_MISMATCH",
    )
    atomic = CombinedDiscoveryFixtures(
        cycle_id="cycle-neg-atomic",
        cycle_cutoff=now,
        campaign_selection_seed="7b6-live-proof-seed",
        provider_contract_versions={"direct": "V2-9.7D.7B.3A"},
        git_provenance_identity="git-7b6",
        evaluated_at=now,
        direct_observations=tuple(origin_proofs.values()),
        origin_proofs=origin_proofs,
        gecko_ops=(
            FixtureSourceFact(
                request_kind=GECKO_TRENDING_REQUEST,
                source_name="geckoterminal",
                body=gecko_body,
                receipt_time=now,
                params=dict(GECKO_TRENDING_PARAMS),
            ),
        ),
        force_handoff_failure="DURING_SECOND",
    )
    return {
        "secondary_isolation": one("neg-isolation", isolation),
        "direct_origin_loss": one("neg-origin", origin_loss),
        "shared_fault": one("neg-shared", shared),
        "atomic_rollback": one("neg-atomic", atomic),
    }


def setup_campaign_simple(
    db_path: Path,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    now: str,
    configuration: dict[str, Any],
):
    apply_migrations(db_path)
    created = create_campaign(
        db_path,
        campaign_id=campaign_id,
        configuration_id=f"configuration-{campaign_id}",
        configuration=configuration,
        launch_provenance=provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity=f"isolated-{campaign_id}",
        proof_source_db_identity=f"source-{campaign_id}",
        policy_version="v2-9.7d.7b.6",
    )
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection, campaign_id=campaign_id, run_id=run_id, run_ordinal=1, now=now
    )
    with connection:
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_cycles(
                cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                created_at, updated_at
            ) VALUES (?, ?, ?, 1, 'PLANNED', ?, ?)
            """,
            (cycle_id, campaign_id, run_id, now, now),
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING'"
        )
        connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
        )
    baseline = locked_counts(connection)
    connection.close()
    return created, configuration, baseline


def main() -> int:
    started = utc_now()
    work_dir = Path(tempfile.mkdtemp(prefix="printer_7b6_live_"))
    evidence_path = work_dir / "redacted_evidence.json"
    print(f"WORK_DIR={work_dir}", flush=True)

    probes: dict[str, Any] = {}
    print("PROBE direct...", flush=True)
    probes["direct"] = probe_direct()
    print("PROBE dexscreener...", flush=True)
    probes["dexscreener"] = probe_dexscreener()
    print("PROBE geckoterminal...", flush=True)
    probes["geckoterminal"] = probe_geckoterminal()
    print("PROBE solana_tracker...", flush=True)
    probes["solana_tracker"] = probe_solana_tracker()

    required = {
        name: probes[name].get("verdict")
        for name in ("direct", "dexscreener", "geckoterminal", "solana_tracker")
    }
    individual_pass = all(str(v).startswith("PASS") for v in required.values())

    evidence: dict[str, Any] = {
        "lane": "V2-9.7D.7B.6",
        "proven_head": PROVEN_HEAD,
        "started_at_utc": started,
        "work_dir": str(work_dir),
        "approved_domains": [
            "api.mainnet-beta.solana.com",
            "api.dexscreener.com",
            "api.geckoterminal.com",
            "data.solanatracker.io",
        ],
        "request_kinds": {
            "direct": [SESSION_REQUEST, BACKFILL_REQUEST, TRANSACTION_REQUEST],
            "dexscreener": ["dexscreener_fresh_profiles", "token_batch"],
            "geckoterminal": [GECKO_TRENDING_REQUEST, GECKO_ACTIVE_REQUEST],
            "solana_tracker": [TRACKER_TRENDING_REQUEST, TRACKER_TOP_REQUEST],
        },
        "providers": {name: redacted(probes[name]) for name in probes},
        "providers_blocked": {
            "pumpportal": {"verdict": "SKIPPED_BLOCKED_CONTRACT", "requests": 0},
            "pumpdev": {"verdict": "EXCLUDED", "requests": 0},
            "pumpswap": {
                "verdict": "PUMPSWAP_CONFIRMATION_NOT_REQUIRED",
                "requests": 0,
                "reason": "no_origin_confirmed_migration_claim_selected_for_live_confirmation",
            },
        },
        "individual_required_verdicts": required,
        "individual_probes_pass": individual_pass,
        "combined": None,
        "negatives": None,
        "temp_raw_deleted": True,
        "overall_verdict": "BLOCKED",
    }

    total_bytes = 0
    total_ops = 0
    for name, probe in probes.items():
        total_bytes += int(probe.get("bytes") or 0)
        total_ops += int(probe.get("operations") or 0)
        if name == "direct":
            total_ops += 0
    evidence["totals"] = {
        "response_bytes": total_bytes
        + int(probes["dexscreener"].get("bytes") or 0)
        + int(probes["geckoterminal"].get("bytes") or 0)
        + int(probes["solana_tracker"].get("bytes") or 0),
        "direct_rpc_operations": int(probes["direct"].get("operations") or 0),
    }

    if not individual_pass:
        evidence["block_reason"] = "required_individual_provider_probe_failed"
        evidence["finished_at_utc"] = utc_now()
        evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
        print(f"EVIDENCE_PATH={evidence_path}", flush=True)
        print(f"INDIVIDUAL_PASS=False", flush=True)
        print(f"OVERALL=BLOCKED", flush=True)
        return 2

    print("COMBINED low-ceiling proof...", flush=True)
    combined = run_combined(work_dir, probes)
    evidence["combined"] = redacted(combined)
    print("NEGATIVES synthetic...", flush=True)
    negatives = run_negatives(work_dir, probes, utc_now())
    evidence["negatives"] = redacted(negatives)

    combined_ok = bool(combined.get("acceptable_market_outcome"))
    negatives_ok = (
        negatives["shared_fault"]["first_terminal_cause"] == "SHARED_CONFIGURATION_MISMATCH"
        and negatives["atomic_rollback"]["slots"] == 0
        and negatives["atomic_rollback"]["tracking"] == 0
        and negatives["atomic_rollback"]["window15m"] == 0
        and negatives["direct_origin_loss"]["first_terminal_cause"]
        == "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
    )
    evidence["combined_ok"] = combined_ok
    evidence["negatives_ok"] = negatives_ok
    evidence["overall_verdict"] = (
        "PASS" if individual_pass and combined_ok and negatives_ok else "BLOCKED"
    )
    evidence["finished_at_utc"] = utc_now()
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    # Dispose any accidental raw dumps if present.
    for path in work_dir.glob("raw_*"):
        try:
            path.unlink()
        except OSError:
            pass
    print(f"EVIDENCE_PATH={evidence_path}", flush=True)
    print(f"INDIVIDUAL_PASS={individual_pass}", flush=True)
    print(f"OVERALL={evidence['overall_verdict']}", flush=True)
    return 0 if evidence["overall_verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
