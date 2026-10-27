import { useEffect, useMemo, useState } from "react";
import {
  commitFacultyImport,
  createFacultyRecord,
  getFacultyImportTypes,
  getFacultyAcademicData,
  previewFacultyImport,
  provisionStudentAccounts,
  updateFacultyStudent,
} from "../services/api.js";
import "./FacultyDashboard.css";

const navigation = [
  "Dashboard",
  "Students",
  "Academic Structure",
  "Subjects & Credits",
  "Timetable",
  "Academic Calendar",
  "Attendance",
  "Marks",
  "Assignments",
  "Data Import",
];

const structureResources = [
  { resource: "academic-years", label: "Academic years" },
  { resource: "departments", label: "Departments" },
  { resource: "branches", label: "Branches" },
  { resource: "semesters", label: "Semesters" },
  { resource: "sections", label: "Class sections" },
];

const laterModules = new Set([
  "Timetable",
  "Academic Calendar",
  "Attendance",
  "Marks",
  "Assignments",
]);

function fieldsFor(page, resource, data) {
  if (page === "Students") {
    return [
      { name: "student_id", label: "College student ID", required: true },
      { name: "full_name", label: "Full name", required: true },
      { name: "email", label: "College email", type: "email", required: true },
      {
        name: "section_id",
        label: "Class section",
        type: "select",
        options: data.sections.map((section) => ({
          value: section.id,
          label: `Section ${section.name} · ${data.branches.find((item) => item.id === section.branch_id)?.name ?? "Branch"} · ${data.academicYears.find((item) => item.id === section.academic_year_id)?.name ?? "Academic year"}`,
        })),
        required: true,
      },
    ];
  }
  if (page === "Subjects & Credits") {
    return [
      {
        name: "branch_id",
        label: "Branch",
        type: "select",
        options: data.branches.map((branch) => ({
          value: branch.id,
          label: `${branch.name} (${branch.code})`,
        })),
        required: true,
      },
      {
        name: "semester_id",
        label: "Semester",
        type: "select",
        options: data.semesters.map((semester) => ({
          value: semester.id,
          label: `${semester.name} · ${data.academicYears.find((year) => year.id === semester.academic_year_id)?.name ?? ""}`,
        })),
        required: true,
      },
      { name: "code", label: "Subject code", required: true },
      { name: "name", label: "Subject name", required: true },
      {
        name: "credits",
        label: "Credits",
        type: "number",
        min: "0.1",
        step: "0.1",
        required: true,
      },
    ];
  }
  if (resource === "academic-years") {
    return [
      { name: "name", label: "Academic year name", placeholder: "2026-27", required: true },
      { name: "start_date", label: "Start date", type: "date", required: true },
      { name: "end_date", label: "End date", type: "date", required: true },
    ];
  }
  if (resource === "departments") {
    return [
      { name: "code", label: "Department code", required: true },
      { name: "name", label: "Department name", required: true },
    ];
  }
  if (resource === "branches") {
    return [
      {
        name: "department_id",
        label: "Department",
        type: "select",
        options: data.departments.map((department) => ({
          value: department.id,
          label: `${department.name} (${department.code})`,
        })),
        required: true,
      },
      { name: "code", label: "Branch code", required: true },
      { name: "name", label: "Branch name", required: true },
    ];
  }
  if (resource === "semesters") {
    return [
      {
        name: "academic_year_id",
        label: "Academic year",
        type: "select",
        options: data.academicYears.map((year) => ({
          value: year.id,
          label: year.name,
        })),
        required: true,
      },
      { name: "number", label: "Semester number", type: "number", min: "1", step: "1", required: true },
      { name: "name", label: "Semester name", placeholder: "Semester 1", required: true },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "end_date", label: "End date", type: "date" },
    ];
  }
  return [
    {
      name: "branch_id",
      label: "Branch",
      type: "select",
      options: data.branches.map((branch) => ({
        value: branch.id,
        label: `${branch.name} (${branch.code})`,
      })),
      required: true,
    },
    {
      name: "academic_year_id",
      label: "Academic year",
      type: "select",
      options: data.academicYears.map((year) => ({
        value: year.id,
        label: year.name,
      })),
      required: true,
    },
    {
      name: "semester_id",
      label: "Semester",
      type: "select",
      options: data.semesters.map((semester) => ({
        value: semester.id,
        label: semester.name,
      })),
      required: true,
    },
    { name: "name", label: "Section name", placeholder: "A", required: true },
  ];
}

