from typing import Any

from .enterprise_hmac import EnterpriseHmacClient


def create_user(
    client: EnterpriseHmacClient,
    org_id: str,
    name: str,
    email: str,
    groups: list[str] | None = None,
    send_key_email: bool = False,
) -> dict[str, Any]:

    # 1️⃣ Create user
    payload: dict[str, Any] = {
        "organization_id": org_id,
        "name": name,
        "email": email,
    }
    if groups is not None:
        payload["groups"] = groups

    created = client.request("POST", f"/user/{org_id}", json_body=payload)

    # Pritunl returns list
    if isinstance(created, list) and created:
        user_obj = created[0]
    elif isinstance(created, dict):
        user_obj = created
    else:
        raise RuntimeError(f"Unexpected create_user response format: {created!r}")

    user_id = user_obj.get("id")
    if not user_id:
        raise RuntimeError(f"Create response missing user id: {user_obj!r}")

    # 2️⃣ If requested, trigger key email the same way UI does
    if send_key_email:
        full_user = dict(user_obj)
        full_user["send_key_email"] = True

        # Important: organization_id must be present for PUT
        full_user["organization_id"] = org_id

        email_resp = client.request(
            "PUT",
            f"/user/{org_id}/{user_id}",
            json_body=full_user,
        )

        return {"user": user_obj, "email_trigger": email_resp}

    return user_obj


def update_user_full(client: EnterpriseHmacClient, org_id: str, user_id: str, full_user_obj: dict[str, Any]) -> dict[str, Any]:
    full_user_obj = dict(full_user_obj)
    full_user_obj["organization_id"] = org_id
    return client.request("PUT", f"/user/{org_id}/{user_id}", json_body=full_user_obj)


def delete_user(client: EnterpriseHmacClient, org_id: str, user_id: str) -> Any:
    return client.request("DELETE", f"/user/{org_id}/{user_id}")
