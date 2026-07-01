import type {
  ChartWorkspaceIndicatorId,
  ChartWorkspaceIndicatorPoint,
  ChartWorkspaceSnapshot,
  MarketMapContext,
  MarketMapProofMarker,
  OrbSessionSummary,
} from '@/types';
import { DEFAULT_INDICATORS, FALLBACK_PRICE_ANCHORS } from './chartWorkspaceConstants';
import { normalizeChartWorkspaceSymbol } from './chartWorkspaceSymbols';
import type { ChartWorkspaceBarLimit } from './chartWorkspaceTypes';

export function buildFallbackChartWorkspaceSnapshot(
  symbol: string,
  selectedIndicators: ChartWorkspaceIndicatorId[],
  limit: ChartWorkspaceBarLimit,
): ChartWorkspaceSnapshot {
  const normalizedSymbol = normalizeChartWorkspaceSymbol(symbol);
  const basePrice = resolveFallbackBasePrice(normalizedSymbol);
  const barCount = Math.max(60, Math.min(limit, 390));
  const bars = buildFallbackBars(normalizedSymbol, basePrice, barCount);
  const indicators = buildFallbackIndicators(bars, selectedIndicators);
  const levels = buildFallbackLevels(normalizedSymbol, bars, basePrice);
  const orbOverlays = buildFallbackOrbOverlays(bars, basePrice);

  return {
    schema_version: 'chart_workspace.local_preview.v1',
    symbol: normalizedSymbol,
    timeframe: '1m',
    source: 'sentinel-edge-local-preview',
    summary: {
      bar_count: bars.length,
      available_bar_count: bars.length,
      indicator_count: Object.keys(indicators).length,
      orb_overlay_count: orbOverlays.length,
    },
    bars,
    indicators,
    levels,
    orb_overlays: orbOverlays,
    orb_session_status: buildFallbackOrbSessionStatus(orbOverlays),
  };
}

function buildFallbackBars(symbol: string, basePrice: number, barCount: number): ChartWorkspaceSnapshot['bars'] {
  const seed = getFallbackSymbolSeed(symbol);
  const sessionStart = new Date();
  sessionStart.setHours(8, 30, 0, 0);
  const volatility = Math.max(basePrice * 0.0012, 0.24);
  const drift = basePrice * (((seed % 13) - 6) / 100000);
  const bars: ChartWorkspaceSnapshot['bars'] = [];
  let previousClose = roundFallbackPrice(basePrice - volatility * 0.8);

  for (let index = 0; index < barCount; index += 1) {
    const timestamp = new Date(sessionStart.getTime() + index * 60_000).toISOString();
    const progress = index / Math.max(1, barCount - 1);
    const primaryWave = Math.sin(index / 8 + seed * 0.011) * volatility * 1.8;
    const secondaryWave = Math.cos(index / 23 + seed * 0.007) * volatility * 1.15;
    const breakoutRamp = Math.max(0, progress - 0.68) * volatility * 5.4;
    const meanReversion = (progress - 0.5) * drift * barCount;
    const close = roundFallbackPrice(basePrice + primaryWave + secondaryWave + breakoutRamp + meanReversion);
    const open = index === 0 ? roundFallbackPrice(close - volatility * 0.25) : previousClose;
    const wick = volatility * (0.45 + Math.abs(Math.sin((index + seed) / 5)) * 0.7);
    const high = roundFallbackPrice(Math.max(open, close) + wick);
    const low = roundFallbackPrice(Math.min(open, close) - wick * 0.9);
    const volumePulse = 1 + Math.abs(Math.sin(index / 14 + seed)) * 0.9 + Math.max(0, progress - 0.72) * 1.6;
    const volume = Math.round((850000 + (seed % 9) * 45000) * volumePulse);

    bars.push({ timestamp, open, high, low, close, volume });
    previousClose = close;
  }

  return bars;
}

