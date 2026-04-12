# Purple AI UI (React)

Single React app for talking to Odoo **AI Core** over HTTP.

## Endpoints (proxied in dev)

- `GET /ai_core/v1/ping`
- `GET /ai_core/v1/settings` — sanitized settings
- `POST /ai_core/v1/chat` — `{ "prompt": "..." }`

## Setup

1. Odoo: enable **ai_core** + **memoai**, configure AI in **Settings → General Settings → AI Core**.
2. Optional: set **React UI Dev API Key** in AI Core and the same value in `.env` as `VITE_AI_CORE_DEV_KEY`.

```bash
cp .env.example .env
npm install
```

## Run

From repo root:

```bash
./run_purpleai
# or: ./run_purpleai 3000
```

Or:

```bash
npm run dev
```

`VITE_ODOO_URL` in `.env` is where Vite proxies **`/ai_core`**, **`/purple_invoices`**, and **`/web`** (default `http://localhost:8069`).

If uploads or invoice API calls return **404**, the dev server is not forwarding to Odoo: check `VITE_ODOO_URL` and restart Vite after changing `.env`.
