import React from 'react';
import { Award, Clock, CheckCircle, AlertCircle, ShieldAlert, GitPullRequest, ArrowUpRight } from 'lucide-react';

export default function Scorecard({ summary, onOpenExport }) {
  if (!summary) return null;

  const getTrafficIcon = (rec) => {
    switch (rec) {
      case 'GO':
        return <CheckCircle size={22} color="#4ade80" />;
      case 'CAUTION':
        return <AlertCircle size={22} color="#fef08a" />;
      default:
        return <ShieldAlert size={22} color="#f87171" />;
    }
  };

  return (
    <div className="glass-card" id="executive-scorecard">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pre-Sales Migration Qualification
          </span>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginTop: '0.15rem' }}>
            Executive Feasibility Scorecard
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '0.25rem', maxWidth: '750px' }}>
            {summary.recommendation_reason}
          </p>
        </div>
        <button 
          className="btn btn-primary" 
          onClick={onOpenExport}
          id="open-export-btn"
          style={{ fontSize: '0.85rem', padding: '0.6rem 1.1rem' }}
        >
          <ArrowUpRight size={16} /> Export Executive 1-Pager
        </button>
      </div>

      <div className="scorecard-grid">
        {/* Metric 1: Readiness Score */}
        <div className="metric-card">
          <div className="metric-label">Porting Readiness Score</div>
          <div className="metric-value">
            <span style={{ color: summary.readiness_score_pct >= 85 ? '#4ade80' : summary.readiness_score_pct >= 65 ? '#fef08a' : '#f87171' }}>
              {summary.readiness_score_pct}%
            </span>
          </div>
          <div className="metric-sub">
            {summary.native_count + summary.agnostic_count} of {summary.total_packages} ready out-of-the-box
          </div>
        </div>

        {/* Metric 2: Qualification Recommendation */}
        <div className="metric-card">
          <div className="metric-label">Sales Recommendation</div>
          <div style={{ marginTop: '0.25rem' }}>
            <span className={`traffic-pill ${summary.recommendation}`}>
              {getTrafficIcon(summary.recommendation)}
              {summary.recommendation}
            </span>
          </div>
          <div className="metric-sub">
            {summary.recommendation === 'GO' ? 'Immediate fit for Power' : summary.recommendation === 'CAUTION' ? 'Minor build/porting effort' : 'Blocker / x86 alternative needed'}
          </div>
        </div>

        {/* Metric 3: Effort Sizing */}
        <div className="metric-card">
          <div className="metric-label">Estimated Porting Sizing</div>
          <div className="metric-value">
            <Clock size={24} color="#60a5fa" style={{ alignSelf: 'center' }} />
            <span>{summary.min_total_person_days} – {summary.max_total_person_days}</span>
            <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-dim)' }}>PD</span>
          </div>
          <div className="metric-sub">
            Total Person-Days
          </div>
        </div>

        {/* Metric 4: Transitive Iceberg */}
        <div className="metric-card">
          <div className="metric-label">Transitive Build Requirements</div>
          <div className="metric-value">
            <GitPullRequest size={24} color={summary.unported_transitive_deps_count > 0 ? '#facc15' : '#4ade80'} style={{ alignSelf: 'center' }} />
            <span>{summary.unported_transitive_deps_count}</span>
            <span style={{ fontSize: '0.9rem', color: 'var(--text-dim)', fontWeight: 500 }}>Unported</span>
          </div>
          <div className="metric-sub">
            Build-time sub-dependencies scoped from source
          </div>
        </div>
      </div>
    </div>
  );
}
