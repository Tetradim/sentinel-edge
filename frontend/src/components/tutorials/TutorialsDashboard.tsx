import React, { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, BookOpen, Bookmark, CheckCircle2, Circle, Clock, Download, LayoutGrid, List, Upload, X, Zap, Target, Shield, ShieldOff, ChevronRight, Lightbulb, Search, SlidersHorizontal } from 'lucide-react';

interface Tutorial {
  id: string;
  title: string;
  dashboard: string;
  icon: string;
  difficulty: 'Advanced' | 'Intermediate';
  color: 'blue' | 'emerald' | 'amber' | 'red' | 'purple';
  brief: string;
  significance: string;
  interpretation: string;
  keyInsight: string;
  bestPractices: string[];
}

interface LearningPath {
  id: string;
  title: string;
  summary: string;
  tutorialIds: string[];
}

export type TutorialModuleView = 'overview' | 'advisor' | 'experience' | 'protection' | 'pnl' | 'markets' | 'portfolio' | 'settings';
type TutorialSortOption = 'path' | 'title' | 'shortest' | 'longest' | 'incomplete' | 'saved' | 'notes';
type TutorialDisplayMode = 'detailed' | 'compact';
type TutorialReadingMode = 'standard' | 'comfortable' | 'large';
type TutorialProgressStatus = 'not-started' | 'in-progress' | 'complete';
type TutorialStatusFilter = 'all' | TutorialProgressStatus;
type TutorialFocusPreset = 'all' | 'resume' | 'saved' | 'notes' | 'complete';

interface TutorialModuleTarget {
  view: TutorialModuleView;
  label: string;
  reason: string;
}

interface TutorialsDashboardProps {
  onOpenModule?: (view: TutorialModuleView) => void;
}

const TUTORIALS: Tutorial[] = [
  {
    id: 'signal-engine',
    title: 'Signal Engine: 5-Layer Composite Scoring',
    dashboard: 'Live Trading',
    icon: 'zap',
    difficulty: 'Advanced',
    color: 'blue',
    brief: 'Understanding the ±10 composite signal that drives all trading decisions',
    significance: `The Signal Engine is the brain of Sentinel Edge. It combines 5 independent layers — ORB breakout proximity, ATR-normalized momentum, volume Z-score, trend alignment, and mean reversion signals — into a single score from -10 (strong sell) to +10 (strong buy). Each layer is weighted and can be toggled per-ticker via the Ticker Config panel. A score ≥ 5.0 in a bullish trend triggers a BUY decision, while ≤ -5.0 in bearish triggers STOP_BUYING. The composite nature means no single noisy indicator can dominate. Understanding which layers contribute most to current signals helps you tune weights and identify when the engine is acting on strong multi-factor confluence vs. a single strong signal.`,
    interpretation: `On the Live Trading dashboard, each ticker card shows the real-time signal_strength value. Values near 0 indicate indecision or conflicting signals across layers. Values ±3–5 represent moderate conviction. Values beyond ±7 indicate strong multi-layer agreement. Watch for divergence: if signal is +8 but trend shows 'neutral', the trend layer is fighting the other 4 layers, suggesting the score may be unstable. The decision feed shows how signal scores translate to actual decisions over time — look for patterns where scores oscillate around decision thresholds (3.0 and 5.0) causing rapid BUY/HOLD flipping, which indicates a ticker needs wider decision bands.`,
    keyInsight: 'Always look for confluence between signal strength and trend direction. Divergence often precedes a reversal.',
    bestPractices: [
      "Don't chase high signal scores — a sustained +6 is better than a spike to +9 that drops quickly.",
      "Use the Ticker Config to disable noisy layers for specific tickers. For example, volume Z-score may be unreliable for low-float stocks.",
      "Monitor the relationship between signal_strength and actual P&L. If high signals consistently produce losses, the engine parameters need recalibration.",
      "Use backtesting to validate signal threshold changes before applying them live.",
      "Consider disabling the signal layer entirely for highly correlated ticker pairs to avoid doubling down on the same market movement.",
    ],
  },
  {
    id: 'greeks-intro',
    title: 'Options Greeks: A Practical Framework',
    dashboard: 'Greeks Dashboard',
    icon: 'trending',
    difficulty: 'Intermediate',
    color: 'purple',
    brief: 'Understanding and using Delta, Theta, Vega, Gamma for better trades',
    significance: `The Greeks are mathematical sensitivities that quantify how option prices respond to changes in the underlying (Delta), time (Theta), volatility (Vega), and the rate of Delta change (Gamma). For long (buying) positions, your goals are: Delta high (strong directional exposure), Theta low (minimal daily decay), Vega positioned for your volatility view, Gamma high (leverage in your favor). Understanding which Greek drives your P&L helps you manage trades more actively. Enable Greek analysis in Settings first.`,
    interpretation: `The Greeks Dashboard shows all four Greeks with color-coded indicators. Green means favorable for buyers, red means unfavorable. Use the summary table to quickly check if your position goals align with current values. For example, if you're long calls and Theta shows red (high daily decay), you know time is working against you and should sell before decay accelerates.`,
    keyInsight: "Your P&L is the sum of all Greeks. Know which one you're betting on.",
    bestPractices: [
      "Before entering a position, decide which Greek is your primary driver.",
      "For directional bets without volatility view, prefer high Delta, low Theta, moderate Gamma.",
      "For volatile views, Vega exposure is your primary driver.",
      "Never ignore Theta when holding longer than a few days.",
      "High Gamma = high leverage both directions. It accelerates wins AND losses.",
    ],
  },
  {
    id: 'volatility-regimes',
    title: 'Volatility Regime Detection & Spike Protection',
    dashboard: 'Settings',
    icon: 'shield',
    difficulty: 'Advanced',
    color: 'amber',
    brief: 'Understanding market volatility regimes and protecting against IV spikes',
    significance: `Market volatility moves through regimes from suppressed (calm) to extreme (crisis). Sentinel Edge monitors IV percentiles against a 252-day historical window and can detect when IV spikes more than 50% above recent averages. This matters because option prices explode higher during volatility expansions. Enable IV tracking and spike protection in Settings under Advanced Options.`,
    interpretation: `Check the Greeks Dashboard for volatility regime indicators. The IV gauge shows current IV relative to historical percentiles — green (below 75th), yellow (75th-95th), red (above 95th). The spike warning appears as an alert. During elevated vol, consider taking profits on long options, rolling to later expirations, or reducing position size.`,
    keyInsight: 'IV regime changes often precede price regime changes. A vol spike can catalyze a directional move.',
    bestPractices: [
      "Enable IV percentile tracking in Settings to see historical IV context.",
      "When the gauge turns yellow, start taking profits on long options.",
      "Never hold into earnings with IV at 90th+ percentile — vega crush will decimate premiums.",
      "Use spike protection alerts as forced discipline to review positions.",
      "After a volatility spike, IV typically mean-reverts. Consider buying vol when extremely elevated.",
    ],
  },
  {
    id: 'orb-mechanics',
    title: 'Opening Range Breakout (ORB) Mechanics',
    dashboard: 'Ticker Config',
    icon: 'target',
    difficulty: 'Intermediate',
    color: 'emerald',
    brief: 'How ORB levels at 5m, 15m, and 30m timeframes anchor trading decisions',
    significance: `ORB is a foundational strategy where the high and low of the opening range (first N minutes of market open) define support and resistance levels. Sentinel Edge tracks three timeframes simultaneously — 5-minute (fast, tight range), 15-minute (standard), and 30-minute (wide, more reliable). Once the time window passes, the ORB level 'locks' and becomes a fixed reference. The range_width (high - low) indicates volatility at open — narrow ranges often precede large breakout moves. ORB levels are ET-anchored to US market hours (9:30 AM ET) and automatically reset each trading day. The ORB component feeds into the Signal Engine as a breakout proximity score.`,
    interpretation: `In the Ticker Config panel, the ORB toggle controls whether ORB data feeds the Signal Engine. When viewing ticker state, check if ORB levels are 'locked' — unlocked levels mean the time window is still forming and the range isn't final. A breakout occurs when price moves above ORB high (bullish) or below ORB low (bearish). False breakouts are common in the 5m timeframe but rarer at 30m. Compare the three timeframes: if all three show bullish breakout, it's a strong signal. If 5m shows breakout but 15m/30m don't, it's likely noise.`,
    keyInsight: 'The 15m ORB is generally the best balance of speed and reliability for most liquid stocks.',
    bestPractices: [
      "The 15m ORB is generally the best balance of speed and reliability for most liquid stocks.",
      "Disable ORB for after-hours or pre-market evaluation since the levels won't be meaningful.",
      "Use range_width as a volatility filter — if the opening range is unusually wide (>2x ATR), breakout signals may be less reliable.",
      "Pair ORB breakout signals with volume confirmation.",
      "For backtesting, test each ORB timeframe independently to see which performs best for your ticker universe.",
    ],
  },
  {
    id: 'risk-tuning',
    title: 'Risk Parameter Tuning Guide',
    dashboard: 'Backtesting',
    icon: 'shield',
    difficulty: 'Advanced',
    color: 'amber',
    brief: 'Optimizing max_consecutive_losses, max_drawdown, and trailing stop thresholds per ticker',
    significance: `Sentinel Edge's risk management operates at three levels: consecutive loss limits (momentum-based protection), drawdown percentage limits (capital preservation), and trailing stop profit thresholds (profit locking). These parameters directly control when the DecisionEngine overrides signal-based decisions with protective actions (EMERGENCY_EXIT, TIGHTEN_STOP). The defaults (3 consecutive losses, 10% max drawdown, 2% trailing threshold) are conservative baselines. Per-ticker overrides via the Ticker Config panel let you adapt risk profiles — volatile stocks like NVDA may need wider drawdown limits, while stable ETFs like SPY can use tighter stops. The relationship between these three parameters determines your strategy's risk/reward profile.`,
    interpretation: `Use the Backtesting dashboard to test parameter combinations. The key metrics to watch: (1) Win rate vs. max drawdown tradeoff — tighter stops increase win rate but may exit profitable trades early. (2) Monte Carlo probability of profit — this should be >60% for viable parameter sets. (3) The equity curve shape — smooth upward curves indicate good risk management, while sharp drops followed by recovery suggest the drawdown limit is set too high. Compare backtest results across different parameter sets for the same ticker and timeframe.`,
    keyInsight: 'Use Monte Carlo with ≥1000 simulations to validate that your parameter set is robust across different market conditions.',
    bestPractices: [
      "Start with backtesting: run the same symbol with 3, 5, and 7 consecutive loss limits and compare.",
      "Set max_drawdown_pct relative to the ticker's typical ATR — for high-ATR stocks, use 15-20%; for low-ATR, use 5-10%.",
      "The trailing stop threshold should be at least 2x the typical slippage + commission.",
      "Never set consecutive_losses below 2 — it causes excessive whipsawing.",
      "Use Monte Carlo with ≥1000 simulations to validate that your parameter set is robust across different market conditions, not just the specific historical period.",
    ],
  },
  {
    id: 'monte-carlo-lab',
    title: 'Monte Carlo Lab: Custom Runs & Saved Charts',
    dashboard: 'Ticker Config',
    icon: 'target',
    difficulty: 'Intermediate',
    color: 'blue',
    brief: 'Customize simulations, save chart datasets, and read tail-risk outputs after a backtest',
    significance: `Monte Carlo turns one backtest into a range of possible outcomes by reshuffling, bootstrapping, or modeling the trade-return sequence. In Sentinel Edge, the Monte Carlo Settings panel lets you choose the method, simulation count, confidence level, volatility multiplier, random seed, sample paths, histogram bins, and whether to create a Saved Chart Bundle. This is the user-facing bridge between a single historical result and the question that matters more: how fragile is this strategy if the next trade order is different?`,
    interpretation: `Open Ticker Config, adjust Monte Carlo Settings, then run a backtest. The results panel shows probability_of_profit, value_at_risk, conditional_value_at_risk, mean drawdown, ruin probability, and median final equity. Saved Chart Bundle lists downloadable chart datasets for the equity fan, final-equity histogram, drawdown distribution, and tail-risk summary. Use a random seed when you want reproducible comparisons between parameter changes; leave it blank when you want a fresh stress sample. Use block bootstrap when trade order matters because clustered wins and losses should stay partially intact.`,
    keyInsight: 'Saved charts make Monte Carlo comparable across runs; use the same random seed and chart bundle when judging one setting change at a time.',
    bestPractices: [
      "Start with 1000 simulations for quick feedback, then rerun promising settings at 5000+ before trusting the result.",
      "Use probability_of_profit with value_at_risk and conditional_value_at_risk; profit odds alone can hide severe downside tails.",
      "Turn on sample paths when you need visual intuition, but reduce sample path count if the chart feels crowded.",
      "Keep saved charts enabled for settings you may revisit, especially when comparing max_drawdown_pct or trailing-stop changes.",
      "Use block bootstrap for streaky strategies so consecutive wins and losses are not completely broken apart.",
    ],
  },
  {
    id: 'circuit-breaker',
    title: 'Circuit Breaker & Pulse Failover',
    dashboard: 'System Health',
    icon: 'shield-off',
    difficulty: 'Intermediate',
    color: 'red',
    brief: 'Understanding the circuit breaker pattern protecting broker communication',
    significance: `The PulseClient uses a circuit breaker pattern to protect against cascading failures when communicating with the Sentinel Pulse broker service. The circuit has three states: CLOSED (normal operation, requests flow through), OPEN (after 5 consecutive failures, all requests are blocked and queued for 60 seconds), and HALF_OPEN (after the 60s cooldown, a single probe request tests if Pulse is back). Failed decisions during OPEN state are automatically enqueued in the retry queue with priority ordering — EMERGENCY_EXIT has highest priority, followed by BUY, then HOLD. The circuit breaker prevents a single broker outage from cascading into system-wide failure.`,
    interpretation: `On the System Health dashboard, the Circuit Breaker panel shows the current state for each provider. Green = CLOSED (healthy), Yellow = HALF_OPEN (testing recovery), Red = OPEN (blocked). When the circuit is OPEN, you'll see queued decisions in the retry queue. The retry queue depth shows how many decisions are waiting. If you see frequent OPEN states, investigate the provider's API status page. The circuit breaker auto-recovers, but persistent failures may indicate a configuration issue.`,
    keyInsight: 'The retry queue preserves decision priority — EMERGENCY_EXIT decisions always get processed first after a broker recovers.',
    bestPractices: [
      "Monitor circuit breaker state changes — frequent transitions to OPEN suggest provider issues that need investigation.",
      "Use the retry queue depth as a leading indicator: growing depth means broker communication is degraded.",
      "When circuit opens, decisions are preserved but delayed. Check the decision feed for timing impact.",
      "The circuit breaker is automatic — you cannot manually override it, but you can switch primary providers in the Ticker Config.",
      "After a circuit transition to OPEN, expect 60-90 seconds of elevated latency as the retry queue drains.",
    ],
  },
];

