import React from 'react';
import { TrendingUp, TrendingDown, Users, Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { CorrelationCluster } from '@/types';

interface Breadth {
  bullish: number;
  bearish: number;
  neutral: number;
  bullish_pct: number;
  bearish_pct: number;
  total: number;
}

interface CorrelationState {
  latest: CorrelationCluster | null;
  breadth: Breadth;
}

interface MarketBreadthProps {
  correlation: CorrelationState;
}

export const MarketBreadth: React.FC<MarketBreadthProps> = ({ correlation }) => {
  const latest = correlation.latest;
  const breadth = correlation.breadth;
  const hasSignals = breadth.total > 1 || breadth.bullish > 0 || breadth.bearish > 0;
  const recommendation = latest?.risk_recommendation;

  return (
    <div
      className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90
        to-gray-800/50 backdrop-blur-sm shadow-xl p-6"
      data-testid="market-breadth-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <Users className="w-5 h-5 text-violet-400" />
          <h3 className="text-lg font-semibold text-white">Market Breadth</h3>
        </div>
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded-full">
          Last 2 minutes
        </span>
      </div>

      {/* Latest cluster — prominent display */}
      <AnimatePresence mode="wait">
        {latest ? (
          <motion.div
            key={latest.timestamp}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            className={`mb-5 p-5 rounded-2xl flex items-center gap-4 border ${
              latest.direction === 'BULLISH'
                ? 'bg-emerald-500/10 border-emerald-500/30'
                : 'bg-red-500/10 border-red-500/30'
            }`}
            data-testid="correlation-cluster-alert"
          >
            {latest.direction === 'BULLISH' ? (
              <TrendingUp className="w-10 h-10 text-emerald-400 shrink-0" />
            ) : (
              <TrendingDown className="w-10 h-10 text-red-400 shrink-0" />
            )}

            <div className="flex-1 min-w-0">
              <p className={`text-2xl font-bold ${
                latest.direction === 'BULLISH' ? 'text-emerald-300' : 'text-red-300'
              }`}>
                {latest.count}-Symbol {latest.direction} Cluster
              </p>
              <p className="text-sm text-gray-400 mt-1 truncate">
                Strength:{' '}
                <span className="font-mono text-white">{latest.strength.toFixed(2)}</span>
                {' '}·{' '}
                {latest.symbols.slice(0, 5).join(', ')}
              </p>
              {recommendation && (
                <div className="mt-3 border-t border-gray-700/70 pt-3 text-xs text-gray-300">
                  <div className="mb-1 font-semibold text-white">Risk recommendation</div>
                  <p>{recommendation.operator_summary}</p>
                  <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div>
                      <dt className="text-gray-500">Action</dt>
                      <dd className="font-mono text-gray-100">{formatRecommendationAction(recommendation.action)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Trail</dt>
                      <dd className="font-mono text-gray-100">
                        {formatTrailingStopAction(recommendation.trailing_stop_action)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Scope</dt>
                      <dd className="font-mono text-gray-100">{formatRecommendationScope(recommendation.scope)}</dd>
                    </div>
                  </dl>
                </div>
              )}
            </div>

            {/* Strength ring */}
            <div className="relative w-14 h-14 shrink-0">
              <svg viewBox="0 0 56 56" className="w-full h-full -rotate-90">
                <circle cx="28" cy="28" r="22" fill="none" stroke="#374151" strokeWidth="4" />
                <circle
                  cx="28" cy="28" r="22"
                  fill="none"
                  stroke={latest.direction === 'BULLISH' ? '#10b981' : '#ef4444'}
                  strokeWidth="4"
                  strokeDasharray={`${2 * Math.PI * 22}`}
                  strokeDashoffset={`${2 * Math.PI * 22 * (1 - latest.strength)}`}
                  strokeLinecap="round"
                  className="transition-all duration-700"
                />
              </svg>
              <span className={`absolute inset-0 flex items-center justify-center text-xs
                font-bold ${latest.direction === 'BULLISH' ? 'text-emerald-400' : 'text-red-400'}`}>
                {Math.round(latest.strength * 100)}%
              </span>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="no-cluster"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-5 text-center py-6 text-gray-500"
            data-testid="no-cluster-placeholder"
          >
            <Activity className="w-8 h-8 mx-auto mb-2 text-gray-700" />
            <p className="text-sm">No significant correlation clusters detected</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Breadth bar */}
      {hasSignals ? (
        <div data-testid="breadth-bar" className="space-y-2">
          <div className="flex justify-between text-xs text-gray-400">
            <span className="text-green-400">
              {breadth.bullish_pct}% Bullish ({breadth.bullish})
            </span>
            <span className="text-gray-500">{breadth.neutral} Neutral</span>
            <span className="text-red-400">
              {breadth.bearish_pct}% Bearish ({breadth.bearish})
            </span>
          </div>
          <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-800">
            <div
              className="bg-green-500 transition-all duration-700"
              style={{ width: `${breadth.bullish_pct}%` }}
            />
            <div
              className="bg-gray-600 transition-all duration-700"
              style={{ width: `${100 - breadth.bullish_pct - breadth.bearish_pct}%` }}
            />
            <div
              className="bg-red-500 transition-all duration-700"
              style={{ width: `${breadth.bearish_pct}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-500 italic" data-testid="breadth-no-signals">
          No directional signals in current window — awaiting BUY / SELL events
        </p>
      )}
    </div>
  );
};

function formatRecommendationAction(action: string) {
  if (action === 'tighten_trailing_global') return 'Tighten trailing stops';
  if (action === 'review_trailing_stops') return 'Review trailing stops';
  if (action === 'observe_momentum') return 'Observe momentum';
  return action.replace(/_/g, ' ');
}

function formatTrailingStopAction(action: string) {
  if (action === 'tighten') return 'Tighten';
  if (action === 'review') return 'Review';
  if (action === 'maintain') return 'Maintain';
  return action.replace(/_/g, ' ');
}

function formatRecommendationScope(scope: string) {
  if (scope === 'cluster_symbols') return 'Cluster symbols';
  return scope.replace(/_/g, ' ');
}
