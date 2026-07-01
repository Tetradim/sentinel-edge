import { Download, Expand, RefreshCw, Settings2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';

export type HeatMode = 'GEX' | 'VEX' | 'VOL';

interface HeatBar {
  index: number;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  callFlow: number;
  putFlow: number;
  netGex: number;
  netVex: number;
  spot: number;
  support: number;
  resistance: number;
}

interface VolumeHeatmapProps {
  symbol: string;
  initialMode?: HeatMode;
  liveRevision?: number;
  onExpand?: () => void;
  className?: string;
}

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  price: number;
  bar: HeatBar;
}

interface ChartGeometry {
  graphLeft: number;
  graphTop: number;
  graphWidth: number;
  graphHeight: number;
  volumeTop: number;
  volumeHeight: number;
  timeTop: number;
  barWidth: number;
}

const symbolBasePrice: Record<string, number> = {
  SPY: 603.47,
  QQQ: 492.18,
  TSLA: 228.45,
  NVDA: 159.32,
  ESU6: 6023.25,
  NQU6: 22114.5,
  'BTC-USD': 106782,
  'ETH-USD': 3892,
};

const heatStops = [
  [0, 8, 9, 28],
  [0.13, 16, 42, 122],
  [0.3, 12, 108, 188],
  [0.45, 0, 168, 168],
  [0.58, 42, 188, 92],
  [0.7, 202, 210, 42],
  [0.82, 235, 150, 32],
  [0.92, 230, 72, 32],
  [1, 222, 30, 40],
] as const;

function clamp(value: number, minimum: number, maximum: number) {
  if (!Number.isFinite(value)) return minimum;
  return Math.min(maximum, Math.max(minimum, value));
}

function lerp(start: number, end: number, amount: number) {
  return start + (end - start) * amount;
}

function gaussian(distance: number, width: number) {
  const safeWidth = Math.max(0.001, width);
  return Math.exp(-(distance * distance) / (2 * safeWidth * safeWidth));
}

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 0xffffffff;
  };
}

function seedFromSymbol(symbol: string, revision: number) {
  let seed = revision * 92821;
  for (let i = 0; i < symbol.length; i += 1) {
    seed = (seed + symbol.charCodeAt(i) * 97 + i * 13) >>> 0;
    seed = ((seed << 5) - seed + symbol.charCodeAt(i)) >>> 0;
  }
  return seed;
}

function getBasePrice(symbol: string) {
  return symbolBasePrice[symbol] ?? 100 + symbol.length * 7;
}

function generateSession(symbol: string, revision = 0) {
  const rng = seededRandom(seedFromSymbol(symbol, revision));
  const bars: HeatBar[] = [];
  const total = 160;
  const sessionStart = new Date();
  sessionStart.setHours(9, 30, 0, 0);
  const base = getBasePrice(symbol);
  const range = Math.max(base * 0.0085, 4.5);
  let close = base;
  let support = base - range * 0.82;
  let resistance = base + range * 0.64;
  let callFlow = 0.64;
  let putFlow = 0.38;

  for (let i = 0; i < total; i += 1) {
    const progress = i / (total - 1);
    const regime = Math.sin(progress * Math.PI * 3.4 + symbol.length) * range * 0.11;
    const trend = Math.sin(progress * Math.PI * 1.4 - 0.3) * range * 0.34;
    const chop = Math.sin(i / 5.8) * range * 0.035 + (rng() - 0.5) * range * 0.085;
    const open = close;
    close = base + trend + regime + chop;
    const high = Math.max(open, close) + range * (0.018 + rng() * 0.035);
    const low = Math.min(open, close) - range * (0.018 + rng() * 0.035);
    const volumePulse = Math.abs(Math.sin(i / 13)) * 0.8 + Math.abs(Math.cos(i / 9)) * 0.35;
    const volume = 42_000 + volumePulse * 145_000 + rng() * 76_000;
    support += (close - support - range * 0.9) * 0.02 + (rng() - 0.5) * range * 0.01;
    resistance += (close - resistance + range * 0.78) * 0.02 + (rng() - 0.5) * range * 0.01;

    callFlow = clamp(callFlow + (rng() - 0.47) * 0.055 + Math.sin(i / 18) * 0.01, 0.08, 0.98);
    putFlow = clamp(putFlow + (rng() - 0.48) * 0.055 + Math.cos(i / 17) * 0.012, 0.08, 0.98);

    bars.push({
      index: i,
      time: sessionStart.getTime() + i * 90_000,
      open,
      high,
      low,
      close,
      volume,
      callFlow,
      putFlow,
      netGex: (callFlow - putFlow) * 2.4,
      netVex: (putFlow - callFlow) * 1.9,
      spot: close,
      support,
      resistance,
    });
  }

  return bars;
}

