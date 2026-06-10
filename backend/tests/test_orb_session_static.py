"""Static checks for ORB session API, persistence, and UI visibility."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ORB = ROOT / "backend" / "orb.py"
SCHEDULER = ROOT / "backend" / "scheduler.py"
SERVER = ROOT / "backend" / "server.py"
TYPES = ROOT / "frontend" / "src" / "types" / "index.ts"
TRADING_OVERVIEW = ROOT / "frontend" / "src" / "components" / "dashboards" / "TradingOverview.tsx"
TICKER_CARD = ROOT / "frontend" / "src" / "components" / "cards" / "TickerCard.tsx"
DECISION_FEED = ROOT / "frontend" / "src" / "components" / "dashboards" / "DecisionFeed.tsx"


class ORBSessionStaticTests(unittest.TestCase):
    def test_orb_tracker_declares_premarket_and_market_open_sessions(self):
        text = ORB.read_text(encoding="utf-8")

        self.assertIn('PREMARKET_SESSION_ID = "premarket_30m"', text)
        self.assertIn('MARKET_OPEN_SESSION_ID = "market_open"', text)
        self.assertIn("ORBSession(", text)
        self.assertIn("timeframes=(30,)", text)
        self.assertIn("timeframes=(5, 15, 30)", text)
        self.assertIn("session_id: str = MARKET_OPEN_SESSION_ID", text)
        self.assertIn("def get_session_levels", text)
        self.assertIn("def get_session_status", text)
        self.assertIn("def get_decision_context", text)

    def test_scheduler_persists_session_keyed_orb_levels(self):
        text = SCHEDULER.read_text(encoding="utf-8")

        self.assertIn("sessions_doc: Dict[str, Dict] = {}", text)
        self.assertIn("for session_id, session_levels in self.orb.get_session_levels(symbol).items():", text)
        self.assertIn('"session_id": session_id', text)
        self.assertIn('"sessions": sessions_doc', text)
        self.assertIn('doc.get("sessions")', text)
        self.assertIn("orb_session_status", text)

    def test_scheduler_persists_and_hands_off_orb_decision_context(self):
        text = SCHEDULER.read_text(encoding="utf-8")

        self.assertIn("orb_decision_context = self.orb.get_decision_context(symbol, now=now)", text)
        self.assertIn('"orb_decision_context": orb_decision_context', text)
        self.assertIn('"decision_context": orb_decision_context', text)
        self.assertIn("orb_metadata = {", text)
        self.assertIn('"orb_decision_context": orb_decision_context', text)

    def test_orb_api_returns_sessions_alongside_legacy_levels(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("session_status = sched.orb.get_session_status(sym)", text)
        self.assertIn('"active_session": session_status["active_session"]', text)
        self.assertIn('"orb_sessions": session_status["sessions"]', text)
        self.assertIn('"orb_session_status": sched.orb.get_session_status(sym)', text)

    def test_trading_overview_surfaces_orb_session_status(self):
        types = TYPES.read_text(encoding="utf-8")
        overview = TRADING_OVERVIEW.read_text(encoding="utf-8")
        card = TICKER_CARD.read_text(encoding="utf-8")

        self.assertIn("orb_session_status?:", types)
        self.assertIn("orbSessionLabel={ticker.orb_session_status?.active_label}", overview)
        self.assertIn("orbSessionStatus={ticker.orb_session_status?.active_status}", overview)
        self.assertIn("orbSessionReadiness={ticker.orb_session_status?.active_readiness}", overview)
        self.assertIn("orbSessionLabel", card)
        self.assertIn("orbSessionStatus", card)
        self.assertIn("orbSessionReadiness", card)
        self.assertIn("ORB Session", card)
        self.assertIn("formatOrbReadiness", card)

    def test_frontend_surfaces_orb_decision_context(self):
        types = TYPES.read_text(encoding="utf-8")
        feed = DECISION_FEED.read_text(encoding="utf-8")

        self.assertIn("orb_decision_context?: OrbDecisionContext", types)
        self.assertIn("export interface OrbDecisionContext", types)
        self.assertIn("active_readiness", types)
        self.assertIn("active_ready", types)
        self.assertIn("signal_readiness", types)
        self.assertIn("ready_timeframes", types)
        self.assertIn("missing_timeframes", types)
        self.assertIn("formatOrbDecisionContext", feed)
        self.assertIn("formatOrbDecisionContext(entry.orb_decision_context)", feed)
        self.assertIn("context.signal_timeframe", feed)
        self.assertIn("context.signal_session", feed)
        self.assertIn("context.active_label", feed)
        self.assertIn("context.active_status", feed)
        self.assertIn("context.signal_readiness", feed)

    def test_chart_workspace_surfaces_orb_readiness(self):
        chart = (ROOT / "frontend" / "src" / "components" / "dashboards" / "ChartWorkspace.tsx").read_text(encoding="utf-8")

        self.assertIn('Metric label="ORB readiness"', chart)
        self.assertIn("formatOrbReadiness", chart)
        self.assertIn("session.ready_timeframes", chart)
        self.assertIn("session.missing_timeframes", chart)


if __name__ == "__main__":
    unittest.main()
