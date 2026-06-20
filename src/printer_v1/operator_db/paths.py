"""Safe local path helpers for the Printer V1 operator database."""

from pathlib import Path


DEFAULT_DATA_DIR_NAME = "data"
DEFAULT_DB_FILE_NAME = "printer_v1.sqlite3"
SQLITE_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".db3"}


def get_project_root(project_root: str | Path | None = None) -> Path:
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def get_default_data_dir(project_root: str | Path | None = None) -> Path:
    return get_project_root(project_root) / DEFAULT_DATA_DIR_NAME


def get_default_db_path(project_root: str | Path | None = None) -> Path:
    return get_default_data_dir(project_root) / DEFAULT_DB_FILE_NAME


def path_is_network_path(path: Path) -> bool:
    return str(path).startswith("\\\\")


def resolve_operator_db_path(db_path: str | Path | None = None, project_root: str | Path | None = None) -> Path:
    candidate = Path(db_path).expanduser() if db_path is not None else get_default_db_path(project_root)
    if path_is_network_path(candidate):
        raise ValueError("Operator DB path must be local.")
    return candidate.resolve(strict=False)


def ensure_data_dir_exists(data_dir: str | Path) -> Path:
    resolved = Path(data_dir).expanduser().resolve(strict=False)
    if path_is_network_path(resolved):
        raise ValueError("Operator data directory must be local.")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def db_path_is_inside_project_data_dir(db_path: str | Path, project_root: str | Path | None = None) -> bool:
    resolved_db_path = Path(db_path).expanduser().resolve(strict=False)
    data_dir = get_default_data_dir(project_root).resolve(strict=False)
    try:
        resolved_db_path.relative_to(data_dir)
    except ValueError:
        return False
    return True


def db_path_is_sqlite_file(db_path: str | Path) -> bool:
    return Path(db_path).suffix.lower() in SQLITE_SUFFIXES
