from __future__ import annotations

from pathlib import Path


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    target.write_text(
        text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:],
        encoding="utf-8",
    )


CAMPAIGN_HANDOFF = r'''def persist_standard_four_hour_handoff_set(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Persist the exact eligible subset of the standard two-slot 1h -> 4h handoff.

    The campaign identity remains exactly two owned slots.  Only slots in the
    explicit eligible subset receive WINDOW_4H ownership.  ``None`` preserves
    the historical all-eligible caller contract.  This B1 primitive creates no
    Scheduler jobs and performs no source work.
    """
    if len(candidates) != 2:
        raise CampaignOwnershipError(
            f"standard four-hour handoff requires exactly two candidates; found {len(candidates)}"
        )
    candidate_ids = [
        _required(candidate.get("token_slot_id"), "token_slot_id")
        for candidate in candidates
    ]
    if len(set(candidate_ids)) != 2:
        raise CampaignOwnershipError("standard four-hour candidates must own two distinct slots")
    if eligible_token_slot_ids is None:
        eligible_ids = set(candidate_ids)
    else:
        requested = [
            _required(slot_id, "eligible_token_slot_id")
            for slot_id in eligible_token_slot_ids
        ]
        if len(requested) != len(set(requested)):
            raise CampaignOwnershipError("four-hour eligible token-slot set contains duplicates")
        eligible_ids = set(requested)
        if not eligible_ids.issubset(set(candidate_ids)):
            raise CampaignOwnershipError("four-hour eligible token-slot set is not campaign-owned")

    campaign = _required(campaign_id, "campaign_id")
    run = _required(run_id, "run_id")
    cycle = _required(cycle_id, "cycle_id")
    timestamp = now or _utc_now()
    savepoint_active = False

    def rollback_savepoint() -> None:
        nonlocal savepoint_active
        if not savepoint_active:
            return
        try:
            connection.execute(
                "ROLLBACK TO SAVEPOINT printer_standard_four_hour_handoff"
            )
            connection.execute(
                "RELEASE SAVEPOINT printer_standard_four_hour_handoff"
            )
        except sqlite3.Error:
            pass
        savepoint_active = False

    try:
        connection.execute("SAVEPOINT printer_standard_four_hour_handoff")
        savepoint_active = True
        slot_rows = connection.execute(
            """SELECT token_slot_id, token_row_id, pair_row_id, mint_identity,
                      pair_identity, lifecycle_identity, token_state
               FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
               ORDER BY slot_ordinal""",
            (campaign, run, cycle),
        ).fetchall()
        if len(slot_rows) != 2:
            raise CampaignOwnershipError(
                "standard four-hour handoff requires the exact two-slot ownership set"
            )
        slot_by_id = {str(row[0]): row for row in slot_rows}
        if set(candidate_ids) != set(slot_by_id):
            raise CampaignOwnershipError(
                "four-hour handoff candidates do not cover both token slots"
            )

        prepared: list[dict[str, Any]] = []
        successor_ids: set[str] = set()
        handoff_modes: set[str] = set()

        for candidate in candidates:
            slot_id = _required(candidate.get("token_slot_id"), "token_slot_id")
            slot = slot_by_id[slot_id]
            try:
                token_row_id = int(candidate.get("token_row_id"))
                pair_row_id = int(candidate.get("pair_row_id"))
                memory_window_1h_id = int(candidate.get("memory_window_1h_id"))
            except (TypeError, ValueError) as exc:
                raise CampaignOwnershipError(
                    f"four-hour handoff numeric identity invalid for {slot_id}"
                ) from exc
            mint_identity = _required(candidate.get("mint_identity"), "mint_identity")
            pair_identity = _required(candidate.get("pair_identity"), "pair_identity")
            lifecycle_identity = _required(
                candidate.get("lifecycle_identity"), "lifecycle_identity"
            )
            predecessor_id = _required(
                candidate.get("campaign_window_1h_id"), "campaign_window_1h_id"
            )
            successor_id = _required(
                candidate.get("campaign_window_4h_id"), "campaign_window_4h_id"
            )
            tracking_lane = _required(candidate.get("tracking_lane"), "tracking_lane")
            state = str(slot[6])
            if (
                int(slot[1]) != token_row_id
                or int(slot[2]) != pair_row_id
                or str(slot[3]) != mint_identity
                or str(slot[4]) != pair_identity
                or str(slot[5]) != lifecycle_identity
            ):
                raise CampaignOwnershipError(
                    f"four-hour handoff slot identity mismatch for {slot_id}"
                )

            slot_successors = connection.execute(
                """SELECT window_id FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                     AND token_slot_id=? AND window_kind='WINDOW_4H'
                   ORDER BY window_id""",
                (campaign, run, cycle, slot_id),
            ).fetchall()
            scoped_successor_ids = {str(row[0]) for row in slot_successors}
            existing_named = connection.execute(
                "SELECT token_slot_id FROM printer_memory_factory_campaign_windows WHERE window_id=?",
                (successor_id,),
            ).fetchone()

            if slot_id not in eligible_ids:
                if state == "WINDOW_4H_CONTINUING":
                    raise CampaignOwnershipError(
                        f"ineligible four-hour slot is already continuing: {slot_id}"
                    )
                if scoped_successor_ids:
                    raise CampaignOwnershipError(
                        f"ineligible four-hour slot has a successor: {slot_id}"
                    )
                if existing_named is not None:
                    raise CampaignOwnershipError(
                        f"ineligible four-hour successor identity is already owned: {successor_id}"
                    )
                continue

            if state not in {"WINDOW_1H_CLOSED", "WINDOW_4H_CONTINUING"}:
                raise CampaignOwnershipError(
                    f"pre-four-hour token state conflict for {slot_id}: {state}"
                )
            if successor_id in successor_ids:
                raise CampaignOwnershipError(
                    "four-hour handoff successor identity is duplicated"
                )
            successor_ids.add(successor_id)

            predecessor = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id,
                          token_row_id, pair_row_id, window_kind, window_state,
                          root_15m_lifecycle_identity, memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE window_id=?""",
                (predecessor_id,),
            ).fetchone()
            if predecessor is None:
                raise CampaignOwnershipError(
                    f"four-hour handoff predecessor missing for {slot_id}"
                )
            if (
                str(predecessor[0]) != campaign
                or str(predecessor[1]) != run
                or str(predecessor[2]) != cycle
                or str(predecessor[3]) != slot_id
                or int(predecessor[4]) != token_row_id
                or int(predecessor[5]) != pair_row_id
                or str(predecessor[6]) != "WINDOW_1H"
                or str(predecessor[7]) != "CLEAN_PROMOTED"
                or str(predecessor[8]) != lifecycle_identity
                or predecessor[9] is None
                or int(predecessor[9]) != memory_window_1h_id
            ):
                raise CampaignOwnershipError(
                    f"four-hour handoff predecessor identity/eligibility mismatch for {slot_id}"
                )

            physical = connection.execute(
                """SELECT token_id, pair_id, window_kind, window_status,
                          data_quality_label, do_not_train, window_end_at
                   FROM printer_memory_windows WHERE id=?""",
                (memory_window_1h_id,),
            ).fetchone()
            if (
                physical is None
                or int(physical[0]) != token_row_id
                or int(physical[1]) != pair_row_id
                or str(physical[2]) != "WINDOW_1H"
                or str(physical[3]) != "WINDOW_CLOSED"
                or str(physical[4]) != "CLEAN_DATA"
                or bool(physical[5])
                or physical[6] is None
            ):
                raise CampaignOwnershipError(
                    f"physical first-hour identity/quality mismatch for {slot_id}"
                )

            clean_episode_count = int(
                connection.execute(
                    """SELECT COUNT(*) FROM printer_episodes
                       WHERE memory_window_id=? AND token_id=? AND pair_id=?
                         AND episode_kind='WINDOW_1H_CLEAN_MEMORY'
                         AND episode_status='COMPLETE'
                         AND memory_status='CLEAN_MEMORY'
                         AND data_quality_label='CLEAN_DATA'
                         AND do_not_train=0
                         AND window_kind='WINDOW_1H'
                         AND memory_quality_label='CLEAN_MEMORY'""",
                    (memory_window_1h_id, token_row_id, pair_row_id),
                ).fetchone()[0]
            )
            if clean_episode_count != 1:
                raise CampaignOwnershipError(
                    f"exact clean first-hour predecessor object missing/ambiguous for {slot_id}"
                )

            from datetime import timedelta
            from printer_v1.snapshots.cadence_policy import get_policy

            policy = get_policy("WINDOW_4H", tracking_lane)
            if policy is None:
                raise CampaignOwnershipError(
                    f"WINDOW_4H cadence policy missing for {tracking_lane}"
                )
            try:
                predecessor_end = datetime.fromisoformat(
                    str(physical[6]).replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise CampaignOwnershipError(
                    f"physical first-hour close timestamp invalid for {slot_id}"
                ) from exc
            if predecessor_end.tzinfo is None:
                raise CampaignOwnershipError(
                    f"physical first-hour close timestamp is timezone-naive for {slot_id}"
                )
            checkpoint_cutoff = (
                predecessor_end.astimezone(timezone.utc)
                + timedelta(seconds=int(policy.window_close_interval_seconds))
            ).isoformat()

            existing = connection.execute(
                """SELECT campaign_id, run_id, cycle_id, token_slot_id,
                          token_row_id, pair_row_id, window_kind, window_state,
                          root_15m_lifecycle_identity, predecessor_window_id,
                          memory_window_row_id
                   FROM printer_memory_factory_campaign_windows
                   WHERE window_id=?""",
                (successor_id,),
            ).fetchone()
            if existing is None:
                if state != "WINDOW_1H_CLOSED" or scoped_successor_ids:
                    raise CampaignOwnershipError(
                        f"partial/conflicting four-hour handoff state for {slot_id}"
                    )
                mode = "NEW"
            else:
                if scoped_successor_ids != {successor_id}:
                    raise CampaignOwnershipError(
                        f"competing four-hour successor ownership for {slot_id}"
                    )
                if (
                    str(existing[0]) != campaign
                    or str(existing[1]) != run
                    or str(existing[2]) != cycle
                    or str(existing[3]) != slot_id
                    or int(existing[4]) != token_row_id
                    or int(existing[5]) != pair_row_id
                    or str(existing[6]) != "WINDOW_4H"
                    or str(existing[7]) != "PLANNED"
                    or str(existing[8]) != lifecycle_identity
                    or str(existing[9]) != predecessor_id
                    or existing[10] is not None
                    or state != "WINDOW_4H_CONTINUING"
                ):
                    raise CampaignOwnershipError(
                        f"conflicting four-hour replay identity for {slot_id}"
                    )
                mode = "REPLAY"
            handoff_modes.add(mode)
            prepared.append(
                {
                    "token_slot_id": slot_id,
                    "token_row_id": token_row_id,
                    "pair_row_id": pair_row_id,
                    "lifecycle_identity": lifecycle_identity,
                    "predecessor_id": predecessor_id,
                    "successor_id": successor_id,
                    "checkpoint_cutoff": checkpoint_cutoff,
                }
            )

        if len(handoff_modes) > 1:
            raise CampaignOwnershipError(
                "partial standard four-hour handoff cannot be replayed or completed"
            )

        if handoff_modes == {"NEW"}:
            for item in prepared:
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_windows(
                        window_id,campaign_id,run_id,cycle_id,token_slot_id,token_row_id,
                        pair_row_id,window_kind,window_state,root_15m_lifecycle_identity,
                        predecessor_window_id,containing_main_window_id,memory_window_row_id,
                        checkpoint_cutoff,support_only,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'WINDOW_4H','PLANNED',?,?,NULL,NULL,?,0,?,?)""",
                    (
                        item["successor_id"], campaign, run, cycle,
                        item["token_slot_id"], item["token_row_id"],
                        item["pair_row_id"], item["lifecycle_identity"],
                        item["predecessor_id"], item["checkpoint_cutoff"],
                        timestamp, timestamp,
                    ),
                )
            for item in prepared:
                cursor = connection.execute(
                    """UPDATE printer_memory_factory_campaign_token_slots
                       SET token_state='WINDOW_4H_CONTINUING', updated_at=?
                       WHERE token_slot_id=? AND campaign_id=? AND run_id=?
                         AND cycle_id=? AND token_state='WINDOW_1H_CLOSED'""",
                    (timestamp, item["token_slot_id"], campaign, run, cycle),
                )
                if cursor.rowcount != 1:
                    raise CampaignOwnershipError(
                        f"four-hour token-state compare-and-update failed for {item['token_slot_id']}"
                    )

        verify_rows = connection.execute(
            """SELECT window_id,token_slot_id,token_row_id,pair_row_id,window_kind,
                      window_state,root_15m_lifecycle_identity,predecessor_window_id,
                      memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND window_kind='WINDOW_4H'
               ORDER BY token_slot_id""",
            (campaign, run, cycle),
        ).fetchall()
        if (
            len(verify_rows) != len(eligible_ids)
            or {str(row[0]) for row in verify_rows} != successor_ids
        ):
            raise CampaignOwnershipError(
                "standard four-hour successor read-back count/identity mismatch"
            )
        expected_by_id = {str(item["successor_id"]): item for item in prepared}
        for row in verify_rows:
            item = expected_by_id[str(row[0])]
            if (
                str(row[1]) != str(item["token_slot_id"])
                or int(row[2]) != int(item["token_row_id"])
                or int(row[3]) != int(item["pair_row_id"])
                or str(row[4]) != "WINDOW_4H"
                or str(row[5]) != "PLANNED"
                or str(row[6]) != str(item["lifecycle_identity"])
                or str(row[7]) != str(item["predecessor_id"])
                or row[8] is not None
            ):
                raise CampaignOwnershipError(
                    f"standard four-hour successor read-back mismatch for {item['token_slot_id']}"
                )
            slot_state = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
                (item["token_slot_id"], campaign, run, cycle),
            ).fetchone()
            if slot_state is None or str(slot_state[0]) != "WINDOW_4H_CONTINUING":
                raise CampaignOwnershipError(
                    f"standard four-hour token-state read-back mismatch for {item['token_slot_id']}"
                )

        for slot_id in set(candidate_ids) - eligible_ids:
            slot_state = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE token_slot_id=? AND campaign_id=? AND run_id=? AND cycle_id=?""",
                (slot_id, campaign, run, cycle),
            ).fetchone()
            if slot_state is None or str(slot_state[0]) == "WINDOW_4H_CONTINUING":
                raise CampaignOwnershipError(
                    f"ineligible four-hour token-state read-back mismatch for {slot_id}"
                )

        replay = bool(eligible_ids) and handoff_modes == {"REPLAY"}
        connection.execute("RELEASE SAVEPOINT printer_standard_four_hour_handoff")
        savepoint_active = False
        return {
            "persisted": not replay,
            "replay": replay,
            "continuation_count": len(eligible_ids),
            "window_ids": sorted(successor_ids),
        }
    except sqlite3.Error as exc:
        rollback_savepoint()
        raise CampaignOwnershipError(str(exc)) from exc
    except Exception:
        rollback_savepoint()
        raise
'''


