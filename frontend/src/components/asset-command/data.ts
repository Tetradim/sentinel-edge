import {
  Activity,
  Bell,
  CheckCircle,
  Gauge,
  Save,
  Search,
  Shield,
  SlidersHorizontal,
  Target,
  Zap,
} from 'lucide-react';
import type {
  BotBridgeHealth,
  BotLockout,
  CoreColorMetric,
  CoreHeatmapConfig,
  CoreLabelMode,
  CoreSizeMetric,
  CoreUniverse,
  DirectiveLedgerEntry,
  EventFilter,
  EventLine,
  MarketRegimeState,
  Metric,
  Mode,
  OperationViewItem,
  OutcomeAttribution,
  PolicyStackRule,
  ProtectionRow,
  Ticker,
  Tone,
  Watcher,
} from './types';

export const money = (value: number) => `$${value.toFixed(2)}`;

const metricMap = (symbol: string, price: number, ids: string[]): Metric[] => {
  const base: Record<string, Metric> = {
    hist: { id: 'hist', label: 'MACD', value: 'Hist', detail: '+0.18', tone: 'gold' },
    vscore: { id: 'vscore', label: 'Vol', value: 'V-score', detail: symbol === 'SPY' ? '71' : '64', tone: 'cyan' },
    emaTop: { id: 'emaTop', label: 'EMA', value: 'EMA top', detail: money(price + 0.7), tone: 'green' },
    emaBottom: { id: 'emaBottom', label: 'EMA', value: 'EMA bottom', detail: money(price - 4.9), tone: 'red' },
    smaTop: { id: 'smaTop', label: 'SMA', value: 'SMA top', detail: money(price + 1.4), tone: 'green' },
    smaBottom: { id: 'smaBottom', label: 'SMA', value: 'SMA bottom', detail: money(price - 6.2), tone: 'red' },
    invalid: { id: 'invalid', label: 'ATR', value: 'Invalid', detail: money(price - 4.2), tone: 'red' },
    momentum: { id: 'momentum', label: 'RSI', value: 'Momentum', detail: symbol === 'NVDA' ? '44' : '62', tone: 'green' },
    liquidity: { id: 'liquidity', label: 'Flow', value: 'Liquidity', detail: '$1.42M', tone: 'cyan' },
    spread: { id: 'spread', label: 'Book', value: 'Spread', detail: '0.04%', tone: 'cyan' },
    drawdown: { id: 'drawdown', label: 'Risk', value: 'Drawdown', detail: '-0.84%', tone: 'red' },
    heat: { id: 'heat', label: 'Risk', value: 'Heat', detail: '46', tone: 'red' },
    atr: { id: 'atr', label: 'ATR', value: 'Vol shelf', detail: '0.72R', tone: 'gold' },
    flow: { id: 'flow', label: 'Flow', value: 'Sweep', detail: '+14', tone: 'cyan' },
    gap: { id: 'gap', label: 'Gap', value: 'Distance', detail: '0.7%', tone: 'gold' },
    volume: { id: 'volume', label: 'Vol', value: 'Rel vol', detail: '1.8x', tone: 'cyan' },
  };
  return ids.map((id) => base[id] || base.momentum);
};

const createTicker = (
  symbol: string,
  change: string,
  status: string,
  watchers: Watcher[],
  price: number,
  metrics: string[],
  signal: string,
): Ticker => ({
  symbol,
  change,
  status,
  watchers,
  price,
  signal,
  metrics: metricMap(symbol, price, metrics),
});

export const tickers: Ticker[] = [
  createTicker('MSFT', '+0.42%', 'Pulse idle', [], 414.2, ['smaTop', 'smaBottom', 'liquidity', 'spread', 'drawdown'], 'Bull 58'),
  createTicker('QQQ', '-0.18%', 'Flow watch', [{ plugin: 'FLOW', status: 'watching', trigger: 'sweep', source: 'Sentinel Pulse' }], 472.8, ['flow', 'spread', 'liquidity', 'momentum', 'drawdown'], 'Flat 49'),
  createTicker('AAPL', '+3.52%', 'EMA scan', [{ plugin: 'EMA', status: 'scanning', trigger: 'cross', source: 'Sentinel Pulse' }], 183.42, ['emaTop', 'emaBottom', 'smaTop', 'smaBottom', 'momentum'], 'Bull 71'),
  createTicker('SPY', '+0.50%', 'MACD-V', [{ plugin: 'MACD-V', status: 'armed', trigger: 'compression', source: 'Sentinel Pulse' }], 632.4, ['hist', 'vscore', 'emaTop', 'invalid', 'momentum'], 'Bull 71'),
  createTicker('NVDA', '-1.88%', 'Risk cut', [{ plugin: 'RISK', status: 'armed', trigger: 'heat', source: 'Sentinel Pulse' }], 141.18, ['heat', 'invalid', 'atr', 'drawdown', 'spread'], 'Bear 42'),
  createTicker('TSLA', '+1.12%', 'Pulse idle', [], 219.64, ['momentum', 'smaTop', 'emaTop', 'liquidity', 'spread'], 'Bull 63'),
  createTicker('META', '-0.07%', 'Gap watch', [{ plugin: 'GAP', status: 'watching', trigger: 'open-gap', source: 'Sentinel Pulse' }], 503.72, ['gap', 'flow', 'volume', 'invalid', 'momentum'], 'Flat 52'),
];

