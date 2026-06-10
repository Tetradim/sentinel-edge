import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Activity, DollarSign, Target, Settings, X, Trash2 } from 'lucide-react';

interface MetricToggles {
  orb: boolean;
  atr: boolean;
  signal: boolean;
  volume: boolean;
  price: boolean;
  breakouts: boolean;
}

interface TickerCardProps {
  symbol: string;
  enabled: boolean;
  currentPrice?: number;
  signalStrength?: number;
  trend?: string;
  orbHigh?: number;
  orbLow?: number;
  orbSessionLabel?: string;
  orbSessionStatus?: string;
  atr?: number;
  volumeRatio?: number;
  priceHistory?: Array<{ value: number }>;
  metricToggles?: MetricToggles;
  onToggle?: () => void;
  onConfigure?: () => void;
  onMetricToggle?: (metric: keyof MetricToggles) => void;
  onRemove?: () => void;
}

const defaultMetricToggles: MetricToggles = {
  orb: true,
  atr: true,
  signal: true,
  volume: true,
  price: true,
  breakouts: true,
};

function buildSparkline(history: Array<{ value: number }>, width: number, height: number): string {
  if (history.length < 2) return '';
  const values = history.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return history
    .map((d, i) => {
      const x = (i / (history.length - 1)) * width;
      const y = height - ((d.value - min) / range) * height * 0.85 - height * 0.05;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

export const TickerCard: React.FC<TickerCardProps> = ({
  symbol,
  enabled,
  currentPrice,
  signalStrength = 0,
  trend = 'neutral',
  orbHigh,
  orbLow,
  orbSessionLabel,
  orbSessionStatus,
  atr,
  volumeRatio,
  priceHistory = [],
  metricToggles = defaultMetricToggles,
  onToggle,
  onMetricToggle,
  onRemove,
}) => {
  const [showConfig, setShowConfig] = useState(false);

  const getTrendColor = () => {
    if (trend === 'bullish') return 'text-green-400';
    if (trend === 'bearish') return 'text-red-400';
    return 'text-gray-400';
  };

  const getTrendIcon = () => {
    if (trend === 'bullish') return <TrendingUp className="w-5 h-5" />;
    if (trend === 'bearish') return <TrendingDown className="w-5 h-5" />;
    return <Activity className="w-5 h-5" />;
  };

  const getSignalColor = () => {
    if (signalStrength >= 5) return 'from-green-500/30 to-green-600/10 border-green-500/50';
    if (signalStrength <= -5) return 'from-red-500/30 to-red-600/10 border-red-500/50';
    return 'from-gray-700/30 to-gray-800/10 border-gray-600/50';
  };

  const sparkColor =
    trend === 'bullish' ? '#22c55e' : trend === 'bearish' ? '#ef4444' : '#6b7280';

  const MetricToggle = ({
    label,
    metric,
    enabled: metricEnabled,
  }: {
    label: string;
    metric: keyof MetricToggles;
    enabled: boolean;
  }) => (
    <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-black/20 hover:bg-black/30 transition-all">
      <span className="text-sm text-gray-300">{label}</span>
      <button
        onClick={() => onMetricToggle?.(metric)}
        data-testid={`${symbol}-toggle-${metric}`}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors
          ${metricEnabled ? 'bg-green-500' : 'bg-gray-600'}`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform
            ${metricEnabled ? 'translate-x-6' : 'translate-x-1'}`}
        />
      </button>
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      data-testid="ticker-card"
      className={`relative overflow-hidden rounded-xl border backdrop-blur-sm
        bg-gradient-to-br ${getSignalColor()}
        shadow-lg hover:shadow-2xl transition-all duration-300
        ${!enabled && 'opacity-60'}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-2xl font-bold text-white">{symbol}</h3>
            <div
              className={`flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ${getTrendColor()} bg-black/30`}
            >
              {getTrendIcon()}
              <span className="capitalize">{trend}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConfig(!showConfig)}
              data-testid={`${symbol}-config-button`}
              className={`p-2 rounded-lg transition-all
                ${showConfig
                  ? 'bg-blue-500/30 text-blue-400'
                  : 'bg-gray-700/20 text-gray-400 hover:bg-gray-700/30'}`}
            >
              <Settings className="w-5 h-5" />
            </button>

            <button
              onClick={onToggle}
              data-testid={`${symbol}-toggle-button`}
              className={`px-4 py-2 rounded-lg font-medium transition-all
                ${enabled
                  ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                  : 'bg-gray-700/20 text-gray-400 hover:bg-gray-700/30'}`}
            >
              {enabled ? 'Active' : 'Paused'}
            </button>

            {onRemove && (
              <button
                onClick={onRemove}
                data-testid={`${symbol}-remove-button`}
                title={`Remove ${symbol}`}
                className="p-2 rounded-lg bg-red-500/10 text-red-400/60 hover:bg-red-500/20 hover:text-red-400 transition-all"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Configuration Panel */}
      <AnimatePresence>
        {showConfig && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden border-b border-gray-700/50 bg-gray-900/50"
          >
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-white">Prometheus Metrics</h4>
                <button
                  onClick={() => setShowConfig(false)}
                  className="text-gray-400 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <MetricToggle label="ORB Levels" metric="orb" enabled={metricToggles.orb} />
              <MetricToggle label="ATR (Volatility)" metric="atr" enabled={metricToggles.atr} />
              <MetricToggle label="Signal Strength" metric="signal" enabled={metricToggles.signal} />
              <MetricToggle label="Volume Ratio" metric="volume" enabled={metricToggles.volume} />
              <MetricToggle label="Price Tracking" metric="price" enabled={metricToggles.price} />
              <MetricToggle label="Breakout Detection" metric="breakouts" enabled={metricToggles.breakouts} />

              <div className="mt-4 pt-3 border-t border-gray-700/50">
                <p className="text-xs text-gray-500">
                  Toggle metrics to reduce Prometheus scrape load and focus on specific indicators.
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Price & Sparkline */}
      <div className="p-4">
        {metricToggles.price && currentPrice !== undefined && (
          <div className="flex items-baseline gap-2 mb-3">
            <DollarSign className="w-5 h-5 text-gray-400" />
            <span className="text-3xl font-bold text-white">{currentPrice.toFixed(2)}</span>
          </div>
        )}

        {metricToggles.price && priceHistory.length >= 2 && (
          <div className="h-16 mb-4">
            <svg
              viewBox="0 0 200 60"
              preserveAspectRatio="none"
              className="w-full h-full"
            >
              <path
                d={buildSparkline(priceHistory, 200, 60)}
                fill="none"
                stroke={sparkColor}
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
        )}

        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-3">
          {metricToggles.orb && orbHigh !== undefined && orbLow !== undefined && (
            <div className="bg-black/20 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Target className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-gray-400">ORB Range</span>
              </div>
              <p className="text-sm font-semibold text-white">
                ${orbLow.toFixed(2)} – ${orbHigh.toFixed(2)}
              </p>
              {(orbSessionLabel || orbSessionStatus) && (
                <p className="mt-1 text-[11px] text-gray-500">
                  <span>ORB Session</span>: {orbSessionLabel || 'Market open ORB'}
                  {orbSessionStatus ? ` / ${orbSessionStatus}` : ''}
                </p>
              )}
            </div>
          )}

          {metricToggles.atr && atr !== undefined && (
            <div className="bg-black/20 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="w-4 h-4 text-purple-400" />
                <span className="text-xs text-gray-400">ATR</span>
              </div>
              <p className="text-sm font-semibold text-white">${atr.toFixed(2)}</p>
            </div>
          )}

          {metricToggles.signal && (
            <div className="bg-black/20 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="w-4 h-4 text-yellow-400" />
                <span className="text-xs text-gray-400">Signal</span>
              </div>
              <p
                className={`text-sm font-semibold ${
                  signalStrength >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {signalStrength.toFixed(1)}
              </p>
            </div>
          )}

          {metricToggles.volume && volumeRatio !== undefined && (
            <div className="bg-black/20 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="w-4 h-4 text-cyan-400" />
                <span className="text-xs text-gray-400">Volume</span>
              </div>
              <p className="text-sm font-semibold text-white">{volumeRatio.toFixed(2)}x</p>
            </div>
          )}
        </div>

        {/* Metric count */}
        <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
          <div
            className={`w-2 h-2 rounded-full ${
              Object.values(metricToggles).filter(Boolean).length === 6
                ? 'bg-green-400'
                : 'bg-yellow-400'
            }`}
          />
          <span>
            {Object.values(metricToggles).filter(Boolean).length}/6 metrics active
          </span>
        </div>
      </div>

      {/* Glow edge */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-1/2 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
      </div>
    </motion.div>
  );
};
