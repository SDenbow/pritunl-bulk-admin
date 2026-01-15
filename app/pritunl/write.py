from typing import Any

from .enterprise_hmac import EnterpriseHmacClient


def create_user(client: EnterpriseHmacClient, org_id: str, name: str, email: str, groups: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "organization_id": org_id,
        "name": name,
        "email": email,
    }
    if groups is not None:
        payload["groups"] = groups
    return client.request("POST", f"/user/{org_id}", json_body=payload)


def update_user_full(client: EnterpriseHmacClient, org_id: str, user_id: str, full_user_obj: dict[str, Any]) -> dict[str, Any]:
    full_user_obj = dict(full_user_obj)
    full_user_obj["organization_id"] = org_id
    return client.request("PUT", f"/user/{org_id}/{user_id}", json_body=full_user_obj)


def delete_user(client: EnterpriseHmacClient, org_id: str, user_id: str) -> Any:
    return client.request("DELETE", f"/user/{org_id}/{user_id}")
