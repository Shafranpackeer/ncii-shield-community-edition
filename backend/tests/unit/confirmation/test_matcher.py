"""Unit tests for the matcher module."""

import pytest
from app.confirmation.matcher import HashMatcher, MatchResult, MatchOutcome


class TestHashMatcher:
    """Test cases for the HashMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create a HashMatcher instance with default thresholds."""
        return HashMatcher(
            phash_threshold=10,
            dhash_threshold=8,
            face_similarity_threshold=0.85
        )

    def test_strong_phash_match(self, matcher):
        """Test strong pHash match results in match_confirmed."""
        result = matcher.match_image(
            image_hash={
                'phash': '0000000000000001',
                'dhash': 'ffffffffffffffff',  # Very different
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',  # 1 bit different
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        assert result.outcome == MatchOutcome.MATCH_CONFIRMED
        assert result.confidence > 0.8
        assert result.match_type == 'strong_phash'
        assert result.details['phash_distance'] == 1

    def test_combined_match(self, matcher):
        """Test dHash + face match results in match_confirmed."""
        # Create similar face embeddings
        target_face = [1.0] + [0.0] * 127
        ref_face = [0.9] + [0.0] * 127

        result = matcher.match_image(
            image_hash={
                'phash': 'ffffffffffffffff',  # Very different
                'dhash': '0000000000000001',   # 1 bit different
                'face_embeddings': [target_face]
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': [ref_face]
            }]
        )

        assert result.outcome == MatchOutcome.MATCH_CONFIRMED
        assert result.match_type == 'combined'
        assert 'face_similarity' in result.details

    def test_face_only_needs_review(self, matcher):
        """Test face-only match results in needs_review."""
        # Create very similar face embeddings
        face = [1.0] + [0.0] * 127

        result = matcher.match_image(
            image_hash={
                'phash': 'ffffffffffffffff',  # Very different
                'dhash': 'ffffffffffffffff',  # Very different
                'face_embeddings': [face]
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': [face]  # Exact same face
            }]
        )

        assert result.outcome == MatchOutcome.NEEDS_REVIEW
        assert result.match_type == 'face'
        assert result.confidence > 0.5

    def test_single_hash_needs_review(self, matcher):
        """Test single hash match results in needs_review."""
        result = matcher.match_image(
            image_hash={
                'phash': 'ffffffffffffffff',  # Very different
                'dhash': '0000000000000001',   # 1 bit different
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        assert result.outcome == MatchOutcome.NEEDS_REVIEW
        assert result.match_type == 'dhash'

    def test_no_match(self, matcher):
        """Test no match case."""
        result = matcher.match_image(
            image_hash={
                'phash': 'ffffffffffffffff',  # Very different
                'dhash': 'ffffffffffffffff',  # Very different
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        assert result.outcome == MatchOutcome.NO_MATCH
        assert result.confidence < 0.3

    def test_multiple_faces(self, matcher):
        """Test matching with multiple faces in images."""
        # Target has 2 faces, reference has 1
        target_face1 = [1.0] + [0.0] * 127
        target_face2 = [0.0, 1.0] + [0.0] * 126
        ref_face = [0.95] + [0.0] * 127  # Similar to target_face1

        result = matcher.match_image(
            image_hash={
                'phash': 'ffffffffffffffff',
                'dhash': 'ffffffffffffffff',
                'face_embeddings': [target_face1, target_face2]
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': [ref_face]
            }]
        )

        # Should find the best matching face
        assert result.outcome == MatchOutcome.NEEDS_REVIEW
        assert result.match_type == 'face'
        assert result.details['face_similarity'] > 0.9

    def test_custom_thresholds(self):
        """Test HashMatcher with custom thresholds."""
        # Very strict matcher
        strict_matcher = HashMatcher(
            phash_threshold=2,
            dhash_threshold=2,
            face_similarity_threshold=0.95
        )

        result = strict_matcher.match_hashes(
            target_hash_data={
                'phash': '0000000000000003',  # 2 bits different
                'dhash': '0000000000000003',  # 2 bits different
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        # Should be below threshold
        assert result.outcome != MatchOutcome.MATCH_CONFIRMED

        # Lenient matcher
        lenient_matcher = HashMatcher(
            phash_threshold=30,
            dhash_threshold=30,
            face_similarity_threshold=0.5
        )

        result = lenient_matcher.match_hashes(
            target_hash_data={
                'phash': '00000000000000ff',  # 8 bits different
                'dhash': '00000000000000ff',  # 8 bits different
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        # Should be within threshold
        assert result.details['phash_distance'] == 8
        assert result.details['dhash_distance'] == 8

    def test_empty_embeddings(self, matcher):
        """Test matching when no faces are present."""
        result = matcher.match_image(
            image_hash={
                'phash': '0000000000000001',
                'dhash': '0000000000000001',
                'face_embeddings': []
            },
            reference_hashes=[{
                'phash': '0000000000000000',
                'dhash': '0000000000000000',
                'face_embeddings': []
            }]
        )

        assert 'face_similarity' not in result.details
        assert result.match_type == 'strong_phash'