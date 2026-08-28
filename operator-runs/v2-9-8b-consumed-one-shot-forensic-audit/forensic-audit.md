Printer V1 — Consumed One-Shot Pre-/Mid-Lifecycle Block Forensic Audit

Lane: read-only forensics / recovery-readiness classification only
Consumed authorization (permanent, non-reusable): V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5
No mutations, recovery, retry, resume, repair, commit, or push were performed.

───

A. Terminal evidence preservation

Application directory:

/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5/

┌──────────────────────────────┬───────┬──────────────────────────────────────────────────────────────────┐
│ Artifact                     │  Size │ SHA-256                                                          │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ application-marker.json      │   907 │ 9099e5f31949bd9dc219dbe58a301e095df1600cd5698b705841ee33bfd0c76a │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ git-provenance-manifest.json │ 41503 │ 0de62d192bb0091c80cce4b219bee3520811254f711f828e565b54de18e2f519 │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ wrapper-terminal.json        │  5846 │ 453e2c7808e45829a63d14a5060cd2b94d3673609e1b88d6c71db528885ae7c5 │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ child-terminal.json          │  1878 │ 652307a16ca4d1f8ca2ef7e9695062d952a1ac5619b7e41e3e7a163027788f37 │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ child-stderr.txt             │ 25105 │ f74a8b5cb2f58c0bd1717fcaf14cdb0b221464f52ec2b8cda609541d07bffb6a │
├──────────────────────────────┼───────┼──────────────────────────────────────────────────────────────────┤
│ child-stdout.txt             │     0 │ e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 │
└──────────────────────────────┴───────┴──────────────────────────────────────────────────────────────────┘

Confirmed
• Marker proves permanent consumption (allowed_invocation_count=1, automatic_retry_allowed=false, resume_allowed=false, restart_allowed=false, successor_allowed=false, manual_rerun_allowed=false).
• Wrapper counters are all zero: retries/resumes/restarts/successors/manual_reruns = 0.
• Wrapper ↔ child ↔ stderr/stdout/marker/manifest SHA identities reconcile exactly.
• Authoritative execution result is child exit 1 (CHILD_EXITED_NONZERO). Any outer shell 0 is only the calling script completing after the wrapper returned a terminal object.
• Bound HEAD matches live repo HEAD: 1d75715ca38c14294f58303b3a5cdb785ed4ad4c.

───

B. Child stderr / exception chain

child-stderr.txt is one reconstructed JSON envelope, not a Python traceback.

Ordered causality (durable, not collapsed)

┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Layer                               │ Fact                                                                                                                                                 │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Originating operational fault    │ LEASE_RENEWAL_SQLITE_LOCKED / SQLITE_LOCK_CONTENTION at 2026-08-28T22:18:07.942980+00:00                                                             │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. Concurrent writer                │ Source response 3516 for request 3888 (pair_market_snapshot) received 2026-08-28T22:18:07.008671+00:00 — ~0.93s before lease failure                 │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. Phase-A cycle terminalization    │ Cycle-1 durable cause remains LEASE_RENEWAL_SQLITE_LOCKED; windows cancelled; slots → MANUAL_REVIEW; factory stop_reason=LEASE_RENEWAL_SQLITE_LOCKED │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. Secondary terminal-shape failure │ FourTokenFactoryAdapterError: one-cycle shared terminal requires exact terminal no-admission evidence while closing shared terminal                  │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5. Cleanup failure                  │ Shared terminalizer never ran → cleanup_complete=false, lease_released=false, lease file still present                                               │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6. Residual Scheduler/attempt state │ Job 2808 still PENDING; Cycle-2 attempt still RUNNING                                                                                                │
└─────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Important reporting distortion: reconstructed child/wrapper first_terminal_cause surfaces the adapter error, and failure_phase=CAMPAIGN_PRE_LIFECYCLE / lifecycle_started=null. Durable DB truth is stronger: Cycle-1 did start lifecycle (2 admitted tokens, 19 succeeded WINDOW_15M_SNAPSHOT works, close jobs cancelled mid-window).

FourTokenFactoryAdapterError is secondary — fail-closed while trying to terminalize after a legitimate lease-failure stop — not the originating market/source outcome.

───

C. Exact six authoritative DB write groups + attributable mutations

Child metric database_writes=6 with authoritative_write_count_status=OWNER_EMITTED_AUTHORITATIVE is the campaign-identity write set, not total mutations:

