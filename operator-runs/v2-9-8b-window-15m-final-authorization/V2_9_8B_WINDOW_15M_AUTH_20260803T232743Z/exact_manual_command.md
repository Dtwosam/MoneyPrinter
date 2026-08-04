# Exact Manual PowerShell Command

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`

Authorization file (repository-relative):

`operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/final_authorization.json`

Exact SHA-256 of `final_authorization.json`:

`2b0bf37ca642f201dba91f31266b29e0c9374347def5a0383a8c0fadcc9cc74a`

## Required preconditions (operator)

1. Independent review PASS for this package.
2. `git checkout 3c426ad546511f759309714c2c3b56d3faf5823e` (authorized parent execution HEAD) with clean tracked/staged trees.
3. Ensure this authorization package and Migration-050 package are present as **untracked** evidence (wrapper rejects tracked current packages). Historical authorization packages must remain tracked or absent from the visible untracked set.
4. Confirm exact visible-untracked equality: Migration-050 visible paths + this package visible paths only.
5. Confirm external application directory does **not** exist:
   `/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`
6. Source secrets without printing values:
   `source /Users/Dtwo1/.config/printer-v1/secrets.env`
7. Confirm no relevant Printer processes and zero active/locked Scheduler residue.
8. Manual Terminal execution only. Exactly one invocation.

## Command

```powershell
cd /Users/Dtwo1/Developer/MoneyPrinter

pwsh -File ./scripts/Start-PrinterV1-Window15M-OneShot.ps1 `
  -AuthorizationFile ./operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z/final_authorization.json `
  -AuthorizationSha256 2b0bf37ca642f201dba91f31266b29e0c9374347def5a0383a8c0fadcc9cc74a `
  -OperatorApproved
```

## Forbidden

- Direct `python -m printer_v1.operator_cli.operational_memory_factory_command ...`
- Any second invocation under this authorization ID
- Retry / rerun / resume / restart / successor
- 1h or 4h continuation under this authorization
- Creating the external application marker or manifest outside the wrapper
- Reuse of historical authorizations including `…211336Z` and prior IDs

## Consumption

Authorization is permanently consumed when wrapper execution begins, regardless of PASS, block, safe-stop, interruption, or failure.

## Executable HEAD note

This authorization binds parent execution HEAD `3c426ad546511f759309714c2c3b56d3faf5823e`.
The later authorization-evidence commit that records this package is not an executable HEAD.
