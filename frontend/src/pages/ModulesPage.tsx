import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { schoolApi } from "../services/api";
import type { SchoolLicense } from "../types";
import { apiErrorMessage } from "../utils/apiError";

const modules = [
  ["dashboard", "Dashboard", 1], ["school_admin", "School Administration", 1], ["school_config", "School Configuration", 1], ["student", "Student Management", 1],
  ["teacher", "Teacher Management", 1], ["fee", "Fee Management", 1], ["marks", "Marks", 1], ["attendance", "Attendance", 1], ["reports", "Reports", 1],
  ["exams", "Exams", 2], ["timetable", "Timetable", 2], ["homework", "Homework", 2], ["online_classes", "Online Classes", 2],
  ["lesson_plans", "Lesson Plans", 2], ["certificates", "Certificates", 2], ["id_cards", "ID Cards", 2],
  ["communication", "Communication", 3], ["transport", "Transport Management", 3], ["gate_pass", "Gate Pass", 3],
  ["hostel", "Hostel Management", 3], ["call_logs", "Call Logs", 3], ["pickup_drop_alerts", "Parent Pickup & Drop Alerts", 3],
  ["smart_attendance", "Smart Attendance", 4], ["face_attendance", "Face Recognition Attendance", 4], ["biometric", "Biometric Integration", 4],
  ["live_gps", "Live GPS Tracking", 4], ["route_monitoring", "Route Monitoring", 4], ["driver_app", "Driver Mobile App", 4],
] as const;

export default function ModulesPage() {
  const { schoolId = "" } = useParams();
  const [license, setLicense] = useState<SchoolLicense | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (schoolId) void schoolApi.getLicense(schoolId).then(setLicense).catch((e) => setError(apiErrorMessage(e,"Failed to load modules"))); }, [schoolId]);
  if (error && !license) return <div className="text-red-600">{error}</div>;
  if (!license) return <div className="text-gray-500">Loading modules…</div>;
  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold">ERP Modules</h1><p className="text-gray-500 mt-1">All Phase 1 modules are the mandatory School ERP core and remain enabled. Future licensed modules will appear here after implementation.</p></div>{error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    {[1,2,3,4].map((phase) => <section key={phase} className="space-y-3"><h2 className="text-lg font-semibold">Phase {phase}</h2><div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {modules.filter((m)=>m[2]===phase).map(([code,name]) => { const enabled=phase===1||license.enabled_modules.includes(code); return <div key={code} className="card flex items-center justify-between gap-3"><div><div className="font-medium">{name}</div><div className="text-xs text-gray-400 font-mono mt-1">{code}</div></div><span className={`text-xs font-medium px-2.5 py-1 rounded-full ${enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-500"}`}>{phase===1?"Core · Always Enabled":"Coming Later"}</span></div>; })}
    </div></section>)}
  </div>;
}