┌───┬─────────────────┬────────────────────────────────────────────────┬───────────────────┬────────┐
│ # │ Group           │ Table                                          │ ID                │ Kind   │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 1 │ Campaign create │ printer_memory_factory_campaigns               │ ...-campaign      │ INSERT │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 2 │ Config create   │ printer_memory_factory_campaign_configurations │ ...-configuration │ INSERT │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 3 │ Cycle create    │ printer_memory_factory_campaign_cycles         │ ...-cycle         │ INSERT │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 4 │ Run create      │ printer_memory_factory_campaign_runs           │ ...-campaign-run  │ INSERT │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 5 │ Campaign update │ printer_memory_factory_campaigns               │ ...-campaign      │ UPDATE │
├───┼─────────────────┼────────────────────────────────────────────────┼───────────────────┼────────┤
│ 6 │ Run update      │ printer_memory_factory_campaign_runs           │ ...-campaign-run  │ UPDATE │
└───┴─────────────────┴────────────────────────────────────────────────┴───────────────────┴────────┘

Current durable ownership state (exact IDs)

┌───────────────────────┬────────────────────────────┬──────────────────┬──────────────────────────────────────────────────────────────────┐
│ Table                 │ ID                         │ State            │ Terminal/cause                                                   │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ campaigns             │ ...-campaign               │ RUNNING          │ none                                                             │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ runs                  │ ...-campaign-run           │ RUNNING          │ none; authoritative factory 42ef6217-3932-4846-948d-e2103fd34309 │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ cycles                │ ...-cycle (ordinal 1 only) │ TERMINAL_BLOCKED │ LEASE_RENEWAL_SQLITE_LOCKED @ 22:18:12.770908Z                   │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ supervision           │ ...-supervision            │ ACTIVE           │ cleanup/lease release null; lease path still exists              │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ factory run           │ 42ef6217-...               │ RUNNING          │ stop_reason=LEASE_RENEWAL_SQLITE_LOCKED                          │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ token slots           │ slot-…-1 / slot-…-2        │ MANUAL_REVIEW    │ LEASE_RENEWAL_SQLITE_LOCKED                                      │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ windows               │ 2× WINDOW_15M              │ CANCELLED        │ LEASE_RENEWAL_SQLITE_LOCKED                                      │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ pre-admission attempt │ pre-admission:...:c0002    │ RUNNING          │ no cause / no terminal_at / consumed_cycle_id=null               │
├───────────────────────┼────────────────────────────┼──────────────────┼──────────────────────────────────────────────────────────────────┤
│ heartbeat failure     │ supervision row            │ recorded         │ SQLITE_LOCK_CONTENTION → LEASE_RENEWAL_SQLITE_LOCKED             │
└───────────────────────┴────────────────────────────┴──────────────────┴──────────────────────────────────────────────────────────────────┘

Broader attributable mutation scale (from action-local deltas)

Notable net positives include: source requests +42 (ids 3847–3888), responses +40, failures +2, scheduler jobs +49, campaign scheduler work +48, factory steps +38, attempt evidence 19 rows, tokens/pairs +2, etc. Pre-campaign backup SHA remains the pre-run baseline dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836.

───

D. The one residual Scheduler item

┌─────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Field                       │ Value                                                                                                                                                │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Job ID                      │ 2808                                                                                                                                                 │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Status                      │ PENDING                                                                                                                                              │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Kind / name                 │ PRE_ADMISSION_DISCOVERY_SELECTION / pre-admission-discovery-selection:...:c0002                                                                      │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ scheduled_for               │ 2026-08-28T22:14:34.110233+00:00                                                                                                                     │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ started_at / finished_at    │ null / null — never executed                                                                                                                         │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Locks                       │ none                                                                                                                                                 │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Campaign scheduler-work row │ none                                                                                                                                                 │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Ownership link              │ printer_pre_admission_discovery_attempts.scheduler_job_id = 2808                                                                                     │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Source-request linkage      │ none on the job itself; prior attempt evidence ends at request 3881                                                                                  │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Classification              │ Incomplete cooperative Cycle-2 acquisition continuation / cleanup residue — due, never claimed, orphaned relative to campaign_scheduler_work linkage │
└─────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

campaign_active_work_report now reports: active_jobs=1, active_pre_admission_attempts=1, active_factory_runs=1, clean_terminal=false.

───

E. Pre-admission attempt evidence (migration 062)

Attempt: pre-admission:20260828T220832Z-704f53472011-campaign:...:c0002
State: RUNNING (no terminal disposition, no certificate)

Evidence (19 rows), all opportunity_ordinal=0:

• 9× OPPORTUNITY_EXECUTED / ACQUISITION_QUANTUM_YIELDED (claims 1–9)
• 10× SOURCE_REQUEST_TERMINAL / SOURCE_RESPONSE (requests 3870–3873, 3876–3881)

