import React, { useState } from 'react';
import { X, Copy, Check, Download, FileText, Table, FileSpreadsheet, Printer } from 'lucide-react';

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

  const handleDownloadPdf = async () => {
    setIsDownloadingPdf(true);
    try {
      const response = await fetch('/api/export/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(triageData || {
          project_name: projectName,
          primary_package_name: primaryPkg,
          git_repo_url: gitUrl,
          doc_url: docUrl,
          executive_brief_markdown: markdownContent
        }),
      });

      if (!response.ok) {
        throw new Error(`PDF generation failed: ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `IBM_Power_Feasibility_${targetLabel.replace(/\s+/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Could not generate PDF: " + err.message);
    } finally {
      setIsDownloadingPdf(false);
    }
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '920px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <FileText size={22} color="#10b981" />
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>
                Executive Porting Feasibility Deliverables
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                Client-ready PDF memo, technical markdown report, and JIRA-ready CSV backlog
              </p>
            </div>
          </div>
          <button className="btn btn-secondary" style={{ padding: '0.35rem 0.65rem' }} onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          {/* Workload Provenance Info Banner */}
          {(primaryPkg || gitUrl || docUrl) && (
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.65rem 0.95rem',
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8rem',
              marginBottom: '1rem'
            }}>
              <span style={{ fontWeight: 700, color: '#34d399', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Check size={14} /> Qualified Workload:
              </span>
              {primaryPkg && (
                <span className="badge" style={{ background: 'rgba(6, 182, 212, 0.15)', color: '#67e8f9', border: '1px solid rgba(6, 182, 212, 0.3)' }}>
                  📦 {primaryPkg}
                </span>
              )}
              {gitUrl && (
                <span style={{ color: 'var(--text-muted)' }}>
                  GitHub: <a href={gitUrl} target="_blank" rel="noreferrer" style={{ color: '#06b6d4', textDecoration: 'underline' }}>{gitUrl.replace('https://github.com/', '')}</a>
                </span>
              )}
              {docUrl && (
                <span style={{ color: 'var(--text-muted)' }}>
                  Docs: <a href={docUrl} target="_blank" rel="noreferrer" style={{ color: '#06b6d4', textDecoration: 'underline' }}>{docUrl.replace(/^https?:\/\//, '')}</a>
                </span>
              )}
            </div>
          )}
          <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
            {/* Primary Action: Download Executive PDF */}
            <button 
              className="btn btn-primary" 
              style={{ fontSize: '0.86rem', padding: '0.6rem 1.15rem' }} 
              onClick={handleDownloadPdf}
              disabled={isDownloadingPdf}
              id="download-pdf-btn"
            >
              {isDownloadingPdf ? (
                <>
                  <div className="spinner" /> Generating PDF...
                </>
              ) : (
                <>
                  <Download size={16} /> Download Executive PDF Report
                </>
              )}
            </button>

            <button className="btn btn-secondary" style={{ fontSize: '0.84rem', padding: '0.55rem 0.95rem' }} onClick={handleDownloadMd}>
              <FileText size={15} color="#06b6d4" /> Download Markdown (.md)
            </button>
            <button className="btn btn-secondary" style={{ fontSize: '0.84rem', padding: '0.55rem 0.95rem' }} onClick={handleDownloadCsv}>
              <Table size={15} color="#8b5cf6" /> Export CSV Backlog
            </button>
            <button 
              className="btn btn-secondary" 
              style={{ fontSize: '0.84rem', padding: '0.55rem 0.95rem', marginLeft: 'auto' }} 
              onClick={() => window.print()}
            >
              <Printer size={15} /> Print
            </button>
            <button className="btn btn-secondary" style={{ fontSize: '0.84rem', padding: '0.55rem 0.95rem' }} onClick={handleCopy}>
              {copied ? <Check size={15} color="#10b981" /> : <Copy size={15} />}
              {copied ? 'Copied!' : 'Copy'}
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
