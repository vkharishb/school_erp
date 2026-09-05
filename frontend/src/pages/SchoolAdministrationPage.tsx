import { Link } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { Building2, School, Users, ShieldCheck, Boxes, CalendarRange, GraduationCap, BookOpen, ScrollText, DatabaseBackup, Settings, UploadCloud } from "lucide-react";
import { canAccessSchoolDirectory, hasAnyPermission, hasPermission } from "../utils/permissions";
import { canAccessBulkImports } from "../utils/bulkImports";
import { canManageOrganizationAcademicYears } from "../utils/academicYears";

export default function SchoolAdministrationPage(){
 const user=useAuthStore(s=>s.user); const sid=user?.school_id;
 const canBulkImport=canAccessBulkImports(user);
 const schoolTarget=(segment:string)=>sid?`/schools/${sid}/${segment}`:`/schools?next=${segment}`;
 const items=[
  ...(canAccessSchoolDirectory(user)?[{title:"Organizations",desc:"Organization details, annual correction and School capacity.",to:"/organizations",icon:Building2,show:hasPermission(user,"organization.view")},{title:"Schools / Branches",desc:"Create and maintain the complete School / Branch profile.",to:"/schools",icon:School,show:true}]:[]),
  {title:"Users",desc:"Create school-level logins, reset passwords and enable/disable accounts.",to:schoolTarget("users"),icon:Users,show:hasPermission(user,"user.view")},
  {title:"Roles & Permissions",desc:"Platform role and permission matrix. Super Admin only.",to:schoolTarget("roles"),icon:ShieldCheck,show:!!user?.is_superuser},
  {title:"Modules",desc:"Enable/disable licensed modules for a selected school. Super Admin only.",to:schoolTarget("modules"),icon:Boxes,show:!!user?.is_superuser},
  {title:"Academic Years",desc:canManageOrganizationAcademicYears(user)?"Create, review and activate organization-wide academic years.":"View the organization Academic Year and its current state.",to:schoolTarget("academic-years"),icon:CalendarRange,show:hasAnyPermission(user,["academic_year.view","academic_year.manage"])},
  {title:"Classes & Sections",desc:"Create campus classes and sections used by enrollment, fees and marks.",to:schoolTarget("classes-sections"),icon:GraduationCap,show:hasPermission(user,"academic_class.manage")||hasPermission(user,"school.config.view")},
  {title:"Subjects",desc:"Create and maintain campus subject masters.",to:schoolTarget("subjects"),icon:BookOpen,show:hasPermission(user,"subject.manage")||hasPermission(user,"school.config.view")},
  {title:"Bulk Imports",desc:"Classes & sections, students, teachers, fee structures and prior-year dues imports. Marks upload stays in Marks.",to:schoolTarget("bulk-imports"),icon:UploadCloud,show:canBulkImport},
  {title:"Audit Logs",desc:"Read-only security and change history for your authorized scope.",to:schoolTarget("audit"),icon:ScrollText,show:hasPermission(user,"audit.view")},
  {title:"Backup & Restore",desc:"Database backup policy and controlled restore operations.",to:"/backup-restore",icon:DatabaseBackup,show:!!user?.is_superuser},
  {title:"System Settings",desc:"Platform security and operational settings. Super Admin only.",to:"/system-settings",icon:Settings,show:!!user?.is_superuser},
 ].filter(i=>i.show);
 return <div className="space-y-6"><div><h1 className="text-2xl font-bold">School Administration</h1><p className="text-gray-500 mt-1">Organization, school, users, academics, modules, audit and system controls.</p>{user?.is_superuser&&<p className="text-sm text-blue-700 mt-2">For school-level functions, select the school/branch first; the ERP opens the requested function directly.</p>}</div><div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">{items.map(i=>{const Icon=i.icon;return <Link key={i.title} to={i.to} className="card hover:border-primary-300 transition"><div className="flex items-start gap-3"><div className="rounded-lg bg-primary-50 p-2 text-primary-700"><Icon size={20}/></div><div><h2 className="font-semibold">{i.title}</h2><p className="text-sm text-gray-500 mt-1">{i.desc}</p></div></div></Link>})}</div></div>;
}
