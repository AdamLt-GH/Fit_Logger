// Works whether VITE_API_BASE_URL is "http://127.0.0.1:8000" OR "http://127.0.0.1:8000/api"
const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
// strip trailing slashes
const BASE = RAW.replace(/\/+$/, "");

// If BASE already has /api at the end, we won't add another.
// Callers should pass "login/" or "register/" (NO leading "api/").
function apiUrl(path) {
  const hasApi = /\/api(\/|$)/.test(BASE);
  const root = hasApi ? BASE : `${BASE}/api`;
  const clean = path.replace(/^\/+/, "").replace(/^api\/+/, ""); // avoid /api/api
  const url = `${root}/${clean}`;
  // helpful in DevTools
  console.log("[auth] URL ->", url);
  return url;
}

async function post(path, payload) {
  try {
    const r = await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));

    if (!r.ok) {
      // backend uses message/detail/errors
      const msg = data?.message || data?.detail || "Request failed";
      return { status: "error", message: msg, errors: data };
    }

    // REGISTER returns {status, data:{email, access, refresh}}
    // LOGIN returns {status, access, refresh}
    const src = data?.data || data || {};
    return {
      status: data?.status || "success",
      email: src.email,
      access: src.access,
      refresh: src.refresh,
    };
  } catch (e) {
    console.error("[auth] fetch error", e);
    return { status: "error", message: "Network error or server unavailable" };
  }
}

export const login = ({ email, password }) => post("login/", { email, password });
export const register = ({ email, display_name, password, password2 }) =>
  post("register/", { email, display_name, password, password2 });

export const saveToken = (t) => t && localStorage.setItem("token", t);
export const getToken = () => localStorage.getItem("token");
export const clearToken = () => localStorage.removeItem("token");
