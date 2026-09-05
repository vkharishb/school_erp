import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BarChart3, Building2, CalendarCheck2, CircleDollarSign, ClipboardCheck, GraduationCap, IndianRupee, School, Settings, ShieldCheck, UserPlus, UsersRound, WalletCards, type LucideIcon } from "lucide-react";
import { dashboardApi, organizationApi, parentStudentApi, schoolApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import type { LinkedStudent, OrganizationDashboard, ParentStudentPortalSummary, SchoolDashboardSummary } from "../types";
import { apiErrorMessage } from "../utils/apiError";
import { accountLabel } from "../utils/account";
import { hasModule, hasPermission } from "../utils/permissions";
import { DashboardPageFrame, MetricTile, Panel, QuickAction, formatMoney } from "../components/dashboard/DashboardUI";

export default function DashboardPage() {
  const user = useAuthStore(state => state.user);
  const [organization,setOrganization]=useState<OrganizationDashboard|null>(null);
  const [school,setSchool]=useState<SchoolDashboardSummary|null>(null);
  const [platform,setPlatform]=useState<{organizations:number;schools:number;activeSchools:number}|null>(null);
  const [linkedStudents,setLinkedStudents]=useState<LinkedStudent[]>([]);
  const [selectedStudentId,setSelectedStudentId]=useState("");
  const [portal,setPortal]=useState<ParentStudentPortalSummary|null>(null);
  const [error,setError]=useState("");
  const isOrganizationAdmin=user?.account_type==="ORGANIZATION_ADMIN";
  const isParentStudent=user?.account_type==="PARENT_STUDENT";

  useEffect(()=>{
    setError("");setOrganization(null);setSchool(null);setPlatform(null);setPortal(null);
    if(!user)return;
    if(user.is_superuser){Promise.all([organizationApi.list(),schoolApi.list()]).then(([orgs,schools])=>setPlatform({organizations:orgs.length,schools:schools.length,activeSchools:schools.filter(item=>item.is_active).length})).catch(e=>setError(apiErrorMessage(e,"Unable to load platform dashboard.")));return;}
    if(isParentStudent){parentStudentApi.students().then(items=>{setLinkedStudents(items);setSelectedStudentId(items[0]?.id||"");}).catch(e=>setError(apiErrorMessage(e,"Unable to load linked students.")));return;}
    if(isOrganizationAdmin&&user.organization_id){organizationApi.dashboard(user.organization_id).then(setOrganization).catch(e=>setError(apiErrorMessage(e,"Unable to load organization dashboard.")));return;}
    if(user.school_id){dashboardApi.schoolSummary(user.school_id).then(setSchool).catch(e=>setError(apiErrorMessage(e,"Unable to load dashboard.")));}
  },[user?.id,user?.organization_id,user?.school_id,isOrganizationAdmin,isParentStudent]);

  useEffect(()=>{if(!isParentStudent||!selectedStudentId){setPortal(null);return;}parentStudentApi.summary(selectedStudentId).then(setPortal).catch(e=>setError(apiErrorMessage(e,"Unable to load student information.")));},[isParentStudent,selectedStudentId]);

  if(user?.is_superuser)return <PlatformDashboard platform={platform} error={error}/>;
  if(isParentStudent)return <ParentStudentDashboard linkedStudents={linkedStudents} selectedStudentId={selectedStudentId} setSelectedStudentId={setSelectedStudentId} portal={portal} error={error}/>;
  if(isOrganizationAdmin)return <OrganizationAdminDashboard organization={organization} error={error}/>;
  return <SchoolRoleDashboard summary={school} error={error}/>;
}

function PlatformDashboard({platform,error}:{platform:{organizations:number;schools:number;activeSchools:number}|null;error:string}) {
  return <DashboardPageFrame title="Platform Control Center" subtitle="Platform-wide organizations, schools, security and operational control." error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3"><MetricTile label="Organizations" value={platform?.organizations} icon={Building2}/><MetricTile label="Schools / Branches" value={platform?.schools} icon={School} tone="green"/><MetricTile label="Active Schools" value={platform?.activeSchools} icon={ShieldCheck} tone="violet"/></div>
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
      <Panel title="Platform Administration"><div className="grid grid-cols-2 gap-3 md:grid-cols-3"><QuickAction label="Organizations" to="/organizations" icon={Building2}/><QuickAction label="Schools / Branches" to="/schools" icon={School} tone="green"/><QuickAction label="School Administration" to="/school-administration" icon={Settings} tone="amber"/><QuickAction label="System Settings" to="/system-settings" icon={Settings} tone="violet"/><QuickAction label="Backup & Restore" to="/backup-restore" icon={ShieldCheck} tone="green"/><QuickAction label="Reports" to="/reports" icon={BarChart3}/></div></Panel>
      <Panel title="Platform status"><div className="space-y-3 text-sm"><StatusRow label="Active Schools" value={`${platform?.activeSchools??0} / ${platform?.schools??0}`}/><StatusRow label="Environment" value="Development"/><StatusRow label="Licensing / Activation" value="Phase 1 closing milestone"/></div></Panel>
    </div>
  </DashboardPageFrame>;
}

function OrganizationAdminDashboard({organization,error}:{organization:OrganizationDashboard|null;error:string}) {
  const user=useAuthStore(state=>state.user);
  const day=organization?.as_of_date||new Date().toISOString().slice(0,10);
  const reportLink=(report:string)=>`/reports?report=${report}&start_date=${day}&end_date=${day}&run=1`;
  const feeVisible=hasPermission(user,"fee.view")&&hasModule(user,"fee");
  const attendanceVisible=hasPermission(user,"attendance.view")&&hasModule(user,"attendance");
  return <DashboardPageFrame title={organization?.organization_name||"Organization Dashboard"} subtitle={`Consolidated operational and financial view across all schools / branches · ${day}`} error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricTile label="Students" value={organization?.student_count} icon={GraduationCap}/><MetricTile label="Teachers" value={organization?.teacher_count} icon={UsersRound} tone="green"/>
      {feeVisible&&<MetricTile label="Today’s Collection" value={formatMoney(organization?.today_collection)} icon={IndianRupee} tone="amber" to={reportLink("fee_collections")}/>} 
      {feeVisible&&<MetricTile label="Outstanding Dues" value={formatMoney(organization?.outstanding_due)} detail={`Overdue ${formatMoney(organization?.overdue_due)}`} icon={CircleDollarSign} tone="rose" to="/reports?report=fee_dues&run=1"/>}
      {attendanceVisible&&<MetricTile label="Student Attendance" value={`${organization?.student_attendance_percentage?.toFixed(1)??"0.0"}%`} detail={`${organization?.student_attendance_present??0} present / ${organization?.student_attendance_marked??0} marked`} icon={ClipboardCheck} tone="violet"/>}
    </div>
    <Panel title="Branch-wise operations" action={<Link className="btn-secondary" to="/schools">Manage Schools / Branches</Link>}><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left text-gray-500"><th className="py-2 pr-4">Branch</th><th className="pr-4">Students</th><th className="pr-4">Teachers</th><th className="pr-4">Collection</th><th className="pr-4">Dues</th><th></th></tr></thead><tbody>{organization?.units.map(unit=><tr key={unit.school_id} className="border-b last:border-0"><td className="py-3 pr-4"><div className="font-medium text-gray-900">{unit.name}</div><div className="text-xs text-gray-500">{unit.code} · {unit.is_active?"Active":"Inactive"}</div></td><td className="pr-4">{unit.student_count}</td><td className="pr-4">{unit.teacher_count}</td><td className="pr-4">{feeVisible?formatMoney(unit.today_collection):"—"}</td><td className="pr-4">{feeVisible?formatMoney(unit.outstanding_due):"—"}</td><td><Link className="text-sm font-medium text-primary-700 hover:underline" to={`/schools/${unit.school_id}`}>Open →</Link></td></tr>)}</tbody></table>{organization?.units.length===0&&<p className="py-8 text-center text-gray-500">No schools or branches are configured.</p>}</div></Panel>
  </DashboardPageFrame>;
}

function SchoolRoleDashboard({summary,error}:{summary:SchoolDashboardSummary|null;error:string}) {
  const user=useAuthStore(state=>state.user);
  const sid=user?.school_id||summary?.school_id||"";
  const role=accountLabel(user?.account_type);
  const isSchoolAdmin=user?.account_type==="SCHOOL_ADMIN";
  const isAccountant=user?.account_type==="ACCOUNTS";
  const isTeacher=user?.account_type==="TEACHER";
  const isReceptionist=user?.account_type==="RECEPTIONIST";
  const financeVisible=(isSchoolAdmin||isAccountant)&&hasPermission(user,"fee.view")&&hasModule(user,"fee")&&summary?.fees_due!==null;
  const schoolPath=(segment:string)=>sid?`/schools/${sid}/${segment}`:`/${segment}`;
  type ActionTone = "blue"|"green"|"amber"|"rose"|"violet";
  type SchoolQuickAction = {label:string;to:string;icon:LucideIcon;tone:ActionTone};
  const quickActions: SchoolQuickAction[] = isTeacher ? [
    {label:"Mark Attendance",to:schoolPath("attendance"),icon:ClipboardCheck,tone:"violet"},
    {label:"Enter Marks",to:schoolPath("marks"),icon:School,tone:"blue"},
    {label:"Student Records",to:schoolPath("students"),icon:GraduationCap,tone:"green"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"amber"},
  ] : isReceptionist ? [
    {label:"New Student",to:schoolPath("students")+"?view=new",icon:UserPlus,tone:"green"},
    {label:"Student Directory",to:schoolPath("students"),icon:GraduationCap,tone:"blue"},
    {label:"Teacher Directory",to:schoolPath("teachers"),icon:UsersRound,tone:"violet"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"amber"},
  ] : isAccountant ? [
    {label:"Fee Collection",to:schoolPath("fees"),icon:WalletCards,tone:"amber"},
    {label:"Student Lookup",to:schoolPath("students"),icon:GraduationCap,tone:"blue"},
    {label:"Fee Reports",to:schoolPath("reports")+"?report=fee_collections",icon:BarChart3,tone:"green"},
    {label:"Outstanding Dues",to:schoolPath("reports")+"?report=fee_dues",icon:AlertTriangle,tone:"rose"},
  ] : [
    {label:"New Student",to:schoolPath("students")+"?view=new",icon:UserPlus,tone:"green"},
    {label:"Fee Collection",to:schoolPath("fees"),icon:WalletCards,tone:"amber"},
    {label:"Attendance",to:schoolPath("attendance"),icon:ClipboardCheck,tone:"violet"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"blue"},
  ];
  const birthdays=summary?.birthdays_today||[];
  const reminders=summary?.reminders||[];
  return <DashboardPageFrame title={`${role} Dashboard`} subtitle={`${summary?.school_name||"School / Branch"}${summary?.academic_year?` · Academic Year ${summary.academic_year}`:""}`} error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"><MetricTile label="Total Students" value={summary?.students} icon={GraduationCap}/><MetricTile label="Total Teachers" value={summary?.teachers} icon={UsersRound} tone="green"/><MetricTile label="Students Present Today" value={summary?.present_students_today} icon={CalendarCheck2} tone="violet"/><MetricTile label="Teachers Present Today" value={summary?.present_teachers_today} icon={ClipboardCheck} tone="amber"/></div>
    {financeVisible&&<div className="grid grid-cols-1 gap-4 md:grid-cols-2"><MetricTile label="Fees Collected" value={formatMoney(summary?.fees_collected)} icon={IndianRupee} tone="green" to={schoolPath("fees")}/><MetricTile label="Outstanding Fees" value={formatMoney(summary?.fees_due)} icon={CircleDollarSign} tone="rose" to={schoolPath("reports")+"?report=fee_dues"}/></div>}
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
      <Panel title="Quick Actions"><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{quickActions.map(action=><QuickAction key={action.label} label={action.label} to={action.to} icon={action.icon} tone={action.tone}/>)}</div></Panel>
      <Panel title="Current Academic Year"><div className="flex items-center justify-between gap-3"><div><div className="text-2xl font-bold text-gray-900">{summary?.academic_year||"Not active"}</div><div className="mt-1 text-sm text-gray-500">{summary?.academic_year_code||"Academic calendar requires attention"}</div></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${summary?.academic_year?"bg-green-100 text-green-700":"bg-amber-100 text-amber-700"}`}>{summary?.academic_year?"Active":"Pending"}</span></div></Panel>
    </div>
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2"><Panel title={`Today’s Birthdays (${birthdays.length})`}>{birthdays.length?<div className="space-y-3">{birthdays.slice(0,6).map(item=><div key={item.student_id} className="flex items-center justify-between gap-3 border-b border-gray-100 pb-3 last:border-0 last:pb-0"><span className="font-medium text-gray-800">{item.name}</span><span className="text-sm text-gray-500">{item.age?`Turns ${item.age}`:"Birthday today"}</span></div>)}</div>:<p className="text-sm text-gray-500">No student birthdays today.</p>}</Panel><Panel title={`User Reminders (${reminders.length})`}>{reminders.length?<div className="space-y-3">{reminders.map((item,index)=><div key={`${item.type}-${index}`} className="flex items-start gap-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900"><AlertTriangle size={17} className="mt-0.5 shrink-0"/><span>{item.message}</span></div>)}</div>:<p className="text-sm text-gray-500">No pending system reminders for this account.</p>}</Panel></div>
  </DashboardPageFrame>;
}

function ParentStudentDashboard({linkedStudents,selectedStudentId,setSelectedStudentId,portal,error}:{linkedStudents:LinkedStudent[];selectedStudentId:string;setSelectedStudentId:(id:string)=>void;portal:ParentStudentPortalSummary|null;error:string}) {
  return <DashboardPageFrame title={portal?.student.school_name||"Parent / Student Portal"} subtitle="Read-only access to linked student information." error={error}><Panel title="Student"><label className="block max-w-xl"><span className="label">Student</span><select className="input" value={selectedStudentId} onChange={e=>setSelectedStudentId(e.target.value)}><option value="">Select Student</option>{linkedStudents.map(student=><option key={student.id} value={student.id}>{student.display_name} · {student.admission_number}</option>)}</select></label>{linkedStudents.length===0&&<p className="mt-3 text-sm text-gray-500">No students are linked to this access number.</p>}</Panel>{portal&&<><div className="grid grid-cols-1 gap-4 md:grid-cols-3"><MetricTile label="Student" value={portal.student.name} icon={GraduationCap}/><MetricTile label="Class" value={portal.enrollment?`${portal.enrollment.class} / ${portal.enrollment.section}`:"—"} icon={School} tone="green"/><MetricTile label="Academic Year" value={portal.enrollment?.academic_year||"—"} icon={CalendarCheck2} tone="violet"/></div><Panel title="Fees"><div className="grid grid-cols-1 gap-4 md:grid-cols-3"><MetricTile label="Total" value={`₹${portal.fees.total}`} icon={WalletCards}/><MetricTile label="Paid" value={`₹${portal.fees.paid}`} icon={IndianRupee} tone="green"/><MetricTile label="Due" value={`₹${portal.fees.due}`} icon={CircleDollarSign} tone="rose"/></div></Panel></>}</DashboardPageFrame>;
}

function StatusRow({label,value}:{label:string;value:string}) {return <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-2 last:border-0"><span className="text-gray-500">{label}</span><span className="text-right font-medium text-gray-800">{value}</span></div>}
