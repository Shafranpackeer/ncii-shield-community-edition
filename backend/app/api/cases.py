from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models import Case, Identifier, ReferenceHash, Target
from app.models.identifier import IdentifierType as ModelIdentifierType
from app.schemas import (
    CaseCreate, CaseResponse, CaseList,
    IdentifierCreate, IdentifierResponse,
    ReferenceHashCreate, ReferenceHashResponse,
    TargetCreate, TargetResponse
)
from app.utils.audit import create_audit_log

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("/", response_model=CaseResponse)
async def create_case(
    case_data: CaseCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new case"""
    # Create the case
    case = Case(
        victim_id=case_data.victim_id,
        authorization_doc=case_data.authorization_doc
    )
    db.add(case)
    db.flush()  # Get the ID without committing

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="case",
        entity_id=case.id,
        action="created",
        new_value={
            "victim_id": case.victim_id,
            "status": "active",
            "authorization_doc": case.authorization_doc
        },
        request=request
    )

    db.commit()
    db.refresh(case)

    return case


@router.get("/", response_model=CaseList)
async def list_cases(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all cases"""
    query = db.query(Case)
    total = query.count()

    cases = query.offset(skip).limit(limit).all()

    return CaseList(cases=cases, total=total)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific case by ID"""
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/identifiers", response_model=IdentifierResponse)
async def add_identifier(
    case_id: int,
    identifier_data: IdentifierCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add an identifier to a case"""
    # Check if case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Create identifier
    identifier = Identifier(
        case_id=case_id,
        type=ModelIdentifierType(identifier_data.type.value),
        value=identifier_data.value
    )
    db.add(identifier)
    db.flush()

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="identifier",
        entity_id=identifier.id,
        action="created",
        new_value={
            "case_id": case_id,
            "type": identifier_data.type.value,
            "value": identifier_data.value
        },
        request=request
    )

    db.commit()
    db.refresh(identifier)

    return identifier


@router.post("/{case_id}/reference-hashes", response_model=ReferenceHashResponse)
async def add_reference_hash(
    case_id: int,
    hash_data: ReferenceHashCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add a reference hash to a case (client-side computed)"""
    # Check if case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Create reference hash
    reference_hash = ReferenceHash(
        case_id=case_id,
        phash=hash_data.phash,
        dhash=hash_data.dhash,
        face_embedding=hash_data.face_embedding,
        label=hash_data.label
    )
    db.add(reference_hash)
    db.flush()

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="reference_hash",
        entity_id=reference_hash.id,
        action="created",
        new_value={
            "case_id": case_id,
            "phash": str(hash_data.phash),
            "dhash": str(hash_data.dhash),
            "has_face_embedding": hash_data.face_embedding is not None,
            "label": hash_data.label
        },
        request=request
    )

    db.commit()
    db.refresh(reference_hash)

    return reference_hash


@router.post("/{case_id}/targets", response_model=TargetResponse)
async def add_target(
    case_id: int,
    target_data: TargetCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Manually add a target URL to a case"""
    # Check if case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Check if URL already exists (targets have unique URLs)
    existing = db.query(Target).filter(Target.url == target_data.url).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"URL already exists as target ID {existing.id} in case {existing.case_id}"
        )

    # Create target
    target = Target(
        case_id=case_id,
        url=target_data.url,
        discovery_source=target_data.discovery_source,
        confidence_score=target_data.confidence_score
    )
    db.add(target)
    db.flush()

    # Create audit log
    create_audit_log(
        db=db,
        entity_type="target",
        entity_id=target.id,
        action="created",
        new_value={
            "case_id": case_id,
            "url": target_data.url,
            "discovery_source": target_data.discovery_source,
            "confidence_score": target_data.confidence_score,
            "status": "discovered"
        },
        request=request
    )

    db.commit()
    db.refresh(target)

    return target
