import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { schoolApi, subscriptionApi } from "../services/api";
import type { SchoolLicense, SchoolSubscription, SubscriptionPlan } from "../types";
import { apiErrorMessage } from "../utils/apiError";

const catalogue = [
  ["dashboard", "Dashboard", 1], ["school_admin", "School Administration", 1], ["school_config", "School Configuration", 1], ["student", "Student Management", 1],
  ["teacher", "Teacher Management", 1], ["fee", "Fee Management", 1], ["marks", "Marks", 1], ["attendance", "Attendance", 1], ["reports", "Reports", 1],
  ["exams", "Exams", 2], ["timetable", "Timetable", 2], ["homework", "Homework", 2], ["online_classes", "Online Classes", 2],
  ["lesson_plans", "Lesson Plans", 2], ["certificates", "Certificates", 2], ["id_cards", "ID Cards", 2],
  ["communication", "Communication", 3], ["transport", "Transport Management", 3], ["gate_pass", "Gate Pass", 3],
  ["hostel", "Hostel Management", 3], ["call_logs", "Call Logs", 3], ["pickup_drop_alerts", "Parent Pickup & Drop Alerts", 3],
  ["smart_attendance", "Smart Attendance", 4], ["face_attendance", "Face Recognition Attendance", 4], ["biometric", "Biometric Integration", 4],
  ["live_gps", "Live GPS Tracking", 4], ["route_monitoring", "Route Monitoring", 4], ["driver_app", "Driver Mobile App", 4],
] as const;

const implemented = new Set(["dashboard","school_admin","school_config","student","teacher","fee","marks","attendance","reports"]);

export default function ModulesPage() {
  const { schoolId = "" } = useParams();
  const [license, setLicense] = useState<SchoolLicense | null>(null);
  const [schoolSubscription, setSchoolSubscription] = useState<SchoolSubscription | null>(null);
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!schoolId) return;
    setError("");
    try {
      const [lic, schoolSubs, plans] = await Promise.all([schoolApi.getLicense(schoolId), subscriptionApi.schools(), subscriptionApi.plans()]);
      setLicense(lic);
      const sub = schoolSubs.find((x) => x.school_id === schoolId) || null;
      setSchoolSubscription(sub);
      setPlan(sub ? plans.find((x) => x.id === sub.plan_id) || null : null);
    } catch (e) {
      setError(apiErrorMessage(e, "Failed to load module entitlement"));
    }
  };
  useEffect(() => { void load(); }, [schoolId]);

  const planModules = useMemo(() => new Set(plan?.enabled_modules || []), [plan]);
  const licenseModules = useMemo(() => new Set(license?.enabled_modules || []), [license]);
  const expectedImplementedModules = useMemo(() => [...planModules].filter((code) => implemented.has(code)).sort(), [planModules]);
  const isInSync = useMemo(() => {
    const current = [...licenseModules].sort();
    return current.length === expectedImplementedModules.length && current.every((x, i) => x === expectedImplementedModules[i]);
  }, [licenseModules, expectedImplementedModules]);

  const syncWithPlan = async () => {
    if (!schoolId || !plan) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const updated = await schoolApi.updateLicense(schoolId, { enabled_modules: expectedImplementedModules });
      setLicense(updated);
      setMessage(`Module allocation synchronized with ${plan.name}.`);
    } catch (e) {
      setError(apiErrorMessage(e, "Failed to synchronize plan modules"));
    } finally { setSaving(false); }
  };

  if (error && !license) return <div className="text-red-600">{error}</div>;
  if (!license) return <div className="text-gray-500">Loading modules…</div>;

  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-bold">Module Catalogue</h1><p className="text-gray-500 mt-1">The School inherits its module entitlement from its assigned subscription plan. The catalogue shows plan entitlement, implementation state and effective School access.</p></div>
      {plan && <button className="btn-primary" disabled={saving || isInSync} onClick={()=>void syncWithPlan()}>{saving ? "Synchronizing…" : isInSync ? "Plan Allocation Synced" : "Sync Modules with Plan"}</button>}
    </div>
    {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    {message && <div className="rounded-lg bg-green-50 border border-green-200 text-green-700 px-4 py-3 text-sm">{message}</div>}

    <section className="card grid grid-cols-1 gap-4 md:grid-cols-4">
      <div><div className="text-xs uppercase tracking-wide text-gray-500">Assigned Plan</div><div className="mt-1 font-semibold">{plan?.name || schoolSubscription?.plan_name || "Not assigned"}</div></div>
      <div><div className="text-xs uppercase tracking-wide text-gray-500">Subscription</div><div className="mt-1 capitalize">{schoolSubscription?.status?.replace(/_/g," ") || "Not assigned"}</div></div>
      <div><div className="text-xs uppercase tracking-wide text-gray-500">Activation</div><div className="mt-1 capitalize">{schoolSubscription?.billing_cycle === "trial" ? "Trial · No key required" : schoolSubscription?.activation_status?.replace(/_/g," ") || "Not assigned"}</div></div>
      <div><div className="text-xs uppercase tracking-wide text-gray-500">Allocation Check</div><div className={`mt-1 font-semibold ${isInSync ? "text-green-700" : "text-amber-700"}`}>{isInSync ? "In sync" : "Needs synchronization"}</div></div>
    </section>

    {[1,2,3,4].map((phase) => <section key={phase} className="space-y-3"><h2 className="text-lg font-semibold">Phase {phase}</h2><div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {catalogue.filter((m)=>m[2]===phase).map(([code,name]) => {
        const implementedNow=implemented.has(code);
        const entitled=planModules.has(code);
        const enabled=implementedNow && entitled && licenseModules.has(code);
        const state = !implementedNow ? "Locked · Not implemented" : !entitled ? "Disabled · Not in plan" : enabled ? "Enabled" : "Disabled · Sync required";
        const cls = enabled ? "bg-green-100 text-green-800" : entitled && !implementedNow ? "bg-amber-100 text-amber-800" : "bg-gray-100 text-gray-600";
        return <div key={code} className="card flex items-center justify-between gap-3"><div><div className="font-medium">{name}</div><div className="text-xs text-gray-400 font-mono mt-1">{code}</div><div className="mt-1 text-xs text-gray-500">{entitled ? `Included in ${plan?.name || "assigned plan"}` : "Not allocated by assigned plan"}</div></div><span className={`text-xs font-medium px-2.5 py-1 rounded-full text-right ${cls}`}>{state}</span></div>;
      })}
    </div></section>)}
  </div>;
}
