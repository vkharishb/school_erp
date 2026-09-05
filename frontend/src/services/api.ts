import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { AccountType, AcademicClass, AcademicYear, Campus, Charge, FeeHead, FeeStructure, Organization, OrganizationAcademicYear, OrganizationDashboard, School, SchoolConfiguration, SchoolLicense, Student, TokenResponse, User, Section, Teacher, AttendanceRecord, SchoolDashboardSummary, Subject, MarkRecord, RbacPermission, RbacRole, AssignableRole, ImportPreview, ImportResult, ReportResult, ERPAccessPolicy, ERPAccessResult, LinkedStudent, ParentStudentPortalSummary, FeeAccountStudent } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const api = axios.create({ baseURL: API_BASE, withCredentials: true });

let accessToken: string | null = null;
export function setAccessToken(token: string | null) { accessToken = token; }

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;

  const method = (config.method || "get").toUpperCase();
  const url = config.url || "";
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  const exempt = url.includes("/auth/login") || url.includes("/auth/refresh") || url.includes("/auth/logout") || url.includes("/auth/change-password") || url.includes("/system/development-reset") || url.endsWith("/preview");
  if (mutating && !exempt && !config.headers["X-Change-Confirmed"]) {
    const confirmed = window.confirm("Do you want to continue with this change?");
    if (!confirmed) throw new axios.CanceledError("Change cancelled by user");
    const reason = (window.prompt("Reason for this change (required):") || "").trim();
    if (reason.length < 3) throw new axios.CanceledError("A reason is required for every change");
    config.headers["X-Change-Confirmed"] = "true";
    config.headers["X-Change-Reason"] = reason;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = axios.post<TokenResponse>(`${API_BASE}/auth/refresh`, undefined, { withCredentials: true })
      .then(({ data }) => { setAccessToken(data.access_token); return data.access_token; })
      .catch((error: unknown) => {
        if (axios.isAxiosError(error) && [401, 403].includes(error.response?.status || 0)) {
          setAccessToken(null);
          return null;
        }
        throw error;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

api.interceptors.response.use((r) => r, async (error: AxiosError) => {
  const config = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  if (error.response?.status === 401 && config && !config._retry && !config.url?.includes("/auth/refresh") && !config.url?.includes("/auth/login")) {
    config._retry = true;
    try {
      const token = await refreshAccessToken();
      if (token) { config.headers.Authorization = `Bearer ${token}`; return api.request(config); }
      setAccessToken(null);
      if (window.location.pathname !== "/login") window.location.href = "/login";
    } catch (refreshError) {
      // A network/5xx refresh failure is not proof that the session is invalid.
      // Preserve the session and let the page show its retryable backend error.
      return Promise.reject(refreshError);
    }
  }
  return Promise.reject(error);
});

export const authApi = {
  login: async (accountType: AccountType, username: string, password: string): Promise<TokenResponse> => (await api.post<TokenResponse>("/auth/login/json", { account_type: accountType, username, password })).data,
  refresh: refreshAccessToken,
  me: async (): Promise<User> => (await api.get<User>("/auth/me")).data,
  logout: async (): Promise<void> => { await api.post("/auth/logout"); },
  changePassword: async (currentPassword:string, newPassword:string): Promise<void> => { await api.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword }); },
};

export const schoolApi = {
  list: async (includeArchived=false): Promise<School[]> => (await api.get<School[]>("/schools", {params: includeArchived ? {include_archived:true} : undefined})).data,
  get: async (id: string): Promise<School> => (await api.get<School>(`/schools/${id}`)).data,
  getLicense: async (id: string): Promise<SchoolLicense> => (await api.get<SchoolLicense>(`/schools/${id}/license`)).data,
  create: async (payload: { organization_id: string; admin?: {full_name:string;designation:"Principal"|"Headmaster"|"School Administrator";username:string;email?:string|null;phone?:string|null;password:string}; configuration: Partial<SchoolConfiguration> & { name: string; area: string }; udise_codes?: {udise_code:string;label?:string|null;is_primary?:boolean}[]; max_users?: number; enabled_modules?: string[]; license_expires_at?: string }): Promise<School> => (await api.post<School>("/schools", payload)).data,
  updateProfile: async (schoolId: string, payload: Record<string, unknown>): Promise<School> => (await api.patch<School>(`/schools/${schoolId}/profile`, payload)).data,
  updateConfiguration: async (schoolId: string, payload: Partial<SchoolConfiguration>): Promise<SchoolConfiguration> => (await api.patch<SchoolConfiguration>(`/schools/${schoolId}/configuration`, payload)).data,
  setStatus: async (schoolId: string, is_active: boolean): Promise<School> => (await api.patch<School>(`/schools/${schoolId}/status`, { is_active })).data,
  archive: async (schoolId: string): Promise<School> => (await api.post<School>(`/schools/${schoolId}/archive`)).data,
  restore: async (schoolId: string): Promise<School> => (await api.post<School>(`/schools/${schoolId}/restore`)).data,
  delete: async (schoolId: string): Promise<void> => { await api.delete(`/schools/${schoolId}`); },
  updateLicense: async (schoolId: string, payload: { enabled_modules?: string[]; max_users?: number; expires_at?: string; is_active?: boolean }): Promise<SchoolLicense> => (await api.patch<SchoolLicense>(`/schools/${schoolId}/license`, payload)).data,
};

export const organizationApi = {
  list: async (includeArchived=false): Promise<Organization[]> => (await api.get<Organization[]>("/organizations", {params: includeArchived ? {include_archived:true} : undefined})).data,
  create: async (payload: { name:string; allowed_schools:number; head_full_name:string; head_email:string; head_phone?:string|null; admin_username:string; admin_email:string; admin_password:string; admin_designation:"Secretary and Correspondent"|"Chairman" }): Promise<Organization> => (await api.post<Organization>("/organizations", payload)).data,
  update: async (organizationId:string, payload:Record<string,unknown>): Promise<Organization> => (await api.patch<Organization>(`/organizations/${organizationId}`, payload)).data,
  dashboard: async (organizationId: string): Promise<OrganizationDashboard> => (await api.get<OrganizationDashboard>(`/organizations/${organizationId}/dashboard`)).data,
  setStatus: async (organizationId: string, is_active: boolean): Promise<Organization> => (await api.patch<Organization>(`/organizations/${organizationId}/status`, { is_active })).data,
  archive: async (organizationId: string): Promise<Organization> => (await api.post<Organization>(`/organizations/${organizationId}/archive`)).data,
  restore: async (organizationId: string): Promise<Organization> => (await api.post<Organization>(`/organizations/${organizationId}/restore`)).data,
  updateLicense: async (organizationId: string, payload: { enabled_modules?: string[]; license_expires_at?: string }): Promise<Organization> => (await api.patch<Organization>(`/organizations/${organizationId}/license`, payload)).data,
  academicYears: async (organizationId:string): Promise<OrganizationAcademicYear[]> => (await api.get<OrganizationAcademicYear[]>(`/organizations/${organizationId}/academic-years`)).data,
  createAcademicYear: async (organizationId:string, payload:{code:string;name:string;starts_on:string;ends_on:string;notes?:string|null}): Promise<OrganizationAcademicYear> => (await api.post<OrganizationAcademicYear>(`/organizations/${organizationId}/academic-years`, payload)).data,
  updateAcademicYear: async (academicYearId:string, payload:Partial<{code:string;name:string;starts_on:string;ends_on:string;notes:string|null}>): Promise<OrganizationAcademicYear> => (await api.patch<OrganizationAcademicYear>(`/organizations/academic-years/${academicYearId}`, payload)).data,
  activateAcademicYear: async (academicYearId:string): Promise<OrganizationAcademicYear> => (await api.post<OrganizationAcademicYear>(`/organizations/academic-years/${academicYearId}/activate`)).data,
};

export const foundationApi = {
  campuses: async (schoolId: string): Promise<Campus[]> => (await api.get<Campus[]>(`/foundation/schools/${schoolId}/campuses`)).data,
  academicYears: async (campusId: string): Promise<AcademicYear[]> => (await api.get<AcademicYear[]>(`/foundation/campuses/${campusId}/academic-years`)).data,
};

export const academicApi = {
  classes: async (campusId: string): Promise<AcademicClass[]> => (await api.get<AcademicClass[]>(`/students/campuses/${campusId}/classes`)).data,
  createClass: async (campusId:string, payload:{code:string;name:string}): Promise<AcademicClass> => (await api.post<AcademicClass>(`/students/campuses/${campusId}/classes`, payload)).data,
  updateClass: async (classId:string, payload:{code?:string;name?:string}): Promise<AcademicClass> => (await api.patch<AcademicClass>(`/students/classes/${classId}`, payload)).data,
  sections: async (classId: string): Promise<Section[]> => (await api.get<Section[]>(`/students/classes/${classId}/sections`)).data,
  createSection: async (classId:string, payload:{code:string;name:string}): Promise<Section> => (await api.post<Section>(`/students/classes/${classId}/sections`, payload)).data,
  updateSection: async (sectionId:string, payload:{code?:string;name?:string}): Promise<Section> => (await api.patch<Section>(`/students/sections/${sectionId}`, payload)).data,
  subjects: async (campusId: string): Promise<Subject[]> => (await api.get<Subject[]>(`/students/campuses/${campusId}/subjects`)).data,
  createSubject: async (campusId:string, payload:{code:string;name:string}): Promise<Subject> => (await api.post<Subject>(`/students/campuses/${campusId}/subjects`, payload)).data,
  updateSubject: async (subjectId:string, payload:{code?:string;name?:string}): Promise<Subject> => (await api.patch<Subject>(`/students/subjects/${subjectId}`, payload)).data,
};

export const studentApi = {
  list: async (schoolId: string, search?: string): Promise<Student[]> => (await api.get<Student[]>(`/students/${schoolId}`, { params: search ? { search } : undefined })).data,
  get: async (schoolId:string, studentId:string): Promise<Student> => (await api.get<Student>(`/students/${schoolId}/${studentId}`)).data,
  create: async (schoolId: string, payload: Record<string, unknown>): Promise<Student> => (await api.post<Student>(`/students/${schoolId}`, payload)).data,
  update: async (schoolId:string, studentId:string, payload:Record<string,unknown>): Promise<Student> => (await api.patch<Student>(`/students/${schoolId}/${studentId}`, payload)).data,
  archive: async (schoolId:string, studentId:string): Promise<Student> => (await api.delete<Student>(`/students/${schoolId}/${studentId}`)).data,
  reactivate: async (schoolId:string, studentId:string): Promise<Student> => (await api.post<Student>(`/students/${schoolId}/${studentId}/reactivate`)).data,
};

export const feeApi = {
  accountStudents: async (schoolId:string): Promise<FeeAccountStudent[]> => (await api.get<FeeAccountStudent[]>(`/fees/${schoolId}/account-students`)).data,
  heads: async (schoolId: string): Promise<FeeHead[]> => (await api.get<FeeHead[]>(`/fees/${schoolId}/heads`)).data,
  structures: async (schoolId: string): Promise<FeeStructure[]> => (await api.get<FeeStructure[]>(`/fees/${schoolId}/structures`)).data,
  charges: async (schoolId: string, studentId: string): Promise<Charge[]> => (await api.get<Charge[]>(`/fees/${schoolId}/students/${studentId}/charges`)).data,
  createHead: async (schoolId: string, payload: { code: string; name: string; is_misc?: boolean }): Promise<FeeHead> => (await api.post<FeeHead>(`/fees/${schoolId}/heads`, payload)).data,
  createStructure: async (schoolId: string, payload: Record<string, unknown>): Promise<FeeStructure> => (await api.post<FeeStructure>(`/fees/${schoolId}/structures`, payload)).data,
  collectPayment: async (schoolId: string, payload: { student_id: string; payment_mode: string; upi_reference_last5?: string; allocations: { charge_id: string; amount: string }[] }): Promise<{ receipt_number: string }> => (await api.post(`/fees/${schoolId}/payments`, payload)).data,
};

export const erpAccessApi = {
  contacts: async (schoolId:string, studentId:string): Promise<{mobile:string;label:string}[]> => (await api.get(`/erp-access/schools/${schoolId}/students/${studentId}/contacts`)).data,
  policy: async (schoolId:string, organizationAcademicYearId:string): Promise<ERPAccessPolicy|null> => (await api.get<ERPAccessPolicy|null>(`/erp-access/schools/${schoolId}/policy`, {params:{organization_academic_year_id:organizationAcademicYearId}})).data,
  setPolicy: async (schoolId:string, payload:{organization_academic_year_id:string;fee_head_id:string;annual_amount:string;is_enabled:boolean}): Promise<ERPAccessPolicy> => (await api.put<ERPAccessPolicy>(`/erp-access/schools/${schoolId}/policy`, payload)).data,
  optIn: async (schoolId:string, payload:{student_id:string;access_number:string;initial_password?:string;notes?:string}): Promise<ERPAccessResult> => (await api.post<ERPAccessResult>(`/erp-access/schools/${schoolId}/opt-in`, payload)).data,
};

export const parentStudentApi = {
  students: async (): Promise<LinkedStudent[]> => (await api.get<LinkedStudent[]>('/parent-student/me/students')).data,
  summary: async (studentId:string): Promise<ParentStudentPortalSummary> => (await api.get<ParentStudentPortalSummary>(`/parent-student/students/${studentId}/summary`)).data,
};

export default api;

export const teacherApi = {
  list: async (schoolId: string, search?: string): Promise<Teacher[]> => (await api.get<Teacher[]>(`/teachers/${schoolId}`, { params: search ? { search } : undefined })).data,
  create: async (schoolId: string, payload: Record<string, unknown>): Promise<Teacher> => (await api.post<Teacher>(`/teachers/${schoolId}`, payload)).data,
  update: async (teacherId: string, payload: Record<string, unknown>): Promise<Teacher> => (await api.patch<Teacher>(`/teachers/${teacherId}`, payload)).data,
};

export const attendanceApi = {
  students: async (schoolId: string, attendanceDate: string): Promise<AttendanceRecord[]> => (await api.get<AttendanceRecord[]>(`/attendance/${schoolId}/students`, { params: { attendance_date: attendanceDate } })).data,
  teachers: async (schoolId: string, attendanceDate: string): Promise<AttendanceRecord[]> => (await api.get<AttendanceRecord[]>(`/attendance/${schoolId}/teachers`, { params: { attendance_date: attendanceDate } })).data,
  markStudents: async (schoolId: string, payload: { attendance_date:string; records:{entity_id:string;status:string;remarks?:string}[] }): Promise<AttendanceRecord[]> => (await api.put<AttendanceRecord[]>(`/attendance/${schoolId}/students`, payload)).data,
  markTeachers: async (schoolId: string, payload: { attendance_date:string; records:{entity_id:string;status:string;remarks?:string}[] }): Promise<AttendanceRecord[]> => (await api.put<AttendanceRecord[]>(`/attendance/${schoolId}/teachers`, payload)).data,
};

export const dashboardApi = {
  schoolSummary: async (schoolId: string): Promise<SchoolDashboardSummary> => (await api.get<SchoolDashboardSummary>(`/dashboard/schools/${schoolId}/summary`)).data,
};


export const userAdminApi = {
  list: async (params?: { organization_id?: string; school_id?: string; campus_id?: string; include_organization_admins?: boolean }): Promise<User[]> => (await api.get<User[]>("/users", { params })).data,
  create: async (payload: Record<string, unknown>): Promise<User> => (await api.post<User>("/users", payload)).data,
  update: async (userId: string, payload: Record<string, unknown>): Promise<User> => (await api.patch<User>(`/users/${userId}`, payload)).data,
  resetPassword: async (userId: string, newPassword: string): Promise<void> => { await api.post(`/users/${userId}/reset-password`, { new_password: newPassword }); },
};

export const marksApi = {
  list: async (schoolId:string): Promise<MarkRecord[]> => (await api.get<MarkRecord[]>(`/marks/${schoolId}`)).data,
  upsert: async (schoolId:string, payload:Record<string, unknown>): Promise<MarkRecord> => (await api.post<MarkRecord>(`/marks/${schoolId}`, payload)).data,
  bulk: async (schoolId:string, records:Record<string, unknown>[]): Promise<MarkRecord[]> => (await api.post<MarkRecord[]>(`/marks/${schoolId}/bulk`, { records })).data,
  lock: async (schoolId:string, markId:string, is_locked:boolean, reason?:string): Promise<MarkRecord> => {
    const headers = !is_locked && reason ? { "X-Change-Confirmed": "true", "X-Change-Reason": reason } : undefined;
    return (await api.patch<MarkRecord>(`/marks/${schoolId}/${markId}/lock`, { is_locked, reason: reason || undefined }, { headers })).data;
  },
};

export const rbacApi = {
  permissions: async (): Promise<RbacPermission[]> => (await api.get<RbacPermission[]>("/rbac/permissions")).data,
  roles: async (schoolId?: string): Promise<RbacRole[]> => (await api.get<RbacRole[]>("/rbac/roles", { params: schoolId ? { school_id: schoolId } : undefined })).data,
  assignableRoles: async (): Promise<AssignableRole[]> => (await api.get<AssignableRole[]>("/rbac/assignable-roles")).data,
  createRole: async (payload:{code:string;name:string;description?:string|null;organization_id?:string|null;school_id?:string|null;permission_codes:string[]}): Promise<RbacRole> => (await api.post<RbacRole>("/rbac/roles", payload)).data,
  updatePermissions: async (roleId:string, permission_codes:string[]): Promise<RbacRole> => (await api.patch<RbacRole>(`/rbac/roles/${roleId}/permissions`, { permission_codes })).data,
};


function appendFormValue(form:FormData, key:string, value:string){ form.append(key,value); }

export const importApi = {
  classSectionTemplate: async (schoolId:string): Promise<Blob> => (await api.get(`/imports/classes-sections/${schoolId}/template`, { responseType:"blob" })).data,
  previewClassSections: async (schoolId:string, file:File, campus_id:string): Promise<ImportPreview> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("file",file); return (await api.post<ImportPreview>(`/imports/classes-sections/${schoolId}/preview`,form)).data; },
  confirmClassSections: async (schoolId:string, file:File, sha256:string, campus_id:string): Promise<ImportResult> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/classes-sections/${schoolId}/confirm`,form)).data; },
  studentTemplate: async (schoolId:string, campusId:string): Promise<Blob> => (await api.get(`/imports/students/${schoolId}/template`, { params:{campus_id:campusId}, responseType:"blob" })).data,
  previewStudents: async (schoolId:string, file:File, context:{campus_id:string}): Promise<ImportPreview> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>appendFormValue(form,k,v)); form.append("file",file); return (await api.post<ImportPreview>(`/imports/students/${schoolId}/preview`,form)).data; },
  confirmStudents: async (schoolId:string, file:File, sha256:string, context:{campus_id:string}): Promise<ImportResult> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>appendFormValue(form,k,v)); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/students/${schoolId}/confirm`,form)).data; },
  teacherTemplate: async (schoolId:string): Promise<Blob> => (await api.get(`/imports/teachers/${schoolId}/template`, { responseType:"blob" })).data,
  previewTeachers: async (schoolId:string, file:File, campus_id:string): Promise<ImportPreview> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("file",file); return (await api.post<ImportPreview>(`/imports/teachers/${schoolId}/preview`,form)).data; },
  confirmTeachers: async (schoolId:string, file:File, sha256:string, campus_id:string): Promise<ImportResult> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/teachers/${schoolId}/confirm`,form)).data; },
  feeStructureTemplate: async (schoolId:string): Promise<Blob> => (await api.get(`/imports/fee-structures/${schoolId}/template`, { responseType:"blob" })).data,
  previewFeeStructures: async (schoolId:string, file:File, campus_id:string): Promise<ImportPreview> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("file",file); return (await api.post<ImportPreview>(`/imports/fee-structures/${schoolId}/preview`,form)).data; },
  confirmFeeStructures: async (schoolId:string, file:File, sha256:string, campus_id:string): Promise<ImportResult> => { const form=new FormData(); form.append("campus_id",campus_id); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/fee-structures/${schoolId}/confirm`,form)).data; },
  priorDuesTemplate: async (schoolId:string): Promise<Blob> => (await api.get(`/imports/prior-year-dues/${schoolId}/template`, { responseType:"blob" })).data,
  previewPriorDues: async (schoolId:string, file:File, context:{campus_id:string;fee_head_id:string}): Promise<ImportPreview> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>form.append(k,v)); form.append("file",file); return (await api.post<ImportPreview>(`/imports/prior-year-dues/${schoolId}/preview`,form)).data; },
  confirmPriorDues: async (schoolId:string, file:File, sha256:string, context:{campus_id:string;fee_head_id:string}): Promise<ImportResult> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>form.append(k,v)); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/prior-year-dues/${schoolId}/confirm`,form)).data; },
  marksTemplate: async (schoolId:string, context:{campus_id:string;academic_year_id:string;academic_class_id:string;section_id:string;subject_id:string;assessment_name:string;max_marks:string}): Promise<Blob> => (await api.get(`/imports/marks/${schoolId}/template`, { params:context, responseType:"blob" })).data,
  previewMarks: async (schoolId:string, file:File, context:{campus_id:string;academic_year_id:string;academic_class_id:string;section_id:string;subject_id:string;assessment_name:string;max_marks:string}): Promise<ImportPreview> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>appendFormValue(form,k,v)); form.append("file",file); return (await api.post<ImportPreview>(`/imports/marks/${schoolId}/preview`,form)).data; },
  confirmMarks: async (schoolId:string, file:File, sha256:string, context:{campus_id:string;academic_year_id:string;academic_class_id:string;section_id:string;subject_id:string;assessment_name:string;max_marks:string}): Promise<ImportResult> => { const form=new FormData(); Object.entries(context).forEach(([k,v])=>appendFormValue(form,k,v)); form.append("expected_sha256",sha256); form.append("file",file); return (await api.post<ImportResult>(`/imports/marks/${schoolId}/confirm`,form)).data; },
};

export interface AuditEventRow {
  id:string; action:string; module:string|null; entity_type:string|null; entity_id:string|null;
  user_id:string|null; user_name:string|null; username:string|null; user_account_type:string|null;
  before:Record<string,unknown>|null; after:Record<string,unknown>|null; metadata:Record<string,unknown>|null; created_at:string;
}

export const auditApi = {
  list: async (schoolId:string): Promise<AuditEventRow[]> => (await api.get('/audit', {params:{school_id:schoolId,limit:200}})).data,
};

export interface BackupItem { name:string; size_bytes:number; sha256:string; created_at:string; offsite?:{configured:boolean;synced:boolean;path?:string}; offsite_error?:string|null; }
export interface BackupStatus { last_local_backup?:string|null; local_count:number; offsite_configured:boolean; offsite_count:number; last_offsite_backup?:string|null; recent_backup_ready_for_archive:boolean; archive_backup_max_age_hours:number; retention:{local_latest:number;daily_days:number;weekly_weeks:number;monthly_months:number}; }

export interface PlatformModuleStatus {
  code:string; name:string; phase:number; status:"ready_dev"|"in_progress"|"planned"; status_label:string; note:string; is_core:boolean;
}
export interface PlatformStatus {
  platform_status:string; release:string; migration_head:string; phase:number; environment:string;
  summary:{ready_dev:number;in_progress:number;planned:number;total:number}; modules:PlatformModuleStatus[];
}
export interface DevelopmentResetPreview {
  enabled:boolean; environment:string; confirmation_phrase:string; preserves:string[];
  deletes:Record<string,number>; requires_relogin:boolean;
}

export const systemApi = {
  settings: async (): Promise<Record<string,unknown>> => (await api.get('/system/settings')).data,
  platformStatus: async (): Promise<PlatformStatus> => (await api.get('/system/platform-status')).data,
  developmentResetPreview: async (): Promise<DevelopmentResetPreview> => (await api.get('/system/development-reset/preview')).data,
  resetDevelopmentData: async (confirmation:string,password:string): Promise<{status:string;environment:string;removed:Record<string,number>;safety_backup:string;requires_relogin:boolean}> => (await api.post('/system/development-reset',{confirmation,password})).data,
  backups: async (): Promise<{items:BackupItem[];schedule_hours:number;retention_count:number;status:BackupStatus}> => (await api.get('/system/backups')).data,
  createBackup: async (): Promise<BackupItem> => (await api.post('/system/backups')).data,
  deleteBackup: async (name:string): Promise<void> => { await api.delete(`/system/backups/${encodeURIComponent(name)}`); },
  downloadBackup: async (name:string): Promise<Blob> => (await api.get(`/system/backups/${encodeURIComponent(name)}/download`, {responseType:'blob'})).data,
  restore: async (name:string, sha256:string, confirmation:string): Promise<Record<string,unknown>> => (await api.post('/system/restore',{backup_name:name,expected_sha256:sha256,confirmation})).data,
};


export type ReportFilters = {
  campus_id?:string; academic_year_id?:string; academic_class_id?:string; section_id?:string; subject_id?:string;
  assessment_name?:string; start_date?:string; end_date?:string; status?:string; payment_mode?:string; limit?:number;
};
export const reportsApi = {
  run: async (schoolId:string, reportKey:string, params:ReportFilters): Promise<ReportResult> => (await api.get<ReportResult>(`/reports/${schoolId}/run/${reportKey}`, { params })).data,
  exportXlsx: async (schoolId:string, reportKey:string, params:ReportFilters): Promise<Blob> => (await api.get(`/reports/${schoolId}/export/${reportKey}`, { params, responseType:"blob" })).data,
};
