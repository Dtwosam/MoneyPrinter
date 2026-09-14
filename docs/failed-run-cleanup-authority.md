# Failed-run cleanup authority

`failed_run_cleanup_authorization_preparation` and
`failed_run_cleanup_one_shot_wrapper` implement the separate
`PRINTER_V1_FAILED_RUN_CLEANUP_AUTHORIZATION_V1` profile. It authorizes only
`REPORT_INELIGIBLE_HISTORICAL_EVIDENCE_MISSING`, with started lifecycle evidence
and primary cause `LEASE_RENEWAL_SQLITE_LOCKED`. It grants no campaign, source,
Scheduler execution, retry, resume, restart, successor or canonical-report authority.

`inspect_cleanup` is read-only. Its exact Git/DB/ownership/residue/artifact facts
must be reviewed before supplying them as `expected_facts` to
`prepare_cleanup_authorization`. Preparation repeats inspection and rejects drift;
it does not consume authority. Use the returned authorization file and SHA with
`apply_cleanup_authorization`, which additionally requires explicit operator approval.
These APIs must not be used on authoritative state during development tests.

The profile requires one campaign/run/cycle/factory, an expired exact supervision
lease, succeeded snapshot-backed lifecycle evidence, no pre-admission or refresh
work, no zero-attempt provenance, no stored campaign/factory report, and absent
historical accounting evidence. Unsupported shapes fail closed; this is not a
generic recovery or lifecycle-resume API. Job, step, slot, queue and window IDs
belong to the reviewed instance, not generic policy.

The application namespace is
`~/PrinterOperations/v2-9-8/failed-run-cleanup-applications/<authorization_id>`.
After all free checks, the wrapper exclusively publishes the exact authorization
and provenance, then creates/fsyncs a create-once application marker. Marker
publication consumes authority even if validation or an owner subsequently fails.
Any existing application directory blocks another invocation, including incomplete
publication. Prior published cleanup IDs must be explicitly included in the
canonical prior-non-reuse declaration; discovery never creates successor authority.

Only canonical supervision cleanup and unified terminal reconciliation mutate DB
state. A fresh read-only connection then checks independent zero state, health,
exact terminal dispositions, and hashes covering completed evidence, unrelated
rows, future capabilities and row membership. Cleanup-era SQLite attribution is
written in the application directory, never the historical execution directory.

The original terminal summary retains `NOT_FINALIZED_CLEANUP_UNPROVEN` and its
original bytes. `cleanup-resolution.json` uses the existing immutable summary
writer and records the later cleanup result with `SIX_UNIT_ACCOUNTING_BLOCKED`,
`report_written=false` and `SIX_UNIT_EVIDENCE_MISSING`. This is not a campaign
report. A failure after consumption attempts `application-terminal.json` with the
known outcomes and unchanged primary cause. Neither artifact permits retry or
pretends committed owner mutations were rolled back. If artifact writing also
fails, the marker/package remains consumed and the exception carries that failure.
