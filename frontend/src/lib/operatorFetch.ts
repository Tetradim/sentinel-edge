const OPERATOR_SECRET_STORAGE_KEY = 'edge_operator_action_secret';
const LIVE_AUTOMATION_SIGNOFF = 'ENABLE LIVE AUTOMATION';
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function configuredSecret(): string {
  const envSecret = String((import.meta as any).env?.VITE_EDGE_OPERATOR_ACTION_SECRET || '').trim();
  if (envSecret) return envSecret;
  try {
    return String(localStorage.getItem(OPERATOR_SECRET_STORAGE_KEY) || '').trim();
  } catch {
    return '';
  }
}

function saveSecret(value: string) {
  try {
    if (value) localStorage.setItem(OPERATOR_SECRET_STORAGE_KEY, value);
  } catch {
    // Storage may be disabled; the current request can still use the value.
  }
}

function requestPath(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  if (typeof Request !== 'undefined' && input instanceof Request) return input.method.toUpperCase();
  return 'GET';
}

function isEdgeMutation(input: RequestInfo | URL, init?: RequestInit) {
  const method = requestMethod(input, init);
  const path = requestPath(input);
  return MUTATING_METHODS.has(method) && (path.startsWith('/api/') || path.includes('/api/'));
}

function withOperatorHeaders(input: RequestInfo | URL, init: RequestInit | undefined, secret: string): RequestInit {
  const existingHeaders = new Headers(
    init?.headers || (typeof Request !== 'undefined' && input instanceof Request ? input.headers : undefined),
  );
  if (secret) existingHeaders.set('X-Edge-Operator-Secret', secret);
  existingHeaders.set('X-Edge-Live-Readiness-Signoff', LIVE_AUTOMATION_SIGNOFF);
  return { ...(init || {}), headers: existingHeaders };
}

async function responseRequestsOperatorSecret(response: Response): Promise<boolean> {
  if (![401, 409, 503].includes(response.status)) return false;
  try {
    const payload = await response.clone().json();
    const detail = typeof payload?.detail === 'string'
      ? payload.detail
      : JSON.stringify(payload?.detail || payload || '');
    return detail.includes('EDGE_OPERATOR_ACTION_SECRET')
      || detail.toLowerCase().includes('operator action secret')
      || detail.includes('live_automation_readiness_signoff_required');
  } catch {
    return response.status === 401;
  }
}

export function installOperatorFetch() {
  if (typeof window === 'undefined' || (window as any).__edgeOperatorFetchInstalled) return;
  const originalFetch = window.fetch.bind(window);

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    if (!isEdgeMutation(input, init)) return originalFetch(input, init);

    let secret = configuredSecret();
    let response = await originalFetch(input, withOperatorHeaders(input, init, secret));
    if (!(await responseRequestsOperatorSecret(response))) return response;

    const entered = window.prompt(
      'Enter the EDGE_OPERATOR_ACTION_SECRET configured on the Sentinel Edge backend. It will be stored in this browser for future operator actions.',
      secret,
    );
    secret = String(entered || '').trim();
    if (!secret) return response;
    saveSecret(secret);
    response = await originalFetch(input, withOperatorHeaders(input, init, secret));
    return response;
  };

  (window as any).__edgeOperatorFetchInstalled = true;
}

export function clearOperatorSecret() {
  try {
    localStorage.removeItem(OPERATOR_SECRET_STORAGE_KEY);
  } catch {
    // Ignore disabled storage.
  }
}
