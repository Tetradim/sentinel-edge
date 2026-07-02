import type {
  ChartWorkspaceIndicatorId,
  ChartWorkspaceSnapshot,
  MarketMapContext,
  OrbSessionSummary,
} from '@/types';
import {
  INDICATOR_OPTIONS,
  INDICATOR_PRESET_OPTIONS,
  ORB_OVERLAY_SESSION_OPTIONS,
} from './chartWorkspaceConstants';
import type {
  ChartWorkspaceChartType,
  ChartWorkspaceIndicatorPresetId,
  ChartWorkspaceLayoutMode,
  ChartWorkspaceOrbOverlaySession,
  ChartWorkspaceSimulationLabExperiment,
  ChartWorkspaceSimulationLabResult,
  ChartWorkspaceSimulationLabStatus,
} from './chartWorkspaceTypes';

function humanizeWorkspaceLabel(value?: string) {
  if (!value) return '--';
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

export function formatMarketMapLevelPrice(value: number) {
  return Number.isFinite(value) ? `$${value.toFixed(2)}` : '--';
}

export function formatOrbSessionStatus(status?: string) {
  return humanizeWorkspaceLabel(status);
}

export function formatOrbReadiness(readiness?: string) {
  return humanizeWorkspaceLabel(readiness);
}

export function formatOrbSessionLevelSummary(session: OrbSessionSummary) {
  const levels = session.levels ?? {};
  const lockedTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.locked);
  if (lockedTimeframes.length) return `${lockedTimeframes.join(', ')} locked`;

  const validTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.is_valid);
  if (validTimeframes.length) return `${validTimeframes.join(', ')} collecting`;

  return `${session.timeframes.join(', ')} configured`;
}

export function formatOrbSessionReadinessDetail(session: OrbSessionSummary) {
  const parts: string[] = [];
  if (session.ready_timeframes.length) parts.push(`ready ${session.ready_timeframes.join(', ')}`);
  if (session.collecting_timeframes.length) parts.push(`collecting ${session.collecting_timeframes.join(', ')}`);
  if (session.missing_timeframes.length) parts.push(`missing ${session.missing_timeframes.join(', ')}`);
  return parts.length ? parts.join(' / ') : formatOrbReadiness(session.readiness);
}

export function formatIndicatorPresetLabel(indicatorPreset: ChartWorkspaceIndicatorPresetId) {
  if (indicatorPreset === 'custom') return 'Custom';
  return INDICATOR_PRESET_OPTIONS.find((preset) => preset.id === indicatorPreset)?.label || 'Custom';
}

export function formatSelectedIndicators(indicators: ChartWorkspaceIndicatorId[]) {
  if (!indicators.length) return 'None';
  return indicators
    .map(formatIndicatorOptionLabel)
    .join(', ');
}

function formatIndicatorOptionLabel(indicator: ChartWorkspaceIndicatorId) {
  return INDICATOR_OPTIONS.find((option) => option.id === indicator)?.label || indicator.toUpperCase();
}

export function buildMarketMapBias(snapshot: ChartWorkspaceSnapshot | null) {
  const latest = snapshot?.bars?.[snapshot.bars.length - 1];
  const vwap = snapshot?.levels?.items?.find((level) => level.kind === 'vwap');
  if (!latest || !vwap) return 'Review';
  if (latest.close > vwap.price) return 'Above VWAP';
  if (latest.close < vwap.price) return 'Below VWAP';
  return 'At VWAP';
}

export function formatNearestMarketMapLevel(snapshot: ChartWorkspaceSnapshot | null) {
  const latest = snapshot?.bars?.[snapshot.bars.length - 1];
  const levels = snapshot?.levels?.items ?? [];
  if (!latest || !levels.length) return '--';
  const nearest = levels.reduce(
    (best, level) => {
      const distance = Math.abs(level.price - latest.close);
      return distance < best.distance ? { level, distance } : best;
    },
    { level: levels[0], distance: Math.abs(levels[0].price - latest.close) },
  );
  return `${nearest.level.label} ${formatMarketMapLevelPrice(nearest.level.price)}`;
}

