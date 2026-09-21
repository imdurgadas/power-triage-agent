import React from 'react';
import { Tile, Button, Tag } from '@carbon/react';
import { Time, CheckmarkFilled, WarningAltFilled, MisuseOutline, ArrowUpRight, Layers, Chip } from '@carbon/icons-react';

export default function Scorecard({ summary, triageResult, onOpenExport }) {
  if (!summary) return null;

  const trafficClass = {
    GO: 'traffic-pill--GO',
    CAUTION: 'traffic-pill--CAUTION',
    HIGH_RISK: 'traffic-pill--HIGH_RISK',
  }[summary.recommendation] || 'traffic-pill--HIGH_RISK';

  const getTrafficIcon = (rec) => {
    switch (rec) {
      case 'GO':       return <CheckmarkFilled size={20} />;
      case 'CAUTION':  return <WarningAltFilled size={20} />;
      default:         return <MisuseOutline size={20} />;
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

  const scoreColor =
    summary.readiness_score_pct >= 85 ? 'var(--cds-support-success)' :
    summary.readiness_score_pct >= 65 ? 'var(--cds-support-warning)' :
    'var(--cds-support-error)';

  return (
    <Tile id="executive-scorecard">
      {/* Top bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div>
          <p className="cds--label" style={{ color: 'var(--cds-interactive)', marginBottom: '0.2rem' }}>
            Pre-Sales Migration Qualification
          </p>
          <h2 className="cds--productive-heading-04">Executive Feasibility Scorecard</h2>
          <p className="cds--body-short-01" style={{ marginTop: '0.25rem', color: 'var(--cds-text-secondary)', maxWidth: '680px' }}>
            {summary.recommendation_reason}
          </p>
          {/* Context row: target environment + deliverable type */}
          {(triageResult?.target_environment || triageResult?.deliverable_type) && (
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.6rem' }}>
              {triageResult.target_environment && (
                <Tag type="cool-gray" size="sm">
                  <Chip size={12} style={{ marginRight: '3px' }} />
                  {triageResult.target_environment}
                </Tag>
              )}
              {triageResult.deliverable_type && (
                <Tag type="cool-gray" size="sm">
                  <Layers size={12} style={{ marginRight: '3px' }} />
                  {triageResult.deliverable_type}
                </Tag>
              )}
            </div>
          )}
        </div>
        <Button
          kind="primary"
          size="md"
          renderIcon={ArrowUpRight}
          onClick={onOpenExport}
          id="open-export-btn"
        >
          Export Executive 1-Pager
        </Button>
      </div>

      {/* Metric grid — 5 tiles when partial_support_count is present */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>

        {/* Readiness Score */}
        <Tile style={{ background: 'var(--cds-layer-02)' }}>
          <p className="cds--label" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Porting Readiness Score
          </p>
          <div style={{ fontSize: '2.25rem', fontWeight: 700, color: scoreColor, lineHeight: 1.1 }}>
            {summary.readiness_score_pct}%
          </div>
          <p className="cds--helper-text-01" style={{ marginTop: '0.4rem' }}>
            {summary.native_count + summary.agnostic_count} of {summary.total_packages} ready out-of-the-box
          </p>
        </Tile>

        {/* Recommendation */}
        <Tile style={{ background: 'var(--cds-layer-02)' }}>
          <p className="cds--label" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Sales Recommendation
          </p>
          <div style={{ marginTop: '0.25rem' }}>
            <span className={`traffic-pill ${trafficClass}`}>
              {getTrafficIcon(summary.recommendation)}
              {summary.recommendation}
            </span>
          </div>
          <p className="cds--helper-text-01" style={{ marginTop: '0.4rem' }}>
            {summary.recommendation === 'GO'
              ? 'Immediate fit for Power'
              : summary.recommendation === 'CAUTION'
              ? 'Minor build/porting effort'
              : 'Blocker / x86 alternative needed'}
          </p>
        </Tile>

        {/* Effort Sizing — show Fibonacci single estimate when available, else range */}
        <Tile style={{ background: 'var(--cds-layer-02)' }}>
          <p className="cds--label" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Estimated Porting Sizing
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
            <Time size={22} style={{ color: 'var(--cds-interactive)', flexShrink: 0 }} />
            <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--cds-text-primary)' }}>
              {summary.fibonacci_effort_pd != null
                ? summary.fibonacci_effort_pd
                : `${summary.min_total_person_days}–${summary.max_total_person_days}`}
            </span>
            <span className="cds--label">PD</span>
          </div>
          <p className="cds--helper-text-01" style={{ marginTop: '0.4rem' }}>
            {summary.fibonacci_effort_pd != null ? 'Fibonacci max estimate' : 'Total Person-Days'}
          </p>
        </Tile>

        {/* Transitive deps */}
        <Tile style={{ background: 'var(--cds-layer-02)' }}>
          <p className="cds--label" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
            Transitive Build Requirements
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
            <span
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                color: summary.unported_transitive_deps_count > 0
                  ? 'var(--cds-support-warning)'
                  : 'var(--cds-support-success)',
              }}
            >
              {summary.unported_transitive_deps_count}
            </span>
            <span className="cds--label">Unported</span>
          </div>
          <p className="cds--helper-text-01" style={{ marginTop: '0.4rem' }}>Build-time sub-dependencies scoped from source</p>
        </Tile>

        {/* Partial deliverable support count — shown only when > 0 */}
        {summary.partial_support_count > 0 && (
          <Tile style={{ background: 'var(--cds-layer-02)', borderLeft: '3px solid var(--cds-support-warning)' }}>
            <p className="cds--label" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem' }}>
              Partial Deliverable Support
            </p>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem' }}>
              <Layers size={22} style={{ color: 'var(--cds-support-warning)', flexShrink: 0 }} />
              <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--cds-support-warning)' }}>
                {summary.partial_support_count}
              </span>
              <span className="cds--label">Packages</span>
            </div>
            <p className="cds--helper-text-01" style={{ marginTop: '0.4rem' }}>
              Artifact type or version mismatch — effort increased
            </p>
          </Tile>
        )}
      </div>
    </Tile>
  );
}
