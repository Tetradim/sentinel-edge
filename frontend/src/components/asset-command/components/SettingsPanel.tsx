import type React from 'react';
import { Save } from 'lucide-react';
import { allMetricOptions } from '../data';
import { UiIterationLab } from './UiIterationLab';

export function SettingsPanel({
  visibleReels,
  setVisibleReels,
  selectedMetrics,
  toggleMetric,
  onSave,
}: {
  visibleReels: number;
  setVisibleReels: React.Dispatch<React.SetStateAction<number>>;
  selectedMetrics: string[];
  toggleMetric: (id: string) => void;
  onSave: () => void;
}) {
  return (
    <>
      <section className="edge-tab-panel edge-settings-panel">
        <div className="edge-tab-head"><div><span>Settings</span><h2>Metric reels</h2></div></div>
        <div className="edge-settings-grid">
          <label>Visible reels<input type="number" min={1} max={8} value={visibleReels} onChange={(event) => setVisibleReels(Math.max(1, Math.min(8, Number(event.target.value))))} /></label>
          <div className="edge-metric-options">{allMetricOptions.map((metric) => <label key={metric.id}><input type="checkbox" checked={selectedMetrics.includes(metric.id)} onChange={() => toggleMetric(metric.id)} />{metric.label}</label>)}</div>
          <button type="button" onClick={onSave}><Save size={14} />Apply settings</button>
        </div>
      </section>
      <UiIterationLab />
    </>
  );
}
