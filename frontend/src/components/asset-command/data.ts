import {
  Activity,
  Bell,
  CheckCircle,
  Gauge,
  LineChart,
  Save,
  Search,
  Shield,
  SlidersHorizontal,
  Target,
  Zap,
} from 'lucide-react';
import type {
  CoreColorMetric,
  CoreHeatmapConfig,
  CoreLabelMode,
  CoreSizeMetric,
  CoreUniverse,
  EventFilter,
  EventLine,
  Metric,
  Mode,
  OperationViewItem,
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
  { id: 'system', label: 'System' },
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

export const nowTime = () => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

export const operationsViews: OperationViewItem[] = [
  { id: 'overview', label: 'Trading Overview', icon: Activity },
  { id: 'charts', label: 'Market Map', icon: LineChart },
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

export const modes: Mode[] = ['monitor', 'command', 'protect', 'operations', 'settings'];

export const modeLabel = (mode: Mode) => (mode === 'protect' ? 'Protect' : mode === 'operations' ? 'Ops' : mode);
