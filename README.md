Pritunl Bulk Admin

A self-hosted web application for bulk user lifecycle management across one or more Pritunl VPN servers.

Built for environments where:

users frequently move between teams / clients

multiple Pritunl servers must be managed consistently

manual UI-based user management does not scale

What this is

Pritunl Bulk Admin is an admin-only management UI that allows you to:

Manage multiple Pritunl targets (e.g. ATL, LA, sandbox)

Export users to CSV

Import CSV files to create, update, disable, or delete users

Perform dry-run previews before making changes

Store Pritunl credentials encrypted at rest

Maintain a full audit trail of all bulk operations

This tool is designed to be run internally (VPN / trusted network) on a dedicated Linux VM.

What this is NOT

❌ Not a replacement for the Pritunl admin UI

❌ Not an identity provider (IdP)

❌ Not a general-purpose IAM system

❌ Not exposed to end users

This is an operations tool for admins.

Key Features (MVP)

Local admin authentication

Password-based login

Optional TOTP (2FA)

First-boot setup wizard

Multiple Pritunl targets per deployment

Community Edition (session-based auth)

Enterprise Edition (API token auth)

CSV-based bulk operations

Row-level actions (create, update, upsert, disable, delete)

Dry-run by default

Encrypted storage of Pritunl credentials

Persistent audit logs of all changes

Supported Pritunl Editions
Edition	Supported	Notes
Community	✅	Uses session-based admin login
Enterprise	✅	Uses official API tokens
Groups	⚠️	Requires Enterprise edition

The application automatically adapts based on target capabilities.

Architecture Overview

Backend: Python / FastAPI

Templates: Jinja2

Database: PostgreSQL

Deployment: Docker Compose

Reverse Proxy: Nginx (TLS termination)

All sensitive credentials are encrypted using a master key provided at runtime.

Deployment Status

⚠️ Important

This repository currently contains:

Docker / Nginx / Postgres scaffolding

Project structure

Documentation

The runnable application code (FastAPI app, setup wizard, auth, targets UI) is added in the next commit.

This is intentional to keep infrastructure and application logic clearly separated.

Intended Deployment Model

Dedicated Linux VM (Ubuntu recommended)

Internal network or VPN access only

Not exposed directly to the internet

Managed by a small number of trusted administrators

Security Model (High Level)

Encrypted credential storage (AES/Fernet)

Local admin accounts

Optional TOTP (RFC 6238)

Audit logging for all bulk operations

Optional Nginx Basic Auth as an outer gate

License

Apache-2.0

This project is free to use, modify, and distribute.
Contributions are welcome.

Project Status

Early development / MVP.

Planned next milestones:

First-boot /setup wizard

Admin login + TOTP

Target management UI

CSV import/export with dry-run

Audit history UI
