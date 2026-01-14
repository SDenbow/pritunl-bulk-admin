Place TLS certs here as:

- fullchain.pem
- privkey.pem

For internal-only testing you can generate a self-signed cert, e.g.:

```bash
openssl req -x509 -newkey rsa:2048 -keyout privkey.pem -out fullchain.pem -days 365 -nodes \
  -subj "/CN=pritunl-bulk-admin.local"
