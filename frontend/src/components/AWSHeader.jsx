import { useState } from 'react';
import './AWSHeader.css';

export default function AWSHeader({ currentConversationTitle }) {
    const [searchQuery, setSearchQuery] = useState('');

    return (
        <header className="aws-console-header">
            <div className="aws-header-left">
                {/* AWS Logo & Console Brand */}
                <div className="aws-brand-container">
                    <svg className="aws-logo-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12.5 17.5L20 8.5L27.5 17.5H12.5Z" fill="#FF9900" />
                        <path d="M8 22.5L20 31.5L32 22.5H8Z" fill="#EC7211" />
                        <circle cx="20" cy="20" r="3" fill="#FFFFFF" />
                    </svg>
                    <div className="aws-brand-titles">
                        <span className="aws-brand-name">aws</span>
                        <span className="aws-service-title">LLM Council</span>
                    </div>
                </div>

                {/* Neuros Engine Status Pill */}
                <div className="neuros-header-pill">
                    <span className="neuros-pulse-dot"></span>
                    <span className="neuros-pill-label">NEUROS CORE v2.4</span>
                    <span className="neuros-pill-badge">Matrix Active</span>
                </div>
            </div>

            {/* Global Console Search */}
            <div className="aws-header-search">
                <div className="aws-search-wrapper">
                    <svg className="aws-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                    <input
                        type="text"
                        placeholder="Search AWS services, models, prompts [Alt+S]"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="aws-search-input"
                    />
                    <span className="aws-search-shortcut">Alt+S</span>
                </div>
            </div>

            {/* AWS Console Right Widgets */}
            <div className="aws-header-right">
                {/* Region Selector */}
                <div className="aws-widget-item aws-region-select">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path>
                        <path d="M2 12h20"></path>
                    </svg>
                    <span>us-east-1 (N. Virginia)</span>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                </div>

                {/* Claude Sparkle Indicator */}
                <div className="aws-widget-item claude-telemetry-badge" title="Claude Neural Engine Integration">
                    <span className="claude-spark-icon">✨</span>
                    <span className="claude-badge-text">Claude Synth</span>
                </div>

                {/* Account / User Menu */}
                <div className="aws-widget-item aws-user-account">
                    <div className="aws-user-avatar">NC</div>
                    <span className="aws-user-id">Neuros_Admin @ 9842-4912</span>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                </div>
            </div>
        </header>
    );
}
