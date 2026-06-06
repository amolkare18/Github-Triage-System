import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

const Auth = () => {
  const [activeTab, setActiveTab] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, signup } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    let result;
    if (activeTab === 'login') {
      result = await login(email, password);
    } else {
      result = await signup(email, password, githubToken);
    }

    if (!result.success) {
      setError(result.error);
    }

    setIsSubmitting(false);
  };

  return (
    <div className="page active">
      <div className="auth-wrapper">
        <div className="auth-box">
          <h1>GitHub Triage Agent</h1>
          <p className="auth-subtitle">AI-powered issue triage for your repositories</p>
          <div className="tabs">
            <button
              className={`tab ${activeTab === 'login' ? 'active' : ''}`}
              onClick={() => { setActiveTab('login'); setError(''); }}
            >
              Login
            </button>
            <button
              className={`tab ${activeTab === 'signup' ? 'active' : ''}`}
              onClick={() => { setActiveTab('signup'); setError(''); }}
            >
              Sign up
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {activeTab === 'signup' && (
              <div className="field">
                <label>GitHub Token <span style={{ color: '#8b949e', fontWeight: 400 }}>(optional)</span></label>
                <input
                  type="password"
                  placeholder="ghp_..."
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.target.value)}
                />
                <p className="hint">With token: post comments &amp; detect duplicates.<br />Without token: classify &amp; preview only — no data stored.</p>
              </div>
            )}

            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Processing...' : (activeTab === 'login' ? '→ Login' : '→ Create account')}
            </button>
          </form>

          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </div>
  );
};

export default Auth;