function buildFallbackIndicators(
  bars: ChartWorkspaceSnapshot['bars'],
  selectedIndicators: ChartWorkspaceIndicatorId[],
): ChartWorkspaceSnapshot['indicators'] {
  const closes = bars.map((bar) => bar.close);
  const indicatorBuilders: Record<ChartWorkspaceIndicatorId, () => ChartWorkspaceSnapshot['indicators'][string]> = {
    ema_9: () => ({
      label: 'EMA 9',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateExponentialMovingAverage(closes, 9)),
    }),
    ema_20: () => ({
      label: 'EMA 20',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateExponentialMovingAverage(closes, 20)),
    }),
    sma_20: () => ({
      label: 'SMA 20',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateSimpleMovingAverage(closes, 20)),
    }),
    sma_50: () => ({
      label: 'SMA 50',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateSimpleMovingAverage(closes, 50)),
    }),
    sma_200: () => ({
      label: 'SMA 200',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateSimpleMovingAverage(closes, 200)),
    }),
    vwap: () => ({
      label: 'VWAP',
      kind: 'overlay',
      points: mapFallbackValuePoints(bars, calculateVolumeWeightedAverage(bars)),
    }),
    rsi_14: () => ({
      label: 'RSI 14',
      kind: 'oscillator',
      points: mapFallbackValuePoints(bars, calculateRelativeStrengthIndex(closes, 14)),
    }),
    macd: () => {
      const macd = calculateMovingAverageConvergenceDivergence(closes);
      return {
        label: 'MACD',
        kind: 'oscillator',
        points: bars.map((bar, index) => ({
          timestamp: bar.timestamp,
          macd: macd.macd[index],
          signal: macd.signal[index],
          histogram: macd.histogram[index],
        })),
      };
    },
    atr_14: () => ({
      label: 'ATR 14',
      kind: 'oscillator',
      points: mapFallbackValuePoints(bars, calculateAverageTrueRange(bars, 14)),
    }),
  };

  return selectedIndicators.reduce<ChartWorkspaceSnapshot['indicators']>((indicators, indicatorId) => {
    indicators[indicatorId] = indicatorBuilders[indicatorId]();
    return indicators;
  }, {});
}

function buildFallbackLevels(
  symbol: string,
  bars: ChartWorkspaceSnapshot['bars'],
  basePrice: number,
): NonNullable<ChartWorkspaceSnapshot['levels']> {
  const latest = bars[bars.length - 1];
  const latestPrice = latest?.close ?? basePrice;
  const timestamp = latest?.timestamp ?? new Date().toISOString();
  const span = Math.max(latestPrice * 0.006, 0.55);

  return {
    schema_version: 'market_map_levels.local_preview.v1',
    items: [
      {
        id: `${symbol}-support-shelf`,
        label: 'Support shelf',
        kind: 'support',
        price: roundFallbackPrice(latestPrice - span * 1.45),
        source: 'local preview',
        session: 'regular',
        confidence: 0.86,
        timestamp,
        locked: true,
      },
      {
        id: `${symbol}-vwap`,
        label: 'Session VWAP',
        kind: 'vwap',
        price: roundFallbackPrice(calculateFallbackSessionVwap(bars) ?? latestPrice - span * 0.2),
        source: 'local preview',
        session: 'regular',
        confidence: 0.78,
        timestamp,
        locked: true,
      },
      {
        id: `${symbol}-resistance-cap`,
        label: 'Resistance cap',
        kind: 'resistance',
        price: roundFallbackPrice(latestPrice + span * 1.2),
        source: 'local preview',
        session: 'regular',
        confidence: 0.82,
        timestamp,
        locked: true,
      },
      {
        id: `${symbol}-risk-pressure`,
        label: 'Do-not-buy pressure',
        kind: 'risk',
        price: roundFallbackPrice(latestPrice + span * 1.85),
        source: 'local preview',
        session: 'regular',
        confidence: 0.74,
        timestamp,
        locked: false,
      },
      {
        id: `${symbol}-breakout-trigger`,
        label: 'Breakout trigger',
        kind: 'breakout',
        price: roundFallbackPrice(latestPrice + span * 2.35),
        source: 'local preview',
        session: 'regular',
        confidence: 0.81,
        timestamp,
        locked: false,
      },
    ],
  };
}

