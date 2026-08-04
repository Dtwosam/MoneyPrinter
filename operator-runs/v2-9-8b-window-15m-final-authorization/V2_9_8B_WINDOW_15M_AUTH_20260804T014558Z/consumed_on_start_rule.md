# Consumed-on-start rule

This authorization is permanently consumed when wrapper execution begins,
regardless of PASS, block, safe-stop, interruption, or failure.

Allowed invocation count: 1.

Forbidden after start: automatic retry, manual rerun, resume, restart, successor,
second wrapper invocation under the same authorization ID, and reuse of this package.
