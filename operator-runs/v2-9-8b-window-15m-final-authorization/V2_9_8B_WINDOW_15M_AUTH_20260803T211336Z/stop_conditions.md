# Stop Conditions

Stop and do **not** apply (or re-apply) authorization `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` if any of:

1. Live HEAD ≠ `6bb73ca165469fd60171098ff700241ec5667b34`
2. Live branch ≠ `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`
3. Tracked or staged tree is dirty with unexpected product changes
4. `final_authorization.json` bytes no longer hash to `5524ada42b3da1a56516ccbb5cfe821b3414ee0653d516453fd4212cb3439c03`
5. Authoritative DB identity differs from bound path/sha256/size/mtime_ns/inode/sidecars
6. Launch-chain file identities differ from bound SHA-256 values
7. Migration-050 package listing digest ≠ `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`
8. Visible untracked set ≠ Migration-050 visible paths + this package's visible paths
9. External application directory already exists for this ID
10. Active or locked Scheduler residue is non-zero
11. Relevant Printer processes are present
12. Operator attempts retry/rerun/resume/restart/successor under this ID
13. Operator attempts WINDOW_1H or continuous 4h continuation under this ID
14. Operator invokes `operational_memory_factory_command` directly
15. Any wallet, signing, funds, retrieval, decision, position, trade, audit, or PnL path is requested
16. Any mutable binding changed after package creation (invalidate; do not silently regenerate in the same lane)
17. Operator attempts to reuse historical authorizations including `…210122Z` or `…204800Z`
