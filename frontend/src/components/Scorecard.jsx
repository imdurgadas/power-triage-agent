import React from 'react';
import { Award, Clock, CheckCircle, AlertCircle, ShieldAlert, Sparkles, GitPullRequest, ArrowUpRight } from 'lucide-react';

export default function Scorecard({ summary, onOpenExport }) {
  if (!summary) return null;

  const rec = summary.recommendation || 'Minimal Effort';
  
  const getPillData = (recommendationStr) => {
    const s = String(recommendationStr);
    if (s.includes('Minimal') || s === 'GO') {
      return {
        className: 'minimal',
        icon: <Sparkles size={17} color="#6ee7b7" />,
        subtext: 'Turnkey fit • Zero or near-zero build adaptation'
      };
    }
    if (s.includes('Minor')) {
      return {
        className: 'minor',
        icon: <CheckCircle size={17} color="#67e8f9" />,
        subtext: 'Straightforward recompile & verification'
      };
    }
    if (s.includes('Moderate') || s === 'CAUTION') {
      return {
        className: 'moderate',
        icon: <AlertCircle size={17} color="#fde047" />,
        subtext: 'Standard build porting with transitive requirements'
      };
    }
    if (s.includes('Significant')) {
      return {
        className: 'significant',
        icon: <Clock size={17} color="#fdba74" />,
        subtext: 'Deep porting • SIMD/VSX translation or custom build trees'
      };
    }
    return {
      className: 'alternative',
      icon: <ShieldAlert size={17} color="#d8b4fe" />,
      subtext: 'x86 binary lock-in • Drop-in OpenBLAS/ESSL alternative recommended'
    };
  };

  const pill = getPillData(rec);
  const fibEffort = summary.fibonacci_effort_pd !== undefined ? summary.fibonacci_effort_pd : (summary.max_total_person_days || 0);

  return (
    <div className="glass-card" id="executive-scorecard">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#06b6d4', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Pre-Sales Migration Qualification
          </span>
          <h2 style={{ fontSize: '1.45rem', fontWeight: 800, marginTop: '0.2rem', color: '#f8fafc' }}>
            Executive Feasibility Scorecard
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '0.35rem', maxWidth: '750px', lineHeight: 1.5 }}>
            {summary.recommendation_reason}
          </p>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={onOpenExport}
          id="open-export-btn"
          style={{ fontSize: '0.86rem', padding: '0.65rem 1.25rem' }}
        >
          <ArrowUpRight size={16} /> Export Executive 1-Pager (PDF / MD)
        </button>
      </div>

      <div className="scorecard-grid">
        {/* Metric 1: Readiness Score */}
        <div className="metric-card">
          <div className="metric-label">Porting Readiness Score</div>
          <div className="metric-value">
            <span style={{ color: summary.readiness_score_pct >= 85 ? '#10b981' : summary.readiness_score_pct >= 65 ? '#06b6d4' : summary.readiness_score_pct >= 40 ? '#f59e0b' : '#a855f7' }}>
              {summary.readiness_score_pct}%
            </span>
          </div>
          <div className="metric-sub">
            {summary.native_count + summary.agnostic_count} of {summary.total_packages} components ready natively
          </div>
        </div>

        {/* Metric 2: Sales Qualification Tier */}
        <div className="metric-card">
          <div className="metric-label">Sales Recommendation Tier</div>
          <div style={{ marginTop: '0.25rem' }}>
            <span className={`traffic-pill ${pill.className}`}>
              {pill.icon}
              {rec}
            </span>
          </div>
          <div className="metric-sub" style={{ marginTop: '0.35rem' }}>
            {pill.subtext}
          </div>
        </div>

        {/* Metric 3: Fibonacci Effort Sizing (Single Value) */}
        <div className="metric-card">
          <div className="metric-label">Porting Effort Estimate</div>
          <div className="metric-value">
            <Clock size={24} color="#06b6d4" style={{ alignSelf: 'center' }} />
            <span>{fibEffort}</span>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-dim)' }}>Person-Days</span>
          </div>
          <div className="metric-sub">
            Single Fibonacci Max Estimate (Ceiling)
          </div>
        </div>

        {/* Metric 4: Transitive Iceberg */}
        <div className="metric-card">
          <div className="metric-label">Transitive Build Requirements</div>
          <div className="metric-value">
            <GitPullRequest size={24} color={summary.unported_transitive_deps_count > 0 ? '#f59e0b' : '#10b981'} style={{ alignSelf: 'center' }} />
            <span>{summary.unported_transitive_deps_count}</span>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 500 }}>Unported</span>
          </div>
          <div className="metric-sub">
            Scoped build-time dependencies from source
          </div>
        </div>
      </div>
    </div>
  );
}
