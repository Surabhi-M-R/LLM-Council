import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage3.css';

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

export default function Stage3({ finalResponse }) {
  const [copied, setCopied] = useState(false);

  if (!finalResponse) {
    return null;
  }

  const chairmanName = getShortModelName(finalResponse.model);

  const handleCopy = () => {
    if (finalResponse.response) {
      navigator.clipboard.writeText(finalResponse.response);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="stage stage3">
      <div className="stage-header-bar">
        <span className="stage-num-badge gold">STAGE 3</span>
        <h3 className="stage-title">Executive Synthesis & Final Consensus</h3>
        <span className="aws-synthesis-spark">✨</span>
      </div>

      <div className="final-response-hero">
        {/* Top Metadata & Actions Bar */}
        <div className="final-hero-header">
          <div className="chairman-details">
            <span className="chairman-title-badge">CHAIRMAN NODE</span>
            <span className="chairman-model-name">{chairmanName}</span>
          </div>

          <div className="hero-right-actions">
            <div className="neuros-verified-stamp">
              <span className="check-icon">✓</span>
              <span>Neuros Consensus Verified</span>
            </div>

            <button className="copy-answer-btn" onClick={handleCopy}>
              {copied ? '✓ Copied' : 'Copy Answer'}
            </button>
          </div>
        </div>

        {/* Response Body */}
        {finalResponse.error ? (
          <div className="stage-error">
            <strong>Chairman Error:</strong> {finalResponse.error}
          </div>
        ) : (
          <div className="final-text markdown-content aws-typography">
            <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
          </div>
        )}

        {/* Footer Meta */}
        <div className="final-hero-footer">
          <div className="footer-meta-pill">
            <span className="label">Pipeline:</span>
            <span className="val">AWS Bedrock • Neuros Engine v2.4</span>
          </div>
          <div className="footer-meta-pill">
            <span className="label">Status:</span>
            <span className="val green font-mono">200 OK (Synthesized)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
