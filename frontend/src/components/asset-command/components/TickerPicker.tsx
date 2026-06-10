import type React from 'react';
import type { Ticker } from '../types';
import { PanelTitle } from './shared';

export function TickerPicker({
  selectedSymbol,
  pickerItems,
  onWheel,
  onKeyDown,
  selectSymbol,
}: {
  selectedSymbol: string;
  pickerItems: Ticker[];
  onWheel: (event: React.WheelEvent<HTMLDivElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => void;
  selectSymbol: (symbol: string) => void;
}) {
  return (
    <section className="edge-glass edge-picker-panel" aria-label="Kinetic watchlist">
      <PanelTitle eyebrow="Kinetic watchlist" title="Picker" chip="wheel / keys" />
      <div
        className="edge-ticker-picker"
        tabIndex={0}
        aria-label="Ticker picker: use mouse wheel or arrow keys"
        onWheel={onWheel}
        onKeyDown={onKeyDown}
      >
        {pickerItems.map((ticker, index) => {
          const active = ticker.symbol === selectedSymbol;
          return (
            <button
              type="button"
              key={`${ticker.symbol}-${index}`}
              className={`edge-picker-item ${active ? 'active' : ''}`}
              style={{ opacity: active ? 1 : Math.max(0.16, 0.75 - Math.abs(index - 3) * 0.18) }}
              aria-current={active ? 'true' : undefined}
              aria-label={active ? `${ticker.symbol} selected in ticker picker` : `Select ${ticker.symbol} in ticker picker`}
              onClick={() => selectSymbol(ticker.symbol)}
            >
              <b>{ticker.symbol}</b>
              {ticker.watchers[0] ? <em>{ticker.watchers[0].plugin}</em> : <span>{ticker.status}</span>}
              <span>{ticker.change}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