function listFor(page, resource, data) {
  if (page === "Students") return data.students;
  if (page === "Subjects & Credits") return data.subjects;
  if (resource === "academic-years") return data.academicYears;
  if (resource === "departments") return data.departments;
  if (resource === "branches") return data.branches;
  if (resource === "semesters") return data.semesters;
  return data.sections;
}

function columnsFor(page, resource) {
  if (page === "Students") {
    return [
      ["student_id", "Student ID"],
      ["full_name", "Name"],
      ["email", "Email"],
      ["section_name", "Section"],
      ["branch_name", "Branch"],
      ["academic_year", "Academic year"],
      ["semester_name", "Semester"],
    ];
  }
  if (page === "Subjects & Credits") {
    return [
      ["code", "Code"],
      ["name", "Subject"],
      ["credits", "Credits"],
      ["branch_id", "Branch ID"],
      ["semester_id", "Semester ID"],
    ];
  }
  if (resource === "academic-years") return [["name", "Academic year"], ["start_date", "Starts"], ["end_date", "Ends"]];
  if (resource === "departments") return [["code", "Code"], ["name", "Department"]];
  if (resource === "branches") return [["code", "Code"], ["name", "Branch"], ["department_id", "Department ID"]];
  if (resource === "semesters") return [["name", "Semester"], ["number", "Number"], ["academic_year_id", "Academic year ID"]];
  return [["name", "Section"], ["branch_id", "Branch ID"], ["academic_year_id", "Year ID"], ["semester_id", "Semester ID"]];
}

const importTypeLabels = {
  students: "Students (with class enrollment)",
  academic_years: "Academic years",
  departments: "Departments",
  branches: "Branches",
  semesters: "Semesters",
  class_sections: "Class sections",
  subjects: "Subjects & credits",
  enrollments: "Student enrollments",
};

function defaultColumnMapping(fields, headers) {
  const normalized = new Map(
    headers.map((header) => [
      header.toLowerCase().replace(/[^a-z0-9]/g, ""),
      header,
    ]),
  );
  return Object.fromEntries(
    fields.map((field) => {
      const match =
        normalized.get(field.toLowerCase().replace(/[^a-z0-9]/g, "")) ?? "";
      return [field, match];
    }),
  );
}

