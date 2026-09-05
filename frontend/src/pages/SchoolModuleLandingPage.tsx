import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { BarChart3, BookOpenCheck, ClipboardCheck, GraduationCap, IndianRupee, School, UploadCloud, UserPlus, UsersRound, WalletCards, type LucideIcon } from "lucide-react";
import { schoolApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import type { School as SchoolType, User } from "../types";
import { apiErrorMessage } from "../utils/apiError";
import { hasAnyPermission, hasPermission } from "../utils/permissions";

interface ModuleCard { title:string; description:string; to:string; icon:LucideIcon; show:boolean; }

export default function SchoolModuleLandingPage({title,description,segment}:{title:string;description:string;segment:string}) {
  const user=useAuthStore(state=>state.user);
  const navigate=useNavigate();
  const location=useLocation();
  const [schools,setSchools]=useState<SchoolType[]>([]);
  const [error,setError]=useState("");
  const sid=user?.school_id||"";

  useEffect(()=>{
    if(sid)return;
    void schoolApi.list().then(setSchools).catch(e=>setError(apiErrorMessage(e,"Failed to load schools / branches.")));
  },[sid]);

  const cards=useMemo(()=>sid?moduleCards(segment,sid,user):[],[segment,sid,user]);
  const destination=(schoolId:string)=>`/schools/${schoolId}/${segment}${location.search}`;

  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold text-gray-900">{title}</h1><p className="mt-1 text-gray-500">{description}</p></div>
    {error&&<div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
    {sid?<div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{cards.filter(card=>card.show).map(card=>{const Icon=card.icon;return <Link key={card.title} to={card.to} className="card group transition hover:border-primary-300 hover:bg-primary-50/30"><div className="flex items-start gap-4"><div className="rounded-xl bg-primary-50 p-3 text-primary-700"><Icon size={23}/></div><div className="min-w-0"><h2 className="font-semibold text-gray-900 group-hover:text-primary-800">{card.title}</h2><p className="mt-1 text-sm leading-6 text-gray-500">{card.description}</p></div></div></Link>})}</div>:<section className="card"><h2 className="mb-4 text-lg font-semibold">Select School / Branch</h2><div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">{schools.map(school=><button key={school.id} className="rounded-xl border border-gray-200 p-4 text-left transition hover:border-primary-400 hover:bg-primary-50" onClick={()=>navigate(destination(school.id))}><div className="font-semibold">{school.configuration?.name||school.code}</div><div className="mt-1 text-sm text-gray-500">{school.code} · {school.is_active?"Active":"Disabled"}</div></button>)}</div>{schools.length===0&&!error&&<div className="py-6 text-gray-500">No accessible schools found.</div>}</section>}
  </div>;
}

function moduleCards(segment:string,sid:string,user:User|null):ModuleCard[] {
  const path=(name:string)=>`/schools/${sid}/${name}`;
  const report=(key:string)=>`${path("reports")}?report=${key}`;
  if(segment==="students")return [
    {title:"Student Records",description:"Search, view, enrol and maintain student profiles.",to:path("students"),icon:GraduationCap,show:true},
    {title:"New Student",description:"Open Student Records and admit a new student using the governed enrolment form.",to:`${path("students")}?view=new`,icon:UserPlus,show:hasPermission(user,"student.create")||hasPermission(user,"student.manage")},
    {title:"Bulk Import",description:"Import the approved 20-field student workbook with per-row Academic Year, Class and Section validation.",to:path("bulk-imports"),icon:UploadCloud,show:hasPermission(user,"student.bulk_upload")},
    {title:"Student Reports",description:"Run and export student reports within your authorized school scope.",to:report("students"),icon:BarChart3,show:hasPermission(user,"reports.view")},
  ];
  if(segment==="teachers")return [
    {title:"Teacher / Staff Records",description:"View and maintain teacher and staff master records.",to:path("teachers"),icon:UsersRound,show:true},
    {title:"Add Teacher / Staff",description:"Open the staff master and add a new teacher or non-teaching staff member.",to:`${path("teachers")}?view=new`,icon:UserPlus,show:hasAnyPermission(user,["teacher.create","teacher.manage"])},
    {title:"Bulk Import",description:"Import staff using the approved teacher/staff template.",to:path("bulk-imports"),icon:UploadCloud,show:hasPermission(user,"teacher.bulk_upload")},
    {title:"Teacher Reports",description:"Run authorized staff and teacher reports.",to:report("teachers"),icon:BarChart3,show:hasPermission(user,"reports.view")},
  ];
  if(segment==="fees")return [
    {title:"Fee Operations",description:"Configure fee setup and perform governed fee collection operations.",to:path("fees"),icon:WalletCards,show:true},
    {title:"Fee Collection Reports",description:"Review collections and financial activity for the selected school.",to:report("fee_collections"),icon:IndianRupee,show:hasPermission(user,"reports.view")},
    {title:"Outstanding Dues",description:"Review students with outstanding fee balances.",to:report("fee_dues"),icon:BarChart3,show:hasPermission(user,"reports.view")},
    {title:"Fee Bulk Imports",description:"Open governed Fee Structure / Prior Year Dues imports when permitted.",to:path("bulk-imports"),icon:UploadCloud,show:hasAnyPermission(user,["fee.structure.bulk_upload","fee.dues.bulk_upload"])},
  ];
  if(segment==="marks")return [
    {title:"Marks Entry / Results",description:"Enter, finalize and govern marks for authorized classes and subjects.",to:path("marks"),icon:BookOpenCheck,show:true},
    {title:"Marks Reports",description:"Review finalized performance reports within your scope.",to:report("marks_performance"),icon:BarChart3,show:hasPermission(user,"reports.view")},
  ];
  if(segment==="attendance")return [
    {title:"Attendance",description:"Mark and correct student/teacher attendance with audit history.",to:path("attendance"),icon:ClipboardCheck,show:true},
    {title:"Attendance Reports",description:"Review student and teacher attendance reports.",to:report("student_attendance"),icon:BarChart3,show:hasPermission(user,"reports.view")},
  ];
  if(segment==="reports")return [
    {title:"Report Center",description:"Choose Student, Teacher, Fee, Attendance, Marks and authorized administrative reports.",to:path("reports"),icon:BarChart3,show:true},
  ];
  return [{title:"Open Module",description:"Open this module for the selected school / branch.",to:path(segment),icon:School,show:true}];
}
