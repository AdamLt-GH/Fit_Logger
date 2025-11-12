import React, { useState } from "react";
import { Link } from "react-router-dom";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const RAW = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
  const BASE = RAW.replace(/\/+$/, "");
  const root = /\/api(\/|$)/.test(BASE) ? BASE : `${BASE}/api`;

  async function onSubmit(e) {
    e.preventDefault();
    setMsg(""); setErr("");

    try {
      const r = await fetch(`${root}/password-reset/request/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok || data?.status === "error") {
        setErr(data?.message || "Request failed");
        return;
      }
      // Success — show message with reset link
      const message = data?.data?.message || data?.message || "If that email exists, a reset link was created.";
      setMsg(message);
    } catch {
      setErr("Network error");
    }
  }

  return (
    <form onSubmit={onSubmit} className="form-container">
      <h2>Forgot Password</h2>
      <input
        type="email"
        placeholder="Enter your account email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <button type="submit">Send reset link</button>
      {err && <p className="form-msg error">{err}</p>}
      {msg && <p className="form-msg ok" style={{ whiteSpace: "pre-wrap" }}>{msg}</p>}
      <p style={{ marginTop: 8 }}>
        <Link className="link" to="/login">Back to login</Link>
      </p>
    </form>
  );
}
