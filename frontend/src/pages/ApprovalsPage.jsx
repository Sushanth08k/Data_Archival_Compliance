/**
 * Approvals page — review and approve/reject cleanup requests.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import approvalsService from '../services/approvals';
import { getErrorMessage } from '../utils/errors';


const STATUS_COLORS = {
  PENDING: 'badge-warning',
  APPROVED: 'badge-success',
  REJECTED: 'badge-error',
};

export default function ApprovalsPage() {
  const navigate = useNavigate();
  const [approvals, setApprovals] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [comments, setComments] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  useEffect(() => {
    loadApprovals();
  }, [filterStatus]);

  const loadApprovals = async () => {
    try {
      const data = await approvalsService.list(filterStatus || null);
      setApprovals(data.approvals || []);
    } catch {
      setError('Failed to load approvals');
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (approvalId, decision) => {
    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const result = await approvalsService.decide(approvalId, decision, comments);
      setSuccess(result.message);
      setComments('');
      setSelectedApproval(null);
      await loadApprovals();
    } catch (err) {
      setError(getErrorMessage(err, `Failed to ${decision.toLowerCase()}`));
    } finally {
      setActionLoading(false);
    }
  };

  const formatDate = (ts) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-overlay"><div className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Approval Queue</h1>
        <p className="subtitle">Review and approve or reject source cleanup requests.</p>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div className="alert alert-success" style={{ marginBottom: '16px' }}>{success}</div>}

      {/* Filter */}
      <div style={{ marginBottom: '24px', display: 'flex', gap: '8px' }}>
        {['', 'PENDING', 'APPROVED', 'REJECTED'].map((s) => (
          <button
            key={s}
            className={`btn ${filterStatus === s ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setFilterStatus(s); setLoading(true); }}
            style={{ padding: '6px 16px', fontSize: '0.8125rem' }}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {approvals.length === 0 ? (
        <div className="empty-state">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '16px' }}>
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          <h3>No {filterStatus ? filterStatus.toLowerCase() : ''} approvals</h3>
          <p>When a control run passes verification, approval requests will appear here.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {approvals.map((approval) => (
            <div key={approval.id} className="card" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ marginBottom: '4px', fontSize: '1rem' }}>
                    {approval.policy_name || 'Unknown Policy'}
                  </h3>
                  <div style={{ display: 'flex', gap: '12px', fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
                    <span>Requested by {approval.requested_by_email || 'Unknown'}</span>
                    <span>•</span>
                    <span>{formatDate(approval.created_at)}</span>
                  </div>
                </div>
                <span className={`badge ${STATUS_COLORS[approval.status]}`}>
                  {approval.status}
                </span>
              </div>

              {/* Summary */}
              <div style={{
                background: 'var(--color-bg)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px 16px',
                marginBottom: '12px',
                fontSize: '0.875rem',
              }}>
                <div style={{ display: 'flex', gap: '24px' }}>
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--color-text-secondary)' }}>Records to cleanup: </span>
                    <span style={{ fontWeight: 700, color: 'var(--color-primary)' }}>{approval.records_to_cleanup}</span>
                  </div>
                </div>
                {approval.summary && (
                  <p style={{ marginTop: '8px', color: 'var(--color-text-secondary)', fontSize: '0.8125rem' }}>
                    {approval.summary}
                  </p>
                )}
                {approval.cleanup_sql && (
                  <div style={{ marginTop: '12px' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>
                      📋 Generated Source Cleanup SQL Query (Pending Approval):
                    </div>
                    <pre style={{
                      background: '#0d1117',
                      color: '#58a6ff',
                      padding: '10px 14px',
                      borderRadius: '6px',
                      fontSize: '0.75rem',
                      overflowX: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      border: '1px solid #30363d',
                      fontFamily: 'Consolas, Monaco, monospace',
                      margin: 0,
                    }}>
                      <code>{approval.cleanup_sql}</code>
                    </pre>
                  </div>
                )}
              </div>

              {/* Review result */}
              {approval.status !== 'PENDING' && approval.reviewed_by_email && (
                <div style={{
                  background: approval.status === 'APPROVED' ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                  marginBottom: '12px',
                  fontSize: '0.8125rem',
                }}>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                    {approval.status === 'APPROVED' ? '✅ Approved' : '❌ Rejected'} by {approval.reviewed_by_email}
                  </div>
                  {approval.review_comments && <p>{approval.review_comments}</p>}
                  <div style={{ color: 'var(--color-text-muted)', marginTop: '4px' }}>
                    {formatDate(approval.reviewed_at)}
                  </div>
                </div>
              )}

              {/* Action buttons for pending approvals */}
              {approval.status === 'PENDING' && (
                <>
                  {selectedApproval === approval.id ? (
                    <div style={{ marginTop: '8px' }}>
                      <textarea
                        placeholder="Optional review comments..."
                        value={comments}
                        onChange={(e) => setComments(e.target.value)}
                        rows={2}
                        style={{
                          width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--color-border)', background: 'var(--color-bg)',
                          color: 'var(--color-text)', fontSize: '0.8125rem', resize: 'vertical',
                          marginBottom: '12px', fontFamily: 'inherit',
                        }}
                      />
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          className="btn btn-primary"
                          onClick={() => handleDecision(approval.id, 'APPROVED')}
                          disabled={actionLoading}
                          style={{ background: 'var(--color-success)' }}
                        >
                          {actionLoading ? 'Processing...' : '✅ Approve Cleanup'}
                        </button>
                        <button
                          className="btn btn-primary"
                          onClick={() => handleDecision(approval.id, 'REJECTED')}
                          disabled={actionLoading}
                          style={{ background: 'var(--color-error)' }}
                        >
                          {actionLoading ? 'Processing...' : '❌ Reject'}
                        </button>
                        <button className="btn btn-secondary" onClick={() => { setSelectedApproval(null); setComments(''); }}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <button className="btn btn-primary" onClick={() => setSelectedApproval(approval.id)}>
                        Review & Decide
                      </button>
                      <button className="btn btn-secondary" onClick={() => navigate('/control-runs')}>
                        View Control Run
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