const colorClasses = {
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', icon: 'text-blue-400' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', icon: 'text-emerald-400' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', icon: 'text-amber-400' },
  red: { bg: 'bg-red-500/10', border: 'border-red-500/30', text: 'text-red-400', icon: 'text-red-400' },
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', icon: 'text-purple-400' },
};

const difficultyColors = {
  Advanced: 'bg-purple-500/20 text-purple-400',
  Intermediate: 'bg-blue-500/20 text-blue-400',
};
const tutorialStatusMeta: Record<TutorialProgressStatus, { label: string; classes: string }> = {
  'not-started': {
    label: 'Not started',
    classes: 'bg-gray-700/50 text-gray-300',
  },
  'in-progress': {
    label: 'In progress',
    classes: 'bg-blue-500/20 text-blue-200',
  },
  complete: {
    label: 'Complete',
    classes: 'bg-emerald-500/20 text-emerald-300',
  },
};

const dashboardOptions = Array.from(new Set(TUTORIALS.map((tutorial) => tutorial.dashboard))).sort();
const difficultyOptions: Tutorial['difficulty'][] = ['Intermediate', 'Advanced'];
const statusFilterOptions: { value: TutorialStatusFilter; label: string }[] = [
  { value: 'all', label: 'All status' },
  { value: 'not-started', label: 'Not started' },
  { value: 'in-progress', label: 'In progress' },
  { value: 'complete', label: 'Complete' },
];
const sortOptions: { value: TutorialSortOption; label: string }[] = [
  { value: 'path', label: 'Path order' },
  { value: 'title', label: 'Title A-Z' },
  { value: 'shortest', label: 'Shortest first' },
  { value: 'longest', label: 'Longest first' },
  { value: 'incomplete', label: 'Incomplete first' },
  { value: 'saved', label: 'Saved first' },
  { value: 'notes', label: 'Notes first' },
];
const readingModeOptions: { value: TutorialReadingMode; label: string; description: string }[] = [
  { value: 'standard', label: 'Standard', description: 'Balanced spacing for dense review.' },
  { value: 'comfortable', label: 'Comfort', description: 'More room for longer explanations.' },
  { value: 'large', label: 'Large', description: 'Larger text for focused reading.' },
];
const readingModeClasses: Record<TutorialReadingMode, { panel: string; body: string; practice: string }> = {
  standard: {
    panel: 'p-6',
    body: 'text-base leading-relaxed text-gray-300',
    practice: 'text-base leading-relaxed text-gray-300',
  },
  comfortable: {
    panel: 'p-6 md:p-7',
    body: 'text-lg leading-8 text-gray-300',
    practice: 'text-base leading-8 text-gray-300',
  },
  large: {
    panel: 'p-6 md:p-8',
    body: 'text-xl leading-9 text-gray-200',
    practice: 'text-lg leading-8 text-gray-200',
  },
};
const READING_WORDS_PER_MINUTE = 225;
const LEARNING_CENTER_EXPORT_VERSION = 1;
const COMPLETED_TUTORIALS_STORAGE_KEY = 'sentinel-edge.learning-center.completed-tutorials';
const SAVED_TUTORIALS_STORAGE_KEY = 'sentinel-edge.learning-center.saved-tutorials';
const TUTORIAL_NOTES_STORAGE_KEY = 'sentinel-edge.learning-center.tutorial-notes';
const TUTORIAL_READING_MODE_STORAGE_KEY = 'sentinel-edge.learning-center.reading-mode';
const TUTORIAL_PRACTICE_CHECKS_STORAGE_KEY = 'sentinel-edge.learning-center.practice-checks';
const RECENT_TUTORIALS_STORAGE_KEY = 'sentinel-edge.learning-center.recent-tutorials';
const TUTORIAL_SECTION_LINKS = [
  { id: 'why-this-matters', label: 'Why This Matters' },
  { id: 'reading-the-dashboard', label: 'Reading the Dashboard' },
  { id: 'best-practices', label: 'Best Practices' },
];
const LEARNING_PATHS: LearningPath[] = [
  {
    id: 'all-guides',
    title: 'All Guides',
    summary: 'Search across every Learning Center guide without narrowing to a recommended path.',
    tutorialIds: TUTORIALS.map((tutorial) => tutorial.id),
  },
  {
    id: 'strategy-builder',
    title: 'Strategy Builder',
    summary: 'Build from signals to ORB mechanics, risk tuning, and Monte Carlo validation.',
    tutorialIds: ['signal-engine', 'orb-mechanics', 'risk-tuning', 'monte-carlo-lab'],
  },
  {
    id: 'risk-control',
    title: 'Risk Control',
    summary: 'Focus on drawdowns, tail risk, saved simulations, and system failover behavior.',
    tutorialIds: ['risk-tuning', 'monte-carlo-lab', 'circuit-breaker'],
  },
  {
    id: 'options-readiness',
    title: 'Options Readiness',
    summary: 'Understand Greeks, volatility regimes, and how those inputs shape option risk.',
    tutorialIds: ['greeks-intro', 'volatility-regimes', 'risk-tuning'],
  },
];

