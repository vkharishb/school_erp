import { useEffect, useRef, useState } from "react";
import { Bell, ChevronDown, LogOut, Search, ShieldCheck, UserRound } from "lucide-react";
import type { SchoolDashboardSummary, User } from "../../types";
import { displayDesignation } from "../../utils/account";

export interface HeaderTenantContext { organization?:string; school?:string; schoolCode?:string; logoUrl?:string; location?:string; }
export default function AppHeader({user,tenant,onAccountSecurity,onProfile,onLogout}:{user:User|null;tenant:HeaderTenantContext;summary:SchoolDashboardSummary|null;onAccountSecurity:()=>void;onProfile:()=>void;onLogout:()=>void}){
 const [menuOpen,setMenuOpen]=useState(false); const ref=useRef<HTMLDivElement>(null);
 const workspaceName=user?.is_superuser?"Platform Owner":tenant.school||tenant.organization||"";
 const workspaceContext=tenant.school&&tenant.organization?tenant.organization:tenant.location||"";
 useEffect(()=>{if(!menuOpen)return;const close=(e:MouseEvent)=>{if(!ref.current?.contains(e.target as Node))setMenuOpen(false)};document.addEventListener("mousedown",close);return()=>document.removeEventListener("mousedown",close)},[menuOpen]);
 return <header className="sticky top-0 z-40 flex h-[68px] items-center border-b border-slate-200 bg-white px-4 lg:px-6">
   <div className="relative w-full max-w-[560px]"><Search size={19} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"/><input className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50/70 pl-11 pr-20 text-sm outline-none transition focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100" placeholder="Search (Society/Trust, Schools, Users, Students, Teachers...)"/><span className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-400">Ctrl + K</span></div>
   {workspaceName&&<div className="mx-4 hidden min-w-0 flex-1 text-right lg:block"><div className="truncate text-sm font-semibold text-slate-900">{workspaceName}</div>{workspaceContext&&<div className="truncate text-xs text-slate-500">{workspaceContext}</div>}</div>}
   <div className="ml-auto flex items-center gap-2 sm:gap-3">
    <button className="relative rounded-xl p-2.5 text-slate-600 hover:bg-slate-100" aria-label="Notifications"><Bell size={21}/><span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white"/></button>
    <div className="mx-1 hidden h-8 w-px bg-slate-200 md:block"/>
    <div className="relative" ref={ref}><button onClick={()=>setMenuOpen(v=>!v)} className="flex items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-slate-50"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-700 font-semibold text-white">{(user?.full_name||user?.username||"U").split(/\s+/).map(x=>x[0]).slice(0,2).join("").toUpperCase()}</span><span className="hidden text-left md:block"><span className="block max-w-48 truncate text-sm font-semibold text-slate-900">{user?.full_name||user?.username}</span><span className="block text-xs text-slate-500">{displayDesignation(user)}</span></span><ChevronDown size={16} className="text-slate-500"/></button>
    {menuOpen&&<div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"><button onClick={()=>{setMenuOpen(false);onProfile()}} className="flex w-full gap-3 px-4 py-3 text-sm hover:bg-slate-50"><UserRound size={18}/>My Profile</button><button onClick={()=>{setMenuOpen(false);onAccountSecurity()}} className="flex w-full gap-3 px-4 py-3 text-sm hover:bg-slate-50"><ShieldCheck size={18}/>Account Security</button><button onClick={()=>{setMenuOpen(false);onLogout()}} className="flex w-full gap-3 border-t px-4 py-3 text-sm text-red-600 hover:bg-red-50"><LogOut size={18}/>Logout</button></div>}</div>
   </div>
 </header>
}