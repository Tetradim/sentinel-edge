import type React from 'react';
import { Suspense, lazy } from 'react';
import type { TutorialModuleView } from '../../tutorials';
import { operationsViews } from '../data';
import type { OperationsView } from '../types';
import { LazyPanelFallback } from './LazyPanelFallback';

const TradingOverview = lazy(() =>
  import('../../dashboards/TradingOverview').then((module) => ({ default: module.TradingOverview })),
);
const ScannerWorkbench = lazy(() =>
  import('../../dashboards/ScannerWorkbench').then((module) => ({ default: module.ScannerWorkbench })),
);
const AdvisorHealth = lazy(() =>
  import('../../dashboards/AdvisorHealth').then((module) => ({ default: module.AdvisorHealth })),
);
const ExperienceDashboard = lazy(() =>
  import('../../dashboards/ExperienceDashboard').then((module) => ({ default: module.ExperienceDashboard })),
);
const OperationsProtectionDashboard = lazy(() =>
  import('../../dashboards/ProtectionDashboard').then((module) => ({ default: module.ProtectionDashboard })),
);
const PnLTracking = lazy(() => import('../../dashboards/PnLTracking').then((module) => ({ default: module.PnLTracking })));
const MarketCoverage = lazy(() =>
  import('../../dashboards/MarketCoverage').then((module) => ({ default: module.MarketCoverage })),
);
const PortfolioAnalytics = lazy(() =>
  import('../../dashboards/PortfolioAnalytics').then((module) => ({ default: module.PortfolioAnalytics })),
);
const SettingsDashboard = lazy(() =>
  import('../../dashboards/SettingsDashboard').then((module) => ({ default: module.SettingsDashboard })),
);
const TutorialsDashboard = lazy(() => import('../../tutorials').then((module) => ({ default: module.TutorialsDashboard })));

export function OperationsPanel({
  activeView,
  setActiveView,
  handleOperationsKeyDown,
}: {
  activeView: OperationsView;
  setActiveView: (view: OperationsView) => void;
  handleOperationsKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>, currentView: OperationsView) => void;
}) {
  return (
    <section className="edge-tab-panel edge-ops-panel" aria-label="Operations deck">
      <div className="edge-tab-head">
        <div>
          <span>Operations</span>
          <h2>Legacy feature deck</h2>
        </div>
        <div className="edge-chip">all old UI modules</div>
      </div>
      <div className="edge-ops-layout">
        <nav className="edge-ops-nav" role="tablist" aria-label="Operations modules">
          {operationsViews.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              id={`edge-ops-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={activeView === id}
              aria-controls={`edge-ops-panel-${id}`}
              className={activeView === id ? 'active' : ''}
              onClick={() => setActiveView(id)}
              onKeyDown={(event) => handleOperationsKeyDown(event, id)}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
        <div
          id={`edge-ops-panel-${activeView}`}
          className="edge-ops-content"
          role="tabpanel"
          aria-labelledby={`edge-ops-tab-${activeView}`}
        >
          <Suspense fallback={<LazyPanelFallback label="Operations module" />}>
            {activeView === 'overview' && <TradingOverview />}
            {activeView === 'scanners' && <ScannerWorkbench />}
            {activeView === 'advisor' && <AdvisorHealth />}
            {activeView === 'experience' && <ExperienceDashboard />}
            {activeView === 'protection' && <OperationsProtectionDashboard />}
            {activeView === 'pnl' && <PnLTracking />}
            {activeView === 'markets' && <MarketCoverage />}
            {activeView === 'portfolio' && <PortfolioAnalytics />}
            {activeView === 'settings' && <SettingsDashboard />}
            {activeView === 'tutorials' && (
              <TutorialsDashboard onOpenModule={(view: TutorialModuleView) => setActiveView(view)} />
            )}
          </Suspense>
        </div>
      </div>
    </section>
  );
}