BUDGETS = r'''def standard_campaign_lifecycle_budget(
    tracking_lanes: tuple[str, str],
    continuing_mask: tuple[bool, bool],
) -> dict[str, Any]:
    """Derive the two-token prefix plus only the eligible WINDOW_4H suffixes."""
    lanes = tuple(str(lane) for lane in tracking_lanes)
    mask = tuple(continuing_mask)
    if len(lanes) != 2 or len(mask) != 2:
        raise ValueError("standard four-hour campaign requires exactly two lanes and two eligibility flags")
    if any(type(flag) is not bool for flag in mask):
        raise ValueError("standard four-hour eligibility mask must contain booleans")

    request_components: dict[str, int] = {"discovery": 2}
    scheduler_components: dict[str, int] = {}
    for index, (lane, continues) in enumerate(zip(lanes, mask, strict=True), start=1):
        if lane not in REQUEST_CEILINGS:
            raise ValueError("TRACK_FAST or TRACK_NORMAL cadence policy required")
        fifteen = get_policy("WINDOW_15M", lane)
        one_hour = get_policy("WINDOW_1H", lane)
        if fifteen is None or one_hour is None:
            raise ValueError("15m and 1h cadence policies required")
        request_components[f"token_{index}_window_15m_snapshots"] = int(
            fifteen.minimum_required_snapshots
        )
        request_components[f"token_{index}_window_15m_context"] = 5
        request_components[f"token_{index}_window_1h_snapshots"] = int(
            one_hour.minimum_required_snapshots
        )
        scheduler_components[f"token_{index}_discovery_handoff"] = 1
        scheduler_components[f"token_{index}_window_15m"] = int(
            fifteen.minimum_required_snapshots
        )
        scheduler_components[f"token_{index}_window_1h"] = int(
            one_hour.minimum_required_snapshots
        )
        if continues:
            phase = runtime_budget(lane)
            request_components[f"token_{index}_window_4h_phase"] = int(
                phase["phase_request_ceiling"]
            )
            scheduler_components[f"token_{index}_window_4h_phase"] = int(
                phase["phase_scheduler_ceiling"]
            )

    continuation_count = sum(1 for flag in mask if flag)
    return {
        "tracking_lanes": lanes,
        "continuing_mask": mask,
        "continuation_count": continuation_count,
        "request_components": request_components,
        "request_ceiling": sum(request_components.values()),
        "scheduler_components": scheduler_components,
        "scheduler_ceiling": sum(scheduler_components.values()),
        "automatic_retries": 0,
        "endpoint_rotation": False,
        "real_collection_enabled": bool(continuation_count) and all(
            bool(runtime_budget(lane)["enabled_for_real_collection"])
            for lane, continues in zip(lanes, mask, strict=True)
            if continues
        ),
    }


def standard_two_token_lifecycle_budget(
    tracking_lanes: tuple[str, str],
) -> dict[str, Any]:
    """Compatibility wrapper for the historical both-eligible standard plan."""
    return standard_campaign_lifecycle_budget(tracking_lanes, (True, True))
'''


