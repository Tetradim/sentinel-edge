import { useEffect, useState } from 'react';
import { CheckCircle2, Database, KeyRound, Loader2, Save, TestTube2 } from 'lucide-react';
import { api } from '@/lib/api';

interface Settings {
  enabled: boolean;
  base_url: string;
  run_id: string;
  participant_id: string;
  display_name: string;
  roles: string[];
  subscribed_symbols: string[];
  token_configured: boolean;
  timeout_seconds: number;
  starting_cash: number;
  commission_per_order: number;
  slippage_bps: number;
}

const input = 'mt-1 w-full rounded-lg border border-gray-600 bg-gray-950 px-3 py-2 text-sm text-white';

export function GeneralApiSettings() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const refresh = () => api.getGeneralApiSettings().then((value) => setSettings(value.settings));
  useEffect(() => { refresh().catch((error) => setMessage(error instanceof Error ? error.message : 'General API unavailable')); }, []);
  const patch = (value: Partial<Settings>) => setSettings((current) => current ? { ...current, ...value } : current);

  const save = async () => {
    if (!settings) return;
    setBusy(true);
    try {
      const payload: Record<string, unknown> = { ...settings };
      delete payload.token_configured;
      if (token) payload.api_token = token;
      const value = await api.updateGeneralApiSettings(payload);
      setSettings(value.settings);
      setToken('');
      setMessage('General API settings saved.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Save failed');
    } finally { setBusy(false); }
  };

  const run = async (action: 'test' | 'register') => {
    setBusy(true);
    try {
      if (token) await save();
      const value = action === 'test' ? await api.testGeneralApi() : await api.registerGeneralApi();
      setMessage(action === 'test'
        ? `Archive reachable (${value.contract || 'archive.general.v1'})${value.participant_authenticated ? '; Edge authenticated.' : '.'}`
        : `Registered ${value.participant?.participant_id || settings?.participant_id}; token stored privately.`);
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `${action} failed`);
    } finally { setBusy(false); }
  };

  if (!settings) return null;
  return (
    <section className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-6" data-testid="general-api-settings">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex gap-3"><Database className="mt-1 h-5 w-5 text-cyan-400" /><div><h3 className="text-lg font-semibold text-white">General API</h3><p className="text-sm text-gray-400">Join an Archive replay as an observer and risk controller. Edge can publish its own observations and directives; Archive never creates Edge decisions.</p></div></div>
        <label className="flex items-center gap-2 text-sm text-gray-300"><input type="checkbox" checked={settings.enabled} onChange={(event) => patch({ enabled: event.target.checked })} /> Enabled</label>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-xs text-gray-400">Archive General URL<input className={input} value={settings.base_url} onChange={(event) => patch({ base_url: event.target.value })} /></label>
        <label className="text-xs text-gray-400">Replay run ID<input className={input} value={settings.run_id} onChange={(event) => patch({ run_id: event.target.value })} placeholder="run-..." /></label>
        <label className="text-xs text-gray-400">Participant ID<input className={input} value={settings.participant_id} onChange={(event) => patch({ participant_id: event.target.value })} /></label>
        <label className="text-xs text-gray-400">Observed symbols<input className={input} value={settings.subscribed_symbols.join(', ')} onChange={(event) => patch({ subscribed_symbols: event.target.value.split(',').map((part) => part.trim().toUpperCase()).filter(Boolean) })} placeholder="SPY, ES=F" /></label>
        <label className="text-xs text-gray-400">Participant token<input className={input} type="password" value={token} onChange={(event) => setToken(event.target.value)} placeholder={settings.token_configured ? 'Stored privately — enter to replace' : 'Paste token or register'} /></label>
        <label className="text-xs text-gray-400">Timeout seconds<input className={input} type="number" min="0.1" step="0.1" value={settings.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })} /></label>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button disabled={busy} onClick={save} className="flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white"><Save className="h-4 w-4" /> Save</button>
        <button disabled={busy} onClick={() => run('test')} className="flex items-center gap-2 rounded-lg border border-gray-600 px-3 py-2 text-sm text-gray-200"><TestTube2 className="h-4 w-4" /> Test</button>
        <button disabled={busy || !settings.run_id} onClick={() => run('register')} className="flex items-center gap-2 rounded-lg border border-cyan-500/40 px-3 py-2 text-sm text-cyan-300"><KeyRound className="h-4 w-4" /> Register</button>
        {busy && <Loader2 className="h-4 w-4 animate-spin text-cyan-300" />}
        {settings.token_configured && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle2 className="h-4 w-4" /> token configured</span>}
      </div>
      {message && <p className="mt-3 text-sm text-gray-400">{message}</p>}
    </section>
  );
}
