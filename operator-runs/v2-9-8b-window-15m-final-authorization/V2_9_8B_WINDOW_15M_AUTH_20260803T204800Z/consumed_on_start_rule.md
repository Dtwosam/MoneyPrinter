# Consumed-On-Start Rule

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

## Law

This authorization is **permanently consumed when wrapper execution begins**.

Consumption occurs regardless of:

- PASS
- block
- safe-stop
- interruption
- failure

After consumption:

- the authorization is **not reusable**
- no automatic retry is authorized
- no manual rerun is authorized
- no resume, restart, or successor is authorized
- a new distinct authorization ID is required for any future attempt

## Mechanism

The one-shot wrapper creates a create-once external application marker
(`PRINTER_V1_APPLICATION_MARKER_V1`) under:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`

Re-application against an existing marker/path is fail-closed.
