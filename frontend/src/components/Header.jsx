import React from "react";
import { Link, NavLink } from "react-router-dom";

export default function Header() {
  return (
    <header className="site-header">
      <div className="container">
        <Link className="brand" to="/">FitChallenge</Link>
        <nav className="nav-actions">
          <NavLink to="/login" className="btn">Log in</NavLink>
          <NavLink to="/register" className="btn btn-outline">Register</NavLink>
        </nav>
      </div>
    </header>
  );
}
