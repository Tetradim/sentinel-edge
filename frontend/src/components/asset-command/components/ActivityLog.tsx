import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { eventFilterOptions, eventSymbols } from '../data';
import type { EventFilter, EventLine } from '../types';
import { PanelTitle } from './shared';

export function ActivityLog({
  selectedSymbol,
  events,
  visibleEvents,
  eventFilter,
  eventFilterCounts,
  setEventFilter,
  selectSymbol,
  compact = false,
  collapsible = false,
  collapsed = compact,
  onToggleCollapsed,
}: {
  selectedSymbol: string;
  events: EventLine[];
  visibleEvents: EventLine[];
  eventFilter: EventFilter;
  eventFilterCounts: Record<EventFilter, number>;
  setEventFilter: (filter: EventFilter) => void;
  selectSymbol: (symbol: string) => void;
  compact?: boolean;
  collapsible?: boolean;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}) {
  const railCollapsed = collapsible ? collapsed : compact;

  return (
    <aside
      className={`edge-glass edge-events ${railCollapsed ? 'edge-events-compact' : ''} ${
        collapsible ? 'edge-events-collapsible' : ''
      }`}
      aria-label="Activity log"
    >
      {collapsible && (
        <button
          type="button"
          className="edge-event-rail-toggle"
          aria-expanded={!railCollapsed}
          onClick={onToggleCollapsed}
        >
          {railCollapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          <span>{railCollapsed ? 'Expand activity' : 'Collapse activity'}</span>
        </button>
      )}

      {railCollapsed ? (
        <>
          <div className="edge-event-rail-summary" aria-label={`${visibleEvents.length} visible events`}>
            <span>Activity</span>
            <strong>{visibleEvents.length}</strong>
            <small>{events.length}</small>
          </div>
        </>
      ) : (
        <>
          <PanelTitle eyebrow="Event log" title="Activity" chip={`${visibleEvents.length} of ${events.length} live`} />
          <div className="edge-event-filters" aria-label="Activity log filters">
            {eventFilterOptions.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={eventFilter === option.id}
                className={eventFilter === option.id ? 'active' : ''}
                onClick={() => setEventFilter(option.id)}
              >
                <span>{option.id === 'selected' ? `${option.label} ${selectedSymbol}` : option.label}</span>
                <b>{eventFilterCounts[option.id]}</b>
              </button>
            ))}
          </div>
          <div className="edge-event-list">
            {visibleEvents.length === 0 ? (
              <div className="edge-event-empty">
                <span>No activity for this filter</span>
                <button type="button" onClick={() => setEventFilter('all')}>Show all activity</button>
              </div>
            ) : visibleEvents.map((event, index) => {
              const canFocusEvent = eventSymbols.has(event.symbol);
              return (
                <button
                  key={event.id}
                  type="button"
                  disabled={!canFocusEvent}
                  aria-label={canFocusEvent ? `Focus ${event.symbol} activity` : `${event.symbol} system activity`}
                  className={`edge-event ${index === 0 ? 'active' : ''} ${canFocusEvent ? 'focusable' : 'system'}`}
                  onClick={() => selectSymbol(event.symbol)}
                >
                  <div><strong>{event.title}</strong>{event.detail}</div>
                  <div><span className="edge-gold">{event.symbol}</span><br /><span>{event.time}</span></div>
                </button>
              );
            })}
          </div>
        </>
      )}
    </aside>
  );
}
