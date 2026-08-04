# Consumed-on-start rule

This authorization is consumed when the canonical one-shot wrapper begins
application and creates its external application marker. It is permanently
non-reusable after that boundary regardless of PASS, block, safe stop,
interruption, child failure or wrapper failure.

No retry, rerun, resume, restart, recovery or successor is authorized.
