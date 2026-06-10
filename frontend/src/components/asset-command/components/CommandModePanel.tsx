import type React from 'react';
import type { Metric, SignalIntelligenceModel, Ticker, Watcher } from '../types';

export function CommandModePanel({
  selected,
  watcher,
  intelligence,
  horizon,
  menuOpen,
  setMenuOpen,
  customHorizon,
  setCustomHorizon,
  setPrediction,
  reels,
}: {
  selected: Ticker;
  watcher?: Watcher;
  intelligence: SignalIntelligenceModel;
  horizon: string;
  menuOpen: boolean;
  setMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  customHorizon: string;
  setCustomHorizon: React.Dispatch<React.SetStateAction<string>>;
  setPrediction: (next: string) => void;
  reels: Metric[];
}) {
  return (
    <>
      <section className="edge-console-grid">
        <SignalIntelligence intelligence={intelligence} />
        <section className="edge-signal-stack" aria-label="Signal and plugin">
          <div className="edge-signal-box">
            <div className="edge-label">Signal</div>
            <strong>{selected.signal}</strong>
            <svg viewBox="0 0 120 18" aria-label="Signal confidence history">
              <path d="M2 15 L14 12 L26 13 L38 9 L50 10 L62 7 L74 8 L86 5 L98 6 L118 3" />
              <path className="fill" d="M2 15 L14 12 L26 13 L38 9 L50 10 L62 7 L74 8 L86 5 L98 6 L118 3 L118 18 L2 18 Z" />
            </svg>
            <span>core alignment</span>
          </div>
          <div className={`edge-plugin-box ${watcher ? '' : 'idle'}`}>
            <div className="edge-label">Plugin watcher</div>
            <strong>{watcher ? watcher.plugin : 'None'}</strong>
            <span>{watcher ? `${watcher.source} / ${watcher.status}` : 'Sentinel Pulse / idle'}</span>
          </div>
        </section>
        <section className="edge-hex-wrap" aria-label="Edge core"><div className="edge-target-core" /></section>
        <section className="edge-prediction" aria-label="Prediction horizon">
          <button type="button" className="edge-predict-button" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}>
            <span>Predict</span><strong>{horizon}</strong><b>v</b>
          </button>
          {menuOpen && (
            <div className="edge-predict-menu">
              {['30m', '3h', 'today'].map((item) => <button key={item} type="button" onClick={() => setPrediction(item)}>{item}</button>)}
              <label>Custom<input value={customHorizon} maxLength={16} onChange={(event) => setCustomHorizon(event.target.value)} /></label>
              <button type="button" onClick={() => setPrediction(customHorizon || '30m')}>Apply</button>
            </div>
          )}
          <div className="edge-horizon-hint">3h / today / custom</div>
        </section>
      </section>
      <MetricReels reels={reels} source={watcher ? `${watcher.plugin} source` : 'market source'} availableCount={selected.metrics.length} />
    </>
  );
}

function SignalIntelligence({ intelligence }: { intelligence: SignalIntelligenceModel }) {
  return (
    <section className="edge-intel-card" aria-label="Signal intelligence">
      <div className="edge-label">Signal intelligence</div>
      <div className="edge-intel-grid">
        <div><span>Move</span><strong>{intelligence.move}</strong></div>
        <div><span>Price</span><strong>{intelligence.price}</strong></div>
        <div><span>Delta</span><strong>{intelligence.delta}</strong></div>
        <div><span>State</span><strong>{intelligence.state}</strong></div>
      </div>
      <div className="edge-intel-note">last 12 candles / {intelligence.pressure}</div>
      <div className="edge-contributors">
        {intelligence.contributors.map((item) => (
          <span key={item.label} className={`edge-contributor edge-tone-${item.tone}`}>{item.label} {item.value}</span>
        ))}
      </div>
    </section>
  );
}

function MetricReels({ reels, source, availableCount }: { reels: Metric[]; source: string; availableCount: number }) {
  return (
    <section className="edge-reels-panel" aria-label="Metric reels">
      <div className="edge-reel-header">
        <span>Slot metric reels</span>
        <div><span>{source}</span><span>{reels.length} of {availableCount} visible</span></div>
      </div>
      <div className="edge-reels" tabIndex={0} aria-label="Scrollable metric reel slots">
        {reels.map((metric) => (
          <div key={metric.id} className="edge-reel">
            <div>
              <span>{metric.label}</span>
              <strong className={`edge-tone-${metric.tone}`}>{metric.value}<br />{metric.detail}</strong>
              <span>{metric.id}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
