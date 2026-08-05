# Exact manual command

```powershell
./scripts/Start-PrinterV1-Window15M-OneShot.ps1 -AuthorizationFile 'operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z/final_authorization.json' -AuthorizationSha256 '500b634619fe1ba59fca1db0dd805c03cab9a2d5a08ba469ff74ea239475256c' -OperatorApproved
```

Start manually from an operator terminal exactly once. Direct child invocation,
reuse, retry, rerun, resume, restart, recovery, automatic successor, concurrent
execution and second execution are not authorized.
