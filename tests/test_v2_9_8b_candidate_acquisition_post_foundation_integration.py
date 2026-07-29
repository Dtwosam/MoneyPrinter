from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.candidate_acquisition import (
    CandidateAcquisitionError,
    legacy_two_token_runtime_projection,
)
from printer_v1.discovery.pump_migration_observation import (
    CANDIDATE_MINT,
    MIGRATION_SIGNATURE,
    NO_PUMP_GRADUATION_CLAIM,
    PUMP_ACTIVE_BONDING_CURVE,
    PUMP_BONDING_CURVE,
    PUMP_GRADUATION_CLAIMED,
    PUMP_LINEAGE_CONFLICT,
    PUMPSWAP_POOL,
    classify_candidate_lineage_branch,
    plan_candidate_migration_locator,
    validate_candidate_migration_locator,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import live_candidate_acquisition_transport as live_transport
from printer_v1.operator_cli.candidate_acquisition_integration import (
    CLI_MODE_N2,
    CLI_MODE_N7,
    MODE_N2,
    MODE_N7,
    MODE_POLICIES,
    AcquisitionSourceOperation,
    CandidateAcquisitionIntegrationError,
    FrozenAcquisitionTransportOwner,
    _load_exact_cursor_heads,
    replay_candidate_acquisition_integration_report,
    run_candidate_acquisition_integration,
)
from printer_v1.operator_cli.live_candidate_acquisition_transport import (
    LiveAcquisitionConfiguration,
    LiveAcquisitionConfigurationError,
    LiveAcquisitionTransportError,
    LiveCandidateAcquisitionTransportOwner,
    TransportResponse,
    UrllibCandidateAcquisitionOneShotTransport,
    _signature_page_request_options,
    build_live_candidate_acquisition_transport_owner,
)
from printer_v1.sources.contracts import NormalizedSourceResult
from printer_v1.sources.dexscreener import (
    build_dexscreener_adapter,
    fixture_success_transport as dexscreener_fixture_success_transport,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)
from printer_v1.sources.geckoterminal import (
    build_geckoterminal_adapter,
    fixture_failure_transport as geckoterminal_fixture_failure_transport,
    fixture_success_transport as geckoterminal_fixture_success_transport,
)
from printer_v1.sources.pump_contracts import (
    ASSOCIATED_TOKEN_PROGRAM_ID,
    METADATA_PROGRAM_ID,
    OFFICIAL_REPOSITORY_COMMIT,
    PUMP_BONDING_CURVE_DISCRIMINATOR,
    PUMP_CREATE_DISCRIMINATOR,
    PUMP_IDL_SHA256,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMPSWAP_POOL_DISCRIMINATOR,
    RENT_SYSVAR_ID,
    SYSTEM_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
    WSOL_MINT,
    _b58encode,
    _derive_ata,
    derive_canonical_pumpswap_pool,
    derive_program_address,
    decode_supported_pump_migration_transaction,
    verify_pinned_pump_migration,
)
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpfun_origin import PUMP_CREATE_INDEX_ADDRESS
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "tests/fixtures/candidate_acquisition_capacity_v1.json").read_text()
)
NOW = "2026-07-29T12:00:00+00:00"
EXPIRES = "2026-07-29T14:00:00+00:00"
POOL_PROGRAM = "675kPX9MHTjS2zt1qfr1NYHuzeuycG6t58pk8Rai7Lb"


def _pumpswap_account(mint: str, ordinal: int) -> dict:
    keys = [item for row in FIXTURE["candidates"] for item in row]
    creator = keys[(ordinal * 5) % len(keys)]
    remaining = [keys[(ordinal * 5 + offset) % len(keys)] for offset in range(1, 4)]
    raw = (
        PUMPSWAP_POOL_DISCRIMINATOR
        + b"\1"
        + (ordinal + 1).to_bytes(2, "little")
        + b"".join(_b58decode(item) for item in (
            creator, mint, WSOL_MINT, remaining[0], remaining[1], remaining[2]
        ))
        + (1_000_000).to_bytes(8, "little")
        + _b58decode(creator)
        + b"\0\0"
        + (0).to_bytes(16, "little", signed=True)
    )
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


