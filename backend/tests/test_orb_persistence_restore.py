"""Behavior tests for ORB persistence restore semantics."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orb import ET, ORBTracker  # noqa: E402
from scheduler import EvaluationScheduler  # noqa: E402


class FakeOrbCursor:
    def __init__(self, docs):
        self._docs = iter(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._docs)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeOrbCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_query = None
        self.last_projection = None

    def find(self, query, projection):
        self.last_query = query
        self.last_projection = projection
        return FakeOrbCursor(self.docs)


class FakeDb:
    def __init__(self, docs):
        self.orb_levels = FakeOrbCollection(docs)


class ORBPersistenceRestoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_uses_et_date_and_normalises_persisted_timestamps(self):
        scheduler = object.__new__(EvaluationScheduler)
        scheduler.orb = ORBTracker()
        scheduler.db = FakeDb(
            [
                {
                    "symbol": "SPY",
                    "date": "2026-06-10",
                    "sessions": {
                        "premarket_30m": {
                            "30": {
                                "high": 101.25,
                                "low": 99.75,
                                "locked": True,
                                "is_valid": True,
                                "session_id": "premarket_30m",
                                "start_time": "2026-06-10T09:00:00-04:00",
                                "lock_time": "2026-06-10T13:30:00Z",
                            }
                        }
                    },
                }
            ]
        )

        await scheduler._load_orb_from_db(now=datetime(2026, 6, 10, 13, 5, tzinfo=timezone.utc))

        self.assertEqual(scheduler.db.orb_levels.last_query, {"date": "2026-06-10"})
        level = scheduler.orb.get_session_levels("SPY")["premarket_30m"][30]
        self.assertIsInstance(level.start_time, datetime)
        self.assertIsInstance(level.lock_time, datetime)
        self.assertEqual(level.start_time.tzinfo, ET)
        self.assertEqual(level.start_time.isoformat(), "2026-06-10T09:00:00-04:00")
        self.assertEqual(level.lock_time.isoformat(), "2026-06-10T09:30:00-04:00")

        status = scheduler.orb.get_session_status("SPY", now=datetime(2026, 6, 10, 9, 35, tzinfo=ET))
        restored_level = status["sessions"]["premarket_30m"]["levels"]["30m"]
        self.assertEqual(restored_level["start_time"], "2026-06-10T09:00:00-04:00")
        self.assertEqual(restored_level["lock_time"], "2026-06-10T09:30:00-04:00")


if __name__ == "__main__":
    unittest.main()
