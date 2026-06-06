import React, { useState } from 'react';
import { apiClient } from '../api/client';

export const IssueCard = ({ 
  issueData, 
  isPending = false, 
  onApprove, 
  onReject, 
  triageMode 
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedComment, setGeneratedComment] = useState('');
  
  const issue = issueData.issue || issueData;
  const classification = issueData.classification || '';
  const severity = (issueData.severity || 'medium').toLowerCase();
  
  const sevCol = (severity === 'critical' || severity === 'high') ? '#f85149'
               : severity === 'low' ? '#3fb950' : '#d29922';

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await apiClient.post('/generate-comment', { 
        title: issue.title || '', 
        body: issue.body || '' 
      });
      setGeneratedComment(res.data?.comment || 'No comment generated.');
    } catch (e) {
      setGeneratedComment('Failed to generate comment.');
    } finally {
      setIsGenerating(false);
    }
  };

  if (isPending) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">{issue.title}</span>
          <span className="card-number">#{issue.number}</span>
        </div>
        <div style={{ marginBottom: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span className="type-tag">{classification}</span>
          <span style={{ fontSize: '12px', fontWeight: 600, color: sevCol }}>{severity.toUpperCase()}</span>
        </div>
        <div className="comment-box">{issueData.comment}</div>
        <div className="card-actions">
          <button className="btn-approve" onClick={() => onApprove(true)}>Post comment</button>
          <button className="btn-reject" onClick={() => onReject(false)}>Skip</button>
        </div>
      </div>
    );
  }

  // Classified view
  const statusBadge = () => {
    if (issueData.posted === true) return <span className="posted-tag">Commented</span>;
    if (issueData.posted === false) return <span className="rejected-tag">Skipped</span>;
    return <span style={{ fontSize: '12px', color: '#8b949e', padding: '3px 8px', border: '1px solid #30363d', borderRadius: '20px' }}>Pending</span>;
  };

  return (
    <div className="severity-card">
      <div className="card-title">{issue.title}</div>
      <div className="card-number">#{issue.number}</div>
      <span className="type-tag">{classification}</span>
      
      {triageMode === 'lite' ? (
        <>
          <button 
            className="btn-generate" 
            onClick={handleGenerate}
            disabled={isGenerating}
          >
            {isGenerating ? 'Generating...' : (generatedComment ? 'Regenerate' : 'Generate comment')}
          </button>
          {generatedComment && (
            <div className="generated-comment">
              {generatedComment}
            </div>
          )}
        </>
      ) : (
        statusBadge()
      )}
    </div>
  );
};
