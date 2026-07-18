from datetime import datetime, timedelta, timezone

import pytest

from flare_intelligence import FlareIntelligenceStore


def _payload(now: datetime, **overrides):
    payload = {
        "contract_version": "flare.intelligence.v1",
        "intelligence_id": "flare-intel:test-1",
        "source_bot": "sentinel-flare",
        "symbol": "NVDA",
        "direction": "bullish",
        "confidence": 0.8,
        "strength": 0.75,
        "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=15)).isoformat(),
        "evidence": {"zscore": 2.4, "adv_pct": 3.1},
    }
    payload.update(overrides)
    return payload


def test_records_deduplicates_and_bounds_flare_adjustment(tmp_path):
    store = FlareIntelligenceStore(tmp_path / "flare.json")
    now = datetime.now(timezone.utc)

    recorded = store.record(_payload(now))
    duplicate = store.record(_payload(now))

    assert recorded == duplicate
    assert store.active("nvda")["intelligence_id"] == "flare-intel:test-1"
    assert 0 < store.adjustment("NVDA") <= 1.25
    assert store.status()["count"] == 1


def test_bearish_intelligence_has_negative_bounded_adjustment(tmp_path):
    store = FlareIntelligenceStore(tmp_path / "flare.json")
    now = datetime.now(timezone.utc)
    store.record(_payload(now, intelligence_id="flare-intel:test-2", direction="bearish", confidence=1.0, strength=1.0))

    assert -1.25 <= store.adjustment("NVDA") < 0


def test_rejects_expired_or_execution_shaped_payloads(tmp_path):
    store = FlareIntelligenceStore(tmp_path / "flare.json")
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="expired"):
        store.record(
            _payload(
                now - timedelta(hours=1),
                intelligence_id="flare-intel:expired",
                expires_at=(now - timedelta(minutes=1)).isoformat(),
            )
        )

    with pytest.raises(ValueError, match="Unsupported"):
        store.record(_payload(now, contract_version="edge.action.v1", intelligence_id="flare-intel:bad"))
