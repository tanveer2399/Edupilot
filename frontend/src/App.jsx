import { useEffect, useState } from "react";
import DashboardPage from "./pages/DashboardPage.jsx";
import FacultyDashboard from "./pages/FacultyDashboard.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import StudentSetupPage from "./pages/StudentSetupPage.jsx";
import {
  getCurrentUser,
  getAssignments,
  getAttendance,
  getAttendanceSummary,
  getDashboard,
  getMarks,
  getStudentProfile,
  login,
  logout,
  sendStudyAssistantMessage,
  getTimetable,
} from "./services/api.js";
import "./App.css";

const initialStudentSetupToken =
  window.location.pathname === "/student-setup"
    ? new URLSearchParams(window.location.search).get("token") ?? ""
    : "";
if (initialStudentSetupToken) {
  window.history.replaceState({}, "", "/student-setup");
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [activePage, setActivePage] = useState("Dashboard");
  const [academicData, setAcademicData] = useState(null);
  const [academicLoading, setAcademicLoading] = useState(false);
  const [academicError, setAcademicError] = useState("");
  const [academicAttempt, setAcademicAttempt] = useState(0);
  const isStudentSetup = window.location.pathname === "/student-setup";

  useEffect(() => {
    let isCurrent = true;

    if (isStudentSetup) {
      setAuthChecking(false);
      return () => {
        isCurrent = false;
      };
    }

    async function restoreSession() {
      try {
        const currentUser = await getCurrentUser();
        if (isCurrent) {
          setUser(currentUser);
        }
      } catch (loadError) {
        if (isCurrent && loadError.status !== 401) {
          setAuthError(loadError.message);
        }
      } finally {
        if (isCurrent) {
          setAuthChecking(false);
        }
      }
    }

    restoreSession();
    return () => {
      isCurrent = false;
    };
  }, [isStudentSetup]);

  useEffect(() => {
    if (!user || user.role !== "student") {
      setData(null);
      return undefined;
    }

    let isCurrent = true;

    async function loadDashboard() {
      setError("");
      try {
        const [profile, dashboard] = await Promise.all([
          getStudentProfile(),
          getDashboard(),
        ]);
        if (isCurrent) {
          setData({ profile, dashboard });
        }
      } catch (loadError) {
        if (isCurrent) {
          setError(loadError.message);
        }
      }
    }

    loadDashboard();
    return () => {
      isCurrent = false;
    };
  }, [attempt, user]);

  useEffect(() => {
    if (
      activePage === "Dashboard" ||
      activePage === "Study Assistant" ||
      activePage === "Study Planner"
    ) {
      return undefined;
    }

    let isCurrent = true;

    async function loadAcademicData() {
      setAcademicData(null);
      setAcademicError("");
      setAcademicLoading(true);
      try {
        let result;
        if (activePage === "Attendance") {
          const [records, summary] = await Promise.all([
            getAttendance(),
            getAttendanceSummary(),
          ]);
          result = { records, summary };
        } else if (activePage === "Marks") {
          result = await getMarks();
        } else if (activePage === "Assignments") {
          result = await getAssignments();
        } else if (activePage === "Timetable") {
          result = await getTimetable();
        } else {
          return;
        }
        if (isCurrent) {
          setAcademicData(result);
        }
      } catch (loadError) {
        if (isCurrent) {
          setAcademicError(loadError.message);
        }
      } finally {
        if (isCurrent) {
          setAcademicLoading(false);
        }
      }
    }

    loadAcademicData();
    return () => {
      isCurrent = false;
    };
  }, [activePage, academicAttempt]);

  if (isStudentSetup) {
    return <StudentSetupPage token={initialStudentSetupToken} />;
  }

  async function handleLogin(credentials) {
    setAuthLoading(true);
    setAuthError("");
    try {
      const authenticatedUser = await login(credentials);
      setUser(authenticatedUser);
      setData(null);
      setAttempt((value) => value + 1);
    } catch (loginError) {
      setAuthError(loginError.message);
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    setAuthError("");
    try {
      await logout();
      setUser(null);
      setData(null);
      setActivePage("Dashboard");
    } catch (logoutError) {
      setAuthError(logoutError.message);
    }
  }

  function navigateToPage(page) {
    setActivePage(page);
    setAcademicData(null);
    setAcademicError("");
    setAcademicLoading(page !== "Dashboard");
  }

  if (authChecking) {
    return (
      <main className="status-screen">
        <div className="status-card" role="status" aria-live="polite">
          <span className="loading-spinner" />
          <h1>Checking your session…</h1>
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <LoginPage
        onLogin={handleLogin}
        error={authError}
        loading={authLoading}
      />
    );
  }

  if (user.role === "faculty") {
    return <FacultyDashboard user={user} onLogout={handleLogout} />;
  }

  if (error) {
    return (
      <main className="status-screen">
        <div className="status-card" role="alert">
          <span className="status-mark error-mark">!</span>
          <p className="eyebrow">CONNECTION ISSUE</p>
          <h1>We couldn’t load your dashboard.</h1>
          <p>{error}</p>
          <button className="primary-button" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
          <small>Make sure the EduPilot backend is running at 127.0.0.1:8000.</small>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="status-screen">
        <div className="status-card" role="status" aria-live="polite">
          <span className="loading-spinner" />
          <h1>Getting things ready…</h1>
          <p>Loading your student profile and academic snapshot.</p>
        </div>
      </main>
    );
  }

  return (
    <DashboardPage
      profile={data.profile}
      dashboard={data.dashboard}
      activePage={activePage}
      onNavigate={navigateToPage}
      academicData={academicData}
      academicLoading={academicLoading}
      academicError={academicError}
      onAcademicRetry={() => setAcademicAttempt((value) => value + 1)}
      sendStudyAssistantMessage={sendStudyAssistantMessage}
      onLogout={handleLogout}
    />
  );
}
