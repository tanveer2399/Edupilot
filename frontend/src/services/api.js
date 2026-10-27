const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readError(response) {
  let result;
  try {
    result = await response.json();
  } catch {
    throw new ApiError(
      "The server returned an invalid response. Please try again.",
      response.status,
    );
  }

  throw new ApiError(
    typeof result.detail === "string"
      ? result.detail
      : `The server returned an error (${response.status}).`,
    response.status,
  );
}

async function get(path) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "include",
    });
  } catch {
    throw new Error(
      "Could not reach EduPilot. Check that the backend is running and try again.",
    );
  }

  if (!response.ok) {
    await readError(response);
  }

  return response.json();
}

async function post(path, body) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Could not reach EduPilot. Check that the backend is running and try again.",
    );
  }

  if (response.status === 204) {
    return null;
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The server returned an invalid response. Please try again.");
  }

  if (!response.ok) {
    throw new ApiError(
      typeof result.detail === "string"
        ? result.detail
        : `The server returned an error (${response.status}).`,
      response.status,
    );
  }

  return result;
}

async function patch(path, body) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      "Could not reach EduPilot. Check that the backend is running and try again.",
    );
  }

  if (!response.ok) {
    await readError(response);
  }

  return response.json();
}

async function postMultipart(path, body) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      credentials: "include",
      body,
    });
  } catch {
    throw new Error(
      "Could not reach EduPilot. Check that the backend is running and try again.",
    );
  }
  if (!response.ok) {
    await readError(response);
  }
  return response.json();
}

export const getCurrentUser = () => get("/auth/me");
export const login = (credentials) => post("/auth/login", credentials);
export const completeStudentPasswordSetup = (token, password) =>
  post("/auth/student/setup", { token, password });
export const logout = () => post("/auth/logout", {});
export const getStudentProfile = () => get("/students/me");
export const getDashboard = () => get("/dashboard");
export const getAttendance = () => get("/attendance");
export const getAttendanceSummary = () => get("/attendance/summary");
export const getMarks = () => get("/marks");
export const getAssignments = () => get("/assignments");
export const getAssignment = (assignmentId) =>
  get(`/assignments/${encodeURIComponent(assignmentId)}`);
export const getTimetable = () => get("/timetable");
export const sendStudyAssistantMessage = (message, conversationId) =>
  post("/study-assistant/chat", {
    message,
    ...(conversationId ? { conversation_id: conversationId } : {}),
  });
export const generateQuiz = (quizRequest) => post("/quiz/generate", quizRequest);
export const submitQuiz = (quizId, answers) =>
  post(`/quiz/${encodeURIComponent(quizId)}/submit`, { answers });
export const generateStudyPlan = (quizId) =>
  post(`/quiz/${encodeURIComponent(quizId)}/study-plan`, {});
export const getFacultyAcademicData = () =>
  Promise.all([
    get("/faculty/academic-years"),
    get("/faculty/departments"),
    get("/faculty/branches"),
    get("/faculty/semesters"),
    get("/faculty/sections"),
    get("/faculty/subjects"),
    get("/faculty/students"),
  ]).then(
    ([
      academicYears,
      departments,
      branches,
      semesters,
      sections,
      subjects,
      students,
    ]) => ({
      academicYears,
      departments,
      branches,
      semesters,
      sections,
      subjects,
      students,
    }),
  );
export const createFacultyRecord = (resource, values) =>
  post(`/faculty/${resource}`, values);
export const updateFacultyStudent = (studentId, values) =>
  patch(`/faculty/students/${encodeURIComponent(studentId)}`, values);
export const provisionStudentAccounts = (sectionId) =>
  post("/faculty/student-accounts/provision", { section_id: Number(sectionId) });
export const getFacultyImportTypes = () => get("/faculty/imports/types");
export const previewFacultyImport = (formData) =>
  postMultipart("/faculty/imports/preview", formData);
export const commitFacultyImport = (previewId) =>
  post("/faculty/imports/commit", { preview_id: previewId, confirm: true });
