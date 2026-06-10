import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, TrendingUp, TrendingDown, Activity, AlertTriangle, Wifi } from 'lucide-react';
import { formatCompactAge } from '@/lib/time';
import type { DecisionEntry, OrbDecisionContext } from '@/types';

interface DecisionFeedProps {
  decisions: DecisionEntry[];
  live?: boolean;
}

const DECISION_STYLES: Record<string, { bg: string; text: string; label: string; Icon: any }> = {
  buy: {
    bg: 'bg-emerald-500/20 border-emerald-500/40',
    text: 'text-emerald-400',
    label: 'BUY',
    Icon: TrendingUp,
  },
  stop_buying: {
    bg: 'bg-red-500/20 border-red-500/40',
    text: 'text-red-400',
    label: 'STOP',
    Icon: TrendingDown,
  },
  enable_trailing_stop: {
    bg: 'bg-blue-500/20 border-blue-500/40',
    text: 'text-blue-400',
    label: 'TRAIL',
    Icon: Activity,
  },
  tighten_trailing_stop: {
    bg: 'bg-purple-500/20 border-purple-500/40',
    text: 'text-purple-400',
    label: 'TIGHTEN',
    Icon: Zap,
  },
  emergency_exit: {
    bg: 'bg-red-600/30 border-red-600/50',
    text: 'text-red-300',
    label: 'EXIT',
    Icon: AlertTriangle,
  },
};

export const DecisionFeed: React.FC<DecisionFeedProps> = ({ decisions, live = true }) => {
  return (
    <div
      className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50
        backdrop-blur-sm shadow-xl"
      data-testid="decision-feed"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
        <h3 className="text-lg font-semibold text-white">Decision Feed</h3>
        {live && (
          <div className="flex items-center gap-1.5 text-xs text-emerald-400">
            <Wifi className="w-3.5 h-3.5 animate-pulse" />
            <span>Live</span>
          </div>
        )}
      </div>

      {/* Feed */}
      <div className="overflow-y-auto" style={{ maxHeight: '280px' }}>
        {decisions.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500 text-sm">
            <Activity className="w-8 h-8 mx-auto mb-2 text-gray-700" />
            No decisions yet — waiting for market signals
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {decisions.map((entry, i) => {
              const style = DECISION_STYLES[entry.decision] ?? {
                bg: 'bg-gray-700/20 border-gray-700/40',
                text: 'text-gray-400',
                label: entry.decision.toUpperCase(),
                Icon: Activity,
              };
              const { Icon } = style;
              const signalColor =
                entry.signal_strength >= 2
                  ? 'text-emerald-400'
                  : entry.signal_strength <= -2
                  ? 'text-red-400'
                  : 'text-gray-400';
              const orbContextLabel = formatOrbDecisionContext(entry.orb_decision_context);

              return (
                <motion.div
                  key={`${entry.symbol}-${entry.timestamp}`}
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.25, delay: i * 0.03 }}
                  className="flex items-center gap-3 px-6 py-3 border-b border-gray-800/60
                    hover:bg-gray-800/30 transition-colors"
                  data-testid="decision-entry"
                >
                  {/* Symbol */}
                  <span className="w-12 text-sm font-bold text-white">{entry.symbol}</span>

                  {/* Decision badge */}
                  <div className="flex min-w-[82px] flex-col gap-1">
                    <div
                      className={`flex w-fit items-center gap-1 px-2 py-0.5 rounded-full border text-xs
                        font-semibold ${style.bg} ${style.text}`}
                    >
                      <Icon className="w-3 h-3" />
                      {style.label}
                    </div>
                    {orbContextLabel && (
                      <span className="max-w-[112px] truncate text-[10px] leading-none text-gray-500 whitespace-nowrap">
                        {orbContextLabel}
                      </span>
                    )}
                  </div>

                  {/* Signal bar */}
                  <div className="flex-1 flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          entry.signal_strength >= 0 ? 'bg-emerald-500' : 'bg-red-500'
                        }`}
                        style={{
                          width: `${Math.abs(entry.signal_strength) * 10}%`,
                          marginLeft: entry.signal_strength < 0 ? 'auto' : undefined,
                        }}
                      />
                    </div>
                    <span className={`text-xs font-mono w-10 text-right ${signalColor}`}>
                      {entry.signal_strength > 0 ? '+' : ''}
                      {entry.signal_strength.toFixed(1)}
                    </span>
                  </div>

                  {/* Price */}
                  <span className="text-xs text-gray-500 w-16 text-right font-mono">
                    ${entry.price.toFixed(2)}
                  </span>

                  {/* Time */}
                  <span className="text-xs text-gray-600 w-14 text-right">
                    {formatCompactAge(entry.timestamp)}
                  </span>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
};

function formatOrbDecisionContext(context?: OrbDecisionContext) {
  if (!context) return '';
  const sessionLabel = formatOrbSessionId(context.signal_session || context.active_session);
  const timeframe = context.signal_timeframe || '15m';
  const status = formatOrbSessionId(context.active_status);
  return `${context.active_label || sessionLabel} / ${sessionLabel} ${timeframe} / ${status}`;
}

function formatOrbSessionId(value?: string) {
  if (!value) return 'ORB';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}
