import { useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { BarChart3, CalendarDays, Building2, ChevronDown, ChevronLeft, ChevronRight, ClipboardCheck, CreditCard, DatabaseBackup, GraduationCap, KeyRound, Layers3, LayoutDashboard, Lock, School, Settings, UsersRound, WalletCards, ClipboardList } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { User } from "../../types";
import { primaryNavigationVisibility } from "../../utils/navigation";
import { hasAnyPermission, hasPermission, isAdminLevel } from "../../utils/permissions";
import { canAccessBulkImports } from "../../utils/bulkImports";
import { branding } from "../../config/branding";

interface SubLink { label: string; to: string; show?: boolean; }
interface MainLink { label: string; to: string; icon: LucideIcon; show: boolean; children?: SubLink[]; }

const linkClass = ({isActive}:{isActive:boolean}) => `flex min-h-11 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-primary-100 text-primary-900" : "text-gray-700 hover:bg-gray-100"}`;

export default function AppSidebar({user}:{user:User|null}) {
  const visibility = primaryNavigationVisibility(user);
  const sid = user?.school_id || "";
  const location = useLocation();
  const [expanded, setExpanded] = useState<Record<string,boolean>>({});
  const [collapsed,setCollapsed]=useState(()=>localStorage.getItem("erp.sidebar.collapsed")==="1");
  useEffect(()=>localStorage.setItem("erp.sidebar.collapsed",collapsed?"1":"0"),[collapsed]);
  const schoolPath = (segment:string) => sid ? `/schools/${sid}/${segment}` : `/${segment}`;
  const canBulk = canAccessBulkImports(user);

  if(user?.is_superuser){
    const platformLinks:MainLink[]=[
      {label:"Dashboard",to:"/",icon:LayoutDashboard,show:true},
      {label:"Planner",to:"/planner",icon:CalendarDays,show:true},
      {label:"Society / Trust",to:"/organizations?view=list",icon:Building2,show:true,children:[
        {label:"Society/Trust List",to:"/organizations?view=list"},{label:"Add Society/Trust",to:"/organizations?view=create"}
      ]},
      {label:"Schools",to:"/schools?view=list",icon:School,show:true,children:[
        {label:"School List",to:"/schools?view=list"},{label:"Create School",to:"/schools?view=create"},{label:"School Capacity",to:"/schools?view=capacity"}
      ]},
      {label:"Subscriptions",to:"/subscriptions",icon:Layers3,show:true,children:[
        {label:"Plans",to:"/subscriptions?tab=plans"},{label:"Subscriptions",to:"/subscriptions?tab=subscriptions"},{label:"Entitlements",to:"/subscriptions?tab=entitlements"},{label:"Activation Keys",to:"/subscriptions?tab=keys"},{label:"Renewals",to:"/subscriptions?tab=renewals"},{label:"Reminders",to:"/subscriptions?tab=reminders"}
      ]},
      {label:"Payments",to:"/payments",icon:CreditCard,show:true,children:[
        {label:"Payment Details",to:"/payments?tab=details"},{label:"Receipts",to:"/payments?tab=receipts"},{label:"Financial Details",to:"/payments?tab=financial"}
      ]},
      {label:"Users",to:"/users",icon:UsersRound,show:true},
      {label:"System Settings",to:"/system-settings",icon:Settings,show:true},
      {label:"Reports",to:"/reports",icon:BarChart3,show:true},
      {label:"Audit Logs",to:"/audit",icon:ClipboardList,show:true},
      {label:"Backup & Restore",to:"/backup-restore",icon:DatabaseBackup,show:true},
    ];
    const childVisible=(child:SubLink)=>child.show!==false;
    return <aside className={`${collapsed?"w-[76px]":"w-64"} sticky top-0 flex h-screen shrink-0 flex-col border-r border-slate-800 bg-gradient-to-b from-[#07142f] to-[#102a55] text-white transition-[width] duration-200`}>
      <div className={`flex h-[76px] items-center ${collapsed?"justify-center":"gap-3 px-4"} border-b border-white/10`}><span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-blue-600"><img src={branding.logoUrl} alt="" className="h-8 w-8 object-contain"/></span>{!collapsed&&<div><div className="font-bold">{branding.productName}</div><div className="text-xs text-blue-200">{branding.releaseVersion}</div></div>}</div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Platform navigation">{platformLinks.map(link=>{const Icon=link.icon;const children=(link.children||[]).filter(childVisible);const basePath=link.to.split("?")[0];const routeActive=link.to==="/"?location.pathname==="/":location.pathname.startsWith(basePath);const open=expanded[link.label]??routeActive;return <div key={link.label}><div className="flex items-center gap-1"><NavLink title={collapsed?link.label:undefined} to={link.to} end={link.to==="/"} className={()=>`flex min-h-11 flex-1 items-center ${collapsed?"justify-center":"gap-3"} rounded-lg px-3 py-2.5 text-sm font-medium transition ${routeActive?"bg-blue-600 text-white shadow":"text-slate-200 hover:bg-white/10 hover:text-white"}`}><Icon size={20}/>{!collapsed&&<span className="min-w-0 flex-1 truncate">{link.label}</span>}</NavLink>{!collapsed&&children.length>0&&<button type="button" aria-label={`${open?"Collapse":"Expand"} ${link.label}`} onClick={()=>setExpanded(prev=>({...prev,[link.label]:!open}))} className="flex h-10 w-9 items-center justify-center rounded-lg text-slate-300 hover:bg-white/10">{open?<ChevronDown size={17}/>:<ChevronRight size={17}/>}</button>}</div>{!collapsed&&open&&children.length>0&&<div className="ml-7 mt-1 space-y-0.5 border-l border-white/15 pl-3">{children.map(child=><NavLink key={`${link.label}-${child.label}`} to={child.to} className="block rounded-md px-2 py-2 text-xs text-slate-300 hover:bg-white/10 hover:text-white">{child.label}</NavLink>)}</div>}</div>})}</nav>
      <button onClick={()=>setCollapsed(v=>!v)} className={`m-3 flex min-h-11 items-center ${collapsed?"justify-center":"gap-3"} rounded-lg bg-white/10 px-3 text-sm hover:bg-white/15`} title={collapsed?"Expand Menu":"Collapse Menu"}>{collapsed?<ChevronRight size={18}/>:<ChevronLeft size={18}/>} {!collapsed&&"Collapse Menu"}</button>
    </aside>;
  }

  const links = useMemo<MainLink[]>(() => [
    {label:"Dashboard",to:"/",icon:LayoutDashboard,show:true},
    {label:"ERP Activation",to:"/erp-activation",icon:KeyRound,show:user?.account_type==="ORGANIZATION_ADMIN"},
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
  const entitled = new Set(user?.enabled_modules || []);
  const lockedModules = isAdminLevel(user) ? [
    ["Student Management","student"],["Teacher Management","teacher"],["Fee Management","fee"],
    ["Marks","marks"],["Attendance","attendance"],["Reports","reports"],
  ].filter(([,code])=>!entitled.has(code)) : [];
  return <aside className={`${collapsed?"w-[76px]":"w-64"} sticky top-0 h-screen shrink-0 border-r border-gray-200 bg-white transition-[width] duration-200`}>
    <nav className="space-y-1 p-3" aria-label="Main navigation">
      {links.map(link => {
        const Icon = link.icon;
        const children = (link.children || []).filter(childVisible);
        const routeActive = link.to === "/" ? location.pathname === "/" : location.pathname.startsWith(link.to) || children.some(child => location.pathname.startsWith(child.to.split("?")[0]));
        const open = expanded[link.label] ?? routeActive;
        return <div key={link.label}>
          <div className="flex items-center gap-1">
            <NavLink to={link.to} end={link.to==="/"} className={({isActive})=>`${linkClass({isActive:isActive||routeActive})} flex-1`}><Icon size={19}/>{!collapsed&&<span className="min-w-0 flex-1 truncate">{link.label}</span>}</NavLink>
            {!collapsed&&children.length>0&&<button type="button" aria-label={`${open?"Collapse":"Expand"} ${link.label}`} onClick={()=>setExpanded(prev=>({...prev,[link.label]:!open}))} className="flex h-10 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100">{open?<ChevronDown size={17}/>:<ChevronRight size={17}/>}</button>}
          </div>
          {!collapsed&&open&&children.length>0&&<div className="ml-7 mt-1 space-y-0.5 border-l border-gray-200 pl-3">{children.map(child=><NavLink key={`${link.label}-${child.label}`} to={child.to} className={({isActive})=>`block rounded-md px-2 py-2 text-xs ${isActive?"bg-primary-50 font-semibold text-primary-800":"text-gray-600 hover:bg-gray-50 hover:text-gray-900"}`}>{child.label}</NavLink>)}</div>}
        </div>;
      })}
      {!collapsed&&lockedModules.length>0&&<div className="mt-3 border-t pt-3"><p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Available with other plans</p>{lockedModules.map(([label,code])=><div key={code} className="flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-400" title="Locked by subscription plan"><Lock size={16}/><span>{label}</span><span className="ml-auto text-[10px] uppercase">Locked</span></div>)}</div>}
      <button onClick={()=>setCollapsed(v=>!v)} className="m-3 flex min-h-10 items-center justify-center rounded-lg border text-sm" title={collapsed?"Expand Menu":"Collapse Menu"}>{collapsed?<ChevronRight size={18}/>:<><ChevronLeft size={18}/><span className="ml-2">Collapse Menu</span></>}</button>
    </nav>
  </aside>;
}
