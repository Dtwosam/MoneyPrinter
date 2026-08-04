# Stop conditions

Stop without applying or re-applying if any of the following hold:

1. Live branch or HEAD differs from `authorized_git`.
2. Tracked worktree or index is dirty with unexpected product changes.
3. Authorization package is missing, modified, or already consumed.
4. External application directory or marker already exists for this authorization ID.
5. Authoritative DB identity drifts (sha256/size/mtime_ns/inode/sidecars).
6. Launch-chain file identities drift.
7. Migration-050 package identity drifts or is re-invoked.
8. Visible untracked set is not exactly Migration-050 plus this package.
9. Active or locked Scheduler residue is present.
10. Relevant Printer processes are present.
11. Any retry/rerun/resume/restart/successor is attempted.
12. Any 1h/4h/12h/24h continuation is attempted under this authorization.
13. Direct `operational_memory_factory_command` invocation is attempted.
14. Historical consumed authorizations are reused.
