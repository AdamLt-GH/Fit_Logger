// src/api/progress.js
const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const BASE = RAW.replace(/\/+$/, "");
const root = /\/api(\/|$)/.test(BASE) ? BASE : `${BASE}/api`;

function authHeader() {
  const t = localStorage.getItem("token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// Log progress for a challenge
export async function logProgress(challengeId, progressData) {
  try {
    const r = await fetch(`${root}/progress/create/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({
        challenge: challengeId,
        ...progressData
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to log progress" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

// Get progress entries for a user
export async function getProgressEntries(challengeId = null) {
  try {
    const url = challengeId 
      ? `${root}/progress/?challenge_id=${challengeId}`
      : `${root}/progress/`;
    const r = await fetch(url, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch progress entries" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

// Get user's challenges with progress
export async function getUserChallenges() {
  try {
    const r = await fetch(`${root}/user/challenges/`, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch user challenges" };
    const data = await r.json();
    return { status: "success", data: data.data }; // Extract data from our custom response format
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

// Get progress history for a specific challenge
export async function getProgressHistory(challengeId) {
  try {
    const r = await fetch(`${root}/challenge/${challengeId}/progress-history/`, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch progress history" };
    const data = await r.json();
    return { status: "success", data: data.data };
  } catch {
    return { status: "error", detail: "Network error" };
  }
}
