import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Clock3, IndianRupee, Plus, RefreshCw, School as SchoolIcon, ShieldAlert } from "lucide-react";
import { organizationApi, plannerApi, schoolApi } from "../services/api";
import type { Organization, PlannerAgendaItem, PlannerItem, School } from "../types";
import { apiErrorMessage } from "../utils/apiError";

type ViewMode = "agenda" | "calendar" | "completed";

type PlannerForm = {
  title: string;
  description: string;
  item_type: string;
  priority: string;
  due_at: string;
  organization_id: string;
  school_id: string;
};

const blankForm = (): PlannerForm => ({ title: "", description: "", item_type: "task", priority: "normal", due_at: "", organization_id: "", school_id: "" });
const dateKey = (value?: string | null) => value ? value.slice(0, 10) : "unscheduled";
const fmtDate = (value?: string | null) => value ? new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "No due date";
const clean = (value: string) => value.replace(/_/g, " ");
const todayKey = () => new Date().toISOString().slice(0, 10);
const isOverdue = (item: PlannerAgendaItem) => item.status !== "completed" && !!item.due_at && new Date(item.due_at).getTime() < Date.now();
const sameDay = (item: PlannerAgendaItem, key: string) => dateKey(item.due_at) === key;
const schoolName = (school: School) => school.configuration?.name || school.code;

