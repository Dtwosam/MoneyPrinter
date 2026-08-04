# Consumed-On-Start Rule

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`

This authorization is permanently consumed when wrapper execution begins.

Consumption is permanent regardless of:

- PASS
- block
- safe-stop
- interruption
- failure

After consumption:

- no reuse
- no retry
- no manual rerun
- no resume
- no restart
- no successor

Allowed invocation count: `1`.
