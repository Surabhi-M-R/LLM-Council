import { useState, useMemo } from 'react';
import { api, clearAuth } from '../api';
import './CognitoAuthModal.css';

/**
 * AWS Cognito default password policy requires ALL of these:
 *   - Minimum 8 characters
 *   - At least 1 lowercase letter (a-z)
 *   - At least 1 uppercase letter (A-Z)
 *   - At least 1 digit (0-9)
 *   - At least 1 special character (^ $ * . [ ] { } ( ) ? - " ! @ # % & / \ , > < ' : ; | _ ~ ` + =)
 * See: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-policies.html
 */
const PASSWORD_RULES = [
    { key: 'length', label: 'At least 8 characters', test: (p) => p.length >= 8 },
    { key: 'lowercase', label: 'At least 1 lowercase letter (a-z)', test: (p) => /[a-z]/.test(p) },
    { key: 'uppercase', label: 'At least 1 uppercase letter (A-Z)', test: (p) => /[A-Z]/.test(p) },
    { key: 'number', label: 'At least 1 number (0-9)', test: (p) => /[0-9]/.test(p) },
    { key: 'special', label: 'At least 1 special character (!@#$%^&* …)', test: (p) => /[^A-Za-z0-9]/.test(p) },
];

export default function CognitoAuthModal({ isOpen, onClose, user, onAuthSuccess }) {
    const [mode, setMode] = useState('signin');
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmCode, setConfirmCode] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [successMsg, setSuccessMsg] = useState('');

    // Live password validation for sign-up form
    const passwordChecks = useMemo(
        () => PASSWORD_RULES.map((rule) => ({ ...rule, passed: rule.test(password) })),
        [password],
    );
    const allPasswordChecksPassed = passwordChecks.every((c) => c.passed);

    if (!isOpen) return null;

    const handleSignIn = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const data = await api.signIn(username, password);
            setSuccessMsg('Successfully authenticated with Amazon Cognito!');
            setTimeout(() => {
                onAuthSuccess(username);
                onClose();
            }, 1000);
        } catch (err) {
            setError(err.message || 'Sign in failed.');
        } finally {
            setLoading(false);
        }
    };

    const handleSignUp = async (e) => {
        e.preventDefault();
        setError('');

        // Client-side validation: block submit if password doesn't meet policy
        if (!allPasswordChecksPassed) {
            const missing = passwordChecks.filter((c) => !c.passed).map((c) => c.label);
            setError(`Password does not meet AWS Cognito policy. Missing: ${missing.join(', ')}`);
            return;
        }

        setLoading(true);
        try {
            await api.signUp(email, username, password);
            setSuccessMsg('Account created! Check your email for the verification code.');
            setMode('confirm');
        } catch (err) {
            setError(err.message || 'Sign up failed.');
        } finally {
            setLoading(false);
        }
    };

    const handleConfirm = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            await api.confirmSignUp(username, confirmCode);
            setSuccessMsg('Email confirmed! You can now sign in.');
            setMode('signin');
        } catch (err) {
            setError(err.message || 'Confirmation failed.');
        } finally {
            setLoading(false);
        }
    };

    const handleSignOut = () => {
        clearAuth();
        onAuthSuccess(null);
        setSuccessMsg('Signed out successfully.');
        setTimeout(() => {
            onClose();
        }, 800);
    };

    return (
        <div className="cognito-modal-overlay" onClick={onClose}>
            <div className="cognito-modal-content" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="cognito-modal-header">
                    <div className="cognito-brand">
                        <svg className="cognito-logo" viewBox="0 0 24 24" fill="none" stroke="#FF9900" strokeWidth="2">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                        <div>
                            <span className="cognito-title">Amazon Cognito Authentication</span>
                            <span className="cognito-subtitle">AWS User Pools & OAuth 2.0 / OIDC</span>
                        </div>
                    </div>
                    <button className="cognito-close-btn" onClick={onClose}>×</button>
                </div>

                {/* Status Banners */}
                {error && <div className="cognito-alert error">{error}</div>}
                {successMsg && <div className="cognito-alert success">{successMsg}</div>}

                {/* Profile View (if already signed in) */}
                {user ? (
                    <div className="cognito-body">
                        <div className="cognito-user-card">
                            <div className="user-avatar-large">{user.substring(0, 2).toUpperCase()}</div>
                            <div className="user-card-info">
                                <h3>{user}</h3>
                                <span className="user-role-badge">Authenticated Cognito User</span>
                                <span className="user-session-id">Token: JWT Bearer Active</span>
                            </div>
                        </div>

                        <div className="cognito-info-box">
                            <div className="info-row">
                                <span>Identity Provider:</span>
                                <strong>AWS Cognito User Pool</strong>
                            </div>
                            <div className="info-row">
                                <span>Auth Mechanism:</span>
                                <strong>RS256 Signed JWT</strong>
                            </div>
                            <div className="info-row">
                                <span>Security Standard:</span>
                                <strong>OAuth 2.0 / OIDC</strong>
                            </div>
                        </div>

                        <div className="cognito-actions">
                            <button className="cognito-btn secondary" onClick={handleSignOut}>
                                Sign Out
                            </button>
                            <button className="cognito-btn primary" onClick={onClose}>
                                Done
                            </button>
                        </div>
                    </div>
                ) : (
                    /* Auth Forms (Sign In / Sign Up / Confirm) */
                    <div className="cognito-body">
                        {/* Tab Switcher */}
                        <div className="cognito-tabs">
                            <button
                                className={`cognito-tab ${mode === 'signin' ? 'active' : ''}`}
                                onClick={() => { setMode('signin'); setError(''); setSuccessMsg(''); }}
                            >
                                Sign In
                            </button>
                            <button
                                className={`cognito-tab ${mode === 'signup' ? 'active' : ''}`}
                                onClick={() => { setMode('signup'); setError(''); setSuccessMsg(''); }}
                            >
                                Sign Up
                            </button>
                            {mode === 'confirm' && (
                                <button className="cognito-tab active">Confirm Code</button>
                            )}
                        </div>

                        {/* Sign In Form */}
                        {mode === 'signin' && (
                            <form onSubmit={handleSignIn} className="cognito-form">
                                <div className="form-group">
                                    <label>Cognito Username / Email</label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="e.g. dev_admin"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        className="cognito-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Password</label>
                                    <input
                                        type="password"
                                        required
                                        placeholder="••••••••••••"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className="cognito-input"
                                    />
                                </div>
                                <button type="submit" disabled={loading} className="cognito-btn primary">
                                    {loading ? 'Authenticating with AWS...' : 'Sign In via Cognito'}
                                </button>
                            </form>
                        )}

                        {/* Sign Up Form */}
                        {mode === 'signup' && (
                            <form onSubmit={handleSignUp} className="cognito-form">
                                <div className="form-group">
                                    <label>Email Address</label>
                                    <input
                                        type="email"
                                        required
                                        placeholder="developer@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        className="cognito-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Username</label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="e.g. aws_developer"
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        className="cognito-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Password (AWS Cognito Policy)</label>
                                    <input
                                        type="password"
                                        required
                                        placeholder="e.g. MyP@ssw0rd!"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        className={`cognito-input ${password.length > 0 ? (allPasswordChecksPassed ? 'input-valid' : 'input-invalid') : ''}`}
                                    />
                                    {/* Live password requirements checklist */}
                                    <div className="password-policy-checklist">
                                        {passwordChecks.map((check) => (
                                            <div
                                                key={check.key}
                                                className={`policy-rule ${password.length === 0 ? 'neutral' : check.passed ? 'passed' : 'failed'}`}
                                            >
                                                <span className="policy-icon">
                                                    {password.length === 0 ? '○' : check.passed ? '✓' : '✗'}
                                                </span>
                                                <span className="policy-label">{check.label}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <button
                                    type="submit"
                                    disabled={loading || (password.length > 0 && !allPasswordChecksPassed)}
                                    className="cognito-btn primary"
                                >
                                    {loading ? 'Creating Cognito User...' : 'Create AWS Cognito Account'}
                                </button>
                            </form>
                        )}

                        {/* Verification Code Form */}
                        {mode === 'confirm' && (
                            <form onSubmit={handleConfirm} className="cognito-form">
                                <div className="form-group">
                                    <label>Username</label>
                                    <input
                                        type="text"
                                        required
                                        value={username}
                                        onChange={(e) => setUsername(e.target.value)}
                                        className="cognito-input"
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Verification Code (From Email)</label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="123456"
                                        value={confirmCode}
                                        onChange={(e) => setConfirmCode(e.target.value)}
                                        className="cognito-input code-input"
                                    />
                                </div>
                                <button type="submit" disabled={loading} className="cognito-btn primary">
                                    {loading ? 'Verifying Code...' : 'Confirm Account Registration'}
                                </button>
                            </form>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
