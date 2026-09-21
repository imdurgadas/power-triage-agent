import React, { useState, useEffect } from 'react';
import {
  Header,
  HeaderName,
  HeaderGlobalBar,
  HeaderGlobalAction,
  SkipToContent,
  Tag,
  InlineNotification,
} from '@carbon/react';
import { Chip, Activity } from '@carbon/icons-react';
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
          setActivePreset(data[2]);
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
    <div className="cds--white" data-carbon-theme="g100">
      <Header aria-label="IBM Power Porting Triage Agent">
        <SkipToContent />
        <HeaderName prefix="IBM">
          Power Porting Triage Agent
        </HeaderName>
        <HeaderGlobalBar>
          <Tag
            type={backendOnline ? 'green' : 'red'}
            size="md"
            style={{ marginRight: '1rem', alignSelf: 'center' }}
          >
            <Activity size={14} style={{ marginRight: '4px' }} />
            {backendOnline ? 'Engine Online' : 'Engine Connecting...'}
          </Tag>
        </HeaderGlobalBar>
      </Header>

      <div
        style={{
          maxWidth: '1440px',
          margin: '0 auto',
          padding: '2rem 1.5rem 4rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.5rem',
        }}
      >
        <InputSection
          onRunTriage={handleRunTriage}
          isRunning={isRunning}
          presets={presets}
          activePreset={activePreset}
          onSelectPreset={setActivePreset}
        />

        <AgentLiveFeed steps={agentSteps} isRunning={isRunning} />

        {triageResult && (
          <Scorecard
            summary={triageResult.summary}
            triageResult={triageResult}
            onOpenExport={() => setShowExportModal(true)}
          />
        )}

        {triageResult && (
          <DependencyTable
            packages={triageResult.packages}
            onOpenCodeAudit={(pkg) => setSelectedAuditPkg(pkg)}
          />
        )}
      </div>

      {selectedAuditPkg && (
        <CodeAuditModal
          packageData={selectedAuditPkg}
          onClose={() => setSelectedAuditPkg(null)}
        />
      )}

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
