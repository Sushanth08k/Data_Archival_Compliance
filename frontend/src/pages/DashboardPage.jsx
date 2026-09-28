/**
 * Dashboard page — matching the prototype's dashboard layout.
 * Shows lifecycle stepper, stats, and quick actions.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

const LIFECYCLE_STEPS = [
  'Upload',
  'AI analysis',
  'Structured rules',
  'Execution',
  'Archival',
  'Verification',
  'Human approval',
  'Source cleanup',
  'Final verification',
  'Audit evidence',
];

export default function DashboardPage() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get('/health');
        setHealth(res.data);
      } catch {
        setHealth({ status: 'error', database: 'disconnected' });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <>
      {/* Lifecycle stepper */}
      <div className="lifecycle-stepper">
        {LIFECYCLE_STEPS.map((step) => (
          <span key={step} className="lifecycle-step">
            {step}
          </span>
        ))}
      </div>

      <div className="page-container">
        <div className="page-header">
          <h1>Dashboard</h1>
          <p className="subtitle">Compliance controls at a glance.</p>
        </div>

        {/* Upload CTA */}
        <div style={{ marginBottom: '32px' }}>
          <Link to="/policies" className="btn btn-primary btn-lg">
            + Upload Policy
          </Link>
        </div>

        {/* Quick action cards */}
        <div className="stats-grid" style={{ marginBottom: '32px' }}>
          <Link to="/policies" className="stat-card primary" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="stat-label" style={{ color: 'rgba(255,255,255,0.7)' }}>Upload Policy</div>
            <div className="stat-value" style={{ color: '#fff', fontSize: '1.125rem' }}>Start a new run</div>
          </Link>
          <Link to="/control-runs" className="stat-card" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="stat-label">Control Runs</div>
            <div className="stat-value" style={{ fontSize: '1.125rem' }}>View executions</div>
          </Link>
          <Link to="/approvals" className="stat-card" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="stat-label">Approval Queue</div>
            <div className="stat-value" style={{ fontSize: '1.125rem' }}>Review pending</div>
          </Link>
          <Link to="/audit-evidence" className="stat-card" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="stat-label">Audit Evidence</div>
            <div className="stat-value" style={{ fontSize: '1.125rem' }}>View evidence</div>
          </Link>
        </div>

        {/* Control lifecycle description */}
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <h3 className="card-title">Control lifecycle</h3>
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', lineHeight: '1.7' }}>
            Upload policy → AI policy analysis → structured rules → control execution → archival →
            independent verification → human approval → controlled source cleanup → final verification → audit evidence.
          </p>
        </div>

        {/* System status */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">System Status</h3>
            {health && (
              <span className={`badge ${health.status === 'ok' ? 'badge-success' : 'badge-error'}`}>
                {health.status === 'ok' ? 'Operational' : 'Degraded'}
              </span>
            )}
          </div>
          {loading ? (
            <div className="loading-overlay" style={{ padding: '20px' }}>
              <div className="spinner" />
            </div>
          ) : (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">API</div>
                <div className="stat-value" style={{ fontSize: '1rem', color: 'var(--color-success)' }}>
                  {health?.service || 'Unknown'}
                </div>
                <div className="stat-subtitle">v{health?.version || '?'}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Database</div>
                <div className="stat-value" style={{ fontSize: '1rem', color: health?.database === 'connected' ? 'var(--color-success)' : 'var(--color-error)' }}>
                  {health?.database || 'Unknown'}
                </div>
                <div className="stat-subtitle">{health?.dialect || 'SQLite'}</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
