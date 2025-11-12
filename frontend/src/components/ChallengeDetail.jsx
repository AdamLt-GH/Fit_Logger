// src/components/ChallengeDetail.jsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getChallengeDetail, joinChallenge, leaveChallenge } from '../api/dashboard';
import { logProgress, getProgressHistory } from '../api/progress';
import '../styles/App.css';

export default function ChallengeDetail() {
  const { challengeId } = useParams();
  const navigate = useNavigate();
  const [challenge, setChallenge] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isParticipating, setIsParticipating] = useState(false);
  const [participantRole, setParticipantRole] = useState('');
  const [showLogForm, setShowLogForm] = useState(false);
  const [logForm, setLogForm] = useState({
    progress_value: '',
    duration_minutes: '',
    notes: ''
  });
  const [logLoading, setLogLoading] = useState(false);
  const [progressHistory, setProgressHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    fetchChallengeDetail();
  }, [challengeId]);

  useEffect(() => {
    if (challenge && isParticipating) {
      fetchProgressHistory();
    }
  }, [challenge, isParticipating]);

  const fetchChallengeDetail = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await getChallengeDetail(challengeId);
      if (response.status === 'success') {
        setChallenge(response.data);
        setIsParticipating(response.data.is_participating);
        setParticipantRole(response.data.user_role || '');
      } else {
        setError('Failed to load challenge details');
      }
    } catch (err) {
      setError('Network error loading challenge');
    } finally {
      setLoading(false);
    }
  };

  const fetchProgressHistory = async () => {
    try {
      setHistoryLoading(true);
      const response = await getProgressHistory(challengeId);
      if (response.status === 'success') {
        setProgressHistory(response.data.progress_entries || []);
      }
    } catch (err) {
      console.error('Failed to fetch progress history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleJoinChallenge = async () => {
    try {
      const response = await joinChallenge(challengeId);
      if (response.status === 'success') {
        setIsParticipating(true);
        setParticipantRole('Participant');
        fetchChallengeDetail(); // Refresh to get updated participant count
      } else {
        setError(response.message || 'Failed to join challenge');
      }
    } catch (err) {
      setError('Network error joining challenge');
    }
  };

  const handleLeaveChallenge = async () => {
    if (!window.confirm('Are you sure you want to leave this challenge?')) return;
    
    try {
      const response = await leaveChallenge(challengeId);
      if (response.status === 'success') {
        // Check if challenge was deleted
        if (response.data?.challenge_deleted) {
          // Challenge was deleted, navigate back to dashboard
          navigate('/dashboard');
          return;
        }
        
        // Regular leave - update state
        setIsParticipating(false);
        setParticipantRole('');
        fetchChallengeDetail(); // Refresh to get updated participant count
      } else {
        setError(response.message || 'Failed to leave challenge');
      }
    } catch (err) {
      setError(err.message || 'Network error leaving challenge');
    }
  };

  const handleLogProgress = async (e) => {
    e.preventDefault();
    if (!logForm.progress_value || !logForm.duration_minutes) return;
    
    // Validate max rate per minute
    const progressValue = parseFloat(logForm.progress_value);
    const durationMinutes = parseFloat(logForm.duration_minutes);
    const ratePerMinute = progressValue / durationMinutes;
    
    // Get max rate from challenge data
    const maxRatePerMinute = challenge?.max_rate_per_minute || 100;
    
    if (ratePerMinute > maxRatePerMinute) {
      setError(`Rate too high! Maximum ${maxRatePerMinute} ${challenge?.exercise_unit_type || 'units'} per minute allowed. Your rate: ${ratePerMinute.toFixed(2)} ${challenge?.exercise_unit_type || 'units'}/minute`);
      return;
    }
    
    try {
      setLogLoading(true);
      const response = await logProgress(challengeId, {
        progress_value: progressValue,
        duration_minutes: durationMinutes,
        notes: logForm.notes
      });
      
      if (response.status === 'success') {
        setShowLogForm(false);
        setLogForm({ progress_value: '', duration_minutes: '', notes: '' });
        fetchChallengeDetail(); // Refresh to get updated progress
        fetchProgressHistory(); // Always refresh progress history
      } else {
        setError(response.message || 'Failed to log progress');
      }
    } catch (err) {
      setError('Network error logging progress');
    } finally {
      setLogLoading(false);
    }
  };


  // Use the progress percentage from the backend (time-based)
  const progressPercentage = challenge?.progress_percentage || 0;

  if (loading) {
    return (
      <div className="challenge-detail">
        <div className="loading">Loading challenge details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="challenge-detail">
        <div className="error">{error}</div>
        <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }

  if (!challenge) {
    return (
      <div className="challenge-detail">
        <div className="error">Challenge not found</div>
        <button onClick={() => navigate('/dashboard')} className="btn btn-primary">
          Back to Dashboard
        </button>
      </div>
    );
  }


  return (
    <div className="challenge-detail">
      <div className="challenge-header">
        <button 
          onClick={() => navigate('/dashboard')} 
          className="btn btn-outline"
        >
          ← Back to Dashboard
        </button>
        <h1>{challenge.title}</h1>
        <div className="challenge-meta">
          <span className="challenge-type">
            {challenge.challenge_type === 0 ? "Habit Based" : "Goal Based"}
          </span>
          <span className="challenge-status">{challenge.status}</span>
        </div>
      </div>

      <div className="challenge-content">
        <div className="challenge-info">
          <div className="challenge-description">
            <h3>Description</h3>
            <p>{challenge.description}</p>
          </div>

          <div className="challenge-progress">
            <h3>Challenge Progress</h3>
            <div className="progress-bar-container">
              <div className="progress-bar">
                <div 
                  className="progress-fill" 
                  style={{ width: `${progressPercentage}%` }}
                ></div>
              </div>
              <span className="progress-text">{Math.round(progressPercentage)}% Complete</span>
            </div>
          </div>

          <div className="challenge-details">
            <h3>Challenge Details</h3>
            <div className="details-grid">
              <div><strong>Created by:</strong> {challenge.creator?.display_name}</div>
              <div><strong>Created:</strong> {new Date(challenge.created_at).toLocaleDateString()}</div>
              <div><strong>Participants:</strong> {challenge.participant_count}</div>
              {challenge.challenge_type === 'Habit' && challenge.habit_details && (
                <>
                  <div><strong>Exercise:</strong> {challenge.habit_details.exercise?.name}</div>
                  <div><strong>Duration:</strong> {challenge.habit_details.duration_weeks} weeks</div>
                  <div><strong>Frequency:</strong> {challenge.habit_details.frequency_per_week} times per week</div>
                </>
              )}
              {challenge.challenge_type === 'Target' && challenge.target_details && (
                <>
                  <div><strong>Exercise:</strong> {challenge.target_details.exercise?.name}</div>
                  <div><strong>Duration:</strong> {challenge.target_details.duration_days} days</div>
                  <div><strong>Target:</strong> {challenge.target_details.target_value} {challenge.target_details.exercise?.unit_type}</div>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="challenge-actions">
          <h3>Actions</h3>
          {!isParticipating ? (
            <button 
              onClick={handleJoinChallenge}
              className="btn btn-primary"
            >
              Join Challenge
            </button>
          ) : (
            <div className="participant-actions">
              <button 
                onClick={() => setShowLogForm(true)}
                className="btn btn-primary"
              >
                Log Progress
              </button>
              <button 
                onClick={handleLeaveChallenge}
                className="btn btn-outline"
              >
                Leave Challenge
              </button>
            </div>
          )}
        </div>

        <div className="participants-section">
          <h3>Participants</h3>
          {challenge.participants && challenge.participants.length > 0 ? (
            <div className="participants-list">
              {challenge.participants.map(participant => (
                <div key={participant.id} className="participant-item">
                  <div className="participant-info">
                    <div className="participant-name">
                      <strong>{participant.display_name}</strong>
                      <span className="participant-role">{participant.role}</span>
                      <span className="participant-state">{participant.state}</span>
                    </div>
                    <div className="participant-progress">
                      <div className="progress-bar-small">
                        <div 
                          className="progress-fill" 
                          style={{ width: `${participant.progress_percentage || 0}%` }}
                        ></div>
                      </div>
                      <span className="progress-text">
                        {participant.total_progress || 0} {challenge?.exercise_unit_type || 'units'} ({participant.progress_percentage || 0}%)
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p>No participants yet.</p>
          )}
        </div>

        {isParticipating && (
          <div className="progress-history-section">
            <h3>My Progress History</h3>
            
            <div className="progress-history">
              {historyLoading ? (
                <p>Loading progress history...</p>
              ) : progressHistory.length > 0 ? (
                <div className="history-list">
                  {progressHistory.map(entry => (
                    <div key={entry.id} className="history-item">
                      <div className="history-date">
                        {new Date(entry.logged_at).toLocaleDateString()} at {new Date(entry.logged_at).toLocaleTimeString()}
                      </div>
                      <div className="history-progress">
                        <strong>{entry.progress_value}</strong> {challenge?.exercise_unit_type || 'units'}
                      </div>
                      {entry.notes && (
                        <div className="history-notes">
                          <em>"{entry.notes}"</em>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p>No progress logged yet.</p>
              )}
            </div>
          </div>
        )}
      </div>

      {showLogForm && (
        <div className="log-progress-modal">
          <div className="modal-content">
            <h3>Log Progress</h3>
            <form onSubmit={handleLogProgress}>
              <div className="form-group">
                <label>
                  Progress Value * 
                  <span className="unit-label">
                    ({challenge?.exercise_unit_type || 'units'})
                  </span>
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={logForm.progress_value}
                  onChange={(e) => setLogForm({...logForm, progress_value: e.target.value})}
                  required
                  placeholder={`Enter ${challenge?.exercise_unit_type || 'progress value'}`}
                />
              </div>
              
              <div className="form-group">
                <label>Duration (minutes) *</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  value={logForm.duration_minutes}
                  onChange={(e) => setLogForm({...logForm, duration_minutes: e.target.value})}
                  required
                  placeholder="Enter duration in minutes"
                />
                <small>How long did this exercise session take?</small>
              </div>
              
              <div className="form-group">
                <label>Notes (Optional)</label>
                <textarea
                  value={logForm.notes}
                  onChange={(e) => setLogForm({...logForm, notes: e.target.value})}
                  placeholder="Add any notes about your progress..."
                  rows="3"
                />
              </div>
              
              <div className="form-actions">
                <button 
                  type="submit" 
                  disabled={logLoading}
                  className="btn btn-primary"
                >
                  {logLoading ? 'Logging...' : 'Log Progress'}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowLogForm(false)}
                  className="btn btn-outline"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
