/**
 * Policies page — upload policy documents and manage policies.
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import policyService from '../services/policies';
import { getErrorMessage } from '../utils/errors';

export default function PoliciesPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const [policies, setPolicies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    try {
      const data = await policyService.list();
      setPolicies(data.policies || []);
    } catch {
      setError('Failed to load policies');
    } finally {
      setLoading(false);
    }
  };

  const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];

  const handleUpload = async (file) => {
    if (!file) return;
    setError('');
    setSuccessMsg('');

    const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError('Only PDF, DOCX, TXT, MD files are accepted');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setUploading(true);

    try {
      const result = await policyService.upload(file);
      setSuccessMsg(`"${result.document_name}" uploaded successfully.`);
      await fetchPolicies();
      // Navigate to the policy detail to trigger analysis
      navigate(`/policies/${result.policy_id}`);
    } catch (err) {
      setError(getErrorMessage(err, 'Upload failed'));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Policies</h1>
        <p className="subtitle">Upload and manage compliance policies.</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {successMsg && <div className="alert alert-success">{successMsg}</div>}

      {/* Upload zone */}
      <div
        className="card"
        style={{
          marginBottom: '32px',
          border: dragOver ? '2px dashed var(--color-primary)' : '2px dashed var(--color-border)',
          background: dragOver ? 'var(--color-primary-surface)' : 'var(--color-surface)',
          textAlign: 'center',
          padding: '48px 24px',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept=".pdf,.docx,.txt,.md"
          style={{ display: 'none' }}
        />
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary-lighter)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '16px' }}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="12" y1="18" x2="12" y2="12" />
          <line x1="9" y1="15" x2="15" y2="15" />
        </svg>
        <h3 style={{ marginBottom: '8px' }}>Upload Policy Document</h3>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
          {uploading ? 'Uploading…' : 'Drag & drop your document here'}
        </p>
        {!uploading && (
          <>
            <p style={{ color: 'var(--color-text-secondary)', marginBottom: '12px' }}>or</p>
            <button className="btn btn-primary" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
              Browse Files
            </button>
            <p style={{ marginTop: '12px', fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
              PDF, DOCX, TXT, MD • Max 25 MB
            </p>
          </>
        )}
        {uploading && <div className="spinner" style={{ margin: '0 auto' }} />}
      </div>

      {/* Policies list */}
      {loading ? (
        <div className="loading-overlay"><div className="spinner" /></div>
      ) : policies.length === 0 ? (
        <div className="empty-state">
          <h3>No policies yet</h3>
          <p>Upload a policy document above to get started.</p>
        </div>
      ) : (
        <div>
          <h2 style={{ marginBottom: '16px' }}>Uploaded Policies</h2>
          {policies.map((policy) => (
            <div
              key={policy.id}
              className="card"
              style={{ marginBottom: '12px', cursor: 'pointer' }}
              onClick={() => navigate(`/policies/${policy.id}`)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ marginBottom: '4px' }}>{policy.name}</h4>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
                    {policy.scope && `Scope: ${policy.scope} • `}
                    Created {formatDate(policy.created_at)}
                  </p>
                </div>
                <span className={`badge ${policy.status === 'ACTIVE' ? 'badge-success' : 'badge-neutral'}`}>
                  {policy.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
