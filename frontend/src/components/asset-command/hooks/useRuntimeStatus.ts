import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeState } from '../types';

const initialRuntime: RuntimeState = {
  connected: false,
  loading: true,
  pulseAvailable: false,
  killSwitchActive: false,
  schedulerPaused: false,
  error: undefined,
};

export function useRuntimeStatus(addEvent: (symbol: string, title: string, detail: string) => void) {
  const [runtime, setRuntime] = useState<RuntimeState>(initialRuntime);

  useEffect(() => {
    let cancelled = false;
    const loadRuntime = async () => {
      try {
        const [health, pulse, kill] = await Promise.allSettled([
          api.getHealth(),
          api.getPulseStatus(),
          api.getKillSwitchStatus(),
        ]);
        if (cancelled) return;
        const healthValue = health.status === 'fulfilled' ? health.value : null;
        const pulseValue = pulse.status === 'fulfilled' ? pulse.value : null;
        const killValue = kill.status === 'fulfilled' ? kill.value : null;
        setRuntime({
          connected: health.status === 'fulfilled',
          loading: false,
          pulseAvailable: Boolean(pulseValue?.available || healthValue?.pulse_available),
          killSwitchActive: Boolean(killValue?.kill_switch_active),
          schedulerPaused: Boolean(healthValue?.paused),
          error: undefined,
        });
      } catch {
        if (!cancelled) {
          setRuntime((current) => ({
            ...current,
            connected: false,
            loading: false,
            pulseAvailable: false,
            error: 'Runtime status unavailable',
          }));
        }
      }
    };
    loadRuntime();
    const id = window.setInterval(loadRuntime, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const toggleScheduler = async () => {
    if (runtime.loading || !runtime.connected) return;
    setRuntime((current) => ({ ...current, error: undefined }));
    try {
      if (runtime.schedulerPaused) {
        await api.resumeScheduler();
      } else {
        await api.pauseScheduler();
      }
      setRuntime((current) => ({ ...current, schedulerPaused: !current.schedulerPaused, error: undefined }));
      addEvent('EDGE', runtime.schedulerPaused ? 'Scheduler resumed' : 'Scheduler paused', 'Runtime control updated from Asset Command');
    } catch {
      setRuntime((current) => ({ ...current, error: 'Scheduler control failed' }));
      addEvent('EDGE', 'Scheduler control failed', 'Backend control endpoint unavailable');
    }
  };

  return { runtime, toggleScheduler };
}
