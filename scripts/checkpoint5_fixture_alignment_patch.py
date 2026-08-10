from pathlib import Path

cp5_path = Path("tests/test_v2_9_8b_post_dtw100_checkpoint5_1h_memory_construction.py")
operational_path = Path("tests/test_v2_9_8b_operational_selective_1h.py")
alignment_path = Path("tests/test_v2_9_8b_standard_first_hour_harness_reporting_alignment.py")

cp5 = cp5_path.read_text(encoding="utf-8")
operational = operational_path.read_text(encoding="utf-8")
alignment = alignment_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


cp5 = replace_once(
    cp5,
'''            """SELECT id,episode_kind,window_kind,memory_status,outcome_label
               FROM printer_episodes WHERE memory_window_id=?""",
''',
'''            """SELECT id,episode_kind,window_kind,memory_status,episode_outcome_label
               FROM printer_episodes WHERE memory_window_id=?""",
''',
    "CP5 episode outcome column",
)

operational = replace_once(
    operational,
'''from printer_v1.operator_cli.operational_selective_1h import (
''',
'''from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    guard_candidate_windows,
)
from printer_v1.operator_cli.operational_selective_1h import (
''',
    "operational Lane Q import",
)

old_operational_test = '''    def test_e2z_promotes_clean_1h_once(self) -> None:
        with self.fx.connection:
            self.fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (1,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (_iso(T0),),
            )
            self.fx.connection.execute(
                """INSERT INTO printer_token_snapshots(
                    id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    source_status,data_quality_label
                ) VALUES (2,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                (_iso(T1H),),
            )
            ctx = {
                "snapshot_id": 2,
                "e2q_audited": True,
                "e2q_audited_by": "lane_e2q",
                "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                "snapshot_ids": [1, 2],
                "tracking_lane": "TRACK_NORMAL",
            }
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,outcome_label,do_not_train,supporting_context_json
                ) VALUES (201,1,1,'WINDOW_1H',?,?,?,?,1,2,'PARTIAL_MEMORY',
                    'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                (
                    _iso(T0),
                    _iso(T1H),
                    _iso(T0),
                    _iso(T1H),
                    json.dumps(ctx),
                ),
            )
        first = create_clean_memory_from_window(
            self.fx.db, 201, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
        second = create_clean_memory_from_window(
            self.fx.db, 201, operator_approved=True, individual_promotion=True
        )
        self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
        self.assertEqual(first["episode_id"], second["episode_id"])
        kind = self.fx.connection.execute(
            "SELECT episode_kind, memory_status FROM printer_episodes WHERE id=?",
            (first["episode_id"],),
        ).fetchone()
        self.assertEqual(kind[0], "WINDOW_1H_CLEAN_MEMORY")
        self.assertEqual(kind[1], "CLEAN_MEMORY")
'''
new_operational_test = '''    def test_e2z_promotes_clean_1h_once(self) -> None:
        snapshot_ids = list(range(1, 14))
        with self.fx.connection:
            for index, snapshot_id in enumerate(snapshot_ids):
                self.fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                    (snapshot_id, _iso(T15 + timedelta(seconds=225 * index))),
                )
            ctx = {
                "snapshot_id": snapshot_ids[-1],
                "e2q_audited": True,
                "e2q_audited_by": "lane_e2q",
                "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                "snapshot_ids": snapshot_ids,
                "tracking_lane": "TRACK_NORMAL",
            }
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,outcome_label,do_not_train,supporting_context_json
                ) VALUES (201,1,1,'WINDOW_1H',?,?,?,?,?,?,'PARTIAL_MEMORY',
                    'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                (
                    _iso(T15),
                    _iso(T1H),
                    _iso(T15),
                    _iso(T1H),
                    snapshot_ids[0],
                    snapshot_ids[-1],
                    json.dumps(ctx),
                ),
            )
        lane_q = guard_candidate_windows(
            self.fx.db,
            [201],
            operator_approved=True,
            production_mode=True,
        )
        first = create_clean_memory_from_window(
            self.fx.db,
            201,
            operator_approved=True,
            individual_promotion=True,
            lane_q_report=lane_q,
        )
        self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
        second = create_clean_memory_from_window(
            self.fx.db,
            201,
            operator_approved=True,
            individual_promotion=True,
            lane_q_report=lane_q,
        )
        self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
        self.assertEqual(first["episode_id"], second["episode_id"])
        kind = self.fx.connection.execute(
            "SELECT episode_kind, memory_status FROM printer_episodes WHERE id=?",
            (first["episode_id"],),
        ).fetchone()
        self.assertEqual(kind[0], "WINDOW_1H_CLEAN_MEMORY")
        self.assertEqual(kind[1], "CLEAN_MEMORY")
'''
operational = replace_once(
    operational,
    old_operational_test,
    new_operational_test,
    "operational direct 1h E2Z fixture",
)

