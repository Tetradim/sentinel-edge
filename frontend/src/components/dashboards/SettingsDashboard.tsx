/**
 * Settings Dashboard
 * Configuration management for Edge
 */
import React, { useEffect, useState } from 'react';
import { Settings, Save, RefreshCw, Database, Zap, Shield, Globe, AlertCircle, TrendingUp, ShieldAlert, BarChart3, CheckCircle, XCircle, FlaskConical, Bell } from 'lucide-react';

interface ConfigSection {
  name: string;
  key: string;
  fields: {
    key: string;
    label: string;
    type: 'text' | 'number' | 'boolean' | 'select';
    value: any;
    options?: string[];
    description?: string;
  }[];
}

interface ProviderInfo {
  key: string;
  label: string;
  quote: boolean;
  ohlcv: boolean;
  requires_key: boolean;
  configured: boolean;
  enabled: boolean;
  intraday?: boolean;
  eod?: boolean;
  free_tier: string;
  notes: string;
}

interface AutomationSettings {
  global_enabled: boolean;
  mode: 'recommend_only' | 'paper' | 'live';
  default_ticker_enabled: boolean;
  per_ticker_enabled: Record<string, boolean>;
  min_confidence: number;
  cooldown_seconds: number;
  quiet_when_pulse_absent: boolean;
}

interface PulseHandoffContract {
  contract_version: string;
  endpoint_env: string;
  recommended_endpoint?: string;
  transport_headers?: Record<string, string>;
  response_contract?: Record<string, PulseHandoffContractResponse>;
  feedback_semantics?: Record<string, PulseFeedbackSemantic>;
}

interface PulseHandoffContractResponse {
  accepted?: boolean;
  status?: string;
  reason?: string;
  handoff_id?: string;
  message?: string;
  error?: string;
}

interface PulseFeedbackSemantic {
  edge_sent?: boolean;
  pulse_side_effect?: string;
  expected_fields?: string[];
}

interface SimulationLabExperiment {
  id?: string;
  label?: string;
  capability?: string;
  runnable?: boolean;
  status?: string;
  state?: string;
  http_method?: string;
  endpoint_path?: string;
  result_schema_version?: string;
}

interface SimulationLabStatus {
  schema_version?: string;
  enabled?: boolean;
  default_hidden?: boolean;
  env_flag?: string;
  experiments?: SimulationLabExperiment[];
}

interface NotificationChannel {
  id: string;
  label: string;
  configured: boolean;
  status: string;
  required_env?: string[];
  configured_env?: string[];
  missing_env?: string[];
  delivery_path?: string;
  purpose?: string;
  confirmation_path?: string;
}

interface NotificationConfirmationPreview {
  schema_version?: string;
  endpoint?: string;
  send_side_effect?: string;
  secret_values?: string;
}

interface NotificationConfirmationAction {
  id: string;
  label?: string;
  description?: string;
  risk?: string;
  requires_confirmation?: boolean;
  default_channels?: string[];
  paper_live_semantics?: string;
  preview_contract?: string;
  expires_in_seconds?: number;
}

interface NotificationsStatus {
  schema_version?: string;
  mode?: string;
  secret_values?: string;
  channels?: NotificationChannel[];
  confirmation_preview?: NotificationConfirmationPreview;
  confirmation_actions?: NotificationConfirmationAction[];
  summary?: {
    configured_count?: number;
    total_count?: number;
    configured_channels?: string[];
    missing_channels?: string[];
  };
}

const MARKET_DATA_OPTIONS = [
  'yfinance',
  'finnhub',
  'polygon',
  'alpha_vantage',
  'twelve_data',
];

const PULSE_RESPONSE_CONTRACT_KEYS = ['accepted_response', 'rejected_response', 'failed_response'];

const isSecretField = (key: string) => {
  const normalized = key.toLowerCase();
  return normalized.includes('api_key') || normalized.includes('secret') || normalized.includes('token');
};

