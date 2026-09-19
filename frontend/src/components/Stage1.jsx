import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  const current = responses[activeTab] || {};

  return (
    <div className="stage stage1">
      <h3 className="stage-title">Stage 1: Individual Responses</h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''} ${resp.error ? 'tab-error' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {resp.model.split('/')[1] || resp.model}
            {resp.error ? ' ⚠️' : ''}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">{current.model}</div>
        {current.error ? (
          <div className="stage-error">
            <strong>Model Error:</strong> {current.error}
          </div>
        ) : (
          <div className="response-text markdown-content">
            <ReactMarkdown>{current.response}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
