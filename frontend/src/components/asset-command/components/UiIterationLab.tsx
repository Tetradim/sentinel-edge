import { useMemo, useState } from 'react';
import type React from 'react';
import { tickers } from '../data';

type IterationFamily = 'new' | 'modified';

interface UiIteration {
  id: string;
  title: string;
  thesis: string;
  layout: string;
  readability: string;
  customization: string;
  background: string;
  visual: string;
}

const newUiIterations: UiIteration[] = [
  {
    id: 'new-01',
    title: 'Ops ledger',
    thesis: 'A dense operator ledger with the command bar always visible and the selected ticker treated like a work order.',
    layout: 'Top status rail, left event rail, middle decision ledger, right configuration stack.',
    readability: 'Highest text contrast, fewer glow layers, larger row targets.',
    customization: 'Saved column sets, command presets, and ticker-specific input defaults.',
    background: '/assets/edge-circuit-matte.jpg',
    visual: 'ledger',
  },
  {
    id: 'new-02',
    title: 'Hex heat desk',
    thesis: 'The heatmap becomes the primary navigation object for scanning risk, signal, and flow.',
    layout: 'Full-width hex matrix, detail drawer, compact activity footer.',
    readability: 'Large ticker labels and explicit heat numbers instead of color-only meaning.',
    customization: 'Color metric, size metric, universe, and threshold controls.',
    background: '/assets/edge-hex-gold.jpg',
    visual: 'hex',
  },
  {
    id: 'new-03',
    title: 'Split scanner',
    thesis: 'Fast scanning first: search, filters, chart context, then commands.',
    layout: 'Left scanner filters, center chart workspace, bottom command tray.',
    readability: 'Wide chart zone with compact cards and fewer simultaneous panels.',
    customization: 'Filter chips, saved scans, and command tray layouts.',
    background: '/assets/edge-hud-frame.jpg',
    visual: 'scanner',
  },
  {
    id: 'new-04',
    title: 'Risk map wall',
    thesis: 'Protection state is always visible as a map of breach distance and exposure.',
    layout: 'Risk heat wall, protection summary, staged action queue.',
    readability: 'Risk numbers use fixed columns and clear labels for stop, invalidation, and exposure.',
    customization: 'Risk-only view presets, alert threshold sliders, and position grouping.',
    background: '/assets/edge-red-armor.jpg',
    visual: 'risk',
  },
  {
    id: 'new-05',
    title: 'Quiet analyst',
    thesis: 'A calmer reading mode for review sessions, tutorials, and low-stress monitoring.',
    layout: 'Single-column analysis stream with pinned asset controls and notes.',
    readability: 'Reduced saturation, wider line height, and focused text blocks.',
    customization: 'Font scale, note templates, and simplified metric sets.',
    background: '/assets/edge-circuit-matte.jpg',
    visual: 'analyst',
  },
];

const modifiedUiIterations: UiIteration[] = [
  {
    id: 'mod-01',
    title: 'Original plus heat core',
    thesis: 'Keeps the current command-console frame and turns the center hex into the active configuration surface.',
    layout: 'Original three-column shell with heat core in the existing target slot.',
    readability: 'Preserves the current mental model while adding explicit heat summaries.',
    customization: 'Core modal, metric reel chooser, and ticker click behavior.',
    background: '/assets/edge-hex-gold.jpg',
    visual: 'original-core',
  },
  {
    id: 'mod-02',
    title: 'Original compact nav',
    thesis: 'Keeps the visual identity but reduces navigation weight so status and inputs are easier to scan.',
    layout: 'Original shell with a shorter mode switch and consolidated runtime pills.',
    readability: 'More room for the status strip and fewer competing capsule controls.',
    customization: 'Reorder modes, hide unused modes, and pin the preferred start view.',
    background: '/assets/edge-hud-frame.jpg',
    visual: 'original-nav',
  },
  {
    id: 'mod-03',
    title: 'Original redline protect',
    thesis: 'Keeps command mode intact but surfaces redline risk next to every command action.',
    layout: 'Original center panel with a persistent protect ribbon and staged action queue.',
    readability: 'Stop and invalidation values become first-class text, not secondary details.',
    customization: 'Risk ribbon thresholds, hedge targets, and confirm-before-reduce toggles.',
    background: '/assets/edge-red-armor.jpg',
    visual: 'original-redline',
  },
  {
    id: 'mod-04',
    title: 'Original command drawer',
    thesis: 'Keeps the current watchlist and activity rail while moving commands into a larger drawer.',
    layout: 'Original grid with a right-side drawer for command forms and plugin inputs.',
    readability: 'Commands get full labels, help text, and validation space.',
    customization: 'Per-command defaults, confirmation levels, and saved form templates.',
    background: '/assets/edge-circuit-matte.jpg',
    visual: 'original-drawer',
  },
  {
    id: 'mod-05',
    title: 'Original readability pass',
    thesis: 'Keeps the current layout but dials down glow, raises font size, and improves form targets.',
    layout: 'Original panels with stronger labels, larger controls, and fewer micro panels.',
    readability: 'Better body copy size and clearer visual hierarchy for long sessions.',
    customization: 'Operator density, font scale, accent color, and reduced-motion presets.',
    background: '/assets/edge-circuit-matte.jpg',
    visual: 'original-readable',
  },
];

