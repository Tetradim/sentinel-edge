import { useMemo, useRef, useState } from 'react';
import type React from 'react';
import { initialEvents, money, nowTime, tickers } from '../data';
import type { EventFilter, EventLine, SignalIntelligenceModel, Tone } from '../types';

export function useAssetCommandState() {
  const [selectedSymbol, setSelectedSymbol] = useState('SPY');
  const [horizon, setHorizon] = useState('30m');
  const [menuOpen, setMenuOpen] = useState(false);
  const [customHorizon, setCustomHorizon] = useState('90m');
  const [visibleReels, setVisibleReels] = useState(5);
  const [selectedMetrics, setSelectedMetrics] = useState(['hist', 'vscore', 'emaTop', 'invalid', 'momentum']);
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
    system: events.filter((event) => event.symbol === 'EDGE' || event.symbol === 'PROTECT').length,
  };
  const visibleEvents = events.filter((event) => {
    if (eventFilter === 'selected') return event.symbol === selected.symbol;
    if (eventFilter === 'system') return event.symbol === 'EDGE' || event.symbol === 'PROTECT';
    return true;
  });

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
      backtest: 'Backtest Window',
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
  };
}
