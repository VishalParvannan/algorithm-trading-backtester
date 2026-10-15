# Running and deploying Backtest Lab

## Local

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m backend.backtest_service
```

Open http://localhost:8000. The launcher now uses FastAPI/Uvicorn. Your
existing Python examples continue to work independently.

## Private deployment

### Render setup

The root `render.yaml` defines one paid, always-on Python service, a 1 GB
persistent disk, a configurable registration invitation code, and `/health` monitoring. The
frontend and backend run together. Review https://render.com/pricing before
creating the service.

1. Create a private GitHub repository and push this project. Exclude `.venv`,
   `.env`, `data`, SQLite files, and API keys; use the included `.gitignore`.
2. Create a Render account. Select **New → Blueprint**, connect the repository,
   and use its `render.yaml`. Review the paid `starter` plan and disk first.
3. The registration code defaults to quantbacktestlab (case-sensitive). To change it,
   set QUANTLAB_INVITATION_CODE in the service Environment settings.
4. Open the HTTPS URL and choose **Create an account**. Supply the invitation
   code and choose your own username/password. Each account has separate data.
   The hosted server works independently of your computer.
5. Optionally set `ALPHA_VANTAGE_API_KEY` in the service's environment.

Personal accounts use hashed passwords and expiring HttpOnly cookies; public
cookies are Secure and require HTTPS. Registration is invitation-gated. There
is no email verification/recovery service. Local data is not automatically uploaded.
Hosted experiments, drafts, asset directories, and paper accounts survive
redeploys on `/var/data/quantlab.sqlite`. Keep one instance/worker. Restarting
the host interrupts polling temporarily and clears unfinished research jobs;
active paper sessions resume afterward, without backfilling missed quotes.

Production starts with `python -m scripts.serve`, uses the hosting `PORT`,
and disables development reload. Startup requires an explicit database path. Individual account passwords
follow the sign-up password requirements. Browser writes from other origins are rejected.
The configuration is ready locally; no public service has been created yet.

Use the included Dockerfile on a Python/container host. Configure:

- `QUANTLAB_PUBLIC=1`
- `QUANTLAB_AUTH_MODE=accounts` (default)
- `QUANTLAB_INVITATION_CODE`: registration code (defaults to `quantbacktestlab`)
- `QUANTLAB_DB_PATH=/app/data/quantlab.sqlite`
- Optionally `ALPHA_VANTAGE_API_KEY`

Attach a persistent writable volume at `/app/data`. Terminate HTTPS at the
hosting provider's proxy before exposing the app. Registration checks the invitation code on the server. Credentials protect the page, assets, drafts, runs and job endpoints;
the non-sensitive `/health` endpoint remains available to the host.

Run one process/replica initially. The research queue is bounded to four
active jobs with two worker threads. Job status is in memory and resets on
restart; completed experiments and dataset snapshots survive in SQLite.
Cancellation interrupts simulations between bars; an in-flight provider
download can finish before cancellation takes effect.

The old single-account behavior remains available with `QUANTLAB_AUTH_MODE=legacy`
and `QUANTLAB_USERNAME`/`QUANTLAB_PASSWORD` for Basic authentication; it is not
the normal browser-account mode. User roles and broker access are not implemented.
Server secrets belong in
the host's environment settings, never in the repository. `.env.example`
documents the variables; the app does not automatically load `.env` files.

Back up the SQLite database using SQLite's backup API or the host's
consistent volume snapshot feature. Do not copy a database mid-write.

## Live monitoring

Click **Connect feed** on the crypto monitor for a Coinbase USD pair. The
browser connects directly to Coinbase's public WebSocket feed and receives
ticker and heartbeat messages. It reconnects up to five times after a
disconnect and marks a silent feed stale after 45 seconds. The monitor
does not execute trades, change positions or feed intraday ticks into
daily-bar strategies.

The browser stream works only while the page is open. Paper trading uses the
built-in server-side polling loop and persists its accounts on the disk. It
continues after closing the browser while the server runs. Yahoo, Coinbase,
and demo support sampled-quote simulation. No live brokerage orders are
implemented or enabled by this deployment.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
node tests/dashboard_fallback.cjs
node tests/live_monitor.cjs
```

Tests use controlled data and simulated feed messages; they do not place
orders or assert that a third-party service is reachable.
