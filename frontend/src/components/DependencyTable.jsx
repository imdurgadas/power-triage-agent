import React, { useState } from 'react';
import {
  Tile,
  Button,
  Tag,
  TextInput,
  Link,
  StructuredListWrapper,
  StructuredListHead,
  StructuredListRow,
  StructuredListCell,
  StructuredListBody,
} from '@carbon/react';
import {
  Checkmark,
  Launch,
  ChevronDown,
  ChevronRight,
  Code,
  Tools,
  Warning,
  CheckmarkFilled,
  WarningAltFilled,
  SubtractAlt,
  Information,
  Layers,
} from '@carbon/icons-react';

function getStatusBadge(status) {
  switch (status) {
    case 'native_available':
      return <span className="porting-badge porting-badge--native"><Checkmark size={12} /> Native ppc64le</span>;
    case 'platform_agnostic':
      return <span className="porting-badge porting-badge--agnostic"><Checkmark size={12} /> Platform Agnostic</span>;
    case 'substitute_available':
      return <span className="porting-badge porting-badge--substitute"><Layers size={12} /> Substitute Exists</span>;
    case 'unported_build_required':
      return <span className="porting-badge porting-badge--unported"><Tools size={12} /> Source Build Required</span>;
    case 'blocker':
      return <span className="porting-badge porting-badge--blocker"><SubtractAlt size={12} /> x86 Blocker</span>;
    default:
      return <span className="porting-badge porting-badge--unported">{status}</span>;
  }
}


function getDeliverableBadge(match) {
  switch (match) {
    case 'supported':
      return <span className="porting-badge porting-badge--deliverable-ok"><Checkmark size={12} /> Supported</span>;
    case 'partial_different_type':
      return <span className="porting-badge porting-badge--deliverable-partial"><Warning size={12} /> Partial — different type</span>;
    case 'partial_different_version':
      return <span className="porting-badge porting-badge--deliverable-partial"><Warning size={12} /> Partial — different version</span>;
    case 'not_supported':
      return <span className="porting-badge porting-badge--deliverable-no"><SubtractAlt size={12} /> Not Supported</span>;
    default:
      return null;
  }
}


