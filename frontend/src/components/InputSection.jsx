import React, { useState, useEffect } from 'react';
import { Play, Sparkles, UploadCloud, Layers, Cpu, Server, Key, FileText } from 'lucide-react';

export default function InputSection({ onRunTriage, isRunning, presets, activePreset, onSelectPreset }) {
  const [targetOs, setTargetOs] = useState('rhel9');
  const [targetPlatform, setTargetPlatform] = useState('ocp');
  const [triageDepth, setTriageDepth] = useState('deep');
  const [manifestText, setManifestText] = useState('');
  const [manifestType, setManifestType] = useState('auto');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeyInput, setShowKeyInput] = useState(false);

  // Sync with selected preset
  useEffect(() => {
    if (activePreset) {
      setManifestText(activePreset.content);
      setTargetOs(activePreset.target_os);
      setTargetPlatform(activePreset.target_platform);
      setManifestType(activePreset.manifest_type);
    }
  }, [activePreset]);

  const handleSubmit = (e) => {
    e.preventDefault();
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
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setManifestText(event.target.result);
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
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Cpu size={20} color="#0f62fe" /> Workload Assessment Parameters
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.2rem' }}>
            Upload manifests, select target Power environment, and let the agent scope availability and build-time dependencies.
          </p>
        </div>
        <button 
          type="button" 
          className="btn btn-secondary" 
          style={{ fontSize: '0.78rem', padding: '0.4rem 0.75rem' }}
          onClick={() => setShowKeyInput(!showKeyInput)}
        >
          <Key size={14} /> {geminiKey ? "Gemini Key Configured" : "API Key Override"}
        </button>
      </div>

      {showKeyInput && (
        <div style={{ background: 'rgba(15, 98, 254, 0.08)', border: '1px solid var(--border-focus)', padding: '0.85rem', borderRadius: 'var(--radius-md)', marginBottom: '1rem' }}>
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

      {/* Preset Workload Selectors */}
      <div className="presets-bar">
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginRight: '0.25rem' }}>
          Quick Test Scenarios:
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

      <form onSubmit={handleSubmit}>
        <div className="input-grid">
          {/* Main Manifest Input */}
          <div className="form-group" style={{ marginBottom: 0 }}>
            <div className="form-label">
              <span>Application Dependency Manifest / Stack Specification</span>
              <label style={{ color: '#38bdf8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <UploadCloud size={14} /> Upload File (SBOM / Dockerfile / txt)
                <input type="file" style={{ display: 'none' }} onChange={handleFileUpload} />
              </label>
            </div>
            <textarea
              className="form-control"
              id="manifest-input"
              rows={8}
              value={manifestText}
              onChange={(e) => setManifestText(e.target.value)}
              placeholder="Paste Dockerfile, SBOM (JSON), requirements.txt, or unstructured description (e.g. 'nginx:1.24, redis, custom C++ dsp library with AVX2')..."
              required
            />
          </div>

          {/* Target Architecture Parameters */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="target-os-select">
                <Server size={14} /> Target OS (ppc64le)
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
                <Layers size={14} /> Target Platform Runtime
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
                <Cpu size={14} /> Triage Depth Mode
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
              disabled={isRunning || !manifestText.trim()}
              style={{ marginTop: 'auto', padding: '0.85rem' }}
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
