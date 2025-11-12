import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../api/auth";

export default function Register() {
  const [form, setForm] = useState({
    email: "",
    display_name: "",
    password: "",
    password2: "",
  });
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
    if (form.password !== form.password2) {
      setMessage("Passwords do not match");
      return;
    }
    if (form.password.length < 8) {
      setMessage("Password must be at least 8 characters long");
      return;
    }

    try {
      const res = await register(form);
      const token = res?.data?.access || res?.access;

      if (res?.status === "success" && token) {
        localStorage.setItem("token", token);
        navigate("/dashboard"); // <-- go to dashboard (not profile)
      } else {
        setMessage(
          res?.errors
            ? Object.values(res.errors).join(" ")
            : res?.message || "Registration failed"
        );
      }
    } catch {
      setMessage("Network error or server unavailable");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="form-container">
      <h2>Register</h2>
      <input
        name="email"
        type="email"
        placeholder="Email"
        value={form.email}
        onChange={handleChange}
        required
      />
      <input
        name="display_name"
        placeholder="Display Name"
        value={form.display_name}
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
      <input
        name="password2"
        type="password"
        placeholder="Confirm Password"
        value={form.password2}
        onChange={handleChange}
        required
      />
      <button type="submit">Register</button>
      <p>{message}</p>
      <p>
        Already have an account?{" "}
        <Link to="/login" className="link">
          Login here
        </Link>
      </p>
    </form>
  );
}
