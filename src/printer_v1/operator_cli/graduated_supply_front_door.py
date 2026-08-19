"""V2-9.8B corrective adapter for graduated candidate-supply composition.

The exact pre-repair implementation is preserved byte-for-byte in
``_graduated_supply_front_door_base``.  This adapter owns only two bounded
correctives proven by the consumed Cycle-2 audit:

* rejoin immutable direct-Pump graduation evidence for an exact historical
  ``PUMPSWAP_GRADUATED_CONFIRMED`` registry candidate before the existing
  source-specific admission validator consumes it; and
* surface stable categorical ``GraduatedSupplyError`` codes/context while
  preserving the original validator and every source/gate/selection owner.

It adds no source call, retry, provider, score, rank, confidence, scheduler path,
lifecycle path, financial capability, liquidity rule, or freeze/selection rule.
"""
from __future__ import annotations

from contextvars import ContextVar
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from printer_v1.operator_cli import _graduated_supply_front_door_base as _base

# Re-export the exact existing surface first, including private compatibility
# helpers imported directly by focused tests and operational owners.
for _name in dir(_base):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_base, _name)


class GraduatedSupplyError(RuntimeError):
    """Typed, bounded graduated-supply composition fault."""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        stage: str | None = None,
        mint: str | None = None,
        pool: str | None = None,
        admission_authority: str | None = None,
        nomination_source: str | None = None,
    ) -> None:
        self.code = _normalize_code(code)
        self.stage = _bounded(stage)
        self.mint = _bounded(mint)
        self.pool = _bounded(pool)
        self.admission_authority = _bounded(admission_authority)
        self.nomination_source = _bounded(nomination_source)
        # ``detail`` is retained for compatibility with the existing safe-code
        # exception protocol.  It is bounded metadata only, never a provider body.
        details = [
            value
            for value in (
                self.stage,
                self.mint,
                self.pool,
                self.admission_authority,
                self.nomination_source,
            )
            if value
        ]
        self.detail = "|".join(details)[:512]
        super().__init__(str(message or self.code)[:768])


def _bounded(value: object | None, limit: int = 192) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _normalize_code(value: object) -> str:
    raw = str(value or "").strip().upper()
    normalized = "".join(
        character if (character.isalnum() or character == "_") else "_"
        for character in raw
    )
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    normalized = normalized.strip("_")
    return normalized or "GRADUATED_SUPPLY_ERROR"


def _code_from_legacy_message(message: object) -> str:
    head = str(message or "").split(":", 1)[0].strip()
    candidate = _normalize_code(head)
    # Preserve only a categorical token; arbitrary prose remains the generic
    # graduated-supply category rather than becoming a terminal identifier.
    if head and all(ch.isupper() or ch.isdigit() or ch == "_" for ch in head):
        return candidate
    return "GRADUATED_SUPPLY_ERROR"


def _typed_error_class(code: str) -> type[GraduatedSupplyError]:
    """Return one stable code-named subclass for the existing class fallback.

    The live campaign's pre-existing safe identifier keeps an allow-list of
    exception classes and otherwise uses ``exc.__class__.__name__``.  A
    categorical subclass therefore preserves the exact code without changing
    that campaign owner or admitting arbitrary exception strings.
    """
    normalized = _normalize_code(code)
    existing = globals().get(normalized)
    if isinstance(existing, type) and issubclass(existing, GraduatedSupplyError):
        return existing
    created = type(normalized, (GraduatedSupplyError,), {"__module__": __name__})
    globals()[normalized] = created
    return created


def _typed_error(
    code: str,
    *,
    message: str | None = None,
    stage: str | None = None,
    mint: str | None = None,
    pool: str | None = None,
    admission_authority: str | None = None,
    nomination_source: str | None = None,
) -> GraduatedSupplyError:
    cls = _typed_error_class(code)
    error = cls(
        code,
        message=message,
        stage=stage,
        mint=mint,
        pool=pool,
        admission_authority=admission_authority,
        nomination_source=nomination_source,
    )
    _stage_active_pre_admission_diagnostic(error)
    return error


def _stage_for_code(code: str, default: str) -> str:
    if "OBSERVATION_TIME" in code or "GRADUATION_TIME" in code:
        return "CANDIDATE_TEMPORAL_CONTEXT"
    return default


_ACTIVE_DB_PATH: ContextVar[str | None] = ContextVar(
    "graduated_supply_active_db_path", default=None
)
_ORIGINAL_SOURCE_SPECIFIC_ADMISSION = _base._source_specific_admission_for
_ORIGINAL_BUILD_GRADUATED_SUPPLY = _base.build_graduated_supply


