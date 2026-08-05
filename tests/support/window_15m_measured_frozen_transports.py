"""Measured frozen transport freezes for ordinary WINDOW_15M continuous proof.

Prefer freezing production network seams so production transports emit
``TransportOperationIdentity`` via their normal measured-payload path.

When an explicit transport callable is required, use
``measured_frozen_payload`` / ``measured_frozen_transport`` so identities are
attached with ``build_transport_identity`` + ``measured_payload_fields``.
"""

from __future__ import annotations

import base64
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, MutableMapping, Sequence
from unittest.mock import patch

from printer_v1.sources.measured_transport import (
    TransportOperationIdentity,
    build_transport_identity,
    measured_payload_fields,
)
from printer_v1.sources.pump_contracts import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    CANONICAL_POOL_INDEX,
    PUMP_EVENT_AUTHORITY_ID,
    PUMP_GLOBAL_ID,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMP_WITHDRAW_AUTHORITY_ID,
    PUMPSWAP_EVENT_AUTHORITY_ID,
    PUMPSWAP_GLOBAL_CONFIG_ID,
    PUMPSWAP_POOL_DISCRIMINATOR,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
    _b58encode,
    _derive_ata,
    decode_pumpswap_pool_account,
    derive_canonical_pumpswap_pool,
    derive_program_address,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/candidate_acquisition_capacity_v1.json").read_text()
)


def measured_frozen_payload(
    body: Mapping[str, Any],
    *,
    stage: str,
    source_name: str,
    endpoint_owner: str,
    governed_request_kind: str,
    method_or_endpoint: str,
    within_request_ordinal: int = 1,
    target_category: str,
    target_identity: str | None = None,
    normalized_rows: int | None = None,
    result: str = "OK",
    reserved_from: str | None = None,
) -> dict[str, Any]:
    """Attach one production-equivalent measured identity to a frozen body."""
    payload = dict(body)
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    rows = (
        int(normalized_rows)
        if normalized_rows is not None
        else _infer_normalized_rows(payload)
    )
    identity = build_transport_identity(
        stage=stage,
        source_name=source_name,
        endpoint_owner=endpoint_owner,
        governed_request_kind=governed_request_kind,
        method_or_endpoint=method_or_endpoint,
        within_request_ordinal=within_request_ordinal,
        target_category=target_category,
        target_identity=target_identity,
        response_bytes=len(raw),
        normalized_rows=rows,
        result=result,
        reserved_from=reserved_from,
    )
    payload["response_bytes"] = len(raw)
    payload.update(measured_payload_fields([identity]))
    return payload


def measured_frozen_transport(
    body: Mapping[str, Any],
    **identity_kwargs: Any,
) -> Callable[[Any], Mapping[str, Any]]:
    """Return a transport callable that always emits measured identities."""

    def transport(context: Any = None) -> Mapping[str, Any]:
        del context
        return MappingProxyType(measured_frozen_payload(body, **identity_kwargs))

    return transport