Phases observed: fresh intake → liquidity backup → protocol confirmation → direct migration.
Missing: delayed opportunities (+600/+1200/+1800), candidate/reject/inventory terminal rows, attempt items, source links, final disposition.

Compared to terminal certificate reducer: attempt is legitimately nonterminal. Exact no-admission evidence does not exist. Adapter did not “miss” a completed no-admission certificate; it correctly refused to invent one. Residual job 2808 shows terminal closure was attempted while cooperative acquisition was still open.

Cycle-1 GeckoTerminal rate-limits (failures 370/371 on requests 3854/3855) are early admission-path provider limits, not the campaign-ending cause.

───

F. Fail-closed guard predicates (finalize_four_token_shared_terminal)

Sanctioned shapes for one admitted cycle:

1. ONE_CYCLE_HONEST_NO_ADMISSION — exactly one Cycle-2 attempt in {NO_PAIR,BLOCKED,FAILED,CANCELLED} with non-empty cause and consumed_cycle_id IS NULL, and no contradictory pre-lifecycle provenance
2. ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT — zero Cycle-2 attempts + exact provenance row
3. Else → raise the observed error
4. Also sanctioned: two-cycle completion path (ordinals [1,2])

Live predicate audit (shape 1)

┌──────────────────────────┬──────────────────────────────────┬───────────────┬──────────────────────┬──────────────────────────────────┐
│ Predicate                │ Required                         │ Observed      │ Result               │ Source                           │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ Admitted cycles          │ exactly 1, ordinal 1             │ 1 / ordinal 1 │ PASS                 │ campaign_cycles                  │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ Cycle-2 attempts         │ exactly 1                        │ 1             │ PASS                 │ pre_admission_discovery_attempts │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ attempt_state            │ NO_PAIR|BLOCKED|FAILED|CANCELLED │ RUNNING       │ FAIL (first blocker) │ attempt row                      │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ first_terminal_cause     │ non-empty                        │ null          │ FAIL                 │ attempt row                      │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ consumed_cycle_id        │ NULL                             │ NULL          │ PASS                 │ attempt row                      │
├──────────────────────────┼──────────────────────────────────┼───────────────┼──────────────────────┼──────────────────────────────────┤
│ Provenance contradiction │ none if honest                   │ none          │ n/a                  │ provenance table empty           │
└──────────────────────────┴──────────────────────────────────┴───────────────┴──────────────────────┴──────────────────────────────────┘

First preventing predicate: attempt_state must be a terminal no-admission state; live value is RUNNING.

Shape 2 is unreachable because len(attempt_rows) != 0.

───

G. Why cleanup did not complete

1. Phase B finalize_four_token_shared_terminal raised before invoking shared_terminalizer.
2. shared_terminalizer is the only path that calls cleanup_campaign_supervision + lease release in the four-token success path.
3. Because Phase B failed, four_token_shared_terminal_evidence stayed empty and durable cleanup/lease release did not complete.
4. Additional structural gap: even if cleanup had run, job 2808 is linked only through the pre-admission attempt, not through campaign_scheduler_work / discovery_work, so the current cleanup SQL would not cancel it.

Durable blockers now:
• supervision ACTIVE, lease file present
• campaign/run/factory still RUNNING
• attempt RUNNING
• job 2808 PENDING

───

H. Existing recovery owners — inspected, not run

┌───────────────────────────────────────┬──────────────────────────────────────────────────┬────────────────────────────────────────┬─────────────────────────┐
│ Owner                                 │ Bound to this state?                             │ Contacts providers / new work?         │ Safe as reconcile-only? │
├───────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────────┼─────────────────────────┤
│ operational_campaign_recovery.py      │ No — hard-bound to 20260726T114155Z-95d9979a9302 │ Designed not to; wrong contract anyway │ N/A                     │
├───────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────────┼─────────────────────────┤
│ scheduler_residue_reconciliation.py   │ No — immutable historical job-ID set             │ No; cancels only audited IDs           │ N/A                     │
├───────────────────────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────────┼─────────────────────────┤
│ heartbeat_terminalization_recovery.py │ No — hard-bound to 20260727T161750Z-95e40c3efae3 │ No sources/Scheduler runtime by design │ N/A for this execution  │
└───────────────────────────────────────┴──────────────────────────────────────────────────┴────────────────────────────────────────┴─────────────────────────┘

Answers:
1. No canonical bounded recovery for this exact post-consumption state.
2. Historical recoveries are reconcile-only for their executions; none may be stretched onto this auth/execution.
3/4. A future recovery for this state must be reconcile/terminalize-only (no providers, no Scheduler runtime advancement, no campaign retry).
5. Required authority: explicit operator approval after audit→design of an exact-execution recovery/reconciliation owner bound to this HEAD+DB+auth evidence.
6. Product gaps are already proven enough that design must address lease-failure cleanup under interrupted Cycle-2 attempt and/or an exact residual reconciliation owner before another authorization.

