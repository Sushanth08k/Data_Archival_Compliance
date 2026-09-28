/**
 * PolicyDetailPage — shows analysis progress, structured rules, and exceptions.
 * Implements the lifecycle stepper from the prototype.
 */

import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import policyService from '../services/policies';
import { getErrorMessage } from '../utils/errors';

const ANALYSIS_STEPS = [
  'Document uploaded',
  'Text extracted',
  'Identifying policies',
  'Extracting rules',
  'Detecting exceptions',
  'Validating policy',
  'Preparing control definition',
];

export default function PolicyDetailPage() {
  const { policyId } = useParams();
  const navigate = useNavigate();
  const [policy, setPolicy] = useState(null);
  const [rules, setRules] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPolicy();
  }, [policyId]);

  const loadPolicy = async () => {
    try {
      const p = await policyService.get(policyId);
      setPolicy(p);
      // If analysis is already done, load rules
      const rulesData = await policyService.getRules(policyId);
      if (rulesData.analysis_status === 'COMPLETED') {
        setRules(rulesData);
        setAnalysisStep(ANALYSIS_STEPS.length); // all done
      }
    } catch (err) {
      setError('Failed to load policy');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setError('');
    setAnalyzing(true);
    setAnalysisStep(0);

    // Simulate progress steps while waiting for LLM
    const interval = setInterval(() => {
      setAnalysisStep((prev) => {
        if (prev < ANALYSIS_STEPS.length - 1) return prev + 1;
        return prev;
      });
    }, 1200);

    try {
      await policyService.analyze(policyId);
      clearInterval(interval);
      setAnalysisStep(ANALYSIS_STEPS.length);

      // Reload policy and rules
      const p = await policyService.get(policyId);
      setPolicy(p);
      const rulesData = await policyService.getRules(policyId);
      setRules(rulesData);
    } catch (err) {
      clearInterval(interval);
      setError(getErrorMessage(err, 'Analysis failed'));
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-overlay"><div className="spinner" /></div>
      </div>
    );
  }

  if (!policy) {
    return (
      <div className="page-container">
        <div className="alert alert-error">Policy not found</div>
      </div>
    );
  }

  const analysisComplete = rules && rules.analysis_status === 'COMPLETED';

  return (
    <>
      {/* Lifecycle stepper */}
      <div className="lifecycle-stepper">
        <span className={`lifecycle-step ${analysisComplete ? 'completed' : 'completed'}`}>
          <span className="step-check">✓</span> Upload
        </span>
        <span className={`lifecycle-step ${analysisComplete ? 'completed' : analyzing ? 'active' : ''}`}>
          {analysisComplete ? <span className="step-check">✓</span> : null} AI analysis
        </span>
        <span className={`lifecycle-step ${analysisComplete ? 'active' : ''}`}>
          {analysisComplete ? null : null} Structured rules
        </span>
        <span className="lifecycle-step">Execution</span>
        <span className="lifecycle-step">Archival</span>
        <span className="lifecycle-step">Verification</span>
        <span className="lifecycle-step">Human approval</span>
        <span className="lifecycle-step">Source cleanup</span>
        <span className="lifecycle-step">Final verification</span>
        <span className="lifecycle-step">Audit evidence</span>
      </div>

      <div className="page-container">
        {error && <div className="alert alert-error">{error}</div>}

        {/* Analysis in progress */}
        {(analyzing || (analysisStep > 0 && !analysisComplete)) && (
          <div style={{ marginBottom: '32px' }}>
            <div className="page-header">
              <h1>Analyzing Policy</h1>
              <p className="subtitle">{policy.name}</p>
            </div>

            {/* Progress bar */}
            <div style={{ background: 'var(--color-border)', borderRadius: '8px', height: '8px', marginBottom: '32px', overflow: 'hidden' }}>
              <div style={{
                width: `${(analysisStep / ANALYSIS_STEPS.length) * 100}%`,
                height: '100%',
                background: 'var(--color-primary)',
                borderRadius: '8px',
                transition: 'width 0.5s ease',
              }} />
            </div>

            {/* Step list */}
            <div className="card">
              {ANALYSIS_STEPS.map((step, i) => (
                <div key={step} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 0',
                  borderBottom: i < ANALYSIS_STEPS.length - 1 ? '1px solid var(--color-border-light)' : 'none',
                }}>
                  {i < analysisStep ? (
                    <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>✓</span>
                  ) : i === analysisStep && analyzing ? (
                    <div className="spinner" style={{ width: '18px', height: '18px', borderWidth: '2px' }} />
                  ) : (
                    <span style={{ color: 'var(--color-text-muted)', width: '18px', textAlign: 'center' }}>○</span>
                  )}
                  <span style={{
                    color: i <= analysisStep ? 'var(--color-text)' : 'var(--color-text-muted)',
                    fontWeight: i <= analysisStep ? 500 : 400,
                  }}>
                    {step}
                  </span>
                </div>
              ))}
            </div>

            {analysisStep === ANALYSIS_STEPS.length && (
              <div className="alert alert-success" style={{ marginTop: '16px' }}>
                <strong>Policy analysis completed</strong>
              </div>
            )}
          </div>
        )}

        {/* Pre-analysis or Failed / Retry state */}
        {!analyzing && !analysisComplete && (
          <div style={{ marginTop: '24px' }}>
            <div className="card" style={{ textAlign: 'center', padding: '32px' }}>
              <h3 style={{ marginBottom: '8px' }}>
                {error ? 'Analysis Did Not Complete' : 'Ready for Policy Analysis'}
              </h3>
              <p style={{ color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
                {error
                  ? 'Click below to extract structured compliance rules using the regex rule engine.'
                  : 'Extract structured compliance rules, conditions, and exceptions from this document.'}
              </p>
              <button className="btn btn-primary btn-lg" onClick={handleAnalyze}>
                {error ? 'Retry Rule Extraction' : 'Extract Policy Rules'}
              </button>
            </div>
          </div>
        )}


        {/* Analysis results — structured rules */}
        {analysisComplete && rules && (
          <div>
            <div className="page-header">
              <h1>Policy Analysis</h1>
              <p className="subtitle">Document: {policy.name}</p>
            </div>

            <div className="alert alert-success" style={{ marginBottom: '24px' }}>
              <strong>Policy analysis completed</strong>
            </div>

            {/* Stats */}
            <div className="stats-grid" style={{ marginBottom: '24px' }}>
              <div className="stat-card">
                <div className="stat-label">Rules detected</div>
                <div className="stat-value">{rules.rules_count}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Exceptions detected</div>
                <div className="stat-value">{rules.exceptions_count}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Ambiguous items</div>
                <div className="stat-value">{rules.ambiguities_count}</div>
              </div>
            </div>

            {/* Policy info */}
            {rules.policy_name && (
              <div className="card" style={{ marginBottom: '16px' }}>
                <h3 style={{ marginBottom: '4px' }}>{rules.policy_name}</h3>
                <span className="badge badge-success" style={{ marginBottom: '8px' }}>VALID</span>
                {rules.scope && <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', marginTop: '8px' }}>Scope: {rules.scope}</p>}
                {rules.description && <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>{rules.description}</p>}
              </div>
            )}

            {/* Rules */}
            {rules.rules.map((rule) => (
              <div key={rule.id} className="card" style={{ marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <h4>{rule.rule_id}</h4>
                  <span className={`badge ${rule.is_valid ? 'badge-success' : 'badge-error'}`}>
                    {rule.is_valid ? 'VALID' : 'INVALID'}
                  </span>
                </div>
                <p style={{ fontSize: '0.9rem', marginBottom: '12px' }}>{rule.description}</p>

                {/* Condition block */}
                <div style={{
                  background: 'var(--color-bg)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  marginBottom: '8px',
                }}>
                  <div><strong>Condition</strong></div>
                  <div style={{ marginTop: '4px' }}>{rule.field}</div>
                  <div>{rule.operator}</div>
                  <div>{rule.value}{rule.unit ? ` ${rule.unit}` : ''}</div>
                </div>

                <p style={{ fontSize: '0.8125rem' }}>
                  Operation <strong>{rule.action}</strong>
                </p>
              </div>
            ))}

            {/* Exceptions */}
            {rules.exceptions.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                {rules.exceptions.map((exc) => (
                  <div key={exc.id} className="alert alert-warning" style={{ marginBottom: '8px' }}>
                    <div>
                      <strong>EXCEPTION</strong>
                      <p style={{ marginTop: '4px' }}>{exc.description}</p>
                      <p style={{ marginTop: '4px', fontSize: '0.8125rem', fontFamily: 'monospace' }}>
                        {exc.field} {exc.operator} {exc.value} → {exc.action}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Ambiguities */}
            {rules.ambiguities.length > 0 && (
              <div style={{ marginTop: '16px' }}>
                <h3 style={{ marginBottom: '12px' }}>Ambiguities</h3>
                {rules.ambiguities.map((amb, i) => (
                  <div key={i} className={`alert ${amb.severity === 'HIGH' ? 'alert-error' : 'alert-warning'}`} style={{ marginBottom: '8px' }}>
                    <div>
                      <strong>{amb.type}</strong> <span className={`badge ${amb.severity === 'HIGH' ? 'badge-error' : 'badge-warning'}`}>{amb.severity}</span>
                      <p style={{ marginTop: '4px' }}>{amb.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Action buttons */}
            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <button className="btn btn-secondary" onClick={() => navigate('/policies')}>
                Back
              </button>
              <button className="btn btn-primary" onClick={() => navigate('/control-runs')}>
                Continue to Execution
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
