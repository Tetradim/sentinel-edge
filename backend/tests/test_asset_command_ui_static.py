"""Static regressions for the Asset Command UI integration."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ASSET_COMMAND = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.tsx"
ASSET_COMMAND_CSS = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.css"
ASSET_COMMAND_ACTIVITY_CSS = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.activity.css"
ASSET_COMMAND_PICKER_CSS = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.picker.css"
ASSET_COMMAND_PANELS_CSS = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.panels.css"
ASSET_COMMAND_TYPES = ROOT / "frontend" / "src" / "components" / "asset-command" / "types.ts"
ASSET_COMMAND_DATA = ROOT / "frontend" / "src" / "components" / "asset-command" / "data.ts"
ASSET_COMMAND_STATE_HOOK = ROOT / "frontend" / "src" / "components" / "asset-command" / "hooks" / "useAssetCommandState.ts"
ASSET_COMMAND_ACTIVITY = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "ActivityLog.tsx"
ASSET_COMMAND_PICKER = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "TickerPicker.tsx"
ASSET_COMMAND_COMMAND_MODE = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "CommandModePanel.tsx"
ASSET_COMMAND_MODE_TABS = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "ModeTabs.tsx"
ASSET_COMMAND_OPERATIONS = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "OperationsPanel.tsx"
ASSET_COMMAND_SHARED = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "shared.tsx"
ASSET_COMMAND_NAVIGATION_HOOK = ROOT / "frontend" / "src" / "components" / "asset-command" / "hooks" / "useAssetCommandNavigation.ts"
ASSET_COMMAND_RUNTIME_HOOK = ROOT / "frontend" / "src" / "components" / "asset-command" / "hooks" / "useRuntimeStatus.ts"
MARKET_COVERAGE = ROOT / "frontend" / "src" / "components" / "dashboards" / "MarketCoverage.tsx"


def read_existing(*paths: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def read_asset_command_styles() -> str:
    return read_existing(ASSET_COMMAND_CSS, ASSET_COMMAND_ACTIVITY_CSS, ASSET_COMMAND_PICKER_CSS, ASSET_COMMAND_PANELS_CSS)


class AssetCommandUiStaticTests(unittest.TestCase):
    def test_pulse_startup_choice_is_available(self):
        text = ASSET_COMMAND.read_text(encoding="utf-8")

        self.assertIn("PulseStartupPanel", text)
        self.assertIn("Connect to Pulse", text)
        self.assertIn("Try Connecting", text)
        self.assertIn("Standalone Mode", text)
        self.assertIn("setShowPulseStartup(false)", text)

    def test_scheduler_control_is_disabled_when_backend_is_not_connected(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_SHARED, ASSET_COMMAND_RUNTIME_HOOK)

        self.assertIn("disabled={runtime.loading || !runtime.connected}", text)
        self.assertIn("aria-disabled={runtime.loading || !runtime.connected}", text)
        self.assertIn("if (runtime.loading || !runtime.connected) return", text)

    def test_runtime_badges_surface_scheduler_control_failures(self):
        text = read_existing(ASSET_COMMAND_TYPES, ASSET_COMMAND_SHARED, ASSET_COMMAND_RUNTIME_HOOK)

        self.assertIn("error?: string", text)
        self.assertIn("error: undefined", text)
        self.assertIn("error: 'Runtime status unavailable'", text)
        self.assertIn("error: 'Scheduler control failed'", text)
        self.assertIn("runtime.error &&", text)
        self.assertIn("{runtime.error}", text)

    def test_monitor_panel_uses_live_runtime_observability(self):
        monitor_panel = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "MonitorPanel.tsx"
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_RUNTIME_HOOK, monitor_panel)

        self.assertIn("runtime={runtime}", text)
        self.assertIn("runtime: RuntimeState", text)
        self.assertIn("const runtimeSignalRows", text)
        self.assertIn("Runtime signals", text)
        self.assertIn("Edge API", text)
        self.assertIn("Scheduler", text)
        self.assertIn("Pulse bridge", text)
        self.assertIn("Kill switch", text)
        self.assertIn("runtime.connected", text)
        self.assertIn("runtime.pulseAvailable", text)
        self.assertIn("runtime.killSwitchActive", text)
        self.assertIn("runtime.schedulerPaused", text)

    def test_market_coverage_only_suppresses_vite_html_fallback(self):
        text = MARKET_COVERAGE.read_text(encoding="utf-8")

        self.assertIn("isFrontendFallbackApiError", text)
        self.assertIn("Expected JSON response", text)
        self.assertIn("setMarketStatusMessage", text)
        self.assertIn("console.error('Failed to load markets:', error)", text)
        self.assertNotIn("if (!(error instanceof ApiError)) {\n        console.error('Failed to load markets:', error)", text)

    def test_mode_and_operations_controls_have_tab_semantics(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_MODE_TABS, ASSET_COMMAND_OPERATIONS, ASSET_COMMAND_NAVIGATION_HOOK)

        self.assertIn('role="tab"', text)
        self.assertIn("aria-selected=", text)
        self.assertIn("aria-controls=", text)
        self.assertIn('role="tabpanel"', text)
        self.assertIn("onKeyDown", text)

    def test_reel_motion_honors_reduced_motion(self):
        css = read_asset_command_styles()

        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("animation: none", css)

    def test_metric_reels_report_rendered_count_and_scroll_slots(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_COMMAND_MODE)
        css = read_asset_command_styles()

        self.assertIn("availableCount={selected.metrics.length}", text)
        self.assertIn("availableCount: number", text)
        self.assertIn("{reels.length} of {availableCount} visible", text)
        self.assertNotIn("{visibleReels} visible", text)
        self.assertIn("overflow-x: auto", css)
        self.assertIn("grid-auto-flow: column", css)
        self.assertIn("grid-auto-columns", css)

    def test_activity_log_can_be_filtered_without_losing_total_context(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)
        css = read_asset_command_styles()

        self.assertIn("type EventFilter = 'all' | 'selected' | 'system'", text)
        self.assertIn("const eventFilterOptions", text)
        self.assertIn("const [eventFilter, setEventFilter] = useState<EventFilter>('all')", text)
        self.assertIn("const visibleEvents = events.filter", text)
        self.assertIn('aria-label="Activity log filters"', text)
        self.assertIn("aria-pressed={eventFilter === option.id}", text)
        self.assertIn("setEventFilter(option.id)", text)
        self.assertIn("`${visibleEvents.length} of ${events.length} live`", text)
        self.assertIn("visibleEvents.length === 0", text)
        self.assertIn(".edge-event-filters", css)
        self.assertIn(".edge-event-empty", css)

    def test_activity_log_filter_buttons_expose_event_counts(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)
        css = read_asset_command_styles()

        self.assertIn("const eventFilterCounts: Record<EventFilter, number>", text)
        self.assertIn("selected: events.filter((event) => event.symbol === selected.symbol).length", text)
        self.assertIn("system: events.filter((event) => event.symbol === 'EDGE' || event.symbol === 'PROTECT').length", text)
        self.assertIn("option.id === 'selected' ? `${option.label} ${selectedSymbol}` : option.label", text)
        self.assertIn("{eventFilterCounts[option.id]}", text)
        self.assertIn(".edge-event-filters button b", css)

    def test_activity_log_empty_state_can_return_to_all_events(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)
        css = read_asset_command_styles()

        self.assertIn("No activity for this filter", text)
        self.assertIn("Show all activity", text)
        self.assertIn("onClick={() => setEventFilter('all')}", text)
        self.assertIn("edge-event-empty button", css)

    def test_activity_log_events_can_focus_tracked_symbols(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)
        css = read_asset_command_styles()

        self.assertIn("const eventSymbols = new Set(tickers.map((ticker) => ticker.symbol))", text)
        self.assertIn("const canFocusEvent = eventSymbols.has(event.symbol)", text)
        self.assertIn("disabled={!canFocusEvent}", text)
        self.assertIn("onClick={() => selectSymbol(event.symbol)}", text)
        self.assertIn("canFocusEvent ? `Focus ${event.symbol} activity`", text)
        self.assertIn("canFocusEvent ? 'focusable' : 'system'", text)
        self.assertIn(".edge-event.focusable", css)
        self.assertIn(".edge-event.system", css)

    def test_reselecting_current_symbol_does_not_add_noise_event(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)

        self.assertIn("const selectSymbol = (symbol: string) => {", text)
        self.assertIn("if (symbol === selectedSymbol) return", text)
        self.assertIn("addEvent(symbol, 'Ticker selected'", text)

    def test_ticker_picker_supports_keyboard_navigation(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_PICKER)
        css = read_asset_command_styles()

        self.assertIn("const handlePickerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {", text)
        self.assertIn("event.key === 'ArrowDown'", text)
        self.assertIn("event.key === 'ArrowUp'", text)
        self.assertIn("event.key === 'Home'", text)
        self.assertIn("event.key === 'End'", text)
        self.assertIn("selectSymbol(tickers[0].symbol)", text)
        self.assertIn("selectSymbol(tickers[tickers.length - 1].symbol)", text)
        self.assertIn("onKeyDown={handlePickerKeyDown}", text)
        self.assertIn(".edge-ticker-picker:focus-visible", css)

    def test_ticker_picker_keyboard_controls_are_discoverable(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_PICKER)

        self.assertIn('chip="wheel / keys"', text)
        self.assertIn('aria-label="Ticker picker: use mouse wheel or arrow keys"', text)

    def test_ticker_picker_exposes_selected_item_to_assistive_tech(self):
        text = read_existing(ASSET_COMMAND, ASSET_COMMAND_TYPES, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_PICKER)

        self.assertIn("aria-current={active ? 'true' : undefined}", text)
        self.assertIn("aria-label={active ? `${ticker.symbol} selected in ticker picker` : `Select ${ticker.symbol} in ticker picker`}", text)

    def test_asset_command_refactor_readers_tolerate_future_modules(self):
        text = read_existing(
            ASSET_COMMAND,
            ASSET_COMMAND_TYPES,
            ASSET_COMMAND_DATA,
            ASSET_COMMAND_STATE_HOOK,
            ASSET_COMMAND_ACTIVITY,
            ASSET_COMMAND_PICKER,
            ASSET_COMMAND_COMMAND_MODE,
            ASSET_COMMAND_MODE_TABS,
            ASSET_COMMAND_OPERATIONS,
            ASSET_COMMAND_SHARED,
            ASSET_COMMAND_NAVIGATION_HOOK,
            ASSET_COMMAND_RUNTIME_HOOK,
        )

        self.assertIn("tickers", text)
        self.assertNotIn(str(ASSET_COMMAND_DATA), text)


if __name__ == "__main__":
    unittest.main()
