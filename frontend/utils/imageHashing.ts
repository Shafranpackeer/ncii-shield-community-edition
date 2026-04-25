import * as faceapi from 'face-api.js';

// Type definitions
export interface ImageHashes {
  phash: bigint;
  dhash: bigint;
  faceEmbedding: number[] | null;
}

// Load face-api models
let modelsLoaded = false;

export async function loadFaceModels() {
  if (modelsLoaded) return;

  const MODEL_URL = '/models';

  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
    faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL)
  ]);

  modelsLoaded = true;
}

// Perceptual hash implementation
export function computePHash(canvas: HTMLCanvasElement, size: number = 8): bigint {
  const ctx = canvas.getContext('2d')!;

  // Resize to small size (default 8x8)
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = size;
  tempCanvas.height = size;
  const tempCtx = tempCanvas.getContext('2d')!;

  tempCtx.drawImage(canvas, 0, 0, size, size);

  // Get grayscale pixels
  const imageData = tempCtx.getImageData(0, 0, size, size);
  const pixels: number[] = [];

  for (let i = 0; i < imageData.data.length; i += 4) {
    const r = imageData.data[i];
    const g = imageData.data[i + 1];
    const b = imageData.data[i + 2];
    const gray = 0.299 * r + 0.587 * g + 0.114 * b;
    pixels.push(gray);
  }

  // Calculate average
  const avg = pixels.reduce((a, b) => a + b, 0) / pixels.length;

  // Create hash
  let hash = 0n;
  pixels.forEach((pixel, idx) => {
    if (pixel > avg) {
      hash |= (1n << BigInt(idx));
    }
  });

  return hash;
}

// Difference hash implementation
export function computeDHash(canvas: HTMLCanvasElement, size: number = 8): bigint {
  const ctx = canvas.getContext('2d')!;

  // Resize to size+1 x size
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = size + 1;
  tempCanvas.height = size;
  const tempCtx = tempCanvas.getContext('2d')!;

  tempCtx.drawImage(canvas, 0, 0, size + 1, size);

  // Get grayscale pixels
  const imageData = tempCtx.getImageData(0, 0, size + 1, size);
  const pixels: number[][] = [];

  for (let y = 0; y < size; y++) {
    pixels[y] = [];
    for (let x = 0; x < size + 1; x++) {
      const idx = (y * (size + 1) + x) * 4;
      const r = imageData.data[idx];
      const g = imageData.data[idx + 1];
      const b = imageData.data[idx + 2];
      const gray = 0.299 * r + 0.587 * g + 0.114 * b;
      pixels[y][x] = gray;
    }
  }

  // Create hash by comparing adjacent pixels
  let hash = 0n;
  let bit = 0;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (pixels[y][x] < pixels[y][x + 1]) {
        hash |= (1n << BigInt(bit));
      }
      bit++;
    }
  }

  return hash;
}

// Extract face embedding using face-api.js
export async function extractFaceEmbedding(canvas: HTMLCanvasElement): Promise<number[] | null> {
  await loadFaceModels();

  const detections = await faceapi
    .detectSingleFace(canvas, new faceapi.TinyFaceDetectorOptions())
    .withFaceLandmarks()
    .withFaceDescriptor();

  if (!detections) {
    return null;
  }

  // faceDescriptor is a Float32Array with 128 values
  return Array.from(detections.descriptor);
}

// Main hashing function that combines all methods
export async function hashImage(file: File): Promise<ImageHashes> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = async (e) => {
      try {
        const img = new Image();
        img.onload = async () => {
          // Create canvas from image
          const canvas = document.createElement('canvas');
          canvas.width = img.width;
          canvas.height = img.height;
          const ctx = canvas.getContext('2d')!;
          ctx.drawImage(img, 0, 0);

          // Compute hashes
          const phash = computePHash(canvas);
          const dhash = computeDHash(canvas);
          const faceEmbedding = await extractFaceEmbedding(canvas);

          resolve({
            phash,
            dhash,
            faceEmbedding
          });
        };

        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = e.target?.result as string;

      } catch (error) {
        reject(error);
      }
    };

    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

// Hamming distance calculation for hash comparison
export function hammingDistance(hash1: bigint, hash2: bigint): number {
  let xor = hash1 ^ hash2;
  let count = 0;

  while (xor > 0n) {
    count += Number(xor & 1n);
    xor >>= 1n;
  }

  return count;
}

// Cosine similarity for face embeddings
export function cosineSimilarity(vec1: number[], vec2: number[]): number {
  if (vec1.length !== vec2.length) return 0;

  let dotProduct = 0;
  let norm1 = 0;
  let norm2 = 0;

  for (let i = 0; i < vec1.length; i++) {
    dotProduct += vec1[i] * vec2[i];
    norm1 += vec1[i] * vec1[i];
    norm2 += vec2[i] * vec2[i];
  }

  if (norm1 === 0 || norm2 === 0) return 0;

  return dotProduct / (Math.sqrt(norm1) * Math.sqrt(norm2));
}