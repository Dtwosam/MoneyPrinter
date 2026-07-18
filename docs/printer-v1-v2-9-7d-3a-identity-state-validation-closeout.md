# V2-9.7D.3A — Campaign Identity and State Validation (Closeout)

## Scope

Add pure, fail-closed validation of campaign identities and campaign
lifecycle-state transitions on top of the persistence introduced in
V2-9.7D.2A. This lane adds **validation logic only**: no schema changes, no
scheduler fairness, no orchestration, no source calls, no continuation, no 5m
capture, no trajectory objects, no runtime, no operational commands, and no
persistent-DB mutation.

The lane reuses migration `031_operational_campaign_persistence.sql` and
`printer_v1.operator_cli.campaign_persistence`. It does not introduce a parallel
persistence or state system: the campaign/report state vocabulary
(`CAMPAIGN_STATES`, `TERMINAL_CAMPAIGN_STATES`) is imported from
`campaign_persistence`.

## Deliverables

- `src/printer_v1/operator_cli/campaign_identity_state.py` — the validators.
- `tests/test_v2_9_7d_3a_identity_state_validation.py` — focused tests.
- `docs/printer-v1-v2-9-7d-3a-identity-state-validation-closeout.md` — this note.

## What was implemented

### Exact identity validation

`validate_identity(kind, value)` validates one identity for a known kind. The
recognised kinds are:

`campaign`, `configuration`, `report`, `cycle`, `token_slot`, `token`, `mint`,
`pair`, `lifecycle`, `window`.

An identity must be a non-empty string of at most 256 characters that begins
with an alphanumeric character and otherwise contains only
`A–Z a–z 0–9 . _ : -`. No normalisation is performed and any surrounding or
embedded whitespace is rejected, so later exact-equality checks cannot be
defeated by invisible differences. `require_identity(kind, actual, expected)`
validates both sides and then requires exact equality. `validate_identity_chain`
validates a `kind -> value` mapping value by value.

### Allowed state transitions

`ALLOWED_CAMPAIGN_TRANSITIONS` encodes the campaign lifecycle graph, mirroring
the state CHECK constraints in migration 031:

- `DRAFT -> {PREFLIGHT, TERMINAL_BLOCKED, TERMINAL_FAILED}`
- `PREFLIGHT -> {RUNNING, TERMINAL_STOPPED, TERMINAL_BLOCKED, TERMINAL_FAILED}`
- `RUNNING -> {STOP_REQUESTED, TERMINAL_COMPLETED, TERMINAL_STOPPED, TERMINAL_BLOCKED, TERMINAL_FAILED}`
- `STOP_REQUESTED -> {TERMINAL_STOPPED, TERMINAL_COMPLETED, TERMINAL_BLOCKED, TERMINAL_FAILED}`
- every terminal state `-> {}` (final)

`TERMINAL_COMPLETED` is deliberately only reachable from `RUNNING` or
`STOP_REQUESTED`, so a campaign cannot "complete" without having run.
`can_transition` / `validate_transition` enforce the graph; unknown states fail
closed.

### Immutable first terminal cause and idempotent terminalization

`terminalize(...)` validates a terminalization request:

- The requested state must be terminal, with a non-empty first terminal cause,
  and the terminal transition from the current non-terminal state must be
  allowed.
- Repeating an identical terminalization (same terminal state and same cause) is
  idempotent and returns `Terminalization(..., changed=False)`.
- Once terminal, the first terminal cause is immutable and the terminal state
  cannot change; a divergent cause or a different terminal state fails closed.
- A non-terminal campaign must not already carry a first terminal cause.

### Fail-closed identity and predecessor mismatches

`validate_report_predecessor(...)` validates a replay's predecessor reference
against a persisted terminal-report record: the predecessor must be a `TERMINAL`
report in the `REPORT_TERMINAL` state whose `campaign_id` and `configuration_id`
exactly match the replay's campaign and configuration. Any mismatch raises
`CampaignIdentityError`.

All errors derive from `CampaignValidationError` (`CampaignIdentityError`,
`CampaignStateError`), so every contract violation is a fail-closed exception.

## Verification

Environment: `TEMP` and `TMP` set to `C:\tmp`; pytest cache disabled; hard
timeout.

- Syntax/import: `python -m py_compile` on the module and test — OK.
- Focused 3A tests: `tests/test_v2_9_7d_3a_identity_state_validation.py` —
  23 passed (23 subtests).
- Persistence regression: `tests/test_v2_9_7d_2a_campaign_persistence.py` —
  8 passed.
- `git diff --check` — clean.

## Verdict

`V2_9_7D_3A_IDENTITY_STATE_VALIDATION_PASS`
