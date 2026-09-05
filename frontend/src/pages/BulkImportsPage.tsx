import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import BulkImportPanel from "../components/BulkImportPanel";
import { feeApi, foundationApi, importApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";
import { hasModule, hasPermission } from "../utils/permissions";
import { canImportClassesAndSections } from "../utils/bulkImports";
import type { Campus, FeeHead } from "../types";

export default function BulkImportsPage(){
  const {schoolId=""}=useParams();
  const user=useAuthStore(s=>s.user);
  const canClassSectionBulk=canImportClassesAndSections(user);
  const canStudent=hasPermission(user,"student.bulk_upload")&&hasModule(user,"student");
  const canTeacher=hasPermission(user,"teacher.bulk_upload")&&hasModule(user,"teacher");
  const canFeeStructure=hasPermission(user,"fee.structure.bulk_upload")&&hasModule(user,"fee");
  const canPriorDues=hasPermission(user,"fee.dues.bulk_upload")&&hasModule(user,"fee");
  const canManageClassSection=hasPermission(user,"academic_class.manage")||hasPermission(user,"school.config.view");
  const [campuses,setCampuses]=useState<Campus[]>([]),[campusId,setCampusId]=useState("");
  const [heads,setHeads]=useState<FeeHead[]>([]),[feeHeadId,setFeeHeadId]=useState("");
  const [error,setError]=useState("");

  useEffect(()=>{if(!schoolId)return;void (async()=>{try{const cs=await foundationApi.campuses(schoolId);setCampuses(cs);setCampusId(user?.campus_id||cs[0]?.id||"");if(canPriorDues||canFeeStructure){try{setHeads(await feeApi.heads(schoolId));}catch{setHeads([])}}}catch(e){setError(apiErrorMessage(e,"Failed to load import setup"))}})()},[schoolId,user?.campus_id,canPriorDues,canFeeStructure]);
  useEffect(()=>{if(!feeHeadId&&heads[0])setFeeHeadId(heads[0].id)},[heads,feeHeadId]);

  const studentContext=useMemo(()=>({campus_id:campusId}),[campusId]);
  const dueContext=useMemo(()=>({campus_id:campusId,fee_head_id:feeHeadId}),[campusId,feeHeadId]);

  return <div className="space-y-6">
    <div><h1 className="text-2xl font-bold">Bulk Imports</h1><p className="text-gray-500 mt-1">Centralized controlled imports for master and opening data. Marks upload remains inside Marks.</p></div>
    {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    <section className="card"><div className="flex flex-wrap items-end justify-between gap-4"><label className="w-full max-w-md"><span className="label">Campus / Branch</span><select className="input" value={campusId} onChange={e=>setCampusId(e.target.value)}><option value="">Select campus</option>{campuses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>{canManageClassSection&&<Link className="btn-secondary" to={`/schools/${schoolId}/classes-sections`}>Create / Manage Classes & Sections</Link>}</div></section>

    {canClassSectionBulk&&<BulkImportPanel
      title="Class & Section Import"
      description="Create Classes and their Sections together from one simple file. Enter section names separated by commas, for example Class 1 → A,B. ERP generates technical codes and class display order automatically."
      contextReady={!!campusId}
      requireContextBeforeFile
      contextMessage="Select a Campus / Branch before uploading. The template can be downloaded now."
      templateFilename="classes-sections-import.xlsx"
      templateUrl={`${import.meta.env.BASE_URL}templates/classes-sections-import.xlsx`}
      previewImport={file=>importApi.previewClassSections(schoolId,file,campusId)}
      confirmImport={(file,sha)=>importApi.confirmClassSections(schoolId,file,sha,campusId)}
    />}

    {canStudent&&<BulkImportPanel
      title="Student Import"
      description="Download the approved 20-field template after selecting a Campus / Branch. Each student row contains its own Academic Year, Class and Section, and the ERP validates those values before import. SIS Number and Student Status are generated automatically. Review the preview before confirming the import."
      contextReady={!!campusId}
      requireContextBeforeFile
      requireContextBeforeTemplate
      contextMessage="Select a Campus / Branch first. Then download the 20-field template with its Campus-specific ERP Reference sheet."
      templateFilename="students-import.xlsx"
      downloadTemplate={()=>importApi.studentTemplate(schoolId,campusId)}
      previewImport={file=>importApi.previewStudents(schoolId,file,studentContext)}
      confirmImport={(file,sha)=>importApi.confirmStudents(schoolId,file,sha,studentContext)}
    />}

    {canTeacher&&<BulkImportPanel title="Teacher Import" description="Imports teacher master data into the selected campus after validation and preview." contextReady={!!campusId} templateFilename="teachers-import.xlsx" downloadTemplate={()=>importApi.teacherTemplate(schoolId)} previewImport={file=>importApi.previewTeachers(schoolId,file,campusId)} confirmImport={(file,sha)=>importApi.confirmTeachers(schoolId,file,sha,campusId)}/>}

    {canFeeStructure&&<BulkImportPanel title="Fee Structure Import" description="Fee Heads must already exist in Fee Management. Academic Year, Class and Fee Head names in the workbook are validated against the selected campus." contextReady={!!campusId} templateFilename="fee-structures-import.xlsx" downloadTemplate={()=>importApi.feeStructureTemplate(schoolId)} previewImport={file=>importApi.previewFeeStructures(schoolId,file,campusId)} confirmImport={(file,sha)=>importApi.confirmFeeStructures(schoolId,file,sha,campusId)}/>}

    {canPriorDues&&<div className="space-y-3"><section className="card"><Select label="Prior Year Dues Fee Head" value={feeHeadId} options={heads.map(h=>[h.id,`${h.code} · ${h.name}`])} onChange={setFeeHeadId}/><p className="text-xs text-gray-500 mt-2">Choose the Fee Head that will receive opening/prior-year dues. Duplicate student/year/head charges are rejected.</p></section><BulkImportPanel title="Prior Year Dues Import" description="Financial opening balances are validated by admission number and prior academic year. Review the total outstanding amount before confirming." contextReady={Object.values(dueContext).every(Boolean)} templateFilename="prior-year-dues-import.xlsx" downloadTemplate={()=>importApi.priorDuesTemplate(schoolId)} previewImport={file=>importApi.previewPriorDues(schoolId,file,dueContext)} confirmImport={(file,sha)=>importApi.confirmPriorDues(schoolId,file,sha,dueContext)}/></div>}

    {!canClassSectionBulk&&!canStudent&&!canTeacher&&!canFeeStructure&&!canPriorDues&&<div className="card text-gray-500">You do not have permission to run bulk imports.</div>}
  </div>
}

function Select({label,value,options,onChange}:{label:string;value:string;options:[string,string][];onChange:(v:string)=>void}){return <label><span className="label">{label}</span><select className="input" value={value} onChange={e=>onChange(e.target.value)}><option value="">Select</option>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
