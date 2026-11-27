export type User={id:string;email:string;display_name:string;is_active:boolean;roles:string[];date_joined:string;session_version:number};
export type Session={user:User|null;csrf_token:string;permissions:{manage_accounts:boolean;view_audit:boolean;view_categories:boolean;manage_categories:boolean;view_directory:boolean;manage_directory:boolean;view_private_contacts:boolean;view_media:boolean;manage_media:boolean;view_events:boolean;create_events:boolean;review_events:boolean;manage_events:boolean;view_issues:boolean;manage_issues:boolean}};
export type Page<T>={count:number;next:string|null;previous:string|null;results:T[]};
export type Audit={id:string;actor_id:string|null;action:string;target_id:string|null;created_at:string;details:Record<string,unknown>};
let token='';
export async function api<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const res=await fetch('/api/v1/admin/'+path,{method,credentials:'same-origin',headers:{'Accept':'application/json',...(method!=='GET'?{...(body instanceof FormData?{}:{'Content-Type':'application/json'}),'X-CSRFToken':token}:{})},...(body!==undefined?{body:body instanceof FormData?body:JSON.stringify(body)}:{})});
  if(res.status===204)return undefined as T;
  const data=await res.json().catch(()=>null);
  if(!res.ok){const msg=data?.message||'Request failed';const fields=data?.fields;throw new Error(`${msg}${fields?' '+JSON.stringify(fields):''}`);}
  if(data?.csrf_token)token=data.csrf_token;
  return data as T;
}
