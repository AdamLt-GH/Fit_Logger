// src/pages/Profile.jsx
import React, { useEffect, useRef, useState } from "react";
import { getMyProfile as fetchProfile, updateMyProfile as updateProfile } from "../api/profile";
import { getUserChallenges } from "../api/progress";
import { logProgress } from "../api/progress";
import { getDashboardData } from "../api/dashboard";
import { useNavigate, Link } from "react-router-dom";
import "../styles/App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL;
const toAbs = (url) => (!url ? "" : url.startsWith("http") ? url : `${API_BASE}${url.startsWith("/") ? "" : "/"}${url}`);

export default function Profile({ onLogout }) {
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // user data
  const [user, setUser] = useState(null);

  // profile fields
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState(""); // read-only
  const [avatarUrl, setAvatarUrl] = useState("");
  const [avatarFile, setAvatarFile] = useState(null);

  // Store original values for cancel functionality
  const [originalDisplayName, setOriginalDisplayName] = useState("");
  const [originalAvatarUrl, setOriginalAvatarUrl] = useState("");

  // Challenges state
  const [challenges, setChallenges] = useState([]);
  const [challengesLoading, setChallengesLoading] = useState(false);
  const [showLogForm, setShowLogForm] = useState(false);
  const [selectedChallenge, setSelectedChallenge] = useState(null);
  const [logForm, setLogForm] = useState({
    progress_value: '',
    duration_minutes: '',
    notes: ''
  });
  const [logLoading, setLogLoading] = useState(false);

  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setErr(""); setMsg("");
      
      // Fetch user data for header
      try {
        const dashboardData = await getDashboardData();
        if (dashboardData?.status === 'success' && dashboardData?.data?.user) {
          setUser(dashboardData.data.user);
        }
      } catch (error) {
        console.error('Error fetching user data:', error);
      }
      
      // Fetch profile data
      const data = await fetchProfile();
      if (data && data.email) {
        setDisplayName(data.display_name || "");
        setEmail(data.email || "");
        setAvatarUrl(toAbs(data.avatar));
        // Store original values for cancel functionality
        setOriginalDisplayName(data.display_name || "");
        setOriginalAvatarUrl(toAbs(data.avatar));
      } else if (data?.detail) {
        setErr(data.detail);
      }
      setLoading(false);
    })();
    
    // Fetch user's challenges
    fetchUserChallenges();
  }, []);

  const fetchUserChallenges = async () => {
    try {
      setChallengesLoading(true);
      const response = await getUserChallenges();
      if (response.status === 'success') {
        // Handle paginated response
        const challengesData = response.data?.results || response.data || [];
        setChallenges(challengesData);
      }
    } catch (error) {
      console.error('Failed to fetch user challenges:', error);
    } finally {
      setChallengesLoading(false);
    }
  };

  function onPickAvatar() {
    fileInputRef.current?.click();
  }
  function onFileChange(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setAvatarFile(f);
    setAvatarUrl(URL.createObjectURL(f)); // instant preview
  }

  async function onSave() {
    setErr(""); setMsg("");

    // Update profile (display name + optional avatar)
    const fd = new FormData();
    fd.append("display_name", displayName);
    if (avatarFile) fd.append("avatar", avatarFile);

    const prof = await updateProfile(fd);
    if (prof?.status === "error" || prof?.errors) {
      setErr(prof?.message || JSON.stringify(prof?.errors));
      return;
    }

    // Update original values after successful save
    setOriginalDisplayName(displayName);
    setOriginalAvatarUrl(avatarUrl);
    setAvatarFile(null); // Clear the file after successful upload

    setMsg("Changes saved. Redirecting…");
    navigate("/dashboard", { replace: true });
  }

  function onCancel() {
    // Navigate back to dashboard
    navigate("/dashboard", { replace: true });
  }

  const handleLogProgress = (challenge) => {
    setSelectedChallenge(challenge);
    setLogForm({ progress_value: '', duration_minutes: '', notes: '' });
    setShowLogForm(true);
  };

  const handleLogSubmit = async (e) => {
    e.preventDefault();
    if (!logForm.progress_value || !logForm.duration_minutes || !selectedChallenge) return;
    
    // Validate max rate per minute
    const progressValue = parseFloat(logForm.progress_value);
    const durationMinutes = parseFloat(logForm.duration_minutes);
    const ratePerMinute = progressValue / durationMinutes;
    
    // Get max rate and unit type from challenge data
    const maxRatePerMinute = selectedChallenge.max_rate_per_minute || 100;
    const exerciseUnitType = selectedChallenge.exercise_unit_type || 'units';
    
    if (ratePerMinute > maxRatePerMinute) {
      alert(`Rate too high! Maximum ${maxRatePerMinute} ${exerciseUnitType} per minute allowed. Your rate: ${ratePerMinute.toFixed(2)} ${exerciseUnitType}/minute`);
      return;
    }

    try {
      setLogLoading(true);
      const response = await logProgress(selectedChallenge.id, {
        progress_value: progressValue,
        duration_minutes: durationMinutes,
        notes: logForm.notes
      });
      
      if (response.status === 'success') {
        setShowLogForm(false);
        setSelectedChallenge(null);
        setLogForm({ progress_value: '', duration_minutes: '', notes: '' });
        // Refresh challenges to show updated progress
        fetchUserChallenges();
      } else {
        setErr(response.message || 'Failed to log progress');
      }
    } catch (error) {
      setErr('Network error logging progress');
    } finally {
      setLogLoading(false);
    }
  };

  if (loading) return <div className="page-container"><p>Loading…</p></div>;

  return (
    <div className="dashboard-container">
      {/* Header Navigation */}
      <nav className="navbar navbar-expand-lg navbar-dark bg-primary">
        <div className="container">
          <a className="navbar-brand fw-bold" href="#">
            <i className="fas fa-trophy me-2" />
            ChallengeHub
          </a>

          <button
            className="navbar-toggler"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#navbarNav"
          >
            <span className="navbar-toggler-icon" />
          </button>

          <div className="collapse navbar-collapse" id="navbarNav">
            <ul className="navbar-nav me-auto">
              <li className="nav-item">
                <a
                  className="nav-link"
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/dashboard");
                  }}
                >
                  <i className="fas fa-home me-1" />
                  Discover Challenges
                </a>
              </li>

              <li className="nav-item">
                <a
                  className="nav-link active"
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/profile");
                  }}
                >
                  <i className="fas fa-user me-1" />
                  Profile
                </a>
              </li>

              <li className="nav-item">
                <a
                  className="nav-link"
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate("/dashboard");
                    // Trigger create challenge view
                    setTimeout(() => {
                      const createButton = document.querySelector('[data-view="create"]');
                      if (createButton) createButton.click();
                    }, 100);
                  }}
                >
                  <i className="fas fa-plus me-1" />
                  Create Challenge
                </a>
              </li>

              {user && user.role === 'Admin' && (
                <li className="nav-item">
                  <a
                    className="nav-link"
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      navigate("/dashboard");
                      // Trigger admin view
                      setTimeout(() => {
                        const adminButton = document.querySelector('[data-view="admin"]');
                        if (adminButton) adminButton.click();
                      }, 100);
                    }}
                  >
                    <i className="fas fa-cog me-1" />
                    Admin Controls
                  </a>
                </li>
              )}
            </ul>

            <div className="navbar-nav">
              <span className="navbar-text me-3">
                Welcome, <strong>{user?.display_name}</strong>!
              </span>
              <a
                className="nav-link"
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  onLogout?.();
                }}
              >
                <i className="fas fa-sign-out-alt me-1" />
                Logout
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="page-container">
        <section className="profile-wrap">
          <h2 className="profile-title">Profile Page</h2>

        <div className="profile-grid">
          {/* LEFT: form */}
          <div className="profile-panel">
            <div className="field">
              <label>Display Name</label>
              <input
                className="input-lg"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your display name"
              />
            </div>

            <div className="field">
              <label>Email</label>
              <input className="input-lg input-readonly" value={email} disabled />
            </div>


            {err && <p className="form-msg error">{err}</p>}
            {msg && <p className="form-msg ok">{msg}</p>}

            <div className="actions-row">
              <button className="btn btn-primary" onClick={onSave}>Confirm Changes</button>
              <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
            </div>
          </div>

          {/* RIGHT: avatar panel */}
          <aside className="avatar-panel">
            <div className="avatar-box">
              {avatarUrl ? (
                <img src={avatarUrl} alt="Avatar preview" />
              ) : (
                <div className="avatar-placeholder">👤</div>
              )}
            </div>

            <button type="button" className="btn btn-outline" onClick={onPickAvatar}>
              Change photo
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              hidden
              onChange={onFileChange}
            />
          </aside>
        </div>

        {/* Challenges Section */}
        <section className="challenges-section">
          <h3>My Challenges</h3>
          {challengesLoading ? (
            <p>Loading challenges...</p>
          ) : challenges.length === 0 ? (
            <p>You're not participating in any challenges yet.</p>
          ) : (
            <div className="challenges-list">
              {challenges.map(challenge => (
                <div key={challenge.id} className="challenge-item">
                  <div className="challenge-info">
                    <h4>{challenge.title}</h4>
                    <p className="challenge-type">
                      {challenge.challenge_type === 0 ? "Habit Based" : "Goal Based"}
                    </p>
                    <p className="challenge-description">{challenge.description}</p>
                    <div className="challenge-meta">
                      <span>Created by: {challenge.creator?.display_name}</span>
                      <span>Participants: {challenge.participant_count}</span>
                    </div>
                  </div>
                  <div className="challenge-actions">
                    <Link 
                      to={`/challenge/${challenge.id}`}
                      className="btn btn-outline btn-sm"
                    >
                      View Details
                    </Link>
                    <button 
                      onClick={() => handleLogProgress(challenge)}
                      className="btn btn-primary btn-sm"
                    >
                      Log Progress
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </section>

      {/* Log Progress Modal */}
      {showLogForm && selectedChallenge && (
        <div className="log-progress-modal">
          <div className="modal-content">
            <h3>Log Progress - {selectedChallenge.title}</h3>
            <form onSubmit={handleLogSubmit}>
              <div className="form-group">
                <label>
                  Progress Value * 
                  <span className="unit-label">
                    ({selectedChallenge.exercise_unit_type || 'units'})
                  </span>
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={logForm.progress_value}
                  onChange={(e) => setLogForm({...logForm, progress_value: e.target.value})}
                  required
                  placeholder={`Enter ${selectedChallenge.exercise_unit_type || 'progress value'}`}
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
      </main>
    </div>
  );
}
