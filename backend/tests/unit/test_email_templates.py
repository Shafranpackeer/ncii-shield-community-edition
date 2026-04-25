"""Unit tests for templated notice generation."""

from datetime import datetime

from app.api.operations import DraftRequest, _email_template_for_action
from app.models.action import ActionType
from app.models.case import Case, CaseStatus
from app.models.contact import Contact
from app.models.target import Target


def _build_case_bundle():
    case = Case(
        victim_id="victim-001",
        status=CaseStatus.ACTIVE,
        created_at=datetime(2026, 4, 25, 12, 0, 0),
    )
    target = Target(
        case_id=1,
        url="https://example.com/profile/test",
        created_at=datetime(2026, 4, 25, 13, 0, 0),
    )
    contact = Contact(
        target_id=1,
        email="abuse@example.com",
        method_found="scraped:https://example.com/contact",
        confidence=0.9,
    )
    return case, target, contact


def test_initial_notice_is_rendered_from_templates():
    case, target, contact = _build_case_bundle()
    draft = _email_template_for_action(
        case,
        target,
        contact,
        DraftRequest(action_type=ActionType.EMAIL_INITIAL, jurisdiction="US"),
    )

    assert draft["template_name"].startswith("day0_initial_")
    assert "Target URL: https://example.com/profile/test" in draft["body"]
    assert "Recipient(s): abuse@example.com" in draft["body"]
    assert "Sincerely," in draft["body"]
    assert "NCII notice for" in draft["subject"] or "Takedown request for" in draft["subject"]


def test_hosting_escalation_uses_template_library():
    case, target, contact = _build_case_bundle()
    draft = _email_template_for_action(
        case,
        target,
        contact,
        DraftRequest(action_type=ActionType.EMAIL_HOSTING, jurisdiction="US"),
    )

    assert draft["template_name"].startswith("day3_hosting_")
    assert "hosting provider" in draft["body"].lower()
    assert "Target URL: https://example.com/profile/test" in draft["body"]
