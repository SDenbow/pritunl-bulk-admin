## [1.1.0] - 2026-02-07

### Added

- Automatically trigger Pritunl key/profile email after user creation (v1.32-compatible)

- Uses PUT /user/{org}/{user} with send_key_email flag (matches UI behavior)



### Fixed

- Removed incorrect key endpoint probing for Pritunl 1.32



# Changelog

## v1.0.0
- Multi-target Pritunl management
- CSV export/import with preview → summary → apply workflow
- Guardrail warnings and apply acknowledgment
- Local admin authentication with optional TOTP
- One-time bootstrap with setup token; setup disabled after initialization
- Superadmin management with “must always have ≥1 superadmin”
- Full audit/history view for bulk operations
- Docker Compose deployment with Nginx TLS termination
