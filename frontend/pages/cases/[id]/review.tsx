import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import axios from 'axios';
import styles from './review.module.css';
import { useToast } from '../../../components/Toast';

const API_BASE_URL =
  typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8001`
    : process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001';

interface Target {
  id: number;
  url: string;
  status: string;
  created_at: string;
  hashes: TargetHash[];
}

interface TargetHash {
  id: number;
  image_url: string;
  match_score: number;
  match_type: string;
  phash_distance?: number;
  dhash_distance?: number;
  face_similarity?: number;
  thumbnail_id?: number;
}

interface ReviewTarget {
  target: Target;
  thumbnail_url?: string;
  match_evidence: {
    match_type: string;
    confidence: number;
    details: any;
  };
}

export default function CaseReview() {
  const toast = useToast();
  const router = useRouter();
  const { id } = router.query;
  const [reviewTargets, setReviewTargets] = useState<ReviewTarget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTargets, setSelectedTargets] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (id) {
      fetchReviewTargets();
    }
  }, [id]);

  const fetchReviewTargets = async () => {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/cases/${id}/review-targets`
      );
      setReviewTargets(response.data.targets);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch review targets');
    } finally {
      setLoading(false);
    }
  };

  const handleTargetAction = async (targetId: number, action: 'confirm' | 'reject' | 'rescrape') => {
    try {
      await axios.post(
        `${API_BASE_URL}/api/v1/targets/${targetId}/review`,
        { action }
      );

      // Refresh the list
      await fetchReviewTargets();

      // Remove from selected
      const newSelected = new Set(selectedTargets);
      newSelected.delete(targetId);
      setSelectedTargets(newSelected);
    } catch (err: any) {
      toast.push(`Failed to ${action} target: ${err.message}`, 'error');
    }
  };

  const handleBulkReject = async (domain: string) => {
    if (!confirm(`Are you sure you want to reject all targets from ${domain}?`)) {
      return;
    }

    try {
      await axios.post(
        `${API_BASE_URL}/api/v1/cases/${id}/bulk-reject`,
        { domain }
      );

      // Refresh the list
      await fetchReviewTargets();
    } catch (err: any) {
      toast.push(`Failed to bulk reject: ${err.message}`, 'error');
    }
  };

  const toggleTargetSelection = (targetId: number) => {
    const newSelected = new Set(selectedTargets);
    if (newSelected.has(targetId)) {
      newSelected.delete(targetId);
    } else {
      newSelected.add(targetId);
    }
    setSelectedTargets(newSelected);
  };

  const getMatchTypeColor = (matchType: string) => {
    switch (matchType) {
      case 'strong_phash':
        return '#28a745';
      case 'combined':
        return '#17a2b8';
      case 'face':
        return '#ffc107';
      case 'dhash':
        return '#fd7e14';
      default:
        return '#6c757d';
    }
  };

  if (loading) {
    return <div className={styles.loading}>Loading review targets...</div>;
  }

  if (error) {
    return <div className={styles.error}>Error: {error}</div>;
  }

  const groupedByDomain = reviewTargets.reduce((acc, rt) => {
    const url = new URL(rt.target.url);
    const domain = url.hostname;
    if (!acc[domain]) {
      acc[domain] = [];
    }
    acc[domain].push(rt);
    return acc;
  }, {} as Record<string, ReviewTarget[]>);

  return (
    <div className={styles.container}>
      <h1>Review Targets for Case #{id}</h1>

      <div className={styles.stats}>
        <div className={styles.statCard}>
          <h3>Total Targets</h3>
          <p>{reviewTargets.length}</p>
        </div>
        <div className={styles.statCard}>
          <h3>Needs Review</h3>
          <p>{reviewTargets.filter(rt => rt.match_evidence.match_type === 'needs_review').length}</p>
        </div>
        <div className={styles.statCard}>
          <h3>Match Confirmed</h3>
          <p>{reviewTargets.filter(rt => rt.match_evidence.match_type === 'match_confirmed').length}</p>
        </div>
      </div>

      {Object.entries(groupedByDomain).map(([domain, targets]) => (
        <div key={domain} className={styles.domainGroup}>
          <div className={styles.domainHeader}>
            <h2>{domain}</h2>
            <button
              className={styles.bulkRejectBtn}
              onClick={() => handleBulkReject(domain)}
            >
              Bulk Reject Domain
            </button>
          </div>

          <div className={styles.targetGrid}>
            {targets.map(rt => (
              <div key={rt.target.id} className={styles.targetCard}>
                <div className={styles.targetHeader}>
                  <input
                    type="checkbox"
                    checked={selectedTargets.has(rt.target.id)}
                    onChange={() => toggleTargetSelection(rt.target.id)}
                  />
                  <a href={rt.target.url} target="_blank" rel="noopener noreferrer">
                    {rt.target.url}
                  </a>
                </div>

                <div className={styles.targetContent}>
                  {rt.thumbnail_url && (
                    <img
                      src={rt.thumbnail_url}
                      alt="Target thumbnail"
                      className={styles.thumbnail}
                    />
                  )}

                  <div className={styles.matchInfo}>
                    <h4>Match Evidence</h4>
                    <div
                      className={styles.matchType}
                      style={{ backgroundColor: getMatchTypeColor(rt.match_evidence.match_type) }}
                    >
                      {rt.match_evidence.match_type}
                    </div>
                    <div className={styles.confidence}>
                      Confidence: {(rt.match_evidence.confidence * 100).toFixed(1)}%
                    </div>

                    {rt.target.hashes.map(hash => (
                      <div key={hash.id} className={styles.hashDetails}>
                        {hash.phash_distance !== undefined && (
                          <div>pHash Distance: {hash.phash_distance}</div>
                        )}
                        {hash.dhash_distance !== undefined && (
                          <div>dHash Distance: {hash.dhash_distance}</div>
                        )}
                        {hash.face_similarity !== undefined && (
                          <div>Face Similarity: {(hash.face_similarity * 100).toFixed(1)}%</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className={styles.targetActions}>
                  <button
                    className={styles.confirmBtn}
                    onClick={() => handleTargetAction(rt.target.id, 'confirm')}
                  >
                    Confirm Match
                  </button>
                  <button
                    className={styles.rejectBtn}
                    onClick={() => handleTargetAction(rt.target.id, 'reject')}
                  >
                    False Positive
                  </button>
                  <button
                    className={styles.rescrapeBtn}
                    onClick={() => handleTargetAction(rt.target.id, 'rescrape')}
                  >
                    Re-scrape
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
