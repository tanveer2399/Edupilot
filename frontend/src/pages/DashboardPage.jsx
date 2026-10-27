import Icon from "../components/Icon.jsx";
import Sidebar from "../components/Sidebar.jsx";
import SummaryCard from "../components/SummaryCard.jsx";
import AcademicPage from "./AcademicPage.jsx";
import QuizGeneratorPage from "./QuizGeneratorPage.jsx";
import StudyAssistantPage from "./StudyAssistantPage.jsx";

function formatDueDate(value) {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatSemester(semester) {
  const suffix =
    semester % 100 >= 11 && semester % 100 <= 13
      ? "th"
      : { 1: "st", 2: "nd", 3: "rd" }[semester % 10] || "th";
  return `${semester}${suffix} Semester`;
}

function formatToday() {
  return new Intl.DateTimeFormat("en", {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
    .format(new Date())
    .toUpperCase();
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function ActivityIcon({ category }) {
  const icon =
    category === "assignment"
      ? "assignments"
      : category === "attendance"
        ? "attendance"
        : "marks";
  return (
    <span className={`activity-icon activity-${category}`}>
      <Icon name={icon} size={18} />
    </span>
  );
}

function SubjectAnalytics({ analytics }) {
  return (
    <section className="academic-panel subject-analytics-panel">
      <div className="panel-heading">
        <div>
          <h2>Subject insights</h2>
          <p>
            Descriptive summaries from recorded attendance and assessments.
            Attention flags use attendance below 75% or marks below 70%.
          </p>
        </div>
      </div>
      <div className="analytics-overview" aria-label="Overall academic summary">
        <span>{analytics.total_subjects} subjects tracked</span>
        <span>{analytics.subjects_with_attendance} with attendance records</span>
        <span>{analytics.subjects_with_marks} with mark records</span>
        <span>{analytics.subjects_needing_attention} flagged for review</span>
      </div>
      {analytics.subjects.length === 0 ? (
        <p className="academic-empty">
          Subject analytics will appear when attendance or marks are recorded.
        </p>
      ) : (
        <div className="academic-table-wrap">
          <table className="academic-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Attendance</th>
                <th>Marks</th>
                <th>Assessments</th>
                <th>Review notes</th>
              </tr>
            </thead>
            <tbody>
              {analytics.subjects.map((subject) => (
                <tr key={subject.subject}>
                  <td>{subject.subject}</td>
                  <td>
                    {subject.attendance_percentage === null
                      ? "No data"
                      : `${subject.attendance_percentage}% (${subject.classes_attended}/${subject.total_classes})`}
                  </td>
                  <td>
                    {subject.marks_percentage === null
                      ? "No data"
                      : `${subject.marks_percentage}%`}
                  </td>
                  <td>{subject.assessments_count}</td>
                  <td>
                    {subject.attention_reasons.length > 0 ? (
                      <ul className="analytics-attention-list">
                        {subject.attention_reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="analytics-note">
        Missing attendance or mark records are shown as “No data” and are
        excluded from percentages.
      </p>
    </section>
  );
}

function DashboardContent({ profile, dashboard }) {
  const upcomingCount = dashboard.upcoming_deadlines.filter(
    (deadline) => deadline.status !== "overdue",
  ).length;
  const overdueCount = dashboard.upcoming_deadlines.filter(
    (deadline) => deadline.status === "overdue",
  ).length;

  return (
    <>
      <section className="welcome-banner">
        <div className="welcome-copy">
          <span className="eyebrow">YOUR LEARNING SNAPSHOT</span>
          <h2>A little progress goes a long way.</h2>
          <p>Stay on top of your classes and keep your goals in sight.</p>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <span className="art-sun" />
          <span className="art-book art-book-back" />
          <span className="art-book art-book-front">
            <Icon name="cap" size={34} />
          </span>
          <span className="art-sparkle">✦</span>
        </div>
      </section>

      <section aria-label="Academic summary">
        <div className="summary-grid">
          <SummaryCard
            icon="attendance"
            label="Attendance"
            value={
              dashboard.attendance.percentage === null
                ? "No data"
                : `${dashboard.attendance.percentage}%`
            }
            detail={
              dashboard.attendance.total_classes
                ? `${dashboard.attendance.classes_attended} of ${dashboard.attendance.total_classes} classes attended`
                : "No attendance records yet"
            }
            accent="blue"
            progress={dashboard.attendance.percentage}
          />
          <SummaryCard
            icon="marks"
            label="Average marks"
            value={
              dashboard.average_marks.percentage === null
                ? "No data"
                : `${dashboard.average_marks.percentage}%`
            }
            detail={dashboard.average_marks.label}
            accent="green"
            progress={dashboard.average_marks.percentage}
          />
          <SummaryCard
            icon="assignments"
            label="Pending assignments"
            value={dashboard.pending_assignments}
            detail="Keep your coursework moving"
            accent="orange"
          />
          <SummaryCard
            icon="planner"
            label="Upcoming exams"
            value={
              dashboard.upcoming_exams === null
                ? "Not tracked"
                : dashboard.upcoming_exams
            }
            detail={
              dashboard.upcoming_exams === null
                ? "Exam schedules aren’t available yet"
                : "Plan ahead and feel prepared"
            }
            accent="purple"
          />
        </div>
      </section>

      <SubjectAnalytics analytics={dashboard.academic_analytics} />

      <div className="content-grid">
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <h2>Recent activity</h2>
              <p>A quick look at what’s happening in your courses</p>
            </div>
            <button className="text-action" type="button" disabled>
              View all <Icon name="arrow" size={16} />
            </button>
          </div>
          <ul className="activity-list">
            {dashboard.recent_activity.map((activity) => (
              <li className="activity-item" key={activity.id}>
                <ActivityIcon category={activity.category} />
                <div className="activity-copy">
                  <strong>{activity.title}</strong>
                  <p>{activity.detail}</p>
                </div>
                <time>{activity.time}</time>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel deadline-panel">
          <div className="panel-heading">
            <div>
              <h2>Upcoming deadlines</h2>
              <p>What’s next on your schedule</p>
            </div>
            <span className="deadline-count">
              {upcomingCount} upcoming
              {overdueCount > 0 ? ` · ${overdueCount} overdue` : ""}
            </span>
          </div>
          <ul className="deadline-list">
            {dashboard.upcoming_deadlines.map((deadline) => (
              <li className="deadline-item" key={deadline.id}>
                <span className={`deadline-date ${deadline.status}`}>
                  <strong>{formatDueDate(deadline.due_date).split(" ")[1]}</strong>
                  <small>{formatDueDate(deadline.due_date).split(" ")[0]}</small>
                </span>
                <div className="deadline-copy">
                  <strong>{deadline.title}</strong>
                  <p>{deadline.course}</p>
                </div>
                <span className={`deadline-status ${deadline.status}`}>
                  {deadline.status === "overdue"
                    ? "Overdue"
                    : deadline.status === "exam"
                      ? "Exam"
                      : "Due"}
                </span>
              </li>
            ))}
          </ul>
          <div className="deadline-note">
            <Icon name="clock" size={16} />
            <span>You’ve got this — one task at a time.</span>
          </div>
        </section>
      </div>

      <footer className="dashboard-footer">
        <span>Making progress, one day at a time.</span>
        <span>EduPilot · {profile.department}</span>
      </footer>
    </>
  );
}

export default function DashboardPage({
  profile,
  dashboard,
  activePage,
  onNavigate,
  academicData,
  academicLoading,
  academicError,
  onAcademicRetry,
  sendStudyAssistantMessage,
  onLogout,
}) {
  const pageHeading = {
    Attendance: "Review your class attendance and subject summaries.",
    Marks: "Track your results across subjects and assessments.",
    Assignments: "Keep track of upcoming and overdue coursework.",
    Timetable: "See your weekly classes in weekday and time order.",
    "Study Assistant": "Ask questions and get clear, step-by-step explanations.",
    "Study Planner": "Generate a practice quiz from a topic or your study notes.",
  };

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />
      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>My learning</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{activePage}</strong>
          </div>
          <div className="student-menu">
            <span className="avatar">{profile.full_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</span>
            <div className="student-menu-name">
              <strong>{profile.full_name}</strong>
              <small>{formatSemester(profile.semester)}</small>
            </div>
            <button className="logout-button" type="button" onClick={onLogout}>
              Sign out
            </button>
          </div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="page-date">{formatToday()}</p>
              {activePage === "Dashboard" ? (
                <>
                  <h1>{getGreeting()}, {profile.full_name.split(" ")[0]} <span>✦</span></h1>
                  <p className="page-subtitle">
                    Here’s what’s happening with your studies today.
                  </p>
                </>
              ) : (
                <>
                  <h1>{activePage}</h1>
                  <p className="page-subtitle">{pageHeading[activePage]}</p>
                </>
              )}
            </div>
            <div className="semester-pill">
              <Icon name="cap" size={17} />
              {formatSemester(profile.semester)}
            </div>
          </section>

          {activePage === "Dashboard" ? (
            <DashboardContent profile={profile} dashboard={dashboard} />
          ) : activePage === "Study Assistant" ? (
            <StudyAssistantPage sendMessage={sendStudyAssistantMessage} />
          ) : activePage === "Study Planner" ? (
            <QuizGeneratorPage />
          ) : (
            <AcademicPage
              page={activePage}
              data={academicData}
              loading={academicLoading}
              error={academicError}
              onRetry={onAcademicRetry}
            />
          )}
        </div>
      </main>
    </div>
  );
}
