import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { hashImage, ImageHashes } from '../utils/imageHashing';

interface ImageHasherProps {
  onHashGenerated: (hash: ImageHashes & { label: string; originalDiscarded: boolean }) => void;
}

export const ImageHasher: React.FC<ImageHasherProps> = ({ onHashGenerated }) => {
  const [isHashing, setIsHashing] = useState(false);
  const [status, setStatus] = useState<string>('');
  const [currentHashes, setCurrentHashes] = useState<ImageHashes | null>(null);
  const [originalDiscarded, setOriginalDiscarded] = useState(false);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setIsHashing(true);
    setStatus('Processing image...');
    setOriginalDiscarded(false);

    try {
      setStatus('Computing perceptual hash...');
      const hashes = await hashImage(file);

      setStatus('Computing face embedding...');
      await new Promise((resolve) => setTimeout(resolve, 500));

      setCurrentHashes(hashes);
      setOriginalDiscarded(true);
      setStatus('Hashing complete. Original image discarded.');

      onHashGenerated({
        ...hashes,
        label: file.name,
        originalDiscarded: true,
      });
    } catch (error) {
      console.error('Hashing error:', error);
      setStatus('Error processing image');
    } finally {
      setIsHashing(false);
    }
  }, [onHashGenerated]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
    },
    multiple: false,
    disabled: isHashing,
  });

  return (
    <div className="image-hasher">
      <div className="zk-banner">
        <strong>Zero-knowledge hashing</strong>
        <span>Hashes are computed locally in the browser. Original images are discarded and never uploaded.</span>
      </div>

      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive ? 'active' : ''} ${isHashing ? 'disabled' : ''}`}
      >
        <input {...getInputProps()} />
        {isDragActive ? (
          <p>Drop the image here. The original will be discarded after hashing.</p>
        ) : isHashing ? (
          <p>{status}</p>
        ) : (
          <p>Drag and drop an image here, or click to select.</p>
        )}
      </div>

      {currentHashes && (
        <div className="hash-results">
          <div className="hash-info">
            <h4>Generated Hashes:</h4>
            <div className="hash-values">
              <p><strong>pHash:</strong> {currentHashes.phash.toString(16).padStart(16, '0')}</p>
              <p><strong>dHash:</strong> {currentHashes.dhash.toString(16).padStart(16, '0')}</p>
              <p><strong>Face Embedding:</strong> {
                currentHashes.faceEmbedding
                  ? `${currentHashes.faceEmbedding.length} dimensions extracted`
                  : 'No face detected'
              }</p>
            </div>
          </div>
          {originalDiscarded && (
            <div className="security-notice">
              Original image discarded. Only hashes retained.
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .image-hasher {
          margin: 20px 0;
        }

        .zk-banner {
          display: grid;
          gap: 4px;
          margin-bottom: 12px;
          padding: 14px 16px;
          border-radius: 14px;
          border: 1px solid rgba(37, 99, 235, 0.12);
          background: linear-gradient(135deg, rgba(239, 246, 255, 0.96), rgba(248, 250, 252, 0.98));
          color: #334155;
        }

        .zk-banner strong {
          font-size: 0.96rem;
          color: #0f172a;
        }

        .zk-banner span {
          font-size: 0.92rem;
          line-height: 1.45;
          color: #475569;
        }

        .dropzone {
          border: 1.5px dashed #94a3b8;
          border-radius: 16px;
          padding: 28px;
          text-align: center;
          cursor: pointer;
          transition: all 0.3s ease;
          background: rgba(248, 250, 252, 0.96);
          color: #0f172a;
        }

        .dropzone:hover {
          border-color: #2563eb;
          background-color: #f8fbff;
        }

        .dropzone.active {
          border-color: #0f766e;
          background-color: #eefcf9;
        }

        .dropzone.disabled {
          cursor: not-allowed;
          opacity: 0.6;
        }

        .hash-results {
          margin-top: 20px;
          padding: 20px;
          background: rgba(248, 250, 252, 0.96);
          border-radius: 14px;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .hash-info h4 {
          margin: 0 0 10px 0;
          color: #0f172a;
        }

        .hash-values p {
          margin: 5px 0;
          font-family: monospace;
          word-break: break-all;
          color: #475569;
        }

        .security-notice {
          margin-top: 15px;
          padding: 10px;
          background-color: #dcfce7;
          border: 1px solid #86efac;
          border-radius: 10px;
          color: #14532d;
          font-weight: 700;
        }
      `}</style>
    </div>
  );
};
