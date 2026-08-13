"""Canonical identity-only token/pair projection for Solana discovery owners.

This owner creates only the neutral database identities required to reference a
candidate.  Tracking activation remains the responsibility of the combined
handoff/admission owners.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3


class TokenPairIdentityError(ValueError):
    """Fail-closed token/pair identity projection error."""


@dataclass(frozen=True)
class NeutralTokenPairIdentity:
    token_row_id: int
    pair_row_id: int
    mint_identity: str
    pair_identity: str


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise TokenPairIdentityError(f"{label.upper()}_INVALID")
    return value


def ensure_neutral_token_pair_identity(
    connection: sqlite3.Connection,
    *,
    mint_identity: str,
    pair_identity: str,
) -> NeutralTokenPairIdentity:
    """Find/create one exact token and canonical pair without activation.

    Newly created tokens deliberately keep ``token_status`` NULL.  The caller
    owns its transaction and any later lifecycle transition.
    """
    mint = _identity(mint_identity, "mint_identity")
    pair = _identity(pair_identity, "pair_identity")
    token_row = connection.execute(
        "SELECT id FROM printer_tokens WHERE token_mint=?", (mint,)
    ).fetchone()
    pair_row = connection.execute(
        "SELECT id,token_id,base_token_mint FROM printer_pairs WHERE pair_address=?",
        (pair,),
    ).fetchone()

    if pair_row is not None:
        if token_row is None:
            raise TokenPairIdentityError("PAIR_TOKEN_IDENTITY_MISMATCH")
        base_mint = pair_row[2]
        if int(pair_row[1]) != int(token_row[0]) or (
            base_mint is not None and str(base_mint) != mint
        ):
            raise TokenPairIdentityError("PAIR_TOKEN_IDENTITY_MISMATCH")
        return NeutralTokenPairIdentity(
            token_row_id=int(token_row[0]),
            pair_row_id=int(pair_row[0]),
            mint_identity=mint,
            pair_identity=pair,
        )

    if token_row is None:
        token_id = int(connection.execute(
            "INSERT INTO printer_tokens(token_mint,token_status) VALUES (?,NULL)",
            (mint,),
        ).lastrowid)
    else:
        token_id = int(token_row[0])
    pair_id = int(connection.execute(
        "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
        (token_id, pair, mint),
    ).lastrowid)
    return NeutralTokenPairIdentity(
        token_row_id=token_id,
        pair_row_id=pair_id,
        mint_identity=mint,
        pair_identity=pair,
    )
