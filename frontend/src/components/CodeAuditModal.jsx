import React from 'react';
import { X, Code, AlertTriangle, CheckCircle2, Cpu } from 'lucide-react';

export default function CodeAuditModal({ packageData, onClose }) {
  if (!packageData || !packageData.arch_sensitivity) return null;

  const arch = packageData.arch_sensitivity;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Cpu size={20} color="#38bdf8" />
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
              Architecture Sensitivity & Remediation: {packageData.package_name}
            </h3>
          </div>
          <button className="btn btn-secondary" style={{ padding: '0.3rem 0.6rem' }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            {arch.has_simd_avx && (
              <span className="badge badge-unported">
                <AlertTriangle size={13} /> x86 SIMD / AVX Intrinsics Detected
              </span>
            )}
            {arch.simd_instruction_count > 0 && (
              <span className="badge" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#fde047', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
                <Cpu size={13} /> {arch.simd_instruction_count} SIMD Instructions
              </span>
            )}
            {arch.simd_porting_complexity && (
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.3)', textTransform: 'uppercase' }}>
                Tier: {arch.simd_porting_complexity.replace('_', ' ')}
              </span>
            )}
            {arch.has_64k_page_risk && (
              <span className="badge badge-unported">
                <AlertTriangle size={13} /> 64KB Page Size Sensitivity
              </span>
            )}
            {arch.has_inline_asm && (
              <span className="badge badge-unported">
                <AlertTriangle size={13} /> Inline x86 Assembly
              </span>
            )}
          </div>

          {arch.has_simd_avx && (
            <div style={{ background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: 'var(--radius-md)', padding: '0.85rem 1rem', marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#38bdf8', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Cpu size={16} /> Engineering Effort Calculation Derivation ({packageData.arch_complexity_effort_pd} PD)
              </div>
              <div style={{ fontSize: '0.8rem', color: '#f8fafc', marginBottom: '0.6rem', fontFamily: 'var(--font-mono)', background: 'rgba(0,0,0,0.25)', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
                Base Engineering ({arch.base_engineering_effort_pd || 2.0} PD) × Instruction Volume ({arch.simd_instruction_multiplier || 1.0}x) × Complexity Tier ({arch.simd_complexity_multiplier || 1.0}x) = <strong>{packageData.arch_complexity_effort_pd} Person-Days</strong>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '0.45rem', borderRadius: '4px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Base Engineering:</span>
                  <div style={{ fontWeight: 700, color: '#93c5fd' }}>{arch.base_engineering_effort_pd || 2.0} PD</div>
                </div>
                <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '0.45rem', borderRadius: '4px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>SIMD Volume ({arch.simd_instruction_count} instrs):</span>
                  <div style={{ fontWeight: 700, color: '#facc15' }}>
                    {arch.simd_instruction_multiplier || 1.0}x ({arch.simd_instruction_count > 500 ? '>500 bracket' : arch.simd_instruction_count > 200 ? '201-500 bracket' : arch.simd_instruction_count > 50 ? '51-200 bracket' : '1-50 bracket'})
                  </div>
                </div>
                <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '0.45rem', borderRadius: '4px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Complexity Tier:</span>
                  <div style={{ fontWeight: 700, color: '#38bdf8', textTransform: 'uppercase' }}>
                    {arch.simd_complexity_multiplier || 1.0}x ({arch.simd_porting_complexity?.replace('_', ' ') || 'direct'})
                  </div>
                </div>
              </div>
            </div>
          )}

          {arch.simd_details && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>SIMD Analysis:</div>
              <p style={{ fontSize: '0.88rem', marginTop: '0.2rem' }}>{arch.simd_details}</p>
            </div>
          )}

          {arch.page_risk_details && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>64KB Page Size Risk:</div>
              <p style={{ fontSize: '0.88rem', marginTop: '0.2rem' }}>{arch.page_risk_details}</p>
            </div>
          )}

          {arch.code_snippet && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                Flagged Source Code Pattern:
              </div>
              <pre className="code-preview-box">{arch.code_snippet}</pre>
            </div>
          )}

          {arch.remediation_strategy && (
            <div style={{ background: 'rgba(25, 128, 56, 0.12)', border: '1px solid rgba(74, 222, 128, 0.3)', padding: '1rem', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.3rem' }}>
                <CheckCircle2 size={16} /> Recommended Power (ppc64le) Remediation Vector
              </div>
              <p style={{ fontSize: '0.88rem', color: '#f1f5f9', lineHeight: 1.5 }}>
                {arch.remediation_strategy}
              </p>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
