import React, { useState } from 'react';
import { Modal, Button, InlineLoading } from '@carbon/react';
import { Download, Copy, Checkmark, Table, Document } from '@carbon/icons-react';

export default function ExportModal({ triageData, markdownContent, csvData, projectName, onClose }) {
  const [copied, setCopied] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  if (!markdownContent) return null;

  const primaryPkg = triageData?.primary_package_name;
  const gitUrl = triageData?.git_repo_url;
  const docUrl = triageData?.doc_url;
  const targetLabel = primaryPkg || projectName || 'Report';

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
    a.download = `IBM_Power_Feasibility_${targetLabel.replace(/\s+/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadCsv = () => {
    if (!csvData) return;
    const blob = new Blob([csvData], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `IBM_Power_Triage_Backlog_${targetLabel.replace(/\s+/g, '_')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPdf = async () => {
    if (!triageData) return;
    setIsDownloadingPdf(true);
    try {
      const res = await fetch('/api/export/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(triageData),
      });
      if (!res.ok) throw new Error(`PDF generation failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `IBM_Power_Feasibility_${targetLabel.replace(/\s+/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('PDF generation failed: ' + err.message);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  return (
    <Modal
      open
      size="lg"
      modalHeading="Pre-Sales Executive Deliverables"
      primaryButtonText="Close"
      onRequestClose={onClose}
      onRequestSubmit={onClose}
      passiveModal
    >
      <p className="cds--body-short-01" style={{ marginBottom: '1rem', color: 'var(--cds-text-secondary)' }}>
        Client-ready executive brief, Markdown report, and JIRA-ready CSV backlog.
      </p>

      {/* Workload provenance banner */}
      {(primaryPkg || gitUrl || docUrl) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center', padding: '0.5rem 0.85rem', background: 'var(--cds-layer-02)', border: '1px solid var(--cds-border-subtle-01)', borderRadius: '2px', marginBottom: '1rem', fontSize: '0.82rem' }}>
          <strong style={{ color: 'var(--cds-text-primary)' }}>Qualified Workload:</strong>
          {primaryPkg && <span style={{ color: 'var(--cds-interactive)' }}>📦 {primaryPkg}</span>}
          {gitUrl && <span style={{ color: 'var(--cds-text-secondary)' }}>GitHub: <a href={gitUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--cds-link-primary)' }}>{gitUrl.replace('https://github.com/', '')}</a></span>}
          {docUrl && <span style={{ color: 'var(--cds-text-secondary)' }}>Docs: <a href={docUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--cds-link-primary)' }}>{docUrl.replace(/^https?:\/\//, '')}</a></span>}
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        <Button kind="primary" size="md" renderIcon={isDownloadingPdf ? undefined : Document} disabled={isDownloadingPdf} onClick={handleDownloadPdf} id="download-pdf-btn">
          {isDownloadingPdf ? <><InlineLoading status="active" style={{ display: 'inline-flex' }} /> Generating PDF...</> : 'Download Executive PDF'}
        </Button>
        <Button kind="secondary" size="md" renderIcon={Download} onClick={handleDownloadMd}>
          Download Markdown
        </Button>
        <Button kind="secondary" size="md" renderIcon={Table} onClick={handleDownloadCsv}>
          Export CSV Backlog
        </Button>
        <Button kind="ghost" size="md" renderIcon={copied ? Checkmark : Copy} onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy Text'}
        </Button>
      </div>

      <pre
        style={{
          background: 'var(--cds-layer-02)',
          border: '1px solid var(--cds-border-subtle-01)',
          borderRadius: '2px',
          padding: '1rem',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '0.8rem',
          overflowX: 'auto',
          maxHeight: '420px',
          whiteSpace: 'pre-wrap',
          lineHeight: 1.6,
        }}
      >
        {markdownContent}
      </pre>
    </Modal>
  );
}
