export type AccountType = "SUPER_ADMIN"|"ORGANIZATION_ADMIN"|"SCHOOL_ADMIN"|"ACCOUNTS"|"TEACHER"|"RECEPTIONIST"|"PARENT_STUDENT";
export interface User { id:string; username:string; account_type:AccountType; email?:string|null; full_name:string; designation?:string|null; phone?:string|null; is_active:boolean; is_superuser:boolean; organization_id?:string|null; school_id?:string|null; campus_id?:string|null; last_login_at?:string|null; must_change_password?:boolean; roles:string[]; permissions?:string[]; enabled_modules?:string[]; }
export interface TokenResponse { access_token:string; token_type:string; }
export interface Organization { id:string; code:string; name:string; allowed_schools:number; head_full_name?:string|null; head_email?:string|null; head_phone?:string|null; admin_username?:string|null; admin_email?:string|null; admin_full_name?:string|null; admin_phone?:string|null; admin_designation?:string|null; is_active:boolean; archived_at?:string|null; archived_by?:string|null; enabled_modules:string[]; license_starts_at?:string|null; license_expires_at?:string|null; }
export interface SchoolUDISE { id?:string; udise_code:string; label?:string|null; is_primary:boolean; is_active?:boolean; }
export interface SchoolConfiguration { id:string; school_id:string; name:string; short_name?:string|null; area?:string|null; area_code?:string|null; tagline?:string|null; principal_head_name?:string|null; principal_head_email?:string|null; principal_head_phone?:string|null; logo_url?:string|null; address_line1?:string|null; address_line2?:string|null; city?:string|null; state?:string|null; country?:string|null; pincode?:string|null; phone?:string|null; email?:string|null; website?:string|null; current_academic_year?:string|null; academic_year_start_month:number; board?:string|null; settings:Record<string,unknown>; created_at:string; updated_at:string; }
export interface School { id:string; code:string; udise_code?:string|null; udise_codes?:SchoolUDISE[]; organization_id?:string|null; is_active:boolean; deleted_at?:string|null; deleted_by?:string|null; created_at:string; updated_at:string; configuration?:SchoolConfiguration|null; }
export interface OrganizationDashboardUnit { school_id:string; code:string; udise_code?:string|null; name:string; is_active:boolean; student_count:number; teacher_count:number; today_collection:string; outstanding_due:string; overdue_due:string; student_attendance_present:number; student_attendance_marked:number; student_attendance_percentage:number; teacher_attendance_present:number; teacher_attendance_marked:number; teacher_attendance_percentage:number; student_performance_percentage?:number|null; }
export interface OrganizationDashboard { organization_id:string; organization_name:string; unit_count:number; active_unit_count:number; allowed_school_count:number; remaining_school_count:number; student_count:number; teacher_count:number; as_of_date:string; today_collection:string; outstanding_due:string; overdue_due:string; student_attendance_present:number; student_attendance_marked:number; student_attendance_percentage:number; teacher_attendance_present:number; teacher_attendance_marked:number; teacher_attendance_percentage:number; student_performance_percentage?:number|null; units:OrganizationDashboardUnit[]; }
export interface SchoolLicense { id:string; school_id:string; license_key:string; enabled_modules:string[]; max_users:number; starts_at:string; expires_at:string; is_active:boolean; notes?:string|null; is_valid:boolean; }
export interface Campus { id:string; school_id:string; code:string; name:string; address_line1?:string|null; address_line2?:string|null; city?:string|null; state?:string|null; country?:string|null; pincode?:string|null; phone?:string|null; is_active:boolean; }
export interface AcademicYear { id:string; campus_id:string; code:string; name:string; starts_on:string; ends_on:string; notes?:string|null; status:string; is_read_only:boolean; activated_at?:string|null; activated_by?:string|null; }
export interface OrganizationAcademicYear { id:string; organization_id:string; code:string; name:string; starts_on:string; ends_on:string; notes?:string|null; status:string; is_read_only:boolean; activated_at?:string|null; activated_by?:string|null; }
export interface AcademicClass { id:string; campus_id:string; code:string; name:string; sort_order:number; is_active:boolean; }
export interface Section { id:string; academic_class_id:string; code:string; name:string; is_active:boolean; }
export interface Subject { id:string; campus_id:string; code:string; name:string; is_active:boolean; }
export interface Student { id:string; school_id:string; campus_id:string; student_code:string; admission_number:string; first_name:string; middle_name?:string|null; last_name?:string|null; date_of_birth?:string|null; gender?:string|null; government_id?:string|null; photo_url?:string|null; admission_date?:string|null; status:string; category?:string|null; address_line1?:string|null; address_line2?:string|null; city?:string|null; state?:string|null; pincode?:string|null; emergency_contact_name?:string|null; emergency_contact_phone?:string|null; custom_fields:Record<string,unknown>; created_at:string; }
export interface FeeAccountStudent { id:string; student_code:string; admission_number:string; first_name:string; last_name?:string|null; status:string; }
export interface FeeHead { id:string; code:string; name:string; is_misc:boolean; is_active:boolean; }
export interface FeeStructure { id:string; school_id:string; campus_id:string; academic_year_id:string; academic_class_id?:string|null; section_id?:string|null; fee_head_id:string; frequency:string; amount:string; due_date?:string|null; is_active:boolean; }
export interface Charge { id:string; school_id:string; student_id:string; academic_year_id:string; fee_head_id:string; description:string; amount:string; due_date?:string|null; status:string; created_at:string; }

