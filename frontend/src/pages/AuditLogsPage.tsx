import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { auditApi, type AuditEventRow } from "../services/api";
import { apiErrorMessage } from "../utils/apiError";

const ACCOUNT_TYPE_LABEL: Record<string,string> = {
  SUPER_ADMIN: "Platform Super Admin",
  ORGANIZATION_ADMIN: "Organization Admin",
  SCHOOL_ADMIN: "School Admin",
  ACCOUNTS: "Accounts",
  TEACHER: "Teacher",
  RECEPTIONIST: "Receptionist",
  PARENT_STUDENT: "Parent / Student",
};

export default function AuditLogsPage(){
  const{schoolId=""}=useParams();
  const[items,setItems]=useState<AuditEventRow[]>([]),[error,setError]=useState("");
  useEffect(()=>{
    setError("");
    if(schoolId)auditApi.list(schoolId).then(setItems).catch(e=>setError(apiErrorMessage(e,"Failed to load audit logs")));
  },[schoolId]);
  return <div className="space-y-6"><div><h1 className="text-2xl font-bold">Audit Logs</h1><p className="text-gray-500 mt-1">Read-only security and change history. Platform, Organization and School Admin users can view logs within their permitted scope.</p></div>{error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}<section className="card overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b text-left"><th className="py-2">Time</th><th>Action</th><th>Module</th><th>Entity</th><th>User</th></tr></thead><tbody>{items.map(x=><tr className="border-b last:border-0" key={x.id}><td className="py-3 whitespace-nowrap">{new Date(x.created_at).toLocaleString()}</td><td>{x.action}</td><td>{x.module||"—"}</td><td>{x.entity_type||"—"}{x.entity_id?` · ${x.entity_id}`:""}</td><td>{x.user_name?<><div className="font-medium text-gray-900">{x.user_name}</div><div className="text-gray-500">{[x.username,x.user_account_type?ACCOUNT_TYPE_LABEL[x.user_account_type]||x.user_account_type:null].filter(Boolean).join(" · ")}</div></>:x.user_id?<span className="text-gray-500">Unknown user</span>:"System"}</td></tr>)}</tbody></table>{items.length===0&&!error&&<div className="py-8 text-center text-gray-500">No audit events found.</div>}</section></div>;
}
