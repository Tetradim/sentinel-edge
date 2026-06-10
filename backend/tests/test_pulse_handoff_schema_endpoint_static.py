"""Static checks for the Pulse handoff schema discovery endpoint."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
README = ROOT / "README.md"


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


if __name__ == "__main__":
    unittest.main()
