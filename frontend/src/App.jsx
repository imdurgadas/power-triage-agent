import React, { useState, useEffect } from 'react';
import { Cpu, Zap, ExternalLink, RefreshCw } from 'lucide-react';
import InputSection from './components/InputSection';
import AgentLiveFeed from './components/AgentLiveFeed';
import Scorecard from './components/Scorecard';
import DependencyTable from './components/DependencyTable';
import CodeAuditModal from './components/CodeAuditModal';
import ExportModal from './components/ExportModal';

export default function App() {
  const [presets, setPresets] = useState([]);
  const [activePreset, setActivePreset] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [agentSteps, setAgentSteps] = useState([]);
  const [triageResult, setTriageResult] = useState(null);
  const [selectedAuditPkg, setSelectedAuditPkg] = useState(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [backendOnline, setBackendOnline] = useState(true);

  // Load sample workloads on mount
  useEffect(() => {
    fetch('/api/sample-workloads')
      .then(res => res.json())
      .then(data => {
        setPresets(data);
        if (data.length > 0) {
          setActivePreset(data[2]); // Default to "High-Throughput Storage Engine (Dependency Iceberg)"
        }
      })
      .catch(err => {
        console.warn('Backend not yet reachable on /api/sample-workloads:', err);
        setBackendOnline(false);
      });
  }, []);

  const handleRunTriage = async (payload) => {
    setIsRunning(true);
    setAgentSteps([]);
    setTriageResult(null);

    try {
      // Use SSE streaming endpoint for live agent thoughts
      const response = await fetch('/api/triage/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const rawJson = line.replace('data: ', '').trim();
            if (!rawJson) continue;
            try {
              const event = JSON.parse(rawJson);
              if (event.type === 'step') {
                setAgentSteps(prev => [...prev, event.step]);
              } else if (event.type === 'result') {
                setTriageResult(event.data);
              }
            } catch (jsonErr) {
              console.error('Error parsing SSE event:', jsonErr);
            }
          }
        }
      }
    } catch (err) {
      console.warn('Streaming error, falling back to direct POST:', err);
      // Fallback to direct synchronous POST
      try {
        const fallbackRes = await fetch('/api/triage', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await fallbackRes.json();
        setTriageResult(data);
      } catch (postErr) {
        alert('Could not communicate with backend: ' + postErr.message);
      }
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-container">
          <div className="brand-section">
            <div className="brand-logo-icon">
              <Cpu size={22} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span className="brand-title">IBM Power Porting Triage Agent</span>
                <span className="brand-badge">ppc64le AI Pre-Sales</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.1rem' }}>
                Automated Multi-Source Availability & Recursive Transitive Build Effort Sizing
              </div>
            </div>
          </div>

          <div className="header-actions">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem', color: backendOnline ? '#4ade80' : '#f87171' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: backendOnline ? '#4ade80' : '#f87171', display: 'inline-block' }}></span>
              {backendOnline ? 'Engine Online' : 'Engine Connecting...'}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Layout */}
      <main className="main-layout">
        {/* Ingestion & Configuration Section */}
        <InputSection 
          onRunTriage={handleRunTriage}
          isRunning={isRunning}
          presets={presets}
          activePreset={activePreset}
          onSelectPreset={setActivePreset}
        />

        {/* Live Agent Execution Stream */}
        <AgentLiveFeed 
          steps={agentSteps} 
          isRunning={isRunning} 
        />

        {/* Executive Scorecard */}
        {triageResult && (
          <Scorecard 
            summary={triageResult.summary} 
            onOpenExport={() => setShowExportModal(true)} 
          />
        )}

        {/* Transitive Dependency Matrix */}
        {triageResult && (
          <DependencyTable 
            packages={triageResult.packages} 
            onOpenCodeAudit={(pkg) => setSelectedAuditPkg(pkg)} 
          />
        )}
      </main>

      {/* Code Sensitivity Drawer / Modal */}
      {selectedAuditPkg && (
        <CodeAuditModal 
          packageData={selectedAuditPkg} 
          onClose={() => setSelectedAuditPkg(null)} 
        />
      )}

      {/* Executive Deliverables Modal */}
      {showExportModal && triageResult && (
        <ExportModal 
          triageData={triageResult}
          markdownContent={triageResult.executive_brief_markdown} 
          csvData={triageResult.export_csv_data}
          projectName={triageResult.project_name}
          onClose={() => setShowExportModal(false)} 
        />
      )}
    </div>
  );
}
