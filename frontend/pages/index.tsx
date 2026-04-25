import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { IntakeForm } from '../components/IntakeForm';
import { Action, Case, casesAPI, discoveryAPI, operationsAPI, Target } from '../api/client';
import { formatCaseReference } from '../utils/caseReference';

type DashboardCase = Case & {
  targets: Target[];
  actions: Action[];
  attentionScore: number;
  attentionLabel: string;
  confirmedCount: number;
  sentCount: number;
  removedCount: number;
  pendingApprovals: number;
  overdueItems: number;
  domains: string[];
  nextDueAt?: string;
  lastActivityAt?: string;
};

const isEmailAction = (action: Action) => String(action.type || '').startsWith('email_');

const isApprovedEmailAction = (action: Action) => {
  const status = String(action.status || '').toLowerCase();
  return isEmailAction(action) && (
    status === 'completed' ||
    status === 'scheduled' ||
    action.payload?.review?.decision === 'approve' ||
    action.payload?.delivery?.status === 'sent'
  );
};

const getDomain = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '').toLowerCase();
  } catch {
    return 'unknown';
  }
};

const getCaseAttention = (caseItem: Case, targets: Target[], actions: Action[]) => {
  const confirmedCount = targets.filter((target) => ['confirmed', 'contacted', 'escalated'].includes(String(target.status || '').toLowerCase())).length;
  const removedCount = targets.filter((target) => ['removed', 'resolved'].includes(String(target.status || '').toLowerCase())).length;
  const sentCount = actions.filter((action) => isApprovedEmailAction(action)).length;
  const pendingApprovals = actions.filter((action) => isEmailAction(action) && String(action.status || '').toLowerCase() === 'pending' && !action.payload?.review?.decision).length;
  const overdueItems = [
    ...targets.map((target) => target.next_action_at),
    ...actions.filter((action) => String(action.status || '').toLowerCase() === 'pending').map((action) => action.scheduled_at),
  ].filter(Boolean).filter((value) => new Date(value as string).getTime() < Date.now()).length;

  const activityDates = [
    caseItem.created_at,
    ...targets.map((target) => target.updated_at || target.created_at).filter(Boolean) as string[],
    ...actions.map((action) => action.executed_at || action.scheduled_at || action.created_at).filter(Boolean) as string[],
  ].map((value) => new Date(value).getTime()).filter((value) => !Number.isNaN(value));

  const lastActivityAt = activityDates.length > 0 ? new Date(Math.max(...activityDates)).toISOString() : undefined;
  const nextDueDates = [
    ...targets.map((target) => target.next_action_at),
    ...actions.filter((action) => String(action.status || '').toLowerCase() === 'pending').map((action) => action.scheduled_at),
  ].filter(Boolean).map((value) => new Date(value as string).toISOString()).sort();
  const nextDueAt = nextDueDates[0];

  const attentionScore = (pendingApprovals * 8) + (overdueItems * 12) + (confirmedCount * 2) + sentCount - (removedCount * 2);
  const attentionLabel = overdueItems > 0
    ? 'Needs action now'
    : pendingApprovals > 0
      ? 'Waiting on approval'
      : sentCount > 0
        ? 'Active'
        : 'Idle';

  return {
    confirmedCount,
    removedCount,
    sentCount,
    pendingApprovals,
    overdueItems,
    nextDueAt,
    lastActivityAt,
    attentionScore,
    attentionLabel,
  };
};

