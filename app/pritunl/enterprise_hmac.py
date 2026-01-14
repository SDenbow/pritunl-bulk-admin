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

    def _auth_headers(self, method: str, path: str) -> dict[str, str]:
        """
        Pritunl API auth per official docs:
        auth_string = '&'.join([token, timestamp, nonce, method.upper(), path])
        signature  = base64(hmac_sha256(secret, auth_string))
        """
        if not path.startswith("/"):
            path = "/" + path

        auth_timestamp = str(int(time.time()))
        auth_nonce = uuid.uuid4().hex

        auth_string = "&".join([
            self.api_token,
            auth_timestamp,
            auth_nonce,
            method.upper(),
            path,
        ]).encode("utf-8")

        digest = hmac.new(
            self.api_secret.encode("utf-8"),
            auth_string,
            hashlib.sha256,
        ).digest()

        auth_signature = base64.b64encode(digest).decode("utf-8")

        return {
            "Auth-Token": self.api_token,
            "Auth-Timestamp": auth_timestamp,
            "Auth-Nonce": auth_nonce,
            "Auth-Signature": auth_signature,
        }

    def request(self, method: str, path: str, json_body: Any | None = None) -> Any:
        if not path.startswith("/"):
            path = "/" + path

        url = self.base_url.rstrip("/") + path

        headers = self._auth_headers(method, path)

        data = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body)

        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=data,
            timeout=self.timeout_s,
            verify=self.verify_tls,
        )

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} from {path}: {resp.text[:300]}")

        if resp.headers.get("content-type", "").lower().startswith("application/json"):
            return resp.json()

        return resp.text

    def list_organizations(self):
        return self.request("GET", "/organization")

    def list_users(self, org_id: str):
        return self.request("GET", f"/user/{org_id}")
