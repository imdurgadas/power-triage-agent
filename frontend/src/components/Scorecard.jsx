import React, { useState } from 'react';
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
  Calculator,
  Information,
  CurrencyDollar,
} from '@carbon/icons-react';

export default function Scorecard({ summary, triageResult, tokenUsage, onOpenExport }) {
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [showTokenBreakdown, setShowTokenBreakdown] = useState(false);

  if (!summary) return null;

  const usage = tokenUsage || triageResult?.token_usage || summary?.token_usage;

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

  // Enterprise Lifecycle Sizing Breakdown Data
  const sb = summary.sizing_breakdown;
  const estimatedEffort = summary.estimated_effort_pd ?? summary.max_total_person_days ?? 0;
  const prepEnvPd = sb?.prep_env_pd ?? 0.0;
  const readinessAuditPd = sb?.readiness_audit_pd ?? 0.0;
  const buildSourcePd = sb?.build_source_pd ?? 0.0;
  const ciPipelinePd = sb?.ci_pipeline_pd ?? 0.0;
  const bugFixValidationPd = sb?.bug_fix_validation_pd ?? 0.0;
  const contingencyBufferPd = sb?.contingency_buffer_pd ?? 0.0;
  const contingencyPct = sb?.contingency_pct ?? 20.0;
  const subtotalPd = sb?.subtotal_pd ?? 0.0;

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
              {estimatedEffort}
            </span>
            <span style={{ fontSize: '0.9rem', color: '#a8a8a8', fontWeight: 600 }}>PD</span>
          </div>
          {estimatedEffort === 0 && (
            <p style={{ fontSize: '0.82rem', color: '#c6c6c6', marginTop: '0.6rem', marginBottom: 0 }}>
              Zero Effort — Turnkey Ready
            </p>
          )}
          {estimatedEffort > 0 && (
            <button
              type="button"
              id="toggle-sizing-breakdown-btn"
              onClick={() => setShowBreakdown(!showBreakdown)}
              style={{
                background: 'none',
                border: 'none',
                color: '#78a9ff',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 600,
                padding: '0.4rem 0 0 0',
                marginTop: 'auto',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                textDecoration: 'underline',
                textAlign: 'left',
              }}
            >
              <Calculator size={13} />
              <span>{showBreakdown ? 'Hide Sizing Breakdown ▲' : 'Inspect Sizing Breakdown ▼'}</span>
            </button>
          )}
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

        {/* Metric 6: LLM Token Usage & Accounting */}
        {usage && (
          <div
            id="llm-telemetry-tile"
            style={{
              background: '#1c1c1c',
              border: '1px solid #333333',
              borderLeft: usage.llm_provider === 'ibm_bob' ? '4px solid #0f62fe' : '4px solid #8a3ffc',
              borderRadius: '2px',
              padding: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.25rem' }}>
              <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>
                LLM Token &amp; Cost Usage
              </p>
              <Tag type={usage.llm_provider === 'ibm_bob' ? 'blue' : 'purple'} size="sm" style={{ margin: 0 }}>
                {usage.llm_provider === 'ibm_bob' ? 'IBM Bob' : 'Google Gemini'}
              </Tag>
            </div>

            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.2rem', marginTop: '0.2rem' }}>
              <CurrencyDollar size={24} style={{ color: '#42be65', flexShrink: 0, alignSelf: 'center' }} />
              <span style={{ fontSize: '2.4rem', fontWeight: 800, color: '#42be65', lineHeight: 1.1 }}>
                ${Number(usage.cost_usd || 0).toFixed(4)}
              </span>
              <span style={{ fontSize: '0.85rem', color: '#a8a8a8', fontWeight: 600, marginLeft: '4px' }}>USD</span>
            </div>

            <div style={{ marginTop: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid #2d2d2d', display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#a8a8a8' }}>Total Tokens:</span>
                <span style={{ fontWeight: 700, color: '#f4f4f4' }}>
                  {Number(usage.total_tokens || ((usage.input_tokens || 0) + (usage.output_tokens || 0)) || 0).toLocaleString()}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.76rem', color: '#8d8d8d' }}>
                <span>In: {Number(usage.input_tokens || 0).toLocaleString()}</span>
                <span>Out: {Number(usage.output_tokens || 0).toLocaleString()}</span>
              </div>
              {usage.calls_count > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: '#78a9ff', marginTop: '2px' }}>
                  <span>API Invocations:</span>
                  <span>{usage.calls_count} call{usage.calls_count !== 1 ? 's' : ''}</span>
                </div>
              )}

              {/* Stage-by-Stage Cost & Token Breakdown */}
              {usage.breakdown && usage.breakdown.length > 0 && (
                <div style={{ marginTop: '0.6rem', paddingTop: '0.55rem', borderTop: '1px solid #282828' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.45rem',
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                    onClick={() => setShowTokenBreakdown(!showTokenBreakdown)}
                    title="Toggle stage breakdown"
                  >
                    <span style={{ fontSize: '0.73rem', fontWeight: 700, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Stage Cost Breakdown ({usage.breakdown.length})
                    </span>
                    <span style={{ fontSize: '0.72rem', color: '#78a9ff' }}>
                      {showTokenBreakdown ? 'Hide ▲' : 'Show ▼'}
                    </span>
                  </div>

                  {showTokenBreakdown && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      {usage.breakdown.map((item, idx) => (
                        <div
                          key={idx}
                          style={{
                            background: '#222222',
                            padding: '0.35rem 0.5rem',
                            borderRadius: '2px',
                            border: '1px solid #2e2e2e',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem' }}>
                            <span style={{ color: '#f4f4f4', fontWeight: 600 }}>{item.stage}</span>
                            <span style={{ color: '#42be65', fontWeight: 700 }}>
                              ${Number(item.cost_usd || 0).toFixed(4)}{' '}
                              <span style={{ color: '#8d8d8d', fontWeight: 400, fontSize: '0.68rem' }}>
                                ({item.percentage || 0}%)
                              </span>
                            </span>
                          </div>
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: '0.69rem',
                              color: '#8d8d8d',
                              marginTop: '2px',
                            }}
                          >
                            <span>{item.calls_count} call{item.calls_count !== 1 ? 's' : ''} • {Number(item.total_tokens || 0).toLocaleString()} tok</span>
                            <span>({Number(item.input_tokens || 0).toLocaleString()} in / {Number(item.output_tokens || 0).toLocaleString()} out)</span>
                          </div>
                          <div
                            style={{
                              width: '100%',
                              height: '3px',
                              background: '#333333',
                              borderRadius: '2px',
                              marginTop: '4px',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${Math.min(100, Math.max(3, item.percentage || 0))}%`,
                                height: '100%',
                                background: usage.llm_provider === 'ibm_bob' ? '#0f62fe' : '#8a3ffc',
                                borderRadius: '2px',
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Transparent Lifecycle Sizing Breakdown Panel */}
      {showBreakdown && estimatedEffort > 0 && (
        <div
          id="sizing-derivation-panel"
          style={{
            marginTop: '1.5rem',
            background: '#181818',
            border: '1px solid #393939',
            borderLeft: '4px solid #0f62fe',
            borderRadius: '2px',
            padding: '1.25rem 1.5rem',
            animation: 'fadeSlideIn 0.2s ease-out',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calculator size={18} style={{ color: '#78a9ff' }} />
              <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f4f4f4' }}>
                Porting Lifecycle Sizing Breakdown ({estimatedEffort} PD Total Committed)
              </span>
            </div>
            <Tag type="blue" size="sm">Enterprise Migration WBS</Tag>
          </div>

          <p style={{ fontSize: '0.84rem', color: '#c6c6c6', lineHeight: 1.5, marginBottom: '1rem' }}>
            Enterprise porting spans all lifecycle stages—from toolchain bootstrapping through architecture readiness, source compilation, CI automation, and stabilization testing, backed by a {contingencyPct}% risk contingency buffer:
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ background: '#222222', border: '1px solid #333333', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a8a8', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                1. Prep Env &amp; Toolchain
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#78a9ff' }}>
                {prepEnvPd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Host, compilers &amp; cross-tools
              </span>
            </div>

            <div style={{ background: '#222222', border: '1px solid #333333', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a8a8', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                2. Readiness &amp; Audit
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#78a9ff' }}>
                {readinessAuditPd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                SIMD/VSX, endian &amp; deps audit
              </span>
            </div>

            <div style={{ background: '#222222', border: '1px solid #333333', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a8a8', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                3. Build from Source
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f4f4f4' }}>
                {buildSourcePd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Package build &amp; C/C++ patches
              </span>
            </div>

            <div style={{ background: '#222222', border: '1px solid #333333', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a8a8', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                4. CI &amp; Container
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#78a9ff' }}>
                {ciPipelinePd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Multi-arch CI &amp; containerization
              </span>
            </div>

            <div style={{ background: '#222222', border: '1px solid #333333', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#a8a8a8', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                5. Bug Fix &amp; Verification
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f1c21b' }}>
                {bugFixValidationPd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Harness testing &amp; fixes
              </span>
            </div>

            <div style={{ background: '#222222', border: '1px solid #0f62fe', padding: '0.85rem', borderRadius: '2px' }}>
              <span style={{ fontSize: '0.72rem', color: '#78a9ff', textTransform: 'uppercase', display: 'block', marginBottom: '0.25rem' }}>
                6. Risk Buffer ({contingencyPct}%)
              </span>
              <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#42be65' }}>
                +{contingencyBufferPd} PD
              </div>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Upstream &amp; arch contingency
              </span>
            </div>
          </div>

          <div style={{ fontSize: '0.8rem', color: '#c6c6c6', fontFamily: "'IBM Plex Mono', monospace", background: '#141414', padding: '0.6rem 0.85rem', borderRadius: '2px', border: '1px solid #2a2a2a' }}>
            Lifecycle WBS: {prepEnvPd}d (Env) + {readinessAuditPd}d (Audit) + {buildSourcePd}d (Build) + {ciPipelinePd}d (CI) + {bugFixValidationPd}d (Validation) + {contingencyBufferPd}d (Buffer) = <strong>{estimatedEffort} Person-Days</strong>
          </div>
        </div>
      )}
    </Tile>
  );
}