export function UiIterationLab() {
  const [family, setFamily] = useState<IterationFamily>('new');
  const [activeIndex, setActiveIndex] = useState(0);
  const [previewTicker, setPreviewTicker] = useState('SPY');
  const [density, setDensity] = useState('balanced');
  const [fontScale, setFontScale] = useState(100);
  const [accent, setAccent] = useState('#f6c14a');
  const [readabilityOverlay, setReadabilityOverlay] = useState(true);
  const iterations = family === 'new' ? newUiIterations : modifiedUiIterations;
  const active = iterations[Math.min(activeIndex, iterations.length - 1)];
  const ticker = useMemo(() => tickers.find((item) => item.symbol === previewTicker) || tickers[0], [previewTicker]);

  const setIterationFamily = (nextFamily: IterationFamily) => {
    setFamily(nextFamily);
    setActiveIndex(0);
  };

  return (
    <section className="edge-ui-lab" aria-label="UI iteration lab">
      <div className="edge-ui-lab-head">
        <div>
          <span>UI iteration lab</span>
          <h2>10 interface directions</h2>
        </div>
        <div className="edge-ui-family-switch" aria-label="Iteration family">
          <button type="button" className={family === 'new' ? 'active' : ''} onClick={() => setIterationFamily('new')}>5 new UI</button>
          <button type="button" className={family === 'modified' ? 'active' : ''} onClick={() => setIterationFamily('modified')}>5 original mods</button>
        </div>
      </div>

      <div className="edge-ui-lab-controls">
        <label>Preview ticker
          <select value={previewTicker} onChange={(event) => setPreviewTicker(event.target.value)}>
            {tickers.map((item) => <option key={item.symbol} value={item.symbol}>{item.symbol}</option>)}
          </select>
        </label>
        <label>Density
          <select value={density} onChange={(event) => setDensity(event.target.value)}>
            <option value="compact">Compact</option>
            <option value="balanced">Balanced</option>
            <option value="spacious">Spacious</option>
          </select>
        </label>
        <label>Font scale <strong>{fontScale}%</strong>
          <input type="range" min={90} max={118} value={fontScale} onChange={(event) => setFontScale(Number(event.target.value))} />
        </label>
        <label>Accent
          <input type="color" value={accent} onChange={(event) => setAccent(event.target.value)} />
        </label>
        <label className="edge-ui-check"><input type="checkbox" checked={readabilityOverlay} onChange={(event) => setReadabilityOverlay(event.target.checked)} />Readability layer</label>
      </div>

      <div className="edge-ui-lab-layout">
        <div className="edge-ui-iteration-list" role="tablist" aria-label={`${family} UI iterations`}>
          {iterations.map((iteration, index) => (
            <button
              key={iteration.id}
              id={`edge-ui-iteration-${iteration.id}`}
              type="button"
              role="tab"
              aria-selected={active.id === iteration.id}
              className={active.id === iteration.id ? 'active' : ''}
              onClick={() => setActiveIndex(index)}
            >
              <b>{String(index + 1).padStart(2, '0')}</b>
              <span>{iteration.title}</span>
            </button>
          ))}
        </div>

        <article
          className={`edge-ui-preview density-${density} ${readabilityOverlay ? 'readable' : ''}`}
          style={{
            '--ui-accent': accent,
            '--ui-scale': `${fontScale}%`,
            backgroundImage: `linear-gradient(rgba(2, 6, 10, .78), rgba(2, 6, 10, .9)), url("${active.background}")`,
          } as React.CSSProperties & Record<string, string>}
          aria-labelledby={`edge-ui-iteration-${active.id}`}
        >
          <div className={`edge-ui-preview-media ${active.visual}`}>
            <div className="edge-ui-mini-top"><span>Sentinel Edge</span><b>{ticker.symbol}</b><em>{ticker.signal}</em></div>
            <div className="edge-ui-mini-main">
              <div className="edge-ui-mini-rail">
                <span>Activity</span>
                <strong>{ticker.status}</strong>
                <i>{ticker.change}</i>
              </div>
              <div className="edge-ui-mini-stage">
                <span>{active.title}</span>
                <strong>{ticker.watchers[0]?.plugin || 'Pulse'}</strong>
                <div className="edge-ui-mini-heat">
                  {ticker.metrics.slice(0, 6).map((metric, index) => (
                    <i key={`${active.id}-${metric.id}`} style={{ '--heat-index': String(index) } as React.CSSProperties}>{metric.value}</i>
                  ))}
                </div>
              </div>
              <div className="edge-ui-mini-drawer">
                <span>Inputs</span>
                <strong>{density}</strong>
                <button type="button">Configure</button>
              </div>
            </div>
          </div>
          <div className="edge-ui-preview-copy">
            <h3>{active.title}</h3>
            <p>{active.thesis}</p>
            <dl>
              <div><dt>Layout</dt><dd>{active.layout}</dd></div>
              <div><dt>Readability</dt><dd>{active.readability}</dd></div>
              <div><dt>Customization</dt><dd>{active.customization}</dd></div>
            </dl>
          </div>
        </article>
      </div>
    </section>
  );
}
