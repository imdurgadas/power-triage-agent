import React, { useState, useEffect } from 'react';
import { Play, Sparkles, UploadCloud, Layers, Cpu, Server, Key, FileText, Globe, GitBranch, Terminal } from 'lucide-react';

export default function InputSection({ onRunTriage, isRunning, presets, activePreset, onSelectPreset }) {
  const [activeTab, setActiveTab] = useState('text'); // 'text' or 'url'
  const [targetOs, setTargetOs] = useState('rhel9');
  const [targetPlatform, setTargetPlatform] = useState('ocp');
  const [triageDepth, setTriageDepth] = useState('deep');
  const [manifestText, setManifestText] = useState('');
  const [manifestType, setManifestType] = useState('auto');
  const [inputUrl, setInputUrl] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeyInput, setShowKeyInput] = useState(false);

  // Sync with selected preset
  useEffect(() => {
    if (activePreset) {
      setActiveTab('text');
      setManifestText(activePreset.content);
      setTargetOs(activePreset.target_os);
      setTargetPlatform(activePreset.target_platform);
      setManifestType(activePreset.manifest_type);
    }
  }, [activePreset]);

  const urlPresets = [
    { name: "RocksDB (GitHub)", url: "https://github.com/facebook/rocksdb", os: "rhel9", platform: "baremetal" },
    { name: "RocksDB (Docs Website)", url: "https://rocksdb.org", os: "rhel9", platform: "powervm" },
    { name: "Redis Engine (GitHub)", url: "https://github.com/redis/redis", os: "rhel9", platform: "ocp" },
    { name: "FastAPI Framework", url: "https://github.com/tiangolo/fastapi", os: "rhel9", platform: "ocp" },
  ];

  const handleSelectUrlPreset = (p) => {
    setActiveTab('url');
    setInputUrl(p.url);
    setTargetOs(p.os);
    setTargetPlatform(p.platform);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (activeTab === 'text') {
      if (!manifestText.trim()) return;
      onRunTriage({
        project_name: activePreset ? activePreset.name : "Custom Workload Migration",
        target_os: targetOs,
        target_platform: targetPlatform,
        triage_depth: triageDepth,
        raw_manifest: manifestText,
        manifest_type: manifestType,
        gemini_api_key: geminiKey || null
      });
    } else {
      if (!inputUrl.trim()) return;
      const raw = inputUrl.trim();
      const isGithub = raw.includes('github.com');
      let extractedPkgName = 'URL Inferred Workload';
      try {
        const clean = raw.replace(/^https?:\/\//, '').replace(/\/$/, '');
        const parts = clean.split('/');
        if (isGithub && parts.length >= 3) {
          extractedPkgName = parts[2].replace(/\.git$/, '');
        } else if (parts.length >= 1) {
          extractedPkgName = parts[0].split('.')[0];
        }
      } catch (err) {
        extractedPkgName = 'URL Inferred Workload';
      }

      onRunTriage({
        project_name: `${extractedPkgName} Porting Qualification`,
        target_os: targetOs,
        target_platform: targetPlatform,
        triage_depth: triageDepth,
        raw_manifest: raw,
        manifest_type: "url",
        doc_url: !isGithub ? raw : null,
        git_repo_url: isGithub ? raw : null,
        gemini_api_key: geminiKey || null
      });
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setManifestText(event.target.result);
      setActiveTab('text');
      if (file.name.endsWith('.json')) setManifestType('sbom');
      else if (file.name.toLowerCase().includes('docker')) setManifestType('dockerfile');
      else if (file.name.endsWith('.txt')) setManifestType('requirements');
      else setManifestType('auto');
    };
    reader.readAsText(file);
  };

  return (
    <div className="glass-card" id="input-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
            <Cpu size={21} color="#10b981" /> Workload Assessment Parameters
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
            Ingest manifests, unstructured email text, or directly provide a GitHub / documentation URL to infer dependencies.
          </p>
        </div>
        <button 
          type="button" 
          className="btn btn-secondary" 
          style={{ fontSize: '0.78rem', padding: '0.45rem 0.8rem' }}
          onClick={() => setShowKeyInput(!showKeyInput)}
        >
          <Key size={14} color="#06b6d4" /> {geminiKey ? "Gemini Key Configured" : "API Key Override"}
        </button>
      </div>

      {showKeyInput && (
        <div style={{ background: 'rgba(16, 185, 129, 0.07)', border: '1px solid var(--border-focus)', padding: '0.85rem', borderRadius: 'var(--radius-md)', marginBottom: '1.2rem' }}>
          <label className="form-label">
            <span>Google Gemini API Key (Optional live LLM override)</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Prototype runs in autonomous simulation mode if blank</span>
          </label>
          <input 
            type="password" 
            className="form-control" 
            placeholder="AIzaSy..." 
            value={geminiKey} 
            onChange={(e) => setGeminiKey(e.target.value)} 
          />
        </div>
      )}

      {/* Input Mode Selector Tabs */}
      <div className="tabs-header">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'text' ? 'active' : ''}`}
          onClick={() => setActiveTab('text')}
        >
          <FileText size={15} /> Manifest / Free-Form Text / Email
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'url' ? 'active' : ''}`}
          onClick={() => setActiveTab('url')}
        >
          <Globe size={15} /> GitHub Repo or Documentation URL
        </button>
      </div>

      {/* Preset Selectors Bar */}
      {activeTab === 'text' ? (
        <div className="presets-bar">
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginRight: '0.25rem' }}>
            Quick Stack Presets:
          </span>
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`preset-chip ${activePreset?.id === preset.id ? 'active' : ''}`}
              onClick={() => onSelectPreset(preset)}
            >
              <Sparkles size={13} /> {preset.name}
            </button>
          ))}
        </div>
      ) : (
        <div className="presets-bar">
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginRight: '0.25rem' }}>
            Sample Repository & Docs URLs:
          </span>
          {urlPresets.map((p, idx) => (
            <button
              key={idx}
              type="button"
              className={`preset-chip ${inputUrl === p.url ? 'active' : ''}`}
              onClick={() => handleSelectUrlPreset(p)}
            >
              <GitBranch size={13} /> {p.name}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="input-grid">
          {/* Main Input Pane */}
          {activeTab === 'text' ? (
            <div className="form-group" style={{ marginBottom: 0 }}>
              <div className="form-label">
                <span className="form-label-title">
                  <FileText size={15} color="#10b981" /> Application Dependency Manifest / Free-form Text
                </span>
                <label style={{ color: '#06b6d4', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <UploadCloud size={14} /> Upload File (SBOM / Dockerfile / txt)
                  <input type="file" style={{ display: 'none' }} onChange={handleFileUpload} />
                </label>
              </div>
              <textarea
                className="form-control"
                id="manifest-input"
                rows={9}
                value={manifestText}
                onChange={(e) => setManifestText(e.target.value)}
                placeholder="Paste Dockerfile, SBOM JSON, requirements.txt, or unstructured notes (e.g. 'Customer is moving nginx:1.24, redis:7.2, and custom RocksDB storage with AVX2')..."
                required
              />
            </div>
          ) : (
            <div className="form-group" style={{ marginBottom: 0 }}>
              <div className="form-label">
                <span className="form-label-title">
                  <Globe size={15} color="#06b6d4" /> GitHub Repository or Documentation Website URL
                </span>
                <span style={{ color: 'var(--text-dim)', fontSize: '0.78rem' }}>LLM automatically crawls & infers library needs</span>
              </div>
              <input
                type="url"
                className="form-control"
                id="url-input"
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                placeholder="https://github.com/facebook/rocksdb or https://rocksdb.org"
                required
                style={{ fontSize: '0.95rem', padding: '0.85rem 1rem' }}
              />
              <div style={{ marginTop: '0.85rem', padding: '1rem', background: 'rgba(6, 182, 212, 0.06)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(6, 182, 212, 0.2)', fontSize: '0.84rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                <p style={{ fontWeight: 600, color: '#67e8f9', marginBottom: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>💡 Autonomous Dependency Discovery</span>
                </p>
                <p>
                  The triage agent will fetch repository manifests (<code>requirements.txt</code>, <code>CMakeLists.txt</code>, <code>package.json</code>, <code>Dockerfile</code>) or documentation specifications from the provided URL, infer exact library versions and build requirements via Gemini LLM, and qualify each against IBM Power (<code>ppc64le</code>).
                </p>
              </div>
            </div>
          )}

          {/* Target Architecture Parameters */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="target-os-select">
                <span className="form-label-title">
                  <Server size={15} color="#06b6d4" /> Target OS (ppc64le)
                </span>
              </label>
              <select 
                id="target-os-select" 
                className="form-control" 
                value={targetOs} 
                onChange={(e) => setTargetOs(e.target.value)}
              >
                <option value="rhel9">Red Hat Enterprise Linux 9 (ppc64le)</option>
                <option value="rhel8">Red Hat Enterprise Linux 8 (ppc64le)</option>
                <option value="ubuntu24">Ubuntu 24.04 LTS Ports (ppc64le)</option>
                <option value="ubuntu22">Ubuntu 22.04 LTS Ports (ppc64le)</option>
                <option value="sles15">SUSE Linux Enterprise Server 15</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="target-platform-select">
                <span className="form-label-title">
                  <Layers size={15} color="#10b981" /> Target Platform Runtime
                </span>
              </label>
              <select 
                id="target-platform-select" 
                className="form-control" 
                value={targetPlatform} 
                onChange={(e) => setTargetPlatform(e.target.value)}
              >
                <option value="ocp">Red Hat OpenShift on Power (OCP)</option>
                <option value="powervm">PowerVM LPAR (Linux Native)</option>
                <option value="baremetal">Bare Metal Power Server</option>
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="triage-depth-select">
                <span className="form-label-title">
                  <Cpu size={15} color="#8b5cf6" /> Triage Depth Mode
                </span>
              </label>
              <select 
                id="triage-depth-select" 
                className="form-control" 
                value={triageDepth} 
                onChange={(e) => setTriageDepth(e.target.value)}
              >
                <option value="deep">Deep Build & Transitive Dependency Scoping (Recommended)</option>
                <option value="express">Express Triage (Registry lookup only)</option>
              </select>
            </div>

            <button 
              type="submit" 
              className="btn btn-primary" 
              id="run-triage-btn"
              disabled={isRunning || (activeTab === 'text' ? !manifestText.trim() : !inputUrl.trim())}
              style={{ marginTop: 'auto', padding: '0.9rem' }}
            >
              {isRunning ? (
                <>
                  <div className="spinner" /> Agentic Triage in Progress...
                </>
              ) : (
                <>
                  <Play size={16} fill="white" /> Launch Power Porting Triage
                </>
              )}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
