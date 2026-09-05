import { FormEvent, useEffect, useState } from "react";
import { Archive, Building2, KeyRound, Plus, RotateCcw, ShieldCheck } from "lucide-react";
import PasswordInput from "../components/PasswordInput";
import { organizationApi, userAdminApi } from "../services/api";
import type { Organization, User } from "../types";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";

const emptyForm = {
  name:"", allowed_schools:1, head_full_name:"", head_email:"", head_phone:"",
  admin_username:"", admin_email:"", admin_password:"", admin_designation:"Secretary and Correspondent" as "Secretary and Correspondent"|"Chairman",
};

export default function OrganizationsPage() {
  const user = useAuthStore(s=>s.user);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showArchived,setShowArchived]=useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice,setNotice]=useState("");
  const [form,setForm]=useState(emptyForm);
  const [editAdminTarget,setEditAdminTarget]=useState<User|null>(null); const [editAdminForm,setEditAdminForm]=useState({full_name:"",designation:"Secretary and Correspondent",email:"",phone:""}); const [editAdminSaving,setEditAdminSaving]=useState(false);
  const [resetTarget,setResetTarget]=useState<User|null>(null);
  const [resetPassword,setResetPassword]=useState("");
  const [resetConfirm,setResetConfirm]=useState("");
  const [resetSaving,setResetSaving]=useState(false);

  const load = async () => {
    setLoading(true);
    try { setOrganizations(await organizationApi.list(user?.is_superuser&&showArchived)); }
    catch (err) { setError(apiErrorMessage(err, "Failed to load organizations.")); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [showArchived,user?.is_superuser]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      await organizationApi.create({
        name:form.name.trim(), allowed_schools:form.allowed_schools,
        head_full_name:form.head_full_name.trim(), head_email:form.head_email.trim(),
        head_phone:form.head_phone.trim()||null, admin_username:form.admin_username.trim(),
        admin_email:form.admin_email.trim(), admin_password:form.admin_password, admin_designation:form.admin_designation,
      });
      setForm(emptyForm); setShowForm(false); setNotice("Organization and Organization Admin created. The admin can sign in with either username or email."); await load();
    } catch (err) { setError(apiErrorMessage(err, "Failed to create organization.")); }
    finally { setSaving(false); }
  };

  const toggleStatus = async (organization: Organization) => {
    setError(""); setNotice("");
    try { await organizationApi.setStatus(organization.id, !organization.is_active); setNotice(organization.is_active?"Organization disabled. Data remains preserved.":"Organization enabled."); await load(); }
    catch (err) { setError(apiErrorMessage(err, "Failed to update organization status.")); }
  };

  const archive = async (organization:Organization)=>{
    setError("");setNotice("");
    try{await organizationApi.archive(organization.id);setNotice("Organization archived. All historical data is preserved and operational access is blocked.");await load();}
    catch(err){setError(apiErrorMessage(err,"Failed to archive Organization."));}
  };
  const restore = async (organization:Organization)=>{
    setError("");setNotice("");
    try{await organizationApi.restore(organization.id);setNotice("Organization restored in Disabled state. Review it before enabling access.");await load();}
    catch(err){setError(apiErrorMessage(err,"Failed to restore Organization."));}
  };

  const openEditAdmin = async (organization:Organization)=>{
    setError("");setNotice("");
    try{
      const users=await userAdminApi.list({organization_id:organization.id});
      const admin=users.find(u=>u.account_type==="ORGANIZATION_ADMIN"&&!u.school_id);
      if(!admin){setError("Organization Admin account was not found for this Organization.");return;}
      setEditAdminTarget(admin);setEditAdminForm({full_name:admin.full_name,designation:admin.designation||"Secretary and Correspondent",email:admin.email||"",phone:admin.phone||""});
    }catch(err){setError(apiErrorMessage(err,"Failed to load Organization Admin profile."));}
  };
  const saveEditAdmin=async(e:FormEvent)=>{e.preventDefault();if(!editAdminTarget)return;setEditAdminSaving(true);setError("");try{await userAdminApi.update(editAdminTarget.id,{full_name:editAdminForm.full_name.trim(),designation:editAdminForm.designation,email:editAdminForm.email.trim()||null,phone:editAdminForm.phone.trim()||null});setNotice(`Profile updated for ${editAdminForm.full_name.trim()}.`);setEditAdminTarget(null);await load();}catch(err){setError(apiErrorMessage(err,"Failed to update Organization Admin profile."));}finally{setEditAdminSaving(false);}};

  const openReset = async (organization:Organization)=>{
    setError("");setNotice("");
    try{
      const users=await userAdminApi.list({organization_id:organization.id});
      const admin=users.find(u=>u.account_type==="ORGANIZATION_ADMIN"&&!u.school_id);
      if(!admin){setError("Organization Admin account was not found for this Organization.");return;}
      setResetTarget(admin);setResetPassword("");setResetConfirm("");
    }catch(err){setError(apiErrorMessage(err,"Failed to load Organization Admin account."));}
  };
  const resetOrgAdmin=async(e:FormEvent)=>{
    e.preventDefault();if(!resetTarget)return;
    if(resetPassword.length<10){setError("Temporary password must be at least 10 characters.");return;}
    if(resetPassword!==resetConfirm){setError("Password confirmation does not match.");return;}
    setResetSaving(true);setError("");
    try{await userAdminApi.resetPassword(resetTarget.id,resetPassword);setNotice(`Password reset for ${resetTarget.full_name}. The user must change it after login.`);setResetTarget(null);setResetPassword("");setResetConfirm("");}
    catch(err){setError(apiErrorMessage(err,"Failed to reset Organization Admin password."));}
    finally{setResetSaving(false);}
  };

  return <div className="space-y-6">
    <div className="flex items-center justify-between gap-4">
      <div><h1 className="text-2xl font-bold text-gray-900">Organizations</h1><p className="text-gray-500 mt-1">Organization identity, owner access, School capacity and non-destructive lifecycle controls.</p></div>
      <div className="flex items-center gap-3">
        {user?.is_superuser&&<label className="flex items-center gap-2 text-sm text-gray-600"><input type="checkbox" checked={showArchived} onChange={e=>setShowArchived(e.target.checked)}/>Show archived</label>}
        {user?.is_superuser&&<button className="btn-primary gap-2" onClick={()=>setShowForm(!showForm)}><Plus size={18}/>New Organization</button>}
      </div>
    </div>
    {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    {notice&&<div className="rounded-lg bg-green-50 border border-green-200 text-green-800 px-4 py-3 text-sm">{notice}</div>}

    {editAdminTarget&&<form className="card border-blue-200" onSubmit={saveEditAdmin}><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">Edit Organization Admin Profile</h2><p className="text-sm text-gray-500 mt-1"><span className="font-mono">{editAdminTarget.username}</span></p></div><button type="button" className="btn-secondary" onClick={()=>setEditAdminTarget(null)}>Cancel</button></div><div className="grid md:grid-cols-2 gap-4 mt-4"><Field label="Person Name" value={editAdminForm.full_name} onChange={v=>setEditAdminForm({...editAdminForm,full_name:v})}/><label><span className="label">Designation *</span><select className="input" value={editAdminForm.designation} onChange={e=>setEditAdminForm({...editAdminForm,designation:e.target.value})}><option>Secretary and Correspondent</option><option>Chairman</option></select></label><Field label="Email" required={false} type="email" value={editAdminForm.email} onChange={v=>setEditAdminForm({...editAdminForm,email:v})}/><Field label="Phone" required={false} value={editAdminForm.phone} onChange={v=>setEditAdminForm({...editAdminForm,phone:v})}/></div><button className="btn-primary mt-4" disabled={editAdminSaving}>{editAdminSaving?"Saving…":"Save Profile"}</button></form>}

    {resetTarget&&<form className="card border-amber-200" onSubmit={resetOrgAdmin}>
      <div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">Reset Organization Admin Password</h2><p className="text-sm text-gray-500 mt-1">{resetTarget.full_name} · <span className="font-mono">{resetTarget.username}</span>{resetTarget.email?<> · {resetTarget.email}</>:null}</p></div><button type="button" className="btn-secondary" onClick={()=>setResetTarget(null)}>Cancel</button></div>
      <div className="grid md:grid-cols-2 gap-4 mt-4"><label><span className="label">Temporary Password</span><PasswordInput value={resetPassword} onChange={setResetPassword} minLength={10}/></label><label><span className="label">Confirm Password</span><PasswordInput value={resetConfirm} onChange={setResetConfirm} minLength={10}/></label></div>
      <p className="text-xs text-gray-500 mt-3">Reset revokes active sessions and requires a password change on the next login.</p>
      <button className="btn-primary mt-4" disabled={resetSaving}>{resetSaving?"Resetting…":"Reset Password"}</button>
    </form>}

    {showForm&&user?.is_superuser&&<div className="card">
      <div className="flex items-start gap-3 mb-5"><ShieldCheck className="text-primary-700"/><div><h2 className="text-lg font-semibold">Create Organization + Organization Admin</h2><p className="text-sm text-gray-500">ERP code is generated automatically. Organization Admin can sign in with either the username or login email; both are case-insensitive.</p></div></div>
      <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Organization Name" value={form.name} onChange={v=>setForm({...form,name:v})}/>
        <label><span className="label">No. of Schools Allowed</span><input className="input" type="number" min={1} max={999} value={form.allowed_schools} onChange={e=>setForm({...form,allowed_schools:Number(e.target.value)})} required/></label>
        <div className="md:col-span-2 border-t pt-4"><h3 className="font-semibold">Organization Admin Profile</h3><p className="text-xs text-gray-500 mt-1">This person will use the Organization Admin login.</p></div>
        <Field label="Admin Person Name" value={form.head_full_name} onChange={v=>setForm({...form,head_full_name:v})}/>
        <label><span className="label">Designation *</span><select className="input" value={form.admin_designation} onChange={e=>setForm({...form,admin_designation:e.target.value as "Secretary and Correspondent"|"Chairman"})}><option>Secretary and Correspondent</option><option>Chairman</option></select></label>
        <Field label="Admin Phone" required={false} value={form.head_phone} onChange={v=>setForm({...form,head_phone:v})}/>
        <Field label="Admin Contact Email" type="email" value={form.head_email} onChange={v=>setForm({...form,head_email:v})}/>
        <div className="md:col-span-2 border-t pt-4"><h3 className="font-semibold">Organization Admin Login</h3><p className="text-xs text-gray-500 mt-1">The account is created in the same confirmed transaction. Username and login email are both valid login IDs.</p></div>
        <Field label="Username" value={form.admin_username} onChange={v=>setForm({...form,admin_username:v})}/>
        <Field label="Login Email" type="email" value={form.admin_email} onChange={v=>setForm({...form,admin_email:v})}/>
        <label><span className="label">Temporary Password</span><PasswordInput value={form.admin_password} onChange={v=>setForm({...form,admin_password:v})} minLength={10} autoComplete="new-password"/></label>
        <div className="md:col-span-2 flex gap-3"><button className="btn-primary" disabled={saving}>{saving?"Creating…":"Create Organization"}</button><button type="button" className="btn-secondary" onClick={()=>setShowForm(false)}>Cancel</button></div>
      </form>
    </div>}

    {loading?<div className="text-gray-500">Loading organizations…</div>:organizations.length===0?<div className="card text-center py-12 text-gray-500"><Building2 className="mx-auto mb-3 text-gray-300" size={40}/><p>No Organizations found.</p></div>:<div className="grid gap-4 md:grid-cols-2">
      {organizations.map(org=>{const archived=!!org.archived_at;const status=archived?"Archived":org.is_active?"Active":"Disabled";return <div key={org.id} className={`card ${archived?"bg-gray-50 border-gray-300":""}`}>
        <div className="flex items-start justify-between gap-4"><div><h2 className="font-semibold text-gray-900">{org.name}</h2><p className="text-sm text-gray-500 mt-1 font-mono">{org.code}</p><p className="text-sm text-gray-600 mt-3">Admin: {org.admin_full_name||org.head_full_name||"—"}{org.admin_designation?` · ${org.admin_designation}`:""}</p><p className="text-xs text-gray-500">{org.head_email||""}</p>{(user?.is_superuser||user?.account_type==="ORGANIZATION_ADMIN")&&<div className="mt-3 rounded-lg bg-gray-50 border px-3 py-2"><p className="text-xs font-medium text-gray-700">Organization Admin Login</p><p className="text-xs text-gray-600 mt-1">Username: <span className="font-mono">{org.admin_username||"—"}</span></p><p className="text-xs text-gray-600">Email: <span className="font-mono">{org.admin_email||"—"}</span></p><p className="text-[11px] text-gray-500 mt-1">Either value can be used to sign in.</p></div>}<p className="text-xs text-gray-500 mt-2">Schools allowed: <strong>{org.allowed_schools}</strong></p>{archived&&<p className="text-xs text-gray-500 mt-2">Archived: {new Date(org.archived_at!).toLocaleString()}</p>}</div><span className={`inline-block text-xs font-medium px-2.5 py-1 rounded-full ${archived?"bg-slate-200 text-slate-700":org.is_active?"bg-green-100 text-green-800":"bg-amber-100 text-amber-800"}`}>{status}</span></div>
        {user?.is_superuser&&<div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
          {!archived&&<button className="btn-secondary text-xs" onClick={()=>void toggleStatus(org)}>{org.is_active?"Disable":"Enable"}</button>}
          {!archived&&<button className="btn-secondary text-xs" onClick={()=>void openEditAdmin(org)}>Edit Admin Profile</button>}{!archived&&<button className="btn-secondary text-xs inline-flex gap-1.5" onClick={()=>void openReset(org)}><KeyRound size={14}/>Reset Org Admin</button>}
          {!archived&&!org.is_active&&<button className="btn-secondary text-xs text-red-700 inline-flex gap-1.5" onClick={()=>void archive(org)}><Archive size={14}/>Archive</button>}
          {archived&&<button className="btn-secondary text-xs inline-flex gap-1.5" onClick={()=>void restore(org)}><RotateCcw size={14}/>Restore</button>}
        </div>}
      </div>})}
    </div>}
  </div>;
}

function Field({label,value,onChange,type="text",required=true}:{label:string;value:string;onChange:(v:string)=>void;type?:string;required?:boolean}){return <label><span className="label">{label}{required?" *":""}</span><input className="input" type={type} required={required} value={value} onChange={e=>onChange(e.target.value)}/></label>}
