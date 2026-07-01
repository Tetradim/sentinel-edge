import type {
  ChartWorkspaceIndicatorId,
  ChartWorkspaceIndicatorPoint,
  ChartWorkspaceSnapshot,
  MarketMapProofMarker,
} from '@/types';
import { DEFAULT_ORB_OVERLAY_SESSIONS, INDICATOR_OPTIONS } from './chartWorkspaceConstants';
import { formatMarketMapLevelPrice } from './chartWorkspaceFormatters';
import type {
  ChartWorkspaceChartType,
  ChartWorkspaceIndicatorSnapshotMetric,
  ChartWorkspaceOrbOverlaySession,
} from './chartWorkspaceTypes';

export function buildPriceTraces(
  snapshot: ChartWorkspaceSnapshot | null,
  chartType: ChartWorkspaceChartType,
  includeOrbOverlays = true,
  includeVolume = true,
  includeOrbOverlaySession: ChartWorkspaceOrbOverlaySession[] = DEFAULT_ORB_OVERLAY_SESSIONS,
  proofMarkers: MarketMapProofMarker[] = [],
) {
  if (!snapshot) return [];
  const x = snapshot.bars.map((bar) => bar.timestamp);
  const baseTrace = chartType === 'candlestick'
    ? {
        x,
        open: snapshot.bars.map((bar) => bar.open),
        high: snapshot.bars.map((bar) => bar.high),
        low: snapshot.bars.map((bar) => bar.low),
        close: snapshot.bars.map((bar) => bar.close),
        type: 'candlestick',
        name: snapshot.symbol,
        increasing: { line: { color: '#39ff88' }, fillcolor: 'rgba(57, 255, 136, 0.18)' },
        decreasing: { line: { color: '#ff3b4f' }, fillcolor: 'rgba(255, 59, 79, 0.18)' },
      }
    : {
        x,
        y: snapshot.bars.map((bar) => bar.close),
        type: 'scatter',
        mode: 'lines',
        name: snapshot.symbol,
        line: { color: '#f5b342', width: 2.5 },
      };
  const volumeTrace = includeVolume
    ? {
        x,
        y: snapshot.bars.map((bar) => bar.volume),
        type: 'bar',
        name: 'Volume',
        yaxis: 'y2',
        marker: {
          color: snapshot.bars.map((bar) =>
            bar.close >= bar.open ? 'rgba(57, 255, 136, 0.22)' : 'rgba(255, 59, 79, 0.22)',
          ),
        },
        opacity: 0.35,
        hovertemplate: 'Volume %{y:,}<extra></extra>',
      }
    : null;
  const indicatorTraces = Object.entries(snapshot.indicators)
    .filter(([, indicator]) => indicator.kind === 'overlay')
    .map(([id, indicator]) => ({
      x: indicator.points.map((point) => point.timestamp),
      y: indicator.points.map((point) => point.value),
      type: 'scatter',
      mode: 'lines',
      name: indicator.label || id,
      line: { color: indicatorTraceColor(id), width: 1.5 },
    }));
  const enabledOrbOverlaySessions = new Set(includeOrbOverlaySession);
  const orbTraces = includeOrbOverlays
    ? snapshot.orb_overlays
        .filter((overlay) => enabledOrbOverlaySessions.has(overlay.session_id as ChartWorkspaceOrbOverlaySession))
        .flatMap((overlay) => [
          orbLineTrace(x, overlay.high, `${overlay.label} ${overlay.timeframe} high`, '#f59e0b'),
          orbLineTrace(x, overlay.low, `${overlay.label} ${overlay.timeframe} low`, '#8b5cf6'),
        ])
    : [];
  return [
    baseTrace,
    ...(volumeTrace ? [volumeTrace] : []),
    ...indicatorTraces,
    ...buildMarketMapLevelTraces(snapshot),
    ...buildMarketMapProofMarkerTraces(snapshot, proofMarkers),
    ...orbTraces,
  ];
}

function buildMarketMapLevelTraces(snapshot: ChartWorkspaceSnapshot | null) {
  const bars = snapshot?.bars ?? [];
  const levels = snapshot?.levels?.items ?? [];
  if (!bars.length || !levels.length) return [];
  const x = [bars[0].timestamp, bars[bars.length - 1].timestamp];
  return levels
    .filter((level) => Number.isFinite(level.price))
    .map((level) => ({
      x,
      y: [level.price, level.price],
      type: 'scatter',
      mode: 'lines',
      name: level.label,
      line: {
        color: marketMapLevelColor(level.kind),
        dash: level.locked ? 'solid' : 'dot',
        width: 1.25,
      },
      hovertemplate: `${level.label}: ${formatMarketMapLevelPrice(level.price)}<extra></extra>`,
    }));
}

