import React, { useState, useEffect, useRef } from 'react';
import {
  Tile,
  Button,
  TextArea,
  Select,
  SelectItem,
  Tag,
  InlineLoading,
  PasswordInput,
  Tabs,
  Tab,
  TabList,
  TabPanels,
  TabPanel,
  InlineNotification,
} from '@carbon/react';
import {
  Play,
  CloudUpload,
  Key,
  Chip,
  Layers,
  Flash,
  Image,
  TrashCan,
  DocumentBlank,
} from '@carbon/icons-react';

const ACCEPTED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // 10 MB

export default function InputSection({ onRunTriage, isRunning, presets, activePreset, onSelectPreset }) {
  const [targetEnvironment, setTargetEnvironment] = useState('rhel9_ocp');
  const [deliverableType, setDeliverableType] = useState('container');
  const [triageDepth, setTriageDepth] = useState('deep');
  const [manifestText, setManifestText] = useState('');
  const [manifestType, setManifestType] = useState('auto');
  const [inputUrl, setInputUrl] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [showKeyInput, setShowKeyInput] = useState(false);

  // Image upload state
  const [imageDataBase64, setImageDataBase64] = useState(null);
  const [imageMediaType, setImageMediaType] = useState('image/png');
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [imageFileName, setImageFileName] = useState('');
  const [imageError, setImageError] = useState('');
  const [activeInputTab, setActiveInputTab] = useState(0); // 0 = text, 1 = image
  const imageDropRef = useRef(null);

  // Sync with selected preset
  useEffect(() => {
    if (activePreset) {
      setActiveTab('text');
      setManifestText(activePreset.content);
      setManifestType(activePreset.manifest_type);
      // Map legacy preset target_os + target_platform to the combined environment key
      const os = activePreset.target_os || 'rhel9';
      const plat = activePreset.target_platform || 'ocp';
      const envKey = `${os}_${plat === 'ocp' ? 'ocp' : 'baremetal'}`;
      if (['rhel9_ocp','rhel10_ocp','rhel9_baremetal','rhel10_baremetal'].includes(envKey)) {
        setTargetEnvironment(envKey);
      }
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
    const hasText = manifestText.trim().length > 0;
    const hasImage = !!imageDataBase64;
    if (!hasText && !hasImage) return;

    onRunTriage({
      project_name: activePreset ? activePreset.name : 'Custom Workload Migration',
      target_environment: targetEnvironment,
      deliverable_type: deliverableType,
      triage_depth: triageDepth,
      raw_manifest: hasText ? manifestText : null,
      manifest_type: manifestType,
      gemini_api_key: geminiKey || null,
      image_data_base64: imageDataBase64 || null,
      image_media_type: imageMediaType,
    });
  };

  const handleTextFileUpload = (e) => {
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

  const processImageFile = (file) => {
    setImageError('');
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setImageError(`Unsupported file type: ${file.type}. Please upload PNG, JPEG, WebP, or GIF.`);
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError(`Image is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is 10 MB.`);
      return;
    }
    setImageFileName(file.name);
    setImageMediaType(file.type);
    // Build preview URL
    const previewUrl = URL.createObjectURL(file);
    setImagePreviewUrl(previewUrl);
    // Read as base64 (strip data URI prefix)
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUri = ev.target.result;
      const base64 = dataUri.split(',')[1];
      setImageDataBase64(base64);
    };
    reader.readAsDataURL(file);
  };

  const handleImageFileInput = (e) => {
    const file = e.target.files[0];
    if (file) processImageFile(file);
    // Reset so the same file can be re-selected
    e.target.value = '';
  };

  const handleImageDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    imageDropRef.current?.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) processImageFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    imageDropRef.current?.classList.add('drag-over');
  };

  const handleDragLeave = () => {
    imageDropRef.current?.classList.remove('drag-over');
  };

  const clearImage = () => {
    if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    setImageDataBase64(null);
    setImagePreviewUrl(null);
    setImageFileName('');
    setImageMediaType('image/png');
    setImageError('');
  };

  const canSubmit = !isRunning && (manifestText.trim().length > 0 || !!imageDataBase64);

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
            Upload manifests or screenshots, select target Power environment, and let the agent scope availability and build-time dependencies.
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

          {/* Left column: tabbed manifest / image input */}
          <div>
            <Tabs selectedIndex={activeInputTab} onChange={({ selectedIndex }) => setActiveInputTab(selectedIndex)}>
              <TabList aria-label="Input method">
                <Tab renderIcon={DocumentBlank}>Text / File</Tab>
                <Tab renderIcon={Image}>Image Upload</Tab>
              </TabList>

              <TabPanels>
                {/* ── Tab 0: text manifest ── */}
                <TabPanel style={{ padding: '1rem 0 0' }}>
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
                </TabPanel>

                {/* ── Tab 1: image upload ── */}
                <TabPanel style={{ padding: '1rem 0 0' }}>
                  {imageError && (
                    <InlineNotification
                      kind="error"
                      title="Upload error:"
                      subtitle={imageError}
                      lowContrast
                      style={{ marginBottom: '0.75rem' }}
                      onCloseButtonClick={() => setImageError('')}
                    />
                  )}

                  {imagePreviewUrl ? (
                    /* Preview state */
                    <div style={{ border: '1px solid var(--cds-border-subtle-01)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '0.5rem 0.75rem',
                          background: 'var(--cds-layer-02)',
                          borderBottom: '1px solid var(--cds-border-subtle-01)',
                        }}
                      >
                        <span className="cds--label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <Image size={14} /> {imageFileName}
                        </span>
                        <Button
                          kind="ghost"
                          size="sm"
                          renderIcon={TrashCan}
                          iconDescription="Remove image"
                          hasIconOnly
                          tooltipPosition="left"
                          onClick={clearImage}
                        />
                      </div>
                      <img
                        src={imagePreviewUrl}
                        alt="Uploaded manifest"
                        style={{ width: '100%', maxHeight: '300px', objectFit: 'contain', background: 'var(--cds-layer-01)', display: 'block' }}
                      />
                      <p className="cds--helper-text-01" style={{ padding: '0.4rem 0.75rem' }}>
                        Gemini Vision will extract dependency text from this image before triage analysis.
                      </p>
                    </div>
                  ) : (
                    /* Drop zone */
                    <div
                      ref={imageDropRef}
                      onDrop={handleImageDrop}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      style={{
                        border: '2px dashed var(--cds-border-subtle-01)',
                        borderRadius: '2px',
                        minHeight: '220px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.75rem',
                        cursor: 'pointer',
                        transition: 'border-color 0.15s, background 0.15s',
                        padding: '2rem',
                      }}
                    >
                      <Image size={40} style={{ color: 'var(--cds-text-secondary)' }} />
                      <p className="cds--body-short-01" style={{ color: 'var(--cds-text-secondary)', textAlign: 'center' }}>
                        Drag &amp; drop a screenshot here, or click to browse
                      </p>
                      <p className="cds--helper-text-01" style={{ textAlign: 'center' }}>
                        PNG · JPEG · WebP · GIF &nbsp;|&nbsp; Max 10 MB
                        <br />
                        e.g. screenshot of a Dockerfile, requirements.txt, or architecture diagram
                      </p>
                      <label>
                        <Button kind="tertiary" size="sm" renderIcon={CloudUpload} as="span">
                          Choose Image
                        </Button>
                        <input
                          type="file"
                          accept={ACCEPTED_IMAGE_TYPES.join(',')}
                          style={{ display: 'none' }}
                          onChange={handleImageFileInput}
                        />
                      </label>
                    </div>
                  )}

                  {/* Optional: also allow typed context alongside the image */}
                  <div style={{ marginTop: '0.75rem' }}>
                    <TextArea
                      id="image-context-input"
                      labelText="Additional context (optional)"
                      helperText="Add any notes about what's in the image, or extra packages not visible."
                      rows={3}
                      value={manifestText}
                      onChange={(e) => setManifestText(e.target.value)}
                      placeholder="e.g. 'This is from our CI pipeline — also include libssl-dev and libffi-dev'"
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.85rem' }}
                    />
                  </div>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </div>

          {/* Right column: target parameters + submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Select
              id="target-env-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Chip size={14} /> Target Environment (ppc64le)</span>}
              value={targetEnvironment}
              onChange={(e) => setTargetEnvironment(e.target.value)}
            >
              <SelectItem value="rhel9_ocp"        text="RHEL 9 on OpenShift (ppc64le)" />
              <SelectItem value="rhel10_ocp"       text="RHEL 10 on OpenShift (ppc64le)" />
              <SelectItem value="rhel9_baremetal"  text="RHEL 9 Bare Metal / PowerVM (ppc64le)" />
              <SelectItem value="rhel10_baremetal" text="RHEL 10 Bare Metal / PowerVM (ppc64le)" />
            </Select>

            <Select
              id="deliverable-type-select"
              labelText={<span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Layers size={14} /> Deliverable Type</span>}
              value={deliverableType}
              onChange={(e) => setDeliverableType(e.target.value)}
              helperText="Match availability against the artefact type you intend to deploy."
            >
              <SelectItem value="container"    text="Container — OCI/Docker image" />
              <SelectItem value="build"        text="Build — compiled binary, RPM, or wheel" />
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
            {(imageDataBase64 || manifestText.trim()) && (
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                {imageDataBase64 && <Tag type="purple" size="sm"><Image size={12} style={{ marginRight: '3px' }} /> Image ready</Tag>}
                {manifestText.trim() && <Tag type="teal" size="sm"><DocumentBlank size={12} style={{ marginRight: '3px' }} /> Text ready</Tag>}
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
