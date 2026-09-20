import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = model.split('/')[1] || model;
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  // Calculate maximum score for visual bar ratio
  const maxScore = aggregateRankings ? Math.max(...aggregateRankings.map(a => a.average_rank)) || 1 : 1;

  return (
    <div className="stage stage2">
      <div className="stage-header-bar">
        <span className="stage-num-badge purple">STAGE 2</span>
        <h3 className="stage-title">Neuros Peer Review & Anonymized Evaluation</h3>
      </div>

      {/* Aggregate Leaderboard Dashboard */}
      {aggregateRankings && aggregateRankings.length > 0 && (
        <div className="aws-metrics-dashboard">
          <div className="metrics-header">
            <div className="metrics-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff9900" strokeWidth="2">
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
              <span>Neuros Consensus Leaderboard (Street Cred)</span>
            </div>
            <span className="metrics-sub">Lower average rank score indicates higher peer consensus</span>
          </div>

          <div className="aggregate-list">
            {aggregateRankings.map((agg, index) => {
              const shortName = agg.model.split('/')[1] || agg.model;
              // Normalize bar fill percentage (1 = 100%, higher rank number = lower bar)
              const fillPercent = Math.max(15, Math.min(100, (1 / agg.average_rank) * 100));

              return (
                <div key={index} className={`aggregate-item rank-${index + 1}`}>
                  <div className="rank-position-badge">
                    {index === 0 ? '🥇 #1' : index === 1 ? '🥈 #2' : index === 2 ? '🥉 #3' : `#${index + 1}`}
                  </div>

                  <div className="rank-details">
                    <div className="rank-model-row">
                      <span className="rank-model-name">{shortName}</span>
                      <div className="rank-score-pill">
                        Avg Rank: <strong>{agg.average_rank.toFixed(2)}</strong>
                        <span className="vote-count">({agg.rankings_count} peer votes)</span>
                      </div>
                    </div>

                    <div className="rank-progress-bg">
                      <div
                        className="rank-progress-fill"
                        style={{ width: `${fillPercent}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Raw Peer Evaluations Tab View */}
      <div className="raw-evaluations-section">
        <h4 className="evaluations-subtitle">Raw Anonymized Peer Evaluations</h4>
        <p className="stage-description">
          Each node evaluated peer responses blind (labeled as Response A, B, C). Model names are highlighted in bold for readability.
        </p>

        <div className="aws-tabs">
          {rankings.map((rank, index) => {
            const shortName = rank.model.split('/')[1] || rank.model;
            return (
              <button
                key={index}
                className={`aws-tab ${activeTab === index ? 'active' : ''} ${rank.error ? 'tab-error' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                <span className="tab-node-icon">Evaluator {index + 1}</span>
                <span className="tab-model-name">{shortName}</span>
                {rank.error && <span className="error-icon">⚠️</span>}
              </button>
            );
          })}
        </div>

        <div className="tab-content">
          <div className="model-info-bar">
            <span className="aws-resource-type purple">AWS::Neuros::Evaluator</span>
            <span className="model-full-name">{rankings[activeTab]?.model}</span>
          </div>

          {rankings[activeTab]?.error ? (
            <div className="stage-error">
              <strong>Evaluation Error:</strong> {rankings[activeTab].error}
            </div>
          ) : (
            <div className="ranking-content markdown-content">
              <ReactMarkdown>
                {deAnonymizeText(rankings[activeTab]?.ranking || '', labelToModel)}
              </ReactMarkdown>
            </div>
          )}

          {rankings[activeTab]?.parsed_ranking && rankings[activeTab].parsed_ranking.length > 0 && (
            <div className="parsed-ranking-box">
              <span className="parsed-title">Extracted Score Priority:</span>
              <ol className="parsed-list">
                {rankings[activeTab].parsed_ranking.map((label, i) => (
                  <li key={i}>
                    {labelToModel && labelToModel[label]
                      ? labelToModel[label].split('/')[1] || labelToModel[label]
                      : label}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
