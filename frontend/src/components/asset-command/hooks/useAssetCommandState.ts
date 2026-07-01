import { useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import { defaultCoreHeatmapConfig, initialEvents, money, nowTime, tickers } from '../data';
import type { CoreHeatmapConfig, EventFilter, EventLine, SignalIntelligenceModel, Tone } from '../types';

const CORE_CONFIG_STORAGE_KEY = 'edge_core_heatmap_config';

export function useAssetCommandState() {
  const [selectedSymbol, setSelectedSymbol] = useState('SPY');
  const [horizon, setHorizon] = useState('30m');
  const [menuOpen, setMenuOpen] = useState(false);
  const [customHorizon, setCustomHorizon] = useState('90m');
  const [visibleReels, setVisibleReels] = useState(5);
  const [selectedMetrics, setSelectedMetrics] = useState(['hist', 'vscore', 'emaTop', 'invalid', 'momentum']);
  const [coreConfig, setCoreConfig] = useState<CoreHeatmapConfig>(() => loadCoreConfig());
  const [coreConfigOpen, setCoreConfigOpen] = useState(false);
  const [events, setEvents] = useState<EventLine[]>(() => initialEvents.map((event) => ({ ...event, time: nowTime() })));
  const [eventFilter, setEventFilter] = useState<EventFilter>('all');
  const [feedPaused, setFeedPaused] = useState(false);
  const [protectionMode, setProtectionMode] = useState('armed');
  const wheelDelta = useRef(0);
  const wheelLocked = useRef(false);

  const selected = tickers.find((ticker) => ticker.symbol === selectedSymbol) || tickers[0];
  const selectedIndex = tickers.findIndex((ticker) => ticker.symbol === selected.symbol);
  const watcher = selected.watchers[0];
  const reels = selected.metrics.filter((metric) => selectedMetrics.includes(metric.id)).slice(0, visibleReels);
  const eventFilterCounts: Record<EventFilter, number> = {
    all: events.length,
    selected: events.filter((event) => event.symbol === selected.symbol).length,
  };
  const visibleEvents = events.filter((event) => {
    if (eventFilter === 'selected') return event.symbol === selected.symbol;
    return true;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(CORE_CONFIG_STORAGE_KEY, JSON.stringify(coreConfig));
  }, [coreConfig]);

  const intelligence: SignalIntelligenceModel = useMemo(() => {
    const pluginBoost = selected.watchers.length ? 18 : 4;
    return {
      move: selected.watchers.some((item) => item.plugin === 'MACD-V') ? '+0.8%' : '+0.4%',
      price: money(selected.price),
      delta: selected.watchers.length ? '+4 pts' : '+1 pt',
      state: selected.watchers.length ? 'strengthening' : 'monitoring',
      pressure: selected.watchers.length ? `${selected.watchers[0].plugin} pressure rising` : 'baseline pressure stable',
      contributors: [
        { label: 'Trend', value: '+22', tone: 'green' as Tone },
        { label: 'Volume', value: '+14', tone: 'cyan' as Tone },
        { label: 'Risk', value: '-6', tone: 'red' as Tone },
        { label: 'Plugin', value: `+${pluginBoost}`, tone: 'gold' as Tone },
      ],
    };
  }, [selected]);

  const addEvent = (symbol: string, title: string, detail: string) => {
    setEvents((current) => [{ id: `${Date.now()}`, symbol, title, detail, time: nowTime() }, ...current].slice(0, 12));
  };

  const selectSymbol = (symbol: string) => {
    const ticker = tickers.find((item) => item.symbol === symbol);
    if (!ticker) return;
    if (symbol === selectedSymbol) return;
    setSelectedSymbol(symbol);
    setSelectedMetrics(ticker.metrics.slice(0, visibleReels).map((metric) => metric.id));
    addEvent(symbol, 'Ticker selected', `${symbol} command state loaded`);
  };

  const movePicker = (direction: number) => {
    const nextIndex = (selectedIndex + direction + tickers.length) % tickers.length;
    selectSymbol(tickers[nextIndex].symbol);
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (wheelLocked.current) return;
    wheelDelta.current += event.deltaY;
    if (Math.abs(wheelDelta.current) < 95) return;
    const direction = wheelDelta.current > 0 ? 1 : -1;
    wheelDelta.current = 0;
    wheelLocked.current = true;
    movePicker(direction);
    window.setTimeout(() => {
      wheelLocked.current = false;
    }, 240);
  };

  const handlePickerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const nextAction =
      event.key === 'ArrowDown' ? () => movePicker(1) :
      event.key === 'ArrowUp' ? () => movePicker(-1) :
      event.key === 'Home' ? () => selectSymbol(tickers[0].symbol) :
      event.key === 'End' ? () => selectSymbol(tickers[tickers.length - 1].symbol) :
      null;
    if (!nextAction) return;
    event.preventDefault();
    nextAction();
  };

  const setPrediction = (next: string) => {
    setHorizon(next);
    setMenuOpen(false);
    addEvent(selected.symbol, 'Prediction horizon changed', `Forecast window set to ${next}`);
  };

  const runCommand = (action: string) => {
    const labels: Record<string, string> = {
      arm: 'Arm Trigger',
      'risk sweep': 'Risk Sweep',
      alert: 'Convert to Alert',
      mute: 'Mute Watch',
    };
    addEvent(selected.symbol, labels[action] || action, `${selected.status} command acknowledged`);
  };

  const runMonitorAction = (action: string) => {
    if (action === 'toggle-feed') setFeedPaused((value) => !value);
    if (action === 'ack') addEvent('EDGE', 'Monitor alerts acknowledged', '3 alerts cleared');
    if (action === 'diagnostics') addEvent('EDGE', 'Diagnostics completed', 'Plugin bus, Pulse bridge, and prediction core checked');
    if (action === 'refresh') addEvent('EDGE', 'Monitor refreshed', 'Health probes and watcher telemetry updated');
  };

  const runProtectionAction = (action: string) => {
    const labels: Record<string, [string, string]> = {
      refresh: ['Protection refreshed', 'Stops, heat, hedge ratio, and invalidation bands updated'],
      tighten: ['Stops tightened', 'Stops trailed toward current price across protected positions'],
      hedge: ['Hedge staged', 'Coverage raised toward the target corridor'],
      reduce: ['Exposure reduced', 'Highest heat symbol reduced and redline corridor recalculated'],
      clear: ['Protection alerts acknowledged', 'Protection queue cleared'],
    };
    if (action === 'tighten') setProtectionMode('tightened');
    if (action === 'hedge') setProtectionMode('hedged');
    if (action === 'reduce') setProtectionMode('de-risked');
    const [title, detail] = labels[action] || labels.refresh;
    addEvent('PROTECT', title, detail);
  };

  const toggleMetric = (id: string) => {
    setSelectedMetrics((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const updateCoreConfig = <K extends keyof CoreHeatmapConfig>(key: K, value: CoreHeatmapConfig[K]) => {
    setCoreConfig((current) => ({ ...current, [key]: value }));
  };

  const resetCoreConfig = () => {
    setCoreConfig(defaultCoreHeatmapConfig);
    addEvent('EDGE', 'Core heatmap reset', 'Visualization settings restored to the default risk view');
  };

  const applyCoreConfig = () => {
    setCoreConfigOpen(false);
    addEvent('EDGE', 'Core heatmap configured', `${coreConfig.colorMetric} color / ${coreConfig.sizeMetric} size / ${coreConfig.horizon}`);
  };

  const selectCoreTicker = (symbol: string) => {
    if (coreConfig.autoFocusTicker) selectSymbol(symbol);
    addEvent(symbol, 'Core heat cell inspected', `${coreConfig.colorMetric} view with ${coreConfig.sizeMetric} sizing`);
  };

  const pickerItems = Array.from({ length: 7 }, (_, offset) => tickers[(selectedIndex + offset - 3 + tickers.length) % tickers.length]);

  return {
    selected,
    watcher,
    reels,
    horizon,
    menuOpen,
    setMenuOpen,
    customHorizon,
    setCustomHorizon,
    coreConfig,
    coreConfigOpen,
    setCoreConfigOpen,
    visibleReels,
    setVisibleReels,
    selectedMetrics,
    eventFilter,
    setEventFilter,
    eventFilterCounts,
    visibleEvents,
    events,
    intelligence,
    feedPaused,
    protectionMode,
    pickerItems,
    addEvent,
    selectSymbol,
    handleWheel,
    handlePickerKeyDown,
    setPrediction,
    runCommand,
    runMonitorAction,
    runProtectionAction,
    toggleMetric,
    updateCoreConfig,
    resetCoreConfig,
    applyCoreConfig,
    selectCoreTicker,
  };
}

function loadCoreConfig(): CoreHeatmapConfig {
  if (typeof window === 'undefined') return defaultCoreHeatmapConfig;

  try {
    const savedConfig = window.localStorage.getItem(CORE_CONFIG_STORAGE_KEY);
    if (!savedConfig) return defaultCoreHeatmapConfig;

    const parsed = JSON.parse(savedConfig) as Partial<CoreHeatmapConfig>;
    return {
      ...defaultCoreHeatmapConfig,
      ...parsed,
      density: clampConfigNumber(parsed.density, 3, 7, defaultCoreHeatmapConfig.density),
      alertThreshold: clampConfigNumber(parsed.alertThreshold, 30, 90, defaultCoreHeatmapConfig.alertThreshold),
      horizon: typeof parsed.horizon === 'string' && parsed.horizon.trim() ? parsed.horizon : defaultCoreHeatmapConfig.horizon,
      operatorNote: typeof parsed.operatorNote === 'string' ? parsed.operatorNote : defaultCoreHeatmapConfig.operatorNote,
    };
  } catch {
    return defaultCoreHeatmapConfig;
  }
}

function clampConfigNumber(value: unknown, min: number, max: number, fallback: number) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return fallback;
  return Math.max(min, Math.min(max, numberValue));
}
