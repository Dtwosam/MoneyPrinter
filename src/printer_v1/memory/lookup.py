"""Local episode lookup helpers without matching or recommendations."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from printer_v1.memory.contracts import MemoryQualityLabel


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return
    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def find_episode_by_window(db_path_or_conn: str | Path | sqlite3.Connection, memory_window_id: int) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            "SELECT * FROM printer_episodes WHERE memory_window_id = ? ORDER BY id DESC LIMIT 1",
            (memory_window_id,),
        ).fetchone()


def find_latest_episode_for_token_pair(db_path_or_conn: str | Path | sqlite3.Connection, token_id: int, pair_id: int | None) -> sqlite3.Row | None:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT * FROM printer_episodes
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (token_id, pair_id),
        ).fetchone()


def find_episodes_for_token_pair(db_path_or_conn: str | Path | sqlite3.Connection, token_id: int, pair_id: int | None) -> list[sqlite3.Row]:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT * FROM printer_episodes
            WHERE token_id = ?
              AND COALESCE(pair_id, -1) = COALESCE(?, -1)
            ORDER BY created_at ASC, id ASC
            """,
            (token_id, pair_id),
        ).fetchall()


def find_clean_episodes_for_token_pair(db_path_or_conn: str | Path | sqlite3.Connection, token_id: int, pair_id: int | None) -> list[sqlite3.Row]:
    return [
        episode for episode in find_episodes_for_token_pair(db_path_or_conn, token_id, pair_id)
        if episode_can_be_used_for_future_retrieval(episode)
    ]


def episode_can_be_used_for_future_retrieval(episode: sqlite3.Row | dict) -> bool:
    return MemoryQualityLabel(episode["memory_quality_label"]) == MemoryQualityLabel.CLEAN_MEMORY
