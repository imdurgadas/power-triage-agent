import React, { useRef, useEffect } from 'react';
import { Tile } from '@carbon/react';
import { Bot, Terminal, CheckmarkFilled, WarningAltFilled } from '@carbon/icons-react';

export default function AgentLiveFeed({ steps, isRunning }) {
  const feedEndRef = useRef(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  if (!steps || steps.length === 0) return null;

  return (
    <Tile id="agent-live-feed" style={{ borderLeft: '4px solid #0f62fe', background: '#262626', padding: '1.25rem 1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Bot size={20} style={{ color: '#78a9ff' }} />
          <span style={{ fontSize: '1rem', fontWeight: 600, color: '#f4f4f4', letterSpacing: '0.01em' }}>
            Autonomous Porting Triage Agent — Execution Stream
          </span>
        </div>

        {isRunning && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'rgba(15, 98, 254, 0.2)',
              border: '1px solid rgba(15, 98, 254, 0.5)',
              padding: '0.25rem 0.75rem',
              borderRadius: '1rem',
              flexShrink: 0,
            }}
          >
            <span className="spinner" style={{ width: '13px', height: '13px', borderWidth: '2px', borderTopColor: '#78a9ff' }} />
            <span style={{ fontSize: '0.8rem', color: '#78a9ff', fontWeight: 600 }}>Active Reasoning...</span>
          </div>
        )}
      </div>

      {/* Step log */}
      <div
        style={{
          maxHeight: '340px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '0.82rem',
          padding: '0.25rem 0.25rem 0.5rem 0.25rem',
        }}
      >
        {steps.map((s, idx) => (
          <div
            key={idx}
            className="agent-step-item"
            style={{
              display: 'flex',
              gap: '0.75rem',
              padding: '0.6rem 0.85rem',
              alignItems: 'flex-start',
              background: '#1c1c1c',
              border: '1px solid #333333',
              borderLeft: '3px solid #0f62fe',
              borderRadius: '2px',
            }}
          >
            {/* Step icon */}
            <span style={{ flexShrink: 0, marginTop: '2px' }}>
              {s.action_type === 'synthesis' ? (
                <CheckmarkFilled size={16} style={{ color: '#42be65' }} />
              ) : s.thought?.includes('⚠️') ? (
                <WarningAltFilled size={16} style={{ color: '#f1c21b' }} />
              ) : (
                <Terminal size={16} style={{ color: '#78a9ff' }} />
              )}
            </span>

            {/* Step content */}
            <div style={{ flex: 1, minWidth: 0, wordBreak: 'break-word' }}>
              <div style={{ lineHeight: 1.5, color: '#f4f4f4' }}>
                <span style={{ color: '#78a9ff', fontWeight: 600 }}>[{s.agent_name}]</span>
                {' '}
                <span style={{ color: '#a8a8a8' }}>&gt; {s.target}:</span>
                {' '}
                <span>{s.thought}</span>
              </div>
              {s.detail && (
                <div style={{ color: '#c6c6c6', fontSize: '0.76rem', marginTop: '0.35rem', paddingLeft: '0.5rem', borderLeft: '2px solid #525252' }}>
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
