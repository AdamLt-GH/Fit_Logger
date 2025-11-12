import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../api/auth";
import "../styles/App.css";

export default function Login() {
  const [form, setForm] = useState({ email: "", password: "" });
  const [message, setMessage] = useState("");
  const navigate = useNavigate();

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(form.email)) {
      setMessage("Please enter a valid email address");
      return;
    }

    try {
      const res = await login(form);
      // normalize token whether it's top-level or under data
      const token = res?.access || res?.data?.access;

      if (res?.status === "success" && token) {
        localStorage.setItem("token", token);
        navigate("/dashboard"); // <-- go to dashboard
      } else {
        setMessage(
          res?.errors
            ? Object.values(res.errors).join(" ")
            : res?.message || "Login failed"
        );
      }
    } catch {
      setMessage("Network error or server unavailable");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="form-container">
      <h2>Login</h2>
      <input
        name="email"
        type="email"
        placeholder="Email"
        value={form.email}
        onChange={handleChange}
        required
      />
      <input
        name="password"
        type="password"
        placeholder="Password"
        value={form.password}
        onChange={handleChange}
        required
      />
      <button type="submit">Login</button>
      <p>{message}</p>
      <p>
        Don&apos;t have an account?{" "}
        <Link to="/register" className="link">
          Register here
        </Link>
      </p>
      <p>
        <Link to="/forgot-password" className="link">
          Forgot your password?
        </Link>
      </p>
    </form>
  );
}
