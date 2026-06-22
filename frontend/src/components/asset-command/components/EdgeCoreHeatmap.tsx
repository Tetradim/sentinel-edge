import { useEffect } from 'react';
import type React from 'react';
import {
  coreColorMetricOptions,
  coreLabelModeOptions,
  coreSizeMetricOptions,
  coreUniverseOptions,
  defaultCoreHeatmapConfig,
} from '../data';
import type { CoreHeatmapConfig, Ticker } from '../types';

interface EdgeCoreHeatmapProps {
  tickers: Ticker[];
  selectedSymbol: string;
  config: CoreHeatmapConfig;
  open: boolean;
  setOpen: React.Dispatch<React.SetStateAction<boolean>>;
  updateConfig: <K extends keyof CoreHeatmapConfig>(key: K, value: CoreHeatmapConfig[K]) => void;
  resetConfig: () => void;
  applyConfig: () => void;
  onSelectTicker: (symbol: string) => void;
}

export function EdgeCoreHeatmap({
  tickers,
  selectedSymbol,
  config,
  open,
  setOpen,
  updateConfig,
  resetConfig,
  applyConfig,
  onSelectTicker,
}: EdgeCoreHeatmapProps) {
  const cells = getVisibleCells(tickers, config);
  const selectedCell = cells.find((cell) => cell.ticker.symbol === selectedSymbol) || cells[0];
  const averageHeat = cells.length ? Math.round(cells.reduce((total, cell) => total + cell.heat, 0) / cells.length) : 0;
  const hotCellCount = cells.filter((cell) => cell.heat >= config.alertThreshold).length;

  return (
    <section className="edge-core-shell" aria-label="Configurable edge heatmap">
      <div className="edge-core-map" style={{ '--edge-cell-count': String(cells.length) } as React.CSSProperties}>
        <button
          type="button"
          className="edge-core-center"
          aria-label="Open core heatmap configuration"
          onClick={() => setOpen(true)}
        >
          <span>Core heat</span>
          <strong>{averageHeat}</strong>
          <em>{config.colorMetric} / {config.horizon}</em>
        </button>
        {cells.map((cell, index) => {
          const style = {
            '--cell-heat': `${cell.heat}%`,
            '--cell-scale': String(cell.scale),
            '--cell-delay': `${index * 35}ms`,
          } as React.CSSProperties & Record<string, string>;
          return (
            <button
              type="button"
              key={cell.ticker.symbol}
              className={`edge-core-cell heat-${cell.tone} ${cell.ticker.symbol === selectedSymbol ? 'active' : ''}`}
              style={style}
              aria-label={`${cell.ticker.symbol} heat ${cell.heat}; select ticker`}
              onClick={() => onSelectTicker(cell.ticker.symbol)}
            >
              <strong>{getCellLabel(cell.ticker, cell.heat, config.labelMode)}</strong>
              <span>{cell.ticker.change}</span>
            </button>
          );
        })}
      </div>
      <div className="edge-core-summary">
        <div>
          <span>Active cell</span>
          <strong>{selectedCell ? selectedCell.ticker.symbol : selectedSymbol}</strong>
        </div>
        <div>
          <span>Alert cells</span>
          <strong>{hotCellCount}</strong>
        </div>
        <div>
          <span>Sizing</span>
          <strong>{config.sizeMetric}</strong>
        </div>
      </div>
      <button type="button" className="edge-core-config-button" onClick={() => setOpen(true)}>
        Configure heatmap
      </button>
      {open && (
        <CoreHeatmapConfigModal
          config={config}
          updateConfig={updateConfig}
          resetConfig={resetConfig}
          applyConfig={applyConfig}
          onClose={() => setOpen(false)}
        />
      )}
    </section>
  );
}

