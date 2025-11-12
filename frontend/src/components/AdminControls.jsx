import React, { useState, useEffect } from 'react';
import { searchUsers, getUserDetails, getExercises, createExercise, updateExercise, deleteExercise, deleteUser, searchChallenges, deleteChallenge } from '../api/admin';
import refreshSystem from '../utils/refreshSystem';
import '../styles/App.css';

export default function AdminControls({ onExerciseCreated, onExerciseDeleted, onChallengeDeleted }) {
  const [activeTab, setActiveTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [exercises, setExercises] = useState([]);
  const [challenges, setChallenges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // User search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetails, setUserDetails] = useState(null);
  
  // Challenge search
  const [challengeSearchQuery, setChallengeSearchQuery] = useState('');
  
  // Exercise management
  const [showExerciseForm, setShowExerciseForm] = useState(false);
  const [editingExercise, setEditingExercise] = useState(null);
  const [exerciseForm, setExerciseForm] = useState({
    name: '',
    max_sessions_per_day: 1,
    max_rate_per_minute: 1,
    unit_type: 'reps',
    category: 'cardio'
  });

  useEffect(() => {
    if (activeTab === 'exercises') {
      loadExercises();
    } else if (activeTab === 'challenges') {
      loadChallenges();
    }
  }, [activeTab]);

  const loadExercises = async () => {
    setLoading(true);
    setError('');
    const response = await getExercises();
    if (response.status === 'success') {
      setExercises(response.data);
    } else {
      setError(response.detail || 'Failed to load exercises');
    }
    setLoading(false);
  };

  const searchUsersHandler = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError('');
    const response = await searchUsers(searchQuery);
    if (response.status === 'success') {
      setUsers(response.data.users);
    } else {
      setError(response.detail || 'Failed to search users');
    }
    setLoading(false);
  };

  const loadUserDetails = async (userId) => {
    setLoading(true);
    setError('');
    const response = await getUserDetails(userId);
    if (response.status === 'success') {
      setUserDetails(response.data);
      setSelectedUser(userId);
    } else {
      setError(response.detail || 'Failed to load user details');
    }
    setLoading(false);
  };

  const handleExerciseSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    const response = editingExercise 
      ? await updateExercise(editingExercise.id, exerciseForm)
      : await createExercise(exerciseForm);

    if (response.status === 'success') {
      setSuccess(editingExercise ? 'Exercise updated successfully!' : 'Exercise created successfully!');
      setShowExerciseForm(false);
      setEditingExercise(null);
      setExerciseForm({
        name: '',
        max_sessions_per_day: 1,
        max_rate_per_minute: 1,
        unit_type: 'reps',
        category: 'cardio'
      });
      loadExercises();
      // Notify parent component to refresh exercises in create challenge dropdown
      if (onExerciseCreated && !editingExercise) {
        onExerciseCreated();
      }
      // Trigger global refresh for all components
      if (!editingExercise) {
        refreshSystem.refreshExercises();
      }
    } else {
      setError(response.message || 'Failed to save exercise');
    }
    setLoading(false);
  };

  const handleEditExercise = (exercise) => {
    setEditingExercise(exercise);
    setExerciseForm({
      name: exercise.name,
      max_sessions_per_day: exercise.max_sessions_per_day,
      max_rate_per_minute: exercise.max_rate_per_minute,
      unit_type: exercise.unit_type,
      category: exercise.category
    });
    setShowExerciseForm(true);
  };

  const handleDeleteExercise = async (exerciseId) => {
    if (!window.confirm('Are you sure you want to delete this exercise?')) return;
    
    setLoading(true);
    setError('');
    const response = await deleteExercise(exerciseId);
    if (response.status === 'success') {
      setSuccess('Exercise deleted successfully!');
      loadExercises();
      // Notify parent component to refresh exercises in create challenge dropdown
      if (onExerciseDeleted) {
        onExerciseDeleted();
      }
      // Trigger global refresh for all components
      refreshSystem.refreshExercises();
    } else {
      setError(response.message || 'Failed to delete exercise');
    }
    setLoading(false);
  };

  const loadChallenges = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await searchChallenges();
      if (response.status === 'success') {
        setChallenges(response.data.challenges);
      } else {
        setError(response.detail || 'Failed to load challenges');
      }
    } catch (error) {
      console.error('Error loading challenges:', error);
      setError('Network error loading challenges');
    }
    setLoading(false);
  };

  const searchChallengesHandler = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await searchChallenges(challengeSearchQuery);
      if (response.status === 'success') {
        setChallenges(response.data.challenges);
      } else {
        setError(response.detail || 'Failed to search challenges');
      }
    } catch (error) {
      console.error('Error searching challenges:', error);
      setError('Network error searching challenges');
    }
    setLoading(false);
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Are you sure you want to delete this user? This action cannot be undone.')) return;
    
    setLoading(true);
    setError('');
    const response = await deleteUser(userId);
    if (response.status === 'success') {
      setSuccess('User deleted successfully!');
      setUserDetails(null);
      setSelectedUser(null);
      // Refresh user search results
      if (searchQuery) {
        searchUsersHandler();
      }
    } else {
      setError(response.message || 'Failed to delete user');
    }
    setLoading(false);
  };

  const handleDeleteChallenge = async (challengeId) => {
    if (!window.confirm('Are you sure you want to delete this challenge? This will remove all participants and cannot be undone.')) return;
    
    setLoading(true);
    setError('');
    const response = await deleteChallenge(challengeId);
    if (response.status === 'success') {
      setSuccess(response.message || 'Challenge deleted successfully!');
      loadChallenges();
      // Notify parent component to refresh challenges list
      if (onChallengeDeleted) {
        onChallengeDeleted();
      }
      // Trigger global refresh for all components
      refreshSystem.refreshChallenges();
    } else {
      setError(response.message || 'Failed to delete challenge');
    }
    setLoading(false);
  };

  return (
    <div className="admin-controls">
      <h2>Admin Controls</h2>
      
      <div className="admin-tabs">
        <button 
          className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          User Management
        </button>
        <button 
          className={`tab-button ${activeTab === 'exercises' ? 'active' : ''}`}
          onClick={() => setActiveTab('exercises')}
        >
          Exercise Management
        </button>
        <button 
          className={`tab-button ${activeTab === 'challenges' ? 'active' : ''}`}
          onClick={() => setActiveTab('challenges')}
        >
          Challenge Management
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {activeTab === 'users' && (
        <div className="admin-section">
          <h3>User Search</h3>
          <div className="search-form">
            <input
              type="text"
              placeholder="Search by email or display name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && searchUsersHandler()}
            />
            <button onClick={searchUsersHandler} disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>

          {users.length > 0 && (
            <div className="users-list">
              <h4>Search Results</h4>
              {users.map(user => (
                <div 
                  key={user.id} 
                  className={`user-item ${selectedUser === user.id ? 'selected' : ''}`}
                  onClick={() => loadUserDetails(user.id)}
                >
                  <div className="user-info">
                    <strong>{user.display_name}</strong>
                    <span>{user.email}</span>
                    <span className="user-role">{user.role}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {userDetails && (
            <div className="user-details">
              <div className="user-details-header">
                <h4>User Details</h4>
                <button 
                  className="btn btn-danger btn-sm"
                  onClick={() => handleDeleteUser(userDetails.user.id)}
                  disabled={loading}
                >
                  Delete User
                </button>
              </div>
              <div className="user-detail-grid">
                <div><strong>ID:</strong> {userDetails.user.id}</div>
                <div><strong>Email:</strong> {userDetails.user.email}</div>
                <div><strong>Display Name:</strong> {userDetails.user.display_name}</div>
                <div><strong>Role:</strong> {userDetails.user.role}</div>
                <div><strong>Created:</strong> {new Date(userDetails.user.created_at).toLocaleDateString()}</div>
                <div><strong>Active:</strong> {userDetails.user.is_active ? 'Yes' : 'No'}</div>
                <div><strong>Staff:</strong> {userDetails.user.is_staff ? 'Yes' : 'No'}</div>
                <div><strong>Location:</strong> {userDetails.user.city}, {userDetails.user.country}</div>
              </div>

              {userDetails.challenges.length > 0 && (
                <div className="user-challenges">
                  <h5>Challenges</h5>
                  {userDetails.challenges.map(challenge => (
                    <div key={challenge.id} className="challenge-item">
                      <strong>{challenge.title}</strong> - {challenge.status} ({challenge.role})
                    </div>
                  ))}
                </div>
              )}

              {userDetails.recent_progress.length > 0 && (
                <div className="user-progress">
                  <h5>Recent Progress</h5>
                  {userDetails.recent_progress.map(progress => (
                    <div key={progress.id} className="progress-item">
                      <strong>{progress.challenge_title}</strong>: {progress.progress_value} 
                      {progress.notes && <span> - {progress.notes}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'exercises' && (
        <div className="admin-section">
          <div className="section-header">
            <h3>Exercise Management</h3>
            <button 
              className="btn btn-primary"
              onClick={() => {
                setShowExerciseForm(true);
                setEditingExercise(null);
                setExerciseForm({
                  name: '',
                  max_sessions_per_day: 1,
                  max_rate_per_minute: 1,
                  unit_type: 'reps',
                  category: 'cardio'
                });
              }}
            >
              Add Exercise
            </button>
          </div>

          {showExerciseForm && (
            <div className="exercise-form">
              <h4>{editingExercise ? 'Edit Exercise' : 'Add New Exercise'}</h4>
              <form onSubmit={handleExerciseSubmit}>
                <div className="form-group">
                  <label>Name</label>
                  <input
                    type="text"
                    value={exerciseForm.name}
                    onChange={(e) => setExerciseForm({...exerciseForm, name: e.target.value})}
                    required
                  />
                </div>
                
                <div className="form-group">
                  <label>Max Sessions Per Day</label>
                  <input
                    type="number"
                    min="1"
                    value={exerciseForm.max_sessions_per_day}
                    onChange={(e) => setExerciseForm({...exerciseForm, max_sessions_per_day: parseInt(e.target.value)})}
                    required
                  />
                </div>
                
                <div className="form-group">
                  <label>Max Rate Per Minute</label>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={exerciseForm.max_rate_per_minute}
                    onChange={(e) => setExerciseForm({...exerciseForm, max_rate_per_minute: parseFloat(e.target.value)})}
                    required
                  />
                </div>
                
                <div className="form-group">
                  <label>Unit Type</label>
                  <select
                    value={exerciseForm.unit_type}
                    onChange={(e) => setExerciseForm({...exerciseForm, unit_type: e.target.value})}
                  >
                    <option value="reps">Repetitions</option>
                    <option value="km">Kilometers</option>
                  </select>
                </div>
                
                <div className="form-group">
                  <label>Category</label>
                  <select
                    value={exerciseForm.category}
                    onChange={(e) => setExerciseForm({...exerciseForm, category: e.target.value})}
                  >
                    <option value="cardio">Cardio</option>
                    <option value="strength">Strength</option>
                    <option value="flexibility">Flexibility</option>
                  </select>
                </div>
                
                <div className="form-actions">
                  <button type="submit" disabled={loading}>
                    {loading ? 'Saving...' : (editingExercise ? 'Update' : 'Create')}
                  </button>
                  <button 
                    type="button" 
                    onClick={() => {
                      setShowExerciseForm(false);
                      setEditingExercise(null);
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          <div className="exercises-list">
            <h4>Existing Exercises</h4>
            {loading ? (
              <p>Loading exercises...</p>
            ) : exercises.length === 0 ? (
              <p>No exercises found.</p>
            ) : (
              <div className="exercises-grid">
                {exercises.map(exercise => (
                  <div key={exercise.id} className="exercise-card">
                    <h5>{exercise.name}</h5>
                    <p><strong>Category:</strong> {exercise.category}</p>
                    <p><strong>Unit:</strong> {exercise.unit_type}</p>
                    <p><strong>Max Sessions/Day:</strong> {exercise.max_sessions_per_day}</p>
                    <p><strong>Max Rate/Min:</strong> {exercise.max_rate_per_minute}</p>
                    <div className="exercise-actions">
                      <button 
                        className="btn btn-sm btn-outline"
                        onClick={() => handleEditExercise(exercise)}
                      >
                        Edit
                      </button>
                      <button 
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDeleteExercise(exercise.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'challenges' && (
        <div className="admin-section">
          <h3>Challenge Management</h3>
          <div className="search-form">
            <input
              type="text"
              placeholder="Search challenges by title or description..."
              value={challengeSearchQuery}
              onChange={(e) => setChallengeSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && searchChallengesHandler()}
            />
            <button onClick={searchChallengesHandler} disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>

          <div className="challenges-list">
            <h4>Challenges</h4>
            {loading ? (
              <p>Loading challenges...</p>
            ) : challenges.length === 0 ? (
              <p>No challenges found.</p>
            ) : (
              <div className="challenges-grid">
                {challenges.map(challenge => (
                  <div key={challenge.id} className="challenge-card">
                    <h5>{challenge.title}</h5>
                    <p><strong>Type:</strong> {challenge.challenge_type}</p>
                    <p><strong>Status:</strong> {challenge.status}</p>
                    <p><strong>Participants:</strong> {challenge.participant_count}</p>
                    <p><strong>Owner:</strong> {challenge.owner?.display_name || 'Unknown'}</p>
                    <p><strong>Created:</strong> {new Date(challenge.created_at).toLocaleDateString()}</p>
                    <div className="challenge-actions">
                      <button 
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDeleteChallenge(challenge.id)}
                        disabled={loading}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
