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
