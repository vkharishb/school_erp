import { useEffect, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { useAuthStore } from "../store/authStore";
import { dashboardApi, organizationApi, schoolApi } from "../services/api";
import type { SchoolDashboardSummary } from "../types";
import AppHeader, { type HeaderTenantContext } from "./shell/AppHeader";
import { branding } from "../config/branding";
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
    if (!user) return;
    const workspaceName = user.is_superuser
      ? "Platform Owner"
      : tenant.school || tenant.organization || branding.schoolName;
    document.title = `${workspaceName} | ${branding.productName}`;
  }, [tenant.organization, tenant.school, user?.id, user?.is_superuser]);

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

  return <div className="min-h-screen bg-gray-50 text-gray-900">
    <div className="flex min-w-0">
      <AppSidebar user={user}/>
      <div className="min-w-0 flex-1">
        <AppHeader
          user={user}
          tenant={tenant}
          summary={summary}
          onProfile={() => navigate("/profile")}
          onAccountSecurity={() => navigate("/account-security")}
          onLogout={() => void signOut()}
        />
        <main className="min-w-0 flex-1">
          <div className="p-4 lg:p-6"><Outlet/></div>
        </main>
      </div>
    </div>
    {location.pathname !== "/" && (
      <button
        type="button"
        aria-label="Go Back"
        title="Go Back"
        onClick={() => {
          if (window.history.length > 1) navigate(-1);
          else navigate("/");
        }}
        className="fixed bottom-5 right-5 z-50 inline-flex h-12 w-12 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-700 shadow-lg transition hover:bg-gray-50 hover:text-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 lg:bottom-6 lg:right-6"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true"/>
      </button>
    )}
  </div>;
}
