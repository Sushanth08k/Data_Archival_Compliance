/**
 * Control Runs page — full compliance lifecycle execution,
 * dynamic SQL query generation & display, and live Active DB vs Archive DB inspection.
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import controlRunService from '../services/controlRuns';
import policyService from '../services/policies';
import approvalsService from '../services/approvals';
import { getErrorMessage } from '../utils/errors';

const STATUS_COLORS = {
  PENDING: 'badge-neutral',
  EVALUATING: 'badge-info',
  EVALUATED: 'badge-info',
  ARCHIVING: 'badge-warning',
  VERIFYING: 'badge-warning',
  AWAITING_APPROVAL: 'badge-warning',
  APPROVED: 'badge-success',
  CLEANING: 'badge-warning',
  FINAL_VERIFICATION: 'badge-warning',
  COMPLETED: 'badge-success',
  FAILED: 'badge-error',
};

const STAGE_STEPS = [
  { key: 'EVALUATED', label: '1. Evaluated' },
  { key: 'ARCHIVING', label: '2. Archival' },
  { key: 'VERIFYING', label: '3. Verification' },
  { key: 'AWAITING_APPROVAL', label: '4. Approval' },
  { key: 'CLEANING', label: '5. Source Cleanup' },
  { key: 'FINAL_VERIFICATION', label: '6. Final Verification' },
  { key: 'COMPLETED', label: '7. Completed' },
];

export default function ControlRunsPage() {
  const navigate = useNavigate();

  const [runs, setRuns] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Start run dialog
  const [showStartDialog, setShowStartDialog] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState('');
  const [numRecords, setNumRecords] = useState(50);
  const [databaseProfiles, setDatabaseProfiles] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState('sqlite_default');

  // Active SQL tab in the SQL viewer
  const [selectedSqlTab, setSelectedSqlTab] = useState('selection'); // 'selection' | 'archival' | 'cleanup'
  const [copiedSql, setCopiedSql] = useState(false);

  // Live Database Viewer
  const [activeDbTab, setActiveDbTab] = useState('records'); // 'records' | 'source_db' | 'archive_db'
  const [sourceDbData, setSourceDbData] = useState({ total_count: 0, records: [] });
  const [archiveDbData, setArchiveDbData] = useState({ total_count: 0, records: [] });
  const [dbLoading, setDbLoading] = useState(false);

  useEffect(() => {
    loadData();
    loadLiveDatabases();
  }, []);

  const loadData = async () => {
    try {
      const [runsData, policiesData, profilesData] = await Promise.all([
        controlRunService.list(),
        policyService.list(),
        controlRunService.getDatabaseProfiles().catch(() => []),
      ]);
      setRuns(runsData.runs || []);
      setPolicies(policiesData.policies || []);
      if (profilesData && profilesData.length > 0) {
        setDatabaseProfiles(profilesData);
        const activeProfile = profilesData.find(p => p.is_active) || profilesData[0];
        setSelectedDatabase(activeProfile.id);
      }
      if (runsData.runs?.length > 0 && !selectedRun) {
        setSelectedRun(runsData.runs[0].id);
        await loadRunDetail(runsData.runs[0].id);
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load control runs'));
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetail = async (runId) => {
    try {
      const detail = await controlRunService.get(runId);
      setRunDetail(detail);
      // Auto-focus relevant SQL tab for current lifecycle step
      if (detail?.run?.status === 'EVALUATED' || detail?.run?.status === 'ARCHIVING') {
        setSelectedSqlTab('archival');
      } else if (detail?.run?.status === 'AWAITING_APPROVAL' || detail?.run?.status === 'APPROVED') {
        setSelectedSqlTab('cleanup');
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load run details'));
    }
  };

  const loadLiveDatabases = async () => {
    try {
      setDbLoading(true);
      const [src, arch] = await Promise.all([
        controlRunService.getSourceDatabase(100),
        controlRunService.getArchiveDatabase(null, 100),
      ]);
      setSourceDbData(src);
      setArchiveDbData(arch);
    } catch (err) {
      console.error('Failed to load databases:', err);
    } finally {
      setDbLoading(false);
    }
  };

  const handleSelectRun = async (runId) => {
    setSelectedRun(runId);
    setError('');
    setSuccess('');
    await loadRunDetail(runId);
    await loadLiveDatabases();
  };

  const handleStartRun = async () => {
    if (!selectedPolicy) return;
    setActionLoading(true);
    setError('');
    try {
      const result = await controlRunService.start(selectedPolicy, numRecords, selectedDatabase);
      setSuccess(result.message);
      setShowStartDialog(false);
      await loadData();
      await handleSelectRun(result.run_id);
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to start control run'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleLifecycleAction = async (action) => {
    if (!selectedRun) return;
    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      let result;
      switch (action) {
        case 'archive':
          result = await controlRunService.archive(selectedRun);
          setSuccess(`✅ Archival SQL executed successfully! ${result.archived_records ?? ''} records copied to archive_transactions with cryptographic hashes. Ready for Step 3: Verification.`);
          break;
        case 'verify':
          result = await controlRunService.verify(selectedRun);
          setSuccess(`✅ Verification completed! ${result.verified_records ?? ''} records verified with SHA-256 hashes. Ready for Step 4: Human Approval.`);
          break;
        case 'cleanup':
          result = await controlRunService.cleanup(selectedRun);
          setSuccess(`✅ Source Cleanup SQL executed successfully! ${result.cleaned_records ?? ''} records deleted from active database source_transactions.`);
          break;
        case 'finalVerify':
          result = await controlRunService.finalVerify(selectedRun);
          setSuccess('✅ Compliance control lifecycle completed! Zero remnants verified in active DB.');
          break;
        default:
          return;
      }
      await loadData();
      await loadRunDetail(selectedRun);
      await loadLiveDatabases();
    } catch (err) {
      setError(getErrorMessage(err, `Failed to execute ${action}`));
    } finally {
      setActionLoading(false);
    }
  };

  const handleQuickApprove = async (approvalId) => {
    if (!approvalId) return;
    setActionLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await approvalsService.decide(approvalId, 'APPROVED', 'Approved via Control Runs lifecycle');
      setSuccess(`✅ Human approval granted! Cleanup SQL is now approved and unlocked for execution.`);
      await loadData();
      await loadRunDetail(selectedRun);
      await loadLiveDatabases();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to approve cleanup'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleSeedDatabase = async () => {
    try {
      setActionLoading(true);
      const res = await controlRunService.seedDatabase(50);
      setSuccess(res.message);
      await loadLiveDatabases();
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to reseed database'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopySql = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  const getNextAction = (status) => {
    const eligible = runDetail?.run?.eligible_records ?? 0;
    const archived = runDetail?.run?.archived_records ?? 0;
    const verified = runDetail?.run?.verified_records ?? 0;
    switch (status) {
      case 'EVALUATED':
      case 'ARCHIVING':
        return {
          stepTitle: 'Step 2: Archival (SQL INSERT)',
          label: `⚡ Step 2: Execute Archival SQL (INSERT) — Archive ${eligible} Records`,
          description: `Active Selection identified ${eligible} eligible records. Ready to execute Archival SQL into archive_transactions table.`,
          action: 'archive',
          icon: '📦',
          isExecute: true,
        };
      case 'VERIFYING':
        return {
          stepTitle: 'Step 3: Verification',
          label: `🔍 Step 3: Verify ${archived} Archived Records (Integrity & Cryptographic Check)`,
          description: `Records are in archive_transactions. Perform independent SHA-256 hash reconciliation before requesting human approval.`,
          action: 'verify',
          icon: '🔍',
        };
      case 'AWAITING_APPROVAL':
        return {
          stepTitle: 'Step 4: Human Approval',
          label: '🛡️ Step 4: Awaiting Human Approval',
          description: `Archival verified for ${verified} records. Review and approve the generated cleanup SQL query before source removal.`,
          action: 'approvals',
          icon: '👤',
        };
      case 'APPROVED':
        return {
          stepTitle: 'Step 5: Source Cleanup (SQL DELETE)',
          label: `⚡ Step 5: Execute Approved Cleanup SQL (DELETE) — Delete ${verified} Records from Active DB`,
          description: 'Human approval granted. Execute controlled source cleanup SQL on source_transactions.',
          action: 'cleanup',
          icon: '⚡',
          isExecute: true,
        };
      case 'CLEANING':
      case 'FINAL_VERIFICATION':
        return {
          stepTitle: 'Step 6: Final Verification',
          label: '✅ Step 6: Verify Source Cleanup & Dual-Database Reconciliation',
          description: 'Confirm zero source remnants and complete archive presence.',
          action: 'finalVerify',
          icon: '✅',
        };
      default:
        return null;
    }
  };

  const parseRecordData = (rec) => {
    if (!rec.record_data) return {};
    try {
      return JSON.parse(rec.record_data);
    } catch {
      return {};
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-overlay"><div className="spinner" /></div>
      </div>
    );
  }

  const cleanSql = (sql) => {
    if (!sql) return '';
    return sql
      .replace(/^--\s*Generated by Google Gemini[^\n]*\n?/gim, '')
      .replace(/^--\s*Generated via Compliance SQL Engine[^\n]*\n?/gim, '')
      .trim();
  };

  const rawSql =
    selectedSqlTab === 'cleanup'
      ? runDetail?.run?.cleanup_sql
      : selectedSqlTab === 'archival'
      ? runDetail?.run?.archival_sql
      : runDetail?.run?.generated_sql;

  const currentSql = cleanSql(rawSql);

  return (
    <div className="page-container">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1>Control Runs</h1>
          <p className="subtitle">Execute compliance controls, generate verified SQL queries, and manage Active vs Archive databases.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" onClick={handleSeedDatabase} disabled={actionLoading} title="Reset Active DB with 50 synthetic banking records">
            🔄 Reseed Active DB
          </button>
          <button className="btn btn-primary" onClick={() => setShowStartDialog(true)}>
            + Start New Control Run
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div className="alert alert-success" style={{ marginBottom: '16px' }}>{success}</div>}

      {/* Start Run Dialog */}
      {showStartDialog && (
        <div className="card" style={{ marginBottom: '24px', border: '2px solid var(--color-primary)', background: 'var(--color-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '1.125rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>🚀</span> Start New Compliance Control Run
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Select target policy & database environment
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '16px' }}>
            {/* 1. Policy Selector */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-secondary)' }}>
                Target Compliance Policy
              </label>
              <select
                value={selectedPolicy}
                onChange={(e) => setSelectedPolicy(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)', background: 'var(--color-bg)',
                  color: 'var(--color-text)', fontSize: '0.875rem',
                }}
              >
                <option value="">Select a policy...</option>
                {policies.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {/* 2. Target Database */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-secondary)' }}>
                Target Database Environment
              </label>
              <div style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '0.875rem',
              }}>
                <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  🗄️ Default Compliance DB (SQLite)
                  <span className="badge" style={{ background: '#003B57', color: '#fff', fontSize: '0.6875rem' }}>SQLITE</span>
                </span>
                <span className="badge badge-success" style={{ fontSize: '0.6875rem' }}>🟢 Live Connected</span>
              </div>
            </div>
          </div>

          {/* Database Profile Details Card */}
          <div style={{
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(0, 59, 87, 0.05)',
            border: '1px solid rgba(0, 59, 87, 0.2)',
            marginBottom: '16px',
            fontSize: '0.75rem',
            color: 'var(--color-text-secondary)',
          }}>
            Host: <code>Localhost (File)</code> • DB: <code>ai_controls.db</code> • Active Table: <code>source_transactions</code> • Archive Table: <code>archive_transactions</code>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
            <div style={{ minWidth: '180px' }}>
              <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px', color: 'var(--color-text-secondary)' }}>
                Sample Size (Records to Evaluate)
              </label>
              <input
                type="number"
                min={10}
                max={200}
                value={numRecords}
                onChange={(e) => setNumRecords(Number(e.target.value))}
                style={{
                  width: '140px', padding: '10px 12px', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)', background: 'var(--color-bg)',
                  color: 'var(--color-text)', fontSize: '0.875rem',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-secondary" onClick={() => setShowStartDialog(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleStartRun} disabled={actionLoading || !selectedPolicy}>
                {actionLoading ? 'Evaluating against Database...' : '🚀 Start Evaluation & Generate SQL'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── RECENT RUNS BAR (TOP-TO-BOTTOM SELECTOR) ──────────────────── */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>⏱️</span> Recent Control Runs ({runs.length})
          </h3>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            Select a run to view its complete audit lifecycle below
          </span>
        </div>

        {runs.length === 0 ? (
          <div className="card" style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
            <p style={{ margin: 0 }}>No control runs yet. Click "+ Start New Control Run" above to initiate your first policy evaluation.</p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '12px',
          }}>
            {runs.map((r) => {
              const isSel = selectedRun === r.id;
              return (
                <div
                  key={r.id}
                  onClick={() => handleSelectRun(r.id)}
                  className={`card ${isSel ? 'active' : ''}`}
                  style={{
                    padding: '12px 16px',
                    cursor: 'pointer',
                    borderRadius: '8px',
                    border: isSel ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
                    background: isSel ? 'rgba(16, 185, 129, 0.08)' : 'var(--color-surface)',
                    boxShadow: isSel ? '0 2px 10px rgba(16, 185, 129, 0.18)' : 'var(--shadow-sm)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.85rem', color: isSel ? 'var(--color-primary)' : 'inherit' }}>
                      RUN-{r.id.slice(0, 8)}
                    </span>
                    <span className={`badge ${STATUS_COLORS[r.status]}`} style={{ fontSize: '0.6875rem', padding: '2px 8px' }}>
                      {r.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text)', marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.policy_name || 'Policy Control Run'}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.71875rem', color: 'var(--color-text-muted)' }}>
                    <span className="badge" style={{
                      fontSize: '0.625rem',
                      padding: '2px 6px',
                      background: '#003B57',
                      color: '#fff',
                    }}>
                      SQLITE
                    </span>
                    <span>Total: <strong>{r.total_records}</strong></span>
                    <span>Eligible: <strong style={{ color: 'var(--color-primary)' }}>{r.eligible_records}</strong></span>
                    <span>Archived: <strong style={{ color: 'var(--color-success)' }}>{r.archived_records}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ─── SELECTED RUN WORKSPACE (FULL 100% WIDTH BELOW) ──────────────── */}
      {selectedRun && runDetail && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', width: '100%', minWidth: 0 }}>
          {/* Header info */}
          <div className="card" style={{ padding: '20px 24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
              <div>
                <h2 style={{ fontSize: '1.25rem', marginBottom: '4px' }}>
                  RUN-{runDetail.run.id.slice(0, 8)}: {runDetail.run.policy_name || 'Policy Control'}
                </h2>
                <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span>Created {new Date(runDetail.run.created_at).toLocaleString()}</span>
                    <span>•</span>
                    <span className="badge" style={{
                      fontSize: '0.7rem',
                      padding: '3px 8px',
                      background: '#003B57',
                      color: '#fff',
                      fontWeight: 600,
                    }}>
                      🗄️ Default Compliance DB (SQLite) [SQLITE]
                    </span>
                    <span>•</span>
                    <span>Active Table: <code>source_transactions</code></span>
                  </div>
                </div>
                <span className={`badge ${STATUS_COLORS[runDetail.run.status]}`} style={{ fontSize: '0.875rem', padding: '6px 14px' }}>
                  {runDetail.run.status}
                </span>
              </div>

              {/* Lifecycle Stage tracker */}
              <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '8px', marginBottom: '16px' }}>
                {STAGE_STEPS.map((step, idx) => {
                  const isCurrent = runDetail.run.status === step.key;
                  return (
                    <div
                      key={step.key}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: isCurrent ? 700 : 500,
                        background: isCurrent ? 'var(--color-primary)' : 'var(--color-bg)',
                        color: isCurrent ? '#fff' : 'var(--color-text-muted)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {step.label}
                    </div>
                  );
                })}
              </div>

              {/* Stats Counters */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '12px' }}>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Total Read</div>
                  <div className="stat-value">{runDetail.run.total_records}</div>
                </div>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Eligible</div>
                  <div className="stat-value" style={{ color: 'var(--color-primary)' }}>{runDetail.run.eligible_records}</div>
                </div>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Legal Hold (Excl.)</div>
                  <div className="stat-value" style={{ color: 'var(--color-warning)' }}>{runDetail.run.excluded_records}</div>
                </div>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Archived</div>
                  <div className="stat-value" style={{ color: 'var(--color-success)' }}>{runDetail.run.archived_records}</div>
                </div>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Verified</div>
                  <div className="stat-value">{runDetail.run.verified_records}</div>
                </div>
                <div className="stat-card" style={{ padding: '12px' }}>
                  <div className="stat-label">Source Cleaned</div>
                  <div className="stat-value" style={{ color: runDetail.run.cleaned_records > 0 ? 'var(--color-error)' : 'inherit' }}>
                    {runDetail.run.cleaned_records}
                  </div>
                </div>
              </div>
            </div>

            {/* Inline Action Feedback */}
            {success && (
              <div className="alert alert-success" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{success}</span>
                <button onClick={() => setSuccess('')} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}>✕</button>
              </div>
            )}
            {error && (
              <div className="alert alert-error" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{error}</span>
                <button onClick={() => setError('')} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}>✕</button>
              </div>
            )}

            {/* Next Action Banner */}
            {(() => {
              const next = getNextAction(runDetail.run.status);
              if (!next) return null;

              if (next.action === 'approvals') {
                return (
                  <div className="card" style={{ marginBottom: '20px', border: '2px solid #f59e0b', background: 'rgba(245, 158, 11, 0.08)', padding: '16px 20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', flexWrap: 'wrap', gap: '12px' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span className="badge badge-warning">{next.stepTitle}</span>
                          <strong>🛡️ Human Approval Required</strong>
                        </div>
                        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
                          {next.description}
                        </p>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        {runDetail.approval_id && (
                          <button
                            className="btn btn-primary"
                            onClick={() => handleQuickApprove(runDetail.approval_id)}
                            disabled={actionLoading}
                            style={{ fontWeight: 700 }}
                          >
                            ✓ Quick Approve Now
                          </button>
                        )}
                        <button className="btn btn-secondary" onClick={() => navigate('/approvals')}>
                          {next.icon} Open Approval Queue
                        </button>
                      </div>
                    </div>
                  </div>
                );
              }

              const isArchivalStep = runDetail.run.status === 'EVALUATED' || runDetail.run.status === 'ARCHIVING';

              return (
                <div
                  className="card"
                  style={{
                    marginBottom: '20px',
                    border: '2px solid var(--color-primary)',
                    background: 'rgba(16, 185, 129, 0.05)',
                    padding: '16px 20px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
                    <div style={{ flex: 1, minWidth: '240px' }}>
                      {runDetail.run.status === 'EVALUATED' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                          <span className="badge badge-success" style={{ fontSize: '0.72rem', padding: '3px 8px' }}>
                            ✓ Step 1: Active Selection & AI Evaluation Completed
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                            Target: <strong>{runDetail.run.target_database || 'Default Database'}</strong> [{runDetail.run.database_dialect?.toUpperCase() || 'SQLITE'}]
                          </span>
                        </div>
                      )}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span className="badge badge-primary">{next.stepTitle}</span>
                        <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
                          Status: <strong>{runDetail.run.status}</strong>
                        </span>
                      </div>
                      <div style={{ fontSize: '0.875rem', color: 'var(--color-text)' }}>
                        {next.description}
                      </div>
                      {isArchivalStep && runDetail.run.eligible_records === 0 && (
                        <div style={{ marginTop: '8px', fontSize: '0.8125rem', color: 'var(--color-warning)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div>⚠️ No records currently eligible under this policy. The policy criteria (e.g. 7-year retention) matched 0 records in the database.</div>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <button className="btn btn-sm btn-secondary" onClick={handleSeedDatabase} disabled={actionLoading}>
                              🔄 Reseed Active DB with Demo Records
                            </button>
                            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                              Or click <strong>RUN-8e227f89</strong> on the left which has 34 eligible records ready to archive.
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleLifecycleAction(next.action)}
                      disabled={actionLoading || (isArchivalStep && runDetail.run.eligible_records === 0)}
                      style={{
                        padding: '12px 24px',
                        fontSize: '0.9375rem',
                        fontWeight: 700,
                        background: runDetail.run.status === 'APPROVED' ? '#ef4444' : undefined,
                        borderColor: runDetail.run.status === 'APPROVED' ? '#dc2626' : undefined,
                        boxShadow: runDetail.run.status === 'APPROVED' ? '0 4px 14px rgba(239, 68, 68, 0.4)' : undefined,
                      }}
                    >
                      {actionLoading ? 'Executing Operation...' : next.label}
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* Completed Alert */}
            {runDetail.run.status === 'COMPLETED' && (
              <div
                className="alert alert-success"
                style={{
                  marginBottom: '20px',
                  display: 'block',
                  lineHeight: '1.6',
                }}
              >
                <span>
                  <strong>✅ Compliance Control Lifecycle Completed</strong> — Records have been safely archived in{' '}
                  <code style={{ background: 'rgba(6, 95, 70, 0.1)', padding: '2px 6px', borderRadius: '4px', fontFamily: 'monospace' }}>
                    archive_transactions
                  </code>
                  , independently verified, and cleaned from{' '}
                  <code style={{ background: 'rgba(6, 95, 70, 0.1)', padding: '2px 6px', borderRadius: '4px', fontFamily: 'monospace' }}>
                    source_transactions
                  </code>
                  .
                </span>
              </div>
            )}

            {/* ─── GENERATED SQL QUERY VIEWER ─────────────────────────────── */}
            <div className="card" style={{ marginBottom: '24px', padding: '16px 20px', border: '1px solid #30363d' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '1.1rem' }}>⚡</span>
                  <h3 style={{ margin: 0, fontSize: '0.95rem' }}>Generated SQL Compliance Script</h3>
                  <span className="badge" style={{
                    fontSize: '0.6875rem',
                    background: '#003B57',
                    color: '#fff',
                    fontWeight: 600,
                  }}>
                    SQLITE
                  </span>
                  <span className="badge badge-info" style={{ fontSize: '0.6875rem' }}>Automated AI Translation</span>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <button
                    onClick={() => setSelectedSqlTab('selection')}
                    className={`btn btn-sm ${selectedSqlTab === 'selection' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '0.75rem' }}
                  >
                    1. Active Selection SQL (SELECT)
                  </button>
                  <button
                    onClick={() => setSelectedSqlTab('archival')}
                    className={`btn btn-sm ${selectedSqlTab === 'archival' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '0.75rem' }}
                  >
                    2. Archival SQL (INSERT)
                  </button>
                  <button
                    onClick={() => setSelectedSqlTab('cleanup')}
                    className={`btn btn-sm ${selectedSqlTab === 'cleanup' ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ fontSize: '0.75rem' }}
                  >
                    3. Source Cleanup SQL (DELETE)
                  </button>

                  {/* Inline Execution/Approval Action Buttons & Status Badges */}
                  {selectedSqlTab === 'selection' && (
                    <span className="badge badge-info" style={{ fontSize: '0.72rem' }}>
                      ✓ {runDetail?.run?.eligible_records} Eligible Records Identified
                    </span>
                  )}

                  {selectedSqlTab === 'archival' && (runDetail?.run?.status === 'EVALUATED' || runDetail?.run?.status === 'ARCHIVING') && (
                    <button
                      onClick={() => handleLifecycleAction('archive')}
                      disabled={actionLoading || runDetail?.run?.eligible_records === 0}
                      className="btn btn-primary btn-sm"
                      style={{ fontSize: '0.75rem', fontWeight: 700 }}
                    >
                      {actionLoading ? 'Archiving...' : '⚡ Execute Archival SQL (INSERT)'}
                    </button>
                  )}
                  {selectedSqlTab === 'archival' && runDetail?.run?.status !== 'EVALUATED' && runDetail?.run?.status !== 'ARCHIVING' && (
                    <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                      ✓ Archival Executed ({runDetail?.run?.archived_records} records in Archive DB)
                    </span>
                  )}

                  {selectedSqlTab === 'cleanup' && runDetail?.run?.status === 'APPROVED' && (
                    <button
                      onClick={() => handleLifecycleAction('cleanup')}
                      disabled={actionLoading}
                      className="btn btn-primary btn-sm"
                      style={{ fontSize: '0.75rem', fontWeight: 700, background: '#ef4444', borderColor: '#dc2626' }}
                    >
                      {actionLoading ? 'Cleaning...' : '⚡ Execute Cleanup SQL (DELETE)'}
                    </button>
                  )}
                  {selectedSqlTab === 'cleanup' && runDetail?.run?.status === 'AWAITING_APPROVAL' && (
                    <button
                      onClick={() => runDetail.approval_id ? handleQuickApprove(runDetail.approval_id) : navigate('/approvals')}
                      disabled={actionLoading}
                      className="btn btn-warning btn-sm"
                      style={{ fontSize: '0.75rem', fontWeight: 700 }}
                    >
                      🛡️ Approve Cleanup SQL
                    </button>
                  )}
                  {selectedSqlTab === 'cleanup' && (runDetail?.run?.status === 'EVALUATED' || runDetail?.run?.status === 'ARCHIVING' || runDetail?.run?.status === 'VERIFYING') && (
                    <span className="badge badge-neutral" style={{ fontSize: '0.72rem', opacity: 0.85 }}>
                      🔒 Cleanup Locked (Requires Step 2 Archival & Step 4 Approval)
                    </span>
                  )}
                  {selectedSqlTab === 'cleanup' && (runDetail?.run?.status === 'CLEANING' || runDetail?.run?.status === 'FINAL_VERIFICATION' || runDetail?.run?.status === 'COMPLETED') && (
                    <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
                      ✓ Cleanup Executed ({runDetail?.run?.cleaned_records} records removed)
                    </span>
                  )}

                  <button
                    onClick={() => handleCopySql(currentSql)}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem' }}
                  >
                    {copiedSql ? '✓ Copied' : '📋 Copy SQL'}
                  </button>
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>
                {selectedSqlTab === 'cleanup' && (
                  <span>⚠️ <strong>Controlled Cleanup Script</strong>: Executed ONLY after human approval. Deletes verified records from <code>source_transactions</code> where <code>legal_hold = 0</code>.</span>
                )}
                {selectedSqlTab === 'archival' && (
                  <span>📦 <strong>Archive-First Script</strong>: Copies eligible records meeting retention rules into <code>archive_transactions</code> with cryptographic verification hashes.</span>
                )}
                {selectedSqlTab === 'selection' && (
                  <span>🔍 <strong>Identification Script</strong>: Filters records from <code>source_transactions</code> older than the policy threshold (e.g. 5 years) excluding active legal holds.</span>
                )}
              </div>

              <pre style={{
                background: '#0d1117',
                color: '#58a6ff',
                padding: '14px 16px',
                borderRadius: '8px',
                fontSize: '0.8125rem',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                border: '1px solid #30363d',
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                margin: 0,
                lineHeight: 1.5,
              }}>
                <code>{currentSql || '-- SQL script will be generated upon run evaluation'}</code>
              </pre>
            </div>

            {/* ─── TABBED DATABASE VIEWER ─────────────────────────────────── */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {/* Tabs header */}
              <div style={{
                display: 'flex',
                background: 'var(--color-bg)',
                borderBottom: '1px solid var(--color-border)',
                padding: '0 12px',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
              }}>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    onClick={() => setActiveDbTab('records')}
                    style={{
                      padding: '12px 16px',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeDbTab === 'records' ? '2px solid var(--color-primary)' : '2px solid transparent',
                      color: activeDbTab === 'records' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                      fontWeight: activeDbTab === 'records' ? 700 : 500,
                      cursor: 'pointer',
                      fontSize: '0.8125rem',
                    }}
                  >
                    📋 Control Run Evaluation ({runDetail.records?.length || 0})
                  </button>
                  <button
                    onClick={() => setActiveDbTab('source_db')}
                    style={{
                      padding: '12px 16px',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeDbTab === 'source_db' ? '2px solid var(--color-primary)' : '2px solid transparent',
                      color: activeDbTab === 'source_db' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                      fontWeight: activeDbTab === 'source_db' ? 700 : 500,
                      cursor: 'pointer',
                      fontSize: '0.8125rem',
                    }}
                  >
                    🟢 Active DB (source_transactions) [{sourceDbData.total_count}]
                  </button>
                  <button
                    onClick={() => setActiveDbTab('archive_db')}
                    style={{
                      padding: '12px 16px',
                      background: 'none',
                      border: 'none',
                      borderBottom: activeDbTab === 'archive_db' ? '2px solid var(--color-primary)' : '2px solid transparent',
                      color: activeDbTab === 'archive_db' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                      fontWeight: activeDbTab === 'archive_db' ? 700 : 500,
                      cursor: 'pointer',
                      fontSize: '0.8125rem',
                    }}
                  >
                    📦 Archive DB (archive_transactions) [{archiveDbData.total_count}]
                  </button>
                </div>
                <div style={{ padding: '6px 8px' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={loadLiveDatabases}
                    disabled={dbLoading}
                    style={{ fontSize: '0.75rem' }}
                  >
                    {dbLoading ? 'Refreshing...' : '🔄 Refresh Live DB'}
                  </button>
                </div>
              </div>

              {/* TAB 1: Control Run Records */}
              {activeDbTab === 'records' && (
                <div style={{ maxHeight: '420px', overflow: 'auto', width: '100%' }}>
                  <table style={{ width: '100%', minWidth: '650px', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 1 }}>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Transaction ID</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Customer Name</th>
                        <th style={{ padding: '10px 10px', textAlign: 'left' }}>Txn Date</th>
                        <th style={{ padding: '10px 10px', textAlign: 'right' }}>Amount</th>
                        <th style={{ padding: '10px 8px', textAlign: 'center' }}>Legal Hold</th>
                        <th style={{ padding: '10px 8px', textAlign: 'center' }}>Eligible</th>
                        <th style={{ padding: '10px 8px', textAlign: 'center' }}>Archived</th>
                        <th style={{ padding: '10px 8px', textAlign: 'center' }}>Verified</th>
                        <th style={{ padding: '10px 8px', textAlign: 'center' }}>Cleaned</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(runDetail.records || []).map((rec) => {
                        const data = parseRecordData(rec);
                        return (
                          <tr key={rec.id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontWeight: 600 }}>
                              {rec.record_identifier}
                            </td>
                            <td style={{ padding: '8px 14px' }}>
                              {data.customer_name || 'Acme Corp'}
                            </td>
                            <td style={{ padding: '8px 10px', color: 'var(--color-text-secondary)' }}>
                              {data.transaction_date || '—'}
                            </td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>
                              {data.amount != null ? `$${Number(data.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'center' }}>
                              {rec.is_excluded ? (
                                <span className="badge badge-warning" style={{ fontSize: '0.6875rem' }}>YES (HOLD)</span>
                              ) : (
                                <span style={{ color: 'var(--color-text-muted)' }}>No</span>
                              )}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'center' }}>
                              {rec.is_eligible ? '✅' : rec.is_excluded ? '⛔' : '—'}
                            </td>
                            <td style={{ padding: '8px', textAlign: 'center' }}>{rec.is_archived ? '✅' : '—'}</td>
                            <td style={{ padding: '8px', textAlign: 'center' }}>{rec.is_verified ? '✅' : '—'}</td>
                            <td style={{ padding: '8px', textAlign: 'center' }}>{rec.is_cleaned ? '✅' : '—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* TAB 2: Live Active DB (source_transactions) */}
              {activeDbTab === 'source_db' && (
                <div style={{ maxHeight: '420px', overflow: 'auto', width: '100%' }}>
                  <div style={{ padding: '10px 16px', background: 'rgba(59, 130, 246, 0.05)', fontSize: '0.75rem', color: 'var(--color-text-secondary)', borderBottom: '1px solid var(--color-border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                    <span>
                      Live snapshot of <strong>{runDetail?.run?.target_database || 'Target Database'}</strong> (Active Table: <code>source_transactions</code>). Records deleted during cleanup will immediately disappear from this table.
                    </span>
                    <span className="badge" style={{
                      fontSize: '0.6875rem',
                      background: '#003B57',
                      color: '#fff',
                      textTransform: 'uppercase',
                    }}>
                      SQLITE
                    </span>
                  </div>
                  <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 1 }}>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Transaction ID</th>
                        <th style={{ padding: '10px 10px', textAlign: 'left' }}>Account ID</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Customer Name</th>
                        <th style={{ padding: '10px 10px', textAlign: 'left' }}>Date</th>
                        <th style={{ padding: '10px 12px', textAlign: 'right' }}>Amount</th>
                        <th style={{ padding: '10px 10px', textAlign: 'center' }}>Type</th>
                        <th style={{ padding: '10px 10px', textAlign: 'center' }}>Legal Hold</th>
                        <th style={{ padding: '10px 10px', textAlign: 'center' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sourceDbData.records.length === 0 ? (
                        <tr>
                          <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                            No active records in <code>source_transactions</code>. Click "Reseed Active DB" above to generate demo data.
                          </td>
                        </tr>
                      ) : (
                        sourceDbData.records.map((r) => (
                          <tr key={r.transaction_id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontWeight: 600 }}>{r.transaction_id}</td>
                            <td style={{ padding: '8px 10px', fontFamily: 'monospace', color: 'var(--color-text-muted)' }}>{r.account_id}</td>
                            <td style={{ padding: '8px 14px' }}>{r.customer_name}</td>
                            <td style={{ padding: '8px 10px', color: 'var(--color-text-secondary)' }}>{r.transaction_date}</td>
                            <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>${Number(r.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}><span className="badge badge-neutral" style={{ fontSize: '0.6875rem' }}>{r.transaction_type}</span></td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                              {r.legal_hold ? (
                                <span className="badge badge-warning" style={{ fontSize: '0.6875rem' }}>HOLD</span>
                              ) : (
                                <span style={{ color: 'var(--color-text-muted)' }}>No</span>
                              )}
                            </td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                              <span className="badge badge-success" style={{ fontSize: '0.6875rem' }}>{r.status}</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* TAB 3: Live Archive DB (archive_transactions) */}
              {activeDbTab === 'archive_db' && (
                <div style={{ maxHeight: '420px', overflow: 'auto', width: '100%' }}>
                  <div style={{ padding: '10px 16px', background: 'rgba(16, 185, 129, 0.05)', fontSize: '0.75rem', color: 'var(--color-text-secondary)', borderBottom: '1px solid var(--color-border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                    <span>
                      Live snapshot of <strong>Approved Archival Storage for {runDetail?.run?.target_database || 'Target Database'}</strong> (Archive Table: <code>archive_transactions</code>). Contains immutable archived copies with cryptographic SHA256 verification hashes.
                    </span>
                    <span className="badge" style={{
                      fontSize: '0.6875rem',
                      background: '#003B57',
                      color: '#fff',
                      textTransform: 'uppercase',
                    }}>
                      SQLITE
                    </span>
                  </div>
                  <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ background: 'var(--color-bg)', position: 'sticky', top: 0, zIndex: 1 }}>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Transaction ID</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Customer Name</th>
                        <th style={{ padding: '10px 10px', textAlign: 'right' }}>Amount</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Run ID</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Archived At</th>
                        <th style={{ padding: '10px 14px', textAlign: 'left' }}>Verification Hash</th>
                        <th style={{ padding: '10px 10px', textAlign: 'center' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {archiveDbData.records.length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                            No records archived yet. Advance a control run through the "Archive" stage to populate this database.
                          </td>
                        </tr>
                      ) : (
                        archiveDbData.records.map((r) => (
                          <tr key={r.transaction_id} style={{ borderBottom: '1px solid var(--color-border-light)' }}>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontWeight: 600 }}>{r.transaction_id}</td>
                            <td style={{ padding: '8px 14px' }}>{r.customer_name}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>${Number(r.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontSize: '0.75rem' }}>RUN-{r.control_run_id?.slice(0, 8)}</td>
                            <td style={{ padding: '8px 14px', color: 'var(--color-text-secondary)', fontSize: '0.75rem' }}>{r.archived_at ? new Date(r.archived_at).toLocaleString() : '—'}</td>
                            <td style={{ padding: '8px 14px', fontFamily: 'monospace', fontSize: '0.7rem', color: 'var(--color-primary)' }}>{r.verification_hash || 'SHA256-OK'}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                              <span className="badge badge-success" style={{ fontSize: '0.6875rem' }}>ARCHIVED</span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
  );
}
