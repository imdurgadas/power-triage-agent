import React, { useState } from 'react';
import { X, Copy, Check, Download, FileText, Table } from 'lucide-react';

export default function ExportModal({ markdownContent, csvData, projectName, onClose }) {
  const [copied, setCopied] = useState(false);

  if (!markdownContent) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(markdownContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadMd = () => {
    const blob = new Blob([markdownContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `IBM_Power_Feasibility_${projectName.replace(/\s+/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadCsv = () => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `IBM_Power_Triage_Backlog_${projectName.replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '900px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <FileText size={20} color="#60a5fa" />
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
              Pre-Sales Executive Deliverables
            </h3>
          </div>
          <button className="btn btn-secondary" style={{ padding: '0.3rem 0.6rem' }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Formatted executive assessment brief ready for customer proposals, client technical qualification calls, or JIRA porting engineering handoffs.
          </p>

          <div style={{ display: 'flex', gap: '0.6rem', marginBottom: '1rem' }}>
            <button className="btn btn-primary" style={{ fontSize: '0.82rem', padding: '0.5rem 0.9rem' }} onClick={handleDownloadMd}>
              <Download size={14} /> Download Markdown Memo
            </button>
            <button className="btn btn-secondary" style={{ fontSize: '0.82rem', padding: '0.5rem 0.9rem' }} onClick={handleDownloadCsv}>
              <Table size={14} /> Export CSV Backlog
            </button>
            <button className="btn btn-secondary" style={{ fontSize: '0.82rem', padding: '0.5rem 0.9rem', marginLeft: 'auto' }} onClick={handleCopy}>
              {copied ? <Check size={14} color="#4ade80" /> : <Copy size={14} />}
              {copied ? 'Copied to Clipboard!' : 'Copy Text'}
            </button>
          </div>

          <pre className="code-preview-box" style={{ maxHeight: '420px', whiteSpace: 'pre-wrap' }}>
            {markdownContent}
          </pre>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
