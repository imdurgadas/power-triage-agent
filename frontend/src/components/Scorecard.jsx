import React from 'react';
import { Tile, Tag, Button } from '@carbon/react';
import {
  CheckmarkFilled,
  WarningAltFilled,
  MisuseOutline,
  Time,
  Layers,
  Chip,
  ArrowUpRight,
  Branch,
} from '@carbon/icons-react';

export default function Scorecard({ summary, triageResult, onOpenExport }) {
  if (!summary) return null;

  const rec = summary.recommendation || 'Minimal Effort';

  const getTrafficInfo = (r) => {
    const s = String(r || '').toLowerCase();
    if (s.includes('minimal') || s.includes('turnkey') || s === 'go') {
      return {
        className: 'traffic-pill--turnkey',
        icon: <CheckmarkFilled size={18} style={{ color: '#42be65' }} />,
        subtext: 'Immediate turnkey fit for IBM Power (ppc64le)',
      };
    }
    if (s.includes('minor')) {
      return {
        className: 'traffic-pill--minor',
        icon: <CheckmarkFilled size={18} style={{ color: '#78a9ff' }} />,
        subtext: 'Straightforward recompile & automated verification',
      };
    }
    if (s.includes('moderate') || s.includes('caution')) {
      return {
        className: 'traffic-pill--moderate',
        icon: <WarningAltFilled size={18} style={{ color: '#f1c21b' }} />,
        subtext: 'Standard build porting with transitive requirements',
      };
    }
    if (s.includes('significant')) {
      return {
        className: 'traffic-pill--significant',
        icon: <Time size={18} style={{ color: '#ff832b' }} />,
        subtext: 'Deep porting • SIMD/VSX translation or custom build trees',
      };
    }
    return {
      className: 'traffic-pill--alternative',
      icon: <MisuseOutline size={18} style={{ color: '#fa4d56' }} />,
      subtext: 'x86 binary lock-in • Drop-in OpenBLAS/ESSL alternative recommended',
    };
  };

  const traffic = getTrafficInfo(rec);

  const scoreColor =
    summary.readiness_score_pct >= 85 ? '#42be65' :
    summary.readiness_score_pct >= 65 ? '#f1c21b' :
    '#fa4d56';

  const targetEnv = triageResult?.target_environment || '';
  const delivType = triageResult?.deliverable_type || '';

  return (
    <Tile id="executive-scorecard" style={{ padding: '1.75rem', background: '#262626', border: '1px solid #393939' }}>
      {/* Top Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#78a9ff', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Pre-Sales Migration Qualification
            </span>
            {(targetEnv || delivType) && (
              <Tag
                type="cool-gray"
                size="md"
                style={{
                  maxWidth: 'none',
                  whiteSpace: 'normal',
                  height: 'auto',
                  padding: '0.25rem 0.6rem',
                  display: 'inline-flex',
                  alignItems: 'center',
                }}
              >
                <Chip size={14} style={{ marginRight: '4px' }} />
                <span>{targetEnv ? `${targetEnv} • ` : ''}Deliverable: {delivType ? delivType.replace('_', ' ').toUpperCase() : 'CONTAINER'}</span>
              </Tag>
            )}
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f4f4f4', margin: '0.2rem 0 0.5rem 0' }}>
            Executive Feasibility Scorecard
          </h2>
          <p style={{ fontSize: '0.92rem', color: '#c6c6c6', maxWidth: '820px', lineHeight: 1.5, margin: 0 }}>
            {summary.recommendation_reason}
          </p>
        </div>

        <Button
          kind="primary"
          size="md"
          renderIcon={ArrowUpRight}
          onClick={onOpenExport}
          id="open-export-btn"
          style={{ alignSelf: 'flex-start' }}
        >
          Export Executive 1-Pager
        </Button>
      </div>

      {/* Metric Tiles Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
        {/* Metric 1: Readiness Score */}
        <div style={{ background: '#1c1c1c', border: '1px solid #333333', borderRadius: '2px', padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.6rem 0' }}>
            Porting Readiness Score
          </p>
          <div style={{ fontSize: '2.5rem', fontWeight: 800, color: scoreColor, lineHeight: 1.1 }}>
            {summary.readiness_score_pct}%
          </div>
          <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
            {summary.native_count + summary.agnostic_count} of {summary.total_packages} ready out-of-the-box
          </p>
        </div>

        {/* Metric 2: Sales Recommendation */}
        <div style={{ background: '#1c1c1c', border: '1px solid #333333', borderRadius: '2px', padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.6rem 0' }}>
            Sales Recommendation
          </p>
          <div style={{ marginTop: '0.2rem' }}>
            <span className={`traffic-pill ${traffic.className}`}>
              {traffic.icon}
              <span>{rec}</span>
            </span>
          </div>
          <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
            {traffic.subtext}
          </p>
        </div>

        {/* Metric 3: Porting Sizing */}
        <div style={{ background: '#1c1c1c', border: '1px solid #333333', borderRadius: '2px', padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.6rem 0' }}>
            Estimated Porting Sizing
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginTop: '0.2rem' }}>
            <Time size={24} style={{ color: '#78a9ff', flexShrink: 0, alignSelf: 'center' }} />
            <span style={{ fontSize: '2.4rem', fontWeight: 800, color: '#f4f4f4', lineHeight: 1.1 }}>
              {summary.fibonacci_effort_pd != null
                ? summary.fibonacci_effort_pd
                : `${summary.min_total_person_days}–${summary.max_total_person_days}`}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#a8a8a8', fontWeight: 600 }}>PD</span>
          </div>
          <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
            {summary.fibonacci_effort_pd != null ? 'Fibonacci maximum ceiling' : 'Person-Days range'}
          </p>
        </div>

        {/* Metric 4: Transitive Icebergs */}
        <div style={{ background: '#1c1c1c', border: '1px solid #333333', borderRadius: '2px', padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.6rem 0' }}>
            Transitive Build Scope
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginTop: '0.2rem' }}>
            <Branch size={22} style={{ color: summary.unported_transitive_deps_count > 0 ? '#f1c21b' : '#42be65', flexShrink: 0, alignSelf: 'center' }} />
            <span
              style={{
                fontSize: '2.4rem',
                fontWeight: 800,
                color: summary.unported_transitive_deps_count > 0 ? '#f1c21b' : '#42be65',
                lineHeight: 1.1,
              }}
            >
              {summary.unported_transitive_deps_count}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#a8a8a8', fontWeight: 600 }}>Icebergs</span>
          </div>
          <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
            Build-time sub-dependencies scoped from source
          </p>
        </div>

        {/* Metric 5: Partial Deliverable Support */}
        {summary.partial_support_count > 0 && (
          <div style={{ background: '#1c1c1c', border: '1px solid #333333', borderLeft: '4px solid #f1c21b', borderRadius: '2px', padding: '1.25rem', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.6rem 0' }}>
              Partial Deliverable Support
            </p>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginTop: '0.2rem' }}>
              <Layers size={22} style={{ color: '#f1c21b', flexShrink: 0, alignSelf: 'center' }} />
              <span style={{ fontSize: '2.4rem', fontWeight: 800, color: '#f1c21b', lineHeight: 1.1 }}>
                {summary.partial_support_count}
              </span>
              <span style={{ fontSize: '0.9rem', color: '#a8a8a8', fontWeight: 600 }}>Packages</span>
            </div>
            <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
              Artifact type or version mismatch — adaptation needed
            </p>
          </div>
        )}
      </div>
    </Tile>
  );
}
