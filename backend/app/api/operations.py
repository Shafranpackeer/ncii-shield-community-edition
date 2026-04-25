"""Operational API for the v1 case lifecycle.

These endpoints provide deterministic local implementations for provider-backed
steps: contact resolution, email drafting, approval, send tracking, escalation,
timeline, and case kill switch.
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Action, AuditLog, Case, Contact, Target
from app.models.action import ActionStatus, ActionType
from app.models.case import CaseStatus
from app.models.target import TargetStatus
from app.utils.audit import create_audit_log
from app.utils.runtime_settings import get_runtime_setting

router = APIRouter(prefix="/operations", tags=["operations"])
_EMAIL_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "emails"
_EMAIL_TEMPLATE_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


class DraftRequest(BaseModel):
    action_type: ActionType = ActionType.EMAIL_INITIAL
    jurisdiction: str = "US"


class ReviewActionRequest(BaseModel):
    decision: str
    edited_subject: Optional[str] = None
    edited_body: Optional[str] = None
    admin_id: str = "local-admin"


class ManualContactRequest(BaseModel):
    email: str
    method_found: str = "manual_override"
    confidence: float = 1.0


def _hash_input(value: str) -> int:
    hash_value = 2166136261
    for char in value:
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


def _encode_reference(value: int, length: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    output = []
    current = value or 1
    for index in range(length):
        output.append(alphabet[current % len(alphabet)])
        current = current // len(alphabet) or _hash_input(f"{value}-{index}")
    return "".join(output)


def _case_reference(case: Case) -> str:
    created_at = case.created_at or datetime.utcnow()
    period = f"{created_at.year}{created_at.month:02d}"
    suffix = _encode_reference(_hash_input(f"{period}-{case.id}"))
    return f"NCII-{period}-{suffix}"


def _sender_details() -> Dict[str, str]:
    contact_email = (
        get_runtime_setting("NOTICE_CONTACT_EMAIL")
        or get_runtime_setting("RESEND_FROM_EMAIL")
        or "takedown@example.com"
    )
    contact_domain = contact_email.split("@", 1)[1] if "@" in contact_email else ""
    website = (
        get_runtime_setting("NOTICE_WEBSITE")
        or get_runtime_setting("NOTICE_ORGANIZATION_URL")
        or (f"https://{contact_domain}" if contact_domain else "")
        or ""
    )
    return {
        "client": get_runtime_setting("NOTICE_CLIENT_NAME", "the client"),
        "name": get_runtime_setting("NOTICE_SENDER_NAME", "NCII Shield Takedown Team"),
        "title": get_runtime_setting("NOTICE_SENDER_TITLE", "Authorized Abuse Reporting Contact"),
        "organization": get_runtime_setting("NOTICE_ORGANIZATION", "NCII Shield"),
        "email": contact_email,
        "website": website,
    }


def _signature_block() -> str:
    sender = _sender_details()
    lines = [
        "Sincerely,",
        sender["name"],
        sender["title"],
        sender["organization"],
        sender["email"],
    ]
    if sender["website"]:
        lines.append(sender["website"])
    return "\n".join(lines)


def _apply_sender_details(body: str) -> str:
    signature = _signature_block()
    sender = _sender_details()
    cleaned = body.replace("[Your Name]", sender["name"])
    cleaned = cleaned.replace("[Your Title]", sender["title"])
    cleaned = cleaned.replace("[Your Organization]", sender["organization"])
    cleaned = cleaned.replace("[Client Name]", sender["client"])
    if "Sincerely," not in cleaned:
        cleaned = f"{cleaned.rstrip()}\n\n{signature}"
    return cleaned


def _strip_prompt_echo(body: str) -> str:
    stop_markers = (
        "case reference:",
        "client name:",
        "target url:",
        "recipient:",
        "jurisdiction:",
        "authorization note:",
        "admin note:",
    )

    cleaned_lines = []
    for line in body.splitlines():
        stripped = line.strip().lower()
        if any(stripped.startswith(marker) for marker in stop_markers):
            break
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or body.strip()


def _draft_is_complete(body: str) -> bool:
    normalized = body.lower()
    required_markers = (
        "dear ",
        "we act as the authorized representative",
        "target url:",
        "recipient",
        "sincerely,",
    )
    return all(marker in normalized for marker in required_markers)


def _pick_template_variant(seed: str, variants: List[Dict[str, str]]) -> Dict[str, str]:
    if not variants:
        return {}
    return variants[_hash_input(seed) % len(variants)]


def _site_display_name(target: Target) -> str:
    parsed = urlparse(target.url)
    hostname = (parsed.hostname or "site").removeprefix("www.")
    root = hostname.split(".")[0]
    readable = root.replace("-", " ").strip()
    if not readable:
        return "Site"
    return " ".join(part.capitalize() for part in readable.split())


def _recipient_string(contact: Contact) -> str:
    recipient = contact.email
    if isinstance(recipient, list):
        return ", ".join(recipient)
    return str(recipient)


def _template_context(case: Case, target: Target, contact: Contact, data: DraftRequest) -> Dict[str, str]:
    sender = _sender_details()
    next_action = _next_action_type(data.action_type)
    next_label = {
        ActionType.EMAIL_FOLLOWUP: "Follow-up notice",
        ActionType.EMAIL_HOSTING: "Hosting escalation",
        ActionType.EMAIL_REGISTRAR: "Registrar escalation",
        ActionType.MANUAL_ESCALATION: "Manual escalation",
        ActionType.CHECK_REMOVAL: "Verification request",
        None: "No further action",
    }.get(next_action, "No further action")
    next_recipient = {
        ActionType.EMAIL_FOLLOWUP: "current abuse recipient",
        ActionType.EMAIL_HOSTING: "hosting provider abuse desk",
        ActionType.EMAIL_REGISTRAR: "domain registrar abuse desk",
        ActionType.MANUAL_ESCALATION: "manual review queue",
        ActionType.CHECK_REMOVAL: "verification queue",
        None: "none",
    }.get(next_action, "none")
    next_date = _schedule_after_action(data.action_type, datetime.utcnow())
    return {
        "case_id": case.id,
        "case_reference": _case_reference(case),
        "target_url": target.url,
        "target_domain": _domain_for_target(target),
        "site_name": _site_display_name(target),
        "recipient_email": contact.email,
        "recipient_list": _recipient_string(contact),
        "current_date": datetime.utcnow().date().isoformat(),
        "date_discovered": (target.created_at or case.created_at or datetime.utcnow()).date().isoformat(),
        "deadline_iso8601": next_date.isoformat() if next_date else "",
        "deadline_human": "48 hours" if data.action_type == ActionType.EMAIL_INITIAL else "24 hours",
        "escalation_next_step": next_label,
        "escalation_next_recipient": next_recipient,
        "escalation_next_date": next_date.isoformat() if next_date else "",
        "response_email": sender["email"],
        "victim_authorization_reference": case.authorization_doc or "authorization on file",
        "legal_basis": "DMCA",
        "sender_name": sender["name"],
        "sender_title": sender["title"],
        "sender_organization": sender["organization"],
        "sender_email": sender["email"],
        "sender_website": sender["website"],
        "signature_block": _signature_block(),
    }


def _render_template_text(text: str, context: Dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, "")
        return "" if value is None else str(value)

    return _EMAIL_TEMPLATE_PATTERN.sub(replace, text)


def _render_email_template(template_key: str, context: Dict[str, str]) -> Dict[str, str]:
    subject_path = _EMAIL_TEMPLATE_ROOT / template_key / "subject.txt.j2"
    body_path = _EMAIL_TEMPLATE_ROOT / template_key / "body.txt.j2"
    if not subject_path.exists() or not body_path.exists():
        raise HTTPException(status_code=500, detail=f"Missing email template: {template_key}")

    subject = _render_template_text(subject_path.read_text(encoding="utf-8"), context).strip()
    body = _render_template_text(body_path.read_text(encoding="utf-8"), context).strip()
    return {
        "template_name": template_key.replace("/", "_"),
        "subject": subject,
        "body": body,
        "html": _render_email_html(subject, body),
    }


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_email_html(subject: str, body: str) -> str:
    safe_subject = _html_escape(subject)
    safe_body = _html_escape(body).replace("\n", "<br>")
    return (
        "<html><body>"
        f"<p><strong>{safe_subject}</strong></p>"
        f"<p>{safe_body}</p>"
        "</body></html>"
    )


def _domain_for_target(target: Target) -> str:
    parsed = urlparse(target.url)
    return parsed.hostname or "unknown-domain"


def _abuse_address_for_domain(domain: str) -> str:
    clean_domain = domain.lower().removeprefix("www.")
    if not clean_domain or "." not in clean_domain:
        return "abuse@example.invalid"
    return f"abuse@{clean_domain}"


def _normalize_obfuscated_emails(text: str) -> str:
    normalized = text
    replacements = [
        (r"\s*(?:\[|\()\s*at\s*(?:\]|\))\s*", "@"),
        (r"\s+(?:at)\s+", "@"),
        (r"\s*(?:\[|\()\s*dot\s*(?:\]|\))\s*", "."),
        (r"\s+(?:dot)\s+", "."),
    ]
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def _extract_emails(text: str) -> List[str]:
    normalized = _normalize_obfuscated_emails(text)
    matches = re.findall(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        normalized,
        flags=re.IGNORECASE,
    )
    deduped = []
    for email in matches:
        clean_email = email.strip(".,;:()[]<>").lower()
        if clean_email not in deduped:
            deduped.append(clean_email)
    return deduped


def _decode_cloudflare_email(cfemail: str) -> Optional[str]:
    try:
        key = int(cfemail[:2], 16)
        chars = []
        for index in range(2, len(cfemail), 2):
            chars.append(chr(int(cfemail[index:index + 2], 16) ^ key))
        return "".join(chars)
    except Exception:
        return None


def _extract_cloudflare_emails(text: str) -> List[str]:
    matches = re.findall(r"data-cfemail=\"([0-9a-fA-F]+)\"", text)
    decoded = []
    for match in matches:
        email = _decode_cloudflare_email(match)
        if email and email not in decoded:
            decoded.append(email.lower())
    return decoded


def _score_contact_email(email: str, source_url: str) -> float:
    score = 0.7
    local_part = email.split("@", 1)[0]
    source = source_url.lower()
    if any(token in local_part for token in ["dmca", "remove", "copyright", "legal"]):
        score += 0.25
    elif any(token in local_part for token in ["abuse", "support", "contact"]):
        score += 0.15
    if any(token in source for token in ["dmca", "contact", "legal", "terms", "2257"]):
        score += 0.05
    return min(score, 1.0)


def _contact_priority(item: Dict[str, object]) -> tuple:
    method_found = str(item.get("method_found") or "")
    confidence = float(item.get("confidence") or 0.0)
    bias = 0.0
    lowered = method_found.lower()
    if "/dmca" in lowered or "dmca" in lowered or "copyright" in lowered:
        bias += 0.2
    elif any(token in lowered for token in ["/contacts", "/contact", "legal", "terms"]):
        bias += 0.1
    return (confidence + bias, confidence)


def _discover_contact_emails(target: Target) -> List[Dict[str, object]]:
    parsed = urlparse(target.url)
    if not parsed.scheme or not parsed.netloc:
        return None

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    contact_paths = [
        "/contacts/",
        "/contacts",
        "/contact/",
        "/contact",
        "/dmca/",
        "/dmca",
        "/report/",
        "/report",
        "/privacy/",
        "/privacy",
        "/terms/",
        "/terms",
        "/legal/",
        "/legal",
        "/about/",
        "/about",
        "/support/",
        "/support",
        "/copyright/",
        "/copyright",
        "/imprint/",
        "/imprint",
        "/help/",
        "/help",
        "/abuse/",
        "/abuse",
        "/2257/",
        "/2257",
    ]
    candidate_urls = [
        target.url,
    ]
    candidate_urls.extend(urljoin(base_url, path) for path in contact_paths)

    seen = set()
    best_by_email: Dict[str, Dict[str, object]] = {}
    headers = {
        "User-Agent": "NCII Shield contact resolver",
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
        for url in candidate_urls:
            if url in seen:
                continue
            seen.add(url)
            try:
                response = client.get(url)
                if response.status_code >= 400 or not response.text:
                    continue
            except Exception:
                continue

            candidate_emails = _extract_cloudflare_emails(response.text) + _extract_emails(response.text)
            for email in candidate_emails:
                score = _score_contact_email(email, str(response.url))
                current = best_by_email.get(email)
                if not current or score > current["confidence"]:
                    best_by_email[email] = {
                        "email": email,
                        "method_found": f"scraped:{response.url}",
                        "confidence": score,
                    }
    return sorted(best_by_email.values(), key=_contact_priority, reverse=True)


def _schedule_after_action(action_type: ActionType, now: datetime) -> Optional[datetime]:
    if action_type == ActionType.EMAIL_INITIAL:
        return now + timedelta(days=2)
    if action_type == ActionType.EMAIL_FOLLOWUP:
        return now + timedelta(days=1)
    if action_type == ActionType.EMAIL_HOSTING:
        return now + timedelta(days=2)
    if action_type == ActionType.EMAIL_REGISTRAR:
        return now + timedelta(days=2)
    return None


def _email_template_for_action(
    case: Case,
    target: Target,
    contact: Contact,
    data: DraftRequest,
) -> Dict[str, str]:
    context = _template_context(case, target, contact, data)
    action_type = data.action_type
    template_choices = {
        ActionType.EMAIL_INITIAL: [
            "day0_initial/standard",
            "day0_initial/cloudflare",
            "day0_initial/smallhost",
        ],
        ActionType.EMAIL_FOLLOWUP: [
            "day2_followup/standard",
            "day2_followup/silence",
        ],
        ActionType.EMAIL_HOSTING: [
            "day3_hosting/standard",
        ],
        ActionType.EMAIL_REGISTRAR: [
            "day5_registrar/standard",
        ],
        ActionType.MANUAL_ESCALATION: [
            "day7_final_warning/standard",
        ],
        ActionType.CHECK_REMOVAL: [
            "day7_verification/standard",
        ],
    }
    templates = template_choices.get(action_type, ["day0_initial/standard"])
    template_key = _pick_template_variant(
        f"{case.id}:{target.id}:{action_type.value}",
        [{"template_name": key} for key in templates],
    ).get("template_name", templates[0])
    return _render_email_template(template_key, context)


def _next_action_type(action_type: ActionType) -> Optional[ActionType]:
    ladder = {
        ActionType.EMAIL_INITIAL: ActionType.EMAIL_FOLLOWUP,
        ActionType.EMAIL_FOLLOWUP: ActionType.EMAIL_HOSTING,
        ActionType.EMAIL_HOSTING: ActionType.EMAIL_REGISTRAR,
        ActionType.EMAIL_REGISTRAR: ActionType.MANUAL_ESCALATION,
    }
    return ladder.get(action_type)


def _draft_email(case: Case, target: Target, contact: Contact, data: DraftRequest) -> Dict[str, str]:
    return _email_template_for_action(case, target, contact, data)


def _send_email(payload: Dict, action_id: int) -> Dict[str, str]:
    api_key = get_runtime_setting("RESEND_API_KEY")
    from_email = get_runtime_setting("RESEND_FROM_EMAIL")
    recipient = payload.get("recipient")
    draft = payload.get("draft") or {}
    draft_body = _strip_prompt_echo(str(draft.get("body") or ""))
    recipients = recipient if isinstance(recipient, list) else ([recipient] if recipient else [])

    if not api_key or not from_email or not recipients:
        now = datetime.utcnow()
        return {
            "status": "sent",
            "provider": "local_outbox",
            "message_id": f"local-{action_id}-{int(now.timestamp())}",
            "sent_at": now.isoformat(),
        }

    response = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_email,
            "to": recipients,
            "subject": draft.get("subject", f"NCII Shield action {action_id}"),
            "text": draft_body,
            "html": draft.get("html"),
            "tags": [
                {"name": "action_id", "value": str(action_id)},
            ],
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    now = datetime.utcnow()
    return {
        "status": "sent",
        "provider": "resend",
        "message_id": data.get("id", f"resend-{action_id}"),
        "sent_at": now.isoformat(),
    }


def _get_tag_value(tags: object, name: str) -> Optional[str]:
    if isinstance(tags, dict):
        value = tags.get(name)
        return str(value) if value is not None else None
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, dict) and tag.get("name") == name:
                value = tag.get("value")
                return str(value) if value is not None else None
    return None


@router.post("/webhooks/resend")
async def resend_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Resend email webhooks and persist delivery/open state."""
    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data") or {}
    action_id = _get_tag_value(data.get("tags"), "action_id")

    if not action_id:
        return {"success": True, "ignored": True}

    action = db.query(Action).filter(Action.id == int(action_id)).first()
    if not action:
        return {"success": True, "ignored": True}

    current_payload = dict(action.payload or {})
    tracking = dict(current_payload.get("tracking") or {})

    if event_type == "email.opened":
        tracking["opened_at"] = payload.get("created_at") or datetime.utcnow().isoformat()
        tracking["open_count"] = int(tracking.get("open_count") or 0) + 1
    elif event_type == "email.delivered":
        tracking["delivered_at"] = payload.get("created_at") or datetime.utcnow().isoformat()
        tracking["delivery_status"] = "delivered"
    elif event_type == "email.bounced":
        tracking["delivery_status"] = "bounced"
        tracking["bounce"] = data.get("bounce")
    elif event_type == "email.clicked":
        tracking["clicked_at"] = payload.get("created_at") or datetime.utcnow().isoformat()
        tracking["click_count"] = int(tracking.get("click_count") or 0) + 1
    else:
        tracking["last_event"] = event_type

    current_payload["tracking"] = tracking
    current_payload["resend_event"] = payload
    action.payload = current_payload

    create_audit_log(
        db,
        entity_type="action",
        entity_id=action.id,
        action=f"resend_{event_type.replace('.', '_') if event_type else 'webhook'}",
        new_value={
            "action_id": action.id,
            "event_type": event_type,
            "tracking": tracking,
        },
        request=request,
    )
    db.commit()
    return {"success": True}


