import type React from 'react';

export type Mode = 'command' | 'charting' | 'greeks' | 'directives' | 'protect' | 'operations' | 'settings';
export type OperationsView = 'overview' | 'scanners' | 'advisor' | 'experience' | 'protection' | 'pnl' | 'markets' | 'portfolio' | 'settings' | 'tutorials';
export type Tone = 'green' | 'cyan' | 'gold' | 'red';
export type EventFilter = 'all' | 'selected';
export type CoreColorMetric = 'risk' | 'signal' | 'flow' | 'drawdown';
export type CoreSizeMetric = 'exposure' | 'liquidity' | 'volatility';
export type CoreUniverse = 'watchlist' | 'watchers' | 'all';
export type CoreLabelMode = 'symbol' | 'signal' | 'heat';
export type BridgeStatus = 'online' | 'degraded' | 'offline' | 'standalone';
export type DirectiveTone = Tone | 'note';

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

export interface DirectiveLedgerEntry {
  id: string;
  time: string;
  bot: string;
  symbol: string;
  directive: string;
  reason: string;
  confidence: string;
  regime: string;
  acknowledgement: string;
  tone: DirectiveTone;
}

export interface BotBridgeHealth {
  name: string;
  status: BridgeStatus;
  heartbeat: string;
  latency: string;
  contract: string;
  lastDirective: string;
  lastAck: string;
  queueDepth: number;
  rejectedEvents: number;
  detail: string;
  tone: Tone;
}

export interface PolicyStackRule {
  id: string;
  label: string;
  state: string;
  strictness: number;
  reason: string;
  effect: string;
  tone: Tone;
}

export interface OutcomeAttribution {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}

export interface MarketRegimeState {
  label: string;
  score: string;
  detail: string;
  pressure: string;
  allowedPosture: string;
  tone: Tone;
}

export interface BotLockout {
  bot: string;
  scope: string;
  state: string;
  reason: string;
  until: string;
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
