# Exact Manual PowerShell Command

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z`

Authorization file (repository-relative):

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z/final_authorization.json`

Exact SHA-256 of `final_authorization.json`:

`8bb922e4450a81ee42e160a638f93175723f128bc05c058664aa211c008c70e7`

## Required preconditions (operator)

1. Independent review PASS for this package.
2. Live HEAD equals `0ab3fa33e580cbe1c55e3a6bfd2b318edd93aa6c` with clean tracked/staged trees.
3. Ensure this authorization package and Migration-050 package are present as **untracked** evidence (wrapper rejects tracked current packages). Historical authorization packages must remain tracked or absent from the visible untracked set.
4. Confirm exact visible-untracked equality: Migration-050 visible paths + this package visible paths only.
5. Confirm external application directory does **not** exist:
   `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z`
6. Source secrets without printing values:
   `source /Users/Dtwo1/.config/printer-v1/secrets.env`
7. Confirm no relevant Printer processes and zero active/locked Scheduler residue.
8. Manual Terminal execution only. Exactly one invocation.
9. Do **not** create or request a separate pre-lifecycle readiness artifact.

## Command

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z/final_authorization.json `
  -AuthorizationSha256 8bb922e4450a81ee42e160a638f93175723f128bc05c058664aa211c008c70e7 `
  -OperatorApproved
```

## Forbidden

- Direct `python -m printer_v1.operator_cli.operational_memory_factory_command ...`
- Any second invocation under this authorization ID
- Retry / rerun / resume / restart / successor
- 1h or 4h continuation under this authorization
- Creating the external application marker or manifest outside the wrapper
- Reuse of historical authorizations including `…005013Z` and prior IDs
- Separate live readiness proof / qualification campaign before the real attempt

## Consumption

Authorization is permanently consumed when wrapper execution begins, regardless of PASS, block, safe-stop, interruption, or failure.

## Executable HEAD note

This authorization binds executable HEAD `0ab3fa33e580cbe1c55e3a6bfd2b318edd93aa6c` (`Strengthen discovery and selection funnel`).