@router.post("/targets/{target_id}/resolve-contact")
async def resolve_contact(target_id: int, request: Request, db: Session = Depends(get_db)):
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    discovered = _discover_contact_emails(target)
    domain = _domain_for_target(target)
    if not discovered:
        discovered = [
            {
                "email": _abuse_address_for_domain(domain),
                "method_found": "domain_abuse_fallback",
                "confidence": 0.65,
            }
        ]

    contacts = []
    for item in discovered[:2]:
        email = str(item["email"])
        method_found = str(item["method_found"])
        confidence = float(item["confidence"])
        contact = db.query(Contact).filter(Contact.target_id == target_id, Contact.email == email).first()
        if not contact:
            contact = Contact(
                target_id=target_id,
                email=email,
                method_found=method_found,
                confidence=confidence,
            )
            db.add(contact)
            db.flush()
        contacts.append(contact)

    contact = contacts[0]

    create_audit_log(
        db,
        entity_type="target",
        entity_id=target_id,
        action="contact_resolved",
        new_value={
            "email": contact.email,
            "method_found": contact.method_found,
            "confidence": contact.confidence,
            "alternate_contacts": [item.email for item in contacts[1:]],
        },
        request=request,
    )
    db.commit()
    db.refresh(contact)
    return {
        "primary_contact": {
            "id": contact.id,
            "target_id": contact.target_id,
            "email": contact.email,
            "method_found": contact.method_found,
            "confidence": contact.confidence,
            "created_at": contact.created_at,
        },
        "alternate_contacts": [
            {
                "id": item.id,
                "target_id": item.target_id,
                "email": item.email,
                "method_found": item.method_found,
                "confidence": item.confidence,
                "created_at": item.created_at,
            }
            for item in contacts[1:]
        ],
    }


