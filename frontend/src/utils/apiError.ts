type ApiValidationIssue = {
  field?: unknown;
  message?: unknown;
  msg?: unknown;
  loc?: unknown;
};

type ApiErrorPayload = {
  detail?: unknown;
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
  request_id?: unknown;
};

const FIELD_LABELS: Record<string, string> = {
  campus_id: "Campus",
  school_id: "School / Branch",
  organization_id: "Organization",
  academic_year_id: "Academic Year",
  academic_class_id: "Class",
  class_id: "Class",
  section_id: "Section",
  subject_id: "Subject",
  student_id: "Student",
  teacher_id: "Teacher",
  fee_head_id: "Fee Head",
  role_code: "Role",
  full_name: "Full Name",
  first_name: "First Name",
  last_name: "Last Name",
  admission_number: "Admission Number",
  employee_code: "Employee Number",
  starts_on: "Start Date",
  ends_on: "End Date",
  attendance_date: "Attendance Date",
  marks_obtained: "Marks Obtained",
  max_marks: "Maximum Marks",
  assessment_name: "Assessment",
  expected_sha256: "Validated File",
  file: "Upload File",
  password: "Password",
  new_password: "New Password",
};

function humanizeField(value: string): string {
  const key = value.trim();
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return key
    .replace(/_id$/i, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function locationLabel(loc: unknown): string {
  if (!Array.isArray(loc)) return "";
  const useful = loc
    .filter((part) => !["body", "query", "path", "form", "header", "cookie"].includes(String(part)))
    .filter((part) => typeof part === "string")
    .map((part) => humanizeField(String(part)));
  return useful.join(" → ");
}

function validationMessages(details: unknown): string[] {
  if (!Array.isArray(details)) return [];
  const messages: string[] = [];
  for (const raw of details) {
    if (typeof raw === "string") {
      messages.push(raw);
      continue;
    }
    if (!raw || typeof raw !== "object") continue;
    const item = raw as ApiValidationIssue;
    const field = typeof item.field === "string" ? humanizeField(item.field) : locationLabel(item.loc);
    const message = typeof item.message === "string"
      ? item.message
      : typeof item.msg === "string"
        ? item.msg
        : "Invalid value";
    messages.push(field ? `${field}: ${message}` : message);
  }
  return [...new Set(messages)];
}

function requestReference(data: ApiErrorPayload | undefined): string {
  return typeof data?.request_id === "string" && data.request_id
    ? ` Reference ID: ${data.request_id}.`
    : "";
}

export function apiErrorMessage(err: unknown, fallback = "Request failed"): string {
  const response = (err as { response?: { status?: number; data?: ApiErrorPayload }; message?: string })?.response;
  const data = response?.data;
  const status = response?.status;

  // v2.9.1 API validation envelope. Prefer field-level details over the generic
  // "Request validation failed" summary.
  const errorCode = typeof data?.error?.code === "string" ? data.error.code : "";
  if (errorCode === "validation_error") {
    const messages = validationMessages(data?.error?.details);
    if (messages.length) return `Please correct: ${messages.join("; ")}`;
  }

  // Backward compatibility with stock FastAPI 422 payloads.
  if (Array.isArray(data?.detail)) {
    const messages = validationMessages(data.detail);
    if (messages.length) return `Please correct: ${messages.join("; ")}`;
  }

  // Structured API errors whose details themselves contain validation issues.
  const structuredMessages = validationMessages(data?.error?.details);
  if (structuredMessages.length && errorCode.includes("validation")) {
    return `Please correct: ${structuredMessages.join("; ")}`;
  }

  if (typeof data?.detail === "string" && data.detail.trim()) return data.detail;
  if (typeof data?.error?.message === "string" && data.error.message.trim()) {
    const suffix = status && status >= 500 ? requestReference(data) : "";
    return `${data.error.message}${suffix}`;
  }
  if (data?.detail && typeof data.detail === "object" && "message" in data.detail) {
    const message = (data.detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }

  if (!response) {
    const message = (err as { message?: unknown })?.message;
    if (typeof message === "string" && /network error|failed to fetch|load failed/i.test(message)) {
      return "Cannot connect to the ERP server. Check that the backend is running and try again.";
    }
  }

  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 404) return "The requested record or action was not found. Refresh the page and try again.";
  if (status === 409) return "This action conflicts with existing data. Refresh the page and check for a duplicate or locked record.";
  if (status && status >= 500) return `${fallback}. The server could not complete the request.${requestReference(data)}`;
  return fallback;
}
