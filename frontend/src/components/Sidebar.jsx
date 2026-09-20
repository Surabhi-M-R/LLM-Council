import { useState, useEffect } from 'react';
import { api } from '../api';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  isOpen = true,
  onClose,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [systemConfig, setSystemConfig] = useState(null);

  useEffect(() => {
    api.getSystemConfig()
      .then(setSystemConfig)
      .catch(() => setSystemConfig(null));
  }, []);

  const filteredConversations = conversations.filter((c) =>
    (c.title || 'New Conversation').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const providerLabel = 'AWS Bedrock';

  const storageLabel = systemConfig?.storage_backend === 'dynamodb'
    ? 'DynamoDB'
    : 'Local JSON';

  const handleSelect = (id) => {
    onSelectConversation(id);
    if (onClose) onClose();
  };

  const handleNew = () => {
    onNewConversation();
    if (onClose) onClose();
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && <div className="sidebar-backdrop" onClick={onClose} />}

      <aside className={`aws-sidebar ${isOpen ? 'open' : 'closed'}`}>
        {/* Mobile Header Bar */}
        <div className="sidebar-mobile-header">
          <span className="sidebar-mobile-title">Navigation</span>
          <button className="sidebar-close-btn" onClick={onClose} aria-label="Close Sidebar">×</button>
        </div>

        {/* Action Header */}
        <div className="sidebar-action-bar">
          <button className="aws-new-session-btn" onClick={handleNew}>
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
                  onClick={() => handleSelect(conv.id)}
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

        {/* AWS Infrastructure Panel */}
        <div className="neuros-telemetry-panel">
          <div className="neuros-panel-header">
            <span className="neuros-spark-glow">☁️</span>
            <span className="neuros-panel-title">AWS INFRASTRUCTURE</span>
          </div>
          <div className="neuros-metrics-grid">
            <div className="neuros-metric">
              <span className="metric-label">Provider</span>
              <span className="metric-val text-amber">{providerLabel}</span>
            </div>
            <div className="neuros-metric">
              <span className="metric-label">Storage</span>
              <span className="metric-val text-cyan">{storageLabel}</span>
            </div>
            <div className="neuros-metric">
              <span className="metric-label">Models</span>
              <span className="metric-val">{systemConfig?.council_models?.length || '—'} Nodes</span>
            </div>
            <div className="neuros-metric">
              <span className="metric-label">Region</span>
              <span className="metric-val text-green">{systemConfig?.aws_region || '—'}</span>
            </div>
            <div className="neuros-metric">
              <span className="metric-label">Auth</span>
              <span className={`metric-val ${systemConfig?.cognito_enabled ? 'text-green' : 'text-muted'}`}>
                {systemConfig?.cognito_enabled ? 'Cognito ✓' : 'Disabled'}
              </span>
            </div>
            <div className="neuros-metric">
              <span className="metric-label">Metrics</span>
              <span className={`metric-val ${systemConfig?.cloudwatch_enabled ? 'text-green' : 'text-muted'}`}>
                {systemConfig?.cloudwatch_enabled ? 'CloudWatch ✓' : 'Disabled'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
