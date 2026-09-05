import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus, RotateCcw, School as SchoolIcon, X } from "lucide-react";
import { organizationApi, schoolApi } from "../services/api";
import PasswordInput from "../components/PasswordInput";
import type { Organization, School } from "../types";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";

const suggestAreaCode=(value:string)=>{
  const cleaned=value.toUpperCase().replace(/[^A-Z0-9]/g,"");
  if(cleaned.length<=3)return cleaned;
  const first=cleaned[0]||"";
  const consonants=cleaned.slice(1).replace(/[AEIOU]/g,"");
  return (first+consonants).slice(0,3) || cleaned.slice(0,3);
};

type UdiseDraft={udise_code:string;label:string;is_primary:boolean};

export default function SchoolsPage() {
  const [searchParams] = useSearchParams();
  const next = searchParams.get("next") || "detail";
  const targetFor = (schoolId:string) => next === "detail" ? `/schools/${schoolId}` : `/schools/${schoolId}/${next}`;
  const user = useAuthStore(s=>s.user);
  const [schools,setSchools]=useState<School[]>([]);
  const [organizations,setOrganizations]=useState<Organization[]>([]);
  const [loading,setLoading]=useState(true);
  const [showForm,setShowForm]=useState(false);
  const [showArchived,setShowArchived]=useState(false);
  const [error,setError]=useState("");
  const [saving,setSaving]=useState(false);
  const [organizationId,setOrganizationId]=useState("");
  const [name,setName]=useState("");
  const [shortName,setShortName]=useState("");
  const [area,setArea]=useState("");
  const [areaCode,setAreaCode]=useState("");
  const [areaEdited,setAreaEdited]=useState(false);
  const [tagline,setTagline]=useState("");
  const [city,setCity]=useState(""); const [state,setState]=useState(""); const [pincode,setPincode]=useState("");
  const [phone,setPhone]=useState(""); const [email,setEmail]=useState(""); const [website,setWebsite]=useState("");
  const [address1,setAddress1]=useState(""); const [address2,setAddress2]=useState("");
  const [principal,setPrincipal]=useState(""); const [principalEmail,setPrincipalEmail]=useState(""); const [principalPhone,setPrincipalPhone]=useState("");
  const [adminDesignation,setAdminDesignation]=useState<"Principal"|"Headmaster"|"School Administrator">("Principal");
  const [adminUsername,setAdminUsername]=useState(""); const [adminPassword,setAdminPassword]=useState("");
  const [logoUrl,setLogoUrl]=useState("");
  const [udise,setUdise]=useState<UdiseDraft[]>([]);
  const [maxUsers,setMaxUsers]=useState(50);
  const canCreate=!!user&&(user.is_superuser||user.account_type==="ORGANIZATION_ADMIN");
  const canManageLifecycle=canCreate;

  const selectedOrg=useMemo(()=>organizations.find(o=>o.id===organizationId),[organizations,organizationId]);

  const load=async()=>{setLoading(true);try{
    const [ss,os]=await Promise.all([schoolApi.list(canManageLifecycle&&showArchived),canCreate?organizationApi.list():Promise.resolve([])]);
    setSchools(ss);setOrganizations(os);setOrganizationId(v=>v||os[0]?.id||"");
  }catch(e){setError(apiErrorMessage(e,"Failed to load Schools / Branches"));}finally{setLoading(false);}};
  useEffect(()=>{void load();},[canCreate,canManageLifecycle,showArchived]);

  const updateArea=(v:string)=>{setArea(v);if(!areaEdited)setAreaCode(suggestAreaCode(v));};
  const addUdise=()=>setUdise(rows=>[...rows,{udise_code:"",label:"",is_primary:rows.length===0}]);
  const updateUdise=(i:number,patch:Partial<UdiseDraft>)=>setUdise(rows=>rows.map((r,idx)=>idx===i?{...r,...patch}:patch.is_primary?{...r,is_primary:false}:r));
  const removeUdise=(i:number)=>setUdise(rows=>{const n=rows.filter((_,idx)=>idx!==i);if(n.length&&!n.some(x=>x.is_primary))n[0]={...n[0],is_primary:true};return n;});

  const handleCreate=async(e:FormEvent)=>{e.preventDefault();setSaving(true);setError("");try{
    await schoolApi.create({
      organization_id:organizationId,
      admin:{full_name:principal.trim(),designation:adminDesignation,username:adminUsername.trim(),email:principalEmail.trim()||null,phone:principalPhone.trim()||null,password:adminPassword},
      configuration:{name:name.trim(),short_name:shortName.trim()||undefined,area:area.trim(),area_code:areaCode.trim().toUpperCase()||undefined,tagline:tagline.trim()||undefined,logo_url:logoUrl.trim()||undefined,address_line1:address1.trim()||undefined,address_line2:address2.trim()||undefined,city:city.trim()||undefined,state:state.trim()||undefined,country:"India",pincode:pincode.trim()||undefined,phone:phone.trim()||undefined,email:email.trim()||undefined,website:website.trim()||undefined,principal_head_name:principal.trim()||undefined,principal_head_email:principalEmail.trim()||undefined,principal_head_phone:principalPhone.trim()||undefined},
      udise_codes:udise.filter(x=>x.udise_code.trim()).map(x=>({...x,udise_code:x.udise_code.trim()})),
      max_users:maxUsers,
      enabled_modules:["dashboard","school_admin","school_config","student","teacher","attendance","fee","marks","reports"],
    });
    setShowForm(false);setName("");setShortName("");setArea("");setAreaCode("");setAreaEdited(false);setTagline("");setCity("");setState("");setPincode("");setPhone("");setEmail("");setWebsite("");setAddress1("");setAddress2("");setPrincipal("");setPrincipalEmail("");setPrincipalPhone("");setAdminDesignation("Principal");setAdminUsername("");setAdminPassword("");setLogoUrl("");setUdise([]);await load();
  }catch(e){setError(apiErrorMessage(e,"Failed to create School / Branch"));}finally{setSaving(false);}};

  const restoreSchool=async(school:School)=>{setError("");try{await schoolApi.restore(school.id);await load();}catch(e){setError(apiErrorMessage(e,"Failed to restore School / Branch"));}};

  return <div className="space-y-6">
    <div className="flex items-center justify-between gap-4"><div><h1 className="text-2xl font-bold text-gray-900">Schools / Branches</h1><p className="text-gray-500 mt-1">Create the full School profile once. ERP code is generated automatically and remains permanent.</p>{next!=="detail"&&<p className="text-sm text-blue-700 mt-1">Select a School / Branch to open {next.replace(/-/g," ")}.</p>}</div><div className="flex items-center gap-3">{canManageLifecycle&&<label className="flex items-center gap-2 text-sm text-gray-600"><input type="checkbox" checked={showArchived} onChange={e=>setShowArchived(e.target.checked)}/>Show archived</label>}{canCreate&&<button className="btn-primary gap-2" onClick={()=>setShowForm(!showForm)}><Plus size={18}/>New School / Branch</button>}</div></div>
    {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}

    {showForm&&canCreate&&<div className="card"><h2 className="text-lg font-semibold">Create School / Branch</h2><p className="text-sm text-gray-500 mt-1 mb-5">School Configuration is merged here. UDISE is optional and multiple codes are supported.</p>
      <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label><span className="label">Organization *</span><select className="input" value={organizationId} onChange={e=>setOrganizationId(e.target.value)} required><option value="">Select organization</option>{organizations.map(o=><option key={o.id} value={o.id}>{o.name} ({o.code})</option>)}</select>{selectedOrg&&<span className="text-xs text-gray-500 mt-1 block">Allowed Schools: {selectedOrg.allowed_schools}</span>}</label>
        <Field label="School / Branch Name" value={name} onChange={setName}/>
        <Field label="Short Name" required={false} value={shortName} onChange={setShortName}/>
        <Field label="Area / Village" value={area} onChange={updateArea}/>
        <label><span className="label">Area Short Code *</span><input className="input uppercase" value={areaCode} onChange={e=>{setAreaEdited(true);setAreaCode(e.target.value.replace(/[^A-Za-z0-9]/g,"").slice(0,10).toUpperCase())}} minLength={2} required/><span className="text-xs text-gray-500 mt-1 block">Suggested automatically; editable before creation. Final ERP code will look like AK-{areaCode||"RZL"}-01.</span></label>
        <Field label="Tagline" required={false} value={tagline} onChange={setTagline}/>
        <Field label="Logo URL" required={false} value={logoUrl} onChange={setLogoUrl}/>
        <div className="md:col-span-2 border-t pt-4"><h3 className="font-semibold">Contact & Address</h3></div>
        <Field label="Address Line 1" required={false} value={address1} onChange={setAddress1}/><Field label="Address Line 2" required={false} value={address2} onChange={setAddress2}/>
        <Field label="City" required={false} value={city} onChange={setCity}/><Field label="State" required={false} value={state} onChange={setState}/><Field label="PIN Code" required={false} value={pincode} onChange={setPincode}/><Field label="School Phone" required={false} value={phone} onChange={setPhone}/><Field label="School Email" type="email" required={false} value={email} onChange={setEmail}/><Field label="Website" required={false} value={website} onChange={setWebsite}/>
        <div className="md:col-span-2 border-t pt-4"><h3 className="font-semibold">School / Branch Admin Profile</h3><p className="text-xs text-gray-500 mt-1">Create the responsible School Admin in the same transaction. The person will sign in with this account and must change the temporary password after first login.</p></div>
        <Field label="Admin Person Name" value={principal} onChange={setPrincipal}/><label><span className="label">Designation *</span><select className="input" value={adminDesignation} onChange={e=>setAdminDesignation(e.target.value as "Principal"|"Headmaster"|"School Administrator")}><option>Principal</option><option>Headmaster</option><option>School Administrator</option></select></label>
        <Field label="Admin Email" type="email" required={false} value={principalEmail} onChange={setPrincipalEmail}/><Field label="Admin Phone" required={false} value={principalPhone} onChange={setPrincipalPhone}/><Field label="Admin Username" value={adminUsername} onChange={setAdminUsername}/><label><span className="label">Temporary Password *</span><PasswordInput value={adminPassword} onChange={setAdminPassword} minLength={10} autoComplete="new-password"/></label>
        <div className="md:col-span-2 border-t pt-4"><div className="flex items-center justify-between"><div><h3 className="font-semibold">UDISE Codes (Optional)</h3><p className="text-xs text-gray-500">A School may have none, one or multiple UDISE codes.</p></div><button type="button" className="btn-secondary text-xs" onClick={addUdise}>+ Add UDISE</button></div><div className="mt-3 space-y-2">{udise.map((u,i)=><div key={i} className="grid grid-cols-[1fr_1fr_auto_auto] gap-2 items-center"><input className="input" placeholder="UDISE code" value={u.udise_code} onChange={e=>updateUdise(i,{udise_code:e.target.value})}/><input className="input" placeholder="Label (optional)" value={u.label} onChange={e=>updateUdise(i,{label:e.target.value})}/><label className="text-xs flex items-center gap-1"><input type="radio" name="primaryUdise" checked={u.is_primary} onChange={()=>updateUdise(i,{is_primary:true})}/>Primary</label><button type="button" className="p-2 text-gray-500" onClick={()=>removeUdise(i)}><X size={16}/></button></div>)}</div></div>
        <label><span className="label">Max Users</span><input className="input" type="number" min={1} max={10000} value={maxUsers} onChange={e=>setMaxUsers(Number(e.target.value))}/></label>
        <div className="md:col-span-2 flex gap-3"><button className="btn-primary" disabled={saving}>{saving?"Creating…":"Create School / Branch"}</button><button type="button" className="btn-secondary" onClick={()=>setShowForm(false)}>Cancel</button></div>
      </form>
    </div>}

    {loading?<div className="text-gray-500">Loading Schools…</div>:schools.length===0?<div className="card text-center py-12 text-gray-500"><SchoolIcon className="mx-auto mb-3 text-gray-300" size={40}/><p>No School / Branch units are assigned.</p></div>:<div className="grid gap-4">{schools.map(s=>{const archived=!!s.deleted_at;const content=<><div><h3 className="font-semibold text-gray-900">{s.configuration?.name||s.code}</h3><p className="text-sm text-gray-500 mt-0.5">ERP Code: <span className="font-mono">{s.code}</span>{s.configuration?.area&&` · ${s.configuration.area}`}</p>{s.udise_codes?.length?<p className="text-xs text-gray-500 mt-1">UDISE history: {s.udise_codes.map(x=>x.udise_code).join(", ")}</p>:<p className="text-xs text-gray-400 mt-1">UDISE: Not provided</p>}</div><span className={`text-xs font-medium px-2.5 py-1 rounded-full ${archived?"bg-slate-200 text-slate-700":s.is_active?"bg-green-100 text-green-800":"bg-amber-100 text-amber-800"}`}>{archived?"Archived":s.is_active?"Active":"Disabled"}</span></>;return archived?<div key={s.id} className="card flex items-start justify-between bg-gray-50 border-gray-300"><div className="flex-1">{content}<button className="btn-secondary text-xs mt-3 inline-flex gap-1.5" onClick={()=>void restoreSchool(s)}><RotateCcw size={14}/>Restore School</button></div></div>:<Link to={targetFor(s.id)} key={s.id} className="card flex items-start justify-between hover:border-primary-300 transition-colors">{content}</Link>})}</div>}
  </div>;
}
function Field({label,value,onChange,type="text",required=true}:{label:string;value:string;onChange:(v:string)=>void;type?:string;required?:boolean}){return <label><span className="label">{label}{required?" *":""}</span><input className="input" type={type} required={required} value={value} onChange={e=>onChange(e.target.value)}/></label>}
