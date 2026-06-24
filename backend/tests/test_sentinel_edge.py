"""Sentinel Edge - Backend API Tests"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ── Health Check ─────────────────────────────────────────────────────────────

class TestHealth:
    """Health check endpoint tests"""

    def test_health_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200

    def test_health_response_structure(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        data = resp.json()
        assert "status" in data
        assert "running" in data
        assert "paused" in data
        assert "active_tickers" in data

    def test_health_status_healthy(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_running_is_bool(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        data = resp.json()
        assert isinstance(data["running"], bool)

    def test_health_paused_is_bool(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        data = resp.json()
        assert isinstance(data["paused"], bool)

    def test_health_active_tickers_is_int(self):
        resp = requests.get(f"{BASE_URL}/api/health")
        data = resp.json()
        assert isinstance(data["active_tickers"], int)


# ── Tickers ───────────────────────────────────────────────────────────────────

class TestTickers:
    """Ticker management endpoint tests"""

    def test_get_tickers_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/tickers")
        assert resp.status_code == 200

    def test_get_tickers_response_structure(self):
        resp = requests.get(f"{BASE_URL}/api/tickers")
        data = resp.json()
        assert "tickers" in data
        assert "count" in data

    def test_get_tickers_default_tickers_present(self):
        resp = requests.get(f"{BASE_URL}/api/tickers")
        data = resp.json()
        tickers = data["tickers"]
        assert isinstance(tickers, list)
        # P1 sprint: tickers are now enriched objects (dicts), not plain strings
        symbols = [t["symbol"] if isinstance(t, dict) else t for t in tickers]
        for symbol in ["SPY", "QQQ", "NVDA", "AAPL"]:
            assert symbol in symbols, f"{symbol} not found in tickers list: {symbols}"

    def test_get_tickers_count_matches_list(self):
        resp = requests.get(f"{BASE_URL}/api/tickers")
        data = resp.json()
        assert data["count"] == len(data["tickers"])

    def test_get_tickers_count_is_4(self):
        resp = requests.get(f"{BASE_URL}/api/tickers")
        data = resp.json()
        assert data["count"] == 12

    def test_add_ticker_returns_200(self):
        resp = requests.post(f"{BASE_URL}/api/tickers/TSLA")
        assert resp.status_code == 200

    def test_add_ticker_response_message(self):
        resp = requests.post(f"{BASE_URL}/api/tickers/TSLA")
        data = resp.json()
        assert "message" in data
        assert "TSLA" in data["message"]

    def test_remove_ticker_returns_200(self):
        # First add it so remove doesn't fail
        requests.post(f"{BASE_URL}/api/tickers/TSLA")
        resp = requests.delete(f"{BASE_URL}/api/tickers/TSLA")
        assert resp.status_code == 200

    def test_remove_ticker_response_message(self):
        requests.post(f"{BASE_URL}/api/tickers/MSFT")
        resp = requests.delete(f"{BASE_URL}/api/tickers/MSFT")
        data = resp.json()
        assert "message" in data
        assert "MSFT" in data["message"]


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestStats:
    """System stats endpoint tests"""

    def test_stats_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        assert resp.status_code == 200

    def test_stats_response_structure(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        data = resp.json()
        assert "active_tickers" in data
        assert "running" in data
        assert "paused" in data

    def test_stats_active_tickers_is_list(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        data = resp.json()
        assert isinstance(data["active_tickers"], list)

    def test_stats_running_is_bool(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        data = resp.json()
        assert isinstance(data["running"], bool)

    def test_stats_orb_levels_count_present(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        data = resp.json()
        assert "orb_levels_count" in data
        assert isinstance(data["orb_levels_count"], int)

    def test_stats_pulse_circuit_state_present(self):
        resp = requests.get(f"{BASE_URL}/api/stats")
        data = resp.json()
        assert "pulse_circuit_state" in data
        assert isinstance(data["pulse_circuit_state"], str)


# ── Markets ───────────────────────────────────────────────────────────────────

class TestMarkets:
    """Market status endpoint tests"""

    def test_markets_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/markets")
        assert resp.status_code == 200

    def test_markets_response_is_dict(self):
        resp = requests.get(f"{BASE_URL}/api/markets")
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_markets_entry_structure(self):
        resp = requests.get(f"{BASE_URL}/api/markets")
        data = resp.json()
        for market_code, market_data in data.items():
            assert "open" in market_data, f"{market_code} missing 'open'"
            assert "lunch_break" in market_data, f"{market_code} missing 'lunch_break'"
            assert "minutes_to_close" in market_data, f"{market_code} missing 'minutes_to_close'"
            break  # Just check first entry

    def test_markets_open_is_bool(self):
        resp = requests.get(f"{BASE_URL}/api/markets")
        data = resp.json()
        for market_code, market_data in data.items():
            assert isinstance(market_data["open"], bool)


# ── Scheduler Control ─────────────────────────────────────────────────────────

class TestSchedulerControl:
    """Scheduler pause/resume endpoint tests"""

    def test_pause_returns_200(self):
        resp = requests.post(f"{BASE_URL}/api/control/pause")
        assert resp.status_code == 200

    def test_pause_response_message(self):
        resp = requests.post(f"{BASE_URL}/api/control/pause")
        data = resp.json()
        assert "message" in data

    def test_resume_returns_200(self):
        resp = requests.post(f"{BASE_URL}/api/control/resume")
        assert resp.status_code == 200

    def test_resume_response_message(self):
        resp = requests.post(f"{BASE_URL}/api/control/resume")
        data = resp.json()
        assert "message" in data

    def test_pause_updates_health(self):
        requests.post(f"{BASE_URL}/api/control/pause")
        health = requests.get(f"{BASE_URL}/api/health").json()
        assert health["paused"] == True

    def test_resume_restores_health(self):
        requests.post(f"{BASE_URL}/api/control/resume")
        health = requests.get(f"{BASE_URL}/api/health").json()
        assert health["paused"] == False


# ── Ticker Config ─────────────────────────────────────────────────────────────

class TestTickerConfig:
    """Ticker metric config endpoint tests"""

    def test_get_config_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/tickers/SPY/config")
        assert resp.status_code == 200

    def test_get_config_response_structure(self):
        resp = requests.get(f"{BASE_URL}/api/tickers/SPY/config")
        data = resp.json()
        assert "symbol" in data
        assert "metrics" in data
        assert data["symbol"] == "SPY"

    def test_get_config_default_metrics(self):
        resp = requests.get(f"{BASE_URL}/api/tickers/SPY/config")
        data = resp.json()
        metrics = data["metrics"]
        for key in ["orb", "atr", "signal", "volume", "price", "breakouts"]:
            assert key in metrics, f"metric '{key}' not found"

    def test_update_config_returns_200(self):
        payload = {"metrics": {"orb": True, "atr": False, "signal": True, "volume": True, "price": True, "breakouts": True}}
        resp = requests.put(f"{BASE_URL}/api/tickers/SPY/config", json=payload)
        assert resp.status_code == 200

    def test_update_config_persists(self):
        payload = {"metrics": {"orb": True, "atr": False, "signal": True, "volume": True, "price": True, "breakouts": True}}
        requests.put(f"{BASE_URL}/api/tickers/SPY/config", json=payload)
        # Read back and verify
        resp = requests.get(f"{BASE_URL}/api/tickers/SPY/config")
        data = resp.json()
        assert data["metrics"]["atr"] == False


# ── ORB Levels ────────────────────────────────────────────────────────────────

class TestORBLevels:
    """ORB levels endpoint tests"""

    def test_orb_levels_returns_200_or_error_dict(self):
        resp = requests.get(f"{BASE_URL}/api/orb/SPY")
        # Either 200 with orb data, or 200 with error message (no ORB data yet)
        assert resp.status_code == 200

    def test_orb_invalid_symbol_returns_error(self):
        resp = requests.get(f"{BASE_URL}/api/orb/INVALID_XYZ_123")
        data = resp.json()
        assert resp.status_code == 200
        assert "error" in data


# ── API Root ──────────────────────────────────────────────────────────────────

class TestAPIRoot:
    """API root endpoint tests"""

    def test_api_root_returns_200(self):
        resp = requests.get(f"{BASE_URL}/api/")
        assert resp.status_code == 200

    def test_api_root_name(self):
        resp = requests.get(f"{BASE_URL}/api/")
        data = resp.json()
        assert "name" in data
        assert data["name"] == "Sentinel Edge"