@router.post("/targets/{target_id}/contacts")
async def add_manual_contact(target_id: int, data: ManualContactRequest, request: Request, db: Session = Depends(get_db)):
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    contact = Contact(
        target_id=target_id,
        email=data.email,
        method_found=data.method_found,
        confidence=data.confidence,
    )
    db.add(contact)
    db.flush()
    create_audit_log(
        db,
        entity_type="contact",
        entity_id=contact.id,
        action="manual_contact_added",
        new_value=data.model_dump(),
        request=request,
    )
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/targets/{target_id}/draft")
async def create_email_draft(target_id: int, data: DraftRequest, request: Request, db: Session = Depends(get_db)):
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    case = db.query(Case).filter(Case.id == target.case_id).first()
    if not case or case.status != CaseStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Case must be active before drafting outbound actions")

    contact = db.query(Contact).filter(Contact.target_id == target_id).order_by(Contact.confidence.desc()).first()
    if not contact:
        raise HTTPException(status_code=400, detail="Resolve or add a contact before drafting")

    extra_contacts = db.query(Contact).filter(
        Contact.target_id == target_id,
        Contact.email != contact.email,
    ).order_by(Contact.confidence.desc()).all()
    recipient_list = [contact.email] + [entry.email for entry in extra_contacts[:1]]

    draft = _draft_email(case, target, contact, data)
    action = Action(
        target_id=target_id,
        type=data.action_type,
        status=ActionStatus.PENDING,
        payload={
            "recipient": recipient_list,
            "draft": draft,
            "jurisdiction": data.jurisdiction,
            "draft_provider": "template_library",
            "send_provider": "resend" if get_runtime_setting("RESEND_API_KEY") else "local_outbox",
            "recipients_resolved": recipient_list,
            "template_name": draft.get("template_name"),
        },
    )
    db.add(action)
    db.flush()
    draft["html"] = _render_email_html(draft["subject"], draft["body"])
    action.payload["draft"] = draft
    action.payload["tracking"] = {"open_tracking_enabled": True, "provider": "resend"}
    create_audit_log(
        db,
        entity_type="action",
        entity_id=action.id,
        action="draft_created",
        new_value={"target_id": target_id, "type": data.action_type.value, "recipient": contact.email},
        request=request,
    )
    db.commit()
    db.refresh(action)
    return action


