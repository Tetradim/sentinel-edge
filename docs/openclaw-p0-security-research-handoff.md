# OpenClaw Handoff: P0 Security Research

Date: 2026-06-07
Repo: `C:\Users\automation\GitBots\Sentinel-Edge`
Branch reviewed: `OC-Iteration`

## Scope

This handoff records online research and recommended fixes for the two P0 review findings from the Sentinel Edge local code review.

No application code was changed in this pass. This file is the only repository change.

## P0-1: Unauthenticated Mutating Control APIs

### Local evidence

- `backend/server.py` exposes state-changing routes for ticker add/remove/config, scheduler pause/resume, kill switch, paper orders, and Pulse bridge actions without an authentication or authorization dependency.
- `backend/server.py` configures CORS with `allow_credentials=True` and origins from `CORS_ORIGINS`, while `docker-compose.yml` sets `CORS_ORIGINS=*`.

Relevant files:

- `backend/server.py`
- `docker-compose.yml`
- `frontend/src/lib/api.ts`
- `frontend/src/App.tsx`

### Online research

- OWASP API5:2023 Broken Function Level Authorization says exposed endpoints are easily exploited when anonymous or non-privileged users can call functions they should not access. OWASP recommends a consistent authorization module invoked from all business functions, deny-by-default enforcement, and explicit role grants per function.
- FastAPI documents OAuth2/JWT security dependencies and OAuth2 scopes, including use of `SecurityScopes`/`Security` for fine-grained permission checks on path operations.
- Starlette CORSMiddleware documents that when credentials are allowed, `allow_origins`, `allow_methods`, and `allow_headers` cannot be wildcarded; they must be explicitly specified.
- OWASP CSRF guidance recommends protecting state-changing requests with CSRF tokens or, for API/AJAX style clients, custom headers plus strict CORS, and also recommends rejecting cross-site non-safe methods with Fetch Metadata headers.

Sources:

- https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/
- https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- https://www.starlette.io/middleware/#corsmiddleware
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

### Recommended fix

Implement one shared security module and apply it to every state-changing or sensitive API route.

Suggested local shape:

1. Add `backend/security.py`.
2. Define operator roles/scopes such as:
   - `edge:read`
   - `edge:control`
   - `edge:automation`
   - `edge:pulse`
   - `edge:admin`
   - `edge:test`
3. Use FastAPI dependencies for route-level enforcement:
   - Read-only health/status endpoints can remain public or require `edge:read`, depending on deployment mode.
   - Scheduler pause/resume, ticker mutation, paper orders, Pulse bridge, kill switch, and automation writes must require explicit scopes.
4. Start with a deployable local-beta option:
   - `EDGE_AUTH_MODE=api_key` using `X-Edge-API-Key`.
   - Store only `EDGE_API_KEY_HASH` or a generated local secret file outside git.
   - Return `401` when missing/invalid and `403` when authenticated without the required scope.
5. If this will be browser-user authenticated, move to JWT/session auth and scope checks instead of static API key only.
6. Tighten CORS:
   - Replace wildcard origins with explicit local/UI origins.
   - Do not use `allow_credentials=True` with wildcard origins/methods/headers.
   - Restrict methods and headers to what the UI actually uses.
7. Add CSRF/Fetch Metadata protection for browser-facing state-changing routes:
   - Reject `POST`, `PUT`, `PATCH`, and `DELETE` when `Sec-Fetch-Site: cross-site`.
   - Require a custom header such as `X-Sentinel-Edge-Request: 1` for mutating API calls.
8. Add tests proving unauthenticated calls fail for every mutating route and authorized calls pass.

## P0-2: Production-Visible Test Command Injection APIs

### Local evidence

- `backend/server.py` exposes `/api/test/pulse-command`, `/api/test/send-command`, and `/api/test/commands`.
- These routes write to or read from the Mongo command bus. In a running environment, they can simulate Pulse fills/position updates and alter Edge decision state.

Relevant file:

- `backend/server.py`

### Online research

- OWASP API8:2023 Security Misconfiguration calls unnecessary enabled features and improper CORS policies security risks, and recommends repeatable hardening, reviewing orchestration/API configs, restricting HTTP verbs, applying proper CORS, and enforcing request schemas.
- OWASP API9:2023 Improper Inventory Management warns that unclear test/development API exposure expands attack surface. OWASP recommends inventorying API hosts/endpoints, documenting environment and network access, keeping docs current, and ensuring non-production deployments get equivalent security treatment if connected to real data.
- OWASP API5 prevention also applies: administrative/test-only functions must use explicit authorization checks, not just naming or route path conventions.

Sources:

- https://owasp.org/API-Security/editions/2023/en/0xa8-security-misconfiguration/
- https://owasp.org/API-Security/editions/2023/en/0xa9-improper-inventory-management/
- https://owasp.org/API-Security/editions/2023/en/0xa5-broken-function-level-authorization/

### Recommended fix

Remove test command routes from the default application surface.

Suggested local shape:

1. Move the command-bus test routes into `backend/test_routes.py` or `backend/devtools.py`.
2. Register them only when all of these are true:
   - `EDGE_ENABLE_TEST_ROUTES=true`
   - `ENVIRONMENT` is not `production`
   - Auth is enabled and the caller has `edge:test` or `edge:admin`
3. In production or default local beta, do not register the routes at all. Prefer 404 over 403 so the route inventory is not exposed.
4. If a manual command-injection tool is still needed, make it a CLI script under `scripts/` that talks directly to a local dev database, not an always-on HTTP API.
5. Add startup logging that clearly states whether dev/test routes are disabled or enabled.
6. Add a CI/static test:
   - Default app should not include `/api/test/*`.
   - Setting `EDGE_ENABLE_TEST_ROUTES=true` in a test environment should register them.
   - Production environment should refuse to register them even if the env var is accidentally set.

## Suggested Fix Order

1. Add auth dependencies and protect mutating routes first.
2. Disable/remove `/api/test/*` routes from default registration.
3. Tighten CORS and add Fetch Metadata/custom-header checks for browser-origin mutations.
4. Add route inventory/security tests.
5. Update README with local-beta auth setup and development-only test route workflow.

## Verification Already Done

From the review session:

- `npm.cmd run build` in `frontend` passed.
- `python -m py_compile backend\server.py backend\scheduler.py backend\pulse_client.py backend\automation.py backend\price_fetcher.py backend\engine.py` passed.
- `pytest backend\tests -q` could not run because `pytest` is not installed in the current shell.
- Direct backend import could not be fully checked because runtime packages such as `python-dotenv` and `prometheus_client` are not installed in the current shell.

## Suggested Skills For Next Agent

- `security-review`
- `fastapi-python`
- `python-testing-patterns`
- `verification-before-completion`
