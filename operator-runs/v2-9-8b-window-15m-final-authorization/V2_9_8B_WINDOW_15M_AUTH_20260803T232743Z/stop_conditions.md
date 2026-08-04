# Stop Conditions

Authorization ID: `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`

Fail closed / stop if any of the following occur:

1. HEAD or branch differs from authorized bindings (`3c426ad546511f759309714c2c3b56d3faf5823e` / `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`).
2. Tracked tree is dirty with unexpected product changes.
3. Authorization package is missing, modified, or already consumed.
4. External application directory or marker already exists for this ID.
5. Authoritative DB identity drifts (sha256/size/mtime_ns/inode/sidecars).
6. Launch-chain identity drifts (including operational command `58b65975…`).
7. Migration-050 package identity drifts or Migration-050 is re-invoked.
8. Visible untracked set is not exactly Migration-050 visible paths plus this package.
9. Any active or locked Scheduler residue exists.
10. Any relevant Printer process is present.
11. Retry / rerun / resume / restart / successor is attempted.
12. WINDOW_1H or continuous 4h continuation is attempted under this authorization.
13. `operational_memory_factory_command` is invoked directly.
14. Mutable bindings change after package creation without a new authorization.
15. Any historical consumed authorization (including `…211336Z`) is reused.
