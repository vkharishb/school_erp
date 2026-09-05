import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuthStore } from "../store/authStore";
import { dashboardApi, organizationApi, schoolApi } from "../services/api";
import type { SchoolDashboardSummary } from "../types";
import AppHeader, { type HeaderTenantContext } from "./shell/AppHeader";
import AppSidebar from "./shell/AppSidebar";

export default function Layout() {
  const {user, logout} = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [tenant, setTenant] = useState<HeaderTenantContext>({});
  const [summary, setSummary] = useState<SchoolDashboardSummary | null>(null);

  useEffect(() => {
    if (user?.must_change_password && location.pathname !== "/account-security") {
      navigate("/account-security", {replace:true});
    }
  }, [user?.must_change_password, location.pathname, navigate]);

  useEffect(() => {
    let cancelled = false;
    setTenant({});
    setSummary(null);
    if (!user || user.must_change_password || user.account_type === "PARENT_STUDENT") return;

    const load = async () => {
      try {
        if (user.is_superuser) return;
        if (user.school_id) {
          const [school, dashboard] = await Promise.all([
            schoolApi.get(user.school_id),
            dashboardApi.schoolSummary(user.school_id),
          ]);
          if (cancelled) return;
          setSummary(dashboard);
          setTenant({
            organization: dashboard.organization_name || undefined,
            school: dashboard.school_name || school.configuration?.name || school.code,
            schoolCode: school.code,
            logoUrl: school.configuration?.logo_url || undefined,
            location: [school.configuration?.city, school.configuration?.state].filter(Boolean).join(", ") || undefined,
          });
          return;
        }
        if (user.organization_id) {
          const organizations = await organizationApi.list();
          if (cancelled) return;
          const organization = organizations.find(item => item.id === user.organization_id);
          setTenant({organization: organization?.name});
        }
      } catch {
        // Header context is helpful, but must never block the authorized workspace.
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [user?.id, user?.school_id, user?.organization_id, user?.account_type, user?.is_superuser, user?.must_change_password]);

  const signOut = async () => { await logout(); navigate("/login"); };
  const showBack = location.pathname !== "/";
  const goBack = () => {
    if (window.history.length > 1) { navigate(-1); return; }
    navigate("/");
  };

  return <div className="min-h-screen bg-gray-50 text-gray-900">
    <AppHeader
      user={user}
      tenant={tenant}
      summary={summary}
      onAccountSecurity={() => navigate("/account-security")}
      onLogout={() => void signOut()}
    />
    <div className="flex min-w-0">
      <AppSidebar user={user}/>
      <main className="min-w-0 flex-1">
        {showBack && <div className="flex justify-end border-b border-gray-100 bg-white px-4 py-2 lg:px-6"><button type="button" onClick={goBack} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"><ArrowLeft size={16}/>Back</button></div>}
        <div className="p-4 lg:p-6"><Outlet/></div>
      </main>
    </div>
  </div>;
}
