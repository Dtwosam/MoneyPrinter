# Printer V1 / V2-9.8B — 07d92adf Historical Disposition Repair Design

Verdict:

`V2_9_8B_07D92ADF_HISTORICAL_DISPOSITION_REPAIR_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

## Objective

Adopt exactly one approved policy disposition:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf -> CONSUMED_CHILD_EXITED_NONZERO`

in the canonical `_POLICY_TERMINAL_DISPOSITIONS` map owned by:

`src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`

## Evidence basis

The exact authorization:

- was prepared once;
- passed independent review;
- was consumed through the production one-shot application path;
- has an immutable application marker;
- started exactly one child;
- child terminal exists and is valid;
- child exit code is `1`;
- wrapper terminal classification was `CHILD_EXITED_NONZERO`;
- no automatic retry, manual rerun, resume, restart, or successor occurred.

Therefore the approved terminal historical disposition is:

`CONSUMED_CHILD_EXITED_NONZERO`

## Narrow implementation

Only the exact-ID policy registration is authorized.

No generic inference/classifier is allowed.

No application-artifact parser, runtime handoff reader, schema change, DB
change, trust-root hard-coding, retry logic, provider logic, Scheduler behavior,
terminal-accounting behavior, frozen-lane behavior, or authorization workflow
change is authorized.

The existing consumed package/application evidence must remain immutable.

## Minimum sufficient proof

1. RED: actual historical enumeration of `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf` resolves to
   `DISPOSITION_NOT_AVAILABLE`.
2. GREEN: after exact mapping, production `_terminal_disposition_for()` and
   historical enumeration resolve it to `CONSUMED_CHILD_EXITED_NONZERO`.
3. wrong/unknown ID remains `DISPOSITION_NOT_AVAILABLE`.
4. prior exact mappings remain unchanged:
   - `...6af1423a -> BLOCKED_UNCONSUMED_SUPERSEDED`
   - `...95dc47dd -> CONSUMED_CHILD_EXITED_NONZERO`
   - `...17181afc -> BLOCKED_UNCONSUMED_SUPERSEDED`
5. future non-reuse trust root is re-derived, sorted, unique, and includes
   `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260825T105852Z_07d92adf` exactly once.
6. canonical evidence reconciliation remains PASS.
7. authoritative DB and consumed application evidence remain unchanged.
8. `py_compile` / focused provenance tests / `git diff --check`.

No broad suite is required.

## Exact next action

`V2-9.8B 07D92ADF HISTORICAL DISPOSITION REPAIR IMPLEMENTATION ONLY`