const tutorialModuleTargets: Record<string, TutorialModuleTarget> = {
  'Live Trading': {
    view: 'overview',
    label: 'Trading Overview',
    reason: 'Review live signal context after reading this guide.',
  },
  'Greeks Dashboard': {
    view: 'portfolio',
    label: 'Portfolio',
    reason: 'Compare options exposure and position context.',
  },
  Settings: {
    view: 'settings',
    label: 'System Settings',
    reason: 'Adjust the feature toggles and thresholds described here.',
  },
  'Ticker Config': {
    view: 'settings',
    label: 'System Settings',
    reason: 'Tune ticker-level inputs and simulation settings.',
  },
  Backtesting: {
    view: 'pnl',
    label: 'P&L Tracking',
    reason: 'Compare backtest outcomes against realized performance.',
  },
  'System Health': {
    view: 'advisor',
    label: 'Advisor Health',
    reason: 'Check service state and recovery signals.',
  },
};

const sanitizeTutorialIds = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];

  const knownTutorialIds = new Set(TUTORIALS.map((tutorial) => tutorial.id));
  return value.filter((id): id is string => typeof id === 'string' && knownTutorialIds.has(id));
};

const sanitizeTutorialNotes = (value: unknown): Record<string, string> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};

  const knownTutorialIds = new Set(TUTORIALS.map((tutorial) => tutorial.id));
  return Object.fromEntries(
    Object.entries(value).filter(([id, note]) => knownTutorialIds.has(id) && typeof note === 'string'),
  ) as Record<string, string>;
};

const sanitizeTutorialPracticeChecks = (value: unknown): Record<string, number[]> => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};

  const entries = Object.entries(value).flatMap(([tutorialId, checks]) => {
    const tutorial = TUTORIALS.find((item) => item.id === tutorialId);
    if (!tutorial || !Array.isArray(checks)) return [];

    const validChecks = Array.from(new Set(checks)).filter(
      (index): index is number => Number.isInteger(index) && index >= 0 && index < tutorial.bestPractices.length,
    );

    return validChecks.length > 0 ? [[tutorialId, validChecks] as const] : [];
  });

  return Object.fromEntries(entries);
};

const sanitizeTutorialReadingMode = (value: unknown): TutorialReadingMode => {
  return readingModeOptions.some((option) => option.value === value) ? value as TutorialReadingMode : 'standard';
};

const loadCompletedTutorialIds = (): string[] => {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(COMPLETED_TUTORIALS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return sanitizeTutorialIds(parsed);
  } catch {
    return [];
  }
};

const loadSavedTutorialIds = (): string[] => {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(SAVED_TUTORIALS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return sanitizeTutorialIds(parsed);
  } catch {
    return [];
  }
};

