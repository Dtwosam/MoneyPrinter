from pathlib import Path

path = Path('src/printer_v1/operator_cli/campaign_ownership.py')
text = path.read_text()
if 'def persist_standard_four_hour_handoff_set(' in text:
    raise SystemExit('B1 owner already exists; refusing duplicate patch')
marker = '\ndef link_report_object(\n'
if marker not in text:
    raise SystemExit('campaign ownership insertion marker missing')

addition = r'''

def persist_standard_four_hour_handoff_set(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    candidates: Sequence[Mapping[str, Any]],
    now: str | None = None,
) -> dict[str, Any]:
    """Atomically persist the exact two-slot standard 1h -> 4h ownership handoff.

    Slice B1 owns campaign WINDOW_4H successor identity and token-slot
    advancement only. It creates no Scheduler jobs and performs no source work.
    The SAVEPOINT keeps this primitive composable inside the later B2
    caller-owned transaction.
    """
    if len(candidates) != 2:
        raise CampaignOwnershipError(
            f"standard four-hour handoff requires exactly two candidates; found {len(candidates)}"
        )
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
        prepared: list[dict[str, Any]] = []
        candidate_slot_ids: set[str] = set()
        successor_ids: set[str] = set()
        handoff_modes: set[str] = set()

        for candidate in candidates:
            slot_id = _required(candidate.get("token_slot_id"), "token_slot_id")
            if slot_id in candidate_slot_ids or slot_id not in slot_by_id:
                raise CampaignOwnershipError(
                    "four-hour handoff candidate token-slot set mismatch"
                )
            candidate_slot_ids.add(slot_id)
            slot = slot_by_id[slot_id]
            state = str(slot[6])
            if state not in {"WINDOW_1H_CLOSED", "WINDOW_4H_CONTINUING"}:
                raise CampaignOwnershipError(
                    f"pre-four-hour token state conflict for {slot_id}: {state}"
                )
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
            if successor_id in successor_ids:
                raise CampaignOwnershipError(
                    "four-hour handoff successor identity is duplicated"
                )
            successor_ids.add(successor_id)
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
            slot_successors = connection.execute(
                """SELECT window_id FROM printer_memory_factory_campaign_windows
                   WHERE campaign_id=? AND run_id=? AND cycle_id=?
                     AND token_slot_id=? AND window_kind='WINDOW_4H'
                   ORDER BY window_id""",
                (campaign, run, cycle, slot_id),
            ).fetchall()
            scoped_successor_ids = {str(row[0]) for row in slot_successors}
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

        if candidate_slot_ids != set(slot_by_id):
            raise CampaignOwnershipError(
                "four-hour handoff candidates do not cover both token slots"
            )
        if len(handoff_modes) != 1:
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
        if len(verify_rows) != 2 or {str(row[0]) for row in verify_rows} != successor_ids:
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

        replay = handoff_modes == {"REPLAY"}
        connection.execute(
            "RELEASE SAVEPOINT printer_standard_four_hour_handoff"
        )
        savepoint_active = False
        return {
            "persisted": not replay,
            "replay": replay,
            "continuation_count": 2,
            "window_ids": sorted(successor_ids),
        }
    except sqlite3.Error as exc:
        rollback_savepoint()
        raise CampaignOwnershipError(str(exc)) from exc
    except Exception:
        rollback_savepoint()
        raise
'''

path.write_text(text.replace(marker, addition + marker, 1))
