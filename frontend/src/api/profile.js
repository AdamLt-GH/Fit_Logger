// src/api/profile.js
const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const BASE = RAW.replace(/\/+$/, "");
const root = /\/api(\/|$)/.test(BASE) ? BASE : `${BASE}/api`;

function authHeader() {
  const t = localStorage.getItem("token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function getMyProfile() {
  try {
    const r = await fetch(`${root}/profile/me/`, { headers: { ...authHeader() } });
    if (!r.ok) return { status: "error", detail: "Failed to fetch profile" };
    return await r.json();
  } catch {
    return { status: "error", detail: "Network error" };
  }
}

export async function updateMyProfile(formData) {
  try {
    const r = await fetch(`${root}/profile/me/`, {
      method: "PUT",
      headers: { ...authHeader() }, // don't set Content-Type for FormData
      body: formData,
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Update failed", errors: data };
    return { status: "success", ...data };
  } catch {
    return { status: "error", message: "Network error" };
  }
}

export async function changePassword(current_password, new_password) {
  try {
    const r = await fetch(`${root}/change-password/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ current_password, new_password }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { status: "error", message: data?.message || "Password change failed" };
    return { status: "success" };
  } catch {
    return { status: "error", message: "Network error" };
  }
}
