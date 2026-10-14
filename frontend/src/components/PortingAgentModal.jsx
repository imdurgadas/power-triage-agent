import React, { useState, useEffect, useRef } from 'react';
import {
  Modal,
  Button,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  TextInput,
  PasswordInput,
  InlineNotification,
  Tag,
  ProgressBar,
  CodeSnippet,
  Select,
  SelectItem,
  Checkbox,
  TextArea,
} from '@carbon/react';
import {
  Play,
  Terminal,
  BareMetalServer,
  Code,
  Copy,
  Launch,
  CheckmarkFilled,
  WarningAltFilled,
  Tools,
  Layers,
  DataPlayer,
  Chip,
} from '@carbon/icons-react';

export default function PortingAgentModal({ packageData, onClose }) {
  const [activeTab, setActiveTab] = useState(0);

  // Configuration state - production real SSH connection
  const [vmHost, setVmHost] = useState('');
  const [vmPort, setVmPort] = useState(22);
  const [vmUser, setVmUser] = useState('');
  const [vmKey, setVmKey] = useState('');
  const [workspaceDir, setWorkspaceDir] = useState('/var/tmp/power_porting');
  const [targetOsImage, setTargetOsImage] = useState('registry.access.redhat.com/ubi9/ubi:latest');
  const [customOsImage, setCustomOsImage] = useState('');
  const [containerEngine, setContainerEngine] = useState('auto');
  const [deliverableTarget, setDeliverableTarget] = useState('wheel');
  const [llmEngine, setLlmEngine] = useState('ibm_bob');
  const [githubToken, setGithubToken] = useState('');
  const [upstreamRepo, setUpstreamRepo] = useState(
    packageData?.git_repo_url?.replace('https://github.com/', '').replace(/\.git$/, '') || ''
  );

  // Child / Sub-dependencies state
  const [includeChildDeps, setIncludeChildDeps] = useState(true);
  const [childDepsList, setChildDepsList] = useState([]);

  // Testing connection state
  const [probingVM, setProbingVM] = useState(false);
  const [probeResult, setProbeResult] = useState(null);
  const [probeError, setProbeError] = useState(null);
  const [formError, setFormError] = useState(null);

  // Job execution state
  const [isRunning, setIsRunning] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobState, setJobState] = useState(null);
  const [copiedEvidence, setCopiedEvidence] = useState(false);
  const terminalRef = useRef(null);

  // Derive child dependencies dynamically from packageData build_dependencies
  useEffect(() => {
    if (packageData) {
      let deps = [];
      if (packageData.build_dependencies && packageData.build_dependencies.length > 0) {
        deps = packageData.build_dependencies.map(d => ({
          name: d.name,
          version: d.version || 'latest',
          purpose: d.purpose || 'BuildRequires',
          status: d.status || 'unported_build_required',
          porting_effort_pd: d.porting_effort_pd || 1.0,
          enabled: true,
        }));
      }
      setChildDepsList(deps);
    }
  }, [packageData]);

  // Auto-scroll terminal to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [jobState]);

  // Derive default deliverable target
  useEffect(() => {
    if (packageData?.ecosystem === 'container') {
      setDeliverableTarget('container');
    } else if (packageData?.ecosystem === 'python') {
      setDeliverableTarget('wheel');
    } else {
      setDeliverableTarget('source');
    }
  }, [packageData]);

  // Test VM Connection
  const handleTestConnection = async () => {
    if (!vmHost.trim()) {
      setProbeError('Please enter the Target Power VM Host or IP Address.');
      setFormError('Please enter the Target Power VM Host or IP Address.');
      return;
    }
    if (!vmUser.trim()) {
      setProbeError('Please enter the SSH Username.');
      setFormError('Please enter the SSH Username.');
      return;
    }
    setFormError(null);
    setProbingVM(true);
    setProbeResult(null);
    setProbeError(null);
    const effectiveOsImage = targetOsImage === 'custom' ? customOsImage.trim() : targetOsImage;
    try {
      const res = await fetch('/api/porting/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: vmHost.trim(),
          port: Number(vmPort) || 22,
          username: vmUser.trim(),
          private_key: vmKey.trim() || null,
          workspace_dir: workspaceDir.trim() || '/var/tmp/power_porting',
          target_os_image: effectiveOsImage || 'registry.access.redhat.com/ubi9/ubi:latest',
          container_engine: containerEngine,
          use_mock: false,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Connection failed');
      }
      setProbeResult(data.system_info);
    } catch (err) {
      setProbeError(err.message);
    } finally {
      setProbingVM(false);
    }
  };

  // Launch Autonomous Porting Agent
  const handleStartPorting = async () => {
    if (!vmHost.trim()) {
      setFormError('Target Power VM Host / IP Address is required before launching porting.');
      setActiveTab(0);
      return;
    }
    if (!vmUser.trim()) {
      setFormError('SSH Username is required before launching porting.');
      setActiveTab(0);
      return;
    }

    const effectiveOsImage = targetOsImage === 'custom' ? customOsImage.trim() : targetOsImage;
    if (targetOsImage === 'custom' && !customOsImage.trim()) {
      setFormError('Please specify the custom container image tag.');
      setActiveTab(0);
      return;
    }

    setFormError(null);
    setProbeError(null);
    setIsRunning(true);
    setActiveTab(1); // Switch to execution tab

    try {
      const activeChildDeps = includeChildDeps
        ? childDepsList.filter(d => d.enabled).map(d => ({ name: d.name, version: d.version, purpose: d.purpose }))
        : [];

      const payload = {
        package_name: packageData?.package_name || 'workload',
        version: packageData?.requested_version || 'latest',
        ecosystem: packageData?.ecosystem || 'python',
        deliverable_target: deliverableTarget,
        git_repo_url: packageData?.git_repo_url || null,
        upstream_repo: upstreamRepo.trim() || null,
        github_token: githubToken.trim() || null,
        llm_provider: llmEngine,
        include_child_dependencies: includeChildDeps,
        child_dependencies: activeChildDeps,
        vm_config: {
          host: vmHost.trim(),
          port: Number(vmPort) || 22,
          username: vmUser.trim(),
          private_key: vmKey.trim() || null,
          workspace_dir: workspaceDir.trim() || '/var/tmp/power_porting',
          target_os_image: effectiveOsImage || 'registry.access.redhat.com/ubi9/ubi:latest',
          container_engine: containerEngine,
          use_mock: false,
        },
        triage_finding: packageData,
      };

      const startRes = await fetch('/api/porting/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!startRes.ok) {
        const errData = await startRes.json();
        throw new Error(errData.detail || 'Failed to start porting job');
      }

      const jobData = await startRes.json();
      setJobId(jobData.job_id);
      setJobState(jobData);

      // Start SSE EventSource stream
      const eventSource = new EventSource(`/api/porting/stream/${jobData.job_id}`);

      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setJobState(parsed);
          if (parsed.status === 'completed' || parsed.status === 'failed') {
            setIsRunning(false);
            eventSource.close();
          }
        } catch (e) {
          console.error('Error parsing SSE porting event:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        pollJobStatus(jobData.job_id);
      };
    } catch (err) {
      setIsRunning(false);
      setFormError('Error launching porting agent: ' + err.message);
      setActiveTab(0);
    }
  };

  const pollJobStatus = async (id) => {
    try {
      const res = await fetch(`/api/porting/status/${id}`);
      if (res.ok) {
        const data = await res.json();
        setJobState(data);
        if (data.status === 'running') {
          setTimeout(() => pollJobStatus(id), 2000);
        } else {
          setIsRunning(false);
        }
      }
    } catch (e) {
      setIsRunning(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedEvidence(true);
    setTimeout(() => setCopiedEvidence(false), 2000);
  };

  const toggleChildDep = (index) => {
    setChildDepsList(prev => prev.map((item, i) => i === index ? { ...item, enabled: !item.enabled } : item));
  };

  const allLogs = jobState?.steps?.flatMap(s => s.logs || []) || [];
  const tokenUsage = jobState?.token_usage;

  return (
    <Modal
      open
      onRequestClose={onClose}
      modalHeading={
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <BareMetalServer size={22} style={{ color: '#0f62fe' }} />
          <span>Autonomous Power Porting Agent (ppc64le)</span>
          <Tag type="blue" size="sm">{packageData?.package_name} {packageData?.requested_version || ''}</Tag>
          {childDepsList.length > 0 && (
            <Tag type="purple" size="sm">+{childDepsList.length} Child Libraries</Tag>
          )}
        </div>
      }
      primaryButtonText={isRunning ? 'Porting in Progress...' : 'Launch Power Porting Agent'}
      primaryButtonDisabled={isRunning}
      onRequestSubmit={handleStartPorting}
      onPrimaryClick={handleStartPorting}
      secondaryButtonText="Close"
      onSecondarySubmit={onClose}
      size="lg"
      className="porting-agent-modal"
    >
      <div style={{ marginTop: '0.5rem' }}>
        <p style={{ color: '#c6c6c6', fontSize: '0.86rem', marginBottom: '1.25rem', lineHeight: 1.45 }}>
          Orchestrates end-to-end autonomous porting of <strong>{packageData?.package_name}</strong> and its sub-libraries
          on IBM Power (ppc64le): connects to target Power VM, builds transitive dependencies,
          diagnoses compiler errors, applies non-breaking guards (<code>#if defined(__powerpc__)</code>), runs unit tests,
          and calculates fine-grained AI token and cost telemetry.
        </p>

        {formError && (
          <InlineNotification
            kind="error"
            title="Target Power VM Configuration Required"
            subtitle={formError}
            onClose={() => setFormError(null)}
            lowContrast
            style={{ marginBottom: '1.25rem' }}
          />
        )}

        {/* Live Token & Cost Telemetry Bar if available */}
        {tokenUsage && (
          <div
            style={{
              background: '#161616',
              border: '1px solid #393939',
              borderLeft: '4px solid #8a3ffc',
              borderRadius: '2px',
              padding: '0.85rem 1rem',
              marginBottom: '1.25rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <DataPlayer size={20} style={{ color: '#a56eff' }} />
              <div>
                <span style={{ fontSize: '0.75rem', color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  AI Porting Telemetry &amp; Cost
                </span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#f4f4f4' }}>
                  ${Number(tokenUsage.cost_usd || 0).toFixed(4)} USD
                  <span style={{ fontSize: '0.8rem', fontWeight: 400, color: '#a8a8a8', marginLeft: '0.5rem' }}>
                    ({Number(tokenUsage.total_tokens || 0).toLocaleString()} tokens • {tokenUsage.calls_count || 1} turns)
                  </span>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span style={{ fontSize: '0.74rem', color: '#8d8d8d' }}>
                Prompt: {Number(tokenUsage.input_tokens || 0).toLocaleString()} tok | Completion: {Number(tokenUsage.output_tokens || 0).toLocaleString()} tok
              </span>
              <Tag type={tokenUsage.llm_provider === 'ibm_bob' ? 'blue' : 'purple'} size="sm">
                {tokenUsage.llm_provider === 'ibm_bob' ? 'IBM Bob CLI' : 'Google Gemini'}
              </Tag>
            </div>
          </div>
        )}

        <Tabs selectedIndex={activeTab} onChange={({ selectedIndex }) => setActiveTab(selectedIndex)}>
          <TabList aria-label="Porting Agent Tabs" style={{ marginBottom: '1.25rem' }}>
            <Tab renderIcon={Tools}>Target VM &amp; Config</Tab>
            <Tab renderIcon={Terminal}>
              Live Execution &amp; Logs
              {isRunning && <span style={{ marginLeft: '6px', color: '#0f62fe' }}>●</span>}
            </Tab>
            <Tab renderIcon={Code}>Generated Patches</Tab>
            <Tab renderIcon={Launch}>Verification Evidence &amp; PR</Tab>
          </TabList>

          <TabPanels>
            {/* TAB 1: Config */}
            <TabPanel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Target Environment Box */}
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <BareMetalServer size={18} style={{ color: '#78a9ff' }} />
                      Target Power Architecture VM Connection (SSH)
                    </span>
                    <Tag type="blue" size="sm">ppc64le Environment</Tag>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) 100px minmax(0, 1fr)', gap: '1rem' }}>
                    <TextInput
                      id="vm-host-input"
                      labelText="Power Host / IP Address"
                      value={vmHost}
                      onChange={(e) => {
                        setVmHost(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="e.g. 10.120.45.10 or power-lpar01.corp.internal"
                      helperText="Hostname or IP address of the target IBM Power server."
                    />
                    <TextInput
                      id="vm-port-input"
                      labelText="SSH Port"
                      value={vmPort}
                      onChange={(e) => setVmPort(e.target.value)}
                      placeholder="22"
                    />
                    <TextInput
                      id="vm-user-input"
                      labelText="SSH Username"
                      value={vmUser}
                      onChange={(e) => {
                        setVmUser(e.target.value);
                        if (formError) setFormError(null);
                      }}
                      placeholder="e.g. root or ibmadmin"
                      helperText="User account with sudo/build permissions."
                    />
                  </div>

                  <div style={{ marginTop: '0.85rem' }}>
                    <TextInput
                      id="vm-workspace-input"
                      labelText="Remote Workspace Directory"
                      value={workspaceDir}
                      onChange={(e) => setWorkspaceDir(e.target.value)}
                      placeholder="/var/tmp/power_porting"
                      helperText="Remote filesystem directory for building source, installing sub-libraries, and running tests."
                    />
                  </div>

                  <div style={{ marginTop: '0.85rem' }}>
                    <TextArea
                      id="vm-key-input"
                      labelText="SSH Private Key (PEM / OpenSSH format)"
                      value={vmKey}
                      onChange={(e) => setVmKey(e.target.value)}
                      rows={3}
                      placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----"
                      helperText="Private key for SSH authentication on the target Power machine (optional if host ssh-agent is configured)."
                      style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem' }}
                    />
                  </div>

                  <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                    <Button
                      size="sm"
                      kind="tertiary"
                      renderIcon={BareMetalServer}
                      onClick={handleTestConnection}
                      disabled={probingVM}
                    >
                      {probingVM ? 'Probing Target Architecture...' : 'Test SSH Connection & Hardware Diagnostics'}
                    </Button>
                  </div>

                  {probeResult && (
                    <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#141414', border: '1px solid #24a148', borderRadius: '2px', fontSize: '0.8rem' }}>
                      <div style={{ color: '#42be65', fontWeight: 600, marginBottom: '0.25rem' }}>
                        ✓ Connection Verified on {probeResult.architecture} ({probeResult.cpu_model || 'POWER10'})
                      </div>
                      <div style={{ color: '#a8a8a8' }}>
                        OS: {probeResult.os} • Page Size: {probeResult.page_size} • VSX Vector: {probeResult.vsx_support ? 'Enabled' : 'Disabled'} • Toolchain: {probeResult.compiler}
                      </div>
                    </div>
                  )}

                  {probeError && (
                    <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#141414', border: '1px solid #da1e28', borderRadius: '2px', fontSize: '0.8rem', color: '#ff8389' }}>
                      ✗ Connection Error: {probeError}
                    </div>
                  )}
                </div>

                {/* Target OS & Build Container Box */}
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Chip size={18} style={{ color: '#0f62fe' }} />
                      Target Operating System &amp; Isolated Build Container
                    </span>
                    <Tag type="cyan" size="sm">OCI Container on ppc64le</Tag>
                  </div>

                  <p style={{ fontSize: '0.8rem', color: '#a8a8a8', marginBottom: '1rem', lineHeight: 1.4 }}>
                    To build from source and run unit tests cleanly without polluting the host VM, the agent automatically spawns an isolated container with the selected operating system directly on the target Power VM.
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
                    <Select
                      id="target-os-select"
                      labelText="Target Operating System Base Image"
                      value={targetOsImage}
                      onChange={(e) => setTargetOsImage(e.target.value)}
                      helperText="Base image pulled and spawned on the Power VM for compiling &amp; testing."
                    >
                      <SelectItem
                        value="registry.access.redhat.com/ubi9/ubi:latest"
                        text="Red Hat UBI 9 (registry.access.redhat.com/ubi9/ubi:latest) — Recommended"
                      />
                      <SelectItem
                        value="registry.access.redhat.com/ubi8/ubi:latest"
                        text="Red Hat UBI 8 (registry.access.redhat.com/ubi8/ubi:latest)"
                      />
                      <SelectItem
                        value="docker.io/library/ubuntu:24.04"
                        text="Ubuntu 24.04 LTS (Noble Numbat ppc64le)"
                      />
                      <SelectItem
                        value="docker.io/library/ubuntu:22.04"
                        text="Ubuntu 22.04 LTS (Jammy Jellyfish ppc64le)"
                      />
                      <SelectItem
                        value="docker.io/library/fedora:40"
                        text="Fedora 40 (ppc64le)"
                      />
                      <SelectItem
                        value="docker.io/library/debian:12"
                        text="Debian 12 Bookworm (ppc64le)"
                      />
                      <SelectItem
                        value="custom"
                        text="Custom Container Image..."
                      />
                    </Select>

                    <Select
                      id="container-engine-select"
                      labelText="Container Runtime Engine on VM"
                      value={containerEngine}
                      onChange={(e) => setContainerEngine(e.target.value)}
                      helperText="Runtime used to execute the build container."
                    >
                      <SelectItem value="auto" text="Auto-Detect (Prefers Podman, falls back to Docker)" />
                      <SelectItem value="podman" text="Podman (Rootless / Enterprise OCI)" />
                      <SelectItem value="docker" text="Docker Engine" />
                    </Select>
                  </div>

                  {targetOsImage === 'custom' && (
                    <div style={{ marginTop: '0.85rem' }}>
                      <TextInput
                        id="custom-os-input"
                        labelText="Custom ppc64le Container Image Tag"
                        value={customOsImage}
                        onChange={(e) => setCustomOsImage(e.target.value)}
                        placeholder="e.g. quay.io/myorg/custom-power-builder:latest"
                        helperText="Image must support the linux/ppc64le architecture."
                      />
                    </div>
                  )}
                </div>

                {/* Sub / Child Libraries Hierarchy Box */}
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div>
                      <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Layers size={18} style={{ color: '#0f62fe' }} />
                        Scoped Sub-Libraries &amp; Child Dependencies
                      </span>
                      <span style={{ fontSize: '0.78rem', color: '#a8a8a8' }}>
                        {childDepsList.length} build-time libraries detected in the dependency iceberg
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Checkbox
                        id="include-child-deps-toggle"
                        labelText="Port Full Dependency Tree (Build all sub-libraries on ppc64le)"
                        checked={includeChildDeps}
                        onChange={(_, { checked }) => setIncludeChildDeps(checked)}
                      />
                    </div>
                  </div>

                  {includeChildDeps && childDepsList.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
                      {childDepsList.map((dep, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '0.5rem 0.75rem',
                            background: '#141414',
                            border: '1px solid #282828',
                            borderRadius: '2px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                            <Checkbox
                              id={`child-dep-${idx}`}
                              labelText=""
                              checked={dep.enabled}
                              onChange={() => toggleChildDep(idx)}
                              hideLabel
                            />
                            <div>
                              <code style={{ fontSize: '0.85rem', color: '#78a9ff', fontWeight: 600 }}>{dep.name}</code>
                              <span style={{ fontSize: '0.78rem', color: '#8d8d8d', marginLeft: '0.4rem' }}>({dep.version})</span>
                            </div>
                          </div>
                          <span style={{ fontSize: '0.75rem', color: '#a8a8a8' }}>
                            {dep.purpose}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.8rem', color: '#8d8d8d', fontStyle: 'italic', marginTop: '0.25rem' }}>
                      {childDepsList.length === 0 ? 'No external build dependencies identified.' : 'Sub-dependency porting disabled. Primary package will be compiled directly.'}
                    </div>
                  )}
                </div>

                {/* Workflow Configuration */}
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'block', marginBottom: '0.85rem' }}>
                    Porting Workflow &amp; Upstream PR Settings
                  </span>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                    <Select
                      id="deliverable-target-select"
                      labelText="Deliverable Target"
                      value={deliverableTarget}
                      onChange={(e) => setDeliverableTarget(e.target.value)}
                    >
                      <SelectItem value="wheel" text="Python Wheel (.whl) for ppc64le" />
                      <SelectItem value="container" text="Multi-Arch Container Image (podman/docker)" />
                      <SelectItem value="source" text="Native Source Build &amp; Binary" />
                    </Select>

                    <Select
                      id="llm-engine-select"
                      labelText="AI Remediation Engine"
                      value={llmEngine}
                      onChange={(e) => setLlmEngine(e.target.value)}
                    >
                      <SelectItem value="ibm_bob" text="IBM Bob CLI (Bob Shell) with Cost Telemetry" />
                      <SelectItem value="gemini" text="Google Gemini 2.5 Flash" />
                    </Select>

                    <TextInput
                      id="upstream-repo-input"
                      labelText="Upstream GitHub Repository"
                      value={upstreamRepo}
                      onChange={(e) => setUpstreamRepo(e.target.value)}
                      placeholder="owner/repo"
                    />

                    <PasswordInput
                      id="github-token-input"
                      labelText="GitHub Personal Access Token (Optional for automatic PR creation)"
                      value={githubToken}
                      onChange={(e) => setGithubToken(e.target.value)}
                      placeholder="ghp_..."
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.25rem' }}>
                  <Button
                    size="md"
                    kind="primary"
                    renderIcon={Play}
                    onClick={handleStartPorting}
                    disabled={isRunning}
                    id="intab-launch-porting-btn"
                  >
                    {isRunning ? 'Porting in Progress...' : 'Launch Power Porting Agent'}
                  </Button>
                </div>
              </div>
            </TabPanel>

            {/* TAB 2: Execution & Stepper */}
            <TabPanel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Stepper overview */}
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4' }}>
                      Lifecycle Porting Progress: {packageData?.package_name}
                    </span>
                    {jobState && (
                      <Tag
                        type={jobState.status === 'completed' ? 'green' : jobState.status === 'failed' ? 'red' : 'blue'}
                        size="md"
                      >
                        {jobState.status.toUpperCase()}
                      </Tag>
                    )}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {(jobState?.steps || [
                      { step_number: 1, title: 'Power VM Diagnostics & Provisioning', status: 'pending' },
                      { step_number: 2, title: 'Target OS Container Creation & Workspace Setup', status: 'pending' },
                      { step_number: 3, title: 'Baseline Compilation & Failure Diagnostic', status: 'pending' },
                      { step_number: 4, title: 'Architecture Remediation & Code Patching', status: 'pending' },
                      { step_number: 5, title: 'Recompilation & Artifact Packaging', status: 'pending' },
                      { step_number: 6, title: 'Unit Test Suite Execution & Fixes', status: 'pending' },
                      { step_number: 7, title: 'Upstream Pull Request & Verification Evidence', status: 'pending' },
                    ]).map((step, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.6rem 0.85rem',
                          background: step.status === 'running' ? '#22272e' : '#141414',
                          border: `1px solid ${step.status === 'running' ? '#0f62fe' : '#262626'}`,
                          borderRadius: '2px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          {step.status === 'completed' && <CheckmarkFilled size={16} style={{ color: '#42be65' }} />}
                          {step.status === 'running' && <span style={{ color: '#78a9ff', fontWeight: 700 }}>▶</span>}
                          {step.status === 'failed' && <WarningAltFilled size={16} style={{ color: '#fa4d56' }} />}
                          {step.status === 'pending' && <span style={{ color: '#6e6e6e' }}>○</span>}
                          <span style={{ fontSize: '0.85rem', fontWeight: step.status === 'running' ? 700 : 500, color: step.status === 'pending' ? '#8d8d8d' : '#f4f4f4' }}>
                            {step.step_number}. {step.title}
                          </span>
                        </div>
                        {step.detail && (
                          <span style={{ fontSize: '0.78rem', color: '#a8a8a8' }}>
                            {step.detail}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Active Build Container Status Banner */}
                {jobState?.container_info?.os_name && (
                  <div style={{ background: '#161616', border: '1px solid #333333', borderLeft: '3px solid #0043ce', borderRadius: '2px', padding: '0.65rem 0.9rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', fontSize: '0.78rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <Chip size={16} style={{ color: '#4589ff' }} />
                      <span style={{ color: '#f4f4f4', fontWeight: 600 }}>Active Build Container:</span>
                      <code style={{ color: '#78a9ff', fontSize: '0.8rem' }}>{jobState.container_info.container_name || jobState.container_info.container_id}</code>
                      <span style={{ color: '#a8a8a8' }}>({jobState.container_info.os_name})</span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      <Tag type="cyan" size="sm">{jobState.container_info.engine || 'podman'}</Tag>
                      <Tag type="outline" size="sm">{jobState.container_info.package_manager || 'dnf'}</Tag>
                    </div>
                  </div>
                )}

                {/* Live Console Output */}
                <div style={{ background: '#0c0c0c', border: '1px solid #333333', borderRadius: '2px', padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#a8a8a8', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Terminal size={14} /> Live Power Target Console
                    </span>
                    <span style={{ fontSize: '0.72rem', color: '#6e6e6e' }}>
                      {allLogs.length} events logged
                    </span>
                  </div>

                  <div
                    ref={terminalRef}
                    style={{
                      fontFamily: "'IBM Plex Mono', monospace",
                      fontSize: '0.78rem',
                      lineHeight: 1.5,
                      color: '#38bdf8',
                      maxHeight: '280px',
                      overflowY: 'auto',
                      background: '#050505',
                      padding: '0.75rem',
                      borderRadius: '2px',
                      border: '1px solid #1a1a1a',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {allLogs.length === 0 ? (
                      <span style={{ color: '#6e6e6e' }}>Waiting to launch porting agent... Click 'Launch Power Porting Agent' to begin.</span>
                    ) : (
                      allLogs.map((log, i) => (
                        <div key={i} style={{ color: log.includes('error') || log.includes('FATAL') ? '#f87171' : log.includes('✓') || log.includes('PASSED') ? '#4ade80' : '#e2e8f0' }}>
                          {log}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </TabPanel>

            {/* TAB 3: Code Patches */}
            <TabPanel>
              <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Code size={18} style={{ color: '#78a9ff' }} />
                    Architecture Conditional Patch (Unified Diff)
                  </span>
                  <Tag type="blue" size="sm">Non-Breaking Architecture Guards</Tag>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#c6c6c6', marginBottom: '0.75rem' }}>
                  Notice that all Power-specific vector instructions and dynamic 64KB page size calls are strictly isolated within <code>#if defined(__powerpc__) || defined(__PPC64__)</code>, preserving <code>#elif defined(__x86_64__)</code> and fallback paths without regressions.
                </p>

                <div style={{ maxHeight: '350px', overflowY: 'auto' }}>
                  <CodeSnippet type="multi" feedback="Copied to clipboard">
                    {jobState?.diff || '// No patch generated yet. Launch the porting agent to inspect live code diff.'}
                  </CodeSnippet>
                </div>
              </div>
            </TabPanel>

            {/* TAB 4: Evidence & PR */}
            <TabPanel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ background: '#1c1c1c', border: '1px solid #333333', padding: '1.25rem', borderRadius: '2px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#f4f4f4', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Launch size={18} style={{ color: '#78a9ff' }} />
                      Upstream Pull Request &amp; Verification Evidence
                    </span>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {jobState?.pr_url && (
                        <Button
                          size="sm"
                          kind="primary"
                          renderIcon={Launch}
                          href={jobState.pr_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          View Upstream PR
                        </Button>
                      )}
                      <Button
                        size="sm"
                        kind="tertiary"
                        renderIcon={Copy}
                        onClick={() => copyToClipboard(jobState?.evidence_report_markdown || '')}
                        disabled={!jobState?.evidence_report_markdown}
                      >
                        {copiedEvidence ? 'Copied!' : 'Copy Evidence Markdown'}
                      </Button>
                    </div>
                  </div>

                  {jobState?.pr_url && (
                    <InlineNotification
                      kind="success"
                      title="Pull Request Ready"
                      subtitle={`Autonomous agent prepared branch 'port/ppc64le-support' and PR: ${jobState.pr_url}`}
                      lowContrast
                      style={{ marginBottom: '1rem' }}
                    />
                  )}

                  <div style={{ maxHeight: '350px', overflowY: 'auto', background: '#141414', padding: '1rem', border: '1px solid #282828', borderRadius: '2px' }}>
                    <pre style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: '0.78rem', color: '#d1d5db', whiteSpace: 'pre-wrap' }}>
                      {jobState?.evidence_report_markdown || 'Evidence report will appear here once the verification run finishes.'}
                    </pre>
                  </div>
                </div>
              </div>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </div>
    </Modal>
  );
}
