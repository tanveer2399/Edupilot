import { useState } from "react";

export default function LoginPage({ onLogin, error, loading }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(event) {
    event.preventDefault();
    await onLogin({ email: email.trim(), password });
  }

  return (
    <main className="status-screen login-screen">
      <form className="status-card login-card" onSubmit={handleSubmit}>
        <p className="eyebrow">EDUPILOT PORTAL</p>
        <h1>Welcome back</h1>
        <p>Sign in with your college account to continue.</p>
        <label className="login-field">
          <span>College email or student ID</span>
          <input
            autoComplete="username"
            type="text"
            required
            maxLength={255}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className="login-field">
          <span>Password</span>
          <input
            autoComplete="current-password"
            type="password"
            required
            maxLength={128}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error && <p className="quiz-error" role="alert">{error}</p>}
        <button
          className="primary-button login-submit"
          type="submit"
          disabled={loading || !email.trim() || !password}
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
