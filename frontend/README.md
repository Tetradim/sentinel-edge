# Sentinel Edge Frontend

React/Vite operator console for Sentinel Edge.

The frontend is the local browser experience for Edge's analysis, readiness, protection, automation, and operations workflows. It is not a broker client and it does not hold provider or broker secrets. All sensitive configuration stays in the backend environment.

## Stack

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Zustand state store
- Framer Motion
- Recharts
- Lucide icons
- Radix/shadcn-style primitives

## Runtime Role

The app talks to the Edge FastAPI backend through the API helpers in `src/lib/api.ts`. The Windows source launcher normally sets the backend URL and starts this app on `127.0.0.1:3001`.

Primary UI surfaces:

- Asset Command Console
- Monitor, Command, Protect, Operations, and Settings modes
- Trading Overview
- Advisor Health
- Experience/RUM observability
- Protection Ops
- P&L Tracking
- Market Coverage
- Portfolio
- System Settings
- Tutorials and Learning Center

## Local Development

From this folder:

```powershell
npm install
npm run dev
```

Typical local URLs:

```text
Frontend: http://127.0.0.1:3001
Backend:  http://127.0.0.1:8001
```

The preferred full-stack source workflow is from the repository root:

```powershell
.\Launch-Sentinel-Edge-Local.ps1 -InstallDeps
```

That launcher starts the backend and frontend, opens the UI in a dedicated temporary browser profile, and shuts down owned tasks when the dedicated browser window closes.

## Environment

Common frontend-facing variables:

| Variable | Purpose |
|----------|---------|
| `VITE_BACKEND_URL` | Explicit backend API base URL for Vite builds. |
| `REACT_APP_BACKEND_URL` | Compatibility fallback used by older code paths and launcher environments. |

Do not add raw broker keys or market-data keys to frontend variables. Browser-visible variables are not secret storage.

## Verification

```powershell
npm run lint
npm run build
npm audit --audit-level=moderate
```

The root verification script also runs the frontend gates:

```powershell
..\scripts\verify-local.ps1 -InstallFrontendDeps
```

## Design Notes

- Keep operator workflows dense and scan-friendly.
- Preserve stale-but-known data when a partial refresh fails, and show a visible warning.
- Use backend endpoints for provider catalogs, Pulse state, readiness blockers, and automation state.
- Keep Pulse handoff controls explicit; recommendation display and execution handoff are separate concerns.
- Keep long-running local browser sessions tied to the launcher lifecycle rather than opening bot pages in a normal personal browser profile.
