export function LazyPanelFallback({ label = 'Loading workspace' }: { label?: string }) {
  return (
    <div className="edge-tab-panel" aria-busy="true">
      <div className="edge-tab-head">
        <div>
          <span>Loading</span>
          <h2>{label}</h2>
        </div>
        <div className="edge-chip">streaming module</div>
      </div>
    </div>
  );
}
