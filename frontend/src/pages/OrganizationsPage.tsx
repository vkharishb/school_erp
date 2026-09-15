import { FormEvent, useEffect, useMemo, useState } from "react";
import { KeyRound, Plus, Search, ShieldCheck } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { organizationApi, schoolApi, subscriptionApi, userAdminApi } from "../services/api";
import type {
  Organization,
  OrganizationSubscription,
  School,
  SubscriptionPlan,
  User,
} from "../types";
import { useAuthStore } from "../store/authStore";
import { apiErrorMessage } from "../utils/apiError";
import {
  EMAIL_ERROR,
  MOBILE_ERROR,
  isValidEmail,
  isValidIndianMobile,
  normalizeIndianMobile,
} from "../utils/contactValidation";

const ORG_ADMIN_DESIGNATIONS=["Chairman","Secretary & Correspondent","Treasurer","Director","Managing Director","Administrator","Authorized Representative"] as const;
const emptyForm={name:"",allowed_schools:1,head_full_name:"",head_email:"",head_phone:"",admin_username:"",admin_designation:"",subscription_plan_id:"",billing_cycle:"yearly",customized_total_amount:"",discount_type:"none",discount_value:"0",discount_reason:"",tax_mode:"non_gst",tax_rate:"0",activation_minimum_amount:"",activation_override_reason:"",payment_due_at:"",subscription_notes:""};

type CommercialCalculation={
  schools:number;
  gross:number;
  discount:number;
  taxable:number;
  gstRate:number;
  gst:number;
  netPayable:number;
  calculatedMinimum:number;
  activationMinimum:number;
  balanceAfterMinimum:number;
};

type CommercialAgreementSnapshot={
  form:typeof emptyForm;
  plan:SubscriptionPlan;
  planCode:string;
  commercial:CommercialCalculation;
};

