# DriveDB — Google Drive as a Backend

A runnable starter project using FastAPI, HTML, vanilla JavaScript, Bootstrap 5, and Tailwind CSS. Users authorize access to their own Google Drive; JSON documents are stored in an app folder in that Drive.

## Included in this starter
- FastAPI app with Google OAuth login/logout and session cookie
- Google Drive API v3 service layer
- Automatic `DriveDB` root folder and collection folders
- JSON document create/list/read/update/delete endpoints
- Responsive dashboard UI with Bootstrap and Tailwind CDN
- Health/configuration endpoints and API docs
- Dockerfile and `.env.example`

## Important design notes
- Google Drive is a document/file store, **not a transactional database**. This starter does not promise MongoDB-equivalent transactions, indexes, or unlimited scale.
- OAuth tokens are held in server memory for this MVP and are not written to browser localStorage. Restarting the server logs users out. For production, replace the in-memory session/token store with Redis or another encrypted server-side session store.
- Public Google OAuth apps may require OAuth consent-screen verification depending on scopes and audience. Start with `drive.file`, which limits access to files created/opened by the app, and verify that the chosen workflow fits your needs.
- Do not put client secrets in frontend code or commit `.env`.
- This is a development starter, not a security-audited production service.

## Requirements
- Python 3.11+
- Google Cloud project with Google Drive API enabled
- OAuth client credentials (Web application)

## Google OAuth setup
1. Open Google Cloud Console and create/select a project.
2. Enable **Google Drive API**.
3. Configure OAuth consent screen.
4. Create an OAuth client ID of type **Web application**.
5. Add `http://localhost:8000/auth/callback` as an authorized redirect URI.
6. Copy the client ID and secret into `.env`.

## Run locally (Windows PowerShell)
```powershell
cd drivedb-platform
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and add Google OAuth credentials + a long random SESSION_SECRET
uvicorn app.main:app --reload
```
Open http://localhost:8000

## Run locally (macOS/Linux)
```bash
cd drivedb-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env
uvicorn app.main:app --reload
```

## Deployment

### Deploy to Render
1. Push your repository to GitHub.
2. Sign in to [Render](https://render.com) and click **New > Web Service** (or connect via Blueprint with `render.yaml`).
3. Connect your GitHub repository `Bring-Your-Own-Drive`.
4. Configure settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, configure:
   - `APP_NAME`: `DriveDB`
   - `APP_ENV`: `production`
   - `BASE_URL`: `https://<your-render-service-name>.onrender.com`
   - `GOOGLE_CLIENT_ID`: `<your-google-client-id>`
   - `GOOGLE_CLIENT_SECRET`: `<your-google-client-secret>`
   - `SESSION_SECRET`: `<a-long-random-secret>`
   - `COOKIE_SECURE`: `true`
6. In **Google Cloud Console > Credentials > OAuth 2.0 Client ID**, add to **Authorized redirect URIs**:
   `https://<your-render-service-name>.onrender.com/auth/callback`

### Deploy to Vercel
1. Install Vercel CLI (`npm i -g vercel`) or import the GitHub repository in the [Vercel Dashboard](https://vercel.com).
2. The repository includes `vercel.json` and `api/index.py` configured for Vercel Python Serverless Functions.
3. In your Vercel Project Settings under **Environment Variables**, add:
   - `APP_NAME`: `DriveDB`
   - `APP_ENV`: `production`
   - `BASE_URL`: `https://<your-vercel-domain>.vercel.app`
   - `GOOGLE_CLIENT_ID`: `<your-google-client-id>`
   - `GOOGLE_CLIENT_SECRET`: `<your-google-client-secret>`
   - `SESSION_SECRET`: `<a-long-random-secret>`
   - `COOKIE_SECURE`: `true`
4. In **Google Cloud Console > Credentials > OAuth 2.0 Client ID**, add to **Authorized redirect URIs**:
   `https://<your-vercel-domain>.vercel.app/auth/callback`

### Custom Domain Setup (`masterperi5.me`)

#### On Render:
1. Open your service in the [Render Dashboard](https://dashboard.render.com).
2. Go to **Settings > Custom Domains**.
3. Add `masterperi5.me` (Render automatically configures `www.masterperi5.me` as well).
4. Update DNS with your domain registrar / DNS provider (Cloudflare, Namecheap, GoDaddy, etc.):
   - **Root domain (`@`)**: Add `ALIAS` / `ANAME` or `A` record pointing to Render's IP provided in dashboard (e.g., `216.24.57.1`).
   - **Subdomain (`www`)**: Add `CNAME` record with Host `www` pointing to `bring-your-own-drive.onrender.com`.
   - Remove any existing `AAAA` records (IPv6) as Render uses IPv4.
5. In **Google Cloud Console > Credentials > OAuth 2.0 Client ID**, add to **Authorized redirect URIs**:
   - `https://masterperi5.me/auth/callback`
   - `https://www.masterperi5.me/auth/callback`
6. In Render Environment Variables, set:
   - `BASE_URL`: `https://masterperi5.me`

#### On Vercel:
1. Open your project in the [Vercel Dashboard](https://vercel.com).
2. Go to **Settings > Domains** and add `masterperi5.me`.
3. Add the DNS records shown by Vercel (`A` record `76.76.21.21` or `CNAME` for `cname.vercel-dns.com`).
4. In Google Cloud Console, add `https://masterperi5.me/auth/callback` to **Authorized redirect URIs**.
5. Set `BASE_URL=https://masterperi5.me`.

## API endpoints
- `GET /api/health` — health status
- `GET /api/me` — current user
- `GET /api/collections` — list DriveDB collections
- `POST /api/collections` — create collection `{ "name": "notes" }`
- `GET /api/collections/{name}/documents` — list JSON docs
- `POST /api/collections/{name}/documents` — create `{ "data": { ... } }`
- `GET /api/collections/{name}/documents/{document_id}` — read document
- `PATCH /api/collections/{name}/documents/{document_id}` — shallow-merge patch
- `DELETE /api/collections/{name}/documents/{document_id}` — delete document
- `GET /docs` — interactive OpenAPI docs

## Phased implementation
### Phase 1 — Foundation
OAuth, app shell, health check, configuration, Drive root folder.
### Phase 2 — CRUD
Collection folders and JSON document CRUD.
### Phase 3 — UX and resilience
Loading/error states, search, pagination, offline cache, conflict handling.
### Phase 4 — Public sharing and deployment
Explicit public sharing flow, quotas/rate limits, persistent sessions, deployment, monitoring.

## Current limitations
- Collections are represented as folders; documents as JSON files.
- Listing is paginated but this MVP fetches one page per request.
- Patch performs a shallow merge.
- No public sharing, Sheets indexing, real-time notifications, or offline write queue yet.
- Token refresh and revoked-token recovery need production hardening.
