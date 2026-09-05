import { useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, Building2, ChevronDown, ChevronRight, ClipboardCheck, GraduationCap, LayoutDashboard, School, UsersRound, WalletCards } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { User } from "../../types";
import { primaryNavigationVisibility } from "../../utils/navigation";
import { hasAnyPermission, hasPermission } from "../../utils/permissions";
import { canAccessBulkImports } from "../../utils/bulkImports";

interface SubLink { label: string; to: string; show?: boolean; }
interface MainLink { label: string; to: string; icon: LucideIcon; show: boolean; children?: SubLink[]; }

const linkClass = ({isActive}:{isActive:boolean}) => `flex min-h-11 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-primary-100 text-primary-900" : "text-gray-700 hover:bg-gray-100"}`;

export default function AppSidebar({user}:{user:User|null}) {
  const visibility = primaryNavigationVisibility(user);
  const sid = user?.school_id || "";
  const location = useLocation();
  const [expanded, setExpanded] = useState<Record<string,boolean>>({});
  const schoolPath = (segment:string) => sid ? `/schools/${sid}/${segment}` : `/${segment}`;
  const canBulk = canAccessBulkImports(user);

  const links = useMemo<MainLink[]>(() => [
    {label:"Dashboard",to:"/",icon:LayoutDashboard,show:true},
    {label:"School Administration",to:"/school-administration",icon:Building2,show:visibility.schoolAdministration,children:[
      {label:"Users",to:schoolPath("users"),show:!!sid&&hasPermission(user,"user.view")},
      {label:"Academic Years",to:schoolPath("academic-years"),show:!!sid&&hasAnyPermission(user,["academic_year.view","academic_year.manage"])},
      {label:"Classes & Sections",to:schoolPath("classes-sections"),show:!!sid&&hasAnyPermission(user,["academic_class.manage","school.config.view"])},
      {label:"Subjects",to:schoolPath("subjects"),show:!!sid&&hasAnyPermission(user,["subject.manage","school.config.view"])},
      {label:"Bulk Imports",to:schoolPath("bulk-imports"),show:!!sid&&canBulk},
      {label:"Audit Logs",to:schoolPath("audit"),show:!!sid&&hasPermission(user,"audit.view")},
    ]},
    {label:"Student Management",to:"/students",icon:GraduationCap,show:visibility.students,children:[
      {label:"Student Records",to:schoolPath("students")},
      {label:"Bulk Import",to:schoolPath("bulk-imports"),show:!!sid&&hasPermission(user,"student.bulk_upload")},
      {label:"Student Reports",to:schoolPath("reports")+"?report=students",show:visibility.reports},
    ]},
    {label:"Teacher Management",to:"/teachers",icon:UsersRound,show:visibility.teachers,children:[
      {label:"Teacher / Staff Records",to:schoolPath("teachers")},
      {label:"Bulk Import",to:schoolPath("bulk-imports"),show:!!sid&&hasPermission(user,"teacher.bulk_upload")},
      {label:"Teacher Reports",to:schoolPath("reports")+"?report=teachers",show:visibility.reports},
    ]},
    {label:"Fee Management",to:"/fees",icon:WalletCards,show:visibility.fees,children:[
      {label:"Fee Operations",to:schoolPath("fees")},
      {label:"Fee Reports",to:schoolPath("reports")+"?report=fee_collections",show:visibility.reports},
    ]},
    {label:"Marks",to:"/marks",icon:School,show:visibility.marks,children:[
      {label:"Marks Entry / Results",to:schoolPath("marks")},
      {label:"Marks Reports",to:schoolPath("reports")+"?report=marks_performance",show:visibility.reports},
    ]},
    {label:"Attendance",to:"/attendance",icon:ClipboardCheck,show:visibility.attendance,children:[
      {label:"Attendance",to:schoolPath("attendance")},
      {label:"Attendance Reports",to:schoolPath("reports")+"?report=student_attendance",show:visibility.reports},
    ]},
    {label:"Reports",to:"/reports",icon:BarChart3,show:visibility.reports},
  ].filter(link => link.show), [sid,user,visibility.schoolAdministration,visibility.students,visibility.teachers,visibility.fees,visibility.marks,visibility.attendance,visibility.reports,canBulk]);

  const childVisible = (child:SubLink) => child.show !== false;
  return <aside className="w-64 shrink-0 border-r border-gray-200 bg-white">
    <nav className="space-y-1 p-3" aria-label="Main navigation">
      {links.map(link => {
        const Icon = link.icon;
        const children = (link.children || []).filter(childVisible);
        const routeActive = link.to === "/" ? location.pathname === "/" : location.pathname.startsWith(link.to) || children.some(child => location.pathname.startsWith(child.to.split("?")[0]));
        const open = expanded[link.label] ?? routeActive;
        return <div key={link.label}>
          <div className="flex items-center gap-1">
            <NavLink to={link.to} end={link.to==="/"} className={({isActive})=>`${linkClass({isActive:isActive||routeActive})} flex-1`}><Icon size={19}/><span className="min-w-0 flex-1 truncate">{link.label}</span></NavLink>
            {children.length>0&&<button type="button" aria-label={`${open?"Collapse":"Expand"} ${link.label}`} onClick={()=>setExpanded(prev=>({...prev,[link.label]:!open}))} className="flex h-10 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100">{open?<ChevronDown size={17}/>:<ChevronRight size={17}/>}</button>}
          </div>
          {open&&children.length>0&&<div className="ml-7 mt-1 space-y-0.5 border-l border-gray-200 pl-3">{children.map(child=><NavLink key={`${link.label}-${child.label}`} to={child.to} className={({isActive})=>`block rounded-md px-2 py-2 text-xs ${isActive?"bg-primary-50 font-semibold text-primary-800":"text-gray-600 hover:bg-gray-50 hover:text-gray-900"}`}>{child.label}</NavLink>)}</div>}
        </div>;
      })}
    </nav>
  </aside>;
}
