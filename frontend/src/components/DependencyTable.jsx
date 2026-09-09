import React, { useState } from 'react';
import { 
  Check, 
  ExternalLink, 
  ChevronDown, 
  ChevronRight, 
  Code, 
  Cpu, 
  Wrench, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle,
  HelpCircle,
  Sparkles
} from 'lucide-react';

export default function DependencyTable({ packages, onOpenCodeAudit }) {
  const [filter, setFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedRows, setExpandedRows] = useState({});

  if (!packages || packages.length === 0) return null;

  const toggleRow = (name) => {
    setExpandedRows(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'native_available':
        return <span className="badge badge-native"><Check size={12} /> Native ppc64le</span>;
      case 'platform_agnostic':
        return <span className="badge badge-agnostic"><Check size={12} /> Platform Agnostic</span>;
      case 'substitute_available':
        return <span className="badge badge-substitute"><Sparkles size={12} /> Substitute Exists</span>;
      case 'unported_build_required':
        return <span className="badge badge-unported"><Wrench size={12} /> Source Build Required</span>;
      case 'blocker':
        return <span className="badge badge-blocker"><XCircle size={12} /> x86 Blocker</span>;
      default:
        return <span className="badge badge-unported">{status}</span>;
    }
  };

  const filteredPackages = packages.filter(p => {
    if (filter !== 'ALL' && p.status !== filter) return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      return p.package_name.toLowerCase().includes(q) || 
             p.ecosystem.toLowerCase().includes(q) ||
             (p.substitute_package && p.substitute_package.toLowerCase().includes(q));
    }
    return true;
  });

  return (
    <div className="glass-card" id="dependency-matrix">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
            Dependency Readiness & Build-Tree Matrix
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Inspect ready packages, alternative Power packages, and scoped build-time transitive dependencies for unported libraries.
          </p>
        </div>

        {/* Filter Chips */}
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {['ALL', 'native_available', 'substitute_available', 'unported_build_required', 'blocker'].map((f) => (
            <button
              key={f}
              className={`preset-chip ${filter === f ? 'active' : ''}`}
              style={{ fontSize: '0.78rem', padding: '0.35rem 0.65rem' }}
              onClick={() => setFilter(f)}
            >
              {f === 'ALL' ? 'All Packages' : f === 'native_available' ? 'Native' : f === 'substitute_available' ? 'Substitutes' : f === 'unported_build_required' ? 'Unported' : 'Blockers'}
            </button>
          ))}
        </div>
      </div>

      {/* Effort Sizing Guide Banner */}
      <div style={{ 
        background: 'rgba(30, 41, 59, 0.45)', 
        border: '1px solid rgba(255, 255, 255, 0.08)', 
        borderRadius: 'var(--radius-md)', 
        padding: '0.55rem 0.85rem', 
        marginBottom: '1rem', 
        fontSize: '0.78rem', 
        display: 'flex', 
        gap: '1.25rem', 
        flexWrap: 'wrap', 
        alignItems: 'center',
        color: 'var(--text-muted)'
      }}>
        <span style={{ fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <HelpCircle size={14} color="#38bdf8" /> Effort Breakdown Guide:
        </span>
        <span>
          <strong style={{ color: '#93c5fd' }}>Build</strong>: Source compilation, toolchain setup & packaging.
        </span>
        <span>
          <strong style={{ color: '#facc15' }}>Engineering</strong>: Architecture adaptation (SIMD/VSX vector porting, replacing proprietary x86 blockers, 64KB page alignment).
        </span>
        <span>
          <strong style={{ color: '#4ade80' }}>Test</strong>: Verification suites, accuracy harnesses & benchmarks.
        </span>
      </div>

      <div style={{ marginBottom: '1rem' }}>
        <input 
          type="text" 
          className="form-control" 
          placeholder="Filter components by name or ecosystem..." 
          value={searchTerm} 
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ width: '100%', maxWidth: '400px', fontSize: '0.85rem' }}
        />
      </div>

      <div className="table-responsive">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '30px' }}></th>
              <th>Component & Ecosystem</th>
              <th>Readiness Status</th>
              <th>Build System & Toolchain</th>
              <th>Transitive Build Scope</th>
              <th>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <span>Estimated Effort</span>
                  <span 
                    title="Effort breakdown:&#10;• Build: Clean source compilation & packaging&#10;• Engineering: Architecture adaptation (SIMD/VSX, replacing proprietary x86 blockers, 64KB page tuning)&#10;• Test: Verification suites & harnesses"
                    style={{ cursor: 'help', color: 'var(--text-muted)' }}
                  >
                    <HelpCircle size={13} />
                  </span>
                </div>
              </th>
              <th>Evidence & Links</th>
            </tr>
          </thead>
          <tbody>
            {filteredPackages.map((p) => {
              const isExpanded = !!expandedRows[p.package_name];
              const hasTransitiveDeps = p.build_dependencies && p.build_dependencies.length > 0;
              const hasArchFlags = p.arch_sensitivity && (p.arch_sensitivity.has_simd_avx || p.arch_sensitivity.has_64k_page_risk || p.arch_sensitivity.has_inline_asm);
              const hasTestDeps = p.test_dependencies && p.test_dependencies.length > 0;
              const hasDocker = p.dockerfile_image_findings && p.dockerfile_image_findings.length > 0;
              const hasConfig = p.config_image_findings && p.config_image_findings.length > 0;
              const hasArchScan = !!p.arch_support_scan;
              const hasDetails = hasTransitiveDeps || hasArchFlags || hasTestDeps || hasDocker || hasConfig || hasArchScan;

              return (
                <React.Fragment key={p.package_name}>
                  <tr className={hasDetails ? 'row-expandable' : ''} onClick={() => hasDetails && toggleRow(p.package_name)}>
                    <td>
                      {hasDetails ? (
                        isExpanded ? <ChevronDown size={16} color="#94a3b8" /> : <ChevronRight size={16} color="#94a3b8" />
                      ) : null}
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {p.package_name}
                        <span className="code-pill" style={{ color: 'var(--text-muted)' }}>{p.requested_version || 'latest'}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>
                        {p.ecosystem} • {p.tier_description}
                      </div>
                      {p.substitute_package && (
                        <div style={{ fontSize: '0.78rem', color: '#c084fc', marginTop: '0.2rem' }}>
                          ↳ Recommend: <strong>{p.substitute_package}</strong>
                        </div>
                      )}
                      {p.version_warning && (
                        <div style={{ fontSize: '0.74rem', color: '#facc15', marginTop: '0.25rem', display: 'flex', alignItems: 'flex-start', gap: '0.3rem', background: 'rgba(234, 179, 8, 0.1)', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>
                          <AlertTriangle size={12} style={{ marginTop: '2px', flexShrink: 0 }} />
                          <span>{p.version_warning}</span>
                        </div>
                      )}
                    </td>
                    <td>{getStatusBadge(p.status)}</td>
                    <td>
                      {p.build_system ? (
                        <div>
                          <span className="code-pill">{p.build_system}</span>
                          {p.toolchain_prerequisites?.length > 0 && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.15rem' }}>
                              {p.toolchain_prerequisites.map(t => t.tool).join(', ')}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>Prebuilt Binary</span>
                      )}
                    </td>
                    <td>
                      {hasTransitiveDeps ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span style={{ fontWeight: 700, color: p.transitive_deps_effort_pd > 0 ? '#facc15' : '#4ade80' }}>
                            {p.build_dependencies.length} Build-Requires
                          </span>
                          {p.transitive_deps_effort_pd > 0 && (
                            <span className="badge badge-unported" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem' }}>
                              +{p.transitive_deps_effort_pd} PD unported
                            </span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>No extra build deps</span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: p.total_effort_pd > 0 ? '#60a5fa' : '#4ade80' }}>
                        {p.total_effort_pd > 0 ? `${p.total_effort_pd} PD` : '0 PD (Ready)'}
                      </div>
                      {p.total_effort_pd > 0 && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.15rem' }}>
                          <span title="Build: Standard compilation & packaging">Build: {p.base_build_effort_pd}d</span>
                          {' | '}
                          <span title="Engineering: Architecture adaptation (SIMD/VSX translation, replacing proprietary x86 blockers, 64KB page tuning)">Engineering: {p.arch_complexity_effort_pd}d</span>
                          {p.test_effort_pd > 0 && (
                            <>
                              {' | '}
                              <span title="Test: Verification suites & test harness porting">Test: {p.test_effort_pd}d</span>
                            </>
                          )}
                        </div>
                      )}
                    </td>
                    <td>
                      {p.evidence_url ? (
                        <a 
                          href={p.evidence_url} 
                          target="_blank" 
                          rel="noopener noreferrer" 
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#38bdf8', fontSize: '0.8rem', textDecoration: 'none' }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          Verify Source <ExternalLink size={12} />
                        </a>
                      ) : (
                        <span style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>Catalog Checked</span>
                      )}
                    </td>
                  </tr>

                  {/* Expandable Transitive Iceberg Drawer */}
                  {isExpanded && (
                    <tr>
                      <td colSpan={7} style={{ padding: '0.5rem 1rem 1rem 1rem', background: 'rgba(10, 14, 24, 0.6)' }}>
                        <div className="sub-table-container">
                          <div className="sub-table-header">
                            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <Wrench size={16} /> Scoped Build-Time Transitive Dependencies for <code>{p.package_name}</code>
                            </span>
                            {hasArchFlags && (
                              <button 
                                className="btn btn-secondary" 
                                style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
                                onClick={(e) => { e.stopPropagation(); onOpenCodeAudit(p); }}
                              >
                                <Code size={13} /> View Architecture Code Audit & SIMDe Fix
                              </button>
                            )}
                          </div>

                          {p.porting_notes && (
                            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                              <strong>Triage Analysis:</strong> {p.porting_notes}
                            </p>
                          )}

                          {/* Nested Transitive Dependency List */}
                          {hasTransitiveDeps && (
                            <div style={{ marginBottom: '1rem' }}>
                              <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: 'var(--text-muted)' }}>Requirement Name</th>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: 'var(--text-muted)' }}>Status on ppc64le</th>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: 'var(--text-muted)' }}>Porting Sizing</th>
                                    <th style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: 'var(--text-muted)' }}>Upstream Proof / Notes</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.build_dependencies.map((dep, dIdx) => (
                                    <tr key={dIdx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                      <td style={{ padding: '0.45rem 0.6rem', fontFamily: 'var(--font-mono)' }}>
                                        {dep.name}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem' }}>
                                        {dep.status === 'native_available' ? (
                                          <span style={{ color: '#4ade80', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                            <CheckCircle2 size={13} /> Native in OS
                                          </span>
                                        ) : (
                                          <span style={{ color: '#fef08a', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                            <AlertTriangle size={13} /> Unported Sub-Dependency
                                          </span>
                                        )}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', fontWeight: 600 }}>
                                        {dep.porting_effort_pd > 0 ? `+${dep.porting_effort_pd} PD` : '0 PD'}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                                        {dep.evidence_source} {dep.notes ? `(${dep.notes})` : ''}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Test Dependencies & Harnesses (Sub-Task 4) */}
                          {hasTestDeps && (
                            <div style={{ marginTop: '0.75rem', marginBottom: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#93c5fd', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                🧪 Test Verification & Test Dependencies (+{p.test_effort_pd} PD)
                              </div>
                              <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '4px' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', color: 'var(--text-muted)' }}>Test Framework / Harness</th>
                                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', color: 'var(--text-muted)' }}>Type</th>
                                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', color: 'var(--text-muted)' }}>ppc64le Status</th>
                                    <th style={{ textAlign: 'left', padding: '0.35rem 0.5rem', color: 'var(--text-muted)' }}>Effort</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.test_dependencies.map((td, tIdx) => (
                                    <tr key={tIdx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                      <td style={{ padding: '0.35rem 0.5rem', fontFamily: 'var(--font-mono)' }}>{td.name}</td>
                                      <td style={{ padding: '0.35rem 0.5rem', color: 'var(--text-dim)' }}>{td.test_dep_type}</td>
                                      <td style={{ padding: '0.35rem 0.5rem' }}>
                                        {td.status === 'native_available' ? (
                                          <span style={{ color: '#4ade80' }}>Verified Ready</span>
                                        ) : (
                                          <span style={{ color: '#facc15' }}>Requires Porting ({td.notes || td.evidence_source})</span>
                                        )}
                                      </td>
                                      <td style={{ padding: '0.35rem 0.5rem', fontWeight: 600 }}>{td.porting_effort_pd > 0 ? `+${td.porting_effort_pd} PD` : '0 PD'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Architecture Support Scan (Sub-Task 6) */}
                          {hasArchScan && (
                            <div style={{ marginTop: '0.75rem', padding: '0.6rem', background: 'rgba(30, 41, 59, 0.4)', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.08)' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.3rem' }}>
                                🏛️ Upstream Architecture Posture & CI Scan
                              </div>
                              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                                <span>Source: <code>{p.arch_support_scan.scan_source}</code></span>
                                <span>CI Matrix Power: <strong>{p.arch_support_scan.ci_matrix_has_power ? 'Yes (Discount applied) ✅' : 'None ❌'}</strong></span>
                                <span>Adjustment Factor: <strong>{p.arch_support_scan.effort_adjustment_factor}x</strong></span>
                              </div>
                            </div>
                          )}

                          {/* Dockerfile Base Images (Sub-Task 5) */}
                          {hasDocker && (
                            <div style={{ marginTop: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#38bdf8', marginBottom: '0.3rem' }}>
                                🐳 Discovered Dockerfile Base Images
                              </div>
                              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                {p.dockerfile_image_findings.map((df, idx) => (
                                  <span key={idx} className="code-pill" style={{ fontSize: '0.75rem' }}>
                                    {df.dockerfile_path}: <strong>{df.base_image}:{df.tag}</strong> ({df.status})
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Compose / CI Images (Sub-Task 7) */}
                          {hasConfig && (
                            <div style={{ marginTop: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#a78bfa', marginBottom: '0.3rem' }}>
                                ⚙️ Discovered Compose / CI Images
                              </div>
                              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                {p.config_image_findings.map((cf, idx) => (
                                  <span key={idx} className="code-pill" style={{ fontSize: '0.75rem' }}>
                                    {cf.config_file_path}: <strong>{cf.image_ref}</strong> ({cf.status})
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