export interface ERPAccessPolicy { id:string; school_id:string; organization_academic_year_id:string; fee_head_id:string; annual_amount:string; is_enabled:boolean; created_at:string; updated_at:string; }
export interface ERPAccessResult { id:string; school_id:string; student_id:string; organization_academic_year_id:string; access_number:string; status:string; login_account_created:boolean; charge_id?:string|null; }
export interface LinkedStudent { id:string; school_id:string; student_code:string; admission_number:string; display_name:string; status:string; }
export interface ParentStudentPortalSummary {
  student:{id:string;student_code:string;admission_number:string;name:string;date_of_birth?:string|null;gender?:string|null;school_name?:string|null;status:string};
  enrollment?:{academic_year:string;academic_year_code:string;class:string;section:string;roll_number?:string|null}|null;
  attendance:Record<string,number>;
  marks:{subject:string;assessment:string;max_marks:string;marks_obtained:string;remarks?:string|null}[];
  fees:{total:string;paid:string;due:string;items:{description:string;amount:string;paid:string;due:string;status:string}[]};
}

export interface Teacher { id:string; school_id:string; campus_id:string; user_id?:string|null; employee_code:string; first_name:string; last_name?:string|null; email?:string|null; phone?:string|null; designation?:string|null; qualification?:string|null; date_of_birth?:string|null; government_id?:string|null; category?:string|null; sub_category?:string|null; custom_fields?:Record<string,unknown>; joining_date?:string|null; status:string; notes?:string|null; is_active:boolean; created_at:string; updated_at:string; }
export interface AttendanceRecord { id:string; school_id:string; campus_id:string; student_id?:string; teacher_id?:string; attendance_date:string; status:string; remarks?:string|null; marked_by?:string|null; marked_at:string; }
export interface DashboardBirthday { student_id:string; name:string; age?:number|null; }
export interface DashboardReminder { type:string; message:string; }
export interface SchoolDashboardSummary { school_id:string; school_code?:string|null; school_name?:string|null; organization_id?:string|null; organization_name?:string|null; academic_year?:string|null; academic_year_code?:string|null; role:string; students:number; teachers:number; present_students_today:number; present_teachers_today:number; fees_due:string|null; fees_collected:string|null; birthdays_today?:DashboardBirthday[]; reminders?:DashboardReminder[]; }

export interface MarkRecord { id:string; school_id:string; campus_id:string; academic_year_id:string; student_id:string; subject_id:string; assessment_name:string; max_marks:string; marks_obtained:string; remarks?:string|null; is_locked:boolean; }

export interface RbacPermission { id:string; code:string; name:string; module:string; description?:string|null; }
export interface RbacRole { id:string; code:string; name:string; description?:string|null; is_system:boolean; school_id?:string|null; organization_id?:string|null; campus_id?:string|null; permissions:string[]; }
export interface AssignableRole { code:string; name:string; }

export interface ImportIssue { row:number; field?:string|null; message:string; }
export interface ImportPreview { sha256:string; row_count:number; valid_count:number; error_count:number; errors:ImportIssue[]; warnings:ImportIssue[]; preview:Record<string,unknown>[]; summary?:Record<string,unknown>; }
export interface ImportResult { imported:number; warnings:number; sha256:string; classes_created?:number; sections_created?:number; }

export interface ReportColumn { key:string; label:string; }
export interface ReportResult { report_key:string; title:string; columns:ReportColumn[]; rows:Record<string,unknown>[]; summary:Record<string,unknown>; total_count:number; generated_at:string; truncated:boolean; }
