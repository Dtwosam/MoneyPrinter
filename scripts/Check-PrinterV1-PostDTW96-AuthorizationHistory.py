from __future__ import annotations

import json
from pathlib import Path

REPO = Path.home() / "Developer" / "MoneyPrinter"
AUTH_ID = "V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z"
AUTH_FILE = (
    REPO
    / "operator-runs"
    / "v2-9-8b-window-15m-final-authorization"
    / AUTH_ID
    / "final_authorization.json"
)
EXPECTED = [
    "V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T005013Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z",
    "V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z",
]

document = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
observed = document.get("prior_authorizations_non_reusable") or []
if sorted(observed) != sorted(EXPECTED):
    raise SystemExit(
        json.dumps(
            {
                "status": "BLOCKED",
                "verdict": "V2_9_8B_POST_DTW96_AUTHORIZATION_HISTORY_EXACT_SET_BLOCKED",
                "missing": sorted(set(EXPECTED) - set(observed)),
                "unexpected": sorted(set(observed) - set(EXPECTED)),
                "observed_count": len(observed),
            },
            indent=2,
            sort_keys=True,
        )
    )
print(
    json.dumps(
        {
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW96_AUTHORIZATION_HISTORY_EXACT_SET_PASS",
            "historical_non_reusable_authorization_count": len(observed),
            "fresh_authorization_id": AUTH_ID,
        },
        indent=2,
        sort_keys=True,
    )
)
