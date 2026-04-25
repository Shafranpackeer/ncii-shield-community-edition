import React, { useEffect, useState } from 'react';
import { ImageHasher } from './ImageHasher';
import { casesAPI, Identifier, ReferenceHash, Target } from '../api/client';
import { ImageHashes } from '../utils/imageHashing';
import { formatCaseReference } from '../utils/caseReference';
import { useToast } from './Toast';
import axios from 'axios';

interface IntakeFormProps {
  onCaseCreated?: (caseId: number) => void;
}

export const IntakeForm: React.FC<IntakeFormProps> = ({ onCaseCreated }) => {
  const toast = useToast();
  const [step, setStep] = useState<'case' | 'identifiers' | 'hashes' | 'targets'>('case');
  const [caseId, setCaseId] = useState<number | null>(null);
  const [caseCreatedAt, setCaseCreatedAt] = useState<string | undefined>();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Form data
  const [victimId, setVictimId] = useState('');
  const [authorizationDoc, setAuthorizationDoc] = useState('');
  const [identifiers, setIdentifiers] = useState<Identifier[]>([]);
  const [referenceHashes, setReferenceHashes] = useState<(ReferenceHash & { originalDiscarded: boolean })[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);

  // Current inputs
  const [currentIdentifier, setCurrentIdentifier] = useState<Identifier>({ type: 'name', value: '' });
  const [currentTarget, setCurrentTarget] = useState('');
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const autosaveKey = 'ncii_shield_intake_draft';

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(autosaveKey);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.victimId) setVictimId(saved.victimId);
      if (saved.authorizationDoc) setAuthorizationDoc(saved.authorizationDoc);
      if (Array.isArray(saved.identifiers)) setIdentifiers(saved.identifiers);
      if (Array.isArray(saved.referenceHashes)) setReferenceHashes(saved.referenceHashes);
      if (Array.isArray(saved.targets)) setTargets(saved.targets);
      if (saved.currentIdentifier) setCurrentIdentifier(saved.currentIdentifier);
      if (saved.currentTarget) setCurrentTarget(saved.currentTarget);
      if (saved.caseId) setCaseId(saved.caseId);
      if (saved.caseCreatedAt) setCaseCreatedAt(saved.caseCreatedAt);
      if (saved.step) setStep(saved.step);
      setLastSavedAt(saved.lastSavedAt || null);
    } catch {
      // ignore corrupt local draft
    }
  }, []);

  useEffect(() => {
    const payload = {
      step,
      caseId,
      caseCreatedAt,
      victimId,
      authorizationDoc,
      identifiers,
      referenceHashes,
      targets,
      currentIdentifier,
      currentTarget,
      lastSavedAt: new Date().toISOString(),
    };
    const timer = window.setTimeout(() => {
      try {
        window.localStorage.setItem(autosaveKey, JSON.stringify(payload));
        setLastSavedAt(payload.lastSavedAt);
      } catch {
        // ignore storage failures
      }
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [step, caseId, caseCreatedAt, victimId, authorizationDoc, identifiers, referenceHashes, targets, currentIdentifier, currentTarget]);

  const clearDraft = () => {
    window.localStorage.removeItem(autosaveKey);
    setLastSavedAt(null);
  };

  const getErrorMessage = (error: unknown, fallback: string) => {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'string' && detail.trim()) {
        return detail;
      }
      if (error.message && error.message !== 'Network Error') {
        return error.message;
      }
    }

    if (error instanceof Error && error.message) {
      return error.message;
    }

    return fallback;
  };

  // Step 1: Create Case
  const handleCreateCase = async () => {
    if (!victimId) {
      toast.push('Victim ID is required', 'warning');
      return;
    }

    setIsSubmitting(true);
    try {
      const newCase = await casesAPI.create({
        victim_id: victimId,
        authorization_doc: authorizationDoc || undefined
      });
      setCaseId(newCase.id);
      setCaseCreatedAt(newCase.created_at);
      setStep('identifiers');
      if (onCaseCreated) onCaseCreated(newCase.id);
    } catch (error) {
      console.error('Error creating case:', error);
      toast.push(getErrorMessage(error, 'Failed to create case'), 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step 2: Add Identifiers
  const handleAddIdentifier = () => {
    if (!currentIdentifier.value) return;

    setIdentifiers([...identifiers, currentIdentifier]);
    setCurrentIdentifier({ type: 'name', value: '' });
  };

  const handleSubmitIdentifiers = async () => {
    if (!caseId || identifiers.length === 0) {
      setStep('hashes');
      return;
    }

    setIsSubmitting(true);
    try {
      await Promise.all(
        identifiers.map(id => casesAPI.addIdentifier(caseId, id))
      );
      setStep('hashes');
    } catch (error) {
      console.error('Error adding identifiers:', error);
      toast.push(getErrorMessage(error, 'Failed to add identifiers'), 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step 3: Add Reference Hashes
  const handleHashGenerated = (hash: ImageHashes & { label: string; originalDiscarded: boolean }) => {
    const referenceHash: ReferenceHash & { originalDiscarded: boolean } = {
      phash: Number(hash.phash),
      dhash: Number(hash.dhash),
      face_embedding: hash.faceEmbedding || undefined,
      label: hash.label,
      originalDiscarded: hash.originalDiscarded
    };
    setReferenceHashes([...referenceHashes, referenceHash]);
  };

  const handleSubmitHashes = async () => {
    if (!caseId || referenceHashes.length === 0) {
      setStep('targets');
      return;
    }

    setIsSubmitting(true);
    try {
      await Promise.all(
        referenceHashes.map(hash => {
          const { originalDiscarded, ...hashData } = hash;
          return casesAPI.addReferenceHash(caseId, hashData);
        })
      );
      setStep('targets');
    } catch (error) {
      console.error('Error adding hashes:', error);
      toast.push(getErrorMessage(error, 'Failed to add reference hashes'), 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step 4: Add Targets
  const handleAddTarget = () => {
    if (!currentTarget) return;

    try {
      const url = new URL(currentTarget);
      setTargets([...targets, { url: currentTarget, discovery_source: 'manual' }]);
      setCurrentTarget('');
    } catch {
      toast.push('Please enter a valid URL', 'warning');
    }
  };

  const handleSubmitTargets = async () => {
    if (!caseId || targets.length === 0) {
      toast.push('Case created successfully!', 'success');
      window.location.reload();
      return;
    }

    setIsSubmitting(true);
    try {
      await Promise.all(
        targets.map(target => casesAPI.addTarget(caseId, target))
      );
      toast.push('Case created successfully with all data!', 'success');
      window.location.reload();
    } catch (error) {
      console.error('Error adding targets:', error);
      toast.push(getErrorMessage(error, 'Failed to add targets'), 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="intake-form">
      <h2>NCII Shield Community Edition - Case Intake</h2>
      <div className="intake-banner">
        <strong>Zero-knowledge intake</strong>
        <span>Reference hashes are computed locally. Original images are discarded and never uploaded.</span>
        <span>Draft autosaves every few seconds so the intake can resume after interruption.</span>
        {lastSavedAt && <span>Last saved: {new Date(lastSavedAt).toLocaleTimeString()}</span>}
      </div>
      <div className="intake-actions">
        <button type="button" className="secondary-button" onClick={clearDraft}>Clear saved draft</button>
      </div>

      {step === 'case' && (
        <div className="form-step">
          <h3>Step 1: Create Case</h3>
          <div className="form-group">
            <label>Victim ID *</label>
            <input
              type="text"
              value={victimId}
              onChange={(e) => setVictimId(e.target.value)}
              placeholder="Enter victim identifier"
            />
          </div>
          <div className="form-group">
            <label>Authorization Document</label>
            <textarea
              value={authorizationDoc}
              onChange={(e) => setAuthorizationDoc(e.target.value)}
              placeholder="Reference to authorization document (optional)"
            />
          </div>
          <button onClick={handleCreateCase} disabled={isSubmitting} className="primary-button">
            Create Case
          </button>
        </div>
      )}

      {step === 'identifiers' && (
        <div className="form-step">
          <h3>Step 2: Add Identifiers (Optional)</h3>
          <p>Case Ref: {formatCaseReference(caseId, caseCreatedAt)}</p>

          <div className="form-group">
            <label>Type</label>
            <select
              value={currentIdentifier.type}
              onChange={(e) => setCurrentIdentifier({ ...currentIdentifier, type: e.target.value as any })}
            >
              <option value="name">Name</option>
              <option value="handle">Handle</option>
              <option value="alias">Alias</option>
              <option value="email">Email</option>
              <option value="phone">Phone</option>
            </select>
          </div>
          <div className="form-group">
            <label>Value</label>
            <input
              type="text"
              value={currentIdentifier.value}
              onChange={(e) => setCurrentIdentifier({ ...currentIdentifier, value: e.target.value })}
              placeholder="Enter identifier value"
            />
            <button onClick={handleAddIdentifier}>Add</button>
          </div>

          {identifiers.length > 0 && (
            <div className="added-items">
              <h4>Added Identifiers:</h4>
              <ul>
                {identifiers.map((id, idx) => (
                  <li key={idx}>{id.type}: {id.value}</li>
                ))}
              </ul>
            </div>
          )}

          <button onClick={handleSubmitIdentifiers} disabled={isSubmitting} className="primary-button">
            {identifiers.length > 0 ? 'Save & Continue' : 'Skip'}
          </button>
        </div>
      )}

      {step === 'hashes' && (
        <div className="form-step">
          <h3>Step 3: Add Reference Images</h3>
          <p>Case Ref: {formatCaseReference(caseId, caseCreatedAt)}</p>
          <p className="info">Images are hashed client-side. Original images are never uploaded.</p>

          <ImageHasher onHashGenerated={handleHashGenerated} />

          {referenceHashes.length > 0 && (
            <div className="added-items">
              <h4>Added Hashes:</h4>
              <ul>
                {referenceHashes.map((hash, idx) => (
                  <li key={idx}>
                    {hash.label} - pHash: {hash.phash.toString(16).substring(0, 8)}...
                    {hash.originalDiscarded && ' Original discarded'}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button onClick={handleSubmitHashes} disabled={isSubmitting} className="primary-button">
            {referenceHashes.length > 0 ? 'Save & Continue' : 'Skip'}
          </button>
        </div>
      )}

      {step === 'targets' && (
        <div className="form-step">
          <h3>Step 4: Add Target URLs (Optional)</h3>
          <p>Case Ref: {formatCaseReference(caseId, caseCreatedAt)}</p>

          <div className="form-group">
            <label>Target URL</label>
            <input
              type="url"
              value={currentTarget}
              onChange={(e) => setCurrentTarget(e.target.value)}
              placeholder="https://example.com/page"
            />
            <button onClick={handleAddTarget} className="secondary-button">Add</button>
          </div>

          {targets.length > 0 && (
            <div className="added-items">
              <h4>Added Targets:</h4>
              <ul>
                {targets.map((target, idx) => (
                  <li key={idx}>{target.url}</li>
                ))}
              </ul>
            </div>
          )}

          <button onClick={handleSubmitTargets} disabled={isSubmitting} className="primary-button">
            {targets.length > 0 ? 'Save & Finish' : 'Finish'}
          </button>
        </div>
      )}

      <style jsx>{`
        .intake-form {
          max-width: 800px;
          margin: 0 auto;
          padding: 20px;
        }

        .form-step {
          background: rgba(248, 250, 252, 0.96);
          padding: 24px;
          border-radius: 18px;
          box-shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
          border: 1px solid rgba(15, 23, 42, 0.08);
          margin-bottom: 18px;
        }

        .intake-banner {
          display: grid;
          gap: 4px;
          padding: 14px 16px;
          margin: 14px 0 12px;
          border-radius: 14px;
          background: linear-gradient(135deg, rgba(239, 246, 255, 0.96), rgba(248, 250, 252, 0.98));
          color: #334155;
          border: 1px solid rgba(37, 99, 235, 0.12);
        }

        .intake-banner strong {
          color: #0f172a;
        }

        .intake-banner span {
          font-size: 0.92rem;
          line-height: 1.45;
          color: #475569;
        }

        .intake-actions {
          display: flex;
          justify-content: flex-end;
          margin-bottom: 14px;
        }

        .form-group {
          margin-bottom: 20px;
        }

        .form-group label {
          display: block;
          margin-bottom: 5px;
          font-weight: bold;
          color: #0f172a;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
          width: 100%;
          padding: 8px 12px;
          border: 1px solid rgba(15, 23, 42, 0.12);
          border-radius: 10px;
          font-size: 14px;
          background: #f8fafc;
          color: #0f172a;
        }

        .form-group textarea {
          min-height: 80px;
          resize: vertical;
        }

        .primary-button, .secondary-button {
          border: none;
          padding: 10px 16px;
          border-radius: 10px;
          cursor: pointer;
          font-size: 15px;
          margin-top: 10px;
          font-weight: 600;
        }

        .primary-button {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          color: #f8fafc;
        }

        .secondary-button {
          background: rgba(255, 255, 255, 0.9);
          color: #0f172a;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .primary-button:hover:not(:disabled),
        .secondary-button:hover:not(:disabled) {
          filter: brightness(1.02);
        }

        button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .added-items {
          margin: 20px 0;
          padding: 15px;
          background: rgba(239, 246, 255, 0.72);
          border-radius: 12px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          color: #0f172a;
        }

        .added-items h4 {
          margin: 0 0 10px 0;
        }

        .added-items ul {
          margin: 0;
          padding-left: 20px;
        }

        .info {
          color: #475569;
          font-style: italic;
          margin-bottom: 20px;
        }
      `}</style>
    </div>
  );
};