def _pinned_pumpswap_account(
    *, creator: str, mint: str, pool: str
) -> dict:
    lp_mint = derive_program_address(
        (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
    )[0]
    base_vault = _derive_ata(
        owner=pool, token_program=TOKEN_PROGRAM_ID, mint=mint
    )
    quote_vault = _derive_ata(
        owner=pool, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
    )
    _pool, bump = derive_canonical_pumpswap_pool(
        creator=creator, base_mint=mint, quote_mint=WSOL_MINT
    )
    assert _pool == pool
    raw = (
        PUMPSWAP_POOL_DISCRIMINATOR
        + bytes([bump])
        + (0).to_bytes(2, "little")
        + b"".join(_b58decode(item) for item in (
            creator, mint, WSOL_MINT, lp_mint, base_vault, quote_vault
        ))
        + (1_000_000).to_bytes(8, "little")
        + _b58decode(creator)
        + b"\0\0"
        + (0).to_bytes(16, "little", signed=True)
    )
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


def _pump_bonding_curve_account(
    *, mint: str, creator: str, complete: bool = False
) -> tuple[str, dict]:
    curve = derive_program_address(
        (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    raw = (
        PUMP_BONDING_CURVE_DISCRIMINATOR
        + (1_000_000).to_bytes(8, "little")
        + (1_000).to_bytes(8, "little")
        + (900_000).to_bytes(8, "little")
        + (900).to_bytes(8, "little")
        + (1_000_000).to_bytes(8, "little")
        + bytes([int(complete)])
        + _b58decode(creator)
        + b"\0\0"
        + _b58decode(WSOL_MINT)
    )
    return curve, {
        "owner": PUMP_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


def _spl_mint_account(*, owner: str = TOKEN_PROGRAM_ID) -> dict:
    raw = bytearray(82)
    raw[45] = 1
    return {"owner": owner, "data": [base64.b64encode(raw).decode(), "base64"]}


def _token_2022_mint_account(*, with_extension: bool = True) -> dict:
    raw = bytearray(166)
    raw[45] = 1
    raw[165] = 1
    if with_extension:
        # Structurally valid synthetic TLV: type=7, length=3, body=3 bytes.
        raw.extend((7).to_bytes(2, "little"))
        raw.extend((3).to_bytes(2, "little"))
        raw.extend(b"xyz")
    return {
        "owner": TOKEN_2022_PROGRAM_ID,
        "data": [base64.b64encode(raw).decode(), "base64"],
    }


class _CanonicalMockNetworkTransport:
    """Frozen responses at the live owner's one-shot HTTP/RPC boundary."""

    def __init__(self, count: int) -> None:
        self.rows = _candidate_rows(count)
        self.mints = {row["mint"] for row in self.rows}
        self.mint_ordinals = {
            row["mint"]: ordinal for ordinal, row in enumerate(self.rows)
        }
        self.pools = {
            row["pool"]: _pumpswap_account(row["mint"], ordinal)
            for ordinal, row in enumerate(self.rows)
        }
        self.calls: list[tuple[str, str]] = []

    def _result(self, payload, operation_kind: str, endpoint_role: str) -> TransportResponse:
        self.calls.append((operation_kind, endpoint_role))
        size = len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        return TransportResponse(payload, size, operation_kind, endpoint_role)

    def http_json(self, *, url, headers, timeout_seconds, byte_ceiling, endpoint_role):
        del url, headers, timeout_seconds, byte_ceiling
        if endpoint_role == "DEXSCREENER_PROFILES":
            payload = [
                {"chainId": "solana", "tokenAddress": row["mint"]}
                for row in self.rows
            ]
        elif endpoint_role == "DEXSCREENER_MARKET_BATCH":
            payload = [
                {
                    "chainId": "solana", "pairAddress": row["pool"],
                    "baseToken": {"address": row["mint"], "symbol": "MEME"},
                    "liquidity": {"usd": 10_000.0},
                    "volume": {"m5": 1_000.0, "h1": 4_000.0},
                    "txns": {"m5": {"buys": 2, "sells": 1}},
                    "pairCreatedAt": 1_785_326_000_000,
                }
                for row in self.rows
            ]
        elif endpoint_role == "GECKOTERMINAL_NEW_POOLS":
            row = self.rows[0]
            payload = {"data": [{
                "id": f"solana_{row['pool']}",
                "attributes": {
                    "chain": "solana", "address": row["pool"],
                    "base_token_address": row["mint"],
                    "reserve_in_usd": 10_000.0,
                    "volume_usd": {"m5": 1_000.0, "h1": 4_000.0},
                    "transactions": {"m5": {"buys": 2, "sells": 1}},
                    "pool_created_at": "2026-07-29T10:00:00+00:00",
                },
            }]}
        elif endpoint_role.startswith("GOPLUS_SAFETY_REFERENCE_"):
            payload = {"result": {}}
        else:
            raise AssertionError(f"unexpected HTTP role: {endpoint_role}")
        return self._result(payload, "HTTP_GET", endpoint_role)

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        del rpc_url, timeout_seconds, byte_ceiling
        if method == "getSignaturesForAddress":
            payload = []
        elif method == "getMultipleAccounts":
            addresses = list(params[0])
            values = []
            for address in addresses:
                if address in self.mints:
                    # Exercise both adopted mint programs through the normal
                    # public CLI path. Token-2022 rows include a valid TLV and
                    # reproduce the live-shaped extended-account boundary.
                    values.append(
                        _spl_mint_account()
                        if self.mint_ordinals[address] % 2 == 0
                        else _token_2022_mint_account(with_extension=True)
                    )
                else:
                    values.append(self.pools[address])
            payload = {"context": {"slot": 420_000_000}, "value": values}
        elif method == "getTokenLargestAccounts":
            payload = {"context": {"slot": 420_000_000}, "value": [
                {"address": self.rows[0]["pool"], "amount": "1", "decimals": 0}
            ]}
        elif method == "getTokenSupply":
            payload = {"context": {"slot": 420_000_000}, "value": {
                "amount": "1000", "decimals": 0, "uiAmount": 1000,
                "uiAmountString": "1000",
            }}
        else:
            raise AssertionError(f"unexpected RPC method: {method}")
        return self._result(payload, method, endpoint_role)


class _LiveShapedAdmissionNetwork(_CanonicalMockNetworkTransport):
    """Exact Pump-curve, PumpSwap, and generic-pool admission fixture."""

    CREATE_SIGNATURES = ("create-live-shaped-1", "create-live-shaped-2")
    MIGRATION_SIGNATURE = "migration-live-shaped-1"

    def __init__(self, count: int) -> None:
        super().__init__(count)
        self.rows = sorted(self.rows, key=lambda row: row["mint"])
        self.mints = {row["mint"] for row in self.rows}
        self.mint_ordinals = {
            row["mint"]: ordinal for ordinal, row in enumerate(self.rows)
        }
        key_material = [item for row in FIXTURE["candidates"] for item in row]
        curve, curve_account = _pump_bonding_curve_account(
            mint=self.rows[0]["mint"], creator=key_material[-1]
        )
        self.rows[0]["pool"] = curve
        # The pinned Pump migration/PumpSwap contract uses the classic SPL
        # token program for its base mint. Keep the migrated fixture on an
        # even ordinal; odd ordinals deliberately exercise Token-2022 through
        # the generic exact-present-pool branch.
        self.migrated_ordinal = 2
        migrated_mint = self.rows[self.migrated_ordinal]["mint"]
        self.migration_creator = derive_program_address(
            (b"pool-authority", _b58decode(migrated_mint)), PUMP_PROGRAM_ID
        )[0]
        migration_pool = derive_canonical_pumpswap_pool(
            creator=self.migration_creator,
            base_mint=migrated_mint,
            quote_mint=WSOL_MINT,
        )[0]
        self.rows[self.migrated_ordinal]["pool"] = migration_pool
        self.pool_accounts = {
            curve: curve_account,
            migration_pool: _pinned_pumpswap_account(
                creator=self.migration_creator,
                mint=migrated_mint,
                pool=migration_pool,
            ),
        }
        self.pool_accounts.update({
            row["pool"]: {
                "owner": POOL_PROGRAM,
                "data": [base64.b64encode(b"generic-present-pool").decode(), "base64"],
            }
            for ordinal, row in enumerate(self.rows)
            if ordinal not in {0, self.migrated_ordinal}
        })
        self.create_transactions = [
            self._create_transaction(self.rows[0]["mint"], key_material, slot=500),
            self._create_transaction(
                self.rows[self.migrated_ordinal]["mint"], key_material, slot=499
            ),
        ]
        self.migration_transaction = self._migration_transaction(
            self.rows[self.migrated_ordinal]["mint"], migration_pool, key_material
        )

    @staticmethod
    def _create_transaction(mint: str, keys: list[str], *, slot: int) -> dict:
        account_keys = list(keys[:14])
        account_keys[0] = mint
        account_keys[1] = derive_program_address((b"mint-authority",), PUMP_PROGRAM_ID)[0]
        account_keys[2] = derive_program_address(
            (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        account_keys[5] = METADATA_PROGRAM_ID
        account_keys[8] = SYSTEM_PROGRAM_ID
        account_keys[9] = TOKEN_PROGRAM_ID
        account_keys[10] = ASSOCIATED_TOKEN_PROGRAM_ID
        account_keys[11] = RENT_SYSVAR_ID
        account_keys[13] = PUMP_PROGRAM_ID
        return {
            "version": "legacy",
            "slot": slot,
            "blockTime": 1_785_326_000 + slot,
            "meta": {"err": None, "innerInstructions": []},
            "transaction": {"message": {
                "accountKeys": account_keys,
                "instructions": [{
                    "programIdIndex": 13,
                    "accounts": list(range(14)),
                    "data": _b58encode(PUMP_CREATE_DISCRIMINATOR),
                }],
            }},
        }

    def _migration_transaction(self, mint: str, pool: str, keys: list[str]) -> dict:
        accounts = list((keys * 3)[:25])
        bonding_curve = derive_program_address(
            (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
        )[0]
        lp_mint = derive_program_address(
            (b"pool_lp_mint", _b58decode(pool)), PUMPSWAP_AMM_PROGRAM_ID
        )[0]
        base_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=mint
        )
        quote_vault = _derive_ata(
            owner=pool, token_program=TOKEN_PROGRAM_ID, mint=WSOL_MINT
        )
        fixed = {
            2: mint, 3: bonding_curve, 6: SYSTEM_PROGRAM_ID,
            7: TOKEN_PROGRAM_ID, 8: PUMPSWAP_AMM_PROGRAM_ID,
            9: pool, 10: self.migration_creator, 14: WSOL_MINT,
            15: lp_mint, 17: base_vault, 18: quote_vault,
            19: TOKEN_2022_PROGRAM_ID, 20: ASSOCIATED_TOKEN_PROGRAM_ID,
            23: PUMP_PROGRAM_ID, 24: RENT_SYSVAR_ID,
        }
        for index, value in fixed.items():
            accounts[index] = value
        return {
            "version": "legacy",
            "slot": 498,
            "blockTime": 1_785_326_498,
            "meta": {"err": None, "innerInstructions": []},
            "transaction": {"message": {
                "accountKeys": accounts,
                "instructions": [{
                    "programIdIndex": 23,
                    "accounts": list(range(25)),
                    "data": _b58encode(PUMP_MIGRATE_DISCRIMINATOR),
                }],
            }},
        }

    def http_json(self, *, url, headers, timeout_seconds, byte_ceiling, endpoint_role):
        del url, headers, timeout_seconds, byte_ceiling
        if endpoint_role == "DEXSCREENER_PROFILES":
            payload = [
                {"chainId": "solana", "tokenAddress": row["mint"]}
                for row in self.rows
            ]
        elif endpoint_role == "DEXSCREENER_MARKET_BATCH":
            payload = [
                {
                    "chainId": "solana", "pairAddress": row["pool"],
                    "baseToken": {"address": row["mint"], "symbol": "MEME"},
                    "quoteToken": {"address": WSOL_MINT, "symbol": "SOL"},
                    "dexId": (
                        "pumpfun" if ordinal == 0
                        else "pumpswap" if ordinal == self.migrated_ordinal else "raydium"
                    ),
                    "liquidity": {"usd": 10_000.0},
                    "volume": {"m5": 1_000.0, "h1": 4_000.0},
                    "txns": {"m5": {"buys": 2, "sells": 1}},
                    "pairCreatedAt": 1_785_326_000_000,
                }
                for ordinal, row in enumerate(self.rows)
            ]
        elif endpoint_role == "GECKOTERMINAL_NEW_POOLS":
            row = self.rows[0]
            payload = {"data": [{
                "id": f"solana_{row['pool']}", "type": "pool",
                "attributes": {
                    "chain": "solana", "address": row["pool"],
                    "reserve_in_usd": 10_000.0,
                    "volume_usd": {"m5": 1_000.0, "h1": 4_000.0},
                    "transactions": {"m5": {"buys": 2, "sells": 1}},
                    "pool_created_at": "2026-07-29T10:00:00+00:00",
                },
                "relationships": {
                    "base_token": {"data": {"id": f"solana_{row['mint']}"}},
                    "quote_token": {"data": {"id": f"solana_{WSOL_MINT}"}},
                    "dex": {"data": {"id": "pumpfun"}},
                },
            }]}
        elif endpoint_role.startswith("GOPLUS_SAFETY_REFERENCE_"):
            payload = {"result": {}}
        else:
            raise AssertionError(f"unexpected HTTP role: {endpoint_role}")
        return self._result(payload, "HTTP_GET", endpoint_role)

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        del rpc_url, timeout_seconds, byte_ceiling
        if method == "getSignaturesForAddress":
            indexed = str(params[0])
            options = dict(params[1]) if len(params) > 1 else {}
            if options.get("until"):
                payload = []
            elif indexed == PUMP_CREATE_INDEX_ADDRESS:
                payload = [
                    {"signature": signature, "slot": 500 - ordinal, "err": None,
                     "confirmationStatus": "finalized"}
                    for ordinal, signature in enumerate(self.CREATE_SIGNATURES)
                ]
            elif indexed == PUMP_PROGRAM_ID:
                payload = [{
                    "signature": self.MIGRATION_SIGNATURE, "slot": 498,
                    "err": None, "confirmationStatus": "finalized",
                }]
            else:
                raise AssertionError(f"unexpected signature target: {indexed}")
        elif method == "getTransaction":
            signature = str(params[0])
            if signature in self.CREATE_SIGNATURES:
                payload = self.create_transactions[self.CREATE_SIGNATURES.index(signature)]
            elif signature == self.MIGRATION_SIGNATURE:
                payload = self.migration_transaction
            else:
                raise AssertionError(f"unexpected transaction signature: {signature}")
        elif method == "getMultipleAccounts":
            addresses = list(params[0])
            if all(address in self.mints for address in addresses):
                values = [
                    _spl_mint_account()
                    if self.mint_ordinals[address] % 2 == 0
                    else _token_2022_mint_account(with_extension=True)
                    for address in addresses
                ]
            elif addresses == [POOL_PROGRAM]:
                values = [{
                    "owner": "BPFLoaderUpgradeab1e11111111111111111111111",
                    "executable": True,
                    "data": [base64.b64encode(b"program-data").decode(), "base64"],
                }]
            else:
                values = [self.pool_accounts[address] for address in addresses]
            payload = {"context": {"slot": 500}, "value": values}
        elif method == "getTokenLargestAccounts":
            payload = {"context": {"slot": 500}, "value": [
                {"address": self.rows[0]["pool"], "amount": "1", "decimals": 0}
            ]}
        elif method == "getTokenSupply":
            payload = {"context": {"slot": 500}, "value": {
                "amount": "1000", "decimals": 0,
                "uiAmount": 1000, "uiAmountString": "1000",
            }}
        else:
            raise AssertionError(f"unexpected RPC method: {method}")
        return self._result(payload, method, endpoint_role)


class _LiveShapedFailureNetwork(_LiveShapedAdmissionNetwork):
    """One-defect-at-a-time low-level evidence mutations for exact taxonomy."""

    def __init__(self, failure: str) -> None:
        super().__init__(7)
        self.failure = failure
        self.target_mint = self.rows[1]["mint"]
        self.target_pool = self.rows[1]["pool"]

    def http_json(self, *, url, headers, timeout_seconds, byte_ceiling, endpoint_role):
        response = super().http_json(
            url=url, headers=headers, timeout_seconds=timeout_seconds,
            byte_ceiling=byte_ceiling, endpoint_role=endpoint_role,
        )
        payload = deepcopy(response.payload)
        if endpoint_role == "DEXSCREENER_MARKET_BATCH":
            pair = next(
                item for item in payload
                if item.get("baseToken", {}).get("address") == self.target_mint
            )
            if self.failure == "missing_quote_identity":
                pair.pop("quoteToken", None)
            elif self.failure == "base_quote_reversal":
                pair["baseToken"] = {"address": WSOL_MINT, "symbol": "SOL"}
                pair["quoteToken"] = {
                    "address": self.target_mint, "symbol": "MEME"
                }
            elif self.failure == "liquidity_failure":
                pair["liquidity"] = {"usd": 1.0}
            elif self.failure == "tradeability_failure":
                pair["volume"] = {"m5": 0.0, "h1": 0.0}
                pair["txns"] = {"m5": {"buys": 0, "sells": 0}}
        return TransportResponse(
            payload, response.bytes_used, response.operation_kind,
            response.endpoint_role,
        )

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        response = super().rpc_json(
            rpc_url=rpc_url, method=method, params=params,
            timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
            endpoint_role=endpoint_role,
        )
        payload = deepcopy(response.payload)
        if endpoint_role == "PUMPSWAP_POOL_ACCOUNT_BATCH":
            addresses = list(params[0])
            values = list(payload["value"])
            target_index = addresses.index(self.target_pool)
            if self.failure == "wrong_pool_role_program":
                values[target_index]["owner"] = PUMP_PROGRAM_ID
            elif self.failure == "pool_target_mismatch":
                values = [
                    {"address": address, "account": account}
                    for address, account in zip(addresses, values, strict=True)
                ]
                values[target_index]["address"] = FIXTURE["candidates"][-1][0]
            payload["value"] = values
        elif (
            self.failure == "holder_failure"
            and method == "getTokenLargestAccounts"
            and str(params[0]) == self.target_mint
        ):
            payload["value"] = [{
                "address": self.target_pool, "amount": "900", "decimals": 0
            }]
        return TransportResponse(
            payload, response.bytes_used, response.operation_kind,
            response.endpoint_role,
        )


class _MintBatchScenarioNetwork(_CanonicalMockNetworkTransport):
    def __init__(self, count: int, transform) -> None:
        super().__init__(count)
        self.transform = transform

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        if endpoint_role != "CANDIDATE_MINT_ACCOUNT_BATCH":
            return super().rpc_json(
                rpc_url=rpc_url, method=method, params=params,
                timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
                endpoint_role=endpoint_role,
            )
        addresses = list(params[0])
        defaults = [
            _spl_mint_account()
            if self.mint_ordinals[address] % 2 == 0
            else _token_2022_mint_account(with_extension=True)
            for address in addresses
        ]
        values = self.transform(addresses, defaults)
        return self._result(
            {"context": {"slot": 420_000_000}, "value": values},
            method, endpoint_role,
        )


class _StaticFailureAdapter:
    def __init__(self, source_name: str, request_kind: str, failure_type: str) -> None:
        self.source_name = source_name
        self.request_kind = request_kind
        self.failure_type = failure_type
        self.call_count = 0

    def execute(self, context):
        assert context.governor_approved
        self.call_count += 1
        return NormalizedSourceResult(
            source_name=self.source_name,
            request_kind=self.request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type=self.failure_type,
            failure_message=self.failure_type,
        )


def _db() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temp = tempfile.TemporaryDirectory()
    path = Path(temp.name) / "integration.sqlite3"
    apply_migrations(path)
    return temp, path


def _preflight(path: Path) -> dict:
    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": str(path.resolve()),
        "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "latest_migration": "049_candidate_acquisition_integration.sql",
        "integrity": "ok",
        "foreign_key_violations": 0,
        "git_provenance": {
            "git_head": "164dcd5e570d7de19a84bfa651e0320850f03348",
            "git_tracked_tree_clean": True,
        },
    }


def _candidate_rows(count: int) -> list[dict]:
    return [
        {
            "mint": mint,
            "pool": pool,
            "pool_program_id": POOL_PROGRAM,
            "base_mint": mint,
            "quote_mint": WSOL_MINT,
            "token_program_id": TOKEN_PROGRAM_ID,
            "venue_label": "FROZEN_SUPPORTED_POOL",
            "lineage_claim": "UNKNOWN_ORIGIN",
        }
        for mint, pool, _ in FIXTURE["candidates"][:count]
    ]


def _adapter(source: str, payload: dict, *, kind: str = FIXTURE_SUCCESS):
    return build_fixture_source_adapter(
        source, fixture_kind=kind, fixture_payload=payload
    )


def _operation(
    source: str,
    request_kind: str,
    rows: list[dict],
    facts: dict,
    *,
    required: bool = True,
    transport_operations: int = 1,
    cursor: dict | None = None,
    fixture_kind: str = FIXTURE_SUCCESS,
    expires_at: str = EXPIRES,
    observed_at: str = NOW,
    observation_scope: str = "CANDIDATE",
    phase: str = "NOMINATION",
) -> AcquisitionSourceOperation:
    observations = []
    for row in rows:
        observations.append({
            **row,
            "facts": dict(facts),
            "observed_at": observed_at,
            "expires_at": expires_at,
        })
    payload = {
        "candidate_observations": observations,
        "underlying_operation_count": transport_operations,
        **({"response_bytes": 0} if transport_operations == 0 else {}),
    }
    return AcquisitionSourceOperation(
        source_name=source,
        request_kind=request_kind,
        adapter=_adapter(source, payload, kind=fixture_kind),
        required=required,
        expected_transport_operations=transport_operations,
        cursor_range=cursor,
        observation_scope=observation_scope,
        phase=phase,
    )


def _dex_nomination_operation(
    rows: list[dict], *, transport_operations: int = 1, stale: bool = False
) -> AcquisitionSourceOperation:
    pairs = [
        {
            "chainId": "solana",
            "pairAddress": row["pool"],
            "baseToken": {"address": row["mint"], "symbol": "MEME"},
            "liquidity": {"usd": 10_000.0},
            "volume": {"m5": 1_000.0, "h1": 4_000.0},
            "txns": {"m5": {"buys": 2, "sells": 1}},
            "pairCreatedAt": 1_700_000_000_000,
        }
        for row in rows
    ]
    adapter = build_dexscreener_adapter(
        enabled=True,
        fixture_transport=dexscreener_fixture_success_transport(
            {"pairs": pairs, "fixture_stale": stale}
        ),
    )
    return AcquisitionSourceOperation(
        source_name="dexscreener",
        request_kind="candidate_nomination",
        adapter=adapter,
        required=False,
        expected_transport_operations=transport_operations,
    )


def _gecko_nomination_operation(
    rows: list[dict], *, failure: bool = False
) -> AcquisitionSourceOperation:
    payload = {
        "data": [
            {
                "id": f"solana_{row['pool']}",
                "attributes": {
                    "chain": "solana",
                    "address": row["pool"],
                    "base_token_address": row["mint"],
                    "reserve_in_usd": 10_000.0,
                    "volume_usd": {"m5": 1_000.0, "h1": 4_000.0},
                    "transactions": {"m5": {"buys": 2, "sells": 1}},
                    "pool_created_at": "2026-07-29T10:00:00+00:00",
                },
            }
            for row in rows
        ]
    }
    transport = (
        geckoterminal_fixture_failure_transport("optional outage")
        if failure
        else geckoterminal_fixture_success_transport(payload)
    )
    return AcquisitionSourceOperation(
        source_name="geckoterminal",
        request_kind="candidate_nomination",
        adapter=build_geckoterminal_adapter(
            enabled=True, fixture_transport=transport
        ),
        required=False,
    )


def _cursor(indexed: str, *, continuity: str = "CONTIGUOUS") -> dict:
    return {
        "indexed_address": indexed,
        "contract_pin": "9c82f61cb711b044a17f770ab8ce9f9bdf78f333",
        "decoder_version": "candidate-integration-v1",
        "direction": "BACKWARD",
        "start_slot": None,
        "start_signature": None,
        "end_slot": 420_000_000,
        "end_signature": f"sig-{indexed}",
        "continuity_state": continuity,
        "cursor_advanced": continuity == "CONTIGUOUS",
        "unresolved_reason": None if continuity == "CONTIGUOUS" else continuity,
    }


def _owner(
    count: int,
    *,
    optional_gecko_failure: bool = False,
    required_pool_failure: str | None = None,
    cursor_continuity: str = "CONTIGUOUS",
    stale_first: bool = False,
    identity_conflict: bool = False,
) -> FrozenAcquisitionTransportOwner:
    rows = _candidate_rows(count)
    dex_rows = deepcopy(rows)
    if identity_conflict and dex_rows:
        dex_rows[0]["pool"] = FIXTURE["candidates"][-1][1]
    operations: list[AcquisitionSourceOperation] = [
        _dex_nomination_operation(
            dex_rows, stale=stale_first
        ),
        _gecko_nomination_operation(
            rows[:1], failure=optional_gecko_failure
        ),
        _operation(
            "solana_rpc", "pumpfun_create_index_signature_page", [], {},
            cursor=_cursor("pump-create-index", continuity=cursor_continuity),
        ),
        _operation(
            "solana_rpc", "pumpfun_migration_signature_page", [], {},
            cursor=_cursor("pump-program", continuity=cursor_continuity),
            required=False, observation_scope="GLOBAL_OPTIONAL",
        ),
        _operation(
            "solana_rpc", "candidate_mint_account_batch", rows,
            {"mint_status": "PASS", "token_program_status": "PASS"},
        ),
    ]
    pool_op = _operation(
        "solana_rpc", "pumpswap_pool_account_batch", rows,
        {"pool_status": "PASS"},
    )
    if required_pool_failure:
        pool_op = AcquisitionSourceOperation(
            source_name="solana_rpc",
            request_kind="pumpswap_pool_account_batch",
            adapter=_StaticFailureAdapter(
                "solana_rpc", "pumpswap_pool_account_batch", required_pool_failure
            ),
            required=True,
        )
    operations.append(pool_op)
    operations.extend((
        _operation(
            "solana_rpc", "candidate_pump_migration_signature_lookup", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
        _operation(
            "solana_rpc", "candidate_pump_migration_transaction", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
        _operation(
            "solana_rpc", "candidate_pumpswap_pool_verification", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
    ))
    for row in rows:
        operations.append(_operation(
            "solana_rpc", "holder_concentration_reference", [row],
            {"holder_status": "PASS"}, transport_operations=2,
        ))
        operations.append(_operation(
            "goplus", "safety_reference", [row], {"safety_status": "PASS"},
            required=False,
        ))
    return FrozenAcquisitionTransportOwner(tuple(operations))


def _run(
    path: Path,
    *,
    mode: str,
    execution_id: str,
    owner: FrozenAcquisitionTransportOwner,
    renewal_hook=None,
    cancellation_probe=None,
    now: str = NOW,
) -> dict:
    return run_candidate_acquisition_integration(
        path,
        mode=mode,
        operator_approved=True,
        transport_owner=owner,
        preflight=_preflight(path),
        execution_id=execution_id,
        owner_id=f"owner:{execution_id}",
        now=now,
        renewal_hook=renewal_hook,
        cancellation_probe=cancellation_probe,
    )


def _seed_lease(path: Path, *, execution_id: str, expires_at: str) -> None:
    integration_id = f"seed-integration:{execution_id}"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_integrations(
                   integration_id,execution_id,mode,selection_capacity,owner_id,
                   authorization_confirmed,preflight_hash,policy_json,
                   integration_state,started_at,created_at,updated_at
               ) VALUES (?,?,?,2,?,1,?,'{}','RUNNING',?,?,?)""",
            (
                integration_id, execution_id, MODE_N2, f"owner:{execution_id}",
                "a" * 64, NOW, NOW, NOW,
            ),
        )
        connection.execute(
            """INSERT INTO printer_candidate_acquisition_leases(
                   lease_id,integration_id,execution_id,owner_id,mode,lease_state,
                   heartbeat_at,lease_expires_at,created_at,updated_at
               ) VALUES (?,?,?,?,?,'ACTIVE',?,?,?,?)""",
            (
                f"seed-lease:{execution_id}", integration_id, execution_id,
                f"owner:{execution_id}", MODE_N2, NOW, expires_at, NOW, NOW,
            ),
        )


@pytest.mark.parametrize(
    ("mode", "count", "expected"),
    ((MODE_N2, 4, 2), (MODE_N7, 14, 7)),
)
def test_offline_end_to_end_exact_modes(mode: str, count: int, expected: int) -> None:
    temp, path = _db()
    try:
        report = _run(
            path, mode=mode, execution_id=f"e2e-{expected}", owner=_owner(count)
        )
        assert report["status"] == "COMPLETED"
        assert report["selected_count"] == expected
        assert report["scheduler_jobs_created"] == report["governed_requests_used"]
        assert report["transport_operations_used"] > report["governed_requests_used"]
        assert report["projection_count"] == (2 if expected == 2 else 0)
        assert report["runtime_handoff_count"] == 0
        assert report["lifecycle_started"] is False
        assert report["active_capacity_lock"] == 2
        assert report["active_lease_count"] == 0
        assert report["scheduler_residue_terminalized"] == 0
        assert not any(report["forbidden_table_deltas"].values())
        assert report["integrity"] == "ok"
        assert report["foreign_key_violations"] == 0
        with sqlite3.connect(path) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_transport_operations"
            ).fetchone()[0] == report["transport_operations_used"]
            assert connection.execute(
                "SELECT COALESCE(SUM(bytes_used),0) "
                "FROM printer_candidate_acquisition_transport_operations"
            ).fetchone()[0] == report["bytes_used"]
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*),MIN(cursor_version),MAX(cursor_version) "
                "FROM printer_candidate_acquisition_cursors"
            ).fetchone() == (2, 1, 1)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"e2e-{expected}"
        ) == report
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, report["manifest_id"])
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("cli_mode", "mode", "count", "expected", "expected_jobs", "expected_calls"),
    (
        (CLI_MODE_N2, MODE_N2, 4, 2, 23, 19),
        (CLI_MODE_N7, MODE_N7, 14, 7, 48, 35),
    ),
)
def test_public_command_dispatches_canonical_offline_path(
    capsys, monkeypatch, cli_mode: str, mode: str, count: int, expected: int,
    expected_jobs: int, expected_calls: int,
) -> None:
    temp, path = _db()
    try:
        seen = {}
        network = _CanonicalMockNetworkTransport(count)
        real_run = command.run_candidate_acquisition_only
        def capture_owner(**kwargs):
            seen["owner"] = kwargs["transport_owner"]
            return real_run(**kwargs)
        monkeypatch.setattr(command, "run_candidate_acquisition_only", capture_owner)
        rc = command.main(
            [cli_mode, "--operator-approved"],
            acquisition_environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?key=secret"},
            acquisition_one_shot_transport=network,
            acquisition_preflight=_preflight(path),
            acquisition_execution_id=f"cli-{expected}",
            acquisition_now=NOW,
            acquisition_db_path=path,
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["mode"] == mode
        assert payload["selected_count"] == expected, json.dumps(payload, indent=2)
        assert payload["projection_count"] == (2 if expected == 2 else 0)
        assert payload["runtime_handoff_count"] == 0
        assert payload["lifecycle_started"] is False
        assert payload["scheduler_jobs_created"] == expected_jobs
        assert payload["scheduler_jobs_created"] == payload["governed_requests_used"]
        assert payload["transport_operations_used"] == expected_calls
        assert payload["transport_operations_used"] == len(network.calls)
        assert payload["active_lease_count"] == 0
        assert payload["scheduler_residue_terminalized"] == 0
        assert not any(payload["forbidden_table_deltas"].values())
        assert isinstance(seen["owner"], LiveCandidateAcquisitionTransportOwner)
        assert "secret" not in json.dumps(payload)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"cli-{expected}"
        ) == payload
        call_count = len(network.calls)
        assert command.main(
            [cli_mode, "--operator-approved"],
            acquisition_environment={
                "PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?key=secret"
            },
            acquisition_one_shot_transport=network,
            acquisition_preflight=_preflight(path),
            acquisition_execution_id=f"cli-{expected}",
            acquisition_now=NOW,
            acquisition_db_path=path,
        ) == 0
        assert json.loads(capsys.readouterr().out) == payload
        assert len(network.calls) == call_count
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, payload["manifest_id"])
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("environment", "reason"),
    (
        ({}, "ACQUISITION_SOLANA_RPC_URL_REQUIRED"),
        ({"PRINTER_SOLANA_RPC_URL": "not a url"}, "ACQUISITION_SOLANA_RPC_URL_MALFORMED"),
        ({"PRINTER_SOLANA_RPC_URL": "http://rpc.example.invalid"}, "ACQUISITION_SOLANA_RPC_HTTPS_REQUIRED"),
        ({"PRINTER_SOLANA_RPC_URL": "https://user:secret@rpc.example.invalid"}, "ACQUISITION_SOLANA_RPC_URL_MALFORMED"),
    ),
)
def test_public_command_blocks_invalid_live_configuration_before_preflight(
    capsys, monkeypatch, environment: dict[str, str], reason: str
) -> None:
    monkeypatch.setattr(
        command, "build_activation_preflight",
        lambda **_kwargs: pytest.fail("preflight must not run for invalid transport configuration"),
    )
    rc = command.main(
        [CLI_MODE_N2, "--operator-approved"], acquisition_environment=environment
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error_message"] == reason
    assert payload["action_run_id"] is None
    assert payload["source_calls"] == 0
    assert payload["scheduler_runtime_calls"] == 0
    assert "secret" not in json.dumps(payload)


def test_public_command_requires_approval_before_configuration(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        command, "build_live_candidate_acquisition_transport_owner",
        lambda **_kwargs: pytest.fail("configuration must not load before approval"),
    )
    assert command.main([CLI_MODE_N2]) == 1
    assert json.loads(capsys.readouterr().err)["error_message"] == (
        "EXPLICIT_OPERATOR_APPROVAL_REQUIRED"
    )


def test_unresolved_required_transport_blocks_during_construction() -> None:
    with pytest.raises(
        LiveAcquisitionConfigurationError,
        match="ACQUISITION_REQUIRED_TRANSPORT_UNRESOLVED",
    ):
        build_live_candidate_acquisition_transport_owner(
            environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid"},
            transport=object(),
        )


def test_one_shot_transport_closes_response_and_reports_exact_bytes(monkeypatch) -> None:
    class Response:
        closed = False
        def __enter__(self): return self
        def __exit__(self, *_args): self.closed = True
        def read(self, _limit): return b'{"ok":true}'
    response = Response(); calls = []
    monkeypatch.setattr(
        live_transport.url_request, "urlopen",
        lambda _request, timeout: calls.append(timeout) or response,
    )
    result = UrllibCandidateAcquisitionOneShotTransport().http_json(
        url="https://provider.example.invalid/path", headers={}, timeout_seconds=3.0,
        byte_ceiling=100, endpoint_role="FIXED_PROVIDER_ROLE",
    )
    assert result.payload == {"ok": True}
    assert result.bytes_used == len(b'{"ok":true}')
    assert response.closed is True
    assert calls == [3.0]


@pytest.mark.parametrize(
    ("body", "expected"),
    ((b"{", "SOURCE_MALFORMED"), (b"x" * 11, "RESPONSE_BYTE_CEILING")),
)
def test_one_shot_transport_malformed_and_byte_failure_are_redacted(
    monkeypatch, body: bytes, expected: str
) -> None:
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self, _limit): return body
    monkeypatch.setattr(live_transport.url_request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().http_json(
            url="https://provider.example.invalid/path?api-key=secret", headers={},
            timeout_seconds=1.0, byte_ceiling=10, endpoint_role="REDACTED_ROLE",
        )
    assert caught.value.code == expected
    assert "secret" not in str(caught.value)
    assert "provider.example" not in str(caught.value)


def test_one_shot_transport_timeout_has_one_attempt_and_no_url_secret(monkeypatch) -> None:
    calls = []
    def timeout(*_args, **_kwargs):
        calls.append(1)
        raise TimeoutError("api-key=secret")
    monkeypatch.setattr(live_transport.url_request, "urlopen", timeout)
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().rpc_json(
            rpc_url="https://rpc.example.invalid/path?api-key=secret",
            method="getMultipleAccounts", params=[[]], timeout_seconds=1.0,
            byte_ceiling=100, endpoint_role="RPC_BATCH",
        )
    assert caught.value.code == "SOURCE_TIMEOUT"
    assert calls == [1]
    assert "secret" not in str(caught.value)


def test_one_shot_transport_auth_failure_closes_and_accounts_redacted_body(
    monkeypatch,
) -> None:
    body = b"credential=secret"
    failure = live_transport.url_error.HTTPError(
        "https://rpc.example.invalid/path?api-key=secret", 401, "unauthorized", {},
        io.BytesIO(body),
    )
    monkeypatch.setattr(
        live_transport.url_request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )
    with pytest.raises(LiveAcquisitionTransportError) as caught:
        UrllibCandidateAcquisitionOneShotTransport().rpc_json(
            rpc_url="https://rpc.example.invalid/path?api-key=secret",
            method="getMultipleAccounts", params=[[]], timeout_seconds=1.0,
            byte_ceiling=100, endpoint_role="RPC_BATCH",
        )
    assert caught.value.code == "SOURCE_AUTH_UNAVAILABLE"
    assert caught.value.bytes_used == len(body)
    assert caught.value.operation_kind == "getMultipleAccounts"
    assert failure.fp is None or failure.fp.closed
    assert "secret" not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(("mode", "expected_cap"), ((MODE_N2, 4), (MODE_N7, 14)))
def test_live_owner_declares_same_approved_source_plan(mode: str, expected_cap: int) -> None:
    owner = build_live_candidate_acquisition_transport_owner(
        environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?api-key=secret"}
    )
    operations = owner.operations(mode=mode, policy=MODE_POLICIES[mode], execution_id="plan")
    assert [item.request_kind for item in operations[:4]] == [
        "candidate_nomination", "candidate_nomination",
        "candidate_market_batch", "candidate_market_batch",
    ]
    assert all(item.expected_transport_operations == 0 for item in operations[2:4])
    declared = {(item.source_name, item.request_kind) for item in operations}
    assert {
        ("dexscreener", "candidate_nomination"),
        ("geckoterminal", "candidate_nomination"),
        ("solana_rpc", "pumpfun_create_index_signature_page"),
        ("solana_rpc", "pumpfun_migration_signature_page"),
        ("solana_rpc", "candidate_mint_account_batch"),
        ("solana_rpc", "pumpswap_pool_account_batch"),
        ("solana_rpc", "candidate_pump_migration_signature_lookup"),
        ("solana_rpc", "candidate_pump_migration_transaction"),
        ("solana_rpc", "candidate_pumpswap_pool_verification"),
        ("solana_rpc", "holder_concentration_reference"),
        ("goplus", "safety_reference"),
    }.issubset(declared)
    assert all(source not in {"dextools", "pumpportal", "birdeye"} for source, _ in declared)
    holders = [item for item in operations if item.request_kind == "holder_concentration_reference"]
    goplus_ops = [item for item in operations if item.request_kind == "safety_reference"]
    expected_selection = MODE_POLICIES[mode]["selection_capacity"]
    candidate_limit = MODE_POLICIES[mode]["candidate_limit"]
    create_transactions = [
        item for item in operations if item.request_kind == "pumpfun_create_index_transaction"
    ]
    migration_transactions = [
        item for item in operations if item.request_kind == "pumpfun_migration_transaction"
    ]
    assert len(create_transactions) == expected_selection
    assert len(migration_transactions) == expected_selection
    assert all(not item.required for item in migration_transactions)
    assert all(
        not item.required
        for item in operations
        if item.request_kind == "pumpfun_migration_signature_page"
    )
    candidate_lookups = [
        item for item in operations
        if item.request_kind == "candidate_pump_migration_signature_lookup"
    ]
    candidate_transactions = [
        item for item in operations
        if item.request_kind == "candidate_pump_migration_transaction"
    ]
    expected_candidate_verifications = 1
    assert (
        len(candidate_lookups)
        == len(candidate_transactions)
        == expected_candidate_verifications
    )
    assert all(item.phase == "ENRICHMENT" for item in candidate_lookups)
    # Fixed source and Scheduler ceilings remain unchanged. N7 uses exactly the
    # 30-request Solana minute; N2 remains inside it.
    solana_operations = [item for item in operations if item.source_name == "solana_rpc"]
    expected_holders = candidate_limit if expected_selection == 2 else expected_selection
    assert len(holders) == expected_holders
    assert len(goplus_ops) <= candidate_limit
    assert all(item.expected_transport_operations == 2 for item in holders)
    assert all(item.phase == "ENRICHMENT" for item in holders + goplus_ops)
    assert len(solana_operations) <= 30
    assert len(operations) <= MODE_POLICIES[mode]["scheduler_job_ceiling"]
    assert sum(item.expected_transport_operations for item in operations) <= (
        MODE_POLICIES[mode]["transport_operation_ceiling"]
    )
    # No operation owns a provider loop. The only two-call composites are the
    # fixed Dex nomination/market pair and fixed holder largest/supply pair.
    assert max(item.expected_transport_operations for item in operations) == 2
    pool_work = next(
        item for item in operations
        if item.request_kind == "pumpswap_pool_account_batch"
    )
    assert pool_work.cursor_range is None
    assert owner.configuration.redacted_rpc_host == "rpc.example.invalid"
    assert "secret" not in repr(owner.configuration)


def test_response_byte_and_row_ceilings_fail_closed() -> None:
    temp_b, path_b = _db(); temp_r, path_r = _db()
    try:
        byte_ops = list(_owner(4).frozen_operations)
        byte_ops[0] = AcquisitionSourceOperation(
            source_name="dexscreener", request_kind="candidate_nomination",
            required=False, expected_transport_operations=1,
            adapter=_adapter("dexscreener", {
                "candidate_observations": [], "underlying_operation_count": 1,
                "response_bytes": 16 * 1024 * 1024 + 1,
            }),
        )
        byte_report = _run(path_b, mode=MODE_N2, execution_id="byte-ceiling",
                           owner=FrozenAcquisitionTransportOwner(tuple(byte_ops)))
        assert byte_report["first_terminal_cause"] == "RESPONSE_BYTE_CEILING"

        row_ops = list(_owner(4).frozen_operations)
        row_ops[0] = _operation(
            "dexscreener", "candidate_nomination",
            [{"mint": f"mint-{index}", "pool": f"pool-{index}"} for index in range(65)],
            {"market_status": "PASS"}, required=False,
        )
        row_report = _run(path_r, mode=MODE_N2, execution_id="row-ceiling",
                          owner=FrozenAcquisitionTransportOwner(tuple(row_ops)))
        assert row_report["first_terminal_cause"] == "OBSERVATION_ROW_CEILING"
    finally:
        temp_b.cleanup(); temp_r.cleanup()


@pytest.mark.parametrize(
    "failure_type",
    ("SOURCE_AUTH_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_MALFORMED"),
)
def test_required_source_failure_categories_do_not_retry(failure_type: str) -> None:
    temp, path = _db()
    try:
        report = _run(path, mode=MODE_N2, execution_id=f"failure-{failure_type}",
                      owner=_owner(4, required_pool_failure=failure_type))
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        assert report["automatic_retry_created"] is False
        assert report["successor_created"] is False
        assert report["restart_created"] is False
    finally:
        temp.cleanup()


def test_authorization_is_required_before_any_write() -> None:
    temp, path = _db()
    try:
        before = path.read_bytes()
        with pytest.raises(
            CandidateAcquisitionIntegrationError,
            match="EXPLICIT_OPERATOR_APPROVAL_REQUIRED",
        ):
            run_candidate_acquisition_integration(
                path, mode=MODE_N2, operator_approved=False,
                transport_owner=_owner(4), preflight=_preflight(path),
                execution_id="unauthorized", owner_id="owner", now=NOW,
            )
        assert path.read_bytes() == before

        invalid = _preflight(path)
        invalid["database_sha256"] = "0" * 64
        before = path.read_bytes()
        with pytest.raises(
            CandidateAcquisitionIntegrationError,
            match="PREFLIGHT_DATABASE_HASH_MISMATCH",
        ):
            run_candidate_acquisition_integration(
                path, mode=MODE_N2, operator_approved=True,
                transport_owner=_owner(4), preflight=invalid,
                execution_id="bad-preflight", owner_id="owner", now=NOW,
            )
        assert path.read_bytes() == before
    finally:
        temp.cleanup()


def test_concurrent_lease_blocks_cleanly_and_expired_lease_recovers_once() -> None:
    temp_h, path_h = _db()
    temp_e, path_e = _db()
    try:
        _seed_lease(
            path_h, execution_id="foreign-active",
            expires_at="2026-07-29T13:00:00+00:00",
        )
        blocked = _run(
            path_h, mode=MODE_N2, execution_id="lease-blocked", owner=_owner(4)
        )
        assert blocked["status"] == "BLOCKED"
        assert blocked["first_terminal_cause"] == "ACQUISITION_LEASE_ALREADY_HELD"
        assert blocked["lease_cleanup"]["lease_acquired"] is False
        with sqlite3.connect(path_h) as connection:
            assert connection.execute(
                "SELECT integration_state FROM printer_candidate_acquisition_integrations "
                "WHERE execution_id='lease-blocked'"
            ).fetchone()[0] == "TERMINAL"

        _seed_lease(
            path_e, execution_id="foreign-expired",
            expires_at="2026-07-29T11:00:00+00:00",
        )
        recovered = _run(
            path_e, mode=MODE_N2, execution_id="lease-recovered", owner=_owner(4)
        )
        assert recovered["status"] == "COMPLETED"
        assert recovered["active_lease_count"] == 0
        with sqlite3.connect(path_e) as connection:
            row = connection.execute(
                """SELECT terminal_status,first_terminal_cause
                   FROM printer_candidate_acquisition_integrations
                   WHERE execution_id='foreign-expired'"""
            ).fetchone()
            assert row == ("BLOCKED", "LEASE_EXPIRED_RECOVERED")
    finally:
        temp_h.cleanup(); temp_e.cleanup()


def test_n_minus_one_is_honest_insufficient_pool() -> None:
    temp, path = _db()
    try:
        report = _run(path, mode=MODE_N2, execution_id="n-minus-one", owner=_owner(1))
        assert report["status"] == "BLOCKED"
        assert report["foundation_report"]["failure_family"] == "INSUFFICIENT_ELIGIBLE_POOL"
        assert report["manifest_id"] is None
    finally:
        temp.cleanup()


def test_optional_outage_degrades_but_required_outage_stops() -> None:
    temp_a, path_a = _db()
    temp_b, path_b = _db()
    try:
        optional = _run(
            path_a, mode=MODE_N2, execution_id="optional-outage",
            owner=_owner(4, optional_gecko_failure=True),
        )
        assert optional["status"] == "COMPLETED"
        assert optional["foundation_report"]["source_failures"]
        required = _run(
            path_b, mode=MODE_N2, execution_id="required-outage",
            owner=_owner(4, required_pool_failure="rpc_transport_failure"),
        )
        assert required["status"] == "BLOCKED"
        assert required["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        assert required["manifest_id"] is None
    finally:
        temp_a.cleanup(); temp_b.cleanup()


def test_budget_gap_unsupported_identity_stale_and_shortage_are_distinct() -> None:
    cases = (
        ("gap", _owner(4, cursor_continuity="GAPPED"), "CURSOR_CONTINUITY_GAPPED"),
        (
            "unsupported", _owner(4, required_pool_failure="unsupported_contract_layout"),
            "UNSUPPORTED_CONTRACT",
        ),
    )
    for execution_id, owner, cause in cases:
        temp, path = _db()
        try:
            report = _run(path, mode=MODE_N2, execution_id=execution_id, owner=owner)
            assert report["status"] == "BLOCKED"
            assert report["first_terminal_cause"] == cause
            assert report["manifest_id"] is None
            if execution_id == "gap":
                with sqlite3.connect(path) as connection:
                    persisted = connection.execute(
                        """SELECT COUNT(*) FROM printer_candidate_acquisition_work
                           WHERE json_extract(cursor_range_json,'$.continuity_state')='GAPPED'"""
                    ).fetchone()[0]
                    assert persisted == 2
                    assert connection.execute(
                        "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors"
                    ).fetchone()[0] == 0
        finally:
            temp.cleanup()

    temp, path = _db()
    try:
        ops = list(_owner(4).frozen_operations)
        ops.insert(1, ops[0])
        report = _run(
            path, mode=MODE_N2, execution_id="budget",
            owner=FrozenAcquisitionTransportOwner(tuple(ops)),
        )
        assert report["first_terminal_cause"] == "SOURCE_REQUEST_BUDGET_EXHAUSTED"
        assert report["manifest_id"] is None
    finally:
        temp.cleanup()

    temp_i, path_i = _db()
    temp_s, path_s = _db()
    try:
        identity = _run(
            path_i, mode=MODE_N2, execution_id="identity",
            owner=_owner(2, identity_conflict=True),
        )
        assert identity["status"] == "BLOCKED"
        assert identity["foundation_report"]["failure_family"] == "IDENTITY_MERGE_FAILURE"
        stale = _run(
            path_s, mode=MODE_N2, execution_id="stale",
            owner=_owner(2, stale_first=True),
        )
        assert stale["status"] == "BLOCKED"
        assert stale["manifest_id"] is None
        assert stale["foundation_report"]["stale_or_expired_evidence_count"] >= 1
    finally:
        temp_i.cleanup(); temp_s.cleanup()


def test_cancellation_renewal_failure_and_idempotent_replay_release_lease() -> None:
    temp_c, path_c = _db()
    temp_r, path_r = _db()
    temp_i, path_i = _db()
    try:
        cancelled = _run(
            path_c, mode=MODE_N2, execution_id="cancelled", owner=_owner(4),
            cancellation_probe=lambda ordinal: "operator stop" if ordinal == 1 else None,
        )
        assert cancelled["status"] == "CANCELLED"
        assert cancelled["first_terminal_cause"] == "ACQUISITION_CANCELLED"
        assert cancelled["active_lease_count"] == 0

        def fail_renewal(ordinal: int) -> None:
            if ordinal == 1:
                raise CandidateAcquisitionIntegrationError("LEASE_RENEWAL_UNCONFIRMED")

        renewal = _run(
            path_r, mode=MODE_N2, execution_id="renewal", owner=_owner(4),
            renewal_hook=fail_renewal,
        )
        assert renewal["status"] == "BLOCKED"
        assert renewal["first_terminal_cause"] == "LEASE_RENEWAL_UNCONFIRMED"
        assert renewal["active_lease_count"] == 0

        first = _run(path_i, mode=MODE_N2, execution_id="idempotent", owner=_owner(4))
        with sqlite3.connect(path_i) as connection:
            source_before = connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
            jobs_before = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]
        second = _run(path_i, mode=MODE_N2, execution_id="idempotent", owner=_owner(4))
        assert second == first
        with sqlite3.connect(path_i) as connection:
            assert connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0] == source_before
            assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == jobs_before
    finally:
        temp_c.cleanup(); temp_r.cleanup(); temp_i.cleanup()


def test_atomic_selection_cooldown_recheck_blocks_manifest() -> None:
    temp, path = _db()
    try:
        mint, pool, _ = FIXTURE["candidates"][0]
        with sqlite3.connect(path) as connection:
            connection.execute(
                """INSERT INTO printer_selection_rotation_state(
                       token_mint,pair_address,last_selected_batch_id,
                       last_selected_batch_seq,last_selected_at,
                       last_evidence_fingerprint_json,selection_count,created_at,updated_at
                   ) VALUES (?,?,?,?,?,'{}',1,?,?)""",
                (mint, pool, "prior", 1, NOW, NOW, NOW),
            )
        report = _run(
            path, mode=MODE_N2, execution_id="cooldown", owner=_owner(2)
        )
        assert report["status"] == "BLOCKED"
        assert report["manifest_id"] is None
        assert report["foundation_report"]["exclusions_by_funnel_stage"]["IDENTITY_AVAILABLE"] >= 1
    finally:
        temp.cleanup()


def test_atomic_active_tracking_recheck_blocks_manifest() -> None:
    temp, path = _db()
    try:
        mint, pool, _ = FIXTURE["candidates"][0]
        with sqlite3.connect(path) as connection:
            token_id = connection.execute(
                "INSERT INTO printer_tokens(token_mint,token_status) "
                "VALUES (?,'TRACK_NORMAL')",
                (mint,),
            ).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) "
                "VALUES (?,?,?)",
                (token_id, pool, mint),
            ).lastrowid
            connection.execute(
                """INSERT INTO printer_tracking_queue(
                       token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                       next_check_at,last_checked_at,queue_status,source_status,
                       data_quality_label
                   ) VALUES (?,?,'TRACK_NORMAL','REFRESH','active fixture',?,?,
                             'READY','COMPLETE','CLEAN_DATA')""",
                (token_id, pair_id, NOW, NOW),
            )
        report = _run(
            path, mode=MODE_N2, execution_id="active-tracking", owner=_owner(2)
        )
        assert report["status"] == "BLOCKED"
        assert report["manifest_id"] is None
        assert report["foundation_report"]["exclusions_by_funnel_stage"][
            "IDENTITY_AVAILABLE"
        ] >= 1
    finally:
        temp.cleanup()


def _dispatch(capsys, path, cli_mode: str, network, execution_id: str) -> dict:
    rc = command.main(
        [cli_mode, "--operator-approved"],
        acquisition_environment={
            "PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid/path?key=secret"
        },
        acquisition_one_shot_transport=network,
        acquisition_preflight=_preflight(path),
        acquisition_execution_id=execution_id,
        acquisition_now=NOW,
        acquisition_db_path=path,
    )
    assert rc == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    ("cli_mode", "count", "expected"),
    ((CLI_MODE_N2, 4, 2), (CLI_MODE_N7, 7, 7)),
)
def test_live_shaped_end_to_end_roles_admit_exact_n(
    capsys, cli_mode: str, count: int, expected: int
) -> None:
    """Public CLI proves every exact-present-pool role without synthesis."""
    temp, path = _db()
    try:
        network = _LiveShapedAdmissionNetwork(count)
        payload = _dispatch(
            capsys, path, cli_mode, network, f"live-shaped-roles-{expected}"
        )
        assert payload["status"] == "COMPLETED"
        assert payload["foundation_report"]["certificates_admitted"] >= expected
        assert payload["selected_count"] == expected
        assert payload["projection_count"] == (2 if expected == 2 else 0)
        assert payload["runtime_handoff_count"] == 0
        assert payload["scheduler_jobs_created"] == payload["governed_requests_used"]
        assert payload["transport_operations_used"] == len(network.calls)
        assert not any(payload["forbidden_table_deltas"].values())
        with sqlite3.connect(path) as connection:
            roles = {
                str(row[0])
                for row in connection.execute(
                    "SELECT json_extract(facts_json,'$.pool_role') "
                    "FROM printer_candidate_source_observations "
                    "WHERE json_extract(facts_json,'$.pool_status')='PASS'"
                )
                if row[0] is not None
            }
            lineages = {
                str(row[0])
                for row in connection.execute(
                    "SELECT lineage_state FROM printer_candidate_identities"
                )
            }
            quote_count = connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_identities "
                "WHERE quote_mint=?",
                (WSOL_MINT,),
            ).fetchone()[0]
            token_programs = {
                str(row[0])
                for row in connection.execute(
                    "SELECT token_program_id FROM printer_candidate_identities"
                )
            }
            source_quote_counts = dict(connection.execute(
                """SELECT source_name,COUNT(*)
                     FROM printer_candidate_source_observations
                    WHERE source_name IN ('dexscreener','geckoterminal')
                      AND quote_mint=?
                    GROUP BY source_name""",
                (WSOL_MINT,),
            ))
        assert {
            "PUMP_BONDING_CURVE", "PUMPSWAP_AMM_POOL", "GENERIC_AMM_POOL"
        } <= roles
        assert {
            "PUMP_ORIGIN_CONFIRMED", "PUMP_GRADUATION_CONFIRMED",
            "NON_PUMP_POOL_CONFIRMED",
        } <= lineages
        assert quote_count >= expected
        assert source_quote_counts["dexscreener"] >= expected
        assert source_quote_counts["geckoterminal"] >= 1
        assert payload["pre_foundation_funnel"]["cross_source_overlap_count"] >= 2
        assert {TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID} <= token_programs
        calls = len(network.calls)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"live-shaped-roles-{expected}"
        ) == payload
        assert len(network.calls) == calls
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, payload["manifest_id"])
    finally:
        temp.cleanup()


def test_live_shaped_sequential_established_cursor_state_completes_n2(capsys) -> None:
    temp, path = _db()
    try:
        first = _dispatch(
            capsys, path, CLI_MODE_N2, _LiveShapedAdmissionNetwork(4),
            "live-shaped-sequential-1",
        )
        second_network = _LiveShapedAdmissionNetwork(4)
        second = _dispatch(
            capsys, path, CLI_MODE_N2, second_network,
            "live-shaped-sequential-2",
        )
        assert first["status"] == second["status"] == "COMPLETED", json.dumps(
            second, indent=2
        )
        assert first["cursor_bootstrap_namespaces"] == 2
        assert second["cursor_heads_loaded"] == 2
        assert second["cursor_bootstrap_namespaces"] == 0
        assert second["cursor_advances_proposed"] == 0
        assert second["cursor_advances_committed"] == 0
        assert second["selected_count"] == 2
        assert second["projection_count"] == 2
        assert second["runtime_handoff_count"] == 0
        assert not any(second["forbidden_table_deltas"].values())
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("failure", "expected_stage", "expected_reason"),
    (
        ("missing_quote_identity", "POOL_QUOTE_VALID", "BASE_QUOTE_ORIENTATION_MISMATCH"),
        ("wrong_pool_role_program", "POOL_QUOTE_VALID", "POOL_PROGRAM_NOT_EXECUTABLE"),
        ("base_quote_reversal", "POOL_QUOTE_VALID", "BASE_QUOTE_ORIENTATION_MISMATCH"),
        ("pool_target_mismatch", "POOL_QUOTE_VALID", "POOL_TARGET_MISMATCH"),
        ("holder_failure", "HOLDER_ACCEPTABLE", "HOLDER_STATUS_FAILED"),
        ("liquidity_failure", "LIQUIDITY_TRADEABILITY_VALID", "LIQUIDITY_STATUS_FAILED"),
        ("tradeability_failure", "ROUTE_TRADEABILITY_VALID", "TRADEABILITY_STATUS_FAILED"),
    ),
)
def test_live_shaped_failure_taxonomy_preserves_first_precise_cause(
    capsys, failure: str, expected_stage: str, expected_reason: str
) -> None:
    temp, path = _db()
    try:
        network = _LiveShapedFailureNetwork(failure)
        payload = _dispatch(
            capsys, path, CLI_MODE_N7, network, f"live-shaped-failure-{failure}"
        )
        assert payload["status"] == "BLOCKED"
        assert payload["manifest_id"] is None
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                """SELECT evidence.stage_name,evidence.reason_code
                   FROM printer_candidate_evidence AS evidence
                   JOIN printer_candidate_identities AS identity
                     ON identity.candidate_id=evidence.candidate_id
                  WHERE identity.mint_identity=?
                    AND evidence.stage_outcome='FAIL'
                  ORDER BY evidence.stage_ordinal
                  LIMIT 1""",
                (network.target_mint,),
            ).fetchone()
        assert row == (expected_stage, expected_reason)
        assert payload["active_lease_count"] == 0
        assert payload["scheduler_residue_terminalized"] == 0
        assert not any(payload["forbidden_table_deltas"].values())
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("cli_mode", "count", "cohort_m", "selection_n"),
    ((CLI_MODE_N2, 6, 4, 2), (CLI_MODE_N7, 16, 14, 7)),
)
def test_high_density_raw_nominations_thin_to_cohort_and_admit_exact_n(
    capsys, cli_mode: str, count: int, cohort_m: int, selection_n: int
) -> None:
    """Raw unique nominations above M thin to an M-bounded cohort, not a stop."""
    temp, path = _db()
    try:
        network = _CanonicalMockNetworkTransport(count)
        payload = _dispatch(capsys, path, cli_mode, network, f"hd-{count}")
        funnel = payload["pre_foundation_funnel"]
        assert funnel["raw_unique_nominations"] == count > cohort_m
        assert funnel["candidate_cohort_bound_m"] == cohort_m
        assert funnel["candidate_cohort_size"] == cohort_m
        assert funnel["thinned_beyond_cohort"] == count - cohort_m
        # DexScreener and GeckoTerminal overlap on the shared first identity and
        # participate under one authority-consistent nomination boundary.
        assert funnel["cross_source_overlap_count"] >= 1
        # Candidate-specific enrichment addressed only cohort identities.
        assert funnel["enrichment_identities"] <= cohort_m
        assert funnel["out_of_cohort_enrichment"] == 0
        assert payload["status"] == "COMPLETED"
        assert payload["selected_count"] == selection_n
        assert payload["projection_count"] == (2 if selection_n == 2 else 0)
        assert payload["runtime_handoff_count"] == 0
        assert payload["lifecycle_started"] is False
        assert payload["foundation_report"]["certificates_admitted"] <= cohort_m
        # No cohort candidate identity was evaluated outside the M bound.
        with sqlite3.connect(path) as connection:
            identities = connection.execute(
                "SELECT COUNT(DISTINCT mint_identity) FROM printer_candidate_identities"
            ).fetchone()[0]
        assert identities <= cohort_m
        calls = len(network.calls)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"hd-{count}"
        ) == payload
        assert len(network.calls) == calls
        if selection_n == 7:
            with pytest.raises(
                CandidateAcquisitionError, match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO"
            ):
                legacy_two_token_runtime_projection(path, payload["manifest_id"])
    finally:
        temp.cleanup()


def _density_frozen_owner(rows: list[dict], *, order: tuple[int, ...]) -> FrozenAcquisitionTransportOwner:
    base = [
        _dex_nomination_operation(rows),
        _gecko_nomination_operation(rows[:2]),
        _operation(
            "solana_rpc", "pumpfun_create_index_signature_page", [], {},
            cursor=_cursor("pump-create-index"),
        ),
        _operation(
            "solana_rpc", "pumpfun_migration_signature_page", [], {},
            cursor=_cursor("pump-program"),
            required=False, observation_scope="GLOBAL_OPTIONAL",
        ),
        _operation(
            "solana_rpc", "candidate_mint_account_batch", rows,
            {"mint_status": "PASS", "token_program_status": "PASS"},
        ),
        _operation(
            "solana_rpc", "pumpswap_pool_account_batch", rows, {"pool_status": "PASS"},
        ),
    ]
    required_decoupled = (
        _operation(
            "solana_rpc", "candidate_pump_migration_signature_lookup", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
        _operation(
            "solana_rpc", "candidate_pump_migration_transaction", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
        _operation(
            "solana_rpc", "candidate_pumpswap_pool_verification", [], {},
            required=False, transport_operations=0, phase="ENRICHMENT",
        ),
    )
    return FrozenAcquisitionTransportOwner(
        tuple(base[index] for index in order) + required_decoupled
    )


def _cohort_identities(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0] for row in connection.execute(
                "SELECT mint_identity FROM printer_candidate_identities"
            )
        }


def test_cohort_membership_is_provider_order_independent() -> None:
    """Provider execution order cannot change source-neutral cohort membership."""
    rows = _candidate_rows(6)
    forward = (0, 1, 2, 3, 4, 5)
    permuted = (5, 4, 1, 0, 3, 2)
    temp_f, path_f = _db()
    temp_p, path_p = _db()
    try:
        report_f = _run(
            path_f, mode=MODE_N2, execution_id="order-f",
            owner=_density_frozen_owner(rows, order=forward),
        )
        report_p = _run(
            path_p, mode=MODE_N2, execution_id="order-p",
            owner=_density_frozen_owner(rows, order=permuted),
        )
        # Six unique nominations thin to the same four lexicographically-smallest
        # cohort identities regardless of the order providers were executed in.
        expected = set(sorted(row["mint"] for row in rows)[:4])
        assert _cohort_identities(path_f) == expected
        assert _cohort_identities(path_p) == expected
        assert report_f["pre_foundation_funnel"]["candidate_cohort_size"] == 4
        assert report_p["pre_foundation_funnel"]["candidate_cohort_size"] == 4
        assert report_f["pre_foundation_funnel"]["thinned_beyond_cohort"] == 2
        assert report_p["pre_foundation_funnel"]["thinned_beyond_cohort"] == 2
    finally:
        temp_f.cleanup()
        temp_p.cleanup()


def test_pump_dex_gecko_overlap_participates_in_one_cohort_boundary() -> None:
    """A Pump-lineage identity competes for the cohort alongside aggregators."""
    temp, path = _db()
    try:
        # Five aggregator nominations (> N2 M=4) plus one Pump-origin nomination
        # that overlaps the first aggregator identity.
        rows = _candidate_rows(5)
        shared_mint = rows[0]["mint"]
        ops = [
            _dex_nomination_operation(rows),
            _gecko_nomination_operation(rows[:1]),
            _operation(
                "solana_rpc", "pumpfun_create_index_signature_page", [], {},
                cursor=_cursor("pump-create-index"),
            ),
            _operation(
                "solana_rpc", "pumpfun_create_index_transaction",
                [{"mint": shared_mint, "base_mint": shared_mint}],
                {}, cursor=_cursor("pump-create-index"),
            ),
            _operation(
                "solana_rpc", "pumpfun_migration_signature_page", [], {},
                cursor=_cursor("pump-program"),
            ),
            _operation(
                "solana_rpc", "candidate_mint_account_batch", rows,
                {"mint_status": "PASS", "token_program_status": "PASS"},
            ),
            _operation(
                "solana_rpc", "pumpswap_pool_account_batch", rows,
                {"pool_status": "PASS"},
            ),
        ]
        report = _run(
            path, mode=MODE_N2, execution_id="overlap",
            owner=FrozenAcquisitionTransportOwner(tuple(ops)),
        )
        funnel = report["pre_foundation_funnel"]
        assert funnel["raw_unique_nominations"] == 5 > 4
        assert funnel["candidate_cohort_size"] == 4
        assert funnel["thinned_beyond_cohort"] == 1
        # dex + gecko + pump all nominate the shared identity: overlap counted.
        assert funnel["nominating_source_count_by_identity"][shared_mint] >= 3
        assert funnel["cross_source_overlap_count"] >= 1
    finally:
        temp.cleanup()


def test_out_of_cohort_enrichment_fails_closed() -> None:
    """An enrichment observation for a non-cohort identity is a fail-closed fault."""
    temp, path = _db()
    try:
        ops = list(_owner(2).frozen_operations)
        rogue = AcquisitionSourceOperation(
            source_name="goplus",
            request_kind="safety_reference",
            adapter=_adapter("goplus", {
                "candidate_observations": [{
                    "mint": "R0GUEmintNeverNominated111111111111111111111",
                    "base_mint": "R0GUEmintNeverNominated111111111111111111111",
                    "facts": {"safety_status": "PASS"},
                    "observed_at": NOW, "expires_at": EXPIRES,
                }],
                "underlying_operation_count": 1,
            }),
            required=False,
            expected_transport_operations=1,
            phase="ENRICHMENT",
        )
        ops.append(rogue)
        report = _run(
            path, mode=MODE_N2, execution_id="ooce",
            owner=FrozenAcquisitionTransportOwner(tuple(ops)),
        )
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "OUT_OF_COHORT_ENRICHMENT"
        assert report["manifest_id"] is None
        assert report["pre_foundation_funnel"]["out_of_cohort_enrichment"] >= 1
    finally:
        temp.cleanup()


def test_cursor_proposed_and_committed_movement_are_distinct() -> None:
    """Proposed cursor advances only become committed inside the foundation."""
    temp_ok, path_ok = _db()
    temp_stop, path_stop = _db()
    try:
        success = _run(path_ok, mode=MODE_N2, execution_id="cursor-ok", owner=_owner(4))
        assert success["status"] == "COMPLETED"
        assert success["cursor_advances_proposed"] == 2
        assert success["cursor_advances_committed"] == 2
        with sqlite3.connect(path_ok) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors "
                "WHERE last_execution_id='cursor-ok'"
            ).fetchone()[0] == 2

        stopped = _run(
            path_stop, mode=MODE_N2, execution_id="cursor-stop",
            owner=_owner(4, required_pool_failure="rpc_transport_failure"),
        )
        assert stopped["status"] == "BLOCKED"
        assert stopped["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        # The signature pages proposed advances, but the foundation never ran, so
        # no durable cursor head committed and no rollback residue remains.
        assert stopped["cursor_advances_proposed"] == 2
        assert stopped["cursor_advances_committed"] == 0
        with sqlite3.connect(path_stop) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_cursors"
            ).fetchone()[0] == 0
    finally:
        temp_ok.cleanup()
        temp_stop.cleanup()


def _chain_mint_reasons(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return [
            str(row[0])
            for row in connection.execute(
                "SELECT reason_code FROM printer_candidate_evidence "
                "WHERE stage_name='CHAIN_MINT_VALID' ORDER BY candidate_id"
            )
        ]


@pytest.mark.parametrize(
    ("account", "expected"),
    (
        (None, "MINT_ACCOUNT_MISSING"),
        (
            {"owner": TOKEN_PROGRAM_ID, "data": ["%%%", "base64"]},
            "MINT_ACCOUNT_DATA_MALFORMED",
        ),
        (
            _spl_mint_account(owner="11111111111111111111111111111111"),
            "MINT_UNSUPPORTED_TOKEN_PROGRAM",
        ),
        (
            {
                "owner": PUMPSWAP_AMM_PROGRAM_ID,
                "data": [base64.b64encode(b"pool").decode(), "base64"],
            },
            "MINT_WRONG_PROGRAM_OWNER",
        ),
    ),
)
def test_mint_account_failure_taxonomy_is_precise(account, expected: str) -> None:
    mint = _candidate_rows(1)[0]["mint"]
    observation = live_transport._mint_account_observation(
        requested_mint=mint,
        response_slot=0,
        response_address=None,
        account=account,
        association_mode="POSITIONAL_RPC_CONTRACT",
        association_failure=None,
    )
    assert observation["facts"]["mint_status"] == "FAIL"
    assert observation["facts"]["mint_failure_reason"] == expected


def test_valid_spl_token_and_extended_token_2022_mints_pass() -> None:
    mints = [row["mint"] for row in _candidate_rows(2)]
    observations = [
        live_transport._mint_account_observation(
            requested_mint=mints[0], response_slot=0, response_address=None,
            account=_spl_mint_account(), association_mode="POSITIONAL_RPC_CONTRACT",
            association_failure=None,
        ),
        live_transport._mint_account_observation(
            requested_mint=mints[1], response_slot=1, response_address=None,
            account=_token_2022_mint_account(with_extension=True),
            association_mode="POSITIONAL_RPC_CONTRACT", association_failure=None,
        ),
    ]
    assert [item["facts"]["mint_status"] for item in observations] == ["PASS", "PASS"]
    assert observations[1]["facts"]["mint_layout_status"] == "PASS"


def test_pair_pool_and_infrastructure_targets_cannot_pass_as_memecoin_mints() -> None:
    row = _candidate_rows(1)[0]
    pair_observation = live_transport._mint_account_observation(
        requested_mint=row["pool"], response_slot=0, response_address=None,
        account={
            "owner": POOL_PROGRAM,
            "data": [base64.b64encode(b"pair-account").decode(), "base64"],
        },
        association_mode="POSITIONAL_RPC_CONTRACT", association_failure=None,
    )
    pool_observation = live_transport._mint_account_observation(
        requested_mint=row["pool"], response_slot=0, response_address=None,
        account=_pumpswap_account(row["mint"], 0),
        association_mode="POSITIONAL_RPC_CONTRACT", association_failure=None,
    )
    infrastructure_observation = live_transport._mint_account_observation(
        requested_mint=WSOL_MINT, response_slot=0, response_address=None,
        account=_spl_mint_account(), association_mode="POSITIONAL_RPC_CONTRACT",
        association_failure=None,
    )
    assert pair_observation["facts"]["mint_failure_reason"] == "MINT_WRONG_PROGRAM_OWNER"
    assert pool_observation["facts"]["mint_failure_reason"] == "MINT_WRONG_PROGRAM_OWNER"
    assert infrastructure_observation["facts"]["mint_failure_reason"] == "INFRASTRUCTURE_MINT_EXCLUDED"


def test_reordered_addressed_and_partially_null_batch_association_is_exact() -> None:
    mints = [row["mint"] for row in _candidate_rows(3)]
    values = [
        {"address": mints[2], "account": _token_2022_mint_account()},
        {"address": mints[0], "account": None},
        {"address": mints[1], "account": _spl_mint_account()},
    ]
    associated = live_transport._batch_account_associations(mints, values)
    assert [(item[0], item[1]) for item in associated] == [
        (mints[0], 1), (mints[1], 2), (mints[2], 0)
    ]
    observations = [
        live_transport._mint_account_observation(
            requested_mint=mint, response_slot=slot,
            response_address=response_address, account=account,
            association_mode=mode, association_failure=failure,
        )
        for mint, slot, response_address, account, mode, failure in associated
    ]
    assert observations[0]["facts"]["mint_failure_reason"] == "MINT_ACCOUNT_MISSING"
    assert observations[1]["facts"]["mint_status"] == "PASS"
    assert observations[2]["facts"]["mint_status"] == "PASS"


def test_address_assertion_target_mismatch_does_not_slide_adjacent_account() -> None:
    mints = [row["mint"] for row in _candidate_rows(2)]
    unknown = _candidate_rows(3)[2]["mint"]
    associated = live_transport._batch_account_associations(
        mints,
        [
            {"address": mints[0], "account": _spl_mint_account()},
            {"address": unknown, "account": _token_2022_mint_account()},
        ],
    )
    assert associated[0][1] == 0
    assert associated[0][5] is None
    assert associated[1][1] is None
    assert associated[1][5] == "MINT_TARGET_MISMATCH"
    observation = live_transport._mint_account_observation(
        requested_mint=associated[1][0], response_slot=associated[1][1],
        response_address=associated[1][2], account=associated[1][3],
        association_mode=associated[1][4], association_failure=associated[1][5],
    )
    assert observation["facts"]["mint_failure_reason"] == "MINT_TARGET_MISMATCH"


@pytest.mark.parametrize(
    ("cli_mode", "count", "expected"),
    ((CLI_MODE_N2, 2, 2), (CLI_MODE_N7, 7, 7)),
)
def test_public_cli_exact_n_mixed_mint_program_proof(
    capsys, cli_mode: str, count: int, expected: int
) -> None:
    temp, path = _db()
    try:
        network = _CanonicalMockNetworkTransport(count)
        payload = _dispatch(capsys, path, cli_mode, network, f"mint-exact-{expected}")
        assert payload["status"] == "COMPLETED"
        assert payload["foundation_report"]["certificates_issued"] == expected
        assert payload["foundation_report"]["certificates_admitted"] == expected
        assert payload["selected_count"] == expected
        assert payload["projection_count"] == (2 if expected == 2 else 0)
        assert payload["runtime_handoff_count"] == 0
        assert payload["lifecycle_started"] is False
        assert payload["scheduler_jobs_created"] == payload["governed_requests_used"]
        with sqlite3.connect(path) as connection:
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_manifest_items"
            ).fetchone()[0] == expected
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_leases "
                "WHERE lease_state <> 'TERMINAL' OR released_at IS NULL"
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs "
                "WHERE status IN ('PENDING','RUNNING','COOLDOWN')"
            ).fetchone()[0] == 0
            operation_count = connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_acquisition_transport_operations"
            ).fetchone()[0]
        assert operation_count == payload["transport_operations_used"]
        assert not any(payload["forbidden_table_deltas"].values())
        calls = len(network.calls)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=f"mint-exact-{expected}"
        ) == payload
        assert len(network.calls) == calls
        if expected == 7:
            with pytest.raises(
                CandidateAcquisitionError,
                match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
            ):
                legacy_two_token_runtime_projection(path, payload["manifest_id"])
    finally:
        temp.cleanup()


def test_sanitized_blocked_stage_a_shape_admits_extended_token_2022_cohort(
    capsys,
) -> None:
    fixture = json.loads(
        (ROOT / "tests/fixtures/candidate_mint_admission_blocked_stage_a_sanitized_v1.json").read_text()
    )
    assert fixture["contains_real_mint_addresses"] is False
    assert fixture["contains_raw_provider_payloads"] is False
    temp, path = _db()
    try:
        network = _MintBatchScenarioNetwork(
            4, lambda addresses, defaults: [
                _token_2022_mint_account(with_extension=True) for _ in addresses
            ]
        )
        payload = _dispatch(capsys, path, CLI_MODE_N2, network, "sanitized-live-shaped")
        assert payload["status"] == "COMPLETED"
        assert payload["foundation_report"]["certificates_issued"] == 4
        assert payload["foundation_report"]["certificates_admitted"] == 4
        assert _chain_mint_reasons(path) == ["MINT_STATUS_PASS"] * 4
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    ("transform", "reason"),
    (
        (lambda addresses, values: [None, values[1]], "MINT_ACCOUNT_MISSING"),
        (
            lambda addresses, values: [
                _spl_mint_account(owner="11111111111111111111111111111111"), values[1]
            ],
            "MINT_UNSUPPORTED_TOKEN_PROGRAM",
        ),
        (
            lambda addresses, values: [
                {"owner": TOKEN_2022_PROGRAM_ID, "data": ["%%%", "base64"]}, values[1]
            ],
            "MINT_ACCOUNT_DATA_MALFORMED",
        ),
    ),
)
def test_public_cli_mint_negatives_reach_precise_chain_reason(
    capsys, transform, reason: str
) -> None:
    temp, path = _db()
    try:
        payload = _dispatch(
            capsys, path, CLI_MODE_N2,
            _MintBatchScenarioNetwork(2, transform), f"mint-negative-{reason}",
        )
        assert payload["status"] == "BLOCKED"
        assert reason in _chain_mint_reasons(path)
        assert payload["first_terminal_cause"] == "ADMISSION_FAILURE"
        assert payload["active_lease_count"] == 0
        assert payload["scheduler_residue_terminalized"] == 0
        assert not any(payload["forbidden_table_deltas"].values())
    finally:
        temp.cleanup()


def test_public_cli_reordered_address_asserted_batch_preserves_targets(capsys) -> None:
    temp, path = _db()
    try:
        def reordered(addresses, values):
            return [
                {"address": address, "account": account}
                for address, account in reversed(list(zip(addresses, values, strict=True)))
            ]
        payload = _dispatch(
            capsys, path, CLI_MODE_N2,
            _MintBatchScenarioNetwork(2, reordered), "mint-reordered",
        )
        assert payload["status"] == "COMPLETED"
        assert payload["selected_count"] == 2
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                "SELECT facts_json FROM printer_candidate_source_observations "
                "WHERE request_kind='candidate_mint_account_batch' ORDER BY mint_identity"
            ).fetchall()
        slots = sorted(json.loads(row[0])["mint_response_slot"] for row in rows)
        assert slots == [0, 1]
        assert all(
            json.loads(row[0])["mint_response_association"] == "EXPLICIT_RESPONSE_ADDRESS"
            for row in rows
        )
    finally:
        temp.cleanup()


def test_mint_evidence_merge_key_mismatch_fails_with_exact_reason() -> None:
    temp, path = _db()
    try:
        rows = _candidate_rows(2)
        operations = list(_owner(2).frozen_operations)
        operations[4] = _operation(
            "solana_rpc", "candidate_mint_account_batch", rows,
            {
                "mint_account_evidence_version": live_transport.MINT_ACCOUNT_EVIDENCE_VERSION,
                "mint_request_target": rows[1]["mint"],
                "mint_response_slot": 0,
                "mint_response_address": None,
                "mint_response_association": "POSITIONAL_RPC_CONTRACT",
                "mint_account_presence": "PRESENT",
                "mint_owner_status": "PASS",
                "mint_layout_status": "PASS",
                "mint_failure_reason": None,
                "mint_status": "PASS",
                "token_program_status": "PASS",
            },
        )
        report = _run(
            path, mode=MODE_N2, execution_id="mint-merge-mismatch",
            owner=FrozenAcquisitionTransportOwner(tuple(operations)),
        )
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "IDENTITY_MERGE_FAILURE"
        assert "MINT_EVIDENCE_MERGE_KEY_MISMATCH" in _chain_mint_reasons(path)
    finally:
        temp.cleanup()


def _failed_signature(signature: str, slot: int) -> dict:
    return {
        "signature": signature,
        "slot": slot,
        "err": {"InstructionError": [0, "Custom"]},
        "memo": None,
        "blockTime": 1_785_326_400,
        "confirmationStatus": "finalized",
    }


class _CursorContinuityNetwork(_CanonicalMockNetworkTransport):
    """Frozen newest-first Solana history with official exclusive bounds."""

    def __init__(
        self,
        count: int,
        histories: dict[str, list[dict]],
        *,
        unreachable_boundaries: set[str] | None = None,
        fail_pool_batch: bool = False,
    ) -> None:
        super().__init__(count)
        self.histories = deepcopy(histories)
        self.unreachable_boundaries = set(unreachable_boundaries or ())
        self.fail_pool_batch = fail_pool_batch
        self.rpc_requests: list[tuple[str, list, str]] = []

    def rpc_json(
        self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
        endpoint_role,
    ):
        del rpc_url, timeout_seconds, byte_ceiling
        self.rpc_requests.append((method, deepcopy(list(params)), endpoint_role))
        if method == "getSignaturesForAddress":
            address, options = str(params[0]), dict(params[1])
            history = self.histories.get(address, [])
            signatures = [str(row["signature"]) for row in history]
            start = 0
            if options.get("before") in signatures:
                start = signatures.index(str(options["before"])) + 1
            end = len(history)
            if options.get("until") in signatures:
                end = signatures.index(str(options["until"]))
            payload = history[start:end][: int(options["limit"])]
            return self._result(payload, method, endpoint_role)
        if method == "getTransaction" and endpoint_role.endswith("_PRIOR_BOUNDARY"):
            signature = str(params[0])
            known = any(
                signature == str(row["signature"])
                for history in self.histories.values() for row in history
            )
            payload = None if (
                not known or signature in self.unreachable_boundaries
            ) else {
                "slot": next(
                    int(row["slot"])
                    for history in self.histories.values() for row in history
                    if signature == str(row["signature"])
                ),
                "transaction": {"message": {"accountKeys": [], "instructions": []}},
                "meta": {"err": {"InstructionError": [0, "Custom"]}},
            }
            return self._result(payload, method, endpoint_role)
        if self.fail_pool_batch and endpoint_role == "PUMPSWAP_POOL_ACCOUNT_BATCH":
            raise LiveAcquisitionTransportError(
                "SOURCE_TRANSPORT_FAILURE", endpoint_role,
                operation_kind=method,
            )
        return super().rpc_json(
            rpc_url="https://rpc.example.invalid", method=method, params=params,
            timeout_seconds=1.0, byte_ceiling=1_048_576,
            endpoint_role=endpoint_role,
        )


def _public_cursor_run(
    *,
    path: Path,
    execution_id: str,
    network: _CursorContinuityNetwork,
    capsys,
    cli_mode: str = CLI_MODE_N2,
    now: str = NOW,
) -> dict:
    assert command.main(
        [cli_mode, "--operator-approved"],
        acquisition_environment={
            "PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid"
        },
        acquisition_one_shot_transport=network,
        acquisition_preflight=_preflight(path),
        acquisition_execution_id=execution_id,
        acquisition_now=now,
        acquisition_db_path=path,
    ) == 0
    return json.loads(capsys.readouterr().out)


def _durable_cursor_rows(path: Path) -> dict[str, sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return {
            str(row["indexed_address"]): row
            for row in connection.execute(
                "SELECT * FROM printer_candidate_acquisition_cursors "
                "WHERE direction='FORWARD' ORDER BY indexed_address"
            )
        }
    finally:
        connection.close()


def test_public_live_cursor_bootstrap_resume_no_new_and_replay(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("create-bootstrap-head", 420_000_010)
    migration_head = _failed_signature("migration-bootstrap-head", 420_000_011)
    try:
        first_network = _CursorContinuityNetwork(4, {
            PUMP_CREATE_INDEX_ADDRESS: [create_head],
            PUMP_PROGRAM_ID: [migration_head],
        })
        first = _public_cursor_run(
            path=path, execution_id="cursor-bootstrap", network=first_network,
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        assert first["cursor_namespaces_declared"] == 2
        assert first["cursor_heads_loaded"] == 0
        assert first["cursor_bootstrap_namespaces"] == 2
        assert first["cursor_advances_proposed"] == 2
        assert first["cursor_advances_committed"] == 2
        assert first["selected_count"] == 2
        assert first["projection_count"] == 2
        rows = _durable_cursor_rows(path)
        assert set(rows) == {PUMP_CREATE_INDEX_ADDRESS, PUMP_PROGRAM_ID}
        assert rows[PUMP_CREATE_INDEX_ADDRESS]["boundary_signature"] == create_head["signature"]
        assert rows[PUMP_PROGRAM_ID]["boundary_signature"] == migration_head["signature"]
        assert {int(row["cursor_version"]) for row in rows.values()} == {1}

        create_new = _failed_signature("create-live-new", 420_000_020)
        migration_new = _failed_signature("migration-live-new", 420_000_021)
        second_network = _CursorContinuityNetwork(4, {
            PUMP_CREATE_INDEX_ADDRESS: [create_new, create_head],
            PUMP_PROGRAM_ID: [migration_new, migration_head],
        })
        second = _public_cursor_run(
            path=path, execution_id="cursor-resume", network=second_network,
            capsys=capsys, now="2026-07-29T12:10:00+00:00",
        )
        assert second["status"] == "COMPLETED", json.dumps(second, indent=2)
        assert second["cursor_heads_loaded"] == 2
        assert second["cursor_bootstrap_namespaces"] == 0
        assert second["cursor_advances_proposed"] == 2
        assert second["cursor_advances_committed"] == 2
        signature_requests = [
            params for method, params, _role in second_network.rpc_requests
            if method == "getSignaturesForAddress"
        ]
        assert {params[1]["until"] for params in signature_requests} == {
            create_head["signature"], migration_head["signature"],
        }
        assert all("before" not in params[1] for params in signature_requests)
        rows = _durable_cursor_rows(path)
        assert rows[PUMP_CREATE_INDEX_ADDRESS]["boundary_signature"] == create_new["signature"]
        assert rows[PUMP_PROGRAM_ID]["boundary_signature"] == migration_new["signature"]
        assert {int(row["cursor_version"]) for row in rows.values()} == {2}
        connection = sqlite3.connect(path)
        try:
            starts = {
                json.loads(row[0])["indexed_address"]: (
                    json.loads(row[0])["start_slot"],
                    json.loads(row[0])["start_signature"],
                )
                for row in connection.execute(
                    "SELECT cursor_range_json FROM printer_candidate_acquisition_work "
                    "WHERE execution_id='cursor-resume' AND cursor_range_json IS NOT NULL"
                )
            }
        finally:
            connection.close()
        assert starts[PUMP_CREATE_INDEX_ADDRESS] == (
            create_head["slot"], create_head["signature"]
        )
        assert starts[PUMP_PROGRAM_ID] == (
            migration_head["slot"], migration_head["signature"]
        )

        stable_network = _CursorContinuityNetwork(4, {
            PUMP_CREATE_INDEX_ADDRESS: [create_new, create_head],
            PUMP_PROGRAM_ID: [migration_new, migration_head],
        })
        stable = _public_cursor_run(
            path=path, execution_id="cursor-no-new", network=stable_network,
            capsys=capsys, now="2026-07-29T12:20:00+00:00",
        )
        assert stable["status"] == "COMPLETED"
        assert stable["cursor_heads_loaded"] == 2
        assert stable["cursor_advances_proposed"] == 0
        assert stable["cursor_advances_committed"] == 0
        rows_after_stable = _durable_cursor_rows(path)
        assert {int(row["cursor_version"]) for row in rows_after_stable.values()} == {2}
        assert all(not any(value for value in report["forbidden_table_deltas"].values())
                   for report in (first, second, stable))
        assert all(report["active_lease_count"] == 0 for report in (first, second, stable))
        assert all(report["scheduler_residue_terminalized"] == 0
                   for report in (first, second, stable))

        before_replay_calls = len(stable_network.calls)
        replay = _public_cursor_run(
            path=path, execution_id="cursor-no-new", network=stable_network,
            capsys=capsys, now="2026-07-29T12:20:00+00:00",
        )
        assert replay == stable
        assert len(stable_network.calls) == before_replay_calls
        assert replay_candidate_acquisition_integration_report(
            path, execution_id="cursor-no-new"
        ) == stable
    finally:
        temp.cleanup()


def test_empty_bootstrap_is_repeatable_without_synthetic_head(capsys) -> None:
    temp, path = _db()
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-empty-bootstrap-1",
            network=_CanonicalMockNetworkTransport(4), capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        assert first["cursor_bootstrap_namespaces"] == 2
        assert first["cursor_advances_proposed"] == 0
        assert first["cursor_advances_committed"] == 0
        assert _durable_cursor_rows(path) == {}
        connection = sqlite3.connect(path)
        try:
            empty_ranges = connection.execute(
                "SELECT COUNT(*) FROM printer_candidate_cursor_ranges "
                "WHERE cursor_advanced=0 AND end_signature IS NULL AND end_slot IS NULL"
            ).fetchone()[0]
        finally:
            connection.close()
        assert empty_ranges >= 2

        second = _public_cursor_run(
            path=path, execution_id="cursor-empty-bootstrap-2",
            network=_CanonicalMockNetworkTransport(4), capsys=capsys,
            now="2026-07-29T12:10:00+00:00",
        )
        assert second["status"] == "COMPLETED"
        assert second["cursor_bootstrap_namespaces"] == 2
        assert second["cursor_advances_proposed"] == 0
        assert second["cursor_advances_committed"] == 0
        assert _durable_cursor_rows(path) == {}
    finally:
        temp.cleanup()


def test_live_cursor_multi_page_preserves_until_and_before(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("create-n7-head", 420_001_000)
    migration_head = _failed_signature("migration-n7-head", 420_001_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-n7-bootstrap",
            network=_CursorContinuityNetwork(14, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys, cli_mode=CLI_MODE_N7,
        )
        assert first["status"] == "COMPLETED"
        assert first["selected_count"] == 7
        assert first["projection_count"] == 0

        create_new = [
            _failed_signature(f"create-n7-new-{index}", 420_001_020 - index)
            for index in range(5)
        ]
        migration_new = [
            _failed_signature(f"migration-n7-new-{index}", 420_001_030 - index)
            for index in range(5)
        ]
        network = _CursorContinuityNetwork(14, {
            PUMP_CREATE_INDEX_ADDRESS: [*create_new, create_head],
            PUMP_PROGRAM_ID: [*migration_new, migration_head],
        })
        second = _public_cursor_run(
            path=path, execution_id="cursor-n7-resume", network=network,
            capsys=capsys, cli_mode=CLI_MODE_N7,
            now="2026-07-29T13:00:00+00:00",
        )
        assert second["status"] == "COMPLETED", json.dumps(second, indent=2)
        assert second["cursor_advances_proposed"] == 2
        assert second["cursor_advances_committed"] == 2
        requests_by_address: dict[str, list[dict]] = {}
        for method, params, _role in network.rpc_requests:
            if method == "getSignaturesForAddress":
                requests_by_address.setdefault(str(params[0]), []).append(dict(params[1]))
        for address, prior in (
            (PUMP_CREATE_INDEX_ADDRESS, create_head),
            (PUMP_PROGRAM_ID, migration_head),
        ):
            options = requests_by_address[address]
            assert len(options) == 2
            assert options[0]["until"] == prior["signature"]
            assert "before" not in options[0]
            assert options[1]["until"] == prior["signature"]
            assert options[1]["before"].endswith("-3")
        rows = _durable_cursor_rows(path)
        assert rows[PUMP_CREATE_INDEX_ADDRESS]["boundary_signature"] == create_new[0]["signature"]
        assert rows[PUMP_PROGRAM_ID]["boundary_signature"] == migration_new[0]["signature"]
        assert {int(row["cursor_version"]) for row in rows.values()} == {2}
        with pytest.raises(
            CandidateAcquisitionError,
            match="LEGACY_RUNTIME_REQUIRES_EXACTLY_TWO",
        ):
            legacy_two_token_runtime_projection(path, second["manifest_id"])
    finally:
        temp.cleanup()


def test_cursor_namespace_identity_missing_head_and_unreachable_fail_closed(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("create-negative-head", 420_002_000)
    migration_head = _failed_signature("migration-negative-head", 420_002_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-negative-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        namespace = (
            "solana-mainnet", PUMP_CREATE_INDEX_ADDRESS,
            OFFICIAL_REPOSITORY_COMMIT, "canonical-live-acquisition-v1", "FORWARD",
        )
        loaded = _load_exact_cursor_heads(path, namespaces=(namespace,))
        assert loaded[namespace]["boundary_slot"] == create_head["slot"]
        for changed in (
            ("wrong-network", namespace[1], namespace[2], namespace[3], namespace[4]),
            (namespace[0], namespace[1], "wrong-pin", namespace[3], namespace[4]),
            (namespace[0], namespace[1], namespace[2], "wrong-decoder", namespace[4]),
        ):
            with pytest.raises(
                CandidateAcquisitionIntegrationError,
                match="CURSOR_NAMESPACE_MISMATCH",
            ):
                _load_exact_cursor_heads(path, namespaces=(changed,))

        backward = (*namespace[:4], "BACKWARD")
        assert _load_exact_cursor_heads(path, namespaces=(backward,))[backward] is None
        wrong_direction_head = dict(loaded[namespace])
        wrong_direction_head["direction"] = "BACKWARD"
        owner = build_live_candidate_acquisition_transport_owner(
            environment={"PRINTER_SOLANA_RPC_URL": "https://rpc.example.invalid"}
        )
        with pytest.raises(
            LiveAcquisitionConfigurationError,
            match="CURSOR_NAMESPACE_MISMATCH",
        ):
            owner.operations(
                mode=MODE_N2, policy=MODE_POLICIES[MODE_N2], execution_id="wrong",
                cursor_heads={namespace: wrong_direction_head},
            )

        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "DELETE FROM printer_candidate_acquisition_cursors "
                "WHERE indexed_address=? AND direction='FORWARD'",
                (PUMP_CREATE_INDEX_ADDRESS,),
            )
            connection.commit()
        finally:
            connection.close()
        no_call_network = _CursorContinuityNetwork(4, {
            PUMP_CREATE_INDEX_ADDRESS: [create_head],
            PUMP_PROGRAM_ID: [migration_head],
        })
        missing = _public_cursor_run(
            path=path, execution_id="cursor-missing-head", network=no_call_network,
            capsys=capsys,
        )
        assert missing["status"] == "BLOCKED"
        assert missing["first_terminal_cause"] == "CURSOR_DURABLE_HEAD_MISSING"
        assert no_call_network.calls == []
    finally:
        temp.cleanup()

    temp, path = _db()
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-unreachable-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        blocked = _public_cursor_run(
            path=path, execution_id="cursor-unreachable",
            network=_CursorContinuityNetwork(
                4,
                {
                    PUMP_CREATE_INDEX_ADDRESS: [create_head],
                    PUMP_PROGRAM_ID: [migration_head],
                },
                unreachable_boundaries={create_head["signature"]},
            ),
            capsys=capsys, now="2026-07-29T12:10:00+00:00",
        )
        assert blocked["status"] == "BLOCKED"
        assert blocked["first_terminal_cause"] == "CURSOR_PRIOR_BOUNDARY_UNREACHABLE"
        assert blocked["foundation_execution_id"] is None
        assert blocked["cursor_advances_committed"] == 0
        rows = _durable_cursor_rows(path)
        assert rows[PUMP_CREATE_INDEX_ADDRESS]["boundary_signature"] == create_head["signature"]
        assert rows[PUMP_PROGRAM_ID]["boundary_signature"] == migration_head["signature"]
    finally:
        temp.cleanup()


def test_cursor_rollback_reconciles_and_backfill_query_is_explicit(capsys) -> None:
    assert _signature_page_request_options(
        range_mode="LIVE_TAIL", head_signature="head",
        previous_page_signature=None, limit=4,
    ) == {"limit": 4, "commitment": "finalized", "until": "head"}
    assert _signature_page_request_options(
        range_mode="LIVE_TAIL", head_signature="head",
        previous_page_signature="page-end", limit=3,
    ) == {
        "limit": 3, "commitment": "finalized", "until": "head",
        "before": "page-end",
    }
    assert _signature_page_request_options(
        range_mode="BACKFILL", head_signature="head",
        previous_page_signature=None, limit=4,
    ) == {"limit": 4, "commitment": "finalized", "before": "head"}
    with pytest.raises(
        LiveAcquisitionConfigurationError,
        match="CURSOR_BACKFILL_HEAD_REQUIRED",
    ):
        _signature_page_request_options(
            range_mode="BACKFILL", head_signature=None,
            previous_page_signature=None, limit=4,
        )

    temp, path = _db()
    create_head = _failed_signature("create-rollback-head", 420_003_000)
    migration_head = _failed_signature("migration-rollback-head", 420_003_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-rollback-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        before = _durable_cursor_rows(path)
        create_new = _failed_signature("create-rollback-new", 420_003_010)
        migration_new = _failed_signature("migration-rollback-new", 420_003_011)
        blocked = _public_cursor_run(
            path=path, execution_id="cursor-rollback",
            network=_CursorContinuityNetwork(
                4,
                {
                    PUMP_CREATE_INDEX_ADDRESS: [create_new, create_head],
                    PUMP_PROGRAM_ID: [migration_new, migration_head],
                },
                fail_pool_batch=True,
            ),
            capsys=capsys, now="2026-07-29T12:10:00+00:00",
        )
        assert blocked["status"] == "BLOCKED"
        assert blocked["first_terminal_cause"] == "REQUIRED_SOURCE_FAILURE"
        assert blocked["cursor_advances_proposed"] == 2
        assert blocked["cursor_advances_committed"] == 0
        assert blocked["foundation_execution_id"] is None
        after = _durable_cursor_rows(path)
        assert {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in before.items()
        } == {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in after.items()
        }
        assert blocked["active_lease_count"] == 0
        assert blocked["scheduler_residue_terminalized"] == 0
        assert not any(blocked["forbidden_table_deltas"].values())
    finally:
        temp.cleanup()


def test_foundation_rejects_wrong_durable_slot_and_signature(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("create-exact-head", 420_004_000)
    migration_head = _failed_signature("migration-exact-head", 420_004_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-exact-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        durable = _durable_cursor_rows(path)

        def owner_with_start_error(*, wrong_field: str) -> FrozenAcquisitionTransportOwner:
            owner = _owner(4)
            seen: set[int] = set()
            for operation in owner.frozen_operations:
                cursor = operation.cursor_range
                if not isinstance(cursor, dict) or id(cursor) in seen:
                    continue
                seen.add(id(cursor))
                address = (
                    PUMP_CREATE_INDEX_ADDRESS
                    if "create" in str(cursor["indexed_address"])
                    else PUMP_PROGRAM_ID
                )
                row = durable[address]
                cursor.update({
                    "indexed_address": address,
                    "contract_pin": str(row["contract_pin"]),
                    "decoder_version": str(row["decoder_version"]),
                    "direction": str(row["direction"]),
                    "start_slot": int(row["boundary_slot"]),
                    "start_signature": str(row["boundary_signature"]),
                    "end_slot": int(row["boundary_slot"]) + 1,
                    "end_signature": f"new-{cursor['indexed_address']}",
                })
            target = next(
                operation.cursor_range for operation in owner.frozen_operations
                if operation.cursor_range
                and operation.cursor_range["indexed_address"] == PUMP_CREATE_INDEX_ADDRESS
            )
            if wrong_field == "slot":
                target["start_slot"] = int(target["start_slot"]) + 1
            else:
                target["start_signature"] = "wrong-prior-signature"
            return owner

        wrong_slot = _run(
            path, mode=MODE_N2, execution_id="cursor-wrong-slot",
            owner=owner_with_start_error(wrong_field="slot"),
            now="2026-07-29T12:10:00+00:00",
        )
        assert wrong_slot["status"] == "BLOCKED"
        assert wrong_slot["first_terminal_cause"] == "CURSOR_START_MISMATCH"
        assert wrong_slot["cursor_advances_committed"] == 0

        wrong_signature = _run(
            path, mode=MODE_N2, execution_id="cursor-wrong-signature",
            owner=owner_with_start_error(wrong_field="signature"),
            now="2026-07-29T12:20:00+00:00",
        )
        assert wrong_signature["status"] == "BLOCKED"
        assert wrong_signature["first_terminal_cause"] == "CURSOR_START_MISMATCH"
        assert wrong_signature["cursor_advances_committed"] == 0
        after = _durable_cursor_rows(path)
        assert {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in durable.items()
        } == {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in after.items()
        }
    finally:
        temp.cleanup()


def test_live_tail_page_ceiling_fails_without_skip_or_rewind(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("create-gap-head", 420_005_000)
    migration_head = _failed_signature("migration-gap-head", 420_005_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="cursor-gap-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        before = _durable_cursor_rows(path)
        blocked = _public_cursor_run(
            path=path, execution_id="cursor-gap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [
                    _failed_signature("create-gap-newest", 420_005_020),
                    _failed_signature("create-gap-second", 420_005_019),
                    create_head,
                ],
                PUMP_PROGRAM_ID: [
                    _failed_signature("migration-gap-newest", 420_005_030),
                    _failed_signature("migration-gap-second", 420_005_029),
                    migration_head,
                ],
            }),
            capsys=capsys, now="2026-07-29T12:10:00+00:00",
        )
        assert blocked["status"] == "BLOCKED"
        assert blocked["first_terminal_cause"] == "CURSOR_CONTINUITY_GAPPED"
        assert blocked["cursor_advances_proposed"] == 0
        assert blocked["cursor_advances_committed"] == 0
        after = _durable_cursor_rows(path)
        assert {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in before.items()
        } == {
            address: (row["boundary_slot"], row["boundary_signature"], row["cursor_version"])
            for address, row in after.items()
        }
    finally:
        temp.cleanup()


def test_optional_global_bounded_coverage_gap_persists_and_continues(capsys) -> None:
    temp, path = _db()
    create_head = _failed_signature("optional-create-head", 420_006_000)
    migration_head = _failed_signature("optional-migration-head", 420_006_001)
    try:
        first = _public_cursor_run(
            path=path, execution_id="optional-gap-bootstrap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [create_head],
                PUMP_PROGRAM_ID: [migration_head],
            }),
            capsys=capsys,
        )
        assert first["status"] == "COMPLETED"
        before = _durable_cursor_rows(path)
        report = _public_cursor_run(
            path=path, execution_id="optional-global-gap",
            network=_CursorContinuityNetwork(4, {
                PUMP_CREATE_INDEX_ADDRESS: [
                    _failed_signature("optional-create-new", 420_006_010),
                    create_head,
                ],
                PUMP_PROGRAM_ID: [
                    _failed_signature("optional-migration-newest", 420_006_020),
                    _failed_signature("optional-migration-second", 420_006_019),
                    migration_head,
                ],
            }),
            capsys=capsys, now="2026-07-29T12:10:00+00:00",
        )
        assert report["status"] == "COMPLETED"
        assert report["selected_count"] == 2
        assert report["projection_count"] == 2
        assert report["runtime_handoff_count"] == 0
        assert report["optional_global_pump_observer"][
            "observer_status"
        ] == "GLOBAL_PUMP_OBSERVER_GAPPED"
        assert report["optional_global_pump_observer"][
            "universal_failure_contribution"
        ] is False
        assert report["operation_accounting"]["identity_mismatch_work_items"] == 0
        after = _durable_cursor_rows(path)
        # Required create continuity may advance; optional gapped migration
        # continuity remains on its exact established head.
        assert after[PUMP_PROGRAM_ID]["boundary_signature"] == (
            before[PUMP_PROGRAM_ID]["boundary_signature"]
        )
        assert int(after[PUMP_PROGRAM_ID]["cursor_version"]) == int(
            before[PUMP_PROGRAM_ID]["cursor_version"]
        )
        with sqlite3.connect(path) as connection:
            gap_work = connection.execute(
                """SELECT work_state,transport_operations_used
                     FROM printer_candidate_acquisition_work
                    WHERE execution_id='optional-global-gap'
                      AND request_kind='pumpfun_migration_signature_page'"""
            ).fetchone()
        assert gap_work == ("SUCCEEDED", 2)
        assert replay_candidate_acquisition_integration_report(
            path, execution_id="optional-global-gap"
        ) == report
    finally:
        temp.cleanup()


def test_decoupled_branch_classification_is_pure_and_presence_is_not_graduation() -> None:
    mint = FIXTURE["candidates"][0][0]
    curve = derive_program_address(
        (b"bonding-curve", _b58decode(mint)), PUMP_PROGRAM_ID
    )[0]
    origin = {"mint": mint, "bonding_curve": curve}
    active = {
        "base_mint": mint, "bonding_curve_address": curve, "complete": False,
    }
    assert classify_candidate_lineage_branch(
        candidate_mint=mint, exact_pump_origin=origin,
        verified_bonding_curve=active,
    )["branch"] == PUMP_ACTIVE_BONDING_CURVE
    assert classify_candidate_lineage_branch(
        candidate_mint=mint,
    )["branch"] == NO_PUMP_GRADUATION_CLAIM
    # A Pool address/presence without exact Pump origin is deliberately not a
    # Pump graduation claim.
    assert classify_candidate_lineage_branch(
        candidate_mint=mint,
        proposed_pumpswap_pool=FIXTURE["candidates"][0][1],
    )["branch"] == NO_PUMP_GRADUATION_CLAIM
    assert classify_candidate_lineage_branch(
        candidate_mint=mint, exact_pump_origin=origin,
        exact_migration_signature="sig",
    )["branch"] == PUMP_GRADUATION_CLAIMED
    conflict = classify_candidate_lineage_branch(
        candidate_mint=mint, exact_pump_origin=origin,
        verified_bonding_curve=active, independently_known_non_pump=True,
    )
    assert conflict == {
        "branch": PUMP_LINEAGE_CONFLICT,
        "reason": "PUMP_AND_NON_PUMP_LINEAGE_CONFLICT",
    }


@pytest.mark.parametrize(
    ("locator_kind", "kwargs"),
    (
        (MIGRATION_SIGNATURE, {"exact_migration_signature": "exact-signature"}),
        (PUMPSWAP_POOL, {"exact_pumpswap_pool": "POOL"}),
        (PUMP_BONDING_CURVE, {"exact_verified_bonding_curve": "CURVE"}),
        (CANDIDATE_MINT, {}),
    ),
)
def test_candidate_locator_precedence_and_exact_join_pass_each_locator(
    locator_kind: str, kwargs: dict,
) -> None:
    network = _LiveShapedAdmissionNetwork(4)
    tx = network.migration_transaction
    decoded = decode_supported_pump_migration_transaction(tx)
    assert decoded["supported"] is True
    mint = str(decoded["mint"])
    pool = str(decoded["pool_address"])
    concrete = dict(kwargs)
    if concrete.get("exact_pumpswap_pool") == "POOL":
        concrete["exact_pumpswap_pool"] = pool
    if concrete.get("exact_verified_bonding_curve") == "CURVE":
        concrete["exact_verified_bonding_curve"] = str(decoded["accounts"][3])
    locator = plan_candidate_migration_locator(
        candidate_mint=mint,
        branch=PUMP_GRADUATION_CLAIMED,
        finalized_cutoff_slot=int(tx["slot"]),
        **concrete,
    )
    assert locator is not None
    assert locator["locator_kind"] == locator_kind
    assert locator["fallback_allowed"] is False
    assert validate_candidate_migration_locator(
        locator=locator, decoded_migration=decoded
    )[0] is True
    verified = verify_pinned_pump_migration(
        tx, {pool: network.pool_accounts[pool]},
        expected_mint=mint, finalized=True,
    )
    assert verified["verified"] is True


def _mutate_pool_account(account: dict, *, offset: int, raw: bytes) -> dict:
    changed = deepcopy(account)
    data = bytearray(base64.b64decode(changed["data"][0]))
    data[offset:offset + len(raw)] = raw
    changed["data"][0] = base64.b64encode(data).decode()
    return changed


@pytest.mark.parametrize(
    "failure",
    (
        "mint", "curve", "pool", "creator", "index", "quote", "pda",
        "lp", "vault", "fixed", "transaction_failed", "finality",
        "version", "layout", "ambiguity",
    ),
)
def test_exact_migrate_and_pumpswap_join_fail_one_field_at_a_time(
    failure: str,
) -> None:
    network = _LiveShapedAdmissionNetwork(4)
    tx = deepcopy(network.migration_transaction)
    decoded = decode_supported_pump_migration_transaction(tx)
    mint = str(decoded["mint"])
    pool = str(decoded["pool_address"])
    infos = {pool: deepcopy(network.pool_accounts[pool])}
    alternate = _b58decode(FIXTURE["candidates"][-1][0])
    finalized = True
    keys = tx["transaction"]["message"]["accountKeys"]
    instruction = tx["transaction"]["message"]["instructions"][0]
    if failure == "mint":
        keys[2] = FIXTURE["candidates"][-1][0]
    elif failure == "curve":
        keys[3] = FIXTURE["candidates"][-1][0]
    elif failure == "pool":
        keys[9] = FIXTURE["candidates"][-1][1]
    elif failure == "creator":
        keys[10] = FIXTURE["candidates"][-1][0]
    elif failure == "index":
        infos[pool] = _mutate_pool_account(
            infos[pool], offset=9, raw=(1).to_bytes(2, "little")
        )
    elif failure == "quote":
        infos[pool] = _mutate_pool_account(
            infos[pool], offset=75, raw=alternate
        )
    elif failure == "pda":
        infos[pool] = _mutate_pool_account(
            infos[pool], offset=8, raw=bytes([0])
        )
    elif failure == "lp":
        infos[pool] = _mutate_pool_account(
            infos[pool], offset=107, raw=alternate
        )
    elif failure == "vault":
        infos[pool] = _mutate_pool_account(
            infos[pool], offset=139, raw=alternate
        )
    elif failure == "fixed":
        keys[6] = FIXTURE["candidates"][-1][0]
    elif failure == "transaction_failed":
        tx["meta"]["err"] = {"InstructionError": [0, "Custom"]}
    elif failure == "finality":
        finalized = False
    elif failure == "version":
        tx["version"] = 1
    elif failure == "layout":
        instruction["accounts"] = list(range(24))
    elif failure == "ambiguity":
        tx["transaction"]["message"]["instructions"].append(deepcopy(instruction))
    assert verify_pinned_pump_migration(
        tx, infos, expected_mint=mint, finalized=finalized
    )["verified"] is False


def _optional_observer_owner(
    *,
    observer_status: str,
    non_pump: bool,
) -> FrozenAcquisitionTransportOwner:
    rows = _candidate_rows(2)
    if non_pump:
        rows = [{**row, "lineage_claim": "NON_PUMP_POOL_CONFIRMED"} for row in rows]
    owner = _owner(2)
    operations = list(owner.frozen_operations)
    pool_index = next(
        index for index, operation in enumerate(operations)
        if operation.request_kind == "pumpswap_pool_account_batch"
    )
    operations[pool_index] = _operation(
        "solana_rpc", "pumpswap_pool_account_batch", rows,
        {"pool_status": "PASS"}, phase="ENRICHMENT",
    )
    global_index = next(
        index for index, operation in enumerate(operations)
        if operation.request_kind == "pumpfun_migration_signature_page"
    )
    if observer_status == "NOT_RUN":
        operations.pop(global_index)
    elif observer_status == "UNAVAILABLE":
        operations[global_index] = AcquisitionSourceOperation(
            source_name="solana_rpc",
            request_kind="pumpfun_migration_signature_page",
            adapter=_StaticFailureAdapter(
                "solana_rpc", "pumpfun_migration_signature_page",
                "SOURCE_TRANSPORT_FAILURE",
            ),
            required=False,
            observation_scope="GLOBAL_OPTIONAL",
        )
    else:
        continuity = {
            "GAPPED": "GAPPED",
            "UNKNOWN": "UNKNOWN",
            "BLOCKED_CONTRACT": "BLOCKED_CONTRACT",
        }[observer_status]
        operations[global_index] = _operation(
            "solana_rpc", "pumpfun_migration_signature_page", [], {},
            required=False,
            cursor=_cursor("pump-program", continuity=continuity),
            observation_scope="GLOBAL_OPTIONAL",
        )
    return FrozenAcquisitionTransportOwner(tuple(operations))


class _OptionalGlobalFailureNetwork(_LiveShapedAdmissionNetwork):
    """Live-shaped optional-global outcomes with exactly one real RPC attempt."""

    def __init__(self, outcome: str) -> None:
        super().__init__(4)
        self.outcome = outcome
        migrated_mint = self.rows[self.migrated_ordinal]["mint"]
        curve, account = _pump_bonding_curve_account(
            mint=migrated_mint, creator=self.migration_creator, complete=True
        )
        self.pool_accounts[curve] = account

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        if (
            endpoint_role.startswith("CANDIDATE_MIGRATION_")
            and method == "getSignaturesForAddress"
        ):
            return self._result([], method, endpoint_role)
        if endpoint_role == "PUMP_MIGRATION_SIGNATURE_PAGE_1":
            if self.outcome == "malformed_response":
                return self._result({}, method, endpoint_role)
        if endpoint_role == "PUMP_MIGRATION_TRANSACTION_1":
            if self.outcome == "provider_failure":
                self.calls.append((method, endpoint_role))
                raise LiveAcquisitionTransportError(
                    "SOURCE_TRANSPORT_FAILURE", endpoint_role,
                    operation_kind=method,
                )
            if self.outcome == "null_pruned_transaction":
                return self._result(None, method, endpoint_role)
            response = super().rpc_json(
                rpc_url=rpc_url, method=method, params=params,
                timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
                endpoint_role=endpoint_role,
            )
            if self.outcome == "unsupported_contract":
                payload = deepcopy(response.payload)
                payload["version"] = 1
                size = len(json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode())
                return TransportResponse(
                    payload, size, response.operation_kind,
                    response.endpoint_role,
                )
            return response
        return super().rpc_json(
            rpc_url=rpc_url, method=method, params=params,
            timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
            endpoint_role=endpoint_role,
        )


@pytest.mark.parametrize(
    ("outcome", "request_kind", "failure_type", "operation_state"),
    (
        (
            "provider_failure", "pumpfun_migration_transaction",
            "SOURCE_TRANSPORT_FAILURE", "FAILED",
        ),
        (
            "unsupported_contract", "pumpfun_migration_transaction",
            "UNSUPPORTED_PUMP_CONTRACT", "COMPLETE",
        ),
        (
            "malformed_response", "pumpfun_migration_signature_page",
            "SOURCE_MALFORMED", "COMPLETE",
        ),
        (
            "null_pruned_transaction", "pumpfun_migration_transaction",
            "PUMP_TRANSACTION_NULL_OR_PRUNED", "COMPLETE",
        ),
    ),
)
def test_live_shaped_optional_global_failures_persist_reconcile_and_continue(
    outcome: str,
    request_kind: str,
    failure_type: str,
    operation_state: str,
) -> None:
    temp, path = _db()
    try:
        network = _OptionalGlobalFailureNetwork(outcome)
        owner = LiveCandidateAcquisitionTransportOwner(
            LiveAcquisitionConfiguration(
                rpc_url="https://rpc.example.invalid",
                redacted_rpc_host="rpc.example.invalid",
            ),
            transport=network,
        )
        execution_id = f"optional-global-{outcome}"
        report = _run(
            path, mode=MODE_N2, execution_id=execution_id, owner=owner,
        )
        assert report["status"] == "COMPLETED"
        assert report["first_terminal_cause"] == "ACQUISITION_ONLY_COMPLETE"
        assert report["pre_foundation_funnel"]["raw_unique_nominations"] == 4
        assert report["pre_foundation_funnel"]["candidate_cohort_size"] == 4
        assert report["pre_foundation_funnel"]["enrichment_identities"] == 4
        assert report["selected_count"] == 2
        assert report["projection_count"] == 2
        assert report["runtime_handoff_count"] == 0
        observer = report["optional_global_pump_observer"]
        assert observer["required"] is False
        assert observer["admission_authority"] == "NONE"
        assert observer["universal_failure_contribution"] is False
        assert report["operation_accounting"]["identity_mismatch_work_items"] == 0
        assert report["operation_accounting"][
            "frozen_synthesized_detail_work_items"
        ] == 0
        with sqlite3.connect(path) as connection:
            scheduler = connection.execute(
                """SELECT COUNT(*),
                          SUM(status='FAILED'),
                          SUM(status='SUCCEEDED')
                     FROM printer_scheduler_jobs
                    WHERE job_name LIKE ?""",
                (f"candidate-acquisition:{execution_id}:%",),
            ).fetchone()
            governed = connection.execute(
                """SELECT
                       (SELECT COUNT(*) FROM printer_source_requests
                         WHERE request_key LIKE ?),
                       (SELECT COUNT(*) FROM printer_source_responses r
                          JOIN printer_source_requests q ON q.id=r.source_request_id
                         WHERE q.request_key LIKE ?),
                       (SELECT COUNT(*) FROM printer_source_failures f
                          JOIN printer_source_requests q ON q.id=f.source_request_id
                         WHERE q.request_key LIKE ?)""",
                (f"{execution_id}:%",) * 3,
            ).fetchone()
            work = connection.execute(
                """SELECT COUNT(*),SUM(work_state='FAILED'),SUM(rows_used),
                          SUM(bytes_used),SUM(transport_operations_used)
                     FROM printer_candidate_acquisition_work
                    WHERE execution_id=?""",
                (execution_id,),
            ).fetchone()
            failed = connection.execute(
                """SELECT w.first_terminal_cause,o.operation_kind,
                          o.operation_state,o.bytes_used
                     FROM printer_candidate_acquisition_work w
                     JOIN printer_candidate_acquisition_transport_operations o
                       ON o.work_id=w.work_id
                    WHERE w.execution_id=? AND w.request_kind=?
                      AND w.work_state='FAILED'
                    ORDER BY o.operation_ordinal""",
                (execution_id, request_kind),
            ).fetchall()
            failure_row = connection.execute(
                """SELECT f.failure_type
                     FROM printer_source_failures f
                     JOIN printer_source_requests q ON q.id=f.source_request_id
                    WHERE q.request_key LIKE ? AND q.request_kind=?""",
                (f"{execution_id}:%", request_kind),
            ).fetchone()
            failed_ordinal = connection.execute(
                """SELECT work_ordinal
                     FROM printer_candidate_acquisition_work
                    WHERE execution_id=? AND request_kind=?
                      AND work_state='FAILED'""",
                (execution_id, request_kind),
            ).fetchone()[0]
            operation_count, operation_bytes = connection.execute(
                """SELECT COUNT(*),COALESCE(SUM(o.bytes_used),0)
                     FROM printer_candidate_acquisition_transport_operations o
                     JOIN printer_candidate_acquisition_work w
                       ON w.work_id=o.work_id
                    WHERE w.execution_id=?""",
                (execution_id,),
            ).fetchone()
        assert scheduler[0] == report["scheduler_jobs_created"]
        assert scheduler[1] == 1
        assert governed == (
            report["governed_requests_used"],
            report["governed_responses"],
            report["governed_failures"],
        )
        assert work[0] == report["governed_requests_used"]
        assert work[1] == 1
        assert work[2] == report["rows_used"]
        assert work[3] == report["bytes_used"]
        assert work[4] == report["transport_operations_used"]
        assert operation_count == report["transport_operations_used"]
        assert operation_bytes == report["bytes_used"]
        assert failure_row == (failure_type,)
        assert len(failed) == 1
        assert failed[0][0] == failure_type
        assert failed[0][1] in {
            "getTransaction", "getSignaturesForAddress",
        }
        assert failed[0][2] == operation_state
        declared_plan = next(
            item for item in report["operation_accounting"]["predeclared_plans"]
            if item["work_ordinal"] == failed_ordinal
        )
        assert declared_plan["declared_operation_ceiling"] == 1
        assert declared_plan["operation_kinds"] in (
            ["getTransaction"], ["getSignaturesForAddress"],
        )
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=execution_id
        ) == report
    finally:
        temp.cleanup()


def test_optional_accounting_mismatch_persists_all_evidence_and_stops() -> None:
    temp, path = _db()
    try:
        operations = list(_owner(4).frozen_operations)
        global_index = next(
            index for index, operation in enumerate(operations)
            if operation.request_kind == "pumpfun_migration_signature_page"
        )
        operations.insert(
            global_index + 1,
            AcquisitionSourceOperation(
                source_name="solana_rpc",
                request_kind="pumpfun_migration_transaction",
                adapter=_adapter("solana_rpc", {
                    "candidate_observations": [{
                        "mint": _candidate_rows(1)[0]["mint"],
                        "base_mint": _candidate_rows(1)[0]["mint"],
                        "facts": {},
                    }],
                    "underlying_operation_count": 2,
                    "underlying_operations": [
                        {
                            "operation_kind": "getTransaction",
                            "operation_state": "COMPLETE",
                            "redacted_endpoint_role": "OPTIONAL_GLOBAL_PRIMARY",
                            "bytes_used": 7,
                        },
                        {
                            "operation_kind": "getTransaction",
                            "operation_state": "COMPLETE",
                            "redacted_endpoint_role": "UNDECLARED_SECOND_CALL",
                            "bytes_used": 11,
                        },
                    ],
                    "response_bytes": 18,
                    "declared_operation_ceiling": True,
                }),
                required=False,
                expected_transport_operations=1,
                observation_scope="GLOBAL_OPTIONAL",
            ),
        )
        execution_id = "optional-accounting-mismatch"
        report = _run(
            path, mode=MODE_N2, execution_id=execution_id,
            owner=FrozenAcquisitionTransportOwner(tuple(operations)),
        )
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "OPERATION_ACCOUNTING_MISMATCH"
        assert report["manifest_id"] is None
        assert report["operation_accounting"]["identity_mismatch_work_items"] == 1
        with sqlite3.connect(path) as connection:
            work = connection.execute(
                """SELECT work_state,first_terminal_cause,
                          transport_operations_used,bytes_used,rows_used
                     FROM printer_candidate_acquisition_work
                    WHERE execution_id=? AND request_kind=
                          'pumpfun_migration_transaction'""",
                (execution_id,),
            ).fetchone()
            operations_persisted = connection.execute(
                    """SELECT o.operation_kind,o.operation_state,o.bytes_used
                     FROM printer_candidate_acquisition_transport_operations o
                     JOIN printer_candidate_acquisition_work w
                       ON w.work_id=o.work_id
                    WHERE w.execution_id=? AND
                          w.request_kind='pumpfun_migration_transaction'
                    ORDER BY operation_ordinal""",
                (execution_id,),
            ).fetchall()
        assert work == (
            "FAILED", "OPERATION_ACCOUNTING_MISMATCH", 2, 18, 1,
        )
        assert operations_persisted == [
            ("getTransaction", "COMPLETE", 7),
            ("getTransaction", "COMPLETE", 11),
        ]
        assert replay_candidate_acquisition_integration_report(
            path, execution_id=execution_id
        ) == report
    finally:
        temp.cleanup()


def test_equal_count_wrong_operation_identity_persists_and_stops() -> None:
    temp, path = _db()
    try:
        operations = list(_owner(4).frozen_operations)
        global_index = next(
            index for index, operation in enumerate(operations)
            if operation.request_kind == "pumpfun_migration_signature_page"
        )
        operations.insert(
            global_index + 1,
            AcquisitionSourceOperation(
                source_name="solana_rpc",
                request_kind="pumpfun_migration_transaction",
                adapter=_adapter("solana_rpc", {
                    "candidate_observations": [],
                    "underlying_operation_count": 1,
                    "underlying_operations": [{
                        "operation_kind": "getMultipleAccounts",
                        "operation_state": "COMPLETE",
                        "redacted_endpoint_role": "WRONG_METHOD",
                        "bytes_used": 13,
                    }],
                    "response_bytes": 13,
                    "declared_operation_ceiling": True,
                }),
                required=False,
                expected_transport_operations=1,
                observation_scope="GLOBAL_OPTIONAL",
            ),
        )
        execution_id = "optional-operation-identity-mismatch"
        report = _run(
            path, mode=MODE_N2, execution_id=execution_id,
            owner=FrozenAcquisitionTransportOwner(tuple(operations)),
        )
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "OPERATION_ACCOUNTING_MISMATCH"
        with sqlite3.connect(path) as connection:
            persisted = connection.execute(
                """SELECT w.work_state,w.first_terminal_cause,
                          o.operation_kind,o.bytes_used
                     FROM printer_candidate_acquisition_work w
                     JOIN printer_candidate_acquisition_transport_operations o
                       ON o.work_id=w.work_id
                    WHERE w.execution_id=?
                      AND w.request_kind='pumpfun_migration_transaction'""",
                (execution_id,),
            ).fetchone()
        assert persisted == (
            "FAILED", "OPERATION_ACCOUNTING_MISMATCH",
            "getMultipleAccounts", 13,
        )
    finally:
        temp.cleanup()


def test_predeclared_transport_ceiling_remains_universally_fail_closed() -> None:
    temp, path = _db()
    try:
        operations = list(_owner(4).frozen_operations)
        operations[0] = AcquisitionSourceOperation(
            source_name="dexscreener",
            request_kind="candidate_nomination",
            adapter=_adapter("dexscreener", {}),
            required=False,
            expected_transport_operations=33,
        )
        report = _run(
            path, mode=MODE_N2, execution_id="transport-ceiling",
            owner=FrozenAcquisitionTransportOwner(tuple(operations)),
        )
        assert report["status"] == "BLOCKED"
        assert report["first_terminal_cause"] == "TRANSPORT_OPERATION_CEILING"
        assert report["scheduler_jobs_created"] == 0
        assert report["governed_requests_used"] == 0
        assert report["transport_operations_used"] == 0
        assert report["manifest_id"] is None
    finally:
        temp.cleanup()


@pytest.mark.parametrize(
    "observer_status",
    ("GAPPED", "UNKNOWN", "UNAVAILABLE", "BLOCKED_CONTRACT", "NOT_RUN"),
)
@pytest.mark.parametrize(
    ("non_pump", "expected_lineage"),
    ((False, "UNKNOWN_ORIGIN"), (True, "NON_PUMP_POOL_CONFIRMED")),
)
def test_generic_and_non_pump_admission_ignore_optional_global_outcomes(
    observer_status: str, non_pump: bool, expected_lineage: str,
) -> None:
    temp, path = _db()
    try:
        report = _run(
            path, mode=MODE_N2,
            execution_id=f"optional-{observer_status}-{int(non_pump)}",
            owner=_optional_observer_owner(
                observer_status=observer_status, non_pump=non_pump
            ),
        )
        assert report["status"] == "COMPLETED"
        assert report["selected_count"] == 2
        assert report["optional_global_pump_observer"][
            "universal_failure_contribution"
        ] is False
        with sqlite3.connect(path) as connection:
            assert {
                str(row[0]) for row in connection.execute(
                    "SELECT lineage_state FROM printer_candidate_identities"
                )
            } == {expected_lineage}
    finally:
        temp.cleanup()


class _CandidateLookupFailureNetwork(_LiveShapedAdmissionNetwork):
    def __init__(self, outcome: str) -> None:
        super().__init__(4)
        self.outcome = outcome
        migrated_mint = self.rows[self.migrated_ordinal]["mint"]
        curve, account = _pump_bonding_curve_account(
            mint=migrated_mint, creator=self.migration_creator, complete=True
        )
        self.pool_accounts[curve] = account

    def rpc_json(self, *, rpc_url, method, params, timeout_seconds, byte_ceiling,
                 endpoint_role):
        if endpoint_role.startswith("CANDIDATE_MIGRATION_PUMPSWAP_POOL_"):
            if self.outcome == "provider":
                raise LiveAcquisitionTransportError(
                    "SOURCE_TRANSPORT_FAILURE", endpoint_role,
                    operation_kind=method,
                )
            payload = (
                {}
                if self.outcome == "malformed"
                else []
                if self.outcome == "empty"
                else [{
                    "signature": self.MIGRATION_SIGNATURE,
                    "slot": 498,
                    "err": {"InstructionError": [0, "Custom"]},
                    "confirmationStatus": "finalized",
                }]
                if self.outcome == "no_match"
                else [{
                    "signature": self.MIGRATION_SIGNATURE,
                    "slot": 498, "err": None,
                    "confirmationStatus": "finalized",
                }]
            )
            return self._result(payload, method, endpoint_role)
        if endpoint_role.startswith("CANDIDATE_MIGRATION_TRANSACTION_"):
            if self.outcome == "null_transaction":
                return self._result(None, method, endpoint_role)
            response = super().rpc_json(
                rpc_url=rpc_url, method=method, params=params,
                timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
                endpoint_role=endpoint_role,
            )
            payload = deepcopy(response.payload)
            if self.outcome == "unsupported":
                payload["version"] = 1
            elif self.outcome == "ambiguity":
                payload["transaction"]["message"]["instructions"].append(
                    deepcopy(payload["transaction"]["message"]["instructions"][0])
                )
            return TransportResponse(
                payload, response.bytes_used, response.operation_kind,
                response.endpoint_role,
            )
        return super().rpc_json(
            rpc_url=rpc_url, method=method, params=params,
            timeout_seconds=timeout_seconds, byte_ceiling=byte_ceiling,
            endpoint_role=endpoint_role,
        )


@pytest.mark.parametrize(
    ("outcome", "reason"),
    (
        ("empty", "CANDIDATE_MIGRATION_HISTORY_UNAVAILABLE"),
        ("no_match", "CANDIDATE_MIGRATION_NOT_FOUND_WITHIN_BOUND"),
        ("provider", "CANDIDATE_MIGRATION_PROVIDER_UNAVAILABLE"),
        ("malformed", "CANDIDATE_MIGRATION_PAGE_MALFORMED"),
        ("null_transaction", "CANDIDATE_MIGRATION_TRANSACTION_NULL_OR_PRUNED"),
        ("unsupported", "CANDIDATE_MIGRATION_UNSUPPORTED_VERSION"),
        ("ambiguity", "CANDIDATE_MIGRATION_AMBIGUOUS"),
    ),
)
def test_candidate_migration_failures_are_precise_and_never_downgrade(
    outcome: str, reason: str,
) -> None:
    temp, path = _db()
    try:
        network = _CandidateLookupFailureNetwork(outcome)
        owner = LiveCandidateAcquisitionTransportOwner(
            LiveAcquisitionConfiguration(
                rpc_url="https://rpc.example.invalid",
                redacted_rpc_host="rpc.example.invalid",
                global_pump_observer_enabled=False,
            ),
            transport=network,
        )
        report = _run(
            path, mode=MODE_N2, execution_id=f"candidate-failure-{outcome}",
            owner=owner,
        )
        # Unrelated active-Pump/generic candidates remain independently
        # admissible even though this explicit graduation branch is rejected.
        assert report["status"] == "COMPLETED"
        with sqlite3.connect(path) as connection:
            failure_rows = connection.execute(
                """SELECT mint_identity,lineage_state
                     FROM printer_candidate_identities
                    WHERE lineage_state='UNSUPPORTED_LINEAGE'"""
            ).fetchall()
            assert len(failure_rows) == 1
            facts = [
                json.loads(str(row[0]))
                for row in connection.execute(
                    """SELECT facts_json
                         FROM printer_candidate_source_observations
                        WHERE json_extract(
                            facts_json,'$.pump_migration_failure_reason'
                        )=?""",
                    (reason,),
                )
            ]
            assert facts
            assert all(
                fact["pump_migration_branch"] == PUMP_GRADUATION_CLAIMED
                and fact["candidate_migration_fallback_allowed"] is False
                for fact in facts
            )
    finally:
        temp.cleanup()


def test_compact_storage_positive_global_locator_and_zero_source_replay(capsys) -> None:
    temp, path = _db()
    try:
        network = _LiveShapedAdmissionNetwork(4)
        report = _dispatch(
            capsys, path, CLI_MODE_N2, network, "compact-decoupled-storage"
        )
        assert report["status"] == "COMPLETED"
        assert report["optional_global_pump_observer"]["required"] is False
        calls = len(network.calls)
        replay = replay_candidate_acquisition_integration_report(
            path, execution_id="compact-decoupled-storage"
        )
        assert replay == report
        assert len(network.calls) == calls
        with sqlite3.connect(path) as connection:
            payloads = [
                json.loads(str(row[0]))
                for row in connection.execute(
                    """SELECT normalized_payload_json
                         FROM printer_source_responses
                        WHERE source_name='solana_rpc'"""
                )
                if row[0]
            ]
            global_pages = [
                payload["page_summary"] for payload in payloads
                if isinstance(payload.get("page_summary"), dict)
                and payload["page_summary"].get("locator_kind")
                    == "GLOBAL_PUMP_PROGRAM"
            ]
            assert global_pages
            assert all(
                len(page["page_hash"]) == 64
                and page["raw_signature_rows_persisted"] is False
                for page in global_pages
            )
            assert any(
                payload.get("positive_migration_match")
                for payload in payloads
            )
            assert any(
                payload.get("positive_joined_evidence")
                for payload in payloads
            )
            assert connection.execute(
                """SELECT required_source,cursor_range_json
                     FROM printer_candidate_acquisition_work
                    WHERE request_kind='pumpfun_migration_signature_page'
                    ORDER BY work_ordinal LIMIT 1"""
            ).fetchone()[0] == 0
            assert connection.execute(
                """SELECT cursor_range_json
                     FROM printer_candidate_acquisition_work
                    WHERE request_kind='pumpswap_pool_account_batch'"""
            ).fetchone()[0] is None
        encoded = json.dumps(payloads, sort_keys=True)
        assert '"signatures":[' not in encoded
        assert '"raw_signature_rows"' not in encoded
        assert report["automatic_retry_created"] is False
        assert report["restart_created"] is False
        assert report["successor_created"] is False
    finally:
        temp.cleanup()


def test_pumpswap_presence_only_stays_unknown_and_active_curve_skips_migration(
    capsys,
) -> None:
    temp_u, path_u = _db()
    temp_a, path_a = _db()
    try:
        unknown_network = _CanonicalMockNetworkTransport(4)
        unknown = _dispatch(
            capsys, path_u, CLI_MODE_N2, unknown_network,
            "pumpswap-presence-only",
        )
        assert unknown["status"] == "COMPLETED"
        with sqlite3.connect(path_u) as connection:
            assert {
                str(row[0]) for row in connection.execute(
                    "SELECT lineage_state FROM printer_candidate_identities"
                )
            } == {"UNKNOWN_ORIGIN"}
        assert not any(
            role.startswith("CANDIDATE_MIGRATION_TRANSACTION_")
            for _method, role in unknown_network.calls
        )

        active_network = _LiveShapedAdmissionNetwork(4)
        active = _dispatch(
            capsys, path_a, CLI_MODE_N2, active_network,
            "active-curve-no-migration",
        )
        assert active["status"] == "COMPLETED"
        with sqlite3.connect(path_a) as connection:
            active_rows = connection.execute(
                """SELECT mint_identity
                     FROM printer_candidate_identities
                    WHERE lineage_state='PUMP_ORIGIN_CONFIRMED'"""
            ).fetchall()
            assert len(active_rows) == 1
        # Exactly the separately claimed graduated candidate is verified; the
        # active curve never enters migration work.
        assert sum(
            role.startswith("CANDIDATE_MIGRATION_TRANSACTION_")
            for _method, role in active_network.calls
        ) == 1
    finally:
        temp_u.cleanup()
        temp_a.cleanup()


def test_candidate_budget_and_identity_failures_keep_exact_families() -> None:
    rows = _candidate_rows(2)
    budget_row = {
        "mint": rows[0]["mint"],
        "base_mint": rows[0]["mint"],
        "lineage_claim": "UNKNOWN_ORIGIN",
    }
    owner = _owner(2)
    operations = list(owner.frozen_operations)
    pool_index = next(
        index for index, operation in enumerate(operations)
        if operation.request_kind == "pumpswap_pool_account_batch"
    )
    operations[pool_index] = _operation(
        "solana_rpc", "pumpswap_pool_account_batch",
        [budget_row, rows[1]],
        {"pool_status": "PASS"},
        phase="ENRICHMENT",
    )
    failure_index = next(
        index for index, operation in enumerate(operations)
        if operation.request_kind == "candidate_pumpswap_pool_verification"
    )
    operations[failure_index] = _operation(
        "solana_rpc", "candidate_pumpswap_pool_verification",
        [budget_row],
        {
            "pump_migration_branch": PUMP_GRADUATION_CLAIMED,
            "pump_migration_failure_family": "BUDGET_EXHAUSTION",
            "pump_migration_failure_reason": (
                "CANDIDATE_MIGRATION_PREDECLARED_BUDGET_EXHAUSTED"
            ),
            "candidate_migration_fallback_allowed": False,
        },
        required=False, transport_operations=0, phase="ENRICHMENT",
    )
    temp_b, path_b = _db()
    temp_i, path_i = _db()
    try:
        budget = _run(
            path_b, mode=MODE_N2, execution_id="candidate-budget-family",
            owner=FrozenAcquisitionTransportOwner(tuple(operations)),
        )
        assert budget["status"] == "BLOCKED"
        assert budget["first_terminal_cause"] == "BUDGET_EXHAUSTION"

        identity = _run(
            path_i, mode=MODE_N2, execution_id="candidate-identity-family",
            owner=_owner(2, identity_conflict=True),
        )
        assert identity["status"] == "BLOCKED"
        assert identity["first_terminal_cause"] == "IDENTITY_MERGE_FAILURE"
    finally:
        temp_b.cleanup()
        temp_i.cleanup()