PLANNING = r'''STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION = "STANDARD_4H_ELIGIBILITY_V1"


def _normalize_standard_4h_eligible_slots(
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None,
) -> tuple[tuple[str, str], set[str]]:
    if len(candidates) != 2:
        raise ValueError("standard four-hour campaign requires exactly two candidates")
    candidate_ids = tuple(str(candidate["token_slot_id"]).strip() for candidate in candidates)
    if any(not slot_id for slot_id in candidate_ids) or len(set(candidate_ids)) != 2:
        raise ValueError("standard four-hour campaign requires two distinct token-slot identities")
    if eligible_token_slot_ids is None:
        return (candidate_ids[0], candidate_ids[1]), set(candidate_ids)
    if isinstance(eligible_token_slot_ids, (str, bytes)):
        raise ValueError("eligible_token_slot_ids must be a sequence of slot identities")
    requested = tuple(str(slot_id).strip() for slot_id in eligible_token_slot_ids)
    if any(not slot_id for slot_id in requested) or len(requested) != len(set(requested)):
        raise ValueError("eligible token-slot identities must be distinct and non-empty")
    if not set(requested).issubset(set(candidate_ids)):
        raise ValueError("eligible token-slot identity is not owned by this campaign")
    return (candidate_ids[0], candidate_ids[1]), set(requested)


def _campaign_slot_identity_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[sqlite3.Row]:
    rows = connection.execute(
        """SELECT token_slot_id,token_row_id,pair_row_id,mint_identity,pair_identity,
                  lifecycle_identity,slot_ordinal
           FROM printer_memory_factory_campaign_token_slots
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY slot_ordinal""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    if len(rows) != 2 or {int(row["slot_ordinal"]) for row in rows} != {1, 2}:
        raise ValueError("standard four-hour eligibility requires the exact two campaign slots")
    return list(rows)


def load_standard_four_hour_eligibility_manifests(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
) -> dict[str, dict[str, Any]] | None:
    """Return the exact durable two-slot standard-4h manifest, or None if absent."""
    slot_rows = _campaign_slot_identity_rows(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    close_by_slot: dict[str, sqlite3.Row] = {}
    present: dict[str, dict[str, Any]] = {}
    for slot in slot_rows:
        slot_id = str(slot["token_slot_id"])
        closes = connection.execute(
            """SELECT id,token_id,pair_id,tracking_lane,memory_window_id,result_json
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=?
                 AND step_kind='CONTINUATION_CLOSE' AND step_status='SUCCEEDED'
               ORDER BY id""",
            (factory_run_id, int(slot["token_row_id"]), int(slot["pair_row_id"])),
        ).fetchall()
        if len(closes) > 1:
            raise ValueError(f"ambiguous successful first-hour close for {slot_id}")
        if not closes:
            continue
        close = closes[0]
        close_by_slot[slot_id] = close
        try:
            payload = json.loads(str(close["result_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid first-hour close result JSON for {slot_id}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid first-hour close result payload for {slot_id}")
        manifest = payload.get("standard_four_hour_eligibility")
        if manifest is not None:
            if not isinstance(manifest, dict):
                raise ValueError(f"invalid standard four-hour eligibility manifest for {slot_id}")
            present[slot_id] = dict(manifest)

    if not present:
        return None
    if len(present) != 2 or set(present) != {str(row["token_slot_id"]) for row in slot_rows}:
        raise ValueError("partial standard four-hour eligibility manifest")

    for slot in slot_rows:
        slot_id = str(slot["token_slot_id"])
        if slot_id not in close_by_slot:
            raise ValueError(f"missing successful first-hour close for manifest slot {slot_id}")
        manifest = present[slot_id]
        eligible = manifest.get("eligible")
        expected_verdict = "CONTINUE_TO_WINDOW_4H" if eligible is True else "BLOCK_CONTINUATION"
        if type(eligible) is not bool:
            raise ValueError(f"invalid eligibility boolean for {slot_id}")
        if (
            str(manifest.get("contract_version"))
            != STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION
            or str(manifest.get("campaign_id")) != str(campaign_id)
            or str(manifest.get("campaign_run_id")) != str(run_id)
            or str(manifest.get("cycle_id")) != str(cycle_id)
            or str(manifest.get("token_slot_id")) != slot_id
            or int(manifest.get("token_id", -1)) != int(slot["token_row_id"])
            or int(manifest.get("pair_id", -1)) != int(slot["pair_row_id"])
            or str(manifest.get("verdict")) != expected_verdict
        ):
            raise ValueError(f"standard four-hour eligibility manifest identity mismatch for {slot_id}")
    return present


def _persist_standard_four_hour_eligibility_manifests(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_ids: set[str],
) -> dict[str, dict[str, Any]]:
    slot_rows = _campaign_slot_identity_rows(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
    )
    slot_by_id = {str(row["token_slot_id"]): row for row in slot_rows}
    candidate_ids = {str(candidate["token_slot_id"]) for candidate in candidates}
    if candidate_ids != set(slot_by_id):
        raise ValueError("standard four-hour manifest candidates do not cover exact campaign slots")

    for candidate in candidates:
        slot_id = str(candidate["token_slot_id"])
        slot = slot_by_id[slot_id]
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        lane = str(candidate["tracking_lane"])
        memory_window_id = int(candidate["memory_window_1h_id"])
        if (
            int(slot["token_row_id"]) != token_id
            or int(slot["pair_row_id"]) != pair_id
            or str(slot["mint_identity"]) != str(candidate["mint_identity"])
            or str(slot["pair_identity"]) != str(candidate["pair_identity"])
            or str(slot["lifecycle_identity"]) != str(candidate["lifecycle_identity"])
        ):
            raise ValueError(f"standard four-hour manifest slot identity mismatch for {slot_id}")
        closes = connection.execute(
            """SELECT id,token_id,pair_id,tracking_lane,memory_window_id,result_json
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                 AND step_kind='CONTINUATION_CLOSE' AND step_status='SUCCEEDED'
               ORDER BY id""",
            (factory_run_id, token_id, pair_id, lane),
        ).fetchall()
        if len(closes) != 1:
            raise ValueError(f"exact successful first-hour close missing/ambiguous for {slot_id}")
        close = closes[0]
        if close["memory_window_id"] is None or int(close["memory_window_id"]) != memory_window_id:
            raise ValueError(f"first-hour close memory identity mismatch for {slot_id}")
        try:
            payload = json.loads(str(close["result_json"] or "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid first-hour close result JSON for {slot_id}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"invalid first-hour close result payload for {slot_id}")
        eligible = slot_id in eligible_ids
        manifest = {
            "contract_version": STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION,
            "campaign_id": str(campaign_id),
            "campaign_run_id": str(run_id),
            "cycle_id": str(cycle_id),
            "token_slot_id": slot_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "verdict": "CONTINUE_TO_WINDOW_4H" if eligible else "BLOCK_CONTINUATION",
            "eligible": eligible,
        }
        existing = payload.get("standard_four_hour_eligibility")
        if existing is not None and existing != manifest:
            raise ValueError(f"standard four-hour eligibility manifest conflict for {slot_id}")
        if existing is None:
            payload["standard_four_hour_eligibility"] = manifest
            connection.execute(
                "UPDATE printer_memory_factory_run_steps SET result_json=?,updated_at=? WHERE id=?",
                (json.dumps(payload, sort_keys=True), datetime.now(timezone.utc).isoformat(), int(close["id"])),
            )

    loaded = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    if loaded is None:
        raise ValueError("standard four-hour eligibility manifest write disappeared")
    actual_eligible = {slot_id for slot_id, manifest in loaded.items() if manifest["eligible"] is True}
    if actual_eligible != eligible_ids:
        raise ValueError("standard four-hour eligibility manifest subset mismatch")
    return loaded


def _standard_campaign_4h_plan_state(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidate_order, eligible_ids = _normalize_standard_4h_eligible_slots(
        candidates, eligible_token_slot_ids
    )
    manifests = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    if manifests is None:
        raise ValueError("standard four-hour plan is missing durable eligibility manifest")
    manifest_eligible = {slot_id for slot_id, manifest in manifests.items() if manifest["eligible"] is True}
    if manifest_eligible != eligible_ids:
        raise ValueError("standard four-hour requested subset differs from durable manifest")

    planned_by_slot: dict[str, int] = {}
    total_expected = 0
    for candidate in candidates:
        slot_id = str(candidate["token_slot_id"])
        token_id = int(candidate["token_row_id"])
        pair_id = int(candidate["pair_row_id"])
        lane = str(candidate["tracking_lane"])
        window_id = str(candidate["campaign_window_4h_id"])
        if slot_id not in eligible_ids:
            window_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                     AND window_kind='WINDOW_4H'""",
                (campaign_id, run_id, cycle_id, slot_id),
            ).fetchone()[0])
            step_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                     AND step_kind LIKE 'LONG_CONTINUATION_%'""",
                (factory_run_id, token_id, pair_id, lane),
            ).fetchone()[0])
            owned_count = int(connection.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                     AND factory_run_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
                     AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
                (campaign_id, run_id, cycle_id, slot_id, factory_run_id),
            ).fetchone()[0])
            slot = connection.execute(
                """SELECT token_state FROM printer_memory_factory_campaign_token_slots
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?""",
                (campaign_id, run_id, cycle_id, slot_id),
            ).fetchone()
            if (
                window_count != 0
                or step_count != 0
                or owned_count != 0
                or slot is None
                or str(slot[0]) == "WINDOW_4H_CONTINUING"
            ):
                raise ValueError(f"ineligible slot has partial four-hour state: {slot_id}")
            continue

        policy = get_policy(WINDOW_KIND, lane)
        if policy is None:
            raise ValueError(f"missing WINDOW_4H policy for {lane}")
        expected = int(policy.minimum_required_snapshots)
        total_expected += expected
        planned_by_slot[slot_id] = expected
        window = connection.execute(
            """SELECT window_state,memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?
                 AND window_id=? AND window_kind='WINDOW_4H'""",
            (campaign_id, run_id, cycle_id, slot_id, window_id),
        ).fetchone()
        if window is None or str(window[0]) != "PLANNED" or window[1] is not None:
            raise ValueError(f"incomplete four-hour campaign window for {slot_id}")
        slot = connection.execute(
            """SELECT token_state FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND run_id=? AND cycle_id=? AND token_slot_id=?""",
            (campaign_id, run_id, cycle_id, slot_id),
        ).fetchone()
        if slot is None or str(slot[0]) != "WINDOW_4H_CONTINUING":
            raise ValueError(f"incomplete four-hour slot state for {slot_id}")
        step_rows = connection.execute(
            """SELECT step_kind,scheduler_job_id
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=? AND tracking_lane=?
                 AND step_kind LIKE 'LONG_CONTINUATION_%'""",
            (factory_run_id, token_id, pair_id, lane),
        ).fetchall()
        if (
            len(step_rows) != expected
            or sum(1 for row in step_rows if str(row[0]) == "LONG_CONTINUATION_CLOSE") != 1
            or any(row[1] is None for row in step_rows)
            or len({int(row[1]) for row in step_rows}) != expected
        ):
            raise ValueError(f"incomplete four-hour run-step plan for {slot_id}")
        ownership_count = int(connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_campaign_scheduler_work AS cw
               JOIN printer_memory_factory_run_steps AS rs
                 ON rs.scheduler_job_id=cw.scheduler_job_id
               WHERE cw.campaign_id=? AND cw.run_id=? AND cw.cycle_id=?
                 AND cw.token_slot_id=? AND cw.window_id=?
                 AND cw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND cw.work_scope='WINDOW_LIFECYCLE' AND cw.stage_id='WINDOW_4H'
                 AND cw.target_category='CAMPAIGN_WINDOW'
                 AND cw.target_identity=cw.window_id AND cw.factory_run_id=?
                 AND rs.run_id=? AND rs.token_id=? AND rs.pair_id=?
                 AND rs.tracking_lane=? AND cw.work_intent=rs.step_kind
                 AND rs.step_kind LIKE 'LONG_CONTINUATION_%'""",
            (
                campaign_id, run_id, cycle_id, slot_id, window_id, factory_run_id,
                factory_run_id, token_id, pair_id, lane,
            ),
        ).fetchone()[0])
        if ownership_count != expected:
            raise ValueError(f"incomplete four-hour Scheduler ownership for {slot_id}")

    total_windows = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    total_steps = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (factory_run_id,),
    ).fetchone()[0])
    total_owned = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id, factory_run_id),
    ).fetchone()[0])
    if (
        total_windows != len(eligible_ids)
        or total_steps != total_expected
        or total_owned != total_expected
    ):
        raise ValueError("partial_or_ambiguous_standard_four_hour_plan")
    later = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND window_kind IN ('WINDOW_12H','WINDOW_24H')""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    if later:
        raise ValueError("standard four-hour plan must not create 12h/24h windows")
    return {
        "planned_by_slot": planned_by_slot,
        "planned_jobs": total_expected,
        "continuation_count": len(eligible_ids),
        "no_op": len(eligible_ids) == 0,
        "eligible_token_slot_ids": [slot for slot in candidate_order if slot in eligible_ids],
    }


def plan_standard_campaign_4h_handoff(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    factory_run_id: str,
    candidates: Sequence[Mapping[str, Any]],
    eligible_token_slot_ids: Sequence[str] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose the exact eligible subset of the standard two-slot 4h campaign."""
    candidate_order, eligible_ids = _normalize_standard_4h_eligible_slots(
        candidates, eligible_token_slot_ids
    )
    campaign_run = connection.execute(
        """SELECT authoritative_run_id FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=?""",
        (campaign_id, run_id),
    ).fetchone()
    if (
        campaign_run is None
        or campaign_run[0] is None
        or str(campaign_run[0]) != str(factory_run_id)
    ):
        raise ValueError("campaign run/factory run identity mismatch")

    lanes = tuple(str(candidate["tracking_lane"]) for candidate in candidates)
    mask = tuple(slot_id in eligible_ids for slot_id in candidate_order)
    budget = standard_campaign_lifecycle_budget(
        (lanes[0], lanes[1]), (bool(mask[0]), bool(mask[1]))
    )
    if bool(budget["real_collection_enabled"]):
        raise ValueError("eligible-subset repair must not enable real WINDOW_4H collection")

    existing_manifests = load_standard_four_hour_eligibility_manifests(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        cycle_id=cycle_id,
        factory_run_id=factory_run_id,
    )
    existing_windows = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'""",
        (campaign_id, run_id, cycle_id),
    ).fetchone()[0])
    existing_steps = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (factory_run_id,),
    ).fetchone()[0])
    existing_owned = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND stage_id='WINDOW_4H' AND work_scope='WINDOW_LIFECYCLE'""",
        (campaign_id, run_id, cycle_id, factory_run_id),
    ).fetchone()[0])

    if existing_manifests is not None:
        manifest_eligible = {
            slot_id for slot_id, manifest in existing_manifests.items()
            if manifest["eligible"] is True
        }
        if manifest_eligible != eligible_ids:
            raise ValueError("requested standard four-hour subset differs from durable manifest")
        verified = _standard_campaign_4h_plan_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
        )
        return {"planned": True, "replay": True, **verified, "budget": budget}

    if existing_windows or existing_steps or existing_owned:
        raise ValueError("partial_or_ambiguous_standard_four_hour_plan_without_manifest")
    if connection.in_transaction:
        raise ValueError(
            "standard four-hour campaign planning requires a clean transaction boundary"
        )

    planned_by_slot: dict[str, int] = {}
    timestamp = now or datetime.now(timezone.utc).isoformat()
    connection.execute("BEGIN")
    try:
        _persist_standard_four_hour_eligibility_manifests(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_ids=eligible_ids,
        )
        handoff = campaign_ownership.persist_standard_four_hour_handoff_set(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
            now=timestamp,
        )
        if not handoff.get("persisted") or handoff.get("replay"):
            raise ValueError("fresh subset composition requires a fresh B1 handoff")

        for candidate in candidates:
            slot_id = str(candidate["token_slot_id"])
            if slot_id not in eligible_ids:
                continue
            window_id = str(candidate["campaign_window_4h_id"])
            token_id = int(candidate["token_row_id"])
            pair_id = int(candidate["pair_row_id"])
            lane = str(candidate["tracking_lane"])
            plan = _plan_token_4h_phase(
                connection,
                run_id=factory_run_id,
                token_id=token_id,
                pair_id=pair_id,
                token_mint=str(candidate["mint_identity"]),
                pair_address=str(candidate["pair_identity"]),
                tracking_lane=lane,
                cumulative_scheduler_ceiling=int(budget["scheduler_ceiling"]),
            )
            if not plan.get("planned") or plan.get("replay"):
                raise ValueError(
                    "standard four-hour token plan failed: "
                    + ";".join(str(item) for item in plan.get("blocked_reasons", []))
                )
            planned_by_slot[slot_id] = int(plan["planned_jobs"])
            for step in plan["steps"]:
                job_id = int(step["scheduler_job_id"])
                campaign_ownership.project_campaign_scheduler_job(
                    connection,
                    scheduler_work_id=(
                        f"campaign4h:{campaign_id}:{run_id}:{cycle_id}:"
                        f"{slot_id}:{job_id}"
                    ),
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    token_slot_id=slot_id,
                    window_id=window_id,
                    factory_run_id=factory_run_id,
                    work_intent=str(step["step_kind"]),
                    deadline_at=str(step["scheduled_for"]),
                    scheduler_job_id=job_id,
                    stage_id="WINDOW_4H",
                    target_category="CAMPAIGN_WINDOW",
                    target_identity=window_id,
                    now=timestamp,
                )
        verified = _standard_campaign_4h_plan_state(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            factory_run_id=factory_run_id,
            candidates=candidates,
            eligible_token_slot_ids=tuple(eligible_ids),
        )
        if verified["planned_by_slot"] != planned_by_slot:
            raise ValueError("standard four-hour planned-slot read-back mismatch")
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    return {"planned": True, "replay": False, **verified, "budget": budget}
'''


