import json
from typing import Any

from ..crypto import decrypt_str
from ..targets.models import Target
from .enterprise_hmac import EnterpriseHmacClient


def _parse_creds(target: Target) -> dict[str, Any]:
    return json.loads(decrypt_str(target.credentials_enc))


def build_client(target: Target) -> EnterpriseHmacClient:
    if target.auth_mode != "enterprise_hmac":
        raise RuntimeError("Target auth_mode is not enterprise_hmac")

    creds = _parse_creds(target)
    token = (creds.get("api_token") or "").strip()
    secret = (creds.get("api_secret") or "").strip()
    if not token or not secret:
        raise RuntimeError("Missing API token/secret for target")

    return EnterpriseHmacClient(
        base_url=target.base_url,
        api_token=token,
        api_secret=secret,
        verify_tls=target.verify_tls,
    )


def choose_org(orgs: list[dict[str, Any]], org_name: str | None) -> dict[str, Any]:
    if not orgs:
        raise RuntimeError("No organizations returned by target")

    if org_name:
        for o in orgs:
            if (o.get("name") or "").strip() == org_name:
                return o
        raise RuntimeError(f"Org '{org_name}' not found on target")

    if len(orgs) == 1:
        return orgs[0]

    raise RuntimeError("Multiple orgs found; set Org Name on the target to disambiguate")
