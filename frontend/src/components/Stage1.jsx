import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

function getShortModelName(model) {
  if (!model) return 'Node';
  if (model.includes('/')) return model.split('/')[1];
  if (model.includes(':')) {
    const parts = model.split(':');
    const base = parts[0].split('.').pop();
    return `${base}:${parts[1]}`;
  }
  if (model.includes('.')) return model.split('.').pop();
  return model;
}

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  const current = responses[activeTab] || {};

  return (
    <div className="stage stage1">
      <div className="stage-header-bar">
        <span className="stage-num-badge">STAGE 1</span>
        <h3 className="stage-title">Neuros Multi-Model Parallel Querying</h3>
        <span className="node-count-badge">{responses.length} Nodes</span>
      </div>

      <div className="aws-tabs">
        {responses.map((resp, index) => {
          const shortName = getShortModelName(resp.model);
          return (
            <button
              key={index}
              className={`aws-tab ${activeTab === index ? 'active' : ''} ${resp.error ? 'tab-error' : ''}`}
              onClick={() => setActiveTab(index)}
            >
              <span className="tab-node-icon">Node {String.fromCharCode(65 + index)}</span>
              <span className="tab-model-name">{shortName}</span>
              {resp.error && <span className="error-icon">⚠️</span>}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        <div className="model-info-bar">
          <span className="aws-resource-type">AWS::Bedrock::ModelNode</span>
          <span className="model-full-name">{current.model}</span>
        </div>

        {current.error ? (
          <div className="stage-error">
            <strong>Model Execution Error:</strong> {current.error}
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
