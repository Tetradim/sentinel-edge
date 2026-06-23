import { useEffect, useState } from 'react';
import { tickers } from './data';
import { ChartWorkspace } from '../dashboards/ChartWorkspace';
import { ActivityLog } from './components/ActivityLog';
import { CommandModePanel } from './components/CommandModePanel';
import { ModeTabs } from './components/ModeTabs';
import { MonitorPanel } from './components/MonitorPanel';
import { OperationsPanel } from './components/OperationsPanel';
import { ProtectionPanel } from './components/ProtectionPanel';
import { SettingsPanel } from './components/SettingsPanel';
import { TickerPicker } from './components/TickerPicker';
import { PanelTitle, RuntimeBadges, StatusMetric } from './components/shared';
import { useAssetCommandNavigation } from './hooks/useAssetCommandNavigation';
import { useAssetCommandState } from './hooks/useAssetCommandState';
import { useRuntimeStatus } from './hooks/useRuntimeStatus';
import './AssetCommandConsole.css';

export default function AssetCommandConsole() {
  const {
    mode,
    operationsView,
    setMode,
    setOperationsView,
    handleModeKeyDown,
    handleOperationsKeyDown,
  } = useAssetCommandNavigation();
  const {
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
    updateCoreConfig,
    resetCoreConfig,
    applyCoreConfig,
    selectCoreTicker,
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
  } = useAssetCommandState();
  const { runtime, toggleScheduler } = useRuntimeStatus(addEvent);
  const [clock, setClock] = useState('--:--');
  const [showPulseStartup, setShowPulseStartup] = useState(true);

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <main className="edge-console" aria-label="Sentinel Edge asset command console">
      <div className="edge-frame" aria-hidden="true" />
      {showPulseStartup && (
        <PulseStartupPanel
          runtime={runtime}
          onConnect={() => setShowPulseStartup(false)}
          onStandalone={() => setShowPulseStartup(false)}
        />
      )}
      <nav className="edge-top-nav">
        <div className="edge-brand">
          <div className="edge-brand-mark" aria-hidden="true" />
          <div>
            Sentinel Edge
            <small>Asset command console</small>
          </div>
        </div>
        <ModeTabs mode={mode} setMode={setMode} handleModeKeyDown={handleModeKeyDown} />
        <div className="edge-clock">
          <RuntimeBadges runtime={runtime} onToggleScheduler={toggleScheduler} />
          <div>
            <span>Current time</span>
            <strong>{clock}</strong>
            <span>local / live</span>
          </div>
          <div className="edge-radar" aria-hidden="true" />
        </div>
      </nav>

      <section className="edge-status-strip" aria-label="Portfolio status">
        <div className="edge-primary-metric">Total PBL: <strong>+$12,500.75</strong></div>
        <StatusMetric label="Selected asset" value={selected.symbol} tone="cyan" />
        <StatusMetric label="Prediction horizon" value={horizon} />
        <StatusMetric label="Signal exposure" value="64.8%" tone="gold" />
        <StatusMetric label="Risk corridor" value="2.18R" tone="red" />
      </section>

      <section className="edge-command-grid">
        <ActivityLog
          selectedSymbol={selected.symbol}
          events={events}
          visibleEvents={visibleEvents}
          eventFilter={eventFilter}
          eventFilterCounts={eventFilterCounts}
          setEventFilter={setEventFilter}
          selectSymbol={selectSymbol}
        />

        <section
          id={`edge-mode-panel-${mode}`}
          className="edge-glass edge-center"
          role="tabpanel"
          aria-label="Asset command center"
        >
          <header className="edge-command-header">
            <div>
              <span>Asset command</span>
              <h1>{selected.symbol}</h1>
            </div>
            <div className="edge-chip">{watcher ? `${watcher.plugin} watcher active` : 'No active watcher'}</div>
          </header>

          {mode === 'command' && (
            <CommandModePanel
              selected={selected}
              watcher={watcher}
              intelligence={intelligence}
              horizon={horizon}
              menuOpen={menuOpen}
              setMenuOpen={setMenuOpen}
              customHorizon={customHorizon}
              setCustomHorizon={setCustomHorizon}
              coreConfig={coreConfig}
              coreConfigOpen={coreConfigOpen}
              setCoreConfigOpen={setCoreConfigOpen}
              updateCoreConfig={updateCoreConfig}
              resetCoreConfig={resetCoreConfig}
              applyCoreConfig={applyCoreConfig}
              selectCoreTicker={selectCoreTicker}
              setPrediction={setPrediction}
              reels={reels}
            />
          )}

          {mode === 'market-map' && <ChartWorkspace />}

          {mode === 'monitor' && (
            <MonitorPanel
              runtime={runtime}
              feedPaused={feedPaused}
              tickers={tickers}
              onAction={runMonitorAction}
              onSelect={selectSymbol}
            />
          )}

          {mode === 'protect' && (
            <ProtectionPanel mode={protectionMode} onAction={runProtectionAction} onSelect={selectSymbol} selectedSymbol={selected.symbol} />
          )}

          {mode === 'operations' && (
            <OperationsPanel
              activeView={operationsView}
              setActiveView={setOperationsView}
              handleOperationsKeyDown={handleOperationsKeyDown}
            />
          )}

          {mode === 'settings' && (
            <SettingsPanel
              visibleReels={visibleReels}
              setVisibleReels={setVisibleReels}
              selectedMetrics={selectedMetrics}
              toggleMetric={toggleMetric}
              onSave={() => addEvent(selected.symbol, 'Metric reel settings updated', `${visibleReels} reels visible`)}
            />
          )}
        </section>

        <aside className="edge-right-stack">
          <TickerPicker
            selectedSymbol={selected.symbol}
            pickerItems={pickerItems}
            onWheel={handleWheel}
            onKeyDown={handlePickerKeyDown}
            selectSymbol={selectSymbol}
          />

          <section className="edge-glass edge-command-panel" aria-label="Plugin commands">
            <PanelTitle eyebrow={watcher ? `${watcher.plugin} command panel` : 'Command panel'} title={selected.symbol} />
            <div className="edge-command-buttons">
              <button type="button" onClick={() => runCommand('arm')}>Arm Trigger</button>
              <button type="button" onClick={() => runCommand('backtest')}>Backtest</button>
              <button type="button" onClick={() => runCommand('alert')}>Convert Alert</button>
              <button type="button" onClick={() => runCommand('mute')}>Mute Watch</button>
            </div>
            <div className="edge-plugin-watch">
              <div>Status <strong>{watcher ? watcher.status : 'idle'}</strong></div>
              <div>Trigger <strong>{watcher ? watcher.trigger : 'none'}</strong></div>
              <div>Source <strong>{watcher ? watcher.source : 'Sentinel Pulse'}</strong></div>
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function PulseStartupPanel({
  runtime,
  onConnect,
  onStandalone,
}: {
  runtime: { connected: boolean; loading: boolean; pulseAvailable: boolean };
  onConnect: () => void;
  onStandalone: () => void;
}) {
  return (
    <section className="edge-pulse-startup edge-glass" aria-label="Sentinel Pulse startup choice">
      <div>
        <span>Sentinel Pulse</span>
        <strong>{runtime.pulseAvailable ? 'Execution bridge detected' : runtime.loading ? 'Checking execution bridge' : 'Execution bridge unavailable'}</strong>
        <p>{runtime.pulseAvailable ? 'Connect Edge to Pulse for order execution and live position updates.' : 'Run Edge standalone while Pulse is unavailable; decisions stay visible without order handoff.'}</p>
      </div>
      <div className="edge-pulse-actions">
        <button type="button" onClick={onConnect}>
          {runtime.pulseAvailable ? 'Connect to Pulse' : 'Try Connecting'}
        </button>
        <button type="button" onClick={onStandalone}>Standalone Mode</button>
      </div>
    </section>
  );
}
