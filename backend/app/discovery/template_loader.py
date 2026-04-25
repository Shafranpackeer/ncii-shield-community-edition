"""
Dork template loader and management system.
"""

import os
import yaml
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class DorkTemplate:
    """Represents a single dork template."""
    id: str
    category: str
    query_pattern: str
    placeholders: List[str]
    engines: List[str]
    risk_level: RiskLevel

    def expand(self, values: Dict[str, str]) -> str:
        """
        Expand template with provided values.

        Args:
            values: Dictionary mapping placeholder names to values

        Returns:
            Expanded query string

        Raises:
            ValueError: If required placeholders are missing
        """
        # Check all required placeholders are provided
        missing = set(self.placeholders) - set(values.keys())
        if missing:
            raise ValueError(f"Missing required placeholders: {missing}")

        # Expand the template
        query = self.query_pattern
        for placeholder, value in values.items():
            if placeholder in self.placeholders:
                query = query.replace(f"{{{placeholder}}}", value)

        return query

    @property
    def needs_approval(self) -> bool:
        """Check if this template requires admin approval based on risk level."""
        return self.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]


class DorkTemplateLoader:
    """Loads and manages dork templates."""

    def __init__(self, template_dir: Optional[str] = None):
        """
        Initialize template loader.

        Args:
            template_dir: Directory containing template files.
                         Defaults to app/discovery/templates/
        """
        if template_dir is None:
            # Default to templates directory relative to this file
            template_dir = os.path.join(
                os.path.dirname(__file__),
                "templates"
            )
        self.template_dir = template_dir
        self.templates: Dict[str, DorkTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all templates from the templates directory."""
        template_file = os.path.join(self.template_dir, "dork_templates.yaml")

        if not os.path.exists(template_file):
            raise FileNotFoundError(f"Template file not found: {template_file}")

        with open(template_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'templates' not in data:
            raise ValueError("Invalid template file format")

        # Parse templates
        for template_data in data['templates']:
            template = DorkTemplate(
                id=template_data['id'],
                category=template_data['category'],
                query_pattern=template_data['query_pattern'],
                placeholders=template_data['placeholders'],
                engines=template_data['engines'],
                risk_level=RiskLevel(template_data['risk_level'])
            )
            self.templates[template.id] = template

    def get_template(self, template_id: str) -> Optional[DorkTemplate]:
        """Get a specific template by ID."""
        return self.templates.get(template_id)

    def get_templates_by_category(self, category: str) -> List[DorkTemplate]:
        """Get all templates in a specific category."""
        return [
            template for template in self.templates.values()
            if template.category == category
        ]

    def get_templates_for_engine(self, engine: str) -> List[DorkTemplate]:
        """Get all templates compatible with a specific search engine."""
        return [
            template for template in self.templates.values()
            if engine in template.engines
        ]

    def get_applicable_templates(
        self,
        available_data: Dict[str, Any],
        engines: List[str],
        risk_threshold: Optional[RiskLevel] = None
    ) -> List[DorkTemplate]:
        """
        Get all templates that can be used with the available data.

        Args:
            available_data: Dictionary of available placeholder values
            engines: List of available search engines
            risk_threshold: Maximum risk level to include (None = all)

        Returns:
            List of applicable templates
        """
        applicable = []

        for template in self.templates.values():
            # Check if we have all required placeholders
            if not all(placeholder in available_data for placeholder in template.placeholders):
                continue

            # Check if template works with available engines
            if not any(engine in template.engines for engine in engines):
                continue

            # Check risk level
            if risk_threshold:
                risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
                if risk_levels.index(template.risk_level) > risk_levels.index(risk_threshold):
                    continue

            applicable.append(template)

        return applicable

    def list_all_templates(self) -> List[DorkTemplate]:
        """Get all loaded templates."""
        return list(self.templates.values())

    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        return sorted(list(set(t.category for t in self.templates.values())))