import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class EnterpriseHmacClient:
    base_url: str
    api_token: str
    api_secret: str
    verify_tls: bool = True
    timeout_s: int = 15
    api_prefix: str = ""  # "", "/api", or reverse-proxy prefix like "/pritunl/api"

    def _normalize_path(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        prefix = (self.api_prefix or "").strip()
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        # prefix='' -> '/organization'
        # prefix='/api' -> '/api/organization'
        return (prefix.rstrip("/") + path) if prefix else path

    def _auth_headers(self, method: str, path: str, body_bytes: bytes) -> dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        method_u = method.upper()

        # IMPORTANT: the path we sign should match the path in the URL request
        signed_path = self._normalize_path(path)

        auth_string = "&".join([
            self.api_token,
            timestamp,
            nonce,
            method_u,
            signed_path,
            body_bytes.decode("utf-8") if body_bytes else "",
        ])

        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            auth_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        signature = base64.b64encode(digest).decode("utf-8")

        return {
            "Auth-Token": self.api_token,
            "Auth-Timestamp": timestamp,
            "Auth-Nonce": nonce,
            "Auth-Signature": signature,
        }

    def request(self, method: str, path: str, json_body: Any | None = None) -> Any:
        req_path = self._normalize_path(path)
        url = self.base_url.rstrip("/") + req_path

        body_bytes = b""
        headers: dict[str, str] = {}

        if json_body is not None:
            body_bytes = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"

        headers.update(self._auth_headers(method, path, body_bytes))

        resp = requests.request(
            method=method.upper(),
            url=url,
            data=body_bytes if body_bytes else None,
            headers=headers,
            timeout=self.timeout_s,
            verify=self.verify_tls,
        )

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {req_path}: {resp.text[:300]}")

        if resp.headers.get("content-type", "").lower().startswith("application/json"):
            return resp.json()

        return resp.text

    def list_organizations(self) -> list[dict[str, Any]]:
        return self.request("GET", "/organization")

    def list_users(self, org_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/user/{org_id}")


def autodetect_prefix(base_url: str, api_token: str, api_secret: str, verify_tls: bool) -> EnterpriseHmacClient:
    """
    Try common API prefixes.
    - First: /organization
    - If 404: /api/organization
    """
    # No prefix
    client = EnterpriseHmacClient(
        base_url=base_url,
        api_token=api_token,
        api_secret=api_secret,
        verify_tls=verify_tls,
        api_prefix="",
    )
    try:
        client.list_organizations()
        return client
    except Exception as e:
        if "HTTP 404" not in str(e):
            raise

    # /api prefix
    client2 = EnterpriseHmacClient(
        base_url=base_url,
        api_token=api_token,
        api_secret=api_secret,
        verify_tls=verify_tls,
        api_prefix="/api",
    )
    client2.list_organizations()
    return client2
