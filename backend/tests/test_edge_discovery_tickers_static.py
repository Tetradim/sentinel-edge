"""Static checks for Edge-only discovery ticker defaults."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_edge_default_tickers_include_discovery_symbols_without_pulse_preseed():
    text = (ROOT / "backend" / "scheduler.py").read_text(encoding="utf-8")
    start = text.index("DEFAULT_TICKERS =")
    end = text.index("EVAL_INTERVAL", start)
    default_segment = text[start:end]

    for symbol in ("LNR", "MU", "SNDK", "INTC", "IRDM", "VSAT", "FLY", "VPG"):
        assert f'"{symbol}"' in default_segment
