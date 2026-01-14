# Pritunl Bulk Admin

A self-hosted web application for **bulk user lifecycle management** across one or more Pritunl VPN servers.

> ⚠️ **Early development / MVP**  
> APIs, configuration, and behavior may change.

---

## What this is

Pritunl Bulk Admin is an **admin-only management UI** that allows you to:

- Manage **multiple Pritunl targets** (e.g. ATL, LA, sandbox)
- Export users to CSV
- Import CSV files to **create, update, disable, or delete users**
- Perform **dry-run previews** before making changes
- Store Pritunl credentials **encrypted at rest**
- Maintain a full **audit trail** of all bulk operations

Built for environments where:

- Users frequently move between teams or clients
- Multiple Pritunl servers must be managed consistently
- Manual UI-based user management does not scale

---

## What this is NOT

- ❌ Not a replacement for the Pritunl admin UI  
- ❌ Not an identity provider (IdP)  
- ❌ Not a general-purpose IAM system  
- ❌ Not exposed to end users  

This tool is intended for **operations and infrastructure administrators only**.

---

## Key Features (MVP)

- Local admin authentication
  - Password-based login
  - Optional TOTP (2FA)
- First-boot setup wizard
- Support for multiple Pritunl targets
  - Community Edition (session-based admin login)
  - Enterprise Edition (API token authentication)
- CSV-based bulk operations
  - Row-level actions (`create`, `update`, `upsert`, `disable`, `delete`)
  - Dry-run mode enabled by default
- Encrypted storage of Pritunl credentials
- Persistent audit logs of all bulk changes

---

## Supported Pritunl Editions

| Edition        | Supported | Notes |
|---------------|-----------|------|
| Community     | ✅ Yes     | Uses session-based admin authentication |
| Enterprise    | ✅ Yes     | Uses official API tokens |
| Groups        | ⚠️ Partial | Requires Enterprise edition |

The application adapts behavior based on target capabilities.

---

## Architecture Overview

- **Backend:** Python / FastAPI
- **Templates:** Jinja2
- **Database:** PostgreSQL
- **Deployment:** Docker Compose
- **Reverse Proxy:** Nginx (TLS termination)

Sensitive credentials are encrypted using a master key provided at runtime.

---

## Deployment Status

> ⚠️ **Important**

This repository currently includes:

- Docker / Nginx / PostgreSQL scaffolding
- Project structure and configuration
- Documentation

The **runnable application code** (FastAPI app, setup wizard, authentication, target management UI) is added in the **next commit**.

This separation is intentional to keep infrastructure and application logic cleanly staged.

---

## Intended Deployment Model

- Dedicated Linux VM (Ubuntu recommended)
- Internal network or VPN access only
- Not exposed directly to the public internet
- Managed by a small number of trusted administrators

---

## Security Model (High-Level)

- Encrypted credential storage (AES/Fernet)
- Local admin accounts
- Optional TOTP (RFC 6238)
- Full audit logging of bulk operations
- Optional Nginx Basic Auth as an additional outer gate

---

## License

Apache-2.0

This project is free to use, modify, and distribute.  
Contributions are welcome.

---

## Project Status & Roadmap

Current stage: **Early MVP**

Planned milestones:

1. First-boot `/setup` wizard
2. Admin login with optional TOTP
3. Target management UI
4. CSV import/export with dry-run previews
5. Audit history UI

---