const loadRecentTutorialIds = (): string[] => {
  if (typeof window === 'undefined') return [];

  try {
    const raw = window.localStorage.getItem(RECENT_TUTORIALS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return sanitizeTutorialIds(parsed).slice(0, 5);
  } catch {
    return [];
  }
};

const loadTutorialNotes = (): Record<string, string> => {
  if (typeof window === 'undefined') return {};

  try {
    const raw = window.localStorage.getItem(TUTORIAL_NOTES_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return sanitizeTutorialNotes(parsed);
  } catch {
    return {};
  }
};

const loadTutorialReadingMode = (): TutorialReadingMode => {
  if (typeof window === 'undefined') return 'standard';

  try {
    return sanitizeTutorialReadingMode(window.localStorage.getItem(TUTORIAL_READING_MODE_STORAGE_KEY));
  } catch {
    return 'standard';
  }
};

const loadTutorialPracticeChecks = (): Record<string, number[]> => {
  if (typeof window === 'undefined') return {};

  try {
    const raw = window.localStorage.getItem(TUTORIAL_PRACTICE_CHECKS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return sanitizeTutorialPracticeChecks(parsed);
  } catch {
    return {};
  }
};

const persistTutorialState = (key: string, value: string, onFailure: (message: string) => void) => {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.error('Failed to persist tutorial state:', error);
    onFailure('Learning progress could not be saved in this browser.');
  }
};

const getTutorialWordCount = (tutorial: Tutorial): number => {
  const text = [
    tutorial.title,
    tutorial.brief,
    tutorial.significance,
    tutorial.interpretation,
    tutorial.keyInsight,
    tutorial.bestPractices.join(' '),
  ].join(' ');

  return text.trim().split(/\s+/).filter(Boolean).length;
};

const getTutorialReadTimeMinutes = (tutorial: Tutorial): number => {
  return Math.max(1, Math.ceil(getTutorialWordCount(tutorial) / READING_WORDS_PER_MINUTE));
};

const getLearningPathReadTime = (tutorials: Tutorial[]): number => {
  return tutorials.reduce((total, tutorial) => total + getTutorialReadTimeMinutes(tutorial), 0);
};

const getLearningPathProgress = (
  tutorials: Tutorial[],
  completedTutorialSet: Set<string>,
): { completed: number; total: number; percent: number; remainingMinutes: number } => {
  const completed = tutorials.filter((tutorial) => completedTutorialSet.has(tutorial.id)).length;
  const remainingMinutes = tutorials
    .filter((tutorial) => !completedTutorialSet.has(tutorial.id))
    .reduce((total, tutorial) => total + getTutorialReadTimeMinutes(tutorial), 0);

  return {
    completed,
    total: tutorials.length,
    percent: tutorials.length > 0 ? Math.round((completed / tutorials.length) * 100) : 0,
    remainingMinutes,
  };
};

const escapeRegExp = (value: string): string => {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

const getSearchHighlightParts = (text: string, query: string): { text: string; highlight: boolean }[] => {
  const terms = Array.from(new Set(query.trim().split(/\s+/).filter(Boolean)));
  if (terms.length === 0) return [{ text, highlight: false }];

  const matcher = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi');
  const queryTerms = new Set(terms.map((term) => term.toLowerCase()));

  return text
    .split(matcher)
    .filter(Boolean)
    .map((part) => ({
      text: part,
      highlight: queryTerms.has(part.toLowerCase()),
    }));
};

const renderHighlightedText = (text: string, query: string): React.ReactNode => {
  return getSearchHighlightParts(text, query).map((part, index) => (
    part.highlight ? (
      <mark key={`${part.text}-${index}`} className="rounded bg-yellow-400/20 px-0.5 text-yellow-100">
        {part.text}
      </mark>
    ) : (
      <React.Fragment key={`${part.text}-${index}`}>{part.text}</React.Fragment>
    )
  ));
};

const getTutorialActionProgress = (
  tutorial: Tutorial,
  tutorialPracticeChecks: Record<string, number[]>,
): { checked: number; total: number; percent: number } => {
  const checked = sanitizeTutorialPracticeChecks({ [tutorial.id]: tutorialPracticeChecks[tutorial.id] })[tutorial.id]?.length || 0;
  const total = tutorial.bestPractices.length;

  return {
    checked,
    total,
    percent: Math.round((checked / total) * 100),
  };
};

const getIcon = (iconName: string, className: string) => {
  switch (iconName) {
    case 'zap': return <Zap className={className} />;
    case 'target': return <Target className={className} />;
    case 'shield': return <Shield className={className} />;
    case 'shield-off': return <ShieldOff className={className} />;
    default: return <BookOpen className={className} />;
  }
};

export const TutorialsDashboard: React.FC<TutorialsDashboardProps> = ({ onOpenModule }) => {
  const learningStateFileInputRef = useRef<HTMLInputElement>(null);
  const [expandedTutorial, setExpandedTutorial] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDashboard, setSelectedDashboard] = useState('All');
  const [selectedDifficulty, setSelectedDifficulty] = useState<'All' | Tutorial['difficulty']>('All');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<TutorialStatusFilter>('all');
  const [selectedSort, setSelectedSort] = useState<TutorialSortOption>('path');
  const [selectedDisplayMode, setSelectedDisplayMode] = useState<TutorialDisplayMode>('detailed');
  const [showIncompleteOnly, setShowIncompleteOnly] = useState(false);
  const [showSavedOnly, setShowSavedOnly] = useState(false);
  const [showNotesOnly, setShowNotesOnly] = useState(false);
  const [completedTutorialIds, setCompletedTutorialIds] = useState<string[]>(loadCompletedTutorialIds);
  const [savedTutorialIds, setSavedTutorialIds] = useState<string[]>(loadSavedTutorialIds);
  const [recentTutorialIds, setRecentTutorialIds] = useState<string[]>(loadRecentTutorialIds);
  const [tutorialNotes, setTutorialNotes] = useState<Record<string, string>>(loadTutorialNotes);
  const [selectedReadingMode, setSelectedReadingMode] = useState<TutorialReadingMode>(loadTutorialReadingMode);
  const [tutorialPracticeChecks, setTutorialPracticeChecks] = useState<Record<string, number[]>>(loadTutorialPracticeChecks);
  const [selectedLearningPath, setSelectedLearningPath] = useState(LEARNING_PATHS[0].id);
  const [importStatus, setImportStatus] = useState('');
  const [persistenceStatus, setPersistenceStatus] = useState('');

  const expanded = TUTORIALS.find(t => t.id === expandedTutorial);
  const activeLearningPath = LEARNING_PATHS.find((path) => path.id === selectedLearningPath) || LEARNING_PATHS[0];
  const activePathTutorials = activeLearningPath.tutorialIds
    .map((tutorialId) => TUTORIALS.find((tutorial) => tutorial.id === tutorialId))
    .filter((tutorial): tutorial is Tutorial => Boolean(tutorial));
  const activePathReadTime = getLearningPathReadTime(activePathTutorials);
  const completedTutorialSet = new Set(completedTutorialIds);
  const activePathProgress = getLearningPathProgress(activePathTutorials, completedTutorialSet);
  const savedTutorialSet = new Set(savedTutorialIds);
  const recentTutorials = recentTutorialIds
    .map((tutorialId) => TUTORIALS.find((tutorial) => tutorial.id === tutorialId))
    .filter((tutorial): tutorial is Tutorial => Boolean(tutorial));
  const completedCount = completedTutorialIds.length;
  const savedCount = savedTutorialIds.length;
  const notesCount = Object.values(tutorialNotes).filter((note) => note.trim().length > 0).length;
  const completionPercent = Math.round((completedCount / TUTORIALS.length) * 100);
  const recommendedTutorial = activePathTutorials.find((tutorial) => !completedTutorialSet.has(tutorial.id)) || activePathTutorials[0];
  const totalPracticeActions = TUTORIALS.reduce((total, tutorial) => total + tutorial.bestPractices.length, 0);
  const checkedPracticeActionCount = TUTORIALS.reduce((total, tutorial) => {
    return total + getTutorialActionProgress(tutorial, tutorialPracticeChecks).checked;
  }, 0);
  const practiceActionPercent = Math.round((checkedPracticeActionCount / totalPracticeActions) * 100);
  const nextPracticeTutorial = activePathTutorials.find((tutorial) => {
    const checks = tutorialPracticeChecks[tutorial.id] || [];
    return checks.length < tutorial.bestPractices.length;
  }) || recommendedTutorial;
  const highlightQuery = searchQuery.trim();
  const getTutorialProgressStatus = (tutorial: Tutorial): TutorialProgressStatus => {
    if (completedTutorialSet.has(tutorial.id)) return 'complete';

    const checkedActions = tutorialPracticeChecks[tutorial.id] || [];
    const hasNote = Boolean(tutorialNotes[tutorial.id]?.trim());
    if (checkedActions.length > 0 || hasNote) return 'in-progress';

    return 'not-started';
  };
  const resumeGuideCount = TUTORIALS.filter((tutorial) => getTutorialProgressStatus(tutorial) === 'in-progress').length;
  const quickFocusOptions: { id: TutorialFocusPreset; label: string; count: number; description: string }[] = [
    { id: 'all', label: 'All guides', count: TUTORIALS.length, description: 'Show every guide in the Learning Center.' },
    { id: 'resume', label: 'Resume', count: resumeGuideCount, description: 'Guides with notes or checked actions.' },
    { id: 'saved', label: 'Saved', count: savedCount, description: 'Guides saved for later review.' },
    { id: 'notes', label: 'Notes', count: notesCount, description: 'Guides where you wrote notes.' },
    { id: 'complete', label: 'Complete', count: completedCount, description: 'Guides marked complete.' },
  ];
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredTutorials = TUTORIALS.filter((tutorial) => {
    const searchableText = [
      tutorial.title,
      tutorial.dashboard,
      tutorial.brief,
      tutorial.significance,
      tutorial.interpretation,
      tutorial.keyInsight,
      tutorial.bestPractices.join(' '),
    ].join(' ').toLowerCase();

    const matchesSearch = normalizedQuery.length === 0 || searchableText.includes(normalizedQuery);
    const matchesDashboard = selectedDashboard === 'All' || tutorial.dashboard === selectedDashboard;
    const matchesDifficulty = selectedDifficulty === 'All' || tutorial.difficulty === selectedDifficulty;
    const matchesCompletion = !showIncompleteOnly || !completedTutorialSet.has(tutorial.id);
    const matchesSaved = !showSavedOnly || savedTutorialSet.has(tutorial.id);
    const matchesNotes = !showNotesOnly || Boolean(tutorialNotes[tutorial.id]?.trim());
    const matchesLearningPath = activeLearningPath.tutorialIds.includes(tutorial.id);
    const matchesStatus = selectedStatusFilter === 'all' || getTutorialProgressStatus(tutorial) === selectedStatusFilter;

    return matchesSearch && matchesDashboard && matchesDifficulty && matchesCompletion && matchesSaved && matchesNotes && matchesLearningPath && matchesStatus;
  });
  const sortedTutorials = [...filteredTutorials].sort((a, b) => {
    const pathOrder = activeLearningPath.tutorialIds.indexOf(a.id) - activeLearningPath.tutorialIds.indexOf(b.id);

    if (selectedSort === 'title') {
      return a.title.localeCompare(b.title);
    }
    if (selectedSort === 'shortest') {
      return getTutorialReadTimeMinutes(a) - getTutorialReadTimeMinutes(b) || pathOrder;
    }
    if (selectedSort === 'longest') {
      return getTutorialReadTimeMinutes(b) - getTutorialReadTimeMinutes(a) || pathOrder;
    }
    if (selectedSort === 'incomplete') {
      return Number(completedTutorialSet.has(a.id)) - Number(completedTutorialSet.has(b.id)) || pathOrder;
    }
    if (selectedSort === 'saved') {
      return Number(savedTutorialSet.has(b.id)) - Number(savedTutorialSet.has(a.id)) || pathOrder;
    }
    if (selectedSort === 'notes') {
      return Number(Boolean(tutorialNotes[b.id]?.trim())) - Number(Boolean(tutorialNotes[a.id]?.trim())) || pathOrder;
    }

    return pathOrder;
  });
  const activeFilterChips = [
    normalizedQuery ? { id: 'search', label: `Search: ${searchQuery.trim()}`, onClear: () => setSearchQuery('') } : null,
    activeLearningPath.id !== 'all-guides' ? { id: 'path', label: `Path: ${activeLearningPath.title}`, onClear: () => setSelectedLearningPath('all-guides') } : null,
    selectedDashboard !== 'All' ? { id: 'dashboard', label: `Dashboard: ${selectedDashboard}`, onClear: () => setSelectedDashboard('All') } : null,
    selectedDifficulty !== 'All' ? { id: 'difficulty', label: `Difficulty: ${selectedDifficulty}`, onClear: () => setSelectedDifficulty('All') } : null,
    selectedStatusFilter !== 'all' ? { id: 'status', label: `Status: ${tutorialStatusMeta[selectedStatusFilter].label}`, onClear: () => setSelectedStatusFilter('all') } : null,
    showIncompleteOnly ? { id: 'incomplete', label: 'Incomplete only', onClear: () => setShowIncompleteOnly(false) } : null,
    showSavedOnly ? { id: 'saved', label: 'Saved only', onClear: () => setShowSavedOnly(false) } : null,
    showNotesOnly ? { id: 'notes', label: 'Notes only', onClear: () => setShowNotesOnly(false) } : null,
  ].filter((chip): chip is { id: string; label: string; onClear: () => void } => Boolean(chip));

  useEffect(() => {
    persistTutorialState(COMPLETED_TUTORIALS_STORAGE_KEY, JSON.stringify(completedTutorialIds), setPersistenceStatus);
  }, [completedTutorialIds]);

  useEffect(() => {
    persistTutorialState(SAVED_TUTORIALS_STORAGE_KEY, JSON.stringify(savedTutorialIds), setPersistenceStatus);
  }, [savedTutorialIds]);

  useEffect(() => {
    persistTutorialState(RECENT_TUTORIALS_STORAGE_KEY, JSON.stringify(recentTutorialIds), setPersistenceStatus);
  }, [recentTutorialIds]);

  useEffect(() => {
    if (!expandedTutorial) return;

    setRecentTutorialIds((current) => [
      expandedTutorial,
      ...current.filter((tutorialId) => tutorialId !== expandedTutorial),
    ].slice(0, 5));
  }, [expandedTutorial]);

  useEffect(() => {
    persistTutorialState(TUTORIAL_NOTES_STORAGE_KEY, JSON.stringify(tutorialNotes), setPersistenceStatus);
  }, [tutorialNotes]);

  useEffect(() => {
    persistTutorialState(TUTORIAL_READING_MODE_STORAGE_KEY, selectedReadingMode, setPersistenceStatus);
  }, [selectedReadingMode]);

  useEffect(() => {
    persistTutorialState(TUTORIAL_PRACTICE_CHECKS_STORAGE_KEY, JSON.stringify(tutorialPracticeChecks), setPersistenceStatus);
  }, [tutorialPracticeChecks]);

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedDashboard('All');
    setSelectedDifficulty('All');
    setSelectedStatusFilter('all');
    setShowIncompleteOnly(false);
    setShowSavedOnly(false);
    setShowNotesOnly(false);
  };

  const applyTutorialFocusPreset = (preset: TutorialFocusPreset) => {
    setSearchQuery('');
    setSelectedDashboard('All');
    setSelectedDifficulty('All');
    setSelectedLearningPath('all-guides');
    setShowIncompleteOnly(false);
    setShowSavedOnly(false);
    setShowNotesOnly(false);

    if (preset === 'resume') {
      setSelectedStatusFilter('in-progress');
      setSelectedSort('incomplete');
      return;
    }

    if (preset === 'saved') {
      setSelectedStatusFilter('all');
      setSelectedSort('saved');
      setShowSavedOnly(true);
      return;
    }

    if (preset === 'notes') {
      setSelectedStatusFilter('all');
      setSelectedSort('notes');
      setShowNotesOnly(true);
      return;
    }

    if (preset === 'complete') {
      setSelectedStatusFilter('complete');
      setSelectedSort('path');
      return;
    }

    setSelectedStatusFilter('all');
    setSelectedSort('path');
  };

  const clearSearchOnly = () => {
    setSearchQuery('');
  };

  const toggleTutorialCompletion = (tutorialId: string) => {
    setCompletedTutorialIds((current) => {
      if (current.includes(tutorialId)) {
        return current.filter((id) => id !== tutorialId);
      }

      return [...current, tutorialId];
    });
  };

  const toggleSavedTutorial = (tutorialId: string) => {
    setSavedTutorialIds((current) => {
      if (current.includes(tutorialId)) {
        return current.filter((id) => id !== tutorialId);
      }

      return [...current, tutorialId];
    });
  };

  const updateTutorialNote = (tutorialId: string, note: string) => {
    setTutorialNotes((current) => ({ ...current, [tutorialId]: note }));
  };

  const toggleTutorialPracticeCheck = (tutorialId: string, practiceIndex: number) => {
    setTutorialPracticeChecks((current) => {
      const checks = new Set(current[tutorialId] || []);
      if (checks.has(practiceIndex)) {
        checks.delete(practiceIndex);
      } else {
        checks.add(practiceIndex);
      }

      return { ...current, [tutorialId]: Array.from(checks).sort((a, b) => a - b) };
    });
  };

  const completeTutorialPracticeChecklist = (tutorial: Tutorial) => {
    setTutorialPracticeChecks((current) => ({
      ...current,
      [tutorial.id]: tutorial.bestPractices.map((_, index) => index),
    }));
  };

  const clearTutorialPracticeChecklist = (tutorialId: string) => {
    setTutorialPracticeChecks((current) => ({ ...current, [tutorialId]: [] }));
  };

  const exportLearningCenterState = () => {
    const exportPayload = {
      version: LEARNING_CENTER_EXPORT_VERSION,
      exportedAt: new Date().toISOString(),
      completedTutorialIds,
      savedTutorialIds,
      recentTutorialIds,
      tutorialNotes,
      selectedReadingMode,
      tutorialPracticeChecks,
    };
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `sentinel-edge-learning-center-state-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setImportStatus('Learning data export ready.');
  };

  const importLearningCenterState = async (file: File | null) => {
    if (!file) return;

    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      setCompletedTutorialIds(sanitizeTutorialIds(parsed.completedTutorialIds));
      setSavedTutorialIds(sanitizeTutorialIds(parsed.savedTutorialIds));
      setRecentTutorialIds(sanitizeTutorialIds(parsed.recentTutorialIds).slice(0, 5));
      setTutorialNotes(sanitizeTutorialNotes(parsed.tutorialNotes));
      setSelectedReadingMode(sanitizeTutorialReadingMode(parsed.selectedReadingMode));
      setTutorialPracticeChecks(sanitizeTutorialPracticeChecks(parsed.tutorialPracticeChecks));
      setImportStatus('Learning data imported.');
    } catch {
      setImportStatus('Import failed. Choose a valid Learning Center JSON export.');
    } finally {
      if (learningStateFileInputRef.current) {
        learningStateFileInputRef.current.value = '';
      }
    }
  };

  if (expanded) {
    const colors = colorClasses[expanded.color];
    const isExpandedComplete = completedTutorialSet.has(expanded.id);
    const isExpandedSaved = savedTutorialSet.has(expanded.id);
    const expandedReadTime = getTutorialReadTimeMinutes(expanded);
    const moduleTarget = tutorialModuleTargets[expanded.dashboard];
    const expandedNote = tutorialNotes[expanded.id] || '';
    const readingModeClass = readingModeClasses[selectedReadingMode];
    const expandedPathIndex = activePathTutorials.findIndex((tutorial) => tutorial.id === expanded.id);
    const previousPathTutorial = expandedPathIndex > 0 ? activePathTutorials[expandedPathIndex - 1] : null;
    const nextPathTutorial = expandedPathIndex >= 0 && expandedPathIndex < activePathTutorials.length - 1
      ? activePathTutorials[expandedPathIndex + 1]
      : null;
    const expandedPathProgress = expandedPathIndex >= 0
      ? Math.round(((expandedPathIndex + 1) / activePathTutorials.length) * 100)
      : 0;
    const expandedPracticeChecks = new Set(tutorialPracticeChecks[expanded.id] || []);
    const expandedPracticePercent = Math.round((expandedPracticeChecks.size / expanded.bestPractices.length) * 100);
    
    return (
      <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
        {/* Back button */}
        <button
          onClick={() => setExpandedTutorial('')}
          className="flex items-center text-sm font-semibold text-gray-400 hover:text-white transition-colors mb-6"
        >
          <ChevronRight className="rotate-180 mr-2" size={16} />
          Back to all tutorials
        </button>

        {/* Header */}
        <div className="bg-gray-800 p-6 md:p-8 rounded-xl border border-gray-700 shadow-md mb-6">
          <div className="flex items-center mb-4">
            <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${colors.bg} ${colors.text} mr-2`}>
              {expanded.dashboard}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-bold ${difficultyColors[expanded.difficulty]}`}>
              {expanded.difficulty}
            </span>
            <span className="inline-flex items-center rounded bg-gray-900 px-2 py-0.5 text-xs font-bold text-gray-300">
              <Clock size={12} className="mr-1" />
              {expandedReadTime} min read
            </span>
          </div>
          <h2 className="text-2xl md:text-3xl font-bold text-white">{expanded.title}</h2>
          <p className="text-base md:text-lg text-gray-400 mt-4">{expanded.brief}</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => toggleTutorialCompletion(expanded.id)}
              className={`inline-flex items-center rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
                isExpandedComplete
                  ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                  : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-blue-500 hover:text-white'
              }`}
            >
              {isExpandedComplete ? <CheckCircle2 size={16} className="mr-2" /> : <Circle size={16} className="mr-2" />}
              {isExpandedComplete ? 'Marked complete' : 'Mark complete'}
            </button>
            <button
              type="button"
              onClick={() => toggleSavedTutorial(expanded.id)}
              className={`inline-flex items-center rounded-lg border px-4 py-2 text-sm font-semibold transition-colors ${
                isExpandedSaved
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-200 hover:bg-amber-500/20'
                  : 'border-gray-600 bg-gray-900 text-gray-300 hover:border-amber-500 hover:text-white'
              }`}
            >
              <Bookmark size={16} className="mr-2" />
              {isExpandedSaved ? 'Saved for later' : 'Save for later'}
            </button>
            {moduleTarget && onOpenModule && (
              <button
                type="button"
                onClick={() => onOpenModule(moduleTarget.view)}
                className="inline-flex items-center rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm font-semibold text-blue-200 transition-colors hover:bg-blue-500/20"
              >
                <ArrowUpRight size={16} className="mr-2" />
                Open related module
              </button>
            )}
          </div>
          {moduleTarget && (
            <p className="mt-3 text-xs text-gray-500">
              Related module: {moduleTarget.label} - {moduleTarget.reason}
            </p>
          )}
        </div>

        {expandedPathIndex >= 0 && (
          <div className="mb-6 rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 shadow-md">
            <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wide text-blue-100">Path position</h3>
                <p className="mt-1 text-sm text-blue-200/80">
                  {activeLearningPath.title}: step {expandedPathIndex + 1} of {activePathTutorials.length}
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs font-semibold text-blue-200">
                <span>{expandedPathProgress}% through this path</span>
              </div>
            </div>
            <div className="mb-4 h-2 overflow-hidden rounded-full bg-gray-900">
              <div
                className="h-full rounded-full bg-blue-400 transition-all duration-300"
                style={{ width: `${expandedPathProgress}%` }}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <button
                type="button"
                disabled={!previousPathTutorial}
                onClick={() => previousPathTutorial && setExpandedTutorial(previousPathTutorial.id)}
                className="flex min-h-20 items-center rounded-lg border border-gray-700 bg-gray-900 p-3 text-left transition-colors enabled:hover:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ChevronRight size={18} className="mr-3 rotate-180 text-blue-300" />
                <span>
                  <span className="block text-xs font-bold uppercase tracking-wide text-gray-500">Previous guide</span>
                  <span className="mt-1 block text-sm font-semibold text-white">
                    {previousPathTutorial ? renderHighlightedText(previousPathTutorial.title, highlightQuery) : 'Start of path'}
                  </span>
                </span>
              </button>
              <button
                type="button"
                disabled={!nextPathTutorial}
                onClick={() => nextPathTutorial && setExpandedTutorial(nextPathTutorial.id)}
                className="flex min-h-20 items-center justify-between rounded-lg border border-gray-700 bg-gray-900 p-3 text-left transition-colors enabled:hover:border-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span>
                  <span className="block text-xs font-bold uppercase tracking-wide text-gray-500">Next guide</span>
                  <span className="mt-1 block text-sm font-semibold text-white">
                    {nextPathTutorial ? renderHighlightedText(nextPathTutorial.title, highlightQuery) : 'Path complete'}
                  </span>
                </span>
                <ChevronRight size={18} className="ml-3 text-blue-300" />
              </button>
            </div>
          </div>
        )}

        <div className="mb-6 rounded-xl border border-gray-700 bg-gray-800 p-4 shadow-md">
          <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wide text-white">Reading comfort</h3>
              <p className="mt-1 text-xs text-gray-500">Adjust tutorial text size and spacing for this browser.</p>
            </div>
            <div className="flex rounded-lg border border-gray-700 bg-gray-950 p-1" aria-label="Tutorial reading comfort">
              {readingModeOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedReadingMode(option.value)}
                  title={option.description}
                  className={`h-9 rounded-md px-3 text-xs font-semibold transition-colors ${
                    selectedReadingMode === option.value
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
          <p className="text-xs text-gray-500">
            {readingModeOptions.find((option) => option.value === selectedReadingMode)?.description}
          </p>
        </div>

        <div className="mb-6 rounded-xl border border-gray-700 bg-gray-800 p-4 shadow-md">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wide text-white">Personal notes</h3>
              <p className="mt-1 text-xs text-gray-500">Saved locally in this browser.</p>
            </div>
            <span className="rounded bg-gray-900 px-2 py-1 text-xs font-bold text-gray-400">
              {expandedNote.trim().length} chars
            </span>
          </div>
          <textarea
            value={expandedNote}
            onChange={(event) => updateTutorialNote(expanded.id, event.target.value)}
            placeholder="Add your setup notes, parameter reminders, or follow-up questions for this guide."
            className="min-h-28 w-full resize-y rounded-lg border border-gray-700 bg-gray-900 p-3 text-sm leading-relaxed text-white outline-none transition-colors placeholder:text-gray-500 focus:border-blue-500"
          />
        </div>

        <div className="mb-6 rounded-xl border border-gray-700 bg-gray-800 p-4 shadow-md">
          <div className="mb-3 flex items-center text-sm font-bold uppercase tracking-wide text-white">
            <BookOpen size={16} className="mr-2 text-blue-400" />
            On this page
          </div>
          <div className="flex flex-wrap gap-2">
            {TUTORIAL_SECTION_LINKS.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm font-semibold text-gray-300 transition-colors hover:border-blue-500 hover:text-white"
              >
                Jump to {section.label}
              </a>
            ))}
          </div>
        </div>

        {/* Why This Matters */}
        <div id="why-this-matters" className="scroll-mt-4 bg-gray-800 rounded-xl border border-gray-700 shadow-md mb-6 overflow-hidden">
          <div className="flex items-center p-4 border-b border-gray-700 bg-gray-900/50">
            <BookOpen size={20} className="text-blue-400 mr-3" />
            <h3 className="text-lg font-bold text-white">Why This Matters</h3>
          </div>
          <div className={readingModeClass.panel}>
            <p className={readingModeClass.body}>{renderHighlightedText(expanded.significance, highlightQuery)}</p>
          </div>
        </div>

        {/* Reading the Dashboard */}
        <div id="reading-the-dashboard" className="scroll-mt-4 bg-gray-800 rounded-xl border border-gray-700 shadow-md mb-6 overflow-hidden">
          <div className="flex items-center p-4 border-b border-gray-700 bg-gray-900/50">
            <Target size={20} className="text-emerald-400 mr-3" />
            <h3 className="text-lg font-bold text-white">Reading the Dashboard</h3>
          </div>
          <div className={readingModeClass.panel}>
            <p className={`${readingModeClass.body} mb-4`}>{renderHighlightedText(expanded.interpretation, highlightQuery)}</p>
            <div className="flex items-start bg-yellow-500/10 border border-yellow-500/20 p-4 rounded-lg">
              <Lightbulb size={18} className="text-yellow-400 mr-2 shrink-0 mt-0.5" />
              <div>
                <strong className="text-yellow-200">Key Insight: </strong>
                <span className={selectedReadingMode === 'large' ? 'text-lg leading-8 text-yellow-100' : 'text-yellow-100'}>
                  {renderHighlightedText(expanded.keyInsight, highlightQuery)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Best Practices */}
        <div id="best-practices" className="scroll-mt-4 bg-gray-800 rounded-xl border border-gray-700 shadow-md mb-8 overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-gray-700 bg-gray-900/50 p-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center">
              <Shield size={20} className="text-amber-400 mr-3" />
              <div>
                <h3 className="text-lg font-bold text-white">Best Practices</h3>
                <p className="mt-1 text-xs text-gray-500">
                  {expandedPracticeChecks.size} of {expanded.bestPractices.length} actions checked
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-gray-950 px-3 py-1.5 text-xs font-bold text-amber-100">
                {expandedPracticePercent}% complete
              </span>
              <button
                type="button"
                disabled={expandedPracticeChecks.size === expanded.bestPractices.length}
                onClick={() => completeTutorialPracticeChecklist(expanded)}
                className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-bold text-emerald-100 transition-colors enabled:hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Mark all done
              </button>
              <button
                type="button"
                disabled={expandedPracticeChecks.size === 0}
                onClick={() => clearTutorialPracticeChecklist(expanded.id)}
                className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-bold text-gray-300 transition-colors enabled:hover:border-amber-500 enabled:hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Reset actions
              </button>
            </div>
          </div>
          <div className={`${readingModeClass.panel} flex flex-col`}>
            {expanded.bestPractices.map((practice, idx) => (
              <label
                key={idx}
                className={`mb-3 flex cursor-pointer items-start rounded-lg border p-4 transition-colors last:mb-0 ${
                  expandedPracticeChecks.has(idx)
                    ? 'border-emerald-500/30 bg-emerald-500/10'
                    : 'border-gray-800 bg-gray-900/30 hover:border-gray-700'
                }`}
              >
                <input
                  type="checkbox"
                  checked={expandedPracticeChecks.has(idx)}
                  onChange={() => toggleTutorialPracticeCheck(expanded.id, idx)}
                  className="mt-1 mr-3 h-4 w-4 rounded border-gray-600 bg-gray-900 text-emerald-500 focus:ring-emerald-500"
                />
                <span className={`${readingModeClass.practice} ${expandedPracticeChecks.has(idx) ? 'text-emerald-100' : ''}`}>
                  {renderHighlightedText(practice, highlightQuery)}
                </span>
              </label>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Grid view
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-gray-800 p-8 rounded-xl border border-gray-700 shadow-md mb-8">
        <BookOpen size={32} className="text-blue-500 mb-4" />
        <h2 className="text-2xl font-bold text-white mb-2">Sentinel Edge Learning Center</h2>
        <p className="text-gray-400 max-w-3xl">
          In-depth guides for intermediate to advanced users on core Sentinel Edge concepts. 
          Each tutorial covers a key system component with practical interpretation guidance and optimization best practices.
        </p>
        <div className="mt-6 max-w-2xl">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="font-semibold text-white">{completedCount} of {TUTORIALS.length} guides complete</span>
            <span className="text-gray-400">{completionPercent}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-gray-900">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-300"
              style={{ width: `${completionPercent}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-gray-400">{savedCount} saved for later</p>
          <p className="mt-1 text-xs text-gray-400">{notesCount} guides with notes</p>
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1fr_1fr_auto]">
          <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Guides complete</span>
            <div className="mt-2 flex items-end justify-between gap-3">
              <span className="text-2xl font-bold text-white">{completionPercent}%</span>
              <span className="text-xs text-gray-400">{completedCount}/{TUTORIALS.length}</span>
            </div>
          </div>
          <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Action checklist</span>
            <div className="mt-2 flex items-end justify-between gap-3">
              <span className="text-2xl font-bold text-emerald-200">{practiceActionPercent}%</span>
              <span className="text-xs text-gray-400">{checkedPracticeActionCount}/{totalPracticeActions}</span>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-950">
              <div
                className="h-full rounded-full bg-emerald-400 transition-all duration-300"
                style={{ width: `${practiceActionPercent}%` }}
              />
            </div>
          </div>
          <div className="rounded-lg border border-gray-700 bg-gray-900/60 p-4">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Saved context</span>
            <div className="mt-2 flex items-end justify-between gap-3">
              <span className="text-2xl font-bold text-amber-100">{savedCount}</span>
              <span className="text-xs text-gray-400">{notesCount} notes</span>
            </div>
          </div>
          {nextPracticeTutorial && (
            <button
              type="button"
              onClick={() => setExpandedTutorial(nextPracticeTutorial.id)}
              className="flex min-h-24 items-center justify-between rounded-lg border border-blue-500/30 bg-blue-500/10 p-4 text-left transition-colors hover:bg-blue-500/20"
            >
              <span>
                <span className="block text-xs font-bold uppercase tracking-wide text-blue-200">Next action</span>
                <span className="mt-1 block max-w-56 text-sm font-semibold text-white">
                  {renderHighlightedText(nextPracticeTutorial.title, highlightQuery)}
                </span>
              </span>
              <ChevronRight size={18} className="ml-3 text-blue-200" />
            </button>
          )}
        </div>
        {recentTutorials.length > 0 && (
          <div className="mt-6 rounded-xl border border-gray-700 bg-gray-900/50 p-4">
            <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wide text-white">Recently viewed</h3>
                <p className="text-xs text-gray-500">Jump back into guides you opened in this browser.</p>
              </div>
              <button
                type="button"
                onClick={() => setRecentTutorialIds([])}
                className="self-start text-xs font-semibold text-gray-400 transition-colors hover:text-white sm:self-auto"
              >
                Clear recent
              </button>
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
              {recentTutorials.slice(0, 3).map((tutorial) => {
                const status = getTutorialProgressStatus(tutorial);
                const statusMeta = tutorialStatusMeta[status];
                const readTime = getTutorialReadTimeMinutes(tutorial);

                return (
                  <button
                    key={tutorial.id}
                    type="button"
                    onClick={() => setExpandedTutorial(tutorial.id)}
                    className="rounded-lg border border-gray-700 bg-gray-950 p-3 text-left transition-colors hover:border-blue-500"
                  >
                    <span className={`mb-2 inline-flex rounded px-2 py-0.5 text-xs font-bold ${statusMeta.classes}`}>
                      {statusMeta.label}
                    </span>
                    <span className="block text-sm font-semibold text-white">{renderHighlightedText(tutorial.title, highlightQuery)}</span>
                    <span className="mt-2 inline-flex items-center text-xs text-gray-500">
                      <Clock size={12} className="mr-1" />
                      {readTime} min read
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={exportLearningCenterState}
            className="inline-flex items-center rounded-lg border border-gray-700 px-4 py-2 text-sm font-semibold text-gray-300 transition-colors hover:border-blue-500 hover:text-white"
          >
            <Download size={16} className="mr-2" />
            Download learning data
          </button>
          <button
            type="button"
            onClick={() => learningStateFileInputRef.current?.click()}
            className="inline-flex items-center rounded-lg border border-gray-700 px-4 py-2 text-sm font-semibold text-gray-300 transition-colors hover:border-blue-500 hover:text-white"
          >
            <Upload size={16} className="mr-2" />
            Import learning data
          </button>
          <input
            ref={learningStateFileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => importLearningCenterState(event.target.files?.[0] || null)}
          />
          {importStatus && <span className="text-xs text-gray-400">{importStatus}</span>}
          {persistenceStatus && <span role="alert" className="text-xs text-red-300">{persistenceStatus}</span>}
        </div>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 shadow-md mb-6 overflow-hidden">
        <div className="border-b border-gray-700 bg-gray-900/50 px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wide text-white">Recommended Learning Path</h3>
              <p className="mt-1 text-sm text-gray-400">{activeLearningPath.summary}</p>
              <p className="mt-1 text-xs text-gray-500">
                {activePathReadTime} path minutes - {activePathProgress.completed}/{activePathProgress.total} complete - {activePathProgress.remainingMinutes} min remaining
              </p>
            </div>
            {recommendedTutorial && (
              <button
                type="button"
                onClick={() => setExpandedTutorial(recommendedTutorial.id)}
                className="inline-flex h-10 items-center justify-center rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-blue-500"
              >
                Continue path <ChevronRight size={16} className="ml-1" />
              </button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 p-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="flex flex-col gap-2">
            {LEARNING_PATHS.map((path) => {
              const isSelected = path.id === activeLearningPath.id;
              const pathTutorials = path.tutorialIds
                .map((tutorialId) => TUTORIALS.find((tutorial) => tutorial.id === tutorialId))
                .filter((tutorial): tutorial is Tutorial => Boolean(tutorial));
              const pathProgress = getLearningPathProgress(pathTutorials, completedTutorialSet);
              return (
                <button
                  type="button"
                  key={path.id}
                  onClick={() => setSelectedLearningPath(path.id)}
                  className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                    isSelected
                      ? 'border-blue-500/60 bg-blue-500/10 text-white'
                      : 'border-gray-700 bg-gray-900/60 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  <span className="block text-sm font-semibold">{path.title}</span>
                  <span className="mt-1 block text-xs text-gray-400">
                    {pathProgress.completed}/{pathProgress.total} complete - {pathProgress.remainingMinutes} min left
                  </span>
                  <span className="mt-3 block h-1.5 overflow-hidden rounded-full bg-gray-950">
                    <span
                      className="block h-full rounded-full bg-blue-400 transition-all duration-300"
                      style={{ width: `${pathProgress.percent}%` }}
                    />
                  </span>
                </button>
              );
            })}
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {activePathTutorials.map((tutorial, index) => {
              const isComplete = completedTutorialSet.has(tutorial.id);
              const colors = colorClasses[tutorial.color];
              const status = getTutorialProgressStatus(tutorial);
              const statusMeta = tutorialStatusMeta[status];
              const actionProgress = getTutorialActionProgress(tutorial, tutorialPracticeChecks);
              return (
                <button
                  type="button"
                  key={tutorial.id}
                  onClick={() => setExpandedTutorial(tutorial.id)}
                  className={`rounded-lg border p-4 text-left transition-colors ${
                    isComplete
                      ? 'border-emerald-500/30 bg-emerald-500/10'
                      : `bg-gray-900/60 ${colors.border} hover:bg-gray-900`
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wide text-gray-500">Step {index + 1}</span>
                    {isComplete ? (
                      <CheckCircle2 size={18} className="text-emerald-300" />
                    ) : (
                      <Circle size={18} className="text-gray-500" />
                    )}
                  </div>
                  <span className={`mb-2 inline-flex rounded px-2 py-0.5 text-xs font-bold ${statusMeta.classes}`}>
                    {statusMeta.label}
                  </span>
                  <h4 className="text-sm font-bold text-white">{renderHighlightedText(tutorial.title, highlightQuery)}</h4>
                  <p className="mt-2 text-xs text-gray-400">{tutorial.dashboard}</p>
                  <p className="mt-1 inline-flex items-center text-xs text-gray-500">
                    <Clock size={12} className="mr-1" />
                    {getTutorialReadTimeMinutes(tutorial)} min read
                  </p>
                  <div className="mt-3">
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="font-semibold text-gray-400">Action progress</span>
                      <span className="text-gray-500">{actionProgress.checked}/{actionProgress.total}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-gray-950">
                      <div
                        className="h-full rounded-full bg-emerald-400 transition-all duration-300"
                        style={{ width: `${actionProgress.percent}%` }}
                      />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 shadow-md mb-6 overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-gray-700 bg-gray-900/50 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <SlidersHorizontal size={18} className="text-blue-400" />
            <div>
              <h3 className="text-sm font-bold uppercase tracking-wide text-white">Find a Tutorial</h3>
              <p className="text-xs text-gray-400">{filteredTutorials.length} of {activePathTutorials.length} path guides shown</p>
            </div>
          </div>
          <div className="flex rounded-lg border border-gray-700 bg-gray-950 p-1" aria-label="Tutorial display mode">
            {[
              { mode: 'detailed' as TutorialDisplayMode, label: 'Detailed cards', icon: LayoutGrid },
              { mode: 'compact' as TutorialDisplayMode, label: 'Compact list', icon: List },
            ].map(({ mode, label, icon: Icon }) => (
              <button
                key={mode}
                type="button"
                onClick={() => setSelectedDisplayMode(mode)}
                className={`inline-flex h-9 items-center rounded-md px-3 text-xs font-semibold transition-colors ${
                  selectedDisplayMode === mode
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Icon size={14} className="mr-2" />
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="border-b border-gray-700 px-5 py-4">
          <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wide text-gray-400">Quick focus</h4>
              <p className="text-xs text-gray-500">Apply common Learning Center views with one click.</p>
            </div>
            <span className="text-xs text-gray-500">Applies across all guides</span>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {quickFocusOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => applyTutorialFocusPreset(option.id)}
                title={option.description}
                className="flex min-h-16 items-center justify-between rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-left transition-colors hover:border-blue-500 hover:bg-gray-900/80"
              >
                <span>
                  <span className="block text-sm font-semibold text-white">{option.label}</span>
                  <span className="mt-0.5 block text-xs text-gray-500">{option.description}</span>
                </span>
                <span className="ml-3 rounded bg-gray-950 px-2 py-1 text-xs font-bold text-blue-200">{option.count}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 p-5 lg:grid-cols-[minmax(0,1fr)_200px_160px_170px_180px_auto_auto_auto_auto]">
          <label className="relative">
            <span className="sr-only">Search tutorials</span>
            <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search tutorials"
              className="h-11 w-full rounded-lg border border-gray-700 bg-gray-900 pl-10 pr-3 text-sm text-white outline-none transition-colors placeholder:text-gray-500 focus:border-blue-500"
            />
          </label>

          <label>
            <span className="sr-only">Dashboard filter</span>
            <select
              value={selectedDashboard}
              onChange={(event) => setSelectedDashboard(event.target.value)}
              className="h-11 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 text-sm text-white outline-none transition-colors focus:border-blue-500"
            >
              <option value="All">All dashboards</option>
              {dashboardOptions.map((dashboard) => (
                <option key={dashboard} value={dashboard}>{dashboard}</option>
              ))}
            </select>
          </label>

          <label>
            <span className="sr-only">Difficulty filter</span>
            <select
              value={selectedDifficulty}
              onChange={(event) => setSelectedDifficulty(event.target.value as 'All' | Tutorial['difficulty'])}
              className="h-11 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 text-sm text-white outline-none transition-colors focus:border-blue-500"
            >
              <option value="All">All levels</option>
              {difficultyOptions.map((difficulty) => (
                <option key={difficulty} value={difficulty}>{difficulty}</option>
              ))}
            </select>
          </label>

          <label>
            <span className="sr-only">Status filter</span>
            <select
              value={selectedStatusFilter}
              onChange={(event) => setSelectedStatusFilter(event.target.value as TutorialStatusFilter)}
              className="h-11 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 text-sm text-white outline-none transition-colors focus:border-blue-500"
            >
              {statusFilterOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            <span className="sr-only">Sort tutorials</span>
            <select
              value={selectedSort}
              onChange={(event) => setSelectedSort(event.target.value as TutorialSortOption)}
              className="h-11 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 text-sm text-white outline-none transition-colors focus:border-blue-500"
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={clearFilters}
            className="h-11 rounded-lg border border-gray-700 px-4 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
          >
            Clear filters
          </button>

          <label className="flex h-11 cursor-pointer items-center justify-center rounded-lg border border-gray-700 px-4 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-500 hover:text-white">
            <input
              type="checkbox"
              checked={showIncompleteOnly}
              onChange={(event) => setShowIncompleteOnly(event.target.checked)}
              className="mr-2 h-4 w-4 rounded border-gray-600 bg-gray-900 text-blue-600 focus:ring-blue-500"
            />
            Show incomplete only
          </label>

          <label className="flex h-11 cursor-pointer items-center justify-center rounded-lg border border-gray-700 px-4 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-500 hover:text-white">
            <input
              type="checkbox"
              checked={showSavedOnly}
              onChange={(event) => setShowSavedOnly(event.target.checked)}
              className="mr-2 h-4 w-4 rounded border-gray-600 bg-gray-900 text-blue-600 focus:ring-blue-500"
            />
            Show saved only
          </label>

          <label className="flex h-11 cursor-pointer items-center justify-center rounded-lg border border-gray-700 px-4 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-500 hover:text-white">
            <input
              type="checkbox"
              checked={showNotesOnly}
              onChange={(event) => setShowNotesOnly(event.target.checked)}
              className="mr-2 h-4 w-4 rounded border-gray-600 bg-gray-900 text-blue-600 focus:ring-blue-500"
            />
            Show notes only
          </label>
        </div>
        {activeFilterChips.length > 0 && (
          <div className="border-t border-gray-700 px-5 py-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <span className="text-xs font-bold uppercase tracking-wide text-gray-400">Active filters</span>
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs font-semibold text-blue-300 transition-colors hover:text-blue-200"
              >
                Clear all
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {activeFilterChips.map((chip) => (
                <button
                  key={chip.id}
                  type="button"
                  onClick={chip.onClear}
                  className="inline-flex items-center rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-100 transition-colors hover:bg-blue-500/20"
                  aria-label={`Remove filter ${chip.label}`}
                >
                  {chip.label}
                  <X size={12} className="ml-2" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {filteredTutorials.length === 0 ? (
        <div className="rounded-xl border border-dashed border-gray-700 bg-gray-800 p-8 text-center shadow-md">
          <BookOpen size={28} className="mx-auto mb-3 text-gray-500" />
          <h3 className="text-lg font-bold text-white">No tutorials match your filters</h3>
          <p className="mx-auto mt-2 max-w-xl text-sm text-gray-400">
            Try a different dashboard, difficulty, or keyword to find the workflow guide you need.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            {normalizedQuery && (
              <button
                type="button"
                onClick={clearSearchOnly}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-semibold text-gray-300 transition-colors hover:border-blue-500 hover:text-white"
              >
                Clear search only
              </button>
            )}
            {activeLearningPath.id !== 'all-guides' && (
              <button
                type="button"
                onClick={() => setSelectedLearningPath('all-guides')}
                className="rounded-lg border border-gray-700 px-4 py-2 text-sm font-semibold text-gray-300 transition-colors hover:border-blue-500 hover:text-white"
              >
                Search all guides
              </button>
            )}
            <button
              type="button"
              onClick={() => applyTutorialFocusPreset('resume')}
              className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm font-semibold text-blue-100 transition-colors hover:bg-blue-500/20"
            >
              Show in-progress guides
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-500"
            >
              Reset all filters
            </button>
          </div>
        </div>
      ) : (
      <div className={selectedDisplayMode === 'compact' ? 'grid grid-cols-1 gap-3' : 'grid grid-cols-1 md:grid-cols-2 gap-6'}>
        {sortedTutorials.map((tutorial) => {
          const colors = colorClasses[tutorial.color];
          const isComplete = completedTutorialSet.has(tutorial.id);
          const isSaved = savedTutorialSet.has(tutorial.id);
          const hasNote = Boolean(tutorialNotes[tutorial.id]?.trim());
          const readTime = getTutorialReadTimeMinutes(tutorial);
          const compact = selectedDisplayMode === 'compact';
          const status = getTutorialProgressStatus(tutorial);
          const statusMeta = tutorialStatusMeta[status];
          const actionProgress = getTutorialActionProgress(tutorial, tutorialPracticeChecks);
          return (
            <button
              key={tutorial.id}
              onClick={() => setExpandedTutorial(tutorial.id)}
              className={`text-left bg-gray-800 rounded-xl border ${colors.border} shadow-md hover:bg-gray-750 transition-all group ${compact ? 'p-4' : 'p-6'}`}
            >
              <div className={`flex items-start ${compact ? 'mb-0' : 'mb-4'}`}>
                <div className={`rounded-xl ${colors.bg} mr-4 ${compact ? 'p-2' : 'p-3'}`}>
                  {getIcon(tutorial.icon, `${compact ? 'h-5 w-5' : 'h-8 w-8'} ${colors.icon}`)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${colors.bg} ${colors.text}`}>
                      {tutorial.dashboard}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${difficultyColors[tutorial.difficulty]}`}>
                      {tutorial.difficulty}
                    </span>
                    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-bold ${statusMeta.classes}`}>
                      {statusMeta.label}
                    </span>
                    {isComplete && (
                      <span className="inline-flex items-center rounded bg-emerald-500/20 px-2 py-0.5 text-xs font-bold text-emerald-300">
                        <CheckCircle2 size={12} className="mr-1" />
                        Complete
                      </span>
                    )}
                    {isSaved && (
                      <span className="inline-flex items-center rounded bg-amber-500/20 px-2 py-0.5 text-xs font-bold text-amber-200">
                        <Bookmark size={12} className="mr-1" />
                        Saved
                      </span>
                    )}
                    {hasNote && (
                      <span className="inline-flex items-center rounded bg-cyan-500/20 px-2 py-0.5 text-xs font-bold text-cyan-200">
                        <BookOpen size={12} className="mr-1" />
                        Notes
                      </span>
                    )}
                    <span className="inline-flex items-center rounded bg-gray-900 px-2 py-0.5 text-xs font-bold text-gray-300">
                      <Clock size={12} className="mr-1" />
                      {readTime} min read
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-white group-hover:text-blue-400 transition-colors">
                    {renderHighlightedText(tutorial.title, highlightQuery)}
                  </h3>
                </div>
              </div>
              {!compact && <p className="text-gray-400 text-sm">{renderHighlightedText(tutorial.brief, highlightQuery)}</p>}
              <div className={`${compact ? 'mt-2 pl-12' : 'mt-4'} max-w-xl`}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-semibold text-gray-400">Action progress</span>
                  <span className="text-gray-500">{actionProgress.checked}/{actionProgress.total}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-gray-950">
                  <div
                    className="h-full rounded-full bg-emerald-400 transition-all duration-300"
                    style={{ width: `${actionProgress.percent}%` }}
                  />
                </div>
              </div>
              <div className={`flex items-center text-blue-400 text-sm font-medium ${compact ? 'mt-2 pl-12' : 'mt-4'}`}>
                View tutorial <ChevronRight size={16} className="ml-1" />
              </div>
            </button>
          );
        })}
      </div>
      )}
    </div>
  );
};

export default TutorialsDashboard;
