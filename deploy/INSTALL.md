# Pritunl Bulk Admin — Installation / Deployment

Docker Compose deployment for a FastAPI + Postgres internal admin tool used to bulk manage Pritunl users.

## Prerequisites
- Docker + Docker Compose (v2)
- Host can reach your Pritunl API endpoints
- TLS cert + key for the included Nginx reverse proxy (or use your own proxy)

---

## Quick start

1) Clone repo and go to the deploy directory:
    git clone <repo-url>
    cd pritunl-bulk-admin/deploy

2) Create `.env` from the example:
    cp .env.example .env

3) Edit `.env` and set required values (see “Environment variables” below).

4) Start the stack:
    docker compose up -d --build

5) Bootstrap first admin (one-time):
    https://<host>/setup?token=<SETUP_TOKEN>

- Create the first admin user (becomes a superadmin).
- After first admin exists, setup routes are disabled and return 404.

6) Log in:
    https://<host>/login

---

## Environment variables

### App (required)
- DATABASE_URL
  Example (compose service name is `db`):
    postgresql+psycopg2://pritunl_admin:<password>@db:5432/pritunl_admin

- SESSION_SECRET
  Long random string (32+ chars recommended)

- PRITUNL_UI_MASTER_KEY
  Long random string (32+ chars recommended)
  Used to encrypt/decrypt sensitive values stored in DB (target creds, etc.)

- SETUP_TOKEN
  Required to access `/setup` until the first admin is created.
  After bootstrap, `/setup` returns 404 regardless of token.

### App (optional)
- APP_ENV (default: prod)
- ALLOW_DELETE (default: false)
  If true, destructive delete operations are allowed in importer apply.

### Postgres (required)
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD

---

## Database initialization
- The app creates tables automatically at startup (SQLAlchemy metadata create).
- DB is persisted in the named Docker volume `postgres_data`.

---

## Reverse proxy notes (Nginx)

This deployment includes an Nginx container that terminates HTTPS on port 443 and proxies traffic to the FastAPI app container.

TLS certificate files required (mounted read-only into the container):
- deploy/nginx/certs/fullchain.pem
- deploy/nginx/certs/privkey.pem

Default behavior:
- Nginx listens on 443
- All traffic proxies to http://app:8000
- Forwarded headers set:
  - Host
  - X-Forwarded-Proto (https)
  - X-Real-IP
  - X-Forwarded-For

Optional Basic Auth (outer gate):
- Create: deploy/nginx/htpasswd
- Uncomment these lines in deploy/nginx/default.conf:
  - auth_basic "Restricted";
  - auth_basic_user_file /etc/nginx/.htpasswd;

Using an external reverse proxy:
- You may disable/remove the nginx service from compose
- Proxy directly to the app service on port 8000
- Ensure these headers are forwarded:
  - Host
  - X-Forwarded-For
  - X-Forwarded-Proto

---

## Backup / restore

Backup (recommended):
    cd deploy
    docker compose exec -T db bash -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup.sql

Restore:
    cd deploy
    cat backup.sql | docker compose exec -T db bash -lc 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'

---

## Reset to a fresh instance (lab/testing)
WARNING: deletes all app data (admins, targets, import history, audit).

    cd deploy
    docker compose down -v
    docker compose up -d --build

Then bootstrap again:
    https://<host>/setup?token=<SETUP_TOKEN>