───

I. Root-cause classification

Primary: EXPECTED_RECOVERABLE_INTERRUPTED_STATE
Originating durable cause: LEASE_RENEWAL_SQLITE_LOCKED from SQLite lock contention during lease renewal while Cycle-1 snapshot transport was concurrently writing.

Secondary: CLEANUP_OR_RESIDUE_RECONCILIATION_DEFECT
After Phase-A lease-failure terminalization of the one admitted cycle, Phase-B shared terminal has no sanctioned shape for a still-RUNNING Cycle-2 attempt, so cleanup/lease release never completes and job 2808 remains.

Not selected
• Not honest source scarcity / expected no-admission (Cycle-1 admitted and collected; Cycle-2 attempt nonterminal with successful source responses).
• Not FOUR_TOKEN_ADAPTER_RECOGNITION_DEFECT of existing no-admission evidence (that evidence does not exist).
• Adapter fail-closed behavior on inventing no-admission is correct; the defect is the missing interrupt/cleanup path for this residue shape.

Proven product gaps
1. Lease renewal aborted by SQLite contention under legitimate concurrent writes (same class as prior WINDOW_15M SQLite-lock history).
2. Four-token lease-failure stop leaves RUNNING Cycle-2 attempt + unlinked PENDING pre-admission job + unreaped lease when Phase B cannot match a sanctioned one-cycle shape.

───

J. Safety / current-state proof

┌──────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Check                                │ Result                                                                                                   │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Live DB SHA-256                      │ c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d (exact match)                           │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Integrity                            │ ok                                                                                                       │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ FK violations                        │ 0                                                                                                        │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Ledger                               │ 62 / tip 062_pre_admission_attempt_evidence.sql                                                          │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Sidecars                             │ none (-wal/-shm/-journal absent)                                                                         │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Printer/Governor/Scheduler processes │ none observed                                                                                            │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Pre-campaign backup                  │ still dececa7c…c93836                                                                                    │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Lease file                           │ still present at /Users/Dtwo1/PrinterOperations/v2-9-8/20260828T220832Z-704f53472011/campaign.lease.lock │
└──────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Pre-run SHA is correctly obsolete; DB was legitimately mutated by the consumed campaign.

───

K. Verdict and next permitted lane

Verdict
Consumed one-shot campaign 20260828T220832Z-704f53472011 admitted Cycle-1, started WINDOW_15M collection, opened Cycle-2 cooperative acquisition, then aborted on lease-renewal SQLite lock contention. Shared terminalization then fail-closed on a nonterminal Cycle-2 attempt, leaving recoverable residue (ACTIVE supervision, unreaped lease, RUNNING attempt, PENDING job 2808). Authorization is permanently consumed and must never be reused.

Exact next permitted lane

POST-CONSUMPTION INTERRUPTED FOUR-TOKEN CAMPAIGN
RESIDUAL-RECONCILIATION / LEASE-FAILURE CLEANUP-PATH
AUDIT → DESIGN (NO EXECUTION)

That lane may only:
• audit/design an exact-execution residual reconciliation and/or lease-failure cleanup path for this residue shape;
• preserve audit → design/specification → implementation if approved → bounded proof → closeout.

It must not:
• rerun/resume/retry/successor this authorization;
• run Printer, providers, Source Governor, or Central Scheduler;
• manually release leases / mutate Scheduler rows / mutate the authoritative DB without an approved exact recovery owner.

CURRENT_HANDOFF.md still points at fresh authorization preparation against the pre-run DB SHA; that pointer is stale relative to this consumed campaign and must not be treated as authorizing another one-shot until residual reconciliation reaches a proven clean terminal/zero-state and a new readiness lane re-binds exact HEAD+DB.

───

Required closeout block

• Files changed: none (read-only)
• What was built: forensic classification report only
• What was not touched: DB, marker, code, recovery owners, governance files, remote/VPS
• Tests/checks run: artifact SHA reconciliation; read-only SQLite integrity/FK/ledger/process/sidecar/SHA; predicate and active-work reconstruction
• Pass/fail: PASS as forensic/classification lane
• Risks/concerns: live residue remains (ACTIVE supervision, lease file, RUNNING attempt, PENDING job 2808); reconstructed child cause understates durable LEASE_RENEWAL_SQLITE_LOCKED mid-lifecycle truth
• Next recommended phase: residual-reconciliation / lease-failure cleanup-path audit → design for this exact consumed execution; never reuse ...5fcb1bf5