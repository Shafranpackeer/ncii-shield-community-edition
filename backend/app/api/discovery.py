"""
Discovery API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import AuditLog, Case, Identifier, Target
from app.models.target import TargetStatus
from app.discovery.jobs import run_discovery_task
from app.discovery.jobs.discovery import DiscoveryRunner
from app.discovery.template_loader import RiskLevel
from app.schemas.target import TargetResponse
from app.utils.audit import create_audit_log

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/cases/{case_id}/run")
async def trigger_discovery(
    case_id: int,
    admin_approved: bool = False,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Trigger discovery run for a case."""
    # Verify case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="case",
        entity_id=case_id,
        action="discovery_triggered",
        new_value={
            "admin_approved": admin_approved
        },
        request=request
    )
    db.commit()

    # Queue discovery task
    task = run_discovery_task.apply_async(
        kwargs={
            "case_id": case_id,
            "admin_approved": admin_approved
        }
    )

    return {
        "success": True,
        "message": "Discovery job queued",
        "task_id": task.id,
        "case_id": case_id
    }


@router.get("/cases/{case_id}/preview")
async def preview_discovery(
    case_id: int,
    admin_approved: bool = False,
    db: Session = Depends(get_db)
):
    """Preview available engines and exact dork queries before a manual scan."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    runner = DiscoveryRunner(db)
    identifiers = db.query(Identifier).filter_by(case_id=case_id).all()
    available_data = runner._build_available_data(identifiers)
    risk_threshold = RiskLevel.HIGH if admin_approved else RiskLevel.LOW
    templates = runner.template_loader.get_applicable_templates(
        available_data=available_data,
        engines=list(runner.adapters.keys()),
        risk_threshold=risk_threshold,
    )

    queries = []
    for template in templates:
        queries.append({
            "id": template.id,
            "category": template.category,
            "query": template.expand(available_data),
            "risk_level": template.risk_level.value,
            "engines": [engine for engine in template.engines if engine in runner.adapters],
        })

    return {
        "case_id": case_id,
        "available_engines": sorted(runner.adapters.keys()),
        "identifier_data": available_data,
        "query_count": len(queries),
        "queries": queries,
    }


@router.post("/cases/{case_id}/run-sync")
async def run_discovery_sync(
    case_id: int,
    admin_approved: bool = True,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Run discovery synchronously so the admin can see results immediately."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    runner = DiscoveryRunner(db)
    try:
        result = runner.run_discovery(case_id=case_id, admin_approved=admin_approved)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Discovery database write failed: {exc.__class__.__name__}",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Discovery scan failed: {exc}",
        ) from exc

    targets = db.query(Target).filter(Target.case_id == case_id).order_by(Target.created_at.desc()).all()

    create_audit_log(
        db=db,
        entity_type="case",
        entity_id=case_id,
        action="manual_discovery_completed",
        new_value=result,
        request=request,
    )
    db.commit()

    return {
        "success": True,
        "result": result,
        "targets": [TargetResponse.model_validate(target).model_dump(mode="json") for target in targets],
    }


@router.get("/cases/{case_id}/progress")
async def discovery_progress(case_id: int, db: Session = Depends(get_db)):
    """Return latest manual discovery progress from persisted audit events."""
    latest_scan = db.query(AuditLog).filter(
        AuditLog.entity_type == "discovery",
        AuditLog.entity_id == case_id,
        AuditLog.action == "scan_started",
    ).order_by(AuditLog.created_at.desc()).first()

    if not latest_scan:
        return {
            "case_id": case_id,
            "latest_action": None,
            "total_queries": 0,
            "completed_queries": 0,
            "failed_queries": 0,
            "done_queries": 0,
            "percent": 0,
            "current_query": None,
            "events": [],
        }

    entries = db.query(AuditLog).filter(
        AuditLog.entity_type == "discovery",
        AuditLog.entity_id == case_id,
        AuditLog.action.in_(["scan_started", "query_started", "query_completed", "query_failed"]),
        AuditLog.created_at >= latest_scan.created_at,
    ).order_by(AuditLog.created_at.desc()).all()

    total = 0
    completed = 0
    failed = 0
    current_query = None
    latest_action = None

    for entry in reversed(entries):
        value = entry.new_value or {}
        total = max(total, int(value.get("total_queries") or 0))
        if entry.action == "query_completed":
            completed += 1
        elif entry.action == "query_failed":
            failed += 1
        if entry.action in ["query_started", "query_completed", "query_failed"]:
            current_query = value.get("query") or value.get("template_id")
        latest_action = entry.action

    done = completed + failed
    percent = min(100, int((done / total) * 100)) if total else 0
    return {
        "case_id": case_id,
        "latest_action": latest_action,
        "total_queries": total,
        "completed_queries": completed,
        "failed_queries": failed,
        "done_queries": done,
        "percent": percent,
        "current_query": current_query,
        "events": [
            {
                "action": entry.action,
                "created_at": entry.created_at,
                "details": entry.new_value,
            }
            for entry in entries
        ],
    }


@router.get("/cases/{case_id}/targets", response_model=List[TargetResponse])
async def get_discovered_targets(
    case_id: int,
    status: Optional[TargetStatus] = None,
    db: Session = Depends(get_db)
):
    """Get discovered targets for a case."""
    # Verify case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Query targets
    query = db.query(Target).filter(Target.case_id == case_id)

    if status:
        query = query.filter(Target.status == status)

    targets = query.order_by(Target.created_at.desc()).all()

    return targets


@router.post("/targets/{target_id}/review")
async def review_target(
    target_id: int,
    action: str,  # "approve" or "reject"
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Review a discovered target."""
    # Get target
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    old_status = target.status

    if action == "approve":
        # Promote to confirmation pending
        target.status = TargetStatus.CONFIRMED
        message = "Target approved for confirmation"
    elif action == "reject":
        # Mark as false positive
        target.status = TargetStatus.FALSE_POSITIVE
        message = "Target rejected as false positive"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="target",
        entity_id=target_id,
        action="reviewed",
        old_value={"status": old_status.value},
        new_value={
            "status": target.status.value,
            "action": action
        },
        request=request
    )

    db.commit()
    db.refresh(target)

    return {
        "success": True,
        "message": message,
        "target": TargetResponse.from_orm(target)
    }


