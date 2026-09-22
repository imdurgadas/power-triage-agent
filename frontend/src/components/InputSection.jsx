import React, { useState, useEffect } from 'react';
import {
  Tile,
  Button,
  TextArea,
  Select,
  SelectItem,
  Tag,
  InlineLoading,
  PasswordInput,
} from '@carbon/react';
import {
  Play,
  CloudUpload,
  Key,
  Chip,
  Layers,
  Flash,
  DocumentBlank,
} from '@carbon/icons-react';

export default function InputSection({ onRunTriage, isRunning, presets, activePreset, onSelectPreset }) {
  const [targetEnvironment, setTargetEnvironment] = useState('rhel9_ocp');
  const [deliverableType, setDeliverableType] = useState('container');
  const [triageDepth, setTriageDepth] = useState('deep');
  const [manifestText, setManifestText] = useState('');
  const [manifestType, setManifestType] = useState('auto');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeyInput, setShowKeyInput] = useState(false);

  // Sync with selected preset
  useEffect(() => {
    if (activePreset) {
      setManifestText(activePreset.content);
      setManifestType(activePreset.manifest_type);
      // Map legacy preset target_os + target_platform to the combined environment key
      const os = activePreset.target_os || activePreset.target_environment?.split('_')[0] || 'rhel9';
      const plat = activePreset.target_platform || (activePreset.target_environment?.includes('ocp') ? 'ocp' : 'baremetal');
      const envKey = activePreset.target_environment || `${os}_${plat === 'ocp' ? 'ocp' : 'baremetal'}`;
      if (['rhel9_ocp','rhel10_ocp','rhel9_baremetal','rhel10_baremetal'].includes(envKey)) {
        setTargetEnvironment(envKey);
      }
    }
  }, [activePreset]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!manifestText.trim()) return;

    onRunTriage({
      project_name: activePreset ? activePreset.name : 'Custom Workload Migration',
      target_environment: targetEnvironment,
      deliverable_type: deliverableType,
      triage_depth: triageDepth,
      raw_manifest: manifestText,
      manifest_type: manifestType,
      gemini_api_key: geminiKey || null,
    });
  };

  const handleTextFileUpload = (e) => {
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

  const canSubmit = !isRunning && manifestText.trim().length > 0;

  return (
    <Tile id="input-section">
      {/* Section heading */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div>
          <p className="cds--label" style={{ marginBottom: '0.25rem' }}>ppc64le AI Pre-Sales</p>
          <h2 className="cds--productive-heading-04" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Chip size={20} /> Workload Assessment Parameters
          </h2>
          <p className="cds--body-short-01" style={{ marginTop: '0.25rem', color: 'var(--cds-text-secondary)' }}>
            Upload manifests, select target Power environment, and let the agent scope availability and build-time dependencies.
          </p>
        </div>
        <Button
          kind="ghost"
          size="sm"
          renderIcon={Key}
          onClick={() => setShowKeyInput(!showKeyInput)}
        >
          {geminiKey ? 'Gemini Key Configured' : 'API Key Override'}
        </Button>
      </div>

      {/* Optional API key */}
      {showKeyInput && (
        <Tile style={{ background: 'var(--cds-layer-02)', marginBottom: '1.25rem' }}>
          <PasswordInput
            id="gemini-key-input"
            labelText="Google Gemini API Key (Optional live LLM override)"
            helperText="Prototype runs in autonomous simulation mode if blank"
            placeholder="AIzaSy..."
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
          />
        </Tile>
      )}

      {/* Quick test scenario chips */}
      {presets.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '1.25rem' }}>
          <span className="cds--label">Quick Test Scenarios:</span>
          {presets.map((preset) => (
            <Tag
              key={preset.id}
              type={activePreset?.id === preset.id ? 'blue' : 'gray'}
              size="md"
              style={{ cursor: 'pointer' }}
              onClick={() => onSelectPreset(preset)}
            >
              {preset.name}
            </Tag>
          ))}
        </div>
      )}

      {/* Main form */}
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>

          {/* Left column: manifest text input */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label className="cds--label" htmlFor="manifest-input">
                Application Dependency Manifest / Stack Specification
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer', color: 'var(--cds-link-primary)', fontSize: '0.875rem' }}>
                <CloudUpload size={16} /> Upload File
                <input type="file" style={{ display: 'none' }} onChange={handleTextFileUpload} />
              </label>
            </div>
            <TextArea
              id="manifest-input"
              labelText=""
              hideLabel
              rows={9}
              value={manifestText}
              onChange={(e) => setManifestText(e.target.value)}
              placeholder="Paste Dockerfile, SBOM (JSON), requirements.txt, or unstructured description (e.g. 'nginx:1.24, redis, custom C++ dsp library with AVX2')..."
              style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}
            />
          </div>

          {/* Right column: target parameters + submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Select
              id="target-env-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Chip size={14} /> Target Environment (ppc64le)</span>}
              value={targetEnvironment}
              onChange={(e) => setTargetEnvironment(e.target.value)}
            >
              <SelectItem value="rhel9_ocp"        text="OpenShift Platform (ppc64le)" />
              <SelectItem value="rhel10_ocp"       text="OpenShift Platform — RHEL 10 (ppc64le)" />
              <SelectItem value="rhel9_baremetal"  text="Bare Metal / PowerVM — RHEL 9 (ppc64le)" />
              <SelectItem value="rhel10_baremetal" text="Bare Metal / PowerVM — RHEL 10 (ppc64le)" />
            </Select>

            <Select
              id="deliverable-type-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Layers size={14} /> Deliverable Type</span>}
              value={deliverableType}
              onChange={(e) => setDeliverableType(e.target.value)}
              helperText="Match availability against the artefact type you intend to deploy."
            >
              <SelectItem value="container"    text="Container — OCI/Docker image" />
              <SelectItem value="build"        text="Build — compiled wheel" />
              <SelectItem value="build_script" text="Build Script — IBM ppc64le build recipe" />
            </Select>

            <Select
              id="triage-depth-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Flash size={14} /> Triage Depth Mode</span>}
              value={triageDepth}
              onChange={(e) => setTriageDepth(e.target.value)}
            >
              <SelectItem value="deep" text="Deep Build & Transitive Dependency Scoping (Recommended)" />
              <SelectItem value="express" text="Express Triage (Registry lookup only)" />
            </Select>

            {/* Active input indicator */}
            {manifestText.trim() && (
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                <Tag type="teal" size="sm"><DocumentBlank size={12} style={{ marginRight: '3px' }} /> Text ready</Tag>
              </div>
            )}

            {isRunning ? (
              <InlineLoading
                description="Agentic Triage in Progress..."
                status="active"
                style={{ marginTop: 'auto' }}
              />
            ) : (
              <Button
                type="submit"
                id="run-triage-btn"
                renderIcon={Play}
                disabled={!canSubmit}
                style={{ marginTop: 'auto', width: '100%', maxWidth: '100%' }}
              >
                Launch Power Porting Triage
              </Button>
            )}
          </div>
        </div>
      </form>
    </Tile>
  );
}
