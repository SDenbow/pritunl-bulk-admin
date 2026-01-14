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

    def _auth_headers(self, method: str, path: str, body_bytes: bytes) -> dict[str, str]:
        """
        Pritunl Enterprise API HMAC signing.
        Signature = base64(HMAC_SHA256(secret, token&timestamp&nonce&method&path&body))
        """
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        method_u = method.upper()

        # Pritunl expects leading slash path, e.g. "/organization"
        if not path.startswith("/"):
            path = "/" + path

        auth_string = "&".join([
            self.api_token,
            timestamp,
            nonce,
            method_u,
            path,
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
        url = self.base_url.rstrip("/") + (path if path.startswith("/") else f"/{path}")
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

        # Raise helpful error
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {path}: {resp.text[:300]}")

        # Most endpoints return JSON
        if resp.headers.get("content-type", "").lower().startswith("application/json"):
            return resp.json()

        return resp.text

    def list_organizations(self) -> list[dict[str, Any]]:
        return self.request("GET", "/organization")

    def list_users(self, org_id: str) -> list[dict[str, Any]]:
        # Common Pritunl pattern: /user/<org_id>
        return self.request("GET", f"/user/{org_id}")
