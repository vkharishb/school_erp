import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BarChart3, Building2, CalendarCheck2, CircleDollarSign, ClipboardCheck, GraduationCap, IndianRupee, KeyRound, School as SchoolIcon, ShieldCheck, UserPlus, UsersRound, WalletCards, type LucideIcon } from "lucide-react";
import { dashboardApi, organizationApi, parentStudentApi, platformPaymentsApi, schoolApi, subscriptionApi, userAdminApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import type { LinkedStudent, OrganizationDashboard, OrganizationSubscription, ParentStudentPortalSummary, PaymentSummary, School, SchoolDashboardSummary, SchoolSubscription, SubscriptionPayment, User } from "../types";
import { apiErrorMessage } from "../utils/apiError";
import { accountLabel } from "../utils/account";
import { hasModule, hasPermission } from "../utils/permissions";
import { DashboardPageFrame, MetricTile, Panel, QuickAction, formatMoney } from "../components/dashboard/DashboardUI";

export default function DashboardPage() {
  const user = useAuthStore(state => state.user);
  const [organization,setOrganization]=useState<OrganizationDashboard|null>(null);
  const [school,setSchool]=useState<SchoolDashboardSummary|null>(null);
  const [platform,setPlatform]=useState<{organizations:number;schools:School[];users:User[];subscriptions:OrganizationSubscription[];schoolSubscriptions:SchoolSubscription[];payments:PaymentSummary;receipts:SubscriptionPayment[]}|null>(null);
  const [linkedStudents,setLinkedStudents]=useState<LinkedStudent[]>([]);
  const [selectedStudentId,setSelectedStudentId]=useState("");
  const [portal,setPortal]=useState<ParentStudentPortalSummary|null>(null);
  const [error,setError]=useState("");
  const isOrganizationAdmin=user?.account_type==="ORGANIZATION_ADMIN";
  const isParentStudent=user?.account_type==="PARENT_STUDENT";

  useEffect(()=>{
    setError("");setOrganization(null);setSchool(null);setPlatform(null);setPortal(null);
    if(!user)return;
    if(user.is_superuser){Promise.all([organizationApi.list(),schoolApi.list(),userAdminApi.list(),subscriptionApi.accounts(),subscriptionApi.schools(),platformPaymentsApi.summary(),platformPaymentsApi.receipts()]).then(([orgs,schools,users,subscriptions,schoolSubscriptions,payments,receipts])=>setPlatform({organizations:orgs.length,schools,users,subscriptions,schoolSubscriptions,payments,receipts})).catch(e=>setError(apiErrorMessage(e,"Unable to load platform dashboard.")));return;}
    if(isParentStudent){parentStudentApi.students().then(items=>{setLinkedStudents(items);setSelectedStudentId(items[0]?.id||"");}).catch(e=>setError(apiErrorMessage(e,"Unable to load linked students.")));return;}
    if(isOrganizationAdmin&&user.organization_id){organizationApi.dashboard(user.organization_id).then(setOrganization).catch(e=>setError(apiErrorMessage(e,"Unable to load organization dashboard.")));return;}
    if(user.school_id){dashboardApi.schoolSummary(user.school_id).then(setSchool).catch(e=>setError(apiErrorMessage(e,"Unable to load dashboard.")));}
  },[user?.id,user?.organization_id,user?.school_id,isOrganizationAdmin,isParentStudent]);

  useEffect(()=>{if(!isParentStudent||!selectedStudentId){setPortal(null);return;}parentStudentApi.summary(selectedStudentId).then(setPortal).catch(e=>setError(apiErrorMessage(e,"Unable to load student information.")));},[isParentStudent,selectedStudentId]);

  if(user?.is_superuser)return <PlatformDashboard platform={platform} error={error}/>;
  if(isParentStudent)return <ParentStudentDashboard linkedStudents={linkedStudents} selectedStudentId={selectedStudentId} setSelectedStudentId={setSelectedStudentId} portal={portal} error={error}/>;
  if(isOrganizationAdmin)return <OrganizationAdminDashboard organization={organization} error={error}/>;
  return <SchoolRoleDashboard summary={school} error={error}/>;
}

function PlatformDashboard({platform,error}:{platform:{organizations:number;schools:School[];users:User[];subscriptions:OrganizationSubscription[];schoolSubscriptions:SchoolSubscription[];payments:PaymentSummary;receipts:SubscriptionPayment[]}|null;error:string}) {
  const schools=(platform?.schools||[]).filter(s=>!s.deleted_at);
  const schoolSubscriptions=platform?.schoolSubscriptions||[];
  const receipts=platform?.receipts||[];
  const subscriptions=platform?.subscriptions||[];
  const now=Date.now();
  const thirtyDays=30*86400000;

  // One current entitlement per School. This prevents historical/duplicate rows from inflating totals.
  const currentBySchool=new Map<string,SchoolSubscription>();
  [...schoolSubscriptions]
    .sort((a,b)=>new Date(b.updated_at).getTime()-new Date(a.updated_at).getTime())
    .forEach(item=>{if(!currentBySchool.has(item.school_id))currentBySchool.set(item.school_id,item);});

  const statusCounts={active:0,expiring:0,expired:0,trial:0,unassigned:0};
  const planCounts:Record<string,number>={};
  for(const school of schools){
    const entitlement=currentBySchool.get(school.id);
    if(!entitlement){statusCounts.unassigned+=1;continue;}
    planCounts[entitlement.plan_name]=(planCounts[entitlement.plan_name]||0)+1;
    const expires=new Date(entitlement.expires_at).getTime();
    if(entitlement.billing_cycle==="trial" && expires>=now && entitlement.status!=="disabled") statusCounts.trial+=1;
    else if(entitlement.status==="expired" || expires<now) statusCounts.expired+=1;
    else if(entitlement.status==="active" && expires-now<=thirtyDays) statusCounts.expiring+=1;
    else if(entitlement.status==="active") statusCounts.active+=1;
    else statusCounts.unassigned+=1;
  }

  const planEntries=Object.entries(planCounts).sort((a,b)=>b[1]-a[1]);
  const totalPlan=Math.max(schools.length,1);
  const classifiedTotal=Object.values(statusCounts).reduce((sum,value)=>sum+value,0);
  const activeSubscriptionAccounts=subscriptions.filter(x=>x.status==="active").length;
  const pendingActivationSchools=[...currentBySchool.values()]
    .filter(item=>item.billing_cycle!=="trial" && item.status!=="disabled" && item.activation_status!=="activated" && item.activation_status!=="not_required")
    .sort((a,b)=>a.school_name.localeCompare(b.school_name));
  const activeUsers=(platform?.users||[])
    .filter(item=>item.is_active)
    .sort((a,b)=>(b.last_login_at||"").localeCompare(a.last_login_at||"") || (a.full_name||a.username).localeCompare(b.full_name||b.username));

  // Revenue Overview: six real calendar months, using receipt dates for Received.
  // Outstanding subscription balances are placed in the month of due_at, or current month when no due date exists.
  const monthKey=(date:Date)=>`${date.getUTCFullYear()}-${String(date.getUTCMonth()+1).padStart(2,"0")}`;
  const monthLabel=(date:Date)=>date.toLocaleDateString("en-US",{month:"short",year:"numeric",timeZone:"UTC"});
  const monthBuckets=Array.from({length:6},(_,index)=>{
    const d=new Date();
    d.setUTCDate(1); d.setUTCHours(0,0,0,0); d.setUTCMonth(d.getUTCMonth()-(5-index));
    return {key:monthKey(d),label:monthLabel(d),received:0,pending:0};
  });
  const byMonth=new Map(monthBuckets.map(bucket=>[bucket.key,bucket]));
  for(const receipt of receipts){
    if(receipt.status!=="received")continue;
    const bucket=byMonth.get(monthKey(new Date(receipt.payment_date)));
    if(bucket)bucket.received+=Number(receipt.amount||0);
  }
  for(const subscription of subscriptions){
    const balance=Number(subscription.balance_amount||0);
    if(balance<=0)continue;
    const dueDate=subscription.due_at?new Date(subscription.due_at):new Date();
    const bucket=byMonth.get(monthKey(dueDate)) || monthBuckets[monthBuckets.length-1];
    bucket.pending+=balance;
  }
  const maxRevenue=Math.max(...monthBuckets.flatMap(x=>[x.received,x.pending]),0);
  const hasRevenueData=maxRevenue>0;
  const recentReceipts=[...receipts].sort((a,b)=>b.payment_date.localeCompare(a.payment_date)).slice(0,5);

  const donutSegments=[
    {label:"Active",value:statusCounts.active,className:"bg-emerald-400"},
    {label:"Expiring Soon",value:statusCounts.expiring,className:"bg-amber-400"},
    {label:"Expired",value:statusCounts.expired,className:"bg-rose-400"},
    {label:"Trial",value:statusCounts.trial,className:"bg-blue-400"},
    {label:"Not Active",value:statusCounts.unassigned,className:"bg-slate-300"},
  ];
  let offset=0;
  const donutStops:string[]=[];
  for(const segment of donutSegments){
    if(segment.value<=0)continue;
    const start=offset/schools.length*100;
    offset+=segment.value;
    const finish=offset/schools.length*100;
    const color=segment.label==="Active"?"#34d399":segment.label==="Expiring Soon"?"#fbbf24":segment.label==="Expired"?"#fb7185":segment.label==="Trial"?"#60a5fa":"#cbd5e1";
    donutStops.push(`${color} ${start}% ${finish}%`);
  }
  const donutBackground=schools.length?`conic-gradient(${donutStops.join(",")})`:"#e2e8f0";

  return <DashboardPageFrame title="Platform Dashboard" subtitle="Manage societies, schools, subscriptions, payments and your entire School ERP platform from here." error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
      <MetricTile label="Total Societies/Trusts" value={platform?.organizations} icon={Building2} to="/organizations?view=list"/>
      <MetricTile label="Total Schools" value={schools.length} icon={SchoolIcon} tone="green" to="/schools?view=list"/>
      <MetricTile label="Active Users" value={activeUsers.length} icon={UsersRound} tone="violet" to="/users"/>
      <MetricTile label="Total Payments Received" value={formatMoney(platform?.payments.total_received)} icon={IndianRupee} tone="amber" to="/payments"/>
      <MetricTile label="Active Subscription Accounts" value={activeSubscriptionAccounts} icon={WalletCards} tone="rose" to="/subscriptions"/>
      <MetricTile label="Pending Activation Schools" value={pendingActivationSchools.length} icon={KeyRound} tone="amber" to="/subscriptions?tab=keys"/>
    </div>

    <Panel title="Quick Actions"><div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <QuickAction label="Add Society/Trust" to="/organizations?view=create" icon={Building2} tone="blue"/>
      <QuickAction label="Create School" to="/schools?view=create" icon={SchoolIcon} tone="green"/>
      <QuickAction label="Subscriptions" to="/subscriptions?tab=subscriptions" icon={WalletCards} tone="violet"/>
      <QuickAction label="Payments" to="/payments?tab=details" icon={IndianRupee} tone="amber"/>
    </div></Panel>

    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <Panel title="Schools by Subscription Plan"><div className="space-y-4">
        {planEntries.length?planEntries.map(([name,count],i)=><div key={name}>
          <div className="mb-1 flex justify-between text-sm"><span>{name}</span><span className="font-semibold">{count} ({Math.round(count/totalPlan*100)}%)</span></div>
          <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-600" style={{width:`${count/totalPlan*100}%`,opacity:Math.max(.35,1-i*.12)}}/></div>
        </div>):<p className="text-sm text-slate-500">No School subscriptions are configured.</p>}
        {statusCounts.unassigned>0&&<p className="text-xs text-amber-700">{statusCounts.unassigned} School{statusCounts.unassigned===1?" is":"s are"} not assigned to a subscription.</p>}
      </div></Panel>

      <Panel title="Revenue Overview"><div className="space-y-3">
        {hasRevenueData?<>
          <div className="flex h-52 items-end gap-3 border-b border-l border-slate-200 px-3 pb-2">
            {monthBuckets.map(bucket=><div key={bucket.key} className="flex h-full flex-1 flex-col justify-end">
              <div className="flex flex-1 items-end justify-center gap-1">
                <span title={`Received ${formatMoney(String(bucket.received))}`} className="w-2/5 rounded-t bg-blue-600" style={{height:`${bucket.received?Math.max(6,bucket.received/maxRevenue*100):0}%`}}/>
                <span title={`Pending ${formatMoney(String(bucket.pending))}`} className="w-2/5 rounded-t bg-blue-200" style={{height:`${bucket.pending?Math.max(6,bucket.pending/maxRevenue*100):0}%`}}/>
              </div>
              <span className="mt-2 truncate text-center text-[10px] text-slate-500">{bucket.label}</span>
            </div>)}
          </div>
          <div className="flex flex-wrap justify-center gap-5 text-xs text-slate-500"><span><span className="text-blue-600">■</span> Received {formatMoney(platform?.payments.total_received)}</span><span><span className="text-blue-300">■</span> Pending {formatMoney(platform?.payments.outstanding)}</span></div>
        </>:<div className="flex h-52 items-center justify-center rounded-lg border border-dashed border-slate-200 text-sm text-slate-500">No payment data available.</div>}
      </div></Panel>

      <Panel title="Subscription Status"><div className="flex flex-col items-center gap-6 sm:flex-row">
        <div className="relative flex h-40 w-40 shrink-0 items-center justify-center rounded-full" style={{background:donutBackground}}>
          <div className="flex h-28 w-28 items-center justify-center rounded-full bg-white text-center"><div><b className="text-2xl">{schools.length}</b><div className="text-xs text-slate-500">Schools</div></div></div>
        </div>
        <div className="w-full space-y-3 text-sm">
          {donutSegments.map(segment=><div key={segment.label} className="flex items-center justify-between gap-4 border-b border-gray-100 pb-2 last:border-0"><span className="flex items-center gap-2 text-gray-500"><span className={`h-2.5 w-2.5 rounded-full ${segment.className}`}/>{segment.label}</span><span className="font-medium text-gray-800">{segment.value} ({schools.length?Math.round(segment.value/schools.length*100):0}%)</span></div>)}
        </div>
      </div>{classifiedTotal!==schools.length&&<p className="mt-3 text-xs text-red-600">Subscription status totals are inconsistent. Refresh the dashboard or review School entitlements.</p>}</Panel>
    </div>

    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Panel title="Attention Required"><div className="divide-y rounded-xl border"><StatusRow label="Subscriptions expiring within 30 days" value={String(statusCounts.expiring)}/><StatusRow label="Not active Schools" value={String(statusCounts.unassigned)}/><StatusRow label="Outstanding payments" value={formatMoney(platform?.payments.outstanding)}/><StatusRow label="Overdue payments" value={formatMoney(platform?.payments.overdue)}/></div></Panel>
      <Panel title="Recent Payments" action={<Link className="text-sm font-semibold text-blue-700" to="/payments">View All</Link>}><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-slate-500"><th className="py-2">Date</th><th>Receipt</th><th>Amount</th><th>Status</th></tr></thead><tbody>{recentReceipts.length?recentReceipts.map(r=><tr key={r.id} className="border-b last:border-0"><td className="py-2">{new Date(r.payment_date).toLocaleString()}</td><td>{r.receipt_number}</td><td>{formatMoney(r.amount)}</td><td><span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">{r.status}</span></td></tr>):<tr><td colSpan={4} className="py-8 text-center text-slate-500">No payments recorded.</td></tr>}</tbody></table></div></Panel>
    </div>

    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Panel title={`Pending Activation Schools (${pendingActivationSchools.length})`} action={<Link className="text-sm font-semibold text-blue-700" to="/subscriptions?tab=keys">Manage Activation</Link>}>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-slate-500"><th className="py-2">School</th><th>Society/Trust</th><th>Plan</th><th>Activation</th><th></th></tr></thead><tbody>{pendingActivationSchools.length?pendingActivationSchools.slice(0,6).map(item=><tr key={item.id} className="border-b last:border-0"><td className="py-2"><div className="font-medium">{item.school_name}</div><div className="text-xs text-slate-500">{item.school_code}</div></td><td>{item.organization_name}</td><td>{item.plan_name}</td><td><span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-1 text-xs font-medium capitalize text-amber-700"><KeyRound size={12}/>{item.activation_status.replace(/_/g," ")}</span></td><td className="text-right"><Link className="text-xs font-semibold text-blue-700 hover:underline" to={`/subscriptions?tab=keys&organization=${item.organization_id}`}>Open</Link></td></tr>):<tr><td colSpan={5} className="py-8 text-center text-slate-500"><span className="inline-flex items-center gap-2"><ShieldCheck size={16}/>No paid Schools are waiting for activation.</span></td></tr>}</tbody></table></div>
      </Panel>
      <Panel title={`Active Users (${activeUsers.length})`} action={<Link className="text-sm font-semibold text-blue-700" to="/users">View All</Link>}>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-slate-500"><th className="py-2">User</th><th>Role</th><th>Scope</th><th>Last Login</th></tr></thead><tbody>{activeUsers.length?activeUsers.slice(0,6).map(item=><tr key={item.id} className="border-b last:border-0"><td className="py-2"><div className="font-medium">{item.full_name||item.username}</div><div className="text-xs text-slate-500">{item.username}</div></td><td>{accountLabel(item.account_type)}</td><td>{item.is_superuser?"Platform":item.school_id?"School":item.organization_id?"Society/Trust":"—"}</td><td>{item.last_login_at?new Date(item.last_login_at).toLocaleString():"Never"}</td></tr>):<tr><td colSpan={4} className="py-8 text-center text-slate-500">No active users found.</td></tr>}</tbody></table></div>
      </Panel>
    </div>

    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <Panel title="Latest Schools" action={<Link className="text-sm font-semibold text-blue-700" to="/schools?view=list">View All</Link>}><div className="space-y-2">{[...schools].sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,4).map(x=><div key={x.id} className="flex justify-between border-b py-2 text-sm"><span className="font-medium">{x.configuration?.name||x.code}</span><span className={x.is_active?"text-emerald-700":"text-amber-700"}>{x.is_active?"Active":"Inactive"}</span></div>)}</div></Panel>
      <Panel title="Latest Users" action={<Link className="text-sm font-semibold text-blue-700" to="/users">View All</Link>}><div className="space-y-2">{[...(platform?.users||[])].slice(0,4).map(x=><div key={x.id} className="flex justify-between border-b py-2 text-sm"><span><span className="font-medium">{x.full_name||x.username}</span><span className="ml-2 text-xs text-slate-500">{accountLabel(x.account_type)}</span></span><span className={x.is_active?"text-emerald-700":"text-amber-700"}>{x.is_active?"Active":"Inactive"}</span></div>)}</div></Panel>
    </div>
  </DashboardPageFrame>;
}

