import React, { useRef, useEffect } from 'react';
import { Tile, Tag, InlineLoading } from '@carbon/react';
import { Bot, Terminal, CheckmarkFilled, WarningAltFilled, Information } from '@carbon/icons-react';

export default function AgentLiveFeed({ steps, isRunning }) {
  const feedEndRef = useRef(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  if (!steps || steps.length === 0) return null;

  return (
    <Tile id="agent-live-feed" style={{ borderLeft: '3px solid var(--cds-interactive)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Bot size={18} />
          <span className="cds--productive-heading-02">
            Autonomous Porting Triage Agent — Execution Stream
          </span>
        </div>
        {isRunning && (
          <InlineLoading description="Active Reasoning" status="active" />
        )}
      </div>

      {/* Step log */}
      <div
        style={{
          maxHeight: '280px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '0.8rem',
        }}
      >
        {steps.map((s, idx) => (
          <div
            key={idx}
            className="agent-step-item"
            style={{ display: 'flex', gap: '0.6rem', padding: '0.3rem 0', alignItems: 'flex-start' }}
          >
            {/* Step icon */}
            <span style={{ flexShrink: 0, marginTop: '2px' }}>
              {s.action_type === 'synthesis' ? (
                <CheckmarkFilled size={16} style={{ color: 'var(--cds-support-success)' }} />
              ) : s.thought?.includes('⚠️') ? (
                <WarningAltFilled size={16} style={{ color: 'var(--cds-support-warning)' }} />
              ) : (
                <Terminal size={16} style={{ color: 'var(--cds-interactive)' }} />
              )}
            </span>

            {/* Step content */}
            <div style={{ flex: 1 }}>
              <span style={{ display: 'inline', lineHeight: 1.5 }}>
                <span style={{ color: 'var(--cds-support-info)', fontWeight: 600 }}>[{s.agent_name}]</span>
                {' '}
                <span style={{ color: 'var(--cds-link-visited)' }}>&gt; {s.target}:</span>
                {' '}
                <span style={{ color: 'var(--cds-text-primary)' }}>{s.thought}</span>
              </span>
              {s.detail && (
                <div style={{ color: 'var(--cds-text-secondary)', fontSize: '0.75rem', marginTop: '0.15rem' }}>
                  ↳ {s.detail}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={feedEndRef} />
      </div>
    </Tile>
  );
}
