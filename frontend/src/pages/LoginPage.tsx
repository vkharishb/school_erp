import { FormEvent, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  GraduationCap,
  ShieldCheck,
  Sparkles,
  UsersRound,
  WalletCards,
} from "lucide-react";
import PasswordInput from "../components/PasswordInput";
import { branding } from "../config/branding";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";
import type { AccountType } from "../types";

const accountTypes: { value: AccountType; label: string }[] = [
  { value: "ORGANIZATION_ADMIN", label: "Organization Admin" },
  { value: "SCHOOL_ADMIN", label: "School / Branch Admin" },
  { value: "ACCOUNTS", label: "Accounts" },
  { value: "TEACHER", label: "Teacher" },
  { value: "RECEPTIONIST", label: "Receptionist" },
  { value: "PARENT_STUDENT", label: "Parent / Student" },
  { value: "SUPER_ADMIN", label: "Super Admin / Platform Owner" },
];

const capabilities = [
  { label: "Student Management", icon: GraduationCap },
  { label: "Teacher Management", icon: UsersRound },
  { label: "Fee Management", icon: WalletCards },
  { label: "Academics & Attendance", icon: BookOpenCheck },
];

export default function LoginPage() {
  const [accountType, setAccountType] = useState<AccountType>("ORGANIZATION_ADMIN");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, isAuthenticated, user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = `${branding.schoolName} | ${branding.productName}`;
  }, []);

  if (isAuthenticated) return <Navigate to={user?.must_change_password ? "/account-security" : "/"} replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(accountType, username.trim(), password);
      const loggedInUser = useAuthStore.getState().user;
      navigate(loggedInUser?.must_change_password ? "/account-security" : "/", { replace: true });
    } catch (err: unknown) {
      setError(apiErrorMessage(err, "Login failed. Check username and password."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 lg:grid lg:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
      <section className="relative hidden min-h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-primary-900 to-primary-700 px-10 py-10 text-white lg:flex lg:flex-col xl:px-16 xl:py-14">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_12%,rgba(96,165,250,0.26),transparent_32%),radial-gradient(circle_at_88%_88%,rgba(14,165,233,0.20),transparent_34%)]" />
        <div className="pointer-events-none absolute -left-24 top-40 h-72 w-72 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -left-10 top-56 h-44 w-44 rounded-full border border-white/10" />
        <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-white/[0.06] blur-sm" />
        <div className="pointer-events-none absolute bottom-24 right-20 h-44 w-44 rounded-full bg-sky-300/10 blur-2xl" />

        <div className="relative z-10 flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/20 bg-white text-primary-800 shadow-2xl shadow-slate-950/30">
            <GraduationCap size={34} strokeWidth={2.1} aria-hidden="true" />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-primary-200">
              {branding.productName}
            </p>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-white xl:text-3xl">
              {branding.schoolName}
            </h1>
          </div>
        </div>

        <div className="relative z-10 my-auto max-w-2xl py-12">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2 text-sm font-semibold text-white backdrop-blur-md">
            <ShieldCheck size={16} aria-hidden="true" />
            Secure school management workspace
          </div>

          <h2 className="max-w-xl text-4xl font-extrabold leading-[1.08] tracking-tight text-white xl:text-5xl">
            Everything your school needs,
            <span className="block text-primary-200">connected in one place.</span>
          </h2>
          <p className="mt-6 max-w-xl text-lg font-medium leading-7 text-white/90">
            {branding.tagline}
          </p>
          <p className="mt-2 max-w-xl text-sm leading-6 text-primary-100/90">
            {branding.welcomeMessage}
          </p>

          <div className="mt-9 grid max-w-2xl grid-cols-2 gap-3">
            {capabilities.map(({ label, icon: Icon }) => (
              <div
                key={label}
                className="flex items-center gap-3 rounded-2xl border border-white/15 bg-white/10 px-4 py-3.5 text-sm font-semibold text-white shadow-sm backdrop-blur-md"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15 text-primary-100">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <span>{label}</span>
              </div>
            ))}
          </div>

          <div className="mt-8 flex items-center gap-2 text-sm text-primary-100">
            <Sparkles size={16} aria-hidden="true" />
            <span>Built for secure, simple and connected school operations.</span>
          </div>
        </div>

        <div className="relative z-10 border-t border-white/15 pt-6 text-xs text-primary-100">
          <p>Secure • Reliable • Connected</p>
        </div>
      </section>

      <section className="flex min-h-screen items-center justify-center bg-slate-50 px-5 py-8 sm:px-8 lg:px-10 xl:px-16">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-800 text-white shadow-lg shadow-primary-900/20">
              <GraduationCap size={27} aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary-700">
                {branding.productName}
              </p>
              <h1 className="text-xl font-bold text-slate-950">{branding.schoolName}</h1>
            </div>
          </div>

          <div className="mb-8">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
              <CheckCircle2 size={14} aria-hidden="true" />
              Secure sign in
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-slate-950">Welcome back</h2>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Sign in to your {branding.schoolName} account to continue.
            </p>
          </div>

          {error && (
            <div
              className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-6 text-red-700"
              role="alert"
              aria-live="polite"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label" htmlFor="accountType">Account Type</label>
              <select
                id="accountType"
                className="input h-12 bg-white px-4 text-[15px] shadow-sm"
                value={accountType}
                onChange={(e) => {
                  setAccountType(e.target.value as AccountType);
                  setUsername("");
                }}
                disabled={loading}
              >
                {accountTypes.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="username">
                {accountType === "PARENT_STUDENT" ? "Phone Number" : accountType === "ORGANIZATION_ADMIN" ? "Username or Email" : "Username"}
              </label>
              <input
                id="username"
                type={accountType === "PARENT_STUDENT" ? "tel" : "text"}
                className="input h-12 bg-white px-4 text-[15px] shadow-sm"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                autoCapitalize="none"
                spellCheck={false}
                autoComplete={accountType === "PARENT_STUDENT" ? "tel" : "username"}
                placeholder={accountType === "PARENT_STUDENT" ? "Enter registered access number" : accountType === "ORGANIZATION_ADMIN" ? "Enter username or email" : "Enter your username"}
                disabled={loading}
              />
            </div>

            <div>
              <label className="label" htmlFor="password">Password</label>
              <PasswordInput
                id="password"
                value={password}
                onChange={setPassword}
                autoComplete="current-password"
                placeholder="Enter your password"
                disabled={loading}
                className="input h-12 bg-white px-4 text-[15px] shadow-sm"
              />
            </div>

            <button
              type="submit"
              className="group flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary-700 px-4 text-sm font-semibold text-white shadow-lg shadow-primary-700/20 transition hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:pointer-events-none disabled:opacity-60"
              disabled={loading}
            >
              <span>{loading ? "Signing in…" : "Sign in"}</span>
              {!loading && (
                <ArrowRight
                  size={17}
                  className="transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              )}
            </button>
          </form>

          <div className="mt-6 rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs leading-5 text-slate-500 shadow-sm">
            Need help signing in? Contact your school administrator. Never share your password with anyone.
          </div>

          <div className="mt-8 border-t border-slate-200 pt-5 text-right text-xs text-slate-400">
            <p>{branding.releaseVersion}</p>
          </div>
        </div>
      </section>
    </main>
  );
}
