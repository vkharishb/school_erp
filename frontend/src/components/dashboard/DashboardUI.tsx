import { Link } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

export function DashboardPageFrame({title,subtitle,error,children}:{title:string;subtitle:string;error?:string;children:React.ReactNode}) {
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold text-gray-900">{title}</h1><p className="mt-1 text-gray-500">{subtitle}</p></div>{error&&<div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}{children}</div>;
}

export function MetricTile({label,value,detail,icon:Icon,to,tone="blue"}:{label:string;value:string|number|null|undefined;detail?:string;icon:LucideIcon;to?:string;tone?:"blue"|"green"|"amber"|"rose"|"violet"}) {
  const tones={blue:"bg-blue-50 text-blue-700",green:"bg-green-50 text-green-700",amber:"bg-amber-50 text-amber-700",rose:"bg-rose-50 text-rose-700",violet:"bg-violet-50 text-violet-700"};
  const body=<div className="card h-full transition hover:border-primary-200"><div className="flex items-start gap-4"><div className={`rounded-xl p-3 ${tones[tone]}`}><Icon size={24}/></div><div className="min-w-0"><p className="text-sm font-medium text-gray-500">{label}</p><p className="mt-1 text-2xl font-bold text-gray-900">{value ?? "—"}</p>{detail&&<p className="mt-1 text-xs text-gray-500">{detail}</p>}</div></div></div>;
  return to?<Link to={to} className="block">{body}</Link>:body;
}

export function QuickAction({label,to,icon:Icon,tone="blue"}:{label:string;to:string;icon:LucideIcon;tone?:"blue"|"green"|"amber"|"rose"|"violet"}) {
  const tones={blue:"bg-blue-50 text-blue-700",green:"bg-green-50 text-green-700",amber:"bg-amber-50 text-amber-700",rose:"bg-rose-50 text-rose-700",violet:"bg-violet-50 text-violet-700"};
  return <Link to={to} className="flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border border-gray-100 bg-white p-4 text-center shadow-sm transition hover:border-primary-300 hover:bg-primary-50"><span className={`rounded-xl p-2 ${tones[tone]}`}><Icon size={22}/></span><span className="text-sm font-semibold text-gray-800">{label}</span></Link>;
}

export function Panel({title,children,action}:{title:string;children:React.ReactNode;action?:React.ReactNode}) {
  return <section className="card"><div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-base font-semibold text-gray-900">{title}</h2>{action}</div>{children}</section>;
}

export function formatMoney(value?:string|null) {
  const amount=Number(value||0);
  return `₹${Number.isFinite(amount)?amount.toLocaleString("en-IN",{minimumFractionDigits:2,maximumFractionDigits:2}):"0.00"}`;
}
