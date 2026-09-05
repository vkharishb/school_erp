import { AlertTriangle, CheckCircle2, CircleDot, DatabaseZap, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import PasswordInput from "../components/PasswordInput";
import { systemApi, type DevelopmentResetPreview, type PlatformModuleStatus, type PlatformStatus } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";

function StatusBadge({status,label}:{status:PlatformModuleStatus["status"];label:string}) {
  const classes = status === "ready_dev"
    ? "bg-green-100 text-green-800"
    : status === "in_progress"
      ? "bg-amber-100 text-amber-800"
      : "bg-gray-100 text-gray-600";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${classes}`}>{label}</span>;
}

function SettingValue({label,value}:{label:string;value:unknown}) {
  return <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
    <div className="text-xs uppercase tracking-wide text-gray-400">{label.replace(/_/g," ")}</div>
    <div className="mt-1 break-words text-sm text-gray-800">{String(value)}</div>
  </div>;
}

export default function SystemSettingsPage() {
  const logout = useAuthStore((state) => state.logout);
  const [settings,setSettings] = useState<Record<string,unknown>|null>(null);
  const [platform,setPlatform] = useState<PlatformStatus|null>(null);
  const [resetPreview,setResetPreview] = useState<DevelopmentResetPreview|null>(null);
  const [error,setError] = useState("");
  const [resetError,setResetError] = useState("");
  const [confirmation,setConfirmation] = useState("");
  const [password,setPassword] = useState("");
  const [resetting,setResetting] = useState(false);

  useEffect(() => {
    void Promise.all([systemApi.settings(), systemApi.platformStatus()])
      .then(([nextSettings,nextPlatform]) => { setSettings(nextSettings); setPlatform(nextPlatform); })
      .catch((e) => setError(apiErrorMessage(e,"Failed to load system settings")));
    void systemApi.developmentResetPreview()
      .then(setResetPreview)
      .catch(() => setResetPreview(null)); // Production/unsupported environments intentionally hide the reset tool.
  }, []);

  const phases = useMemo(() => {
    const grouped = new Map<number,PlatformModuleStatus[]>();
    for (const module of platform?.modules || []) {
      grouped.set(module.phase,[...(grouped.get(module.phase)||[]),module]);
    }
    return [...grouped.entries()].sort(([a],[b])=>a-b);
  }, [platform]);

  async function resetDevelopmentData() {
    if (!resetPreview || resetting) return;
    setResetError("");
    if (confirmation !== resetPreview.confirmation_phrase) {
      setResetError(`Type exactly: ${resetPreview.confirmation_phrase}`);
      return;
    }
    if (!password) {
      setResetError("Enter the Platform Owner password.");
      return;
    }
    const finalConfirm = window.confirm("This will permanently remove all lower-environment organizations, schools, users and business data after creating a safety backup. Continue?");
    if (!finalConfirm) return;
    setResetting(true);
    try {
      const result = await systemApi.resetDevelopmentData(confirmation,password);
      window.alert(`Development data reset completed. Safety backup: ${result.safety_backup}. You will now be signed out.`);
      await logout();
    } catch (e) {
      setResetError(apiErrorMessage(e,"Development data reset failed"));
    } finally {
      setResetting(false);
    }
  }

  return <div className="space-y-6">
    <div>
      <h1 className="text-2xl font-bold">System Settings</h1>
      <p className="mt-1 text-gray-500">Platform Owner controls, platform health and lower-environment maintenance.</p>
    </div>

    {error && <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

    <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="card flex items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Platform Status</div>
          <div className="mt-1 text-xl font-bold text-gray-900">{platform?.platform_status || "Loading…"}</div>
          {platform && <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
            <span>{platform.summary.ready_dev} Ready in DEV</span><span>•</span>
            <span>{platform.summary.in_progress} In Progress</span><span>•</span>
            <span>{platform.summary.planned} Planned</span>
          </div>}
        </div>
        <CircleDot className="text-blue-600" size={30}/>
      </div>
      <div className="card flex items-center justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Platform Version</div>
          <div className="mt-1 text-xl font-bold text-gray-900">{platform?.release || "Loading…"}</div>
          {platform && <div className="mt-2 text-xs text-gray-500">Alembic {platform.migration_head} · Environment: {platform.environment}</div>}
        </div>
        <ShieldCheck className="text-green-600" size={30}/>
      </div>
    </section>

    <section className="card space-y-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="font-semibold">Platform Module Status Checklist</h2>
          <p className="text-sm text-gray-500">Product-development status, separate from each school's license or module entitlement.</p>
        </div>
        {platform && <div className="text-sm font-medium text-gray-600">{platform.summary.total} modules</div>}
      </div>
      {!platform ? <div className="text-gray-500">Loading module status…</div> : <div className="space-y-5">
        {phases.map(([phase,modules]) => <div key={phase}>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">Phase {phase}</h3>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr><th className="px-3 py-2">Module</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Current Note</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {modules.map((module) => <tr key={module.code}>
                  <td className="px-3 py-3 font-medium text-gray-900"><div className="flex items-center gap-2"><CheckCircle2 size={16} className={module.status === "planned" ? "text-gray-300" : "text-green-600"}/>{module.name}</div></td>
                  <td className="px-3 py-3"><StatusBadge status={module.status} label={module.status_label}/></td>
                  <td className="px-3 py-3 text-gray-600">{module.note}</td>
                </tr>)}
              </tbody>
            </table>
          </div>
        </div>)}
      </div>}
    </section>

    <section className="card">
      <h2 className="mb-4 font-semibold">Effective Phase 1 Policy</h2>
      {settings ? <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(settings).map(([key,value]) => <SettingValue key={key} label={key} value={value}/>) }
      </div> : <div className="text-gray-500">Loading…</div>}
    </section>

    {resetPreview && <section className="card border border-red-200">
      <div className="flex items-start gap-3">
        <DatabaseZap className="mt-0.5 shrink-0 text-red-600" size={24}/>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-red-900">Development Data Reset</h2>
          <p className="mt-1 text-sm text-red-700">Available only in approved lower environments. It cannot run in Production.</p>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(resetPreview.deletes).map(([key,value]) => <div key={key} className="rounded-lg bg-red-50 px-3 py-2">
              <div className="text-lg font-bold text-red-900">{value}</div><div className="text-xs text-red-700">{key.replace(/_/g," ")}</div>
            </div>)}
          </div>
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <div className="flex gap-2"><AlertTriangle size={18} className="shrink-0"/><div><strong>Preserved:</strong> {resetPreview.preserves.join(", ")}. A safety backup is mandatory before the reset.</div></div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <label className="text-sm font-medium text-gray-700">Type <span className="font-mono text-red-700">{resetPreview.confirmation_phrase}</span>
              <input className="input mt-1" value={confirmation} onChange={(e)=>setConfirmation(e.target.value)} autoComplete="off"/>
            </label>
            <label className="text-sm font-medium text-gray-700">Platform Owner Password
              <div className="mt-1"><PasswordInput value={password} onChange={setPassword} autoComplete="current-password"/></div>
            </label>
          </div>
          {resetError && <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{resetError}</div>}
          <button type="button" className="mt-4 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50" disabled={resetting || confirmation !== resetPreview.confirmation_phrase || !password} onClick={()=>void resetDevelopmentData()}>
            {resetting ? "Creating backup and resetting…" : "Reset Development Data"}
          </button>
        </div>
      </div>
    </section>}

    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">Security-sensitive platform values remain code/environment managed. Normal Organization and School administrators cannot access System Settings.</div>
  </div>;
}
