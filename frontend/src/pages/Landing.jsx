// src/pages/Landing.jsx
import React, { useEffect } from "react";
import { Link } from "react-router-dom";

export default function Landing() {
  // Simple reveal-on-scroll
  useEffect(() => {
    const els = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            // once visible, stop observing (keeps it visible)
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -10% 0px" }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <main className="landing">
      {/* HERO */}
      <section className="hero section reveal">
        <div className="hero__content">
          <h1>
            Build habits. <span className="accent">Level up.</span> Together.
          </h1>
          <p className="lede">
            Create fitness challenges, join the community, log your progress,
            and earn acknowledgements for completing goals.
          </p>

          <div className="cta-row">
            <Link to="/register" className="btn btn-primary">Get started</Link>
            <Link to="/login" className="btn btn-ghost">I already have an account</Link>
          </div>
        </div>
      </section>

      {/* FEATURE GRID */}
      <section className="section reveal" style={{ transitionDelay: "80ms" }}>
        <h2 className="section-title">What you can do</h2>
        <div className="features">
          <article className="card">
            <div className="card__icon">🏁</div>
            <h3>Create Challenges</h3>
            <p>
              Set up habit or target-based challenges with clear rules and time
              frames. Make them public so others can join.
            </p>
          </article>

          <article className="card" style={{ transitionDelay: "60ms" }}>
            <div className="card__icon">🤝</div>
            <h3>Join & Compete</h3>
            <p>
              Discover challenges from the community and team up with
              like-minded people to stay accountable.
            </p>
          </article>

          <article className="card" style={{ transitionDelay: "120ms" }}>
            <div className="card__icon">📈</div>
            <h3>Log Progress</h3>
            <p>
              Track sessions and effort directly in the app. Your timeline
              makes improvement visible and motivating.
            </p>
          </article>

          <article className="card" style={{ transitionDelay: "180ms" }}>
            <div className="card__icon">🏅</div>
            <h3>Earn Acknowledgements</h3>
            <p>
              Finish a challenge to unlock an acknowledgement—proof you showed
              up and did the work.
            </p>
          </article>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="section reveal" style={{ transitionDelay: "120ms" }}>
        <h2 className="section-title">How it works</h2>
        <ol className="steps">
          <li className="step">
            <span className="step__num">1</span>
            <div>
              <h4>Create or find a challenge</h4>
              <p>Pick a habit (e.g., daily push-ups) or a target (e.g., 50 km in 14 days).</p>
            </div>
          </li>
          <li className="step">
            <span className="step__num">2</span>
            <div>
              <h4>Invite friends or join the community</h4>
              <p>Public challenges help you stay consistent, thanks to friendly accountability.</p>
            </div>
          </li>
          <li className="step">
            <span className="step__num">3</span>
            <div>
              <h4>Log, track, complete</h4>
              <p>Record progress, hit your threshold, and earn your acknowledgement.</p>
            </div>
          </li>
        </ol>
      </section>

      {/* FINAL CTA */}
      <section className="section section--cta reveal" style={{ transitionDelay: "160ms" }}>
        <h2 className="section-title">Ready to move?</h2>
        <p className="lede">
          Join free, start a challenge in seconds, and make momentum a habit.
        </p>
        <div className="cta-row">
          <Link to="/register" className="btn btn-primary">Create your first challenge</Link>
          <Link to="/login" className="btn btn-ghost">Log in</Link>
        </div>
      </section>
    </main>
  );
}