function buildFallbackOrbOverlays(
  bars: ChartWorkspaceSnapshot['bars'],
  basePrice: number,
): ChartWorkspaceSnapshot['orb_overlays'] {
  const firstFifteen = bars.slice(0, Math.min(15, bars.length));
  const firstThirty = bars.slice(0, Math.min(30, bars.length));
  return [
    buildFallbackOrbOverlay('market_open', 'Market Open ORB', '15m', firstFifteen, basePrice),
    buildFallbackOrbOverlay('premarket_30m', 'Premarket ORB', '30m', firstThirty, basePrice),
  ];
}

function buildFallbackOrbOverlay(
  sessionId: string,
  label: string,
  timeframe: string,
  bars: ChartWorkspaceSnapshot['bars'],
  basePrice: number,
): ChartWorkspaceSnapshot['orb_overlays'][number] {
  const high = bars.length ? Math.max(...bars.map((bar) => bar.high)) : basePrice * 1.003;
  const low = bars.length ? Math.min(...bars.map((bar) => bar.low)) : basePrice * 0.997;
  return {
    session_id: sessionId,
    label,
    timeframe,
    high: roundFallbackPrice(high),
    low: roundFallbackPrice(low),
    range_width: roundFallbackPrice(high - low),
    locked: true,
    is_valid: true,
    date: new Date().toISOString().slice(0, 10),
  };
}

function buildFallbackOrbSessionStatus(
  overlays: ChartWorkspaceSnapshot['orb_overlays'],
): NonNullable<ChartWorkspaceSnapshot['orb_session_status']> {
  const marketOpenOverlay = overlays.find((overlay) => overlay.session_id === 'market_open') ?? overlays[0];
  const premarketOverlay = overlays.find((overlay) => overlay.session_id === 'premarket_30m') ?? overlays[1] ?? overlays[0];

  return {
    active_session: 'market_open',
    active_label: 'Market Open ORB',
    active_status: 'locked',
    active_ready: true,
    active_readiness: 'ready',
    active_ready_timeframes: ['15m', '30m'],
    active_missing_timeframes: [],
    sessions: {
      market_open: buildFallbackOrbSessionSummary('market_open', 'Market Open ORB', '15m', marketOpenOverlay),
      premarket_30m: buildFallbackOrbSessionSummary('premarket_30m', 'Premarket ORB', '30m', premarketOverlay),
    },
  };
}

function buildFallbackOrbSessionSummary(
  id: string,
  label: string,
  timeframe: string,
  overlay: ChartWorkspaceSnapshot['orb_overlays'][number],
): OrbSessionSummary {
  return {
    id,
    label,
    description: `${label} local preview levels`,
    status: 'locked',
    ready: true,
    readiness: 'ready',
    ready_timeframes: [timeframe],
    collecting_timeframes: [],
    missing_timeframes: [],
    start_time: new Date().toISOString(),
    timeframes: [timeframe],
    levels: {
      [timeframe]: {
        high: overlay.high,
        low: overlay.low,
        locked: overlay.locked,
        range_width: overlay.range_width,
        is_valid: overlay.is_valid,
        date: overlay.date,
        session_id: overlay.session_id,
        start_time: null,
        lock_time: new Date().toISOString(),
      },
    },
  };
}

