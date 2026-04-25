import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { casesAPI, discoveryAPI, operationsAPI, Case, Target, Action, AuditEntry } from '../../api/client';
import { DiscoveryReview } from '../../components/discovery/DiscoveryReview';
import { formatCaseReference } from '../../utils/caseReference';

type Tab = 'overview' | 'discovery' | 'operations' | 'timeline';
type TimelineFilter = 'all' | 'operator' | 'system';

export default function CaseDetail() {
  const router = useRouter();
  const { id } = router.query;
  const caseId = Number(id);

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [targets, setTargets] = useState<Target[]>([]);
  const [actions, setActions] = useState<Action[]>([]);
  const [timeline, setTimeline] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>('all');

  useEffect(() => {
    if (!id) return;
    loadPage();
  }, [id]);

  const loadPage = async () => {
    setLoading(true);
    try {
      const [caseInfo, targetData, actionData, timelineData] = await Promise.all([
        casesAPI.get(caseId),
        discoveryAPI.getTargets(caseId),
        operationsAPI.listActions(caseId),
        operationsAPI.timeline(caseId),
      ]);
      setCaseData(caseInfo);
      setTargets(targetData);
      setActions(actionData);
      setTimeline(timelineData);
    } catch (error) {
      console.error('Error loading case page:', error);
    } finally {
      setLoading(false);
    }
  };

  const caseRef = useMemo(() => {
    if (!caseData) return 'NCII-PENDING';
    return formatCaseReference(caseData.id, caseData.created_at);
  }, [caseData]);

  function isEmailAction(action: Action) {
    return String(action.type || '').startsWith('email_');
  }

  function isRejectedEmailAction(action: Action) {
    return isEmailAction(action) && (
      (action.status || '').toLowerCase() === 'rejected' ||
      action.payload?.review?.decision === 'reject'
    );
  }

  function isApprovedEmailAction(action: Action) {
    return isEmailAction(action) && (
      (action.status || '').toLowerCase() === 'completed' ||
      (action.status || '').toLowerCase() === 'scheduled' ||
      action.payload?.review?.decision === 'approve' ||
      action.payload?.delivery?.status === 'sent'
    );
  }

  function formatDiscoverySource(source?: string) {
    if (!source) return 'Manual entry';
    if (source === 'manual_frontend') return 'Manual entry';
    if (source === 'manual') return 'Manual entry';
    return source.replace(/_/g, ' ');
  }

  function getTimelineCategory(entry: AuditEntry) {
    const action = String(entry.action || '').toLowerCase();
    if ([
      'created',
      'draft_created',
      'approved',
      'rejected',
      'manual_contact_added',
      'status_changed',
      'resolved',
      'kill_switch',
    ].includes(action) || action.startsWith('email_')) {
      return 'operator';
    }
    return 'system';
  }

  const stats = useMemo(() => {
    const discovered = targets.filter((target) => (target.status || '').toLowerCase() === 'discovered').length;
    const confirmed = targets.filter((target) => ['confirmed', 'contacted', 'escalated', 'removed', 'resolved'].includes((target.status || '').toLowerCase())).length;
    const contacted = targets.filter((target) => (target.status || '').toLowerCase() === 'contacted').length;
    const sentActions = actions.filter((action) => isApprovedEmailAction(action) && ((action.status || '').toLowerCase() === 'completed' || action.payload?.delivery?.status === 'sent')).length;
    const openedActions = actions.filter((action) => isApprovedEmailAction(action) && (action.payload?.tracking?.opened_at || Number(action.payload?.tracking?.open_count || 0) > 0)).length;
    const bouncedActions = actions.filter((action) => isApprovedEmailAction(action) && action.payload?.tracking?.delivery_status === 'bounced').length;

    return { discovered, confirmed, contacted, sentActions, openedActions, bouncedActions };
  }, [actions, targets]);

  const recentTargets = useMemo(() => targets.slice(0, 5), [targets]);
  const visibleActions = useMemo(() => actions.filter((action) => !isRejectedEmailAction(action)), [actions]);
  const approvedEmailActions = useMemo(() => visibleActions.filter((action) => isApprovedEmailAction(action)), [visibleActions]);
  const pendingEmailActions = useMemo(() => visibleActions.filter((action) => isEmailAction(action) && (action.status || '').toLowerCase() === 'pending' && !action.payload?.review?.decision), [visibleActions]);
  const monitoringActions = useMemo(() => visibleActions.filter((action) => !isEmailAction(action)), [visibleActions]);
  const recentActions = useMemo(() => visibleActions.slice(0, 6), [visibleActions]);
  const recentTimeline = useMemo(() => timeline.slice(0, 8), [timeline]);
  const filteredTimeline = useMemo(
    () => timeline.filter((entry) => timelineFilter === 'all' ? true : getTimelineCategory(entry) === timelineFilter),
    [timeline, timelineFilter]
  );

  const groupEmailActions = (items: Action[]) => {
    const grouped = new Map<string, Action[]>();
    items.forEach((action) => {
      const targetKey = String(action.target_id ?? action.id);
      const list = grouped.get(targetKey) || [];
      list.push(action);
      grouped.set(targetKey, list);
    });

    return Array.from(grouped.entries()).map(([targetId, group]) => ({
      targetId,
      latest: group[0],
      history: group.slice(1),
      count: group.length,
    }));
  };

  const pendingEmailGroups = useMemo(() => groupEmailActions(pendingEmailActions), [pendingEmailActions]);
  const approvedEmailGroups = useMemo(() => groupEmailActions(approvedEmailActions), [approvedEmailActions]);

  const getActionRecipient = (action: Action) => {
    const recipient = action.payload?.recipient;
    if (Array.isArray(recipient)) {
      return recipient.join(', ');
    }
    return recipient || 'Unspecified recipient';
  };

  const getActionSubject = (action: Action) => action.payload?.draft?.subject || `Action #${action.id}`;

  const getActionSentAt = (action: Action) => {
    return action.payload?.delivery?.sent_at || action.executed_at || action.scheduled_at || action.created_at;
  };

  const getActionLabel = (action: Action) => {
    const type = String(action.type || '').toLowerCase();
    const labels: Record<string, string> = {
      email_initial: 'Initial notice',
      email_followup: 'Follow-up notice',
      email_hosting: 'Hosting escalation',
      email_registrar: 'Registrar escalation',
      manual_escalation: 'Manual escalation',
      check_removal: 'Link check',
    };
    return labels[type] || type.replace(/_/g, ' ');
  };

  const getActionBodyPreview = (action: Action) => {
    const body = sanitizeDraftBody(action.payload?.draft?.body);
    if (!body) return '';
    return String(body).split('\n').slice(0, 6).join('\n');
  };

  const sanitizeDraftBody = (body?: string) => {
    if (!body) return '';
    const stopMarkers = [
      'case reference:',
      'client name:',
      'jurisdiction:',
      'authorization note:',
      'admin note:',
    ];

    const lines = String(body).split('\n');
    const kept: string[] = [];
    for (const line of lines) {
      const normalized = line.trim().toLowerCase();
      if (stopMarkers.some((marker) => normalized.startsWith(marker))) {
        break;
      }
      kept.push(line);
    }
    return kept.join('\n').trim() || String(body).trim();
  };

  const getActionDeliveryState = (action: Action) => {
    const tracking = action.payload?.tracking || {};
    const delivery = action.payload?.delivery || {};
    if (tracking.delivery_status === 'bounced' || delivery.status === 'failed') return 'bounced';
    if (tracking.opened_at || tracking.open_count > 0) return 'opened';
    if (tracking.delivered_at || delivery.status === 'sent') return 'delivered';
    return 'pending';
  };

  const getTargetActions = (targetId: number) => {
    return actions.filter((action) => {
      if (action.target_id !== targetId) return false;
      const status = (action.status || '').toLowerCase();
      const rejected = status === 'rejected' || action.payload?.review?.decision === 'reject';
      return !rejected;
    });
  };

  const getNextEmailOptions = (targetStatus?: string) => {
    const status = (targetStatus || '').toLowerCase();
    if (status === 'contacted') {
      return [
        { label: 'Follow-up', actionType: 'email_followup' as const },
        { label: 'Hosting', actionType: 'email_hosting' as const },
        { label: 'Registrar', actionType: 'email_registrar' as const },
        { label: 'Escalate', actionType: 'manual_escalation' as const },
      ];
    }

    return [
      { label: 'Prepare Notice', actionType: 'email_initial' as const },
      { label: 'Follow-up', actionType: 'email_followup' as const },
    ];
  };

  const runTargetStep = async (targetId: number, step: 'contact' | 'draft', actionType?: 'email_initial' | 'email_followup' | 'email_hosting' | 'email_registrar' | 'manual_escalation') => {
    setBusy(true);
    try {
      if (step === 'contact') {
        await operationsAPI.resolveContact(targetId);
      } else {
        await operationsAPI.createDraft(targetId, { action_type: actionType || 'email_initial', jurisdiction: 'US' });
      }
      await loadPage();
    } finally {
      setBusy(false);
    }
  };

  const reviewAction = async (actionId: number, decision: 'approve' | 'reject') => {
    setBusy(true);
    try {
      await operationsAPI.reviewAction(actionId, { decision, admin_id: 'local-admin' });
      await loadPage();
    } finally {
      setBusy(false);
    }
  };

  const killSwitch = async () => {
    if (!caseData) return;
    if (!confirm('Suspend this case and reject pending/scheduled outbound actions?')) return;
    await operationsAPI.killSwitch(caseData.id);
    await loadPage();
  };

  const resolveCase = async () => {
    if (!caseData) return;
    await operationsAPI.resolveCase(caseData.id);
    await loadPage();
  };

  const confirmedTargets = targets.filter((t) => ['confirmed', 'contacted', 'escalated'].includes((t.status || '').toLowerCase()));
  const readyDrafts: Action[] = [];

  return (
    <div className="case-detail">
      <div className="shell">
        <aside className="side-nav">
          <button onClick={() => router.push('/')} className="back-button">
            ← Dashboard
          </button>

          <div className="nav-card">
            <div className="eyebrow">Community Edition</div>
            <h1>{caseRef}</h1>
            <p>{caseData ? `Victim ID: ${caseData.victim_id}` : 'Loading case data…'}</p>
          </div>

          <div className="nav-links">
            {(['overview', 'discovery', 'operations', 'timeline'] as Tab[]).map((tab) => (
              <button
                key={tab}
                className={`nav-link ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className="nav-meta">
            <div className="meta-line">Case #{caseData?.id ?? '—'}</div>
            <div className="meta-line">{caseData?.status ?? 'loading'}</div>
            <div className="meta-line">{caseData ? new Date(caseData.created_at).toLocaleDateString() : '—'}</div>
          </div>
        </aside>

        <main className="main-panel">
          <div className="header-card">
            <div>
              <div className="eyebrow">Community Edition</div>
              <h1>{caseRef}</h1>
              <p>{caseData ? `Victim ID: ${caseData.victim_id}` : 'Loading case data…'}</p>
            </div>
            <div className="header-actions">
              <button className="secondary-button" onClick={() => router.push('/settings')} disabled={busy || loading}>Settings</button>
              <button className="danger-button" onClick={killSwitch} disabled={busy || loading}>Kill Switch</button>
              <button className="success-button" onClick={resolveCase} disabled={busy || loading}>Resolve Case</button>
            </div>
          </div>

          <div className="tabs sticky-tabs">
            {(['overview', 'discovery', 'operations', 'timeline'] as Tab[]).map((tab) => (
              <button
                key={tab}
                className={`tab ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          <div className="case-info">
            {loading ? (
              <>
                <div className="info-skeleton" />
                <div className="info-skeleton" />
                <div className="info-skeleton short" />
                <div className="info-skeleton" />
              </>
            ) : caseData ? (
              <>
                <div>Victim ID: {caseData.victim_id}</div>
                <div>Internal DB ID: #{caseData.id}</div>
                <div>Status: <span className={`status ${caseData.status}`}>{caseData.status}</span></div>
                <div>Created: {new Date(caseData.created_at).toLocaleDateString()}</div>
              </>
            ) : null}
          </div>

          <div className="tab-content">
            {activeTab === 'overview' && (
              <div className="overview-panel">
                <h2>Case Overview</h2>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton" />
                    <div className="panel-skeleton" />
                  </div>
                ) : (
                  <>
                    <p className="muted">Discovery, confirmation, and outbound actions are grouped here for a single case workflow.</p>

                    <div className="summary-grid">
                      <div className="summary-card">
                        <span className="summary-label">Discovered URLs</span>
                        <strong>{targets.length}</strong>
                        <span className="muted">{stats.discovered} still in discovery</span>
                      </div>
                      <div className="summary-card">
                        <span className="summary-label">Confirmed / escalated</span>
                        <strong>{stats.confirmed}</strong>
                        <span className="muted">{stats.contacted} contacted</span>
                      </div>
                      <div className="summary-card">
                        <span className="summary-label">Outbound notices</span>
                        <strong>{actions.length}</strong>
                        <span className="muted">{stats.sentActions} sent, {stats.bouncedActions} bounced</span>
                      </div>
                      <div className="summary-card">
                        <span className="summary-label">Engagement</span>
                        <strong>{stats.openedActions}</strong>
                        <span className="muted">opened / tracked</span>
                      </div>
                    </div>

                    {caseData?.authorization_doc && (
                      <div className="section-card">
                        <h3>Authorization</h3>
                        <p>{caseData.authorization_doc}</p>
                      </div>
                    )}

                    <div className="section-card">
                      <h3>Recent Discovery</h3>
                      {recentTargets.length === 0 ? (
                        <p className="muted">No URLs discovered yet.</p>
                      ) : (
                        <div className="mini-list">
                          {recentTargets.map((target) => (
                            <div key={target.id} className="mini-row">
                              <div>
                                <strong>{target.url}</strong>
                                <p className="muted">{formatDiscoverySource(target.discovery_source)} • {target.status || 'unknown'}</p>
                              </div>
                              <span className={`status ${(target.status || 'discovered').toLowerCase()}`}>{target.status || 'discovered'}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="section-card">
                      <h3>Outbound Activity</h3>
                      {recentActions.length === 0 ? (
                        <p className="muted">No outbound notices yet.</p>
                      ) : (
                        <div className="mini-list">
                          {recentActions.map((action) => (
                            <div key={action.id} className="mini-row">
                              <div>
                                <strong>{getActionSubject(action)}</strong>
                                <p className="muted">{getActionRecipient(action)}</p>
                              </div>
                              <div className="right-stack">
                                <span className={`badge badge-${getActionDeliveryState(action)}`}>{getActionDeliveryState(action)}</span>
                                <span className="muted">{action.status}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}

            {activeTab === 'discovery' && caseData && (
              <DiscoveryReview caseId={caseData.id} caseRef={caseRef} />
            )}

            {activeTab === 'operations' && (
              <div className="overview-panel ops-layout">
                <div className="ops-header">
                  <div>
                    <h2>Outbound Action Review</h2>
                    <p className="muted">Approve, send, or stop outgoing notices.</p>
                  </div>
                </div>

                <h3>Confirmed / Contacted Targets</h3>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton" />
                    <div className="panel-skeleton" />
                  </div>
                ) : confirmedTargets.length === 0 ? (
                  <p className="muted">No confirmed targets yet.</p>
                ) : confirmedTargets.map((target) => {
                  const targetActions = getTargetActions(target.id!);
                  const nextOptions = getNextEmailOptions(target.status);
                  return (
                    <div key={target.id} className="ops-card compact-card">
                      <div className="card-head">
                        <strong>{target.status}</strong>
                        <span className="muted">{formatDiscoverySource(target.discovery_source)}</span>
                      </div>
                      <a href={target.url} target="_blank" rel="noreferrer">{target.url}</a>

                      <div className="section-subhead">
                        <strong>Next email</strong>
                        <span>Choose the next step for this target</span>
                      </div>
                      <div className="ops-actions">
                        <button disabled={busy} onClick={() => runTargetStep(target.id!, 'contact')}>Resolve Contact</button>
                        {nextOptions.map((option) => (
                          <button
                            key={option.actionType}
                            disabled={busy}
                            className={option.actionType === 'manual_escalation' ? 'danger-button' : 'success-button'}
                            onClick={() => runTargetStep(target.id!, 'draft', option.actionType)}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>

                      <details className="history-drawer">
                        <summary>Target timeline ({targetActions.length})</summary>
                        <div className="history-list">
                          {targetActions.length === 0 ? (
                            <p className="muted">No actions yet.</p>
                          ) : targetActions.map((action) => (
                            <div key={action.id} className="history-item">
                              <strong>#{action.id}</strong>
                              <span>{getActionLabel(action)}</span>
                              <span>{action.status}</span>
                              <span>{new Date(action.created_at).toLocaleString()}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  );
                })}

                <h3>Pending Review</h3>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton tall" />
                  </div>
                ) : pendingEmailActions.length === 0 ? (
                  <p className="muted">No pending email drafts.</p>
                ) : pendingEmailGroups.map((group) => {
                  const action = group.latest;
                  return (
                    <div key={`pending-${group.targetId}`} className={`ops-card compact-card action-${(action.status || '').toLowerCase()}`}>
                      <div className="action-head">
                        <div>
                          <strong>{getActionSubject(action)}</strong>
                          <span>{getActionLabel(action)}</span>
                        </div>
                        <span>Action #{action.id}</span>
                      </div>
                      <div className="status-badges">
                        <span className={`badge badge-${getActionDeliveryState(action)}`}>{getActionDeliveryState(action)}</span>
                        {group.count > 1 && <span className="badge badge-pending">{group.count} drafts</span>}
                      </div>
                      <pre className="draft-excerpt">{getActionBodyPreview(action) || '(body not available yet)'}</pre>
                      <details className="draft-drawer">
                        <summary>
                          <span className="summary-title">View full email</span>
                          <span className="summary-chevron" aria-hidden="true">&#9662;</span>
                        </summary>
                        <div className="draft-meta">
                          <span><strong>Recipient:</strong> {getActionRecipient(action)}</span>
                          <span><strong>Target:</strong> {action.target_id}</span>
                          <span><strong>Template:</strong> {action.payload?.template_name || action.payload?.draft?.template_name || 'default'}</span>
                        </div>
                        <pre>{sanitizeDraftBody(action.payload?.draft?.body) || getActionBodyPreview(action) || '(body not available yet)'}</pre>
                      </details>
                      <div className="ops-actions">
                        <button disabled={busy} className="success-button" onClick={() => reviewAction(action.id, 'approve')}>Approve / Send</button>
                        <button disabled={busy} className="danger-button" onClick={() => reviewAction(action.id, 'reject')}>Reject</button>
                      </div>
                    </div>
                  );
                })}

                <h3>Sent Notices</h3>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton tall" />
                    <div className="panel-skeleton tall" />
                  </div>
                ) : readyDrafts.length === 0 ? (
                  <p className="muted">No sent notices yet.</p>
                ) : (
                  <div className="sent-table-wrap">
                    <table className="sent-table">
                      <thead>
                        <tr>
                          <th>To</th>
                          <th>Status</th>
                          <th>Subject</th>
                          <th>Sent</th>
                        </tr>
                      </thead>
                      <tbody>
                        {approvedEmailGroups.map((group) => {
                          const action = group.latest;
                          return (
                            <tr key={`sent-${group.targetId}`} className="sent-row">
                              <td>{getActionRecipient(action)}</td>
                              <td>
                                <span className={`badge badge-${getActionDeliveryState(action)}`}>{getActionDeliveryState(action)}</span>
                              </td>
                              <td>
                                <strong>{getActionSubject(action)}</strong>
                                <div className="row-subtle">{getActionLabel(action)}</div>
                              </td>
                              <td>{getActionSentAt(action) ? new Date(getActionSentAt(action)).toLocaleString() : 'Pending'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                <h3>Pending Review</h3>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton tall" />
                  </div>
                ) : pendingEmailActions.length === 0 ? (
                  <p className="muted">No pending email drafts.</p>
                ) : pendingEmailActions.map((action) => (
                  <div key={action.id} className={`ops-card compact-card action-${(action.status || '').toLowerCase()}`}>
                    <div className="action-head">
                      <div>
                        <strong>#{action.id} {getActionLabel(action)}</strong>
                        <span>pending review</span>
                      </div>
                      {action.scheduled_at && <span>Scheduled: {new Date(action.scheduled_at).toLocaleString()}</span>}
                    </div>
                    <div className="status-badges">
                      <span className={`badge badge-${getActionDeliveryState(action)}`}>{getActionDeliveryState(action)}</span>
                    </div>
                    <details className="draft-drawer">
                      <summary>
                        <span className="summary-title">{action.payload?.draft?.subject || `Action #${action.id}`}</span>
                        <span className="summary-chevron" aria-hidden="true">&#9662;</span>
                      </summary>
                      <div className="draft-meta">
                        <span><strong>Recipient:</strong> {getActionRecipient(action)}</span>
                        <span><strong>Action:</strong> {getActionLabel(action)}</span>
                      </div>
                      <pre>{sanitizeDraftBody(action.payload?.draft?.body) || '(body not available yet)'}</pre>
                    </details>
                    <div className="ops-actions">
                      <button disabled={busy} className="success-button" onClick={() => reviewAction(action.id, 'approve')}>Approve / Send</button>
                      <button disabled={busy} className="danger-button" onClick={() => reviewAction(action.id, 'reject')}>Reject</button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === 'timeline' && (
              <div className="overview-panel">
                <div className="timeline-head">
                  <div>
                    <h2>Audit Trail</h2>
                    <p className="muted">Forensic record of operator actions and system events.</p>
                  </div>
                  <div className="timeline-filters">
                    <button className={timelineFilter === 'all' ? 'active' : ''} onClick={() => setTimelineFilter('all')}>All</button>
                    <button className={timelineFilter === 'operator' ? 'active' : ''} onClick={() => setTimelineFilter('operator')}>Operator</button>
                    <button className={timelineFilter === 'system' ? 'active' : ''} onClick={() => setTimelineFilter('system')}>System</button>
                  </div>
                </div>
                {loading ? (
                  <div className="stack">
                    <div className="panel-skeleton tall" />
                    <div className="panel-skeleton tall" />
                  </div>
                ) : filteredTimeline.length === 0 ? (
                  <p className="muted">No timeline entries yet.</p>
                ) : (
                  filteredTimeline.map((entry) => (
                    <div key={entry.id} className="timeline-entry">
                      <div className="timeline-entry-head">
                        <strong>{entry.action}</strong>
                        <span className={`badge badge-${getTimelineCategory(entry)}`}>{getTimelineCategory(entry)}</span>
                      </div>
                      <span>{entry.entity_type} #{entry.entity_id}</span>
                      <span>{new Date(entry.created_at).toLocaleString()}</span>
                      <pre>{JSON.stringify(entry.new_value || entry.old_value || {}, null, 2)}</pre>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </main>
      </div>

      <style jsx>{`
        .case-detail {
          max-width: 1600px;
          margin: 0 auto;
          padding: 20px;
        }

        .shell {
          display: grid;
          grid-template-columns: 300px minmax(0, 1fr);
          gap: 18px;
          align-items: start;
        }

        .side-nav {
          position: sticky;
          top: 20px;
          display: grid;
          gap: 14px;
          align-self: start;
        }

        .nav-card, .nav-links, .nav-meta {
          background: rgba(255, 255, 255, 0.84);
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 18px;
          padding: 16px;
          box-shadow: 0 16px 30px rgba(15, 23, 42, 0.06);
        }

        .nav-card h1 {
          font-size: 1.45rem;
          margin-bottom: 4px;
        }

        .nav-links {
          display: grid;
          gap: 10px;
        }

        .nav-link {
          border: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(248, 250, 252, 0.96);
          padding: 10px 12px;
          border-radius: 12px;
          text-align: left;
          font-weight: 600;
          color: #0f172a;
        }

        .nav-link.active {
          background: #e2e8f0;
          color: #0f172a;
          border-color: #cbd5e1;
        }

        .nav-meta {
          display: grid;
          gap: 8px;
          color: #475569;
          font-size: 14px;
        }

        .main-panel {
          display: grid;
          gap: 16px;
          min-width: 0;
        }

        .header-card {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          padding: 18px 20px;
          background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,250,252,0.96));
          color: #0f172a;
          border-radius: 18px;
        }

        .eyebrow {
          display: inline-flex;
          padding: 4px 10px;
          margin-bottom: 8px;
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.10);
          color: #1d4ed8;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .header-card h1 {
          font-size: clamp(1.6rem, 3vw, 2.3rem);
          margin-bottom: 4px;
        }

        .header-card p {
          color: #475569;
        }

        .header-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }

        .back-button {
          background: rgba(255,255,255,0.92);
          color: #0f172a;
          border: 1px solid rgba(15, 23, 42, 0.08);
          padding: 8px 14px;
          border-radius: 10px;
          cursor: pointer;
          font-size: 14px;
          white-space: nowrap;
        }

        .case-info {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          padding: 14px 16px;
          background: rgba(255,255,255,0.84);
          backdrop-filter: blur(6px);
          border-radius: 16px;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .info-skeleton {
          height: 18px;
          border-radius: 999px;
          background: #e2e8f0;
          position: relative;
          overflow: hidden;
        }

        .info-skeleton.short {
          width: 60%;
        }

        .info-skeleton::after,
        .panel-skeleton::after {
          content: '';
          position: absolute;
          inset: 0;
          transform: translateX(-100%);
          background: linear-gradient(90deg, transparent, rgba(148,163,184,0.6), transparent);
          animation: shimmer 1.2s infinite;
        }

        .tabs {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .sticky-tabs {
          position: sticky;
          top: 18px;
          z-index: 10;
          background: rgba(248, 250, 252, 0.96);
          backdrop-filter: blur(8px);
          padding: 10px;
          border-radius: 16px;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .tab {
          padding: 10px 16px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(255,255,255,0.92);
          cursor: pointer;
          font-size: 14px;
          border-radius: 999px;
          font-weight: 600;
          color: #0f172a;
        }

        .tab.active {
          background: #e2e8f0;
          color: #0f172a;
          border-color: #cbd5e1;
        }

        .tab-content {
          min-height: 420px;
        }

        .overview-panel {
          padding: 18px;
          background: rgba(255, 255, 255, 0.84);
          border-radius: 18px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          box-shadow: 0 20px 50px rgba(15, 23, 42, 0.04);
        }

        .ops-layout {
          display: grid;
          gap: 14px;
        }

        .section-card, .ops-card, .timeline-entry {
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 14px;
          padding: 12px;
          margin: 10px 0;
          display: grid;
          gap: 10px;
          background: rgba(248, 250, 252, 0.96);
        }

        .summary-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          margin: 14px 0 8px;
        }

        .summary-card {
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 14px;
          padding: 14px;
          background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.94));
          display: grid;
          gap: 6px;
        }

        .summary-card strong {
          font-size: 1.5rem;
          letter-spacing: -0.03em;
          color: #0f172a;
        }

        .summary-label {
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: #64748b;
          font-weight: 700;
        }

        .section-subhead {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 12px;
          margin: 14px 0 8px;
          color: #475569;
        }

        .section-subhead strong {
          font-size: 14px;
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }

        .section-subhead span {
          font-size: 13px;
          color: #64748b;
        }

        .mini-list {
          display: grid;
          gap: 10px;
        }

        .mini-row {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 12px;
          padding: 12px;
          border-radius: 12px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(255,255,255,0.92);
        }

        .mini-row strong {
          display: block;
          margin-bottom: 4px;
          word-break: break-word;
        }

        .right-stack {
          display: grid;
          justify-items: end;
          gap: 6px;
          text-align: right;
        }

        .compact-card {
          margin: 8px 0;
        }

        .card-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
        }

        .stack {
          display: grid;
          gap: 12px;
          margin-top: 10px;
        }

        .panel-skeleton {
          position: relative;
          overflow: hidden;
          border-radius: 14px;
          background: #e2e8f0;
          height: 64px;
        }

        .panel-skeleton.tall {
          height: 160px;
        }

        .ops-header {
          margin-bottom: 12px;
        }

        .ops-card a {
          display: block;
          color: #2563eb;
          word-break: break-all;
          margin-top: 4px;
        }

        .action-head {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          flex-wrap: wrap;
        }

        .sent-table-wrap {
          overflow: hidden;
          border-radius: 16px;
          border: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(255,255,255,0.92);
        }

        .sent-table {
          width: 100%;
          border-collapse: collapse;
        }

        .sent-table th,
        .sent-table td {
          padding: 14px 16px;
          border-bottom: 1px solid rgba(15, 23, 42, 0.08);
          text-align: left;
          vertical-align: top;
        }

        .sent-table th {
          background: rgba(248, 250, 252, 0.98);
          color: #475569;
          font-size: 12px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .sent-row {
          background: rgba(255,255,255,0.92);
        }

        .sent-row td {
          color: #0f172a;
        }

        .sent-row td strong {
          display: block;
          margin-bottom: 4px;
        }

        .row-subtle {
          color: #64748b;
          font-size: 12px;
        }

        .status-badges {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .draft-drawer {
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 12px;
          background: rgba(248, 250, 252, 0.96);
          overflow: hidden;
        }

        .draft-drawer summary {
          cursor: pointer;
          font-weight: 700;
          padding: 12px 14px;
          list-style: none;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .draft-drawer summary::-webkit-details-marker {
          display: none;
        }

        .timeline-head {
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 14px;
          margin-bottom: 12px;
        }

        .timeline-filters {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .timeline-filters button {
          border: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(255,255,255,0.92);
          color: #0f172a;
          border-radius: 999px;
          padding: 8px 12px;
          cursor: pointer;
        }

        .timeline-filters button.active {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          border-color: transparent;
          color: #f8fafc;
        }

        .timeline-entry-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }

        .summary-title {
          min-width: 0;
        }

        .summary-chevron {
          flex: 0 0 auto;
          color: #64748b;
          transition: transform 160ms ease;
        }

        .draft-drawer[open] .summary-chevron {
          transform: rotate(180deg);
        }

        .history-drawer {
          border: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 12px;
          background: rgba(248, 250, 252, 0.96);
          overflow: hidden;
        }

        .history-drawer summary {
          cursor: pointer;
          padding: 10px 12px;
          font-weight: 700;
          list-style: none;
        }

        .history-drawer summary::-webkit-details-marker {
          display: none;
        }

        .history-list {
          display: grid;
          gap: 8px;
          padding: 10px 12px 12px;
          border-top: 1px solid rgba(15, 23, 42, 0.08);
          background: rgba(248, 250, 252, 0.96);
        }

        .history-item {
          display: grid;
          grid-template-columns: auto auto 1fr auto;
          gap: 10px;
          align-items: center;
          padding: 8px 10px;
          border-radius: 10px;
          background: rgba(255,255,255,0.92);
          border: 1px solid rgba(15, 23, 42, 0.08);
          font-size: 13px;
        }

        .draft-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          padding: 10px 14px 0;
          color: #475569;
          font-size: 13px;
        }

        .draft-excerpt {
          margin: 0;
          background: #f8fafc;
          border-top: 1px solid rgba(15, 23, 42, 0.08);
          border-bottom: 1px solid rgba(15, 23, 42, 0.08);
          border-left: none;
          border-right: none;
          border-radius: 0;
          padding: 12px 14px;
          max-height: 7.5em;
          overflow: hidden;
          white-space: pre-wrap;
          display: -webkit-box;
          -webkit-line-clamp: 5;
          -webkit-box-orient: vertical;
        }

        .draft-drawer pre {
          border: none;
          border-top: 1px solid rgba(15, 23, 42, 0.08);
          border-radius: 0;
          margin: 0;
          padding: 12px 14px;
          white-space: pre-wrap;
          background: #f8fafc;
          color: #0f172a;
        }

        .badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 8px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          background: #e2e8f0;
          color: #0f172a;
        }

        .badge-pending { background: #f3f4f6; color: #4b5563; }
        .badge-delivered { background: #dbeafe; color: #1d4ed8; }
        .badge-opened { background: #dcfce7; color: #166534; }
        .badge-bounced { background: #fee2e2; color: #b91c1c; }

        .ops-actions {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .ops-actions button, .success-button, .danger-button, .secondary-button {
          border: none;
          border-radius: 10px;
          padding: 8px 12px;
          cursor: pointer;
          font-weight: 600;
        }

        .secondary-button {
          background: rgba(255,255,255,0.92);
          color: #0f172a;
          border: 1px solid rgba(15, 23, 42, 0.08);
        }

        .success-button {
          background: linear-gradient(135deg, #2563eb, #1d4ed8);
          color: #f8fafc;
        }

        .danger-button {
          background: #fee2e2;
          color: #991b1b;
        }

        .status {
          padding: 4px 8px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
        }

        .status.active { background: #d1fae5; color: #065f46; }
        .status.resolved { background: #dbeafe; color: #1d4ed8; }
        .status.suspended { background: #fee2e2; color: #b91c1c; }

        pre {
          background: #172233;
          padding: 12px;
          overflow: auto;
          white-space: pre-wrap;
          border-radius: 12px;
          border: 1px solid rgba(148, 163, 184, 0.14);
          margin: 0;
        }

        .muted {
          color: #64748b;
        }

        button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        @keyframes shimmer {
          100% { transform: translateX(100%); }
        }

        @media (max-width: 1100px) {
          .shell {
            grid-template-columns: 1fr;
          }

          .side-nav {
            position: static;
          }
        }

        @media (max-width: 900px) {
          .case-info {
            grid-template-columns: 1fr 1fr;
          }

          .summary-grid {
            grid-template-columns: 1fr 1fr;
          }
        }

        @media (max-width: 640px) {
          .case-info {
            grid-template-columns: 1fr;
          }

          .summary-grid {
            grid-template-columns: 1fr;
          }

          .header-card {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
}