export default function OrganizationsPage(){
 const location=useLocation();
 const navigate=useNavigate();
 const user=useAuthStore(s=>s.user); const [organizations,setOrganizations]=useState<Organization[]>([]); const [plans,setPlans]=useState<SubscriptionPlan[]>([]); const [subscriptionAccounts,setSubscriptionAccounts]=useState<OrganizationSubscription[]>([]); const [schools,setSchools]=useState<School[]>([]); const [loading,setLoading]=useState(true); const [showForm,setShowForm]=useState(false); const [form,setForm]=useState(emptyForm); const [query,setQuery]=useState(""); const [selected,setSelected]=useState<Organization|null>(null); const [error,setError]=useState(""); const [notice,setNotice]=useState(""); const [saving,setSaving]=useState(false); const [credential,setCredential]=useState<{password:string;username:string;email?:string|null}|null>(null); const [showCommercialConfirm,setShowCommercialConfirm]=useState(false); const [commercialSnapshot,setCommercialSnapshot]=useState<CommercialAgreementSnapshot|null>(null); const [reason,setReason]=useState(""); const [emergencyOverride,setEmergencyOverride]=useState(false); const [statusTarget,setStatusTarget]=useState<Organization|null>(null); const [editOrganization,setEditOrganization]=useState<Organization|null>(null); const [editAdmin,setEditAdmin]=useState<User|null>(null); const [adminForm,setAdminForm]=useState({full_name:"",designation:"",email:"",phone:""});
 const load=async()=>{setLoading(true);try{const [orgRows,schoolRows]=await Promise.all([organizationApi.list(true),schoolApi.list(true)]);setOrganizations(orgRows);setSchools(schoolRows);}catch(e){setError(apiErrorMessage(e,"Failed to load Society/Trust records."));}finally{setLoading(false)}};
 useEffect(()=>{
   void load();
   if(user?.is_superuser){
     Promise.all([subscriptionApi.plans(),subscriptionApi.accounts()])
       .then(([planRows,accountRows])=>{
         setPlans(planRows.filter(p=>p.is_active));
         setSubscriptionAccounts(accountRows);
       })
       .catch(()=>{
         setPlans([]);
         setSubscriptionAccounts([]);
       });
   }
 },[user?.is_superuser]);
 useEffect(()=>{
   const view=new URLSearchParams(location.search).get("view");

   if(view==="create"){
     setShowForm(true);
     setSelected(null);
     setEditOrganization(null);
     setEditAdmin(null);
     setStatusTarget(null);
     setShowCommercialConfirm(false);
     setCommercialSnapshot(null);
     setReason("");
     setError("");
     setNotice("");
     return;
   }

   if(view==="list" || !view){
     setShowForm(false);
     setSelected(null);
     setEditOrganization(null);
     setEditAdmin(null);
     setStatusTarget(null);
     setShowCommercialConfirm(false);
     setCommercialSnapshot(null);
     setReason("");
     setError("");
     setNotice("");
   }
 },[location.search]);
 const selectedPlan=useMemo(()=>plans.find(p=>p.id===form.subscription_plan_id)||null,[plans,form.subscription_plan_id]);
 const planCode=(selectedPlan?.code||"").toUpperCase();
 const isTrial=planCode==="TRIAL";
 const isCustomized=planCode==="CUSTOMIZED";
 const isPayg=planCode==="PAYG";

 const commercial=useMemo(()=>{
   if(!selectedPlan)return null;

   const schools=Math.max(Number(form.allowed_schools)||1,1);
   const money=(n:number)=>Math.round((Number.isFinite(n)?n:0)*100)/100;

   let gross=0;
   if(!isTrial){
     if(isCustomized){
       gross=money(Number(form.customized_total_amount)||0);
     }else{
       const unitPrice=Number(form.billing_cycle==="monthly"?selectedPlan.monthly_price:selectedPlan.yearly_price)||0;
       gross=isPayg
         ? money(unitPrice*Math.max(Number(selectedPlan.minimum_students)||1,1)*schools)
         : money(unitPrice*schools);
     }
   }

   const discountValue=Number(form.discount_value)||0;
   let discount=0;
   if(!isTrial&&form.discount_type==="percent")discount=money(gross*discountValue/100);
   else if(!isTrial&&form.discount_type==="fixed")discount=money(discountValue);

   const taxable=money(Math.max(gross-discount,0));
   const gstRate=!isTrial&&form.tax_mode==="gst"?(Number(form.tax_rate)||0):0;
   const gst=money(taxable*gstRate/100);
   const netPayable=money(taxable+gst);

   const calculatedMinimum=isTrial?0:money(netPayable*0.50);
   const override=form.activation_minimum_amount!==""?Number(form.activation_minimum_amount):null;
   const activationMinimum=isTrial?0:money(override===null?calculatedMinimum:override);
   const balanceAfterMinimum=money(Math.max(netPayable-activationMinimum,0));

   return {
     schools,
     gross,
     discount,
     taxable,
     gstRate,
     gst,
     netPayable,
     calculatedMinimum,
     activationMinimum,
     balanceAfterMinimum
   };
 },[selectedPlan,isTrial,isCustomized,isPayg,form.allowed_schools,form.customized_total_amount,form.billing_cycle,form.discount_type,form.discount_value,form.tax_mode,form.tax_rate,form.activation_minimum_amount]);

 const subscriptionByOrganization=useMemo(()=>{
   const map=new Map<string,OrganizationSubscription>();
   for(const account of subscriptionAccounts){
     const existing=map.get(account.organization_id);
     if(!existing || new Date(account.created_at).getTime()>new Date(existing.created_at).getTime()){
       map.set(account.organization_id,account);
     }
   }
   return map;
 },[subscriptionAccounts]);

 const displayPhone=(value?:string|null)=>{
   if(!value)return "—";
   const digits=value.replace(/\D/g,"");
   if(digits.length===12 && digits.startsWith("91"))return digits.slice(2);
   return digits;
 };

 const activeSchoolCountByOrganization=useMemo(()=>{
   const counts=new Map<string,number>();
   for(const school of schools){
     const organizationId=school.organization_id;
     if(!school.is_active || !organizationId)continue;
     counts.set(organizationId,(counts.get(organizationId)||0)+1);
   }
   return counts;
 },[schools]);

 const filtered=useMemo(()=>{
   const q=query.toLowerCase().trim();
   if(!q)return organizations;
   return organizations.filter(o=>{
     const planName=subscriptionByOrganization.get(o.id)?.plan_name;
     return [o.name,o.code,o.admin_full_name,o.head_full_name,o.admin_email,o.head_email,o.admin_phone,o.head_phone,planName]
       .some(v=>String(v||"").toLowerCase().includes(q));
   });
 },[organizations,query,subscriptionByOrganization]);
 const selectPlan=(planId:string)=>{
   const p=plans.find(x=>x.id===planId);
   const code=(p?.code||"").toUpperCase();

   if(code==="TRIAL"){
     setForm({
       ...form,
       subscription_plan_id:planId,
       allowed_schools:1,
       billing_cycle:"trial",
       customized_total_amount:"",
       discount_type:"none",
       discount_value:"0",
       discount_reason:"",
       tax_mode:"non_gst",
       tax_rate:"0",
       activation_minimum_amount:"",
       activation_override_reason:"",
       payment_due_at:""
     });
     return;
   }

   const flexible=code==="CUSTOMIZED"||code==="PAYG";
   setForm({
     ...form,
     subscription_plan_id:planId,
     billing_cycle:flexible?"monthly":"yearly",
     customized_total_amount:"",
     discount_type:"none",
     discount_value:"0",
     discount_reason:"",
     tax_mode:"non_gst",
     tax_rate:"0",
     activation_minimum_amount:"",
     activation_override_reason:"",
     payment_due_at:""
   });
 };

 const validateCommercialAgreement=()=>{
   setError("");

   if(!selectedPlan){
     setError("Please select a subscription plan.");
     return false;
   }
   if(!isValidEmail(form.head_email)){
     setError(EMAIL_ERROR);
     return false;
   }
   if(!isValidIndianMobile(form.head_phone)){
     setError(MOBILE_ERROR);
     return false;
   }
   if(!form.admin_designation){
     setError("Please select an Organization Admin designation.");
     return false;
   }
   if(form.allowed_schools<1){
     setError("Number of Schools must be at least 1.");
     return false;
   }

   if(isTrial){
     return true;
   }

   if(isCustomized && (!form.customized_total_amount || Number(form.customized_total_amount)<=0)){
     setError("Customized Total Amount must be greater than zero.");
     return false;
   }

   if(form.discount_type==="percent" && Number(form.discount_value)>100){
     setError("Percentage discount cannot exceed 100.");
     return false;
   }

   if(commercial && commercial.discount>commercial.gross){
     setError("Discount cannot exceed the plan amount.");
     return false;
   }

   if(form.discount_type!=="none" && !form.discount_reason.trim()){
     setError("Discount Reason is required when a discount is applied.");
     return false;
   }

   if(form.tax_mode==="gst"){
     const rate=Number(form.tax_rate);
     if(form.tax_rate==="" || !Number.isFinite(rate) || rate<0 || rate>100){
       setError("Please enter a valid GST Rate between 0 and 100.");
       return false;
     }
   }

   if(!form.payment_due_at){
     setError("Payment Due Date is required for paid plans.");
     return false;
   }

   if(form.activation_minimum_amount){
     if(commercial && Number(form.activation_minimum_amount)<commercial.calculatedMinimum && !form.activation_override_reason.trim()){
       setError("Reason is required when Minimum Activation Payment is below the calculated minimum.");
       return false;
     }
     if(commercial && Number(form.activation_minimum_amount)>commercial.netPayable){
       setError("Minimum Activation Payment cannot exceed Net Payable.");
       return false;
     }
   }

   return true;
 };

 const create=async(e:FormEvent)=>{
   e.preventDefault();
   if(saving)return;
   if(!validateCommercialAgreement())return;
   if(!selectedPlan||!commercial)return;

   setCommercialSnapshot({
     form:{...form},
     plan:selectedPlan,
     planCode,
     commercial:{...commercial}
   });

   setShowCommercialConfirm(true);
 };

 const confirmCreate=async()=>{
   if(saving || !commercialSnapshot)return;

   const snapshot=commercialSnapshot;
   const agreedForm=snapshot.form;
   const agreedPlanCode=snapshot.planCode;
   const agreedIsTrial=agreedPlanCode==="TRIAL";
   const agreedIsCustomized=agreedPlanCode==="CUSTOMIZED";

   setSaving(true);
   setError("");

   try{
     const payload={
       ...agreedForm,
       name:agreedForm.name.trim(),
       head_full_name:agreedForm.head_full_name.trim(),
       head_email:agreedForm.head_email.trim(),
       head_phone:normalizeIndianMobile(agreedForm.head_phone),
       admin_email:agreedForm.head_email.trim(),

       billing_cycle:agreedIsTrial?"trial":agreedForm.billing_cycle,
       customized_total_amount:agreedIsCustomized?agreedForm.customized_total_amount:null,

       discount_type:agreedIsTrial?"none":agreedForm.discount_type,
       discount_value:agreedIsTrial?"0":agreedForm.discount_value,
       discount_reason:agreedIsTrial?null:(agreedForm.discount_reason.trim()||null),

       tax_mode:agreedIsTrial?"non_gst":agreedForm.tax_mode,
       tax_rate:agreedIsTrial?"0":(agreedForm.tax_mode==="gst"?agreedForm.tax_rate:"0"),

       activation_minimum_amount:agreedIsTrial?null:(agreedForm.activation_minimum_amount||null),
       activation_override_reason:agreedIsTrial?null:(agreedForm.activation_override_reason.trim()||null),

       payment_due_at:agreedIsTrial?null:new Date(agreedForm.payment_due_at).toISOString(),
       subscription_notes:agreedForm.subscription_notes.trim()||null
     };

     const org=await organizationApi.create(payload);

     setCredential({
       password:org.temporary_password||"",
       username:org.admin_username||agreedForm.admin_username,
       email:org.admin_email||agreedForm.head_email
     });

     setNotice(
       org.email_delivery_status==="sent"
         ?"Society/Trust and Organization Admin created; account email sent."
         :"Society/Trust and Organization Admin created. Email was not delivered; use Resend Email or communicate credentials separately."
     );

     setShowCommercialConfirm(false);
     setCommercialSnapshot(null);
     setForm(emptyForm);
     setShowForm(false);
     await load();
   }catch(e){
     setError(apiErrorMessage(e,"Failed to create Society/Trust."));
   }finally{
     setSaving(false);
   }
 };
 const openEditOrganization=async(o:Organization)=>{
   setError(""); setSelected(o); setEditOrganization(o);
   const phone=displayPhone(o.admin_phone||o.head_phone);
   setForm({...emptyForm,name:o.name,allowed_schools:o.allowed_schools,head_full_name:o.admin_full_name||o.head_full_name||"",head_email:o.admin_email||o.head_email||"",head_phone:phone==="—"?"":phone,admin_username:o.admin_username||"",admin_designation:o.admin_designation||""});
   setShowForm(false);
   try{
     const users=await userAdminApi.list({organization_id:o.id});
     const admin=users.find(x=>x.account_type==="ORGANIZATION_ADMIN"&&!x.school_id)||null;
     setEditAdmin(null);
     if(admin)setAdminForm({full_name:admin.full_name,designation:admin.designation||"",email:admin.email||"",phone:(admin.phone||"").replace(/^\+91/,"")});
   }catch(e){setError(apiErrorMessage(e,"Organization Admin could not be loaded."));}
   navigate("/organizations?view=edit");
 };
 const saveOrganizationDetails=async(e:FormEvent)=>{
   e.preventDefault(); if(!editOrganization||saving)return; setError("");
   if(!form.name.trim()){setError("Society/Trust Name is required.");return;}
   if(!isValidEmail(form.head_email)){setError(EMAIL_ERROR);return;}
   if(!isValidIndianMobile(form.head_phone)){setError(MOBILE_ERROR);return;}
   if(!form.admin_designation){setError("Please select an Organization Admin designation.");return;}
   setSaving(true);
   try{
     await organizationApi.update(editOrganization.id,{name:form.name.trim(),head_full_name:form.head_full_name.trim(),head_email:form.head_email.trim(),head_phone:normalizeIndianMobile(form.head_phone)});
     if(editAdmin)await userAdminApi.update(editAdmin.id,{full_name:form.head_full_name.trim(),designation:form.admin_designation,email:form.head_email.trim(),phone:normalizeIndianMobile(form.head_phone)});
     setNotice("Society/Trust details updated."); setEditOrganization(null); setEditAdmin(null); setForm(emptyForm); await load(); navigate("/organizations?view=list");
   }catch(e){setError(apiErrorMessage(e,"Failed to update Society/Trust details."));}
   finally{setSaving(false);}
 };
 const openAdmin=async(o:Organization)=>{try{setEditOrganization(null);const users=await userAdminApi.list({organization_id:o.id});const a=users.find(x=>x.account_type==="ORGANIZATION_ADMIN"&&!x.school_id);if(!a)throw new Error("Admin not found");setEditAdmin(a);setAdminForm({full_name:a.full_name,designation:a.designation||"",email:a.email||"",phone:(a.phone||"").replace(/^\+91/,"")});navigate("/organizations?view=edit-admin");}catch(e){setError(apiErrorMessage(e,"Organization Admin not found."));}};
 const saveAdmin=async(e:FormEvent)=>{
   e.preventDefault();
   if(!editAdmin)return;

   setError("");

   if(!isValidEmail(adminForm.email)){
     setError(EMAIL_ERROR);
     return;
   }

   if(!isValidIndianMobile(adminForm.phone)){
     setError(MOBILE_ERROR);
     return;
   }

   try{
     await userAdminApi.update(editAdmin.id,{
       ...adminForm,
       email:adminForm.email.trim(),
       phone:normalizeIndianMobile(adminForm.phone)
     });
     setEditAdmin(null);
     setNotice("Organization Admin profile updated.");
     navigate("/organizations?view=detail");
     await load();
   }catch(e){
     setError(apiErrorMessage(e,"Failed to update Admin profile."));
   }
 };
 const resetTemp=async(o:Organization)=>{try{const r=await organizationApi.resetAdminTemporaryPassword(o.id);setCredential({password:r.temporary_password,username:r.username,email:r.email});setNotice("New temporary password generated. It is shown once and the Admin must change it after login.");}catch(e){setError(apiErrorMessage(e,"Failed to reset temporary password."));}};
 const resend=async(o:Organization)=>{try{await organizationApi.resendAdminEmail(o.id);setNotice("Account information email resent.");}catch(e){setError(apiErrorMessage(e,"Email could not be resent."));}};
 const status=async(o:Organization)=>{if(!reason.trim()){setError("Reason is required for Disable / Enable.");return;}try{await organizationApi.setStatus(o.id,!o.is_active,reason.trim(),o.is_active&&emergencyOverride);setReason("");setEmergencyOverride(false);setStatusTarget(null);setNotice(`Society/Trust ${o.is_active?"disabled":"enabled"}.`);await load();setSelected(prev=>prev?.id===o.id?{...prev,is_active:!o.is_active}:prev);}catch(e){setError(apiErrorMessage(e,"Status change is not allowed."));}};
 return <div className="space-y-6">
  <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold">Society / Trust</h1><p className="text-gray-500 mt-1">Society/Trust identity, Organization Admin, school capacity and commercial lifecycle.</p></div>{user?.is_superuser&&<button className="btn-primary gap-2" onClick={()=>{setShowForm(true);setSelected(null);setEditAdmin(null);navigate("/organizations?view=create");}}><Plus size={18}/>Add Society/Trust</button>}</div>
  {error&&<div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}{notice&&<div className="rounded-lg bg-green-50 border border-green-200 text-green-800 px-4 py-3 text-sm">{notice}</div>}
  {credential&&<div className="card border-amber-300"><h2 className="font-semibold">One-time Organization Admin Credentials</h2><p className="text-sm mt-2">Login: <b>{credential.email||credential.username}</b></p><p className="text-sm">Username: <b>{credential.username}</b></p><p className="text-sm">Temporary Password: <code className="font-mono font-bold">{credential.password}</code></p><p className="text-xs text-amber-700 mt-2">Copy this now. The plaintext password is not retrievable after this panel is closed.</p><button className="btn-secondary mt-3" onClick={()=>setCredential(null)}>Close</button></div>}
  {showForm&&<form onSubmit={create} className="card grid md:grid-cols-2 gap-4">
    <div className="md:col-span-2 flex gap-2">
      <ShieldCheck/>
      <h2 className="font-semibold">Create Society/Trust + Organization Admin</h2>
    </div>

    <Field label="Society/Trust Name" value={form.name} onChange={v=>setForm({...form,name:v})}/>
    <label>
      <span className="label">Number of Schools <RedStar/></span>
      <input className="input" type="number" min={1} value={String(isTrial?1:form.allowed_schools)} disabled={isTrial} onChange={e=>setForm({...form,allowed_schools:Number(e.target.value)})}/>
      {isTrial&&<p className="text-xs text-gray-500 mt-1">Trial plan is limited to 1 School.</p>}
    </label>

    <Field label="Admin Person Name" value={form.head_full_name} onChange={v=>setForm({...form,head_full_name:v})}/>
    <SelectField label="Designation" value={form.admin_designation} options={ORG_ADMIN_DESIGNATIONS} onChange={v=>setForm({...form,admin_designation:v})}/>

    <Field label="Admin Contact / Login Email" type="email" value={form.head_email} onChange={v=>setForm({...form,head_email:v})}/>
    <Field label="Admin Phone" value={form.head_phone} onChange={v=>setForm({...form,head_phone:v.replace(/\D/g,"").slice(0,10)})}/>
    <Field label="Username" value={form.admin_username} onChange={v=>setForm({...form,admin_username:v})}/>

    <label>
      <span className="label">Plan <RedStar/></span>
      <select required className="input" value={form.subscription_plan_id} onChange={e=>selectPlan(e.target.value)}>
        <option value="">Select Plan</option>
        {plans.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>

    <label>
      <span className="label">Billing Cycle <RedStar/></span>
      <select
        required
        className="input"
        value={form.billing_cycle}
        disabled={isTrial || (planCode!=="" && !isCustomized && !isPayg)}
        onChange={e=>setForm({...form,billing_cycle:e.target.value})}
      >
        {isTrial
          ? <option value="trial">Trial</option>
          : <>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </>
        }
      </select>
      {planCode!==""&&!isTrial&&!isCustomized&&!isPayg&&
        <p className="text-xs text-gray-500 mt-1">This plan uses Yearly billing.</p>
      }
    </label>

    {isCustomized&&
      <Field
        label="Customized Total Amount"
        type="number"
        value={form.customized_total_amount}
        onChange={v=>setForm({...form,customized_total_amount:v})}
      />
    }

    <label>
      <span className="label">Discount Type <RedStar/></span>
      <select
        required
        className="input"
        disabled={isTrial}
        value={isTrial?"none":form.discount_type}
        onChange={e=>setForm({...form,discount_type:e.target.value,discount_value:e.target.value==="none"?"0":form.discount_value,discount_reason:e.target.value==="none"?"":form.discount_reason})}
      >
        <option value="none">No Discount</option>
        <option value="fixed">Fixed Amount</option>
        <option value="percent">Percentage</option>
      </select>
    </label>

    {!isTrial&&form.discount_type!=="none"&&<>
      <Field
        label={form.discount_type==="percent"?"Discount Percentage":"Discount Amount"}
        type="number"
        value={form.discount_value}
        onChange={v=>setForm({...form,discount_value:v})}
      />
      <Field label="Discount Reason" value={form.discount_reason} onChange={v=>setForm({...form,discount_reason:v})}/>
    </>}

    <label>
      <span className="label">Tax Type <RedStar/></span>
      <select
        required
        className="input"
        disabled={isTrial}
        value={isTrial?"non_gst":form.tax_mode}
        onChange={e=>setForm({...form,tax_mode:e.target.value,tax_rate:e.target.value==="gst"?form.tax_rate:"0"})}
      >
        <option value="non_gst">Non-GST</option>
        <option value="gst">GST</option>
      </select>
    </label>

    {!isTrial&&form.tax_mode==="gst"&&
      <Field
        label="GST Rate (%)"
        type="number"
        value={form.tax_rate}
        onChange={v=>setForm({...form,tax_rate:v})}
      />
    }

    {!isTrial&&<>
      <label>
        <span className="label">Minimum Activation Payment</span>
        <input
          className="input"
          type="number"
          placeholder={commercial?String(commercial.calculatedMinimum):""}
          value={form.activation_minimum_amount}
          onChange={e=>setForm({...form,activation_minimum_amount:e.target.value})}
        />
        <p className="text-xs text-gray-500 mt-1">
          Default: 50% of Net Payable{commercial?` (${formatINR(commercial.calculatedMinimum)})`:""}.
          A reason is required only when the entered amount is below the calculated minimum.
        </p>
      </label>

      {form.activation_minimum_amount&&commercial&&Number(form.activation_minimum_amount)<commercial.calculatedMinimum&&
        <Field
          label="Activation Override Reason"
          value={form.activation_override_reason}
          onChange={v=>setForm({...form,activation_override_reason:v})}
        />
      }

      <Field
        label="Payment Due Date"
        type="date"
        value={form.payment_due_at}
        onChange={v=>setForm({...form,payment_due_at:v})}
      />
    </>}

    <Field
      label="Agreed Terms / Notes"
      required={false}
      value={form.subscription_notes}
      onChange={v=>setForm({...form,subscription_notes:v})}
    />

    {selectedPlan&&commercial&&
      <div className="md:col-span-2 rounded-lg border border-gray-200 bg-gray-50 p-4">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold">Commercial Statement</h3>
            <p className="text-xs text-gray-500">Review the calculated agreement before creating the Society/Trust.</p>
          </div>
          <span className="text-sm font-medium">{selectedPlan.name}</span>
        </div>

        {isTrial?
          <div className="grid md:grid-cols-3 gap-4 text-sm">
            <Info label="Schools" value={String(commercial.schools)}/>
            <Info label="Billing" value="Trial"/>
            <Info label="Trial Period" value={`${selectedPlan.trial_days||30} days`}/>
            <Info label="Gross Amount" value={formatINR(0)}/>
            <Info label="Discount" value={formatINR(0)}/>
            <Info label="Net Payable" value={formatINR(0)}/>
            <Info label="Activation Payment" value="Not Required"/>
            <Info label="Tax Type" value="Non-GST"/>
          </div>
        :
          <div className="grid md:grid-cols-3 gap-4 text-sm">
            <Info label="Schools" value={String(commercial.schools)}/>
            <Info label="Billing" value={form.billing_cycle==="monthly"?"Monthly":"Yearly"}/>
            <Info label="Gross Amount" value={formatINR(commercial.gross)}/>
            <Info label="Discount" value={formatINR(commercial.discount)}/>
            <Info label="Taxable Amount" value={formatINR(commercial.taxable)}/>
            <Info label="Tax Type" value={form.tax_mode==="gst"?`GST ${commercial.gstRate}%`:"Non-GST"}/>
            <Info label="GST Amount" value={formatINR(commercial.gst)}/>
            <Info label="Net Payable" value={formatINR(commercial.netPayable)}/>
            <Info label="Minimum Activation Payment" value={formatINR(commercial.activationMinimum)}/>
            <Info label="Balance after Minimum Payment" value={formatINR(commercial.balanceAfterMinimum)}/>
            <Info label="Payment Due Date" value={form.payment_due_at||"Not selected"}/>
          </div>
        }
      </div>
    }

    <div className="md:col-span-2 flex gap-2">
      <button disabled={saving} className="btn-primary">
        Review & Create Society/Trust
      </button>
      <button
        type="button"
        className="btn-secondary"
        onClick={()=>{setShowForm(false);setCommercialSnapshot(null);setShowCommercialConfirm(false);navigate("/organizations?view=list");}}
        disabled={saving}
      >
        Cancel
      </button>
    </div>
  </form>}
  {editOrganization&&<form onSubmit={saveOrganizationDetails} className="card grid md:grid-cols-2 gap-4">
    <div className="md:col-span-2"><h2 className="font-semibold">Edit Society/Trust</h2><p className="text-xs text-gray-500 mt-1">Commercial plan, billing and school limit are managed separately.</p></div>
    <Field label="Society/Trust Name" value={form.name} onChange={v=>setForm({...form,name:v})}/>
    <label><span className="label">Society/Trust Code</span><input className="input bg-gray-100" value={editOrganization.code} disabled/></label>
    <Field label="Admin Person Name" value={form.head_full_name} onChange={v=>setForm({...form,head_full_name:v})}/>
    <SelectField label="Designation" value={form.admin_designation} options={ORG_ADMIN_DESIGNATIONS} onChange={v=>setForm({...form,admin_designation:v})}/>
    <Field label="Admin Contact / Login Email" type="email" value={form.head_email} onChange={v=>setForm({...form,head_email:v})}/>
    <Field label="Admin Phone" value={form.head_phone} onChange={v=>setForm({...form,head_phone:v.replace(/\D/g,"").slice(0,10)})}/>
    <label><span className="label">School Limit</span><input className="input bg-gray-100" value={String(editOrganization.allowed_schools)} disabled/></label>
    <label><span className="label">Username</span><input className="input bg-gray-100" value={editOrganization.admin_username||""} disabled/></label>
    <div className="md:col-span-2 flex gap-2"><button className="btn-primary" disabled={saving}>{saving?"Saving...":"Save Changes"}</button><button type="button" className="btn-secondary" disabled={saving} onClick={()=>{setEditOrganization(null);setEditAdmin(null);setForm(emptyForm);navigate("/organizations?view=detail");}}>Cancel</button></div>
  </form>}
  {editAdmin&&<form onSubmit={saveAdmin} className="card grid md:grid-cols-2 gap-4"><h2 className="md:col-span-2 font-semibold">Edit Organization Admin Profile</h2><Field label="Admin Person Name" value={adminForm.full_name} onChange={v=>setAdminForm({...adminForm,full_name:v})}/><SelectField label="Designation" value={adminForm.designation} options={ORG_ADMIN_DESIGNATIONS} onChange={v=>setAdminForm({...adminForm,designation:v})}/><Field label="Email" type="email" value={adminForm.email} onChange={v=>setAdminForm({...adminForm,email:v})}/><Field label="Phone" value={adminForm.phone} onChange={v=>setAdminForm({...adminForm,phone:v.replace(/\D/g,"").slice(0,10)})}/><div className="md:col-span-2 flex gap-2"><button className="btn-primary">Save Profile</button><button type="button" className="btn-secondary" onClick={()=>{setEditAdmin(null);navigate("/organizations?view=detail")}}>Cancel</button></div></form>}
  {!selected&&!editOrganization&&!editAdmin&&<><div className="card">
    <div className="relative">
      <Search size={18} className="absolute left-3 top-3 text-gray-400"/>
      <input className="input pl-10" placeholder="Search Society/Trust, ID, Admin, email, phone or plan" value={query} onChange={e=>setQuery(e.target.value)}/>
    </div>
  </div>
  {loading?<div>Loading...</div>:<div className="card overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="p-3">Society/Trust</th>
          <th>Org Admin</th>
          <th>Phone</th>
          <th>Plan</th>
          <th>Schools</th>
          <th>Status</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {filtered.map(o=>{
          const subscription=subscriptionByOrganization.get(o.id);
          return <tr key={o.id} className="border-b">
            <td className="p-3"><b>{o.name}</b><div className="font-mono text-xs text-gray-500">{o.code}</div></td>
            <td>{o.admin_full_name||o.head_full_name||"—"}<div className="text-xs text-gray-500">{o.admin_email||o.head_email||"—"}</div></td>
            <td>{displayPhone(o.admin_phone||o.head_phone)}</td>
            <td><span className="font-medium">{subscription?.plan_name||"—"}</span></td>
            <td>{activeSchoolCountByOrganization.get(o.id)||0} / {o.allowed_schools}</td>
            <td>{o.archived_at?"Archived":o.is_active?"Active":"Disabled"}</td>
            <td><button className="btn-secondary text-xs" onClick={()=>{setSelected(o);setShowForm(false);setEditAdmin(null);navigate("/organizations?view=detail");}}>View</button></td>
          </tr>;
        })}
      </tbody>
    </table>
  </div>}
  </>}
  {selected&&!editOrganization&&!editAdmin&&<div className="space-y-5">
    <div className="card flex flex-col justify-between gap-5 lg:flex-row lg:items-center"><div><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{selected.name}</h1><span className={`rounded-full px-3 py-1 text-xs font-semibold ${selected.is_active?"bg-emerald-50 text-emerald-700":"bg-rose-50 text-rose-700"}`}>● {selected.is_active?"Active":"Disabled"}</span></div><p className="mt-2 text-sm text-slate-500">ERP Code: <b className="font-mono text-blue-700">{selected.code}</b></p><p className="mt-1 text-sm text-slate-500">Society/Trust governance, Schools and commercial administration.</p></div><div className="flex gap-2"><button className="btn-secondary" onClick={()=>{setSelected(null);setEditAdmin(null);navigate("/organizations?view=list")}}>← Back to Society/Trust List</button>{user?.is_superuser&&<button className="btn-primary" onClick={()=>void openEditOrganization(selected)}>Edit Details</button>}</div></div>
    <div className="grid gap-4 md:grid-cols-3"><div className="card"><Info label="Organization Admin" value={selected.admin_full_name||selected.head_full_name||"—"}/></div><div className="card"><Info label="Admin Email" value={selected.admin_email||selected.head_email||"—"}/></div><div className="card"><Info label="Schools (Active / Total)" value={`${activeSchoolCountByOrganization.get(selected.id)||0} / ${selected.allowed_schools}`}/></div></div>
    <div className="grid gap-4 xl:grid-cols-[1fr_2fr]"><div className="card"><h2 className="text-lg font-semibold">Society/Trust Profile</h2><div className="mt-4 space-y-4"><Info label="Society/Trust Name" value={selected.name}/><Info label="ERP Code" value={selected.code}/><Info label="Admin Phone" value={displayPhone(selected.admin_phone||selected.head_phone)}/><Info label="Status" value={selected.is_active?"Active":"Disabled"}/></div></div><div className="space-y-4"><div className="card"><h2 className="text-lg font-semibold">Quick Actions</h2><p className="mt-1 text-sm text-slate-500">Common Society/Trust governance actions.</p>{user?.is_superuser&&<div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><button className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-left font-semibold text-blue-800" onClick={()=>void openEditOrganization(selected)}>Edit Details</button><button className="rounded-xl border border-violet-100 bg-violet-50 p-4 text-left font-semibold text-violet-800" onClick={()=>void openAdmin(selected)}>Manage Admin</button><button className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-left font-semibold text-amber-800" onClick={()=>navigate(`/subscriptions?tab=subscriptions&organization=${selected.id}`)}>Subscription & Payments</button><button className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-left font-semibold text-emerald-800" onClick={()=>navigate(`/schools?view=list&organization=${selected.id}`)}>Manage Schools</button></div>}</div><div className="card"><div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold">Schools under this Society/Trust</h2><p className="text-sm text-slate-500">Schools managed by this Society/Trust.</p></div></div><div className="mt-4 overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-slate-500"><th className="py-2">School</th><th>ERP Code</th><th>Status</th></tr></thead><tbody>{schools.filter(x=>x.organization_id===selected.id).map(x=><tr key={x.id} className="border-b last:border-0"><td className="py-3 font-medium">{x.configuration?.name||x.code}</td><td>{x.code}</td><td>{x.is_active?"Active":"Inactive"}</td></tr>)}</tbody></table></div></div>{user?.is_superuser&&<div className="card"><div className="flex flex-wrap gap-2"><button className="btn-secondary" onClick={()=>void resetTemp(selected)}><KeyRound size={14}/> Reset Temporary Password</button><button className="btn-secondary" onClick={()=>void resend(selected)}>Resend Email</button><button className="btn-secondary" onClick={()=>{setReason("");setEmergencyOverride(false);setError("");setStatusTarget(selected)}}>{selected.is_active?"Disable":"Enable"}</button></div></div>}</div></div>
  </div>}
  {statusTarget&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
    <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
      <div className="border-b p-5"><h2 className="text-lg font-semibold">{statusTarget.is_active?"Disable":"Enable"} Society/Trust</h2><p className="mt-1 text-sm text-gray-500">{statusTarget.name}</p></div>
      <div className="p-5 space-y-4"><label><span className="label">Reason <RedStar/></span><textarea className="input min-h-28" maxLength={500} required value={reason} onChange={e=>setReason(e.target.value)} placeholder={`Enter reason to ${statusTarget.is_active?"disable":"enable"} this Society/Trust`}/></label>{statusTarget.is_active&&<label className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><input type="checkbox" className="mt-1" checked={emergencyOverride} onChange={e=>setEmergencyOverride(e.target.checked)}/><span><b>Emergency suspension override</b><br/>Use this only when an active Society/Trust must be suspended immediately for compliance, fraud, safety, or similar governance reasons. The reason and override are audited.</span></label>}</div>
      <div className="flex justify-end gap-2 border-t p-5"><button type="button" className="btn-secondary" onClick={()=>{setStatusTarget(null);setReason("");setEmergencyOverride(false);}}>Cancel</button><button type="button" className={statusTarget.is_active?"btn-secondary":"btn-primary"} onClick={()=>void status(statusTarget)} disabled={!reason.trim()}>{statusTarget.is_active?"Disable":"Enable"}</button></div>
    </div>
  </div>}
  {showCommercialConfirm&&commercialSnapshot&&(()=>{
    const snapshot=commercialSnapshot;
    const agreedForm=snapshot.form;
    const agreedCommercial=snapshot.commercial;
    const agreedPlan=snapshot.plan;
    const agreedIsTrial=snapshot.planCode==="TRIAL";

    return <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="commercial-agreement-title"
    >
      <div className="w-full max-w-3xl rounded-xl bg-white shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="border-b p-5">
          <h2 id="commercial-agreement-title" className="text-lg font-semibold">
            Confirm Commercial Agreement
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Verify the finalized commercial terms before creating the Society/Trust.
          </p>
        </div>

        <div className="p-5 space-y-5">
          <div className="grid md:grid-cols-3 gap-4 text-sm">
            <Info label="Plan" value={agreedPlan.name}/>
            <Info label="Schools" value={String(agreedCommercial.schools)}/>
            <Info
              label="Billing"
              value={agreedIsTrial?"Trial":agreedForm.billing_cycle==="monthly"?"Monthly":"Yearly"}
            />
          </div>

          {agreedIsTrial?
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="grid md:grid-cols-3 gap-4 text-sm">
                <Info label="Gross Amount" value={formatINR(0)}/>
                <Info label="Discount" value={formatINR(0)}/>
                <Info label="Net Payable" value={formatINR(0)}/>
                <Info label="Tax Type" value="Non-GST"/>
                <Info label="Activation Payment" value="Not Required"/>
                <Info
                  label="Trial Expiry"
                  value={`${agreedPlan.trial_days||30} days from creation`}
                />
              </div>
            </div>
          :
            <div className="rounded-lg border bg-gray-50 p-4">
              <div className="grid md:grid-cols-3 gap-4 text-sm">
                <Info label="Gross Amount" value={formatINR(agreedCommercial.gross)}/>
                <Info label="Discount" value={formatINR(agreedCommercial.discount)}/>
                <Info label="Taxable Amount" value={formatINR(agreedCommercial.taxable)}/>
                <Info
                  label="Tax Type"
                  value={agreedForm.tax_mode==="gst"?`GST ${agreedCommercial.gstRate}%`:"Non-GST"}
                />
                <Info label="GST Amount" value={formatINR(agreedCommercial.gst)}/>
                <Info label="Net Payable" value={formatINR(agreedCommercial.netPayable)}/>
                <Info
                  label="Minimum Activation Payment"
                  value={formatINR(agreedCommercial.activationMinimum)}
                />
                <Info
                  label="Balance after Minimum Payment"
                  value={formatINR(agreedCommercial.balanceAfterMinimum)}
                />
                <Info
                  label="Payment Due Date"
                  value={agreedForm.payment_due_at||"Not selected"}
                />
              </div>

              {agreedForm.activation_minimum_amount&&
                <div className="mt-4 rounded-lg border p-3 text-sm">
                  <div className="font-medium">Activation Minimum Override</div>
                  <div className="mt-1 text-gray-600">
                    System 50% minimum: {formatINR(agreedCommercial.calculatedMinimum)}
                  </div>
                  <div className="text-gray-600">
                    Agreed minimum: {formatINR(agreedCommercial.activationMinimum)}
                  </div>
                  <div className="text-gray-600">
                    Reason: {agreedForm.activation_override_reason}
                  </div>
                </div>
              }
            </div>
          }

          {agreedForm.discount_type!=="none"&&!agreedIsTrial&&
            <div className="text-sm">
              <span className="font-medium">Discount Reason: </span>
              {agreedForm.discount_reason}
            </div>
          }

          {agreedForm.subscription_notes.trim()&&
            <div className="text-sm">
              <span className="font-medium">Agreed Terms / Notes: </span>
              {agreedForm.subscription_notes}
            </div>
          }

          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
            By selecting Confirm & Create, these reviewed commercial terms will be used
            to create the Society/Trust, Organization Admin and subscription agreement.
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t p-5">
          <button
            type="button"
            className="btn-secondary"
            disabled={saving}
            onClick={()=>{
              setShowCommercialConfirm(false);
              setCommercialSnapshot(null);
            }}
          >
            Cancel
          </button>

          <button
            type="button"
            className="btn-primary"
            disabled={saving}
            onClick={()=>void confirmCreate()}
          >
            {saving?"Creating...":"Confirm & Create"}
          </button>
        </div>
      </div>
    </div>;
  })()}

 </div>
}
function RedStar(){return <span className="text-red-600">*</span>}
function Field({label,value,onChange,type="text",required=true}:{label:string;value:string;onChange:(v:string)=>void;type?:string;required?:boolean}){return <label><span className="label">{label} {required&&<RedStar/>}</span><input className="input" type={type} required={required} value={value} onChange={e=>onChange(e.target.value)}/></label>}
function formatINR(value:number){
  return new Intl.NumberFormat("en-IN",{
    style:"currency",
    currency:"INR",
    minimumFractionDigits:2,
    maximumFractionDigits:2
  }).format(Number.isFinite(value)?value:0);
}

function SelectField({label,value,options,onChange}:{label:string;value:string;options:readonly string[];onChange:(v:string)=>void}){return <label><span className="label">{label} <RedStar/></span><select required className="input" value={value} onChange={e=>onChange(e.target.value)}><option value="">Select Designation</option>{options.map(option=><option key={option} value={option}>{option}</option>)}</select></label>}
function Info({label,value}:{label:string;value:string}){return <div><div className="text-xs text-gray-500">{label}</div><div className="font-medium">{value}</div></div>}