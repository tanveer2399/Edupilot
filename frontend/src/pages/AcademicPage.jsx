import { useState } from "react";
import Icon from "../components/Icon.jsx";
import { getAssignment } from "../services/api.js";

function formatDate(value) {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function formatTime(value) {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(`1970-01-01T${value}`));
}

function StatusBadge({ value }) {
  return <span className={`status-badge ${value}`}>{value}</span>;
}

function EmptyState({ message }) {
  return <p className="academic-empty">{message}</p>;
}

function AttendanceContent({ data }) {
  if (data.records.length === 0) {
    return <EmptyState message="No attendance records have been added yet." />;
  }

  return (
    <>
      <section className="academic-summary" aria-label="Overall attendance">
        <div className="academic-summary-value">{data.summary.percentage}%</div>
        <div>
          <strong>Overall attendance</strong>
          <p>
            {data.summary.classes_attended} of {data.summary.total_classes} classes
            attended (present or late)
          </p>
        </div>
      </section>
      <section className="academic-panel">
        <h2>Subject-wise attendance</h2>
        <div className="academic-table-wrap">
          <table className="academic-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Present</th>
                <th>Late</th>
                <th>Absent</th>
                <th>Attendance</th>
              </tr>
            </thead>
            <tbody>
              {data.summary.subjects.map((subject) => (
                <tr key={subject.subject}>
                  <td>{subject.subject}</td>
                  <td>{subject.present}</td>
                  <td>{subject.late}</td>
                  <td>{subject.absent}</td>
                  <td>{subject.percentage}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="academic-panel">
        <h2>Attendance records</h2>
        <div className="academic-table-wrap">
          <table className="academic-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Remarks</th>
              </tr>
            </thead>
            <tbody>
              {data.records.map((record) => (
                <tr key={record.id}>
                  <td>{formatDate(record.class_date)}</td>
                  <td>{record.subject}</td>
                  <td><StatusBadge value={record.status} /></td>
                  <td>{record.remarks || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function MarksContent({ data }) {
  if (data.length === 0) {
    return <EmptyState message="No marks have been added yet." />;
  }

  return (
    <section className="academic-panel">
      <h2>Assessment results</h2>
      <div className="academic-table-wrap">
        <table className="academic-table">
          <thead>
            <tr>
              <th>Subject</th>
              <th>Assessment</th>
              <th>Date</th>
              <th>Marks</th>
              <th>Percentage</th>
            </tr>
          </thead>
          <tbody>
            {data.map((mark) => (
              <tr key={mark.id}>
                <td>{mark.subject}</td>
                <td>{mark.assessment_name}</td>
                <td>{mark.assessment_date ? formatDate(mark.assessment_date) : "—"}</td>
                <td>{mark.marks_obtained} / {mark.maximum_marks}</td>
                <td>{mark.percentage}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AssignmentsContent({ data }) {
  const [selectedId, setSelectedId] = useState(null);
  const [details, setDetails] = useState(null);
  const [loadingId, setLoadingId] = useState(null);
  const [error, setError] = useState("");

  async function toggleDetails(assignment) {
    if (selectedId === assignment.id) {
      setSelectedId(null);
      setDetails(null);
      setError("");
      return;
    }

    setSelectedId(assignment.id);
    setDetails(null);
    setError("");
    setLoadingId(assignment.id);
    try {
      setDetails(await getAssignment(assignment.id));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoadingId(null);
    }
  }

  if (data.length === 0) {
    return <EmptyState message="No assignments have been added yet." />;
  }

  return (
    <section className="academic-panel">
      <h2>Coursework</h2>
      <ul className="assignment-list">
        {data.map((assignment) => (
          <li className="assignment-item" key={assignment.id}>
            <div className="assignment-main">
              <div>
                <span className="assignment-subject">{assignment.subject}</span>
                <h3>{assignment.title}</h3>
              </div>
              <div className="assignment-meta">
                <span>Due {formatDate(assignment.due_date)}</span>
                <StatusBadge value={assignment.status} />
              </div>
            </div>
            <button
              className="assignment-details-button"
              type="button"
              aria-expanded={selectedId === assignment.id}
              onClick={() => toggleDetails(assignment)}
            >
              {selectedId === assignment.id ? "Hide details" : "View details"}
              <Icon name="arrow" size={15} />
            </button>
            {selectedId === assignment.id && (
              <div className="assignment-details">
                {loadingId === assignment.id && <p role="status">Loading details…</p>}
                {error && <p className="academic-error" role="alert">{error}</p>}
                {details?.id === assignment.id && (
                  <p>{details.description || "No additional instructions provided."}</p>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function TimetableContent({ data }) {
  if (data.length === 0) {
    return <EmptyState message="No classes have been added to the timetable yet." />;
  }

  const days = data.reduce((groups, entry) => {
    if (!groups[entry.day_of_week]) {
      groups[entry.day_of_week] = [];
    }
    groups[entry.day_of_week].push(entry);
    return groups;
  }, {});

  return (
    <div className="timetable-list">
      {Object.entries(days).map(([day, entries]) => (
        <section className="academic-panel" key={day}>
          <h2>{day}</h2>
          <ul className="timetable-day">
            {entries.map((entry) => (
              <li key={entry.id}>
                <time>
                  {formatTime(entry.start_time)} – {formatTime(entry.end_time)}
                </time>
                <strong>{entry.subject}</strong>
                <span>{entry.location || "Location not set"}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export default function AcademicPage({ page, data, loading, error, onRetry }) {
  if (loading) {
    return (
      <div className="academic-state" role="status" aria-live="polite">
        <span className="loading-spinner" />
        <p>Loading {page.toLowerCase()}…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="academic-state" role="alert">
        <p>We couldn’t load {page.toLowerCase()}: {error}</p>
        <button className="primary-button" type="button" onClick={onRetry}>
          Try again
        </button>
      </div>
    );
  }

  if (data === null) {
    return <EmptyState message="No information is available right now." />;
  }

  if (page === "Attendance") {
    return <AttendanceContent data={data} />;
  }
  if (page === "Marks") {
    return <MarksContent data={data} />;
  }
  if (page === "Assignments") {
    return <AssignmentsContent data={data} />;
  }
  return <TimetableContent data={data} />;
}
