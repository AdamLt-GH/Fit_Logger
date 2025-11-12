import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";

export default function ResetPassword() {
  const params = new URLSearchParams(window.location.search);
  const token = useMemo(() => params.get("token") || "", [params]);

  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
  const BASE = RAW.replace(/\/+$/, "");
  const root = /\/api(\/|$)/.test(BASE) ? BASE : `${BASE}/api`;

  async function onSubmit(e) {
    e.preventDefault();
    setMsg(""); setErr("");

    if (!token) { setErr("Missing reset token"); return; }
    if (password !== password2) { setErr("Passwords do not match"); return; }

    try {
      const r = await fetch(`${root}/password-reset/confirm/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || data?.status === "error") {
        setErr(data?.message || "Reset failed");
        return;
      }
      setMsg("Password changed. You can now log in.");
    } catch {
      setErr("Network error");
    }
  }

  return (
    <form onSubmit={onSubmit} className="form-container">
      <h2>Set New Password</h2>
      <input
        type="password"
        placeholder="New password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Confirm new password"
        value={password2}
        onChange={(e) => setPassword2(e.target.value)}
        required
      />
      <button type="submit">Change password</button>
      {err && <p className="form-msg error">{err}</p>}
      {msg && <p className="form-msg ok">{msg}</p>}
      <p style={{ marginTop: 8 }}>
        <Link className="link" to="/login">Back to login</Link>
      </p>
    </form>
  );
}
