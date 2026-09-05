import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, setAccessToken } from "../services/api";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";

export default function AccountSecurityPage(){
  const navigate=useNavigate(); const logout=useAuthStore(s=>s.logout);
  const [currentPassword,setCurrentPassword]=useState(""),[newPassword,setNewPassword]=useState(""),[confirm,setConfirm]=useState(""),[error,setError]=useState("");
  const submit=async(e:FormEvent)=>{e.preventDefault();setError("");if(newPassword!==confirm){setError("New password confirmation does not match.");return;}try{await authApi.changePassword(currentPassword,newPassword);setAccessToken(null);await logout();navigate("/login",{replace:true});}catch(e){setError(apiErrorMessage(e,"Password change failed"));}};
  return <div className="max-w-2xl space-y-6"><div><h1 className="text-2xl font-bold">Account Security</h1><p className="text-gray-500 mt-1">Change your own password. All active sessions are revoked after a successful change.</p></div>{error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}<form className="card space-y-4" onSubmit={submit}><Field label="Current password" value={currentPassword} onChange={setCurrentPassword}/><Field label="New password" value={newPassword} onChange={setNewPassword}/><Field label="Confirm new password" value={confirm} onChange={setConfirm}/><p className="text-xs text-gray-500">Use 10–128 characters and at least three character classes: uppercase, lowercase, number and symbol. Common passwords are blocked.</p><button className="btn-primary">Change password & sign out</button></form></div>
}
function Field({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}){return <label><span className="label">{label}</span><input className="input" type="password" autoComplete="new-password" value={value} onChange={e=>onChange(e.target.value)} required/></label>}
