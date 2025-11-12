// src/components/Dashboard.jsx
import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  getDashboardData,
  joinChallenge,
  leaveChallenge,
  createChallenge,
  getExercises,
} from "../api/dashboard";
import WeatherWidget from "./WeatherWidget";
import AdminControls from "./AdminControls";
import refreshSystem from "../utils/refreshSystem";
import "../styles/Dashboard.css";

export default function Dashboard({ onLogout }) {
  const navigate = useNavigate();

  // views left: 'challenges' and 'create'
  const [currentView, setCurrentView] = useState("challenges");

  const [challenges, setChallenges] = useState([]);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [exercises, setExercises] = useState([]);
  const [createForm, setCreateForm] = useState({
    title: "",
    description: "",
    challenge_type: "habit",
    threshold_percentage: 80,
    exercise_id: "",
    duration_weeks: 4,
    frequency_per_week: 5,
    duration_days: 7,
    target_value: 100,
  });
  const [createLoading, setCreateLoading] = useState(false);
  const [createMessage, setCreateMessage] = useState("");

  useEffect(() => {
    fetchDashboardData();
    fetchExercises();

    // Set up global refresh listeners
    const handleExercisesChanged = () => {
      fetchExercises();
    };

    const handleChallengesChanged = () => {
      fetchDashboardData();
    };

    const handleSystemRefresh = () => {
      fetchDashboardData();
      fetchExercises();
    };

    // Subscribe to refresh events
    refreshSystem.subscribe('exercises_changed', handleExercisesChanged);
    refreshSystem.subscribe('challenges_changed', handleChallengesChanged);
    refreshSystem.subscribe('system_refresh', handleSystemRefresh);

    // Cleanup listeners on unmount
    return () => {
      refreshSystem.unsubscribe('exercises_changed', handleExercisesChanged);
      refreshSystem.unsubscribe('challenges_changed', handleChallengesChanged);
      refreshSystem.unsubscribe('system_refresh', handleSystemRefresh);
    };
  }, []);

  // Function to refresh exercises (can be called from admin controls)
  const refreshExercises = () => {
    fetchExercises();
  };

  // Function to refresh challenges (can be called from admin controls)
  const refreshChallenges = () => {
    fetchDashboardData();
  };

  // Function to refresh everything (for major changes)
  const refreshAll = () => {
    fetchDashboardData();
    fetchExercises();
  };

  async function fetchExercises() {
    try {
      const res = await getExercises();
      if (res.status === "success") {
        // The data now contains the paginated response with results array
        const exerciseData = res.data.results || res.data;
        setExercises(exerciseData);
      } else {
        console.error("Failed to load exercises - no success status:", res);
      }
    } catch (e) {
      console.error("Failed to load exercises:", e);
    }
  }

  async function fetchDashboardData() {
    try {
      setLoading(true);
      setError("");
      const res = await getDashboardData();
      if (res.status === "success") {
        setChallenges(res.data.challenges);
        setUser(res.data.user);
      } else {
        setError("Failed to load dashboard data");
      }
    } catch (e) {
      if (String(e?.message || "").includes("401")) {
        localStorage.removeItem("token");
        window.location.reload();
      } else {
        setError("Network error: " + e.message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleJoinChallenge(id) {
    try {
      const res = await joinChallenge(id);
      if (res.status === "success") {
        setChallenges((prev) =>
          prev.map((c) => (c.id === id ? { ...c, is_participating: true } : c))
        );
      } else {
        alert(res.message || "Join failed");
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  }

  async function handleLeaveChallenge(id) {
    if (!window.confirm("Leave this challenge?")) return;
    try {
      const res = await leaveChallenge(id);
      if (res.status === "success") {
        // Check if challenge was deleted
        if (res.data?.challenge_deleted) {
          // Challenge was deleted, remove it from the list
          setChallenges((prev) => prev.filter((c) => c.id !== id));
          return;
        }
        
        // Regular leave - update participation status
        setChallenges((prev) =>
          prev.map((c) => (c.id === id ? { ...c, is_participating: false } : c))
        );
      } else {
        alert(res.message || "Leave failed");
      }
    } catch (e) {
      alert("Error: " + e.message);
    }
  }

  function handleChallengeClick(id) {
    navigate(`/challenge/${id}`);
  }

  function handleCreateFormChange(e) {
    const { name, value } = e.target;
    setCreateForm((p) => ({ ...p, [name]: value }));
  }

  async function handleCreateSubmit(e) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateMessage("");

    try {
      const payload = {
        title: createForm.title,
        description: createForm.description,
        challenge_type: createForm.challenge_type === "habit" ? 0 : 1,
        threshold_percentage: parseInt(createForm.threshold_percentage),
        status: "published",
      };

      if (createForm.challenge_type === "habit") {
        payload.habit_details = {
          exercise_id: parseInt(createForm.exercise_id),
          duration_weeks: parseInt(createForm.duration_weeks),
          frequency_per_week: parseInt(createForm.frequency_per_week),
        };
      } else {
        payload.target_details = {
          exercise_id: parseInt(createForm.exercise_id),
          duration_days: parseInt(createForm.duration_days),
          target_value: parseInt(createForm.target_value),
        };
      }

      const res = await createChallenge(payload);
      if (res.status === "success") {
        setCreateMessage("Challenge created successfully!");
        setCreateForm({
          title: "",
          description: "",
          challenge_type: "habit",
          threshold_percentage: 80,
          exercise_id: "",
          duration_weeks: 4,
          frequency_per_week: 5,
          duration_days: 7,
          target_value: 100,
        });
        fetchDashboardData();
        setTimeout(() => setCurrentView("challenges"), 800);
      } else {
        setCreateMessage("Failed: " + (res.message || "Unknown error"));
      }
    } catch (e) {
      setCreateMessage("Error: " + e.message);
    } finally {
      setCreateLoading(false);
    }
  }

  function handleLocationUpdate(loc) {
    setUser((u) => ({ ...(u || {}), ...loc }));
  }

  const filtered = challenges.filter((c) => {
    if (!filter) return true;
    const f = filter.toLowerCase();
    return (
      c.challenge_type === f ||
      c.exercise?.toLowerCase().includes(f) ||
      c.title.toLowerCase().includes(f)
    );
  });

  const getIcon = (exercise) => {
    const s = (exercise || "").toLowerCase();
    if (s.includes("running")) return "fas fa-running";
    if (s.includes("lift")) return "fas fa-dumbbell";
    return "fas fa-dumbbell";
  };
  const typeColor = (t) => (t === "habit" ? "bg-info" : "bg-success");

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="loading-spinner">
          <i className="fas fa-spinner fa-spin fa-2x" />
          <p>Loading challenges...</p>
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error-message">
          <i className="fas fa-exclamation-triangle fa-2x" />
          <p>{error}</p>
          <button onClick={fetchDashboardData} className="btn btn-primary">
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Neon top bar */}
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
                  className={`nav-link ${
                    currentView === "challenges" ? "active" : ""
                  }`}
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    setCurrentView("challenges");
                  }}
                >
                  <i className="fas fa-home me-1" />
                  Discover Challenges
                </a>
              </li>

              {/* Profile now routes to the standalone /profile page */}
              <li className="nav-item">
                <a
                  className="nav-link"
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
                  className={`nav-link ${
                    currentView === "create" ? "active" : ""
                  }`}
                  href="#"
                  onClick={(e) => {
                    e.preventDefault();
                    setCurrentView("create");
                  }}
                >
                  <i className="fas fa-plus me-1" />
                  Create Challenge
                </a>
              </li>

              {user && user.role === 'Admin' && (
                <li className="nav-item">
                  <a
                    className={`nav-link ${
                      currentView === "admin" ? "active" : ""
                    }`}
                    href="#"
                    onClick={(e) => {
                      e.preventDefault();
                      setCurrentView("admin");
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
      <div className="container mt-4">
        {/* Create view */}
        {currentView === "create" && (
          <div className="row">
            <div className="col-12">
              <div className="card">
                <div className="card-header">
                  <h3 className="mb-0">Create New Challenge</h3>
                </div>
                <div className="card-body">
                  <form onSubmit={handleCreateSubmit}>
                    <div className="row">
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label className="form-label">Challenge Title *</label>
                          <input
                            type="text"
                            className="form-control"
                            name="title"
                            value={createForm.title}
                            onChange={handleCreateFormChange}
                            required
                            placeholder="Enter challenge title"
                          />
                        </div>
                      </div>
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label className="form-label">Challenge Type *</label>
                          <select
                            className="form-select"
                            name="challenge_type"
                            value={createForm.challenge_type}
                            onChange={handleCreateFormChange}
                            required
                          >
                            <option value="habit">Habit Based</option>
                            <option value="target">Goal Based</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    <div className="mb-3">
                      <label className="form-label">Description</label>
                      <textarea
                        className="form-control"
                        name="description"
                        rows="3"
                        value={createForm.description}
                        onChange={handleCreateFormChange}
                        placeholder="Describe your challenge..."
                      />
                    </div>

                    <div className="row">
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label className="form-label">Exercise *</label>
                          <select
                            className="form-select"
                            name="exercise_id"
                            value={createForm.exercise_id}
                            onChange={handleCreateFormChange}
                            required
                          >
                            <option value="">Select an exercise</option>
                            {exercises.map((ex) => (
                              <option key={ex.id} value={ex.id}>
                                {ex.name} ({ex.unit_type})
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label className="form-label">
                            Success Threshold (%)
                          </label>
                          <input
                            type="number"
                            className="form-control"
                            name="threshold_percentage"
                            min="1"
                            max="100"
                            value={createForm.threshold_percentage}
                            onChange={handleCreateFormChange}
                            required
                          />
                        </div>
                      </div>
                    </div>

                    {createForm.challenge_type === "habit" ? (
                      <div className="row">
                        <div className="col-md-6">
                          <div className="mb-3">
                            <label className="form-label">
                              Duration (weeks) *
                            </label>
                            <input
                              type="number"
                              className="form-control"
                              name="duration_weeks"
                              min="1"
                              max="52"
                              value={createForm.duration_weeks}
                              onChange={handleCreateFormChange}
                              required
                            />
                          </div>
                        </div>
                        <div className="col-md-6">
                          <div className="mb-3">
                            <label className="form-label">
                              Frequency per week *
                            </label>
                            <input
                              type="number"
                              className="form-control"
                              name="frequency_per_week"
                              min="1"
                              max="7"
                              value={createForm.frequency_per_week}
                              onChange={handleCreateFormChange}
                              required
                            />
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="row">
                        <div className="col-md-6">
                          <div className="mb-3">
                            <label className="form-label">
                              Duration (days) *
                            </label>
                            <input
                              type="number"
                              className="form-control"
                              name="duration_days"
                              min="1"
                              max="365"
                              value={createForm.duration_days}
                              onChange={handleCreateFormChange}
                              required
                            />
                          </div>
                        </div>
                        <div className="col-md-6">
                          <div className="mb-3">
                            <label className="form-label">Target Value *</label>
                            <input
                              type="number"
                              className="form-control"
                              name="target_value"
                              min="1"
                              value={createForm.target_value}
                              onChange={handleCreateFormChange}
                              required
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {createMessage && (
                      <div
                        className={`alert ${
                          createMessage.includes("success")
                            ? "alert-success"
                            : "alert-danger"
                        }`}
                      >
                        {createMessage}
                      </div>
                    )}

                    <div className="d-flex gap-2">
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={createLoading}
                      >
                        {createLoading ? (
                          <>
                            <i className="fas fa-spinner fa-spin me-1" />
                            Creating...
                          </>
                        ) : (
                          <>
                            <i className="fas fa-plus me-1" />
                            Create Challenge
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => setCurrentView("challenges")}
                      >
                        <i className="fas fa-arrow-left me-1" />
                        Back to Challenges
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Challenges view */}
        {currentView === "challenges" && (
          <>
            <div className="row mb-4">
              <div className="col-md-8">
                <h1 className="h2 mb-3">Discover More Challenges</h1>
                <p className="text-muted">
                  Find and join exciting fitness challenges created by the
                  community
                </p>
              </div>
              <div className="col-md-4">
                <div className="card">
                  <div className="card-body p-3">
                    <WeatherWidget
                      user={user}
                      onLocationUpdate={handleLocationUpdate}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Filters */}
            <div className="row mb-4">
              <div className="col-md-6">
                <label className="form-label fw-bold">Filters:</label>
                <select
                  className="form-select"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="">All Challenges</option>
                  <option value="habit">Habit Based</option>
                  <option value="target">Goal Based</option>
                </select>
              </div>
            </div>

            {/* List */}
            <div className="row">
              <div className="col-12">
                <h3 className="h4 mb-3">Challenge List:</h3>

                {filtered.length ? (
                  <div className="row" id="challengeList">
                    {filtered.map((c) => (
                      <div key={c.id} className="col-md-6 col-lg-4 mb-4">
                        <div
                          className="card challenge-card h-100"
                          onClick={() => handleChallengeClick(c.id)}
                        >
                          <div className="card-body">
                            <div className="d-flex justify-content-between align-items-start mb-3">
                              <div>
                                <h5 className="card-title mb-1">{c.title}</h5>
                                <span
                                  className={`badge challenge-type-badge ${typeColor(
                                    c.challenge_type
                                  )}`}
                                >
                                  {c.challenge_type === 0
                                    ? "Habit Based"
                                    : "Goal Based"}
                                </span>
                              </div>
                              <div className="challenge-icon">
                                <i className={`${getIcon(c.exercise)} text-primary`} />
                              </div>
                            </div>

                            <div className="mb-3">
                              <div className="row text-muted small">
                                <div className="col-6">
                                  <strong>Category:</strong>
                                  <br />
                                  {c.exercise || "N/A"}
                                </div>
                                <div className="col-6">
                                  <strong>Duration:</strong>
                                  <br />
                                  {c.duration_weeks
                                    ? `${c.duration_weeks} weeks`
                                    : c.duration_days
                                    ? `${c.duration_days} days`
                                    : "N/A"}
                                </div>
                              </div>
                              <div className="mt-2">
                                <strong>Creator:</strong>{" "}
                                {c.creator.display_name}
                                <br />
                                <strong>Participants:</strong>{" "}
                                {c.participant_count}
                              </div>
                            </div>

                            {c.description && (
                              <p className="card-text text-muted small">
                                {c.description.length > 100
                                  ? c.description.slice(0, 100) + "…"
                                  : c.description}
                              </p>
                            )}

                            <div
                              className="d-flex gap-2 mt-auto"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {c.is_participating ? (
                                <button
                                  className="btn btn-outline-danger btn-sm flex-fill"
                                  onClick={() => handleLeaveChallenge(c.id)}
                                >
                                  <i className="fas fa-times me-1" />
                                  Leave Challenge
                                </button>
                              ) : (
                                <button
                                  className="btn btn-primary btn-sm flex-fill"
                                  onClick={() => handleJoinChallenge(c.id)}
                                >
                                  <i className="fas fa-plus me-1" />
                                  Join Challenge
                                </button>
                              )}
                              <button
                                className="btn btn-outline-secondary btn-sm"
                                onClick={() => handleChallengeClick(c.id)}
                              >
                                <i className="fas fa-eye me-1" />
                                View
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-5">
                    <i className="fas fa-trophy fa-3x text-muted mb-3" />
                    <h4 className="text-muted">No challenges available</h4>
                    <p className="text-muted">
                      Be the first to create a challenge!
                    </p>
                    <button
                      className="btn btn-primary"
                      onClick={() => setCurrentView("create")}
                    >
                      <i className="fas fa-plus me-1" />
                      Create Challenge
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* Admin view */}
        {currentView === "admin" && user && user.role === 'Admin' && (
          <div className="row">
            <div className="col-12">
              <AdminControls 
                onExerciseCreated={refreshExercises}
                onExerciseDeleted={refreshExercises}
                onChallengeDeleted={refreshChallenges}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
