import type React from 'react';

export type Mode = 'monitor' | 'command' | 'protect' | 'operations' | 'settings';
export type OperationsView = 'overview' | 'advisor' | 'experience' | 'protection' | 'pnl' | 'markets' | 'portfolio' | 'settings' | 'tutorials';
export type Tone = 'green' | 'cyan' | 'gold' | 'red';
export type EventFilter = 'all' | 'selected' | 'system';

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
  killSwitchActive: boolean;
  schedulerPaused: boolean;
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
