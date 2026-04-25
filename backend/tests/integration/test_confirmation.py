"""Integration tests for the confirmation module."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch
import uuid
from sqlalchemy import text

from app.main import app
from app.db.session import get_db, SessionLocal
from app.models import (
    Case, Target, TargetHash, ReferenceHash, ReviewThumbnail
)
from app.models.case import CaseStatus
from app.models.target import TargetStatus


@pytest.fixture
def db_session():
    """Create a test database session with cleanup."""
    # Create a new session for each test
    session = SessionLocal()

    # Clean up any existing test data before running the test
    session.execute(text("""
        TRUNCATE TABLE
            review_thumbnails,
            target_hashes,
            contacts,
            actions,
            audit_log,
            identifiers,
            reference_hashes,
            targets,
            cases
        RESTART IDENTITY CASCADE
    """))
    session.commit()

    # Override the get_db dependency
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Cleanup after test
    session.rollback()
    session.execute(text("""
        TRUNCATE TABLE
            review_thumbnails,
            target_hashes,
            contacts,
            actions,
            audit_log,
            identifiers,
            reference_hashes,
            targets,
            cases
        RESTART IDENTITY CASCADE
    """))
    session.commit()
    session.close()

    # Remove the override
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session):
    """Create a test client with the test database session."""
    return TestClient(app)


class TestConfirmationAPI:
    """Test cases for confirmation API endpoints."""

    def test_get_review_targets(self, client, db_session):
        """Test getting targets for review."""
        # Create test case
        case = Case(
            victim_id="test_victim_001",
            status=CaseStatus.ACTIVE
        )
        db_session.add(case)
        db_session.commit()

        # Create target with matches
        test_url = f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg"
        target = Target(
            case_id=case.id,
            url=test_url,
            status=TargetStatus.DISCOVERED
        )
        db_session.add(target)
        db_session.commit()

        # Create target hash with match
        target_hash = TargetHash(
            target_id=target.id,
            image_url=test_url,
            phash=1,  # Using integer value for phash
            dhash=1,  # Using integer value for dhash
            face_embedding=[[1.0] + [0.0] * 127],  # Changed from face_embeddings to face_embedding
            match_score=0.9,
            match_type="strong_phash"
        )
        db_session.add(target_hash)

        # Create thumbnail
        thumbnail = ReviewThumbnail(
            target_id=target.id,
            image_url=test_url,
            thumbnail_blob=b"fake_thumbnail_data",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db_session.add(thumbnail)
        db_session.commit()

        # Test endpoint
        response = client.get(f"/api/v1/cases/{case.id}/review-targets")
        assert response.status_code == 200

        data = response.json()
        assert 'targets' in data
        assert len(data['targets']) == 1

        review_target = data['targets'][0]
        assert review_target['target']['id'] == target.id
        assert review_target['target']['url'] == target.url
        assert review_target['thumbnail_url'] is not None
        assert review_target['match_evidence']['match_type'] == 'strong_phash'
        assert review_target['match_evidence']['confidence'] == 0.9

        # No cleanup needed - transaction rollback handles it

    def test_get_thumbnail(self, client, db_session):
        """Test serving thumbnail images."""
        # Create a case and target first
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        test_url = f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg"
        target = Target(
            case_id=case.id,
            url=test_url,
            status=TargetStatus.DISCOVERED
        )
        db_session.add(target)
        db_session.commit()

        # Create thumbnail
        thumbnail = ReviewThumbnail(
            target_id=target.id,
            image_url=test_url,
            thumbnail_blob=b"\xff\xd8\xff\xe0\x00\x10JFIF",  # Minimal JPEG header
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db_session.add(thumbnail)
        db_session.commit()

        # Test successful retrieval
        response = client.get(f"/api/v1/thumbnails/{thumbnail.id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        assert response.content.startswith(b"\xff\xd8\xff")

        # No cleanup needed - transaction rollback handles it

    def test_get_thumbnail_expired(self, client, db_session):
        """Test expired thumbnail returns 410."""
        # Create a case and target first
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        test_url = f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg"
        target = Target(
            case_id=case.id,
            url=test_url,
            status=TargetStatus.DISCOVERED
        )
        db_session.add(target)
        db_session.commit()

        # Create expired thumbnail
        thumbnail = ReviewThumbnail(
            target_id=target.id,
            image_url=test_url,
            thumbnail_blob=b"fake_data",
            expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired
        )
        db_session.add(thumbnail)
        db_session.commit()

        response = client.get(f"/api/v1/thumbnails/{thumbnail.id}")
        assert response.status_code == 410
        assert response.json()["detail"] == "Thumbnail expired"

        # No cleanup needed - transaction rollback handles it

    def test_get_thumbnail_not_found(self, client):
        """Test non-existent thumbnail returns 404."""
        response = client.get("/api/v1/thumbnails/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Thumbnail not found"

    def test_review_target_confirm(self, client, db_session):
        """Test confirming a target match."""
        # Create test data
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        test_url = f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg"
        target = Target(
            case_id=case.id,
            url=test_url,
            status=TargetStatus.DISCOVERED
        )
        db_session.add(target)
        db_session.commit()
        target_id = target.id  # Store ID before API call

        # Create thumbnail to be deleted
        thumbnail = ReviewThumbnail(
            target_id=target_id,
            image_url=test_url,
            thumbnail_blob=b"fake_data",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db_session.add(thumbnail)
        db_session.commit()
        thumbnail_id = thumbnail.id  # Store ID before API call

        # Test confirm action
        response = client.post(
            f"/api/v1/targets/{target_id}/review",
            json={"action": "confirm"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify target status updated
        updated_target = db_session.query(Target).filter(Target.id == target_id).first()
        assert updated_target.status == TargetStatus.CONFIRMED

        # Verify thumbnail was deleted
        thumbnail_check = db_session.query(ReviewThumbnail).filter(
            ReviewThumbnail.id == thumbnail_id
        ).first()
        assert thumbnail_check is None

        # No cleanup needed - transaction rollback handles it

    def test_review_target_reject(self, client, db_session):
        """Test rejecting a target as false positive."""
        # Create test data
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        target = Target(
            case_id=case.id,
            url=f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg",
            status=TargetStatus.DISCOVERED
        )
        db_session.add(target)
        db_session.commit()
        target_id = target.id  # Store ID before API call

        # Test reject action
        response = client.post(
            f"/api/v1/targets/{target_id}/review",
            json={"action": "reject"}
        )
        assert response.status_code == 200

        # Verify target status updated
        updated_target = db_session.query(Target).filter(Target.id == target_id).first()
        assert updated_target.status == TargetStatus.FALSE_POSITIVE

        # No cleanup needed - transaction rollback handles it

    def test_review_target_rescrape(self, client, db_session):
        """Test queueing target for re-scraping."""
        # Create test data
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        target = Target(
            case_id=case.id,
            url=f"https://example.com/test_{uuid.uuid4().hex[:8]}.jpg",
            status=TargetStatus.CONFIRMED
        )
        db_session.add(target)
        db_session.commit()
        target_id = target.id  # Store ID before API call

        # Test rescrape action
        with patch('app.confirmation.tasks.confirm_target.delay') as mock_task:
            response = client.post(
                f"/api/v1/targets/{target_id}/review",
                json={"action": "rescrape"}
            )

        assert response.status_code == 200
        mock_task.assert_called_once_with(target_id)

        # Verify target status reset
        updated_target = db_session.query(Target).filter(Target.id == target_id).first()
        assert updated_target.status == TargetStatus.DISCOVERED

        # No cleanup needed - transaction rollback handles it

    def test_review_target_invalid_action(self, client, db_session):
        """Test invalid review action."""
        response = client.post(
            "/api/v1/targets/1/review",
            json={"action": "invalid"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid action"

    def test_bulk_reject_domain(self, client, db_session):
        """Test bulk rejecting all targets from a domain."""
        # Create test case
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        # Create targets from same domain
        target_ids = []
        for i in range(3):
            target = Target(
                case_id=case.id,
                url=f"https://badsite.com/image{i}.jpg",
                status=TargetStatus.DISCOVERED
            )
            db_session.add(target)
            db_session.flush()  # Get the ID
            target_ids.append(target.id)

        # Create target from different domain
        other_target = Target(
            case_id=case.id,
            url="https://goodsite.com/image.jpg",
            status=TargetStatus.DISCOVERED
        )
        db_session.add(other_target)
        db_session.flush()  # Get the ID
        other_target_id = other_target.id
        db_session.commit()

        # Test bulk reject
        response = client.post(
            f"/api/v1/cases/{case.id}/bulk-reject",
            json={"domain": "badsite.com"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["targets_rejected"] == 3

        # Verify targets updated
        for target_id in target_ids:
            updated_target = db_session.query(Target).filter(Target.id == target_id).first()
            assert updated_target.status == TargetStatus.FALSE_POSITIVE

        # Verify other domain not affected
        updated_other_target = db_session.query(Target).filter(Target.id == other_target_id).first()
        assert updated_other_target.status == TargetStatus.DISCOVERED

        # No cleanup needed - transaction rollback handles it

    def test_trigger_batch_confirmation(self, client, db_session):
        """Test triggering batch confirmation for a case."""
        # Create test case
        case = Case(victim_id="test_victim_001", status=CaseStatus.ACTIVE)
        db_session.add(case)
        db_session.commit()

        # Test trigger
        with patch('app.confirmation.tasks.confirm_case_batch.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"

            response = client.post(f"/api/v1/cases/{case.id}/confirm-batch")

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["task_id"] == "test-task-id"
        mock_task.assert_called_once_with(case.id)

        # No cleanup needed - transaction rollback handles it

    def test_trigger_batch_confirmation_case_not_found(self, client):
        """Test batch confirmation with non-existent case."""
        response = client.post("/api/v1/cases/99999/confirm-batch")
        assert response.status_code == 404
        assert response.json()["detail"] == "Case not found"
