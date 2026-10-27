import { useState } from "react";
import { completeStudentPasswordSetup } from "../services/api.js";

export default function StudentSetupPage({ token }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [complete, setComplete] = useState(false);
  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    if (!token) {
      setError("This password setup link is missing its token.");
      return;
    }
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setSaving(true);
    try {
      await completeStudentPasswordSetup(token, password);
      window.history.replaceState({}, "", "/");
      setComplete(true);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="status-screen login-screen">
      <form className="status-card login-card" onSubmit={handleSubmit}>
        <p className="eyebrow">EDUPILOT STUDENT ACCOUNT</p>
        {complete ? (
          <>
            <h1>Password set</h1>
            <p>Your student login is ready. Sign in using your student ID or email.</p>
            <a className="primary-button login-submit" href="/">Go to sign in</a>
          </>
        ) : (
          <>
            <h1>Set your password</h1>
            <p>Choose a password with at least 12 characters. This link can only be used once.</p>
            <label className="login-field">
              <span>New password</span>
              <input
                autoComplete="new-password"
                type="password"
                minLength={12}
                maxLength={128}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label className="login-field">
              <span>Confirm password</span>
              <input
                autoComplete="new-password"
                type="password"
                minLength={12}
                maxLength={128}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
            {error && <p className="quiz-error" role="alert">{error}</p>}
            <button
              className="primary-button login-submit"
              type="submit"
              disabled={saving || !password || !confirmation}
            >
              {saving ? "Saving password…" : "Set password"}
            </button>
          </>
        )}
      </form>
    </main>
  );
}
