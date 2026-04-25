"""
Hash matching module for NCII confirmation.

Compares scraped image hashes against reference hashes
and determines match confidence levels.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .hasher import hamming_distance, cosine_similarity

logger = logging.getLogger(__name__)


class MatchType(Enum):
    """Types of hash matches."""
    STRONG_PHASH = "strong_phash"
    DHASH = "dhash"
    FACE = "face"
    COMBINED = "combined"


class MatchOutcome(Enum):
    """Overall match determination outcomes."""
    MATCH_CONFIRMED = "match_confirmed"
    NEEDS_REVIEW = "needs_review"
    NO_MATCH = "no_match"


@dataclass
class MatchResult:
    """Result of comparing an image against reference hashes."""
    outcome: MatchOutcome
    confidence: float
    match_type: Optional[str] = None
    matched_ref_id: Optional[int] = None
    phash_distance: Optional[int] = None
    dhash_distance: Optional[int] = None
    face_similarity: Optional[float] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class HashMatcher:
    """Compares image hashes against reference hashes."""

    def __init__(
        self,
        phash_threshold: int = 10,
        dhash_threshold: int = 8,
        face_similarity_threshold: float = 0.85
    ):
        """
        Initialize the matcher with configurable thresholds.

        Args:
            phash_threshold: Maximum Hamming distance for pHash match
            dhash_threshold: Maximum Hamming distance for dHash match
            face_similarity_threshold: Minimum cosine similarity for face match
        """
        self.phash_threshold = phash_threshold
        self.dhash_threshold = dhash_threshold
        self.face_similarity_threshold = face_similarity_threshold

    def match_image(
        self,
        image_hash: Dict[str, Any],
        reference_hashes: List[Dict[str, Any]]
    ) -> MatchResult:
        """
        Compare an image hash against all reference hashes.

        Args:
            image_hash: Hash data from hasher.hash_image()
            reference_hashes: List of reference hash records

        Returns:
            MatchResult with outcome and confidence
        """
        best_match = MatchResult(
            outcome=MatchOutcome.NO_MATCH,
            confidence=0.0
        )

        for ref in reference_hashes:
            result = self._compare_single_reference(image_hash, ref)

            # Keep the best match (highest confidence)
            if result.confidence > best_match.confidence:
                best_match = result

        logger.info(
            f"Match result: {best_match.outcome.value} "
            f"with confidence {best_match.confidence:.2f}"
        )

        return best_match

    def match_hashes(
        self,
        target_hash_data: Dict[str, Any],
        reference_hashes: List[Dict[str, Any]]
    ) -> MatchResult:
        """Backward-compatible alias used by tests and callers."""
        return self.match_image(target_hash_data, reference_hashes)

    def _compare_single_reference(
        self,
        image_hash: Dict[str, Any],
        reference: Dict[str, Any]
    ) -> MatchResult:
        """
        Compare image hash against a single reference.

        Args:
            image_hash: Hash data from the scraped image
            reference: Single reference hash record

        Returns:
            MatchResult for this specific comparison
        """
        # Extract reference ID
        ref_id = reference.get('id')

        # Compare perceptual hashes
        phash_distance = hamming_distance(
            image_hash['phash'],
            str(reference['phash'])
        )
        dhash_distance = hamming_distance(
            image_hash['dhash'],
            str(reference['dhash'])
        )

        # Check hash matches
        phash_match = phash_distance < self.phash_threshold
        dhash_match = dhash_distance < self.dhash_threshold

        # Compare face embeddings if available
        face_similarity = 0.0
        face_match = False

        reference_embeddings = (
            reference.get('face_embeddings')
            or reference.get('face_embedding')
            or []
        )
        if reference_embeddings and isinstance(reference_embeddings[0], (int, float)):
            reference_embeddings = [reference_embeddings]

        if (image_hash.get('face_embeddings') and reference_embeddings):
            # Best face vs best face comparison
            face_similarity = self._best_face_similarity(
                image_hash['face_embeddings'],
                reference_embeddings
            )
            face_match = face_similarity >= self.face_similarity_threshold

        # Determine match outcome based on signals
        if phash_match:
            # Strong pHash match alone is sufficient
            return MatchResult(
                outcome=MatchOutcome.MATCH_CONFIRMED,
                confidence=0.9 + (0.1 * (1 - phash_distance / self.phash_threshold)),
                match_type=MatchType.STRONG_PHASH.value,
                matched_ref_id=ref_id,
                phash_distance=phash_distance,
                dhash_distance=dhash_distance,
                face_similarity=face_similarity,
                details={
                    'phash_match': True,
                    'dhash_match': dhash_match,
                    'face_match': face_match,
                    'phash_distance': phash_distance,
                    'dhash_distance': dhash_distance
                }
            )

        elif dhash_match and face_match:
            # Combined dHash + face match
            return MatchResult(
                outcome=MatchOutcome.MATCH_CONFIRMED,
                confidence=0.9,
                match_type=MatchType.COMBINED.value,
                matched_ref_id=ref_id,
                phash_distance=phash_distance,
                dhash_distance=dhash_distance,
                face_similarity=face_similarity,
                details={
                    'phash_match': False,
                    'dhash_match': True,
                    'face_match': True,
                    'phash_distance': phash_distance,
                    'dhash_distance': dhash_distance,
                    'face_similarity': face_similarity
                }
            )

        elif face_match:
            # Face-only match needs review
            return MatchResult(
                outcome=MatchOutcome.NEEDS_REVIEW,
                confidence=0.6,
                match_type=MatchType.FACE.value,
                matched_ref_id=ref_id,
                phash_distance=phash_distance,
                dhash_distance=dhash_distance,
                face_similarity=face_similarity,
                details={
                    'phash_match': False,
                    'dhash_match': False,
                    'face_match': True,
                    'phash_distance': phash_distance,
                    'dhash_distance': dhash_distance,
                    'face_similarity': face_similarity
                }
            )

        elif phash_match or dhash_match:
            # Single hash match without face needs review
            return MatchResult(
                outcome=MatchOutcome.NEEDS_REVIEW,
                confidence=0.5,
                match_type=MatchType.DHASH.value if dhash_match else MatchType.STRONG_PHASH.value,
                matched_ref_id=ref_id,
                phash_distance=phash_distance,
                dhash_distance=dhash_distance,
                face_similarity=face_similarity,
                details={
                    'phash_match': phash_match,
                    'dhash_match': dhash_match,
                    'face_match': False,
                    'phash_distance': phash_distance,
                    'dhash_distance': dhash_distance
                }
            )

        else:
            # No significant matches
            return MatchResult(
                outcome=MatchOutcome.NO_MATCH,
                confidence=0.0,
                matched_ref_id=ref_id,
                phash_distance=phash_distance,
                dhash_distance=dhash_distance,
                face_similarity=face_similarity,
                details={
                    'phash_match': False,
                    'dhash_match': False,
                    'face_match': False,
                    'phash_distance': phash_distance,
                    'dhash_distance': dhash_distance
                }
            )

    def _best_face_similarity(
        self,
        image_embeddings: List[List[float]],
        reference_embeddings: List[List[float]]
    ) -> float:
        """
        Find the best face match between image faces and reference face.

        Args:
            image_embeddings: List of face embeddings from scraped image
            reference_embeddings: Face embeddings from reference

        Returns:
            Highest similarity score found
        """
        if not image_embeddings or not reference_embeddings:
            return 0.0

        best_similarity = 0.0

        for img_embedding in image_embeddings:
            for ref_embedding in reference_embeddings:
                similarity = cosine_similarity(img_embedding, ref_embedding)
                best_similarity = max(best_similarity, similarity)

        return best_similarity
