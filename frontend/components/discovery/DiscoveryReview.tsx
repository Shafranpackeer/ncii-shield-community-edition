import React, { useEffect, useState } from 'react';
import { casesAPI, discoveryAPI, operationsAPI, Target } from '../../api/client';
import { useToast } from '../Toast';

interface DiscoveryReviewProps {
  caseId: number;
  caseRef?: string;
}

type IdentifierType = 'name' | 'handle' | 'alias' | 'email' | 'phone';

export const DiscoveryReview: React.FC<DiscoveryReviewProps> = ({ caseId, caseRef }) => {
  const toast = useToast();
  const [targets, setTargets] = useState<Target[]>([]);
  const [selectedTargets, setSelectedTargets] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [preview, setPreview] = useState<any>(null);
  const [scanResult, setScanResult] = useState<any>(null);
  const [scanProgress, setScanProgress] = useState<any>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [filter, setFilter] = useState('');
  const [groupByDomain, setGroupByDomain] = useState(true);
  const [identifierType, setIdentifierType] = useState<IdentifierType>('name');
  const [identifierValue, setIdentifierValue] = useState('');
  const [manualUrl, setManualUrl] = useState('');
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [bootstrapped, setBootstrapped] = useState(false);

  const formatDiscoverySource = (source?: string) => {
    if (!source) return 'Manual entry';
    if (source === 'manual_frontend' || source === 'manual') return 'Manual entry';
    return source.replace(/_/g, ' ');
  };

  useEffect(() => {
    loadAll();
  }, [caseId, filter]);

  const loadAll = async () => {
    try {
      await Promise.all([loadTargets(), loadStats(), loadPreview()]);
    } finally {
      setBootstrapped(true);
    }
  };

  const loadTargets = async () => {
    const data = await discoveryAPI.getTargets(caseId, filter || undefined);
    setTargets(data);
  };

  const loadStats = async () => {
    const data = await discoveryAPI.getStats(caseId);
    setStats(data);
  };

  const loadPreview = async () => {
    const data = await discoveryAPI.previewDiscovery(caseId, true);
    setPreview(data);
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await loadAll();
      setLastRefresh(new Date());
    } finally {
      setLoading(false);
    }
  };

  const handleManualScan = async () => {
    setLoading(true);
    setIsScanning(true);
    setScanResult(null);
    try {
      const data = await discoveryAPI.runManualScan(caseId, true);
      setScanResult(data.result);
      setTargets(data.targets || []);
      await Promise.all([loadStats(), loadPreview()]);
      setLastRefresh(new Date());
    } catch (error: any) {
      toast.push(error?.response?.data?.detail || error.message || 'Manual scan failed', 'error');
    } finally {
      setLoading(false);
      setIsScanning(false);
    }
  };

  useEffect(() => {
    if (!isScanning) return;
    const interval = setInterval(async () => {
      try {
        const progress = await discoveryAPI.scanProgress(caseId);
        setScanProgress(progress);
      } catch (error) {
        console.error('Progress polling failed:', error);
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [isScanning, caseId]);

  const addIdentifier = async () => {
    if (!identifierValue.trim()) return;
    await casesAPI.addIdentifier(caseId, { type: identifierType, value: identifierValue.trim() });
    setIdentifierValue('');
    await loadPreview();
  };

  const addManualTarget = async () => {
    if (!manualUrl.trim()) return;
    await casesAPI.addTarget(caseId, {
      url: manualUrl.trim(),
      discovery_source: 'manual',
      confidence_score: 1,
    });
    setManualUrl('');
    await loadAll();
  };

  const handleTriggerDiscovery = async (adminApproved: boolean) => {
    setLoading(true);
    try {
      await discoveryAPI.triggerDiscovery(caseId, adminApproved);
      toast.push('Background discovery queued. Use Refresh to update results.', 'success');
    } finally {
      setLoading(false);
    }
  };

  const handleReviewTarget = async (targetId: number, action: 'approve' | 'reject') => {
    await discoveryAPI.reviewTarget(targetId, action);
    await loadAll();
  };

  const handleBulkReview = async (action: 'approve' | 'reject') => {
    if (selectedTargets.size === 0) {
      toast.push('No targets selected', 'warning');
      return;
    }
    await discoveryAPI.bulkReviewTargets(Array.from(selectedTargets), action);
    setSelectedTargets(new Set());
    await loadAll();
  };

  const checkTarget = async (targetId: number) => {
    const result = await operationsAPI.checkTargetAlive(targetId);
    toast.push(`Alive: ${result.alive}. Status: ${result.status_code || result.error || 'unknown'}`, result.alive ? 'success' : 'warning');
    await loadAll();
  };

  const checkAllLinks = async () => {
    setLoading(true);
    try {
      const result = await operationsAPI.checkCaseLinks(caseId);
      setScanResult({ link_check: result });
      await loadAll();
    } finally {
      setLoading(false);
    }
  };

  const toggleSelection = (targetId: number) => {
    const next = new Set(selectedTargets);
    next.has(targetId) ? next.delete(targetId) : next.add(targetId);
    setSelectedTargets(next);
  };

  const selectAll = () => setSelectedTargets(new Set(targets.map((t) => t.id!).filter(Boolean)));

  const getDomain = (url: string) => {
    try {
      return new URL(url).hostname.toLowerCase().replace('www.', '');
    } catch {
      return 'unknown';
    }
  };

  const groupedTargets = groupByDomain
    ? targets.reduce((acc, target) => {
        const domain = getDomain(target.url);
        if (!acc[domain]) acc[domain] = [];
        acc[domain].push(target);
        return acc;
      }, {} as Record<string, Target[]>)
    : { 'All Targets': targets };

  return (
    <div className="discovery-review">
      <div className="discovery-header">
        <div>
          <div className="eyebrow">Community Edition</div>
          <h2>Discovery / Manual Scan</h2>
          <p className="case-ref">{caseRef || `Case #${caseId}`}</p>
        </div>
        <div className="discovery-actions">
          <button onClick={handleRefresh} disabled={loading} className="btn-secondary">Refresh</button>
          <button onClick={() => handleTriggerDiscovery(false)} disabled={loading} className="btn-primary">Queue Low-Risk Discovery</button>
          <button onClick={handleManualScan} disabled={loading} className="btn-success">Run Manual Scan Now</button>
          <button onClick={checkAllLinks} disabled={loading} className="btn-warning">Check All Links Alive</button>
        </div>
      </div>

      <div className="input-panel">
        <div>
          <h3>Identifiers for Google/Serper Dorks</h3>
          <p>These generate the bad-word/leak-site queries from the project plan.</p>
          <select value={identifierType} onChange={(e) => setIdentifierType(e.target.value as IdentifierType)}>
            <option value="name">Full name</option>
            <option value="handle">Handle</option>
            <option value="alias">Alias</option>
            <option value="email">Email</option>
            <option value="phone">Phone</option>
          </select>
          <input value={identifierValue} onChange={(e) => setIdentifierValue(e.target.value)} placeholder="Full name, handle, email..." />
          <button onClick={addIdentifier} className="btn-primary">Add Identifier</button>
        </div>
        <div>
          <h3>Known URL</h3>
          <p>Add a URL directly when you already have a suspect page.</p>
          <input value={manualUrl} onChange={(e) => setManualUrl(e.target.value)} placeholder="https://example.com/page" />
          <button onClick={addManualTarget} className="btn-secondary">Add Manual URL</button>
        </div>
      </div>

      {(stats || !bootstrapped) && (
        <div className="stats-panel">
          {!bootstrapped ? (
            <>
              <div className="stat-skel" />
              <div className="stat-skel" />
              <div className="stat-skel" />
              <div className="stat-skel" />
            </>
          ) : (
            <>
              <div className="stat"><span>Total</span><strong>{stats.total_targets}</strong></div>
              <div className="stat"><span>Domains</span><strong>{stats.unique_domains}</strong></div>
              {Object.entries(stats.status_breakdown || {}).map(([status, count]) => (
                <div key={status} className="stat"><span>{status}</span><strong>{count as number}</strong></div>
              ))}
              {lastRefresh && <div className="stat"><span>Last refresh</span><strong>{lastRefresh.toLocaleTimeString()}</strong></div>}
            </>
          )}
        </div>
      )}

      <div className="preview-panel">
        <h3>Queries That Will Run</h3>
        <div className="preview-meta">
          <span>Engines: {preview?.available_engines?.join(', ') || 'none configured'}</span>
          <span>Queries ready: {preview?.query_count ?? 0}</span>
        </div>
        {!bootstrapped ? (
          <div className="query-list">
            {[1, 2, 3, 4].map((item) => (
              <div key={item} className="query-skel" />
            ))}
          </div>
        ) : preview?.query_count === 0 ? (
          <p className="warning">No queries yet. Add a full name, handle, or email above. If engines are none, the Serper key is not loaded.</p>
        ) : (
          <div className="query-list">
            {(preview?.queries || []).map((query: any) => (
              <div key={`${query.id}-${query.query}`} className={`query-item risk-${query.risk_level}`}>
                <strong>{query.category}</strong>
                <code>{query.query}</code>
                <span>{query.risk_level} via {query.engines.join(', ')}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {scanResult && (
        <div className="scan-result">
          <h3>Latest Scan / Follow-Up Result</h3>
          <pre>{JSON.stringify(scanResult, null, 2)}</pre>
        </div>
      )}

      {(isScanning || scanProgress) && (
        <div className="progress-panel">
          <h3>Scan Progress</h3>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${scanProgress?.percent || 0}%` }} />
          </div>
          <p>
            {scanProgress?.done_queries || 0} / {scanProgress?.total_queries || preview?.query_count || 0} queries complete
            {scanProgress?.failed_queries ? `, ${scanProgress.failed_queries} failed` : ''}
          </p>
          {scanProgress?.current_query && <code>{scanProgress.current_query}</code>}
          <div className="progress-events">
            {(scanProgress?.events || []).slice(0, 6).map((event: any, index: number) => (
              <div key={`${event.created_at}-${index}`}>
                <strong>{event.action}</strong> {event.details?.query || event.details?.template_id || ''}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="filters">
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All Targets</option>
          <option value="discovered">Discovered</option>
          <option value="confirmed">Confirmed</option>
          <option value="contacted">Contacted</option>
          <option value="removed">Removed</option>
          <option value="false_positive">False Positive</option>
        </select>
        <label><input type="checkbox" checked={groupByDomain} onChange={(e) => setGroupByDomain(e.target.checked)} /> Group by domain</label>
      </div>

      {selectedTargets.size > 0 && (
        <div className="bulk-actions">
          <span>{selectedTargets.size} selected</span>
          <button onClick={() => handleBulkReview('approve')} className="btn-success">Approve Selected</button>
          <button onClick={() => handleBulkReview('reject')} className="btn-danger">Reject Selected</button>
          <button onClick={() => setSelectedTargets(new Set())} className="btn-secondary">Clear</button>
          <button onClick={selectAll} className="btn-secondary">Select All</button>
        </div>
      )}

      <div className="targets-list">
        {!bootstrapped ? (
          <div className="target-group">
            <div className="target-skel" />
            <div className="target-skel" />
            <div className="target-skel" />
          </div>
        ) : null}
        {Object.entries(groupedTargets).map(([group, groupTargets]) => (
          <div key={group} className="target-group">
            {groupByDomain && <h3>{group} ({groupTargets.length})</h3>}
            {groupTargets.map((target) => (
              <div key={target.id} className={`target-item ${target.status}`}>
                <input type="checkbox" checked={selectedTargets.has(target.id!)} onChange={() => toggleSelection(target.id!)} />
                <div className="target-info">
                  <a href={target.url} target="_blank" rel="noopener noreferrer">{target.url}</a>
                  <div className="target-meta">
                    <span>Status: {target.status}</span>
                    <span>Source: {formatDiscoverySource(target.discovery_source)}</span>
                    <span>Created: {new Date(target.created_at!).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="target-actions">
                  <button onClick={() => checkTarget(target.id!)} className="btn-small btn-warning">Alive?</button>
                  {target.status === 'discovered' && (
                    <>
                      <button onClick={() => handleReviewTarget(target.id!, 'approve')} className="btn-small btn-success">Approve</button>
                      <button onClick={() => handleReviewTarget(target.id!, 'reject')} className="btn-small btn-danger">Reject</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <style jsx>{`
        .discovery-review { padding: 0; }
        .discovery-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; padding: 18px; background: rgba(255,255,255,0.84); border-radius: 18px; border: 1px solid rgba(15, 23, 42, 0.08); }
        .eyebrow { display: inline-flex; padding: 4px 10px; margin-bottom: 8px; border-radius: 999px; background: rgba(37, 99, 235, 0.10); color: #1d4ed8; font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
        .case-ref { color: #64748b; font-size: 14px; }
        .discovery-actions, .bulk-actions, .target-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .input-panel { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; background: rgba(255,255,255,0.84); border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 16px; padding: 16px; margin-bottom: 16px; }
        .input-panel input, .input-panel select, .filters select { padding: 9px 10px; border: 1px solid rgba(15, 23, 42, 0.10); border-radius: 10px; margin-right: 8px; background: #f8fafc; color: #0f172a; }
        .stats-panel { display: flex; gap: 12px; padding: 14px; background: rgba(255,255,255,0.84); border-radius: 16px; margin-bottom: 16px; flex-wrap: wrap; border: 1px solid rgba(15, 23, 42, 0.08); }
        .stat { display: flex; flex-direction: column; min-width: 96px; padding: 10px 12px; border-radius: 12px; background: rgba(248,250,252,0.96); }
        .stat span { font-size: 12px; color: #64748b; }
        .stat strong { font-size: 22px; }
        .stat-skel { height: 54px; border-radius: 12px; background: #e2e8f0; position: relative; overflow: hidden; }
        .preview-panel, .scan-result, .progress-panel { padding: 16px; background: rgba(255,255,255,0.84); border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 16px; margin-bottom: 16px; }
        .progress-bar { height: 14px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
        .progress-fill { height: 100%; background: #5a8ca8; transition: width 0.3s ease; }
        .progress-events { display: grid; gap: 4px; margin-top: 10px; font-size: 13px; color: #475569; }
        .preview-meta { display: flex; gap: 20px; margin-bottom: 12px; }
        .warning { color: #9a3412; }
        .query-list { display: grid; gap: 8px; max-height: 300px; overflow: auto; }
        .query-item { display: grid; gap: 4px; padding: 10px; background: rgba(248,250,252,0.96); border-left: 4px solid #64748b; }
        .query-item code { white-space: pre-wrap; word-break: break-word; }
        .query-skel { height: 72px; border-radius: 10px; background: #e2e8f0; position: relative; overflow: hidden; }
        .risk-low { border-left-color: #16a34a; }
        .risk-medium { border-left-color: #f59e0b; }
        .risk-high { border-left-color: #dc2626; }
        .filters { display: flex; gap: 20px; margin-bottom: 20px; }
        .targets-list { display: flex; flex-direction: column; gap: 20px; }
        .target-group { border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 16px; padding: 14px; background: rgba(255,255,255,0.84); }
        .target-item { display: flex; align-items: center; gap: 10px; padding: 12px 10px; border-bottom: 1px solid #eef2f7; }
        .target-item:last-child { border-bottom: none; }
        .target-item.false_positive { opacity: 0.5; }
        .target-info { flex: 1; }
        .target-info a { color: #2563eb; text-decoration: none; word-break: break-all; }
        .target-meta { display: flex; gap: 20px; margin-top: 5px; font-size: 12px; color: #475569; flex-wrap: wrap; }
        .target-skel { height: 78px; border-radius: 12px; background: #e2e8f0; margin: 10px 0; position: relative; overflow: hidden; }
        .btn-primary, .btn-warning, .btn-success, .btn-danger, .btn-secondary, .btn-small { padding: 9px 12px; border: none; border-radius: 10px; cursor: pointer; font-size: 14px; font-weight: 600; }
        .btn-small { padding: 6px 10px; font-size: 12px; }
        .btn-primary { background: linear-gradient(135deg, #2563eb, #1d4ed8); color: #f8fafc; }
        .btn-secondary { background: rgba(255,255,255,0.92); color: #0f172a; border: 1px solid rgba(15, 23, 42, 0.08); }
        .btn-warning { background: #fef3c7; color: #92400e; }
        .btn-success { background: #dcfce7; color: #166534; }
        .btn-danger { background: #fee2e2; color: #991b1b; }
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        @media (max-width: 900px) { .input-panel { grid-template-columns: 1fr; } .discovery-header { align-items: flex-start; flex-direction: column; } }
      `}</style>
    </div>
  );
};