const CONFIG_SECTIONS: ConfigSection[] = [
  {
    name: 'Data Source',
    key: 'data',
    fields: [
      { key: 'source', label: 'Primary Data Source', type: 'select', value: 'yfinance', options: MARKET_DATA_OPTIONS, description: 'Preferred intraday market-data source. Backend fallback order is controlled by MARKET_DATA_PROVIDER_ORDER.' },
      { key: 'fallback_order', label: 'Fallback Order', type: 'text', value: 'yfinance,finnhub,polygon,alpha_vantage,twelve_data', description: 'Comma-separated intraday provider order for backend env MARKET_DATA_PROVIDER_ORDER. EOD-only sources are ignored for live ticks.' },
    ]
  },
  {
    name: 'Risk Management',
    key: 'risk',
    fields: [
      { key: 'max_position_size', label: 'Max Position Size (%)', type: 'number', value: 10, description: 'Maximum position size as % of portfolio' },
      { key: 'stop_loss_pct', label: 'Stop Loss (%)', type: 'number', value: 5, description: 'Default stop loss percentage' },
      { key: 'take_profit_pct', label: 'Take Profit (%)', type: 'number', value: 15, description: 'Default take profit percentage' },
      { key: 'max_consecutive_losses', label: 'Max Consecutive Losses', type: 'number', value: 3, description: 'Stop trading after this many losses' },
    ]
  },
  {
    name: 'Greek Analysis',
    key: 'greeks',
    fields: [
      { key: 'delta', label: 'Delta Analysis', type: 'boolean', value: false, description: 'Direction & Probability - measures sensitivity to price movements' },
      { key: 'theta', label: 'Theta Analysis', type: 'boolean', value: false, description: 'Time Decay - measures daily value erosion' },
      { key: 'vega', label: 'Vega Analysis', type: 'boolean', value: false, description: 'Volatility Sensitivity - measures IV impact' },
      { key: 'gamma', label: 'Gamma Analysis', type: 'boolean', value: false, description: 'Delta Acceleration - measures rate of delta change' },
      { key: 'rho', label: 'Rho Analysis', type: 'boolean', value: false, description: 'Interest Rate Sensitivity - bond yield impact' },
      { key: 'gex', label: 'GEX (Gamma Exposure)', type: 'boolean', value: false, description: 'Aggregate market maker gamma' },
      { key: 'vex', label: 'VEX (Vega Exposure)', type: 'boolean', value: false, description: 'Aggregate volatility exposure' },
    ]
  },
  {
    name: 'Advanced Options',
    key: 'advanced',
    fields: [
      { key: 'iv_tracking', label: 'IV Percentile Tracking', type: 'boolean', value: false, description: 'Track IV relative to historical percentiles' },
      { key: 'spike_protection', label: 'Volatility Spike Protection', type: 'boolean', value: true, description: 'Detect and warn on IV spikes >50% above normal' },
      { key: 'short_interest', label: 'Short Interest Analysis', type: 'boolean', value: false, description: 'Days to cover & squeeze potential analysis' },
    ]
  },
  {
    name: 'Chart Options',
    key: 'charts',
    fields: [
      { key: 'chart_type', label: 'Default Chart Type', type: 'select', value: 'line', options: ['area', 'bar', 'line', 'candlestick', 'heatmap'], description: 'Default visualization type' },
      { key: 'dashboard_layout', label: 'Dashboard Layout', type: 'select', value: 'grid', options: ['grid', 'list', 'heatmap'], description: 'Card layout arrangement' },
    ]
  },
  {
    name: 'Rate Limiting',
    key: 'rate_limit',
    fields: [
      { key: 'requests_per_second', label: 'Requests/Second', type: 'number', value: 10, description: 'Max API requests per second' },
      { key: 'max_retries', label: 'Max Retries', type: 'number', value: 3, description: 'Max retry attempts on failure' },
      { key: 'base_delay', label: 'Base Delay (s)', type: 'number', value: 1, description: 'Base delay for exponential backoff' },
    ]
  }
];

