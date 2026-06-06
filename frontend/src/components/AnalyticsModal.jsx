import React, { useRef } from 'react';
import html2canvas from 'html2canvas';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

export const AnalyticsModal = ({ isOpen, onClose, classifiedIssues }) => {
  const modalRef = useRef(null);

  if (!isOpen) return null;

  const total = classifiedIssues.length;
  const bugs = classifiedIssues.filter(r => r.classification === 'bug').length;
  const features = classifiedIssues.filter(r => r.classification === 'feature' || r.classification === 'enhancement').length;
  const questions = classifiedIssues.filter(r => r.classification === 'question').length;
  const highSev = classifiedIssues.filter(r => {
    const sev = (r.severity || '').toLowerCase();
    return sev === 'critical' || sev === 'high';
  }).length;

  const handleDownload = async () => {
    if (!modalRef.current) return;
    try {
      const canvas = await html2canvas(modalRef.current, {
        backgroundColor: '#0d1117',
        scale: 2,
      });
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = 'triage-analytics.png';
      link.click();
    } catch (err) {
      console.error('Failed to capture dashboard', err);
    }
  };

  const chartData = [
    { name: 'Bugs', value: bugs, color: '#f85149' },
    { name: 'Features', value: features, color: '#2f81f7' },
    { name: 'Questions', value: questions, color: '#d29922' },
  ].filter(item => item.value > 0);

  const topPriorityIssues = classifiedIssues
    .filter(r => {
      const sev = (r.severity || '').toLowerCase();
      return sev === 'critical' || sev === 'high';
    })
    .slice(0, 3);

  return (
    <div className="dashboard-modal-overlay active">
      <div className="dashboard-modal" ref={modalRef}>
        <div className="dashboard-modal-header">
          <h2>Triage Analytics</h2>
          <button className="btn-close" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-content-grid">
          {/* Left Column: Stats */}
          <div className="stats-column">
            <div className="stats-grid">
              <div className="stat-card" style={{ gridColumn: 'span 2' }}>
                <div className="stat-title">Total Issues</div>
                <div className="stat-value">{total}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Bugs</div>
                <div className="stat-value bugs">{bugs}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Features</div>
                <div className="stat-value features">{features}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Questions</div>
                <div className="stat-value questions">{questions}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">High Sev</div>
                <div className="stat-value bugs">{highSev}</div>
              </div>
            </div>
          </div>

          {/* Right Column: Chart */}
          <div className="chart-column">
            {total > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    stroke="none"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', color: '#e6edf3' }} 
                    itemStyle={{ color: '#e6edf3' }}
                  />
                  <Legend verticalAlign="bottom" height={36}/>
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#8b949e', fontSize: '13px' }}>
                No data to chart
              </div>
            )}
          </div>
        </div>

        {/* Top Priority Section */}
        {topPriorityIssues.length > 0 && (
          <div className="priority-section">
            <h3 className="priority-title">🔥 Top Priority Issues</h3>
            <div className="priority-list">
              {topPriorityIssues.map((item, idx) => (
                <div key={idx} className="priority-item">
                  <span className="priority-number">#{item.issue.number}</span>
                  <span className="priority-text">{item.issue.title}</span>
                  <span className="priority-tag">{item.classification}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <button className="btn-download" onClick={handleDownload}>📸 Download as Image</button>
      </div>
    </div>
  );
};
