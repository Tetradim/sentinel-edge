from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUS_ROUTES = ROOT / "backend" / "bot_event_bus_routes.py"
OPERATOR_FETCH = ROOT / "frontend" / "src" / "lib" / "operatorFetch.ts"
MAIN = ROOT / "frontend" / "src" / "main.tsx"
APP = ROOT / "frontend" / "src" / "App.tsx"
DRAWER = ROOT / "frontend" / "src" / "components" / "dashboards" / "AutomationOperationsDrawer.tsx"


def test_automation_operations_route_exposes_pending_and_data_freshness():
    route = BUS_ROUTES.read_text(encoding="utf-8")

    assert '@router.get("/automation-operations")' in route
    assert '"pending_commands": pending' in route
    assert '"execution_data": execution_data' in route
    assert "execution_data_status" in route
    assert "queue_stats" in route


def test_frontend_mutations_attach_operator_contract_headers():
    source = OPERATOR_FETCH.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")

    assert "X-Edge-Operator-Secret" in source
    assert "X-Edge-Live-Readiness-Signoff" in source
    assert "ENABLE LIVE AUTOMATION" in source
    assert "installOperatorFetch();" in main


def test_live_handoff_drawer_is_visible_from_every_shell_view():
    app = APP.read_text(encoding="utf-8")
    drawer = DRAWER.read_text(encoding="utf-8")

    assert "AutomationOperationsDrawer" in app
    assert "/api/bus/automation-operations" in drawer
    assert "Pending exactly-once commands" in drawer
    assert "Executable market data" in drawer
    assert "automation-operations-drawer" in drawer
