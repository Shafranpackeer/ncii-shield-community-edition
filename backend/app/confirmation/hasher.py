"""
Image hashing module for NCII confirmation.

Computes perceptual hashes (pHash, dHash) and face embeddings
for server-side image matching.
"""

import logging
import os
from typing import Dict, List, Optional, Any
import numpy as np

try:
    import imagehash
    from PIL import Image
    import face_recognition
except ImportError as e:
    logging.error(f"Missing required library: {e}")
    raise

logger = logging.getLogger(__name__)


def hash_image(image_path: str) -> Dict[str, Any]:
    """
    Compute perceptual hashes and face embeddings for an image.

    Args:
        image_path: Path to the image file

    Returns:
        Dictionary containing:
        - phash: 64-bit perceptual hash as hex string
        - dhash: 64-bit difference hash as hex string
        - face_embeddings: List of 128-dim face embeddings (may be empty)

    Raises:
        ValueError: If image cannot be loaded or processed
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)

    try:
        # Load image with PIL for perceptual hashing
        pil_image = Image.open(image_path)

        # Convert to RGB if needed (handles RGBA, grayscale, etc.)
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        # Compute perceptual hashes
        phash = str(imagehash.phash(pil_image, hash_size=8))  # 64-bit hash
        dhash = str(imagehash.dhash(pil_image, hash_size=8))  # 64-bit hash

        # Load image for face recognition (requires numpy array)
        face_image = face_recognition.load_image_file(image_path)

        # Find all face locations and encodings
        face_locations = face_recognition.face_locations(face_image)
        face_embeddings = []

        if face_locations:
            # Get face encodings for all detected faces
            encodings = face_recognition.face_encodings(face_image, face_locations)
            # Convert to list of lists (JSON-serializable)
            face_embeddings = [encoding.tolist() for encoding in encodings]
            logger.info(f"Found {len(face_embeddings)} faces in image")
        else:
            logger.info("No faces detected in image")

        return {
            'phash': phash,
            'dhash': dhash,
            'face_embeddings': face_embeddings
        }

    except Exception as e:
        logger.error(f"Failed to hash image {image_path}: {str(e)}")
        raise ValueError(f"Image hashing failed: {str(e)}")


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Calculate Hamming distance between two hash strings.

    Args:
        hash1: First hash as hex string
        hash2: Second hash as hex string

    Returns:
        Hamming distance (number of differing bits)
    """
    try:
        # Convert hex strings to integers
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)

        # XOR and count set bits
        xor = int1 ^ int2
        distance = bin(xor).count('1')

        return distance
    except ValueError as e:
        logger.error(f"Invalid hash format: {e}")
        raise ValueError(f"Invalid hash format: {e}")


def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two face embeddings.

    Args:
        embedding1: First face embedding (128-dim list)
        embedding2: Second face embedding (128-dim list)

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    try:
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Preserve the full cosine range [-1, 1].
        return float(max(-1.0, min(1.0, similarity)))

    except Exception as e:
        logger.error(f"Failed to calculate cosine similarity: {e}")
        raise ValueError(f"Cosine similarity calculation failed: {e}")


def create_thumbnail(image_path: str, size: tuple = (200, 200), max_size: Optional[tuple] = None) -> bytes:
    """
    Create a thumbnail from an image for admin review.

    Args:
        image_path: Path to the source image
        size: Thumbnail dimensions (width, height)

    Returns:
        Thumbnail image as bytes (JPEG format)
    """
    try:
        from io import BytesIO

        # Open and convert to RGB
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Create thumbnail maintaining aspect ratio
        img.thumbnail(max_size or size, Image.Resampling.LANCZOS)

        # Strip EXIF data by re-encoding
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)

        return buffer.getvalue()

    except Exception as e:
        logger.error(f"Failed to create thumbnail: {e}")
        raise ValueError(f"Thumbnail creation failed: {e}")
