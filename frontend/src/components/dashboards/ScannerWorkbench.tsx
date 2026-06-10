import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, BarChart3, RefreshCw, Search, Target, Zap } from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ScannerWorkbenchCatalog,
  ScannerWorkbenchCollectionPack,
  ScannerWorkbenchIndicator,
  ScannerWorkbenchScanner,
  ScannerWorkbenchStrategy,
  ScannerWorkbenchTicker,
  ScannerWorkbenchWatchIntent,
  ScannerWorkbenchWatchIntentValidation,
} from '@/types';

export const SCANNER_WORKBENCH_STORAGE_KEY = 'sentinel-edge.scanner-workbench.watchlist.v1';

type ScannerWorkbenchTabId = 'scanners' | 'tickers' | 'strategies' | 'indicators';

const DEFAULT_WATCH_STATE: ScannerWorkbenchWatchIntent = {
  scanners: [],
  tickers: [],
  strategies: [],
  indicators: [],
};

const tabs = [
  { id: 'scanners' as const, label: 'Scanners', icon: Search },
  { id: 'tickers' as const, label: 'Tickers', icon: Target },
  { id: 'strategies' as const, label: 'Strategies', icon: Zap },
  { id: 'indicators' as const, label: 'Indicators', icon: BarChart3 },
];

