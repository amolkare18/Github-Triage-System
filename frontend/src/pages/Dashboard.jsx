import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { apiClient } from '../api/client';
import { IssueCard } from '../components/IssueCard';
import { AnalyticsModal } from '../components/AnalyticsModal';

const Dashboard = () => {
  const { logout } = useAuth();
  const [repo, setRepo] = useState('');
  const [isTrigging, setIsTrigging] = useState(false);
  const [statusText, setStatusText] = useState('');
  const [triageMode, setTriageMode] = useState('full');
  
  const [pendingIssue, setPendingIssue] = useState(null);
  const [classifiedIssues, setClassifiedIssues] = useState([]);
  const [isDone, setIsDone] = useState(false);
  const [fetchedCount, setFetchedCount] = useState(0);
  const [showDashboardBtn, setShowDashboardBtn] = useState(false);
  
  const [isModalOpen, setIsModalOpen] = useState(false);

  const threadIdRef = useRef(null);
  const pollTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const runTriage = async () => {
    const trimmedRepo = repo.trim();
    if (!trimmedRepo) return;

    setIsTrigging(true);
    setStatusText('Starting triage...');
    setPendingIssue(null);
    setClassifiedIssues([]);
    setIsDone(false);
    setFetchedCount(0);
    setShowDashboardBtn(false);

    try {
      const res = await apiClient.post('/triage', { repo: trimmedRepo });
      if (!res.data || !res.data.thread_id) {
        alert(res.data?.detail || 'Failed to start triage');
        resetState();
        return;
      }

      threadIdRef.current = res.data.thread_id;
      setTriageMode(res.data.mode || 'full');
      setStatusText('Running triage...');
      
      pollTimerRef.current = setInterval(poll, 3000);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to start triage');
      resetState();
    }
  };

  const poll = async () => {
    if (!threadIdRef.current) return;
    try {
      const res = await apiClient.get(`/status/${threadIdRef.current}`);
      const data = res.data;
      
      if (data.mode) setTriageMode(data.mode);
      setClassifiedIssues(data.classified || []);
      setPendingIssue(data.pending);
      setFetchedCount(data.fetched_count || 0);

      if (data.status === 'done') {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
        setIsDone(true);
        resetState();
        if (data.classified && data.classified.length > 0) {
          setShowDashboardBtn(true);
        }
      }
    } catch (e) {
      console.error('Polling error', e);
    }
  };

  const approveIssue = async (approved) => {
    setPendingIssue(null);
    try {
      await apiClient.post('/approve', { thread_id: threadIdRef.current, approved });
      poll(); // Immediate fetch instead of waiting for timer
    } catch (e) {
      console.error('Approve failed', e);
    }
  };

  const resetState = () => {
    setIsTrigging(false);
    setStatusText('');
  };

  const handleLogout = () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    logout();
  };

  // Grouping classified issues
  const buckets = { high: [], medium: [], low: [] };
  classifiedIssues.forEach(r => {
    const sev = (r.severity || 'medium').toLowerCase();
    const key = (sev === 'critical' || sev === 'high') ? 'high' : sev === 'low' ? 'low' : 'medium';
    buckets[key].push(r);
  });

  // Top priority: up to 5 high/critical issues
  const topPriority = classifiedIssues
    .filter(r => {
      const sev = (r.severity || '').toLowerCase();
      return sev === 'critical' || sev === 'high';
    })
    .slice(0, 5);

  return (
    <div className="page active">
      <div className="dashboard">
        <div className="topbar">
          <h1>
            🔍 Triage Agent
            {triageMode && threadIdRef.current && (
              <span className={`mode-badge mode-${triageMode}`}>
                {triageMode === 'lite' ? 'Lite — classify only' : 'Full'}
              </span>
            )}
          </h1>
          <button className="logout" onClick={handleLogout}>Logout</button>
        </div>

        <div className="run-box">
          <input 
            type="text" 
            placeholder="Enter owner/repo  e.g. facebook/react" 
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            disabled={isTrigging}
          />
          <button onClick={runTriage} disabled={isTrigging}>
            {isTrigging ? 'Running...' : '▶ Run Triage'}
          </button>
        </div>

        {statusText && (
          <div className="status-bar" style={{ marginBottom: '28px' }}>
            <span className="spinner"></span>
            <span>{statusText}</span>
          </div>
        )}

        {showDashboardBtn && (
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '36px' }}>
            <button className="btn-dashboard" onClick={() => setIsModalOpen(true)}>
              ⚡ View Analytics Dashboard
            </button>
          </div>
        )}

        {/* ── Top Priority Issues ── */}
        {topPriority.length > 0 && (
          <div className="top-priority-section">
            <div className="top-priority-header">
              <span className="top-priority-title">🔥 Top Priority Issues</span>
              <span className="top-priority-count">{topPriority.length} critical / high</span>
            </div>
            <div className="top-priority-list">
              {topPriority.map((item, idx) => {
                const issue = item.issue || item;
                const sev = (item.severity || 'high').toLowerCase();
                const sevColor = sev === 'critical' ? '#ff6b6b' : '#f85149';
                return (
                  <div key={idx} className="top-priority-item">
                    <span className="tpi-rank">#{idx + 1}</span>
                    <div className="tpi-body">
                      <span className="tpi-title">{issue.title}</span>
                      <span className="tpi-meta">Issue #{issue.number}</span>
                    </div>
                    <div className="tpi-badges">
                      {item.classification && (
                        <span className="tpi-tag tpi-type">{item.classification}</span>
                      )}
                      <span className="tpi-tag tpi-sev" style={{ color: sevColor, borderColor: sevColor, background: `${sevColor}18` }}>
                        {sev.toUpperCase()}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <p className="section-title">Review queue</p>
        <div id="pending-list">
          {pendingIssue && (
            <IssueCard 
              issueData={pendingIssue} 
              isPending={true} 
              onApprove={approveIssue} 
              onReject={approveIssue} 
              triageMode={triageMode}
            />
          )}
        </div>

        <p className="section-title" style={{ marginTop: '32px' }}>Classified Issues</p>
        
        {classifiedIssues.length === 0 && isDone && fetchedCount === 0 && (
          <div className="empty" style={{ display: 'block' }}>
            No open issues found in this repository.
          </div>
        )}

        <div className="severity-grid">
          <div className="severity-lane lane-high">
            <span className="lane-header">High / Critical</span>
            <div>
              {buckets.high.length > 0 ? (
                buckets.high.map((issue, idx) => (
                  <IssueCard key={idx} issueData={issue} triageMode={triageMode} />
                ))
              ) : (
                <p style={{ color: '#8b949e', fontSize: '13px', padding: '8px 0' }}>None</p>
              )}
            </div>
          </div>
          <div className="severity-lane lane-medium">
            <span className="lane-header">Medium</span>
            <div>
              {buckets.medium.length > 0 ? (
                buckets.medium.map((issue, idx) => (
                  <IssueCard key={idx} issueData={issue} triageMode={triageMode} />
                ))
              ) : (
                <p style={{ color: '#8b949e', fontSize: '13px', padding: '8px 0' }}>None</p>
              )}
            </div>
          </div>
          <div className="severity-lane lane-low">
            <span className="lane-header">Low</span>
            <div>
              {buckets.low.length > 0 ? (
                buckets.low.map((issue, idx) => (
                  <IssueCard key={idx} issueData={issue} triageMode={triageMode} />
                ))
              ) : (
                <p style={{ color: '#8b949e', fontSize: '13px', padding: '8px 0' }}>None</p>
              )}
            </div>
          </div>
        </div>

        <AnalyticsModal 
          isOpen={isModalOpen} 
          onClose={() => setIsModalOpen(false)} 
          classifiedIssues={classifiedIssues} 
        />
      </div>
    </div>
  );
};

export default Dashboard;
