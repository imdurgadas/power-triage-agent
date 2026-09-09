import React, { useRef, useEffect } from 'react';
import { Bot, Terminal, CheckCircle2, AlertTriangle, ArrowRight, Loader } from 'lucide-react';

export default function AgentLiveFeed({ steps, isRunning }) {
  const feedEndRef = useRef(null);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  if (!steps || steps.length === 0) return null;

  return (
    <div className="agent-feed-card" id="agent-live-feed">
      <div className="agent-feed-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Bot size={18} color="#60a5fa" />
          <span>Autonomous Porting Triage Agent Execution Stream</span>
        </div>
        {isRunning && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: '#38bdf8' }}>
            <Loader size={14} className="spin-slow" /> Active Reasoning
          </div>
        )}
      </div>

      <div style={{ maxHeight: '260px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem', paddingRight: '0.5rem' }}>
        {steps.map((s, idx) => (
          <div key={idx} className="agent-step-item">
            <div className="step-icon">
              {s.action_type === 'synthesis' ? (
                <CheckCircle2 size={16} color="#4ade80" />
              ) : s.thought?.includes('⚠️') ? (
                <AlertTriangle size={16} color="#facc15" />
              ) : (
                <Terminal size={16} color="#38bdf8" />
              )}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
                <span className="step-agent">[{s.agent_name}]</span>
                <span className="step-target">&gt; {s.target}:</span>
                <span style={{ color: '#f1f5f9' }}>{s.thought}</span>
              </div>
              {s.detail && <div className="step-detail">↳ {s.detail}</div>}
            </div>
          </div>
        ))}
        <div ref={feedEndRef} />
      </div>
    </div>
  );
}
