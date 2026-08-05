"""Central temporal validity law for one-use WINDOW_15M authorizations.

Pure validation only: no staging, marker creation, network I/O, or DB writes.
Called before any consumption side effect so temporal failures leave packages
unconsumed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


# Single centrally owned maximum-age / maximum-validity policy.
AUTHORIZATION_MAX_VALIDITY_SECONDS = 86400
# Small clock skew tolerance for "future issued" only (not for expiry extension).
_ISSUE_CLOCK_SKEW_SECONDS = 60


class AuthorizationTemporalError(ValueError):
    """Raised when an authorization fails temporal validity."""


def _require_aware_utc(value: Any, *, label: str) -> datetime:
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise AuthorizationTemporalError(f"AUTHORIZATION_{label}_MISSING")
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        # Accept trailing Z and nanosecond-truncated fractional seconds by clipping
        # to microseconds for fromisoformat.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "." in text:
            head, rest = text.split(".", 1)
            # rest may be "555929+00:00" or "555929000Z"-style already normalized
            digits = []
            tz_part = ""
            for i, ch in enumerate(rest):
                if ch.isdigit():
                    digits.append(ch)
                else:
                    tz_part = rest[i:]
                    break
            frac = "".join(digits)
            if len(frac) > 6:
                frac = frac[:6]
            elif len(frac) < 6:
                frac = frac.ljust(6, "0")
            text = f"{head}.{frac}{tz_part}"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise AuthorizationTemporalError(
                f"AUTHORIZATION_{label}_MALFORMED"
            ) from exc
    if parsed.tzinfo is None:
        raise AuthorizationTemporalError(f"AUTHORIZATION_{label}_NAIVE_TIMEZONE")
    return parsed.astimezone(timezone.utc)


def validate_authorization_temporal_validity(
    document: Mapping[str, Any],
    *,
    now: datetime | None = None,
    max_validity_seconds: int = AUTHORIZATION_MAX_VALIDITY_SECONDS,
) -> dict[str, object]:
    """Validate authorization temporal fields before staging or consumption.

    Required:
    * timezone-aware issue time (``authorized_at``)
    * timezone-aware expiry later than issue (``expires_at`` or derived from
      ``validity_seconds``)
    * current time within the valid interval
    * validity span and issue age within the central maximum-age policy

    Missing, malformed, future-issued, over-age, or expired packages fail.
    """
    if not isinstance(document, Mapping):
        raise AuthorizationTemporalError("AUTHORIZATION_DOCUMENT_NOT_OBJECT")

    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise AuthorizationTemporalError("AUTHORIZATION_NOW_NAIVE_TIMEZONE")
    current = current.astimezone(timezone.utc)

    issued = _require_aware_utc(document.get("authorized_at"), label="ISSUE_TIME")

    expires_raw = document.get("expires_at")
    validity_raw = document.get("validity_seconds")
    validity_seconds: int | None = None
    if validity_raw is not None and str(validity_raw).strip() != "":
        try:
            validity_seconds = int(validity_raw)
        except (TypeError, ValueError) as exc:
            raise AuthorizationTemporalError(
                "AUTHORIZATION_VALIDITY_SECONDS_MALFORMED"
            ) from exc
        if validity_seconds <= 0:
            raise AuthorizationTemporalError(
                "AUTHORIZATION_VALIDITY_SECONDS_NON_POSITIVE"
            )
        if validity_seconds > int(max_validity_seconds):
            raise AuthorizationTemporalError(
                "AUTHORIZATION_OVER_MAX_AGE_POLICY"
            )

    if expires_raw is not None and str(expires_raw).strip() != "":
        expires = _require_aware_utc(expires_raw, label="EXPIRY_TIME")
    elif validity_seconds is not None:
        expires = issued + timedelta(seconds=validity_seconds)
    else:
        raise AuthorizationTemporalError("AUTHORIZATION_EXPIRY_TIME_MISSING")

    if expires <= issued:
        raise AuthorizationTemporalError("AUTHORIZATION_EXPIRY_NOT_AFTER_ISSUE")

    span_seconds = (expires - issued).total_seconds()
    if span_seconds > float(max_validity_seconds):
        raise AuthorizationTemporalError("AUTHORIZATION_OVER_MAX_AGE_POLICY")

    # Future-issued beyond skew.
    if issued > current + timedelta(seconds=_ISSUE_CLOCK_SKEW_SECONDS):
        raise AuthorizationTemporalError("AUTHORIZATION_FUTURE_ISSUED")

    if current < issued:
        raise AuthorizationTemporalError("AUTHORIZATION_NOT_YET_VALID")

    if current > expires:
        raise AuthorizationTemporalError("AUTHORIZATION_EXPIRED")

    age_seconds = (current - issued).total_seconds()
    if age_seconds > float(max_validity_seconds):
        raise AuthorizationTemporalError("AUTHORIZATION_OVER_AGE")

    return {
        "status": "TEMPORALLY_VALID",
        "authorized_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "validity_seconds": validity_seconds
        if validity_seconds is not None
        else int(span_seconds),
        "max_validity_seconds": int(max_validity_seconds),
        "age_seconds": int(age_seconds),
        "remaining_seconds": int((expires - current).total_seconds()),
        "evaluated_at": current.isoformat(),
    }


__all__ = [
    "AUTHORIZATION_MAX_VALIDITY_SECONDS",
    "AuthorizationTemporalError",
    "validate_authorization_temporal_validity",
]