alignment = replace_once(
    alignment,
'''from printer_v1.operator_cli.operational_selective_1h import (
''',
'''from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    guard_candidate_windows,
)
from printer_v1.operator_cli.operational_selective_1h import (
''',
    "alignment Lane Q import",
)
alignment = replace_once(
    alignment,
'''    T0,
    T1H,
''',
'''    T0,
    T15,
    T1H,
''',
    "alignment T15 import",
)

old_alignment_test = '''    def test_genuine_1h_clean_object_creates_episode_and_fingerprint_once(self) -> None:
        fx = Selective1hFixture()
        try:
            with fx.connection:
                fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (3301,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                    (_iso(T0),),
                )
                fx.connection.execute(
                    """INSERT INTO printer_token_snapshots(
                        id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        source_status,data_quality_label
                    ) VALUES (3302,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                    (_iso(T1H),),
                )
                ctx = {
                    "snapshot_id": 3302,
                    "snapshot_ids": [3301, 3302],
                    "e2q_audited": True,
                    "e2q_audited_by": "lane_e2q",
                    "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                    "tracking_lane": "TRACK_NORMAL",
                }
                fx.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label,outcome_label,do_not_train,supporting_context_json
                    ) VALUES (3201,1,1,'WINDOW_1H',?,?,?,?,3301,3302,'PARTIAL_MEMORY',
                        'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                    (
                        _iso(T0),
                        _iso(T1H),
                        _iso(T0),
                        _iso(T1H),
                        json.dumps(ctx),
                    ),
                )
            first = create_clean_memory_from_window(
                fx.db, 3201, operator_approved=True, individual_promotion=True
            )
            self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
            second = create_clean_memory_from_window(
                fx.db, 3201, operator_approved=True, individual_promotion=True
            )
            self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
            self.assertEqual(first["episode_id"], second["episode_id"])
            self.assertEqual(first["fingerprint_id"], second["fingerprint_id"])
            row = fx.connection.execute(
                """SELECT e.episode_kind, f.fingerprint_kind
                   FROM printer_episodes AS e
                   JOIN printer_memory_fingerprints AS f ON f.episode_id=e.id
                   WHERE e.id=? AND f.id=?""",
                (first["episode_id"], first["fingerprint_id"]),
            ).fetchone()
            self.assertEqual(tuple(row), ("WINDOW_1H_CLEAN_MEMORY", "STATIC_CONDITION_SUMMARY"))
        finally:
            fx.close()
'''
new_alignment_test = '''    def test_genuine_1h_clean_object_creates_episode_and_fingerprint_once(self) -> None:
        fx = Selective1hFixture()
        try:
            snapshot_ids = list(range(3301, 3314))
            with fx.connection:
                for index, snapshot_id in enumerate(snapshot_ids):
                    fx.connection.execute(
                        """INSERT INTO printer_token_snapshots(
                            id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                            source_status,data_quality_label
                        ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                        (snapshot_id, _iso(T15 + timedelta(seconds=225 * index))),
                    )
                ctx = {
                    "snapshot_id": snapshot_ids[-1],
                    "snapshot_ids": snapshot_ids,
                    "e2q_audited": True,
                    "e2q_audited_by": "lane_e2q",
                    "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                    "tracking_lane": "TRACK_NORMAL",
                }
                fx.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label,outcome_label,do_not_train,supporting_context_json
                    ) VALUES (3201,1,1,'WINDOW_1H',?,?,?,?,?,?,'PARTIAL_MEMORY',
                        'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                    (
                        _iso(T15),
                        _iso(T1H),
                        _iso(T15),
                        _iso(T1H),
                        snapshot_ids[0],
                        snapshot_ids[-1],
                        json.dumps(ctx),
                    ),
                )
            lane_q = guard_candidate_windows(
                fx.db,
                [3201],
                operator_approved=True,
                production_mode=True,
            )
            first = create_clean_memory_from_window(
                fx.db,
                3201,
                operator_approved=True,
                individual_promotion=True,
                lane_q_report=lane_q,
            )
            self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
            second = create_clean_memory_from_window(
                fx.db,
                3201,
                operator_approved=True,
                individual_promotion=True,
                lane_q_report=lane_q,
            )
            self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
            self.assertEqual(first["episode_id"], second["episode_id"])
            self.assertEqual(first["fingerprint_id"], second["fingerprint_id"])
            row = fx.connection.execute(
                """SELECT e.episode_kind, f.fingerprint_kind
                   FROM printer_episodes AS e
                   JOIN printer_memory_fingerprints AS f ON f.episode_id=e.id
                   WHERE e.id=? AND f.id=?""",
                (first["episode_id"], first["fingerprint_id"]),
            ).fetchone()
            self.assertEqual(tuple(row), ("WINDOW_1H_CLEAN_MEMORY", "STATIC_CONDITION_SUMMARY"))
        finally:
            fx.close()
'''
alignment = replace_once(
    alignment,
    old_alignment_test,
    new_alignment_test,
    "alignment direct 1h E2Z fixture",
)

cp5_path.write_text(cp5, encoding="utf-8")
operational_path.write_text(operational, encoding="utf-8")
alignment_path.write_text(alignment, encoding="utf-8")