export function buildFallbackProofMarkers(symbol: string, barLimit: ChartWorkspaceBarLimit): MarketMapProofMarker[] {
  const normalizedSymbol = normalizeChartWorkspaceSymbol(symbol);
  const bars = buildFallbackBars(normalizedSymbol, resolveFallbackBasePrice(normalizedSymbol), Math.max(60, barLimit));
  const markerBars = [
    bars[Math.floor(bars.length * 0.28)],
    bars[Math.floor(bars.length * 0.57)],
    bars[Math.floor(bars.length * 0.82)],
  ].filter((bar): bar is ChartWorkspaceSnapshot['bars'][number] => Boolean(bar));

  return markerBars.map((bar, index) => {
    const markerMap = [
      {
        kind: 'support_reclaim',
        label: 'Support reclaim proof',
        status: 'accepted',
        parser_confidence: 0.91,
        raw_text: 'Sentinel Edge: support reclaimed; allow monitoring only.',
      },
      {
        kind: 'risk_pressure',
        label: 'Risk pressure raised',
        status: 'review',
        parser_confidence: 0.84,
        raw_text: 'Sentinel Edge: reduce size until pressure clears.',
      },
      {
        kind: 'breakout_confirmation',
        label: 'Breakout confirmation',
        status: 'pass',
        parser_confidence: 0.88,
        raw_text: 'Sentinel Edge: breakout confirmed above guard line.',
      },
    ];
    const marker = markerMap[index];
    return {
      id: `${normalizedSymbol}-local-proof-${index}`,
      symbol: normalizedSymbol,
      timestamp: bar.timestamp,
      kind: marker.kind,
      label: marker.label,
      status: marker.status,
      parser_confidence: marker.parser_confidence,
      raw_text: marker.raw_text,
      proof: { price: bar.close, source: 'local-preview' },
    };
  });
}

export function buildFallbackMarketMapContext(symbol: string, barLimit: ChartWorkspaceBarLimit): MarketMapContext {
  const snapshot = buildFallbackChartWorkspaceSnapshot(symbol, DEFAULT_INDICATORS, barLimit);
  const latest = snapshot.bars[snapshot.bars.length - 1];
  const levels = snapshot.levels?.items ?? [];
  const nearest = findNearestFallbackLevel(levels, latest.close);
  const vwap = levels.find((level) => level.kind === 'vwap');
  const aboveVwap = Boolean(vwap && latest.close >= vwap.price);
  const pressureLevel = levels.find((level) => level.kind === 'risk');
  const nearPressure = Boolean(pressureLevel && Math.abs(pressureLevel.price - latest.close) / latest.close < 0.012);

  return {
    schema_version: 'market_map_context.local_preview.v1',
    symbol: snapshot.symbol,
    status: nearPressure ? 'review' : 'pass',
    score: nearPressure ? 78 : 86,
    directional_bias: aboveVwap ? 'upside watch' : 'neutral review',
    trend_state: aboveVwap ? 'above vwap' : 'inside range',
    momentum_state: latest.close >= latest.open ? 'positive guard flow' : 'mixed guard flow',
    volatility_state: 'contained',
    level_proximity: nearest
      ? {
          id: nearest.level.id,
          label: nearest.level.label,
          price: nearest.level.price,
          distance_pct: nearest.distance / latest.close,
        }
      : null,
    reasons: [
      'Local preview feed is supplying chart workspace data.',
      aboveVwap ? 'Price is holding above session VWAP.' : 'Price is still inside the review range.',
      'Support and resistance guard lines are available for bot advisory decisions.',
    ],
    warnings: nearPressure ? ['Do-not-buy pressure is close enough to require review.'] : [],
  };
}

function findNearestFallbackLevel(levels: NonNullable<ChartWorkspaceSnapshot['levels']>['items'], price: number) {
  if (!levels.length) return null;
  return levels.reduce(
    (nearest, level) => {
      const distance = Math.abs(level.price - price);
      return distance < nearest.distance ? { level, distance } : nearest;
    },
    { level: levels[0], distance: Math.abs(levels[0].price - price) },
  );
}

function mapFallbackValuePoints(
  bars: ChartWorkspaceSnapshot['bars'],
  values: Array<number | null>,
): ChartWorkspaceIndicatorPoint[] {
  return bars.map((bar, index) => ({
    timestamp: bar.timestamp,
    value: values[index] ?? null,
  }));
}

