import { useEffect, useRef, useState } from "react";
import { Bell, CalendarDays, ChevronDown, GraduationCap, LogOut, ShieldCheck, UserRound } from "lucide-react";
import type { SchoolDashboardSummary, User } from "../../types";
import { branding } from "../../config/branding";
import { displayDesignation } from "../../utils/account";

export interface HeaderTenantContext {
  organization?: string;
  school?: string;
  schoolCode?: string;
  logoUrl?: string;
  location?: string;
}

export default function AppHeader({
  user,
  tenant,
  summary,
  onAccountSecurity,
  onLogout,
}: {
  user: User | null;
  tenant: HeaderTenantContext;
  summary: SchoolDashboardSummary | null;
  onAccountSecurity: () => void;
  onLogout: () => void;
}) {
  const [now, setNow] = useState(() => new Date());
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  const platform = !!user?.is_superuser;
  const parentStudent = user?.account_type === "PARENT_STUDENT";
  const organizationName = platform ? branding.productName : tenant.organization || branding.schoolName;
  const contextTitle = platform
    ? "Platform Control Center"
    : parentStudent
      ? "Parent / Student Portal"
      : tenant.school || (tenant.organization ? "All Schools / Branches" : branding.schoolName);
  const contextSubtitle = platform
    ? "School ERP administration"
    : parentStudent
      ? (user?.full_name || "Linked student access")
      : tenant.school
        ? [tenant.schoolCode, tenant.location].filter(Boolean).join(" · ") || tenant.organization || "School / Branch"
        : tenant.organization || "Organization Administration";
  const birthdays = summary?.birthdays_today || [];
  const reminders = summary?.reminders || [];
  const showTicker = !platform && !!tenant.school;
  const dateLabel = new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }).format(now);
  const timeLabel = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(now);

  return <>
    <header className="erp-header border-b border-gray-200 bg-white px-4 py-3 lg:px-6">
      <div className="grid min-w-0 grid-cols-1 items-center gap-3 lg:grid-cols-[minmax(220px,1fr)_minmax(280px,1.35fr)_minmax(300px,1fr)]">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-gray-200 bg-white text-primary-700">
            {tenant.logoUrl ? <img src={tenant.logoUrl} alt="School logo" className="h-full w-full object-contain p-1"/> : <GraduationCap size={28}/>} 
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold uppercase tracking-[0.16em] text-gray-400">{platform ? "School ERP" : "Organization"}</p>
            <p className="truncate text-base font-bold text-gray-900" title={organizationName}>{organizationName}</p>
          </div>
        </div>

        <div className="min-w-0 text-left lg:text-center">
          <h1 className="truncate text-lg font-bold text-gray-900 lg:text-xl" title={contextTitle}>{contextTitle}</h1>
          <p className="truncate text-sm text-gray-500" title={contextSubtitle}>{contextSubtitle}</p>
        </div>

        <div className="flex min-w-0 items-center justify-between gap-3 lg:justify-end">
          <div className="hidden items-center gap-2 border-r border-gray-200 pr-4 text-sm text-gray-600 sm:flex">
            <CalendarDays size={19} className="text-primary-700"/>
            <div><div className="font-medium text-gray-800">{dateLabel}</div><div className="text-xs text-gray-500">{timeLabel}</div></div>
          </div>
          <div className="hidden rounded-full bg-primary-50 p-2 text-primary-700 md:block" aria-label="Notifications"><Bell size={20}/></div>
          <div className="relative" ref={menuRef}>
            <button type="button" onClick={() => setMenuOpen(v => !v)} className="flex min-h-11 items-center gap-2 rounded-xl px-2 py-1.5 text-left hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500" aria-expanded={menuOpen} aria-haspopup="menu">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-800"><UserRound size={20}/></div>
              <div className="hidden min-w-0 md:block"><div className="max-w-40 truncate text-sm font-semibold text-gray-900">{user?.full_name || user?.username || "User"}</div><div className="max-w-40 truncate text-xs text-gray-500">{displayDesignation(user)}</div></div>
              <ChevronDown size={16} className="text-gray-500"/>
            </button>
            {menuOpen && <div role="menu" className="absolute right-0 z-50 mt-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg">
              <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onAccountSecurity(); }} className="flex w-full items-center gap-3 px-4 py-3 text-sm text-gray-700 hover:bg-gray-50"><ShieldCheck size={18} className="text-primary-700"/>Account Security</button>
              <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onLogout(); }} className="flex w-full items-center gap-3 border-t border-gray-100 px-4 py-3 text-sm text-red-600 hover:bg-red-50"><LogOut size={18}/>Logout</button>
            </div>}
          </div>
        </div>
      </div>
    </header>
    {showTicker && <div className="context-ticker border-b border-primary-100 bg-primary-50/70" aria-label="School notices">
      <div className="context-ticker-track flex min-w-max items-center gap-10 px-6 py-2 text-sm">
        <span className="font-medium text-primary-800">🎂 Today&apos;s Birthdays: {birthdays.length ? birthdays.map(item => `${item.name}${item.age ? ` (${item.age})` : ""}`).join(", ") : "None"}</span>
        {reminders.length ? reminders.map((item, index) => <span key={`${item.type}-${index}`} className="font-medium text-amber-700">🔔 {item.message}</span>) : <span className="text-gray-500">🔔 No pending system reminders</span>}
        {summary?.academic_year && <span className="font-medium text-gray-600">Academic Year: {summary.academic_year}</span>}
      </div>
    </div>}
  </>;
}
