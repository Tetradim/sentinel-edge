"""Static architecture guard for the Edge/Pulse execution boundary."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

BROKER_CREDENTIAL_ENVS = {
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "TRADIER_ACCESS_TOKEN",
    "IBKR_ACCOUNT_ID",
    "INTERACTIVE_BROKERS_ACCOUNT_ID",
}

BROKER_ORDER_CALLS = {
    ".submit_order(",
    ".place_order(",
    ".market_order(",
    ".limit_order(",
    ".replace_order(",
}

BROKER_SDK_IMPORTS = {
    "alpaca_trade_api",
    "alpaca.trading",
    "ib_insync",
    "tradier",
}


def _production_python_files():
    for path in BACKEND.rglob("*.py"):
        parts = set(path.relative_to(BACKEND).parts)
        if "tests" in parts or "__pycache__" in parts:
            continue
        yield path


def test_edge_backend_does_not_read_broker_execution_credentials():
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        for env_name in BROKER_CREDENTIAL_ENVS:
            if env_name in text:
                offenders.append(f"{path.relative_to(ROOT)}:{env_name}")

    assert offenders == []


def test_edge_backend_does_not_import_broker_sdks_or_submit_orders():
    offenders = []
    for path in _production_python_files():
        text = path.read_text(encoding="utf-8")
        for token in BROKER_SDK_IMPORTS | BROKER_ORDER_CALLS:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}:{token}")

    assert offenders == []