export const eventSymbols = new Set(tickers.map((ticker) => ticker.symbol));

export const initialEvents: EventLine[] = [
  { id: 'e1', symbol: 'SPY', title: 'MACD-V watcher armed', detail: 'Histogram compression detected', time: '--:--:--' },
  { id: 'e2', symbol: 'AAPL', title: 'EMA scan updated', detail: 'Trend shelf strengthened', time: '--:--:--' },
  { id: 'e3', symbol: 'NVDA', title: 'Risk cut queued', detail: 'Heat corridor narrowed', time: '--:--:--' },
];

export const eventFilterOptions: { id: EventFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'selected', label: 'Selected' },
];

export const allMetricOptions = Array.from(
  new Map(tickers.flatMap((ticker) => ticker.metrics.map((metric) => [metric.id, { id: metric.id, label: metric.value }]))).values(),
);

export const defaultCoreHeatmapConfig: CoreHeatmapConfig = {
  colorMetric: 'risk',
  sizeMetric: 'exposure',
  universe: 'watchlist',
  horizon: '30m',
  density: 7,
  alertThreshold: 65,
  includeIdle: true,
  autoFocusTicker: true,
  labelMode: 'symbol',
  operatorNote: 'Watch heat against signal confirmation before staging a command.',
};

export const coreColorMetricOptions: { id: CoreColorMetric; label: string; detail: string }[] = [
  { id: 'risk', label: 'Risk heat', detail: 'Heat, invalidation, and watcher risk' },
  { id: 'signal', label: 'Signal strength', detail: 'Bull/bear score from active signal' },
  { id: 'flow', label: 'Flow pressure', detail: 'Sweep, volume, and liquidity pressure' },
  { id: 'drawdown', label: 'Drawdown', detail: 'Loss corridor and downside pressure' },
];

export const coreSizeMetricOptions: { id: CoreSizeMetric; label: string }[] = [
  { id: 'exposure', label: 'Exposure' },
  { id: 'liquidity', label: 'Liquidity' },
  { id: 'volatility', label: 'Volatility' },
];

export const coreUniverseOptions: { id: CoreUniverse; label: string }[] = [
  { id: 'watchlist', label: 'Active watchlist' },
  { id: 'watchers', label: 'Watcher only' },
  { id: 'all', label: 'All tracked assets' },
];

export const coreLabelModeOptions: { id: CoreLabelMode; label: string }[] = [
  { id: 'symbol', label: 'Symbol' },
  { id: 'signal', label: 'Signal' },
  { id: 'heat', label: 'Heat' },
];

export const serviceRows = [
  ['Market data feed', 'online', '22ms', '1.8k msg/min'],
  ['Sentinel Pulse bridge', 'online', '18ms', '5 watchers'],
  ['Prediction core', 'online', '31ms', '42 forecasts/min'],
  ['Plugin bus', 'degraded', '44ms', '1 retry/min'],
  ['Event router', 'online', '12ms', '92 events/min'],
];

export const protectionRows: ProtectionRow[] = [
  { symbol: 'SPY', guard: 'MACD-V / trailing', exposure: '32%', stop: '$628.20', invalid: '$626.80', heat: '38', action: 'tighten into strength', tone: 'green' },
  { symbol: 'AAPL', guard: 'EMA / protected', exposure: '18%', stop: '$180.10', invalid: '$178.80', heat: '31', action: 'hold corridor', tone: 'green' },
  { symbol: 'QQQ', guard: 'FLOW / hedged', exposure: '28%', stop: '$468.40', invalid: '$465.90', heat: '44', action: 'watch sweep fade', tone: 'gold' },
  { symbol: 'NVDA', guard: 'RISK / redline', exposure: '21%', stop: '$137.90', invalid: '$135.80', heat: '69', action: 'reduce if 135.80 breaks', tone: 'red' },
];

export const marketRegime: MarketRegimeState = {
  label: 'Gamma pin / breakout watch',
  score: '72',
  detail: 'Trend is constructive, but GEX pressure and support proximity require confirmation.',
  pressure: 'Moderate risk',
  allowedPosture: 'Advise / block below support',
  tone: 'gold',
};

