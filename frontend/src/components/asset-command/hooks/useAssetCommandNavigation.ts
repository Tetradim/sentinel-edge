import { useEffect, useState } from 'react';
import type React from 'react';
import { modes, operationsViews } from '../data';
import type { Mode, OperationsView } from '../types';

const parseHashState = (): { mode: Mode; operationsView: OperationsView } => {
  if (typeof window === 'undefined') return { mode: 'command', operationsView: 'overview' };
  const raw = window.location.hash.replace('#', '');
  const [modePart, viewPart] = raw.split(':');
  const mode = normalizeMode(modePart);
  const operationsView = operationsViews.some((item) => item.id === viewPart) ? (viewPart as OperationsView) : 'overview';
  return { mode, operationsView };
};

const normalizeMode = (modePart: string): Mode => {
  if (modePart === 'monitor' || modePart === 'market-map') return 'charting';
  return modes.includes(modePart as Mode) ? (modePart as Mode) : 'command';
};

const writeHashState = (mode: Mode, operationsView = 'overview') => {
  if (typeof window === 'undefined') return;
  const hash = mode === 'operations' ? `#operations:${operationsView}` : `#${mode}`;
  if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
};

export function useAssetCommandNavigation() {
  const initialHashState = parseHashState();
  const [mode, setModeState] = useState<Mode>(initialHashState.mode);
  const [operationsView, setOperationsViewState] = useState<OperationsView>(initialHashState.operationsView);

  useEffect(() => {
    const onHashChange = () => {
      const next = parseHashState();
      setModeState(next.mode);
      setOperationsViewState(next.operationsView);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const setMode = (nextMode: Mode) => {
    setModeState(nextMode);
    writeHashState(nextMode, operationsView);
  };

  const setOperationsView = (nextView: OperationsView) => {
    setOperationsViewState(nextView);
    writeHashState('operations', nextView);
  };

  const handleModeKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, currentMode: Mode) => {
    const currentIndex = modes.indexOf(currentMode);
    const nextMode =
      event.key === 'ArrowRight' ? modes[(currentIndex + 1) % modes.length] :
      event.key === 'ArrowLeft' ? modes[(currentIndex - 1 + modes.length) % modes.length] :
      event.key === 'Home' ? modes[0] :
      event.key === 'End' ? modes[modes.length - 1] :
      null;
    if (!nextMode) return;
    event.preventDefault();
    setMode(nextMode);
    window.requestAnimationFrame(() => document.getElementById(`edge-mode-tab-${nextMode}`)?.focus());
  };

  const handleOperationsKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, currentView: OperationsView) => {
    const viewIds = operationsViews.map((item) => item.id);
    const currentIndex = viewIds.indexOf(currentView);
    const nextView =
      event.key === 'ArrowDown' || event.key === 'ArrowRight' ? viewIds[(currentIndex + 1) % viewIds.length] :
      event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? viewIds[(currentIndex - 1 + viewIds.length) % viewIds.length] :
      event.key === 'Home' ? viewIds[0] :
      event.key === 'End' ? viewIds[viewIds.length - 1] :
      null;
    if (!nextView) return;
    event.preventDefault();
    setOperationsView(nextView);
    window.requestAnimationFrame(() => document.getElementById(`edge-ops-tab-${nextView}`)?.focus());
  };

  return { mode, operationsView, setMode, setOperationsView, handleModeKeyDown, handleOperationsKeyDown };
}
