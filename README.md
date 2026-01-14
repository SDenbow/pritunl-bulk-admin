# Pritunl Bulk Admin (MVP)

Self-hosted FastAPI + Jinja web app to bulk manage Pritunl users across multiple VPN hosts.

## MVP goals
- Local admin authentication (password + optional TOTP)
- Manage multiple Pritunl targets (ATL/LA/etc.)
- Export users to CSV
- Import CSV with row-level actions (dry-run by default)
- Store Pritunl target credentials encrypted at rest
- Audit log of changes

## Deployment (Docker Compose)
This project is intended to run on a dedicated Linux VM (Ubuntu recommended).

### 1) Copy environment file
```bash
cp .env.example .env