function calculateSimpleMovingAverage(values: number[], period: number): Array<number | null> {
  let total = 0;
  return values.map((value, index) => {
    total += value;
    if (index >= period) total -= values[index - period];
    if (index < period - 1) return null;
    return roundFallbackPrice(total / period);
  });
}

function calculateExponentialMovingAverage(values: number[], period: number): number[] {
  const multiplier = 2 / (period + 1);
  let previous = values[0] ?? 0;
  return values.map((value, index) => {
    previous = index === 0 ? value : value * multiplier + previous * (1 - multiplier);
    return roundFallbackPrice(previous);
  });
}

function calculateVolumeWeightedAverage(bars: ChartWorkspaceSnapshot['bars']): number[] {
  let cumulativePriceVolume = 0;
  let cumulativeVolume = 0;
  return bars.map((bar) => {
    const typicalPrice = (bar.high + bar.low + bar.close) / 3;
    cumulativePriceVolume += typicalPrice * bar.volume;
    cumulativeVolume += bar.volume;
    return roundFallbackPrice(cumulativePriceVolume / Math.max(1, cumulativeVolume));
  });
}

function calculateRelativeStrengthIndex(values: number[], period: number): Array<number | null> {
  const points: Array<number | null> = Array(values.length).fill(null);
  let averageGain = 0;
  let averageLoss = 0;

  for (let index = 1; index < values.length; index += 1) {
    const change = values[index] - values[index - 1];
    const gain = Math.max(0, change);
    const loss = Math.max(0, -change);

    if (index <= period) {
      averageGain += gain;
      averageLoss += loss;
      if (index === period) {
        averageGain /= period;
        averageLoss /= period;
      }
    } else {
      averageGain = (averageGain * (period - 1) + gain) / period;
      averageLoss = (averageLoss * (period - 1) + loss) / period;
    }

    if (index >= period) {
      const relativeStrength = averageLoss === 0 ? 100 : averageGain / averageLoss;
      points[index] = roundFallbackPrice(100 - 100 / (1 + relativeStrength));
    }
  }

  return points;
}

function calculateMovingAverageConvergenceDivergence(values: number[]) {
  const ema12 = calculateExponentialMovingAverage(values, 12);
  const ema26 = calculateExponentialMovingAverage(values, 26);
  const macd = values.map((_, index) => roundFallbackPrice(ema12[index] - ema26[index]));
  const signal = calculateExponentialMovingAverage(macd, 9);
  const histogram = macd.map((value, index) => roundFallbackPrice(value - signal[index]));
  return { macd, signal, histogram };
}

function calculateAverageTrueRange(
  bars: ChartWorkspaceSnapshot['bars'],
  period: number,
): Array<number | null> {
  const trueRanges = bars.map((bar, index) => {
    if (index === 0) return bar.high - bar.low;
    const previousClose = bars[index - 1].close;
    return Math.max(bar.high - bar.low, Math.abs(bar.high - previousClose), Math.abs(bar.low - previousClose));
  });
  return calculateSimpleMovingAverage(trueRanges, period);
}

function calculateFallbackSessionVwap(bars: ChartWorkspaceSnapshot['bars']) {
  const values = calculateVolumeWeightedAverage(bars);
  return values[values.length - 1];
}

function resolveFallbackBasePrice(symbol: string) {
  const normalizedSymbol = normalizeChartWorkspaceSymbol(symbol);
  if (FALLBACK_PRICE_ANCHORS[normalizedSymbol]) return FALLBACK_PRICE_ANCHORS[normalizedSymbol];
  const seed = getFallbackSymbolSeed(normalizedSymbol);
  return roundFallbackPrice(75 + (seed % 240) + (seed % 17) * 0.13);
}

function getFallbackSymbolSeed(symbol: string) {
  return symbol.split('').reduce((seed, character, index) => seed + character.charCodeAt(0) * (index + 7), 17);
}

function roundFallbackPrice(value: number) {
  return Math.round(value * 100) / 100;
}