function heatColor(value: number) {
  const v = clamp(value, 0, 1);
  for (let i = 0; i < heatStops.length - 1; i += 1) {
    const current = heatStops[i];
    const next = heatStops[i + 1];
    if (v >= current[0] && v <= next[0]) {
      const amount = (v - current[0]) / Math.max(0.001, next[0] - current[0]);
      const red = Math.round(lerp(current[1], next[1], amount));
      const green = Math.round(lerp(current[2], next[2], amount));
      const blue = Math.round(lerp(current[3], next[3], amount));
      return `rgb(${red}, ${green}, ${blue})`;
    }
  }

  return 'rgb(160, 8, 16)';
}

function formatTime(ms: number) {
  const value = new Date(ms);
  return `${value.getHours().toString().padStart(2, '0')}:${value.getMinutes().toString().padStart(2, '0')}`;
}

function formatFlow(value: number) {
  const absolute = Math.abs(value);
  return `${value < 0 ? '-' : ''}$${absolute.toFixed(1)}B`;
}

function getGeometry(width: number, height: number, barCount: number): ChartGeometry {
  const graphLeft = 54;
  const graphTop = 44;
  const graphRightPad = 96;
  const volumeHeight = 54;
  const timeHeight = 28;
  const graphHeight = Math.max(210, height - graphTop - volumeHeight - timeHeight - 24);
  const graphWidth = Math.max(360, width - graphLeft - graphRightPad);

  return {
    graphLeft,
    graphTop,
    graphWidth,
    graphHeight,
    volumeTop: graphTop + graphHeight + 12,
    volumeHeight,
    timeTop: graphTop + graphHeight + volumeHeight + 20,
    barWidth: graphWidth / Math.max(1, barCount),
  };
}

