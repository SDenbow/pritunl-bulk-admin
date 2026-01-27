# Pritunl Bulk Admin

A self-hosted web application for **bulk user lifecycle management** across one or more Pritunl VPN servers.

> ✅ **Production-ready for internal use**  
> Designed for operations teams managing users at scale across multiple Pritunl environments.

---

## What this is

Pritunl Bulk Admin is an **admin-only management UI** that allows infrastructure and operations teams to:

- Manage **multiple Pritunl targets** (e.g. ATL, LA, sandbox)
- Export users to CSV
- Import CSV files to **create, update, disable, or delete users**
- Perform **dry-run previews** before making changes
- Store Pritunl credentials **encrypted at rest**
- Maintain a full **audit trail** of all bulk operations

It is built for environments where:

- Users frequently move between teams or clients
- Multiple Pritunl servers must be managed consistently
- Manual, UI-driven user administration does not scale

---

## What this is NOT

- ❌ Not a replacement for the Pritunl admin UI
- ❌ Not an identity provider (IdP)
- ❌ Not a general-purpose IAM system
- ❌ Not exposed to end users

This tool is intended for **trusted operations and infrastructure administrators only**.

---

## Key Features

### Authentication & Access
- Local admin authentication
  - Password-based login
  - Optional TOTP (2FA)
- Secure first-boot `/setup` flow
  - Requires a one-time setup token
  - Automatically promotes the first admin to **superadmin**
  - Setup routes are permanently disabled after bootstrap

### Pritunl Target Management
- Support for multiple Pritunl servers
- Community Edition
  - Session-based admin authentication
- Enterprise Edition
  - API token authentication
- Target capabilities are detected automatically

### Bulk Operations
- CSV-based import/export
- Row-level actions:
  - `create`
  - `update`
  - `upsert`
  - `disable`
  - `delete`
- Dry-run mode enabled by default
- Explicit confirmation required for destructive changes

### Security & Auditing
- Encrypted storage of Pritunl credentials (AES/Fernet)
- Full audit log of all bulk operations
- Timestamped, immutable history suitable for compliance review

---

## Supported Pritunl Editions

| Edition        | Supported | Notes |
|---------------|-----------|------|
| Community     | ✅ Yes     | Session-based admin authentication |
| Enterprise    | ✅ Yes     | Official API token support |
| Groups        | ⚠️ Partial | Requires Enterprise edition |

---

## Architecture Overview

- **Backend:** Python / FastAPI
- **Templates:** Jinja2
- **Database:** PostgreSQL
- **Deployment:** Docker Compose
- **Reverse Proxy:** Nginx (TLS termination)

Sensitive credentials are encrypted using a master key supplied at runtime and never stored in plaintext.

---

## Intended Deployment Model

- Dedicated Linux VM (Ubuntu recommended)
- Internal network or VPN access only
- Not exposed directly to the public internet
- Managed by a small number of trusted administrators

This tool is intentionally **not multi-tenant** and does not attempt to abstract or replace Pritunl’s native security model.

---

## Security Model (High-Level)

- Encrypted credential storage
- Local admin accounts only
- Optional TOTP (RFC 6238)
- One-time bootstrap with setup token
- Automatic superadmin assignment for first admin
- Complete audit logging of bulk actions

Optional outer protections (e.g. network ACLs or reverse proxy auth) may be added based on organizational policy.

---

## License

Apache-2.0

Free to use, modify, and distribute.  
Contributions and internal forks are welcome.

---

## Project Status

**Stable for internal production use**

Ongoing development focuses on:

- UX refinements
- Audit visibility improvements
- Additional safety rails around destructive operations
