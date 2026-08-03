# Stop Conditions

Stop and do **not** apply (or re-apply) authorization `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z` if any of:

1. Live HEAD ≠ `e07ff977292d79f36a2067319187a0ad1f17f2f7`
2. Live branch ≠ `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`
3. Tracked or staged tree is dirty with unexpected product changes
4. `final_authorization.json` bytes no longer hash to `1c32c9eea764752893d97b7c2b3dce2e70e54d5a8f84c9dcba19fbe2c114c680`
5. Authoritative DB identity differs from bound path/sha256/size/mtime_ns/inode/sidecars
6. Launch-chain file identities differ from bound SHA-256 values
7. Migration-050 package listing digest ≠ `08e6f40b2e472d0bd8c6e8e1adaaac27a8b1af59d93571daa6cfb18f31dacb7a`
8. External application directory already exists for this ID
9. Active or locked Scheduler residue is non-zero
10. Relevant Printer processes are present
11. Operator attempts retry/rerun/resume/restart/successor under this ID
12. Operator attempts WINDOW_1H or continuous 4h continuation under this ID
13. Operator invokes `operational_memory_factory_command` directly
14. Any wallet, signing, funds, retrieval, decision, position, trade, audit, or PnL path is requested
15. Any mutable binding changed after package creation (invalidate; do not silently regenerate in the same lane)
