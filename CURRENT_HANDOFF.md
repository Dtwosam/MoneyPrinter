# Printer V1 Handoff

## Current capability

Branch: `assistant/v2-9-8b-later-cycle-mint-market-replay-repair`.
Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor is the sole governed source-request owner and Central Scheduler the sole scheduler owner. `WINDOW_5M_MICRO_EVENT` remains support-only; `WINDOW_12H` and `WINDOW_24H` remain locked. Only clean evidence may become training memory.

## Latest operational result

The latest four-token Standard-4H attempt used consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260911T191415Z_8331c5b4` on HEAD `dd459221918e38b9fbe8da59e2c5a7612cf1b3d9`. It is permanently non-reusable. Campaign `20260911T193532Z-bbc0b4e94dc8-campaign` terminalized safely at `2026-09-11T19:55:39.884055+00:00` with `OPERATIONAL_CAMPAIGN_FAILED:CampaignSixUnitError`; cleanup completed, lease released, and zero active owned work remained.

No lifecycle started and Cycle 1 never admitted. Discovery itself progressed cleanly through two scheduled refreshes; recent source requests were `COMPLETE / CLEAN_DATA`. The prior mixed-protocol collision and negative-history front-slice starvation were not the terminal blocker.
## Proven blocker and repair

The run sealed 21 six-unit stages and recorded 27 source transport operations before failing with `SIX_UNIT_STAGE_EVIDENCE_MALFORMED:PRE_OPERATION_NO_WORK_CONTRACT`.

Root cause: `_seal_holder_stage(...)` used the campaign-global `PRE_OPERATION_NO_WORK` sentinel whenever holder safety had zero transports. That sentinel is only legal before any campaign operation; ingesting it after 21 prior stages correctly failed closed.

Repair: zero-six-unit holder work now emits no accounting stage and does not call the six-unit evidence sink. Holder status/cause remain in `HolderContextResult`. If any six-unit work exists, holder evidence still seals and ingests through the existing canonical path. The strict `PRE_OPERATION_NO_WORK` validator is unchanged.

TDD proof: the zero-holder-work boundary was RED on `dd459221...` and is GREEN after the repair; a companion test proves real holder transport still seals and ingests exactly once.
Focused verification: the two new holder-accounting regressions pass, the strict pre-operation-no-work contract test passes, and the wider accounting/holder/four-token focused set passes 104 tests with only independently reproduced baseline-debt cases deselected. The same four wider failures reproduce on an untouched detached `dd459221...` worktree.

## Exact next permitted action

Commit and push this accounting repair, then verify focused CI on the exact pushed HEAD. No operational execution is permitted from the consumed `...191415Z...` authorization. A future provider-driven attempt requires a fresh one-shot authorization, exact then-current HEAD+DB binding, migration/integrity/FK/zero-active-work gates, and new explicit operator approval.
