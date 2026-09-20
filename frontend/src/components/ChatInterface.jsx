import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  onNewConversation,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation, isLoading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface empty">
        <div className="aws-empty-hero">
          <div className="aws-hero-logo-badge">
            <svg width="48" height="48" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12.5 17.5L20 8.5L27.5 17.5H12.5Z" fill="#FF9900" />
              <path d="M8 22.5L20 31.5L32 22.5H8Z" fill="#EC7211" />
              <circle cx="20" cy="20" r="3" fill="#FFFFFF" />
            </svg>
          </div>
          <h2>AWS LLM Council Matrix</h2>
          <p className="aws-hero-subtitle">
            Powered by <strong>Neuros Neural Engine v2.4</strong> & <strong>AWS Bedrock Consensus</strong>
          </p>
          <div className="aws-feature-pills">
            <span className="pill">⚡ 3-Stage Peer Deliberation</span>
            <span className="pill">🛡️ Anonymized Scoring</span>
            <span className="pill">🎯 Executive Synthesis</span>
          </div>
          <button className="aws-hero-action-btn" onClick={onNewConversation}>
            <span>+ Start New Deliberation</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      {/* Console Top Breadcrumbs */}
      <div className="aws-console-breadcrumbs">
        <span className="bc-root">AWS Console</span>
        <span className="bc-sep">/</span>
        <span className="bc-item">Neuros Engine</span>
        <span className="bc-sep">/</span>
        <span className="bc-item active">
          {conversation.title || 'New Session'}
        </span>
        <div className="aws-status-indicator">
          <span className={`status-dot ${isLoading ? 'busy' : 'ready'}`}></span>
          <span className="status-label">
            {isLoading ? 'Neuros Processing...' : 'Consensus Ready'}
          </span>
        </div>
      </div>

      {/* Messages Feed */}
      <div className="messages-container">
        <div className="messages-container-inner">
          {conversation.messages.length === 0 ? (
            <div className="aws-empty-chat">
              <div className="aws-sparkle-intro">
                <span className="sparkle">✨</span>
              </div>
              <h3>Initiate Deliberation Session</h3>
              <p>Type your query below to launch multi-model consensus across AWS Bedrock nodes.</p>
            </div>
          ) : (
            conversation.messages.map((msg, index) => (
              <div key={index} className="message-group">
                {msg.role === 'user' ? (
                  <div className="user-message">
                    <div className="message-header">
                      <span className="user-avatar-badge">USER</span>
                      <span className="message-label">Request Payload</span>
                    </div>
                    <div className="message-content">
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="assistant-message">
                    <div className="message-header">
                      <div className="aws-council-badge">
                        <span className="aws-badge-orange">AWS</span>
                        <span className="neuros-badge-cyan">Neuros Council</span>
                      </div>
                    </div>

                    {msg.error && (
                      <div className="stage-error">
                        <strong>AWS Bedrock Error:</strong> {msg.error}
                      </div>
                    )}

                    {/* Stage 1 Loading & Content */}
                    {msg.loading?.stage1 && (
                      <div className="aws-stage-loading">
                        <div className="aws-shimmer-bar"></div>
                        <div className="loading-body">
                          <span className="aws-sparkle-spin">✨</span>
                          <div className="loading-text">
                            <strong>Stage 1: Multi-Model Querying</strong>
                            <span>Dispatching prompt across independent AWS Bedrock LLM nodes...</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {msg.stage1 && <Stage1 responses={msg.stage1} />}

                    {/* Stage 2 Loading & Content */}
                    {msg.loading?.stage2 && (
                      <div className="aws-stage-loading">
                        <div className="aws-shimmer-bar"></div>
                        <div className="loading-body">
                          <span className="aws-sparkle-spin">✨</span>
                          <div className="loading-text">
                            <strong>Stage 2: Neuros Peer Review Matrix</strong>
                            <span>Anonymizing outputs and generating peer ranking evaluations...</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {msg.stage2 && (
                      <Stage2
                        rankings={msg.stage2}
                        labelToModel={msg.metadata?.label_to_model}
                        aggregateRankings={msg.metadata?.aggregate_rankings}
                      />
                    )}

                    {/* Stage 3 Loading & Content */}
                    {msg.loading?.stage3 && (
                      <div className="aws-stage-loading">
                        <div className="aws-shimmer-bar"></div>
                        <div className="loading-body">
                          <span className="aws-sparkle-spin">✨</span>
                          <div className="loading-text">
                            <strong>Stage 3: Executive Consensus Synthesis</strong>
                            <span>Synthesizing final consensus answer...</span>
                          </div>
                        </div>
                      </div>
                    )}
                    {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Global Loading Indicator if starting */}
          {isLoading && !conversation.messages[conversation.messages.length - 1]?.loading && (
            <div className="aws-global-loading">
              <div className="aws-shimmer-bar"></div>
              <div className="loading-content">
                <span className="aws-sparkle-pulse">✨</span>
                <span>Neuros AI Engine deliberating...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Console Bar */}
      <form className="aws-input-form" onSubmit={handleSubmit}>
        <div className="aws-input-form-inner">
          <div className="aws-input-container">
            <textarea
              ref={textareaRef}
              className="aws-message-textarea"
              placeholder="Ask AWS LLM Council... (Shift+Enter for newline, Enter to transmit)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
            />
            <div className="input-toolbar">
              <div className="input-hints">
                <span className="hint-pill">Neuros v2.4</span>
                <span className="hint-pill font-mono">Shift+Enter: newline</span>
              </div>
              <button
                type="submit"
                className="aws-send-button"
                disabled={!input.trim() || isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="aws-btn-spark">✨</span>
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <span>Transmit Query</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <line x1="22" y1="2" x2="11" y2="13"></line>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
