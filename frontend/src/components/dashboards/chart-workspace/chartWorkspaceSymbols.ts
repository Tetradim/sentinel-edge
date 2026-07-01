import { DEFAULT_PREFERENCES_STATE } from './chartWorkspaceConstants';

export function normalizeChartWorkspaceSymbol(value: unknown) {
  if (typeof value !== 'string') return DEFAULT_PREFERENCES_STATE.activeSymbol;
  const symbol = value.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,10}$/.test(symbol) ? symbol : DEFAULT_PREFERENCES_STATE.activeSymbol;
}
