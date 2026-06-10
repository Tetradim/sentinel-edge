import React, { useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Scale, Wallet } from 'lucide-react';

interface PulsePosition {
  symbol: string;
  quantity?: number;
  qty?: number;
  market_value?: number;
  unrealized_pnl?: number;
  realized_pnl?: number;
}

interface PulseAccount {
  status?: string;
  error?: string;
  equity?: number;
  total_equity?: number;
  buying_power?: number;
  available_balance?: number;
  positions?: PulsePosition[];
}

function numberOrZero(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function currency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function PortfolioAnalytics() {
  const [account, setAccount] = useState<PulseAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPortfolio();
    const interval = window.setInterval(fetchPortfolio, 10000);
    return () => window.clearInterval(interval);
  }, []);

  const fetchPortfolio = async () => {
    try {
      const response = await fetch('/api/pulse/account');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.status === 'unavailable' || data.error) {
        setAccount(null);
        setError(typeof data.error === 'string' ? data.error : 'Pulse portfolio data unavailable');
      } else {
        setAccount(data);
        setError(null);
      }
    } catch {
      setAccount(null);
      setError('Pulse portfolio data unavailable');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (error || !account) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center gap-3 text-gray-400">
          <Wallet className="w-5 h-5" />
          <span>Portfolio Analytics</span>
        </div>
        {error && (
          <p role="alert" className="text-red-300 mt-4 text-sm">
            {error}
          </p>
        )}
        <p className="text-gray-500 mt-4 text-sm">
          Live portfolio analytics require Sentinel Pulse account data. No generated portfolio data is displayed.
        </p>
      </div>
    );
  }

  const equity = numberOrZero(account.total_equity ?? account.equity);
  const buyingPower = numberOrZero(account.buying_power ?? account.available_balance);
  const positions = account.positions || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <Wallet className="w-4 h-4" />
            <span className="text-sm">Total Equity</span>
          </div>
          <p className="text-2xl font-bold text-white">{currency(equity)}</p>
        </div>

        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <Scale className="w-4 h-4" />
            <span className="text-sm">Buying Power</span>
          </div>
          <p className="text-2xl font-bold text-white">{currency(buyingPower)}</p>
        </div>

        <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-2">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm">Positions</span>
          </div>
          <p className="text-2xl font-bold text-white">{positions.length}</p>
        </div>
      </div>

      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">Open Positions</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-400 text-sm border-b border-gray-700">
                <th className="pb-3 font-medium">Symbol</th>
                <th className="pb-3 font-medium">Quantity</th>
                <th className="pb-3 font-medium">Market Value</th>
                <th className="pb-3 font-medium">Unrealized P&L</th>
                <th className="pb-3 font-medium">Realized P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => {
                const quantity = numberOrZero(position.quantity ?? position.qty);
                const unrealized = numberOrZero(position.unrealized_pnl);
                const realized = numberOrZero(position.realized_pnl);
                return (
                  <tr key={position.symbol} className="border-b border-gray-700/50 text-sm">
                    <td className="py-3 text-white font-medium">{position.symbol}</td>
                    <td className="py-3 text-gray-300">{quantity.toFixed(2)}</td>
                    <td className="py-3 text-gray-300">{currency(numberOrZero(position.market_value))}</td>
                    <td className={`py-3 ${unrealized >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {currency(unrealized)}
                    </td>
                    <td className={`py-3 ${realized >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {currency(realized)}
                    </td>
                  </tr>
                );
              })}
              {positions.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-gray-500">
                    No positions reported by Pulse
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
