"""Unit tests for the hasher module."""

import os
import tempfile
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image
import pytest

from app.confirmation.hasher import (
    hash_image,
    hamming_distance,
    cosine_similarity,
    create_thumbnail
)


class TestHasher:
    """Test cases for the hasher module."""

    @pytest.fixture
    def test_image(self):
        """Create a test image file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Create a simple test image
            img = Image.new('RGB', (200, 200), color='red')
            img.save(f.name, 'JPEG')
            yield f.name
            os.unlink(f.name)

    def test_hash_image(self, test_image):
        """Test hash_image function."""
        with patch('face_recognition.face_locations', return_value=[(0, 100, 100, 0)]):
            with patch('face_recognition.face_encodings', return_value=[np.random.rand(128)]):
                result = hash_image(test_image)

                assert 'phash' in result
                assert 'dhash' in result
                assert 'face_embeddings' in result
                assert len(result['phash']) == 16  # 64-bit hash as hex
                assert len(result['dhash']) == 16
                assert len(result['face_embeddings']) == 1
                assert len(result['face_embeddings'][0]) == 128

    def test_hash_image_no_faces(self, test_image):
        """Test hash_image when no faces are found."""
        with patch('face_recognition.face_locations', return_value=[]):
            result = hash_image(test_image)

            assert 'phash' in result
            assert 'dhash' in result
            assert 'face_embeddings' in result
            assert result['face_embeddings'] == []

    def test_hash_image_grayscale(self):
        """Test hash_image with grayscale image."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Create a grayscale test image
            img = Image.new('L', (200, 200), color=128)
            img.save(f.name, 'JPEG')

            try:
                with patch('face_recognition.face_locations', return_value=[]):
                    result = hash_image(f.name)
                    assert 'phash' in result
                    assert 'dhash' in result
            finally:
                os.unlink(f.name)

    def test_hamming_distance(self):
        """Test hamming_distance function."""
        # Same hashes
        assert hamming_distance('0000000000000000', '0000000000000000') == 0

        # Different by 1 bit
        assert hamming_distance('0000000000000000', '0000000000000001') == 1

        # Different by 4 bits
        assert hamming_distance('0000000000000000', '000000000000000f') == 4

        # Completely different
        assert hamming_distance('0000000000000000', 'ffffffffffffffff') == 64

    def test_cosine_similarity(self):
        """Test cosine_similarity function."""
        # Identical vectors
        v1 = [1.0, 0.0, 0.0]
        assert cosine_similarity(v1, v1) == pytest.approx(1.0)

        # Orthogonal vectors
        v2 = [0.0, 1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)

        # Opposite vectors
        v3 = [-1.0, 0.0, 0.0]
        assert cosine_similarity(v1, v3) == pytest.approx(-1.0)

        # Similar vectors
        v4 = [0.9, 0.1, 0.0]
        sim = cosine_similarity(v1, v4)
        assert 0.9 < sim < 1.0

    def test_create_thumbnail(self, test_image):
        """Test create_thumbnail function."""
        # Create thumbnail
        thumbnail_data = create_thumbnail(test_image, max_size=(100, 100))

        assert thumbnail_data is not None
        assert len(thumbnail_data) > 0

        # Verify it's valid JPEG data
        assert thumbnail_data.startswith(b'\xff\xd8\xff')  # JPEG header

        # Load thumbnail and check size
        import io
        thumbnail_img = Image.open(io.BytesIO(thumbnail_data))
        assert thumbnail_img.width <= 100
        assert thumbnail_img.height <= 100

    def test_create_thumbnail_aspect_ratio(self):
        """Test that create_thumbnail preserves aspect ratio."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Create a wide image
            img = Image.new('RGB', (400, 200), color='blue')
            img.save(f.name, 'JPEG')

            try:
                thumbnail_data = create_thumbnail(f.name, max_size=(100, 100))

                import io
                thumbnail_img = Image.open(io.BytesIO(thumbnail_data))

                # Should be 100x50 to preserve aspect ratio
                assert thumbnail_img.width == 100
                assert thumbnail_img.height == 50
            finally:
                os.unlink(f.name)

    def test_hash_image_file_not_found(self):
        """Test hash_image with non-existent file."""
        with pytest.raises(FileNotFoundError):
            hash_image('/non/existent/file.jpg')

    def test_create_thumbnail_invalid_image(self):
        """Test create_thumbnail with invalid image data."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'Not an image')
            f.flush()

            try:
                with pytest.raises(Exception):
                    create_thumbnail(f.name)
            finally:
                os.unlink(f.name)