@router.post("/targets/{target_id}/check-alive")
async def check_target_alive(target_id: int, request: Request, db: Session = Depends(get_db)):
    """Check whether a target URL is still reachable and persist the result."""
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    checked_at = datetime.utcnow()
    alive = False
    status_code = None
    error = None

    try:
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            response = client.head(target.url)
            if response.status_code in [405, 403]:
                response = client.get(target.url)
            status_code = response.status_code
            alive = status_code < 400
    except Exception as exc:
        error = str(exc)

    old_status = target.status
    if not alive and status_code in [404, 410, 451]:
        target.status = TargetStatus.REMOVED
    elif alive and target.status == TargetStatus.REMOVED:
        target.status = TargetStatus.CONTACTED

    action = Action(
        target_id=target.id,
        type=ActionType.CHECK_REMOVAL,
        status=ActionStatus.COMPLETED,
        executed_at=checked_at,
        payload={
            "url": target.url,
            "alive": alive,
            "status_code": status_code,
            "error": error,
            "checked_at": checked_at.isoformat(),
            "reshare_monitor": True,
        },
    )
    db.add(action)
    db.flush()

    create_audit_log(
        db,
        entity_type="target",
        entity_id=target.id,
        action="link_alive_checked",
        old_value={"status": old_status.value},
        new_value={
            "status": target.status.value,
            "alive": alive,
            "status_code": status_code,
            "error": error,
        },
        request=request,
    )
    db.commit()
    db.refresh(action)
    return {
        "target_id": target.id,
        "url": target.url,
        "alive": alive,
        "status_code": status_code,
        "error": error,
        "target_status": target.status.value,
        "action": action,
    }