export const ScannerWorkbench: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ScannerWorkbenchTabId>('scanners');
  const [catalog, setCatalog] = useState<ScannerWorkbenchCatalog | null>(null);
  const [watchState, setWatchState] = useState<ScannerWorkbenchWatchIntent>(readScannerWorkbenchWatchState);
  const [validation, setValidation] = useState<ScannerWorkbenchWatchIntentValidation | null>(null);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState('');
  const [validationMessage, setValidationMessage] = useState('');

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const nextCatalog = await api.getScannerWorkbenchCatalog();
      setCatalog(nextCatalog);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scanner workbench catalog');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  useEffect(() => {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(SCANNER_WORKBENCH_STORAGE_KEY, JSON.stringify(watchState));
  }, [watchState]);

  const validateWatchIntent = useCallback(async () => {
    setValidating(true);
    setValidationMessage('');
    try {
      const nextValidation = await api.validateScannerWorkbenchWatchIntent(watchState);
      setValidation(nextValidation);
      setValidationMessage(
        nextValidation.valid
          ? 'Watch intent matches the current catalog.'
          : `${nextValidation.invalid_count} stale watch selections need review.`,
      );
    } catch (err) {
      setValidationMessage(err instanceof Error ? err.message : 'Failed to validate watch intent');
    } finally {
      setValidating(false);
    }
  }, [watchState]);

  const scannerLookup = useMemo(() => {
    return new Map((catalog?.scanners ?? []).map((scanner) => [scanner.id, scanner]));
  }, [catalog]);

  const strategyLookup = useMemo(() => {
    return new Map((catalog?.strategies ?? []).map((strategy) => [strategy.id, strategy]));
  }, [catalog]);

  const indicatorLookup = useMemo(() => {
    return new Map((catalog?.indicators ?? []).map((indicator) => [indicator.id, indicator]));
  }, [catalog]);

  const selectedCount = watchState.scanners.length + watchState.tickers.length + watchState.strategies.length + watchState.indicators.length;
  const selectedScannerNames = watchState.scanners.map((id) => scannerLookup.get(id)?.name ?? id);
  const selectedTickerSymbols = watchState.tickers;
  const selectedStrategyNames = watchState.strategies.map((id) => strategyLookup.get(id)?.name ?? id);
  const selectedIndicatorNames = watchState.indicators.map((id) => indicatorLookup.get(id)?.name ?? id);

  const toggleWatchValue = (key: keyof ScannerWorkbenchWatchIntent, value: string) => {
    setWatchState((current) => {
      const nextValues = new Set(current[key]);
      if (nextValues.has(value)) nextValues.delete(value);
      else nextValues.add(value);
      return { ...current, [key]: Array.from(nextValues).sort() };
    });
  };

  const applyCollectionPack = (pack: ScannerWorkbenchCollectionPack) => {
    setWatchState((current) => ({
      ...current,
      scanners: Array.from(new Set([...current.scanners, ...pack.scanner_ids])).sort(),
    }));
  };

  const applyStrategyKit = (strategy: ScannerWorkbenchStrategy) => {
    setWatchState((current) => ({
      ...current,
      strategies: Array.from(new Set([...current.strategies, strategy.id])).sort(),
      scanners: Array.from(new Set([...current.scanners, ...strategy.scanner_ids])).sort(),
      indicators: Array.from(new Set([...current.indicators, ...strategy.indicator_ids])).sort(),
    }));
  };

  const clearWatchIntent = () => {
    setWatchState(DEFAULT_WATCH_STATE);
    setValidation(null);
    setValidationMessage('');
  };

  const applySanitizedWatchIntent = () => {
    if (!validation) return;
    setWatchState(validation.sanitized_intent);
    setValidation({
      ...validation,
      valid: true,
      invalid_count: 0,
      invalid_selections: DEFAULT_WATCH_STATE,
    });
    setValidationMessage('Stale watch selections removed.');
  };

  return (
    <div className="space-y-6" data-testid="scanner-workbench">
      <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-5 shadow-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-cyan-300">
              <Search className="h-4 w-4" />
              Native scanner catalog
            </div>
            <h2 className="text-2xl font-bold text-white">Scanner Workbench</h2>
            <p className="max-w-3xl text-sm leading-6 text-gray-300">
              Edge-native scanner templates built from public market-tool research. Selections are saved as watch intent and do not send live orders.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={loadCatalog}
              className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/20"
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              type="button"
              onClick={validateWatchIntent}
              className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200 hover:bg-emerald-500/20"
              disabled={validating}
            >
              Validate watch intent
            </button>
            <button
              type="button"
              onClick={clearWatchIntent}
              className="rounded-lg border border-gray-700 px-3 py-2 text-sm font-medium text-gray-300 hover:border-gray-500 hover:text-white"
            >
              Clear watch intent
            </button>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-gray-800 bg-gray-900/70 px-4 py-3 text-sm text-gray-300" aria-live="polite">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <span className="font-semibold text-white">Watch validation</span>
              <span className="ml-2 text-gray-400">
                {validationMessage || 'Validate before connecting this selection to future scanner automation.'}
              </span>
              {validation?.invalid_count ? (
                <span className="ml-2 text-amber-300">
                  Invalid: {formatInvalidSelectionSummary(validation.invalid_selections)}
                </span>
              ) : null}
            </div>
            {validation?.invalid_count ? (
              <button
                type="button"
                onClick={applySanitizedWatchIntent}
                className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-200 hover:bg-amber-500/20"
              >
                Apply sanitized watch intent
              </button>
            ) : null}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Metric label="Selected" value={selectedCount} detail="watch fields" />
          <Metric label="Scanners" value={catalog?.counts.scanners ?? 0} detail={`${watchState.scanners.length} selected`} />
          <Metric label="Tickers" value={catalog?.counts.recommended_tickers ?? 0} detail={`${watchState.tickers.length} selected`} />
          <Metric label="Strategies" value={catalog?.counts.strategies ?? 0} detail={`${watchState.strategies.length} selected`} />
          <Metric label="Indicators" value={catalog?.counts.indicators ?? 0} detail={`${watchState.indicators.length} selected`} />
        </div>

        <div className="mt-4 rounded-lg border border-gray-800 bg-gray-900/70 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Activity className="h-4 w-4 text-cyan-300" />
            Bot watchlist
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 text-sm text-gray-300 md:grid-cols-2 xl:grid-cols-4">
            <WatchSummary label="Scanner watch" values={selectedScannerNames} />
            <WatchSummary label="Ticker watch" values={selectedTickerSymbols} />
            <WatchSummary label="Strategy watch" values={selectedStrategyNames} />
            <WatchSummary label="Indicator watch" values={selectedIndicatorNames} />
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-gray-800 bg-gray-950/60">
        <div className="border-b border-gray-800 p-3">
          <div className="flex flex-wrap gap-2" role="tablist" aria-label="Scanner workbench sections">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={activeTab === id}
                className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                  activeTab === id
                    ? 'bg-cyan-500/15 text-cyan-200 ring-1 ring-cyan-500/40'
                    : 'text-gray-400 hover:bg-gray-900 hover:text-white'
                }`}
                onClick={() => setActiveTab(id)}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4">
          {error && (
            <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200" role="alert">
              {error}
            </div>
          )}

          {loading && !catalog ? (
            <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-6 text-sm text-gray-300">Loading scanner catalog...</div>
          ) : null}

          {catalog && activeTab === 'scanners' && (
            <ScannerTab
              scanners={catalog.scanners}
              packs={catalog.collection_packs}
              selectedIds={watchState.scanners}
              onToggle={(id) => toggleWatchValue('scanners', id)}
              onApplyPack={applyCollectionPack}
            />
          )}
          {catalog && activeTab === 'tickers' && (
            <TickerTab
              tickers={catalog.recommended_tickers}
              selectedIds={watchState.tickers}
              onToggle={(symbol) => toggleWatchValue('tickers', symbol)}
              scannerLookup={scannerLookup}
            />
          )}
          {catalog && activeTab === 'strategies' && (
            <StrategyTab
              strategies={catalog.strategies}
              selectedIds={watchState.strategies}
              onToggle={(id) => toggleWatchValue('strategies', id)}
              onApplyKit={applyStrategyKit}
              scannerLookup={scannerLookup}
              indicatorLookup={indicatorLookup}
            />
          )}
          {catalog && activeTab === 'indicators' && (
            <IndicatorTab
              indicators={catalog.indicators}
              selectedIds={watchState.indicators}
              onToggle={(id) => toggleWatchValue('indicators', id)}
              strategyLookup={strategyLookup}
            />
          )}
        </div>
      </div>
    </div>
  );
};

function ScannerTab({
  scanners,
  packs,
  selectedIds,
  onToggle,
  onApplyPack,
}: {
  scanners: ScannerWorkbenchScanner[];
  packs: ScannerWorkbenchCollectionPack[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onApplyPack: (pack: ScannerWorkbenchCollectionPack) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-lg font-semibold text-white">Collections distilled into packs</h3>
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {packs.map((pack) => (
            <div key={pack.id} className="rounded-lg border border-gray-800 bg-gray-900/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="font-semibold text-white">{pack.name}</h4>
                  <p className="mt-1 text-sm leading-5 text-gray-400">{pack.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onApplyPack(pack)}
                  className="shrink-0 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20"
                >
                  Add pack
                </button>
              </div>
              <div className="mt-3 text-xs uppercase tracking-wide text-gray-500">{pack.scanner_ids.length} scanners</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {scanners.map((scanner) => (
          <SelectableCard
            key={scanner.id}
            title={scanner.name}
            checked={selectedIds.includes(scanner.id)}
            onToggle={() => onToggle(scanner.id)}
            badge={scanner.category}
            detail={scanner.description}
            meta={[
              `Signals: ${scanner.watch_signals.slice(0, 3).join(', ')}`,
              `Frames: ${scanner.timeframes.join(', ')}`,
              `Requires: ${scanner.requires.slice(0, 4).join(', ')}`,
            ]}
          />
        ))}
      </div>
    </div>
  );
}

function TickerTab({
  tickers,
  selectedIds,
  onToggle,
  scannerLookup,
}: {
  tickers: ScannerWorkbenchTicker[];
  selectedIds: string[];
  onToggle: (symbol: string) => void;
  scannerLookup: Map<string, ScannerWorkbenchScanner>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
      {tickers.map((ticker) => (
        <SelectableCard
          key={ticker.symbol}
          title={`${ticker.symbol} - ${ticker.name}`}
          checked={selectedIds.includes(ticker.symbol)}
          onToggle={() => onToggle(ticker.symbol)}
          badge={ticker.asset_class}
          detail={ticker.notes}
          meta={[
            `Liquidity: ${ticker.liquidity_profile}`,
            `Pairs with: ${formatIds(ticker.recommended_for, scannerLookup)}`,
          ]}
        />
      ))}
    </div>
  );
}

function StrategyTab({
  strategies,
  selectedIds,
  onToggle,
  onApplyKit,
  scannerLookup,
  indicatorLookup,
}: {
  strategies: ScannerWorkbenchStrategy[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onApplyKit: (strategy: ScannerWorkbenchStrategy) => void;
  scannerLookup: Map<string, ScannerWorkbenchScanner>;
  indicatorLookup: Map<string, ScannerWorkbenchIndicator>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
      {strategies.map((strategy) => (
        <div key={strategy.id} className="space-y-2">
          <SelectableCard
            title={strategy.name}
            checked={selectedIds.includes(strategy.id)}
            onToggle={() => onToggle(strategy.id)}
            badge={strategy.default_mode}
            detail={strategy.description}
            meta={[
              `Scanners: ${formatIds(strategy.scanner_ids, scannerLookup)}`,
              `Indicators: ${formatIds(strategy.indicator_ids, indicatorLookup)}`,
              strategy.risk_notes,
            ]}
          />
          <button
            type="button"
            onClick={() => onApplyKit(strategy)}
            className="w-full rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-500/20"
          >
            Add strategy kit
          </button>
        </div>
      ))}
    </div>
  );
}

function IndicatorTab({
  indicators,
  selectedIds,
  onToggle,
  strategyLookup,
}: {
  indicators: ScannerWorkbenchIndicator[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  strategyLookup: Map<string, ScannerWorkbenchStrategy>;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
      {indicators.map((indicator) => (
        <SelectableCard
          key={indicator.id}
          title={indicator.name}
          checked={selectedIds.includes(indicator.id)}
          onToggle={() => onToggle(indicator.id)}
          badge="indicator"
          detail={indicator.description}
          meta={[
            `Parameters: ${indicator.parameters.join(', ')}`,
            `Used by: ${formatIds(indicator.used_by, strategyLookup)}`,
          ]}
        />
      ))}
    </div>
  );
}

function SelectableCard({
  title,
  checked,
  onToggle,
  badge,
  detail,
  meta,
}: {
  title: string;
  checked: boolean;
  onToggle: () => void;
  badge: string;
  detail: string;
  meta: string[];
}) {
  return (
    <label
      className={`block rounded-lg border p-4 transition ${
        checked ? 'border-cyan-500/60 bg-cyan-500/10' : 'border-gray-800 bg-gray-900/60 hover:border-gray-700'
      }`}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-950 text-cyan-500 focus:ring-cyan-500"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-semibold text-white">{title}</h4>
            <span className="rounded-full border border-gray-700 px-2 py-0.5 text-xs uppercase tracking-wide text-gray-400">
              {badge}
            </span>
          </div>
          <p className="mt-2 text-sm leading-5 text-gray-300">{detail}</p>
          <div className="mt-3 space-y-1">
            {meta.map((item) => (
              <div key={item} className="text-xs leading-5 text-gray-500">
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </label>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/70 p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-1 text-2xl font-bold text-white">{value}</div>
      <div className="mt-1 text-sm text-gray-400">{detail}</div>
    </div>
  );
}

function WatchSummary({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-2 text-sm text-gray-300">
        {values.length ? values.slice(0, 4).join(', ') : 'None selected'}
        {values.length > 4 ? ` +${values.length - 4}` : ''}
      </div>
    </div>
  );
}

function formatIds<T extends { id: string; name: string }>(ids: string[], lookup: Map<string, T>) {
  const labels = ids.map((id) => lookup.get(id)?.name ?? id);
  if (!labels.length) return 'none';
  if (labels.length <= 3) return labels.join(', ');
  return `${labels.slice(0, 3).join(', ')} +${labels.length - 3}`;
}

function formatInvalidSelectionSummary(invalidSelections: ScannerWorkbenchWatchIntent) {
  return Object.entries(invalidSelections)
    .filter(([, values]) => values.length > 0)
    .map(([key, values]) => `${key} ${values.length}`)
    .join(', ');
}

function readScannerWorkbenchWatchState(): ScannerWorkbenchWatchIntent {
  if (typeof localStorage === 'undefined') return DEFAULT_WATCH_STATE;
  try {
    const raw = localStorage.getItem(SCANNER_WORKBENCH_STORAGE_KEY);
    if (!raw) return DEFAULT_WATCH_STATE;
    const parsed = JSON.parse(raw) as Partial<ScannerWorkbenchWatchIntent>;
    return {
      scanners: normalizeStringList(parsed.scanners),
      tickers: normalizeStringList(parsed.tickers),
      strategies: normalizeStringList(parsed.strategies),
      indicators: normalizeStringList(parsed.indicators),
    };
  } catch {
    return DEFAULT_WATCH_STATE;
  }
}

function normalizeStringList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.length > 0);
}
