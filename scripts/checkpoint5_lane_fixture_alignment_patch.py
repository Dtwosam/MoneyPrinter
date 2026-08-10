from pathlib import Path

operational_path = Path("tests/test_v2_9_8b_operational_selective_1h.py")
alignment_path = Path("tests/test_v2_9_8b_standard_first_hour_harness_reporting_alignment.py")

operational = operational_path.read_text(encoding="utf-8")
alignment = alignment_path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


operational = replace_once(
    operational,
'''    def test_e2z_promotes_clean_1h_once(self) -> None:
        snapshot_ids = list(range(1, 14))
        with self.fx.connection:
            for index, snapshot_id in enumerate(snapshot_ids):
''',
'''    def test_e2z_promotes_clean_1h_once(self) -> None:
        snapshot_ids = list(range(1, 14))
        with self.fx.connection:
            self.fx.connection.execute(
                "UPDATE printer_tokens SET token_status='TRACK_NORMAL' WHERE id=1"
            )
            for index, snapshot_id in enumerate(snapshot_ids):
''',
    "operational explicit cadence lane",
)

alignment = replace_once(
    alignment,
'''    def test_genuine_1h_clean_object_creates_episode_and_fingerprint_once(self) -> None:
        fx = Selective1hFixture()
        try:
            snapshot_ids = list(range(3301, 3314))
            with fx.connection:
                for index, snapshot_id in enumerate(snapshot_ids):
''',
'''    def test_genuine_1h_clean_object_creates_episode_and_fingerprint_once(self) -> None:
        fx = Selective1hFixture()
        try:
            snapshot_ids = list(range(3301, 3314))
            with fx.connection:
                fx.connection.execute(
                    "UPDATE printer_tokens SET token_status='TRACK_NORMAL' WHERE id=1"
                )
                for index, snapshot_id in enumerate(snapshot_ids):
''',
    "alignment explicit cadence lane",
)

operational_path.write_text(operational, encoding="utf-8")
alignment_path.write_text(alignment, encoding="utf-8")