@router.post("/cases/{case_id}/check-links")
async def check_case_links(case_id: int, request: Request, db: Session = Depends(get_db)):
    """Check all non-false-positive target URLs for a case."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    targets = db.query(Target).filter(
        Target.case_id == case_id,
        Target.status != TargetStatus.FALSE_POSITIVE,
    ).all()
    results = []
    for target in targets:
        result = await check_target_alive(target.id, request, db)
        results.append({
            "target_id": result["target_id"],
            "url": result["url"],
            "alive": result["alive"],
            "status_code": result["status_code"],
            "target_status": result["target_status"],
        })

    return {"case_id": case_id, "checked": len(results), "results": results}


@router.get("/cases/{case_id}/actions")
async def list_case_actions(case_id: int, db: Session = Depends(get_db)):
    target_ids = [target.id for target in db.query(Target).filter(Target.case_id == case_id).all()]
    if not target_ids:
        return []
    return db.query(Action).filter(Action.target_id.in_(target_ids)).order_by(Action.created_at.desc()).all()


@router.post("/actions/{action_id}/review")
async def review_action(action_id: int, data: ReviewActionRequest, request: Request, db: Session = Depends(get_db)):
    action = db.query(Action).filter(Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status not in [ActionStatus.PENDING, ActionStatus.SCHEDULED]:
        raise HTTPException(status_code=400, detail=f"Action cannot be reviewed from status {action.status.value}")
    if data.decision not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="decision must be approve or reject")

    old_status = action.status
    payload = dict(action.payload or {})
    draft = dict(payload.get("draft") or {})
    if data.edited_subject:
        draft["subject"] = data.edited_subject
    if data.edited_body:
        draft["body"] = data.edited_body
    payload["draft"] = draft

    if data.decision == "reject":
        action.status = ActionStatus.REJECTED
        payload["review"] = {"decision": "reject", "admin_id": data.admin_id, "reviewed_at": datetime.utcnow().isoformat()}
    else:
        now = datetime.utcnow()
        action.status = ActionStatus.COMPLETED
        action.executed_at = now
        action.created_by = data.admin_id
        payload["review"] = {"decision": "approve", "admin_id": data.admin_id, "reviewed_at": now.isoformat()}
        try:
            payload["delivery"] = _send_email(payload, action.id)
        except Exception as exc:
            action.status = ActionStatus.FAILED
            action.error_message = str(exc)
            payload["delivery"] = {"status": "failed", "provider": "resend", "error": str(exc)}
            action.payload = payload
            create_audit_log(
                db,
                entity_type="action",
                entity_id=action.id,
                action="send_failed",
                old_value={"status": old_status.value},
                new_value={"status": ActionStatus.FAILED.value, "error": str(exc)},
                request=request,
                user_id=data.admin_id,
            )
            db.commit()
            db.refresh(action)
            return action
        action.target.status = TargetStatus.CONTACTED
        action.target.next_action_at = _schedule_after_action(action.type, now)

        next_type = _next_action_type(action.type)
        if next_type and action.target.next_action_at:
            followup = Action(
                target_id=action.target_id,
                type=next_type,
                status=ActionStatus.SCHEDULED,
                scheduled_at=action.target.next_action_at,
                payload={
                    "recipient": payload.get("recipient"),
                    "reason": "escalation_ladder",
                    "previous_action_id": action.id,
                },
            )
            db.add(followup)

    action.payload = payload
    create_audit_log(
        db,
        entity_type="action",
        entity_id=action.id,
        action="reviewed",
        old_value={"status": old_status.value},
        new_value={"status": action.status.value, "decision": data.decision},
        request=request,
        user_id=data.admin_id,
    )
    db.commit()
    db.refresh(action)
    return action


@router.post("/cases/{case_id}/kill-switch")
async def kill_switch(case_id: int, request: Request, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = case.status
    case.status = CaseStatus.SUSPENDED
    targets = db.query(Target).filter(Target.case_id == case_id).all()
    target_ids = [target.id for target in targets]
    if target_ids:
        db.query(Action).filter(
            Action.target_id.in_(target_ids),
            Action.status.in_([ActionStatus.PENDING, ActionStatus.SCHEDULED]),
        ).update({"status": ActionStatus.REJECTED}, synchronize_session=False)

    create_audit_log(
        db,
        entity_type="case",
        entity_id=case_id,
        action="kill_switch",
        old_value={"status": old_status.value},
        new_value={"status": CaseStatus.SUSPENDED.value, "cancelled_pending_actions": True},
        request=request,
    )
    db.commit()
    db.refresh(case)
    return {"success": True, "case": case}


@router.post("/cases/{case_id}/resolve")
async def resolve_case(case_id: int, request: Request, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    old_status = case.status
    case.status = CaseStatus.RESOLVED
    create_audit_log(
        db,
        entity_type="case",
        entity_id=case_id,
        action="resolved",
        old_value={"status": old_status.value},
        new_value={"status": CaseStatus.RESOLVED.value},
        request=request,
    )
    db.commit()
    db.refresh(case)
    return {"success": True, "case": case}


@router.get("/cases/{case_id}/timeline")
async def case_timeline(case_id: int, db: Session = Depends(get_db)):
    target_ids = [target.id for target in db.query(Target).filter(Target.case_id == case_id).all()]
    action_ids = []
    if target_ids:
        action_ids = [action.id for action in db.query(Action.id).filter(Action.target_id.in_(target_ids)).all()]

    entries = db.query(AuditLog).filter(
        (AuditLog.entity_type == "case") & (AuditLog.entity_id == case_id)
        | ((AuditLog.entity_type == "target") & (AuditLog.entity_id.in_(target_ids or [-1])))
        | ((AuditLog.entity_type == "action") & (AuditLog.entity_id.in_(action_ids or [-1])))
    ).order_by(AuditLog.created_at.desc()).all()
    return entries
