"""
API endpoints for confirmation and review functionality.
"""

from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Target, TargetHash, ReviewThumbnail
from app.models.target import TargetStatus
from app.utils.audit import create_audit_log

router = APIRouter(
    prefix="/api/v1",
    tags=["confirmation"]
)


@router.get("/cases/{case_id}/review-targets")
async def get_review_targets(case_id: int, db: Session = Depends(get_db)):
    """Get targets needing review for a case."""
    # Get targets that need review or have been confirmed but not yet approved
    targets = db.query(Target).filter(
        Target.case_id == case_id,
        Target.status.in_([TargetStatus.DISCOVERED, TargetStatus.CONFIRMED])
    ).all()

    review_targets = []
    for target in targets:
        # Get target hashes with match info
        hashes = db.query(TargetHash).filter(
            TargetHash.target_id == target.id,
            TargetHash.match_score > 0
        ).all()

        # Get thumbnail if available
        thumbnail = db.query(ReviewThumbnail).filter(
            ReviewThumbnail.target_id == target.id
        ).first()

        # Determine overall match evidence
        best_match = max(hashes, key=lambda h: h.match_score) if hashes else None

        if best_match:
            review_targets.append({
                'target': {
                    'id': target.id,
                    'url': target.url,
                    'status': target.status.value,
                    'created_at': target.created_at.isoformat(),
                    'hashes': [
                        {
                            'id': h.id,
                            'image_url': h.image_url,
                            'match_score': h.match_score,
                            'match_type': h.match_type,
                            'phash_distance': getattr(h, 'phash_distance', None),
                            'dhash_distance': getattr(h, 'dhash_distance', None),
                            'face_similarity': getattr(h, 'face_similarity', None)
                        } for h in hashes
                    ]
                },
                'thumbnail_url': f"/api/v1/thumbnails/{thumbnail.id}" if thumbnail else None,
                'match_evidence': {
                    'match_type': best_match.match_type or 'unknown',
                    'confidence': best_match.match_score,
                    'details': {}
                }
            })

    return {'targets': review_targets}


@router.get("/thumbnails/{thumbnail_id}")
async def get_thumbnail(thumbnail_id: int, db: Session = Depends(get_db)):
    """Serve a thumbnail image."""
    thumbnail = db.query(ReviewThumbnail).filter(
        ReviewThumbnail.id == thumbnail_id
    ).first()

    if not thumbnail:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    # Check if thumbnail is expired
    from datetime import datetime, timezone

    # Handle both timezone-aware and naive datetimes
    expires_at = thumbnail.expires_at
    now = datetime.now(timezone.utc)

    # If expires_at is naive, make it aware in UTC
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        raise HTTPException(status_code=410, detail="Thumbnail expired")

    return Response(
        content=thumbnail.thumbnail_blob,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f"inline; filename=thumbnail_{thumbnail.id}.jpg"
        }
    )


@router.post("/targets/{target_id}/review")
async def review_target(
    target_id: int,
    review_data: Dict,
    db: Session = Depends(get_db)
):
    """Process admin review action for a target."""
    action = review_data.get('action')
    if action not in ['confirm', 'reject', 'rescrape']:
        raise HTTPException(status_code=400, detail="Invalid action")

    target = db.query(Target).filter(Target.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    old_status = target.status

    if action == 'confirm':
        target.status = TargetStatus.CONFIRMED
    elif action == 'reject':
        target.status = TargetStatus.FALSE_POSITIVE
    elif action == 'rescrape':
        # Queue for re-scraping
        target.status = TargetStatus.DISCOVERED
        from app.confirmation.tasks import confirm_target
        confirm_target.delay(target_id)

    # Delete thumbnails after decision
    if action in ['confirm', 'reject']:
        db.query(ReviewThumbnail).filter(
            ReviewThumbnail.target_id == target_id
        ).delete()

    create_audit_log(
        db=db,
        entity_type="target",
        entity_id=target_id,
        action="admin_review",
        old_value={"status": old_status.value},
        new_value={"status": target.status.value, "action": action}
    )

    db.commit()

    return {"status": "success", "target_id": target_id, "action": action}


@router.post("/cases/{case_id}/bulk-reject")
async def bulk_reject_domain(
    case_id: int,
    data: Dict,
    db: Session = Depends(get_db)
):
    """Bulk reject all targets from a domain."""
    domain = data.get('domain')
    if not domain:
        raise HTTPException(status_code=400, detail="Domain required")

    # Find all targets from this domain
    targets = db.query(Target).filter(
        Target.case_id == case_id,
        Target.url.like(f"%{domain}%")
    ).all()

    rejected_count = 0
    for target in targets:
        if target.status in [TargetStatus.DISCOVERED, TargetStatus.CONFIRMED]:
            old_status = target.status
            target.status = TargetStatus.FALSE_POSITIVE

            create_audit_log(
                db=db,
                entity_type="target",
                entity_id=target.id,
                action="bulk_domain_reject",
                old_value={"status": old_status.value},
                new_value={"status": target.status.value, "domain": domain}
            )
            rejected_count += 1

    db.commit()

    return {
        "status": "success",
        "domain": domain,
        "targets_rejected": rejected_count
    }


@router.post("/cases/{case_id}/confirm-batch")
async def trigger_batch_confirmation(
    case_id: int,
    db: Session = Depends(get_db)
):
    """Trigger batch confirmation for all discovered targets in a case."""
    from app.confirmation.tasks import confirm_case_batch

    # Verify case exists
    from app.models import Case
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Queue batch confirmation
    task = confirm_case_batch.delay(case_id)

    return {
        "status": "queued",
        "case_id": case_id,
        "task_id": task.id
    }