# Exact Manual PowerShell Command

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

Authorization file (repository-relative):

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json`

Exact SHA-256 of `final_authorization.json`:

`1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680`

## Required preconditions (operator)

1. Independent review PASS for this package.
2. `git checkout e07ff977292d79f36a2067319187a0ad1f17f2f7` (authorized exact HEAD) with clean tracked/staged trees.
3. Ensure this authorization package and Migration-050 package are present as **untracked** evidence (wrapper rejects tracked current packages).
4. Confirm external application directory does **not** exist:
   `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`
5. Source secrets without printing values:
   `source /Users/Dtwo1/.config/printer-v1/secrets.env`
6. Confirm no relevant Printer processes and zero active/locked Scheduler residue.
7. Manual Terminal execution only. Exactly one invocation.

## Command

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z/final_authorization.json `
  -AuthorizationSha256 1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680 `
  -OperatorApproved
```

## Forbidden

- Direct `python -m printer_v1.operator_cli.operational_memory_factory_command ...`
- Any second invocation under this authorization ID
- Retry / rerun / resume / restart / successor
- 1h or 4h continuation under this authorization
- Creating the external application marker or manifest outside the wrapper

## Consumption

Authorization is permanently consumed when wrapper execution begins, regardless of PASS, block, safe-stop, interruption, or failure.
