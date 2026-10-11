import {UserManager,WebStorageStateStore} from 'oidc-client-ts';
type Config={mode:string;authority:string;clientId:string;scope:string;appUrl:string};
let configPromise:Promise<Config>|undefined;
let managerPromise:Promise<UserManager>|undefined;
let developmentKey='';
export function config(){return configPromise??=(fetch('/api/config').then(async r=>{if(!r.ok)throw new Error('Authentication configuration unavailable');return r.json()}))}
export function setDevelopmentKey(key:string){developmentKey=key}
export async function manager(){return managerPromise??=(config().then(c=>new UserManager({authority:c.authority,client_id:c.clientId,redirect_uri:c.appUrl+'/',post_logout_redirect_uri:c.appUrl+'/',response_type:'code',scope:c.scope,automaticSilentRenew:false,userStore:new WebStorageStateStore({store:window.sessionStorage})})))}
export async function authHeaders():Promise<Record<string,string>>{
  const c=await config();
  if(c.mode==='development')return developmentKey?{'X-API-Key':developmentKey}:{};
  const user=await (await manager()).getUser();
  if(!user||user.expired)return {};
  return {Authorization:'Bearer '+user.access_token};
}
export async function apiFetch(path:string,init:RequestInit={}){
  if(!path.startsWith('/api/'))throw new Error('Only same-origin API paths are allowed');
  return fetch(path,{...init,headers:{...await authHeaders(),...init.headers},cache:'no-store'});
}
