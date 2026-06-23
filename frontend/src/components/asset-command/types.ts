import type React from 'react';

export type Mode = 'monitor' | 'command' | 'market-map' | 'protect' | 'operations' | 'settings';
export type OperationsView = 'overview' | 'charts' | 'scanners' | 'advisor' | 'experience' | 'protection' | 'pnl' | 'markets' | 'portfolio' | 'settings' | 'tutorials';
export type Tone = 'green' | 'cyan' | 'gold' | 'red';
export type EventFilter = 'all' | 'selected' | 'system';
export type CoreColorMetric = 'risk' | 'signal' | 'flow' | 'drawdown';
export type CoreSizeMetric = 'exposure' | 'liquidity' | 'volatility';
export type CoreUniverse = 'watchlist' | 'watchers' | 'all';
export type CoreLabelMode = 'symbol' | 'signal' | 'heat';

export interface Watcher {
  plugin: string;
  status: string;
  trigger: string;
  source: string;
}

export interface Metric {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}

export interface Ticker {
  symbol: string;
  change: string;
  status: string;
  signal: string;
  price: number;
  watchers: Watcher[];
  metrics: Metric[];
}

export interface EventLine {
  id: string;
  symbol: string;
  title: string;
  detail: string;
  time: string;
}

export interface RuntimeState {
  connected: boolean;
  loading: boolean;
  pulseAvailable: boolean;
  pulseCircuitState?: string;
  edgeLive: boolean;
  killSwitchActive: boolean;
  schedulerPaused: boolean;
  runtimeReady: boolean;
  readinessFailingChecks: string[];
  edgePid?: number;
  edgeUptimeSeconds?: number;
  edgeLiveTimestamp?: string;
  rateLimitPressure: 'normal' | 'warning' | 'unknown';
  rateLimitRemaining?: number;
  rateLimitResetSeconds?: number;
  frontendRumStatus: 'receiving' | 'waiting' | 'unknown';
  frontendRumSampleCount?: number;
  frontendRumRouteCount?: number;
  frontendRumLastRoute?: string | null;
  frontendRumAgeSeconds?: number | null;
  updatedAt?: string;
  error?: string;
}

export interface OperationViewItem {
  id: OperationsView;
  label: string;
  icon: React.ElementType;
}

export interface ProtectionRow {
  symbol: string;
  guard: string;
  exposure: string;
  stop: string;
  invalid: string;
  heat: string;
  action: string;
  tone: Tone;
}

export interface SignalIntelligenceModel {
  move: string;
  price: string;
  delta: string;
  state: string;
  pressure: string;
  contributors: { label: string; value: string; tone: Tone }[];
}

export interface CoreHeatmapConfig {
  colorMetric: CoreColorMetric;
  sizeMetric: CoreSizeMetric;
  universe: CoreUniverse;
  horizon: string;
  density: number;
  alertThreshold: number;
  includeIdle: boolean;
  autoFocusTicker: boolean;
  labelMode: CoreLabelMode;
  operatorNote: string;
}