export default function PlannerPage() {
  const [view, setView] = useState<ViewMode>("agenda");
  const [agenda, setAgenda] = useState<PlannerAgendaItem[]>([]);
  const [completed, setCompleted] = useState<PlannerItem[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [schools, setSchools] = useState<School[]>([]);
  const [form, setForm] = useState<PlannerForm>(() => blankForm());
  const [monthCursor, setMonthCursor] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setError("");
    try {
      const [agendaRows, completedRows, orgRows, schoolRows] = await Promise.all([
        plannerApi.agenda(45),
        plannerApi.items("completed"),
        organizationApi.list(true),
        schoolApi.list(true),
      ]);
      setAgenda(agendaRows.items);
      setCompleted(completedRows);
      setOrganizations(orgRows);
      setSchools(schoolRows);
    } catch (err) {
      setError(apiErrorMessage(err, "Unable to load platform planner."));
    }
  };

  useEffect(() => { void load(); }, []);

  const stats = useMemo(() => {
    const open = agenda.filter(item => item.status !== "completed");
    const weekEnd = Date.now() + 7 * 24 * 60 * 60 * 1000;
    return {
      today: open.filter(item => sameDay(item, todayKey())).length,
      overdue: open.filter(isOverdue).length,
      week: open.filter(item => item.due_at && new Date(item.due_at).getTime() <= weekEnd).length,
      auto: open.filter(item => item.is_auto).length,
    };
  }, [agenda]);

  const visibleSchools = useMemo(() => form.organization_id ? schools.filter(school => school.organization_id === form.organization_id) : schools, [form.organization_id, schools]);
  const grouped = useMemo(() => agenda.reduce<Record<string, PlannerAgendaItem[]>>((acc, item) => { const key = dateKey(item.due_at); (acc[key] ||= []).push(item); return acc; }, {}), [agenda]);
  const calendarDays = useMemo(() => buildCalendar(monthCursor), [monthCursor]);

  const createItem = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    const selectedSchool = schools.find(school => school.id === form.school_id);
    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      item_type: form.item_type,
      priority: form.priority,
      due_at: form.due_at ? new Date(form.due_at).toISOString() : null,
      organization_id: form.organization_id || selectedSchool?.organization_id || null,
      school_id: form.school_id || null,
      metadata_json: { source: "platform_owner_planner" },
    };
    try {
      await plannerApi.create(payload);
      setForm(blankForm());
      setNotice("Planner item added.");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, "Planner item could not be added."));
    } finally {
      setSaving(false);
    }
  };

  const complete = async (item: PlannerAgendaItem | PlannerItem) => {
    setError("");
    try {
      await plannerApi.complete(item.id);
      setNotice("Planner item completed.");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err, "Planner item could not be completed."));
    }
  };

  return <div className="space-y-6">
    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div><h1 className="text-2xl font-bold">Calendar Planner</h1><p className="mt-1 text-gray-500">Platform follow-ups for renewals, payments, activation, onboarding and owner tasks.</p></div>
      <button type="button" className="btn-secondary inline-flex items-center gap-2" onClick={() => void load()}><RefreshCw size={16}/>Refresh</button>
    </div>

    {error&&<div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
    {notice&&<div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">{notice}</div>}

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Metric label="Due Today" value={stats.today} icon={Clock3}/>
      <Metric label="Overdue" value={stats.overdue} icon={ShieldAlert} tone="rose"/>
      <Metric label="Next 7 Days" value={stats.week} icon={CalendarDays} tone="green"/>
      <Metric label="Auto Follow-ups" value={stats.auto} icon={IndianRupee} tone="amber"/>
    </div>

    <form onSubmit={createItem} className="card">
      <div className="flex items-center gap-2"><Plus size={18}/><h2 className="font-semibold">Add Planner Item</h2></div>
      <div className="mt-4 grid gap-4 lg:grid-cols-4">
        <label className="lg:col-span-2"><span className="label">Title *</span><input className="input" required minLength={2} maxLength={255} value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label>
        <label><span className="label">Type</span><select className="input" value={form.item_type} onChange={e=>setForm({...form,item_type:e.target.value})}><option value="task">Task</option><option value="reminder">Reminder</option><option value="follow_up">Follow-up</option><option value="meeting">Meeting</option></select></label>
        <label><span className="label">Priority</span><select className="input" value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option><option value="low">Low</option></select></label>
        <label><span className="label">Due Date</span><input className="input" type="datetime-local" value={form.due_at} onChange={e=>setForm({...form,due_at:e.target.value})}/></label>
        <label><span className="label">Society / Trust</span><select className="input" value={form.organization_id} onChange={e=>setForm({...form,organization_id:e.target.value,school_id:""})}><option value="">None</option>{organizations.map(org=><option key={org.id} value={org.id}>{org.name}</option>)}</select></label>
        <label><span className="label">School</span><select className="input" value={form.school_id} onChange={e=>setForm({...form,school_id:e.target.value})}><option value="">None</option>{visibleSchools.map(school=><option key={school.id} value={school.id}>{schoolName(school)}</option>)}</select></label>
        <label className="lg:col-span-2"><span className="label">Description</span><input className="input" maxLength={4000} value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label>
      </div>
      <button className="btn-primary mt-4 inline-flex items-center gap-2" disabled={saving}><Plus size={16}/>{saving?"Adding...":"Add to Planner"}</button>
    </form>

    <div className="flex gap-2 border-b">{(["agenda","calendar","completed"] as const).map(item=><button key={item} type="button" onClick={()=>setView(item)} className={`px-4 py-3 text-sm font-semibold capitalize ${view===item?"border-b-2 border-primary-600 text-primary-700":"text-gray-500"}`}>{item}</button>)}</div>

    {view==="agenda"&&<section className="grid gap-4 lg:grid-cols-2">{agenda.length===0?<Empty/>:agenda.map(item=><AgendaRow key={item.id} item={item} onComplete={complete}/>)}</section>}
    {view==="calendar"&&<section className="card"><div className="mb-4 flex items-center justify-between"><button type="button" className="btn-secondary" onClick={()=>setMonthCursor(addMonths(monthCursor,-1))}><ChevronLeft size={16}/></button><h2 className="font-semibold">{monthCursor.toLocaleString("en-IN",{month:"long",year:"numeric"})}</h2><button type="button" className="btn-secondary" onClick={()=>setMonthCursor(addMonths(monthCursor,1))}><ChevronRight size={16}/></button></div><div className="grid grid-cols-7 gap-2 text-xs font-semibold text-gray-500">{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(day=><div key={day}>{day}</div>)}</div><div className="mt-2 grid grid-cols-7 gap-2">{calendarDays.map(day=><div key={day.key} className={`min-h-28 rounded-lg border p-2 ${day.currentMonth?"bg-white":"bg-gray-50 text-gray-400"}`}><div className="text-xs font-semibold">{day.date.getDate()}</div><div className="mt-2 space-y-1">{(grouped[day.key]||[]).slice(0,3).map(item=><div key={item.id} className={`truncate rounded px-2 py-1 text-[11px] ${item.is_auto?"bg-blue-50 text-blue-700":"bg-gray-100 text-gray-700"}`}>{item.title}</div>)}{(grouped[day.key]||[]).length>3&&<div className="text-[11px] text-gray-500">+{(grouped[day.key]||[]).length-3} more</div>}</div></div>)}</div></section>}
    {view==="completed"&&<section className="grid gap-4 lg:grid-cols-2">{completed.length===0?<Empty message="No completed planner items."/>:completed.map(item=><CompletedRow key={item.id} item={item}/>)}</section>}
  </div>;
}

function Metric({label,value,icon:Icon,tone="blue"}:{label:string;value:number;icon:typeof CalendarDays;tone?:"blue"|"rose"|"green"|"amber"}) {
  const tones = { blue:"bg-blue-50 text-blue-700", rose:"bg-rose-50 text-rose-700", green:"bg-green-50 text-green-700", amber:"bg-amber-50 text-amber-700" };
  return <div className="card flex items-center gap-4"><span className={`flex h-12 w-12 items-center justify-center rounded-lg ${tones[tone]}`}><Icon size={22}/></span><div><p className="text-sm text-gray-500">{label}</p><p className="text-2xl font-bold">{value}</p></div></div>;
}

function AgendaRow({item,onComplete}:{item:PlannerAgendaItem;onComplete:(item:PlannerAgendaItem)=>void}) {
  const autoLabel = item.is_auto ? "Auto" : "Manual";
  return <article className="card flex flex-col gap-4 md:flex-row md:items-center md:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${item.priority==="urgent"?"bg-rose-100 text-rose-700":item.priority==="high"?"bg-amber-100 text-amber-700":"bg-gray-100 text-gray-700"}`}>{clean(item.priority)}</span><span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">{autoLabel}</span><span className="rounded-full bg-gray-100 px-2 py-1 text-xs capitalize text-gray-600">{clean(item.source)}</span></div><h3 className="mt-2 truncate font-semibold">{item.title}</h3><p className="mt-1 text-sm text-gray-500">{item.description || item.organization_name || item.school_name || "Platform planner item"}</p><p className="mt-2 text-xs text-gray-500">{fmtDate(item.due_at)}{item.organization_name?` · ${item.organization_name}`:""}{item.school_name?` · ${item.school_name}`:""}</p></div><div className="flex shrink-0 gap-2">{item.action_path&&<Link className="btn-secondary text-xs" to={item.action_path}>Open</Link>}{!item.is_auto&&item.status!=="completed"&&<button type="button" className="btn-primary text-xs" onClick={()=>onComplete(item)}><CheckCircle2 size={14}/>Done</button>}</div></article>;
}

function CompletedRow({item}:{item:PlannerItem}) {
  return <article className="card"><div className="flex items-center gap-2 text-green-700"><CheckCircle2 size={18}/><h3 className="font-semibold">{item.title}</h3></div><p className="mt-2 text-sm text-gray-500">{item.description || item.organization_name || item.school_name || "Completed planner item"}</p><p className="mt-2 text-xs text-gray-500">Completed {fmtDate(item.completed_at)}{item.due_at?` · Due ${fmtDate(item.due_at)}`:""}</p></article>;
}

function Empty({message="No planner items found."}:{message?:string}) {
  return <div className="card lg:col-span-2 py-10 text-center text-sm text-gray-500"><SchoolIcon className="mx-auto mb-3 text-gray-400"/> {message}</div>;
}

function addMonths(date: Date, months: number) { return new Date(date.getFullYear(), date.getMonth() + months, 1); }
function buildCalendar(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    return { date, key: date.toISOString().slice(0, 10), currentMonth: date.getMonth() === month.getMonth() };
  });
}
