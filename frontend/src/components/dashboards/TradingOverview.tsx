import React, { useEffect, useState } from 'react';
import { Activity, TrendingUp, AlertCircle, Zap, Plus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { MetricCard } from '../cards/MetricCard';
import { TickerCard } from '../cards/TickerCard';
import { DecisionFeed } from './DecisionFeed';
import { MarketBreadth } from './MarketBreadth';
import { useStore } from '@/store/useStore';
import { api } from '@/lib/api';
import type { DecisionEntry } from '@/types';

const AddTickerForm: React.FC<{
  onAdd: (symbol: string) => Promise<void>;
  disabled?: boolean;
}> = ({ onAdd, disabled }) => {
  const [value, setValue] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const symbol = value.trim().toUpperCase();
    if (!symbol || !/^[A-Z]{1,6}$/.test(symbol)) {
      setError('Enter a valid symbol (1-6 letters)');
      return;
    }
    setError('');
    setAdding(true);
    try {
      await onAdd(symbol);
      setValue('');
    } catch {
      setError('Failed to add ticker');
    } finally {
      setAdding(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3" data-testid="add-ticker-form">
      <input
        type="text"
        value={value}
        onChange={(event) => {
          setValue(event.target.value.toUpperCase());
          setError('');
        }}
        placeholder="e.g. TSLA"
        maxLength={6}
        disabled={disabled || adding}
        data-testid="add-ticker-input"
        className="w-36 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-emerald-500 transition-colors disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || adding || !value.trim()}
        data-testid="add-ticker-button"
        className="flex items-center gap-1.5 px-4 py-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-sm font-medium hover:bg-emerald-500/30 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        <Plus className="w-4 h-4" />
        {adding ? 'Adding...' : 'Add'}
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </form>
  );
};

export const TradingOverview: React.FC = () => {
  const {
    tickers,
    stats,
    setTickers,
    removeTicker,
    setStats,
    correlation,
    setCorrelation,
  } = useStore();

  const [tickerConfigs, setTickerConfigs] = useState<Record<string, any>>({});
  const [decisions, setDecisions] = useState<DecisionEntry[]>([]);
  const [actionError, setActionError] = useState('');
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    loadData();
    const interval = window.setInterval(loadData, 5000);
    return () => window.clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [tickersRes, statsRes, corrRes, decsRes] = await Promise.allSettled([
        api.getTickers(),
        api.getStats(),
        api.getCorrelation(),
        api.getDecisions(),
      ]);
      const failedLoads = [tickersRes, statsRes, corrRes, decsRes].filter(
        (result) => result.status === 'rejected',
      );

      if (tickersRes.status === 'fulfilled') {
        const raw: any[] = tickersRes.value.tickers || [];
        setTickers(
          raw.map((ticker: any) => (
            typeof ticker === 'string' ? { symbol: ticker, enabled: true } : ticker
          )),
        );
      }

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value);
      }

      if (corrRes.status === 'fulfilled') {
        const data = corrRes.value;
        setCorrelation({
          latest: data.latest ?? null,
          breadth: data.breadth ?? correlation.breadth,
          clusters: data.clusters ?? [],
        });
      }

      if (decsRes.status === 'fulfilled') {
        setDecisions(decsRes.value.decisions || []);
      }

      if (failedLoads.length > 0) {
        setLoadError('Trading overview data failed to refresh. Showing latest available data.');
      } else {
        setLoadError('');
      }
    } catch (error) {
      console.error('Failed to load trading overview:', error);
      setLoadError('Trading overview data failed to refresh. Showing latest available data.');
    }
  };

  const handleAddTicker = async (symbol: string) => {
    setActionError('');
    await api.addTicker(symbol);
    await loadData();
  };

  const handleRemoveTicker = async (symbol: string) => {
    try {
      setActionError('');
      await api.removeTicker(symbol);
      removeTicker(symbol);
    } catch {
      setActionError(`Failed to remove ${symbol}`);
    }
  };

  const handleMetricToggle = async (symbol: string, metric: string) => {
    const current = tickerConfigs[symbol] || {
      orb: true,
      atr: true,
      signal: true,
      volume: true,
      price: true,
      breakouts: true,
    };
    const updated = { ...current, [metric]: !current[metric] };
    setTickerConfigs({ ...tickerConfigs, [symbol]: updated });
    try {
      setActionError('');
      await api.updateTickerConfig(symbol, { metrics: updated });
    } catch {
      // Keep local UI responsive; next poll will reconcile with backend state.
      setActionError(`Failed to update ${symbol} metrics`);
    }
  };

  const activeTickers = tickers.filter((ticker) => ticker.enabled);
  const avgSignalStrength =
    activeTickers.length > 0
      ? activeTickers.reduce((sum, ticker) => sum + (ticker.signal_strength || 0), 0) / activeTickers.length
      : 0;

  return (
    <div className="space-y-6" data-testid="trading-overview">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Active Tickers"
          value={activeTickers.length}
          subtitle="Currently monitored"
          icon={Activity}
          color="blue"
          trend="neutral"
        />
        <MetricCard
          title="Market Breadth"
          value={`${correlation.breadth.bullish_pct.toFixed(0)}%`}
          subtitle="Bullish symbols"
          icon={TrendingUp}
          color="green"
        />
        <MetricCard
          title="Avg Signal"
          value={avgSignalStrength.toFixed(1)}
          subtitle="Across all tickers"
          icon={Zap}
          color={avgSignalStrength >= 0 ? 'green' : 'red'}
        />
        <MetricCard
          title="System Status"
          value={stats?.running ? 'Running' : 'Stopped'}
          subtitle={stats?.paused ? 'Paused' : 'Active'}
          icon={AlertCircle}
          color={stats?.running ? 'green' : 'red'}
        />
      </div>

      {loadError && (
        <p role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {loadError}
        </p>
      )}

      <MarketBreadth correlation={correlation} />
      <DecisionFeed decisions={decisions} live />

      <div>
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h2 className="text-2xl font-bold text-white">Active Tickers</h2>
          <AddTickerForm onAdd={handleAddTicker} />
        </div>
        {actionError && <p className="mb-4 text-sm text-red-300">{actionError}</p>}

        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          <AnimatePresence>
            {activeTickers.map((ticker) => (
              <motion.div
                key={ticker.symbol}
                layout
                initial={{ opacity: 0, scale: 0.92 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.88, transition: { duration: 0.2 } }}
              >
                <TickerCard
                  symbol={ticker.symbol}
                  enabled={ticker.enabled}
                  currentPrice={ticker.current_price}
                  signalStrength={ticker.signal_strength}
                  trend={ticker.trend}
                  orbHigh={ticker.orb_levels?.['15m']?.high}
                  orbLow={ticker.orb_levels?.['15m']?.low}
                  atr={ticker.atr}
                  volumeRatio={ticker.volume_ratio}
                  metricToggles={tickerConfigs[ticker.symbol]}
                  onToggle={() => {}}
                  onConfigure={() => {}}
                  onMetricToggle={(metric) => handleMetricToggle(ticker.symbol, metric)}
                  onRemove={() => handleRemoveTicker(ticker.symbol)}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {activeTickers.length === 0 && (
          <div className="text-center py-12" data-testid="no-tickers-placeholder">
            <Activity className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">No active tickers</p>
            <p className="text-gray-500 text-sm">Use the input above to add a ticker</p>
          </div>
        )}
      </div>
    </div>
  );
};

export { TradingOverview as HealthDashboard };
