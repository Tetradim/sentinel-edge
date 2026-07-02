import { Component, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ErrorInfo, MouseEvent as ReactMouseEvent, ReactNode } from 'react';
import api from '../../lib/api';
import './SentinelEdgeUnifiedShell.css';

type ViewKey =
  | 'overview'
  | 'network'
  | 'risk'
  | 'breakouts'
  | 'ops'
  | 'settings';

type HeatMode = 'GEX' | 'VEX' | 'VOL';
type Severity = 'low' | 'medium' | 'high';
type GateMode = 'recommend_only' | 'paper' | 'live' | string;
type AdvisoryCommand =
  | 'Arm Trigger'
  | 'Risk Sweep'
  | 'Convert Alert'
  | 'Mute Watch'
  | 'Diagnostics'
  | 'Ack Alerts'
  | 'Lock Buys'
  | 'Advise Stops'
  | 'Reduce Size'
  | 'Inject Break'
  | 'Allow Guarded Breakout'
  | 'Block Buy Below Support'
  | 'Reduce Size On Heat Spike'
  | 'Resimulate Greeks'
  | 'Export Levels';
type OperationsModuleId =
  | 'overview'
  | 'scanners'
  | 'advisor'
  | 'experience'
  | 'protection'
  | 'pnl'
  | 'markets'
  | 'portfolio'
  | 'settings'
  | 'tutorials';

const TradingOverviewModule = lazy(() => import('../dashboards/TradingOverview').then((module) => ({ default: module.TradingOverview })));
const ScannerWorkbenchModule = lazy(() => import('../dashboards/ScannerWorkbench').then((module) => ({ default: module.ScannerWorkbench })));
const AdvisorHealthModule = lazy(() => import('../dashboards/AdvisorHealth').then((module) => ({ default: module.AdvisorHealth })));
const ExperienceDashboardModule = lazy(() => import('../dashboards/ExperienceDashboard').then((module) => ({ default: module.ExperienceDashboard })));
const ProtectionDashboardModule = lazy(() => import('../dashboards/ProtectionDashboard').then((module) => ({ default: module.ProtectionDashboard })));
const PnLTrackingModule = lazy(() => import('../dashboards/PnLTracking').then((module) => ({ default: module.PnLTracking })));
const MarketCoverageModule = lazy(() => import('../dashboards/MarketCoverage').then((module) => ({ default: module.MarketCoverage })));
const PortfolioAnalyticsModule = lazy(() => import('../dashboards/PortfolioAnalytics').then((module) => ({ default: module.PortfolioAnalytics })));
const SettingsDashboardModule = lazy(() => import('../dashboards/SettingsDashboard').then((module) => ({ default: module.SettingsDashboard })));
const TutorialsDashboardModule = lazy(() => import('../tutorials').then((module) => ({ default: module.TutorialsDashboard })));

const OPERATIONS_MODULES: { id: OperationsModuleId; label: string; detail: string }[] = [
  { id: 'overview', label: 'Trading Overview', detail: 'portfolio, decisions, breadth' },
  { id: 'scanners', label: 'Scanner Workbench', detail: 'watch intent and strategy kits' },
  { id: 'advisor', label: 'Advisor Health', detail: 'service and policy checks' },
  { id: 'experience', label: 'Experience', detail: 'operator workflow status' },
  { id: 'protection', label: 'Protection Ops', detail: 'guardrails and controls' },
  { id: 'pnl', label: 'P&L Tracking', detail: 'trade performance' },
  { id: 'markets', label: 'Market Coverage', detail: 'coverage and sessions' },
  { id: 'portfolio', label: 'Portfolio', detail: 'allocation analytics' },
  { id: 'settings', label: 'System Settings', detail: 'backend configuration' },
  { id: 'tutorials', label: 'Tutorials', detail: 'guided workflows' },
];

interface LoadState<T = any> {
  data: T | null;
  error: string | null;
  stale: boolean;
}

class ModuleErrorBoundary extends Component<
  { moduleId: string; children: ReactNode },
  { error: string | null }
> {
  state: { error: string | null } = { error: null };

  componentDidUpdate(previousProps: { moduleId: string }) {
    if (previousProps.moduleId !== this.props.moduleId && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ error: error.message || 'Module failed to render' });
    console.error('Operations module render failed', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="se-module-error">
          <strong>Module unavailable</strong>
          <span>{this.state.error}</span>
        </div>
      );
    }

    return this.props.children;
  }
}

interface EdgeSnapshot {
  health: LoadState;
  live: LoadState;
  ready: LoadState;
  providers: LoadState;
  marketDataProviders: LoadState;
  pulse: LoadState;
  pulseHandoffSchema: LoadState;
  queue: LoadState;
  account: LoadState;
  positions: LoadState;
  stats: LoadState;
  tickers: LoadState;
  decisions: LoadState;
  correlation: LoadState;
  automation: LoadState;
  killSwitch: LoadState;
  orb: LoadState;
  chart: LoadState;
  marketMap: LoadState;
  supportResistance: LoadState;
  markets: LoadState;
  rateLimit: LoadState;
}

interface BotRow {
  id: string;
  name: string;
  subtitle: string;
  repo: string;
  localPath: string;
  icon: string;
  color: string;
  health: number;
  risk: number;
  latencyMs: number;
  state: 'healthy' | 'watch' | 'blocked' | 'offline';
  lastDirective: string;
}

interface DecisionRow {
  id: string;
  time: string;
  symbol: string;
  action: 'allow' | 'block' | 'stop' | 'reduce' | 'watch' | 'sell';
  headline: string;
  detail: string;
  severity: Severity;
  confidence: number;
  source: string;
}

interface LevelRow {
  symbol: string;
  support: number;
  price: number;
  resistance: number;
  status: string;
  tone: 'ok' | 'warn' | 'bad' | 'blue' | 'gold';
  distancePct: number;
  source: string;
}

interface AuditRow {
  time: string;
  actor: string;
  event: string;
  outcome: string;
  tone: 'ok' | 'warn' | 'bad' | 'blue' | 'gold';
}

interface SeriesPoint {
  time: string;
  price: number;
  allow: number;
  risk: number;
  volume: number;
  heat: number;
}

interface ChartBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface NormalizedLevel {
  price: number;
  role: 'support' | 'resistance';
  label: string;
  source: string;
}

interface DerivedState {
  riskScore: number;
  portfolioHealth: number;
  alerts: number;
  decisionsToday: number;
  pulseGate: string;
  regime: string;
  regimeConfidence: number;
  lastPrice: number;
  support: number;
  resistance: number;
  levelSource: string;
  maxPain: number;
  netGamma: number;
  netDelta: number;
  botRows: BotRow[];
  decisionRows: DecisionRow[];
  levelRows: LevelRow[];
  auditRows: AuditRow[];
  series: SeriesPoint[];
}

const DEFAULT_SYMBOLS = ['SPY', 'QQQ', 'TSLA', 'NVDA', 'BTC-USD', 'ESU6'];

