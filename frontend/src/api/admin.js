// src/api/admin.js
const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const BASE = RAW.replace(/\/+$/, "");
const root = /\/api(\/|$)/.test(BASE) ? BASE : `${BASE}/api`;

function authHeader() {
  const t = localStorage.getItem("token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// User search and management
export async function searchUsers(query = '', page = 1, pageSize = 20) {
  try {
    const url = `${root}/admin/users/search/?q=${encodeURIComponent(query)}&page=${page}&page_size=${pageSize}`;
    const r = await fetch(url, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to search users" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

export async function getUserDetails(userId) {
  try {
    const r = await fetch(`${root}/admin/users/${userId}/`, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch user details" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

// Exercise management
export async function getExercises() {
  try {
    const r = await fetch(`${root}/admin/exercises/`, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch exercises" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

export async function createExercise(exerciseData) {
  try {
    const r = await fetch(`${root}/admin/exercises/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify(exerciseData),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to create exercise" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

export async function updateExercise(exerciseId, exerciseData) {
  try {
    const r = await fetch(`${root}/admin/exercises/${exerciseId}/`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify(exerciseData),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to update exercise" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

export async function deleteExercise(exerciseId) {
  try {
    const r = await fetch(`${root}/admin/exercises/${exerciseId}/`, {
      method: "DELETE",
      headers: { ...authHeader() },
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to delete exercise" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

// User deletion
export async function deleteUser(userId) {
  try {
    const r = await fetch(`${root}/admin/users/${userId}/`, {
      method: "DELETE",
      headers: { ...authHeader() },
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to delete user" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

// Challenge management
export async function searchChallenges(query = '', page = 1, pageSize = 20) {
  try {
    const url = `${root}/admin/challenges/?q=${encodeURIComponent(query)}&page=${page}&page_size=${pageSize}`;
    const r = await fetch(url, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to search challenges" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

export async function deleteChallenge(challengeId) {
  try {
    const r = await fetch(`${root}/admin/challenges/${challengeId}/`, {
      method: "DELETE",
      headers: { ...authHeader() },
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Failed to delete challenge" };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}
