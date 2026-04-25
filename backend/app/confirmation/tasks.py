"""
Celery tasks for NCII confirmation workflow.

Orchestrates scraping, hashing, and matching for discovered targets.
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models import Target, Case, ReferenceHash, TargetHash, AuditLog
from app.models.target import TargetStatus
from app.models.action import ActionType
from app.persistence.idempotent import idempotent_action
from app.utils.audit import create_audit_log

from .scraper import ImageScraper
from .hasher import hash_image, create_thumbnail
from .matcher import HashMatcher, MatchOutcome

logger = logging.getLogger(__name__)


def get_scraper() -> ImageScraper:
    """Create configured scraper instance from environment."""
    return ImageScraper(
        proxy_url=os.getenv('PROXY_URL'),
        timeout_seconds=int(os.getenv('SCRAPE_TIMEOUT_SECONDS', '30')),
        rate_limit_seconds=int(os.getenv('SCRAPE_RATE_LIMIT_PER_DOMAIN', '10')),
        headless=os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
    )


def get_matcher() -> HashMatcher:
    """Create configured matcher instance from environment."""
    return HashMatcher(
        phash_threshold=int(os.getenv('MATCH_PHASH_THRESHOLD', '10')),
        dhash_threshold=int(os.getenv('MATCH_DHASH_THRESHOLD', '8')),
        face_similarity_threshold=float(os.getenv('MATCH_FACE_SIMILARITY_THRESHOLD', '0.85'))
    )


@celery_app.task(bind=True)
def confirm_target(self, target_id: int):
    """
    Confirm a single target by scraping, hashing, and matching.

    Args:
        target_id: ID of the target to confirm

    Returns:
        Dict with confirmation results
    """
    db = SessionLocal()
    try:
        # Get target
        target = db.query(Target).filter(Target.id == target_id).first()
        if not target:
            logger.error(f"Target {target_id} not found")
            return {'error': 'Target not found'}

        # Check target is in correct state
        if target.status != TargetStatus.DISCOVERED:
            logger.warning(f"Target {target_id} not in DISCOVERED state: {target.status}")
            return {'error': f'Target in wrong state: {target.status}'}

        # Run confirmation in idempotent wrapper
        idempotency_key = f"confirm_target_{target_id}"

        with idempotent_action(
            target_id=target_id,
            action_type=ActionType.CHECK_REMOVAL,  # Using CHECK_REMOVAL for confirmation
            idempotency_key=idempotency_key,
            db=db,
            payload={'task': 'confirm_target'}
        ) as action:
            if action.is_already_completed():
                logger.info(f"Target {target_id} confirmation already completed")
                return action.get_result()

            action.mark_executing()

            # Update task binding for heartbeat
            if hasattr(self, 'request'):
                action.celery_task_id = self.request.id

            # Start confirmation workflow
            result = _confirm_target_workflow(db, target, action)

            # Store result in action payload
            action.action.payload['result'] = result
            db.commit()

            return result

    except Exception as e:
        logger.error(f"Error confirming target {target_id}: {e}")
        raise
    finally:
        db.close()


def _confirm_target_workflow(db: Session, target: Target, action) -> Dict:
    """
    Execute the confirmation workflow for a target.

    Args:
        db: Database session
        target: Target to confirm
        action: Idempotent action context

    Returns:
        Confirmation result dict
    """
    scraper = get_scraper()
    matcher = get_matcher()

    # Update status to scraping
    target.status = TargetStatus.DISCOVERED  # We'll create custom status later
    create_audit_log(
        db=db,
        entity_type="target",
        entity_id=target.id,
        action="status_changed",
        old_value={"status": "discovered"},
        new_value={"status": "scraping"}
    )
    db.commit()

    try:
        # Scrape images from target URL
        logger.info(f"Scraping images from {target.url}")
        scrape_result = asyncio.run(scraper.scrape_images(target.url))
        if isinstance(scrape_result, dict):
            if not scrape_result.get("success"):
                scraped_images = []
            else:
                scraped_images = [
                    {"image_url": path, "local_path": path}
                    for path in scrape_result.get("images", [])
                ]
        else:
            scraped_images = scrape_result

        if not scraped_images:
            logger.warning(f"No images found at {target.url}")
            target.status = TargetStatus.DISCOVERED
            create_audit_log(
                db=db,
                entity_type="target",
                entity_id=target.id,
                action="scrape_failed",
                new_value={"reason": "no_images_found"}
            )
            db.commit()
            return {
                'status': 'scrape_failed',
                'reason': 'No images found',
                'image_count': 0
            }

        logger.info(f"Found {len(scraped_images)} images to process")

        # Get reference hashes for this case
        reference_hashes = db.query(ReferenceHash).filter(
            ReferenceHash.case_id == target.case_id
        ).all()

        if not reference_hashes:
            logger.error(f"No reference hashes found for case {target.case_id}")
            return {
                'status': 'error',
                'reason': 'No reference hashes'
            }

        # Convert reference hashes to dict format
        ref_hash_dicts = []
        for ref in reference_hashes:
            ref_dict = {
                'id': ref.id,
                'phash': ref.phash,
                'dhash': ref.dhash,
                'face_embedding': ref.face_embedding
            }
            ref_hash_dicts.append(ref_dict)

        # Process each scraped image
        matches_found = []
        all_hashes = []

        for scraped in scraped_images:
            try:
                # Hash the image
                logger.debug(f"Hashing {scraped['image_url']}")
                image_hash = hash_image(scraped['local_path'])

                # Match against references
                match_result = matcher.match_image(image_hash, ref_hash_dicts)

                # Create thumbnail if match found
                thumbnail_blob = None
                if match_result.outcome != MatchOutcome.NO_MATCH:
                    thumbnail_blob = create_thumbnail(scraped['local_path'])

                # Store target hash
                target_hash = TargetHash(
                    target_id=target.id,
                    image_url=scraped['image_url'],
                    phash=int(image_hash['phash'], 16),
                    dhash=int(image_hash['dhash'], 16),
                    face_embedding=image_hash['face_embeddings'][0] if image_hash['face_embeddings'] else None,
                    match_against_ref_id=match_result.matched_ref_id,
                    match_score=match_result.confidence,
                    match_type=match_result.match_type if match_result.match_type else None
                )
                db.add(target_hash)
                all_hashes.append(target_hash)

                # Store thumbnail if created
                if thumbnail_blob:
                    from app.models.review_thumbnail import ReviewThumbnail
                    from datetime import datetime, timedelta

                    ttl_seconds = int(os.getenv('THUMBNAIL_TTL_SECONDS', '3600'))
                    thumbnail = ReviewThumbnail(
                        target_id=target.id,
                        image_url=scraped['image_url'],
                        thumbnail_blob=thumbnail_blob,
                        expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
                    )
                    db.add(thumbnail)

                if match_result.outcome != MatchOutcome.NO_MATCH:
                    matches_found.append({
                        'image_url': scraped['image_url'],
                        'outcome': match_result.outcome.value,
                        'confidence': match_result.confidence,
                        'match_type': match_result.match_type if match_result.match_type else None,
                        'details': match_result.details
                    })

            except Exception as e:
                logger.error(f"Error processing image {scraped['image_url']}: {e}")
                continue
            finally:
                # Image is deleted when scraper context exits
                pass

        # Determine overall target status based on matches
        if any(m['outcome'] == MatchOutcome.MATCH_CONFIRMED.value for m in matches_found):
            new_status = TargetStatus.CONFIRMED
        elif any(m['outcome'] == MatchOutcome.NEEDS_REVIEW.value for m in matches_found):
            new_status = TargetStatus.DISCOVERED  # Will update to custom status
        else:
            new_status = TargetStatus.FALSE_POSITIVE

        # Update target status
        old_status = target.status
        target.status = new_status
        create_audit_log(
            db=db,
            entity_type="target",
            entity_id=target.id,
            action="confirmation_complete",
            old_value={"status": old_status.value},
            new_value={
                "status": new_status.value,
                "matches_found": len(matches_found),
                "images_processed": len(scraped_images)
            }
        )

        db.commit()

        return {
            'status': 'success',
            'target_status': new_status.value,
            'images_processed': len(scraped_images),
            'matches_found': matches_found,
            'reference_hashes_checked': len(reference_hashes)
        }

    except Exception as e:
        logger.error(f"Error in confirmation workflow: {e}")
        # Update status to indicate failure
        target.status = TargetStatus.DISCOVERED
        create_audit_log(
            db=db,
            entity_type="target",
            entity_id=target.id,
            action="confirmation_error",
            new_value={"error": str(e)}
        )
        db.commit()
        raise


@celery_app.task
def confirm_case_batch(case_id: int):
    """
    Confirm all discovered targets for a case.

    Args:
        case_id: ID of the case

    Returns:
        Dict with batch confirmation results
    """
    db = SessionLocal()
    try:
        # Get all discovered targets for the case
        targets = db.query(Target).filter(
            Target.case_id == case_id,
            Target.status == TargetStatus.DISCOVERED
        ).all()

        if not targets:
            logger.info(f"No discovered targets found for case {case_id}")
            return {
                'case_id': case_id,
                'targets_processed': 0,
                'results': []
            }

        logger.info(f"Starting batch confirmation for {len(targets)} targets")

        # Create subtasks for each target
        results = []
        for target in targets:
            # Queue confirmation task
            task_result = confirm_target.apply_async(
                args=[target.id],
                queue='default'
            )
            results.append({
                'target_id': target.id,
                'target_url': target.url,
                'task_id': task_result.id
            })

        create_audit_log(
            db=db,
            entity_type="case",
            entity_id=case_id,
            action="batch_confirmation_started",
            new_value={
                "targets_queued": len(targets)
            }
        )
        db.commit()

        return {
            'case_id': case_id,
            'targets_processed': len(targets),
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in batch confirmation: {e}")
        raise
    finally:
        db.close()


@celery_app.task
def cleanup_expired_thumbnails():
    """
    Scheduled task to clean up expired thumbnails.
    """
    db = SessionLocal()
    try:
        from app.models.review_thumbnail import ReviewThumbnail

        # Delete expired thumbnails
        expired_count = db.query(ReviewThumbnail).filter(
            ReviewThumbnail.expires_at < datetime.utcnow()
        ).delete()

        db.commit()

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired thumbnails")

        return {
            'expired_thumbnails_deleted': expired_count
        }

    except Exception as e:
        logger.error(f"Error cleaning up thumbnails: {e}")
        db.rollback()
        raise
    finally:
        db.close()