export const directiveLedger: DirectiveLedgerEntry[] = [
  {
    id: 'd1',
    time: '09:42:18',
    bot: 'Sentinel Pulse',
    symbol: 'SPY',
    directive: 'Allow guarded breakout',
    reason: 'Price above support, MACD-V compression resolving, risk corridor inside limit.',
    confidence: '0.82',
    regime: 'Gamma pin',
    acknowledgement: 'ack 42ms',
    tone: 'green',
  },
  {
    id: 'd2',
    time: '09:43:02',
    bot: 'Discord Trading Bot',
    symbol: 'NVDA',
    directive: 'Block buy',
    reason: 'Heat 69, support shelf weakening, spread widening into redline.',
    confidence: '0.88',
    regime: 'Risk expansion',
    acknowledgement: 'ack 71ms',
    tone: 'red',
  },
  {
    id: 'd3',
    time: '09:44:31',
    bot: 'Futures',
    symbol: 'NQ',
    directive: 'Reduce size',
    reason: 'Correlation cluster elevated and VEX expansion crossed policy threshold.',
    confidence: '0.76',
    regime: 'Vol expansion',
    acknowledgement: 'queued',
    tone: 'gold',
  },
  {
    id: 'd4',
    time: '09:45:10',
    bot: 'Auto-Crypto',
    symbol: 'BTC',
    directive: 'Watch only',
    reason: 'Liquidity acceptable but market regime mismatch keeps breakout inactive.',
    confidence: '0.64',
    regime: 'Range chop',
    acknowledgement: 'ack 55ms',
    tone: 'cyan',
  },
  {
    id: 'd5',
    time: '09:46:44',
    bot: 'Consolidation',
    symbol: 'AAPL',
    directive: 'Allow with size cap',
    reason: 'EMA shelf intact, but same-sector exposure caps requested size.',
    confidence: '0.79',
    regime: 'Trend continuation',
    acknowledgement: 'ack 33ms',
    tone: 'green',
  },
];

export const botBridgeHealth: BotBridgeHealth[] = [
  {
    name: 'Sentinel Pulse',
    status: 'online',
    heartbeat: '3s',
    latency: '18ms',
    contract: 'edge.pulse.v1',
    lastDirective: 'Allow guarded breakout',
    lastAck: '09:42:18',
    queueDepth: 0,
    rejectedEvents: 0,
    detail: 'Primary execution bridge acknowledged.',
    tone: 'green',
  },
  {
    name: 'Discord Trading Bot',
    status: 'online',
    heartbeat: '5s',
    latency: '42ms',
    contract: 'edge.discord.v1',
    lastDirective: 'Block buy',
    lastAck: '09:43:04',
    queueDepth: 1,
    rejectedEvents: 0,
    detail: 'Alert parser receiving suppression directives.',
    tone: 'green',
  },
  {
    name: 'Auto-Crypto',
    status: 'degraded',
    heartbeat: '24s',
    latency: '88ms',
    contract: 'edge.crypto.v1',
    lastDirective: 'Watch only',
    lastAck: '09:45:11',
    queueDepth: 2,
    rejectedEvents: 1,
    detail: 'Crypto bridge is slow but still accepting advice.',
    tone: 'gold',
  },
  {
    name: 'Futures',
    status: 'online',
    heartbeat: '4s',
    latency: '21ms',
    contract: 'edge.futures.v1',
    lastDirective: 'Reduce size',
    lastAck: 'queued',
    queueDepth: 1,
    rejectedEvents: 0,
    detail: 'Size controls waiting on acknowledgement.',
    tone: 'cyan',
  },
  {
    name: 'Tandem Suite',
    status: 'online',
    heartbeat: '8s',
    latency: '36ms',
    contract: 'edge.tandem.v1',
    lastDirective: 'Runtime clear',
    lastAck: '09:41:02',
    queueDepth: 0,
    rejectedEvents: 0,
    detail: 'System supervisor bridge healthy.',
    tone: 'green',
  },
  {
    name: 'Darkpool Mon',
    status: 'standalone',
    heartbeat: 'local',
    latency: 'n/a',
    contract: 'read-only',
    lastDirective: 'Flow input only',
    lastAck: 'n/a',
    queueDepth: 0,
    rejectedEvents: 0,
    detail: 'Used as intelligence source, not directive target.',
    tone: 'cyan',
  },
  {
    name: 'Consolidation',
    status: 'online',
    heartbeat: '6s',
    latency: '39ms',
    contract: 'edge.alerts.v1',
    lastDirective: 'Allow with size cap',
    lastAck: '09:46:44',
    queueDepth: 0,
    rejectedEvents: 0,
    detail: 'Options alert bridge applying size caps.',
    tone: 'green',
  },
  {
    name: 'APK Alerts',
    status: 'offline',
    heartbeat: 'lost',
    latency: 'n/a',
    contract: 'edge.mobile.v1',
    lastDirective: 'No route',
    lastAck: '08:58:10',
    queueDepth: 4,
    rejectedEvents: 2,
    detail: 'Mobile alert bridge is unavailable.',
    tone: 'red',
  },
  {
    name: 'Extension External',
    status: 'degraded',
    heartbeat: '31s',
    latency: '105ms',
    contract: 'edge.extension.v1',
    lastDirective: 'Suppress stale setup',
    lastAck: '09:39:58',
    queueDepth: 3,
    rejectedEvents: 1,
    detail: 'Browser extension bridge has stale acknowledgements.',
    tone: 'gold',
  },
];

