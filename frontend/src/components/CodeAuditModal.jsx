import React from 'react';
import { Modal, Tag } from '@carbon/react';
import { Chip, WarningAltFilled, CheckmarkFilled } from '@carbon/icons-react';

export default function CodeAuditModal({ packageData, onClose }) {
  if (!packageData || !packageData.arch_sensitivity) return null;

  const arch = packageData.arch_sensitivity;

  return (
    <Modal
      open
      size="lg"
      modalHeading={`Architecture Sensitivity & Remediation: ${packageData.package_name}`}
      primaryButtonText="Close"
      onRequestClose={onClose}
      onRequestSubmit={onClose}
      passiveModal
    >
      {/* Sensitivity tags */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        {arch.has_simd_avx && (
          <Tag type="yellow" size="md">
            <WarningAltFilled size={13} style={{ marginRight: '4px' }} /> x86 SIMD / AVX Intrinsics Detected
          </Tag>
        )}
        {arch.simd_instruction_count > 0 && (
          <Tag type="warm-gray" size="md">
            <Chip size={13} style={{ marginRight: '4px' }} /> {arch.simd_instruction_count} SIMD Instructions
          </Tag>
        )}
        {arch.simd_porting_complexity && (
          <Tag type="cyan" size="md">
            Tier: {arch.simd_porting_complexity.replace('_', ' ')}
          </Tag>
        )}
        {arch.has_64k_page_risk && (
          <Tag type="yellow" size="md">
            <WarningAltFilled size={13} style={{ marginRight: '4px' }} /> 64KB Page Size Sensitivity
          </Tag>
        )}
        {arch.has_inline_asm && (
          <Tag type="yellow" size="md">
            <WarningAltFilled size={13} style={{ marginRight: '4px' }} /> Inline x86 Assembly
          </Tag>
        )}
      </div>

      {/* Effort derivation */}
      {arch.has_simd_avx && (
        <div
          style={{
            background: 'var(--cds-layer-02)',
            border: '1px solid var(--cds-border-subtle-01)',
            borderRadius: '2px',
            padding: '0.85rem 1rem',
            marginBottom: '1.25rem',
          }}
        >
          <div style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--cds-interactive)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Chip size={16} /> Engineering Effort Calculation ({packageData.arch_complexity_effort_pd} PD)
          </div>
          <div
            style={{
              fontSize: '0.8rem',
              fontFamily: "'IBM Plex Mono', monospace",
              background: 'var(--cds-layer-01)',
              padding: '0.4rem 0.6rem',
              borderRadius: '2px',
              marginBottom: '0.6rem',
            }}
          >
            Base Engineering ({arch.base_engineering_effort_pd || 2.0} PD) × Instruction Volume ({arch.simd_instruction_multiplier || 1.0}x) × Complexity Tier ({arch.simd_complexity_multiplier || 1.0}x) = <strong>{packageData.arch_complexity_effort_pd} Person-Days</strong>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
            {[
              { label: 'Base Engineering', value: `${arch.base_engineering_effort_pd || 2.0} PD`, color: 'var(--cds-link-primary)' },
              {
                label: `SIMD Volume (${arch.simd_instruction_count} instrs)`,
                value: `${arch.simd_instruction_multiplier || 1.0}x`,
                color: 'var(--cds-support-warning)',
              },
              {
                label: 'Complexity Tier',
                value: `${arch.simd_complexity_multiplier || 1.0}x (${(arch.simd_porting_complexity || 'direct').replace('_', ' ')})`,
                color: 'var(--cds-interactive)',
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ background: 'var(--cds-layer-01)', padding: '0.45rem', borderRadius: '2px' }}>
                <span style={{ color: 'var(--cds-text-secondary)', display: 'block', marginBottom: '0.15rem' }}>{label}</span>
                <div style={{ fontWeight: 700, color }}>{value}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SIMD analysis */}
      {arch.simd_details && (
        <div style={{ marginBottom: '1rem' }}>
          <p className="cds--label" style={{ marginBottom: '0.2rem' }}>SIMD Analysis:</p>
          <p className="cds--body-long-01">{arch.simd_details}</p>
        </div>
      )}

      {/* Page risk */}
      {arch.page_risk_details && (
        <div style={{ marginBottom: '1rem' }}>
          <p className="cds--label" style={{ marginBottom: '0.2rem' }}>64KB Page Size Risk:</p>
          <p className="cds--body-long-01">{arch.page_risk_details}</p>
        </div>
      )}

      {/* Code snippet */}
      {arch.code_snippet && (
        <div style={{ marginBottom: '1.25rem' }}>
          <p className="cds--label" style={{ marginBottom: '0.4rem' }}>Flagged Source Code Pattern:</p>
          <pre
            style={{
              background: 'var(--cds-layer-02)',
              border: '1px solid var(--cds-border-subtle-01)',
              borderRadius: '2px',
              padding: '1rem',
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '0.8rem',
              overflowX: 'auto',
              lineHeight: 1.6,
            }}
          >
            {arch.code_snippet}
          </pre>
        </div>
      )}

      {/* Remediation */}
      {arch.remediation_strategy && (
        <div
          style={{
            background: 'var(--cds-layer-02)',
            border: '1px solid var(--cds-support-success)',
            borderRadius: '2px',
            padding: '1rem',
          }}
        >
          <div style={{ fontWeight: 700, color: 'var(--cds-support-success)', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.4rem', fontSize: '0.88rem' }}>
            <CheckmarkFilled size={16} /> Recommended Power (ppc64le) Remediation Vector
          </div>
          <p className="cds--body-long-01" style={{ color: 'var(--cds-text-primary)', lineHeight: 1.6 }}>
            {arch.remediation_strategy}
          </p>
        </div>
      )}
    </Modal>
  );
}
