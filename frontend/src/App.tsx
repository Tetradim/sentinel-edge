import SentinelEdgeUnifiedShell from './components/sentinel-edge/SentinelEdgeUnifiedShell';
import { AutomationOperationsDrawer } from './components/dashboards/AutomationOperationsDrawer';

export default function App() {
  return (
    <>
      <SentinelEdgeUnifiedShell />
      <AutomationOperationsDrawer />
    </>
  );
}
