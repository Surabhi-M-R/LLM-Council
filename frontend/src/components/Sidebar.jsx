import { useState } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
}) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredConversations = conversations.filter((c) =>
    (c.title || 'New Conversation').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside className="aws-sidebar">
      {/* Action Header */}
      <div className="sidebar-action-bar">
        <button className="aws-new-session-btn" onClick={onNewConversation}>
          <span className="aws-btn-icon">+</span>
          <span>New Deliberation Session</span>
        </button>
      </div>

      {/* Filter / Search Conversations */}
      <div className="sidebar-search-box">
        <input
          type="text"
          placeholder="Filter sessions..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="sidebar-search-input"
        />
      </div>

      {/* Section Title */}
      <div className="sidebar-section-title">
        <span>DELIBERATION SESSIONS ({conversations.length})</span>
      </div>

      {/* Conversation List */}
      <div className="conversation-list">
        {filteredConversations.length === 0 ? (
          <div className="no-conversations">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <p>No active sessions found</p>
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = conv.id === currentConversationId;
            return (
              <div
                key={conv.id}
                className={`conversation-item ${isActive ? 'active' : ''}`}
                onClick={() => onSelectConversation(conv.id)}
              >
                <div className="conversation-item-header">
                  <span className="conversation-title">
                    {conv.title || 'New Session'}
                  </span>
                </div>
                <div className="conversation-meta">
                  <span className="meta-badge">
                    {conv.message_count || 0} msgs
                  </span>
                  <span className="meta-date">
                    {conv.created_at ? new Date(conv.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Neuros Telemetry Footer */}
      <div className="neuros-telemetry-panel">
        <div className="neuros-panel-header">
          <span className="neuros-spark-glow">✨</span>
          <span className="neuros-panel-title">NEUROS TELEMETRY</span>
        </div>
        <div className="neuros-metrics-grid">
          <div className="neuros-metric">
            <span className="metric-label">Ensemble</span>
            <span className="metric-val">4 AWS Nodes</span>
          </div>
          <div className="neuros-metric">
            <span className="metric-label">Claude Synth</span>
            <span className="metric-val text-amber">Active</span>
          </div>
          <div className="neuros-metric">
            <span className="metric-label">Latency</span>
            <span className="metric-val text-green">~320ms</span>
          </div>
          <div className="neuros-metric">
            <span className="metric-label">Status</span>
            <span className="metric-val text-cyan">Optimal</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
