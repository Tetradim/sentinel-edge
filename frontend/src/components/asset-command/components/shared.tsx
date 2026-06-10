import { AlertTriangle, CheckCircle, Pause, Play, Shield } from 'lucide-react';
import type { RuntimeState, Tone } from '../types';

export function RuntimeBadges({ runtime, onToggleScheduler }: { runtime: RuntimeState; onToggleScheduler: () => void }) {
  return (
    <div className="edge-runtime-badges" aria-label="Runtime status">
      <button
        type="button"
        className={`edge-runtime-pill ${runtime.schedulerPaused ? 'warn' : 'ok'}`}
        disabled={runtime.loading || !runtime.connected}
        aria-disabled={runtime.loading || !runtime.connected}
        onClick={onToggleScheduler}
      >
        {runtime.schedulerPaused ? <Play size={14} /> : <Pause size={14} />}
        {runtime.schedulerPaused ? 'Resume' : 'Pause'}
      </button>
      <span className={`edge-runtime-pill ${runtime.killSwitchActive ? 'danger' : 'muted'}`}>
        <AlertTriangle size={14} />
        {runtime.killSwitchActive ? 'Kill Active' : 'Kill Clear'}
      </span>
      <span className={`edge-runtime-pill ${runtime.pulseAvailable ? 'ok' : 'warn'}`}>
        <Shield size={14} />
        {runtime.pulseAvailable ? 'Pulse' : 'No Pulse'}
      </span>
      <span className={`edge-runtime-pill ${runtime.connected ? 'ok' : 'danger'}`}>
        {runtime.connected ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
        {runtime.loading ? 'Connecting' : runtime.connected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}

export function StatusMetric({ label, value, tone }: { label: string; value: string; tone?: Tone }) {
  return <div className="edge-status-metric"><span>{label}</span><strong className={tone ? `edge-${tone}` : ''}>{value}</strong></div>;
}

export function PanelTitle({ eyebrow, title, chip }: { eyebrow: string; title: string; chip?: string }) {
  return (
    <div className="edge-panel-title">
      <div><span>{eyebrow}</span><h2>{title}</h2></div>
      {chip && <div className="edge-chip">{chip}</div>}
    </div>
  );
}

export function HealthCard({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: Tone }) {
  return <article className={`edge-health-card edge-tone-${tone}`}><span>{label}</span><strong>{value}</strong><p>{detail}</p></article>;
}

export function SectionHead({ label, value }: { label: string; value: string }) {
  return <div className="edge-section-head"><span>{label}</span><strong>{value}</strong></div>;
}

export function ServiceRow({ row }: { row: string[] }) {
  return <div className="edge-service-row"><div><strong>{row[0]}</strong><span>{row[3]}</span></div><b>{row[1]}</b><em>{row[2]}</em></div>;
}