export function VolumeHeatmap({
  symbol,
  initialMode = 'GEX',
  liveRevision = 0,
  onExpand,
  className = '',
}: VolumeHeatmapProps) {
  const [mode, setMode] = useState<HeatMode>(initialMode);
  const [refreshRevision, setRefreshRevision] = useState(0);
  const [viewport, setViewport] = useState({ width: 960, height: 430 });
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [activeBarIndex, setActiveBarIndex] = useState<number | null>(null);

  const bars = useMemo(
    () => generateSession(symbol, liveRevision + refreshRevision),
    [symbol, liveRevision, refreshRevision],
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const barCount = bars.length;
  const maxVolume = Math.max(...bars.map((bar) => bar.volume), 1);
  const pricePoints = bars.flatMap((bar) => [bar.low, bar.high, bar.support, bar.resistance, bar.spot]);
  const minPrice = Math.min(...pricePoints);
  const maxPrice = Math.max(...pricePoints);
  const priceRange = Math.max(1, maxPrice - minPrice);
  const currentSpot = bars[bars.length - 1]?.spot ?? getBasePrice(symbol);

  const modeSummary = useMemo(() => {
    if (mode === 'VOL') {
      return { label: 'Volume heat', detail: 'Volume concentration across active price bands.' };
    }
    if (mode === 'VEX') {
      return { label: 'VEX pressure', detail: 'Volatility exposure pressure with cumulative flow overlays.' };
    }
    return { label: 'GEX heat', detail: 'Gamma exposure density with call and put flow overlays.' };
  }, [mode]);

  const requestResize = useCallback(() => {
    const next = containerRef.current;
    if (!next) return;
    const { width: measuredWidth, height: measuredHeight } = next.getBoundingClientRect();
    const width = Math.max(620, Math.floor(measuredWidth - 16));
    const height = Math.max(340, Math.floor(measuredHeight - 16));
    setViewport((current) => {
      if (current.width === width && current.height === height) return current;
      return { width, height };
    });
  }, []);

  useEffect(() => {
    requestResize();
    const observer = new ResizeObserver(() => requestResize());
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [requestResize]);

  useEffect(() => {
    setMode(initialMode);
  }, [initialMode]);

  const paint = useCallback((phase = 0) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = viewport.width;
    const height = viewport.height;
    const geometry = getGeometry(width, height, barCount);
    const {
      graphLeft,
      graphTop,
      graphWidth,
      graphHeight,
      volumeTop,
      volumeHeight,
      timeTop,
      barWidth,
    } = geometry;
    const graphRight = graphLeft + graphWidth;
    const rows = 58;
    const cellHeight = graphHeight / rows;

    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    ctx.clearRect(0, 0, width, height);

    const panelGradient = ctx.createLinearGradient(0, 0, 0, height);
    panelGradient.addColorStop(0, '#0c0d1a');
    panelGradient.addColorStop(0.48, '#08091c');
    panelGradient.addColorStop(1, '#06060b');
    ctx.fillStyle = panelGradient;
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#08091c';
    ctx.fillRect(graphLeft, graphTop, graphWidth, graphHeight);

    for (let row = 0; row < rows; row += 1) {
      const y = graphTop + row * cellHeight;
      const price = maxPrice - (row / (rows - 1)) * priceRange;
      for (let i = 0; i < barCount; i += 1) {
        const bar = bars[i];
        const x = graphLeft + i * barWidth;
        const sigma = priceRange / 13;
        const timeBlock = 0.82 + (Math.floor(i / 18) % 3) * 0.1 + Math.sin(i / 7) * 0.06;
        const noise = (Math.sin(i * 12.9898 + row * 78.233) * 43758.5453) % 1;
        const volumeLevel = 40 + (bar.volume / maxVolume) * 80;
        const intensity = clamp(
          (
            gaussian(price - bar.spot, sigma) * (0.45 + volumeLevel / 140)
            + gaussian(price - bar.support, sigma * 0.52) * 0.3
            + gaussian(price - bar.resistance, sigma * 0.48) * 0.36
          )
          * timeBlock
          * (mode === 'VEX' ? (bar.putFlow * 100) / 78 : mode === 'GEX' ? (bar.callFlow * 100) / 82 : volumeLevel / 110)
          + Math.abs(noise) * 0.04,
          0,
          1,
        );

        ctx.fillStyle = heatColor(intensity);
        ctx.globalAlpha = 0.88;
        ctx.fillRect(x, y, Math.ceil(barWidth) + 0.4, Math.ceil(cellHeight) + 0.4);
      }
    }
    ctx.globalAlpha = 1;

    ctx.strokeStyle = 'rgba(236, 234, 246, 0.075)';
    ctx.lineWidth = 1;
    for (let tick = 0; tick <= 5; tick += 1) {
      const y = graphTop + (tick / 5) * graphHeight;
      const price = maxPrice - (tick / 5) * priceRange;
      ctx.beginPath();
      ctx.moveTo(graphLeft, y);
      ctx.lineTo(graphRight, y);
      ctx.stroke();
      ctx.fillStyle = 'rgba(236, 234, 246, 0.62)';
      ctx.font = '11px "Share Tech Mono", monospace';
      ctx.textAlign = 'right';
      ctx.fillText(price.toFixed(0), graphLeft - 10, y + 4);
    }

    for (let tick = 0; tick <= 9; tick += 1) {
      const x = graphLeft + (tick / 9) * graphWidth;
      ctx.strokeStyle = 'rgba(236, 234, 246, 0.055)';
      ctx.beginPath();
      ctx.moveTo(x, graphTop);
      ctx.lineTo(x, graphTop + graphHeight + volumeHeight + 8);
      ctx.stroke();
    }

    const xFromIndex = (index: number) => graphLeft + index * barWidth + barWidth / 2;
    const yFromPrice = (price: number) => graphTop + graphHeight - ((price - minPrice) / priceRange) * graphHeight;
    const yFromGuardFlow = (value: number) => graphTop + graphHeight - value * graphHeight * 0.82 - graphHeight * 0.08;

    const drawPath = (points: number[], yFromValue: (value: number) => number, stroke: string, lineWidth: number, dash: number[] = []) => {
      ctx.beginPath();
      points.forEach((value, index) => {
        const x = xFromIndex(index);
        const y = yFromValue(value);
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth;
      ctx.setLineDash(dash);
      ctx.stroke();
      ctx.setLineDash([]);
    };

    drawPath(bars.map((bar) => bar.spot), yFromPrice, 'rgba(240, 199, 94, 0.75)', 1.4);
    drawPath(bars.map((bar) => bar.support), yFromPrice, 'rgba(40, 209, 124, 0.65)', 1.1, [5, 4]);
    drawPath(bars.map((bar) => bar.resistance), yFromPrice, 'rgba(255, 77, 94, 0.68)', 1.1, [5, 4]);
    drawPath(bars.map((bar) => bar.callFlow), yFromGuardFlow, '#28D17C', 2.2);
    drawPath(bars.map((bar) => bar.putFlow), yFromGuardFlow, '#FF4D5E', 2.2);

    const spotY = yFromPrice(currentSpot);
    ctx.strokeStyle = 'rgba(255, 212, 55, 0.54)';
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.moveTo(graphLeft, spotY);
    ctx.lineTo(graphRight, spotY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#F0C75E';
    ctx.textAlign = 'left';
    ctx.font = '700 12px "Share Tech Mono", monospace';
    ctx.fillText(currentSpot.toFixed(2), graphRight + 6, spotY + 4);

    for (let i = 0; i < barCount; i += 1) {
      const bar = bars[i];
      const x = xFromIndex(i);
      const volumeWidth = Math.max(1, barWidth * 0.72);
      const barHeight = (bar.volume / maxVolume) * (volumeHeight - 14);
      const y = volumeTop + volumeHeight - barHeight;
      ctx.fillStyle = bar.close >= bar.open ? 'rgba(34, 221, 83, 0.82)' : 'rgba(255, 48, 55, 0.78)';
      ctx.fillRect(x - volumeWidth / 2, y, volumeWidth, barHeight);
    }

    ctx.strokeStyle = 'rgba(201, 162, 39, 0.18)';
    ctx.strokeRect(graphLeft, graphTop, graphWidth, graphHeight);
    ctx.strokeStyle = 'rgba(201, 162, 39, 0.12)';
    ctx.beginPath();
    ctx.moveTo(graphLeft, volumeTop + volumeHeight);
    ctx.lineTo(graphRight, volumeTop + volumeHeight);
    ctx.stroke();

    for (let tick = 0; tick < barCount; tick += 18) {
      const x = xFromIndex(tick);
      ctx.fillStyle = 'rgba(236, 234, 246, 0.62)';
      ctx.textAlign = 'center';
      ctx.font = '11px "Share Tech Mono", monospace';
      ctx.fillText(formatTime(bars[tick].time), x, timeTop);
    }

    const legendX = graphRight + 42;
    const legendY = graphTop + 18;
    const legendH = Math.max(130, graphHeight - 54);
    const legendW = 14;
    const legend = ctx.createLinearGradient(0, legendY + legendH, 0, legendY);
    for (const [stop, red, green, blue] of heatStops) {
      legend.addColorStop(stop, `rgb(${red}, ${green}, ${blue})`);
    }
    ctx.fillStyle = legend;
    ctx.fillRect(legendX, legendY, legendW, legendH);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.strokeRect(legendX, legendY, legendW, legendH);
    ctx.fillStyle = 'rgba(236, 234, 246, 0.68)';
    ctx.textAlign = 'left';
    ctx.font = '12px Rajdhani, sans-serif';
    ctx.fillText('High', legendX + 22, legendY + 8);
    ctx.fillText('Low', legendX + 22, legendY + legendH);
    ctx.fillText(formatFlow(2), graphRight + 12, graphTop + 28);
    ctx.fillText('$0', graphRight + 12, graphTop + graphHeight * 0.5);
    ctx.fillText(formatFlow(-2), graphRight + 12, graphTop + graphHeight - 10);

    const sweepX = graphLeft + ((phase * 0.08) % 1) * graphWidth;
    const sweepGradient = ctx.createLinearGradient(sweepX - 120, 0, sweepX + 120, 0);
    sweepGradient.addColorStop(0, 'rgba(255, 255, 255, 0)');
    sweepGradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.08)');
    sweepGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = sweepGradient;
    ctx.fillRect(Math.max(graphLeft, sweepX - 120), graphTop, Math.min(240, graphRight - sweepX + 120), graphHeight);

    if (activeBarIndex !== null && bars[activeBarIndex]) {
      const hoverX = xFromIndex(activeBarIndex);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.72)';
      ctx.setLineDash([4, 5]);
      ctx.beginPath();
      ctx.moveTo(hoverX, graphTop);
      ctx.lineTo(hoverX, volumeTop + volumeHeight);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.fillStyle = 'rgba(236, 234, 246, 0.9)';
    ctx.font = '12px "Share Tech Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${symbol} ${modeSummary.label}`, graphLeft, 18);
    ctx.fillText(modeSummary.detail, graphLeft, 33);
  }, [activeBarIndex, barCount, bars, currentSpot, maxPrice, maxVolume, minPrice, mode, modeSummary.detail, modeSummary.label, priceRange, symbol, viewport]);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frame = 0;

    const animate = (time: number) => {
      paint(time / 1000);
      if (!reduceMotion) {
        frame = window.requestAnimationFrame(animate);
      }
    };

    animate(0);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [paint]);

  const onPointerMove = useCallback(
    (event: MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const geometry = getGeometry(viewport.width, viewport.height, barCount);
      const rawIndex = ((x - geometry.graphLeft) / geometry.graphWidth) * barCount;
      const index = Math.max(0, Math.min(barCount - 1, Math.floor(rawIndex)));

      if (
        !Number.isFinite(index)
        || x < geometry.graphLeft
        || x > geometry.graphLeft + geometry.graphWidth
        || y < geometry.graphTop
        || y > geometry.volumeTop + geometry.volumeHeight
      ) {
        setActiveBarIndex(null);
        setTooltip(null);
        return;
      }

      const bar = bars[index];
      if (!bar) {
        setActiveBarIndex(null);
        setTooltip(null);
        return;
      }

      const price = maxPrice - ((y - geometry.graphTop) / geometry.graphHeight) * priceRange;
      setActiveBarIndex(index);
      setTooltip({
        visible: true,
        x,
        y,
        price,
        bar,
      });
    },
    [barCount, bars, maxPrice, priceRange, viewport.height, viewport.width],
  );

  const onPointerLeave = useCallback(() => {
    setActiveBarIndex(null);
    setTooltip(null);
  }, []);

  const refreshData = useCallback(() => {
    setRefreshRevision((value) => value + 1);
    setActiveBarIndex(null);
    setTooltip(null);
  }, []);

  const onDownload = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const anchor = document.createElement('a');
    anchor.href = canvas.toDataURL('image/png');
    anchor.download = `${symbol.toLowerCase()}-${mode.toLowerCase()}-heatmap.png`;
    anchor.click();
  }, [mode, symbol]);

  return (
    <section className={`edge-volume-heatmap ${className}`}>
      <header className="edge-volume-heatmap-head">
        <div>
          <span>{symbol} GEX / VEX Heat Map</span>
          <strong>
            {symbol}
            {' '}
            -
            {' '}
            {mode}
            {' '}
            mode
          </strong>
        </div>
        <div className="edge-volume-heatmap-toolbar">
          <div className="edge-volume-modes" role="group" aria-label="Heat mode">
            <button type="button" className={mode === 'GEX' ? 'active' : ''} onClick={() => setMode('GEX')}>GEX</button>
            <button type="button" className={mode === 'VEX' ? 'active' : ''} onClick={() => setMode('VEX')}>VEX</button>
            <button type="button" className={mode === 'VOL' ? 'active' : ''} onClick={() => setMode('VOL')}>VOL</button>
          </div>
          <button type="button" onClick={refreshData}>
            <RefreshCw size={12} />
            Refresh
          </button>
          <button type="button" onClick={onDownload}>
            <Download size={12} />
            Save
          </button>
          {onExpand && (
            <button type="button" onClick={onExpand}>
              <Expand size={12} />
              Expand
            </button>
          )}
        </div>
      </header>
      <div className="edge-volume-heatmap-canvas-wrap" ref={containerRef}>
        <canvas
          ref={canvasRef}
          className="edge-volume-heatmap-canvas"
          onMouseMove={onPointerMove}
          onMouseLeave={onPointerLeave}
          aria-label="GEX and VEX density heatmap with flow overlays"
        />
        {tooltip?.visible && tooltip.bar && (
          <div className="edge-volume-heatmap-tooltip" style={{ left: `${tooltip.x + 12}px`, top: `${tooltip.y + 12}px` }}>
            <strong>
              {symbol}
              {' '}
              {formatTime(tooltip.bar.time)}
            </strong>
            <span>
              Strike:
              {' '}
              {tooltip.price.toFixed(2)}
            </span>
            <span>
              Spot:
              {' '}
              {tooltip.bar.spot.toFixed(2)}
            </span>
            <span>
              Call flow:
              {' '}
              {(tooltip.bar.callFlow * 2).toFixed(2)}
              B
            </span>
            <span>
              Put flow:
              {' '}
              {(-tooltip.bar.putFlow * 2).toFixed(2)}
              B
            </span>
            <span>
              Net
              {' '}
              {mode}
              :
              {' '}
              {(mode === 'VEX' ? tooltip.bar.netVex : tooltip.bar.netGex).toFixed(2)}
              B
            </span>
            <span>
              Volume:
              {' '}
              {Math.round(tooltip.bar.volume).toLocaleString()}
            </span>
          </div>
        )}
      </div>
      <footer className="edge-volume-heatmap-footer">
        <small>
          <Settings2 size={11} />
          Gamma density, cumulative call/put flow, spot line, and volume share the same panel.
        </small>
        <small>
          {barCount}
          {' '}
          bars -
          {' '}
          {modeSummary.label}
        </small>
      </footer>
    </section>
  );
}
