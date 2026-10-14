import React, { useState, useEffect } from 'react';
import {
  Tile,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  TextArea,
  TextInput,
  PasswordInput,
  Select,
  SelectItem,
  Button,
  Tag,
  InlineLoading,
} from '@carbon/react';
import {
  Play,
  DocumentBlank,
  Chip,
  Layers,
  Flash,
  Launch,
  Key,
  Upload,
  TrashCan,
} from '@carbon/icons-react';

export default function InputSection({
  onRunTriage,
  isRunning,
}) {
  const [selectedTabIndex, setSelectedTabIndex] = useState(0); // 0: Text, 1: URL
  const [manifestText, setManifestText] = useState('');
  const [inputUrl, setInputUrl] = useState('');
  const [targetEnvironment, setTargetEnvironment] = useState('rhel9_ocp');
  const [deliverableType, setDeliverableType] = useState('build');
  const [triageDepth, setTriageDepth] = useState('deep');
  const [llmProvider, setLlmProvider] = useState('ibm_bob');
  const [bobKey, setBobKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeyInput, setShowKeyInput] = useState(false);
  const [llmConfig, setLlmConfig] = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState('');

  // Fetch detected LLM config from server on mount
  useEffect(() => {
    fetch('/api/llm-config')
      .then(res => res.json())
      .then(cfg => {
        setLlmConfig(cfg);
        if (cfg.default_provider) {
          setLlmProvider(cfg.default_provider);
        }
      })
      .catch(err => console.debug('Could not fetch LLM config:', err));
  }, []);

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string') {
        setManifestText(content);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    let targetOs = 'rhel9';
    let targetPlatform = 'ocp';
    if (targetEnvironment.startsWith('rhel10')) targetOs = 'rhel10';
    if (targetEnvironment.includes('baremetal')) targetPlatform = 'baremetal';

    const commonPayload = {
      target_os: targetOs,
      target_platform: targetPlatform,
      target_environment: targetEnvironment,
      deliverable_type: deliverableType,
      triage_depth: triageDepth,
      llm_provider: llmProvider,
      bobshell_api_key: bobKey.trim() || null,
      gemini_api_key: geminiKey.trim() || null,
    };

    if (selectedTabIndex === 0) {
      if (!manifestText.trim()) return;
      let derivedName = "Enterprise Workload Qualification";
      const lines = manifestText.split('\n').map(l => l.trim()).filter(Boolean);
      const firstNamedLine = lines.find(l => !l.startsWith('#') && !l.startsWith('//') && l.length < 50);
      if (firstNamedLine) {
        const cleanPkg = firstNamedLine.split(/[\s=<>@:]/)[0];
        if (cleanPkg) derivedName = `${cleanPkg} Workload Porting`;
      }
      onRunTriage({
        ...commonPayload,
        project_name: uploadedFileName ? `${uploadedFileName} Porting Qualification` : derivedName,
        raw_manifest: manifestText,
        manifest_type: "auto",
      });
    } else if (selectedTabIndex === 1) {
      if (!inputUrl.trim()) return;
      const raw = inputUrl.trim();
      const isGithub = raw.includes('github.com');
      let extractedPkgName = 'Workload';
      try {
        const clean = raw.replace(/^https?:\/\//, '').replace(/\/$/, '');
        const parts = clean.split('/');
        if (isGithub && parts.length >= 3) {
          extractedPkgName = parts[2].replace(/\.git$/, '');
        } else if (parts.length >= 1) {
          extractedPkgName = parts[0].split('.')[0];
        }
      } catch (err) {
        extractedPkgName = 'Workload';
      }

      onRunTriage({
        ...commonPayload,
        project_name: `${extractedPkgName} Porting Qualification`,
        raw_manifest: raw,
        manifest_type: "url",
        doc_url: !isGithub ? raw : null,
        git_repo_url: isGithub ? raw : null,
      });
    }
  };

  const canSubmit = !isRunning && (
    (selectedTabIndex === 0 && manifestText.trim().length > 0) ||
    (selectedTabIndex === 1 && inputUrl.trim().length > 0)
  );

  const isBobActive = llmProvider === 'ibm_bob';
  const hasServerBob = llmConfig?.providers?.ibm_bob?.key_configured;
  const hasServerGemini = llmConfig?.providers?.gemini?.key_configured;

  return (
    <Tile id="input-section" style={{ padding: '1.5rem', background: 'var(--cds-layer-01)' }}>
      {/* Title + AI Engine Selector */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <div>
          <h2 className="cds--productive-heading-03" style={{ color: 'var(--cds-text-primary)' }}>
            Workload Specification &amp; Qualification Vector
          </h2>
          <p className="cds--body-short-01" style={{ color: 'var(--cds-text-secondary)' }}>
            Analyze manifests, package lists, or GitHub repositories to evaluate IBM Power (ppc64le) porting feasibility.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Button
            kind={showKeyInput ? "secondary" : "ghost"}
            size="sm"
            renderIcon={Key}
            onClick={() => setShowKeyInput(!showKeyInput)}
            id="configure-keys-btn"
          >
            {showKeyInput ? 'Hide Engine Config' : 'Configure LLM Engine & Keys'}
          </Button>
        </div>
      </div>

      {/* AI Engine Selection Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        padding: '0.65rem 1rem',
        background: '#1f1f1f',
        border: '1px solid #333333',
        borderRadius: '3px',
        marginBottom: '1.25rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#c6c6c6', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Chip size={15} style={{ color: '#78a9ff' }} /> LLM Orchestrator:
          </span>

          <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
            {/* IBM Bob Button */}
            <button
              type="button"
              id="engine-bob-toggle"
              onClick={() => setLlmProvider('ibm_bob')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.35rem 0.8rem',
                borderRadius: '3px',
                border: isBobActive ? '2px solid #0f62fe' : '1px solid #4a4a4a',
                background: isBobActive ? 'rgba(15, 98, 254, 0.22)' : '#161616',
                color: isBobActive ? '#78a9ff' : '#a8a8a8',
                fontWeight: isBobActive ? 700 : 500,
                fontSize: '0.82rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease-in-out',
              }}
            >
              <span>IBM Bob</span>
              {hasServerBob && (
                <span style={{ background: '#24a148', color: '#ffffff', fontSize: '0.65rem', padding: '1px 5px', borderRadius: '4px', fontWeight: 700 }}>
                  ACTIVE
                </span>
              )}
            </button>

            {/* Google Gemini Button */}
            <button
              type="button"
              id="engine-gemini-toggle"
              onClick={() => setLlmProvider('gemini')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.35rem 0.8rem',
                borderRadius: '3px',
                border: !isBobActive ? '2px solid #8a3ffc' : '1px solid #4a4a4a',
                background: !isBobActive ? 'rgba(138, 63, 252, 0.22)' : '#161616',
                color: !isBobActive ? '#d4bbff' : '#a8a8a8',
                fontWeight: !isBobActive ? 700 : 500,
                fontSize: '0.82rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease-in-out',
              }}
            >
              <Flash size={13} />
              <span>Google Gemini</span>
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.78rem', color: '#8d8d8d' }}>
          {isBobActive ? (
            <span>⚡ Headless CLI Execution • Real-time Token &amp; Cost Telemetry</span>
          ) : (
            <span>🌐 Google GenAI Cloud API • Prompt / Candidate Token Tracking</span>
          )}
        </div>
      </div>

      {/* Collapsible Key Configuration Drawer */}
      {showKeyInput && (
        <div style={{
          marginBottom: '1.25rem',
          padding: '1rem',
          background: '#1e1e1e',
          borderRadius: '3px',
          border: '1px solid #3d3d3d',
          borderLeft: isBobActive ? '4px solid #0f62fe' : '4px solid #8a3ffc',
        }}>
          <h4 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f4f4f4', marginBottom: '0.75rem' }}>
            LLM Provider Configuration &amp; Credentials
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div>
              <PasswordInput
                id="bob-key-input"
                labelText="IBM Bob Key (BOBSHELL_API_KEY)"
                helperText={hasServerBob ? "✓ Loaded from server .env file. Enter only to override." : "Enter your IBM Bob API key."}
                placeholder={hasServerBob ? "Configured in server .env" : "your_bob_api_key..."}
                value={bobKey}
                onChange={(e) => setBobKey(e.target.value)}
              />
            </div>
            <div>
              <PasswordInput
                id="gemini-key-input"
                labelText="Google Gemini API Key (GEMINI_API_KEY)"
                helperText={hasServerGemini ? "✓ Loaded from server .env file. Enter only to override." : "Enter your Google Gemini API key."}
                placeholder={hasServerGemini ? "Configured in server .env" : "AIzaSy..."}
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
              />
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(300px, 1fr)', gap: '1.5rem' }}>
          {/* Left: Input Tabs (Manifest Text, URL, Image) */}
          <div>
            <Tabs
              selectedIndex={selectedTabIndex}
              onChange={({ selectedIndex }) => setSelectedTabIndex(selectedIndex)}
            >
              <TabList aria-label="Input specification type" contained>
                <Tab renderIcon={DocumentBlank}>Manifest File / Text</Tab>
                <Tab renderIcon={Launch}>GitHub Repo / Docs URL</Tab>
              </TabList>
              <TabPanels>
                {/* Panel 0: Manifest Text & File Upload */}
                <TabPanel style={{ padding: '1rem 0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
                    <span className="cds--label" style={{ fontSize: '0.82rem', color: '#c6c6c6' }}>
                      Manifest Specification:
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <label
                        htmlFor="manifest-file-upload"
                        className="cds--btn cds--btn--sm cds--btn--tertiary"
                        style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', margin: 0, padding: '0 0.75rem', height: '2rem' }}
                      >
                        <Upload size={14} />
                        <span>{uploadedFileName ? `Loaded: ${uploadedFileName}` : 'Upload Manifest File'}</span>
                      </label>
                      <input
                        id="manifest-file-upload"
                        type="file"
                        style={{ display: 'none' }}
                        onChange={handleFileUpload}
                      />
                      {manifestText && (
                        <Button
                          kind="ghost"
                          size="sm"
                          hasIconOnly
                          renderIcon={TrashCan}
                          iconDescription="Clear manifest input"
                          onClick={() => { setManifestText(''); setUploadedFileName(''); }}
                        />
                      )}
                    </div>
                  </div>

                  <TextArea
                    id="manifest-text-input"
                    labelText="Manifest, Requirements, Dockerfile, or Dependency Specification"
                    helperText="Upload or paste requirements.txt, go.mod, pom.xml, package.json, Dockerfile, or direct software package list."
                    rows={9}
                    value={manifestText}
                    onChange={(e) => setManifestText(e.target.value)}
                    placeholder="Paste package dependencies, Dockerfile, requirements.txt, or upload a manifest file to evaluate IBM Power readiness."
                    style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}
                  />
                </TabPanel>

                {/* Panel 1: URL */}
                <TabPanel style={{ padding: '1rem 0' }}>
                  <div style={{ marginBottom: '1rem' }}>
                    <TextInput
                      id="input-url-field"
                      labelText="Upstream Git Repository or Documentation Site URL"
                      helperText="Specify any public or enterprise Git repository (e.g. GitHub/GitLab URL) or project documentation site URL."
                      placeholder="https://github.com/organization/repository or https://docs.example.org"
                      value={inputUrl}
                      onChange={(e) => setInputUrl(e.target.value)}
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}
                    />
                  </div>
                  <div style={{ padding: '0.85rem', background: '#1e1e1e', border: '1px solid #333', borderRadius: '4px' }}>
                    <p className="cds--helper-text-01" style={{ color: '#c6c6c6', lineHeight: 1.5, margin: 0 }}>
                      Autonomous porting agents will inspect the upstream repository or technical documentation to detect C/C++ SIMD vector intrinsics (AVX2/SSE), page-size sensitivities (64KB Linux kernels), build toolchain requirements, and transitive sub-dependencies.
                    </p>
                  </div>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </div>

          {/* Right: Target Architecture Parameters & Submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Select
              id="target-env-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Chip size={14} /> Target Environment (ppc64le)</span>}
              value={targetEnvironment}
              onChange={(e) => setTargetEnvironment(e.target.value)}
            >
              <SelectItem value="rhel9_ocp" text="Red Hat OpenShift on Power (RHEL 9)" />
              <SelectItem value="rhel10_ocp" text="Red Hat OpenShift on Power (RHEL 10)" />
              <SelectItem value="rhel9_baremetal" text="Bare Metal / PowerVM — RHEL 9 (ppc64le)" />
              <SelectItem value="rhel10_baremetal" text="Bare Metal / PowerVM — RHEL 10 (ppc64le)" />
            </Select>

            <Select
              id="deliverable-type-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Layers size={14} /> Required Deliverable Type</span>}
              value={deliverableType}
              onChange={(e) => setDeliverableType(e.target.value)}
              helperText="Match readiness against the deployment deliverable you require."
            >
              <SelectItem value="container" text="Container Image (Docker Hub / Quay / ICR)" />
              <SelectItem value="build" text="Build (Compiled Wheel / Binary / RPM)" />
              <SelectItem value="build_script" text="Build Script Recipe (ppc64le/build-scripts)" />
            </Select>

            <Select
              id="triage-depth-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Flash size={14} /> Triage Depth Mode</span>}
              value={triageDepth}
              onChange={(e) => setTriageDepth(e.target.value)}
            >
              <SelectItem value="deep" text="Deep Build & Transitive Dependency Scoping" />
              <SelectItem value="express" text="Express Triage (Registry lookup only)" />
            </Select>

            {/* Status indicator tags */}
            {((selectedTabIndex === 1 && inputUrl.trim()) || (selectedTabIndex === 2 && imageDataBase64)) && (
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {selectedTabIndex === 1 && inputUrl.trim() && (
                  <Tag type="blue" size="sm"><Launch size={12} style={{ marginRight: '3px' }} /> URL ready</Tag>
                )}
                {selectedTabIndex === 2 && imageDataBase64 && (
                  <Tag type="purple" size="sm"><Image size={12} style={{ marginRight: '3px' }} /> Image ready</Tag>
                )}
              </div>
            )}

            <Button
              type="submit"
              id="run-triage-btn"
              renderIcon={isRunning ? undefined : Play}
              disabled={isRunning || !canSubmit}
              style={{
                marginTop: 'auto',
                width: '100%',
                maxWidth: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isRunning ? (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span className="spinner" style={{ width: '14px', height: '14px', borderTopColor: '#ffffff' }} />
                  <span>Agentic Triage in Progress...</span>
                </div>
              ) : (
                'Launch Power Porting Triage'
              )}
            </Button>
          </div>
        </div>
      </form>
    </Tile>
  );
}