export const policyStackRules: PolicyStackRule[] = [
  {
    id: 'stale-data',
    label: 'Stale data lockout',
    state: 'armed',
    strictness: 94,
    reason: 'Any provider gap over 12s blocks new risk.',
    effect: 'Block Buy / Watch only',
    tone: 'green',
  },
  {
    id: 'support-break',
    label: 'Support break',
    state: 'active on NVDA',
    strictness: 88,
    reason: 'Invalidation shelf is within 0.7 ATR.',
    effect: 'Stop trading / Reduce size',
    tone: 'red',
  },
  {
    id: 'gex-vex',
    label: 'GEX / VEX pressure',
    state: 'monitoring',
    strictness: 72,
    reason: 'Gamma pin makes breakout chasing lower quality.',
    effect: 'Require confirmation',
    tone: 'gold',
  },
  {
    id: 'correlation',
    label: 'Correlation cluster',
    state: 'watch',
    strictness: 67,
    reason: 'QQQ, NVDA, and AAPL exposure move together.',
    effect: 'Cap size',
    tone: 'cyan',
  },
  {
    id: 'drawdown',
    label: 'Daily drawdown',
    state: 'clear',
    strictness: 81,
    reason: 'Loss guard remains below trigger.',
    effect: 'Allow normal advisory',
    tone: 'green',
  },
];

export const outcomeAttribution: OutcomeAttribution[] = [
  { label: 'Bad entries blocked', value: '12', detail: '+$4.2K avoided drawdown estimate', tone: 'green' },
  { label: 'Allowed winners', value: '8', detail: 'Signals that passed policy stack', tone: 'green' },
  { label: 'False blocks', value: '2', detail: 'Good setups blocked by strict regime', tone: 'gold' },
  { label: 'Bots stopped in chop', value: '3', detail: 'Suppressed during range conditions', tone: 'cyan' },
  { label: 'Risk saves', value: '5', detail: 'Reduce/stop directives before support failed', tone: 'red' },
];

export const botLockouts: BotLockout[] = [
  { bot: 'Discord Trading Bot', scope: 'NVDA buys', state: 'blocked', reason: 'Support shelf weakening under risk heat', until: 'support reclaim', tone: 'red' },
  { bot: 'Auto-Crypto', scope: 'BTC breakouts', state: 'watch only', reason: 'Regime mismatch and liquidity drift', until: 'vol reset', tone: 'gold' },
  { bot: 'Futures', scope: 'NQ size', state: 'capped', reason: 'VEX expansion over threshold', until: 'next sweep', tone: 'cyan' },
  { bot: 'Sentinel Pulse', scope: 'SPY', state: 'allowed', reason: 'Breakout valid above support', until: 'corridor break', tone: 'green' },
];

export const nowTime = () => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const operationsViews: OperationViewItem[] = [
  { id: 'overview', label: 'Trading Overview', icon: Activity },
  { id: 'scanners', label: 'Scanner Workbench', icon: Search },
  { id: 'advisor', label: 'Advisor Health', icon: Gauge },
  { id: 'experience', label: 'Experience', icon: Zap },
  { id: 'protection', label: 'Protection Ops', icon: Shield },
  { id: 'pnl', label: 'P&L Tracking', icon: Target },
  { id: 'markets', label: 'Market Coverage', icon: SlidersHorizontal },
  { id: 'portfolio', label: 'Portfolio', icon: Bell },
  { id: 'settings', label: 'System Settings', icon: Save },
  { id: 'tutorials', label: 'Tutorials', icon: CheckCircle },
];

export const modes: Mode[] = ['command', 'charting', 'greeks', 'directives', 'protect', 'operations', 'settings'];

export const modeLabel = (mode: Mode) => {
  if (mode === 'charting') return 'Charting';
  if (mode === 'greeks') return 'Greeks';
  if (mode === 'directives') return 'Directives';
  if (mode === 'protect') return 'Protect';
  if (mode === 'operations') return 'Ops';
  return mode;
};