export function formatParserConfidence(value: unknown) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '--';
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`;
}

export function formatProofMarkerTimestamp(value: string) {
  if (!value) return '--';
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return timestamp.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function formatMarketMapContextStatus(value?: string) {
  return humanizeWorkspaceLabel(value);
}

export function formatMarketMapContextProximity(context: MarketMapContext | null) {
  const proximity = context?.level_proximity;
  if (!proximity) return '--';
  const label = proximity.label || proximity.id || 'Level';
  const price = typeof proximity.price === 'number' ? formatMarketMapLevelPrice(proximity.price) : '--';
  if (typeof proximity.distance_pct !== 'number') return `${label} ${price}`;
  return `${label} ${price} / ${(proximity.distance_pct * 100).toFixed(2)}%`;
}

export function formatOrbOverlaySessionSummary(
  showOrbOverlays: boolean,
  orbOverlaySessions: ChartWorkspaceOrbOverlaySession[],
) {
  if (!showOrbOverlays) return 'Off';
  if (!orbOverlaySessions.length) return 'None';
  return orbOverlaySessions
    .map((session) => ORB_OVERLAY_SESSION_OPTIONS.find((option) => option.id === session)?.label || session)
    .join(', ');
}

export function formatVolumeOverlay(showVolume: boolean) {
  return showVolume ? 'On' : 'Off';
}

export function formatSimulationLabGate(
  simulationLabStatus: ChartWorkspaceSimulationLabStatus | null,
  simulationLabEnabled: boolean,
) {
  if (!simulationLabStatus) return 'Unknown';
  return simulationLabEnabled ? 'Enabled' : 'Hidden';
}

export function formatSimulationLabDisabledReason(simulationLabStatus: ChartWorkspaceSimulationLabStatus | null) {
  return simulationLabStatus?.disabled_reason || '--';
}

export function formatChartType(chartType: ChartWorkspaceChartType) {
  return chartType === 'candlestick' ? 'Candle' : 'Line';
}

export function formatLayoutMode(layoutMode: ChartWorkspaceLayoutMode) {
  return humanizeWorkspaceLabel(layoutMode);
}

export function formatSimulationLabEndpoint(experiment: ChartWorkspaceSimulationLabExperiment) {
  const method = experiment.http_method || 'POST';
  const endpoint = experiment.endpoint_path || 'endpoint unavailable';
  const schemaVersion = experiment.result_schema_version || 'schema unknown';
  return `${method} ${endpoint} / ${schemaVersion}`;
}

export function formatSimulationLabExperimentId(id?: string) {
  if (!id) return 'Experiment';
  return humanizeWorkspaceLabel(id);
}

export function formatSimulationLabResultTitle(result: ChartWorkspaceSimulationLabResult) {
  const schemaVersion = result.result.schema_version || 'schema_version unknown';
  return `${result.label} / ${schemaVersion}`;
}

export function formatSimulationLabResultMeta(result: ChartWorkspaceSimulationLabResult) {
  const parts: string[] = [];
  if (result.symbol) parts.push(result.symbol);
  if (result.created_at) parts.push(formatSimulationLabResultTimestamp(result.created_at));
  return parts.length ? parts.join(' / ') : 'Session context unavailable';
}

export function formatSimulationLabResultMismatch(result: ChartWorkspaceSimulationLabResult, activeChartSymbol: string) {
  return `Result symbol differs from active chart: ${result.symbol || 'Unknown'} vs ${activeChartSymbol}`;
}

export function formatSimulationLabResultScopeLabel(hasSymbolMismatch: boolean) {
  return hasSymbolMismatch ? 'Different chart' : 'Current chart';
}

export function formatSimulationLabResultScopeClass(hasSymbolMismatch: boolean) {
  const baseClass = 'rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase';
  return hasSymbolMismatch
    ? `${baseClass} border-amber-400/30 bg-amber-400/10 text-amber-200`
    : `${baseClass} border-emerald-400/30 bg-emerald-400/10 text-emerald-200`;
}

function formatSimulationLabResultTimestamp(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return timestamp.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function buildSimulationLabResultMetrics(
  result: ChartWorkspaceSimulationLabResult,
  formatMetric = formatSimulationLabResultMetric,
) {
  const summary = result.result.summary ?? {};
  const metrics = [
    {
      label: 'schema_version',
      value: result.result.schema_version || '--',
    },
    {
      label: 'run_id',
      value: result.result.run_id || '--',
    },
    {
      label: 'input_fp',
      value: formatSimulationLabFingerprint(result.result.input_fingerprint),
    },
  ];

  if (result.kind === 'orb_backtest') {
    metrics.push(
      { label: 'breakouts', value: formatMetric(summary.breakouts) },
      { label: 'sessions', value: formatMetric(summary.sessions) },
      { label: 'scored_breakouts', value: formatMetric(summary.scored_breakouts) },
      { label: 'avg_reward_r', value: formatMetric(summary.avg_reward_r_multiple) },
      { label: 'target_hits', value: formatMetric(summary.target_hits) },
      { label: 'stop_hits', value: formatMetric(summary.stop_hits) },
      { label: 'avg_realized_r', value: formatMetric(summary.avg_realized_r_multiple) },
    );
  }

  if (result.kind === 'buying_power_allocation') {
    metrics.push(
      { label: 'allocated_notional', value: formatMetric(summary.allocated_notional, 'currency') },
      { label: 'allocated_count', value: formatMetric(summary.allocated_count) },
      { label: 'skipped_count', value: formatMetric(summary.skipped_count) },
      { label: 'fill_ratio', value: formatMetric(summary.fill_ratio, 'ratio') },
      { label: 'unfilled_requested', value: formatMetric(summary.unfilled_requested_notional, 'currency') },
      { label: 'skipped_reason', value: formatSimulationLabAllocationSkipReason(result.result.skipped) },
      { label: 'position_limited', value: formatMetric(summary.position_limited_count) },
      { label: 'post_cap_fill', value: formatMetric(summary.post_cap_fill_ratio, 'ratio') },
    );
  }

  if (result.kind === 'stop_trailing_dca') {
    metrics.push(
      { label: 'best_plan', value: formatMetric(summary.best_plan) },
      { label: 'best_pnl', value: formatMetric(summary.best_pnl, 'currency') },
      { label: 'best_pnl_pct', value: formatMetric(summary.best_pnl_pct, 'percent') },
      { label: 'worst_pnl_pct', value: formatMetric(summary.worst_pnl_pct, 'percent') },
    );
  }

  return metrics;
}

function formatSimulationLabAllocationSkipReason(value: unknown) {
  if (!Array.isArray(value) || value.length === 0) return '--';
  const reasons = Array.from(new Set(value.map((item) => {
    if (!isRecord(item) || typeof item.reason !== 'string') return '';
    if (item.reason === 'buying_power_exhausted') return 'buying power exhausted';
    if (item.reason === 'position_limit') return 'position limit';
    return item.reason.replace(/[_-]+/g, ' ');
  }).filter(Boolean)));
  return reasons.length ? reasons.join(', ') : '--';
}

function formatSimulationLabResultMetric(value: unknown, mode: 'plain' | 'currency' | 'percent' | 'ratio' = 'plain') {
  if (value === null || value === undefined || value === '') return '--';
  if (mode === 'currency' && typeof value === 'number') return `$${value.toLocaleString()}`;
  if (mode === 'percent' && typeof value === 'number') return `${value.toFixed(2)}%`;
  if (mode === 'ratio' && typeof value === 'number') return `${(value * 100).toFixed(2)}%`;
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value).replace(/[_-]+/g, ' ');
}

function formatSimulationLabFingerprint(value: unknown) {
  if (typeof value !== 'string' || !value) return '--';
  return value.length > 12 ? `${value.slice(0, 12)}...` : value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}