const BOT_CATALOG: Array<Omit<BotRow, 'health' | 'risk' | 'latencyMs' | 'state' | 'lastDirective'>> = [
  {
    id: 'sentinel-pulse',
    name: 'Sentinel Pulse',
    subtitle: 'Execution handoff worker',
    repo: 'Tetradim/Sentinel-Pulse',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-05-22\based-on-my-analysis-of-the\Sentinel-Pulse-branch-audit`,
    icon: 'P',
    color: 'purple',
  },
  {
    id: 'tandem-suite',
    name: 'Tandem Suite',
    subtitle: 'Options flow / signal layer',
    repo: 'Tetradim/Tandem-Suite',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-12\c-users-lite-os-openclaw-workspace\work\Tandem-Suite`,
    icon: 'T',
    color: 'cyan',
  },
  {
    id: 'sentinel-edge',
    name: 'Sentinel Edge',
    subtitle: 'Risk control brain',
    repo: 'Tetradim/Sentinel-Edge',
    localPath: String.raw`C:\Users\automation\GitBots\Sentinel-Edge`,
    icon: 'E',
    color: 'gold',
  },
  {
    id: 'consolidation',
    name: 'Consolidation',
    subtitle: 'Data aggregator',
    repo: 'Tetradim/Consolidation',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-17\files-mentioned-by-the-user-readme\work\Consolidation`,
    icon: 'C',
    color: 'green',
  },
  {
    id: 'apk-alerts',
    name: 'APK Alerts',
    subtitle: 'Mobile alert transport',
    repo: 'Tetradim/APK-Alerts',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-26\https-www-skills-sh-nextlevelbuilder-ui-2\work\APK-Alerts`,
    icon: 'A',
    color: 'red',
  },
  {
    id: 'darkpool-mon',
    name: 'Darkpool Mon',
    subtitle: 'Dark-pool monitor',
    repo: 'Tetradim/Darkpool-Mon',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-17\files-mentioned-by-the-user-pasted\work\Darkpool-Mon`,
    icon: 'D',
    color: 'purple',
  },
  {
    id: 'extension-external',
    name: 'Extension External',
    subtitle: 'Browser extension bridge',
    repo: 'Tetradim/Extension-External',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-24\th\work\Extension-External`,
    icon: 'X',
    color: 'amber',
  },
  {
    id: 'futures-bot',
    name: 'Futures Bot',
    subtitle: 'Futures execution target',
    repo: 'Tetradim/Futures',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-28\do-research-on-futures-in-the\work\futures-bot`,
    icon: 'F',
    color: 'blue',
  },
  {
    id: 'auto-crypto',
    name: 'Auto-Crypto',
    subtitle: 'Crypto execution target',
    repo: 'Tetradim/Auto-Crypto',
    localPath: String.raw`C:\Users\Lite OS\Documents\Codex\2026-06-17\start-by-researching-crypto-trading-bots\work\Auto-Crypto`,
    icon: '₿',
    color: 'orange',
  },
];

const EMPTY_LOAD: LoadState = { data: null, error: null, stale: false };

const INITIAL_SNAPSHOT: EdgeSnapshot = {
  health: EMPTY_LOAD,
  live: EMPTY_LOAD,
  ready: EMPTY_LOAD,
  providers: EMPTY_LOAD,
  marketDataProviders: EMPTY_LOAD,
  pulse: EMPTY_LOAD,
  pulseHandoffSchema: EMPTY_LOAD,
  queue: EMPTY_LOAD,
  account: EMPTY_LOAD,
  positions: EMPTY_LOAD,
  stats: EMPTY_LOAD,
  tickers: EMPTY_LOAD,
  decisions: EMPTY_LOAD,
  correlation: EMPTY_LOAD,
  automation: EMPTY_LOAD,
  killSwitch: EMPTY_LOAD,
  orb: EMPTY_LOAD,
  chart: EMPTY_LOAD,
  marketMap: EMPTY_LOAD,
  supportResistance: EMPTY_LOAD,
  markets: EMPTY_LOAD,
  rateLimit: EMPTY_LOAD,
};

const POLICY_STACK = [
  {
    id: 'breakout-confirm',
    name: 'Breakout confirmation',
    detail: 'Require close beyond resistance/support and confirmation volume.',
    enabled: true,
    tone: 'ok' as const,
  },
  {
    id: 'support-loss-stop',
    name: 'Support-loss stop',
    detail: 'Issue STOP TRADING or SELL directive when support fails.',
    enabled: true,
    tone: 'bad' as const,
  },
  {
    id: 'atr-position-size',
    name: 'ATR risk sizing',
    detail: 'Reduce size when ATR expansion breaches configured band.',
    enabled: true,
    tone: 'warn' as const,
  },
  {
    id: 'pulse-gate',
    name: 'Pulse handoff gates',
    detail: 'Global mode, confidence, cooldown, readiness, and circuit breaker.',
    enabled: true,
    tone: 'blue' as const,
  },
];

function createLoad<T = any>(data: T | null = null, error: string | null = null, stale = false): LoadState<T> {
  return { data, error, stale };
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Request failed';
}

async function settle<T>(promise: Promise<T>, previous?: LoadState<T>): Promise<LoadState<T>> {
  try {
    return createLoad(await promise, null, false);
  } catch (error) {
    return createLoad(previous?.data ?? null, errorMessage(error), Boolean(previous?.data));
  }
}

function toArray(value: any, keys: string[] = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    if (Array.isArray(value?.[key])) return value[key];
  }
  return [];
}

function objectRows(value: any) {
  if (!value || Array.isArray(value) || typeof value !== 'object') return [];
  return Object.entries(value).map(([key, item]) => (
    item && typeof item === 'object'
      ? { key, name: key, ...(item as Record<string, unknown>) }
      : { key, name: key, value: item }
  ));
}

function collectionRows(value: any, keys: string[] = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    const nested = value?.[key];
    if (Array.isArray(nested)) return nested;
    const rows = objectRows(nested);
    if (rows.length) return rows;
  }
  return objectRows(value);
}

function toNumber(value: any, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function formatMoney(value: number) {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function formatNumber(value: number, decimals = 2) {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function safePercent(value: number, decimals = 0) {
  return `${clamp(value, 0, 100).toFixed(decimals)}%`;
}

function statusFlag(value: any) {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value > 0;
  const raw = String(value ?? '').trim().toLowerCase();
  return ['true', '1', 'active', 'enabled', 'engaged', 'on'].includes(raw);
}

function isKillSwitchActive(payload: any) {
  return statusFlag(payload?.kill_switch_active ?? payload?.killSwitchActive ?? payload?.enabled ?? payload?.active ?? payload?.state);
}

function timeLabel(date = new Date()) {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function downloadJsonFile(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function actionFromPayload(value: any): DecisionRow['action'] {
  const raw = String(value?.action ?? value?.recommendation ?? value?.decision ?? value?.signal ?? value ?? '').toLowerCase();
  if (raw.includes('stop')) return 'stop';
  if (raw.includes('sell')) return 'sell';
  if (raw.includes('block') || raw.includes("don't") || raw.includes('dont')) return 'block';
  if (raw.includes('reduce') || raw.includes('trim')) return 'reduce';
  if (raw.includes('watch') || raw.includes('wait')) return 'watch';
  return 'allow';
}

function severityFor(action: DecisionRow['action'], confidence: number): Severity {
  if (action === 'stop' || action === 'sell' || action === 'block') return 'high';
  if (action === 'reduce' || confidence < 60) return 'medium';
  return 'low';
}

function priceForSymbol(symbol: string, index = 0) {
  const base: Record<string, number> = {
    SPY: 603.47,
    QQQ: 492.18,
    TSLA: 379.79,
    NVDA: 148.92,
    'BTC-USD': 106782,
    BTC: 106782,
    ES: 6023.25,
    ESU6: 6023.25,
    MSTR: 389.12,
    COIN: 266.8,
  };
  return base[symbol.toUpperCase()] ?? 100 + index * 37.5;
}

function parseTickerSymbols(tickerPayload: any) {
  const rows = toArray(tickerPayload, ['tickers', 'active_tickers', 'symbols', 'data']);
  const symbols = rows
    .map((row: any) => String(row?.symbol ?? row?.ticker ?? row?.name ?? row ?? '').trim().toUpperCase())
    .filter(Boolean);
  return Array.from(new Set([...symbols, ...DEFAULT_SYMBOLS]));
}

function payloadMatchesSymbol(payload: any, symbol: string) {
  const payloadSymbol = String(payload?.symbol ?? payload?.levels?.symbol ?? '').trim().toUpperCase();
  return !payloadSymbol || payloadSymbol === symbol.toUpperCase();
}

function normalizeChartBar(row: any): ChartBar | null {
  const open = Number(row?.open ?? row?.o);
  const high = Number(row?.high ?? row?.h);
  const low = Number(row?.low ?? row?.l);
  const close = Number(row?.close ?? row?.c ?? row?.price);
  const timestamp = String(row?.timestamp ?? row?.time ?? row?.date ?? '').trim();
  if (!timestamp || ![open, high, low, close].every((value) => Number.isFinite(value) && value > 0)) return null;
  const volume = Number(row?.volume ?? row?.v);
  return {
    timestamp,
    open,
    high,
    low,
    close,
    ...(Number.isFinite(volume) && volume >= 0 ? { volume } : {}),
  };
}

function extractChartBars(chartPayload: any): ChartBar[] {
  return toArray(chartPayload?.bars ?? chartPayload?.candles ?? chartPayload?.data, ['bars', 'candles'])
    .map(normalizeChartBar)
    .filter((bar): bar is ChartBar => Boolean(bar));
}

function buildSupportResistancePayload(snapshot: EdgeSnapshot, symbol: string) {
  const chart = snapshot.chart.data as any;
  if (!payloadMatchesSymbol(chart, symbol)) return null;
  const bars = extractChartBars(chart);
  const currentPrice = extractLastPrice(snapshot, symbol);
  if (!bars.length || !Number.isFinite(currentPrice) || currentPrice <= 0) return null;
  return {
    symbol,
    bars,
    current_price: currentPrice,
    settings: {
      opening_range_minutes: 30,
      swing_window: 2,
    },
    emit_event: false,
  };
}

function extractLastPrice(snapshot: EdgeSnapshot, symbol: string) {
  const map = snapshot.marketMap.data as any;
  const chart = snapshot.chart.data as any;
  const stats = snapshot.stats.data as any;
  const possible = [
    payloadMatchesSymbol(map, symbol) ? map?.price : null,
    payloadMatchesSymbol(map, symbol) ? map?.last_price : null,
    payloadMatchesSymbol(map, symbol) ? map?.current_price : null,
    payloadMatchesSymbol(map, symbol) ? map?.underlying_price : null,
    payloadMatchesSymbol(chart, symbol) ? chart?.last_price : null,
    payloadMatchesSymbol(chart, symbol) ? chart?.current_price : null,
    stats?.prices?.[symbol],
  ];
  for (const value of possible) {
    const n = Number(value);
    if (Number.isFinite(n) && n > 0) return n;
  }

  const bars = payloadMatchesSymbol(chart, symbol) ? extractChartBars(chart) : [];
  const close = bars[bars.length - 1]?.close;
  if (Number.isFinite(close) && close > 0) return close;

  return priceForSymbol(symbol);
}

function classifyLevelRole(row: any, price: number): NormalizedLevel['role'] | null {
  const role = String(row?.role ?? '').toLowerCase();
  if (role === 'support' || role === 'resistance') return role;
  const kind = String(row?.kind ?? row?.id ?? row?.label ?? '').toLowerCase();
  if (kind.includes('support') || kind.includes('low') || kind.includes('lower')) return 'support';
  if (kind.includes('resistance') || kind.includes('high') || kind.includes('upper')) return 'resistance';
  const levelPrice = Number(row?.price ?? row?.value ?? row?.level);
  if (Number.isFinite(levelPrice) && levelPrice > 0) return levelPrice <= price ? 'support' : 'resistance';
  return null;
}

function normalizeLevel(row: any, price: number, fallbackSource: string): NormalizedLevel | null {
  const levelPrice = Number(row?.price ?? row?.value ?? row?.level);
  if (!Number.isFinite(levelPrice) || levelPrice <= 0) return null;
  const role = classifyLevelRole(row, price);
  if (!role) return null;
  return {
    price: levelPrice,
    role,
    label: String(row?.label ?? row?.kind ?? row?.id ?? role),
    source: String(row?.source ?? fallbackSource),
  };
}

function supportResistanceLevels(snapshot: EdgeSnapshot, symbol: string, price: number): NormalizedLevel[] {
  const supportResistance = snapshot.supportResistance.data as any;
  if (!payloadMatchesSymbol(supportResistance, symbol)) return [];
  return toArray(supportResistance?.levels?.items, ['items'])
    .map((row: any) => normalizeLevel(row, price, 'S/R API'))
    .filter((level): level is NormalizedLevel => Boolean(level));
}

function chartWorkspaceLevels(snapshot: EdgeSnapshot, symbol: string, price: number): NormalizedLevel[] {
  const chart = snapshot.chart.data as any;
  if (!payloadMatchesSymbol(chart, symbol)) return [];
  return toArray(chart?.levels?.items, ['items'])
    .map((row: any) => normalizeLevel(row, price, 'chart workspace'))
    .filter((level): level is NormalizedLevel => Boolean(level));
}

function orbLevels(snapshot: EdgeSnapshot, symbol: string, price: number): NormalizedLevel[] {
  const orb = snapshot.orb.data as any;
  if (!payloadMatchesSymbol(orb, symbol)) return [];
  const rows = Object.entries(orb?.orb_levels ?? {}).flatMap(([timeframe, value]: [string, any]) => [
    { id: `${timeframe}_orb_high`, label: `${timeframe} ORB high`, kind: 'orb_high', price: value?.high, source: 'ORB' },
    { id: `${timeframe}_orb_low`, label: `${timeframe} ORB low`, kind: 'orb_low', price: value?.low, source: 'ORB' },
  ]);
  return rows
    .map((row) => normalizeLevel(row, price, 'ORB'))
    .filter((level): level is NormalizedLevel => Boolean(level));
}

function barDerivedLevels(snapshot: EdgeSnapshot, symbol: string, price: number): NormalizedLevel[] {
  const chart = snapshot.chart.data as any;
  const bars = payloadMatchesSymbol(chart, symbol) ? extractChartBars(chart) : [];
  if (!bars.length) return [];
  const recent = bars.slice(-90);
  const low = Math.min(...recent.map((bar) => bar.low));
  const high = Math.max(...recent.map((bar) => bar.high));
  const closes = recent.map((bar) => bar.close);
  const mean = closes.reduce((sum, close) => sum + close, 0) / Math.max(1, closes.length);
  return [
    { price: low, role: 'support', label: 'Recent low', source: 'OHLCV fallback' },
    { price: high, role: 'resistance', label: 'Recent high', source: 'OHLCV fallback' },
    {
      price: mean,
      role: mean <= price ? 'support' : 'resistance',
      label: '90-bar mean',
      source: 'OHLCV fallback',
    },
  ];
}

function nearestLevel(levels: NormalizedLevel[], price: number, role: NormalizedLevel['role']): NormalizedLevel | null {
  const filtered = levels.filter((level) => level.role === role);
  if (!filtered.length) return null;
  const preferred = role === 'support'
    ? filtered.filter((level) => level.price <= price).sort((a, b) => b.price - a.price)
    : filtered.filter((level) => level.price >= price).sort((a, b) => a.price - b.price);
  if (preferred.length) return preferred[0];
  return filtered.sort((a, b) => Math.abs(a.price - price) - Math.abs(b.price - price))[0];
}

function extractSupportResistance(snapshot: EdgeSnapshot, symbol: string, price: number) {
  const orb = snapshot.orb.data as any;
  const map = snapshot.marketMap.data as any;
  const levelSets = [
    { source: 'S/R API', levels: supportResistanceLevels(snapshot, symbol, price) },
    { source: 'chart workspace', levels: chartWorkspaceLevels(snapshot, symbol, price) },
    { source: 'ORB', levels: orbLevels(snapshot, symbol, price) },
    { source: 'OHLCV fallback', levels: barDerivedLevels(snapshot, symbol, price) },
  ];
  const active = levelSets.find((set) => nearestLevel(set.levels, price, 'support') && nearestLevel(set.levels, price, 'resistance'));
  const supportLevel = active ? nearestLevel(active.levels, price, 'support') : null;
  const resistanceLevel = active ? nearestLevel(active.levels, price, 'resistance') : null;
  const support = toNumber(
    supportLevel?.price
      ?? (payloadMatchesSymbol(orb, symbol) ? orb?.support ?? orb?.orb_low ?? orb?.low : null)
      ?? (payloadMatchesSymbol(map, symbol) ? map?.support ?? map?.levels?.support : null),
    price * 0.988,
  );
  const resistance = toNumber(
    resistanceLevel?.price
      ?? (payloadMatchesSymbol(orb, symbol) ? orb?.resistance ?? orb?.orb_high ?? orb?.high : null)
      ?? (payloadMatchesSymbol(map, symbol) ? map?.resistance ?? map?.levels?.resistance : null),
    price * 1.012,
  );
  const maxPain = toNumber(payloadMatchesSymbol(map, symbol) ? map?.max_pain ?? map?.maxPain : null, (support + resistance) / 2);
  return { support, resistance, maxPain, source: active?.source ?? 'price fallback' };
}

function buildDecisions(payload: any, symbol: string): DecisionRow[] {
  const rows = toArray(payload, ['decisions', 'recent_decisions', 'recommendations', 'items']);
  const mapped = rows.slice(0, 20).map((row: any, index: number) => {
    const action = actionFromPayload(row);
    const confidence = clamp(toNumber(row?.confidence ?? row?.score ?? row?.probability, 72 + (index % 5) * 4), 0, 100);
    const severity = String(row?.severity ?? '').toLowerCase() as Severity;
    return {
      id: String(row?.id ?? row?.timestamp ?? `decision-${index}`),
      time: String(row?.time ?? row?.timestamp ?? row?.created_at ?? timeLabel(new Date(Date.now() - index * 180000))),
      symbol: String(row?.symbol ?? row?.ticker ?? symbol).toUpperCase(),
      action,
      headline: String(row?.headline ?? row?.reason ?? row?.title ?? labelForAction(action)),
      detail: String(row?.detail ?? row?.explanation ?? row?.message ?? detailForAction(action)),
      severity: ['low', 'medium', 'high'].includes(severity) ? severity : severityFor(action, confidence),
      confidence,
      source: String(row?.source ?? row?.engine ?? 'Sentinel Edge'),
    } satisfies DecisionRow;
  });

  if (mapped.length) return mapped;
  return fallbackDecisions(symbol);
}

function labelForAction(action: DecisionRow['action']) {
  switch (action) {
    case 'block':
      return 'Block buy';
    case 'stop':
      return 'Stop trading';
    case 'sell':
      return 'Support broken — sell';
    case 'reduce':
      return 'Reduce risk';
    case 'watch':
      return 'Watch only';
    default:
      return 'Allow trade';
  }
}

function detailForAction(action: DecisionRow['action']) {
  switch (action) {
    case 'block':
      return 'Breakout quality failed policy stack.';
    case 'stop':
      return 'Support broken and volatility expanding.';
    case 'sell':
      return 'Support lost with weak recovery attempt.';
    case 'reduce':
      return 'Position size exceeds current ATR risk envelope.';
    case 'watch':
      return 'Range compression detected; waiting for confirmation.';
    default:
      return 'Risk gates clear and trend alignment acceptable.';
  }
}

function fallbackDecisions(symbol: string): DecisionRow[] {
  const now = Date.now();
  const rows: DecisionRow[] = [
    {
      id: 'fallback-allow',
      time: timeLabel(new Date(now - 30_000)),
      symbol,
      action: 'allow',
      headline: 'Allow trade',
      detail: 'Trend, liquidity, and support gates currently aligned.',
      severity: 'low',
      confidence: 78,
      source: 'Policy stack',
    },
    {
      id: 'fallback-watch',
      time: timeLabel(new Date(now - 130_000)),
      symbol: 'QQQ',
      action: 'watch',
      headline: 'Watch resistance',
      detail: 'Price approaching upper band; breakout requires volume confirmation.',
      severity: 'medium',
      confidence: 66,
      source: 'Breakout radar',
    },
    {
      id: 'fallback-reduce',
      time: timeLabel(new Date(now - 270_000)),
      symbol: 'TSLA',
      action: 'reduce',
      headline: 'Reduce size',
      detail: 'ATR and correlation risk are above preferred envelope.',
      severity: 'medium',
      confidence: 72,
      source: 'Risk engine',
    },
    {
      id: 'fallback-block',
      time: timeLabel(new Date(now - 410_000)),
      symbol: 'NVDA',
      action: 'block',
      headline: 'Block buy',
      detail: 'Momentum is extended into resistance with poor reward/risk.',
      severity: 'high',
      confidence: 84,
      source: 'Decision engine',
    },
    {
      id: 'fallback-stop',
      time: timeLabel(new Date(now - 620_000)),
      symbol: 'ESU6',
      action: 'stop',
      headline: 'Stop trading',
      detail: 'Support break plus expanding volatility; automation suppressed.',
      severity: 'high',
      confidence: 88,
      source: 'Safety gate',
    },
  ];
  return rows;
}

function buildLevels(symbols: string[], snapshot: EdgeSnapshot, selected: string): LevelRow[] {
  const last = extractLastPrice(snapshot, selected);
  const sr = extractSupportResistance(snapshot, selected, last);
  const orderedSymbols = Array.from(new Set([selected, ...symbols])).slice(0, 9);
  return orderedSymbols.map((symbol, index) => {
    const price = symbol === selected ? last : priceForSymbol(symbol, index) * (1 + Math.sin(index + Date.now() / 1000000) * 0.006);
    const support = symbol === selected ? sr.support : price * (0.985 - index * 0.0006);
    const resistance = symbol === selected ? sr.resistance : price * (1.012 + index * 0.0007);
    const distToSupport = ((price - support) / price) * 100;
    const distToResistance = ((resistance - price) / price) * 100;
    const status = price < support
      ? 'Support broken'
      : price > resistance
        ? 'Breakout confirmed'
        : distToResistance < 0.55
          ? 'At resistance'
          : distToSupport < 0.55
            ? 'Testing support'
            : 'In range';
    const tone: LevelRow['tone'] = status.includes('broken')
      ? 'bad'
      : status.includes('resistance') || status.includes('support')
        ? 'warn'
        : status.includes('Breakout')
          ? 'blue'
          : 'ok';
    return {
      symbol,
      support,
      price,
      resistance,
      status,
      tone,
      distancePct: Math.min(distToSupport, distToResistance),
      source: symbol === selected ? sr.source : 'watchlist fallback',
    };
  });
}

function buildBots(snapshot: EdgeSnapshot, decisions: DecisionRow[]): BotRow[] {
  const ready = snapshot.ready.data as any;
  const pulse = snapshot.pulse.data as any;
  const providers = snapshot.providers.data as any;
  const providerRows = collectionRows(providers, ['providers', 'items', 'health']);
  const pulseHealthy = Boolean(pulse?.available ?? pulse?.healthy ?? pulse?.connected ?? pulse?.ok ?? false);
  const blockerCount = decisions.filter((row) => row.severity === 'high').length;

  return BOT_CATALOG.map((bot, index) => {
    const seed = hash(`${bot.id}-${JSON.stringify(snapshot.live.data ?? {})}`);
    let health = 82 + (seed % 17) - blockerCount * 2;
    if (bot.id === 'sentinel-edge') health = ready?.ready === false ? 62 : 96;
    if (bot.id === 'sentinel-pulse') health = pulseHealthy ? 91 : 55;
    if (bot.id === 'consolidation' && providerRows.length) health = 88;
    health = clamp(health, 5, 100);
    const risk = clamp(100 - health + blockerCount * 8 + (index % 3) * 5, 0, 100);
    const state: BotRow['state'] = health < 45 ? 'offline' : risk > 68 ? 'blocked' : risk > 38 ? 'watch' : 'healthy';
    const lastDirective = state === 'blocked'
      ? 'Stop trading that'
      : state === 'watch'
        ? 'Do not buy without confirmation'
        : bot.id === 'sentinel-edge'
          ? 'Policy stack enforcing gates'
          : 'Normal advisory flow';
    return {
      ...bot,
      health,
      risk,
      latencyMs: 8 + (seed % 47),
      state,
      lastDirective,
    };
  });
}

function buildAudit(snapshot: EdgeSnapshot, decisions: DecisionRow[], gateMode: GateMode): AuditRow[] {
  const rows: AuditRow[] = decisions.slice(0, 5).map((decision) => ({
    time: decision.time,
    actor: decision.source,
    event: `${decision.symbol} ${labelForAction(decision.action)}`,
    outcome: decision.detail,
    tone: decision.severity === 'high' ? 'bad' : decision.severity === 'medium' ? 'warn' : 'ok',
  }));

  rows.push(
    {
      time: timeLabel(new Date()),
      actor: 'Automation Gate',
      event: `Mode: ${String(gateMode).replace('_', ' ')}`,
      outcome: 'Execution handoff remains separated from recommendation display.',
      tone: gateMode === 'live' ? 'warn' : 'blue',
    },
    {
      time: timeLabel(new Date(Date.now() - 80_000)),
      actor: 'Readiness Guard',
      event: (snapshot.ready.data as any)?.ready === false ? 'Blockers detected' : 'Runtime ready',
      outcome: snapshot.ready.error ? `Stale data: ${snapshot.ready.error}` : 'Readiness checks surfaced to operator console.',
      tone: (snapshot.ready.data as any)?.ready === false ? 'bad' : 'ok',
    },
  );
  return rows.slice(0, 8);
}

function buildSeries(symbol: string, lastPrice: number, support: number, resistance: number): SeriesPoint[] {
  const rng = mulberry(hash(symbol) || 1);
  const points: SeriesPoint[] = [];
  const count = 160;
  let price = lastPrice * (0.985 + rng() * 0.016);
  for (let i = 0; i < count; i += 1) {
    const t = i / Math.max(1, count - 1);
    const wave = Math.sin(t * Math.PI * 4.7) * lastPrice * 0.0022 + Math.sin(t * Math.PI * 11) * lastPrice * 0.00065;
    price += (lastPrice - price) * 0.018 + (rng() - 0.5) * lastPrice * 0.0007;
    const allow = 50 + Math.sin(t * Math.PI * 2.4 - 0.7) * 24 + t * 16 + (rng() - 0.5) * 8;
    const risk = 45 + Math.sin(t * Math.PI * 3.3 + 0.8) * 21 - t * 10 + (rng() - 0.5) * 9;
    const heat = 45 + Math.sin((price - support) / Math.max(1, resistance - support) * Math.PI) * 48 + (rng() - 0.5) * 22;
    points.push({
      time: `${String(9 + Math.floor(i / 24)).padStart(2, '0')}:${String((i * 3) % 60).padStart(2, '0')}`,
      price: price + wave,
      allow: clamp(allow, 0, 100),
      risk: clamp(risk, 0, 100),
      volume: 40 + rng() * 180 + (i < 12 || i > count - 18 ? 90 : 0),
      heat: clamp(heat, 0, 100),
    });
  }
  points[points.length - 1].price = lastPrice;
  return points;
}

function deriveState(snapshot: EdgeSnapshot, symbol: string): DerivedState {
  const tickerSymbols = parseTickerSymbols(snapshot.tickers.data);
  const decisions = buildDecisions(snapshot.decisions.data, symbol);
  const lastPrice = extractLastPrice(snapshot, symbol);
  const { support, resistance, maxPain, source: levelSource } = extractSupportResistance(snapshot, symbol, lastPrice);
  const series = buildSeries(symbol, lastPrice, support, resistance);
  const highRiskCount = decisions.filter((row) => row.severity === 'high').length;
  const mediumRiskCount = decisions.filter((row) => row.severity === 'medium').length;
  const readyData = snapshot.ready.data as any;
  const pulseData = snapshot.pulse.data as any;
  const killData = snapshot.killSwitch.data as any;
  const automation = snapshot.automation.data as any;
  const gateMode = String(automation?.mode ?? automation?.settings?.mode ?? 'recommend_only');
  const killActive = isKillSwitchActive(killData);
  const readyPenalty = readyData?.ready === false ? 18 : 0;
  const pulsePenalty = pulseData && !(pulseData.available ?? pulseData.connected ?? pulseData.healthy ?? true) ? 10 : 0;
  const riskScore = clamp(16 + highRiskCount * 15 + mediumRiskCount * 6 + readyPenalty + pulsePenalty + (killActive ? 32 : 0), 0, 100);
  const portfolioHealth = clamp(96 - riskScore * 0.58 - (snapshot.account.error ? 7 : 0), 0, 100);
  const regimeConfidence = clamp(82 - riskScore * 0.38 + (lastPrice > maxPain ? 6 : -2), 0, 100);
  const regime = lastPrice > resistance
    ? 'Breakout Bullish'
    : lastPrice < support
      ? 'Support Failed'
      : lastPrice > maxPain
        ? 'Trending Bullish'
        : 'Range / Neutral';
  const netGamma = (lastPrice - maxPain) * 1_750_000 + (resistance - support) * 320_000;
  const netDelta = decisions.reduce((acc, row) => {
    const sign = row.action === 'allow' ? 1 : row.action === 'watch' ? 0.25 : -1;
    return acc + sign * row.confidence * 1_000_000;
  }, 0);
  const levelRows = buildLevels(tickerSymbols, snapshot, symbol);
  const botRows = buildBots(snapshot, decisions);
  const auditRows = buildAudit(snapshot, decisions, gateMode);
  const pulseGate = killActive ? 'KILL SWITCH' : gateMode === 'live' ? 'Live gated' : gateMode === 'paper' ? 'Paper gated' : 'Recommend only';

  return {
    riskScore,
    portfolioHealth,
    alerts: highRiskCount + mediumRiskCount,
    decisionsToday: decisions.length + toNumber((snapshot.stats.data as any)?.recommendation_count ?? (snapshot.stats.data as any)?.decisions_today, 0),
    pulseGate,
    regime,
    regimeConfidence,
    lastPrice,
    support,
    resistance,
    levelSource,
    maxPain,
    netGamma,
    netDelta,
    botRows,
    decisionRows: decisions,
    levelRows,
    auditRows,
    series,
  };
}

function hash(input: string) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h >>> 0);
}

function mulberry(seed: number) {
  let t = seed >>> 0;
  return function rng() {
    t += 0x6D2B79F5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function statusTone(state: BotRow['state']) {
  if (state === 'healthy') return 'ok';
  if (state === 'watch') return 'warn';
  return 'bad';
}

export default function SentinelEdgeUnifiedShell() {
  const [view, setView] = useState<ViewKey>('overview');
  const [symbol, setSymbol] = useState('SPY');
  const [heatMode, setHeatMode] = useState<HeatMode>('GEX');
  const [snapshot, setSnapshot] = useState<EdgeSnapshot>(INITIAL_SNAPSHOT);
  const [livePolling, setLivePolling] = useState(true);
  const [loading, setLoading] = useState(false);
  const [selectedBot, setSelectedBot] = useState('sentinel-edge');
  const [expanded, setExpanded] = useState<'heatmap' | 'gamma' | 'breakout' | 'risk' | 'levels' | null>(null);
  const [commandResult, setCommandResult] = useState<string>('Idle');
  const [tickerInput, setTickerInput] = useState(symbol);
  const [gateMode, setGateMode] = useState<GateMode>('recommend_only');
  const [operationsModule, setOperationsModule] = useState<OperationsModuleId>('overview');
  const [predictionHorizon, setPredictionHorizon] = useState('30m');
  const [customHorizon, setCustomHorizon] = useState('90m');
  const [operatorAuditRows, setOperatorAuditRows] = useState<AuditRow[]>([]);
  const refreshSequenceRef = useRef(0);

  const derived = useMemo(() => deriveState(snapshot, symbol), [snapshot, symbol]);
  const auditRows = useMemo(() => [...operatorAuditRows, ...derived.auditRows].slice(0, 30), [operatorAuditRows, derived.auditRows]);
  const symbols = useMemo(() => parseTickerSymbols(snapshot.tickers.data), [snapshot.tickers.data]);
  const selectedBotRow = derived.botRows.find((bot) => bot.id === selectedBot) ?? derived.botRows[0];
  const errors = (Object.entries(snapshot) as Array<[keyof EdgeSnapshot, LoadState]>)
    .filter(([, state]) => state.error)
    .map(([key, state]) => `${String(key)}: ${state.error}`);

  const refresh = useCallback(async () => {
    const refreshSequence = refreshSequenceRef.current + 1;
    refreshSequenceRef.current = refreshSequence;
    setLoading(true);
    setCommandResult('Refreshing Edge state...');
    setSnapshot((previous) => previous);
    const [
      health,
      live,
      ready,
      providers,
      marketDataProviders,
      pulse,
      pulseHandoffSchema,
      queue,
      account,
      positions,
      stats,
      tickers,
      decisions,
      correlation,
      automation,
      killSwitch,
      orb,
      chart,
      marketMap,
      markets,
      rateLimit,
    ] = await Promise.all([
      settle(api.getHealth(), snapshot.health),
      settle(api.getLiveness(), snapshot.live),
      settle(api.getReadiness(), snapshot.ready),
      settle(api.getProviderHealth(), snapshot.providers),
      settle(api.getMarketDataProviders(), snapshot.marketDataProviders),
      settle(api.getPulseStatus(), snapshot.pulse),
      settle(api.getPulseHandoffSchema(), snapshot.pulseHandoffSchema),
      settle(api.getPulseQueue(), snapshot.queue),
      settle(api.getPulseAccount(), snapshot.account),
      settle(api.getPulsePositions(), snapshot.positions),
      settle(api.getStats(), snapshot.stats),
      settle(api.getTickers(), snapshot.tickers),
      settle(api.getDecisions(), snapshot.decisions),
      settle(api.getCorrelation(), snapshot.correlation),
      settle(api.getAutomationStatus(), snapshot.automation),
      settle(api.getKillSwitchStatus(), snapshot.killSwitch),
      settle(api.getOrbLevels(symbol), snapshot.orb),
      settle(api.getChartWorkspace(symbol, { limit: 180 }), snapshot.chart),
      settle(api.getMarketMapContext(symbol), snapshot.marketMap),
      settle(api.getMarkets(), snapshot.markets),
      settle(api.getRateLimitStatus(), snapshot.rateLimit),
    ]);
    const next: EdgeSnapshot = {
      health,
      live,
      ready,
      providers,
      marketDataProviders,
      pulse,
      pulseHandoffSchema,
      queue,
      account,
      positions,
      stats,
      tickers,
      decisions,
      correlation,
      automation,
      killSwitch,
      orb,
      chart,
      marketMap,
      supportResistance: snapshot.supportResistance,
      markets,
      rateLimit,
    };
    if (refreshSequenceRef.current !== refreshSequence) return;
    const supportResistancePayload = buildSupportResistancePayload(next, symbol);
    next.supportResistance = supportResistancePayload
      ? await settle(api.evaluateSupportResistance(supportResistancePayload), snapshot.supportResistance)
      : createLoad(snapshot.supportResistance.data, 'Chart bars unavailable for S/R evaluation', Boolean(snapshot.supportResistance.data));
    if (refreshSequenceRef.current !== refreshSequence) return;
    setSnapshot(next);
    const errorCount = Object.values(next).filter((state) => state.error).length;
    setCommandResult(errorCount ? `Refreshed with ${errorCount} stale/fallback source(s)` : 'Live data refreshed');
    setLoading(false);
  }, [snapshot, symbol]);

  useEffect(() => {
    refresh();
  }, [symbol]);

  useEffect(() => {
    if (!livePolling) return undefined;
    const id = window.setInterval(() => {
      refresh();
    }, 7000);
    return () => window.clearInterval(id);
  }, [livePolling, refresh]);

  useEffect(() => {
    const mode = String((snapshot.automation.data as any)?.mode ?? (snapshot.automation.data as any)?.settings?.mode ?? 'recommend_only');
    setGateMode(mode);
  }, [snapshot.automation.data]);

  const runCommand = useCallback(async (label: string, callback: () => Promise<any>) => {
    setCommandResult(`${label}...`);
    try {
      await callback();
      setCommandResult(`${label} complete`);
      await refresh();
    } catch (error) {
      setCommandResult(`${label} failed: ${errorMessage(error)}`);
    }
  }, [refresh]);

  const handleModeUpdate = (mode: GateMode) => {
    setGateMode(mode);
    runCommand(`Setting handoff mode to ${mode}`, async () => {
      await api.updateAutomationSettings({ mode });
    });
  };

  const handleAddTicker = () => {
    const next = tickerInput.trim().toUpperCase();
    if (!next) return;
    runCommand(`Adding ${next}`, async () => api.addTicker(next));
    setSymbol(next);
  };

  const handleRemoveTicker = () => {
    if (!window.confirm(`Remove ${symbol} from the active Sentinel Edge ticker list?`)) return;
    runCommand(`Removing ${symbol}`, async () => api.removeTicker(symbol));
  };

  const handleKillSwitch = () => {
    const active = isKillSwitchActive(snapshot.killSwitch.data);
    const next = !active;
    const message = next
      ? 'Enable global kill switch? This should suppress handoffs and protection workflows.'
      : 'Disable global kill switch? Only do this when the system is ready.';
    if (!window.confirm(message)) return;
    runCommand(next ? 'Enabling kill switch' : 'Disabling kill switch', async () => api.toggleKillSwitch(next));
  };

  const recordOperatorAction = (event: string, outcome: string, tone: AuditRow['tone'] = 'blue') => {
    setCommandResult(`${event}: ${outcome}`);
    setOperatorAuditRows((rows) => [
      {
        time: timeLabel(new Date()),
        actor: 'Operator',
        event,
        outcome,
        tone,
      },
      ...rows,
    ].slice(0, 30));
  };

  const handleAdvisoryCommand = (command: AdvisoryCommand) => {
    const outcomes: Record<AdvisoryCommand, string> = {
      'Arm Trigger': `${symbol} advisory trigger armed for ${predictionHorizon}. Pulse handoff still gated by policy.`,
      'Risk Sweep': `${symbol} risk sweep queued against live support/resistance, heat, and gate state.`,
      'Convert Alert': `${symbol} alert converted into advisory watch context.`,
      'Mute Watch': `${symbol} watch muted locally for this operator session.`,
      Diagnostics: 'Runtime diagnostics reviewed across backend health, readiness, providers, Pulse, and rate limits.',
      'Ack Alerts': 'Visible alert stack acknowledged locally for this operator session.',
      'Lock Buys': `${symbol} buy-side advisory posture locked behind support/resistance and policy gates.`,
      'Advise Stops': `${symbol} stop review staged from current support, ATR, and Pulse position context.`,
      'Reduce Size': `${symbol} size-reduction advisory recorded for high-heat review.`,
      'Inject Break': `${symbol} synthetic breakout/breakdown scenario injected into local operator review.`,
      'Allow Guarded Breakout': `${symbol} guarded breakout directive staged; Pulse handoff still requires policy gates.`,
      'Block Buy Below Support': `${symbol} buy-side block recorded below current support.`,
      'Reduce Size On Heat Spike': `${symbol} heat-spike size-reduction directive staged for review.`,
      'Resimulate Greeks': `${symbol} Greek surface resimulation requested for local review.`,
      'Export Levels': `${symbol} key-level export recorded in the audit trail.`,
    };
    const tone: AuditRow['tone'] = command === 'Reduce Size' || command === 'Lock Buys' || command === 'Reduce Size On Heat Spike'
      ? 'warn'
      : command === 'Risk Sweep' || command === 'Export Levels'
        ? 'gold'
        : 'blue';
    recordOperatorAction(command, outcomes[command], tone);
  };

  const handlePredictionHorizon = (horizon: string) => {
    const next = horizon.trim() || '30m';
    setPredictionHorizon(next);
    recordOperatorAction('Prediction Horizon', `${symbol} forecast window set to ${next}.`, 'blue');
  };

  const exportAudit = () => {
    downloadJsonFile(`sentinel-edge-audit-${symbol}-${Date.now()}.json`, {
      exported_at: new Date().toISOString(),
      symbol,
      derived,
      operator_audit_rows: operatorAuditRows,
      audit_rows: auditRows,
      snapshot_errors: errors,
    });
  };

  const saveHeatmapSnapshot = useCallback(() => {
    downloadJsonFile(`sentinel-edge-heatmap-${symbol}-${heatMode}-${Date.now()}.json`, {
      exported_at: new Date().toISOString(),
      symbol,
      mode: heatMode,
      current_price: derived.lastPrice,
      support: derived.support,
      resistance: derived.resistance,
      level_source: derived.levelSource,
      max_pain: derived.maxPain,
      risk_score: derived.riskScore,
      regime: derived.regime,
      regime_confidence: derived.regimeConfidence,
      levels: derived.levelRows,
      series: derived.series,
    });
    recordOperatorAction('Save Heatmap', `${symbol} ${heatMode} heatmap snapshot exported with ${derived.series.length} plotted points.`, 'gold');
    setCommandResult(`${symbol} ${heatMode} heatmap snapshot exported`);
  }, [derived, heatMode, recordOperatorAction, symbol]);

  const copySnapshot = async () => {
    const payload = JSON.stringify({ symbol, risk: derived.riskScore, regime: derived.regime, pulseGate: derived.pulseGate }, null, 2);
    await navigator.clipboard?.writeText(payload);
    setCommandResult('Snapshot copied to clipboard');
  };

  return (
    <div className="se-shell">
      <aside className="se-sidebar">
        <Brand />
        <nav className="se-nav" aria-label="Sentinel Edge views">
          <NavButton active={view === 'overview'} icon="⌘" label="Overview" onClick={() => setView('overview')} />
          <NavButton active={view === 'network'} icon="☷" label="Bot Network" onClick={() => setView('network')} />
          <NavButton active={view === 'risk'} icon="◈" label="Risk Engine" onClick={() => setView('risk')} />
          <NavButton active={view === 'breakouts'} icon="↗" label="Breakouts" onClick={() => setView('breakouts')} />
          <NavButton active={view === 'ops'} icon="⚙" label="Protection Ops" onClick={() => setView('ops')} />
          <NavButton active={view === 'settings'} icon="☰" label="Settings" onClick={() => setView('settings')} />
        </nav>

        <div className="se-side-card">
          <h3>Sentinel Status</h3>
          <StatusLine label="Core" value={(snapshot.ready.data as any)?.ready === false ? 'BLOCKED' : 'OPERATIONAL'} tone={(snapshot.ready.data as any)?.ready === false ? 'bad' : 'ok'} />
          <StatusLine label="Mode" value={derived.pulseGate} tone={derived.pulseGate === 'KILL SWITCH' ? 'bad' : gateMode === 'live' ? 'warn' : 'blue'} />
          <StatusLine label="Latency" value={`${(snapshot.rateLimit.data as any)?.reset_seconds ?? selectedBotRow?.latencyMs ?? 14}ms`} tone="ok" />
          <StatusLine label="Source" value={errors.length ? 'Fallback' : 'Live'} tone={errors.length ? 'warn' : 'ok'} />
        </div>

        <div className="se-side-card se-side-card-grow">
          <h3>Selected Bot</h3>
          {selectedBotRow && (
            <div className="se-selected-bot">
              <div className={`se-bot-icon ${selectedBotRow.color}`}>{selectedBotRow.icon}</div>
              <strong>{selectedBotRow.name}</strong>
              <small>{selectedBotRow.subtitle}</small>
              <p>{selectedBotRow.lastDirective}</p>
              <div className="se-meter"><span style={{ width: `${selectedBotRow.health}%` }} /></div>
              <StatusLine label="Health" value={safePercent(selectedBotRow.health)} tone={statusTone(selectedBotRow.state) as any} />
              <StatusLine label="Risk" value={safePercent(selectedBotRow.risk)} tone={selectedBotRow.risk > 68 ? 'bad' : selectedBotRow.risk > 38 ? 'warn' : 'ok'} />
            </div>
          )}
        </div>

        <div className="se-side-footer">
          <button type="button" className="se-action se-action-wide" onClick={copySnapshot}>Copy Status Snapshot</button>
          <button type="button" className="se-action se-action-wide" onClick={exportAudit}>Export Audit Log</button>
        </div>
      </aside>

      <main className="se-main">
        <header className="se-topbar">
          <div className="se-mission">
            <div className="se-slash" />
            <div>
              <h2>Sentinel Edge</h2>
              <p>Protect capital. Enforce discipline. Tell the bot ecosystem when not to act.</p>
            </div>
          </div>
          <div className="se-top-actions">
            <label className="se-symbol-box">
              <span>Symbol</span>
              <input value={tickerInput} onChange={(event) => setTickerInput(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && handleAddTicker()} />
            </label>
            <select className="se-select" value={symbol} onChange={(event) => { setSymbol(event.target.value); setTickerInput(event.target.value); }}>
              {symbols.map((item) => <option key={item}>{item}</option>)}
            </select>
            <div className="se-segment" role="group" aria-label="Heat map mode">
              {(['GEX', 'VEX', 'VOL'] as HeatMode[]).map((mode) => (
                <button key={mode} type="button" className={heatMode === mode ? 'active' : ''} onClick={() => setHeatMode(mode)}>{mode}</button>
              ))}
            </div>
            <button type="button" className={`se-action ${livePolling ? 'live' : ''}`} onClick={() => setLivePolling((value) => !value)}>{livePolling ? 'Live' : 'Paused'}</button>
            <button type="button" className="se-action" onClick={refresh} disabled={loading}>{loading ? 'Syncing…' : 'Refresh'}</button>
            <button type="button" className="se-action danger" onClick={handleKillSwitch}>Kill Switch</button>
          </div>
        </header>

        {errors.length > 0 && (
          <div className="se-warning-strip" role="status">
            <strong>Partial refresh warning:</strong> {errors.slice(0, 3).join(' • ')}{errors.length > 3 ? ` • +${errors.length - 3} more` : ''}
          </div>
        )}

        <section className="se-kpi-row">
          <KpiCard label="Risk Score" value={`${derived.riskScore.toFixed(0)} / 100`} sub={derived.riskScore > 65 ? 'High risk' : derived.riskScore > 35 ? 'Guarded' : 'Low risk'} tone={derived.riskScore > 65 ? 'bad' : derived.riskScore > 35 ? 'warn' : 'ok'} />
          <KpiCard label="Portfolio Health" value={safePercent(derived.portfolioHealth)} sub="Pulse / local view" tone={derived.portfolioHealth > 78 ? 'ok' : derived.portfolioHealth > 55 ? 'warn' : 'bad'} />
          <KpiCard label="Active Alerts" value={String(derived.alerts)} sub="Requires operator review" tone={derived.alerts ? 'warn' : 'ok'} />
          <KpiCard label="Bots Monitored" value={`${derived.botRows.filter((bot) => bot.state !== 'offline').length} / ${derived.botRows.length}`} sub="Ecosystem mesh" tone="blue" />
          <KpiCard label="Decisions Today" value={String(derived.decisionsToday)} sub="Recommendations + actions" tone="gold" />
          <KpiCard label="Pulse Gate" value={derived.pulseGate} sub={commandResult} tone={derived.pulseGate === 'KILL SWITCH' ? 'bad' : gateMode === 'live' ? 'warn' : 'blue'} small />
        </section>

        {view === 'overview' && (
          <OverviewGrid
            symbol={symbol}
            heatMode={heatMode}
            derived={derived}
            selectedBot={selectedBot}
            setSelectedBot={setSelectedBot}
            setExpanded={setExpanded}
            onPause={() => runCommand('Pausing scheduler', () => api.pauseScheduler())}
            onResume={() => runCommand('Resuming scheduler', () => api.resumeScheduler())}
            onExport={exportAudit}
            onRefreshHeatmap={refresh}
            onSaveHeatmap={saveHeatmapSnapshot}
          />
        )}

        {view === 'network' && (
          <section className="se-grid se-grid-network">
            <Panel title="Bot Ecosystem Mesh" meta="Advisory bus / dependency map" className="se-network-wide" onExpand={() => setExpanded('risk')}>
              <BotMesh bots={derived.botRows} selected={selectedBot} onSelect={setSelectedBot} />
            </Panel>
            <Panel title="Bot Directive Matrix" meta="Sentinel says what each bot may do">
              <BotDirectiveTable bots={derived.botRows} />
            </Panel>
            <Panel title="Recent Sentinel Decisions" meta="Block / allow / reduce / stop">
              <DecisionFeed rows={derived.decisionRows} />
            </Panel>
          </section>
        )}

        {view === 'risk' && (
          <section className="se-grid se-grid-risk">
            <Panel title="Risk Exposure Brain" meta="Composite risk model" onExpand={() => setExpanded('risk')}>
              <RiskPanel derived={derived} />
            </Panel>
            <Panel title="Policy Stack" meta="Active guardrails">
              <PolicyStack />
            </Panel>
            <Panel title="Gamma by Strike" meta="Profile + spot line" onExpand={() => setExpanded('gamma')}>
              <GammaStrikeChart symbol={symbol} derived={derived} />
            </Panel>
            <Panel title="Audit Log" meta="Explainable decisions" className="se-wide">
              <AuditLog rows={auditRows} />
            </Panel>
          </section>
        )}

        {view === 'breakouts' && (
          <section className="se-grid se-grid-breakouts">
            <Panel title="Breakout / Breakdown Radar" meta={`${symbol} support, resistance, confirmation`} className="se-wide" onExpand={() => setExpanded('breakout')}>
              <BreakoutRadar symbol={symbol} derived={derived} />
            </Panel>
            <Panel title="Key Levels Monitor" meta={`${derived.levelSource} support / resistance`} onExpand={() => setExpanded('levels')}>
              <LevelsTable rows={derived.levelRows} />
            </Panel>
            <Panel title={`${heatMode} Heat Map`} meta="Heat + flow + risk lines" className="se-wide" onExpand={() => setExpanded('heatmap')}>
              <UnifiedHeatmap symbol={symbol} mode={heatMode} derived={derived} onRefresh={refresh} onSave={saveHeatmapSnapshot} />
            </Panel>
          </section>
        )}

        {view === 'ops' && (
          <section className="se-grid se-grid-ops">
            <Panel title="Protection Operations" meta="Explicit operator controls" className="se-wide">
              <OpsControls
                symbol={symbol}
                gateMode={gateMode}
                onMode={handleModeUpdate}
                onPause={() => runCommand('Pausing scheduler', () => api.pauseScheduler())}
                onResume={() => runCommand('Resuming scheduler', () => api.resumeScheduler())}
                onEnableTicker={() => runCommand(`Enabling ${symbol} handoff`, () => api.updateTickerAutomation(symbol, true))}
                onDisableTicker={() => runCommand(`Disabling ${symbol} handoff`, () => api.updateTickerAutomation(symbol, false))}
                onTrailingStop={() => {
                  const pct = Number(window.prompt(`Trailing stop percent for ${symbol}`, '1.25'));
                  if (Number.isFinite(pct) && pct > 0) runCommand(`Pulse trailing-stop bridge for ${symbol}`, () => api.enablePulseTrailingStop(symbol, pct));
                }}
                onEmergencyExit={() => {
                  if (window.confirm(`Send Pulse emergency-exit bridge command for ${symbol}?`)) {
                    runCommand(`Emergency exit bridge for ${symbol}`, () => api.sendPulseEmergencyExit(symbol, 'Sentinel Edge operator control'));
                  }
                }}
                onAddTicker={handleAddTicker}
                onRemoveTicker={handleRemoveTicker}
                predictionHorizon={predictionHorizon}
                customHorizon={customHorizon}
                setCustomHorizon={setCustomHorizon}
                onPredictionHorizon={handlePredictionHorizon}
                onAdvisoryCommand={handleAdvisoryCommand}
              />
            </Panel>
            <Panel title="System Health" meta="Backend, Pulse, providers">
              <SystemHealth snapshot={snapshot} />
            </Panel>
            <Panel title="Pulse Queue / Positions" meta="Read-only execution context">
              <PulseContext snapshot={snapshot} />
            </Panel>
            <Panel title="Operations Modules" meta="Recovered dashboards" className="se-ops-module-panel">
              <OperationsModulesPanel active={operationsModule} setActive={setOperationsModule} />
            </Panel>
            <Panel title="Audit Log" meta="Exportable JSON" className="se-wide">
              <AuditLog rows={auditRows} />
            </Panel>
          </section>
        )}

        {view === 'settings' && (
          <section className="se-grid se-grid-settings">
            <Panel title="Local Settings" meta="No browser secrets">
              <SettingsPanel livePolling={livePolling} setLivePolling={setLivePolling} heatMode={heatMode} setHeatMode={setHeatMode} />
            </Panel>
            <Panel title="Provider / Readiness Details" meta="Validation state" className="se-wide">
              <ReadinessDetails snapshot={snapshot} />
            </Panel>
            <Panel title="Policy Stack" meta="Safety model">
              <PolicyStack />
            </Panel>
          </section>
        )}
      </main>

      {expanded && (
        <ExpandedPanel title={expandedTitle(expanded, heatMode, symbol)} onClose={() => setExpanded(null)}>
          {expanded === 'heatmap' && <UnifiedHeatmap symbol={symbol} mode={heatMode} derived={derived} expanded onRefresh={refresh} onSave={saveHeatmapSnapshot} />}
          {expanded === 'gamma' && <GammaStrikeChart symbol={symbol} derived={derived} expanded />}
          {expanded === 'breakout' && <BreakoutRadar symbol={symbol} derived={derived} expanded />}
          {expanded === 'risk' && <RiskPanel derived={derived} expanded />}
          {expanded === 'levels' && <LevelsTable rows={derived.levelRows} expanded />}
        </ExpandedPanel>
      )}
    </div>
  );
}

function expandedTitle(expanded: 'heatmap' | 'gamma' | 'breakout' | 'risk' | 'levels', mode: HeatMode, symbol: string) {
  switch (expanded) {
    case 'heatmap':
      return `${symbol} ${mode} Heat Map`;
    case 'gamma':
      return `${symbol} Gamma by Strike`;
    case 'breakout':
      return `${symbol} Breakout Radar`;
    case 'risk':
      return 'Sentinel Risk Brain';
    case 'levels':
      return 'Key Levels Monitor';
    default:
      return 'Expanded Window';
  }
}

function Brand() {
  return (
    <div className="se-brand">
      <div className="se-logo" aria-hidden="true">
        <svg viewBox="0 0 64 64" role="img">
          <path d="M32 6 52 14v15c0 14-8.5 23.5-20 29C20.5 52.5 12 43 12 29V14L32 6Z" fill="none" stroke="currentColor" strokeWidth="3" />
          <path d="M21 32h8l3-12 5 25 4-13h4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div>
        <h1>Sentinel Edge</h1>
        <p>Risk Control Brain</p>
      </div>
    </div>
  );
}

function NavButton({ active, icon, label, onClick }: { active: boolean; icon: string; label: string; onClick: () => void }) {
  return (
    <button type="button" className={active ? 'active' : ''} onClick={onClick}>
      <span className="se-nav-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function StatusLine({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'warn' | 'bad' | 'blue' | 'gold' }) {
  return (
    <div className="se-status-line">
      <span>{label}</span>
      <b className={tone}>{value}</b>
    </div>
  );
}

function KpiCard({ label, value, sub, tone, small = false }: { label: string; value: string; sub: string; tone: 'ok' | 'warn' | 'bad' | 'blue' | 'gold'; small?: boolean }) {
  return (
    <article className="se-kpi">
      <label>{label}</label>
      <div className={`se-kpi-value ${tone} ${small ? 'small' : ''}`}>{value}</div>
      <div className="se-kpi-sub"><span>{sub}</span><Sparkline tone={tone} /></div>
    </article>
  );
}

function Sparkline({ tone }: { tone: string }) {
  const points = '0,18 10,17 18,19 27,12 36,14 46,8 55,10 66,2';
  return (
    <svg className={`se-spark ${tone}`} viewBox="0 0 66 22" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Panel({ title, meta, children, className = '', onExpand }: { title: string; meta?: string; children: ReactNode; className?: string; onExpand?: () => void }) {
  return (
    <section className={`se-panel ${className}`}>
      <header className="se-panel-head">
        <div className="se-panel-title">
          <h3>{title}</h3>
          {meta && <span>{meta}</span>}
        </div>
        <div className="se-panel-tools">
          {onExpand && <button type="button" className="se-icon-btn" onClick={onExpand} aria-label={`Expand ${title}`}>↗</button>}
        </div>
      </header>
      <div className="se-panel-body">{children}</div>
    </section>
  );
}

function OperationsModulesPanel({
  active,
  setActive,
}: {
  active: OperationsModuleId;
  setActive: (id: OperationsModuleId) => void;
}) {
  const selected = OPERATIONS_MODULES.find((module) => module.id === active) ?? OPERATIONS_MODULES[0];
  return (
    <div className="se-ops-module-layout">
      <nav className="se-ops-module-tabs" role="tablist" aria-label="Operations modules">
        {OPERATIONS_MODULES.map((module) => (
          <button
            key={module.id}
            id={`se-ops-module-tab-${module.id}`}
            type="button"
            role="tab"
            aria-selected={active === module.id}
            aria-controls={`se-ops-module-panel-${module.id}`}
            className={active === module.id ? 'active' : ''}
            onClick={() => setActive(module.id)}
          >
            <span>{module.label}</span>
            <small>{module.detail}</small>
          </button>
        ))}
      </nav>
      <section
        id={`se-ops-module-panel-${active}`}
        className="se-ops-module-content"
        role="tabpanel"
        aria-labelledby={`se-ops-module-tab-${active}`}
        tabIndex={0}
      >
        <ModuleErrorBoundary moduleId={active}>
          <Suspense fallback={<ModuleLoading label={selected.label} />}>
            {active === 'overview' && <TradingOverviewModule />}
            {active === 'scanners' && <ScannerWorkbenchModule />}
            {active === 'advisor' && <AdvisorHealthModule />}
            {active === 'experience' && <ExperienceDashboardModule />}
            {active === 'protection' && <ProtectionDashboardModule />}
            {active === 'pnl' && <PnLTrackingModule />}
            {active === 'markets' && <MarketCoverageModule />}
            {active === 'portfolio' && <PortfolioAnalyticsModule />}
            {active === 'settings' && <SettingsDashboardModule />}
            {active === 'tutorials' && <TutorialsDashboardModule onOpenModule={(module) => setActive(module)} />}
          </Suspense>
        </ModuleErrorBoundary>
      </section>
    </div>
  );
}

function ModuleLoading({ label }: { label: string }) {
  return (
    <div className="se-module-loading">
      <span className="se-spinner" aria-hidden="true" />
      <strong>Loading {label}</strong>
    </div>
  );
}

function OverviewGrid({
  symbol,
  heatMode,
  derived,
  selectedBot,
  setSelectedBot,
  setExpanded,
  onPause,
  onResume,
  onExport,
  onRefreshHeatmap,
  onSaveHeatmap,
}: {
  symbol: string;
  heatMode: HeatMode;
  derived: DerivedState;
  selectedBot: string;
  setSelectedBot: (id: string) => void;
  setExpanded: (panel: 'heatmap' | 'gamma' | 'breakout' | 'risk' | 'levels') => void;
  onPause: () => void;
  onResume: () => void;
  onExport: () => void;
  onRefreshHeatmap: () => void;
  onSaveHeatmap: () => void;
}) {
  return (
    <section className="se-grid se-grid-overview">
      <Panel title={`${heatMode} Heat Map`} meta={`${symbol} heat, flow, risk, support / resistance`} className="se-heat-panel" onExpand={() => setExpanded('heatmap')}>
        <UnifiedHeatmap symbol={symbol} mode={heatMode} derived={derived} onRefresh={onRefreshHeatmap} onSave={onSaveHeatmap} />
      </Panel>
      <Panel title="Bot Ecosystem Overview" meta="Sentinel Edge control mesh" className="se-mesh-panel">
        <BotMesh bots={derived.botRows} selected={selectedBot} onSelect={setSelectedBot} />
      </Panel>
      <Panel title="Recent Sentinel Decisions" meta="Advisory output">
        <DecisionFeed rows={derived.decisionRows} />
      </Panel>
      <Panel title="Market Regime Detection" meta={`${derived.regime} · ${safePercent(derived.regimeConfidence)}`} onExpand={() => setExpanded('risk')}>
        <RiskPanel derived={derived} compact />
      </Panel>
      <Panel title="Breakout / Breakdown Radar" meta="Confirmation logic" onExpand={() => setExpanded('breakout')}>
        <BreakoutRadar symbol={symbol} derived={derived} compact />
      </Panel>
      <Panel title="Key Levels Monitor" meta={`${derived.levelSource} support / resistance`} onExpand={() => setExpanded('levels')}>
        <LevelsTable rows={derived.levelRows} compact />
      </Panel>
      <Panel title="Gamma by Strike" meta="Delta / gamma profile" onExpand={() => setExpanded('gamma')}>
        <GammaStrikeChart symbol={symbol} derived={derived} compact />
      </Panel>
      <Panel title="Protection Controls" meta="Operator-supervised actions">
        <div className="se-quick-actions">
          <button type="button" className="se-action" onClick={onPause}>Pause Scheduler</button>
          <button type="button" className="se-action live" onClick={onResume}>Resume Scheduler</button>
          <button type="button" className="se-action" onClick={onExport}>Export Audit</button>
        </div>
        <PolicyStack compact />
      </Panel>
    </section>
  );
}

function UnifiedHeatmap({
  symbol,
  mode,
  derived,
  expanded = false,
  onRefresh,
  onSave,
}: {
  symbol: string;
  mode: HeatMode;
  derived: DerivedState;
  expanded?: boolean;
  onRefresh?: () => void;
  onSave?: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; html: string; visible: boolean }>({ x: 0, y: 0, html: '', visible: false });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(620, Math.floor(rect.width));
    const height = expanded ? Math.max(620, Math.floor(rect.height)) : Math.max(350, Math.floor(rect.height));
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawHeatmapCanvas(ctx, width, height, symbol, mode, derived);
  }, [derived, expanded, mode, symbol]);

  useEffect(() => {
    draw();
    const wrap = wrapRef.current;
    if (!wrap) return undefined;
    const observer = new ResizeObserver(draw);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [draw]);

  const onMove = (event: ReactMouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const pointIndex = clamp(Math.floor((x / rect.width) * derived.series.length), 0, derived.series.length - 1);
    const point = derived.series[pointIndex];
    setTooltip({
      x: Math.min(x + 14, rect.width - 210),
      y: Math.max(12, Math.min(y + 14, rect.height - 92)),
      visible: true,
      html: `<b>${symbol} · ${point.time}</b><br/>Price ${formatNumber(point.price)}<br/>Allow ${point.allow.toFixed(0)} · Risk ${point.risk.toFixed(0)}<br/>Volume ${point.volume.toFixed(0)}K`,
    });
  };

  return (
    <div className={`se-chart-stage se-heat-stage ${expanded ? 'expanded' : ''}`} ref={wrapRef}>
      <canvas ref={canvasRef} onMouseMove={onMove} onMouseLeave={() => setTooltip((state) => ({ ...state, visible: false }))} />
      <div className="se-chart-legend">
        <span><i className="green" />Call / allow flow</span>
        <span><i className="red" />Risk pressure</span>
        <span><i className="gold" />Spot / price</span>
        <span><i className="purple" />Support / resistance</span>
      </div>
      {(onRefresh || onSave) && (
        <div className="se-heat-toolbar">
          {onRefresh && <button type="button" className="se-action" onClick={onRefresh}>Refresh Heatmap</button>}
          {onSave && <button type="button" className="se-action" onClick={onSave}>Save Heatmap</button>}
        </div>
      )}
      <div className="se-heat-scale"><span>High</span><b /><span>Low</span></div>
      <div className={`se-tooltip ${tooltip.visible ? 'visible' : ''}`} style={{ left: tooltip.x, top: tooltip.y }} dangerouslySetInnerHTML={{ __html: tooltip.html }} />
    </div>
  );
}

function drawHeatmapCanvas(ctx: CanvasRenderingContext2D, width: number, height: number, symbol: string, mode: HeatMode, derived: DerivedState) {
  const padding = { left: 48, right: 62, top: 28, bottom: 70 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const rows = 54;
  const cols = 150;
  const rng = mulberry(hash(`${symbol}-${mode}-${Math.round(derived.lastPrice)}`));
  const cellW = chartW / cols;
  const cellH = chartH / rows;
  const minPrice = Math.min(derived.support * 0.985, derived.lastPrice * 0.98);
  const maxPrice = Math.max(derived.resistance * 1.015, derived.lastPrice * 1.02);

  const bg = ctx.createLinearGradient(0, 0, 0, height);
  bg.addColorStop(0, '#070814');
  bg.addColorStop(1, '#0c0d1a');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.translate(padding.left, padding.top);

  for (let c = 0; c < cols; c += 1) {
    const t = c / Math.max(1, cols - 1);
    const priceCenter = 0.5 + Math.sin(t * Math.PI * 2.5 + rng() * 0.3) * 0.08 + (t - 0.52) * 0.1;
    const spread = 0.09 + Math.sin(t * Math.PI * 4) * 0.015 + (mode === 'VOL' ? 0.035 : 0);
    for (let r = 0; r < rows; r += 1) {
      const yT = r / Math.max(1, rows - 1);
      const dist = Math.abs(yT - priceCenter);
      let intensity = Math.exp(-(dist * dist) / (2 * spread * spread));
      intensity += Math.exp(-Math.pow(yT - 0.35 - Math.sin(t * 8) * 0.025, 2) / 0.003) * 0.45;
      intensity += (rng() - 0.5) * 0.16;
      intensity = clamp(intensity, 0, 1);
      if (mode === 'VEX') intensity = clamp(intensity * (0.72 + yT * 0.7), 0, 1);
      if (mode === 'GEX') intensity = clamp(intensity * (1.05 - Math.abs(yT - 0.5) * 0.28), 0, 1);
      ctx.fillStyle = heatColor(intensity);
      ctx.fillRect(c * cellW, r * cellH, Math.ceil(cellW) + 0.5, Math.ceil(cellH) + 0.5);
    }
  }

  ctx.globalCompositeOperation = 'screen';
  const glow = ctx.createRadialGradient(chartW * 0.56, chartH * 0.52, 10, chartW * 0.56, chartH * 0.52, chartW * 0.52);
  glow.addColorStop(0, 'rgba(240,199,94,0.16)');
  glow.addColorStop(1, 'rgba(69,37,181,0)');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, chartW, chartH);
  ctx.globalCompositeOperation = 'source-over';

  drawGrid(ctx, chartW, chartH);

  const priceToY = (price: number) => chartH - ((price - minPrice) / Math.max(1, maxPrice - minPrice)) * chartH;
  const supportY = priceToY(derived.support);
  const resistanceY = priceToY(derived.resistance);
  const spotY = priceToY(derived.lastPrice);

  drawBand(ctx, chartW, supportY, 'Support', '#4525B5');
  drawBand(ctx, chartW, resistanceY, 'Resistance', '#C9A227');

  drawLine(ctx, derived.series.map((point, i) => [
    (i / Math.max(1, derived.series.length - 1)) * chartW,
    chartH - (point.allow / 100) * chartH * 0.65 - chartH * 0.16,
  ]), '#28D17C', 2.3);
  drawLine(ctx, derived.series.map((point, i) => [
    (i / Math.max(1, derived.series.length - 1)) * chartW,
    chartH - (point.risk / 100) * chartH * 0.6 - chartH * 0.22,
  ]), '#FF4D5E', 2.1);
  drawLine(ctx, derived.series.map((point, i) => [
    (i / Math.max(1, derived.series.length - 1)) * chartW,
    priceToY(point.price),
  ]), '#F0C75E', 1.9);

  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = 'rgba(240,199,94,0.55)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, spotY);
  ctx.lineTo(chartW, spotY);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = '#F0C75E';
  ctx.font = '700 11px JetBrains Mono, monospace';
  ctx.fillText(`Spot ${formatNumber(derived.lastPrice)}`, chartW - 128, spotY - 7);

  const maxVol = Math.max(...derived.series.map((point) => point.volume));
  derived.series.forEach((point, i) => {
    const x = (i / Math.max(1, derived.series.length - 1)) * chartW;
    const volH = (point.volume / maxVol) * 48;
    ctx.fillStyle = point.allow >= point.risk ? 'rgba(40,209,124,0.65)' : 'rgba(255,77,94,0.65)';
    ctx.fillRect(x, chartH + 12 + (48 - volH), Math.max(1, chartW / derived.series.length - 1), volH);
  });

  ctx.restore();

  ctx.fillStyle = '#8C8AA3';
  ctx.font = '600 11px JetBrains Mono, monospace';
  for (let i = 0; i < 6; i += 1) {
    const price = minPrice + ((maxPrice - minPrice) / 5) * i;
    const y = padding.top + chartH - (chartH / 5) * i;
    ctx.fillText(formatNumber(price), 8, y + 4);
  }
  ['09:30', '10:30', '11:30', '12:30', '13:30', '14:30', '15:30'].forEach((label, i, arr) => {
    const x = padding.left + (chartW / (arr.length - 1)) * i;
    ctx.fillText(label, x - 16, padding.top + chartH + 68);
  });

  ctx.fillStyle = '#ECEAF6';
  ctx.font = '700 13px Space Grotesk, system-ui';
  ctx.fillText(`${mode} ${symbol} · Breakout control heat`, padding.left, 18);
}

function drawGrid(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.strokeStyle = 'rgba(236,234,246,0.065)';
  ctx.lineWidth = 1;
  for (let x = 0; x <= width; x += width / 8) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += height / 6) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
}

function drawBand(ctx: CanvasRenderingContext2D, width: number, y: number, label: string, color: string) {
  ctx.save();
  ctx.fillStyle = `${color}22`;
  ctx.fillRect(0, y - 7, width, 14);
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = `${color}aa`;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, y);
  ctx.lineTo(width, y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#ECEAF6';
  ctx.font = '700 10px JetBrains Mono, monospace';
  ctx.fillText(label, 8, y - 10);
  ctx.restore();
}

function drawLine(ctx: CanvasRenderingContext2D, points: number[][], color: string, width = 2) {
  if (!points.length) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 12;
  ctx.lineWidth = width;
  ctx.beginPath();
  points.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.restore();
}

function heatColor(t: number) {
  const stops: Array<[number, number, number, number]> = [
    [0.0, 8, 9, 28],
    [0.16, 16, 42, 122],
    [0.32, 12, 108, 188],
    [0.48, 0, 168, 168],
    [0.6, 42, 188, 92],
    [0.72, 202, 210, 42],
    [0.84, 235, 150, 32],
    [0.94, 230, 72, 32],
    [1, 222, 30, 40],
  ];
  const clamped = clamp(t, 0, 1);
  for (let i = 0; i < stops.length - 1; i += 1) {
    const a = stops[i];
    const b = stops[i + 1];
    if (clamped >= a[0] && clamped <= b[0]) {
      const local = (clamped - a[0]) / Math.max(0.00001, b[0] - a[0]);
      const r = Math.round(a[1] + (b[1] - a[1]) * local);
      const g = Math.round(a[2] + (b[2] - a[2]) * local);
      const blue = Math.round(a[3] + (b[3] - a[3]) * local);
      return `rgb(${r},${g},${blue})`;
    }
  }
  return 'rgb(222,30,40)';
}

function BotMesh({ bots, selected, onSelect }: { bots: BotRow[]; selected: string; onSelect: (id: string) => void }) {
  return (
    <div className="se-bot-mesh">
      <svg className="se-mesh-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {[[50, 50, 16, 18], [50, 50, 84, 18], [50, 50, 13, 47], [50, 50, 87, 47], [50, 50, 18, 80], [50, 50, 82, 80], [50, 50, 50, 10], [50, 50, 50, 88]].map((line, index) => (
          <line key={index} x1={line[0]} y1={line[1]} x2={line[2]} y2={line[3]} />
        ))}
      </svg>
      <div className="se-brain-core">
        <b>EDGE</b>
        <span>Control Brain</span>
      </div>
      {bots.map((bot, index) => (
        <button
          type="button"
          key={bot.id}
          className={`se-bot-node node-${index} ${selected === bot.id ? 'active' : ''} ${bot.state}`}
          onClick={() => onSelect(bot.id)}
          title={`${bot.repo} · ${bot.localPath}`}
        >
          <div className={`se-bot-icon ${bot.color}`}>{bot.icon}</div>
          <div className="se-bot-copy">
            <strong>{bot.name}</strong>
            <small>{bot.subtitle}</small>
            <span className={statusTone(bot.state)}>{bot.state}</span>
          </div>
          <Sparkline tone={statusTone(bot.state)} />
        </button>
      ))}
    </div>
  );
}

function DecisionFeed({ rows }: { rows: DecisionRow[] }) {
  return (
    <div className="se-feed-list">
      {rows.map((row) => (
        <article key={row.id} className="se-decision">
          <span className="se-time">{row.time}</span>
          <span className={`se-tag ${row.action}`}>{labelForAction(row.action)}</span>
          <div>
            <b>{row.symbol} · {row.headline}</b>
            <p>{row.detail}</p>
          </div>
          <span className={`se-severity ${row.severity}`}>{row.severity}</span>
        </article>
      ))}
    </div>
  );
}

function LevelsTable({ rows, compact = false, expanded = false }: { rows: LevelRow[]; compact?: boolean; expanded?: boolean }) {
  return (
    <div className={`se-table-wrap ${expanded ? 'expanded' : ''}`}>
      <table className="se-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Support</th>
            <th>Price</th>
            <th>Resistance</th>
            <th>Status</th>
            {!compact && <th>Source</th>}
            {!compact && <th>Distance</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td><b>{row.symbol}</b></td>
              <td>{formatNumber(row.support)}</td>
              <td>{formatNumber(row.price)}</td>
              <td>{formatNumber(row.resistance)}</td>
              <td className={row.tone}>{row.status}</td>
              {!compact && <td>{row.source}</td>}
              {!compact && <td>{row.distancePct.toFixed(2)}%</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RiskPanel({ derived, compact = false, expanded = false }: { derived: DerivedState; compact?: boolean; expanded?: boolean }) {
  const risk = derived.riskScore;
  const slices = [
    { label: 'Market risk', value: clamp(risk * 0.34, 2, 45), tone: 'ok' },
    { label: 'Volatility risk', value: clamp(risk * 0.27, 1, 32), tone: 'warn' },
    { label: 'Liquidity risk', value: clamp(risk * 0.16, 1, 22), tone: 'blue' },
    { label: 'Correlation risk', value: clamp(risk * 0.13, 1, 18), tone: 'gold' },
    { label: 'Handoff risk', value: clamp(risk * 0.1, 1, 18), tone: 'bad' },
  ];
  return (
    <div className={`se-risk-panel ${compact ? 'compact' : ''} ${expanded ? 'expanded' : ''}`}>
      <div className="se-donut" style={{ '--risk': `${risk * 3.6}deg` } as CSSProperties}>
        <span>{risk.toFixed(0)}</span>
        <small>Risk Score</small>
      </div>
      <div className="se-regime-box">
        <h4>{derived.regime}</h4>
        <p>Confidence {safePercent(derived.regimeConfidence)}</p>
        <div className="se-bars">
          <RiskBar label="Momentum" value={derived.regimeConfidence} tone="ok" />
          <RiskBar label="Volatility" value={clamp(derived.riskScore, 10, 100)} tone={derived.riskScore > 55 ? 'warn' : 'ok'} />
          <RiskBar label="Net Gamma" value={clamp(Math.abs(derived.netGamma) / 18_000_000, 10, 100)} tone={derived.netGamma >= 0 ? 'ok' : 'bad'} />
          <RiskBar label="Net Delta" value={clamp(Math.abs(derived.netDelta) / 7_000_000, 10, 100)} tone={derived.netDelta >= 0 ? 'blue' : 'bad'} />
        </div>
      </div>
      {!compact && (
        <div className="se-risk-slices">
          {slices.map((slice) => (
            <div key={slice.label}>
              <span className={slice.tone}>{slice.label}</span>
              <b>{slice.value.toFixed(1)}%</b>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="se-risk-bar">
      <span>{label}</span>
      <div><b className={tone} style={{ width: `${clamp(value, 0, 100)}%` }} /></div>
      <strong>{safePercent(value)}</strong>
    </div>
  );
}

function BreakoutRadar({ symbol, derived, compact = false, expanded = false }: { symbol: string; derived: DerivedState; compact?: boolean; expanded?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(360, rect.width);
    const height = Math.max(compact ? 170 : expanded ? 500 : 250, rect.height);
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawBreakoutCanvas(ctx, width, height, symbol, derived);
  }, [compact, derived, expanded, symbol]);
  useEffect(() => {
    draw();
    const wrap = wrapRef.current;
    if (!wrap) return undefined;
    const observer = new ResizeObserver(draw);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [draw]);
  return (
    <div ref={wrapRef} className={`se-chart-stage se-breakout-stage ${expanded ? 'expanded' : ''}`}>
      <canvas ref={canvasRef} />
      <div className="se-floating-badge">{derived.regime}</div>
    </div>
  );
}

function drawBreakoutCanvas(ctx: CanvasRenderingContext2D, width: number, height: number, symbol: string, derived: DerivedState) {
  const pad = { left: 48, right: 22, top: 22, bottom: 34 };
  const w = width - pad.left - pad.right;
  const h = height - pad.top - pad.bottom;
  const min = Math.min(...derived.series.map((p) => p.price), derived.support) * 0.995;
  const max = Math.max(...derived.series.map((p) => p.price), derived.resistance) * 1.005;
  const y = (price: number) => pad.top + h - ((price - min) / Math.max(1, max - min)) * h;
  ctx.fillStyle = '#08091c';
  ctx.fillRect(0, 0, width, height);
  drawGridTranslated(ctx, pad.left, pad.top, w, h);
  ctx.fillStyle = 'rgba(69,37,181,0.18)';
  ctx.fillRect(pad.left, y(derived.resistance) - 7, w, 14);
  ctx.fillStyle = 'rgba(40,209,124,0.13)';
  ctx.fillRect(pad.left, y(derived.support) - 7, w, 14);
  drawLine(ctx, derived.series.map((point, index) => [pad.left + (index / Math.max(1, derived.series.length - 1)) * w, y(point.price)]), '#F0C75E', 2.2);
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = '#28D17C';
  ctx.beginPath();
  ctx.moveTo(pad.left, y(derived.support));
  ctx.lineTo(pad.left + w, y(derived.support));
  ctx.stroke();
  ctx.strokeStyle = '#FFB84D';
  ctx.beginPath();
  ctx.moveTo(pad.left, y(derived.resistance));
  ctx.lineTo(pad.left + w, y(derived.resistance));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#ECEAF6';
  ctx.font = '700 13px Space Grotesk, system-ui';
  ctx.fillText(`${symbol} support / resistance radar`, pad.left, 16);
  ctx.fillStyle = '#28D17C';
  ctx.fillText(`Support ${formatNumber(derived.support)}`, pad.left + 8, y(derived.support) - 10);
  ctx.fillStyle = '#FFB84D';
  ctx.fillText(`Resistance ${formatNumber(derived.resistance)}`, pad.left + 8, y(derived.resistance) - 10);
  ctx.fillStyle = '#F0C75E';
  ctx.beginPath();
  const lastX = pad.left + w;
  const lastY = y(derived.lastPrice);
  ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#8C8AA3';
  ctx.font = '600 10px JetBrains Mono, monospace';
  ['09:30', '11:00', '12:30', '14:00', '15:30'].forEach((label, i, arr) => ctx.fillText(label, pad.left + (w / (arr.length - 1)) * i - 12, height - 12));
}

function drawGridTranslated(ctx: CanvasRenderingContext2D, x0: number, y0: number, width: number, height: number) {
  ctx.save();
  ctx.translate(x0, y0);
  drawGrid(ctx, width, height);
  ctx.restore();
}

function GammaStrikeChart({ symbol, derived, compact = false, expanded = false }: { symbol: string; derived: DerivedState; compact?: boolean; expanded?: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(330, rect.width);
    const height = Math.max(compact ? 180 : expanded ? 500 : 260, rect.height);
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawGammaCanvas(ctx, width, height, symbol, derived);
  }, [compact, derived, expanded, symbol]);
  useEffect(() => {
    draw();
    const wrap = wrapRef.current;
    if (!wrap) return undefined;
    const observer = new ResizeObserver(draw);
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [draw]);
  return (
    <div ref={wrapRef} className={`se-chart-stage se-gamma-stage ${expanded ? 'expanded' : ''}`}>
      <canvas ref={canvasRef} />
    </div>
  );
}

function drawGammaCanvas(ctx: CanvasRenderingContext2D, width: number, height: number, symbol: string, derived: DerivedState) {
  const pad = { left: 44, right: 18, top: 24, bottom: 38 };
  const w = width - pad.left - pad.right;
  const h = height - pad.top - pad.bottom;
  const center = derived.lastPrice;
  const strikes = Array.from({ length: 34 }, (_, index) => center * (0.92 + index * (0.16 / 33)));
  const rng = mulberry(hash(`${symbol}-gamma`));
  const values = strikes.map((strike) => {
    const dist = Math.abs(strike - center) / center;
    const curve = Math.exp(-(dist * dist) / 0.0017);
    const call = curve * (0.6 + rng() * 0.9) * 100;
    const put = -curve * (0.45 + rng() * 1.15) * 100;
    return { strike, call, put };
  });
  const maxAbs = Math.max(...values.flatMap((row) => [Math.abs(row.call), Math.abs(row.put)]));
  ctx.fillStyle = '#08091c';
  ctx.fillRect(0, 0, width, height);
  drawGridTranslated(ctx, pad.left, pad.top, w, h);
  const zeroY = pad.top + h / 2;
  ctx.strokeStyle = 'rgba(236,234,246,0.25)';
  ctx.beginPath();
  ctx.moveTo(pad.left, zeroY);
  ctx.lineTo(pad.left + w, zeroY);
  ctx.stroke();
  const barW = w / values.length * 0.72;
  values.forEach((row, index) => {
    const x = pad.left + (index / values.length) * w + (w / values.length - barW) / 2;
    const callH = (row.call / maxAbs) * (h * 0.45);
    const putH = (Math.abs(row.put) / maxAbs) * (h * 0.45);
    ctx.fillStyle = '#28D17C';
    ctx.fillRect(x, zeroY - callH, barW, callH);
    ctx.fillStyle = '#FF4D5E';
    ctx.fillRect(x, zeroY, barW, putH);
  });
  const spotX = pad.left + ((center - strikes[0]) / Math.max(1, strikes[strikes.length - 1] - strikes[0])) * w;
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = '#2D8CFF';
  ctx.beginPath();
  ctx.moveTo(spotX, pad.top);
  ctx.lineTo(spotX, pad.top + h);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = '#2D8CFF';
  ctx.font = '700 10px JetBrains Mono, monospace';
  ctx.fillText(`Spot ${formatNumber(center)}`, spotX + 5, pad.top + 12);
  ctx.fillStyle = '#ECEAF6';
  ctx.font = '700 13px Space Grotesk, system-ui';
  ctx.fillText(`${symbol} gamma / delta by strike`, pad.left, 16);
  ctx.fillStyle = '#8C8AA3';
  ctx.font = '600 10px JetBrains Mono, monospace';
  for (let i = 0; i < 5; i += 1) {
    const strike = strikes[Math.round((strikes.length - 1) * (i / 4))];
    ctx.fillText(formatNumber(strike, symbol.includes('BTC') || symbol.includes('ES') ? 0 : 2), pad.left + (w / 4) * i - 14, height - 12);
  }
}

function PolicyStack({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`se-policy-stack ${compact ? 'compact' : ''}`}>
      {POLICY_STACK.map((policy) => (
        <article key={policy.id}>
          <div>
            <strong>{policy.name}</strong>
            {!compact && <p>{policy.detail}</p>}
          </div>
          <span className={`se-switch ${policy.enabled ? 'on' : ''} ${policy.tone}`}><i /></span>
        </article>
      ))}
    </div>
  );
}

function AuditLog({ rows }: { rows: AuditRow[] }) {
  const [filter, setFilter] = useState<'all' | 'operator' | 'system'>('all');
  const filteredRows = rows.filter((row) => {
    if (filter === 'operator') return row.actor === 'Operator';
    if (filter === 'system') return row.actor !== 'Operator';
    return true;
  });

  return (
    <div className="se-audit-shell">
      <div className="se-audit-filter" role="group" aria-label="Audit log filter">
        {[
          ['all', 'All Activity', rows.length],
          ['operator', 'Operator', rows.filter((row) => row.actor === 'Operator').length],
          ['system', 'Backend/System', rows.filter((row) => row.actor !== 'Operator').length],
        ].map(([id, label, count]) => (
          <button
            key={id}
            type="button"
            className={filter === id ? 'active' : ''}
            onClick={() => setFilter(id as 'all' | 'operator' | 'system')}
          >
            <span>{label}</span>
            <b>{count}</b>
          </button>
        ))}
      </div>
      <div className="se-audit-list">
        {filteredRows.map((row, index) => (
          <article key={`${row.time}-${index}`}>
            <span>{row.time}</span>
            <b>{row.actor}</b>
            <strong className={row.tone}>{row.event}</strong>
            <p>{row.outcome}</p>
          </article>
        ))}
        {filteredRows.length === 0 && <div className="se-empty-state">No audit rows match this filter.</div>}
      </div>
    </div>
  );
}

function BotDirectiveTable({ bots }: { bots: BotRow[] }) {
  return (
    <div className="se-table-wrap">
      <table className="se-table">
        <thead><tr><th>Bot</th><th>Health</th><th>Directive</th><th>Latency</th></tr></thead>
        <tbody>
          {bots.map((bot) => (
            <tr key={bot.id}>
              <td><b>{bot.name}</b><br /><small>{bot.repo}</small></td>
              <td className={statusTone(bot.state)}>{safePercent(bot.health)}</td>
              <td>{bot.lastDirective}</td>
              <td>{bot.latencyMs}ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpsControls({
  symbol,
  gateMode,
  onMode,
  onPause,
  onResume,
  onEnableTicker,
  onDisableTicker,
  onTrailingStop,
  onEmergencyExit,
  onAddTicker,
  onRemoveTicker,
  predictionHorizon,
  customHorizon,
  setCustomHorizon,
  onPredictionHorizon,
  onAdvisoryCommand,
}: {
  symbol: string;
  gateMode: GateMode;
  onMode: (mode: GateMode) => void;
  onPause: () => void;
  onResume: () => void;
  onEnableTicker: () => void;
  onDisableTicker: () => void;
  onTrailingStop: () => void;
  onEmergencyExit: () => void;
  onAddTicker: () => void;
  onRemoveTicker: () => void;
  predictionHorizon: string;
  customHorizon: string;
  setCustomHorizon: (value: string) => void;
  onPredictionHorizon: (horizon: string) => void;
  onAdvisoryCommand: (command: AdvisoryCommand) => void;
}) {
  return (
    <div className="se-ops-grid">
      <div className="se-ops-card">
        <h4>Prediction Horizon</h4>
        <p>Recovered local forecast window control from the old command panel.</p>
        <div className="se-segment wide">
          {['30m', '3h', 'today'].map((horizon) => (
            <button key={horizon} type="button" className={predictionHorizon === horizon ? 'active' : ''} onClick={() => onPredictionHorizon(horizon)}>{horizon}</button>
          ))}
        </div>
        <label className="se-inline-input">
          <span>Custom</span>
          <input value={customHorizon} maxLength={16} onChange={(event) => setCustomHorizon(event.target.value)} />
          <button type="button" className="se-action" onClick={() => onPredictionHorizon(customHorizon)}>Apply</button>
        </label>
      </div>
      <div className="se-ops-card">
        <h4>Advisory Commands</h4>
        <p>Local command acknowledgements; Pulse execution remains behind gates.</p>
        <button type="button" className="se-action live" onClick={() => onAdvisoryCommand('Arm Trigger')}>Arm Trigger</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Risk Sweep')}>Risk Sweep</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Convert Alert')}>Convert Alert</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Mute Watch')}>Mute Watch</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Diagnostics')}>Diagnostics</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Ack Alerts')}>Ack Alerts</button>
      </div>
      <div className="se-ops-card">
        <h4>Protection Advisories</h4>
        <p>Recovered local protection actions; backend execution still requires explicit bridge controls.</p>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Lock Buys')}>Lock Buys</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Advise Stops')}>Advise Stops</button>
        <button type="button" className="se-action danger" onClick={() => onAdvisoryCommand('Reduce Size')}>Reduce Size</button>
      </div>
      <div className="se-ops-card">
        <h4>Chart Directives</h4>
        <p>Recovered chart-map command feed actions for local advisory review.</p>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Inject Break')}>Inject Break</button>
        <button type="button" className="se-action live" onClick={() => onAdvisoryCommand('Allow Guarded Breakout')}>Allow Guarded Breakout</button>
        <button type="button" className="se-action danger" onClick={() => onAdvisoryCommand('Block Buy Below Support')}>Block Buy Below Support</button>
        <button type="button" className="se-action danger" onClick={() => onAdvisoryCommand('Reduce Size On Heat Spike')}>Reduce Size On Heat Spike</button>
      </div>
      <div className="se-ops-card">
        <h4>Greek Workbench</h4>
        <p>Recovered Greek workbench actions; visual analysis stays in Risk Engine and Breakouts.</p>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Resimulate Greeks')}>Resimulate Greeks</button>
        <button type="button" className="se-action" onClick={() => onAdvisoryCommand('Export Levels')}>Export Levels</button>
      </div>
      <div className="se-ops-card">
        <h4>Automation Mode</h4>
        <p>Recommendation display stays separate from Pulse execution handoff.</p>
        <div className="se-segment wide">
          {(['recommend_only', 'paper', 'live'] as GateMode[]).map((mode) => (
            <button key={mode} type="button" className={gateMode === mode ? 'active' : ''} onClick={() => onMode(mode)}>{String(mode).replace('_', ' ')}</button>
          ))}
        </div>
      </div>
      <div className="se-ops-card">
        <h4>Scheduler</h4>
        <p>Pause or resume continuous ticker evaluation.</p>
        <button type="button" className="se-action" onClick={onPause}>Pause</button>
        <button type="button" className="se-action live" onClick={onResume}>Resume</button>
      </div>
      <div className="se-ops-card">
        <h4>{symbol} Gate</h4>
        <p>Per-ticker handoff permission control.</p>
        <button type="button" className="se-action live" onClick={onEnableTicker}>Enable Ticker</button>
        <button type="button" className="se-action danger" onClick={onDisableTicker}>Disable Ticker</button>
      </div>
      <div className="se-ops-card">
        <h4>Pulse Bridge</h4>
        <p>Explicit operator bridge commands to Pulse.</p>
        <button type="button" className="se-action" onClick={onTrailingStop}>Trailing Stop</button>
        <button type="button" className="se-action danger" onClick={onEmergencyExit}>Emergency Exit</button>
      </div>
      <div className="se-ops-card">
        <h4>Ticker List</h4>
        <p>Add or remove active symbols.</p>
        <button type="button" className="se-action live" onClick={onAddTicker}>Add Current Input</button>
        <button type="button" className="se-action danger" onClick={onRemoveTicker}>Remove {symbol}</button>
      </div>
    </div>
  );
}

function SystemHealth({ snapshot }: { snapshot: EdgeSnapshot }) {
  const rows = [
    { name: 'Backend live', state: snapshot.live, good: !snapshot.live.error },
    { name: 'Readiness', state: snapshot.ready, good: Boolean((snapshot.ready.data as any)?.ready ?? !snapshot.ready.error) },
    { name: 'Provider health', state: snapshot.providers, good: !snapshot.providers.error },
    { name: 'Market data providers', state: snapshot.marketDataProviders, good: !snapshot.marketDataProviders.error },
    { name: 'Pulse status', state: snapshot.pulse, good: !snapshot.pulse.error },
    { name: 'Pulse handoff schema', state: snapshot.pulseHandoffSchema, good: !snapshot.pulseHandoffSchema.error },
    { name: 'Rate limit', state: snapshot.rateLimit, good: !snapshot.rateLimit.error },
  ];
  return (
    <div className="se-health-list">
      {rows.map((row) => (
        <article key={row.name}>
          <span className={`se-dot ${row.good ? 'ok' : 'bad'}`} />
          <strong>{row.name}</strong>
          <em className={row.good ? 'ok' : 'bad'}>{row.good ? 'Healthy' : 'Needs review'}</em>
          <small>{row.state.error ?? 'Live'}</small>
        </article>
      ))}
    </div>
  );
}

function PulseContext({ snapshot }: { snapshot: EdgeSnapshot }) {
  const positionsPayload = snapshot.positions.data as any;
  const queuePayload = snapshot.queue.data as any;
  const schemaPayload = snapshot.pulseHandoffSchema.data as any;
  const positions = toArray(positionsPayload, ['positions', 'items', 'data']);
  const queue = toArray(queuePayload, ['queue', 'items', 'data']);
  const queueSize = Number(queuePayload?.queue_size ?? queuePayload?.size ?? queuePayload?.count);
  const defaultTtl = Number(queuePayload?.default_ttl_seconds);
  const emergencyTtl = Number(queuePayload?.emergency_ttl_seconds);
  const headerRows = objectRows(schemaPayload?.transport_headers);
  const idempotencyHeader = headerRows.find((row: any) => String(row.key ?? row.name ?? '').toLowerCase() === 'idempotency-key');
  return (
    <div className="se-pulse-context">
      <h4>Positions</h4>
      {positions.length ? positions.slice(0, 4).map((pos: any, index: number) => (
        <div key={index}><StatusLine label={String(pos.symbol ?? pos.ticker ?? `Position ${index + 1}`)} value={String(pos.qty ?? pos.quantity ?? pos.side ?? 'active')} tone="blue" /></div>
      )) : <p>No Pulse position rows returned.</p>}
      <h4>Queue</h4>
      {queue.length ? queue.slice(0, 4).map((item: any, index: number) => (
        <div key={index}><StatusLine label={String(item.symbol ?? item.action ?? `Queue ${index + 1}`)} value={String(item.status ?? item.state ?? 'queued')} tone="warn" /></div>
      )) : Number.isFinite(queueSize) ? (
        <>
          <StatusLine label="Queue size" value={String(queueSize)} tone={queueSize > 0 ? 'warn' : 'ok'} />
          {Number.isFinite(defaultTtl) && <StatusLine label="Default TTL" value={`${defaultTtl}s`} tone="blue" />}
          {Number.isFinite(emergencyTtl) && <StatusLine label="Emergency TTL" value={`${emergencyTtl}s`} tone="gold" />}
        </>
      ) : <p>No Pulse queue rows returned.</p>}
      <h4>Handoff Contract</h4>
      {schemaPayload ? (
        <>
          <StatusLine label="Contract version" value={String(schemaPayload.contract_version ?? 'unknown')} tone="blue" />
          <StatusLine label="Recommended endpoint" value={String(schemaPayload.recommended_endpoint ?? '--')} tone="gold" />
          <StatusLine label="Idempotency header" value={idempotencyHeader ? 'Required' : 'Missing'} tone={idempotencyHeader ? 'ok' : 'bad'} />
        </>
      ) : <p>Pulse handoff contract unavailable.</p>}
    </div>
  );
}

function SettingsPanel({ livePolling, setLivePolling, heatMode, setHeatMode }: { livePolling: boolean; setLivePolling: (value: boolean) => void; heatMode: HeatMode; setHeatMode: (mode: HeatMode) => void }) {
  return (
    <div className="se-settings-panel">
      <label><input type="checkbox" checked={livePolling} onChange={(event) => setLivePolling(event.target.checked)} /> Live polling</label>
      <label>Default heat map mode
        <select value={heatMode} onChange={(event) => setHeatMode(event.target.value as HeatMode)}>
          <option>GEX</option>
          <option>VEX</option>
          <option>VOL</option>
        </select>
      </label>
      <p>Secrets stay in the backend environment. This console only renders backend state and operator controls.</p>
    </div>
  );
}

function ReadinessDetails({ snapshot }: { snapshot: EdgeSnapshot }) {
  const ready = snapshot.ready.data as any;
  const failingChecks = Array.isArray(ready?.failing_check_details) ? ready.failing_check_details : [];
  const allChecks = collectionRows(ready?.check_details);
  const failingNames = new Set(failingChecks.map((check: any) => String(check?.name ?? check?.key ?? check?.label ?? '')));
  const checks = [
    ...failingChecks,
    ...allChecks.filter((check: any) => !failingNames.has(String(check?.name ?? check?.key ?? check?.label ?? ''))),
  ];
  const providers = collectionRows(snapshot.providers.data, ['providers', 'items', 'health']);
  const marketDataProviders = collectionRows(snapshot.marketDataProviders.data, ['providers', 'items', 'market_data_providers']);
  return (
    <div className="se-readiness-details">
      <div>
        <h4>Readiness</h4>
        {Array.isArray(checks) && checks.length ? checks.slice(0, 8).map((check: any, index: number) => (
          <div key={check.name ?? check.key ?? index}><StatusLine label={String(check.label ?? check.name ?? check.key ?? `Check ${index + 1}`)} value={check.ready === false ? 'Blocked' : 'Ready'} tone={check.ready === false ? 'bad' : 'ok'} /></div>
        )) : <p>No readiness checks returned.</p>}
      </div>
      <div>
        <h4>Providers</h4>
        {providers.length ? providers.slice(0, 8).map((provider: any, index: number) => (
          <div key={provider.name ?? provider.key ?? index}><StatusLine label={String(provider.label ?? provider.name ?? provider.provider ?? provider.key ?? `Provider ${index + 1}`)} value={String(provider.status ?? provider.state ?? (provider.healthy === false ? 'Unhealthy' : 'Healthy'))} tone={provider.healthy === false || String(provider.status ?? provider.state ?? '').toLowerCase().includes('fail') ? 'bad' : 'ok'} /></div>
        )) : <p>No provider rows returned.</p>}
      </div>
      <div>
        <h4>Market Data</h4>
        {marketDataProviders.length ? marketDataProviders.slice(0, 8).map((provider: any, index: number) => (
          <div key={provider.name ?? provider.provider ?? provider.key ?? index}><StatusLine label={String(provider.label ?? provider.name ?? provider.provider ?? provider.key ?? `Market provider ${index + 1}`)} value={String(provider.status ?? provider.state ?? (provider.enabled ? (provider.configured ? 'Configured' : provider.requires_key ? 'Needs key' : 'Enabled') : 'Disabled'))} tone={provider.enabled ? (provider.configured ? 'ok' : 'warn') : 'bad'} /></div>
        )) : <p>No market-data provider rows returned.</p>}
      </div>
    </div>
  );
}

function ExpandedPanel({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="se-modal-backdrop" role="dialog" aria-modal="true" aria-label={title}>
      <div className="se-modal">
        <header>
          <h2>{title}</h2>
          <button type="button" className="se-icon-btn" onClick={onClose} aria-label="Close expanded panel">×</button>
        </header>
        <div className="se-modal-body">{children}</div>
      </div>
    </div>
  );
}
