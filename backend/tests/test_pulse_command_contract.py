"""Tests for Pulse-produced Mongo command documents consumed by Edge."""
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.commands import command_from_dict  # noqa: E402


class PulseCommandContractTests(unittest.TestCase):
    def test_order_filled_accepts_pulse_document_fields(self):
        cmd = command_from_dict(
            {
                "command_type": "ORDER_FILLED",
                "timestamp": "2026-06-12T12:00:00+00:00",
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": 10,
                "price": 150.25,
                "total_value": 1502.5,
                "order_type": "market",
                "order_id": "ord-1",
                "execution_id": "exec-1",
                "avg_entry": 150.25,
                "position_qty": 10,
                "pnl": 0.0,
                "pnl_percent": 0.0,
                "trading_mode": "paper",
                "broker_id": "alpaca",
                "reason": "edge_handoff",
                "source": "pulse",
                "version": "1.0",
            }
        )

        self.assertEqual("ORDER_FILLED", cmd.command_type.value)
        self.assertEqual("AAPL", cmd.symbol)
        self.assertEqual(150.25, cmd.fill_price)
        self.assertEqual(0.0, cmd.pnl_realized)
        self.assertEqual("BUY", cmd.side)

    def test_position_update_accepts_pulse_document_fields(self):
        cmd = command_from_dict(
            {
                "command_type": "POSITION_UPDATE",
                "timestamp": "2026-06-12T12:00:00+00:00",
                "symbol": "AAPL",
                "quantity": 10,
                "avg_entry": 100.0,
                "current_price": 112.5,
                "market_value": 1125.0,
                "cost_basis": 1000.0,
                "unrealized_pnl": 125.0,
                "unrealized_pnl_percent": 12.5,
                "trading_mode": "paper",
                "broker_id": "alpaca",
                "source": "pulse",
                "version": "1.0",
            }
        )

        self.assertEqual("POSITION_UPDATE", cmd.command_type.value)
        self.assertEqual(10, cmd.position_size)
        self.assertEqual(100.0, cmd.entry_price)
        self.assertEqual(12.5, cmd.current_pnl_pct)
        self.assertEqual(125.0, cmd.current_pnl_dollar)

    def test_account_update_accepts_pulse_document_without_symbol(self):
        cmd = command_from_dict(
            {
                "command_type": "ACCOUNT_UPDATE",
                "timestamp": "2026-06-12T12:00:00+00:00",
                "account_balance": 5000.0,
                "allocated": 1250.0,
                "available": 3750.0,
                "cash_reserve": 500.0,
                "total_realized_pnl": 125.0,
                "total_unrealized_pnl": 75.0,
                "open_positions": 2,
                "positions": [{"symbol": "AAPL", "quantity": 10}],
                "trading_mode": "paper",
                "source": "pulse",
                "version": "1.0",
            }
        )

        self.assertEqual("ACCOUNT_UPDATE", cmd.command_type.value)
        self.assertEqual("ACCOUNT", cmd.symbol)
        self.assertEqual(3750.0, cmd.buying_power)
        self.assertEqual(5000.0, cmd.total_equity)
        self.assertEqual(125.0, cmd.day_pnl_dollar)


if __name__ == "__main__":
    unittest.main()
