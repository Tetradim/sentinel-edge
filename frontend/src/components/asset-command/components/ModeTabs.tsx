import type React from 'react';
import { modeLabel, modes } from '../data';
import type { Mode } from '../types';

export function ModeTabs({
  mode,
  setMode,
  handleModeKeyDown,
}: {
  mode: Mode;
  setMode: (mode: Mode) => void;
  handleModeKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>, currentMode: Mode) => void;
}) {
  return (
    <div className="edge-mode-switch" role="tablist" aria-label="Modes">
      {modes.map((item) => (
        <button
          key={item}
          id={`edge-mode-tab-${item}`}
          type="button"
          role="tab"
          aria-selected={mode === item}
          aria-controls={`edge-mode-panel-${item}`}
          className={mode === item ? 'active' : ''}
          onClick={() => setMode(item)}
          onKeyDown={(event) => handleModeKeyDown(event, item)}
        >
          {modeLabel(item)}
        </button>
      ))}
    </div>
  );
}
