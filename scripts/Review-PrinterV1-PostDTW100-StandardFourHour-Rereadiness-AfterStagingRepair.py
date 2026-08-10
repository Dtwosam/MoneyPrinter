from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path.home() / "Developer" / "MoneyPrinter"
BASE_HELPER = REPO / "scripts" / "Review-PrinterV1-PostDTW100-StandardFourHour-Rereadiness.py"
EXPECTED_BRANCH = (
    "agent/v2-9-8b-post-dtw100-standard-four-hour-rereadiness-after-staging-repair"
)


def main() -> int:
    if not BASE_HELPER.is_file():
        raise RuntimeError(f"base rereadiness helper missing: {BASE_HELPER}")
    spec = importlib.util.spec_from_file_location(
        "printer_v1_post_dtw100_standard_four_hour_rereadiness_base",
        BASE_HELPER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("base rereadiness helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXPECTED_BRANCH = EXPECTED_BRANCH
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