function OrganizationAdminDashboard({organization,error}:{organization:OrganizationDashboard|null;error:string}) {
  const user=useAuthStore(state=>state.user);
  const day=organization?.as_of_date||new Date().toISOString().slice(0,10);
  const reportLink=(report:string)=>`/reports?report=${report}&start_date=${day}&end_date=${day}&run=1`;
  const feeVisible=hasPermission(user,"fee.view")&&hasModule(user,"fee");
  const attendanceVisible=hasPermission(user,"attendance.view")&&hasModule(user,"attendance");
  return <DashboardPageFrame title={organization?.organization_name||"Organization Dashboard"} subtitle={`Consolidated operational and financial view across all Schools · ${day}`} error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricTile label="Students" value={organization?.student_count} icon={GraduationCap}/><MetricTile label="Teachers" value={organization?.teacher_count} icon={UsersRound} tone="green"/>
      {feeVisible&&<MetricTile label="Today’s Collection" value={formatMoney(organization?.today_collection)} icon={IndianRupee} tone="amber" to={reportLink("fee_collections")}/>} 
      {feeVisible&&<MetricTile label="Outstanding Dues" value={formatMoney(organization?.outstanding_due)} detail={`Overdue ${formatMoney(organization?.overdue_due)}`} icon={CircleDollarSign} tone="rose" to="/reports?report=fee_dues&run=1"/>}
      {attendanceVisible&&<MetricTile label="Student Attendance" value={`${organization?.student_attendance_percentage?.toFixed(1)??"0.0"}%`} detail={`${organization?.student_attendance_present??0} present / ${organization?.student_attendance_marked??0} marked`} icon={ClipboardCheck} tone="violet"/>}
    </div>
    <Panel title="School-wise operations" action={<Link className="btn-secondary" to="/schools">Manage Schools</Link>}><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left text-gray-500"><th className="py-2 pr-4">School</th><th className="pr-4">Students</th><th className="pr-4">Teachers</th><th className="pr-4">Collection</th><th className="pr-4">Dues</th><th></th></tr></thead><tbody>{organization?.units.map(unit=><tr key={unit.school_id} className="border-b last:border-0"><td className="py-3 pr-4"><div className="font-medium text-gray-900">{unit.name}</div><div className="text-xs text-gray-500">{unit.code} · {unit.is_active?"Active":"Inactive"}</div></td><td className="pr-4">{unit.student_count}</td><td className="pr-4">{unit.teacher_count}</td><td className="pr-4">{feeVisible?formatMoney(unit.today_collection):"—"}</td><td className="pr-4">{feeVisible?formatMoney(unit.outstanding_due):"—"}</td><td><Link className="text-sm font-medium text-primary-700 hover:underline" to={`/schools/${unit.school_id}`}>Open →</Link></td></tr>)}</tbody></table>{organization?.units.length===0&&<p className="py-8 text-center text-gray-500">No Schools are configured.</p>}</div></Panel>
  </DashboardPageFrame>;
}