@router.post("/targets/bulk-review")
async def bulk_review_targets(
    target_ids: List[int],
    action: str,  # "approve" or "reject"
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Bulk review multiple targets."""
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Get targets
    targets = db.query(Target).filter(Target.id.in_(target_ids)).all()

    if len(targets) != len(target_ids):
        raise HTTPException(status_code=404, detail="Some targets not found")

    updated_count = 0

    for target in targets:
        old_status = target.status

        if action == "approve":
            target.status = TargetStatus.CONFIRMED
        else:
            target.status = TargetStatus.FALSE_POSITIVE

        # Create audit log
        create_audit_log(
            db=db,
            entity_type="target",
            entity_id=target.id,
            action="bulk_reviewed",
            old_value={"status": old_status.value},
            new_value={
                "status": target.status.value,
                "action": action
            },
            request=request
        )

        updated_count += 1

    db.commit()

    return {
        "success": True,
        "message": f"{updated_count} targets {action}d",
        "updated_count": updated_count
    }


@router.get("/stats/{case_id}")
async def get_discovery_stats(
    case_id: int,
    db: Session = Depends(get_db)
):
    """Get discovery statistics for a case."""
    # Verify case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get target counts by status
    status_counts = db.query(
        Target.status,
        func.count(Target.id)
    ).filter(
        Target.case_id == case_id
    ).group_by(Target.status).all()

    # Convert to dict
    stats = {status.value: count for status, count in status_counts}

    # Get unique domains
    targets = db.query(Target.url).filter(Target.case_id == case_id).all()
    domains = set()

    for (url,) in targets:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc:
                domains.add(parsed.netloc.lower().replace("www.", ""))
        except:
            pass

    return {
        "case_id": case_id,
        "total_targets": sum(stats.values()),
        "status_breakdown": stats,
        "unique_domains": len(domains),
        "domains": sorted(list(domains))
    }
