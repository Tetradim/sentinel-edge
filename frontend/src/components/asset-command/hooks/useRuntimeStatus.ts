import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeState } from '../types';

const initialRuntime: RuntimeState = {
  connected: false,
  loading: true,
  pulseAvailable: false,
  pulseCircuitState: undefined,
  edgeLive: false,
  killSwitchActive: false,
  schedulerPaused: false,
  runtimeReady: false,
  readinessFailingChecks: [],
  edgePid: undefined,
  edgeUptimeSeconds: undefined,
  edgeLiveTimestamp: undefined,
  rateLimitPressure: 'unknown',
  rateLimitRemaining: undefined,
  rateLimitResetSeconds: undefined,
  frontendRumStatus: 'unknown',
  frontendRumSampleCount: undefined,
  frontendRumRouteCount: undefined,
  frontendRumLastRoute: undefined,
  frontendRumAgeSeconds: undefined,
  updatedAt: undefined,
  error: undefined,
};

export function useRuntimeStatus(addEvent: (symbol: string, title: string, detail: string) => void) {
  const [runtime, setRuntime] = useState<RuntimeState>(initialRuntime);

  useEffect(() => {
    let cancelled = false;
    const loadRuntime = async () => {
      try {
        const [health, liveness, readiness, rateLimit, frontendRum, pulse, kill] = await Promise.allSettled([
          api.getHealth(),
          api.getLiveness(),
          api.getReadiness(),
          api.getRateLimitStatus(),
          api.getFrontendRumStatus(),
          api.getPulseStatus(),
          api.getKillSwitchStatus(),
        ]);
        if (cancelled) return;
        const healthValue = health.status === 'fulfilled' ? health.value : null;
        const livenessValue = liveness.status === 'fulfilled' ? liveness.value : null;
        const readinessValue = readiness.status === 'fulfilled' ? readiness.value : null;
        const rateLimitValue = rateLimit.status === 'fulfilled' ? rateLimit.value : null;
        const frontendRumValue = frontendRum.status === 'fulfilled' ? frontendRum.value : null;
        const pulseValue = pulse.status === 'fulfilled' ? pulse.value : null;
        const killValue = kill.status === 'fulfilled' ? kill.value : null;
        setRuntime({
          connected: health.status === 'fulfilled',
          loading: false,
          pulseAvailable: Boolean(pulseValue?.available || healthValue?.pulse_available),
          pulseCircuitState: pulseValue?.circuit_state || healthValue?.pulse_circuit_state,
          edgeLive: livenessValue?.status === 'alive',
          killSwitchActive: Boolean(killValue?.kill_switch_active),
          schedulerPaused: Boolean(healthValue?.paused),
          runtimeReady: Boolean(readinessValue?.ready),
          readinessFailingChecks: readinessValue?.failing_checks || [],
          edgePid: livenessValue?.pid,
          edgeUptimeSeconds: livenessValue?.uptime_seconds,
          edgeLiveTimestamp: livenessValue?.timestamp,
          rateLimitPressure: rateLimitValue?.pressure || 'unknown',
          rateLimitRemaining: rateLimitValue?.remaining_requests,
          rateLimitResetSeconds: rateLimitValue?.reset_seconds,
          frontendRumStatus: frontendRumValue?.status === 'receiving' || frontendRumValue?.status === 'waiting'
            ? frontendRumValue.status
            : 'unknown',
          frontendRumSampleCount: frontendRumValue?.sample_count,
          frontendRumRouteCount: frontendRumValue?.route_count,
          frontendRumLastRoute: frontendRumValue?.last_route,
          frontendRumAgeSeconds: frontendRumValue?.seconds_since_last,
          updatedAt: new Date().toISOString(),
          error: undefined,
        });
      } catch {
        if (!cancelled) {
          setRuntime((current) => ({
            ...current,
            connected: false,
            loading: false,
            pulseAvailable: false,
            pulseCircuitState: undefined,
            edgeLive: false,
            runtimeReady: false,
            readinessFailingChecks: [],
            edgePid: undefined,
            edgeUptimeSeconds: undefined,
            edgeLiveTimestamp: undefined,
            rateLimitPressure: 'unknown',
            rateLimitRemaining: undefined,
            rateLimitResetSeconds: undefined,
            frontendRumStatus: 'unknown',
            frontendRumSampleCount: undefined,
            frontendRumRouteCount: undefined,
            frontendRumLastRoute: undefined,
            frontendRumAgeSeconds: undefined,
            updatedAt: new Date().toISOString(),
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