function SchoolRoleDashboard({summary,error}:{summary:SchoolDashboardSummary|null;error:string}) {
  const user=useAuthStore(state=>state.user);
  const sid=user?.school_id||summary?.school_id||"";
  const role=accountLabel(user?.account_type);
  const isSchoolAdmin=user?.account_type==="SCHOOL_ADMIN";
  const isAccountant=user?.account_type==="ACCOUNTS";
  const isTeacher=user?.account_type==="TEACHER";
  const isReceptionist=user?.account_type==="RECEPTIONIST";
  const financeVisible=(isSchoolAdmin||isAccountant)&&hasPermission(user,"fee.view")&&hasModule(user,"fee")&&summary?.fees_due!==null;
  const schoolPath=(segment:string)=>sid?`/schools/${sid}/${segment}`:`/${segment}`;
  type ActionTone = "blue"|"green"|"amber"|"rose"|"violet";
  type SchoolQuickAction = {label:string;to:string;icon:LucideIcon;tone:ActionTone};
  const quickActions: SchoolQuickAction[] = isTeacher ? [
    {label:"Mark Attendance",to:schoolPath("attendance"),icon:ClipboardCheck,tone:"violet"},
    {label:"Enter Marks",to:schoolPath("marks"),icon:SchoolIcon,tone:"blue"},
    {label:"Student Records",to:schoolPath("students"),icon:GraduationCap,tone:"green"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"amber"},
  ] : isReceptionist ? [
    {label:"New Student",to:schoolPath("students")+"?view=new",icon:UserPlus,tone:"green"},
    {label:"Student Directory",to:schoolPath("students"),icon:GraduationCap,tone:"blue"},
    {label:"Teacher Directory",to:schoolPath("teachers"),icon:UsersRound,tone:"violet"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"amber"},
  ] : isAccountant ? [
    {label:"Fee Collection",to:schoolPath("fees"),icon:WalletCards,tone:"amber"},
    {label:"Student Lookup",to:schoolPath("students"),icon:GraduationCap,tone:"blue"},
    {label:"Fee Reports",to:schoolPath("reports")+"?report=fee_collections",icon:BarChart3,tone:"green"},
    {label:"Outstanding Dues",to:schoolPath("reports")+"?report=fee_dues",icon:AlertTriangle,tone:"rose"},
  ] : [
    {label:"New Student",to:schoolPath("students")+"?view=new",icon:UserPlus,tone:"green"},
    {label:"Fee Collection",to:schoolPath("fees"),icon:WalletCards,tone:"amber"},
    {label:"Attendance",to:schoolPath("attendance"),icon:ClipboardCheck,tone:"violet"},
    {label:"Reports",to:schoolPath("reports"),icon:BarChart3,tone:"blue"},
  ];
  const birthdays=summary?.birthdays_today||[];
  const reminders=summary?.reminders||[];
  return <DashboardPageFrame title={`${role} Dashboard`} subtitle={`${summary?.school_name||"School"}${summary?.academic_year?` · Academic Year ${summary.academic_year}`:""}`} error={error}>
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"><MetricTile label="Total Students" value={summary?.students} icon={GraduationCap}/><MetricTile label="Total Teachers" value={summary?.teachers} icon={UsersRound} tone="green"/><MetricTile label="Students Present Today" value={summary?.present_students_today} icon={CalendarCheck2} tone="violet"/><MetricTile label="Teachers Present Today" value={summary?.present_teachers_today} icon={ClipboardCheck} tone="amber"/></div>
    {financeVisible&&<div className="grid grid-cols-1 gap-4 md:grid-cols-2"><MetricTile label="Fees Collected" value={formatMoney(summary?.fees_collected)} icon={IndianRupee} tone="green" to={schoolPath("fees")}/><MetricTile label="Outstanding Fees" value={formatMoney(summary?.fees_due)} icon={CircleDollarSign} tone="rose" to={schoolPath("reports")+"?report=fee_dues"}/></div>}
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
      <Panel title="Quick Actions"><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{quickActions.map(action=><QuickAction key={action.label} label={action.label} to={action.to} icon={action.icon} tone={action.tone}/>)}</div></Panel>
      <Panel title="Current Academic Year"><div className="flex items-center justify-between gap-3"><div><div className="text-2xl font-bold text-gray-900">{summary?.academic_year||"Not active"}</div><div className="mt-1 text-sm text-gray-500">{summary?.academic_year_code||"Academic calendar requires attention"}</div></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${summary?.academic_year?"bg-green-100 text-green-700":"bg-amber-100 text-amber-700"}`}>{summary?.academic_year?"Active":"Pending"}</span></div></Panel>
    </div>
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2"><Panel title={`Today’s Birthdays (${birthdays.length})`}>{birthdays.length?<div className="space-y-3">{birthdays.slice(0,6).map(item=><div key={item.student_id} className="flex items-center justify-between gap-3 border-b border-gray-100 pb-3 last:border-0 last:pb-0"><span className="font-medium text-gray-800">{item.name}</span><span className="text-sm text-gray-500">{item.age?`Turns ${item.age}`:"Birthday today"}</span></div>)}</div>:<p className="text-sm text-gray-500">No student birthdays today.</p>}</Panel><Panel title={`User Reminders (${reminders.length})`}>{reminders.length?<div className="space-y-3">{reminders.map((item,index)=><div key={`${item.type}-${index}`} className="flex items-start gap-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900"><AlertTriangle size={17} className="mt-0.5 shrink-0"/><span>{item.message}</span></div>)}</div>:<p className="text-sm text-gray-500">No pending system reminders for this account.</p>}</Panel></div>
  </DashboardPageFrame>;
}

function ParentStudentDashboard({linkedStudents,selectedStudentId,setSelectedStudentId,portal,error}:{linkedStudents:LinkedStudent[];selectedStudentId:string;setSelectedStudentId:(id:string)=>void;portal:ParentStudentPortalSummary|null;error:string}) {
  return <DashboardPageFrame title={portal?.student.school_name||"Parent / Student Portal"} subtitle="Read-only access to linked student information." error={error}><Panel title="Student"><label className="block max-w-xl"><span className="label">Student</span><select className="input" value={selectedStudentId} onChange={e=>setSelectedStudentId(e.target.value)}><option value="">Select Student</option>{linkedStudents.map(student=><option key={student.id} value={student.id}>{student.display_name} · {student.admission_number}</option>)}</select></label>{linkedStudents.length===0&&<p className="mt-3 text-sm text-gray-500">No students are linked to this access number.</p>}</Panel>{portal&&<><div className="grid grid-cols-1 gap-4 md:grid-cols-3"><MetricTile label="Student" value={portal.student.name} icon={GraduationCap}/><MetricTile label="Class" value={portal.enrollment?`${portal.enrollment.class} / ${portal.enrollment.section}`:"—"} icon={SchoolIcon} tone="green"/><MetricTile label="Academic Year" value={portal.enrollment?.academic_year||"—"} icon={CalendarCheck2} tone="violet"/></div><Panel title="Fees"><div className="grid grid-cols-1 gap-4 md:grid-cols-3"><MetricTile label="Total" value={`₹${portal.fees.total}`} icon={WalletCards}/><MetricTile label="Paid" value={`₹${portal.fees.paid}`} icon={IndianRupee} tone="green"/><MetricTile label="Due" value={`₹${portal.fees.due}`} icon={CircleDollarSign} tone="rose"/></div></Panel></>}</DashboardPageFrame>;
}

function StatusRow({label,value}:{label:string;value:string}) {return <div className="flex items-center justify-between gap-4 border-b border-gray-100 pb-2 last:border-0"><span className="text-gray-500">{label}</span><span className="text-right font-medium text-gray-800">{value}</span></div>}
