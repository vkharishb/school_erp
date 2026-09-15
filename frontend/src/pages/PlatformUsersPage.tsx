import { useEffect, useMemo, useState } from "react";
import { userAdminApi } from "../services/api";
import type { User } from "../types";
import { apiErrorMessage } from "../utils/apiError";

const LABELS:Record<string,string>={SUPER_ADMIN:"Platform Owner",ORGANIZATION_ADMIN:"Organization Admin",SCHOOL_ADMIN:"School Admin",ACCOUNTS:"Accounts",TEACHER:"Teacher",RECEPTIONIST:"Receptionist",PARENT_STUDENT:"Parent / Student"};

export default function PlatformUsersPage(){
 const[users,setUsers]=useState<User[]>([]),[error,setError]=useState(""),[query,setQuery]=useState("");
 const load=async()=>{setError("");try{setUsers(await userAdminApi.list())}catch(e){setError(apiErrorMessage(e,"Failed to load platform users"))}};
 useEffect(()=>{void load()},[]);
 const filtered=useMemo(()=>{const q=query.trim().toLowerCase();if(!q)return users;return users.filter(u=>[u.full_name,u.username,u.email,u.phone,u.account_type].some(v=>String(v||"").toLowerCase().includes(q)))},[users,query]);
 return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-bold">Users</h1><p className="mt-1 text-gray-500">Platform-wide user directory. School user creation and maintenance remains inside the relevant School.</p></div><input className="input w-80" placeholder="Search name, username, email, phone or role…" value={query} onChange={e=>setQuery(e.target.value)}/></div>{error&&<div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}<section className="card overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left text-gray-500"><th className="py-2">User</th><th>Login</th><th>Account Type</th><th>Scope</th><th>Status</th></tr></thead><tbody>{filtered.map(u=><tr key={u.id} className="border-b last:border-0"><td className="py-3"><div className="font-medium">{u.full_name||"—"}</div><div className="text-xs text-gray-500">{u.email||u.phone||"—"}</div></td><td className="font-mono text-xs">{u.username}</td><td>{LABELS[u.account_type]||u.account_type}</td><td>{u.is_superuser?"Platform":u.school_id?"School":u.organization_id?"Society/Trust":"—"}</td><td><span className={u.is_active?"text-emerald-700":"text-rose-700"}>{u.is_active?"Active":"Disabled"}</span></td></tr>)}</tbody></table>{!filtered.length&&!error&&<div className="py-8 text-center text-gray-500">No users found.</div>}</section></div>;
}