export default function Home() {
  const router = useRouter();
  const [cases, setCases] = useState<DashboardCase[]>([]);
  const [showIntake, setShowIntake] = useState(false);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'resolved' | 'suspended'>('all');

  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    setLoading(true);
    try {
      const data = await casesAPI.list();
      const enriched = await Promise.all((data.cases || []).map(async (caseItem) => {
        const [fullCase, targets, actions] = await Promise.all([
          casesAPI.get(caseItem.id),
          discoveryAPI.getTargets(caseItem.id),
          operationsAPI.listActions(caseItem.id),
        ]);
        const metrics = getCaseAttention(fullCase, targets, actions);
        const domains = Array.from(new Set(targets.map((target) => getDomain(target.url)).filter(Boolean)));
        return {
          ...fullCase,
          targets,
          actions,
          domains,
          ...metrics,
        };
      }));
      setCases(enriched);
    } catch (error) {
      console.error('Error loading cases:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCases = useMemo(() => {
    const term = search.trim().toLowerCase();
    return cases
      .filter((caseItem) => {
        if (statusFilter !== 'all' && caseItem.status !== statusFilter) return false;
        if (!term) return true;
        const caseRef = formatCaseReference(caseItem.id, caseItem.created_at).toLowerCase();
        return (
          caseItem.victim_id.toLowerCase().includes(term) ||
          caseRef.includes(term) ||
          caseItem.domains.some((domain) => domain.includes(term))
        );
      })
      .sort((a, b) => b.attentionScore - a.attentionScore || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [cases, search, statusFilter]);

  const totals = useMemo(() => ({
    cases: cases.length,
    attentionNow: cases.filter((item) => item.overdueItems > 0 || item.pendingApprovals > 0).length,
    active: cases.filter((item) => item.status === 'active').length,
    resolved: cases.filter((item) => item.status === 'resolved').length,
  }), [cases]);

  return (
    <div className="container">
      <header>
        <div className="brand">Community Edition</div>
        <h1>NCII Shield Community Edition</h1>
        <p>Operations console for sensitive takedown work. Cases are ranked by urgency, not creation date.</p>
      </header>

      <main>
        {!showIntake ? (
          <div className="dashboard">
            <div className="actions">
              <button onClick={() => setShowIntake(true)} className="primary-button">Create New Case</button>
              <button onClick={() => router.push('/settings')} className="secondary-button">Settings</button>
              <button onClick={loadCases} className="secondary-button">Refresh</button>
            </div>

            <div className="dashboard-metrics">
              <div className="metric-card"><span>Cases</span><strong>{totals.cases}</strong></div>
              <div className="metric-card"><span>Needs attention</span><strong>{totals.attentionNow}</strong></div>
              <div className="metric-card"><span>Active</span><strong>{totals.active}</strong></div>
              <div className="metric-card"><span>Resolved</span><strong>{totals.resolved}</strong></div>
            </div>

            <div className="filters">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search case ID, victim ID, or domain"
              />
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)}>
                <option value="all">All statuses</option>
                <option value="active">Active</option>
                <option value="resolved">Resolved</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>

            <div className="cases-list">
              <h2>Cases</h2>
              <p className="subtle">Sorted by what needs your attention now.</p>
              {loading ? (
                <div className="card-grid">
                  {[1, 2, 3].map((item) => (
                    <div key={item} className="case-card skeleton-card">
                      <div className="skeleton wide" />
                      <div className="skeleton mid" />
                      <div className="skeleton small" />
                      <div className="skeleton mid" />
                    </div>
                  ))}
                </div>
              ) : filteredCases.length === 0 ? (
                <div className="empty-state">
                  <h3>No cases match the current filter.</h3>
                  <p>Create a new case or clear the search to continue.</p>
                  <button onClick={() => setShowIntake(true)} className="primary-button">Create New Case</button>
                </div>
              ) : (
                <div className="card-grid">
                  {filteredCases.map((caseItem) => {
                    const caseRef = formatCaseReference(caseItem.id, caseItem.created_at);
                    return (
                      <article key={caseItem.id} className="case-card" onClick={() => router.push(`/cases/${caseItem.id}`)}>
                        <div className="case-head">
                          <div>
                            <div className="eyebrow">{caseItem.attentionLabel}</div>
                            <h3>{caseRef}</h3>
                            <p>{caseItem.victim_id}</p>
                          </div>
                          <span className={`status ${caseItem.status}`}>{caseItem.status}</span>
                        </div>
                        <div className="case-numbers">
                          <div><span>Confirmed</span><strong>{caseItem.confirmedCount}</strong></div>
                          <div><span>Sent</span><strong>{caseItem.sentCount}</strong></div>
                          <div><span>Removed</span><strong>{caseItem.removedCount}</strong></div>
                        </div>
                        <div className="case-foot">
                          <span>{caseItem.domains.length > 0 ? caseItem.domains.slice(0, 2).join(', ') : 'No domains yet'}</span>
                          <span>{caseItem.nextDueAt ? `Next due ${new Date(caseItem.nextDueAt).toLocaleDateString()}` : 'No deadline set'}</span>
                        </div>
                        {caseItem.overdueItems > 0 && <div className="attention-badge">Deadline missed</div>}
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div>
            <button onClick={() => { setShowIntake(false); loadCases(); }} className="back-button">
              Back to Dashboard
            </button>
            <IntakeForm onCaseCreated={() => { setShowIntake(false); loadCases(); }} />
          </div>
        )}
      </main>

      <style jsx global>{`
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }

        body {
          font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.06), transparent 32%),
            radial-gradient(circle at bottom right, rgba(15, 118, 110, 0.04), transparent 28%),
            #f8fafc;
          color: #0f172a;
        }

        .container {
          min-height: 100vh;
        }

        header {
          background: linear-gradient(135deg, rgba(255,255,255,0.94) 0%, rgba(248,250,252,0.96) 58%, rgba(239,246,255,0.94) 100%);
          color: #0f172a;
          padding: 44px 20px 38px;
          text-align: center;
          position: relative;
          overflow: hidden;
        }

        .brand {
          display: inline-flex;
          padding: 6px 12px;
          margin-bottom: 12px;
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.10);
          color: #1d4ed8;
          font-size: 12px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        header h1 {
          font-size: clamp(2rem, 4vw, 3.2rem);
          margin-bottom: 10px;
          letter-spacing: -0.03em;
        }

        header p {
          font-size: 1.05rem;
          opacity: 0.88;
          max-width: 760px;
          margin: 0 auto;
          color: #475569;
        }

        main {
          max-width: 1320px;
          margin: 0 auto;
          padding: 28px 20px 48px;
        }

        .dashboard {
          background: rgba(255, 255, 255, 0.84);
          backdrop-filter: blur(10px);
          padding: 28px;
          border-radius: 20px;
          box-shadow: 0 20px 60px rgba(2, 6, 23, 0.45);
          border: 1px solid rgba(15, 23, 42, 0.08);
          min-height: 420px;
        }

        .actions {
          display: flex;
          gap: 10px;
          margin-bottom: 22px;
        }

        .primary-button, .secondary-button, .back-button {
          border: none;
          padding: 12px 18px;
          border-radius: 12px;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
        }

        .primary-button {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          color: #f8fafc;
        }

        .secondary-button, .back-button {
          background: rgba(255,255,255,0.92);
          color: #0f172a;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .dashboard-metrics {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 18px;
        }

        .metric-card {
          background: rgba(255, 255, 255, 0.84);
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 16px;
          padding: 16px;
        }

        .metric-card span {
          display: block;
          color: #64748b;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 8px;
        }

        .metric-card strong {
          font-size: 1.8rem;
          color: #0f172a;
        }

        .filters {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 220px;
          gap: 12px;
          margin: 18px 0 26px;
        }

        .filters input, .filters select {
          width: 100%;
          background: rgba(255,255,255,0.92);
          border: 1px solid rgba(15, 23, 42, 0.08);
          color: #0f172a;
          padding: 12px 14px;
          border-radius: 12px;
        }

        .cases-list h2 {
          margin-bottom: 6px;
          font-size: 1.2rem;
        }

        .subtle {
          color: #475569;
          margin-bottom: 18px;
        }

        .empty-state {
          padding: 28px;
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.86);
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .empty-state h3 {
          margin-bottom: 8px;
        }

        .card-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 14px;
        }

        .case-card {
          position: relative;
          padding: 18px;
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.86);
          border: 1px solid rgba(15, 23, 42, 0.08);
          cursor: pointer;
          transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
        }

        .case-card:hover {
          transform: translateY(-1px);
          background: rgba(255, 255, 255, 0.98);
          border-color: rgba(59, 130, 246, 0.22);
        }

        .case-head {
          display: flex;
          align-items: start;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 16px;
        }

        .case-head h3 {
          font-size: 1.15rem;
          margin-top: 4px;
        }

        .case-head p {
          color: #475569;
          margin-top: 4px;
        }

        .eyebrow {
          color: #1d4ed8;
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .status {
          padding: 5px 10px;
          border-radius: 999px;
          font-size: 12px;
          text-transform: uppercase;
          font-weight: 700;
        }

        .status.active { background: rgba(34, 197, 94, 0.18); color: #86efac; }
        .status.resolved { background: rgba(59, 130, 246, 0.12); color: #1d4ed8; }
        .status.suspended { background: rgba(239, 68, 68, 0.12); color: #b91c1c; }

        .case-numbers {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 10px;
        }

        .case-numbers div {
          padding: 12px;
          border-radius: 14px;
          background: rgba(248, 250, 252, 0.92);
          border: 1px solid rgba(15, 23, 42, 0.06);
        }

        .case-numbers span {
          display: block;
          color: #64748b;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          margin-bottom: 8px;
        }

        .case-numbers strong {
          font-size: 1.5rem;
          color: #0f172a;
        }

        .case-foot {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          margin-top: 14px;
          color: #475569;
          font-size: 13px;
        }

        .attention-badge {
          position: absolute;
          top: 16px;
          right: 16px;
          padding: 4px 8px;
          border-radius: 999px;
          background: rgba(250, 204, 21, 0.18);
          color: #fde68a;
          font-size: 11px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .skeleton-card {
          min-height: 188px;
        }

        .skeleton, .info-skeleton {
          background: linear-gradient(90deg, rgba(148,163,184,0.08), rgba(148,163,184,0.18), rgba(148,163,184,0.08));
          background-size: 200% 100%;
          animation: shimmer 1.5s infinite;
          border-radius: 10px;
        }

        .skeleton.wide { height: 24px; margin-bottom: 14px; }
        .skeleton.mid { height: 16px; margin-bottom: 10px; }
        .skeleton.small { height: 12px; width: 60%; margin-bottom: 10px; }

        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        @media (max-width: 980px) {
          .dashboard-metrics,
          .card-grid {
            grid-template-columns: 1fr;
          }

          .filters {
            grid-template-columns: 1fr;
          }

          .case-foot {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
}
