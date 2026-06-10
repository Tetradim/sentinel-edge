import type React from 'react';
import { AdvisorHealth } from '../../dashboards/AdvisorHealth';
import { ExperienceDashboard } from '../../dashboards/ExperienceDashboard';
import { MarketCoverage } from '../../dashboards/MarketCoverage';
import { PnLTracking } from '../../dashboards/PnLTracking';
import { PortfolioAnalytics } from '../../dashboards/PortfolioAnalytics';
import { ProtectionDashboard as OperationsProtectionDashboard } from '../../dashboards/ProtectionDashboard';
import { SettingsDashboard } from '../../dashboards/SettingsDashboard';
import { TradingOverview } from '../../dashboards/TradingOverview';
import { TutorialsDashboard, type TutorialModuleView } from '../../tutorials';
import { operationsViews } from '../data';
import type { OperationsView } from '../types';

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
          {activeView === 'overview' && <TradingOverview />}
          {activeView === 'advisor' && <AdvisorHealth />}
          {activeView === 'experience' && <ExperienceDashboard />}
          {activeView === 'protection' && <OperationsProtectionDashboard />}
          {activeView === 'pnl' && <PnLTracking />}
          {activeView === 'markets' && <MarketCoverage />}
          {activeView === 'portfolio' && <PortfolioAnalytics />}
          {activeView === 'settings' && <SettingsDashboard />}
          {activeView === 'tutorials' && <TutorialsDashboard onOpenModule={(view: TutorialModuleView) => setActiveView(view)} />}
        </div>
      </div>
    </section>
  );
}
