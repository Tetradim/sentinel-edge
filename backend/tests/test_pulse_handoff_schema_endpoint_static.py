"""Static checks for the Pulse handoff schema discovery endpoint."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
README = ROOT / "README.md"
SETTINGS = ROOT / "frontend" / "src" / "components" / "dashboards" / "SettingsDashboard.tsx"


class PulseHandoffSchemaEndpointStaticTests(unittest.TestCase):
    def test_server_exposes_pulse_handoff_schema_endpoint(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("pulse_handoff_contract_document", text)
        self.assertIn('@api_router.get("/pulse/handoff/schema")', text)
        self.assertIn("async def get_pulse_handoff_schema", text)
        self.assertIn("return pulse_handoff_contract_document()", text)

    def test_readme_documents_pulse_handoff_schema_endpoint(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("/api/pulse/handoff/schema", text)
        self.assertIn("edge.pulse.handoff.v1", text)

    def test_settings_dashboard_surfaces_pulse_handoff_contract(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("PulseHandoffContract", text)
        self.assertIn("pulseHandoffContract", text)
        self.assertIn("api.getPulseHandoffSchema()", text)
        self.assertIn("Pulse handoff contract", text)
        self.assertIn("PULSE_HANDOFF_ENDPOINT", text)
        self.assertIn("contract_version", text)
        self.assertIn("recommended_endpoint", text)
        self.assertIn("transport_headers", text)
        self.assertIn("Idempotency-Key", text)
        self.assertIn("response_contract", text)
        self.assertIn("field_semantics", text)
        self.assertIn("feedback_semantics", text)
        self.assertIn("accepted_response", text)
        self.assertIn("rejected_response", text)
        self.assertIn("failed_response", text)
        self.assertIn("Pulse field semantics", text)
        self.assertIn("known_edge_values", text)
        self.assertIn("known_orb_session_values", text)
        self.assertIn("formatPulseFieldSemanticsValue", text)
        self.assertIn("formatPulseContractLabel", text)
        self.assertIn("formatPulseContractBoolean", text)
        self.assertIn("Pulse feedback semantics", text)
        self.assertIn("expected_fields", text)
        self.assertIn("pulse_side_effect", text)
        self.assertIn("accepted/rejected/failed feedback semantics", README.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