function StudentAccountProvisioning({ sections, onProvisioned }) {
  const [sectionId, setSectionId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  async function provisionAccounts() {
    if (!sectionId) return;
    const section = sections.find((item) => String(item.id) === sectionId);
    if (!window.confirm(
      `Create student login accounts for eligible students in section ${section?.name ?? sectionId}?`,
    )) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const response = await provisionStudentAccounts(sectionId);
      setResult(response);
      await onProvisioned();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="faculty-panel faculty-student-account-panel">
      <div className="faculty-panel-heading">
        <div>
          <p className="faculty-eyebrow">STUDENT ACCESS</p>
          <h2>Create Student Login Accounts</h2>
        </div>
      </div>
      <p>
        Creates login accounts for existing active students in a section and
        sends each student a single-use password setup link. Student records
        are reused; passwords are never set or shown by faculty.
      </p>
      <div className="faculty-record-form">
        <label>
          <span>Authorized class section</span>
          <select
            value={sectionId}
            onChange={(event) => setSectionId(event.target.value)}
            disabled={busy || sections.length === 0}
          >
            <option value="">Select a section…</option>
            {sections.map((section) => (
              <option key={section.id} value={section.id}>
                Section {section.name} (ID: {section.id})
              </option>
            ))}
          </select>
        </label>
        <div className="faculty-form-actions">
          <button
            type="button"
            onClick={provisionAccounts}
            disabled={busy || !sectionId}
          >
            {busy ? "Creating accounts…" : "Create Student Login Accounts"}
          </button>
        </div>
      </div>
      {sections.length === 0 && (
        <p className="faculty-form-note">
          Create and assign a class section, and enroll students, before provisioning accounts.
        </p>
      )}
      {error && <div className="faculty-alert import-alert" role="alert">{error}</div>}
      {result && (
        <div className="faculty-student-account-result" role="status">
          <strong>Provisioning complete</strong>
          <div className="faculty-import-result">
            <span>Created: {result.summary.created}</span>
            <span>Already linked: {result.summary.already_linked}</span>
            <span>Skipped: {result.summary.skipped}</span>
            <span>Failed: {result.summary.failed}</span>
            {result.summary.delivery_failed > 0 && (
              <span>Email delivery failed: {result.summary.delivery_failed}</span>
            )}
          </div>
          {result.results.some((item) => item.reason) && (
            <ul className="faculty-student-account-errors">
              {result.results.filter((item) => item.reason).map((item) => (
                <li key={`${item.student_id}-${item.status}`}>
                  {item.student_id}: {item.reason}
                </li>
              ))}
            </ul>
          )}
          {result.local_development_only && (
            <div className="faculty-local-setup-links">
              <strong>LOCAL DEVELOPMENT ONLY — one-time setup links</strong>
              <p>
                These links contain sensitive, single-use tokens. Share each link
                only with the matching student. Do not use this mode in production.
              </p>
              {result.local_setup_links.map((item) => (
                <p key={item.student_id}>
                  {item.student_id}: <a href={item.url} target="_blank" rel="noreferrer">Open setup link</a>
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ImportDesign({ onImported }) {
  const [importTypes, setImportTypes] = useState(null);
  const [file, setFile] = useState(null);
  const [importType, setImportType] = useState("students");
  const [duplicatePolicy, setDuplicatePolicy] = useState("skip");
  const [mappingInfo, setMappingInfo] = useState(null);
  const [mapping, setMapping] = useState({});
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getFacultyImportTypes()
      .then(setImportTypes)
      .catch((loadError) => setError(loadError.message));
  }, []);

  function resetPreview() {
    setMappingInfo(null);
    setMapping({});
    setPreview(null);
    setResult(null);
    setError("");
  }

  function makeFormData(columnMapping = null) {
    const body = new FormData();
    body.append("file", file);
    body.append("import_type", importType);
    body.append("duplicate_policy", duplicatePolicy);
    if (columnMapping) body.append("mapping", JSON.stringify(columnMapping));
    return body;
  }

  async function inspectFile() {
    if (!file) {
      setError("Choose a CSV or XLSX file first.");
      return;
    }
    setBusy(true);
    setError("");
    setPreview(null);
    setResult(null);
    try {
      const response = await previewFacultyImport(makeFormData());
      setMappingInfo(response);
      setMapping(
        defaultColumnMapping(response.mapping_fields.fields, response.headers),
      );
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function validateFile() {
    setBusy(true);
    setError("");
    setPreview(null);
    setResult(null);
    try {
      const mapped = Object.fromEntries(
        Object.entries(mapping).filter(([, header]) => header),
      );
      const response = await previewFacultyImport(makeFormData(mapped));
      setPreview(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!preview?.can_commit || !preview.preview_id) return;
    const counts = preview.summary;
    const confirmed = window.confirm(
      `Import ${counts.created} new, update ${counts.updated}, and skip ${counts.skipped} records? This will write to the database.`,
    );
    if (!confirmed) return;
    setBusy(true);
    setError("");
    try {
      const response = await commitFacultyImport(preview.preview_id);
      setResult(response.summary);
      setPreview(null);
      setMappingInfo(null);
      setFile(null);
      await onImported();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="faculty-import-workflow">
      <section className="faculty-panel import-design">
        <p className="faculty-eyebrow">FACULTY DATA WORKFLOW</p>
        <h2>Import academic records</h2>
        <p>
          Supported files: CSV and Excel (.xlsx), up to 5 MB and 5,000 data
          rows. A preview does not write records. Existing records are skipped
          by default; choose update to review proposed changes before confirming.
          Student passwords and login accounts are never created by imports.
        </p>
        <div className="faculty-record-form import-controls">
          <label>
            <span>Record type</span>
            <select
              value={importType}
              onChange={(event) => {
                setImportType(event.target.value);
                resetPreview();
              }}
            >
              {Object.entries(importTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>CSV or Excel file</span>
            <input
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                resetPreview();
              }}
            />
          </label>
          <label>
            <span>Existing duplicate records</span>
            <select
              value={duplicatePolicy}
              onChange={(event) => {
                setDuplicatePolicy(event.target.value);
                resetPreview();
              }}
            >
              <option value="skip">Skip existing records</option>
              <option value="update">Update existing records (review first)</option>
            </select>
          </label>
        </div>
        <div className="faculty-form-actions">
          <button type="button" onClick={inspectFile} disabled={busy || !file || !importTypes}>
            {busy ? "Reading file…" : "Read headers and sample"}
          </button>
        </div>
        {error && <div className="faculty-alert import-alert" role="alert">{error}</div>}
        {result && (
          <div className="faculty-import-result" role="status">
            <strong>Import completed</strong>
            <span>Created: {result.created}</span>
            <span>Updated: {result.updated}</span>
            <span>Skipped: {result.skipped}</span>
            <span>Failed: {result.failed}</span>
          </div>
        )}
      </section>

      {mappingInfo && (
        <section className="faculty-panel">
          <div className="faculty-panel-heading">
            <div><p className="faculty-eyebrow">STEP 2</p><h2>Map spreadsheet columns</h2></div>
            <span className="faculty-form-note">{mappingInfo.row_count} data rows · first worksheet / CSV</span>
          </div>
          <p className="faculty-form-note">
            Fields marked required must be mapped. Relationship values must
            match academic records already in your faculty scope.
          </p>
          <div className="faculty-import-mappings">
            {mappingInfo.mapping_fields.fields.map((field) => {
              const required = mappingInfo.mapping_fields.required_fields.includes(field);
              return (
                <label key={field}>
                  <span>{field.replaceAll("_", " ")}{required ? " *" : " (optional)"}</span>
                  <select
                    value={mapping[field] ?? ""}
                    onChange={(event) => setMapping({ ...mapping, [field]: event.target.value })}
                  >
                    <option value="">Do not map</option>
                    {mappingInfo.headers.map((header) => (
                      <option key={`${field}-${header}`} value={header}>{header}</option>
                    ))}
                  </select>
                </label>
              );
            })}
          </div>
          <div className="faculty-import-sample">
            <h3>Sample rows</h3>
            <div className="faculty-table-wrap">
              <table>
                <thead><tr><th>Row</th>{mappingInfo.headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
                <tbody>
                  {mappingInfo.sample_rows.map((sample) => (
                    <tr key={sample.row_number}>
                      <td>{sample.row_number}</td>
                      {mappingInfo.headers.map((header) => <td key={header}>{String(sample.values[header] ?? "")}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="faculty-form-actions">
            <button type="button" onClick={validateFile} disabled={busy}>
              {busy ? "Validating…" : "Validate and preview changes"}
            </button>
          </div>
        </section>
      )}

      {preview && (
        <section className="faculty-panel">
          <div className="faculty-panel-heading">
            <div><p className="faculty-eyebrow">STEP 3 · REVIEW BEFORE SAVING</p><h2>Import preview</h2></div>
            <span className="faculty-form-note">Duplicate policy: {preview.duplicate_policy}</span>
          </div>
          <div className="faculty-import-result">
            <span>To create: {preview.summary.created}</span>
            <span>To update: {preview.summary.updated}</span>
            <span>To skip: {preview.summary.skipped}</span>
            <span>Validation errors: {preview.summary.failed}</span>
          </div>
          {preview.records.length > 0 && (
            <div className="faculty-table-wrap faculty-import-preview-table">
              <table>
                <thead><tr><th>Row</th><th>Identifier</th><th>Action</th><th>Proposed values</th></tr></thead>
                <tbody>
                  {preview.records.map((record) => (
                    <tr key={record.row_number}>
                      <td>{record.row_number}</td>
                      <td>{record.identity}</td>
                      <td><span className={`import-action import-${record.action}`}>{record.action}</span></td>
                      <td>
                        {record.before && <strong>Current: {Object.entries(record.before).map(([key, value]) => `${key}: ${value ?? ""}`).join(" · ")}<br /></strong>}
                        Proposed: {Object.entries(record.values).map(([key, value]) => `${key}: ${value ?? ""}`).join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {preview.records_truncated && <p className="faculty-form-note">Preview table limited to the first 100 records; all rows will be processed after confirmation.</p>}
          {preview.errors.length > 0 && (
            <div className="faculty-import-errors" role="alert">
              <h3>Rows requiring correction</h3>
              <ul>{preview.errors.map((item) => <li key={`${item.row_number}-${item.message}`}>Row {item.row_number}: {item.message}</li>)}</ul>
              {preview.errors_truncated && <p>Only the first 100 errors are shown.</p>}
            </div>
          )}
          <div className="faculty-form-actions">
            <button type="button" onClick={confirmImport} disabled={busy || !preview.can_commit}>
              {busy ? "Importing…" : "Review and confirm import"}
            </button>
            {!preview.can_commit && <span className="faculty-form-note">Correct validation errors and create a new preview before importing.</span>}
          </div>
        </section>
      )}
    </div>
  );
}

export default function FacultyDashboard({ user, onLogout }) {
  const [activePage, setActivePage] = useState("Dashboard");
  const [activeResource, setActiveResource] = useState("academic-years");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({});
  const [editingStudent, setEditingStudent] = useState(null);

  async function refresh() {
    setError("");
    setLoading(true);
    try {
      setData(await getFacultyAcademicData());
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const selectedResource = useMemo(
    () => structureResources.find((item) => item.resource === activeResource),
    [activeResource],
  );
  const fields = data
    ? fieldsFor(activePage, activeResource, data).filter(
        (field) =>
          !editingStudent ||
          field.name === "full_name" ||
          field.name === "email",
      )
    : [];
  const records = data ? listFor(activePage, activeResource, data) : [];
  const columns = columnsFor(activePage, activeResource);
  const resource = activePage === "Students"
    ? "students"
    : activePage === "Subjects & Credits"
      ? "subjects"
      : activeResource;

  async function submitForm(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const values = { ...form };
      for (const field of fields) {
        if (field.type === "number" || field.type === "select") {
          values[field.name] = Number(values[field.name]);
        }
      }
      if (values.start_date === "") delete values.start_date;
      if (values.end_date === "") delete values.end_date;
      if (editingStudent) {
        await updateFacultyStudent(editingStudent, {
          full_name: values.full_name,
          email: values.email,
        });
        setNotice("Student profile updated.");
      } else {
        await createFacultyRecord(resource, values);
        setNotice("Record saved.");
      }
      setEditingStudent(null);
      setForm({});
      await refresh();
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  function changePage(page) {
    setActivePage(page);
    setEditingStudent(null);
    setForm({});
    setError("");
    setNotice("");
  }

  function startStudentEdit(student) {
    setActivePage("Students");
    setEditingStudent(student.student_id);
    setForm({ full_name: student.full_name, email: student.email });
    setNotice("");
    setError("");
  }

  const isEntryPage = activePage === "Students" ||
    activePage === "Subjects & Credits" ||
    activePage === "Academic Structure";

  return (
    <div className="faculty-shell">
      <aside className="faculty-sidebar">
        <a className="faculty-brand" href="/" aria-label="EduPilot faculty home">
          <span className="faculty-brand-mark">E</span>
          <span><strong>EduPilot</strong><small>FACULTY PORTAL</small></span>
        </a>
        <nav aria-label="Faculty navigation">
          {navigation.map((page) => (
            <button
              className={`faculty-nav-item${activePage === page ? " active" : ""}`}
              key={page}
              type="button"
              onClick={() => changePage(page)}
            >
              {page}
            </button>
          ))}
        </nav>
        <div className="faculty-sidebar-footer">
          <div><strong>{user.display_name}</strong><small>{user.email}</small></div>
          <button type="button" onClick={onLogout}>Sign out</button>
        </div>
      </aside>

      <main className="faculty-main">
        <header className="faculty-topbar">
          <div><span>FACULTY WORKSPACE</span><strong>{activePage}</strong></div>
          <button type="button" className="faculty-refresh" onClick={refresh} disabled={loading}>Refresh data</button>
        </header>
        <div className="faculty-content">
          {error && <div className="faculty-alert" role="alert">{error}<button type="button" onClick={refresh}>Retry</button></div>}
          {notice && <div className="faculty-notice" role="status">{notice}</div>}

          {loading && !data ? (
            <div className="faculty-state" role="status">Loading faculty records…</div>
          ) : null}

          {data && activePage === "Dashboard" && (
            <>
              <section className="faculty-welcome">
                <p className="faculty-eyebrow">COLLEGE MANAGEMENT</p>
                <h1>Welcome, {user.display_name}.</h1>
                <p>Manage the academic structure and student records assigned to your faculty account.</p>
              </section>
              <div className="faculty-stat-grid">
                <article><span>Students in assigned sections</span><strong>{data.students.length}</strong></article>
                <article><span>Academic years created by you</span><strong>{data.academicYears.length}</strong></article>
                <article><span>Assigned class sections</span><strong>{data.sections.length}</strong></article>
                <article><span>Subjects & credits created by you</span><strong>{data.subjects.length}</strong></article>
              </div>
              <section className="faculty-panel">
                <h2>Stage 1 scope</h2>
                <p>Academic years, departments, branches, semesters, class sections, subjects, student enrollment, and staged CSV/XLSX import are connected to the database. Timetable, academic calendar, attendance entry, marks, and assignments remain staged placeholders.</p>
              </section>
            </>
          )}

          {data && activePage === "Data Import" && <ImportDesign onImported={refresh} />}

          {data && laterModules.has(activePage) && (
            <section className="faculty-panel faculty-placeholder">
              <p className="faculty-eyebrow">PLANNED STAGE</p>
              <h2>{activePage}</h2>
              <p>This navigation page is a placeholder. No management form or write API is available for this module in Stage 1.</p>
            </section>
          )}

          {data && isEntryPage && (
            <>
              {activePage === "Students" && (
                <StudentAccountProvisioning
                  sections={data.sections}
                  onProvisioned={refresh}
                />
              )}
              {activePage === "Academic Structure" && (
                <div className="faculty-tabs" role="tablist" aria-label="Academic structure types">
                  {structureResources.map((item) => (
                    <button
                      key={item.resource}
                      type="button"
                      className={activeResource === item.resource ? "selected" : ""}
                      onClick={() => {
                        setActiveResource(item.resource);
                        setForm({});
                        setEditingStudent(null);
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
              <section className="faculty-panel faculty-entry-panel">
                <div className="faculty-panel-heading">
                  <div>
                    <p className="faculty-eyebrow">{activePage === "Students" ? "ENROLLMENT" : "ACADEMIC DATA"}</p>
                    <h2>{editingStudent ? "Update student profile" : activePage === "Students" ? "Register student in a class" : activePage === "Subjects & Credits" ? "Add subject and credits" : `Add ${selectedResource?.label.toLowerCase()}`}</h2>
                  </div>
                </div>
                {activePage === "Students" && editingStudent ? (
                  <p className="faculty-form-note">Editing {editingStudent}. Class placement cannot be changed in this stage.</p>
                ) : null}
                <form className="faculty-record-form" onSubmit={submitForm}>
                  {fields.map((field) => (
                    <label key={field.name}>
                      <span>{field.label}</span>
                      {field.type === "select" ? (
                        <select
                          required={field.required}
                          value={form[field.name] ?? ""}
                          onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}
                        >
                          <option value="">Select…</option>
                          {field.options.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={field.type ?? "text"}
                          min={field.min}
                          step={field.step}
                          placeholder={field.placeholder}
                          required={field.required}
                          value={form[field.name] ?? ""}
                          onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}
                        />
                      )}
                    </label>
                  ))}
                  <div className="faculty-form-actions">
                    <button type="submit" disabled={saving || fields.some((field) => field.type === "select" && field.options.length === 0)}>
                      {saving ? "Saving…" : editingStudent ? "Save student" : "Save record"}
                    </button>
                    {editingStudent && <button type="button" className="faculty-secondary-button" onClick={() => { setEditingStudent(null); setForm({}); }}>Cancel</button>}
                  </div>
                </form>
                {activePage === "Students" && data.sections.length === 0 && (
                  <p className="faculty-form-note">Create an academic year, department, branch, semester, and class section before enrolling a student.</p>
                )}
                {activePage === "Academic Structure" && activeResource === "sections" && (
                  <p className="faculty-form-note">A new section is automatically assigned to the faculty member who creates it.</p>
                )}
              </section>
              <section className="faculty-panel">
                <div className="faculty-panel-heading"><div><h2>Records</h2><p>{records.length ? `${records.length} record${records.length === 1 ? "" : "s"} in your faculty scope` : "No records have been created in your faculty scope."}</p></div></div>
                {records.length ? (
                  <div className="faculty-table-wrap">
                    <table>
                      <thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}{activePage === "Students" && <th>Action</th>}</tr></thead>
                      <tbody>
                        {records.map((record, index) => (
                          <tr key={record.student_id ?? record.id ?? index}>
                            {columns.map(([key]) => <td key={key}>{record[key] ?? "—"}</td>)}
                            {activePage === "Students" && <td><button className="faculty-link-button" type="button" onClick={() => startStudentEdit(record)}>Edit</button></td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <p className="faculty-empty">Records you create will appear here.</p>}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
