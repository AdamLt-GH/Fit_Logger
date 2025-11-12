import React from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";

import Header from "./components/Header";
import Landing from "./pages/Landing";
import Login from "./components/Login";
import Register from "./components/Register";
import ForgotPassword from "./components/ForgotPassword";
import ResetPassword from "./components/ResetPassword";
import Profile from "./pages/Profile";
import Dashboard from "./components/Dashboard";
import ChallengeDetail from "./components/ChallengeDetail";
import "./styles/App.css";

// Simple auth guard
function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  return token ? children : <Navigate to="/login" replace />;
}

// Public layout -> shows global header and standard page padding
function PublicLayout() {
  return (
    <>
      <Header />
      <div className="page-container">
        <Outlet />
      </div>
    </>
  );
}

// Private layout -> NO header, full-bleed shell styled like landing
function PrivateLayout() {
  return (
    <div className="private-shell">
      <Outlet />
    </div>
  );
}

export default function App() {
  const handleLogout = () => {
    localStorage.removeItem("token");
    window.location.href = "/login";
  };

  return (
    <Routes>
      {/* PUBLIC */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
      </Route>

      {/* PRIVATE */}
      <Route
        element={
          <RequireAuth>
            <PrivateLayout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<Dashboard onLogout={handleLogout} />} />
        <Route path="/profile" element={<Profile onLogout={handleLogout} />} />
        <Route path="/challenge/:challengeId" element={<ChallengeDetail />} />
      </Route>

      {/* catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