function buildMarketMapProofMarkerTraces(
  snapshot: ChartWorkspaceSnapshot | null,
  markers: MarketMapProofMarker[],
) {
  const bars = snapshot?.bars ?? [];
  if (!bars.length || !markers.length) return [];
  const latestClose = bars[bars.length - 1].close;
  return markers
    .filter((marker) => marker.timestamp)
    .map((marker) => {
      const proofPrice = resolveProofMarkerPrice(marker);
      return {
        x: [marker.timestamp],
        y: [proofPrice ?? latestClose],
        type: 'scatter',
        mode: 'markers+text',
        name: marker.label,
        text: [marker.kind],
        textposition: 'top center',
        marker: {
          size: 10,
          color: marker.status === 'accepted' || marker.status === 'pass' ? '#22c55e' : '#f59e0b',
          symbol: 'diamond',
        },
        hovertemplate: `${marker.label}<br>${marker.kind}<br>${marker.status}<extra></extra>`,
      };
    });
}

export function buildOscillatorTraces(snapshot: ChartWorkspaceSnapshot | null) {
  if (!snapshot) return [];
  const traces: any[] = [];
  Object.entries(snapshot.indicators).forEach(([id, indicator]) => {
    if (indicator.kind !== 'oscillator') return;
    if (id.startsWith('rsi_')) {
      traces.push({
        x: indicator.points.map((point) => point.timestamp),
        y: indicator.points.map((point) => point.value),
        type: 'scatter',
        mode: 'lines',
        name: indicator.label,
        line: { color: '#a78bfa', width: 2 },
      });
    }
    if (id === 'macd') {
      traces.push(
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.macd),
          type: 'scatter',
          mode: 'lines',
          name: 'MACD',
          line: { color: '#22d3ee', width: 1.5 },
        },
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.signal),
          type: 'scatter',
          mode: 'lines',
          name: 'Signal',
          line: { color: '#f59e0b', width: 1.5 },
        },
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.histogram),
          type: 'bar',
          name: 'Histogram',
          marker: { color: '#64748b' },
        },
      );
    }
  });
  return traces;
}

export function buildIndicatorSnapshotMetrics(
  snapshot: ChartWorkspaceSnapshot | null,
  selectedIndicators: ChartWorkspaceIndicatorId[],
): ChartWorkspaceIndicatorSnapshotMetric[] {
  if (!snapshot) return [];
  const metrics: ChartWorkspaceIndicatorSnapshotMetric[] = [];

  selectedIndicators.forEach((id) => {
    const indicator = snapshot.indicators[id];
    if (!indicator) return;
    const latestPoint = findLatestIndicatorPoint(indicator.points);
    metrics.push({
      label: indicator.label || INDICATOR_OPTIONS.find((option) => option.id === id)?.label || id.toUpperCase(),
      value: formatIndicatorSnapshotValue(id, latestPoint),
      timestamp: latestPoint?.timestamp,
    });
  });

  return metrics;
}

function findLatestIndicatorPoint(points: ChartWorkspaceIndicatorPoint[]) {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    if (
      (point.value !== null && point.value !== undefined) ||
      (point.macd !== null && point.macd !== undefined) ||
      (point.signal !== null && point.signal !== undefined) ||
      (point.histogram !== null && point.histogram !== undefined)
    ) {
      return point;
    }
  }
  return undefined;
}

function formatIndicatorSnapshotValue(id: ChartWorkspaceIndicatorId, point?: ChartWorkspaceIndicatorPoint) {
  if (!point) return '--';
  if (id === 'macd') {
    return [
      `MACD ${formatIndicatorPointNumber(point.macd)}`,
      `Sig ${formatIndicatorPointNumber(point.signal)}`,
      `Hist ${formatIndicatorPointNumber(point.histogram)}`,
    ].join(' / ');
  }
  return formatIndicatorPointNumber(point.value);
}

function formatIndicatorPointNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(4);
}

function orbLineTrace(x: string[], y: number, name: string, color: string) {
  return {
    x: [x[0], x[x.length - 1]],
    y: [y, y],
    type: 'scatter',
    mode: 'lines',
    name,
    line: { color, dash: 'dot', width: 1.5 },
  };
}

function marketMapLevelColor(kind: string) {
  const normalizedKind = kind.toLowerCase();
  if (normalizedKind.includes('risk') || normalizedKind.includes('stop')) return '#ff3b4f';
  if (normalizedKind.includes('resistance') || normalizedKind.includes('high') || normalizedKind.includes('upper')) {
    return '#f59e0b';
  }
  if (normalizedKind.includes('support') || normalizedKind.includes('low') || normalizedKind.includes('lower')) {
    return '#39ff88';
  }
  if (normalizedKind === 'vwap') return '#f5b342';
  if (normalizedKind.includes('breakout')) return '#b66dff';
  return '#8b5cf6';
}

function indicatorTraceColor(id: string) {
  if (id === 'ema_9') return '#f5b342';
  if (id === 'ema_20') return '#b66dff';
  if (id === 'sma_20') return '#39ff88';
  if (id === 'sma_50') return '#8b5cf6';
  if (id === 'sma_200') return '#ff3b4f';
  if (id === 'vwap') return '#f59e0b';
  return '#d8b4fe';
}

function resolveProofMarkerPrice(marker: MarketMapProofMarker) {
  const price = marker.proof?.price ?? marker.proof?.entry_price ?? marker.proof?.fill_price;
  if (typeof price === 'number' && Number.isFinite(price)) return price;
  if (typeof price === 'string') {
    const numericPrice = Number(price);
    return Number.isFinite(numericPrice) ? numericPrice : undefined;
  }
  return undefined;
}
