import { FormEvent, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { academicApi, erpAccessApi, foundationApi, studentApi } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { hasPermission } from "../utils/permissions";
import { apiErrorMessage } from "../utils/apiError";
import type { AcademicClass, AcademicYear, Campus, Section, Student } from "../types";

const GENDERS = ["Male","Female","Transgender","Other","Prefer not to say"];
const CASTE_CATEGORIES = ["OC","SC","ST","BC-A","BC-B","BC-C","BC-D","BC-E","BC-F"];

const emptyStudentForm = {
  campus_id:"",
  academic_year_id:"",
  academic_class_id:"",
  section_id:"",
  admission_number:"",
  admission_date:"",
  student_name:"",
  date_of_birth:"",
  gender:"",
  father_name:"",
  mother_name:"",
  father_number:"",
  mother_number:"",
  email_id:"",
  aadhaar_number:"",
  caste_category:"",
  sub_caste:"",
  address:"",
  emergency_contact_number:"",
};

function splitStudentName(name:string):{first_name:string;last_name:string|null}{
  const parts=name.trim().split(/\s+/).filter(Boolean);
  return {first_name:parts[0]||"",last_name:parts.length>1?parts.slice(1).join(" "):null};
}

export default function StudentsPage(){
  const {schoolId=""}=useParams();
  const [searchParams]=useSearchParams();
  const user=useAuthStore(s=>s.user);
  const canCreate=hasPermission(user,"student.create"),canEdit=hasPermission(user,"student.edit"),canOptERP=hasPermission(user,"erp_access.opt");
  const [students,setStudents]=useState<Student[]>([]),[campuses,setCampuses]=useState<Campus[]>([]),[years,setYears]=useState<AcademicYear[]>([]),[classes,setClasses]=useState<AcademicClass[]>([]),[sections,setSections]=useState<Section[]>([]);
  const [show,setShow]=useState(false),[search,setSearch]=useState(""),[error,setError]=useState(""),[message,setMessage]=useState(""),[editing,setEditing]=useState<Student|null>(null);
  const [form,setForm]=useState({...emptyStudentForm});
  const [accessStudent,setAccessStudent]=useState<Student|null>(null),[contacts,setContacts]=useState<{mobile:string;label:string}[]>([]),[accessNumber,setAccessNumber]=useState(""),[initialPassword,setInitialPassword]=useState("");

  const load=async()=>{try{setStudents(await studentApi.list(schoolId,search||undefined));}catch(e){setError(apiErrorMessage(e,"Failed to load students"))}};
  const selectCampus=async(id:string)=>{
    setForm(f=>({...f,campus_id:id,academic_year_id:"",academic_class_id:"",section_id:""}));
    if(!id){setYears([]);setClasses([]);setSections([]);return;}
    try{
      const[ys,cls]=await Promise.all([foundationApi.academicYears(id),academicApi.classes(id)]);
      setYears(ys);setClasses(cls);
      const classId=cls[0]?.id||"";
      const ss=classId?await academicApi.sections(classId):[];
      setSections(ss);
      setForm(f=>({...f,campus_id:id,academic_year_id:ys.find(y=>y.status==="active")?.id||ys[0]?.id||"",academic_class_id:classId,section_id:ss[0]?.id||""}));
    }catch(e){setError(apiErrorMessage(e,"Failed to load academic setup"));}
  };
  const loadAcademic=async()=>{try{const cs=await foundationApi.campuses(schoolId);setCampuses(cs);await selectCampus(user?.campus_id||cs[0]?.id||"");}catch(e){setError(apiErrorMessage(e,"Failed to load academic setup. Create Organization Academic Year, classes and sections first."));}};
  useEffect(()=>{if(schoolId){void load();void loadAcademic();}},[schoolId,user?.campus_id]);
  useEffect(()=>{if(searchParams.get("view")==="new"&&canCreate)setShow(true);},[searchParams,canCreate]);
  const classChanged=async(id:string)=>{setForm(f=>({...f,academic_class_id:id,section_id:""}));try{const ss=await academicApi.sections(id);setSections(ss);setForm(f=>({...f,academic_class_id:id,section_id:ss[0]?.id||""}));}catch{setSections([])}};

  const submit=async(e:FormEvent)=>{
    e.preventDefault();setError("");setMessage("");
    const mandatory:[string,string][]=[
      ["Campus",form.campus_id],["Academic Year",form.academic_year_id],["Class",form.academic_class_id],["Section",form.section_id],
      ["Admission Number",form.admission_number],["Admission Date",form.admission_date],["Student Name",form.student_name],["Date of Birth",form.date_of_birth],
      ["Gender",form.gender],["Father's Name",form.father_name],["Mother's Name",form.mother_name],["Father's Mobile Number",form.father_number],["Caste Category",form.caste_category],
    ];
    const missing=mandatory.filter(([,value])=>!value.trim()).map(([label])=>label);
    if(missing.length){setError(`Please complete the mandatory fields: ${missing.join(", ")}.`);return;}
    const {first_name,last_name}=splitStudentName(form.student_name);
    try{
      await studentApi.create(schoolId,{
        campus_id:form.campus_id,
        academic_year_id:form.academic_year_id,
        academic_class_id:form.academic_class_id,
        section_id:form.section_id,
        admission_number:form.admission_number.trim(),
        admission_date:form.admission_date,
        first_name,
        last_name,
        date_of_birth:form.date_of_birth,
        gender:form.gender,
        father_name:form.father_name.trim(),
        mother_name:form.mother_name.trim(),
        father_number:form.father_number.trim(),
        mother_number:form.mother_number.trim()||null,
        email_id:form.email_id.trim()||null,
        government_id:form.aadhaar_number.trim()||null,
        category:form.caste_category,
        sub_caste:form.sub_caste.trim()||null,
        address_line1:form.address.trim()||null,
        emergency_contact_name:form.emergency_contact_number.trim()?"Emergency Contact":null,
        emergency_contact_phone:form.emergency_contact_number.trim()||null,
      });
      setShow(false);
      setForm(f=>({...emptyStudentForm,campus_id:f.campus_id,academic_year_id:f.academic_year_id,academic_class_id:f.academic_class_id,section_id:f.section_id}));
      setMessage("Student created, SIS generated and enrolment completed.");
      await load();
    }catch(e){setError(apiErrorMessage(e,"Failed to create student"));}
  };

  const saveEdit=async(e:FormEvent)=>{e.preventDefault();if(!editing)return;try{await studentApi.update(schoolId,editing.id,{admission_number:editing.admission_number,first_name:editing.first_name,last_name:editing.last_name||null,date_of_birth:editing.date_of_birth||null,gender:editing.gender||null,admission_date:editing.admission_date||null,category:editing.category||null,government_id:editing.government_id||null,address_line1:editing.address_line1||null,emergency_contact_name:editing.emergency_contact_name||null,emergency_contact_phone:editing.emergency_contact_phone||null});setEditing(null);setMessage("Student profile updated.");await load();}catch(e){setError(apiErrorMessage(e,"Failed to update student"));}};
  const toggleStatus=async(s:Student)=>{try{if(s.status==="active")await studentApi.archive(schoolId,s.id);else await studentApi.reactivate(schoolId,s.id);setMessage(s.status==="active"?"Student archived.":"Student reactivated.");await load();}catch(e){setError(apiErrorMessage(e,"Failed to update student status"));}};
  const openERPAccess=async(s:Student)=>{setError("");setMessage("");setAccessStudent(s);setAccessNumber("");setInitialPassword("");try{const items=await erpAccessApi.contacts(schoolId,s.id);setContacts(items);setAccessNumber(items[0]?.mobile||"");if(items.length===0)setError("No registered contact number is available. Add a parent/guardian or emergency contact number to the Student profile first.");}catch(e){setContacts([]);setError(apiErrorMessage(e,"Unable to load registered access numbers."));}};
  const optERP=async()=>{if(!accessStudent||!accessNumber)return;setError("");setMessage("");try{const result=await erpAccessApi.optIn(schoolId,{student_id:accessStudent.id,access_number:accessNumber,initial_password:initialPassword||undefined});setMessage(`ERP access activated for ${accessStudent.first_name}. The annual ERP fee was added to the Student ledger.${result.login_account_created?" A new Parent / Student login account was created.":" The existing family login was linked to this Student."}`);setAccessStudent(null);setContacts([]);setInitialPassword("");}catch(e){setError(apiErrorMessage(e,"Failed to activate Parent / Student ERP access."));}};

  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="text-2xl font-bold">Students Management</h1><p className="text-gray-500 mt-1">Student master, enrolment and Parent / Student ERP access.</p></div>{canCreate&&<button className="btn-primary" onClick={()=>setShow(!show)}>New Student</button>}</div>
    {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    {message&&<div className="rounded-lg bg-green-50 border border-green-200 text-green-700 px-4 py-3 text-sm">{message}</div>}

    <section className="card space-y-3">
      <div><h2 className="font-semibold">Student Enrolment Setup</h2><p className="text-sm text-gray-500">Campus is the working scope. Academic Year → Class → Section determines where the Student is enrolled.</p></div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Select label="Campus" value={form.campus_id} onChange={v=>void selectCampus(v)} options={campuses.map(c=>[c.id,c.name])}/>
        <Select label="Academic Year*" value={form.academic_year_id} onChange={v=>setForm({...form,academic_year_id:v})} options={years.map(y=>[y.id,`${y.name} (${y.status})`])}/>
        <Select label="Class*" value={form.academic_class_id} onChange={v=>void classChanged(v)} options={classes.map(c=>[c.id,c.name])}/>
        <Select label="Section*" value={form.section_id} onChange={v=>setForm({...form,section_id:v})} options={sections.map(s=>[s.id,s.name])}/>
      </div>
    </section>

    {show&&<form onSubmit={submit} className="card space-y-6">
      <div><h2 className="text-lg font-semibold">New Student Enrolment</h2><p className="text-sm text-gray-500 mt-1">The manual form and Student Bulk Upload use the same 20-field enrolment model. Fields marked * are mandatory.</p></div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ReadonlyField label="SIS Number" value="Generated automatically after save"/>
        <ReadonlyField label="Student Status" value="Active (system generated)"/>
      </div>
      <div>
        <h3 className="font-semibold mb-3">Admission Details</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Admission Number*" value={form.admission_number} onChange={v=>setForm({...form,admission_number:v})}/>
          <Field label="Admission Date*" type="date" value={form.admission_date} onChange={v=>setForm({...form,admission_date:v})}/>
          <Field label="Student Name*" value={form.student_name} onChange={v=>setForm({...form,student_name:v})}/>
          <Field label="Date of Birth*" type="date" value={form.date_of_birth} onChange={v=>setForm({...form,date_of_birth:v})}/>
          <Select label="Gender*" value={form.gender} onChange={v=>setForm({...form,gender:v})} options={GENDERS.map(v=>[v,v])}/>
        </div>
      </div>
      <div>
        <h3 className="font-semibold mb-3">Parent / Contact Details</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Father's Name*" value={form.father_name} onChange={v=>setForm({...form,father_name:v})}/>
          <Field label="Mother's Name*" value={form.mother_name} onChange={v=>setForm({...form,mother_name:v})}/>
          <Field label="Father's Mobile Number*" type="tel" value={form.father_number} onChange={v=>setForm({...form,father_number:v})}/>
          <Field label="Mother's Mobile Number" type="tel" value={form.mother_number} onChange={v=>setForm({...form,mother_number:v})} required={false}/>
          <Field label="Email ID" type="email" value={form.email_id} onChange={v=>setForm({...form,email_id:v})} required={false}/>
          <Field label="Emergency Contact Number" type="tel" value={form.emergency_contact_number} onChange={v=>setForm({...form,emergency_contact_number:v})} required={false}/>
          <div className="md:col-span-2"><Field label="Address" value={form.address} onChange={v=>setForm({...form,address:v})} required={false}/></div>
        </div>
      </div>
      <div>
        <h3 className="font-semibold mb-3">Additional Details</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Aadhaar Number" value={form.aadhaar_number} onChange={v=>setForm({...form,aadhaar_number:v})} required={false}/>
          <Select label="Caste Category*" value={form.caste_category} onChange={v=>setForm({...form,caste_category:v})} options={CASTE_CATEGORIES.map(v=>[v,v])}/>
          <Field label="Sub-caste" value={form.sub_caste} onChange={v=>setForm({...form,sub_caste:v})} required={false}/>
        </div>
      </div>
      <div><button className="btn-primary">Create & Enroll</button></div>
    </form>}

    {editing&&<form onSubmit={saveEdit} className="card grid grid-cols-1 md:grid-cols-2 gap-4"><div className="md:col-span-2 flex justify-between"><div><h2 className="font-semibold">Edit Student</h2><p className="text-sm text-gray-500">Changes require confirmation, reason and are audited.</p></div><button type="button" className="btn-secondary" onClick={()=>setEditing(null)}>Cancel</button></div><Field label="Admission number" value={editing.admission_number} onChange={v=>setEditing({...editing,admission_number:v})}/><Field label="First name" value={editing.first_name} onChange={v=>setEditing({...editing,first_name:v})}/><Field label="Last name" value={editing.last_name||""} onChange={v=>setEditing({...editing,last_name:v})} required={false}/><Field label="Date of birth" type="date" value={editing.date_of_birth||""} onChange={v=>setEditing({...editing,date_of_birth:v})} required={false}/><Field label="Admission date" type="date" value={editing.admission_date||""} onChange={v=>setEditing({...editing,admission_date:v})} required={false}/><Field label="Gender" value={editing.gender||""} onChange={v=>setEditing({...editing,gender:v})} required={false}/><Field label="Caste Category" value={editing.category||""} onChange={v=>setEditing({...editing,category:v})} required={false}/><Field label="Aadhaar Number" value={editing.government_id||""} onChange={v=>setEditing({...editing,government_id:v})} required={false}/><Field label="Address" value={editing.address_line1||""} onChange={v=>setEditing({...editing,address_line1:v})} required={false}/><Field label="Emergency Contact" value={editing.emergency_contact_phone||""} onChange={v=>setEditing({...editing,emergency_contact_phone:v})} required={false}/><div className="md:col-span-2"><button className="btn-primary">Save Changes</button></div></form>}

    {accessStudent&&<section className="card space-y-4"><div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">Activate Parent / Student ERP Access</h2><p className="text-sm text-gray-500">{accessStudent.first_name} {accessStudent.last_name||""} · Access activates immediately and the configured annual ERP fee is added automatically.</p></div><button className="btn-secondary" onClick={()=>setAccessStudent(null)}>Cancel</button></div><Select label="Login & WhatsApp Access Number" value={accessNumber} onChange={setAccessNumber} options={contacts.map(c=>[c.mobile,`${c.mobile} · ${c.label}`])}/><Field label="Initial school-issued password (required only for a new family access number)" type="password" value={initialPassword} onChange={setInitialPassword} required={false}/><p className="text-xs text-gray-500">If this number already has an account for another child, leave the password blank; the Student will be linked to the existing family login.</p><div><button type="button" className="btn-primary" disabled={!accessNumber} onClick={()=>void optERP()}>Opt & Activate ERP Access</button></div></section>}

    <div className="card flex gap-2"><input className="input" placeholder="Search name, admission number or SIS number" value={search} onChange={e=>setSearch(e.target.value)}/><button className="btn-secondary" onClick={()=>void load()}>Search</button></div>
    <div className="card overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left border-b"><th className="py-2">Student</th><th>Admission</th><th>SIS Number</th><th>Registered Contact</th><th>Status</th>{(canEdit||canOptERP)&&<th>Actions</th>}</tr></thead><tbody>{students.map(s=><tr key={s.id} className="border-b last:border-0"><td className="py-3 font-medium">{s.first_name} {s.last_name||""}</td><td>{s.admission_number}</td><td className="font-mono text-xs">{s.student_code}</td><td>{s.emergency_contact_phone||"See parent contacts"}</td><td>{s.status}</td>{(canEdit||canOptERP)&&<td><div className="flex flex-wrap gap-2">{canEdit&&<><button className="btn-secondary" onClick={()=>setEditing({...s})}>Edit</button><button className="btn-secondary" onClick={()=>void toggleStatus(s)}>{s.status==="active"?"Archive":"Reactivate"}</button></>}{canOptERP&&s.status==="active"&&<button className="btn-secondary" onClick={()=>void openERPAccess(s)}>ERP Access</button>}</div></td>}</tr>)}</tbody></table>{students.length===0&&<div className="py-8 text-center text-gray-500">No students found.</div>}</div>
  </div>;
}

function Field({label,value,onChange,type="text",required=true}:{label:string;value:string;onChange:(v:string)=>void;type?:string;required?:boolean}){return <label><span className="label">{label}</span><input className="input" type={type} value={value} onChange={e=>onChange(e.target.value)} required={required}/></label>}
function ReadonlyField({label,value}:{label:string;value:string}){return <label><span className="label">{label}</span><input className="input bg-gray-50 text-gray-500" value={value} readOnly/></label>}
function Select({label,value,onChange,options}:{label:string;value:string;onChange:(v:string)=>void;options:[string,string][]}){return <label><span className="label">{label}</span><select className="input" value={value} onChange={e=>onChange(e.target.value)} required><option value="">Select</option>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>}
