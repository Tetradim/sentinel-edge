"""Route contract tests for the frontend API client used by the unified UI."""
import re
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_API = REPO_ROOT / "frontend" / "src" / "lib" / "api.ts"

for path in (REPO_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


API_CLIENT_ROUTE_CONTRACTS = [
    ("getHealth", "GET", "/api/health", ("'/api/health'",)),
    ("getLiveness", "GET", "/api/live", ("'/api/live'",)),
    ("getReadiness", "GET", "/api/ready", ("'/api/ready'",)),
    ("getProviderHealth", "GET", "/api/providers/health", ("'/api/providers/health'",)),
    ("getMarketDataProviders", "GET", "/api/market-data/providers", ("'/api/market-data/providers'",)),
    ("getPulseStatus", "GET", "/api/pulse/status", ("'/api/pulse/status'",)),
    ("getPulseAccount", "GET", "/api/pulse/account", ("'/api/pulse/account'",)),
    ("getPulsePositions", "GET", "/api/pulse/positions", ("'/api/pulse/positions'",)),
    ("getPulseQueue", "GET", "/api/pulse/queue", ("'/api/pulse/queue'",)),
    ("getPulseHandoffSchema", "GET", "/api/pulse/handoff/schema", ("'/api/pulse/handoff/schema'",)),
    ("postFrontendRum", "POST", "/api/frontend/rum", ("FRONTEND_RUM_PATH", "method: 'POST'")),
    ("sendFrontendRumBeacon", "POST", "/api/frontend/rum", ("FRONTEND_RUM_PATH", "navigator.sendBeacon", "method: 'POST'")),
    ("getFrontendRumStatus", "GET", "/api/frontend/rum/status", ("'/api/frontend/rum/status'",)),
    ("getRateLimitStatus", "GET", "/api/rate-limit/status", ("'/api/rate-limit/status'",)),
    ("getStats", "GET", "/api/stats", ("'/api/stats'",)),
    ("getTickers", "GET", "/api/tickers", ("'/api/tickers'",)),
    ("addTicker", "POST", "/api/tickers/{symbol}", ("`/api/tickers/${encodeURIComponent(symbol)}`", "method: 'POST'")),
    ("removeTicker", "DELETE", "/api/tickers/{symbol}", ("`/api/tickers/${encodeURIComponent(symbol)}`", "method: 'DELETE'")),
    (
        "updateTickerConfig",
        "PUT",
        "/api/tickers/{symbol}/config",
        ("`/api/tickers/${encodeURIComponent(symbol)}/config`", "method: 'PUT'"),
    ),
    ("getTickerConfig", "GET", "/api/tickers/{symbol}/config", ("`/api/tickers/${encodeURIComponent(symbol)}/config`",)),
    ("getOrbLevels", "GET", "/api/orb/{symbol}", ("`/api/orb/${encodeURIComponent(symbol)}`",)),
    ("getChartWorkspace", "GET", "/api/chart-workspace/{symbol}", ("`/api/chart-workspace/${encodeURIComponent(symbol)}",)),
    (
        "getMarketMapProofMarkers",
        "GET",
        "/api/market-map/proof-markers/{symbol}",
        ("`/api/market-map/proof-markers/${encodeURIComponent(symbol)}",),
    ),
    ("getMarketMapContext", "GET", "/api/market-map/context/{symbol}", ("`/api/market-map/context/${encodeURIComponent(symbol)}`",)),
    ("getScannerWorkbenchCatalog", "GET", "/api/scanner-workbench/catalog", ("'/api/scanner-workbench/catalog'",)),
    (
        "validateScannerWorkbenchWatchIntent",
        "POST",
        "/api/scanner-workbench/watch-intent/validate",
        ("'/api/scanner-workbench/watch-intent/validate'", "method: 'POST'"),
    ),
    ("getMarkets", "GET", "/api/markets", ("'/api/markets'",)),
    ("runBacktest", "POST", "/api/backtest", ("'/api/backtest'", "method: 'POST'")),
    ("optimizeStrategy", "POST", "/api/backtest/optimize", ("'/api/backtest/optimize'", "method: 'POST'")),
    ("getDryRunStatus", "GET", "/api/dry-run/status", ("'/api/dry-run/status'",)),
    ("getSimulationLabStatus", "GET", "/api/simulation-lab/status", ("'/api/simulation-lab/status'",)),
    ("getNotificationsStatus", "GET", "/api/notifications/status", ("'/api/notifications/status'",)),
    ("validateConfig", "POST", "/api/config/validate", ("'/api/config/validate'", "method: 'POST'")),
    ("runSimulationLabOrbBacktest", "POST", "/api/simulation-lab/orb/backtest", ("'/api/simulation-lab/orb/backtest'", "method: 'POST'")),
    (
        "runSimulationLabBuyingPowerAllocation",
        "POST",
        "/api/simulation-lab/buying-power/allocation",
        ("'/api/simulation-lab/buying-power/allocation'", "method: 'POST'"),
    ),
    (
        "runSimulationLabStopTrailingDcaComparison",
        "POST",
        "/api/simulation-lab/stop-trailing-dca/compare",
        ("'/api/simulation-lab/stop-trailing-dca/compare'", "method: 'POST'"),
    ),
    ("evaluateSupportResistance", "POST", "/api/support-resistance/evaluate", ("'/api/support-resistance/evaluate'", "method: 'POST'")),
    ("pauseScheduler", "POST", "/api/control/pause", ("'/api/control/pause'", "method: 'POST'")),
    ("resumeScheduler", "POST", "/api/control/resume", ("'/api/control/resume'", "method: 'POST'")),
    ("toggleKillSwitch", "POST", "/api/emergency/kill-switch", ("`/api/emergency/kill-switch?state=${state}`", "method: 'POST'")),
    ("getKillSwitchStatus", "GET", "/api/emergency/kill-switch", ("'/api/emergency/kill-switch'",)),
    ("getAutomationStatus", "GET", "/api/automation", ("'/api/automation'",)),
    ("updateAutomationSettings", "PUT", "/api/automation", ("'/api/automation'", "method: 'PUT'")),
    ("updateTickerAutomation", "PUT", "/api/automation/tickers/{symbol}", ("`/api/automation/tickers/${encodeURIComponent(symbol)}`", "method: 'PUT'")),
    ("getCorrelation", "GET", "/api/correlation", ("'/api/correlation'",)),
    ("getDecisions", "GET", "/api/decisions", ("'/api/decisions'",)),
    (
        "enablePulseTrailingStop",
        "POST",
        "/api/pulse/trailing-stop/{symbol}",
        ("`/api/pulse/trailing-stop/${encodeURIComponent(symbol)}", "method: 'POST'"),
    ),
    (
        "sendPulseEmergencyExit",
        "POST",
        "/api/pulse/emergency-exit/{symbol}",
        ("`/api/pulse/emergency-exit/${encodeURIComponent(symbol)}", "method: 'POST'"),
    ),
]


def _frontend_api_source() -> str:
    return FRONTEND_API.read_text(encoding="utf-8")


def _api_client_method_names(source: str) -> set[str]:
    match = re.search(r"class ApiClient \{(?P<body>.*?)\n\}", source, re.DOTALL)
    if not match:
        raise AssertionError("Could not locate ApiClient class in frontend API client")
    return set(re.findall(r"^\s{2}(?:async\s+)?([a-z]\w+)\(", match.group("body"), re.MULTILINE))


class FrontendApiClientRouteContractTests(unittest.TestCase):
    def test_route_contract_covers_every_public_api_client_method(self):
        source = _frontend_api_source()
        expected_method_names = {contract[0] for contract in API_CLIENT_ROUTE_CONTRACTS}

        self.assertEqual(48, len(API_CLIENT_ROUTE_CONTRACTS))
        self.assertEqual(expected_method_names, _api_client_method_names(source))

    def test_frontend_source_keeps_expected_route_markers(self):
        source = _frontend_api_source()

        for client_name, method, route, markers in API_CLIENT_ROUTE_CONTRACTS:
            with self.subTest(client_name=client_name, method=method, route=route):
                self.assertIn(f"{client_name}(", source)
                for marker in markers:
                    self.assertIn(marker, source)

    def test_current_fastapi_app_registers_frontend_api_client_routes(self):
        from server import app

        paths = app.openapi()["paths"]

        for client_name, method, route, _markers in API_CLIENT_ROUTE_CONTRACTS:
            with self.subTest(client_name=client_name, method=method, route=route):
                self.assertIn(route, paths)
                self.assertIn(method.lower(), paths[route])


if __name__ == "__main__":
    unittest.main()