def _stage_active_pre_admission_diagnostic(error: GraduatedSupplyError) -> None:
    """Stage bounded context for the exact active Cycle-2 Scheduler job.

    Diagnostic staging is deliberately non-authoritative: zero or ambiguous
    matching jobs do nothing, and a staging fault can never replace the original
    supply failure or create a new admission decision.
    """
    db_path = _ACTIVE_DB_PATH.get()
    if not db_path:
        return
    try:
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT id
                FROM printer_scheduler_jobs
                WHERE job_kind = 'PRE_ADMISSION_DISCOVERY_SELECTION'
                  AND status = 'RUNNING'
                  AND locked_at IS NOT NULL
                  AND length(trim(COALESCE(lock_owner, ''))) > 0
                ORDER BY id
                LIMIT 2
                """
            ).fetchall()
        finally:
            connection.close()
        if len(rows) != 1:
            return
        from printer_v1.scheduler.scheduler import stage_job_failure_diagnostic

        stage_job_failure_diagnostic(
            job_id=int(rows[0]["id"]),
            failure_code=error.code,
            context={
                "stage": error.stage,
                "mint": error.mint,
                "pool": error.pool,
                "admission_authority": error.admission_authority,
                "nomination_source": error.nomination_source,
            },
        )
    except Exception:
        return


def _rehydrate_historical_direct_candidate(
    item: Mapping[str, Any],
    *,
    db_path: str | Path | None,
) -> dict[str, Any]:
    """Rejoin immutable registry proof for one exact historical candidate.

    This is zero-source, exact-mint+pool only, and is deliberately inapplicable
    to ``MARKET_PRESENT_POOL`` candidates.  A synthetic protocol-resume carrier
    with no durable graduated-registry row is left untouched; it is never
    relabelled as direct Pump evidence.
    """
    materialized = dict(item)
    if isinstance(materialized.get("direct_pump_evidence"), Mapping):
        return materialized
    if str(materialized.get("admission_authority") or "").strip() == "MARKET_PRESENT_POOL":
        return materialized
    if db_path is None:
        return materialized

    mint = str(materialized.get("mint") or "").strip()
    pool = str(
        materialized.get("pool") or materialized.get("pumpswap_pool") or ""
    ).strip()
    if not mint or not pool:
        return materialized

    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        row = _base.lookup_graduated_candidate(connection, mint)
    finally:
        connection.close()
    if row is None:
        return materialized
    if str(row.get("lifecycle_state") or "") != "PUMPSWAP_GRADUATED_CONFIRMED":
        return materialized
    registry_pool = str(row.get("pumpswap_pool") or "").strip()
    if registry_pool != pool:
        raise _typed_error(
            "DIRECT_PUMP_EVIDENCE_MISMATCH",
            stage="SOURCE_SPECIFIC_ADMISSION",
            mint=mint,
            pool=pool,
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            nomination_source="direct_pump_migration",
        )

    signature = str(row.get("migration_signature") or "").strip()
    program_id = str(row.get("pumpswap_program_id") or "").strip()
    graduation_time = row.get("graduation_block_time")
    if (
        not signature
        or program_id != _base.PUMPSWAP_PROGRAM_ID
        or type(graduation_time) is not int
        or graduation_time <= 0
    ):
        raise _typed_error(
            "DIRECT_PUMP_EVIDENCE_MISSING",
            stage="SOURCE_SPECIFIC_ADMISSION",
            mint=mint,
            pool=pool,
            admission_authority="DIRECT_PUMP_PUMPSWAP",
            nomination_source="direct_pump_migration",
        )

    materialized.update(
        {
            "direct_pump_evidence": {
                "mint": mint,
                "pool": pool,
                "migration_signature": signature,
                "pumpswap_program_id": program_id,
                "graduation_slot": row.get("graduation_slot"),
                "graduation_block_time": graduation_time,
                "confirmed": True,
            },
            "admission_authority": "DIRECT_PUMP_PUMPSWAP",
            "nomination_source": "direct_pump_migration",
            "lineage_state": "PUMP_GRADUATION_CONFIRMED",
            "exact_present_pool_confirmed": True,
        }
    )
    return materialized


def _convert_base_error(
    exc: BaseException,
    *,
    item: Mapping[str, Any] | None = None,
    default_stage: str = "GRADUATED_SUPPLY_COMPOSITION",
) -> GraduatedSupplyError:
    message = str(exc)
    code = _code_from_legacy_message(message)
    carrier = dict(item or {})
    return _typed_error(
        code,
        message=message,
        stage=_stage_for_code(code, default_stage),
        mint=str(carrier.get("mint") or "").strip() or None,
        pool=str(carrier.get("pool") or carrier.get("pumpswap_pool") or "").strip()
        or None,
        admission_authority=str(carrier.get("admission_authority") or "").strip()
        or None,
        nomination_source=str(
            carrier.get("nomination_source") or carrier.get("provenance") or ""
        ).strip()
        or None,
    )


def _source_specific_admission_for(
    item: Mapping[str, Any],
):
    """Apply the exact existing validator after bounded historical proof rejoin."""
    materialized = _rehydrate_historical_direct_candidate(
        item, db_path=_ACTIVE_DB_PATH.get()
    )
    try:
        return _ORIGINAL_SOURCE_SPECIFIC_ADMISSION(materialized)
    except _base.GraduatedSupplyError as exc:
        raise _convert_base_error(
            exc,
            item=materialized,
            default_stage="SOURCE_SPECIFIC_ADMISSION",
        ) from exc


def build_graduated_supply(
    db_path: str | Path,
    *args: Any,
    **kwargs: Any,
):
    """Run the existing supply owner with exact historical-proof context bound."""
    token = _ACTIVE_DB_PATH.set(str(db_path))
    try:
        return _ORIGINAL_BUILD_GRADUATED_SUPPLY(db_path, *args, **kwargs)
    except GraduatedSupplyError:
        raise
    except _base.GraduatedSupplyError as exc:
        raise _convert_base_error(exc) from exc
    finally:
        _ACTIVE_DB_PATH.reset(token)


# The preserved base build resolves this name dynamically from its own module.
# Rebind only this validation seam; every other base owner/function stays exact.
_base._source_specific_admission_for = _source_specific_admission_for

# Public overrides after the compatibility re-export above.
globals()["GraduatedSupplyError"] = GraduatedSupplyError
globals()["_source_specific_admission_for"] = _source_specific_admission_for
globals()["build_graduated_supply"] = build_graduated_supply
globals()["_rehydrate_historical_direct_candidate"] = (
    _rehydrate_historical_direct_candidate
)