def _infer_normalized_rows(payload: Mapping[str, Any]) -> int:
    for key in ("pairs", "signatures", "data", "tokens", "profiles"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
    result = payload.get("result")
    if isinstance(result, list):
        return len(result)
    if isinstance(result, Mapping) and isinstance(result.get("value"), list):
        return len(result["value"])
    return 0


def _pool_account(creator: str, mint: str) -> tuple[str, dict[str, Any]]:
    pool, bump = derive_canonical_pumpswap_pool(creator=creator, base_mint=mint)
    lp_mint = derive_program_address(
        (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
    )[0]
    base_vault = derive_program_address(
        (_b58decode(pool), _b58decode(TOKEN_PROGRAM_ID), _b58decode(mint)),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]
    quote_vault = derive_program_address(
        (_b58decode(pool), _b58decode(TOKEN_PROGRAM_ID), _b58decode(WSOL_MINT)),
        ASSOCIATED_TOKEN_PROGRAM_ID,
    )[0]
    pubkeys = [creator, mint, WSOL_MINT, lp_mint, base_vault, quote_vault]
    raw = (
        PUMPSWAP_POOL_DISCRIMINATOR
        + bytes([bump])
        + CANONICAL_POOL_INDEX.to_bytes(2, "little")
        + b"".join(_b58decode(value) for value in pubkeys)
        + (1_000_000).to_bytes(8, "little")
        + _b58decode(creator)
        + b"\0\0"
        + (0).to_bytes(16, "little", signed=True)
    )
    return pool, {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
        "executable": False,
        "lamports": 1_000_000,
    }


def build_four_migration_cases() -> list[dict[str, Any]]:
    """Build four distinct pinned-style migration cases from frozen fixture mints.

    Candidate index 2 is the pinned mainnet ``PUMP_WITHDRAW_AUTHORITY_ID`` and
    must never be used as a migration mint (role-1 relation would fail closed).
    Role 1 is always the fixed withdraw authority; user is a distinct non-mint
    fixture key that does not collide with fixed programs or the pool authority.
    """
    # Skip fixture index 2 (withdraw authority pubkey).
    mint_indices = (0, 1, 3, 4)
    cases: list[dict[str, Any]] = []
    for case_index, mint_index in enumerate(mint_indices):
        mint = FIXTURE["candidates"][mint_index][0]
        # Distinct user per case; avoid mint index and fixed withdraw authority.
        user_index = (mint_index + 5) % 32
        if user_index == 2:
            user_index = 6
        user = FIXTURE["candidates"][user_index][0]
        creator = derive_program_address(
            (b"pool-authority", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        pool, account = _pool_account(creator, mint)
        decoded = decode_pumpswap_pool_account(account, pool_address=pool)
        bonding_curve = derive_program_address(
            (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        keys = [
            FIXTURE["candidates"][(mint_index + i) % 32][0] for i in range(25)
        ]
        keys[0] = PUMP_GLOBAL_ID
        keys[1] = PUMP_WITHDRAW_AUTHORITY_ID
        keys[2] = mint
        keys[3] = bonding_curve
        keys[4] = _derive_ata(
            owner=bonding_curve, token_program=TOKEN_PROGRAM_ID, mint=mint
        )
        keys[5] = user
        keys[6] = SYSTEM_PROGRAM_ID
        keys[7] = TOKEN_PROGRAM_ID
        keys[8] = PUMPSWAP_AMM_PROGRAM_ID
        keys[9] = pool
        keys[10] = creator
        keys[11] = _derive_ata(
            owner=creator, token_program=TOKEN_PROGRAM_ID, mint=mint
        )
        keys[12] = _derive_ata(
            owner=creator, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
        )
        keys[13] = PUMPSWAP_GLOBAL_CONFIG_ID
        keys[14] = WSOL_MINT
        keys[15] = decoded["lp_mint"]
        keys[16] = _derive_ata(
            owner=user, token_program=TOKEN_2022_PROGRAM_ID, mint=decoded["lp_mint"]
        )
        keys[17] = decoded["pool_base_token_account"]
        keys[18] = decoded["pool_quote_token_account"]
        keys[19] = TOKEN_2022_PROGRAM_ID
        keys[20] = ASSOCIATED_TOKEN_PROGRAM_ID
        keys[21] = PUMPSWAP_EVENT_AUTHORITY_ID
        keys[22] = PUMP_EVENT_AUTHORITY_ID
        keys[23] = PUMP_PROGRAM_ID
        keys[24] = RENT_SYSVAR_ID
        signature = (
            f"5ContSupplyMigSig{case_index:02d}"
            + "1" * (88 - len(f"5ContSupplyMigSig{case_index:02d}"))
        )[:88]
        tx = {
            "version": 0,
            "slot": 420_000_000 + case_index,
            "blockTime": 1_785_326_400 + case_index,
            "transaction": {
                "message": {
                    "accountKeys": keys,
                    "instructions": [
                        {
                            "programIdIndex": 23,
                            "accounts": list(range(25)),
                            "data": _b58encode(PUMP_MIGRATE_DISCRIMINATOR),
                        }
                    ],
                }
            },
            "meta": {
                "err": None,
                "loadedAddresses": {"writable": [], "readonly": []},
            },
        }
        cases.append(
            {
                "mint": mint,
                "pool": pool,
                "signature": signature,
                "tx": tx,
                "accounts": {pool: account},
            }
        )
    return cases


def geckoterminal_new_pools_body(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Lawful GeckoTerminal new_pools body so production normalizer preserves measured IDs.

    Evidence timestamps must be fresh relative to wall-clock campaign ``now``.
    Fixed historical stamps make retained liquidity appear expired and block
    protocol promotion to MEMORY_OBSERVATION_ELIGIBLE.
    """
    # Fresh relative observation window: created a few minutes ago, still valid.
    observed = datetime.now(timezone.utc) - timedelta(minutes=2)
    observed_iso = observed.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data: list[dict[str, Any]] = []
    for case in cases:
        mint = str(case["mint"])
        pool = str(case["pool"])
        data.append(
            {
                "id": f"solana_{pool}",
                "type": "pool",
                "attributes": {
                    "address": pool,
                    "name": "MEME / SOL",
                    "base_token_price_usd": "0.10",
                    "reserve_in_usd": "12000.0",
                    "fdv_usd": "50000.0",
                    "market_cap_usd": "50000.0",
                    "pool_created_at": observed_iso,
                    "captured_at": observed_iso,
                    "volume_usd": {"m5": "100.0", "h1": "1000.0", "h24": "10000.0"},
                    "transactions": {
                        "m5": {"buys": 3, "sells": 2},
                        "h1": {"buys": 30, "sells": 20},
                        "h24": {"buys": 300, "sells": 200},
                    },
                    "price_change_percentage": {"m5": "1.0", "h1": "2.0", "h24": "3.0"},
                },
                "relationships": {
                    "base_token": {
                        "data": {"id": f"solana_{mint}", "type": "token"}
                    },
                    "quote_token": {
                        "data": {"id": f"solana_{WSOL_MINT}", "type": "token"}
                    },
                    "dex": {"data": {"id": "pumpswap", "type": "dex"}},
                    "network": {"data": {"id": "solana", "type": "network"}},
                },
            }
        )
    return {"data": data, "included": []}


def dexscreener_pair_body(pool: str, mint: str, liquidity_usd: float) -> dict[str, Any]:
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "dexId": "pumpswap",
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "quoteToken": {
                    "address": WSOL_MINT,
                    "symbol": "SOL",
                    "name": "Wrapped SOL",
                },
                "priceUsd": "0.10",
                "liquidity": {"usd": liquidity_usd},
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
                "marketCap": 50_000.0 if liquidity_usd >= 3000 else 5.0,
                "fdv": 50_000.0,
            }
        ]
    }


class NetworkFreezeBundle:
    """Route-level freezes for production transports (measured identities emitted by production)."""

    def __init__(self, cases: Sequence[Mapping[str, Any]]) -> None:
        self.cases = list(cases)
        self.by_sig = {
            str(case["signature"]): (case["tx"], dict(case["accounts"]))
            for case in self.cases
        }
        self.pair_by_pool = {
            str(case["pool"]): dexscreener_pair_body(
                str(case["pool"]), str(case["mint"]), 12_000.0 + i
            )
            for i, case in enumerate(self.cases)
        }
        self.pair_by_mint = {
            str(case["mint"]): self.pair_by_pool[str(case["pool"])]
            for case in self.cases
        }
        self.rpc_calls: list[tuple[str, Any]] = []
        self.http_calls: list[str] = []

    def freeze(self) -> list[Any]:
        """Return patch context managers for production network seams."""
        return [
            patch(
                "printer_v1.sources.direct_pump_migration._rpc_post",
                side_effect=self._rpc_post,
            ),
            patch(
                "printer_v1.sources.pump_migration._rpc_post",
                side_effect=self._rpc_post,
            ),
            patch(
                "printer_v1.sources.solana_rpc_holder._rpc_post",
                side_effect=self._rpc_post,
            ),
            patch(
                "printer_v1.sources.dexscreener._dexscreener_http_get_json",
                side_effect=self._dex_http_get_json,
            ),
            patch(
                "urllib.request.urlopen",
                side_effect=self._urlopen,
            ),
        ]

    def _rpc_post(
        self,
        rpc_url: str,
        method: str,
        params: list[Any],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        del rpc_url, timeout_seconds
        self.rpc_calls.append((method, params))
        if method == "getSignaturesForAddress":
            rows = [
                {
                    "signature": case["signature"],
                    "slot": case["tx"]["slot"],
                    "err": None,
                    "confirmationStatus": "finalized",
                }
                for case in self.cases
            ]
            body = {"jsonrpc": "2.0", "id": 1, "result": rows}
            raw = json.dumps(body).encode("utf-8")
            return MappingProxyType(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": rows,
                    "response_bytes": len(raw),
                    "transport_operations_used": 1,
                }
            )
        if method == "getTransaction":
            signature = params[0]
            tx, _accounts = self.by_sig.get(str(signature), (None, {}))
            body = {"jsonrpc": "2.0", "id": 1, "result": tx}
            raw = json.dumps(body, default=str).encode("utf-8")
            return MappingProxyType(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": tx,
                    "response_bytes": len(raw),
                    "transport_operations_used": 1,
                }
            )
        if method == "getMultipleAccounts":
            keys = params[0] if params else []
            values = []
            for key in keys:
                found = None
                for _sig, (_tx, infos) in self.by_sig.items():
                    if key in infos:
                        found = infos[key]
                        break
                values.append(found)
            result = {
                "context": {"slot": 420_000_000, "apiVersion": "2.0"},
                "value": values,
            }
            body = {"jsonrpc": "2.0", "id": 1, "result": result}
            raw = json.dumps(body, default=str).encode("utf-8")
            return MappingProxyType(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": result,
                    "response_bytes": len(raw),
                    "transport_operations_used": 1,
                }
            )
        if method == "getTokenLargestAccounts":
            # Spread supply so top-10 concentration is healthy (< extreme).
            accounts = [
                {
                    "address": f"HolderATA{i:02d}" + "1" * 24,
                    "amount": str(100_000 - i * 5_000),
                    "decimals": 6,
                    "uiAmount": float(100_000 - i * 5_000) / 1_000_000,
                    "uiAmountString": str((100_000 - i * 5_000) / 1_000_000),
                }
                for i in range(10)
            ]
            result = {
                "context": {"slot": 420_000_000},
                "value": accounts,
            }
            body = {"jsonrpc": "2.0", "id": 1, "result": result}
            raw = json.dumps(body).encode("utf-8")
            return MappingProxyType(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": result,
                    "response_bytes": len(raw),
                    "transport_operations_used": 1,
                }
            )
        if method == "getTokenSupply":
            result = {
                "context": {"slot": 420_000_000},
                "value": {
                    "amount": "1000000",
                    "decimals": 6,
                    "uiAmount": 1.0,
                    "uiAmountString": "1",
                },
            }
            body = {"jsonrpc": "2.0", "id": 1, "result": result}
            raw = json.dumps(body).encode("utf-8")
            return MappingProxyType(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": result,
                    "response_bytes": len(raw),
                    "transport_operations_used": 1,
                }
            )
        return MappingProxyType(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": None,
                "response_bytes": 2,
                "transport_operations_used": 1,
            }
        )

    def _dex_http_get_json(
        self,
        endpoint: str,
        timeout_seconds: float,
        *,
        byte_ceiling: int = 2_000_000,
    ) -> tuple[Any, int]:
        del timeout_seconds, byte_ceiling
        self.http_calls.append(str(endpoint))
        text = str(endpoint)
        # Fresh profiles.
        if "token-profiles" in text:
            profiles = [
                {
                    "chainId": "solana",
                    "tokenAddress": case["mint"],
                    "url": f"https://dexscreener.com/solana/{case['mint']}",
                }
                for case in self.cases
            ]
            raw = json.dumps(profiles).encode("utf-8")
            return profiles, len(raw)
        # Mint batch: /tokens/v1/solana/{comma-separated}
        if "/tokens/v1/solana/" in text:
            tail = text.rsplit("/solana/", 1)[-1]
            mints = [part for part in tail.split(",") if part]
            pairs: list[dict[str, Any]] = []
            for mint in mints:
                body = self.pair_by_mint.get(mint)
                if body:
                    pairs.extend(body.get("pairs") or [])
            raw = json.dumps(pairs).encode("utf-8")
            return pairs, len(raw)
        # Exact pair: /pairs/solana/{pool}
        if "/pairs/solana/" in text:
            pool = text.rsplit("/solana/", 1)[-1].split("?")[0]
            body = self.pair_by_pool.get(pool) or {"pairs": []}
            raw = json.dumps(body).encode("utf-8")
            return body, len(raw)
        # Unknown dexscreener endpoint: honest empty.
        empty: list[Any] = []
        raw = json.dumps(empty).encode("utf-8")
        return empty, len(raw)

    def _urlopen(self, request, timeout=None):  # noqa: ANN001
        """Catch residual HTTP with measured-friendly frozen bodies."""
        del timeout
        url = getattr(request, "full_url", None) or getattr(request, "get_full_url", lambda: "")()
        text = str(url)
        self.http_calls.append(text)
        post_data = getattr(request, "data", None)
        # Solana JSON-RPC over HTTPS (account batch, residual RPC).
        if post_data and (
            "solana" in text.lower()
            or "alchemy" in text.lower()
            or "helius" in text.lower()
            or "rpc" in text.lower()
            or text.startswith("http")
        ):
            rpc_body = self._json_rpc_from_post(post_data)
            if rpc_body is not None:
                raw = json.dumps(rpc_body, default=str).encode("utf-8")
                return self._http_response(raw)
        # DexScreener pair/profile/batch may use smoke transport (urlopen) rather
        # than _dexscreener_http_get_json depending on builder.
        if "dexscreener.com" in text:
            parsed, _nbytes = self._dex_http_get_json(text, 5.0)
            # Smoke transport expects the parsed JSON body as the response payload.
            body = parsed if not isinstance(parsed, list) else parsed
            if isinstance(parsed, list) and "token-profiles" in text:
                body = parsed
            elif isinstance(parsed, list) and "/tokens/v1/solana/" in text:
                # Pair snapshot smoke expects object with schemaVersion/pairs.
                body = {
                    "schemaVersion": "1.0.0",
                    "pairs": parsed,
                }
            elif isinstance(parsed, dict) and "pairs" in parsed:
                body = {
                    "schemaVersion": "1.0.0",
                    **parsed,
                }
            raw = json.dumps(body).encode("utf-8")
        elif "geckoterminal.com" in text:
            # Prefer lawful pool bodies so the production normalizer keeps
            # transport_operation_identities (empty data fails without them).
            if "new_pools" in text or "/pools" in text:
                body = geckoterminal_new_pools_body(self.cases)
            else:
                body = {"data": [], "included": []}
            raw = json.dumps(body).encode("utf-8")
        elif "coingecko.com" in text:
            body = {
                "bitcoin": {"usd": 1.0, "usd_24h_change": 0.0, "usd_24h_vol": 1.0},
                "ethereum": {"usd": 1.0, "usd_24h_change": 0.0, "usd_24h_vol": 1.0},
                "solana": {"usd": 1.0, "usd_24h_change": 0.0, "usd_24h_vol": 1.0},
            }
            raw = json.dumps(body).encode("utf-8")
        elif "gopluslabs.io" in text:
            # Token security: /api/v1/token_security/solana?contract_addresses=MINT
            # or path containing mint. Production expects mint-keyed result.
            mint = None
            if "contract_addresses=" in text:
                mint = text.rsplit("contract_addresses=", 1)[-1].split("&")[0]
            elif self.cases:
                mint = str(self.cases[0]["mint"])
            if not mint:
                mint = "UnknownMint"
            body = {
                "code": 1,
                "message": "OK",
                "result": {
                    mint: {
                        "mint_authority": None,
                        "freeze_authority": None,
                        "is_in_dex": "1",
                        "holder_count": "100",
                        "total_supply": "1000000000",
                        "owner_balance": "0",
                        "owner_percent": "0",
                        "creator_percent": "0",
                        "is_honeypot": "0",
                        "is_open_source": "1",
                        "is_proxy": "0",
                        "is_mintable": "0",
                        "is_blacklisted": "0",
                        "can_take_back_ownership": "0",
                        "hidden_owner": "0",
                        "slippage_modifiable": "0",
                        "personal_slippage_modifiable": "0",
                        "transfer_pausable": "0",
                        "is_anti_whale": "0",
                        "trading_cooldown": "0",
                    }
                },
            }
            raw = json.dumps(body).encode("utf-8")
        elif "jup.ag" in text:
            body = {
                "inputMint": WSOL_MINT,
                "outputMint": WSOL_MINT,
                "inAmount": "1000000",
                "outAmount": "1000000",
                "otherAmountThreshold": "990000",
                "swapMode": "ExactIn",
                "slippageBps": 50,
                "priceImpactPct": "0",
                "routePlan": [],
            }
            raw = json.dumps(body).encode("utf-8")
        elif "helius" in text.lower():
            body = {"jsonrpc": "2.0", "id": 1, "result": None}
            raw = json.dumps(body).encode("utf-8")
        else:
            body = {}
            raw = json.dumps(body).encode("utf-8")

        return self._http_response(raw)

    def _json_rpc_from_post(self, post_data: Any) -> dict[str, Any] | None:
        """Decode a Solana JSON-RPC POST body and return a frozen result."""
        try:
            if isinstance(post_data, bytes):
                raw_req = post_data
            elif isinstance(post_data, str):
                raw_req = post_data.encode("utf-8")
            else:
                return None
            envelope = json.loads(raw_req.decode("utf-8"))
        except (TypeError, ValueError, UnicodeDecodeError):
            return None
        if not isinstance(envelope, Mapping):
            return None
        method = str(envelope.get("method") or "")
        params = list(envelope.get("params") or ())
        # Reuse the same RPC freeze used by direct/pump migration _rpc_post.
        frozen = self._rpc_post(
            "https://frozen.invalid",
            method,
            params,
            timeout_seconds=5.0,
        )
        return dict(frozen)

    @staticmethod
    def _http_response(raw: bytes) -> Any:
        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def read(self_inner, n: int = -1) -> bytes:
                return raw if n < 0 else raw[:n]

            status = 200

        return _Resp()


__all__ = [
    "NetworkFreezeBundle",
    "TransportOperationIdentity",
    "build_four_migration_cases",
    "dexscreener_pair_body",
    "geckoterminal_new_pools_body",
    "measured_frozen_payload",
    "measured_frozen_transport",
]
