"""
Discovery job implementation.

Handles the orchestration of search queries across multiple engines.
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.models import Case, Identifier, Target
from app.models.target import TargetStatus
from app.utils.audit import create_audit_log
from app.utils.runtime_settings import get_runtime_setting

from ..template_loader import DorkTemplateLoader, RiskLevel
from ..adapters import (
    BingAdapter,
    SerpApiAdapter,
    SerpApiYandexAdapter,
    SerperAdapter,
    SearchResult
)


logger = logging.getLogger(__name__)


class DiscoveryRunner:
    """Handles the discovery process for a case."""

    def __init__(self, db: Session):
        self.db = db
        self.template_loader = DorkTemplateLoader()
        self.adapters = self._initialize_adapters()

    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize available search engine adapters.

        Priority order: SerpAPI-Yandex > Serper-Google > Bing
        """
        adapters = {}

        # Initialize SerpAPI (Yandex) - highest priority for NCII
        if get_runtime_setting("SERPAPI_KEY"):
            try:
                adapters["yandex"] = SerpApiYandexAdapter()
                logger.info("SerpAPI-Yandex adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize SerpAPI-Yandex adapter: {e}")

        # Initialize Serper (Google) - better than custom search
        if get_runtime_setting("SERPER_API_KEY"):
            try:
                adapters["serper-google"] = SerperAdapter()
                logger.info("Serper-Google adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Serper adapter: {e}")

        # Initialize Bing - fallback option
        if get_runtime_setting("BING_API_KEY"):
            try:
                adapters["bing"] = BingAdapter()
                logger.info("Bing adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Bing adapter: {e}")

        if not adapters:
            logger.error("No search engine adapters available!")

        return adapters

    def run_discovery(self, case_id: int, admin_approved: bool = False) -> Dict[str, Any]:
        """
        Run discovery for a case.

        Args:
            case_id: ID of the case to run discovery for
            admin_approved: Whether admin has pre-approved high-risk queries

        Returns:
            Dictionary with discovery results
        """
        # Load case and identifiers
        case = self.db.query(Case).filter(Case.id == case_id).first()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        identifiers = self.db.query(Identifier).filter(
            Identifier.case_id == case_id
        ).all()

        # Build available data for template expansion
        available_data = self._build_available_data(identifiers)

        # Get applicable templates
        risk_threshold = RiskLevel.HIGH if admin_approved else RiskLevel.LOW
        templates = self.template_loader.get_applicable_templates(
            available_data=available_data,
            engines=list(self.adapters.keys()),
            risk_threshold=risk_threshold
        )

        logger.info(f"Found {len(templates)} applicable templates for case {case_id}")
        create_audit_log(
            db=self.db,
            entity_type="discovery",
            entity_id=case_id,
            action="scan_started",
            new_value={
                "total_queries": len(templates),
                "engines": list(self.adapters.keys()),
            }
        )
        self.db.commit()

        # Execute searches
        all_results = []
        queries_executed = []

        for index, template in enumerate(templates, start=1):
            try:
                # Expand template with available data
                query = template.expand(available_data)

                # Log query execution
                create_audit_log(
                    db=self.db,
                    entity_type="discovery",
                    entity_id=case_id,
                    action="query_started",
                    new_value={
                        "template_id": template.id,
                        "query": query,
                        "engines": template.engines,
                        "risk_level": template.risk_level.value,
                        "current_query": index,
                        "total_queries": len(templates),
                    }
                )
                self.db.commit()

                # Execute on compatible engines
                for engine_name in template.engines:
                    if engine_name in self.adapters:
                        results = self.adapters[engine_name].search(query)
                        all_results.extend(results)

                        queries_executed.append({
                            "template_id": template.id,
                            "query": query,
                            "engine": engine_name,
                            "results_count": len(results)
                        })
                        create_audit_log(
                            db=self.db,
                            entity_type="discovery",
                            entity_id=case_id,
                            action="query_completed",
                            new_value={
                                "template_id": template.id,
                                "query": query,
                                "engine": engine_name,
                                "results_count": len(results),
                                "current_query": index,
                                "total_queries": len(templates),
                            }
                        )
                        self.db.commit()

            except Exception as e:
                logger.error(f"Error executing template {template.id}: {e}")
                create_audit_log(
                    db=self.db,
                    entity_type="discovery",
                    entity_id=case_id,
                    action="query_failed",
                    new_value={
                        "template_id": template.id,
                        "error": str(e),
                        "current_query": index,
                        "total_queries": len(templates),
                    }
                )
                self.db.commit()

        # Deduplicate results by URL
        unique_results = self._deduplicate_results(all_results)

        # Create target entries
        new_targets = self._create_targets(case_id, unique_results)

        self.db.commit()

        return {
            "case_id": case_id,
            "queries_executed": len(queries_executed),
            "total_results": len(all_results),
            "unique_results": len(unique_results),
            "new_targets": len(new_targets),
            "queries": queries_executed
        }

    def _build_available_data(self, identifiers: List[Identifier]) -> Dict[str, str]:
        """Build dictionary of available data from identifiers."""
        data = {}

        for identifier in identifiers:
            # Add primary identifier
            data[identifier.type.value] = identifier.value

            # Extract components for name types
            if identifier.type.value == "name":
                parts = identifier.value.split()
                if len(parts) >= 2:
                    data["first_name"] = parts[0]
                    data["last_name"] = " ".join(parts[1:])
                elif len(parts) == 1:
                    data["first_name"] = parts[0]

        return data

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Deduplicate results by URL, keeping the highest ranked."""
        seen_urls = {}

        for result in results:
            # Normalize URL
            parsed = urlparse(result.url.lower())
            # Remove www. prefix for better deduplication
            host = parsed.netloc.replace("www.", "")
            normalized_url = f"{parsed.scheme}://{host}{parsed.path}"

            if normalized_url not in seen_urls:
                seen_urls[normalized_url] = result
            else:
                # Keep the one with better position
                if result.position < seen_urls[normalized_url].position:
                    seen_urls[normalized_url] = result

        return list(seen_urls.values())

    def _create_targets(
        self,
        case_id: int,
        results: List[SearchResult]
    ) -> List[Target]:
        """Create target entries from search results."""
        new_targets = []

        for result in results:
            # Check if URL already exists
            existing = self.db.query(Target).filter(
                Target.url == result.url
            ).first()

            if existing:
                logger.info(f"URL already exists as target: {result.url}")
                continue

            # Create new target
            target = Target(
                case_id=case_id,
                url=result.url,
                status=TargetStatus.DISCOVERED,
                discovery_source=f"{result.engine}:{result.query[:50]}",
                confidence_score=0.0,  # Will be set during confirmation
                created_at=result.discovered_at
            )

            self.db.add(target)
            self.db.flush()
            new_targets.append(target)

            # Create audit log
            create_audit_log(
                db=self.db,
                entity_type="target",
                entity_id=target.id,
                action="discovered",
                new_value={
                    "url": result.url,
                    "engine": result.engine,
                    "query": result.query,
                    "title": result.title,
                    "snippet": result.snippet
                }
            )

        return new_targets


@celery_app.task(name="app.tasks.discovery.run_discovery")
def run_discovery_task(case_id: int, admin_approved: bool = False) -> Dict[str, Any]:
    """
    Celery task to run discovery for a case.

    Runs case-level discovery. Discovery is case-scoped, while outbound actions
    are target-scoped, so this task records audit events rather than creating an
    Action row with an invalid target foreign key.
    """
    db = SessionLocal()
    try:
        runner = DiscoveryRunner(db)
        result = runner.run_discovery(case_id, admin_approved)
        create_audit_log(
            db=db,
            entity_type="case",
            entity_id=case_id,
            action="discovery_completed",
            new_value=result,
        )
        db.commit()
        logger.info(f"Discovery completed for case {case_id}: {result}")
        return result

    except Exception as e:
        logger.error(f"Discovery failed for case {case_id}: {str(e)}")
        raise

    finally:
        db.close()
