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
        self.updates = []

    def find(self, query, projection):
        self.last_query = query
        self.last_projection = projection
        return FakeOrbCursor(self.docs)

    async def update_one(self, query, update, upsert=False):
        self.updates.append({"query": query, "update": update, "upsert": upsert})


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

    async def test_persist_skips_stale_levels_during_next_day_preopen(self):
        scheduler = object.__new__(EvaluationScheduler)
        scheduler.orb = ORBTracker()
        scheduler.db = FakeDb([])

        scheduler.orb.update("SPY", 100.0, datetime(2026, 6, 15, 9, 31, tzinfo=ET))
        stale_levels = scheduler.orb.get_levels("SPY")

        await scheduler._persist_orb(
            "SPY",
            stale_levels,
            datetime(2026, 6, 16, 8, 30, tzinfo=ET),
        )

        self.assertEqual(scheduler.db.orb_levels.updates, [])

    async def test_restore_skips_doc_with_cross_date_level_timestamps(self):
        scheduler = object.__new__(EvaluationScheduler)
        scheduler.orb = ORBTracker()
        scheduler.db = FakeDb(
            [
                {
                    "symbol": "SPY",
                    "date": "2026-06-16",
                    "sessions": {
                        "market_open": {
                            "15": {
                                "high": 450.0,
                                "low": 445.0,
                                "locked": True,
                                "is_valid": True,
                                "session_id": "market_open",
                                "start_time": "2026-06-15T09:30:00-04:00",
                                "lock_time": "2026-06-15T09:45:00-04:00",
                            }
                        }
                    },
                }
            ]
        )

        await scheduler._load_orb_from_db(now=datetime(2026, 6, 16, 8, 30, tzinfo=ET))

        level = scheduler.orb.get_session_levels("SPY")["market_open"][15]
        self.assertFalse(level.is_valid)


if __name__ == "__main__":
    unittest.main()
