# Top 25

Independent fan game for ranking the men’s college football and basketball top 25. The browser app is a React SPA. The API is FastAPI. Both talk to Postgres.

Locally, open the app at [http://localhost:5173](http://localhost:5173). The API listens on port 8000, and the Vite dev server proxies `/api` to it so the session cookie stays on the app origin.

## Prerequisites

- Docker, for Postgres and Mailpit
- Python 3.12
- Node.js with npm
- `make`

`make setup` installs [uv](https://docs.astral.sh/uv/) into `.tools/bin` when it is not already on your `PATH`.

## First-time setup

From the repository root:

```bash
make setup
```

That copies `.env.example` to `.env` if you do not already have one, installs backend and frontend dependencies, and starts Postgres and Mailpit.

Edit `.env` before you seed. Change `SECRET_PEPPER`, `SUPERADMIN_EMAIL`, and `SUPERADMIN_PASSWORD`. The pepper is mixed into session and token hashes. Changing it later signs everyone out and invalidates unused magic links and password resets.

Then create the schema, load schools, and create the first super admin:

```bash
make migrate
make seed
make dev
```

Sign in with `SUPERADMIN_EMAIL`. The first visit asks you to confirm a public display name. That name is what other players see. It is not your account email.

`make dev` applies pending migrations, then runs the API and the frontend together. Stop it with Ctrl-C. That stops the two app processes. Postgres and Mailpit keep running until `make down`.

## Day-to-day commands

Run these from the repository root.

| Command | What it does |
| --- | --- |
| `make setup` | Create `.env` if needed, install dependencies, start Postgres and Mailpit |
| `make dev` | Start Postgres and Mailpit, migrate, then run the API and frontend |
| `make backend` | Start Postgres and Mailpit, then run only the API with reload |
| `make frontend` | Run only the Vite dev server |
| `make db` | Start Postgres and Mailpit |
| `make migrate` | Apply Alembic migrations (`alembic upgrade head`) |
| `make revision msg="describe the change"` | Autogenerate a new Alembic revision from model changes |
| `make seed` | Insert starter schools if the catalog is empty, and create or promote the super admin |
| `make test` | Run the backend pytest suite. Tests use an in-memory database and do not need Docker |
| `make lint` | Run Ruff on the API and `tsc --noEmit` on the frontend |
| `make types` | Export the OpenAPI schema and regenerate `frontend/src/api-types.ts` |
| `make down` | Stop the Docker containers. The database volume is kept |

After you change a SQLAlchemy model, generate a migration and apply it:

```bash
make revision msg="add the column"
make migrate
```

After you change a response schema, regenerate the frontend types and commit `frontend/src/api-types.ts`:

```bash
make types
```

## Where things run

| Service | URL |
| --- | --- |
| App | http://localhost:5173 |
| API | http://localhost:8000 |
| Health check | http://localhost:8000/api/health |
| API docs | http://localhost:5173/api/docs |
| Mailpit | http://localhost:8025 |

Mailpit catches magic-link and password-reset messages. Open a message there and use the link. SMTP in development is `localhost:1025`, which Mailpit accepts with no login.

Postgres is published on host port **5435**, because 5432 is often already taken. `DATABASE_URL` in `.env` must use that same port. The database name, user, and password are all `top25`.

## Environment

Settings load from `.env` at the repository root. Names below match that file.

| Variable | Local value | Production |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://top25:top25@localhost:5435/top25` | Neon, or another Postgres URL, using the `postgresql+psycopg://` driver |
| `SECRET_PEPPER` | Any private string | A long random secret. Do not rotate it casually |
| `DOCS_PUBLIC` | `true` | `false`. Docs then return 404 unless the caller is an admin or super admin |
| `FRONTEND_URL` | `http://localhost:5173` | The public site origin, with no trailing path |
| `SMTP_HOST` | `localhost` | Your mail host. Leave empty to skip sending |
| `SMTP_PORT` | `1025` | The host’s SMTP port |
| `SMTP_FROM` | `Top 25 <noreply@localhost>` | The From address players see |
| `GOOGLE_CLIENT_ID` | Empty until you enable Google sign-in | OAuth client id |
| `GOOGLE_CLIENT_SECRET` | Empty until you enable Google sign-in | OAuth client secret. Stays on the API |
| `GOOGLE_REDIRECT_URI` | `http://localhost:5173/api/auth/google/callback` | `https://<your-domain>/api/auth/google/callback` |
| `SUPERADMIN_EMAIL` | `admin@example.com` | The email `make seed` promotes to super admin |
| `SUPERADMIN_PASSWORD` | `change-me` | That account’s password, if it does not have one yet |
| `STORAGE_DIR` | `uploads` | A persistent directory on the API machine. Relative paths live under `backend/` |
| `COOKIE_SECURE` | `false` | `true` once the site is served over HTTPS |
| `EMAIL_OUTBOX` | `false` | Leave `false`. `true` keeps messages in process memory and is for tests |

The mailer opens a plain SMTP connection and does not send a username or password. Mailpit accepts that. A host that requires SMTP authentication needs a mailer change before it will work.

Google sign-in is optional. When you turn it on, register the redirect URI on the OAuth client exactly as `GOOGLE_REDIRECT_URI`. The callback is under `/api` on the site origin so the session cookie is set for the app, not for a separate API host.

## Debugging in VS Code

1. Run `make migrate` once so the database schema exists.
2. Open **Run and Debug** and start the **Full stack** compound.

That compound starts Postgres, Mailpit, and Vite, then launches the API under debugpy and opens Chrome at the app. The API debugger uses `backend/.venv/bin/python` and the root `.env`.

You can also run the pieces separately with `make backend` and `make frontend`.

## Accounts and API docs

`make seed` creates one super admin. The Players screen can grant or revoke the admin role. It cannot create another super admin or change a super admin’s role. To promote the configured address again, run `make seed`.

With `DOCS_PUBLIC=true`, Swagger is at `/api/docs` and ReDoc is at `/api/redoc`. Set `DOCS_PUBLIC=false` in production. Admins and super admins can still open those pages. Everyone else gets 404.

## Tests and checks

```bash
make test
make lint
```

`make test` does not use the Docker database. `make lint` is Ruff plus the TypeScript check. The frontend production build is the same typecheck plus the Vite bundle:

```bash
cd frontend && npm run build
```

The static files are written to `frontend/dist`.

## Deploy

The app stays on one public origin. Cloudflare Pages serves the site, and `/api` on that same host is forwarded to FastAPI on Fly.io. Session cookies are then first-party. Point `FRONTEND_URL` and `GOOGLE_REDIRECT_URI` at the Pages domain, not at `*.fly.dev`.

`.github/workflows/deploy.yml` runs on every pull request and on every push to `main`. Pull requests run the API checks and the frontend build. A push to `main` does that, then deploys. Fly builds `backend/Dockerfile`, runs `alembic upgrade head` before the new API takes traffic, and keeps one machine running. Pages publishes `frontend/dist`. `frontend/public/_worker.js` proxies `/api` to `API_ORIGIN` in `frontend/wrangler.toml`.

Create the hosts once before the first push to `main`. The workflow has nothing to deploy to until these exist.

1. Create a Neon database and copy its connection string. The API expects the `postgresql+psycopg://` scheme.
2. Install [flyctl](https://fly.io/docs/flyctl/install/) and sign in. If the app name `top25` is taken, pick another name and change `app` in `backend/fly.toml` and `API_ORIGIN` in `frontend/wrangler.toml` together.

```bash
fly apps create top25
fly volumes create top25_uploads --region iad --size 1 -a top25
fly secrets set \
  DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require" \
  SECRET_PEPPER="a long random string" \
  FRONTEND_URL="https://top25.pages.dev" \
  GOOGLE_REDIRECT_URI="https://top25.pages.dev/api/auth/google/callback" \
  SMTP_HOST="your-smtp-host" \
  SMTP_PORT="25" \
  SMTP_FROM="Top 25 <noreply@example.com>" \
  SUPERADMIN_EMAIL="you@example.com" \
  SUPERADMIN_PASSWORD="a real password" \
  -a top25
```

`COOKIE_SECURE`, `DOCS_PUBLIC`, and `STORAGE_DIR` are already set in `backend/fly.toml`. `STORAGE_DIR` is the Fly volume, so uploaded logos survive deploys. The volume is attached to the one machine in `iad`.

3. In Cloudflare, create a Pages project named `top25` and an API token that can edit Pages. Put that token, the account id, and a Fly deploy token in the GitHub repo secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, and `FLY_API_TOKEN`.

4. Push to `main`. After Pages finishes, set `FRONTEND_URL` and `GOOGLE_REDIRECT_URI` to the real hostname if it is not `https://top25.pages.dev`. Changing a custom domain means updating those two secrets and `API_ORIGIN` only if the Fly app name changed.

5. Seed the super admin once:

```bash
fly ssh console -a top25 -C "python -m app.seed"
```

Later runs only refill an empty school catalog and make sure that email is still a super admin. Then sign in, confirm the display name, and create the season and the first week from the Weeks screen.

The mailer opens a plain SMTP connection and does not send a username or password. `SMTP_HOST` has to accept that. A host that requires authentication needs a mailer change before it will work.