export function SettingsDashboard() {
  const [sections, setSections] = useState(CONFIG_SECTIONS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [providerOrder, setProviderOrder] = useState<string[]>([]);
  const [automation, setAutomation] = useState<AutomationSettings | null>(null);
  const [pulseHandoffContract, setPulseHandoffContract] = useState<PulseHandoffContract | null>(null);
  const [simulationLabStatus, setSimulationLabStatus] = useState<SimulationLabStatus | null>(null);
  const [notificationsStatus, setNotificationsStatus] = useState<NotificationsStatus | null>(null);
  const [tickers, setTickers] = useState<string[]>([]);
  const [settingsError, setSettingsError] = useState('');
  const [runtimeSettingsError, setRuntimeSettingsError] = useState('');

  // Load saved config from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('edge_config');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        const sanitized = Object.fromEntries(
          Object.entries(parsed).map(([sectionKey, values]) => [
            sectionKey,
            Object.fromEntries(
              Object.entries((values as Record<string, any>) || {}).filter(([fieldKey]) => !isSecretField(fieldKey))
            ),
          ])
        );
        if (JSON.stringify(sanitized) !== saved) {
          localStorage.setItem('edge_config', JSON.stringify(sanitized));
        }
        // Update sections with saved values
        setSections(sections.map(section => ({
          ...section,
          fields: section.fields.map(field => ({
            ...field,
            value: sanitized[section.key]?.[field.key] ?? field.value
          }))
        })));
      } catch (error) {
        console.error('Failed to load saved config', error);
        localStorage.removeItem('edge_config');
        setSettingsError('Saved settings could not be loaded; defaults are shown.');
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadRuntimeSettings = async () => {
      try {
        const [
          providerResponse,
          automationResponse,
          tickersResponse,
          pulseContractResponse,
          simulationLabResponse,
          notificationsResponse,
        ] = await Promise.allSettled([
          fetch('/api/market-data/providers'),
          fetch('/api/automation'),
          fetch('/api/tickers'),
          fetch('/api/pulse/handoff/schema'),
          fetch('/api/simulation-lab/status'),
          fetch('/api/notifications/status'),
        ]);
        if (cancelled) return;

        const failedRuntimeLoads = [
          providerResponse.status === 'rejected' || !providerResponse.value.ok,
          automationResponse.status === 'rejected' || !automationResponse.value.ok,
          tickersResponse.status === 'rejected' || !tickersResponse.value.ok,
          pulseContractResponse.status === 'rejected' || !pulseContractResponse.value.ok,
          simulationLabResponse.status === 'rejected' || !simulationLabResponse.value.ok,
          notificationsResponse.status === 'rejected' || !notificationsResponse.value.ok,
        ].filter(Boolean);
        setRuntimeSettingsError(failedRuntimeLoads.length > 0 ? 'Settings metadata failed to refresh. Showing latest available data.' : '');

        if (providerResponse.status === 'fulfilled' && providerResponse.value.ok) {
          const data = await providerResponse.value.json();
          setProviders(data.providers || []);
          setProviderOrder(data.fallback_order || []);
        }
        if (automationResponse.status === 'fulfilled' && automationResponse.value.ok) {
          const data = await automationResponse.value.json();
          setAutomation(data.settings || null);
        }
        if (tickersResponse.status === 'fulfilled' && tickersResponse.value.ok) {
          const data = await tickersResponse.value.json();
          setTickers((data.tickers || []).map((ticker: any) => ticker.symbol).filter(Boolean));
        }
        if (pulseContractResponse.status === 'fulfilled' && pulseContractResponse.value.ok) {
          const data = await pulseContractResponse.value.json();
          setPulseHandoffContract(data);
        }
        if (simulationLabResponse.status === 'fulfilled' && simulationLabResponse.value.ok) {
          const data = await simulationLabResponse.value.json();
          setSimulationLabStatus(data);
        }
        if (notificationsResponse.status === 'fulfilled' && notificationsResponse.value.ok) {
          const data = await notificationsResponse.value.json();
          setNotificationsStatus(data);
        }
      } catch (e) {
        if (!cancelled) {
          setRuntimeSettingsError('Settings metadata failed to refresh. Showing latest available data.');
        }
      }
    };
    loadRuntimeSettings();
    const id = window.setInterval(loadRuntimeSettings, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const handleFieldChange = (sectionKey: string, fieldKey: string, value: any) => {
    setSections(sections.map(section => {
      if (section.key !== sectionKey) return section;
      return {
        ...section,
        fields: section.fields.map(field => 
          field.key === fieldKey ? { ...field, value } : field
        )
      };
    }));
    setSaved(false);
  };

  const saveAutomation = async (patch: Partial<AutomationSettings>) => {
    const previous = automation;
    const next = { ...(automation || {} as AutomationSettings), ...patch } as AutomationSettings;
    setSettingsError('');
    setAutomation(next);
    try {
      const response = await fetch('/api/automation', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
      if (!response.ok) throw new Error('Automation settings failed to save');
      const data = await response.json();
      setAutomation(data.settings || next);
    } catch (error) {
      setAutomation(previous);
      setSettingsError(error instanceof Error ? error.message : 'Automation settings failed to save');
    }
  };

  const saveTickerAutomation = async (symbol: string, enabled: boolean) => {
    const previous = automation;
    const perTicker = { ...(automation?.per_ticker_enabled || {}), [symbol]: enabled };
    setSettingsError('');
    setAutomation((prev) => prev ? { ...prev, per_ticker_enabled: perTicker } : prev);
    try {
      const response = await fetch(`/api/automation/tickers/${symbol}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) throw new Error(`Failed to save ${symbol} handoff setting`);
      const data = await response.json();
      setAutomation(data.settings || null);
    } catch (error) {
      setAutomation(previous);
      setSettingsError(error instanceof Error ? error.message : `Failed to save ${symbol} handoff setting`);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSettingsError('');
    
    // Save to localStorage
    const config: Record<string, Record<string, any>> = {};
    sections.forEach(section => {
      config[section.key] = {};
      section.fields.forEach(field => {
        if (isSecretField(field.key)) return;
        config[section.key][field.key] = field.value;
      });
    });
    
    localStorage.setItem('edge_config', JSON.stringify(config));
    
    // Validate against backend schema when available; browser storage remains the source.
    try {
      const response = await fetch('/api/config/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (!response.ok) throw new Error('Backend config validation failed');
      const validation = await response.json();
      if (validation.valid === false) throw new Error('Backend config validation reported issues');
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : 'Backend config validation unavailable');
    }
    
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setSections(CONFIG_SECTIONS);
    localStorage.removeItem('edge_config');
    setSaved(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gray-800">
            <Settings className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Settings</h2>
            <p className="text-sm text-gray-400">Configure Edge behavior</p>
          </div>
        </div>
        
        <div className="flex gap-3">
          <button
            onClick={handleReset}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              saved 
                ? 'bg-emerald-500 text-white' 
                : saving 
                  ? 'bg-gray-600 text-gray-400'
                  : 'bg-emerald-500 hover:bg-emerald-600 text-white'
            }`}
          >
            {saving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : saved ? (
              <Save className="w-4 h-4" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {saved ? 'Saved!' : 'Save Settings'}
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-300">
          <p className="font-medium">Settings are stored locally</p>
          <p className="text-blue-400/70">Your non-secret configuration is saved to your browser and persists across sessions. API keys are not saved here; configure them as backend environment variables.</p>
        </div>
      </div>

      {settingsError && (
        <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {settingsError}
        </div>
      )}

      {runtimeSettingsError && (
        <div role="alert" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
          {runtimeSettingsError}
        </div>
      )}

      {/* Autonomous Pulse Handoff */}
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-red-400" />
          Autonomous Pulse Handoff
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Edge can recommend continuously, but Pulse commands are sent only when the global switch and each ticker switch allow it. Turning global handoff off preserves ticker choices.
        </p>

        {!automation ? (
          <div className="text-sm text-gray-500">Automation settings unavailable until the backend is running.</div>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                <div className="text-sm font-medium text-gray-300">Global handoff</div>
                <button
                  onClick={() => saveAutomation({ global_enabled: !automation.global_enabled })}
                  className={`mt-3 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors ${automation.global_enabled ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
                >
                  {automation.global_enabled ? 'Enabled' : 'Disabled'}
                </button>
              </div>

              <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                <label className="text-sm font-medium text-gray-300">Mode</label>
                <select
                  value={automation.mode}
                  onChange={(event) => saveAutomation({ mode: event.target.value as AutomationSettings['mode'] })}
                  className="mt-3 w-full rounded-lg border border-gray-600 bg-gray-950 px-3 py-2 text-sm text-white"
                >
                  <option value="recommend_only">Recommend only</option>
                  <option value="paper">Paper</option>
                  <option value="live">Live</option>
                </select>
              </div>

              <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                <label className="text-sm font-medium text-gray-300">Minimum confidence</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  value={automation.min_confidence}
                  onChange={(event) => saveAutomation({ min_confidence: parseFloat(event.target.value) || 0 })}
                  className="mt-3 w-full rounded-lg border border-gray-600 bg-gray-950 px-3 py-2 text-sm text-white"
                />
              </div>

              <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                <label className="text-sm font-medium text-gray-300">Cooldown seconds</label>
                <input
                  type="number"
                  min="0"
                  max="3600"
                  value={automation.cooldown_seconds}
                  onChange={(event) => saveAutomation({ cooldown_seconds: parseInt(event.target.value, 10) || 0 })}
                  className="mt-3 w-full rounded-lg border border-gray-600 bg-gray-950 px-3 py-2 text-sm text-white"
                />
              </div>
            </div>

            <div>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h4 className="text-sm font-semibold text-white">Ticker handoff switches</h4>
                  <p className="text-xs text-gray-500">Per-ticker preferences are preserved even when global handoff is disabled.</p>
                </div>
                <button
                  onClick={() => saveAutomation({ default_ticker_enabled: !automation.default_ticker_enabled })}
                  className={`rounded-lg px-3 py-2 text-xs font-medium ${automation.default_ticker_enabled ? 'bg-emerald-500/20 text-emerald-300' : 'bg-gray-700 text-gray-400'}`}
                >
                  Default: {automation.default_ticker_enabled ? 'On' : 'Off'}
                </button>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                {tickers.length === 0 && <div className="text-sm text-gray-500">No active tickers loaded yet.</div>}
                {tickers.map((symbol) => {
                  const enabled = automation.per_ticker_enabled?.[symbol] ?? automation.default_ticker_enabled;
                  return (
                    <button
                      key={symbol}
                      onClick={() => saveTickerAutomation(symbol, !enabled)}
                      className={`rounded-lg border px-4 py-3 text-left transition-colors ${enabled ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border-gray-700 bg-gray-900/50 text-gray-400 hover:bg-gray-800'}`}
                    >
                      <div className="font-medium">{symbol}</div>
                      <div className="mt-1 text-xs">{enabled ? 'Handoff allowed when global is on' : 'Recommendations only'}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Pulse Handoff Contract */}
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-cyan-400" />
          Pulse handoff contract
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Read-only discovery for PULSE_HANDOFF_ENDPOINT so Edge and Pulse agree on the structured handoff envelope before paper or live automation runs.
        </p>

        {!pulseHandoffContract ? (
          <div className="text-sm text-gray-500">Pulse handoff contract unavailable until the backend schema endpoint responds.</div>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <RuntimeDetail label="contract_version" value={pulseHandoffContract.contract_version} />
            <RuntimeDetail label="endpoint_env" value={pulseHandoffContract.endpoint_env} />
            <RuntimeDetail label="recommended_endpoint" value={pulseHandoffContract.recommended_endpoint || '--'} />

            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 md:col-span-3">
              <div className="text-sm font-medium text-gray-300">transport_headers</div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                {Object.entries(pulseHandoffContract.transport_headers || {}).map(([name, detail]) => (
                  <div key={name} className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/60 p-3">
                    <div className="truncate text-xs font-semibold text-cyan-200">{name}</div>
                    <div className="mt-1 text-xs text-gray-500">{detail}</div>
                  </div>
                ))}
              </div>
              {!pulseHandoffContract.transport_headers?.['Idempotency-Key'] && (
                <div className="mt-3 text-xs text-amber-300">Idempotency-Key header missing from contract discovery.</div>
              )}
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 md:col-span-3">
              <div className="text-sm font-medium text-gray-300">response_contract</div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                {PULSE_RESPONSE_CONTRACT_KEYS.map((name) => {
                  const response = pulseHandoffContract.response_contract?.[name];
                  if (!response) return null;
                  return (
                    <div key={name} className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/60 p-3">
                      <div className="truncate text-xs font-semibold text-cyan-200">
                        {formatPulseContractLabel(name)}
                      </div>
                      <div className="mt-2 space-y-1 text-xs text-gray-500">
                        <div>accepted: {formatPulseContractBoolean(response.accepted)}</div>
                        <div>status: {response.status || '--'}</div>
                        <div>reason: {response.reason || response.error || '--'}</div>
                        {response.handoff_id && <div>handoff_id: {response.handoff_id}</div>}
                        {response.message && <div>message: {response.message}</div>}
                      </div>
                    </div>
                  );
                })}
              </div>
              {Object.keys(pulseHandoffContract.response_contract || {}).length === 0 && (
                <div className="mt-3 text-xs text-amber-300">No Pulse response contract entries discovered.</div>
              )}
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4 md:col-span-3">
              <div className="text-sm font-medium text-gray-300">Pulse feedback semantics</div>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                {Object.entries(pulseHandoffContract.feedback_semantics || {}).map(([name, semantics]) => (
                  <div key={name} className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/60 p-3">
                    <div className="truncate text-xs font-semibold text-cyan-200">
                      {formatPulseContractLabel(name)}
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-gray-500">
                      <div>edge_sent: {formatPulseContractBoolean(semantics.edge_sent)}</div>
                      <div>expected_fields: {formatPulseExpectedFields(semantics.expected_fields)}</div>
                      <div>pulse_side_effect: {semantics.pulse_side_effect || '--'}</div>
                    </div>
                  </div>
                ))}
              </div>
              {Object.keys(pulseHandoffContract.feedback_semantics || {}).length === 0 && (
                <div className="mt-3 text-xs text-amber-300">No Pulse feedback semantics discovered.</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Operator Notification Paths */}
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Bell className="w-5 h-5 text-violet-400" />
          Operator notification paths
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Read-only discovery for Telegram, Discord, Slack, and WhatsApp-style notification channels. Settings shows env-var readiness only; secret_values remain redacted and no messages are sent from this panel.
        </p>

        {!notificationsStatus ? (
          <div className="text-sm text-gray-500">Notification channel status unavailable until the backend status endpoint responds.</div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <RuntimeDetail label="schema_version" value={notificationsStatus.schema_version || '--'} />
              <RuntimeDetail label="mode" value={notificationsStatus.mode || '--'} />
              <RuntimeDetail label="secret_values" value={notificationsStatus.secret_values || '--'} />
              <RuntimeDetail
                label="configured"
                value={`${notificationsStatus.summary?.configured_count ?? 0}/${notificationsStatus.summary?.total_count ?? 0}`}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {(notificationsStatus.channels || []).map((channel) => (
                <div key={channel.id} className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-white">{channel.label}</div>
                      <div className="mt-1 text-xs text-gray-500">{channel.purpose || 'Operator notification channel'}</div>
                    </div>
                    <span className={`rounded-md px-2 py-1 text-xs font-semibold ${channel.configured ? 'bg-emerald-500/10 text-emerald-300' : 'bg-amber-500/10 text-amber-300'}`}>
                      {channel.configured ? 'configured' : 'missing env'}
                    </span>
                  </div>
                  <dl className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-400 sm:grid-cols-2">
                    <div>
                      <dt className="text-gray-500">Delivery path</dt>
                      <dd>{channel.delivery_path || '--'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Confirmation path</dt>
                      <dd>{channel.confirmation_path || '--'}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Configured env</dt>
                      <dd>{formatNotificationEnvList(channel.configured_env)}</dd>
                    </div>
                    <div>
                      <dt className="text-gray-500">Missing env</dt>
                      <dd>{formatNotificationEnvList(channel.missing_env)}</dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
            {(notificationsStatus.channels || []).length === 0 && (
              <div className="text-xs text-amber-300">No notification channels discovered.</div>
            )}

            {(notificationsStatus.confirmation_actions || []).length > 0 && (
              <div className="border-t border-gray-700 pt-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">Confirmation workflows</div>
                    <div className="mt-1 text-xs text-gray-500">
                      Preview-only operator confirmations for safety-sensitive Pulse actions.
                    </div>
                  </div>
                  <div className="text-right text-xs text-gray-500">
                    <div>{notificationsStatus.confirmation_preview?.schema_version || 'preview contract unavailable'}</div>
                    <div>{notificationsStatus.confirmation_preview?.send_side_effect || 'none_preview_only'}</div>
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
                  {(notificationsStatus.confirmation_actions || []).map((action) => (
                    <div key={action.id} className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/50 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="truncate text-sm font-semibold text-violet-100">
                          {action.label || formatNotificationActionId(action.id)}
                        </div>
                        <span className={`rounded-md px-2 py-1 text-xs font-semibold ${action.risk === 'critical' ? 'bg-red-500/10 text-red-300' : action.risk === 'high' ? 'bg-amber-500/10 text-amber-300' : 'bg-blue-500/10 text-blue-300'}`}>
                          {action.risk || 'standard'}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-gray-500">{action.description || 'Operator confirmation workflow'}</div>
                      <dl className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-400 sm:grid-cols-2">
                        <div>
                          <dt className="text-gray-500">Requires confirmation</dt>
                          <dd>{formatNotificationBoolean(action.requires_confirmation)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">Expires</dt>
                          <dd>{formatNotificationExpiry(action.expires_in_seconds)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">Default channels</dt>
                          <dd>{formatNotificationEnvList(action.default_channels)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-500">Preview contract</dt>
                          <dd className="break-words">{action.preview_contract || '--'}</dd>
                        </div>
                      </dl>
                      {action.paper_live_semantics && (
                        <div className="mt-2 text-xs text-gray-500">{action.paper_live_semantics}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Simulation Lab Status */}
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <FlaskConical className="w-5 h-5 text-amber-400" />
          Simulation Lab status
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Read-only discovery for the default-hidden Simulation Lab gate. Lab actions stay hidden unless EDGE_SIMULATION_LAB_ENABLED is enabled on the backend.
        </p>

        {!simulationLabStatus ? (
          <div className="text-sm text-gray-500">Simulation Lab status unavailable until the backend status endpoint responds.</div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <RuntimeDetail label="schema_version" value={simulationLabStatus.schema_version || '--'} />
              <RuntimeDetail label="env_flag" value={simulationLabStatus.env_flag || 'EDGE_SIMULATION_LAB_ENABLED'} />
              <RuntimeDetail label="enabled" value={formatSimulationLabBoolean(simulationLabStatus.enabled)} />
              <RuntimeDetail label="default_hidden" value={formatSimulationLabBoolean(simulationLabStatus.default_hidden)} />
            </div>

            <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
              <div className="text-sm font-medium text-gray-300">Experiment catalog</div>
              <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-3">
                {(simulationLabStatus.experiments || []).map((experiment, index) => (
                  <div key={experiment.id || experiment.endpoint_path || experiment.label || `simulation-lab-experiment-${index}`} className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/60 p-3">
                    <div className="truncate text-xs font-semibold text-amber-200">
                      {experiment.label || formatSimulationLabExperimentId(experiment.id)}
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-gray-500">
                      <div>state: {experiment.state || '--'}</div>
                      <div>status: {experiment.status || '--'}</div>
                      <div>runnable: {formatSimulationLabBoolean(experiment.runnable)}</div>
                      <div>{formatSimulationLabExperimentEndpoint(experiment)}</div>
                      <div>result_schema_version: {experiment.result_schema_version || '--'}</div>
                      {experiment.capability && <div>{experiment.capability}</div>}
                    </div>
                  </div>
                ))}
              </div>
              {(simulationLabStatus.experiments || []).length === 0 && (
                <div className="mt-3 text-xs text-amber-300">No Simulation Lab experiments discovered.</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Market Data Providers */}
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Database className="w-5 h-5 text-emerald-400" />
          Market Data Providers
        </h3>
        <p className="text-sm text-gray-400 mb-4">
          Edge monitors market data only. API keys are configured on the backend as environment variables; this panel only shows provider availability.
        </p>
        <div className="space-y-3">
          {providers.length === 0 && (
            <div className="text-sm text-gray-500">Provider metadata unavailable until the backend is running.</div>
          )}
          {providers.map((provider) => (
            <div key={provider.key} className="flex items-start justify-between gap-4 rounded-lg border border-gray-700 bg-gray-900/50 p-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{provider.label}</span>
                  {providerOrder.includes(provider.key) && (
                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">intraday fallback</span>
                  )}
                  {provider.eod && !provider.intraday && (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">EOD/backfill only</span>
                  )}
                </div>
                <p className="mt-1 text-xs text-gray-500">{provider.free_tier}</p>
                <p className="mt-1 text-xs text-gray-500">{provider.notes}</p>
              </div>
              <div className="flex items-center gap-2 text-sm">
                {provider.configured ? (
                  <CheckCircle className="h-4 w-4 text-emerald-400" />
                ) : (
                  <XCircle className="h-4 w-4 text-gray-500" />
                )}
                <span className={provider.configured ? 'text-emerald-300' : 'text-gray-500'}>
                  {provider.requires_key ? (provider.configured ? 'key configured' : 'needs env key') : 'no key'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Config Sections */}
      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.key} className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              {section.key === 'data' && <Database className="w-5 h-5 text-emerald-400" />}
              {section.key === 'risk' && <Shield className="w-5 h-5 text-red-400" />}
              {section.key === 'greeks' && <TrendingUp className="w-5 h-5 text-purple-400" />}
              {section.key === 'advanced' && <ShieldAlert className="w-5 h-5 text-amber-400" />}
              {section.key === 'charts' && <BarChart3 className="w-5 h-5 text-blue-400" />}
              {section.key === 'paper' && <Zap className="w-5 h-5 text-amber-400" />}
              {section.key === 'rate_limit' && <Globe className="w-5 h-5 text-blue-400" />}
              {section.name}
            </h3>
            
            <div className="space-y-4">
              {section.fields.map((field) => (
                <div key={field.key} className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-300 mb-1">
                      {field.label}
                    </label>
                    {field.description && (
                      <p className="text-xs text-gray-500">{field.description}</p>
                    )}
                  </div>
                  
                  <div className="w-48">
                    {field.type === 'select' && (
                      <select
                        value={field.value}
                        onChange={(e) => handleFieldChange(section.key, field.key, e.target.value)}
                        className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                      >
                        {field.options?.map((opt) => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    )}
                    
                    {field.type === 'number' && (
                      <input
                        type="number"
                        value={field.value}
                        onChange={(e) => handleFieldChange(section.key, field.key, parseFloat(e.target.value) || 0)}
                        className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                      />
                    )}
                    
                    {field.type === 'text' && (
                      <input
                        type="text"
                        value={field.value}
                        onChange={(e) => handleFieldChange(section.key, field.key, e.target.value)}
                        placeholder="Optional"
                        className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                      />
                    )}
                    
                    {field.type === 'boolean' && (
                      <button
                        onClick={() => handleFieldChange(section.key, field.key, !field.value)}
                        className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                          field.value 
                            ? 'bg-emerald-500 text-white' 
                            : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {field.value ? 'Enabled' : 'Disabled'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const RuntimeDetail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="rounded-lg border border-gray-700 bg-gray-900/50 p-4">
    <div className="text-sm font-medium text-gray-300">{label}</div>
    <div className="mt-2 break-words text-sm text-white">{value || '--'}</div>
  </div>
);

function formatPulseContractLabel(value: string) {
  return value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatPulseContractBoolean(value?: boolean) {
  if (value === undefined) return '--';
  return value ? 'true' : 'false';
}

function formatPulseExpectedFields(fields?: string[]) {
  return fields?.length ? fields.join(', ') : '--';
}

function formatSimulationLabBoolean(value?: boolean) {
  if (value === undefined) return '--';
  return value ? 'true' : 'false';
}

function formatSimulationLabExperimentEndpoint(experiment: SimulationLabExperiment) {
  const method = experiment.http_method || 'POST';
  const endpoint = experiment.endpoint_path || 'endpoint unavailable';
  return `${method} ${endpoint}`;
}

function formatNotificationEnvList(values?: string[]) {
  return values?.length ? values.join(', ') : '--';
}

function formatNotificationBoolean(value?: boolean) {
  if (value === undefined) return '--';
  return value ? 'true' : 'false';
}

function formatNotificationExpiry(seconds?: number) {
  if (!seconds) return '--';
  return `${seconds}s`;
}

function formatNotificationActionId(id?: string) {
  if (!id) return 'Confirmation workflow';
  return id.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatSimulationLabExperimentId(id?: string) {
  if (!id) return 'Experiment';
  return id.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}