TERMINAL_VALIDATOR = r'''def _standard_campaign_four_hour_terminal_validation(
    conn: sqlite3.Connection,
    *,
    factory_run_id: str,
    campaign_id: str | None,
    run_id: str | None,
    cycle_id: str | None,
) -> dict[str, Any]:
    """Validate standard 4h terminal truth against the durable eligible subset."""
    if not all((campaign_id, run_id, cycle_id, factory_run_id)):
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}

    from printer_v1.operator_cli.one_token_4h_runtime import (
        load_standard_four_hour_eligibility_manifests,
    )

    try:
        manifests = load_standard_four_hour_eligibility_manifests(
            conn,
            campaign_id=str(campaign_id),
            run_id=str(run_id),
            cycle_id=str(cycle_id),
            factory_run_id=str(factory_run_id),
        )
    except Exception as exc:
        return {
            "enabled": True,
            "complete": False,
            "reasons": [f"standard_four_hour_eligibility_manifest_invalid:{exc}"],
            "per_token": [],
            "expected_continuation_count": 0,
            "window_count": 0,
            "active_owned_four_hour_work": 0,
            "nonterminal_owned_four_hour_windows": 0,
        }

    windows = conn.execute(
        """SELECT w.*,s.slot_ordinal,s.token_state,s.token_row_id AS slot_token_row_id,
                  s.pair_row_id AS slot_pair_row_id
           FROM printer_memory_factory_campaign_windows AS w
           JOIN printer_memory_factory_campaign_token_slots AS s
             ON s.token_slot_id=w.token_slot_id
            AND s.campaign_id=w.campaign_id AND s.run_id=w.run_id AND s.cycle_id=w.cycle_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.window_kind='WINDOW_4H'
           ORDER BY s.slot_ordinal,w.window_id""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchall()
    if manifests is None and not windows:
        return {"enabled": False, "complete": True, "reasons": [], "per_token": []}

    manifest_mode = manifests is not None
    expected_slot_ids = (
        {slot_id for slot_id, manifest in manifests.items() if manifest["eligible"] is True}
        if manifests is not None
        else {str(row["token_slot_id"]) for row in windows}
    )
    expected_continuation_count = len(expected_slot_ids) if manifest_mode else 2
    reasons: list[str] = []
    actual_slot_ids = {str(row["token_slot_id"]) for row in windows}
    if len(windows) != expected_continuation_count:
        reasons.append(
            f"standard_window_4h_count:{len(windows)} expected={expected_continuation_count}"
        )
    if manifest_mode and actual_slot_ids != expected_slot_ids:
        reasons.append("standard_window_4h_slot_set_mismatch")
    if len(actual_slot_ids) != len(windows):
        reasons.append("duplicate_standard_window_4h_slot_identity")
    if len({int(row["token_row_id"]) for row in windows}) != len(windows):
        reasons.append("duplicate_standard_window_4h_token_identity")

    success_states = {
        "CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"
    }
    per_token: list[dict[str, Any]] = []
    expected_owned_total = 0
    for window in windows:
        window_reasons: list[str] = []
        slot_id = str(window["token_slot_id"])
        token_id = int(window["token_row_id"])
        pair_id = int(window["pair_row_id"])
        if manifest_mode and slot_id not in expected_slot_ids:
            window_reasons.append("unexpected_4h_window_for_ineligible_slot")
        if (
            int(window["slot_token_row_id"]) != token_id
            or int(window["slot_pair_row_id"]) != pair_id
        ):
            window_reasons.append("slot_token_pair_identity_mismatch")
        owned = conn.execute(
            """SELECT s.*,j.status AS scheduler_status,sw.work_state,sw.scheduler_work_id
               FROM printer_memory_factory_campaign_scheduler_work AS sw
               JOIN printer_memory_factory_run_steps AS s
                 ON s.scheduler_job_id=sw.scheduler_job_id
               JOIN printer_scheduler_jobs AS j ON j.id=sw.scheduler_job_id
               WHERE sw.campaign_id=? AND sw.run_id=? AND sw.cycle_id=?
                 AND sw.factory_run_id=? AND sw.window_id=? AND sw.token_slot_id=?
                 AND sw.ownership_contract_version='V2_STAGE_SCOPED'
                 AND sw.work_scope='WINDOW_LIFECYCLE' AND sw.stage_id='WINDOW_4H'
                 AND sw.target_category='CAMPAIGN_WINDOW' AND sw.target_identity=sw.window_id
                 AND s.run_id=? AND s.token_id=? AND s.pair_id=?
                 AND s.step_kind IN ('LONG_CONTINUATION_SNAPSHOT','LONG_CONTINUATION_CLOSE')
               ORDER BY s.scheduled_for,s.id""",
            (
                str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id),
                str(window["window_id"]), slot_id, str(factory_run_id), token_id, pair_id,
            ),
        ).fetchall()
        lanes = {str(row["tracking_lane"]) for row in owned}
        lane = next(iter(lanes)) if len(lanes) == 1 else None
        if lane is None:
            window_reasons.append("missing_or_ambiguous_4h_tracking_lane")
            expected = 0
        else:
            try:
                policy = _cadence_get_policy("WINDOW_4H", lane)
                if policy is None:
                    raise ValueError("missing policy")
                expected = int(policy.minimum_required_snapshots)
            except Exception:
                expected = 0
                window_reasons.append("missing_4h_cadence_policy")
        expected_owned_total += expected
        if expected and len(owned) != expected:
            window_reasons.append(f"owned_4h_work_count:{len(owned)} expected={expected}")
        actual = sum(1 for row in owned if row["snapshot_id"] is not None)
        if expected and actual != expected:
            window_reasons.append(f"incomplete_4h_collection:{actual}/{expected}")
        closes = [row for row in owned if str(row["step_kind"]) == "LONG_CONTINUATION_CLOSE"]
        if len(closes) != 1:
            window_reasons.append(f"owned_4h_close_count:{len(closes)} expected=1")
            close = None
        else:
            close = closes[0]
            if str(close["step_status"]) != "SUCCEEDED":
                window_reasons.append(f"owned_4h_close_not_succeeded:{close['step_status']}")
            if str(close["scheduler_status"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_scheduler_not_succeeded:{close['scheduler_status']}"
                )
            if str(close["work_state"]) != "SUCCEEDED":
                window_reasons.append(
                    f"owned_4h_close_campaign_work_not_succeeded:{close['work_state']}"
                )
        memory_id = (
            int(window["memory_window_row_id"])
            if window["memory_window_row_id"] is not None else None
        )
        if memory_id is None:
            window_reasons.append("missing_bound_4h_memory_window")
            physical = None
            clean_object = None
        else:
            physical = conn.execute(
                """SELECT id,token_id,pair_id,window_kind,data_quality_label,
                          memory_status,memory_quality_label,do_not_train
                   FROM printer_memory_windows WHERE id=?""",
                (memory_id,),
            ).fetchone()
            if (
                physical is None
                or int(physical["token_id"]) != token_id
                or int(physical["pair_id"]) != pair_id
                or str(physical["window_kind"]) != "WINDOW_4H"
            ):
                window_reasons.append("bound_4h_memory_identity_mismatch")
                clean_object = None
            else:
                clean_object = _exact_complete_clean_4h_object(
                    conn, memory_window_row_id=memory_id
                )
        window_state = str(window["window_state"])
        if window_state not in success_states:
            window_reasons.append(f"nonterminal_or_failed_4h_window_state:{window_state}")
        if str(window["token_state"]) != "WINDOW_4H_CLOSED":
            window_reasons.append(f"token_slot_not_window_4h_closed:{window['token_state']}")
        if window_state in {"CLEAN_PROMOTED", "ALREADY_EXISTS_IDEMPOTENT"}:
            if clean_object is None:
                window_reasons.append("clean_campaign_state_without_complete_clean_object")
        elif window_state == "DIRTY" and physical is not None:
            dirty = (
                int(physical["do_not_train"] or 0) != 0
                or str(physical["data_quality_label"] or "") != "CLEAN_DATA"
                or str(physical["memory_status"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
                or str(physical["memory_quality_label"] or "") in {
                    "DIRTY_MEMORY", "AUDIT_ONLY_MEMORY", "DO_NOT_TRAIN"
                }
            )
            if not dirty:
                window_reasons.append("dirty_campaign_state_without_dirty_physical_memory")
        elif window_state == "NO_PROMOTION" and clean_object is not None:
            window_reasons.append("no_promotion_campaign_state_with_clean_object")

        per_token.append(
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "token_slot_id": slot_id,
                "window_id": str(window["window_id"]),
                "tracking_lane": lane,
                "expected_snapshots": expected,
                "actual_snapshots": actual,
                "window_state": window_state,
                "token_state": str(window["token_state"]),
                "memory_window_row_id": memory_id,
                "complete_clean_object": clean_object is not None,
                "reasons": window_reasons,
            }
        )
        reasons.extend(f"{window['window_id']}:{reason}" for reason in window_reasons)

    if manifest_mode and manifests is not None:
        for slot_id, manifest in manifests.items():
            if manifest["eligible"] is True:
                continue
            token_id = int(manifest["token_id"])
            pair_id = int(manifest["pair_id"])
            long_count = int(conn.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_run_steps
                   WHERE run_id=? AND token_id=? AND pair_id=?
                     AND step_kind LIKE 'LONG_CONTINUATION_%'""",
                (str(factory_run_id), token_id, pair_id),
            ).fetchone()[0])
            owned_count = int(conn.execute(
                """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
                   WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
                     AND token_slot_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
                     AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
                (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id), slot_id),
            ).fetchone()[0])
            if long_count:
                reasons.append(f"ineligible_slot_long_work:{slot_id}:{long_count}")
            if owned_count:
                reasons.append(f"ineligible_slot_owned_4h_work:{slot_id}:{owned_count}")

    total_long = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%'""",
        (str(factory_run_id),),
    ).fetchone()[0])
    total_owned = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'""",
        (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id)),
    ).fetchone()[0])
    if manifest_mode:
        if total_long != expected_owned_total:
            reasons.append(f"standard_long_work_count:{total_long} expected={expected_owned_total}")
        if total_owned != expected_owned_total:
            reasons.append(f"standard_owned_4h_work_count:{total_owned} expected={expected_owned_total}")
        later = int(conn.execute(
            """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND window_kind IN ('WINDOW_12H','WINDOW_24H')""",
            (str(campaign_id), str(run_id), str(cycle_id)),
        ).fetchone()[0])
        if later:
            reasons.append(f"unexpected_later_window_count:{later}")

    active_owned = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE' AND stage_id='WINDOW_4H'
             AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
        (str(campaign_id), str(run_id), str(cycle_id), str(factory_run_id)),
    ).fetchone()[0])
    nonterminal_windows = int(conn.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND window_kind='WINDOW_4H'
             AND window_state IN ('PLANNED','COLLECTING','CLOSE_PENDING','AUDITING')""",
        (str(campaign_id), str(run_id), str(cycle_id)),
    ).fetchone()[0])
    if active_owned:
        reasons.append(f"active_owned_four_hour_work:{active_owned}")
    if nonterminal_windows:
        reasons.append(f"nonterminal_owned_four_hour_windows:{nonterminal_windows}")
    return {
        "enabled": True,
        "complete": not reasons,
        "reasons": reasons,
        "per_token": per_token,
        "expected_continuation_count": expected_continuation_count,
        "eligibility_manifest_present": manifest_mode,
        "active_owned_four_hour_work": active_owned,
        "nonterminal_owned_four_hour_windows": nonterminal_windows,
        "window_count": len(windows),
    }
'''


replace_between(
    "src/printer_v1/operator_cli/campaign_ownership.py",
    "def persist_standard_four_hour_handoff_set(",
    "def link_report_object(",
    CAMPAIGN_HANDOFF,
)
replace_between(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    "def standard_two_token_lifecycle_budget(",
    "def require_projected_capacity(",
    BUDGETS,
)
replace_between(
    "src/printer_v1/operator_cli/one_token_4h_runtime.py",
    "def _standard_campaign_4h_plan_state(",
    "def close_current_run_4h(",
    PLANNING,
)
replace_between(
    "src/printer_v1/operator_cli/one_command_15m_factory.py",
    "def _standard_campaign_four_hour_terminal_validation(",
    "def _two_token_continuous_proof_validation(",
    TERMINAL_VALIDATOR,
)
