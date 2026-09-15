import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

test("Platform Owner has organization-first navigation, profile and subscriptions", async()=>{
  const [sidebar,app,dashboard,profile,subscriptions]=await Promise.all([
    readFile(new URL("../src/components/shell/AppSidebar.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/App.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/pages/DashboardPage.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/pages/ProfilePage.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/pages/SubscriptionsPage.tsx",import.meta.url),"utf8"),
  ]);
  assert.ok(sidebar.indexOf('label:"Organizations"')<sidebar.indexOf('label:"Schools"'));
  assert.match(sidebar,/label:"Subscriptions"/);
  assert.match(app,/path="profile"/);
  assert.match(app,/path="subscriptions"/);
  assert.match(dashboard,/Platform Dashboard/);
  assert.match(profile,/Profile updated successfully/);
  assert.match(subscriptions,/Subscription modules are controlled by the Platform Owner/);
});

test("active Platform Owner surfaces no Branch terminology",async()=>{
  const files=["DashboardPage.tsx","SchoolsPage.tsx","SchoolDetailPage.tsx","LoginPage.tsx"];
  for(const file of files){
    const source=await readFile(new URL(`../src/pages/${file}`,import.meta.url),"utf8");
    assert.doesNotMatch(source,/School \/ Branch|Schools \/ Branches|Branch-wise/);
  }
});

test("Platform Owner dashboard exposes activation and active-user operational lists",async()=>{
  const dashboard=await readFile(new URL("../src/pages/DashboardPage.tsx",import.meta.url),"utf8");
  assert.match(dashboard,/Pending Activation Schools/);
  assert.match(dashboard,/Manage Activation/);
  assert.match(dashboard,/activation_status!=="activated"/);
  assert.match(dashboard,/Active Users/);
  assert.match(dashboard,/filter\(item=>item\.is_active\)/);
  assert.match(dashboard,/Last Login/);
});

test("authenticated workspace exposes a universal floating back button",async()=>{
  const layout=await readFile(new URL("../src/components/Layout.tsx",import.meta.url),"utf8");
  assert.match(layout,/aria-label="Go Back"/);
  assert.match(layout,/fixed bottom-5 right-5/);
  assert.match(layout,/navigate\(-1\)/);
  assert.match(layout,/location\.pathname !== "\/"/);
});

test("authenticated workspace uses tenant context for header and browser title", async()=>{
  const [layout,header,sidebar]=await Promise.all([
    readFile(new URL("../src/components/Layout.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/components/shell/AppHeader.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/components/shell/AppSidebar.tsx",import.meta.url),"utf8"),
  ]);
  assert.match(layout,/document\.title = `\$\{workspaceName\} \| \$\{branding\.productName\}`/);
  assert.match(layout,/tenant\.school \|\| tenant\.organization \|\| branding\.schoolName/);
  assert.ok(layout.indexOf("<AppSidebar user={user}/>") < layout.indexOf("<AppHeader"));
  assert.match(sidebar,/sticky top-0 flex h-screen/);
  assert.match(header,/workspaceName=user\?\.is_superuser\?"Platform Owner":tenant\.school\|\|tenant\.organization/);
  assert.match(header,/workspaceContext=tenant\.school&&tenant\.organization\?tenant\.organization:tenant\.location/);
  assert.match(header,/aria-label="Notifications"/);
  assert.match(header,/My Profile/);
  assert.doesNotMatch(header,/CircleHelp|Grid3X3|aria-label="Help"|aria-label="Applications"/);
  assert.doesNotMatch(header,/img src=\{.*logo/);
});
test("ERP and login branding use configured logo asset", async()=>{
  const [brandingConfig,login,sidebar,envTyping,envExample]=await Promise.all([
    readFile(new URL("../src/config/branding.ts",import.meta.url),"utf8"),
    readFile(new URL("../src/pages/LoginPage.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/components/shell/AppSidebar.tsx",import.meta.url),"utf8"),
    readFile(new URL("../src/vite-env.d.ts",import.meta.url),"utf8"),
    readFile(new URL("../.env.example",import.meta.url),"utf8"),
  ]);
  assert.match(brandingConfig,/logoUrl: env\.VITE_ERP_LOGO_URL\?\.trim\(\) \|\| "\/favicon\.svg"/);
  assert.match(login,/img src=\{branding\.logoUrl\}/);
  assert.match(sidebar,/img src=\{branding\.logoUrl\}/);
  assert.match(envTyping,/VITE_ERP_LOGO_URL/);
  assert.match(envExample,/VITE_ERP_LOGO_URL=\/logos\/smart-school-erp-brand\.jpeg/);
});

test("Platform Owner dashboard labels inactive subscriptions clearly", async()=>{
  const dashboard=await readFile(new URL("../src/pages/DashboardPage.tsx",import.meta.url),"utf8");
  assert.match(dashboard,/label:"Not Active"/);
  assert.doesNotMatch(dashboard,/Not Subscribed/);
});