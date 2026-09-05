import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { attendanceApi, studentApi, teacherApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { hasPermission } from "../utils/permissions";
import type { Student, Teacher } from "../types";
import { apiErrorMessage } from "../utils/apiError";

type Kind = "students" | "teachers";
const statuses = ["present", "absent", "late", "half_day", "leave"];
export default function AttendancePage() {
  const { schoolId = "" } = useParams();
  const user = useAuthStore((s) => s.user);
  const canMark = hasPermission(user, "attendance.mark");
  const [kind, setKind] = useState<Kind>("students");
  const [day, setDay] = useState(new Date().toISOString().slice(0,10));
  const [students, setStudents] = useState<Student[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [marks, setMarks] = useState<Record<string,string>>({});
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const people = useMemo(() => kind === "students" ? students.map((s)=>({id:s.id, code:s.admission_number, name:`${s.first_name} ${s.last_name || ""}`})) : teachers.map((t)=>({id:t.id, code:t.employee_code, name:`${t.first_name} ${t.last_name || ""}`})), [kind,students,teachers]);
  const load = async () => {
    try {
      const [s,t,existing] = await Promise.all([studentApi.list(schoolId), teacherApi.list(schoolId), kind === "students" ? attendanceApi.students(schoolId, day) : attendanceApi.teachers(schoolId, day)]);
      setStudents(s); setTeachers(t); const m:Record<string,string>={}; existing.forEach((r)=>m[kind === "students" ? r.student_id! : r.teacher_id!] = r.status); setMarks(m);
    } catch (err:unknown) { setError(apiErrorMessage(err,"Failed to load attendance")); }
  };
  useEffect(()=>{ if(schoolId) void load(); },[schoolId,kind,day]);
  const save = async () => { setError(""); setMessage(""); try { const records=people.map((p)=>({entity_id:p.id,status:marks[p.id] || "present"})); if(kind === "students") await attendanceApi.markStudents(schoolId,{attendance_date:day,records}); else await attendanceApi.markTeachers(schoolId,{attendance_date:day,records}); setMessage(`${kind === "students" ? "Student" : "Teacher"} attendance saved for ${day}`); await load(); } catch(err:unknown){ setError(apiErrorMessage(err,"Failed to save attendance")); } };
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold">Attendance</h1><p className="text-gray-500 mt-1">Daily student and teacher attendance.</p></div>
    {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}{message && <div className="rounded-lg bg-green-50 border border-green-200 text-green-700 px-4 py-3 text-sm">{message}</div>}
    <section className="card"><div className="flex flex-wrap gap-3 items-end"><label><span className="label">Attendance Type</span><select className="input" value={kind} onChange={(e)=>setKind(e.target.value as Kind)}><option value="students">Students</option><option value="teachers">Teachers</option></select></label><label><span className="label">Date</span><input className="input" type="date" value={day} onChange={(e)=>setDay(e.target.value)} /></label><div className="text-sm text-gray-500 pb-2">{people.length} record(s)</div></div></section>
    <section className="card"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="py-2">Code</th><th>Name</th><th>Attendance</th></tr></thead><tbody>{people.map((p)=><tr key={p.id} className="border-b last:border-0"><td className="py-3 font-mono">{p.code}</td><td>{p.name}</td><td><select className="input max-w-40" value={marks[p.id] || "present"} disabled={!canMark} onChange={(e)=>setMarks({...marks,[p.id]:e.target.value})}>{statuses.map((s)=><option key={s} value={s}>{s.replace("_"," ")}</option>)}</select></td></tr>)}</tbody></table>{people.length===0 && <div className="py-8 text-center text-gray-500">No records found.</div>}</div>{canMark && people.length>0 && <div className="pt-4"><button className="btn-primary" onClick={()=>void save()}>Save Attendance</button></div>}</section>
  </div>;
}
