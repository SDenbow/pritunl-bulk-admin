import csv
import io
import uuid
from dataclasses import dataclass, asdict
from typing import Any

VALID_ACTIONS = {"skip", "create", "update", "upsert", "disable", "delete", ""}

@dataclass
class PreviewItem:
    row: int
    action: str
    email: str
    username: str | None
    status: str  # ok|skip|error
    before: str
    after: str
    error: str | None

@dataclass
class PreviewSummary:
    total_rows: int = 0
    actioned_rows: int = 0
    creates: int = 0
    updates: int = 0
    disables: int = 0
    deletes: int = 0
    clears: int = 0
    skips: int = 0
    errors: int = 0


def _norm(s: Any) -> str:
    return (str(s).strip() if s is not None else "").strip()


def _split_groups(groups_str: str) -> list[str]:
    # CSV cell is a single string "A,B,C" (quoted as needed by CSV)
    parts = [p.strip() for p in groups_str.split(",")] if groups_str else []
    # dedupe while preserving order
    out = []
    seen = set()
    for p in parts:
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def _fmt_state(user: dict[str, Any] | None) -> str:
    if not user:
        return "(not found)"
    groups = user.get("groups")
    if isinstance(groups, list):
        groups = ",".join([str(g) for g in groups])
    return f"email={user.get('email','')}, name={user.get('name','')}, disabled={user.get('disabled', False)}, groups={groups or ''}"


def build_user_index_by_email(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for u in users:
        email = _norm(u.get("email")).lower()
        if not email:
            continue
        # if duplicates exist, keep first; duplicates will be flagged later if needed
        if email not in idx:
            idx[email] = u
    return idx


def preview_csv_against_users(csv_bytes: bytes, existing_users: list[dict[str, Any]]) -> tuple[str, PreviewSummary, list[PreviewItem], list[PreviewItem]]:
    """
    Returns:
      job_id, summary, items_for_ui (first 200), full_items_for_report
    """
    job_id = uuid.uuid4().hex
    summary = PreviewSummary()

    user_by_email = build_user_index_by_email(existing_users)

    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    required_cols = {"action", "email"}
    cols = set([c.strip().lower() for c in (reader.fieldnames or [])])

    if not required_cols.issubset(cols):
        missing = ", ".join(sorted(required_cols - cols))
        raise ValueError(f"CSV missing required columns: {missing}. Required: action,email")

    items: list[PreviewItem] = []

    for i, row in enumerate(reader, start=2):  # header is line 1
        summary.total_rows += 1

        action = _norm(row.get("action")).lower()
        email = _norm(row.get("email")).lower()
        username = _norm(row.get("username")) or None
        groups_mode = _norm(row.get("groups_mode")).lower() or "replace"
        groups_cell = _norm(row.get("groups"))

        if action not in VALID_ACTIONS:
            summary.errors += 1
            items.append(PreviewItem(i, action, email, username, "error", "", "", f"Invalid action '{action}'"))
            continue

        if action == "" or action == "skip":
            summary.skips += 1
            items.append(PreviewItem(i, action or "skip", email, username, "skip", "", "", None))
            continue

        if not email:
            summary.errors += 1
            items.append(PreviewItem(i, action, email, username, "error", "", "", "Missing email"))
            continue

        existing = user_by_email.get(email)

        # Build proposed changes (preview only)
        proposed = {}
        before_str = _fmt_state(existing)
        after_str = before_str

        # groups semantics:
        # - groups_mode=clear -> groups becomes []
        # - groups_mode=replace -> only replace if groups cell non-empty
        proposed_groups = None
        if action in {"create", "update", "upsert"}:
            if groups_mode == "clear":
                proposed_groups = []
                summary.clears += 1
            elif groups_mode == "replace":
                if groups_cell != "":
                    proposed_groups = _split_groups(groups_cell)
            else:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", before_str, "", f"Invalid groups_mode '{groups_mode}'"))
                continue

        if action == "create":
            summary.actioned_rows += 1
            summary.creates += 1
            if existing:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", before_str, "", "User already exists (email match)"))
                continue
            if not username:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", "(not found)", "", "Create requires username"))
                continue
            after_str = f"email={email}, name={username}, disabled=False, groups={','.join(proposed_groups or [])}"
            items.append(PreviewItem(i, action, email, username, "ok", "(not found)", after_str, None))
            continue

        if action == "update":
            summary.actioned_rows += 1
            summary.updates += 1
            if not existing:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", "(not found)", "", "User not found for update (email match)"))
                continue

            # preview update: username optional, groups optional per rules
            new_name = username if username else _norm(existing.get("name"))
            disabled = bool(existing.get("disabled", False))
            final_groups = existing.get("groups") if proposed_groups is None else proposed_groups
            if isinstance(final_groups, list):
                final_groups_str = ",".join([str(g) for g in final_groups])
            else:
                final_groups_str = _norm(final_groups)

            after_str = f"email={email}, name={new_name}, disabled={disabled}, groups={final_groups_str}"
            items.append(PreviewItem(i, action, email, username, "ok", before_str, after_str, None))
            continue

        if action == "upsert":
            summary.actioned_rows += 1
            if existing:
                summary.updates += 1
                new_name = username if username else _norm(existing.get("name"))
                disabled = bool(existing.get("disabled", False))
                final_groups = existing.get("groups") if proposed_groups is None else proposed_groups
                if isinstance(final_groups, list):
                    final_groups_str = ",".join([str(g) for g in final_groups])
                else:
                    final_groups_str = _norm(final_groups)
                after_str = f"email={email}, name={new_name}, disabled={disabled}, groups={final_groups_str}"
                items.append(PreviewItem(i, action, email, username, "ok", before_str, after_str, None))
            else:
                summary.creates += 1
                if not username:
                    summary.errors += 1
                    items.append(PreviewItem(i, action, email, username, "error", "(not found)", "", "Upsert(create) requires username"))
                    continue
                after_str = f"email={email}, name={username}, disabled=False, groups={','.join(proposed_groups or [])}"
                items.append(PreviewItem(i, action, email, username, "ok", "(not found)", after_str, None))
            continue

        if action == "disable":
            summary.actioned_rows += 1
            summary.disables += 1
            if not existing:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", "(not found)", "", "User not found for disable (email match)"))
                continue
            after_str = f"email={email}, name={_norm(existing.get('name'))}, disabled=True, groups={','.join(existing.get('groups') or []) if isinstance(existing.get('groups'), list) else _norm(existing.get('groups'))}"
            items.append(PreviewItem(i, action, email, username, "ok", before_str, after_str, None))
            continue

        if action == "delete":
            summary.actioned_rows += 1
            summary.deletes += 1
            if not existing:
                summary.errors += 1
                items.append(PreviewItem(i, action, email, username, "error", "(not found)", "", "User not found for delete (email match)"))
                continue
            after_str = "(deleted)"
            items.append(PreviewItem(i, action, email, username, "ok", before_str, after_str, None))
            continue

        # Should never reach
        summary.errors += 1
        items.append(PreviewItem(i, action, email, username, "error", before_str, "", "Unhandled action"))

    # Derive skips/errors counts
    summary.errors = sum(1 for it in items if it.status == "error")
    summary.skips = sum(1 for it in items if it.status == "skip")

    # UI limit
    items_ui = items[:200]
    return job_id, summary, items_ui, items


def preview_report_csv(items: list[PreviewItem]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "action", "email", "username", "status", "before", "after", "error"])
    for it in items:
        w.writerow([it.row, it.action, it.email, it.username or "", it.status, it.before, it.after, it.error or ""])
    return buf.getvalue().encode("utf-8")
