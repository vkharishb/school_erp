import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Download, Printer, RefreshCw } from "lucide-react";
import { academicApi, foundationApi, reportsApi, type ReportFilters } from "../services/api";
import { useAuthStore } from "../store/authStore";
import type { AcademicClass, AcademicYear, Campus, ReportResult, Section, Subject } from "../types";
import { hasModule, hasPermission } from "../utils/permissions";
import { apiErrorMessage } from "../utils/apiError";

type ReportOption={key:string;label:string;module:string;permission:string};
const REPORTS:ReportOption[]=[
  {key:"student_roster",label:"Student Enrollment",module:"student",permission:"student.view"},
  {key:"teacher_roster",label:"Teachers",module:"teacher",permission:"teacher.view"},
  {key:"student_attendance",label:"Student Attendance",module:"attendance",permission:"attendance.view"},
  {key:"teacher_attendance",label:"Teacher Attendance",module:"attendance",permission:"attendance.view"},
  {key:"fee_collections",label:"Fee Collections",module:"fee",permission:"fee.view"},
  {key:"fee_dues",label:"Outstanding Fee Dues",module:"fee",permission:"fee.view"},
  {key:"marks_performance",label:"Marks Performance",module:"marks",permission:"marks.view"},
];

function firstOfMonth(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-01`;}
function today(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;}
function labelize(key:string){return key.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase());}
function display(value:unknown){if(value===null||value===undefined||value==="")return "—";if(typeof value==="object")return JSON.stringify(value);return String(value);}

export default function ReportsPage(){
  const {schoolId=""}=useParams(); const user=useAuthStore(s=>s.user); const [searchParams]=useSearchParams();
  const query=searchParams.toString(); const requestedReport=searchParams.get("report")||"";
  const available=useMemo(()=>REPORTS.filter(r=>hasPermission(user,r.permission)&&hasModule(user,r.module)),[user]);
  const [reportKey,setReportKey]=useState(requestedReport); const [campuses,setCampuses]=useState<Campus[]>([]); const [years,setYears]=useState<AcademicYear[]>([]); const [classes,setClasses]=useState<AcademicClass[]>([]); const [sections,setSections]=useState<Section[]>([]); const [subjects,setSubjects]=useState<Subject[]>([]);
  const [campusId,setCampusId]=useState(""); const [yearId,setYearId]=useState(""); const [classId,setClassId]=useState(""); const [sectionId,setSectionId]=useState(""); const [subjectId,setSubjectId]=useState("");
  const [assessment,setAssessment]=useState(""); const [status,setStatus]=useState(""); const [paymentMode,setPaymentMode]=useState(""); const [startDate,setStartDate]=useState(searchParams.get("start_date")||firstOfMonth()); const [endDate,setEndDate]=useState(searchParams.get("end_date")||today());
  const [report,setReport]=useState<ReportResult|null>(null); const [loading,setLoading]=useState(false); const [error,setError]=useState("");
  const autoRunHandled=useRef(false);
  const canExport=hasPermission(user,"reports.export")&&(!reportKey.startsWith("fee_")||hasPermission(user,"fee.export"));

  useEffect(()=>{const requested=REPORTS.find(r=>r.key===requestedReport&&available.some(a=>a.key===r.key));setReportKey(current=>requested?.key||(available.some(r=>r.key===current)?current:available[0]?.key||""));},[available,requestedReport,query]);
  useEffect(()=>{if(!schoolId)return;void foundationApi.campuses(schoolId).then(c=>{setCampuses(c);if(c.length===1)setCampusId(c[0].id);}).catch(e=>setError(apiErrorMessage(e,"Failed to load campuses")));},[schoolId]);
  useEffect(()=>{setYearId("");setClassId("");setSectionId("");setSubjectId("");setYears([]);setClasses([]);setSections([]);setSubjects([]);if(!campusId)return;void Promise.all([foundationApi.academicYears(campusId),academicApi.classes(campusId),academicApi.subjects(campusId)]).then(([y,c,s])=>{setYears(y);setClasses(c);setSubjects(s);}).catch(e=>setError(apiErrorMessage(e,"Failed to load academic filters")));},[campusId]);
  useEffect(()=>{setSectionId("");setSections([]);if(classId)void academicApi.sections(classId).then(setSections).catch(e=>setError(apiErrorMessage(e,"Failed to load sections")));},[classId]);
  useEffect(()=>{setReport(null);setError("");},[reportKey]);

  const usesDates=["student_attendance","teacher_attendance","fee_collections"].includes(reportKey);
  const usesAcademic=["student_roster","student_attendance","fee_dues","marks_performance"].includes(reportKey);
  const usesSubject=reportKey==="marks_performance"; const usesAssessment=reportKey==="marks_performance";
  const usesStatus=["student_roster","teacher_roster","fee_collections"].includes(reportKey);
  const filters=():ReportFilters=>({campus_id:campusId||undefined,academic_year_id:usesAcademic?yearId||undefined:undefined,academic_class_id:usesAcademic?classId||undefined:undefined,section_id:usesAcademic?sectionId||undefined:undefined,subject_id:usesSubject?subjectId||undefined:undefined,assessment_name:usesAssessment?assessment.trim()||undefined:undefined,start_date:usesDates?startDate||undefined:undefined,end_date:usesDates?endDate||undefined:undefined,status:usesStatus?status||undefined:undefined,payment_mode:reportKey==="fee_collections"?paymentMode||undefined:undefined,limit:500});
  const run=async()=>{if(!reportKey)return;setLoading(true);setError("");try{setReport(await reportsApi.run(schoolId,reportKey,filters()));}catch(e){setError(apiErrorMessage(e,"Failed to generate report"));}finally{setLoading(false);}};
  useEffect(()=>{if(searchParams.get("run")!=="1"||autoRunHandled.current||!schoolId||!reportKey)return;autoRunHandled.current=true;void run();},[schoolId,reportKey,query]);
  const exportXlsx=async()=>{if(!reportKey||!canExport)return;setError("");try{const blob=await reportsApi.exportXlsx(schoolId,reportKey,filters());const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`${reportKey}-${today()}.xlsx`;a.click();URL.revokeObjectURL(url);}catch(e){setError(apiErrorMessage(e,"Failed to export report"));}};

  if(!available.length)return <div className="card text-gray-600">You have Reports access, but no underlying Student, Teacher, Attendance, Fee or Marks report permission is available.</div>;
  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold">Reports</h1><p className="text-gray-500 mt-1">Permission-scoped operational and academic reports. Sensitive IDs and passwords are never included.</p></div>
    {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    <section className="card space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-4 gap-4">
        <Select label="Report" value={reportKey} onChange={v=>{setReportKey(v);setStatus("");setPaymentMode("");}} options={available.map(r=>[r.key,r.label])}/>
        <Select label="Campus / Branch" value={campusId} onChange={setCampusId} options={campuses.map(c=>[c.id,c.name])} allLabel="All accessible campuses"/>
        {usesAcademic&&<Select label="Academic Year" value={yearId} onChange={v=>{setYearId(v);setClassId("");setSectionId("");}} options={years.map(y=>[y.id,y.name||y.code])} allLabel="All years"/>}
        {usesAcademic&&<Select label="Class" value={classId} onChange={setClassId} options={classes.map(c=>[c.id,c.name])} allLabel="All classes"/>}
        {usesAcademic&&<Select label="Section" value={sectionId} onChange={setSectionId} options={sections.map(s=>[s.id,s.name])} allLabel="All sections"/>}
        {usesSubject&&<Select label="Subject" value={subjectId} onChange={setSubjectId} options={subjects.map(s=>[s.id,s.name])} allLabel="All subjects"/>}
        {usesAssessment&&<Field label="Assessment" value={assessment} onChange={setAssessment} placeholder="e.g. Unit Test 1"/>}
        {usesDates&&<Field label="From" type="date" value={startDate} onChange={setStartDate}/>} {usesDates&&<Field label="To" type="date" value={endDate} onChange={setEndDate}/>} 
        {reportKey==="fee_collections"&&<Select label="Payment Mode" value={paymentMode} onChange={setPaymentMode} options={[["cash","Cash"],["upi","UPI"]]} allLabel="All modes"/>}
        {usesStatus&&<Select label="Status" value={status} onChange={setStatus} options={reportKey==="fee_collections"?[["posted","Posted"],["cancelled","Cancelled"]]:[["active","Active"],["inactive","Inactive"]]} allLabel="All statuses"/>}
      </div>
      {(classId||sectionId)&&!campusId&&<div className="text-sm text-amber-700">Select a campus before using class/section filters.</div>}
      <div className="flex flex-wrap gap-2"><button className="btn-primary inline-flex items-center gap-2" onClick={()=>void run()} disabled={loading}><RefreshCw size={16}/>{loading?"Generating…":"Generate Report"}</button>{canExport&&<button className="btn-secondary inline-flex items-center gap-2" onClick={()=>void exportXlsx()}><Download size={16}/>Export Excel</button>}<button className="btn-secondary inline-flex items-center gap-2" onClick={()=>window.print()}><Printer size={16}/>Print / Save PDF</button></div>
    </section>
    {report&&<>
      <section className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-3">{Object.entries(report.summary).map(([k,v])=><div key={k} className="card"><div className="text-xs uppercase tracking-wide text-gray-400">{labelize(k)}</div><div className="text-lg font-semibold mt-1 break-words">{display(v)}</div></div>)}</section>
      <section className="card overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 mb-4"><div><h2 className="text-lg font-semibold">{report.title}</h2><div className="text-sm text-gray-500">{report.total_count} matching row(s){report.truncated?" · preview limited to 500":""}</div></div><div className="text-xs text-gray-400">Generated {new Date(report.generated_at).toLocaleString()}</div></div><div className="overflow-auto max-h-[65vh]"><table className="min-w-full text-sm"><thead className="bg-gray-50 sticky top-0"><tr>{report.columns.map(c=><th key={c.key} className="px-3 py-2 text-left whitespace-nowrap border-b">{c.label}</th>)}</tr></thead><tbody>{report.rows.map((row,i)=><tr key={i} className="border-b last:border-b-0 hover:bg-gray-50">{report.columns.map(c=><td key={c.key} className="px-3 py-2 whitespace-nowrap">{display(row[c.key])}</td>)}</tr>)}</tbody></table>{report.rows.length===0&&<div className="py-10 text-center text-gray-500">No data matched the selected filters.</div>}</div></section>
    </>}
  </div>;
}
function Select({label,value,onChange,options,allLabel}:{label:string;value:string;onChange:(v:string)=>void;options:string[][];allLabel?:string}){return <label><span className="label">{label}</span><select className="input" value={value} onChange={e=>onChange(e.target.value)}><option value="">{allLabel||"Select…"}</option>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
function Field({label,value,onChange,type="text",placeholder=""}:{label:string;value:string;onChange:(v:string)=>void;type?:string;placeholder?:string}){return <label><span className="label">{label}</span><input className="input" type={type} value={value} placeholder={placeholder} onChange={e=>onChange(e.target.value)}/></label>}
