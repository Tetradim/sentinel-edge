import React, { useEffect, useState } from 'react';
import { DollarSign, TrendingDown, TrendingUp, Percent, RefreshCw } from 'lucide-react';
import { MetricCard } from '../cards/MetricCard';

interface PulseAccount {
  status?: string;
  error?: string;
  equity?: number;
  total_equity?: number;
  buying_power?: number;
  available_balance?: number;
  daily_pnl?: number;
  day_pnl?: number;
  realized_pnl_today?: number;
  daily_pnl_pct?: number;
  day_pnl_pct?: number;
  unrealized_pnl?: number;
  drawdown_pct?: number;
}

function numberOrZero(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function currency(value: number): string {
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export const PnLTracking: React.FC = () => {
  const [account, setAccount] = useState<PulseAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAccount();
    const interval = window.setInterval(loadAccount, 10000);
    return () => window.clearInterval(interval);
  }, []);

  const loadAccount = async () => {
    try {
      const response = await fetch('/api/pulse/account');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.status === 'unavailable' || data.error) {
        setAccount(null);
        setError(typeof data.error === 'string' ? data.error : 'Pulse account data unavailable');
      } else {
        setAccount(data);
        setError(null);
      }
    } catch {
      setAccount(null);
      setError('Pulse account data unavailable');
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
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700" data-testid="pnl-tracking">
        <div className="flex items-center gap-3 text-gray-400">
          <DollarSign className="w-5 h-5" />
          <span>P&L Tracking</span>
        </div>
        {error && (
          <p role="alert" className="text-red-300 mt-4 text-sm">
            {error}
          </p>
        )}
        <p className="text-gray-500 mt-4 text-sm">
          Live P&L requires Sentinel Pulse account data. No generated P&L data is displayed.
        </p>
      </div>
    );
  }

  const equity = numberOrZero(account.total_equity ?? account.equity);
  const buyingPower = numberOrZero(account.buying_power ?? account.available_balance);
  const dailyPnl = numberOrZero(account.daily_pnl ?? account.day_pnl ?? account.realized_pnl_today);
  const dailyPnlPct = numberOrZero(account.daily_pnl_pct ?? account.day_pnl_pct);
  const unrealizedPnl = numberOrZero(account.unrealized_pnl);
  const drawdownPct = numberOrZero(account.drawdown_pct);

  return (
    <div className="space-y-6" data-testid="pnl-tracking">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Equity"
          value={currency(equity)}
          subtitle="Pulse account"
          icon={DollarSign}
          color="blue"
        />
        <MetricCard
          title="Daily P&L"
          value={currency(dailyPnl)}
          subtitle={`${dailyPnlPct.toFixed(2)}% today`}
          icon={TrendingUp}
          color={dailyPnl >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          title="Unrealized P&L"
          value={currency(unrealizedPnl)}
          subtitle="Open positions"
          icon={TrendingDown}
          color={unrealizedPnl >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          title="Drawdown"
          value={`${drawdownPct.toFixed(2)}%`}
          subtitle={`Buying power ${currency(buyingPower)}`}
          icon={Percent}
          color={Math.abs(drawdownPct) > 5 ? 'red' : 'yellow'}
        />
      </div>
    </div>
  );
};