export default function DependencyTable({ packages, onOpenCodeAudit }) {
  const [filter, setFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedRows, setExpandedRows] = useState({});

  if (!packages || packages.length === 0) return null;

  const toggleRow = (name) => {
    setExpandedRows(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const filteredPackages = packages.filter(p => {
    if (filter !== 'ALL' && p.status !== filter) return false;
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      return (
        p.package_name.toLowerCase().includes(q) ||
        p.ecosystem.toLowerCase().includes(q) ||
        (p.substitute_package && p.substitute_package.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const filterOptions = [
    { value: 'ALL', label: 'All' },
    { value: 'native_available', label: 'Native' },
    { value: 'substitute_available', label: 'Substitutes' },
    { value: 'unported_build_required', label: 'Unported' },
    { value: 'blocker', label: 'Blockers' },
  ];

  return (
    <Tile id="dependency-matrix">
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem' }}>
        <div>
          <h3 className="cds--productive-heading-03">Dependency Readiness & Build-Tree Matrix</h3>
          <p className="cds--body-short-01" style={{ color: 'var(--cds-text-secondary)', marginTop: '0.25rem' }}>
            Inspect ready packages, alternative Power packages, and scoped build-time transitive dependencies for unported libraries.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          {filterOptions.map(({ value, label }) => (
            <Tag
              key={value}
              type={filter === value ? 'blue' : 'gray'}
              size="md"
              style={{ cursor: 'pointer' }}
              onClick={() => setFilter(value)}
            >
              {label}
            </Tag>
          ))}
        </div>
      </div>

      {/* Effort guide */}
      <div
        style={{
          background: 'var(--cds-layer-02)',
          border: '1px solid var(--cds-border-subtle-01)',
          borderRadius: '2px',
          padding: '0.5rem 0.85rem',
          marginBottom: '1rem',
          fontSize: '0.78rem',
          display: 'flex',
          gap: '1.25rem',
          flexWrap: 'wrap',
          alignItems: 'center',
          color: 'var(--cds-text-secondary)',
        }}
      >
        <span style={{ fontWeight: 600, color: 'var(--cds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <Information size={14} style={{ color: 'var(--cds-interactive)' }} /> Effort Breakdown Guide:
        </span>
        <span><strong style={{ color: 'var(--cds-link-primary)' }}>Build</strong>: Source compilation, toolchain setup &amp; packaging.</span>
        <span><strong style={{ color: 'var(--cds-support-warning)' }}>Engineering</strong>: Architecture adaptation (SIMD/VSX vector porting, replacing proprietary x86 blockers, 64KB page alignment).</span>
        <span><strong style={{ color: 'var(--cds-support-success)' }}>Test</strong>: Verification suites, accuracy harnesses &amp; benchmarks.</span>
      </div>

      {/* Search */}
      <div style={{ marginBottom: '1rem', maxWidth: '400px' }}>
        <TextInput
          id="dep-search"
          labelText=""
          hideLabel
          size="md"
          placeholder="Filter components by name or ecosystem..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Table */}
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <table
          className="cds--data-table cds--data-table--normal cds--data-table--sort"
          style={{ width: '100%' }}
        >
          <thead>
            <tr>
              <th style={{ width: '32px' }}><span className="cds--table-header-label"></span></th>
              <th><span className="cds--table-header-label">Component &amp; Ecosystem</span></th>
              <th><span className="cds--table-header-label">Readiness Status</span></th>
              <th><span className="cds--table-header-label">Deliverable Support</span></th>
              <th><span className="cds--table-header-label">Build System &amp; Toolchain</span></th>
              <th><span className="cds--table-header-label">Transitive Build Scope</span></th>
              <th><span className="cds--table-header-label">Estimated Effort</span></th>
              <th><span className="cds--table-header-label">Evidence &amp; Links</span></th>
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
                  <tr
                    style={{ cursor: hasDetails ? 'pointer' : 'default' }}
                    onClick={() => hasDetails && toggleRow(p.package_name)}
                  >
                    <td>
                      {hasDetails
                        ? (isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />)
                        : null}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {p.package_name}
                        <span className="code-pill">{p.requested_version || 'latest'}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--cds-text-secondary)', textTransform: 'uppercase', marginTop: '0.15rem' }}>
                        {p.ecosystem} · {p.tier_description}
                      </div>
                      {p.substitute_package && (
                        <div style={{ fontSize: '0.78rem', color: 'var(--cds-support-info)', marginTop: '0.15rem' }}>
                          ↳ Recommend: <strong>{p.substitute_package}</strong>
                        </div>
                      )}
                      {p.version_warning && (
                        <div style={{ fontSize: '0.74rem', color: 'var(--cds-support-warning)', marginTop: '0.2rem', display: 'flex', alignItems: 'flex-start', gap: '0.3rem' }}>
                          <Warning size={12} style={{ marginTop: '2px', flexShrink: 0 }} />
                          <span>{p.version_warning}</span>
                        </div>
                      )}
                    </td>
                    <td>{getStatusBadge(p.status)}</td>
                    <td>
                      {getDeliverableBadge(p.deliverable_match)}
                      {p.deliverable_detail && (
                        <div style={{ fontSize: '0.73rem', color: 'var(--cds-text-secondary)', marginTop: '0.2rem', maxWidth: '220px', lineHeight: 1.35 }}>
                          {p.deliverable_detail}
                        </div>
                      )}
                    </td>
                    <td>
                      {p.build_system ? (
                        <div>
                          <span className="code-pill">{p.build_system}</span>
                          {p.toolchain_prerequisites?.length > 0 && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--cds-text-secondary)', marginTop: '0.15rem' }}>
                              {p.toolchain_prerequisites.map(t => t.tool).join(', ')}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.8rem' }}>Prebuilt Binary</span>
                      )}
                    </td>
                    <td>
                      {hasTransitiveDeps ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span style={{ fontWeight: 600, color: p.transitive_deps_effort_pd > 0 ? 'var(--cds-support-warning)' : 'var(--cds-support-success)' }}>
                            {p.build_dependencies.length} Build-Requires
                          </span>
                          {p.transitive_deps_effort_pd > 0 && (
                            <span className="porting-badge porting-badge--unported" style={{ fontSize: '0.7rem' }}>
                              +{p.transitive_deps_effort_pd} PD unported
                            </span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.8rem' }}>No extra build deps</span>
                      )}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: p.total_effort_pd > 0 ? 'var(--cds-interactive)' : 'var(--cds-support-success)' }}>
                        {p.total_effort_pd > 0 ? `${p.total_effort_pd} PD` : '0 PD (Ready)'}
                      </div>
                      {p.total_effort_pd > 0 && (
                        <div style={{ fontSize: '0.72rem', color: 'var(--cds-text-secondary)', marginTop: '0.1rem' }}>
                          <span>Build: {p.base_build_effort_pd}d</span>
                          {' | '}
                          <span>Eng: {p.arch_complexity_effort_pd}d</span>
                          {p.test_effort_pd > 0 && <>{' | '}<span>Test: {p.test_effort_pd}d</span></>}
                        </div>
                      )}
                    </td>
                    <td>
                      {p.evidence_url ? (
                        <Link
                          href={p.evidence_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          style={{ fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                        >
                          Verify Source <Launch size={12} />
                        </Link>
                      ) : (
                        <span style={{ color: 'var(--cds-text-secondary)', fontSize: '0.8rem' }}>Catalog Checked</span>
                      )}
                    </td>
                  </tr>

                  {/* Expandable drawer */}
                  {isExpanded && (
                    <tr>
                      <td colSpan={8} style={{ padding: '0.5rem 1rem 1rem', background: 'var(--cds-layer-02)' }}>
                        <div style={{ border: '1px solid var(--cds-border-subtle-01)', borderRadius: '2px', padding: '1.25rem' }}>
                          {/* Drawer header */}
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                            <span style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--cds-support-warning)' }}>
                              <Tools size={16} /> Scoped Build-Time Transitive Dependencies for{' '}
                              <code style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{p.package_name}</code>
                            </span>
                            {hasArchFlags && (
                              <Button
                                kind="ghost"
                                size="sm"
                                renderIcon={Code}
                                onClick={(e) => { e.stopPropagation(); onOpenCodeAudit(p); }}
                              >
                                View Architecture Code Audit &amp; SIMDe Fix
                              </Button>
                            )}
                          </div>

                          {p.porting_notes && (
                            <p className="cds--body-short-01" style={{ marginBottom: '0.75rem', color: 'var(--cds-text-secondary)' }}>
                              <strong>Triage Analysis:</strong> {p.porting_notes}
                            </p>
                          )}

                          {/* Effort derivation */}
                          {p.total_effort_pd > 0 && (
                            <div className="effort-derivation">
                              <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--cds-interactive)', marginBottom: '0.35rem' }}>
                                📐 Effort Sizing Derivation ({p.total_effort_pd} Person-Days Total)
                              </div>
                              <div style={{ fontSize: '0.76rem', color: 'var(--cds-text-secondary)', fontFamily: "'IBM Plex Mono', monospace", marginBottom: '0.6rem' }}>
                                Total {p.total_effort_pd} PD = Build ({p.base_build_effort_pd}d) + Engineering ({p.arch_complexity_effort_pd}d) + Test ({p.test_effort_pd}d)
                                {p.transitive_deps_effort_pd > 0 ? ` + Transitive (${p.transitive_deps_effort_pd}d)` : ''}
                              </div>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                                <div style={{ background: 'var(--cds-layer-01)', padding: '0.5rem', borderRadius: '2px' }}>
                                  <div style={{ color: 'var(--cds-link-primary)', fontWeight: 600 }}>1. Base Compilation</div>
                                  <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>{p.base_build_effort_pd} PD</div>
                                  <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.72rem' }}>Toolchain &amp; clean source build</div>
                                </div>
                                <div style={{ background: 'var(--cds-layer-01)', padding: '0.5rem', borderRadius: '2px' }}>
                                  <div style={{ color: 'var(--cds-support-warning)', fontWeight: 600 }}>2. Engineering Adaptation</div>
                                  <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>{p.arch_complexity_effort_pd} PD</div>
                                  {p.arch_sensitivity?.simd_instruction_count > 0 ? (
                                    <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.72rem', lineHeight: 1.3 }}>
                                      Base {p.arch_sensitivity.base_engineering_effort_pd || 2.0}d × {p.arch_sensitivity.simd_instruction_multiplier || 1.0}x ({p.arch_sensitivity.simd_instruction_count} SIMD)
                                    </div>
                                  ) : (
                                    <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.72rem' }}>Architecture adaptation</div>
                                  )}
                                </div>
                                {p.test_effort_pd > 0 && (
                                  <div style={{ background: 'var(--cds-layer-01)', padding: '0.5rem', borderRadius: '2px' }}>
                                    <div style={{ color: 'var(--cds-support-success)', fontWeight: 600 }}>3. Testing &amp; Validation</div>
                                    <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>{p.test_effort_pd} PD</div>
                                    <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.72rem' }}>{p.test_dependencies?.length || 0} test harness(es)</div>
                                  </div>
                                )}
                                {p.transitive_deps_effort_pd > 0 && (
                                  <div style={{ background: 'var(--cds-layer-01)', padding: '0.5rem', borderRadius: '2px' }}>
                                    <div style={{ color: 'var(--cds-support-error)', fontWeight: 600 }}>4. Unported Transitive Deps</div>
                                    <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>+{p.transitive_deps_effort_pd} PD</div>
                                    <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.72rem' }}>Transitive build requirements</div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Transitive deps table */}
                          {hasTransitiveDeps && (
                            <div style={{ marginBottom: '1rem' }}>
                              <table style={{ width: '100%', fontSize: '0.82rem', borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid var(--cds-border-subtle-01)' }}>
                                    {['Requirement Name', 'Status on ppc64le', 'Porting Sizing', 'Upstream Proof / Notes'].map(h => (
                                      <th key={h} style={{ textAlign: 'left', padding: '0.4rem 0.6rem', color: 'var(--cds-text-secondary)', fontWeight: 600 }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.build_dependencies.map((dep, dIdx) => (
                                    <tr key={dIdx} style={{ borderBottom: '1px solid var(--cds-border-subtle-00)' }}>
                                      <td style={{ padding: '0.45rem 0.6rem', fontFamily: "'IBM Plex Mono', monospace" }}>{dep.name}</td>
                                      <td style={{ padding: '0.45rem 0.6rem' }}>
                                        {dep.status === 'native_available' ? (
                                          <span style={{ color: 'var(--cds-support-success)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                            <CheckmarkFilled size={13} /> Native in OS
                                          </span>
                                        ) : (
                                          <span style={{ color: 'var(--cds-support-warning)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                                            <WarningAltFilled size={13} /> Unported Sub-Dependency
                                          </span>
                                        )}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', fontWeight: 600 }}>
                                        {dep.porting_effort_pd > 0 ? `+${dep.porting_effort_pd} PD` : '0 PD'}
                                      </td>
                                      <td style={{ padding: '0.45rem 0.6rem', color: 'var(--cds-text-secondary)', fontSize: '0.78rem' }}>
                                        {dep.evidence_source} {dep.notes ? `(${dep.notes})` : ''}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Test dependencies */}
                          {hasTestDeps && (
                            <div style={{ marginTop: '0.75rem', marginBottom: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--cds-link-primary)', marginBottom: '0.4rem' }}>
                                🧪 Test Verification &amp; Dependencies (+{p.test_effort_pd} PD)
                              </div>
                              <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse' }}>
                                <thead>
                                  <tr style={{ borderBottom: '1px solid var(--cds-border-subtle-01)' }}>
                                    {['Test Framework / Harness', 'Type', 'ppc64le Status', 'Effort'].map(h => (
                                      <th key={h} style={{ textAlign: 'left', padding: '0.35rem 0.5rem', color: 'var(--cds-text-secondary)', fontWeight: 600 }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {p.test_dependencies.map((td, tIdx) => (
                                    <tr key={tIdx} style={{ borderBottom: '1px solid var(--cds-border-subtle-00)' }}>
                                      <td style={{ padding: '0.35rem 0.5rem', fontFamily: "'IBM Plex Mono', monospace" }}>{td.name}</td>
                                      <td style={{ padding: '0.35rem 0.5rem', color: 'var(--cds-text-secondary)' }}>{td.test_dep_type}</td>
                                      <td style={{ padding: '0.35rem 0.5rem' }}>
                                        {td.status === 'native_available'
                                          ? <span style={{ color: 'var(--cds-support-success)' }}>Verified Ready</span>
                                          : <span style={{ color: 'var(--cds-support-warning)' }}>Requires Porting ({td.notes || td.evidence_source})</span>}
                                      </td>
                                      <td style={{ padding: '0.35rem 0.5rem', fontWeight: 600 }}>{td.porting_effort_pd > 0 ? `+${td.porting_effort_pd} PD` : '0 PD'}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Architecture scan */}
                          {hasArchScan && (
                            <div style={{ marginTop: '0.75rem', padding: '0.6rem', background: 'var(--cds-layer-01)', borderRadius: '2px', border: '1px solid var(--cds-border-subtle-01)' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.3rem' }}>
                                🏛️ Upstream Architecture Posture &amp; CI Scan
                              </div>
                              <div style={{ fontSize: '0.78rem', color: 'var(--cds-text-secondary)', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                                <span>Source: <code style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{p.arch_support_scan.scan_source}</code></span>
                                <span>CI Matrix Power: <strong>{p.arch_support_scan.ci_matrix_has_power ? 'Yes ✅' : 'None ❌'}</strong></span>
                                <span>Adjustment Factor: <strong>{p.arch_support_scan.effort_adjustment_factor}x</strong></span>
                              </div>
                            </div>
                          )}

                          {/* Dockerfile images */}
                          {hasDocker && (
                            <div style={{ marginTop: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--cds-interactive)', marginBottom: '0.3rem' }}>
                                🐳 Discovered Dockerfile Base Images
                              </div>
                              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                                {p.dockerfile_image_findings.map((df, idx) => (
                                  <span key={idx} className="code-pill">
                                    {df.dockerfile_path}: <strong>{df.base_image}:{df.tag}</strong> ({df.status})
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Compose / CI images */}
                          {hasConfig && (
                            <div style={{ marginTop: '0.75rem' }}>
                              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--cds-support-info)', marginBottom: '0.3rem' }}>
                                ⚙️ Discovered Compose / CI Images
                              </div>
                              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                                {p.config_image_findings.map((cf, idx) => (
                                  <span key={idx} className="code-pill">
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
    </Tile>
  );
}
