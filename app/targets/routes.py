import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from starlette.responses import Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..crypto import encrypt_str
from .models import Target
from ..auth.routes import require_login
from ..pritunl.service import build_client, choose_org
from ..pritunl.write import create_user, update_user_full, delete_user
from ..importer.preview import preview_csv_against_users, preview_report_csv
from ..importer.models import ImportBatch, ImportRow, AuditLog
from ..importer.apply import sha256_hex, stable_json_hash, acquire_target_lock, release_target_lock, get_actor_from_request, now_utc
from ..settings import settings
from ..settings_service import get_settings

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/targets")
def targets_list(request: Request, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir
    targets = db.query(Target).order_by(Target.name.asc()).all()
    return _templates(request).TemplateResponse("targets.html", {"request": request, "targets": targets, "error": None})



@router.get("/targets/new")
def targets_new_get(request: Request, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir
    return _templates(request).TemplateResponse(
        "target_new.html",
        {"request": request, "error": None},
    )


@router.post("/targets/new")
def targets_new_post(
    request: Request,
    name: str = Form(...),
    base_url: str = Form(...),
    auth_mode: str = Form(...),
    verify_tls: str = Form(default="on"),
    supports_groups: str = Form(default=""),
    org_name: str = Form(default=""),
    api_token: str = Form(default=""),
    api_secret: str = Form(default=""),
    login_user: str = Form(default=""),
    login_pass: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    verify = verify_tls == "on"
    groups = supports_groups == "on"

    if auth_mode == "enterprise_hmac":
        creds = {"api_token": api_token.strip(), "api_secret": api_secret.strip()}
    elif auth_mode == "session_login":
        creds = {"username": login_user.strip(), "password": login_pass}
    else:
        return _templates(request).TemplateResponse(
            "target_new.html",
            {"request": request, "error": "Invalid auth_mode"},
        )

    t = Target(
        name=name.strip(),
        base_url=base_url.strip(),
        auth_mode=auth_mode,
        verify_tls=verify,
        supports_groups=groups,
        org_name=org_name.strip() or None,
        credentials_enc=encrypt_str(json.dumps(creds)),
    )

    db.add(t)
    db.commit()
    return RedirectResponse("/targets", status_code=303)


@router.post("/targets")
def targets_create(
    request: Request,
    name: str = Form(...),
    base_url: str = Form(...),
    auth_mode: str = Form(...),
    verify_tls: str = Form(default="on"),
    supports_groups: str = Form(default=""),
    org_name: str = Form(default=""),
    api_token: str = Form(default=""),
    api_secret: str = Form(default=""),
    login_user: str = Form(default=""),
    login_pass: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    verify = verify_tls == "on"
    groups = supports_groups == "on"

    if auth_mode == "enterprise_hmac":
        creds = {"api_token": api_token.strip(), "api_secret": api_secret.strip()}
    elif auth_mode == "session_login":
        creds = {"username": login_user.strip(), "password": login_pass}
    else:
        targets = db.query(Target).order_by(Target.name.asc()).all()
        return _templates(request).TemplateResponse(
            "targets.html",
            {"request": request, "targets": targets, "error": "Invalid auth_mode"},
        )

    t = Target(
        name=name.strip(),
        base_url=base_url.strip(),
        auth_mode=auth_mode,
        verify_tls=verify,
        supports_groups=groups,
        org_name=org_name.strip() or None,
        credentials_enc=encrypt_str(json.dumps(creds)),
    )

    db.add(t)
    db.commit()
    return RedirectResponse("/targets", status_code=303)


@router.get("/targets/{target_id}")
def target_detail(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    return _templates(request).TemplateResponse(
        "target_detail.html",
        {"request": request, "target": t, "result": None, "error": None},
    )


@router.get("/targets/{target_id}/import/template.csv")
def target_import_template_csv(request: Request, target_id: str, db: Session = Depends(get_db)):
    """
    Download an import template (headers + example rows).

    Import headers:
      action,email,username,groups_mode,groups

    Notes:
      - status is export-only (do not include it in imports)
      - quote groups if it contains commas, e.g. "Admin,IT,ClientA"
    """
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    buf = io.StringIO()
    w = csv.writer(buf)

    # Required headers
    w.writerow(["action", "email", "username", "groups_mode", "groups"])

    # Example rows (generic data)
    w.writerow(["create", "jane.doe@example.com", "Jane Doe", "replace", '"Admin,IT,ClientA"'])
    w.writerow(["update", "john.smith@example.com", "", "replace", "ClientA"])
    w.writerow(["disable", "disabled.user@example.com", "", "", ""])
    w.writerow(["enable", "reenable.user@example.com", "", "", ""])
    w.writerow(["delete", "former.user@example.com", "", "", ""])

    # Excel-friendly UTF-8 BOM
    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    filename = f"{t.name}_import_template.csv".replace(" ", "_")
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(content=csv_bytes, headers=headers)

@router.get("/targets/{target_id}/export.csv")
def target_export_csv(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    if t.auth_mode != "enterprise_hmac":
        return Response("Export is implemented for enterprise_hmac targets only (for now).", status_code=400)

    client = build_client(t)
    orgs = client.list_organizations()
    chosen = choose_org(orgs, t.org_name)
    org_id = chosen.get("id")
    if not org_id:
        return Response("Chosen org did not include an 'id' field.", status_code=500)

    users = client.list_users(org_id)
    if not isinstance(users, list):
        return Response("Unexpected user list format from target.", status_code=500)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["action", "email", "username", "groups_mode", "groups", "status"])

    for u in users:
        username = (u.get("name") or "").strip()
        email = (u.get("email") or "").strip()

        groups = u.get("groups") or []
        if isinstance(groups, list):
            groups_str = ",".join([str(g).strip() for g in groups if str(g).strip()])
        else:
            groups_str = str(groups).strip()

        disabled = bool(u.get("disabled", False))
        w.writerow(["", email, username, "replace", groups_str, "disabled" if disabled else "active"])

    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    filename = f"{t.name}_users.csv".replace(" ", "_")
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(content=csv_bytes, headers=headers)


@router.post("/targets/{target_id}/import/preview")
async def target_import_preview(request: Request, target_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    if t.auth_mode != "enterprise_hmac":
        return _templates(request).TemplateResponse(
            "import_preview.html",
            {
                "request": request,
                "target": t,
                "error": "Preview is implemented for enterprise_hmac targets only (for now).",
                "summary": None,
                "items": None,
                "job_id": None,
                "batch_id": None,
                "preview_sha256": None,
                "can_apply": False,
                "apply_disabled_reason": "enterprise_hmac only",
                "apply_result": None,
            "warn": warn,
            "warn_msgs": warn_msgs,
            },
        )

    csv_bytes = await file.read()
    csv_sha = sha256_hex(csv_bytes)

    client = build_client(t)
    orgs = client.list_organizations()
    chosen = choose_org(orgs, t.org_name)
    org_id = chosen.get("id")
    if not org_id:
        return _templates(request).TemplateResponse(
            "import_preview.html",
            {
                "request": request,
                "target": t,
                "error": "Chosen org did not include an 'id' field.",
                "summary": None,
                "items": None,
                "job_id": None,
                "batch_id": None,
                "preview_sha256": None,
                "can_apply": False,
                "apply_disabled_reason": "org error",
                "apply_result": None,
            },
        )

    users = client.list_users(org_id)
    if not isinstance(users, list):
        return _templates(request).TemplateResponse(
            "import_preview.html",
            {
                "request": request,
                "target": t,
                "error": "Unexpected user list format from target.",
                "summary": None,
                "items": None,
                "job_id": None,
                "batch_id": None,
                "preview_sha256": None,
                "can_apply": False,
                "apply_disabled_reason": "user list error",
                "apply_result": None,
            },
        )

    try:
        _job_id, summary, items_ui, items_full = preview_csv_against_users(csv_bytes, users)
    except Exception as e:
        return _templates(request).TemplateResponse(
            "import_preview.html",
            {
                "request": request,
                "target": t,
                "error": str(e),
                "summary": None,
                "items": None,
                "job_id": None,
                "batch_id": None,
                "preview_sha256": None,
                "can_apply": False,
                "apply_disabled_reason": "preview error",
                "apply_result": None,
            },
        )

    plan_for_hash = [
        {
            "row": it.row,
            "action": it.action,
            "email": it.email,
            "username": it.username,
            "status": it.status,
            "before": it.before,
            "after": it.after,
            "error": it.error,
            "desired": it.desired,
            "diff": it.diff,
            "will_apply": it.will_apply,
        }
        for it in items_full
    ]
    preview_sha = stable_json_hash(plan_for_hash)

    actor = get_actor_from_request(request)

    batch = ImportBatch(
        target_id=t.id,
        created_by=actor,
        status="previewed",
        csv_sha256=csv_sha,
        csv_bytes=csv_bytes,
        preview_sha256=preview_sha,
        summary={
            "total_rows": summary.total_rows,
            "actioned_rows": summary.actioned_rows,
            "creates": summary.creates,
            "updates": summary.updates,
            "disables": summary.disables,
            "enables": summary.enables,
            "deletes": summary.deletes,
            "clears": summary.clears,
            "skips": summary.skips,
            "errors": summary.errors,
        },
        meta={
            "org_id": org_id,
            "org_name": chosen.get("name"),
        },
    )
    db.add(batch)
    db.commit()

    for it in items_full:
        r = ImportRow(
            batch_id=batch.id,
            row_num=it.row,
            action=it.action,
            email=it.email,
            username=it.username,
            status=it.status,
            before=it.before,
            after=it.after,
            error=it.error,
            desired=it.desired or {},
            diff=it.diff or {},
            will_apply=bool(it.will_apply and it.status == "ok"),
        )
        db.add(r)
    db.commit()

    can_apply = (summary.actioned_rows > 0) and (summary.errors == 0)
    apply_disabled_reason = "Apply enabled only when Actioned rows > 0 and Errors == 0."

    # Guardrails (warnings only): highlight if thresholds are met/exceeded
    app_settings = get_settings(db)
    warn = {
        "creates": (app_settings.warn_create_count > 0 and summary.creates >= app_settings.warn_create_count),
        "disables": (app_settings.warn_disable_count > 0 and summary.disables >= app_settings.warn_disable_count),
        "deletes": (app_settings.warn_delete_count > 0 and summary.deletes >= app_settings.warn_delete_count),
        "clears": (app_settings.warn_group_clear_count > 0 and summary.clears >= app_settings.warn_group_clear_count),
    }

    warn_msgs = []
    if warn["disables"]:
        warn_msgs.append(f"Disables in batch: {summary.disables} (warn threshold: {app_settings.warn_disable_count})")
    if warn["deletes"]:
        warn_msgs.append(f"Deletes in batch: {summary.deletes} (warn threshold: {app_settings.warn_delete_count})")
    if warn["clears"]:
        warn_msgs.append(f"Group clears in batch: {summary.clears} (warn threshold: {app_settings.warn_group_clear_count})")
    if warn["creates"]:
        warn_msgs.append(f"Creates in batch: {summary.creates} (warn threshold: {app_settings.warn_create_count})")

    return _templates(request).TemplateResponse(
        "import_preview.html",
        {
            "request": request,
            "target": t,
            "error": None,
            "summary": summary,
            "items": items_ui,
            "warn": warn,
            "warn_msgs": warn_msgs,
            "job_id": batch.id,
            "batch_id": batch.id,
            "preview_sha256": preview_sha,
            "can_apply": can_apply,
            "apply_disabled_reason": apply_disabled_reason,
            "apply_result": None,
        },
    )


@router.get("/targets/{target_id}/import/preview_report.csv")
def target_import_preview_report(request: Request, target_id: str, job: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    batch = db.query(ImportBatch).filter(ImportBatch.id == job, ImportBatch.target_id == t.id).first()
    if not batch:
        return Response("Preview report not found (batch id expired). Re-run preview.", status_code=404)

    rows = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).order_by(ImportRow.row_num.asc()).all()

    from ..importer.preview import PreviewItem  # type: ignore
    items = []
    for r in rows:
        items.append(PreviewItem(
            row=r.row_num,
            action=r.action,
            email=r.email,
            username=r.username,
            status=r.status,
            before=r.before,
            after=r.after,
            error=r.error,
            desired=r.desired,
            diff=r.diff,
            will_apply=r.will_apply,
        ))

    csv_bytes = preview_report_csv(items)
    filename = f"{t.name}_preview_report.csv".replace(" ", "_")

    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(content=csv_bytes, headers=headers)


@router.post("/targets/{target_id}/import/apply")
def target_import_apply(
    request: Request,
    target_id: str,
    batch_id: str = Form(...),
    preview_sha256: str = Form(...),
    confirm: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    if confirm != "yes":
        return Response("Confirmation checkbox is required.", status_code=400)

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id, ImportBatch.target_id == t.id).first()
    if not batch:
        return Response("Batch not found for this target. Re-run preview.", status_code=404)

    if batch.preview_sha256 != preview_sha256:
        return Response("Preview hash mismatch. Re-run preview.", status_code=400)

    if batch.status not in {"previewed", "failed"}:
        return Response(f"Batch status is '{batch.status}', cannot apply.", status_code=400)

    if int((batch.summary or {}).get("errors", 0)) != 0:
        return Response("Batch contains preview errors. Fix CSV and re-run preview.", status_code=400)

    if t.auth_mode != "enterprise_hmac":
        return Response("Apply is implemented for enterprise_hmac targets only (for now).", status_code=400)

    actor = get_actor_from_request(request)

    acquire_target_lock(db, t.id)
    try:
        batch.status = "applying"
        db.add(batch)
        db.commit()

        client = build_client(t)
        orgs = client.list_organizations()
        chosen = choose_org(orgs, t.org_name)
        org_id = chosen.get("id")
        if not org_id:
            raise RuntimeError("Chosen org did not include an 'id' field")

        users = client.list_users(org_id)
        if not isinstance(users, list):
            raise RuntimeError("Unexpected user list format from target")

        user_by_email: dict[str, dict[str, Any]] = {}
        for u in users:
            em = (u.get("email") or "").strip().lower()
            if em and em not in user_by_email:
                user_by_email[em] = u

        rows = db.query(ImportRow).filter(ImportRow.batch_id == batch.id).order_by(ImportRow.row_num.asc()).all()

        results = {"applied": 0, "skipped": 0, "failed": 0, "details": []}

        for r in rows:
            if not r.will_apply:
                r.apply_status = "skipped"
                r.apply_result = {"reason": "will_apply=false or status!=ok"}
                results["skipped"] += 1
                db.add(r)
                continue

            email = (r.email or "").strip().lower()
            action = (r.action or "").strip().lower()
            existing = user_by_email.get(email)

            try:
                if action == "create":
                    if existing:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "idempotent: already exists"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    name = (r.username or "").strip()
                    if not name:
                        raise RuntimeError("Create requires username")

                    groups = (r.desired or {}).get("groups") or []
                    resp = create_user(
                        client,
                        org_id,
                        name=name,
                        email=email,
                        groups=groups if t.supports_groups else None,
                        send_key_email=True,
                    )

                    db.add(AuditLog(
                        actor=actor,
                        target_id=t.id,
                        batch_id=batch.id,
                        row_id=r.id,
                        email=email,
                        operation="user.create",
                        success=True,
                        request={"email": email, "name": name, "groups": groups},
                        response={"result": resp},
                    ))

                    r.apply_status = "applied"
                    r.apply_result = {"result": resp}
                    r.applied_at = now_utc()
                    results["applied"] += 1

                elif action == "update":
                    if not existing:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "missing user for update; ignored"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    user_id = existing.get("id")
                    if not user_id:
                        raise RuntimeError("Existing user record missing id")

                    merged = dict(existing)

                    # Username is read-only for update; do NOT set merged["name"]

                    gm = ((r.desired or {}).get("groups_mode") or "").lower()
                    groups_cell = (r.desired or {}).get("groups_cell") or ""
                    desired_groups = (r.desired or {}).get("groups")

                    if t.supports_groups:
                        if gm == "clear":
                            merged["groups"] = []
                        elif gm == "replace":
                            if str(groups_cell) != "":
                                merged["groups"] = desired_groups or []
                        else:
                            pass  # blank/unknown => do nothing

                    # idempotent best-effort
                    if merged.get("groups") == existing.get("groups"):
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "idempotent: no change"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    resp = update_user_full(client, org_id, user_id, merged)

                    db.add(AuditLog(
                        actor=actor,
                        target_id=t.id,
                        batch_id=batch.id,
                        row_id=r.id,
                        email=email,
                        operation="user.update",
                        success=True,
                        request={"user_id": user_id},
                        response={"result": resp},
                    ))

                    r.apply_status = "applied"
                    r.apply_result = {"result": resp}
                    r.applied_at = now_utc()
                    results["applied"] += 1

                elif action == "disable":
                    if not existing:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "missing user for disable; ignored"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    user_id = existing.get("id")
                    if not user_id:
                        raise RuntimeError("Existing user record missing id")

                    if bool(existing.get("disabled", False)) is True:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "idempotent: already disabled"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    merged = dict(existing)
                    merged["disabled"] = True

                    resp = update_user_full(client, org_id, user_id, merged)

                    db.add(AuditLog(
                        actor=actor,
                        target_id=t.id,
                        batch_id=batch.id,
                        row_id=r.id,
                        email=email,
                        operation="user.disable",
                        success=True,
                        request={"user_id": user_id, "disabled": True},
                        response={"result": resp},
                    ))

                    r.apply_status = "applied"
                    r.apply_result = {"result": resp}
                    r.applied_at = now_utc()
                    results["applied"] += 1

                elif action == "enable":
                    if not existing:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "missing user for enable; ignored"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    user_id = existing.get("id")
                    if not user_id:
                        raise RuntimeError("Existing user record missing id")

                    if bool(existing.get("disabled", False)) is False:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "idempotent: already enabled"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    merged = dict(existing)
                    merged["disabled"] = False

                    resp = update_user_full(client, org_id, user_id, merged)

                    db.add(AuditLog(
                        actor=actor,
                        target_id=t.id,
                        batch_id=batch.id,
                        row_id=r.id,
                        email=email,
                        operation="user.enable",
                        success=True,
                        request={"user_id": user_id, "disabled": False},
                        response={"result": resp},
                    ))

                    r.apply_status = "applied"
                    r.apply_result = {"result": resp}
                    r.applied_at = now_utc()
                    results["applied"] += 1

                elif action == "delete":
                    if not settings.allow_delete:
                        r.apply_status = "failed"
                        r.apply_result = {"error": "ALLOW_DELETE=false"}
                        results["failed"] += 1
                        db.add(r)
                        continue

                    if not existing:
                        r.apply_status = "skipped"
                        r.apply_result = {"reason": "missing user for delete; ignored"}
                        results["skipped"] += 1
                        db.add(r)
                        continue

                    user_id = existing.get("id")
                    if not user_id:
                        raise RuntimeError("Existing user record missing id")

                    resp = delete_user(client, org_id, user_id)

                    db.add(AuditLog(
                        actor=actor,
                        target_id=t.id,
                        batch_id=batch.id,
                        row_id=r.id,
                        email=email,
                        operation="user.delete",
                        success=True,
                        request={"user_id": user_id},
                        response={"result": resp if isinstance(resp, dict) else {"text": str(resp)}},
                    ))

                    r.apply_status = "applied"
                    r.apply_result = {"result": resp}
                    r.applied_at = now_utc()
                    results["applied"] += 1

                else:
                    r.apply_status = "skipped"
                    r.apply_result = {"reason": f"unknown/unsupported action '{action}'"}
                    results["skipped"] += 1

            except Exception as e:
                results["failed"] += 1
                r.apply_status = "failed"
                r.apply_result = {"error": str(e)}

                db.add(AuditLog(
                    actor=actor,
                    target_id=t.id,
                    batch_id=batch.id,
                    row_id=r.id,
                    email=email,
                    operation=f"user.{action}",
                    success=False,
                    error=str(e),
                    request={"row": r.row_num, "action": action},
                    response={},
                ))

            db.add(r)
            results["details"].append({"row": r.row_num, "email": email, "action": action, "status": r.apply_status})

        batch.status = "applied" if results["failed"] == 0 else "failed"
        db.add(batch)
        db.commit()

        items_ui = []
        for rr in rows[:200]:
            items_ui.append({
                "row": rr.row_num,
                "action": rr.action,
                "email": rr.email,
                "username": rr.username,
                "status": rr.status,
                "before": rr.before,
                "after": rr.after,
                "error": rr.error,
            })

        class SummaryObj:
            pass
        s = SummaryObj()
        for k, v in (batch.summary or {}).items():
            setattr(s, k, v)

        return _templates(request).TemplateResponse(
            "import_preview.html",
            {
                "request": request,
                "target": t,
                "error": None,
                "summary": s,
                "items": items_ui,
                "job_id": batch.id,
                "batch_id": batch.id,
                "preview_sha256": batch.preview_sha256,
                "can_apply": False,
                "apply_disabled_reason": "Already applied.",
                "apply_result": json.dumps(results, indent=2),
            },
        )

    finally:
        try:
            release_target_lock(db, t.id)
            db.commit()
        except Exception:
            pass


@router.get("/targets/{target_id}/edit")
def target_edit_get(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    return _templates(request).TemplateResponse(
        "target_edit.html",
        {"request": request, "target": t, "error": None},
    )


@router.post("/targets/{target_id}/edit")
def target_edit_post(
    request: Request,
    target_id: str,
    name: str = Form(...),
    base_url: str = Form(...),
    auth_mode: str = Form(...),
    verify_tls: str = Form(default=""),
    supports_groups: str = Form(default=""),
    org_name: str = Form(default=""),
    api_token: str = Form(default=""),
    api_secret: str = Form(default=""),
    login_user: str = Form(default=""),
    login_pass: str = Form(default=""),
    db: Session = Depends(get_db),
):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    t.name = name.strip()
    t.base_url = base_url.strip()
    t.auth_mode = auth_mode
    t.verify_tls = (verify_tls == "on")
    t.supports_groups = (supports_groups == "on")
    t.org_name = org_name.strip() or None

    replace_creds = False
    new_creds = None

    if auth_mode == "enterprise_hmac":
        if api_token.strip() or api_secret.strip():
            if not api_token.strip() or not api_secret.strip():
                return _templates(request).TemplateResponse(
                    "target_edit.html",
                    {"request": request, "target": t, "error": "To update Enterprise credentials, provide BOTH API Token and API Secret."},
                )
            new_creds = {"api_token": api_token.strip(), "api_secret": api_secret.strip()}
            replace_creds = True

    elif auth_mode == "session_login":
        if login_user.strip() or login_pass:
            if not login_user.strip() or not login_pass:
                return _templates(request).TemplateResponse(
                    "target_edit.html",
                    {"request": request, "target": t, "error": "To update Session Login credentials, provide BOTH username and password."},
                )
            new_creds = {"username": login_user.strip(), "password": login_pass}
            replace_creds = True
    else:
        return _templates(request).TemplateResponse(
            "target_edit.html",
            {"request": request, "target": t, "error": "Invalid auth_mode."},
        )

    if replace_creds and new_creds is not None:
        t.credentials_enc = encrypt_str(json.dumps(new_creds))

    db.add(t)
    db.commit()
    return RedirectResponse(f"/targets/{t.id}", status_code=303)


@router.post("/targets/{target_id}/test")
def target_test_connection(request: Request, target_id: str, db: Session = Depends(get_db)):
    redir = require_login(request)
    if redir:
        return redir

    t = db.query(Target).filter(Target.id == target_id).first()
    if not t:
        return RedirectResponse("/targets", status_code=303)

    if t.auth_mode != "enterprise_hmac":
        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": None, "error": "Test is implemented for enterprise_hmac only (for now)."},
        )

    try:
        client = build_client(t)
        orgs = client.list_organizations()
        chosen = choose_org(orgs, t.org_name)
        org_id = chosen.get("id")
        org_name = chosen.get("name")

        if not org_id:
            raise RuntimeError("Chosen org did not include an 'id' field")

        users = client.list_users(org_id)

        result = {
            "org_name": org_name,
            "org_id": org_id,
            "user_count": len(users) if isinstance(users, list) else None,
            "sample_users": [
                {
                    "name": u.get("name"),
                    "email": u.get("email"),
                    "disabled": u.get("disabled"),
                    "groups": u.get("groups"),
                }
                for u in (users[:10] if isinstance(users, list) else [])
            ],
        }

        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": result, "error": None},
        )

    except Exception as e:
        return _templates(request).TemplateResponse(
            "target_detail.html",
            {"request": request, "target": t, "result": None, "error": str(e)},
        )