function CoreHeatmapConfigModal({
  config,
  updateConfig,
  resetConfig,
  applyConfig,
  onClose,
}: {
  config: CoreHeatmapConfig;
  updateConfig: <K extends keyof CoreHeatmapConfig>(key: K, value: CoreHeatmapConfig[K]) => void;
  resetConfig: () => void;
  applyConfig: () => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="edge-core-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="edge-core-modal" role="dialog" aria-modal="true" aria-labelledby="edge-core-modal-title">
        <header>
          <div>
            <span>Core configuration</span>
            <h2 id="edge-core-modal-title">Hex heatmap setup</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close core heatmap configuration">Close</button>
        </header>

        <div className="edge-core-modal-grid">
          <label>
            Color metric
            <select
              value={config.colorMetric}
              onChange={(event) => updateConfig('colorMetric', event.target.value as CoreHeatmapConfig['colorMetric'])}
            >
              {coreColorMetricOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
            <small>{coreColorMetricOptions.find((option) => option.id === config.colorMetric)?.detail}</small>
          </label>

          <label>
            Size metric
            <select
              value={config.sizeMetric}
              onChange={(event) => updateConfig('sizeMetric', event.target.value as CoreHeatmapConfig['sizeMetric'])}
            >
              {coreSizeMetricOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            Universe
            <select
              value={config.universe}
              onChange={(event) => updateConfig('universe', event.target.value as CoreHeatmapConfig['universe'])}
            >
              {coreUniverseOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            Label mode
            <select
              value={config.labelMode}
              onChange={(event) => updateConfig('labelMode', event.target.value as CoreHeatmapConfig['labelMode'])}
            >
              {coreLabelModeOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
          </label>

          <label>
            Horizon
            <input
              type="text"
              maxLength={16}
              value={config.horizon}
              onChange={(event) => updateConfig('horizon', event.target.value || defaultCoreHeatmapConfig.horizon)}
            />
          </label>

          <label>
            Alert threshold <strong>{config.alertThreshold}</strong>
            <input
              type="range"
              min={30}
              max={90}
              value={config.alertThreshold}
              onChange={(event) => updateConfig('alertThreshold', Number(event.target.value))}
            />
          </label>

          <label>
            Cell density <strong>{config.density}</strong>
            <input
              type="range"
              min={3}
              max={7}
              value={config.density}
              onChange={(event) => updateConfig('density', Number(event.target.value))}
            />
          </label>

          <label className="edge-core-note">
            Operator note
            <textarea
              maxLength={140}
              value={config.operatorNote}
              onChange={(event) => updateConfig('operatorNote', event.target.value)}
            />
          </label>
        </div>

        <div className="edge-core-toggle-row">
          <label><input type="checkbox" checked={config.includeIdle} onChange={(event) => updateConfig('includeIdle', event.target.checked)} />Show idle assets</label>
          <label><input type="checkbox" checked={config.autoFocusTicker} onChange={(event) => updateConfig('autoFocusTicker', event.target.checked)} />Focus ticker on cell click</label>
        </div>

        <footer>
          <button type="button" onClick={resetConfig}>Reset</button>
          <button type="button" onClick={applyConfig}>Apply configuration</button>
        </footer>
      </section>
    </div>
  );
}

function getVisibleCells(tickers: Ticker[], config: CoreHeatmapConfig) {
  const filtered = tickers.filter((ticker) => {
    if (!config.includeIdle && !ticker.watchers.length) return false;
    if (config.universe === 'watchers') return ticker.watchers.length > 0;
    return true;
  });

  return filtered
    .slice(0, config.universe === 'all' ? tickers.length : config.density)
    .map((ticker) => {
      const heat = getHeatValue(ticker, config.colorMetric);
      const size = getSizeValue(ticker, config.sizeMetric);
      return {
        ticker,
        heat,
        scale: Number((0.88 + (size / 100) * 0.2).toFixed(2)),
        tone: heat >= config.alertThreshold ? 'high' : heat >= Math.max(30, config.alertThreshold - 18) ? 'mid' : 'low',
      };
    });
}

function getCellLabel(ticker: Ticker, heat: number, labelMode: CoreHeatmapConfig['labelMode']) {
  if (labelMode === 'heat') return String(heat);
  if (labelMode === 'signal') return ticker.signal.replace(' ', '\n');
  return ticker.symbol;
}

function getHeatValue(ticker: Ticker, metric: CoreHeatmapConfig['colorMetric']) {
  if (metric === 'risk') {
    return clampHeat(getMetricNumber(ticker, 'heat') || getMetricNumber(ticker, 'drawdown') * 18 + ticker.watchers.length * 16 + 24);
  }
  if (metric === 'signal') return clampHeat(getSignalScore(ticker));
  if (metric === 'flow') {
    return clampHeat(getMetricNumber(ticker, 'flow') * 3 + getMetricNumber(ticker, 'volume') * 18 + getMetricNumber(ticker, 'liquidity') / 50000 + 30);
  }
  return clampHeat(getMetricNumber(ticker, 'drawdown') * 24 + getMetricNumber(ticker, 'invalid') / Math.max(ticker.price, 1) * 12 + 22);
}

function getSizeValue(ticker: Ticker, metric: CoreHeatmapConfig['sizeMetric']) {
  if (metric === 'liquidity') return clampHeat(getMetricNumber(ticker, 'liquidity') / 28000 + 45);
  if (metric === 'volatility') return clampHeat(getMetricNumber(ticker, 'atr') * 80 + Math.abs(getChangeNumber(ticker.change)) * 12 + 26);
  return clampHeat(ticker.watchers.length * 24 + Math.abs(getChangeNumber(ticker.change)) * 10 + 44);
}

function getSignalScore(ticker: Ticker) {
  const match = ticker.signal.match(/\d+/);
  return match ? Number(match[0]) : 50;
}

function getMetricNumber(ticker: Ticker, id: string) {
  const detail = ticker.metrics.find((metric) => metric.id === id)?.detail || '';
  const match = detail.replace(/,/g, '').match(/-?\d+(\.\d+)?/);
  return match ? Math.abs(Number(match[0])) : 0;
}

function getChangeNumber(change: string) {
  const match = change.match(/-?\d+(\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

function clampHeat(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}
